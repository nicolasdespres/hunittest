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

# TODO(Nicolas Despres): Handle terminal resize events.

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
        self._cr = self._termnfo.carriage_return
        if not self._cr:
            self._cr = "\r"
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

    def _write_termctrl(self, string):
        """Use it only to write special terminal control character.

        Most of the time you must use write().
        """
        if self._quiet:
            return
        self._output.write(string)
        self._output.flush()

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

    def overwrite_message(self, *args, ellipse_index=None, ellipse="..."):
        if ellipse_index is None or not self._isatty:
            return self.overwrite("".join(args))
        termwidth = self._get_termwidth()
        if not termwidth:
            return self.overwrite("".join(args))
        prefix = "".join(args[:ellipse_index])
        p_trunc, p_vlen, _ = ansi_string_truncinfo(prefix, termwidth)
        if p_trunc < len(prefix):
            return self.overwrite("".join(args))
        suffix = "".join(args[ellipse_index+1:])
        s_trunc, s_vlen, _ = ansi_string_truncinfo(suffix, termwidth-p_vlen)
        msg = args[ellipse_index]
        m_trunc, m_vlen, m_ansi = ansi_string_truncinfo(msg,
                                                        termwidth-p_vlen-s_vlen)
        assert m_ansi is False, "we do not support ellipse in the middle with ansi char at the moment"
        if m_trunc < len(msg):
            p = (m_vlen - len(ellipse)) // 2
            msg = msg[:p] + ellipse + msg[-p:]
        return self.overwrite(prefix + msg[:m_trunc] + suffix)

    def overwrite(self, line):
        # Do nothing if the line has not changed.
        if self._prev_line is not None and self._prev_line == line:
            return
        written_line = line
        if self._isatty:
            self.write(self._cr)
            termwidth = self._get_termwidth()
            if termwidth:
                truncinfo = ansi_string_truncinfo(line, termwidth)
                trunc_pos, line_visual_len, line_has_ansi = truncinfo
                written_line = line[:trunc_pos]
        self.write(written_line)
        if not self._isatty:
            self.write("\n")
        if self._isatty and self._prev_line is not None:
            if self._termnfo.clear_eol:
                self.write(self._termnfo.clear_eol)
            else:
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

    def show_cursor(self):
        self._write_termctrl(self._termnfo.show_cursor)

    def hide_cursor(self):
        self._write_termctrl(self._termnfo.hide_cursor)

    def __enter__(self):
        self.hide_cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.show_cursor()
        return False
