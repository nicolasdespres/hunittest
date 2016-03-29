# -*- encoding: utf-8 -*-
"""Utility routines
"""


import os
import re
from enum import Enum
from contextlib import contextmanager
import unittest
import sys
from io import StringIO


def pyname_join(seq):
    return ".".join(seq)

def is_pkgdir(dirpath):
    return os.path.isdir(dirpath) \
        and os.path.isfile(os.path.join(dirpath, "__init__.py"))

def drop_pyext(pathname):
    return re.sub(r"\.py$", "", pathname)

def mod_split(modname):
    mo = re.match(r"^(.+)\.(.*)$", modname)
    if not mo:
        raise ValueError("invalid python path identifier")
    return (mo.group(1), mo.group(2))

def is_empty_generator(generator):
    try:
        next(generator)
    except StopIteration:
        return True
    else:
        return False

class AutoEnum(Enum):
    def __new__(cls):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

def mkdir_p(path):
    try:
        os.makedirs(path)
    except FileExistsError:
        pass

@contextmanager
def protect_cwd(dirpath=None):
    saved_cwd = os.getcwd()
    if dirpath is not None:
        os.chdir(dirpath)
    try:
        yield
    finally:
        os.chdir(saved_cwd)

def safe_getcwd():
    try:
        return os.getcwd()
    except FileNotFoundError:
        return None

def load_single_test_case(test_name):
    test_suite = list(unittest.defaultTestLoader.loadTestsFromName(test_name))
    assert len(test_suite) == 1
    return test_suite[0]

@contextmanager
def silent_stderr():
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        yield
    finally:
        sys.stderr = old_stderr
