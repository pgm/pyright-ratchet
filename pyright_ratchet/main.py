import os
import subprocess
import re
import sys
from typing  import Set
import argparse

PAST_ERRORS_FILE = "pyright-ratchet-errors.txt"

def exec_command(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result.stdout.decode("utf8").split("\n")

def run_cmd(args, include_stdout):
    if args == []:
        args = ["pyright"]

    output = exec_command(args)
    errors = parse_output(output)
    line_to_simplified = dict(errors)
    past_errors = load_errors()
    new_errors = []
    unseen_errors = set(past_errors)

    for line in output:
        if line in line_to_simplified:
            # if this line is an error, see if its new or not
            error = line_to_simplified[line]
            if error in past_errors:
                if include_stdout:
                    print(f"(ignoring due to ratchet) {line}")
            else:
                new_errors.append(line)
                if include_stdout:
                    print(f"(new error) {line}")
            if error in unseen_errors:
                unseen_errors.remove(error)
        else:
            if include_stdout:
                print(line)
    
    print(f"{len(new_errors)} new errors")
    if len(unseen_errors) > 0:
        print(f"{len(unseen_errors)} past errors have been fixed. Removing these from the list of ignored errors.")
        save_errors(past_errors.difference(unseen_errors))

    for new_error in new_errors:
        print(new_error)

    if len(new_errors) > 0:
        return 1

def tighten_cmd(args):
    if args == []:
        args = ["pyright"]
    output = exec_command(args)
    lines_with_error = parse_output(output)
    past_errors = load_errors()
    print_comparison(past_errors, set([simplified for line, simplified in lines_with_error]))
    unique_error_count = save_errors([error for _, error in lines_with_error])
    print(f"Recorded {unique_error_count} errors to {PAST_ERRORS_FILE}")

def save_errors(errors : Set):
    errors = sorted(set(errors))
    with open(PAST_ERRORS_FILE, "wt") as fd:
        for error in errors:
            fd.write(f"{error}\n")
    return len(errors)

def load_errors():
    if not os.path.exists(PAST_ERRORS_FILE):
        return set()
        
    errors = set()
    with open(PAST_ERRORS_FILE, "rt") as fd:
        for line in fd:
            errors.add(line.strip())
    return errors

def print_comparison(past_errors, new_errors):
    fixed_errors = past_errors.difference(new_errors)
    regressions = new_errors.difference(past_errors)
    #assert len(regressions) == 0
    print(f"Fixed {len(fixed_errors)} errors")

def main():
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()
    
    run_parser = subparser.add_parser("run")
    run_parser.add_argument("--only-changes", dest="include_stdout", action="store_false", help="if set, only outputs the different between expected errors and current errors")
    run_parser.add_argument("args", nargs="*")
    run_parser.set_defaults(func=lambda args: run_cmd(args.args, args.include_stdout))

    tighten_parser = subparser.add_parser("tighten")
    tighten_parser.add_argument("args", nargs="*")
    tighten_parser.set_defaults(func=lambda args: tighten_cmd(args.args))
    
    def _default_cmd(args):
        run_cmd([], True)

    parser.set_defaults(func=_default_cmd)
    args = parser.parse_args()

    ret = args.func(args)
    if ret:
        sys.exit(ret)

def parse_output(output):
    error_count = None
    errors = []
    lines = [line for line in output]
    for line in lines:
        m = re.match("([^:]+):(\\d+):(\\d+) - (error: .*)", line)
        if m:
            filename, lineno, pos, error_msg = m.groups()
            filename = filename.strip().split("/")[-1]
            simplified_error = f"{filename}: {error_msg}"
            errors.append((line, simplified_error))

        m = re.match("(\\d+) errors?, \\d+ warnings?, \\d+ informations?", line)
        if m:
            error_count = int(m.group(1))
            
    assert error_count is not None, f"Could not find line with summary in output: {lines}"
    assert error_count == len(errors)
    return errors

