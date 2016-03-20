# -*- encoding: utf-8 -*-
"""Integration of the coverage package.
"""

import os
import re
import tempfile

from hunittest.collectlib import get_test_spec_last_pkg
from hunittest.utils import mkdir_p

try:
    import coverage
except ImportError:
    COVERAGE_ENABLED = False
else:
    COVERAGE_ENABLED = True

def get_user_test_files(test_names):
    s = set()
    for test_spec in test_names:
        pkgname = get_test_spec_last_pkg(test_spec)
        if pkgname is None:
            # This is a top level module
            mod = test_spec.partition(".")[0]
            path = mod + ".py"
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

def get_test_files_to_omit(test_names):
    l = get_my_test_files()
    l.append(os.path.join(tempfile.gettempdir(), "*"))
    l.append("/tmp/*")
    if test_names is not None:
        l.extend(get_user_test_files(test_names))
    return l

class CoverageInstrument(object):

    def __init__(self, dir_path, njobs=0):
        self.dir_path = dir_path
        self.cov = None
        if COVERAGE_ENABLED and self.dir_path:
            self.cov = coverage.Coverage(
                concurrency='multiprocessing' if njobs > 0 else None)
        self.test_names = None

    def __enter__(self):
        if self.cov is not None:
            self.cov.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.cov is not None:
            self.cov.stop()
            self.cov.combine()
            self.cov.save()
            mkdir_p(self.dir_path)
            kwargs = {"directory": self.dir_path}
            kwargs["omit"] = get_test_files_to_omit(self.test_names)
            self.cov.html_report(**kwargs)
        return False # Tell to re-raise the exception if there was one.
