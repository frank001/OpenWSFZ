#!/usr/bin/env python
"""Post-play steps of run_study.py (collect logs, trim to the battery window, match, S3c, analyse) for a battery whose PLAYBACK
finished but whose collection step could not find its inputs (QA tooling, Linux).

Why it exists: run_study_detached only forwards ``--wsjt-all-txt`` if WSJT-X's ALL.TXT exists when the battery STARTS; on a clean
WSJT-X profile it does not, so run_study.py falls back to its Windows default path and stops after the last scenario. The
audio and both decoders' logs are intact; this script performs steps 3-5 of run_study.main() with explicit paths, calling the
same functions (``_trim_log_to_window``, ``_py``, the same matcher / S3c scorer / analyser arguments).

    python post_run_linux.py --run-dir <results/YYYY-MM-DD-sha7> --wsjt-all-txt <path> --owsfz-all-txt <path> \\
           --battery-start 2026-10-11T02:31:11Z --wsjt-version "<exact build string>"
"""
import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent          # qa/rr-study
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "linux" / "shim"))

import run_study as RS  # noqa: E402  (main() is guarded by __name__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--wsjt-all-txt", required=True)
    ap.add_argument("--owsfz-all-txt", required=True)
    ap.add_argument("--battery-start", required=True, help="UTC, e.g. 2026-10-11T02:31:11Z (status.json battery_started_utc)")
    ap.add_argument("--wsjt-version", required=True, help="the exact WSJT-X build string recorded for this run")
    ap.add_argument("--scenarios", default="S1,S1b,S2,S3,S4,S5,S7,S8,S3c")
    a = ap.parse_args()

    run_dir = Path(a.run_dir).resolve()
    start = datetime.strptime(a.battery_start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    scenario_ids = [s.strip() for s in a.scenarios.split(",") if s.strip()]
    arm = RS._load_arm_config(run_dir)
    flag_state = arm.get("subtraction_enabled", "unknown")
    build_sha = arm.get("commit") or "unknown"
    dll_prefix = (arm.get("dll_sha256") or "unknown")[:16]

    wsjt_dest, owsfz_dest = run_dir / "wsjt-all.txt", run_dir / "owsfz-all.txt"
    shutil.copy2(a.wsjt_all_txt, wsjt_dest)
    shutil.copy2(a.owsfz_all_txt, owsfz_dest)
    for dest in (wsjt_dest, owsfz_dest):
        kept, dropped = RS._trim_log_to_window(dest, start)
        print(f"  Trimmed {dest.name} to the battery window: kept {kept} lines, dropped {dropped}")
    (run_dir / "wsjt-version.txt").write_text(a.wsjt_version, encoding="utf-8")

    for sid in scenario_ids:
        if sid == RS._S3C_ID:
            continue
        RS._py("harness/matcher.py", "--run-dir", str(run_dir), "--scenario", sid, "--wsjt", str(wsjt_dest), "--owsfz", str(owsfz_dest))
        print(f"  [OK] {sid} matched", flush=True)
    if RS._S3C_ID in scenario_ids:
        r = RS._py("s3c/s3c_score.py", "--scenario", str(RS._SCENARIO_REGISTRY[RS._S3C_ID]), "--run-dir", str(run_dir),
                   "--wsjtx-alltxt", str(wsjt_dest), "--owsfz-alltxt", str(owsfz_dest), "--subtraction-enabled", flag_state,
                   "--build-sha", build_sha, "--dll-sha256-prefix", dll_prefix, "--trend", str(HERE / "s3c_trend.csv"), check=False)
        if r.returncode != 0:
            print(f"  [WARN] S3c scoring exited {r.returncode}", flush=True)
    RS._py("harness/analyse.py", "--run-dir", str(run_dir))
    print(f"Done. Report: {run_dir / 'report.md'}")


if __name__ == "__main__":
    main()
