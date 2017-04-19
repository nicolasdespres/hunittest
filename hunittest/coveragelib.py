# -*- encoding: utf-8 -*-
"""Integration of the coverage package.
"""

import os
import re
import tempfile
import sys
import textwrap
from glob import glob
from warnings import warn
import argparse

from hunittest.collectlib import get_test_spec_last_pkg
from hunittest.utils import silent_stderr

try:
    import coverage
except ImportError:
    COVERAGE_ENABLED = False
else:
    COVERAGE_ENABLED = True

def get_user_test_files(test_names, top_level_dir):
    s = set()
    for test_spec in test_names:
        pkgname = get_test_spec_last_pkg(test_spec)
        if pkgname is None:
            # This is a top level module
            mod = test_spec.partition(".")[0]
            path = os.path.join(top_level_dir, mod + ".py")
            if os.path.isfile(path):
                s.add(path)
        else:
            path = re.subn(r"\.", "/", pkgname)[0]
            path = os.path.join(path, "*")
            s.add(path)
    return s

def get_my_test_files():
    # My own files
    return [os.path.join(os.path.dirname(__file__), "*")]

def get_test_files_to_omit(test_names, top_level_dir):
    l = get_my_test_files()
    l.append(os.path.join(tempfile.gettempdir(), "*"))
    l.append("/tmp/*")
    if test_names is not None:
        l.extend(get_user_test_files(test_names, top_level_dir))
    return l

def write_sitecustomize(path):
    with open(path, "w") as stream:
        stream.write(textwrap.dedent("""\
        import coverage
        coverage.process_startup()
        """))

class CoverageInstrument(object):
    """Integration of the 'coverage' package.

    This class is in charge of setting up the environment variable and site
    customization script as well as clearing old data and generating the
    coverage report.

    We create the site customization script in the user project directory
    (generally it is the top level directory) because this directory available
    in the path and it avoid to clutter the site-package directory with a
    script that is loaded by many projects that do not need it.

    Most of the configuration of the coverage package does not happen here.
    The user must create a suitable configuration file at the root of its
    project (generally named .coveragerc). The run:parallel option must be set
    to true regardless that the test will or will not be run in parallel.

    Although we automatically compute a quiet accurate list of files to omit,
    we encourage users to set the 'source' option in their configuration files
    so that the coverage package can warn them when a file is not covered at
    all.
    """

    def __init__(self,
                 top_level_dir=os.getcwd(),
                 config_file='.coveragerc',
                 reporters=None,
                 top_level_test_specs=None):
        if not COVERAGE_ENABLED or reporters is None:
            self.cov = None
            return
        self.top_level_dir = top_level_dir
        self.SITECUSTOMIZE = os.path.join(top_level_dir, "sitecustomize.py")
        if not os.path.isabs(config_file):
            self.config_file = os.path.join(top_level_dir, config_file)
        self.top_level_test_specs = top_level_test_specs
        self.omit = get_test_files_to_omit(self.top_level_test_specs,
                                           self.top_level_dir)
        self.cov = coverage.Coverage(config_file=self.config_file,
                                     omit=self.omit)
        assert self.cov.get_option("run:parallel") == True, \
            "The run:parallel option must be set to True in your coverage "\
            "configuration file regardless you are "\
            "running your test in parallel or not"
        self.test_names = None
        self.write_sitecustomize()
        self.reporters = reporters

    def __del__(self):
        if self.cov is None:
            return
        try:
            os.remove(self.SITECUSTOMIZE)
        except FileNotFoundError:
            pass

    def write_sitecustomize(self):
        if not os.path.exists(self.SITECUSTOMIZE):
            write_sitecustomize(self.SITECUSTOMIZE)

    def set_env(self):
        os.environ["COVERAGE_PROCESS_START"] = self.config_file

    def unset_env(self):
        del os.environ["COVERAGE_PROCESS_START"]

    def erase(self):
        if self.cov is None:
            return
        self.cov.erase()

    def start(self):
        if self.cov is None:
            return
        self.set_env()
        self.write_sitecustomize()
        self.cov.start()

    def stop(self):
        if self.cov is None:
            return
        self.cov.stop()
        self.unset_env()
        # Coverage is confused because it collect no data when we load
        # the test module whereas the code at module level is important. We
        # silent its warning.
        with silent_stderr():
            self.cov.save()

    def _drop_combined_data_suffix(self):
        """Get rid of the combined data file suffix.

        In parallel mode, coverage always add a suffix to the saved file.
        Surprisingly, it also does it for the combined data file which by
        definition should not be suffixed. Anyway, the coveralls package
        needs a combined data file named .coverage to successfully make its
        report. This function do the file renaming.
        """
        filename = self.cov.data_files.filename
        pattern = filename+".*"
        filenames = glob(pattern)
        nfilenames = len(filenames)
        if nfilenames == 1:
            os.rename(filenames[0], filename)
        else:
            warn("found exactly {} coverage file(s) matching '{}' from '{}'; "\
                 "combination may have failed".format(nfilenames,
                                                      pattern,
                                                      os.getcwd()))

    def combine(self):
        if self.cov is None:
            return
        self.cov.combine()
        self.cov.save()
        self._drop_combined_data_suffix()
        self.combined = True

    def report(self):
        if self.cov is None:
            return
        if "term" in self.reporters:
            self.cov.report(show_missing=False)
        if "term-missing" in self.reporters:
            self.cov.report(show_missing=True)
        if "annotate" in self.reporters:
            self.cov.annotate()
        if "html" in self.reporters:
            self.cov.html_report()
        if "xml" in self.reporters:
            self.cov.xml_report()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
        return False # Tell to re-raise the exception if there was one.

def add_coverage_cmdline_arguments(parser):
    DEFAULT_REPORTER = "term"
    VALID_REPORTERS = set((DEFAULT_REPORTER, "term-missing",
                           "annotate", "html", "xml"))
    if COVERAGE_ENABLED:
        help_msg = "Comma separated list of report types to generate "\
                   "(any combination of: {})"\
                   .format(", ".join(VALID_REPORTERS))
        def coverage_param(param_str):
            reporters = set(param_str.split(","))
            invalid_reporters = reporters - VALID_REPORTERS
            if invalid_reporters:
                raise argparse.ArgumentTypeError(
                    "invalid coverage reporters: {}"
                    .format(", ".join(invalid_reporters)))
            return reporters
    else:
        help_msg = "install 'coverage' package to enable this option"
        def coverage_param(param_str):
            raise argparse.ArgumentTypeError("'coverage' package is not "
                                             "installed")
    parser.add_argument(
        "--coverage",
        type=coverage_param,
        action='store',
        metavar="REPORTERS",
        nargs='?',
        const=DEFAULT_REPORTER,
        default=None,
        help=help_msg)
