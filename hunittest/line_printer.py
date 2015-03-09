# -*- encoding: utf-8 -*-
"""A module to print status line on terminal.
"""


import sys
import os
import re
import fcntl
import termios
import struct


ANSI_ESCAPE_PATTERN = r'\x1b.*?m'

try:
    from colorama.Style import RESET_ALL as ANSI_RESET_ALL
except ImportError:
    ANSI_RESET_ALL = '\x1b[0m'

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

def get_terminal_size(default_lines=25, default_columns=80):
    env = os.environ
    def ioctl_GWINSZ(fd):
        try:
            cr = struct.unpack('hh',
                               fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
        except:
            return
        return cr
    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            try:
                cr = ioctl_GWINSZ(fd)
            finally:
                os.close(fd)
        except:
            pass
    if not cr:
        cr = (env.get('LINES', default_lines),
              env.get('COLUMNS', default_columns))
    return (int(cr[1]), int(cr[0]))

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
                 default_termwidth=80):
        self._output = output
        self._isatty = self._isatty_output() if isatty is None else isatty
        self.default_termwidth = default_termwidth
        self.quiet = quiet
        self.reset()

    def _isatty_output(self):
        try:
            fileno = self._output.fileno()
        except:
            return False
        else:
            return os.isatty(fileno)

    def reset(self):
        self._prev_line = None
        self._last_is_nl = True

    def _write(self, string):
        self._last_is_nl = string.endswith("\n")
        self._output.write(string)

    def write(self, string):
        if self.quiet:
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
        return get_terminal_size(default_columns=self.default_termwidth)[0]

    def overwrite(self, line):
        # Do nothing if the line has not changed.
        if self._prev_line is not None and self._prev_line == line:
            return
        written_line = line
        if self._isatty:
            self.write("\r")
            termwidth = self._get_termwidth()
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
                    eraser += ANSI_RESET_ALL
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
