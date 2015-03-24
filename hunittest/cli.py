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
from contextlib import contextmanager
import re
import shutil

from hunittest.line_printer import LinePrinter
from hunittest.unittestresultlib import HTestResult
from hunittest.filter_rules import RuleOperator
from hunittest.filter_rules import FilterAction
from hunittest.filter_rules import PatternType
from hunittest.filter_rules import FilterRules
from hunittest.collectlib import collect_all
from hunittest.completionlib import test_spec_completer
from hunittest.collectlib import setup_top_level_directory
from hunittest.collectlib import get_test_spec_last_pkg
from hunittest.utils import AutoEnum

try:
    import argcomplete
except ImportError:
    sys.stderr.write("info: you can get shell completion by installing "
                     "'argcomplete'\n")
    ARGCOMPLETE_ENABLED = False
else:
    ARGCOMPLETE_ENABLED = True

try:
    import coverage
except ImportError:
    COVERAGE_ENABLED = False
else:
    COVERAGE_ENABLED = True

def reported_collect(printer, test_specs, pattern, filter_rules,
                     top_level_directory):
    collection = collect_all(test_specs, pattern, top_level_directory)
    test_names = []
    for n, test_name in enumerate(filter_rules(collection)):
        prefix = "collecting {:d}: ".format(n+1)
        msg = test_name
        printer.overwrite_message(prefix, msg, ellipse_index=1)
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

EPILOGUE = \
"""
Exit code:
 0 - test suite was successful
 1 - test suite was not successful
 2 - an internal error happened.

Environment variables:
 PAGER - the pager to use (see --pager)
 HUNITTEST_LOG_FILE - name of the file where error are logged

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

def get_coverage_omit_list(options):
    l = [os.path.join(os.path.dirname(__file__), "*")] # myself
    for test_spec in options.test_specs:
        pkgname = get_test_spec_last_pkg(test_spec)
        path = re.subn(r"\.", "/", pkgname)[0]
        path = os.path.join(path, "*")
        l.append(path)
    return l

@contextmanager
def coverage_instrument(options):
    cov = None
    if COVERAGE_ENABLED and options.coverage_html:
        cov = coverage.Coverage()
    try:
        if cov is not None:
            cov.start()
        yield
    finally:
        if cov is not None:
            cov.stop()
            cov.save()
            cov.html_report(directory=options.coverage_html,
                            omit=get_coverage_omit_list(options))

class PagerMode(AutoEnum):
    auto = ()
    never = ()

def spawn_pager(filename):
    pager = os.environ.get("PAGER", "less")
    executable = shutil.which(pager)
    os.execvp(executable, [pager, filename])

def maybe_spawn_pager(options, log_filename):
    if options.quiet:
        return
    if options.pager is PagerMode.auto:
        spawn_pager(log_filename)
    elif options.pager is PagerMode.never:
        pass
    else:
        raise ValueError("invalid pager option: {}".format(options.pager))

def build_cli():
    class RawDescriptionWithArgumentDefaultsHelpFormatter(
            argparse.ArgumentDefaultsHelpFormatter,
            argparse.RawDescriptionHelpFormatter,
    ):
        """Mix both formatter."""
    def top_level_directory_param(param_str):
        top_level_directory = param_str
        for preproc in (os.path.expanduser,
                        os.path.expandvars,
                        os.path.abspath,
                        os.path.realpath):
            top_level_directory = preproc(top_level_directory)
        if not os.path.isdir(top_level_directory):
            raise argparse.ArgumentTypeError("must be a directory: '{}'"
                                             .format(param_str))
        assert os.path.isabs(top_level_directory)
        return top_level_directory
    def pager_param(param_str):
        # Cannot raise AttributeError since the choices is limited by argparse.
        return getattr(PagerMode, param_str)
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=dedent(EPILOGUE),
        formatter_class=RawDescriptionWithArgumentDefaultsHelpFormatter)
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
    # TODO(Nicolas Despres): Introduce a ColorMode enumeration
    parser.add_argument(
        "-C", "--color",
        action="store",
        choices=("auto", "always", "never"),
        default="auto",
        help="Whether to use color.")
    if COVERAGE_ENABLED:
        coverage_html_help = "Where to store the html report"
    else:
        coverage_html_help = "install 'coverage' to support enable this option"
    parser.add_argument(
        "--coverage-html",
        action="store",
        help=coverage_html_help)
    parser.add_argument(
        "--pager",
        type=pager_param,
        action="store",
        choices=[pm.name for pm in PagerMode],
        default=PagerMode.auto.name,
        help="Automatically pipe the result to a pager.")
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
    if options.pager is PagerMode.auto:
        log_filename = os.environ.get("HUNITTEST_LOG_FILE", ".hunittest.log")
    elif options.pager is PagerMode.never:
        log_filename = None
    else:
        raise ValueError("invalid pager option: {!r}".format(options.pager))
    result = None
    with LinePrinter(isatty=isatty, quiet=options.quiet,
                     color_mode=options.color) as printer:
        try:
            test_names = reported_collect(printer, test_specs, options.pattern,
                                          filter_rules,
                                          options.top_level_directory)
            if options.collect_only:
                printer.new_line()
                return 0
            test_suite = unittest.defaultTestLoader \
                                 .loadTestsFromNames(test_names)
            result = HTestResult(printer, len(test_names),
                                 failfast=options.failfast,
                                 log_filename=log_filename)
            with coverage_instrument(options):
                test_suite.run(result)
            result.print_summary()
            printer.new_line()
        except Exception as e:
            printer.write_exception()
            return 2
        finally:
            if result is not None:
                result.close_log_file()
    if result.wasSuccessful():
        return 0
    else:
        maybe_spawn_pager(options, log_filename)
        # maybe_spawn_pager may never return if the pager has been
        # spawned. Otherwise we return 1.
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
