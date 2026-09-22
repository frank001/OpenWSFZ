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

GATE SCOPE (Architect ruling, 2026-09-22, reading commit c1a27a67's whole-tree
version -- "a whole-tree check blocks on files that can't reach the binary,
and a gate that fires on irrelevant state gets bypassed, HK-021(k)"):
endurance_supervisor.py's PRECHECK refuses to arm only when a change (tracked
or untracked) exists under BUILD_RELEVANT_PREFIXES/BUILD_RELEVANT_ROOT_NAMES
below -- src/, native/, repo-root build inputs (*.sln, Directory.Build.*,
Directory.Packages.props, global.json, NuGet.config), and this project's own
publish script. The WHOLE-tree dirty_files list is still recorded in full,
every time, as disclosure -- it is just not what gates.

Writes <publish_dir>/build_provenance.json:
  {"branch": <str>, "commit": <40-hex str>,
   "dirty": <bool>            -- WHOLE-tree, disclosure only, never gates,
   "dirty_files": [<paths>]   -- WHOLE-tree, disclosure only,
   "build_dirty": <bool>      -- build-relevant subset, THIS is the gate,
   "build_dirty_files": [<paths>],   -- the subset that set build_dirty,
   "captured_utc": <ISO8601>}

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

# Path-prefix list, in code, not prose (Architect ruling, 2026-09-22). A repo-relative path
# (forward slashes, as git status --porcelain reports) is build-relevant if it starts with one
# of these prefixes...
BUILD_RELEVANT_PREFIXES = ("src/", "native/")
# ...or is this exact repo-root file...
BUILD_RELEVANT_EXACT = {"tools/publish_selfcontained.py"}
# ...or is a repo-ROOT-level file (no "/" in it) matching one of these build-input patterns.
BUILD_RELEVANT_ROOT_SUFFIXES = (".sln",)
BUILD_RELEVANT_ROOT_PREFIXES = ("directory.build.",)
BUILD_RELEVANT_ROOT_EXACT = {"directory.packages.props", "global.json", "nuget.config"}


def is_build_relevant(path):
    """path is repo-relative, as returned by git status --porcelain (forward or back slashes
    both handled)."""
    p = path.replace("\\", "/")
    if p in BUILD_RELEVANT_EXACT:
        return True
    if any(p.startswith(prefix) for prefix in BUILD_RELEVANT_PREFIXES):
        return True
    if "/" not in p:
        low = p.lower()
        if low.endswith(BUILD_RELEVANT_ROOT_SUFFIXES):
            return True
        if low.startswith(BUILD_RELEVANT_ROOT_PREFIXES):
            return True
        if low in BUILD_RELEVANT_ROOT_EXACT:
            return True
    return False


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
    build_dirty_files = [p for p in dirty_files if is_build_relevant(p)]
    provenance = {
        "branch": branch,
        "commit": commit,
        "dirty": bool(dirty_files),
        "dirty_files": dirty_files,
        "build_dirty": bool(build_dirty_files),
        "build_dirty_files": build_dirty_files,
        "captured_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = os.path.join(pdir, "build_provenance.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=1)
    print(f"wrote {out}")
    print(json.dumps(provenance, indent=1))
    if provenance["build_dirty"]:
        print(f"\nWARNING: {len(build_dirty_files)} BUILD-RELEVANT file(s) dirty. "
              f"endurance_supervisor.py's PRECHECK will refuse to arm against this build.",
              file=sys.stderr)
    elif provenance["dirty"]:
        print(f"\nNote: {len(dirty_files)} file(s) dirty, none build-relevant -- recorded for "
              f"disclosure, does not gate.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
