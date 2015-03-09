# -*- encoding: utf-8 -*-
"""A module to print status line on terminal.
"""


import sys
import os
import re


ANSI_ESCAPE_PATTERN = r'\x1b.*?m'

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

    def __init__(self, output=sys.stdout, isatty=None, quiet=False):
        self.output = output
        self.isatty = self._isatty_output() if isatty is None else isatty
        self._termsize = get_terminal_size() if self.isatty else None
        self.quiet = quiet
        self.reset()

    def _isatty_output(self):
        try:
            fileno = self.output.fileno()
        except:
            return False
        else:
            return os.isatty(fileno)

    def reset(self):
        self.prev_line = None
        self._last_is_nl = True

    def _write(self, string):
        self._last_is_nl = string.endswith("\n")
        self.output.write(string)

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

    def _truncate_line(self, line):
        if self._termsize is None:
            return line
        tw = self._termsize[0]
        return truncate_line(line, tw)

    def overwrite(self, line):
        # Do nothing if the line has not changed.
        if self.prev_line is not None and self.prev_line == line:
            return
        if self.isatty:
            self.write("\r")
        self.write(line)
        if not self.isatty:
            self.write("\n")
        if self.isatty and self.prev_line is not None:
            len_line = len(strip_ansi_escape(line))
            len_prev_line = len(strip_ansi_escape(self.prev_line))
            if len_line < len_prev_line:
                self.write(" " * (len_prev_line - len_line))
        self.prev_line = line
        self.output.flush()

    def overwrite_nl(self, line, auto=True):
        self.overwrite(line)
        self.new_line(auto=auto)
