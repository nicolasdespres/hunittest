# -*- encoding: utf-8 -*-
"""
"""

import unittest
import time
from typing import NoReturn

class NumbersTest(unittest.TestCase):

    def test_even_failures(self) -> None:
        """
        Test that numbers between 0 and 5 are all even.
        """
        for i in range(0, 6):
            with self.subTest(i=i):
                print("testing", i)
                self.assertEqual(i % 2, 0)

    def test_even_error(self) -> None:
        """
        Test that numbers between 0 and 5 are all even.
        """
        for i in range(0, 6):
            with self.subTest(i=i):
                print("testing", i)
                if i % 2 != 0:
                    raise RuntimeError("on purpose error for i={}".format(i))

    def test_even_mixed_error_failures(self) -> None:
        """
        Test that numbers between 0 and 5 are all even.
        """
        for i in range(0, 6):
            with self.subTest(i=i):
                print("testing", i)
                if i % 2 == 0:
                    raise RuntimeError("on purpose error for i={}".format(i))
                else:
                    self.assertEqual(i % 2, 0)

    def test_allgood(self) -> None:
        """
        Test that numbers between 0 and 5 are all even.
        """
        for i in range(0, 6):
            with self.subTest(i=i):
                time.sleep(0.1)
                self.assertEqual(i % 2, i % 2)

    def test_allgood_but_fail_at_end(self) -> NoReturn:
        """
        Test that numbers between 0 and 5 are all even.
        """
        for i in range(0, 6):
            with self.subTest(i=i):
                time.sleep(0.1)
                self.assertEqual(i % 2, i % 2)
        self.fail("on-purpose")
