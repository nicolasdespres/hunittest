# -*- encoding: utf-8 -*-
"""Environment variable name.
"""

_PREFIX: str = "HUNITTEST"
def _mkvar(name: str) -> str:
    return "_".join((_PREFIX, name))

WORKDIR: str = _mkvar("WORKDIR")
SUMMARY: str = _mkvar("SUMMARY")
