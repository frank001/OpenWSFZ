#!/usr/bin/env python3
"""
capture_build_provenance.py — record which git branch/commit/dirty-state a
just-published OpenWSFZ.Daemon binary was actually built from.

Background (Architect, 2026-09-22, reading endurance_supervisor.py commit
85c43a77): "the latest binary" is ambiguous once more than one branch carries
decoder-affecting work -- qa/live-gap-map (main-based, shim 20260051) and
decoding_improvement (shim 20260054, Stage 1 suppression) are BOTH "latest" on
their own branch, and they are not the same decoder. Querying the running
daemon's own /api/v1/status doesn't resolve this: its reported version string
(confirmed live, 2026-09-22: "0.49", no commit suffix) carries no git
provenance in this build. So provenance has to be captured independently, at
build time, by whoever runs the publish -- this script is that capture step.

Run this immediately after tools/publish_selfcontained.py, on the SAME
worktree, before anything else touches the tree (a checkout, a stash, a new
commit) -- it records the state of the tree at the moment it is called, which
is only meaningful if that is still the state the binary was built from.

Writes <publish_dir>/build_provenance.json:
  {"branch": <str>, "commit": <40-hex str>, "dirty": <bool>,
   "dirty_files": [<paths>] (only if dirty), "captured_utc": <ISO8601>}

endurance_supervisor.py's PRECHECK reads this file (same directory as
--daemon-exe) and REQUIRES it (refuses to arm if missing) and REFUSES to arm
if dirty=True -- until the Captain has ruled on which branch's binary is "the"
standard one, provenance is recorded and a dirty tree is refused outright, per
the Architect's interim instruction.

Usage:
  python3 tools/capture_build_provenance.py [--rid <rid>]
  (same --rid convention as tools/publish_selfcontained.py; defaults to the
  local platform's RID)

Exit codes
  0  wrote build_provenance.json
  1  git command failed (not a git checkout, or git not on PATH)
  2  usage / environment error
"""
import argparse
import datetime
import json
import os
import platform
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAEMON_PROJECT = os.path.join("src", "OpenWSFZ.Daemon")


def local_rid():
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "win-x64"
    if system == "Linux":
        return "linux-x64"
    if system == "Darwin":
        return "osx-arm64" if machine in ("arm64", "aarch64") else "osx-x64"
    return None


def publish_dir(rid):
    # The MSBuild default publish output for this project/config -- same path
    # tools/publish_selfcontained.py's own docstring names as canonical (no -o
    # override there, deliberately).
    return os.path.join(REPO_ROOT, DAEMON_PROJECT, "bin", "Release", "net10.0", rid, "publish")


def git(args):
    r = subprocess.run(["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rid", default=None, help="Runtime identifier (default: local platform)")
    args = parser.parse_args()

    rid = args.rid or local_rid()
    if rid is None:
        print(f"error: could not determine a default RID for this platform "
              f"({platform.system()}/{platform.machine()}) — pass --rid explicitly.", file=sys.stderr)
        return 2

    pdir = publish_dir(rid)
    if not os.path.isdir(pdir):
        print(f"error: {pdir} does not exist -- run tools/publish_selfcontained.py --rid {rid} first.",
              file=sys.stderr)
        return 2

    try:
        branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
        commit = git(["rev-parse", "HEAD"])
        status = git(["status", "--porcelain"])
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    dirty_files = [line[3:] for line in status.splitlines() if line.strip()]
    provenance = {
        "branch": branch,
        "commit": commit,
        "dirty": bool(dirty_files),
        "dirty_files": dirty_files,
        "captured_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = os.path.join(pdir, "build_provenance.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=1)
    print(f"wrote {out}")
    print(json.dumps(provenance, indent=1))
    if provenance["dirty"]:
        print(f"\nWARNING: working tree is DIRTY ({len(dirty_files)} file(s)). "
              f"endurance_supervisor.py's PRECHECK will refuse to arm against this build.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
