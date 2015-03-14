# -*- encoding: utf-8 -*-
"""Test 'hunittest.utils' module.
"""


import unittest
from datetime import timedelta

from hunittest.timedeltalib import timedelta_to_hstr


class TestTimedeltaToHstr(unittest.TestCase):

    def test_microseconds(self):
        data = [
            ("0us",     timedelta(microseconds=0)),
            ("1us",     timedelta(microseconds=1)),
            ("10us",    timedelta(microseconds=10)),
            ("100us",   timedelta(microseconds=100)),
            ("1ms",     timedelta(microseconds=1000)),
            ("10ms",    timedelta(microseconds=10000)),
            ("100ms",   timedelta(microseconds=100000)),
            ("1s",      timedelta(microseconds=1000000)),
            ("10s",     timedelta(microseconds=10000000)),
            ("50s",     timedelta(microseconds=50000000)),
            ("0:01:00", timedelta(microseconds=60000000)),
            ("0:01:40", timedelta(microseconds=100000000)),
        ]
        for i, (a, q) in enumerate(data):
            self.assertEqual(a, timedelta_to_hstr(q),
                             "wrong answer for {!r} for data {}".format(q, i))
