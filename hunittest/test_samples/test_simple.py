# -*- encoding: utf-8 -*-
"""

"""

import unittest
import time
import sys

class Case1(unittest.TestCase):

    def test_success(self):
        time.sleep(0.5)
        self.assertEqual(1, 1)

    def test_failure(self):
        time.sleep(0.5)
        self.assertEqual(1, 2)

    @unittest.skip("because")
    def test_skip(self):
        time.sleep(0.1)
        self.assertFalse(True)

    @unittest.expectedFailure
    def test_expected_failure(self):
        time.sleep(0.1)
        self.assertEqual(1, 0, "broken")

    @unittest.expectedFailure
    def test_unexpected_success(self):
        time.sleep(0.1)
        self.assertEqual(1, 1, "not broken after all")

    def test_error(self):
        raise RuntimeError("error raised for testing purpose")

    def test_buffer_success(self):
        sys.stdout.write("!!!!should not appear because success!!!!")
        sys.stderr.write("!!!!should not appear because success!!!!")

    def test_buffer_failure(self):
        sys.stdout.write("!!!!failure stdout!!!!")
        sys.stderr.write("!!!!failure stderr!!!!")
        self.assertEqual(1, 2)

    @unittest.expectedFailure
    def test_buffer_unexpected_success(self):
        sys.stdout.write("!!!!unexpected success stdout!!!!")
        sys.stderr.write("!!!!unexpected success stderr!!!!")
        self.assertEqual(1, 1, "not broken after all")

class Case2(unittest.TestCase):

    def test_success(self):
        self.assertTrue(True)

class EmptyCase(unittest.TestCase):
    pass
