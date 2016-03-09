# -*- encoding: utf-8 -*-
"""Routines and classes to report unittest result.
"""


import traceback
import io
import functools
import sys
import os
import re
import unittest
import json

from hunittest.line_printer import strip_ansi_escape
from hunittest.timedeltalib import timedelta_to_hstr
from hunittest.timedeltalib import timedelta_to_unit
from hunittest.stopwatch import StopWatch
from hunittest.utils import mkdir_p
from hunittest.utils import safe_getcwd

def failfast_decorator(method):
    @functools.wraps(method)
    def inner(self, test, err=None):
        if getattr(self, 'failfast', False):
            self._last_traceback = err[2]
            self.stop()
        return method(self, test, err)
    return inner

class _LogLinePrinter(object):
    """Proxy over a LinePrinter.

    This proxy offers some more methods starting by "log_" allowing to
    also log the printed message to a file.
    """

    def __init__(self, printer, filename=None):
        self._printer = printer
        self._filename = filename
        self._file = None
        if self._filename is not None:
            mkdir_p(os.path.dirname(filename))
            self._file = open(filename, "w")

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None

    def __del__(self):
        self.close()

    @property
    def term_info(self):
        return self._printer.term_info

    def overwrite_message(self, *args, **kwargs):
        return self._printer.overwrite_message(*args, **kwargs)

    def overwrite(self, line):
        return self._printer.overwrite(line)

    def overwrite_nl(self, *args, **kwargs):
        return self._printer.overwrite_nl(*args, **kwargs)

    def write_nl(self, *args, **kwargs):
        return self._printer.write_nl(*args, **kwargs)

    def write(self, string):
        return self._printer.write(string)

    def log_overwrite(self, line):
        self.overwrite(line)
        self._log(line)

    def log_overwrite_nl(self, msg):
        self.overwrite_nl(msg)
        self._log(msg)

    def log_write_nl(self, msg):
        self.write_nl(msg)
        self._log(msg)

    def log_write(self, msg):
        self.write(msg)
        self._log(msg, False)

    def _log(self, msg, nl=True):
        if self._file is None:
            return
        self._file.write(msg)
        if nl:
            self._file.write("\n")

def _full_test_name(test):
    """Return the full name of the given test object.

    A string of the form: pkg.mod.Class.test_method
    """
    return ".".join((
        test.__module__,
        type(test).__name__,
        test._testMethodName,
    ))

class StatusDB:
    """A tiny DB to store status counters.

    Status counters are the number of test falling in each category: pass, fail,
    error, xpass, etc...

    It is used to show the difference between to similar run.
    """

    def __init__(self, filename):
        self.filename = filename

    def save(self, status_scores):
        if self.filename is None:
            return
        mkdir_p(os.path.dirname(self.filename))
        with open(self.filename, "w") as stream:
            json.dump(status_scores, stream)

    def load(self):
        if self.filename is None:
            return
        try:
            with open(self.filename) as stream:
                return json.load(stream)
        except FileNotFoundError:
            return

class HTestResult(object):

    ALL_STATUS = "pass fail error skip xfail xpass".split()
    _STATUS_MAXLEN = max(len(s) for s in ALL_STATUS+["running"])

    @staticmethod
    def status_counter_name(status):
        return "_{}_count".format(status)

    def __init__(self, printer, total_tests, top_level_directory,
                 failfast=False,
                 log_filename=None,
                 status_db=None,
                 strip_unittest_traceback=False,
                 show_progress=True):
        self._failfast = failfast
        self._tests_run = 0
        self._should_stop = False
        self._printer = _LogLinePrinter(printer, log_filename)
        self._total_tests = total_tests
        self._top_level_directory = top_level_directory
        self._status_db = status_db
        self._strip_unittest_traceback=strip_unittest_traceback
        self._show_progress = show_progress
        for status in self.ALL_STATUS:
            self._set_status_counter(status, 0)
        self._stopwatch = StopWatch()
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._stdout_buffer = io.StringIO()
        self._stderr_buffer = io.StringIO()
        self._hbar_len = None
        self._last_traceback = None
        self._error_test_specs = set()
        self._succeed_test_specs = set()
        self.PASS_COLOR = self._printer.term_info.fore_green
        self.FAIL_COLOR = self._printer.term_info.fore_red
        self.SKIP_COLOR = self._printer.term_info.fore_blue
        self.XFAIL_COLOR = self._printer.term_info.fore_cyan
        self.XPASS_COLOR = self._printer.term_info.fore_yellow
        self.ERROR_COLOR = self._printer.term_info.fore_magenta
        self.RUNNING_COLOR = self._printer.term_info.fore_white
        self.RESET = self._printer.term_info.reset_all
        self.TRACE_HL = self._printer.term_info.fore_white \
                        + self._printer.term_info.bold

    @property
    def shouldStop(self):
        return self._should_stop

    @property
    def buffer(self):
        return True

    @buffer.setter
    def buffer(self, value):
        if not value:
            raise NotImplementedError("we cannot support un-buffered IO.")

    @property
    def failfast(self):
        return self._failfast

    @property
    def testsRun(self):
        return self._tests_run

    @property
    def total_tests(self):
        return self._total_tests

    @property
    def progress(self):
        return self._tests_run / self._total_tests

    @property
    def pass_count(self):
        return self._pass_count

    @property
    def fail_count(self):
        return self._fail_count

    @property
    def skip_count(self):
        return self._skip_count

    @property
    def xfail_count(self):
        return self._xfail_count

    @property
    def xpass_count(self):
        return self._xpass_count

    @property
    def error_count(self):
        return self._error_count

    def status_color(self, status):
        return getattr(self, "{}_COLOR".format(status.upper()))

    def get_status_counter(self, status):
        return getattr(self, self.status_counter_name(status))

    def _set_status_counter(self, status, value):
        setattr(self, self.status_counter_name(status), value)

    def _inc_status_counter(self, status, inc=1):
        v = self.get_status_counter(status)
        self._set_status_counter(status, v+inc)

    def format_test_status(self, status, aligned=True):
        msg = status.upper()
        if aligned:
            formatter = "{{:^{:d}}}".format(self._STATUS_MAXLEN)
        else:
            formatter = "{}"
        return self.status_color(status) \
            + formatter.format(msg) \
            + self.RESET

    def _print_progress_message(self, full_test_name, test_status):
        counters = {}
        counter_formats = []
        for status in self.ALL_STATUS:
            counters[status] = self.status_color(status) \
                               + str(self.get_status_counter(status)) \
                               + self.RESET
            counter_formats.append("{{{s}}}".format(s=status))
        prefix_formatter = "[{progress:>4.0%}|{mean_split_time:.2f}ms|" \
                           + "|".join(f for f in counter_formats) \
                           + "] {test_status}: "
        suffix_formatter = " ({elapsed})"
        prefix = prefix_formatter.format(
            progress=self.progress,
            test_status=self.format_test_status(test_status),
            mean_split_time=timedelta_to_unit(self._stopwatch.mean_split_time,
                                              "ms"),
            **counters)
        if test_status != "running" \
           and self._stopwatch.last_split_time is not None:
            suffix = suffix_formatter.format(
                elapsed=timedelta_to_hstr(self._stopwatch.last_split_time))
        else:
            suffix = ""
        self._printer.overwrite_message(prefix, full_test_name,
                                        suffix, ellipse_index=1)

    def _print_outcome_message(self, test, test_status, err=None, reason=None):
        self._stopwatch.split()
        self._inc_status_counter(test_status)
        full_test_name = _full_test_name(test)
        if err is None:
            self._succeed_test_specs.add(full_test_name)
        else:
            self._error_test_specs.add(full_test_name)
        self._print_message(test, test_status, err=err, reason=reason)

    def _print_message(self, test, test_status, err=None, reason=None):
        full_test_name = _full_test_name(test)
        if self._show_progress:
            self._print_progress_message(full_test_name, test_status)
        if err is not None:
            self._print_error(test, test_status, err)
        if reason is not None:
            self._print_reason(test, test_status, reason)

    def _extract_filename_from_error_line(self, line):
        mo = re.match(r'^\s+File "(.*)", line \d+, in .*$', line,
                      re.MULTILINE)
        if mo:
            return mo.group(1)

    def _is_user_filename(self, line):
        filename = self._extract_filename_from_error_line(line)
        if filename is None:
            return None
        return filename.startswith(self._top_level_directory)

    def _is_unittest_filename(self, line):
        filename = self._extract_filename_from_error_line(line)
        if filename is None:
            return None
        return filename.startswith(os.path.dirname(unittest.__file__))

    def _print_header(self, test, test_status):
        full_test_name = _full_test_name(test)
        msg = "{test_status}: {fullname}"\
            .format(test_status=self.format_test_status(test_status,
                                                        aligned=False),
                    fullname=full_test_name)
        self._hbar_len = len(strip_ansi_escape(msg))
        self._printer.log_overwrite_nl("-" * self._hbar_len)
        self._printer.log_overwrite_nl(msg)


    def _print_error(self, test, test_status, err):
        assert err is not None
        self._print_header(test, test_status)
        self._printer.log_write_nl("-" * self._hbar_len)
        ### Print exception traceback
        all_lines = traceback.format_exception(*err)
        for i in range(len(all_lines)-1):
            lines = all_lines[i]
            is_user_filename = self._is_user_filename(lines)
            skip_next = False
            for line in lines.splitlines():
                if skip_next:
                    continue
                if is_user_filename:
                    formatted_line = self.TRACE_HL + line + self.RESET
                else:
                    if self._strip_unittest_traceback \
                       and self._is_unittest_filename(line):
                        skip_next = True
                        formatted_line = None
                    else:
                        formatted_line = line
                if formatted_line is not None:
                    self._printer.log_write_nl(formatted_line)
        ### Print exception message
        err_lines = str(err[1]).splitlines()
        if len(err_lines) == 0:
            self._printer.log_write_nl(self.status_color(test_status) \
                                       + err[0].__name__ \
                                       + self.RESET)
        else:
            self._printer.log_write_nl(self.status_color(test_status) \
                                       + err[0].__name__ \
                                       + self.RESET \
                                       + ": " \
                                       + err_lines[0])
            for i in range(1, len(err_lines)):
                self._printer.log_write_nl(err_lines[i])

    def _print_reason(self, test, test_status, reason):
        assert reason is not None
        msg = "{test_status}: {fullname}: {reason}"\
            .format(test_status=self.format_test_status(test_status,
                                                        aligned=False),
                    fullname=_full_test_name(test),
                    reason=reason)
        self._printer.log_overwrite_nl(msg)

    def _print_io(self, test, output, channel):
        if not output:
            return
        assert self._hbar_len is not None
        chanstr = " {} ".format(channel.upper())
        start = (self._hbar_len - len(chanstr)) // 2
        msg = "-" * start
        msg += chanstr
        msg += "-" * start
        self._printer.log_write_nl(msg)
        for line in output.splitlines():
            self._printer.log_write_nl(line)

    def _print_ios(self, test, stdout_value, stderr_value):
        if not stdout_value and not stderr_value:
            return
        if test._outcome is None or test._outcome.success:
            # If the test pass the header was not printed yet by
            # _print_error.
            self._print_header(test, "pass")
        self._print_io(test, stdout_value, "stdout")
        self._print_io(test, stderr_value, "stderr")
        if stdout_value or stderr_value:
            self._printer.log_write_nl("-" * self._hbar_len)

    def startTest(self, test):
        self._tests_run += 1
        if not self._stopwatch.is_started:
            self._stopwatch.start()
        self._print_message(test, "running")
        self.old_cwd = safe_getcwd()
        self._setupStdout()

    def _setupStdout(self):
        sys.stdout = self._stdout_buffer
        sys.stderr = self._stderr_buffer

    def stopTest(self, test):
        new_cwd = safe_getcwd()
        if self.old_cwd is None or new_cwd is None \
           or self.old_cwd != new_cwd:
            raise RuntimeError("working directory changed during test")
        stdout_value = self._stdout_buffer.getvalue()
        stderr_value = self._stderr_buffer.getvalue()
        self._restoreStdout()
        self._print_ios(test, stdout_value, stderr_value)

    def _restoreStdout(self):
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self._stdout_buffer.seek(0)
        self._stdout_buffer.truncate()
        self._stderr_buffer.seek(0)
        self._stderr_buffer.truncate()

    def startTestRun(self):
        # print("startTestRun")
        pass

    def stopTestRun(self):
        # print("stopTesRun")
        pass

    def addSubTest(self, test, subtest, outcome):
        assert False

    def addSuccess(self, test):
        # print("addSuccess", repr(test))
        self._print_outcome_message(test, "pass")

    @failfast_decorator
    def addFailure(self, test, err):
        # print("addFailure", repr(test), repr(err))
        self._print_outcome_message(test, "fail", err=err)

    @failfast_decorator
    def addError(self, test, err):
        # print("addError", repr(test), repr(err))
        self._print_outcome_message(test, "error", err=err)

    def addSkip(self, test, reason):
        self._print_outcome_message(test, "skip", reason=reason)

    def addExpectedFailure(self, test, err):
        self._print_outcome_message(test, "xfail")

    @failfast_decorator
    def addUnexpectedSuccess(self, test, err=None):
        self._print_outcome_message(test, "xpass")

    def _format_run_status(self):
        if self.wasSuccessful():
            color = self.PASS_COLOR
        else:
            color = self.FAIL_COLOR
        return color + "Run" + self.RESET

    def print_summary(self):
        prev_counters = self._load_status()
        ### Print main summary
        formatter = "{run_status} {total_count} tests in "\
                    "{total_time} (avg: {mean_split_time})"
        msg = formatter.format(
            run_status=self._format_run_status(),
            total_count=self._tests_run,
            total_time=timedelta_to_hstr(self._stopwatch.total_split_time),
            mean_split_time=timedelta_to_hstr(self._stopwatch.mean_split_time))
        self._printer.log_overwrite_nl(msg)
        ### Print detailed summary
        counters = {}
        counter_formats = []
        for status in self.ALL_STATUS:
            count = self.get_status_counter(status)
            if prev_counters is None:
                count_delta = 0
            else:
                count_delta = count - prev_counters[status]
            if count > 0 or count_delta != 0:
                s = self.status_color(status) + str(count)
                if count_delta != 0:
                    s += "({:+d})".format(count_delta)
                s += self.RESET
                counters[status] = s
                counter_formats.append("{{{s}}} {s}".format(s=status))
        # Print detailed summary only if there were tests.
        if counter_formats:
            msg = " ".join(counter_formats).format(**counters)
            self._printer.log_write_nl(msg)
        self._write_status()

    def stop(self):
        self._should_stop = True

    def wasSuccessful(self):
        return self.fail_count \
            == self.error_count \
            == self.xpass_count \
            == 0

    def close_log_file(self):
        self._printer.close()

    @property
    def log_filename(self):
        return self._printer.filename

    @property
    def last_traceback(self):
        return self._last_traceback

    @property
    def error_test_specs(self):
        return self._error_test_specs

    @property
    def succeed_test_specs(self):
        return self._succeed_test_specs

    @property
    def status_scores(self):
        return {status:self.get_status_counter(status)
                for status in self.ALL_STATUS}

    def _write_status(self):
        return self._status_db.save(self.status_scores)

    def _load_status(self):
        return self._status_db.load()
