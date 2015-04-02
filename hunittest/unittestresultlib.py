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

from hunittest.line_printer import strip_ansi_escape
from hunittest.timedeltalib import timedelta_to_hstr
from hunittest.timedeltalib import timedelta_to_unit
from hunittest.stopwatch import StopWatch
from hunittest.utils import mkdir_p

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

class HTestResult(object):

    ALL_STATUS = "success failure error skip expected_failure "\
                 "unexpected_success".split()

    @staticmethod
    def status_counter_name(status):
        return "_{}_count".format(status)

    def __init__(self, printer, total_tests, failfast=False,
                 log_filename=None):
        self._failfast = failfast
        self._tests_run = 0
        self._should_stop = False
        self._printer = _LogLinePrinter(printer, log_filename)
        self._total_tests = total_tests
        for status in self.ALL_STATUS:
            self._set_status_counter(status, 0)
        self._stopwatch = StopWatch()
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._stdout_buffer = io.StringIO()
        self._stderr_buffer = io.StringIO()
        self._hbar_len = None
        self._last_traceback = None
        self._error_test_specs = []
        self.SUCCESS_COLOR = self._printer.term_info.fore_green
        self.FAILURE_COLOR = self._printer.term_info.fore_red
        self.SKIP_COLOR = self._printer.term_info.fore_blue
        self.EXPECTED_FAILURE_COLOR = self._printer.term_info.fore_cyan
        self.UNEXPECTED_SUCCESS_COLOR = self._printer.term_info.fore_yellow
        self.ERROR_COLOR = self._printer.term_info.fore_magenta
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
    def success_count(self):
        return self._success_count

    @property
    def failure_count(self):
        return self._failure_count

    @property
    def skip_count(self):
        return self._skip_count

    @property
    def expected_failure_count(self):
        return self._expected_failure_count

    @property
    def unexpected_success_count(self):
        return self._unexpected_success_count

    @property
    def error_count(self):
        return self._error_count

    def full_test_name(self, test):
        return ".".join((
            test.__module__,
            type(test).__name__,
            test._testMethodName,
        ))

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
        if status == "unexpected_success":
            msg = "~SUCCESS"
        elif status == "expected_failure":
            msg = "~FAILURE"
        else:
            msg = status.upper()
        if aligned:
            formatter = "{:^8}"
        else:
            formatter = "{}"
        return self.status_color(status) \
            + formatter.format(msg) \
            + self.RESET

    def _print_message(self, test, test_status, err=None, reason=None):
        self._stopwatch.split()
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
        suffix = suffix_formatter.format(
            elapsed=timedelta_to_hstr(self._stopwatch.last_split_time))
        msg = self.full_test_name(test)
        self._inc_status_counter(test_status)
        self._printer.overwrite_message(prefix, msg, suffix, ellipse_index=1)
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
        return not filename.startswith(os.path.dirname(unittest.__file__))

    def _print_error(self, test, test_status, err):
        assert err is not None
        full_test_name = self.full_test_name(test)
        self._error_test_specs.append(full_test_name)
        msg = "{test_status}: {fullname}"\
            .format(test_status=self.format_test_status(test_status,
                                                        aligned=False),
                    fullname=full_test_name)
        self._hbar_len = len(strip_ansi_escape(msg))
        self._printer.log_overwrite_nl("-" * self._hbar_len)
        self._printer.log_overwrite_nl(msg)
        self._printer.log_write_nl("-" * self._hbar_len)
        all_lines = traceback.format_exception(*err)
        for i in range(len(all_lines)-1):
            lines = all_lines[i]
            is_user_filename = self._is_user_filename(lines)
            for line in lines.splitlines():
                if is_user_filename:
                    formatted_line = self.TRACE_HL + line + self.RESET
                else:
                    formatted_line = line
                self._printer.log_write_nl(formatted_line)
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
                    fullname=self.full_test_name(test),
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
        if test._outcome is None or test._outcome.success:
            return
        self._print_io(test, stdout_value, "stdout")
        self._print_io(test, stderr_value, "stderr")
        if stdout_value or stderr_value:
            self._printer.log_write_nl("-" * self._hbar_len)

    def startTest(self, test):
        self._tests_run += 1
        if not self._stopwatch.is_started:
            self._stopwatch.start()
        self._setupStdout()

    def _setupStdout(self):
        sys.stdout = self._stdout_buffer
        sys.stderr = self._stderr_buffer

    def stopTest(self, test):
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
        self._print_message(test, "success")

    @failfast_decorator
    def addFailure(self, test, err):
        # print("addFailure", repr(test), repr(err))
        self._print_message(test, "failure", err=err)

    @failfast_decorator
    def addError(self, test, err):
        # print("addError", repr(test), repr(err))
        self._print_message(test, "error", err=err)

    def addSkip(self, test, reason):
        self._print_message(test, "skip", reason=reason)

    def addExpectedFailure(self, test, err):
        self._print_message(test, "expected_failure")

    @failfast_decorator
    def addUnexpectedSuccess(self, test, err=None):
        self._print_message(test, "unexpected_success")

    def _format_run_status(self):
        if self.wasSuccessful():
            color = self.SUCCESS_COLOR
        else:
            color = self.FAILURE_COLOR
        return color + "Run" + self.RESET

    def print_summary(self):
        counters = {}
        counter_formats = []
        for status in self.ALL_STATUS:
            counters[status] = self.status_color(status) \
                               + str(self.get_status_counter(status)) \
                               + self.RESET
            counter_formats.append("{{{s}}} {s}".format(s=status))

        formatter = "{run_status} {total_count} tests in "\
                    "{total_time} (avg: {mean_split_time}): "
        formatter += " ".join(counter_formats)
        msg = formatter.format(
            run_status=self._format_run_status(),
            total_count=self._total_tests,
            total_time=self._stopwatch.total_split_time,
            mean_split_time=self._stopwatch.mean_split_time,
            **counters)
        self._printer.log_overwrite(msg)

    def stop(self):
        self._should_stop = True

    def wasSuccessful(self):
        return self.failure_count \
            == self.error_count \
            == self.unexpected_success_count \
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
