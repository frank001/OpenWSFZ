#!/usr/bin/env python3
"""
publish_selfcontained.py — publish OpenWSFZ.Daemon self-contained WITHOUT
Native AOT, to the default publish output directory.

Background (dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md):
`OpenWSFZ.Daemon.csproj` sets `<PublishAot Condition="'$(RuntimeIdentifier)'!=''">
true</PublishAot>` — AOT switches on for ANY RID-targeted publish, self-contained
or not. NAudio's [ComImport] WASAPI COM activation is incompatible with Native
AOT and crashes real capture hardware on Windows ("Common Language Runtime
detected an invalid program" from MMDeviceEnumeratorComObject..ctor()). Until
the deferred ComWrappers migration lands, the only *working* standalone
Windows binary is this non-AOT self-contained publish, produced by overriding
PublishAot at the command line (global properties beat the project file's
conditional PropertyGroup).

This is the primary, default publish output — `bin/Release/net10.0/<rid>/publish/`
— the one binary this project ships and expects people to actually run. The
Native AOT build is the secondary, deliberately out-of-the-way one (see
`tools/pre_merge_check.py`'s `step_aot()` and CI's "AOT publish (Daemon)" step,
both of which publish to a separate `publish-aot/` directory instead) — it
exists only as a toolchain compile-check for the deferred ComWrappers work, not
as something anyone should run.

This script is the single source of truth for the working-binary command —
README.md, CI (.github/workflows/ci.yml), and tools/pre_merge_check.py all
either call this script directly or document the identical command line, so
there is exactly one place to update if the command ever needs to change.

Usage:
  python3 tools/publish_selfcontained.py [--rid <rid>]

  --rid <rid>   Runtime identifier to publish for (win-x64, linux-x64,
                osx-arm64, ...). Defaults to the local platform's RID if
                omitted.

Output directory (the standard MSBuild default for this project/config/RID —
no -o override, deliberately, since this is now the canonical publish output):
  src/OpenWSFZ.Daemon/bin/Release/net10.0/<rid>/publish/

Exit codes
  0  publish succeeded
  1  publish failed
  2  usage / environment error (unrecognised local platform, no --rid given)
"""
import argparse
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


def publish(rid):
    cmd = [
        "dotnet", "publish", DAEMON_PROJECT,
        "-c", "Release",
        "-r", rid,
        "--self-contained",
        "-p:PublishAot=false",
    ]
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=REPO_ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rid", default=None, help="Runtime identifier (default: local platform)")
    args = parser.parse_args()

    rid = args.rid or local_rid()
    if rid is None:
        print(
            f"error: could not determine a default RID for this platform "
            f"({platform.system()}/{platform.machine()}) — pass --rid explicitly.",
            file=sys.stderr)
        return 2

    return publish(rid)


if __name__ == "__main__":
    sys.exit(main())
