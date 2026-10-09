"""Tests call the COM-backed readers in-process. A cyclic-GC Release of a stale comtypes pointer crashed
the test run natively (same stack as the 2026-10-03 sampler crash), so GC is off, as in the worker.

2026-10-04: pytest's own ``unraisableexception`` plugin runs a forced ``gc.collect()`` in ``pytest_unconfigure``,
which re-triggered that Release AFTER the last test: an access violation at teardown, exit code 139, and the
summary line swallowed in a redirected run. The worker leaves through ``os._exit`` after flushing for the same
reason (sampler.py, end of ``main``), and so does this session: remember the real exit status, then, once the
summary has been printed (``pytest_unconfigure`` runs after it), flush and leave directly with that status.
"""
import gc
import os
import sys

import pytest

_STATUS = {"code": 0}


def pytest_configure(config):
    gc.disable()


def pytest_sessionfinish(session, exitstatus):
    _STATUS["code"] = int(exitstatus)


@pytest.hookimpl(tryfirst=True)
def pytest_unconfigure(config):
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_STATUS["code"])
