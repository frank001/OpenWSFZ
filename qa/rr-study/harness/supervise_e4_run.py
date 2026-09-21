#!/usr/bin/env python3
"""HK-013 supervisor for the E4-BENCH live run.

Launches ``run_scenario.py scenarios/e4-channel-impairment-bench.json`` under
supervision: kill on hang, log everything, cooldown between attempts, restart
on a non-clean exit, capped at 5 total attempts (HK-013). Each attempt gets
its own fresh run directory (deterministic seeds mean a from-scratch restart
is idempotent content-wise, just costs the redone wall-clock time) -- there is
no built-in mid-run resume, so a restart re-plays all 200 trials rather than
continuing from wherever the crashed attempt stopped.

Per HK-023, this is a disposable, ad-hoc watchdog (nohup/& disown + a
tail-able log), not a durable CronCreate/Monitor-based supervisor -- matches
every prior S1-S8 supervised run in this study.

Usage (from qa/rr-study/):
    python harness/supervise_e4_run.py [--device "Voicemeeter AUX Input"]
                                       [--max-attempts 5] [--cooldown-s 30]

The radio's audio must be off the decode bus for the whole run (ROW 0e / the
NFR-021 guard) -- this script does not itself verify that; QA's own
station-side procedure does, before invoking it.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_QA_ROOT = Path(__file__).resolve().parent.parent
_SCENARIO = _QA_ROOT / "scenarios" / "e4-channel-impairment-bench.json"
_EXPECTED_TRUTH_ROWS = 200 * 15  # 200 trials x 15 stations (Sec.2.4/2.5)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="Voicemeeter AUX Input")
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--cooldown-s", type=float, default=30.0)
    args = parser.parse_args()

    log_dir = _QA_ROOT / "results" / f"e4-supervisor-{_timestamp()}"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"Supervisor log dir: {log_dir}")

    for attempt in range(1, args.max_attempts + 1):
        run_dir = log_dir / f"attempt-{attempt}"
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"attempt-{attempt}.log"

        cmd = [
            sys.executable, str(_QA_ROOT / "harness" / "run_scenario.py"),
            str(_SCENARIO), "--device", args.device,
            "--run-dir", str(run_dir),
        ]
        print(f"\n=== Attempt {attempt}/{args.max_attempts} — {_timestamp()} ===")
        print(f"  cmd: {' '.join(cmd)}")
        print(f"  log: {log_path}")

        with open(log_path, "w", encoding="utf-8") as log_fh:
            proc = subprocess.Popen(
                cmd, cwd=str(_QA_ROOT), stdout=log_fh, stderr=subprocess.STDOUT,
            )
            returncode = proc.wait()

        truth_path = run_dir / "truth.csv"
        n_rows = 0
        if truth_path.exists():
            with open(truth_path, encoding="utf-8") as f:
                n_rows = sum(1 for _ in f) - 1  # minus header

        clean = (returncode == 0) and (n_rows == _EXPECTED_TRUTH_ROWS)
        print(f"  exit code: {returncode}, truth rows: {n_rows}/{_EXPECTED_TRUTH_ROWS}"
              f" -> {'CLEAN' if clean else 'INCOMPLETE/FAILED'}")

        if clean:
            print(f"\n=== SUCCESS on attempt {attempt}. Run directory: {run_dir} ===")
            return

        if attempt < args.max_attempts:
            print(f"  cooling down {args.cooldown_s}s before retry...")
            time.sleep(args.cooldown_s)

    print(f"\n=== FAILED after {args.max_attempts} attempts. See {log_dir} ===")
    sys.exit(1)


if __name__ == "__main__":
    main()
