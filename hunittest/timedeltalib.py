# -*- encoding: utf-8 -*-
"""Routines working on datetime.timedelta.
"""


from datetime import timedelta


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
