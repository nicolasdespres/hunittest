# -*- encoding: utf-8 -*-
"""Routines to execute test suites.
"""

import unittest
import multiprocessing as mp
import sys
import traceback
from multiprocessing.connection import Connection, wait
from typing import Any, NamedTuple, Sequence, cast

from hunittest.unittestresultlib import HTestResultClient
from hunittest.unittestresultlib import HTestResult
from hunittest.unittestresultlib import HTestResultServer
from hunittest.unittestresultlib import TestResultMsg
from hunittest.coveragelib import CoverageInstrument

class _ErrMsg(NamedTuple):
    """Message representing an uncaught exception raised in the worker process.
    """

    type: type[BaseException]
    value: BaseException
    msg: list[str]

    def print_exception(self, prefix: str) -> None:
        for item in self.msg:
            for line in item.splitlines():
                print(prefix, line)

_testLoader: unittest.TestLoader = unittest.loader.defaultTestLoader

def _worker_run_aux(test_name: str, result: HTestResultClient) -> None:
    test = _testLoader.loadTestsFromNames([test_name])
    test(cast(unittest.TestResult, result))

def _worker_run(
        conn: Connection, worker_id: int,
        worker_kwargs: dict[str, Any] | None,
        cov_args: dict[str, Any] | None) -> None:
    """Executed in the worker process.
    """
    if cov_args is None:
        cov_args = {}
    if worker_kwargs is None:
        worker_kwargs = {}
    cov = CoverageInstrument(**cov_args)
    with conn, cov:
        result = HTestResultClient(worker_id, conn, **worker_kwargs)
        done = False
        while not done:
            try:
                msg = conn.recv()
            except EOFError:
                raise RuntimeError("parent process of worker {} probably "
                                   "died unexpectedly.".format(worker_id))
            else:
                if msg is None:
                    done = True
                elif isinstance(msg, str):
                    try:
                        _worker_run_aux(msg, result)
                    except (Exception, KeyboardInterrupt, SystemExit) as e:
                        msg_obj = _ErrMsg(
                            type(e), e,
                            traceback.format_exception(*sys.exc_info()))
                        conn.send((worker_id, msg_obj))
                        done = True
                else:
                    raise RuntimeError("worker {} received unexpected message: "
                                       "{!r}".format(worker_id, msg))

def run_concurrent_tests(
        test_names: Sequence[str], result: HTestResultServer, njobs: int = 0,
        cov_args: dict[str, Any] | None = None,
        worker_kwargs: dict[str, Any] | None = None) -> None:
    """Run multiple tests concurrently using multiple process.

    This function is executed in the master process. It distribute tests to
    each worker. The scheduling is trivial: when a worker finished the next
    not-yet-run test spec is sent to it. Workers later send a TestResultMsg back
    to the master process. If an error occurred the worker is stopped and never
    re-spawned. A bidirectional connection pipe
    connects the master process to each of its worker.
    """
    if njobs <= 0:
        njobs = mp.cpu_count()

    def start_test(conn: Connection, test_name: str) -> None:
        conn.send(test_name)
        result.startTest(test_name)

    def stop_worker(conn: Connection) -> None:
        """Tell the worker connected to the given *conn* pipe to stop."""
        conn.send(None)

    ntest = len(test_names)
    if ntest == 0:
        return
    nproc = min(ntest, njobs)
    ### Create workers
    conns: list[Connection] = []
    workers: list[mp.Process] = []
    for i in range(nproc):
        my_conn, worker_conn = mp.Pipe()
        proc = mp.Process(target=_worker_run,
                          args=(worker_conn, i, worker_kwargs, cov_args))
        conns.append(my_conn)
        workers.append(proc)
        proc.start()
        # We close the writable end of the pipe now to be sure that
        # p is the only process which owns a handle for it.  This
        # ensures that when p closes its handle for the writable end,
        # wait() will promptly report the readable end as being ready.
        worker_conn.close()
    ### Distribute work
    try:
        # Bootstrap the pool of workers by sending one test to each of them.
        t = 0
        while t < nproc:
            start_test(conns[t], test_names[t])
            t += 1
        while conns:
            for ready_conn in wait(conns):
                conn = cast(Connection, ready_conn)
                try:
                    msg = conn.recv()
                except EOFError:
                    # The other end of the connection has been closed. Remove
                    # it so that we exit the loop when the connections list is
                    # empty.
                    conns.remove(conn)
                else:
                    # Print results and send new test.
                    worker_id, obj = cast(tuple[int, object], msg)
                    if isinstance(obj, _ErrMsg):
                        obj.print_exception("[worker{}]".format(worker_id))
                    elif isinstance(obj, TestResultMsg):
                        result.process_result(obj)
                        # Start next test if there is still some
                        if t < ntest and not result.shouldStop:
                            start_test(conn, test_names[t])
                            t += 1
                        else:
                            stop_worker(conn)
                    else:
                        raise RuntimeError("main process cannot handle "
                                           "message {!r} "
                                           "from worker {}"
                                           .format(obj, worker_id))
    finally:
        for conn in conns:
            stop_worker(conn)
            conn.close()
        ### Wait for workers to finish.
        # FIXME(Nicolas Despres): Add a timeout on join()
        for p in workers:
            p.join()

def run_monoproc_tests(
        test_names: Sequence[str], result: HTestResult,
        cov: CoverageInstrument) -> None:
    with cov:
        for test_name in test_names:
            # If a test has failed and -f/--failfast is set we must exit now.
            if result.shouldStop:
                break
            test = _testLoader.loadTestsFromNames([test_name])
            test(cast(unittest.TestResult, result))
