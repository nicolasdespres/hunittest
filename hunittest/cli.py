# -*- encoding: utf-8 -*-
"""Highlighted unittest command line interface.
"""

import sys
import argparse
import os
import unittest
import operator
import time
from textwrap import dedent
import subprocess

from hunittest.line_printer import LinePrinter
from hunittest.unittestresultlib import HTestResult
from hunittest.filter_rules import RuleOperator
from hunittest.filter_rules import FilterAction
from hunittest.filter_rules import PatternType
from hunittest.filter_rules import FilterRules
from hunittest.collectlib import collect_all
from hunittest.completionlib import test_spec_completer
from hunittest.collectlib import setup_top_level_directory

try:
    import argcomplete
except ImportError:
    sys.stderr.write("info: you can get shell completion by installing "
                     "'argcomplete'\n")
    ARGCOMPLETE_ENABLED = False
else:
    ARGCOMPLETE_ENABLED = True


def reported_collect(printer, test_specs, pattern, filter_rules):
    collection = collect_all(test_specs, pattern)
    test_names = []
    for n, test_name in enumerate(filter_rules(collection)):
        printer.overwrite("collecting {:d}: {}"
                          .format(n+1, test_name))
        test_names.append(test_name)
    if len(test_names) == 0:
        printer.overwrite("no test collected")
    else:
        printer.overwrite("collected {:d} test(s)".format(len(test_names)))
    return test_names

def complete_arg(arg, completer):
    if ARGCOMPLETE_ENABLED:
        arg.completer = completer
    return arg

EPILOG = \
"""
Exit code:
0 - test suite was successful
1 - test suite was not successful
2 - an internal error happened.

Copyright (c) 2015, Nicolas Desprès
All rights reserved.
"""

def git_describe(cwd="."):
    """Return the description of this repository.

    This function use git-describe(1) because the features is not available
    in pygit2 version 0.22.0.
    """
    # TODO(Nicolas Despres): Use pygit2 ASAP.
    cmd = ["git", "describe", "--always", "--dirty", "--match", "v*"]
    description = subprocess.check_output(cmd, cwd=cwd)
    return description.decode().strip()

def get_version():
    return git_describe(cwd=os.path.dirname(os.path.realpath(__file__)))

def build_cli():
    def top_level_directory_param(param_str):
        top_level_directory = param_str
        for preproc in (os.path.expanduser,
                        os.path.expandvars,
                        os.path.abspath):
            top_level_directory = preproc(top_level_directory)
        if not os.path.isdir(top_level_directory):
            raise argparse.ArgumentTypeError("must be a directory: '{}'"
                                             .format(param_str))
        return top_level_directory
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=dedent(EPILOG),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Disable smart terminal output.")
    parser.add_argument(
        "-p", "--pattern",
        action="store",
        default=r"^test_",
        help="Only module name matching this pattern gets collected")
    parser.add_argument(
        "-e", "--exclude",
        metavar="GLOB_PATTERN",
        action=FilterAction,
        filter_rule_operator=RuleOperator.exclude,
        pattern_type=PatternType.glob,
        help="Add an exclude glob pattern filter rule.")
    parser.add_argument(
        "-i", "--include",
        metavar="GLOB_PATTERN",
        action=FilterAction,
        filter_rule_operator=RuleOperator.include,
        pattern_type=PatternType.glob,
        help="Add an include glob pattern filter rule.")
    parser.add_argument(
        "--re",
        metavar="REGEX_PATTERN",
        action=FilterAction,
        filter_rule_operator=RuleOperator.exclude,
        pattern_type=PatternType.regex,
        help="Add an exclude regex pattern filter rule.")
    parser.add_argument(
        "--ri",
        metavar="REGEX_PATTERN",
        action=FilterAction,
        filter_rule_operator=RuleOperator.include,
        pattern_type=PatternType.regex,
        help="Add an include regex pattern filter rule.")
    parser.add_argument(
        "-c", "--collect-only",
        action="store_true",
        help="Only collect test (do not run anything).")
    parser.add_argument(
        "-f", "--failfast",
        action="store_true",
        help="Stop on first failure")
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Print nothing. Exit status is the outcome.")
    parser.add_argument(
        "-t", "--top-level-directory",
        type=top_level_directory_param,
        action="store",
        default=os.getcwd(),
        help="Top level directory of project")
    parser.add_argument(
        "-C", "--color",
        action="store",
        choices=("auto", "always", "never"),
        default="auto",
        help="Whether to use color.")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version information and exit")
    arg = parser.add_argument(
        "test_specs",
        action="store",
        nargs=argparse.REMAINDER,
        default=None,
        help="Test directory/module/TestCase/test_method.")
    complete_arg(arg, test_spec_completer)
    return parser

def main(argv):
    cli = build_cli()
    if ARGCOMPLETE_ENABLED:
        argcomplete.autocomplete(cli)
    options = cli.parse_args(argv[1:])
    if options.version:
        print(get_version())
        return 0
    setup_top_level_directory(options.top_level_directory)
    filter_rules = options.filter_rules
    if filter_rules is None:
        filter_rules = FilterRules()
    test_specs = options.test_specs
    if not test_specs:
        test_specs = list(get_current_packages())
    isatty = False if options.verbose else None
    with LinePrinter(isatty=isatty, quiet=options.quiet,
                     color_mode=options.color) as printer:
        try:
            test_names = reported_collect(printer, test_specs, options.pattern,
                                          filter_rules)
            if options.collect_only:
                printer.new_line()
                return 0
            test_suite = unittest.defaultTestLoader \
                                 .loadTestsFromNames(test_names)
            result = HTestResult(printer, len(test_names),
                                 failfast=options.failfast)
            test_suite.run(result)
            result.print_summary()
            printer.new_line()
            return 0 if result.wasSuccessful() else 1
        except Exception as e:
            printer.write_exception()
            return 2

if __name__ == "__main__":
    sys.exit(main(sys.argv))
