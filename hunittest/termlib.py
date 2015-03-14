# -*- encoding: utf-8 -*-
"""Get information from terminal.

Try to do it in a portable way and by just relying on python standard library.
"""


import sys
import os
import re


# FIXME(Nicolas Despres): Would be nice if it is not hard coded!
ANSI_PREFIX_CHAR = '\x1b'

ANSI_ESCAPE_PATTERN = r'{}.*?m'.format(ANSI_PREFIX_CHAR)

def strip_ansi_escape(string):
    return re.subn(ANSI_ESCAPE_PATTERN, "", string)[0]

def ansi_string_truncinfo(string, size):
    if size < 0:
        raise ValueError("size must be positive")
    if string is None:
        raise ValueError("expected a string, not {!r}"
                         .format(type(string).__name__))
    cl = 0 # cumulative number of character visited so far
    al = 0 # cumulative number of ansi escape character visited so far
    last_end = 0
    has_ansi = False
    for mo in re.finditer(ANSI_ESCAPE_PATTERN, string):
        # print("MO", repr(mo), len(mo.group(0).encode()))
        cl += mo.start() - last_end
        if cl >= size:
            break
        al += mo.end() - mo.start()
        last_end = mo.end()
        has_ansi = True
        # print("cl", cl, "al", al)
    cl += len(string) - last_end
    # print("last cl", cl)
    length = min(size, cl)
    return (al+length, length, has_ansi)

def truncate_ansi_string(string, size):
    string_pos, visual_pos, isansi = ansi_string_truncinfo(string, size)
    return string[:string_pos]

# The list order matter since that is their index in the ANSI color table
ANSI_COLOR_NAMES = \
    tuple("black red green yellow blue magenta cyan white".split())

def fore_color_name(name):
    return "fore_" + name

def back_color_name(name):
    return "back_" + name

class TermInfo(object):

    def __init__(self, term_stream=sys.stdout, color_mode="auto"):
        ### By default we have no information.
        self.color_mode = color_mode
        for cname in ANSI_COLOR_NAMES:
            self._set_fore_color(cname, '')
            self._set_back_color(cname, '')
        self.ansi_prefix_char = None
        ### Get capabilities
        self.isatty = self._get_isatty_term(term_stream)
        # int capa
        for attr, capa, default in (("max_colors", "colors", None),
                                    ("lines", "lines", None),
                                    ("columns", "cols", None)):
            self._setintcapa(attr, capa, default)
        # str capa
        for attr, capa, default in (("carriage_return", "cr", None),
                                    ("clear_eol", "el", None),
                                    ("reset_all", "sgr0", ""),
                                    ("hide_cursor", "civis", ""),
                                    ("show_cursor", "cnorm", "")):
            self._setstrcapa(attr, capa, default)
        ### Initialize colors
        self.color_enabled = False
        if self.color_mode == "auto":
            if self.isatty and self.support_colors:
                self._init_colors()
        elif self.color_mode == "never":
            pass
        elif self.color_mode == "always":
            self._init_hardcoded_colors()
        else:
            raise ValueError("invalid color mode: {}".format(color_mode))

    def _get_curses(self):
        if not hasattr(self, "_curses"):
            # 'curses' module is not always available.
            try:
                import curses
                curses.setupterm()
            except Exception:
                self._curses = None
            else:
                self._curses = curses
        return self._curses

    def _setintcapa(self, attr, capa, default):
        setattr(self, attr, default)
        curses = self._get_curses()
        if not curses:
            return
        value = curses.tigetnum(capa)
        assert isinstance(value, int)
        setattr(self, attr, value)

    def _setstrcapa(self, attr, capa, default):
        setattr(self, attr, default)
        curses = self._get_curses()
        if not curses:
            return
        value = curses.tigetstr(capa)
        assert isinstance(value, (str, bytes, type(None)))
        if value:
            value = value.decode()
        else:
            value = default
        setattr(self, attr, value)

    def _get_isatty_term(self, stream):
        try:
            fileno = stream.fileno()
        except:
            return False
        else:
            return os.isatty(fileno)

    def _init_hardcoded_colors(self):
        for i, cname in enumerate(ANSI_COLOR_NAMES):
            self._set_fore_color(cname,
                                 "{}[{}m".format(ANSI_PREFIX_CHAR, 30+i))
        for i, cname in enumerate(ANSI_COLOR_NAMES):
            self._set_back_color(cname,
                                 "{}[{}m".format(ANSI_PREFIX_CHAR, 40+i))
        self.color_enabled = True

    def _init_colors(self):
        curses = self._get_curses()
        if not curses:
            return
        ### Set foreground colors
        setaf_param = curses.tigetstr("setaf")
        for i, cname in enumerate(ANSI_COLOR_NAMES):
            self._set_fore_color(cname, curses.tparm(setaf_param, i))
        ### Set background colors
        setab_param = curses.tigetstr("setab")
        for i, cname in enumerate(ANSI_COLOR_NAMES):
            self._set_back_color(cname, curses.tparm(setab_param, i))
        self.color_enabled = True

    def _set_fore_color(self, name, value):
        self._set_ansi_escape_code(fore_color_name(name), value)

    def _set_back_color(self, name, value):
        self._set_ansi_escape_code(back_color_name(name), value)

    def _set_ansi_escape_code(self, name, value):
        if isinstance(value, bytes):
            value = value.decode()
        if not isinstance(value, str):
            raise TypeError("must be a str or bytes, not {}"
                            .format(type(value).__name__))
        if value:
            prefix_char = value[0]
            if not self.ansi_prefix_char:
                self.ansi_prefix_char = prefix_char
            else:
                assert self.ansi_prefix_char == prefix_char
        setattr(self, name, value)

    @property
    def support_colors(self):
        return self.max_colors is not None and self.max_colors > 0

    @property
    def size(self):
        return (self.lines, self.columns)
