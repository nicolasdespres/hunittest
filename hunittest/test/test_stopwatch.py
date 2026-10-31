# -*- encoding: utf-8 -*-
"""Test 'stopwath' module.
"""


import unittest
import time
from datetime import timedelta

from hunittest.stopwatch import StopWatch


class TestStopWatch(unittest.TestCase):

    def assertTimedeltaAlmostEqual(
            self, td1: timedelta, td2: timedelta,
            prec: float = 1e-3) -> bool:
        return abs(td1 - td2).total_seconds() <= prec

    def test_is_started(self) -> None:
        sw = StopWatch()
        self.assertFalse(sw.is_started)
        sw.start()
        self.assertTrue(sw.is_started)
        sw.reset()
        self.assertFalse(sw.is_started)

    def test_split(self) -> None:
        sw = StopWatch()
        sw.start()
        self.assertEqual(0, sw.splits_count)
        ### split 1
        delay1 = 0.5
        time.sleep(delay1)
        sw.split()
        self.assertEqual(1, sw.splits_count)
        last_split_time = sw.last_split_time
        assert last_split_time is not None
        self.assertAlmostEqual(delay1,
                               last_split_time.total_seconds(),
                               places=1)
        self.assertAlmostEqual(delay1,
                               sw.mean_split_time.total_seconds(),
                               places=1)
        self.assertEqual(last_split_time, sw.total_split_time)
        ### split 1
        delay2 = 1.0
        time.sleep(delay2)
        sw.split()
        self.assertEqual(2, sw.splits_count)
        last_split_time = sw.last_split_time
        total_split_time = sw.total_split_time
        assert last_split_time is not None
        assert total_split_time is not None
        self.assertAlmostEqual(delay2,
                               last_split_time.total_seconds(),
                               places=1)
        self.assertAlmostEqual((delay1 + delay2) / 2,
                               sw.mean_split_time.total_seconds(),
                               places=1)
        self.assertAlmostEqual(delay1 + delay2,
                               total_split_time.total_seconds(),
                               places=1)

    def test_total_time(self) -> None:
        sw = StopWatch()
        sw.start()
        delay = 0.5
        time.sleep(delay)
        self.assertAlmostEqual(delay, sw.total_time.total_seconds(), places=1)

    def test_split_raises_if_not_started(self) -> None:
        sw = StopWatch()
        with self.assertRaises(RuntimeError):
            sw.split()

    def test_start_raises_if_already_started(self) -> None:
        sw = StopWatch()
        sw.start()
        with self.assertRaises(RuntimeError):
            sw.start()

    def test_total_split_time_is_zero_when_not_started(self) -> None:
        self.assertEqual(timedelta(0), StopWatch().total_split_time)

    def test_mean_split_time_is_zero_when_not_started(self) -> None:
        self.assertEqual(timedelta(0), StopWatch().mean_split_time)

    def test_total_time_is_zero_when_not_started(self) -> None:
        self.assertEqual(timedelta(0), StopWatch().total_time)
