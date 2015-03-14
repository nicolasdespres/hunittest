# -*- encoding: utf-8 -*-
"""Routines working on datetime.timedelta.
"""


from datetime import timedelta
import enum

def has_decimal(v):
    return (v - int(v)) != 0.0

def strip_decimal(v):
    if has_decimal(v):
        return v
    else:
        return int(v)

def timedelta_to_hstr(tdelta):
    if tdelta < timedelta(microseconds=1e3):
        return "{:d}us".format(tdelta.microseconds)
    elif tdelta < timedelta(microseconds=1e6):
        return "{}ms".format(strip_decimal(tdelta.microseconds / 1e3))
    elif tdelta < timedelta(minutes=1):
        return "{}s".format(tdelta.seconds)
    else:
        return str(tdelta)


@enum.unique
class TimeUnit(enum.Enum):
    microsecond = timedelta(microseconds=0)
    millisecond = timedelta(microseconds=1e3)
    second = timedelta(seconds=1)
    minute = timedelta(minutes=1)
    hour = timedelta(hours=1)
    day = timedelta(days=1)
    week = timedelta(weeks=1)

    @property
    def abbrev(self):
        if self is TimeUnit.microsecond:
            return "us"
        elif self is TimeUnit.millisecond:
            return "ms"
        else:
            return self.name[0]

    @classmethod
    def from_name(cls, name):
        for s in cls:
            if s.name == name:
                return s

    @classmethod
    def from_abbrev(cls, abbrev):
        for s in cls:
            if s.abbrev == abbrev:
                return s

    @classmethod
    def from_string(cls, string):
        for s in cls:
            if s.name == string or s.abbrev == string:
                return s

def as_timeunit(obj):
    if isinstance(obj, TimeUnit):
        return obj
    elif isinstance(obj, str):
        return TimeUnit.from_string(obj)
    else:
        raise TypeError("cannot convert to a TimeUnit an object of type {}"
                        .format(type(obj).__name__))

def timedelta_to_unit(tdelta, unit):
    timeunit = as_timeunit(unit)
    return tdelta / timeunit.value
