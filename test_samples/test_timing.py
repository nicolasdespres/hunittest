# -*- encoding: utf-8 -*-
"""Sample test module for testing time measurement.
"""


import unittest
import time


class TestTime(unittest.TestCase):

    def test_one_sec(self):
        time.sleep(1.0)

    def test_half_sec(self):
        time.sleep(0.5)

    def test_three_sec(self):
        time.sleep(3.0)

    def test_one_and_half_sec(self):
        time.sleep(1.5)
