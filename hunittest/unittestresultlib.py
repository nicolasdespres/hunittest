# -*- encoding: utf-8 -*-
"""Routines and classes to report unittest result.
"""


import traceback
import io
import sys
import os
import re
import unittest
import json
from enum import Enum
from datetime import timedelta
import textwrap
from fnmatch import fnmatch
from multiprocessing.connection import Connection
from types import TracebackType
from typing import Any, Generator, Mapping, NamedTuple, Self, TextIO, cast

from hunittest.line_printer import LinePrinter
from hunittest.termlib import TermInfo
from hunittest.timedeltalib import timedelta_to_hstr as _timedelta_to_hstr
from hunittest.timedeltalib import timedelta_to_unit
from hunittest.termlib import strip_ansi_escape
from hunittest.stopwatch import StopWatch
from hunittest.utils import mkdir_p
from hunittest.utils import safe_getcwd
from hunittest.utils import issubdir
from hunittest import envar


def timedelta_to_hstr(tdelta: timedelta) -> str:
    return _timedelta_to_hstr(tdelta, precision=2)

class _LogLinePrinter(object):
    """Proxy over a LinePrinter.

    This proxy offers some more methods starting by "log_" allowing to
    also log the printed message to a file.
    """

    def __init__(
            self, printer: LinePrinter,
            filename: str | None = None) -> None:
        self._printer = printer
        self._filename = filename
        self._file: TextIO | None = None
        if self._filename is not None:
            mkdir_p(os.path.dirname(self._filename))
            self._file = open(self._filename, "w")

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def __del__(self) -> None:
        self.close()

    @property
    def term_info(self) -> TermInfo:
        return self._printer.term_info

    def overwrite_message(self, *args: Any, **kwargs: Any) -> None:
        return self._printer.overwrite_message(*args, **kwargs)

    def overwrite(self, line: str) -> None:
        return self._printer.overwrite(line)

    def overwrite_nl(self, *args: Any, **kwargs: Any) -> None:
        return self._printer.overwrite_nl(*args, **kwargs)

    def write_nl(self, *args: Any, **kwargs: Any) -> None:
        return self._printer.write_nl(*args, **kwargs)

    def write(self, string: str) -> None:
        return self._printer.write(string)

    def log_overwrite(self, line: str) -> None:
        self.overwrite(line)
        self._log(line)

    def log_overwrite_nl(self, msg: str) -> None:
        self.overwrite_nl(msg)
        self._log(msg)

    def log_write_nl(self, msg: str) -> None:
        self.write_nl(msg)
        self._log(msg)

    def log_write(self, msg: str) -> None:
        self.write(msg)
        self._log(msg, False)

    def _log(self, msg: str, nl: bool = True) -> None:
        if self._file is None:
            return
        self._file.write(msg)
        if nl:
            self._file.write("\n")

def get_test_name(test: unittest.TestCase | str) -> str:
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

    def __init__(self, filename: str | None) -> None:
        self.filename = filename

    def save(self, status_scores: Mapping[str, object]) -> None:
        if self.filename is None:
            return
        mkdir_p(os.path.dirname(self.filename))
        with open(self.filename, "w") as stream:
            json.dump(status_scores, stream)

    def load(self) -> Any | None:
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
    def stopped(cls) -> Generator["Status", None, None]:
        """Yield all status representing a stopped test."""
        for status in cls:
            if status is not cls.RUNNING and status is not cls.STOP:
                yield status

    def is_erroneous(self) -> bool:
        """Return whether this status is considered as an erroneous test status.
        """
        return self is self.FAIL or self is self.ERROR or self is self.XPASS

class StatusCounters:
    """Hold test counters for each possible status.
    """

    pass_count: int
    fail_count: int
    error_count: int
    skip_count: int
    xfail_count: int
    xpass_count: int

    @staticmethod
    def name(status: Status) -> str:
        return "{}_count".format(status.value)

    def __init__(self) -> None:
        for status in Status.stopped():
            self.set(status, 0)

    def get(self, status: Status) -> int:
        return getattr(self, self.name(status))

    def set(self, status: Status, value: int) -> None:
        setattr(self, self.name(status), value)

    def inc(self, status: Status, inc: int = 1) -> None:
        v = self.get(status)
        self.set(status, v+inc)

    def is_successful(self) -> bool:
        return self.fail_count \
            == self.error_count \
            == self.xpass_count \
            == 0

def _format_exception(
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | list[str] | None) -> list[str]:
    """Own customization of traceback.format_exception().

    When the result comes from another process the traceback is already
    serialized thus we just have to return it.
    """
    # HTestResultServer passes serialized traceback.
    if isinstance(exc_traceback, list):
        return exc_traceback
    return traceback.format_exception(exc_type, exc_value, exc_traceback)

def _serialize_subtest_params(
        params: Mapping[object, object] | None
        ) -> Mapping[object, object] | None:
    if not params:
        return params
    return {str(k):repr(v) for k, v in params.items()}

def _format_subtest_params(params: Mapping[object, object] | None) -> str:
    if not params:
        return ''
    return "{{{}}}".format(", ".join("{}={}".format(k, v)
                                     for k, v in params.items()))

class SummaryMode(Enum):
    always = 0
    on_error = 1

    @classmethod
    def from_str(cls, string: str) -> "SummaryMode":
        for mode in cls:
            if mode.name == string:
                return mode
        raise ValueError("unknown summary mode: "+string)

def get_summary_mode_from_env() -> SummaryMode:
    return SummaryMode.from_str(os.environ.get(envar.SUMMARY, "on_error"))

class Color:

    def __init__(self, term_info: TermInfo) -> None:
        self.STATUS_PASS = term_info.fore_green
        self.STATUS_FAIL = term_info.fore_red
        self.STATUS_SKIP = term_info.fore_blue
        self.STATUS_XFAIL = term_info.fore_cyan
        self.STATUS_XPASS = term_info.fore_yellow
        self.STATUS_ERROR = term_info.fore_magenta
        self.STATUS_RUNNING = term_info.fore_white
        self.STATUS_STOP = term_info.fore_white
        self.RESET = term_info.reset_all
        self.TRACE_HL = term_info.fore_white \
                        + term_info.bold
        self.TEST_TRACE_HL = term_info.fore_white \
                             + term_info.bold \
                             + term_info.underline

    def status(self, status: Status) -> str:
        return getattr(self, "STATUS_{}".format(status.value.upper()))

class ResultPrinter:

    _STATUS_MAXLEN: int = max(len(s.value) for s in Status)

    def __init__(
            self, printer: LinePrinter, top_level_directory: str,
            pattern: str, log_filename: str | None = None,
            strip_unittest_traceback: bool = False,
            show_progress: bool = True) -> None:
        self._printer: _LogLinePrinter = _LogLinePrinter(printer, log_filename)
        self._top_level_directory: str = top_level_directory
        self._pattern: str = pattern
        self._strip_unittest_traceback: bool = strip_unittest_traceback
        self._show_progress: bool = show_progress
        self._hbar_len: int | None = None
        self._color: Color = Color(self._printer.term_info)
        self._summary_printer: SummaryPrinter = SummaryPrinter(self._printer)

    def format_test_status(self, status: Status, aligned: bool = True) -> str:
        msg = status.value.upper()
        if aligned:
            formatter = "{{:^{:d}}}".format(self._STATUS_MAXLEN)
        else:
            formatter = "{}"
        return self._color.status(status) \
            + formatter.format(msg) \
            + self._color.RESET

    def _print_progress_message(
            self, test_name: str, test_status: Status,
            status_counters: StatusCounters, progress: float,
            mean_split_time: timedelta, last_split_time: timedelta | None,
            params: Mapping[object, object] | None = None) -> None:
        counters: dict[str, str] = {}
        counters_format_parts: list[str] = []
        for status in Status.stopped():
            counter_value = status_counters.get(status)
            if counter_value > 0:
                counters[status.value] = self._color.status(status) \
                                         + str(counter_value) \
                                         + self._color.RESET
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

    def reset(self) -> None:
        self._subtests_printed: bool = False
        self._header_printed: bool = False

    def print_message(
            self, test: unittest.TestCase | str, test_status: Status,
            status_counters: StatusCounters, progress: float,
            mean_split_time: timedelta, last_split_time: timedelta | None,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
        if test_status is Status.RUNNING:
            self.reset()
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

    def _extract_filename_from_error_line(self, line: str) -> str | None:
        mo = re.match(r'^\s+File "(.*)", line \d+, in .*$', line,
                      re.MULTILINE)
        if mo:
            return mo.group(1)

    def _is_user_filename(self, line: str) -> bool | None:
        filename = self._extract_filename_from_error_line(line)
        if filename is None:
            return None
        return issubdir(filename, self._top_level_directory)

    def _is_user_test_filename(self, line: str) -> bool | None:
        filename = self._extract_filename_from_error_line(line)
        if filename is None:
            return None
        return issubdir(filename, self._top_level_directory) \
            and fnmatch(os.path.basename(filename), self._pattern)

    def _is_unittest_filename(self, line: str) -> bool | None:
        filename = self._extract_filename_from_error_line(line)
        if filename is None:
            return None
        return issubdir(filename, os.path.dirname(unittest.__file__))

    def _header_prefix(self, test_status: Status) -> str:
        status = self.format_test_status(test_status, aligned=False)
        return "{status}: ".format(status=status)

    def _print_header(
            self, test: unittest.TestCase | str, test_status: Status,
            params: Mapping[object, object] | None = None) -> None:
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

    def _print_subtest_params(
            self, test_status: Status,
            params: Mapping[object, object] | None, width: int) -> None:
        if not params:
            return
        prefix_len = len(strip_ansi_escape(self._header_prefix(test_status)))
        for line in textwrap.wrap(_format_subtest_params(params),
                                  width=width - prefix_len):
            self._printer.log_write_nl("{}{}".format(" " * prefix_len, line))
        self._subtests_printed = True

    def _print_error(
            self, test: unittest.TestCase | str, test_status: Status,
            err: Any, params: Mapping[object, object] | None = None) -> None:
        assert err is not None
        # Do not assert self._header_printed is False here, because this
        # method can be called multiple times per test (in case of error
        # raised from tearDown()).
        self._print_header(test, test_status, params=params)
        assert self._hbar_len is not None
        self._printer.log_write_nl("-" * self._hbar_len)
        ### Print exception traceback
        all_lines = _format_exception(*err)
        for i in range(len(all_lines)-1):
            lines = all_lines[i]
            is_user_filename = self._is_user_filename(lines)
            is_user_test_filename = self._is_user_test_filename(lines)
            skip_next = False
            for line in lines.splitlines():
                leading_space = re.sub(r"^(\s*).*$", "\\1", line)
                if skip_next:
                    continue
                if is_user_test_filename:
                    formatted_line = leading_space + self._color.TEST_TRACE_HL \
                                     + line.strip() + self._color.RESET
                elif is_user_filename:
                    formatted_line \
                        = self._color.TRACE_HL + line + self._color.RESET
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
            self._printer.log_write_nl(self._color.status(test_status) \
                                       + err[0].__name__ \
                                       + self._color.RESET)
        else:
            self._printer.log_write_nl(self._color.status(test_status) \
                                       + err[0].__name__ \
                                       + self._color.RESET \
                                       + ": " \
                                       + err_lines[0])
            for i in range(1, len(err_lines)):
                self._printer.log_write_nl(err_lines[i])
        ### Print exception notes
        notes = getattr(err[1], "__notes__", None)
        if notes is not None:
            for note in notes:
                lines = note.splitlines()
                if lines:
                    self._printer.log_write_nl("+ " + lines[0])
                    for line in lines[1:]:
                        self._printer.log_write_nl("| " + line)

    def _print_reason(
            self, test: unittest.TestCase | str, test_status: Status,
            reason: str) -> None:
        assert reason is not None
        msg = "{status}: {name}: {reason}"\
            .format(status=self.format_test_status(test_status, aligned=False),
                    name=get_test_name(test),
                    reason=reason)
        self._printer.log_overwrite_nl(msg)

    def _print_io(
            self, test: unittest.TestCase | str, output: str | None,
            channel: str) -> None:
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

    def print_ios(
            self, test: unittest.TestCase | str, stdout_value: str | None,
            stderr_value: str | None) -> None:
        if not stdout_value and not stderr_value:
            return
        status = Status.STOP if self._subtests_printed else Status.PASS
        self._print_header(test, status)
        assert self._hbar_len is not None
        self._print_io(test, stdout_value, "stdout")
        self._print_io(test, stderr_value, "stderr")
        if stdout_value or stderr_value:
            self._printer.log_write_nl("-" * self._hbar_len)

    def print_summary(self, *args: Any, **kwargs: Any) -> None:
        return self._summary_printer.print_summary(*args, **kwargs)

    def close(self) -> None:
        self._printer.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
            self, exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            exc_traceback: TracebackType | None) -> bool:
        self.close()
        return False

class SummaryPrinter:

    def __init__(self, printer: _LogLinePrinter) -> None:
        self._printer = printer
        self._color = Color(self._printer.term_info)
        self.summary_mode = get_summary_mode_from_env()

    def _format_run_status(self, status_counters: StatusCounters) -> str:
        if status_counters.is_successful():
            color = self._color.STATUS_PASS
        else:
            color = self._color.STATUS_FAIL
        return color + "Ran" + self._color.RESET

    def print_summary(
            self, tests_run: int, subtests_run: int,
            prev_status_counters: Mapping[str, int] | None,
            status_counters: StatusCounters,
            subtests_status_counters: StatusCounters,
            total_time: timedelta, mean_split_time: timedelta,
            wall_time: timedelta) -> None:
        total_count = str(tests_run)
        caption = "tests"
        if subtests_run > 0:
            total_count += "+{}".format(subtests_run)
            caption += "(+sub)"
        ### Print main summary
        formatter = "{run_status} {total_count} {caption} in "\
                    "{wall_time} (avg: {mean_split_time}; "\
                    "total: {total_time}; speedup: {speedup:.2f})"
        speedup = total_time / wall_time if wall_time else 0
        msg = formatter.format(
            run_status=self._format_run_status(status_counters),
            total_count=total_count,
            caption=caption,
            total_time=timedelta_to_hstr(total_time),
            mean_split_time=timedelta_to_hstr(mean_split_time),
            wall_time=timedelta_to_hstr(wall_time),
            speedup=speedup,
        )
        self._printer.log_overwrite_nl(msg)
        ### Print detailed summary
        counters: dict[str, str] = {}
        counters_format: list[str] = []
        # If the detailed summary consists only in all passing tests it does
        # not deserves to be printed.
        pass_status_only = True
        for status in Status.stopped():
            count = status_counters.get(status)
            if prev_status_counters is None:
                count_delta = 0
            else:
                count_delta = count - prev_status_counters[status.value]
            if count > 0 or count_delta != 0:
                sub_count = subtests_status_counters.get(status)
                if sub_count > 0:
                    count_str = "{}+{}".format(count-sub_count, sub_count)
                else:
                    count_str = str(count)
                s = self._color.status(status) + count_str
                if count_delta != 0:
                    s += "({:+d})".format(count_delta)
                s += self._color.RESET
                counters[status.value] = s
                counters_format.append("{{{s}}} {s}".format(s=status.value))
                if status is not Status.PASS:
                    pass_status_only = False
        # Print detailed summary only if there were failing tests.
        if self.should_print(len(counters_format), pass_status_only):
            msg = " ".join(counters_format).format(**counters)
            self._printer.log_write_nl(msg)

    def should_print(
            self, non_zero_counters_count: int,
            pass_status_only: bool) -> bool:
        if self.summary_mode is SummaryMode.always:
            return True
        elif self.summary_mode is SummaryMode.on_error:
            return non_zero_counters_count > 1 \
                or (non_zero_counters_count == 1 and not pass_status_only)
        else:
            raise RuntimeError("invalid summary mode: {!r}"
                               .format(self.summary_mode))

class BaseResult:
    """Root result object used as base class for super delegation chain.
    """

    def __init__(self) -> None:
        self._should_stop: bool = False

    @property
    def shouldStop(self) -> bool:
        return self._should_stop

    def stop(self) -> None:
        self._should_stop = True

    def startTest(self, test: unittest.TestCase | str) -> None:
        # the delegation chain stops here
        assert not hasattr(super(), 'startTest')

    def stopTest(self, test: unittest.TestCase | str) -> None:
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')

    def startTestRun(self) -> None:
        # print("startTestRun")
        pass

    def stopTestRun(self) -> None:
        # print("stopTesRun")
        pass

    def addSubTest(
            self, test: unittest.TestCase, subtest: unittest.TestCase,
            err: Any) -> None:
        if err is not None:
            if issubclass(err[0], test.failureException):
                status = Status.FAIL
            else:
                status = Status.ERROR
        else:
            status = Status.PASS
        self.addOutcome(
            test, status, err=err,
            params=cast(Any, subtest).params)

    def addSuccess(self, test: unittest.TestCase) -> None:
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.PASS)

    def addFailure(self, test: unittest.TestCase, err: Any) -> None:
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.FAIL, err=err)

    def addError(self, test: unittest.TestCase, err: Any) -> None:
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.ERROR, err=err)

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.SKIP, reason=reason)

    def addExpectedFailure(
            self, test: unittest.TestCase, err: Any) -> None:
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.XFAIL, err=err)

    def addUnexpectedSuccess(self, test: unittest.TestCase) -> None:
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')
        self.addOutcome(test, Status.XPASS)

    def addOutcome(
            self, test: unittest.TestCase | str, status: Status,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
        """Called by all outcome callback.

        Introduced to ease addition of behavior for all possible test outcomes.
        """
        # the delegation chain stops here
        assert not hasattr(super(), 'stopTest')

class Failfast(BaseResult):
    """Stop the test suite as soon as a test failed.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(
            self, failfast: bool = False, raise_exception: bool = False,
            **kwds: Any) -> None:
        super().__init__(**kwds)
        self._failfast = failfast
        self._raise_exception = raise_exception
        self._last_traceback: Any | None = None

    @property
    def failfast(self) -> bool:
        return self._failfast

    @property
    def last_traceback(self) -> Any | None:
        return self._last_traceback

    def addOutcome(
            self, test: unittest.TestCase | str, status: Status,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
        super().addOutcome(test, status, err, reason, params)
        if self._failfast and status.is_erroneous():
            if err is not None:
                if self._raise_exception:
                    raise err[1]  # Raise so that debugger can catch it.
                self._last_traceback = err[2]
            self.stop()

class CheckCWDDidNotChanged(BaseResult):
    """Check whether current working directory has changed after test execution.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, **kwds: Any) -> None:
        super().__init__(**kwds)

    def startTest(self, test: unittest.TestCase | str) -> None:
        self.old_cwd = safe_getcwd()
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase | str) -> None:
        super().stopTest(test)
        new_cwd = safe_getcwd()
        if self.old_cwd is None or new_cwd is None \
           or self.old_cwd != new_cwd:
            raise RuntimeError("working directory changed during test")

class CaptureStdio(BaseResult):
    """Capture and store test's stdout and stderr.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, buffer: bool = True, **kwds: Any) -> None:
        super().__init__(**kwds)
        self.buffer = buffer
        self._original_stdout: TextIO = sys.stdout
        self._original_stderr: TextIO = sys.stderr
        self._stdout_buffer = io.StringIO()
        self._stderr_buffer = io.StringIO()
        self._stdout_value: str | None = None
        self._stderr_value: str | None = None

    def startTest(self, test: unittest.TestCase | str) -> None:
        if self.buffer:
            self._setupStdout()
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase | str) -> None:
        super().stopTest(test)
        if self.buffer:
            self._stdout_value = self._stdout_buffer.getvalue()
            self._stderr_value = self._stderr_buffer.getvalue()
            self._restoreStdout()

    def _setupStdout(self) -> None:
        sys.stdout = self._stdout_buffer
        sys.stderr = self._stderr_buffer
        self._stdout_value = None
        self._stderr_value = None

    def _restoreStdout(self) -> None:
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self._stdout_buffer.seek(0)
        self._stdout_buffer.truncate()
        self._stderr_buffer.seek(0)
        self._stderr_buffer.truncate()

    @property
    def stdout_value(self) -> str | None:
        return self._stdout_value

    @property
    def stderr_value(self) -> str | None:
        return self._stderr_value

class TestExecStopwatch(BaseResult):
    """Time test execution using a stopwatch.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, **kwds: Any) -> None:
        super().__init__(**kwds)
        self.stopwatch = StopWatch()

    def startTest(self, test: unittest.TestCase | str) -> None:
        if not self.stopwatch.is_started:
            self.stopwatch.start()
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase | str) -> None:
        super().stopTest(test)
        self.stopwatch.split()

class RunProgress(BaseResult):
    """Count running and ran tests.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, total_tests: int, **kwds: Any) -> None:
        super().__init__(**kwds)
        # number of ran tests not including sub tests
        self._tests_run: int = 0
        # total number of tests not including subtests
        self._total_tests: int = total_tests
        self._subtests_run: int = 0

    @property
    def testsRun(self) -> int:
        return self._tests_run

    @property
    def subtestsRun(self) -> int:
        return self._subtests_run

    @property
    def total_tests(self) -> int:
        return self._total_tests

    @property
    def progress(self) -> float:
        return self._tests_run / self._total_tests

    def startTest(self, test: unittest.TestCase | str) -> None:
        self._tests_run += 1
        super().startTest(test)

    def addOutcome(
            self, test: unittest.TestCase | str, status: Status,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
        super().addOutcome(test, status, err, reason, params)
        if params:
            self._subtests_run += 1

class StatusTracker(BaseResult):
    """Count test for each status.

    In addition, it allow to store/retrieved the statistics from a database.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, status_db: StatusDB, **kwds: Any) -> None:
        super().__init__(**kwds)
        self._status_db = status_db
        self.subtests_status_counters: StatusCounters = StatusCounters()
        self.tests_status_counters: StatusCounters = StatusCounters()
        self.status_counters: StatusCounters = StatusCounters()

    def addOutcome(
            self, test: unittest.TestCase | str, status: Status,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
        super().addOutcome(test, status, err, reason, params)
        if params:
            self.subtests_status_counters.inc(status)
        else:
            self.tests_status_counters.inc(status)
        self.status_counters.inc(status)

    def wasSuccessful(self) -> bool:
        return self.status_counters.is_successful()

    @property
    def status_scores(self) -> dict[str, int]:
        return {status.value:self.status_counters.get(status)
                for status in Status.stopped()}

    def save_status(self) -> None:
        if not self.shouldStop:
            return self._status_db.save(self.status_scores)

    def load_status(self) -> dict[str, int] | None:
        if not self.shouldStop:
            return self._status_db.load()

class ErrSuccTracker(BaseResult):
    """List erroneous/succesful tests.

    Erroneous tests are determined using Status.is_erroneous. Successful tests
    are all tests that are not erroneous.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, **kwds: Any) -> None:
        super().__init__(**kwds)
        self._error_test_specs: set[str] = set()
        self._succeed_test_specs: set[str] = set()

    def addOutcome(
            self, test: unittest.TestCase | str, status: Status,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
        super().addOutcome(test, status, err, reason, params)
        test_name = get_test_name(test)
        if status.is_erroneous():
            self._error_test_specs.add(test_name)
        else:
            self._succeed_test_specs.add(test_name)

    @property
    def error_test_specs(self) -> set[str]:
        return self._error_test_specs

    @property
    def succeed_test_specs(self) -> set[str]:
        return self._succeed_test_specs

class Walltime(BaseResult):
    """Compute the whole execution time of the test suite.

    This is not the sum of the execution time of each test. It is useful
    to measure the speedup of running test in parallel.

    Use it as a mix-in of a unittest's result class.
    """

    def __init__(self, **kwds: Any) -> None:
        super().__init__(**kwds)
        self._walltime_watch = StopWatch()

    @property
    def walltime(self) -> timedelta:
        return self._walltime_watch.total_time

    def startTest(self, test: unittest.TestCase | str) -> None:
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

    def __init__(
            self, result_printer: ResultPrinter, **kwds: Any) -> None:
        super().__init__(**kwds)
        self._printer = result_printer

    def startTest(self, test: unittest.TestCase | str) -> None:
        self._printer.print_message(test, Status.RUNNING, self.status_counters,
                                    self.progress,
                                    self.stopwatch.mean_split_time,
                                    self.stopwatch.last_split_time)
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase | str) -> None:
        super().stopTest(test)
        self._printer.print_ios(test, self.stdout_value, self.stderr_value)

    def addSubTest(
            self, test: unittest.TestCase, subtest: unittest.TestCase,
            err: Any) -> None:
        super().addSubTest(test, subtest, err)
        # We cannot print IOs for each sub test because the test runner
        # calls 'addSubTest' once the main test has returned.

    def addOutcome(
            self, test: unittest.TestCase | str, status: Status,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
        super().addOutcome(test, status, err, reason, params)
        self._printer.print_message(test, status, self.status_counters,
                                    self.progress,
                                    self.stopwatch.mean_split_time,
                                    self.stopwatch.last_split_time,
                                    err=err, reason=reason,
                                    params=_serialize_subtest_params(params))

    def addDuration(self, test: unittest.TestCase, elapsed: float) -> None:
        pass  # We already track the duration of each test using the stopwatch.

    def print_summary(self) -> None:
        prev_counters = self.load_status()
        self._printer.print_summary(
            self.testsRun, self.subtestsRun,
            prev_counters,
            self.status_counters,
            self.subtests_status_counters,
            self.stopwatch.total_split_time,
            self.stopwatch.mean_split_time,
            self.walltime)
        self.save_status()

# Message representing the result of test.
class SubtestResult(NamedTuple):
    status: Status
    error: tuple[
        type[BaseException] | None,
        BaseException | None,
        list[str],
    ] | None
    reason: str | None
    params: Mapping[object, object] | None

class TestResultMsg(NamedTuple):
    stdout: str | None
    stderr: str | None
    test_name: str
    total_time: timedelta | None
    results: list[SubtestResult]

class HTestResultClient(CheckCWDDidNotChanged,
                        Failfast,
                        CaptureStdio,
                        TestExecStopwatch):
    """Client side of result class used by the multi-process runner.

    An instance of this class run in each worker process. The outcome of each
    test is sent back to the master process in the form of ResultMsg object.

    It partially implements the unittest.TestResult interface.
    """

    def __init__(
            self, worker_id: int, conn: Connection,
            **kwds: Any) -> None:
        super().__init__(**kwds)
        self._worker_id: int = worker_id
        self._conn: Connection = conn
        self._result_attrs: dict[str, Any] | None = None
        self._sub_results: list[SubtestResult] = []

    def stopTest(self, test: unittest.TestCase | str) -> None:
        super().stopTest(test)
        self._send_outcome()

    def _send_outcome(self) -> None:
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

    def addOutcome(
            self, test: unittest.TestCase | str, status: Status,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
        super().addOutcome(test, status, err, reason, params)
        self._save_result(test, status, err, reason, params)

    def addDuration(self, test: unittest.TestCase, elapsed: float) -> None:
        pass  # We already track the duration of each test using the stopwatch.

    def _save_result(
            self, test: unittest.TestCase | str, status: Status,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
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
            params=_serialize_subtest_params(params),
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

    def __init__(
            self, result_printer: ResultPrinter, **kwds: Any) -> None:
        super().__init__(**kwds)
        self._printer = result_printer
        # The last result message received.
        self._last_result_msg: TestResultMsg | None = None
        # Store the sum of the execution time of each finished tests.
        self._total_split_time: timedelta = timedelta(0)

    def process_result(self, result_msg: TestResultMsg) -> None:
        ### Update internal state.
        self._last_result_msg = result_msg
        last_split_time = self.last_split_time
        assert last_split_time is not None
        self._total_split_time += last_split_time
        # Force reset here because startTest() last call may have been for
        # another test than us since several are running in parallel. The
        # effect is that the header will always be printed but it is
        # important since last progress message may be for another test.
        self._printer.reset()
        for result in result_msg.results: # Show result for each subtest.
            ### Dispatch handling of the received message.
            self.addOutcome(result_msg.test_name, result.status,
                            err=result.error,
                            reason=result.reason,
                            params=result.params)
        self.stopTest(result_msg.test_name)

    def startTest(self, test: unittest.TestCase | str) -> None:
        self._printer.print_message(test, Status.RUNNING, self.status_counters,
                                    self.progress,
                                    self.mean_split_time,
                                    self.last_split_time)
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase | str) -> None:
        assert self._last_result_msg is not None
        super().stopTest(test)
        self._printer.print_ios(test,
                                self._last_result_msg.stdout,
                                self._last_result_msg.stderr)

    def addSubTest(
            self, test: unittest.TestCase, subtest: unittest.TestCase,
            err: Any) -> None:
        # We do not have sub test in this class since we receive sub tests
        # result in batch.
        raise NotImplementedError

    def addOutcome(
            self, test: unittest.TestCase | str, status: Status,
            err: Any = None, reason: str | None = None,
            params: Mapping[object, object] | None = None) -> None:
        assert self._last_result_msg is not None
        super().addOutcome(test, status, err, reason, params)
        self._printer.print_message(test, status, self.status_counters,
                                    self.progress,
                                    self.mean_split_time,
                                    self.last_split_time,
                                    err=err, reason=reason, params=params)

    def print_summary(self) -> None:
        prev_counters = self.load_status()
        self._printer.print_summary(
            self.testsRun, self.subtestsRun,
            prev_counters,
            self.status_counters,
            self.subtests_status_counters,
            self.total_split_time,
            self.mean_split_time,
            self.walltime)
        self.save_status()

    @property
    def last_split_time(self) -> timedelta | None:
        # The last split time in multiprocess mode is the total execution
        # time of the test that just finished. For the first test we return
        # None as Stopwatch.last_split_time() does.
        if self._last_result_msg is None:
            return
        return self._last_result_msg.total_time

    @property
    def mean_split_time(self) -> timedelta:
        if self.testsRun == 0:
            return timedelta(0)
        return self.total_split_time / self.testsRun

    @property
    def total_split_time(self) -> timedelta:
        return self._total_split_time
