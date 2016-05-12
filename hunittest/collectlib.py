# -*- encoding: utf-8 -*-
"""Routines to collect tests.
"""


from enum import Enum
from importlib import import_module
import os
import pkgutil
import re
import unittest
import functools
import sys
import itertools
from fnmatch import fnmatch
import types

from hunittest.utils import pyname_join
from hunittest.utils import is_pkgdir
from hunittest.utils import drop_pyext
from hunittest.utils import issubdir


def list_packages_from(dirpath):
    """Yields all packages directly available from *dirpath*."""
    for name in os.listdir(dirpath):
        if is_pkgdir(os.path.join(dirpath, name)):
            yield name

def list_modules_from(dirpath, pattern):
    """Yields all modules directly available form *dirpath.

    Useful to suggest module located at the root of top level directory the
    discovery procedure starts from.
    """
    for name in os.listdir(dirpath):
        if os.path.isfile(name) and fnmatch(name, pattern):
            yield drop_pyext(name)

def is_test_case(obj):
    return isinstance(obj, type) and issubclass(obj, unittest.TestCase)

def collect_test_cases(module):
    return filter(is_test_case,
                  map(lambda x: getattr(module, x),
                      dir(module)))

def is_test_method(name):
    return re.match(r"^test_", name)

def collect_test_names(test_case):
    return map(functools.partial(getattr, test_case),
               filter(is_test_method, dir(test_case)))

def build_test_name(test_module, test_case=None, test_method=None):
    l = [test_module]
    if test_case is not None:
        l.append(test_case)
    if test_method is not None:
        l.append(test_method)
    def transform(x):
        if hasattr(x, "__name__"):
            return x.__name__
        else:
            return x
    return pyname_join(map(transform, l))

def collect_all_test_modules(package, pattern, top_level_only=False):
    # We cannot use the finder to load the module because it mess up unittest.
    # Using import_module() is fine.
    for _, name, ispkg in pkgutil.walk_packages(package.__path__,
                                                package.__name__+'.'):
        if not ispkg and fnmatch(re.sub(r"^.*\.", "", name) + ".py", pattern):
            if top_level_only:
                yield name
            else:
                try:
                    yield import_module(name)
                except unittest.SkipTest as e:
                    yield SkippedTestSpec(name, str(e))

class TestSpecType(Enum):
    package = 1
    module = 2
    test_case = 3
    test_method = 4
    skipped = 5

def is_pkg(obj):
    return hasattr(obj, "__file__") \
        and os.path.basename(obj.__file__) == "__init__.py"

class InvalidTestSpecError(Exception):

    def __init__(self, test_spec, message):
        self.test_spec = test_spec
        self.message = message

    def __str__(self):
        return "invalid test spec '{}': {}".format(self.test_spec,
                                                   self.message)

class SkippedTestSpec:

    def __init__(self, test_spec, reason):
        """Create a new SkippedTestSpec object from the *test_spec* we were
        importing when we caught the SkipTest exception and the reason
        attached to the exception.
        """
        self.test_spec = test_spec
        self.reason = reason

def get_test_spec_type(test_spec, top_level_directory):
    _check_top_level_directory(top_level_directory)
    if not test_spec:
        raise ValueError("empty test spec")
    if isinstance(test_spec, str):
        spec = test_spec.split(".")
    elif isinstance(test_spec, (list, tuple)):
        spec = test_spec
        test_spec = pyname_join(spec)
    else:
        raise TypeError("must be a str, list or tuple, not {!r}"
                        .format(type(test_spec).__name__))
    assert len(spec) > 0
    mod = None
    first_import_err = None
    for i in range(len(spec)-1, -1, -1):
        name_to_import = pyname_join(spec[:i+1])
        try:
            mod = import_module(name_to_import)
        except unittest.SkipTest as e:
            return (TestSpecType.skipped,
                    SkippedTestSpec(name_to_import, str(e)))
            skipped = True
            break
        except ImportError as e:
            if first_import_err is None:
                first_import_err = e
            pass
        else:
            break
    if mod is None:
        # It happens when we failed to import the first package/module
        # of the test spec.
        assert first_import_err is not None
        raise first_import_err
    modpath = os.path.realpath(mod.__file__)
    moddir = os.path.dirname(modpath)
    if not issubdir(moddir, top_level_directory):
        raise InvalidTestSpecError(
            test_spec,
            "package or module '{modname}' (from '{moddir}'), "
            "refers outside of your top level directory '{top_level_dir}'"
            .format(modname=mod.__name__,
                    moddir=moddir,
                    top_level_dir=top_level_directory,
                ))
    mods = spec[:i+1]
    attrs = spec[i+1:]
    if not attrs:
        if is_pkg(mod): # Package
            return (TestSpecType.package, mod)
        else: # module
            return (TestSpecType.module, mod)
    else:
        obj = mod
        for i in range(len(attrs)):
            attr = attrs[i]
            try:
                obj = getattr(obj, attr)
            except AttributeError as e:
                if is_pkg(obj):
                    # Normally we stop importing package, sub-packages and
                    # modules when we reach the TestCase class. If there
                    # is an error when importing the module we stop earlier
                    # and the error shows up again here.
                    import_module(pyname_join((obj.__name__, attr)))
                    assert False, \
                        "an ImportError exception should have been raised"
                else:
                    raise InvalidTestSpecError(
                        test_spec,
                        "cannot get attribute '{}' from '{}'"
                        .format(attr, pyname_join(mods+attrs[:i])))
        if is_test_case(obj):
            return (TestSpecType.test_case, obj)
        else:
            return (TestSpecType.test_method, obj)

def collect_all_from_test_case(test_case):
    for test_method in collect_test_names(test_case):
        yield build_test_name(test_case.__module__, test_case, test_method)

def collect_all_from_module(test_module, top_level_only=False):
    if top_level_only:
        yield build_test_name(test_module)
    else:
        for test_case in collect_test_cases(test_module):
            yield from collect_all_from_test_case(test_case)

def collect_all_from_package(package, pattern, top_level_only=False):
    for test_module in collect_all_test_modules(package, pattern,
                                                top_level_only=top_level_only):
        if isinstance(test_module, types.ModuleType):
            yield from collect_all_from_module(test_module,
                                               top_level_only=top_level_only)
        else:
            yield test_module

def collect_all(test_specs, pattern, top_level_directory, top_level_only=False):
    """Collect all test case from the given test specification.

    The top_level_only flag tells whether to load only the top level test
    specs (i.e. packages and module). When this flag is on no module are loaded
    and thus, the collection process should be faster.
    """
    if not test_specs:
        test_specs = itertools.chain(list_packages_from(top_level_directory),
                                     list_modules_from(top_level_directory,
                                                       pattern))
    def gen():
        for test_spec in test_specs:
            tst, value = get_test_spec_type(test_spec, top_level_directory)
            if tst is TestSpecType.package:
                yield from collect_all_from_package(
                    value, pattern, top_level_only=top_level_only)
            elif tst is TestSpecType.module:
                yield from collect_all_from_module(
                    value, top_level_only=top_level_only)
            elif tst is TestSpecType.test_case:
                if top_level_only:
                    yield value.__module__
                else:
                    yield from collect_all_from_test_case(value)
            elif tst is TestSpecType.test_method:
                if top_level_only:
                    yield value.__module__
                else:
                    yield test_spec
            elif tst is TestSpecType.skipped:
                yield value
            else:
                raise RuntimeError("unsupported test spec type: {}"
                                   .format(tst))
    seen = set()
    for i in gen():
        if i not in seen:
            seen.add(i)
            yield i

def _check_top_level_directory(top_level_directory):
    if not os.path.isabs(top_level_directory):
        raise ValueError("top level directory must be an absolute path: '{}'"
                         .format(top_level_directory))
    if not os.path.isdir(top_level_directory):
        raise NotADirectoryError(top_level_directory)

def setup_top_level_directory(top_level_directory=None):
    if not top_level_directory:
        top_level_directory = os.getcwd()
    _check_top_level_directory(top_level_directory)
    sys.path.insert(0, top_level_directory)
    return top_level_directory

def get_test_spec_last_pkg(test_spec):
    last_pkg = None
    for part in test_spec.split("."):
        try:
            obj = import_module(part)
        except ImportError:
            break
        else:
            if is_pkg(obj):
                if last_pkg is None:
                    last_pkg = part
                else:
                    last_pkg = pyname_join((last_pkg, part))
            else:
                break
    return last_pkg
