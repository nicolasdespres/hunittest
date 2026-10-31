# -*- encoding: utf-8 -*-
"""Utility routines
"""


import os
import re
from enum import Enum
from contextlib import contextmanager
import sys
from io import StringIO
from typing import Generator, Iterable, Iterator, Self


def pyname_join(seq: Iterable[str]) -> str:
    return ".".join(seq)

def is_pkgdir(dirpath: str) -> bool:
    return os.path.isdir(dirpath) \
        and os.path.isfile(os.path.join(dirpath, "__init__.py"))

def drop_pyext(pathname: str) -> str:
    return re.sub(r"\.py$", "", pathname)

def mod_split(modname: str) -> tuple[str, str]:
    mo = re.match(r"^(.+)\.(.*)$", modname)
    if not mo:
        raise ValueError("invalid python path identifier")
    return (mo.group(1), mo.group(2))

def is_empty_generator(generator: Iterator[object]) -> bool:
    try:
        next(generator)
    except StopIteration:
        return True
    else:
        return False

class AutoEnum(Enum):
    def __new__(cls) -> Self:
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

def mkdir_p(path: str) -> None:
    try:
        os.makedirs(path)
    except FileExistsError:
        pass

@contextmanager
def protect_cwd(dirpath: str | None = None) -> Generator[None, None, None]:
    saved_cwd = os.getcwd()
    if dirpath is not None:
        os.chdir(dirpath)
    try:
        yield
    finally:
        os.chdir(saved_cwd)

def safe_getcwd() -> str | None:
    try:
        return os.getcwd()
    except FileNotFoundError:
        return None

@contextmanager
def silent_stderr() -> Generator[None, None, None]:
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        yield
    finally:
        sys.stderr = old_stderr

def ensure_trailing_slash(path: str) -> str:
    if not path.endswith("/"):
        return path + "/"
    return path

def issubdir(filepath: str, dirpath: str) -> bool:
    return filepath.startswith(ensure_trailing_slash(dirpath))
