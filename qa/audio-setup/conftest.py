"""Tests call the COM-backed readers in-process. A cyclic-GC Release of a stale comtypes pointer crashed
the test run natively (same stack as the 2026-10-03 sampler crash), so GC is off, as in the worker."""
import gc


def pytest_configure(config):
    gc.disable()
