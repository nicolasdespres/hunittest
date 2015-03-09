# -*- encoding: utf-8 -*-
"""Utility routines
"""


import os
import re


def pyname_join(seq):
    return ".".join(seq)

def is_pkgdir(dirpath):
    return os.path.isdir(dirpath) \
        and os.path.isfile(os.path.join(dirpath, "__init__.py"))

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
