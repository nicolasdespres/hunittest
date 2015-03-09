# -*- encoding: utf-8 -*-
"""Routines to report unittest result.
"""


import unittest
from datetime import datetime
from datetime import timedelta
import traceback

from hunittest.line_printer import strip_ansi_escape

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
        self._last_laps_time = None
        self._last_laps_at = None
        self._total_time = 0
        self._tick_count = 0

    @property
    def started_at(self):
        return self._started_at

    def start(self):
        self._started_at = datetime.utcnow()

    def tick(self):
        self._last_laps_at = datetime.utcnow()
        self._last_laps_time = self._last_laps_at - self._started_at
        self._total_time += self._last_laps_time.microseconds
        self._tick_count += 1

    @property
    def mean_laps_time(self):
        """Return mean laps time in microseconds."""
        return self._total_time / self._tick_count

    @property
    def last_laps_time(self):
        return self._last_laps_time

    @property
    def total_time(self):
        return timedelta(microseconds=self._total_time)

class SmartTestResult(unittest.TestResult):

    SUCCESS_COLOR = Fore.GREEN
    FAILURE_COLOR = Fore.RED
    SKIP_COLOR = Fore.BLUE
    EXPECTED_FAILURE_COLOR = Fore.YELLOW
    UNEXPECTED_SUCCESS_COLOR = Fore.CYAN
    ERROR_COLOR = Fore.MAGENTA

    ALL_STATUS = "success failure error skip expected_failure "\
                 "unexpected_success".split()

    @staticmethod
    def status_counter_name(status):
        return "_{}_count".format(status)

    def __init__(self, printer, total_tests):
        super(SmartTestResult, self).__init__()
        self._printer = printer
        self._total_tests = total_tests
        for status in self.ALL_STATUS:
            self._set_status_counter(status, 0)
        self._stopwatch = StopWatch()

    @property
    def total_tests(self):
        return self._total_tests

    @property
    def progress(self):
        return self.testsRun / self._total_tests

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
    def expected_failure(self):
        return self._expected_failure_count

    @property
    def unexpected_success(self):
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
        self._stopwatch.tick()
        counters = {}
        counter_formats = []
        for status in self.ALL_STATUS:
            counters[status] = self.status_color(status) \
                               + str(self.get_status_counter(status)) \
                               + Fore.RESET
            counter_formats.append("{{{s}}}".format(s=status))
        formatter = "[{progress:>4.0%}|{mean_time:.2f}|" \
                    + "|".join(f for f in counter_formats) \
                    + "] {test_status}: {fullname} ({elapsed})"
        msg = formatter.format(
            progress=self.progress,
            fullname=self.full_test_name(test),
            test_status=self.format_test_status(test_status),
            elapsed=self._stopwatch.last_laps_time,
            mean_time=self._stopwatch.mean_laps_time / 1000,
            **counters)
        self._inc_status_counter(test_status)
        self._printer.overwrite(msg)
        if err is not None:
            self._print_error(test, test_status, err)
        if reason is not None:
            self._print_reason(test, test_status, reason)

    def _print_error(self, test, test_status, err):
        assert err is not None
        hbar_len = len(strip_ansi_escape(self._printer.prev_line))
        msg = "{test_status}: {fullname}"\
            .format(test_status=self.format_test_status(test_status,
                                                        aligned=False),
                    fullname=self.full_test_name(test))
        hbar_len = len(strip_ansi_escape(msg))
        self._printer.overwrite_nl("-" * hbar_len)
        self._printer.overwrite_nl(msg)
        self._printer.write_nl("-" * hbar_len)
        for lines in traceback.format_exception(*err):
            for line in lines.splitlines():
                self._printer.write_nl(line)

    def _print_reason(self, test, test_status, reason):
        msg = "{test_status}: {fullname}: {reason}"\
            .format(test_status=self.format_test_status(test_status,
                                                        aligned=False),
                    fullname=self.full_test_name(test),
                    reason=reason)
        # self._printer.new_line()
        self._printer.overwrite_nl(msg)

    def startTest(self, test):
        super(SmartTestResult, self).startTest(test)
        # print("startTest", repr(test), test.__class__, test._testMethodName)
        self._stopwatch.start()

    def stopTest(self, test):
        super(SmartTestResult, self).stopTest(test)
        # print("stopTest", repr(test))

    def startTestRun(self):
        super(SmartTestResult, self).startTestRun()
        # print("startTestRun")

    def stopTestRun(self):
        super(SmartTestResult, self).stopTestRun()
        # print("stopTesRun")

    def addSuccess(self, test):
        super(SmartTestResult, self).addSuccess(test)
        # print("addSuccess", repr(test))
        self._print_message(test, "success")

    def addFailure(self, test, err):
        super(SmartTestResult, self).addFailure(test, err)
        # print("addFailure", repr(test), repr(err))
        self._print_message(test, "failure", err=err)

    def addError(self, test, err):
        super(SmartTestResult, self).addError(test, err)
        # print("addError", repr(test), repr(err))
        self._print_message(test, "error", err=err)

    def addSkip(self, test, reason):
        super(SmartTestResult, self).addSkip(test, reason)
        self._print_message(test, "skip", reason=reason)

    def addExpectedFailure(self, test, err):
        super(SmartTestResult, self).addExpectedFailure(test, err)
        self._print_message(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super(SmartTestResult, self).addUnexpectedSuccess(test)
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
                    "{elapsed_time}: "
        formatter += " ".join(counter_formats)
        msg = formatter.format(
            run_status=self._format_run_status(),
            total_count=self._total_tests,
            elapsed_time=self._stopwatch.total_time,
            **counters)
        self._printer.overwrite(msg)
