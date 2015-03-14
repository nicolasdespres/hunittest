# -*- encoding: utf-8 -*-
"""Test 'stopwath' module.
"""


import unittest
import time
from datetime import timedelta

from hunittest.stopwatch import StopWatch


class TestStopWatch(unittest.TestCase):

    def assertTimedeltaAlmostEqual(self, td1, td2, prec=1e-3):
        return abs(td1 - td2).total_seconds <= prec

    def test_is_started(self):
        sw = StopWatch()
        self.assertFalse(sw.is_started)
        sw.start()
        self.assertTrue(sw.is_started)
        sw.reset()
        self.assertFalse(sw.is_started)

    def test_split(self):
        sw = StopWatch()
        sw.start()
        self.assertEqual(0, sw.splits_count)
        ### split 1
        delay1 = 0.5
        time.sleep(delay1)
        sw.split()
        self.assertEqual(1, sw.splits_count)
        self.assertAlmostEqual(delay1,
                               sw.last_split_time.total_seconds(),
                               places=1)
        self.assertAlmostEqual(delay1,
                               sw.mean_split_time.total_seconds(),
                               places=1)
        self.assertEqual(sw.last_split_time, sw.total_split_time)
        ### split 1
        delay2 = 1.0
        time.sleep(delay2)
        sw.split()
        self.assertEqual(2, sw.splits_count)
        self.assertAlmostEqual(delay2,
                               sw.last_split_time.total_seconds(),
                               places=1)
        self.assertAlmostEqual((delay1 + delay2) / 2,
                               sw.mean_split_time.total_seconds(),
                               places=1)
        self.assertAlmostEqual(delay1 + delay2,
                               sw.total_split_time.total_seconds(),
                               places=1)

    def test_total_time(self):
        sw = StopWatch()
        sw.start()
        delay = 0.5
        time.sleep(delay)
        self.assertAlmostEqual(delay, sw.total_time.total_seconds(), places=1)

    def test_split_raises_if_not_started(self):
        sw = StopWatch()
        with self.assertRaises(RuntimeError):
            sw.split()

    def test_start_raises_if_already_started(self):
        sw = StopWatch()
        sw.start()
        with self.assertRaises(RuntimeError):
            sw.start()
