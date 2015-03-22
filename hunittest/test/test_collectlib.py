# -*- encoding: utf-8 -*-
"""Test 'hunittest.collectlib' module.
"""


import unittest
from importlib import import_module
import sys

from hunittest.collectlib import is_pkg


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
