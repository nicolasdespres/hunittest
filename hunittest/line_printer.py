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
from types import TracebackType
from typing import Self, TextIO

from hunittest.termlib import ansi_string_truncinfo
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

    def __init__(
            self, output: TextIO = sys.stdout, isatty: bool | None = None,
            quiet: bool = False, color_mode: str = "auto",
            verbose: bool = False) -> None:
        self._termnfo = TermInfo(output, color_mode)
        self._cr: str | None = self._termnfo.carriage_return
        if not self._cr:
            self._cr = "\r"
        self._output: TextIO = output
        self._isatty: bool = self._termnfo.isatty if isatty is None else isatty
        self._quiet: bool = quiet
        self._verbose: bool = verbose
        self.reset()

    def reset(self) -> None:
        self._prev_line: str | None = None
        self._last_is_nl: bool = True

    def _write(self, string: str) -> None:
        self._last_is_nl = string.endswith("\n")
        self._output.write(string)

    def write(self, string: object) -> None:
        if not isinstance(string, str):
            raise TypeError("string must be str, not {}"
                            .format(type(string).__name__))
        if self._quiet:
            return
        self._write(string)

    def _write_termctrl(self, string: str) -> None:
        """Use it only to write special terminal control character.

        Most of the time you must use write().
        """
        if self._quiet:
            return
        self._output.write(string)
        self._output.flush()

    def write_nl(self, line: object, auto: bool = True) -> None:
        if not isinstance(line, str):
            raise TypeError("line must be str, not {}"
                            .format(type(line).__name__))
        self.write(line)
        self.new_line(auto=auto)

    def new_line(self, auto: bool = True) -> None:
        if not auto or not self._last_is_nl:
            self.write("\n")
        self.reset()

    def _get_termwidth(self) -> int | None:
        assert self._isatty
        return self._termnfo.columns

    def overwrite_message(
            self, *args: str, ellipse_index: int | None = None,
            ellipse: str = "...") -> None:
        if ellipse_index is None or not self.has_overwrite:
            return self.overwrite("".join(args))
        termwidth = self._get_termwidth()
        if not termwidth:
            return self.overwrite("".join(args))
        prefix = "".join(args[:ellipse_index])
        p_trunc, p_vlen, _ = ansi_string_truncinfo(prefix, termwidth)
        if p_trunc < len(prefix):
            return self.overwrite("".join(args))
        suffix = "".join(args[ellipse_index+1:])
        _, s_vlen, _ = ansi_string_truncinfo(suffix, termwidth-p_vlen)
        msg = args[ellipse_index]
        m_trunc, m_vlen, m_ansi = ansi_string_truncinfo(msg,
                                                        termwidth-p_vlen-s_vlen)
        assert m_ansi is False, "we do not support ellipse in the middle with ansi char at the moment"
        if m_trunc < len(msg):
            p = (m_vlen - len(ellipse)) // 2
            msg = msg[:p] + ellipse + msg[-p:]
        return self.overwrite(prefix + msg[:m_trunc] + suffix)

    def overwrite(self, line: object) -> None:
        if not isinstance(line, str):
            raise TypeError("line must be str, not {}"
                            .format(type(line).__name__))
        # Do nothing if the line has not changed.
        if self._prev_line is not None and self._prev_line == line:
            return
        written_line = line
        termwidth: int | None = None
        line_visual_len = len(line)
        line_has_ansi = False
        if self.has_overwrite:
            self.write(self._cr)
            termwidth = self._get_termwidth()
            if termwidth:
                truncinfo = ansi_string_truncinfo(line, termwidth)
                trunc_pos, line_visual_len, line_has_ansi = truncinfo
                written_line = line[:trunc_pos]
        self.write(written_line)
        if not self.has_overwrite:
            self.write("\n")
        if self.has_overwrite and self._prev_line is not None:
            if self._termnfo.clear_eol:
                self.write(self._termnfo.clear_eol)
            elif termwidth is not None:
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

    def overwrite_nl(self, line: object, auto: bool = True) -> None:
        if not isinstance(line, str):
            raise TypeError("line must be str, not {}"
                            .format(type(line).__name__))
        self.overwrite(line)
        self.new_line(auto=auto)

    @property
    def prev_line(self) -> str | None:
        return self._prev_line

    @property
    def output(self) -> TextIO:
        return self._output

    @property
    def isatty(self) -> bool:
        return self._isatty

    @property
    def quiet(self) -> bool:
        return self._quiet

    @property
    def verbose(self) -> bool:
        return self._verbose

    @property
    def has_overwrite(self) -> bool:
        return self._isatty and not self._verbose

    def write_exception(self) -> None:
        self.new_line()
        for line in traceback.format_exc().splitlines():
            self.write_nl(line)

    @property
    def term_info(self) -> TermInfo:
        return self._termnfo

    def show_cursor(self) -> None:
        self._write_termctrl(self._termnfo.show_cursor)

    def hide_cursor(self) -> None:
        self._write_termctrl(self._termnfo.hide_cursor)

    def __enter__(self) -> Self:
        self.hide_cursor()
        return self

    def __exit__(
            self, exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None) -> bool:
        self.show_cursor()
        return False
