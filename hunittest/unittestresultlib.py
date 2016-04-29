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
from collections import namedtuple
from datetime import timedelta
import textwrap

from hunittest.line_printer import strip_ansi_escape
from hunittest.timedeltalib import timedelta_to_hstr as _timedelta_to_hstr
from hunittest.timedeltalib import timedelta_to_unit
from hunittest.stopwatch import StopWatch
from hunittest.utils import mkdir_p
from hunittest.utils import safe_getcwd
from hunittest.utils import load_single_test_case

def timedelta_to_hstr(tdelta):
    return _timedelta_to_hstr(tdelta, precision=2)

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
    # HTestResultServer may pass test name instead of test object.
    if isinstance(test, str):
        return test
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
    STOP = "stop"

    @classmethod
    def stopped(cls):
        """Yield all status representing a stopped test."""
        for status in cls:
            if status is not cls.RUNNING and status is not cls.STOP:
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

def _format_exception(exc_type, exc_value, exc_traceback):
    """Own customization of traceback.format_exception().

    When the result comes from another process the traceback is already
    serialized thus we just have to return it.
    """
    # HTestResultServer passes serialized traceback.
    if isinstance(exc_traceback, list):
        return exc_traceback
    return traceback.format_exception(exc_type, exc_value, exc_traceback)

def _format_subtest_params(params):
    if not params:
        return ''
    return "{{{}}}".format(", ".join("{}={!r}".format(k, v)
                                     for k, v in params.items()))

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
        self.STOP_COLOR = self._printer.term_info.fore_white
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
                                mean_split_time, last_split_time,
                                params=None):
        counters = {}
        counters_format_parts = []
        for status in Status.stopped():
            counter_value = status_counters.get(status)
            if counter_value > 0:
                counters[status.value] = self.status_color(status) \
                                         + str(counter_value) \
                                         + self.RESET
                counters_format_parts.append("{{{s}}}".format(s=status.value))
        if counters_format_parts:
            counter_format = "|" + "|".join(f for f in counters_format_parts)
        else:
            counter_format = ""
        prefix_formatter = "[{progress:>4.0%}|{mean_split_time:.2f}ms" \
                           + counter_format \
                           + "] {test_status}: "
        suffix_formatter = " ({elapsed})"
        prefix = prefix_formatter.format(
            progress=progress,
            test_status=self.format_test_status(test_status),
            mean_split_time=timedelta_to_unit(mean_split_time,
                                              "ms"),
            **counters)
        if test_status != Status.RUNNING \
           and last_split_time is not None \
           and not params:
            suffix = suffix_formatter.format(
                elapsed=timedelta_to_hstr(last_split_time))
        else:
            suffix = ""
        printed_test_name = test_name+_format_subtest_params(params)
        self._printer.overwrite_message(prefix, printed_test_name,
                                        suffix, ellipse_index=1)

    def print_message(self, test, test_status, status_counters, progress,
                      mean_split_time, last_split_time,
                      err=None, reason=None, params=None):
        if test_status is Status.RUNNING:
            self._subtests_printed = False
            self._header_printed = False
        test_name = get_test_name(test)
        if self._show_progress:
            self._print_progress_message(test_name, test_status,
                                         status_counters, progress,
                                         mean_split_time, last_split_time,
                                         params=params)
        if err is not None:
            self._print_error(test, test_status, err, params=params)
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

    def _header_prefix(self, test_status):
        status = self.format_test_status(test_status, aligned=False)
        return "{status}: ".format(status=status)

    def _print_header(self, test, test_status, params=None):
        if self._header_printed:
            return
        test_name = get_test_name(test)
        msg = self._header_prefix(test_status) \
              + "{name}".format(name=test_name)
        self._hbar_len = len(strip_ansi_escape(msg))
        self._printer.log_overwrite_nl("-" * self._hbar_len)
        self._printer.log_write_nl(msg)
        self._print_subtest_params(test_status, params, self._hbar_len)
        self._header_printed = not params

    def _print_subtest_params(self, test_status, params, width):
        if not params:
            return
        prefix_len = len(strip_ansi_escape(self._header_prefix(test_status)))
        for line in textwrap.wrap(_format_subtest_params(params),
                                  width=width - prefix_len):
            self._printer.log_write_nl("{}{}".format(" " * prefix_len, line))
        self._subtests_printed = True

    def _print_error(self, test, test_status, err, params=None):
        assert err is not None
        self._print_header(test, test_status, params=params)
        self._printer.log_write_nl("-" * self._hbar_len)
        ### Print exception traceback
        all_lines = _format_exception(*err)
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
        start, rem = divmod(self._hbar_len - len(chanstr), 2)
        msg = "-" * start
        msg += chanstr
        msg += "-" * (start + rem)
        self._printer.log_write_nl(msg)
        for line in output.splitlines():
            self._printer.log_write_nl(line)

    def print_ios(self, test, stdout_value, stderr_value):
        if not stdout_value and not stderr_value:
            return
        status = Status.STOP if self._subtests_printed else Status.PASS
        self._print_header(test, status)
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
                      mean_split_time,
                      wall_time):
        ### Print main summary
        formatter = "{run_status} {total_count} tests in "\
                    "{wall_time} (avg: {mean_split_time}; "\
                    "total: {total_time}; speedup: {speedup:.2f})"
        speedup = total_time / wall_time if wall_time else 0
        msg = formatter.format(
            run_status=self._format_run_status(status_counters),
            total_count=tests_run,
            total_time=timedelta_to_hstr(total_time),
            mean_split_time=timedelta_to_hstr(mean_split_time),
            wall_time=timedelta_to_hstr(wall_time),
            speedup=speedup,
        )
        self._printer.log_overwrite_nl(msg)
        ### Print detailed summary
        counters = {}
        counters_format = []
        # If the detailed summary consists only in all passing tests it does
        # not deserves to be print.
        pass_status_only = True
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
                counters_format.append("{{{s}}} {s}".format(s=status.value))
                if status is not Status.PASS:
                    pass_status_only = False
        # Print detailed summary only if there were tests.
        if len(counters_format) > 1 \
           or (len(counters_format) == 1 and not pass_status_only):
            msg = " ".join(counters_format).format(**counters)
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

    def addSubTest(self, test, subtest, err):
        if err is not None:
            if issubclass(err[0], test.failureException):
                status = Status.FAIL
            else:
                status = Status.ERROR
        else:
            status = Status.PASS
        self.addOutcome(test, status, err=err, params=subtest.params)

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

    def addOutcome(self, test, status, err=None, reason=None, params=None):
        """Called by all outcome callback.

        Introduced to ease addition of behavior for all possible test outcomes.
        """
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')

class Failfast(BaseResult):
    """Stop the test suite as soon as a test failed.

    Use it as a mix-in of a unittest's result class.
    """

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

    def addOutcome(self, test, status, err=None, reason=None, params=None):
        super().addOutcome(test, status, err, reason, params)
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

    def stopTest(self, test):
        super().stopTest(test)
        self.stopwatch.split()

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
    """Count test for each status.

    In addition, it allow to store/retrieved the statistics from a database.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, status_db, **kwds):
        super().__init__(**kwds)
        self._status_db = status_db
        self.status_counters = StatusCounters()

    def addOutcome(self, test, status, err=None, reason=None, params=None):
        super().addOutcome(test, status, err, reason, params)
        self.status_counters.inc(status)

    def wasSuccessful(self):
        return self.status_counters.is_successful()

    @property
    def status_scores(self):
        return {status.value:self.status_counters.get(status)
                for status in Status.stopped()}

    def save_status(self):
        if not self.shouldStop:
            return self._status_db.save(self.status_scores)

    def load_status(self):
        if not self.shouldStop:
            return self._status_db.load()

class ErrSuccTracker(BaseResult):
    """List erroneous/succesful tests.

    Erroneous tests are determined using Status.is_erroneous. Successful tests
    are all tests that are not erroneous.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, **kwds):
        super().__init__(**kwds)
        self._error_test_specs = set()
        self._succeed_test_specs = set()

    def addOutcome(self, test, status, err=None, reason=None, params=None):
        super().addOutcome(test, status, err, reason, params)
        test_name = get_test_name(test)
        if status.is_erroneous():
            self._error_test_specs.add(test_name)
        else:
            self._succeed_test_specs.add(get_test_name)

    @property
    def error_test_specs(self):
        return self._error_test_specs

    @property
    def succeed_test_specs(self):
        return self._succeed_test_specs

class Walltime(BaseResult):
    """Compute the whole execution time of the test suite.

    This is not the sum of the execution time of each test. It is useful
    to measure the speedup of running test in parallel.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, **kwds):
        super().__init__(**kwds)
        self._walltime_watch = StopWatch()

    @property
    def walltime(self):
        return self._walltime_watch.total_time

    def startTest(self, test):
        if not self._walltime_watch.is_started:
            self._walltime_watch.start()
        super().startTest(test)

class HTestResult(Walltime,
                  CheckCWDDidNotChanged,
                  Failfast,
                  RunProgress,
                  StatusTracker,
                  ErrSuccTracker,
                  TestExecStopwatch,
                  CaptureStdio):
    """Result class for single process runner.

    Its interface is compatible with unittest.TestResult.
    """

    def __init__(self, result_printer,
                 **kwds):
        super().__init__(**kwds)
        self._printer = result_printer

    def startTest(self, test):
        self._printer.print_message(test, Status.RUNNING, self.status_counters,
                                    self.progress,
                                    self.stopwatch.mean_split_time,
                                    self.stopwatch.last_split_time)
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        self._printer.print_ios(test, self.stdout_value, self.stderr_value)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        # We cannot print IOs for each sub test because the test runner
        # calls 'addSubTest' once the main test has returned.

    def addOutcome(self, test, status, err=None, reason=None, params=None):
        super().addOutcome(test, status, err, reason, params)
        self._printer.print_message(test, status, self.status_counters,
                                    self.progress,
                                    self.stopwatch.mean_split_time,
                                    self.stopwatch.last_split_time,
                                    err=err, reason=reason,
                                    params=params)

    def print_summary(self):
        prev_counters = self.load_status()
        self._printer.print_summary(
            self._tests_run,
            prev_counters,
            self.status_counters,
            self.stopwatch.total_split_time,
            self.stopwatch.mean_split_time,
            self.walltime)
        self.save_status()

# Message representing the result of test.
SubtestResult \
    = namedtuple("SubtestResult",
                 ("status",      # The test status.
                  "error",       # An exception raised during test
                                 # execution represented as a tuple
                                 # similar to the one returned by
                                 # sys.exc_info(). The last obj is a
                                 # serialized traceback.
                  "reason",      # A string containing the reason why
                                 # a test has been skipped.
                  "params"))      # The params of the sub-test.

TestResultMsg \
    = namedtuple("TestResultMsg",
                 ("stdout",     # The stdout produced by the test.
                  "stderr",     # The stderr produced by the test.
                  "test_name",  # The complete spec of the test.
                  "total_time", # The total execution time of a test.
                  "results"))   # A list of SubtestResult object.

class HTestResultClient(CheckCWDDidNotChanged,
                        Failfast,
                        CaptureStdio,
                        TestExecStopwatch):
    """Client side of result class used by the multi-process runner.

    An instance of this class run in each worker process. The outcome of each
    test is sent back to the master process in the form of ResultMsg object.

    It partially implements the unittest.TestResult interface.
    """

    def __init__(self, worker_id, conn, **kwds):
        super().__init__(**kwds)
        self._worker_id = worker_id
        self._conn = conn
        self._result_attrs = None
        self._sub_results = []

    def stopTest(self, test):
        super().stopTest(test)
        self._send_outcome()

    def _send_outcome(self):
        assert self._result_attrs is not None
        assert self._sub_results
        self._result_attrs["total_time"] = self.stopwatch.last_split_time
        msg = TestResultMsg(stdout=self.stdout_value,
                            stderr=self.stderr_value,
                            results=self._sub_results,
                            **self._result_attrs)
        self._conn.send((self._worker_id, msg))
        self._result_attrs = None
        self._sub_results = []

    def addOutcome(self, test, status, err=None, reason=None, params=None):
        super().addOutcome(test, status, err, reason, params)
        self._save_result(test, status, err, reason, params)

    def _save_result(self, test, status, err=None, reason=None, params=None):
        if err is not None:
            error = (err[0], err[1], traceback.format_exception(*err))
        else:
            error = None
        self._result_attrs = dict(
            test_name=get_test_name(test),
        )
        self._sub_results.append(SubtestResult(
            status=status,
            error=error,
            reason=reason,
            params=params,
        ))

class HTestResultServer(Walltime,
                        RunProgress,
                        Failfast,
                        StatusTracker,
                        ErrSuccTracker):
    """Server side of result class used by the multi-process runner.

    An instance of this class run in the master process.
    The runner calls the process_result() when it receives a message from a
    worker.

    It partially implements the unittest.TestResult interface.
    """

    def __init__(self, result_printer, **kwds):
        super().__init__(**kwds)
        self._printer = result_printer
        # The last result message received.
        self._last_result_msg = None
        # Store the sum of the execution time of each finished tests.
        self._total_split_time = timedelta(0)

    def process_result(self, result_msg):
        ### Update internal state.
        self._last_result_msg = result_msg
        self._total_split_time += self.last_split_time
        for result in result_msg.results:
            ### Dispatch handling of the received message.
            self.addOutcome(result_msg.test_name, result.status,
                            err=result.error,
                            reason=result.reason,
                            params=result.params)
        self.stopTest(result_msg.test_name)

    def startTest(self, test):
        self._printer.print_message(test, Status.RUNNING, self.status_counters,
                                    self.progress,
                                    self.mean_split_time,
                                    self.last_split_time)
        super().startTest(test)

    def stopTest(self, test):
        assert self._last_result_msg is not None
        super().stopTest(test)
        self._printer.print_ios(test,
                                self._last_result_msg.stdout,
                                self._last_result_msg.stderr)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        # We cannot print IOs for each sub test because the test runner
        # calls 'addSubTest' once the main test has returned.

    def addOutcome(self, test, status, err=None, reason=None, params=None):
        assert self._last_result_msg is not None
        super().addOutcome(test, status, err, reason, params)
        self._printer.print_message(test, status, self.status_counters,
                                    self.progress,
                                    self.mean_split_time,
                                    self.last_split_time,
                                    err=err, reason=reason, params=params)

    def print_summary(self):
        prev_counters = self.load_status()
        self._printer.print_summary(
            self._tests_run,
            prev_counters,
            self.status_counters,
            self.total_split_time,
            self.mean_split_time,
            self.walltime)
        self.save_status()

    @property
    def last_split_time(self):
        # The last split time in multiprocess mode is the total execution
        # time of the test that just finished. For the first test we return
        # None as Stopwatch.last_split_time() does.
        if self._last_result_msg is None:
            return
        return self._last_result_msg.total_time

    @property
    def mean_split_time(self):
        if self.testsRun == 0:
            return timedelta(0)
        return self.total_split_time / self.testsRun

    @property
    def total_split_time(self):
        return self._total_split_time
