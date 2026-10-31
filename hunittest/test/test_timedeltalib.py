# -*- encoding: utf-8 -*-
"""Test 'hunittest.utils' module.
"""


import unittest
from datetime import timedelta
import itertools
import operator

from hunittest.timedeltalib import timedelta_to_hstr
from hunittest.timedeltalib import TimeUnit
from hunittest.timedeltalib import as_timeunit
from hunittest.timedeltalib import timedelta_to_unit


class TestTimedeltaToHstr(unittest.TestCase):

    def test_microseconds(self) -> None:
        data = [
            ("0us",      timedelta(microseconds=0)),
            ("1us",      timedelta(microseconds=1)),
            ("10us",     timedelta(microseconds=10)),
            ("100us",    timedelta(microseconds=100)),
            ("1ms",      timedelta(microseconds=1000)),
            ("10ms",     timedelta(microseconds=10000)),
            ("100ms",    timedelta(microseconds=100000)),
            ("1s",       timedelta(microseconds=1000000)),
            ("10s",      timedelta(microseconds=10000000)),
            ("50s",      timedelta(microseconds=50000000)),
            ("1m",       timedelta(microseconds=60000000)),
            ("1m 40s",   timedelta(microseconds=100000000)),
            ("1d",       timedelta(days=1)),
            ("4d 8m",    timedelta(days=4, minutes=8)),
            ("1w 2d 3h", timedelta(weeks=1, days=2, hours=3,
                                   minutes=4,
                                   seconds=5, milliseconds=6,
                                   microseconds=7)),
            ("1w 3h",    timedelta(weeks=1, hours=3)),
        ]
        for i, (a, q) in enumerate(data):
            self.assertEqual(a, timedelta_to_hstr(q),
                             "wrong answer for {!r} for data {}".format(q, i))

class TestTimeUnit(unittest.TestCase):

    UNIT_NAMES: list[tuple[str, TimeUnit]] = [
        ("microsecond", TimeUnit.microsecond),
        ("millisecond", TimeUnit.millisecond),
        ("second",      TimeUnit.second),
        ("minute",      TimeUnit.minute),
        ("hour",        TimeUnit.hour),
        ("day",         TimeUnit.day),
        ("week",        TimeUnit.week),
    ]

    UNIT_ABBREVS: list[tuple[str, TimeUnit]] = [
        ("us", TimeUnit.microsecond),
        ("ms", TimeUnit.millisecond),
        ("s",  TimeUnit.second),
        ("m",  TimeUnit.minute),
        ("h",  TimeUnit.hour),
        ("d",  TimeUnit.day),
        ("w",  TimeUnit.week),
    ]

    ALL_UNITS: list[TimeUnit] = list(map(operator.itemgetter(1), UNIT_NAMES))

    def test_sanity(self) -> None:
        self.assertEqual(len(TimeUnit), len(self.UNIT_NAMES))
        self.assertEqual(len(TimeUnit), len(self.UNIT_ABBREVS))
        self.assertEqual(len(TimeUnit), len(self.ALL_UNITS))

    def test_name(self) -> None:
        for i, (a, q) in enumerate(self.UNIT_NAMES):
            self.assertEqual(a, q.name,
                             "wrong answer for {!r} for data {}".format(q, i))

    def test_abbrev(self) -> None:
        for i, (a, q) in enumerate(self.UNIT_ABBREVS):
            self.assertEqual(a, q.abbrev,
                             "wrong answer for {!r} for data {}".format(q, i))

    def test_from_name(self) -> None:
        for i, (q, a) in enumerate(self.UNIT_NAMES):
            self.assertEqual(a, TimeUnit.from_name(q),
                             "wrong answer for {!r} for data {}".format(q, i))

    def test_from_abbrev(self) -> None:
        for i, (q, a) in enumerate(self.UNIT_ABBREVS):
            self.assertEqual(a, TimeUnit.from_abbrev(q),
                             "wrong answer for {!r} for data {}".format(q, i))

    def test_from_string(self) -> None:
        for i, (q, a) in enumerate(itertools.chain(self.UNIT_NAMES,
                                                   self.UNIT_ABBREVS)):
            self.assertIs(a, TimeUnit.from_string(q),
                          "wrong answer for {!r} for data {}".format(q, i))

    def test_as_timeunit(self) -> None:
        identity = zip(self.ALL_UNITS, self.ALL_UNITS)
        iterator = itertools.chain(self.UNIT_NAMES,
                                   self.UNIT_ABBREVS,
                                   identity)
        for _, (_, a) in enumerate(iterator):
            self.assertIs(a, as_timeunit(a))

    def test_timedelta_to_unit(self) -> None:
        data = [
            (1000.0, timedelta(seconds=1), "ms"),
        ]
        for a, q, u in data:
            self.assertEqual(a, timedelta_to_unit(q, u))
