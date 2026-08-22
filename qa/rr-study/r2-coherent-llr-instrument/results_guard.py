#!/usr/bin/env python3
"""N14 guard (`openspec/qa-backlog.md` N14): refuse to silently clobber a git-tracked
results file.

Three independent scripts in this directory (`b_dt_c3_offline_negative_dt.py`,
`b_orig_a_origin_convention.py`, `row0g_instrument_gain_check.py`) were each caught
this session overwriting their own committed `results/*.{json,log}` baseline the
moment they were re-run -- no warning, no confirmation, no suffixing. Nothing was
lost (caught via `git status` before anything else touched the tree, restored with
`git checkout --`), but relying on an operator to notice that every single time is
exactly the manual discipline HK-016/HK-017 exist to replace with something
mechanical.

This module is that mechanical guarantee, applied per suggested fix (b) in N14
(shared guard, refuse-without-`--force`) rather than (a) (derive a run-unique
filename), so a re-run's output stays comparable byte-for-byte with the committed
baseline unless the operator explicitly asks to replace it.

Usage (see any of the three scripts above for a wired-in example):

    from results_guard import guard_paths
    ...
    def _write(out_dir, bundle, log_lines):
        guard_paths([os.path.join(out_dir, "foo_report.json"),
                     os.path.join(out_dir, "foo_run.log")], REPO_ROOT)
        P.write_json(...)
        ...

`--force` is read straight off `sys.argv` so call sites need no argparse wiring of
their own (none of the three scripts had one before this fix).
"""
from __future__ import annotations

import os
import subprocess
import sys


def _is_git_tracked(path: str, repo_root: str) -> bool:
    """True iff `path` both exists and is tracked by git in `repo_root`.

    Fails safe (returns False) if git itself is unavailable -- this guard exists to
    add a check, not to make the underlying script unable to run without git on PATH.
    """
    if not os.path.exists(path):
        return False
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0


def guard_paths(paths, repo_root: str, force: bool = None) -> None:
    """Raise SystemExit before any git-tracked path in `paths` would be clobbered.

    `force` defaults to `"--force" in sys.argv`; pass an explicit bool to override
    (e.g. from a script that already has its own argparse). A caller that wants the
    write to proceed unconditionally (this run should replace the baseline) passes
    `force=True` or re-invokes with `--force` on the command line.
    """
    if force is None:
        force = "--force" in sys.argv
    if force:
        return
    tracked = [p for p in paths if _is_git_tracked(p, repo_root)]
    if not tracked:
        return
    lines = [
        "",
        "N14 GUARD (qa-backlog.md): refusing to overwrite git-tracked result file(s) "
        "without --force:",
    ]
    lines += ["  " + p for p in tracked]
    lines += [
        "",
        "These are committed baselines, not scratch output. Remedy:",
        "  1. cp <path> <path>.<utc-timestamp>-<reason>   # preserve today's run first",
        "  2. git checkout -- <path>                       # restore the baseline",
        "  3. re-run with --force only if this run is meant to REPLACE the baseline",
        "     itself (e.g. it is stale and superseded by design, not by accident).",
        "",
    ]
    msg = "\n".join(lines)
    print(msg, file=sys.stderr)
    raise SystemExit(msg)
