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

from hunittest.utils import pyname_join


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

def collect_all_test_modules(package, pattern):
    directory = os.path.realpath(os.path.dirname(package.__file__))
    # We cannot use the finder to load the module because it mess up unittest.
    # Using import_module() is fine.
    for finder, name, ispkg in pkgutil.walk_packages(path=[directory]):
        if ispkg:
            fullname = pyname_join((package.__name__, name))
            mod = import_module(fullname)
            yield from collect_all_test_modules(mod, pattern)
        else:
            if re.match(pattern, name):
                fullname = pyname_join((package.__name__, name))
                mod = import_module(fullname)
                yield mod

class TestSpecType(Enum):
    package = 1
    module = 2
    test_case = 3
    test_method = 4

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
    for i in range(len(spec)-1, -1, -1):
        name_to_import = pyname_join(spec[:i+1])
        try:
            mod = import_module(name_to_import)
        except ImportError:
            pass
        else:
            break
    if mod is None:
        raise InvalidTestSpecError(test_spec, "failed to import anything")
    modpath = os.path.realpath(mod.__file__)
    moddir = os.path.dirname(modpath)
    if not moddir.startswith(top_level_directory):
        raise InvalidTestSpecError(
            test_spec,
            "package or module '{modname}' (from '{modpath}'), "
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
                    try:
                        import_module(pyname_join((obj.__name__, attr)))
                    except ImportError as e:
                        raise InvalidTestSpecError(test_spec, str(e))
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

def collect_all_from_module(test_module):
    for test_case in collect_test_cases(test_module):
        yield from collect_all_from_test_case(test_case)

def collect_all_from_package(package, pattern):
    for test_module in collect_all_test_modules(package, pattern):
        yield from collect_all_from_module(test_module)

def collect_all(test_specs, pattern, top_level_directory):
    for test_spec in test_specs:
        tst, value = get_test_spec_type(test_spec, top_level_directory)
        if tst is TestSpecType.package:
            yield from collect_all_from_package(value, pattern)
        elif tst is TestSpecType.module:
            yield from collect_all_from_module(value)
        elif tst is TestSpecType.test_case:
            yield from collect_all_from_test_case(value)
        elif tst is TestSpecType.test_method:
            yield pyname_join((value.__module__, value.__qualname__))
        else:
            raise RuntimeError("unsupported test spec type: {}"
                               .format(tst))

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
