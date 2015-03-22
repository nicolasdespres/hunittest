# -*- encoding: utf-8 -*-
"""Test 'hunittest.collectlib' module.
"""


import unittest
from importlib import import_module
import sys

from hunittest.collectlib import is_pkg
from hunittest.collectlib import get_test_spec_last_pkg


class TestIsPkg(unittest.TestCase):

    def test_package(self):
        pkg = import_module("hunittest.test")
        self.assertTrue(is_pkg(pkg))

    def test_module(self):
        this_module = sys.modules[__name__]
        self.assertFalse(is_pkg(this_module))

    def test_class(self):
        class C(object):
            pass
        self.assertFalse(is_pkg(C))

    def test_method(self):
        class C(object):
            def m(self):
                pass
        c = C()
        self.assertFalse(is_pkg(c.m))

    def test_function(self):
        def f():
            pass
        self.assertFalse(is_pkg(f))

    def test_string(self):
        self.assertFalse(is_pkg("foo"))

class TestGetLastTestSpecPkg(unittest.TestCase):

    def test_pkg(self):
        actual = get_test_spec_last_pkg("hunittest")
        self.assertEqual("hunittest", actual)

    def test_error_pkg(self):
        actual = get_test_spec_last_pkg("doesnotexist")
        self.assertIsNone(actual)

    def test_subpkg(self):
        actual = get_test_spec_last_pkg("hunittest.test")
        self.assertEqual("hunittest.test", actual)

    def test_error_subpkg(self):
        actual = get_test_spec_last_pkg("hunittest.doesnotexist")
        self.assertEqual("hunittest", actual)

    def test_module(self):
        actual = get_test_spec_last_pkg("hunittest.test.test_collectlib")
        self.assertEqual("hunittest.test", actual)

    def test_error_module(self):
        actual = get_test_spec_last_pkg("hunittest.test.test_doesnotexists")
        self.assertEqual("hunittest.test", actual)
