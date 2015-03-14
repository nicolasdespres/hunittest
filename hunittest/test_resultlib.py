# -*- encoding: utf-8 -*-
"""Routines and classes to report unittest result.
"""


from datetime import datetime
from datetime import timedelta
import traceback
import io
import functools
import sys

from hunittest.line_printer import strip_ansi_escape
from hunittest.timedeltalib import timedelta_to_hstr
from hunittest.timedeltalib import timedelta_to_unit

try:
    from colorama import Fore
except ImportError:
    sys.stderr.write("info: you can get color by install 'colorama'\n")
    class Fore(object):
        BLACK = ""
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        MAGENTA = ""
        CYAN = ""
        WHITE = ""
        RESET = ""


class StopWatch(object):

    def __init__(self):
        self.reset()

    def reset(self):
        self._started_at = None
        self._last_split_time = None
        self._last_split_at = None
        self._total_split_time = None
        self._tick_count = 0

    @property
    def started_at(self):
        return self._started_at

    @property
    def last_split_at(self):
        return self._last_split_at

    def start(self):
        if self.is_started:
            raise RuntimeError("stopwatch already started")
        self._started_at = datetime.utcnow()
        self._last_split_at = self._started_at
        self._last_split_time = None
        self._total_split_time = None
        self._splits_count = 0

    @property
    def is_started(self):
        return self._started_at is not None

    def _check_is_started(self):
        if not self.is_started:
            raise RuntimeError("stopwatch not started")

    def split(self):
        self._check_is_started()
        now = datetime.utcnow()
        self._last_split_time = now - self._last_split_at
        self._last_split_at = now
        self._splits_count += 1
        if self._total_split_time is None:
            self._total_split_time = self._last_split_time
        else:
            self._total_split_time += self._last_split_time

    @property
    def splits_count(self):
        return self._splits_count

    @property
    def total_split_time(self):
        return self._total_split_time

    @property
    def mean_split_time(self):
        """Return mean split time in microseconds."""
        self._check_is_started()
        return self._total_split_time / self._splits_count

    @property
    def mean_split_time_in_ms(self):
        return timedelta_to_unit(self.mean_split_time, "ms")

    @property
    def last_split_time(self):
        return self._last_split_time

    @property
    def total_time(self):
        self._check_is_started()
        return datetime.utcnow() - self._started_at

def failfast_decorator(method):
    @functools.wraps(method)
    def inner(self, *args, **kw):
        if getattr(self, 'failfast', False):
            self.stop()
        return method(self, *args, **kw)
    return inner

class HTestResult(object):

    SUCCESS_COLOR = Fore.GREEN
    FAILURE_COLOR = Fore.RED
    SKIP_COLOR = Fore.BLUE
    EXPECTED_FAILURE_COLOR = Fore.CYAN
    UNEXPECTED_SUCCESS_COLOR = Fore.YELLOW
    ERROR_COLOR = Fore.MAGENTA

    ALL_STATUS = "success failure error skip expected_failure "\
                 "unexpected_success".split()

    @staticmethod
    def status_counter_name(status):
        return "_{}_count".format(status)

    def __init__(self, printer, total_tests, failfast=False):
        self._failfast = failfast
        self._tests_run = 0
        self._should_stop = False
        self._printer = printer
        self._total_tests = total_tests
        for status in self.ALL_STATUS:
            self._set_status_counter(status, 0)
        self._stopwatch = StopWatch()
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._stdout_buffer = io.StringIO()
        self._stderr_buffer = io.StringIO()
        self._hbar_len = None

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
        # pprint(dir(test))
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
            + Fore.RESET

    def _print_message(self, test, test_status, err=None, reason=None):
        self._stopwatch.split()
        counters = {}
        counter_formats = []
        for status in self.ALL_STATUS:
            counters[status] = self.status_color(status) \
                               + str(self.get_status_counter(status)) \
                               + Fore.RESET
            counter_formats.append("{{{s}}}".format(s=status))
        formatter = "[{progress:>4.0%}|{mean_split_time:.2f}ms|" \
                    + "|".join(f for f in counter_formats) \
                    + "] {test_status}: {fullname} ({elapsed})"
        msg = formatter.format(
            progress=self.progress,
            fullname=self.full_test_name(test),
            test_status=self.format_test_status(test_status),
            elapsed=timedelta_to_hstr(self._stopwatch.last_split_time),
            mean_split_time=self._stopwatch.mean_split_time_in_ms,
            **counters)
        self._inc_status_counter(test_status)
        self._printer.overwrite(msg)
        if err is not None:
            self._print_error(test, test_status, err)
        if reason is not None:
            self._print_reason(test, test_status, reason)

    def _print_error(self, test, test_status, err):
        assert err is not None
        msg = "{test_status}: {fullname}"\
            .format(test_status=self.format_test_status(test_status,
                                                        aligned=False),
                    fullname=self.full_test_name(test))
        self._hbar_len = len(strip_ansi_escape(msg))
        self._printer.overwrite_nl("-" * self._hbar_len)
        self._printer.overwrite_nl(msg)
        self._printer.write_nl("-" * self._hbar_len)
        for lines in traceback.format_exception(*err):
            for line in lines.splitlines():
                self._printer.write_nl(line)

    def _print_reason(self, test, test_status, reason):
        msg = "{test_status}: {fullname}: {reason}"\
            .format(test_status=self.format_test_status(test_status,
                                                        aligned=False),
                    fullname=self.full_test_name(test),
                    reason=reason)
        self._printer.overwrite_nl(msg)

    def _print_io(self, test, output, channel):
        if not output:
            return
        assert self._hbar_len is not None
        chanstr = " {} ".format(channel.upper())
        start = (self._hbar_len - len(chanstr)) // 2
        msg = "-" * start
        msg += chanstr
        msg += "-" * start
        self._printer.write_nl(msg)
        for line in output.splitlines():
            self._printer.write_nl(line)

    def _print_ios(self, test, stdout_value, stderr_value):
        if test._outcome is None or test._outcome.success:
            return
        self._print_io(test, stdout_value, "stdout")
        self._print_io(test, stderr_value, "stderr")
        if stdout_value or stderr_value:
            self._printer.write_nl("-" * self._hbar_len)

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
    def addUnexpectedSuccess(self, test):
        self._print_message(test, "unexpected_success")

    def _format_run_status(self):
        if self.wasSuccessful():
            color = self.SUCCESS_COLOR
        else:
            color = self.FAILURE_COLOR
        return color + "Run" + Fore.RESET

    def print_summary(self):
        counters = {}
        counter_formats = []
        for status in self.ALL_STATUS:
            counters[status] = self.status_color(status) \
                               + str(self.get_status_counter(status)) \
                               + Fore.RESET
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
        self._printer.overwrite(msg)

    def stop(self):
        self._should_stop = True

    def wasSuccessful(self):
        return self.failure_count \
            == self.error_count \
            == self.unexpected_success_count \
            == 0
