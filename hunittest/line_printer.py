# -*- encoding: utf-8 -*-
"""A module to print status line on terminal.

Strongly inspired by:
  http://code.activestate.com/recipes/475116-using-terminfo-for-portable-color-output-cursor-co/
See also:
  https://developer.apple.com/library/mac/documentation/Darwin/Reference/ManPages/man5/terminfo.5.html#//apple_ref/doc/man/5/terminfo
  'curses' python module doc
"""


import sys
import traceback

from hunittest.termlib import ANSI_ESCAPE_PATTERN
from hunittest.termlib import strip_ansi_escape
from hunittest.termlib import ansi_string_truncinfo
from hunittest.termlib import truncate_ansi_string
from hunittest.termlib import TermInfo

class LinePrinter(object):
    """Robust line overwriting in terminal.

    To show progress of a task on the terminal it is useful to be able to
    overwrite the previous line (using the carriage return special character).
    This way we can report a task progress in
    live without printing many lines on the terminal. Doing so, some artifact
    may appears if we are overwriting a long previous line by a shorter one
    (the end of the previous line may not be erased). This class mainly takes
    care of that. In addition it does not overwrite a line by exactly the
    same one to prevent useless refresh of the terminal. Finally, it adjusts
    its output when not printing to a terminal (e.g. a file). When using
    this object your message should not contains the "\\r" or "\\n" character,
    since it may cause confusion. Instead you should use the provided methods.
    """

    def __init__(self, output=sys.stdout, isatty=None, quiet=False,
                 color_mode="auto"):
        self._termnfo = TermInfo(output, color_mode)
        self._output = output
        self._isatty = self._termnfo.isatty if isatty is None else isatty
        self._quiet = quiet
        self.reset()

    def reset(self):
        self._prev_line = None
        self._last_is_nl = True

    def _write(self, string):
        self._last_is_nl = string.endswith("\n")
        self._output.write(string)

    def write(self, string):
        if self._quiet:
            return
        self._write(string)

    def write_nl(self, line, auto=True):
        self.write(line)
        self.new_line(auto=auto)

    def new_line(self, auto=True):
        if not auto or not self._last_is_nl:
            self.write("\n")
        self.reset()

    def _get_termwidth(self):
        assert self._isatty
        return self._termnfo.columns

    def overwrite(self, line):
        # Do nothing if the line has not changed.
        if self._prev_line is not None and self._prev_line == line:
            return
        written_line = line
        if self._isatty:
            self.write("\r")
            termwidth = self._get_termwidth()
            if termwidth:
                truncinfo = ansi_string_truncinfo(line, termwidth)
                trunc_pos, line_visual_len, line_has_ansi = truncinfo
                written_line = line[:trunc_pos]
        self.write(written_line)
        if not self._isatty:
            self.write("\n")
        if self._isatty and self._prev_line is not None:
            truncinfo = ansi_string_truncinfo(self._prev_line, termwidth)
            _, prev_line_visual_len, _ = truncinfo
            if line_visual_len < prev_line_visual_len:
                eraser = ""
                if line_has_ansi:
                    eraser += self._termnfo.reset_all
                eraser += " " * (prev_line_visual_len - line_visual_len)
                self.write(eraser)
        self._prev_line = line
        self._output.flush()

    def overwrite_nl(self, line, auto=True):
        self.overwrite(line)
        self.new_line(auto=auto)

    @property
    def prev_line(self):
        return self._prev_line

    @property
    def output(self):
        return self._output

    @property
    def isatty(self):
        return self._isatty

    @property
    def quiet(self):
        return self._quiet

    def write_exception(self):
        self.new_line()
        for line in traceback.format_exc().splitlines():
            self.write_nl(line)

    @property
    def term_info(self):
        return self._termnfo
