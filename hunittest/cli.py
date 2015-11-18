# -*- encoding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
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
import hashlib

from hunittest.line_printer import LinePrinter
from hunittest.unittestresultlib import HTestResult
from hunittest.filter_rules import RuleOperator
from hunittest.filter_rules import FilterAction
from hunittest.filter_rules import PatternType
from hunittest.filter_rules import FilterRules
from hunittest.collectlib import collect_all
from hunittest.completionlib import test_spec_completer
from hunittest.completionlib import list_packages_from
from hunittest.collectlib import setup_top_level_directory
from hunittest.collectlib import get_test_spec_last_pkg
from hunittest.utils import AutoEnum
from hunittest.utils import mkdir_p
from hunittest import envar

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
    printer.overwrite("Loading previous errors...")
    previous_errors = load_error_test_specs()
    collection = collect_all(test_specs, pattern, top_level_directory)
    test_names = []
    for n, test_name in enumerate(filter_rules(collection)):
        prefix = "collecting {:d}: ".format(n+1)
        msg = test_name
        printer.overwrite_message(prefix, msg, ellipse_index=1)
        if test_name in previous_errors:
            test_names.insert(0, test_name)
        else:
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

DEFAULT_WORKDIR = ".hunittest"
DEFAULT_PAGER = "less"

def get_workdir():
    return os.environ.get(envar.WORKDIR, DEFAULT_WORKDIR)

def get_log_filename():
    return os.path.join(get_workdir(), "log")

def get_error_filename():
    return os.path.join(get_workdir(), "error")

def get_status_filename(options):
    """Build status filename based on the options."""
    m = hashlib.md5()
    m.update(" ".join(options.test_specs).encode())
    m.update(os.path.realpath(options.top_level_directory).encode())
    m.update(repr(options.filter_rules).encode())
    m.update(options.pattern.encode())
    return os.path.join(get_workdir(), "status", m.hexdigest(), "status.json")

EPILOGUE = \
"""
Exit code:
 0 - test suite was successful
 1 - test suite was not successful
 2 - an internal error happened.

Environment variables:
 PAGER - the pager to use (see --pager) (default: {default_pager})
 {envar_workdir} - directory where hunittest stores its stuff
                     (default: {default_workdir})

Copyright (c) 2015, Nicolas Desprès
All rights reserved.
""".format(
    default_pager=DEFAULT_PAGER,
    envar_workdir=envar.WORKDIR,
    default_workdir=DEFAULT_WORKDIR,
)

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
        data_file = os.path.join(options.coverage_html, "coverage.data")
        cov = coverage.Coverage(data_file=data_file)
    try:
        if cov is not None:
            cov.start()
        yield
    finally:
        if cov is not None:
            cov.stop()
            mkdir_p(options.coverage_html)
            cov.save()
            cov.html_report(directory=options.coverage_html,
                            omit=get_coverage_omit_list(options))

class PagerMode(AutoEnum):
    auto = ()
    never = ()

def spawn_pager(filename):
    pager = os.environ.get("PAGER", DEFAULT_PAGER)
    executable = shutil.which(pager)
    os.execvp(executable, [pager, filename])

def maybe_spawn_pager(options, log_filename, isatty=True):
    if options.quiet:
        return
    if options.pager is PagerMode.auto:
        if isatty:
            assert os.path.exists(log_filename)
            assert os.path.getsize(log_filename) > 0
            spawn_pager(log_filename)
    elif options.pager is PagerMode.never:
        pass
    else:
        raise ValueError("invalid pager option: {}".format(options.pager))

def is_pdb_on(options):
    return not options.quiet and options.pdb

def write_error_test_specs(result):
    filename = get_error_filename()
    # We load the previous erroneous test specs, we add the new one
    # and remove the one that succeeded.
    error_test_specs = load_error_test_specs_from(filename)
    error_test_specs |= result.error_test_specs
    error_test_specs -= result.succeed_test_specs
    mkdir_p(os.path.dirname(filename))
    with open(filename, "w") as stream:
        for test_spec in sorted(error_test_specs):
            stream.write(test_spec)
            stream.write("\n")

def load_error_test_specs():
    filename = get_error_filename()
    return load_error_test_specs_from(filename)

def load_error_test_specs_from(filename):
    try:
        s = set()
        with open(filename) as stream:
            for line in stream:
                s.add(line.strip())
        return s
    except FileNotFoundError:
        return set()

def build_cli():
    class RawDescriptionWithArgumentDefaultsHelpFormatter(
            argparse.ArgumentDefaultsHelpFormatter,
            argparse.RawDescriptionHelpFormatter,
    ):
        """Mix both formatter."""
    # TODO(Nicolas Despres): Generalize this for any enum class.
    class PagerModeAction(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            if nargs is not None:
                raise ValueError("'nargs' is not allowed.")
            if "choices" in kwargs:
                raise ValueError("'choices' is not allowed")
            kwargs["choices"] = [pm.name for pm in PagerMode]
            super(PagerModeAction, self).__init__(option_strings, dest,
                                                  **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            assert isinstance(values, str)
            # Cannot raise AttributeError because we set 'choices' in the
            # first place.
            v = getattr(PagerMode, values)
            setattr(namespace, self.dest, v)
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
        coverage_html_help = "Directory where to store the html report"
    else:
        coverage_html_help = "install 'coverage' to support enable this option"
    parser.add_argument(
        "--coverage-html",
        action="store",
        help=coverage_html_help)
    parser.add_argument(
        "--pager",
        action=PagerModeAction,
        default=PagerMode.auto,
        help="Whether to spawn a pager showing the errors/failures log.")
    parser.add_argument(
        "--pdb",
        action="store_true",
        default=False,
        help="Popup pdb when error/failure happens (implies --failfast)")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version information and exit")
    arg = parser.add_argument(
        "test_specs",
        action="store",
        nargs='*',
        default=None,
        help="Test directory/module/TestCase/test_method.")
    complete_arg(arg, test_spec_completer)
    return parser

def main(argv):
    cli = build_cli()
    if ARGCOMPLETE_ENABLED:
        # It is tempting to set a validator that always return True so that
        # we could return the list of sub-modules without their full path
        # but unfortunately it does not work.
        argcomplete.autocomplete(cli)
    options = cli.parse_args(argv[1:])
    if options.version:
        print(get_version())
        return 0
    top_level_directory = setup_top_level_directory(options.top_level_directory)
    filter_rules = options.filter_rules
    if filter_rules is None:
        filter_rules = FilterRules()
    test_specs = options.test_specs
    if not test_specs:
        test_specs = list(list_packages_from(top_level_directory))
    isatty = False if options.verbose else None
    failfast = options.failfast or options.pdb
    log_filename = get_log_filename()
    result = None
    with LinePrinter(isatty=isatty, quiet=options.quiet,
                     color_mode=options.color) as printer:
        try:
            test_names = reported_collect(printer, test_specs, options.pattern,
                                          filter_rules,
                                          top_level_directory)
            if options.collect_only:
                printer.new_line()
                return 0
            test_suite = unittest.defaultTestLoader \
                                 .loadTestsFromNames(test_names)
            result = HTestResult(printer, len(test_names), top_level_directory,
                                 failfast=failfast,
                                 log_filename=log_filename,
                                 status_filename=get_status_filename(options))
            with coverage_instrument(options):
                test_suite.run(result)
            result.print_summary()
            printer.new_line()
        except Exception as e:
            printer.write_exception()
            return 2
        finally:
            if result is not None:
                write_error_test_specs(result)
                result.close_log_file()
    if result.wasSuccessful():
        return 0
    else:
        if is_pdb_on(options):
            if result.last_traceback is not None:
                printer.write_nl(">>> Entering pdb")
                # TODO(Nicolas Despres): Do not know how to properly skip
                #  the test runner traceback levels and to go up to the
                #  unit test case frame.
                #  See: http://pydoc.net/Python/django-pdb/0.4.1/django_pdb.testrunners/
                import pdb
                pdb.post_mortem(result.last_traceback)
        else:
            maybe_spawn_pager(options, log_filename, printer.isatty)
            # maybe_spawn_pager may never return if the pager has been
            # spawned. Otherwise we return 1.
        return 1

def sys_main():
    sys.exit(main(sys.argv))

if __name__ == "__main__":
    sys_main()
