"""M4 CPU load generator. Implements SS6.1's load levels as OS processes rather than Python
threads -- CPython's GIL means a pure-Python busy loop run as a `threading.Thread` cannot
actually occupy more than one logical processor regardless of thread count, which would
silently fail to produce the load levels the spec calls for. `multiprocessing.Process`
workers, each pinned in a tight spin loop, are the substitution that actually saturates C
logical processors the way SS6.1 intends -- disclosed here, not a quiet deviation.

Each worker inherits the launching Python process's priority class, which on Windows is
Normal by default for anything not explicitly started with a different one -- satisfying
"at normal priority" without needing an explicit priority-class call.
"""
from __future__ import annotations

import datetime
import multiprocessing
import time


def log(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}Z] M4-load: {msg}", flush=True)


def _spin(stop_at: float) -> None:
    # Tight busy loop, no sleep, no syscalls in the hot path -- genuinely occupies a core
    # until the deadline. A local counter avoids the loop being optimised away and keeps
    # time.time() calls infrequent enough not to dominate the loop's own cost.
    n = 0
    while True:
        for _ in range(200_000):
            n += 1
        if time.time() >= stop_at:
            return


class LoadGenerator:
    """Context-manager-style controller for N busy-spin worker processes."""

    def __init__(self, n_workers: int, level_label: str):
        self.n_workers = n_workers
        self.level_label = level_label
        self._procs: list[multiprocessing.Process] = []

    def start(self, duration_s: float) -> None:
        stop_at = time.time() + duration_s
        log(f"[{self.level_label}] starting {self.n_workers} busy-spin worker process(es), "
            f"duration={duration_s:.0f}s")
        for _ in range(self.n_workers):
            p = multiprocessing.Process(target=_spin, args=(stop_at,), daemon=True)
            p.start()
            self._procs.append(p)

    def stop(self) -> None:
        alive = [p for p in self._procs if p.is_alive()]
        for p in alive:
            p.terminate()
        for p in self._procs:
            p.join(timeout=5)
        for p in self._procs:
            if p.is_alive():
                log(f"[{self.level_label}] WARNING: worker pid={p.pid} still alive after "
                    f"terminate+join, killing")
                p.kill()
                p.join(timeout=5)
        log(f"[{self.level_label}] {len(self._procs)} worker process(es) stopped")
        self._procs = []

    def __enter__(self) -> "LoadGenerator":
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
