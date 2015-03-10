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
from hunittest.test_resultlib import HTestResult
from hunittest.filter_rules import RuleOperator
from hunittest.filter_rules import FilterAction
from hunittest.filter_rules import PatternType
from hunittest.filter_rules import FilterRules
from hunittest.collectlib import collect_all
from hunittest.completionlib import test_spec_completer

try:
    import argcomplete
except ImportError:
    sys.stderr.write("info: you can get shell completion by installing "
                     "'argcomplete'")
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
    # Force all module we are going to load to comes from the current
    # working directory. Otherwise, since a package call "test" may appears
    # multiple times in the PYTHONPATH we will got the wrong one.
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    cli = build_cli()
    if ARGCOMPLETE_ENABLED:
        argcomplete.autocomplete(cli)
    options = cli.parse_args(argv[1:])
    if options.version:
        print(get_version())
        return 0
    filter_rules = options.filter_rules
    if filter_rules is None:
        filter_rules = FilterRules()
    test_specs = options.test_specs
    if not test_specs:
        test_specs = list(get_current_packages())
    isatty = False if options.verbose else None
    printer = LinePrinter(isatty=isatty, quiet=options.quiet)
    test_names = reported_collect(printer, test_specs, options.pattern,
                                  filter_rules)
    if options.collect_only:
        printer.new_line()
        return 0
    test_suite = unittest.defaultTestLoader.loadTestsFromNames(test_names)
    result = HTestResult(printer, len(test_names), failfast=options.failfast)
    test_suite.run(result)
    result.print_summary()
    printer.new_line()
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
