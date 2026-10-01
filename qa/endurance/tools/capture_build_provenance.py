#!/usr/bin/env python
"""Writes <publish-dir>/build_provenance.json for endurance_supervisor.py's PRECHECK (QA-owned; re-created 2026-09-30).

The original tools/capture_build_provenance.py was not in the repository (it lived in an ephemeral build tree), so this file
re-creates it from the contract the supervisor reads (endurance_supervisor.py: load_build_provenance / precheck). Fields:
  branch, commit, dirty, dirty_files, build_dirty, build_dirty_files, captured_utc
plus, as extra disclosure the supervisor ignores: libft8_sha256 (the DLL next to the daemon exe), daemon_exe, checkout.

build_dirty is the ONLY gate (Architect ruling 2026-09-22): True iff a file under a build-relevant path has uncommitted changes.
BUILD_RELEVANT below = src/, native/, tests are NOT build inputs, plus the root build files. The whole-tree dirty/dirty_files is
recorded as disclosure only.

Usage: python capture_build_provenance.py <checkout-dir> <publish-dir>
Run it IMMEDIATELY after `dotnet publish`, in the same clean checkout the publish came from.
"""
import datetime
import hashlib
import json
import os
import subprocess
import sys

BUILD_RELEVANT_PREFIXES = ("src/", "native/")
BUILD_RELEVANT_FILES = ("Directory.Build.props", "Directory.Build.targets", "Directory.Packages.props", "global.json",
                        "nuget.config", "NuGet.config", "OpenWSFZ.slnx", "VERSION")


def git(checkout, *a):
    return subprocess.run(["git", "-C", checkout, *a], capture_output=True, text=True).stdout.strip()


def main():
    checkout, publish = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    commit = git(checkout, "rev-parse", "HEAD")
    branch = git(checkout, "rev-parse", "--abbrev-ref", "HEAD")
    status = [l for l in git(checkout, "status", "--porcelain").splitlines() if l.strip()]
    dirty_files = [l[3:].strip().strip('"') for l in status]
    relevant = [f for f in dirty_files
                if f.replace("\\", "/").startswith(BUILD_RELEVANT_PREFIXES) or os.path.basename(f) in BUILD_RELEVANT_FILES]
    dll = os.path.join(publish, "libft8.dll")
    sha = hashlib.sha256(open(dll, "rb").read()).hexdigest() if os.path.isfile(dll) else None
    rec = {"branch": branch, "commit": commit, "dirty": bool(dirty_files), "dirty_files": dirty_files,
           "build_dirty": bool(relevant), "build_dirty_files": relevant,
           "captured_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "libft8_sha256": sha, "daemon_exe": os.path.join(publish, "OpenWSFZ.Daemon.exe"), "checkout": checkout}
    out = os.path.join(publish, "build_provenance.json")
    json.dump(rec, open(out, "w"), indent=1)
    print(json.dumps({k: rec[k] for k in ("branch", "commit", "dirty", "build_dirty", "libft8_sha256", "captured_utc")}, indent=1))
    return 0 if not relevant else 1


if __name__ == "__main__":
    sys.exit(main())
