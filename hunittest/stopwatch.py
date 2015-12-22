# -*- encoding: utf-8 -*-
"""Provide a traditional stopwatch.
"""


from datetime import datetime
from datetime import timedelta


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
        if self.is_started:
            return self._total_split_time
        else:
            return timedelta(0)

    @property
    def mean_split_time(self):
        """Return mean split time in microseconds."""
        if self.is_started and self._total_split_time is not None:
            return self._total_split_time / self._splits_count
        else:
            return timedelta(0)

    @property
    def last_split_time(self):
        return self._last_split_time

    @property
    def total_time(self):
        if self.is_started:
            return datetime.utcnow() - self._started_at
        else:
            return timedelta(0)
