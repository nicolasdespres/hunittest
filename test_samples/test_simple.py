# -*- encoding: utf-8 -*-
"""

"""

import unittest
import time

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

class Case2(unittest.TestCase):

    def test_success(self):
        self.assertTrue(True)

class EmptyCase(unittest.TestCase):
    pass
