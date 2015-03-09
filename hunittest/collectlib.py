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
    directory = os.path.dirname(package.__file__)
    assert directory.startswith(os.getcwd())
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

def is_pkg(mod):
    return os.path.basename(mod.__file__) == "__init__.py"

class InvalidTestSpecError(Exception):

    def __init__(self, test_spec, message):
        self.test_spec = test_spec
        self.message = message

    def __str__(self):
        return "invalid test spec '{}': {}".format(self.test_spec,
                                                   self.message)

def get_test_spec_type(test_spec):
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
        try:
            mod = import_module(pyname_join(spec[:i+1]))
        except ImportError:
            pass
        else:
            break
    if mod is None:
        raise InvalidTestSpecError(test_spec, "failed to import anything")
    # if not os.path.dirname(mod.__file__).startswith(os.getcwd()):
    #     raise InvalidTestSpecError(
    #         test_spec,
    #         "package or module '{}' refers outside of your current directory "
    #         "you should set PYTHONPATH=.".format(mod.__name__))
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
            except AttributeError:
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

def collect_all(test_specs, pattern):
    for test_spec in test_specs:
        tst, value = get_test_spec_type(test_spec)
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
