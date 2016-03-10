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
from enum import Enum

from hunittest.line_printer import strip_ansi_escape
from hunittest.timedeltalib import timedelta_to_hstr
from hunittest.timedeltalib import timedelta_to_unit
from hunittest.stopwatch import StopWatch
from hunittest.utils import mkdir_p
from hunittest.utils import safe_getcwd

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

def get_test_name(test):
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

class Status(Enum):
    """Possible test status.
    """

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"
    XFAIL = "xfail"
    XPASS = "xpass"
    RUNNING = "running"

    @classmethod
    def stopped(cls):
        """Yield all status representing a stopped test."""
        for status in cls:
            if status is not cls.RUNNING:
                yield status

    def is_erroneous(self):
        """Return whether this status is considered as an erroneous test status.
        """
        return self is self.FAIL or self is self.ERROR or self is self.XPASS

class StatusCounters:
    """Hold test counters for each possible status.
    """

    @staticmethod
    def name(status):
        return "{}_count".format(status.value)

    def __init__(self):
        for status in Status.stopped():
            self.set(status, 0)

    def get(self, status):
        return getattr(self, self.name(status))

    def set(self, status, value):
        setattr(self, self.name(status), value)

    def inc(self, status, inc=1):
        v = self.get(status)
        self.set(status, v+inc)

    def is_successful(self):
        return self.fail_count \
            == self.error_count \
            == self.xpass_count \
            == 0

class ResultPrinter:

    _STATUS_MAXLEN = max(len(s.value) for s in Status)

    def __init__(self, printer, top_level_directory,
                 log_filename=None,
                 strip_unittest_traceback=False,
                 show_progress=True):
        self._printer = _LogLinePrinter(printer, log_filename)
        self._top_level_directory = top_level_directory
        self._strip_unittest_traceback=strip_unittest_traceback
        self._show_progress = show_progress
        self._hbar_len = None
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

    def status_color(self, status):
        return getattr(self, "{}_COLOR".format(status.value.upper()))

    def format_test_status(self, status, aligned=True):
        msg = status.value.upper()
        if aligned:
            formatter = "{{:^{:d}}}".format(self._STATUS_MAXLEN)
        else:
            formatter = "{}"
        return self.status_color(status) \
            + formatter.format(msg) \
            + self.RESET

    def _print_progress_message(self, test_name, test_status,
                                status_counters, progress,
                                mean_split_time, last_split_time):
        counters = {}
        counter_formats = []
        for status in Status.stopped():
            counters[status.value] = self.status_color(status) \
                                     + str(status_counters.get(status)) \
                                     + self.RESET
            counter_formats.append("{{{s}}}".format(s=status.value))
        prefix_formatter = "[{progress:>4.0%}|{mean_split_time:.2f}ms|" \
                           + "|".join(f for f in counter_formats) \
                           + "] {test_status}: "
        suffix_formatter = " ({elapsed})"
        prefix = prefix_formatter.format(
            progress=progress,
            test_status=self.format_test_status(test_status),
            mean_split_time=timedelta_to_unit(mean_split_time,
                                              "ms"),
            **counters)
        if test_status != Status.RUNNING \
           and last_split_time is not None:
            suffix = suffix_formatter.format(
                elapsed=timedelta_to_hstr(last_split_time))
        else:
            suffix = ""
        self._printer.overwrite_message(prefix, test_name,
                                        suffix, ellipse_index=1)

    def print_message(self, test, test_status, status_counters, progress,
                      mean_split_time, last_split_time,
                      err=None, reason=None):
        test_name = get_test_name(test)
        if self._show_progress:
            self._print_progress_message(test_name, test_status,
                                         status_counters, progress,
                                         mean_split_time, last_split_time)
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
        test_name = get_test_name(test)
        msg = "{status}: {name}"\
            .format(status=self.format_test_status(test_status, aligned=False),
                    name=test_name)
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
        msg = "{status}: {name}: {reason}"\
            .format(status=self.format_test_status(test_status, aligned=False),
                    name=get_test_name(test),
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

    def print_ios(self, test, stdout_value, stderr_value):
        if not stdout_value and not stderr_value:
            return
        if test._outcome is None or test._outcome.success:
            # If the test pass the header was not printed yet by
            # _print_error.
            self._print_header(test, Status.PASS)
        self._print_io(test, stdout_value, "stdout")
        self._print_io(test, stderr_value, "stderr")
        if stdout_value or stderr_value:
            self._printer.log_write_nl("-" * self._hbar_len)

    def _format_run_status(self, status_counters):
        if status_counters.is_successful():
            color = self.PASS_COLOR
        else:
            color = self.FAIL_COLOR
        return color + "Ran" + self.RESET

    def print_summary(self,
            tests_run,
            prev_status_counters,
            status_counters,
            total_time,
            mean_split_time):
        ### Print main summary
        formatter = "{run_status} {total_count} tests in "\
                    "{total_time} (avg: {mean_split_time})"
        msg = formatter.format(
            run_status=self._format_run_status(status_counters),
            total_count=tests_run,
            total_time=timedelta_to_hstr(total_time),
            mean_split_time=timedelta_to_hstr(mean_split_time))
        self._printer.log_overwrite_nl(msg)
        ### Print detailed summary
        counters = {}
        counter_formats = []
        for status in Status.stopped():
            count = status_counters.get(status)
            if prev_status_counters is None:
                count_delta = 0
            else:
                count_delta = count - prev_status_counters[status.value]
            if count > 0 or count_delta != 0:
                s = self.status_color(status) + str(count)
                if count_delta != 0:
                    s += "({:+d})".format(count_delta)
                s += self.RESET
                counters[status.value] = s
                counter_formats.append("{{{s}}} {s}".format(s=status.value))
        # Print detailed summary only if there were tests.
        if counter_formats:
            msg = " ".join(counter_formats).format(**counters)
            self._printer.log_write_nl(msg)

    def close(self):
        self._printer.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()
        return False

class BaseResult:
    """Root result object used has base class for super delegation chain.
    """

    def __init__(self):
        self._should_stop = False

    @property
    def shouldStop(self):
        return self._should_stop

    def stop(self):
        self._should_stop = True

    def startTest(self, test):
        # the delegation chain stops here
        assert not hasattr(super(), 'startTest')

    def stopTest(self, test):
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')

    def startTestRun(self):
        # print("startTestRun")
        pass

    def stopTestRun(self):
        # print("stopTesRun")
        pass

    def addSubTest(self, test, subtest, outcome):
        assert False

    def addSuccess(self, test):
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.PASS)

    def addFailure(self, test, err):
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.FAIL, err=err)

    def addError(self, test, err):
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.ERROR, err=err)

    def addSkip(self, test, reason):
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.SKIP, reason=reason)

    def addExpectedFailure(self, test, err):
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.XFAIL, err=err)

    def addUnexpectedSuccess(self, test):
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.XPASS)

    def addOutcome(self, test, status, err=None, reason=None):
        """Called by all outcome callback.

        Introduced to ease addition of behavior for all possible test outcomes.
        """
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')

class Failfast(BaseResult):

    def __init__(self, failfast=False, **kwds):
        super().__init__(**kwds)
        self._failfast = failfast
        self._last_traceback = None

    @property
    def failfast(self):
        return self._failfast

    @property
    def last_traceback(self):
        return self._last_traceback

    def addOutcome(self, test, status, err=None, reason=None):
        super().addOutcome(test, status, err, reason)
        if self._failfast and status.is_erroneous():
            if err is not None:
                self._last_traceback = err[2]
            self.stop()

class CheckCWDDidNotChanged(BaseResult):
    """Check whether current working directory has changed after test execution.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, **kwds):
        super().__init__(**kwds)

    def startTest(self, test):
        self.old_cwd = safe_getcwd()
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        new_cwd = safe_getcwd()
        if self.old_cwd is None or new_cwd is None \
           or self.old_cwd != new_cwd:
            raise RuntimeError("working directory changed during test")

class CaptureStdio(BaseResult):
    """Capture and store test's stdout and stderr.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, buffer=True, **kwds):
        super().__init__(**kwds)
        self.buffer = buffer
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._stdout_buffer = io.StringIO()
        self._stderr_buffer = io.StringIO()
        self._stdout_value = None
        self._stderr_value = None

    def startTest(self, test):
        if self.buffer:
            self._setupStdout()
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        if self.buffer:
            self._stdout_value = self._stdout_buffer.getvalue()
            self._stderr_value = self._stderr_buffer.getvalue()
            self._restoreStdout()

    def _setupStdout(self):
        sys.stdout = self._stdout_buffer
        sys.stderr = self._stderr_buffer
        self._stdout_value = None
        self._stderr_value = None

    def _restoreStdout(self):
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self._stdout_buffer.seek(0)
        self._stdout_buffer.truncate()
        self._stderr_buffer.seek(0)
        self._stderr_buffer.truncate()

    @property
    def stdout_value(self):
        return self._stdout_value

    @property
    def stderr_value(self):
        return self._stderr_value

class TestExecStopwatch(BaseResult):
    """Time test execution using a stopwatch.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, **kwds):
        super().__init__(**kwds)
        self.stopwatch = StopWatch()

    def startTest(self, test):
        if not self.stopwatch.is_started:
            self.stopwatch.start()
        super().startTest(test)

    def addOutcome(self, test, status, err=None, reason=None):
        self.stopwatch.split()
        super().addOutcome(test, status, err, reason)

class RunProgress(BaseResult):
    """Count running and ran tests.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, total_tests, **kwds):
        super().__init__(**kwds)
        self._tests_run = 0
        self._total_tests = total_tests

    @property
    def testsRun(self):
        return self._tests_run

    @property
    def total_tests(self):
        return self._total_tests

    @property
    def progress(self):
        return self._tests_run / self._total_tests

    def startTest(self, test):
        self._tests_run += 1
        super().startTest(test)

class StatusTracker(BaseResult):

    def __init__(self, status_db, **kwds):
        super().__init__(**kwds)
        self._status_db = status_db
        self.status_counters = StatusCounters()

    def addOutcome(self, test, status, err=None, reason=None):
        super().addOutcome(test, status, err, reason)
        self.status_counters.inc(status)

    def wasSuccessful(self):
        return self.status_counters.is_successful()

    @property
    def status_scores(self):
        return {status.value:self.status_counters.get(status)
                for status in Status.stopped()}

    def save_status(self):
        return self._status_db.save(self.status_scores)

    def load_status(self):
        return self._status_db.load()

class HTestResult(CheckCWDDidNotChanged,
                  Failfast,
                  RunProgress,
                  StatusTracker,
                  TestExecStopwatch,
                  CaptureStdio):

    def __init__(self, result_printer,
                 **kwds):
        super().__init__(**kwds)
        self._printer = result_printer
        self._error_test_specs = set()
        self._succeed_test_specs = set()

    def _print_outcome_message(self, test, test_status, err=None, reason=None):
        test_name = get_test_name(test)
        if err is None:
            self._succeed_test_specs.add(test_name)
        else:
            self._error_test_specs.add(test_name)
        self._printer.print_message(test, test_status, self.status_counters,
                                    self.progress,
                                    self.stopwatch.mean_split_time,
                                    self.stopwatch.last_split_time,
                                    err=err, reason=reason)

    def startTest(self, test):
        self._printer.print_message(test, Status.RUNNING, self.status_counters,
                                    self.progress,
                                    self.stopwatch.mean_split_time,
                                    self.stopwatch.last_split_time)
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        self._printer.print_ios(test, self.stdout_value, self.stderr_value)

    def addOutcome(self, test, status, err=None, reason=None):
        super().addOutcome(test, status, err, reason)
        self._print_outcome_message(test, status, err, reason)

    def print_summary(self):
        prev_counters = self.load_status()
        self._printer.print_summary(
            self._tests_run,
            prev_counters,
            self.status_counters,
            self.stopwatch.total_split_time,
            self.stopwatch.mean_split_time)
        self.save_status()

    @property
    def error_test_specs(self):
        return self._error_test_specs

    @property
    def succeed_test_specs(self):
        return self._succeed_test_specs
