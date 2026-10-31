# -*- encoding: utf-8 -*-
"""Provide a traditional stopwatch.
"""


from datetime import datetime, timedelta, timezone


class StopWatch(object):

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._started_at: datetime | None = None
        self._last_split_time: timedelta | None = None
        self._last_split_at: datetime | None = None
        self._total_split_time: timedelta | None = None
        self._tick_count = 0

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def last_split_at(self) -> datetime | None:
        return self._last_split_at

    def start(self) -> None:
        if self.is_started:
            raise RuntimeError("stopwatch already started")
        self._started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self._last_split_at = self._started_at
        self._last_split_time = None
        self._total_split_time = None
        self._splits_count = 0

    @property
    def is_started(self) -> bool:
        return self._started_at is not None

    def _check_is_started(self) -> None:
        if not self.is_started:
            raise RuntimeError("stopwatch not started")

    def split(self) -> None:
        self._check_is_started()
        assert self._last_split_at is not None
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        last_split_time = now - self._last_split_at
        self._last_split_time = last_split_time
        self._last_split_at = now
        self._splits_count += 1
        if self._total_split_time is None:
            self._total_split_time = last_split_time
        else:
            self._total_split_time += last_split_time

    @property
    def splits_count(self) -> int:
        return self._splits_count

    @property
    def total_split_time(self) -> timedelta | None:
        if self.is_started:
            return self._total_split_time
        else:
            return timedelta(0)

    @property
    def mean_split_time(self) -> timedelta:
        """Return mean split time in microseconds."""
        if self.is_started and self._total_split_time is not None:
            return self._total_split_time / self._splits_count
        else:
            return timedelta(0)

    @property
    def last_split_time(self) -> timedelta | None:
        return self._last_split_time

    @property
    def total_time(self) -> timedelta:
        if self.is_started:
            assert self._started_at is not None
            return datetime.now(timezone.utc).replace(tzinfo=None) \
                - self._started_at
        else:
            return timedelta(0)
