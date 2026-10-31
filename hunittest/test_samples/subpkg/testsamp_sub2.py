# -*- encoding: utf-8 -*-
"""

"""

import unittest
import time

class Case1(unittest.TestCase):

    def test_success(self) -> None:
        time.sleep(0.5)
        self.assertEqual(1, 1)

    def test_failure(self) -> None:
        time.sleep(0.5)
        self.assertEqual(1, 2)

    @unittest.skip("because")
    def test_skip(self) -> None:
        time.sleep(0.1)
        self.assertFalse(True)

class Case2(unittest.TestCase):

    def test_success(self) -> None:
        self.assertTrue(True)
