# -*- encoding: utf-8 -*-
"""Environment variable name.
"""

_PREFIX = "HUNITTEST"
def _mkvar(name):
    return "_".join((_PREFIX, name))

WORKDIR = _mkvar("WORKDIR")
SUMMARY = _mkvar("SUMMARY")
