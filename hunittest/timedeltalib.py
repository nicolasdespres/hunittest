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
    """A prettier string version of a timedelta.

    Print units for each part (weeks, days, hours, etc...) and skip them
    when they are zero.
    """
    result = []
    r = tdelta
    for u in reversed(TimeUnit):
        q, r = divmod(r, u.value)
        if q != 0:
            result.append("{:d}{}".format(q, u.abbrev))
    if result:
        return " ".join(result)
    else:
        return "0" + TimeUnit.microsecond.abbrev

@enum.unique
class TimeUnit(enum.Enum):
    microsecond = timedelta(microseconds=1)
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
    """Convert timedelta *tdelta* to the given *unit*.

    Return a float.
    """
    timeunit = as_timeunit(unit)
    return tdelta / timeunit.value
