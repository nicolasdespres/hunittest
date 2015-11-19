# -*- encoding: utf-8 -*-
"""Routines to do shell-completion of CLI argument.
"""

# TODO(Nicolas Despres): Unit test this module!!

import os
import pkgutil
import re
from importlib import import_module

from hunittest.utils import pyname_join
from hunittest.utils import is_pkgdir
from hunittest.utils import mod_split
from hunittest.utils import is_empty_generator
from hunittest.collectlib import get_test_spec_type
from hunittest.collectlib import TestSpecType
from hunittest.collectlib import collect_test_cases
from hunittest.collectlib import collect_test_names
from hunittest.collectlib import setup_top_level_directory

# Set this to True to enable logging. Useful for debugging.
LOGGER_ENABLED = False
if LOGGER_ENABLED:
    import logging
    logging.basicConfig(
        filename=os.path.join(os.path.dirname(__file__), "completionlib.log"),
        level=logging.DEBUG,
        filemode='a',
    )
    LOGGER = logging.getLogger(__name__)
else:
    class DummyLogger(object):
        def debug(self, *args, **kwargs):
            pass
        def info(self, *args, **kwargs):
            pass
        def warning(self, *args, **kwargs):
            pass
        def error(self, *args, **kwargs):
            pass
        def critical(self, *args, **kwargs):
            pass
    LOGGER = DummyLogger()

LOGGER.info("Start logging ================================")

try:
    import argcomplete
except ImportError:
    def warn(*args):
        return LOGGER.warning(*args)
else:
    def warn(*args):
        argcomplete.warn(*args)
        LOGGER.warning(*args)

def list_packages_from(dirpath):
    """Yields all packages directly available from *dirpath*."""
    for name in os.listdir(dirpath):
        if is_pkgdir(os.path.join(dirpath, name)):
            yield name

def collect_from_test_suite(test_suite):
    """Generate all test full names in *test_suite* recursively.
    """
    def rec(test_suite):
        for t in test_suite:
            if isinstance(t, unittest.TestSuite):
                yield from rec(t._tests)
            elif isinstance(t, unittest.TestCase):
                yield pyname_join((t.__module__,
                                   t.__class__.__name__,
                                   t._testMethodName))
            else:
                raise RuntimeError("do not know what to do with {!r}".format(t))
    if not isinstance(test_suite, unittest.TestSuite):
        raise TypeError("must be a unittest.TestSuite, not {}"
                        .format(type(test_suite).__name__))
    yield from rec(test_suite)

def argcomplete_directories(prefix, top_level_directory):
    for directory in list_packages_from(top_level_directory):
        if directory.startswith(prefix):
            yield directory

def argcomplete_modules(package, pattern, prefix):
    directory = os.path.dirname(package.__file__)
    for _, name, ispkg in pkgutil.iter_modules(path=[directory]):
        if not name.startswith(prefix):
            continue
        if ispkg or re.match(pattern, name):
            fullname = pyname_join((package.__name__, name))
            try:
                import_module(fullname)
            except:
                warn("failed to load module {!r}".format(fullname))
            else:
                yield fullname

def argcomplete_test_cases(module, prefix):
    for test_case in collect_test_cases(module):
        name = test_case.__name__
        if name.startswith(prefix):
            yield pyname_join((module.__name__, name))

def argcomplete_test_methods(test_case, prefix):
    for test_method in collect_test_names(test_case):
        name = test_method.__name__
        if name.startswith(prefix):
            yield pyname_join((test_case.__module__,
                               test_case.__name__,
                               name))

def gen_test_spec_completion(prefix, parsed_args):
    spec = prefix.split(".")
    assert len(spec) > 0
    if len(spec) == 1:
        yield from argcomplete_directories(spec[0],
                                           parsed_args.top_level_directory)
    else:
        test_spec = spec[:-1]
        rest = spec[-1]
        LOGGER.debug("TEST SPEC: '%s'", test_spec)
        try:
            tst, obj = get_test_spec_type(test_spec,
                                          parsed_args.top_level_directory)
        except:
            warn("failed to load test spec {!r} (prefix={!r})"
                 .format(pyname_join(test_spec), prefix))
        else:
            if tst is TestSpecType.package:
                yield from argcomplete_modules(obj, parsed_args.pattern, rest)
            elif tst is TestSpecType.module:
                yield from argcomplete_test_cases(obj, rest)
            elif tst is TestSpecType.test_case:
                yield from argcomplete_test_methods(obj, rest)
            elif tst is TestSpecType.test_method:
                pass # nothing to complete
            else:
                raise RuntimeError("unsupported test spec type: {}"
                                   .format(tst))

def with_next_completion(completion, parsed_args):
    next_completion = completion + "."
    next_completions = gen_test_spec_completion(next_completion, parsed_args)
    if not is_empty_generator(next_completions):
        LOGGER.debug("YIELD '%s' AND '%s'", completion, next_completion)
        yield completion
        yield next_completion

def test_spec_completer(prefix, parsed_args, **kwargs):
    LOGGER.debug("TEST_SPEC_COMPLETER prefix='%s' kwargs=%r", prefix, kwargs)
    setup_top_level_directory(parsed_args.top_level_directory)
    completions = gen_test_spec_completion(prefix, parsed_args)
    for completion in completions:
        yield from with_next_completion(completion, parsed_args)
