#!/usr/bin/env python3
"""
pre_merge_check.py — run every locally-runnable CI gate in one command before
declaring a change "ready for merge."

Usage:
  python3 tools/pre_merge_check.py [--skip-native-refresh] [--skip-aot] [--skip-selfcontained] [--skip-tests] [--skip-openspec] [--skip-wsl]

Background (HK-006, see the QA memory note this script exists to satisfy):
`daemon-background-mode` (PR #78) was declared "ready for merge" after only
reading REQUIREMENTS.md's content — not running the scripts that actually
verify it. CI immediately failed Gate G9a (doc/VERSION drift) and Gate G3
(a new requirement with no test carrying its "FR-###:" DisplayName prefix).
Both gates are trivially runnable locally and would have failed instantly.
This script exists so there is exactly ONE command to run — not four
separately-remembered ones — before telling anyone a change is ready.

Gap found 2026-07-25 (cycle-audio-archive, PR #109): this script's Gate G9
step only ever ran check_version_docs.py (doc/VERSION cross-reference). CI's
own "Gate G9 — Version governance" job runs THAT *and* check_version_bump.py
(the mandatory-bump-on-user-facing-change check, .github/workflows/ci.yml's
G9b step) — a second script this file had never modelled at all. Consequence:
this script reported "READY" on a PR that CI's real Gate G9 then failed
minutes later, for exactly the class of gap this script exists to prevent.
Fixed by adding step_g9b() below, invoking check_version_bump.py against the
same effective base ref CI uses (origin/${{ github.base_ref }}), defaulting
to origin/main since that's this project's base branch for the overwhelming
majority of PRs — override with --base-ref for the rare case it isn't
(e.g. a stacked PR per HK-008).

Gap found 2026-08-14 (r0-reproducible-native-build pre-merge review): a
FT8_SHIM_VERSION bump landed with the Windows DLL rebuilt but the committed
Linux `.so` and macOS `.dylib` left stale — invisible to every gate below
except the WSL step, which failed with four opaque "Native library ABI
mismatch" test errors rather than naming the actual, cheaply-checkable cause.
Fixed by adding step_native_binary_freshness() below, which runs FIRST, before
anything else: it reads the expected shim version straight from
Ft8LibInterop.cs, checks all three committed platform binaries with the
already-existing tools/check_native_version.py, and — this is the part beyond
a plain check — REBUILDS any binary this machine has the toolchain for
(Windows always, when running here; Linux via WSL Debian or natively; macOS
only when running natively on macOS with clang) before the rest of the gates
run, so a stale binary doesn't waste a full build+test cycle discovering what
a five-second byte scan already knew. A binary this machine cannot rebuild
(most commonly macOS, since this project's own development happens on
Windows/WSL) is reported INCONCLUSIVE, same convention as the AOT/self-
contained toolchain-missing case below — not silently skipped, not a hard
FAIL for an environment gap. 🛑 This step WRITES to the working tree (a
rebuilt binary replaces the stale committed one on disk) — it does not
commit anything; review and commit the result yourself, same as any other
`git status` change this script's build/publish steps already produce.

What this runs, in order:
  0. Native binary freshness check + auto-rebuild
     (tools/check_native_version.py, native/ft8_lib_build/rebuild_shim.bat,
     native/ft8_lib_build/build_linux.sh) — see "Gap found 2026-08-14" above.
  1. Gate G9a — doc/VERSION consistency        (tools/check_version_docs.py)
  1b. Gate G9b — mandatory VERSION bump on a    (tools/check_version_bump.py)
      newly-introduced User-facing: yes change   — see "Gap found 2026-07-25"
                                                   above. Refreshes the local
                                                   origin/main ref first (a
                                                   stale cached ref would make
                                                   the diff meaningless); a
                                                   fetch failure (no network,
                                                   no remote) degrades to
                                                   INCONCLUSIVE, not FAIL — an
                                                   environment gap, not a code
                                                   regression.
  2. Build the solution in Release              (dotnet build -c Release)
  3. The full local test suite                  (dotnet test -c Release, minus E2E
                                                   unless a published binary already
                                                   exists — see --skip-tests)
  4. Gate G3  — requirement traceability        (tools/TraceabilityCheck)
  5. Lint — UDP capture margin check            (tools/check_udp_capture_margin.py)
     — added 2026-07-19 alongside step 9 below, same incident. Flags a
     ReceiveAllAsync(listener, N, ...) call (ExternalReportingServiceTests.cs's
     UDP-datagram test helper) that asserts a specific WSJT-X datagram type is
     present without a comment documenting why N was chosen. See that script's
     own module docstring for the full incident this exists to catch — the
     short version: PR #90 added a Clear datagram send ahead of Close in
     StopAsync, and a pre-existing test's fixed 3-datagram capture window
     silently truncated Close off the end on a slower CI runner, because
     nothing forced whoever wrote (or later touched) that capture count to
     account for headroom above the observed minimum.
  6. Gate G8  — OpenSpec strict validation       (openspec validate --strict --all)
  6b. Gate G10 — test-delay-synchronization lint (tools/check_test_delay_sync.py)
     — added 2026-07-20 (fix-flaky-test-delay-synchronization). Flags a bare
     Task.Delay(<numeric literal>) synchronization barrier in test code that
     isn't already tracked as pre-existing migration debt (see that change's
     test-delay-debt.md). Pure text scan over test source files — same
     placement style as the UDP capture-margin lint (doesn't depend on the
     build having succeeded, runs unconditionally and early).
  7. A self-contained, non-AOT publish for the local platform
     (dev-tasks/2026-07-18-self-contained-non-aot-working-binary.md)
     — publishes to the DEFAULT output directory
     (bin/Release/net10.0/<rid>/publish/), because this is the one standalone
     binary this project actually ships and expects people to run. Overrides
     PublishAot=false at the command line (global properties beat the project
     file's conditional PropertyGroup) via tools/publish_selfcontained.py.
     Implementation choice made for this gate: it confirms the PUBLISH
     succeeds locally; the functional proof — banner, /api/v1/status 200, and
     both audio-device endpoints 200 against the actual binary — is left to
     CI's SelfContainedNonAotE2ETests, which has the full three-OS matrix.
  8. A real AOT publish for the local platform   (dotnet publish -p:PublishAot=true)
     — the exact check that caught a real AOT-breaking defect in
     remote-daemon-restart after it was believed ready (tasks.md convention,
     every daemon-background-mode-style change since). Publishes to a SEPARATE
     output directory (publish-aot/, never the default publish/ step 7 uses)
     so it can never clobber the working binary. Best-effort: if the local
     machine is missing the native linker toolchain (no MSVC / no clang), this
     step is reported as INCONCLUSIVE rather than FAIL — that is an
     environment gap, not a code regression — but it is never silently
     skipped by default; you have to pass --skip-aot to skip it outright.
     IMPORTANT — PASS here means only that the AOT toolchain compiled the
     binary; it says NOTHING about whether the binary is functionally
     correct. Windows WASAPI audio is known-broken under Native AOT (NAudio's
     [ComImport] COM activation throws "Common Language Runtime detected an
     invalid program" — see dev-tasks/2026-07-18-aot-comwrappers-audio-
     migration.md, the deferred real fix). Do not read an AOT-publish PASS as
     "the standalone binary works" — step 7 above is the gate that actually
     proves that, and is the one that matters day to day.
  9. WSL Debian compile + test (Windows hosts only)
     — a real Linux/glibc build+test run via `wsl -d Debian`, on the SAME
     working tree (via the /mnt/<drive> auto-mount, no copy step), before
     ever pushing to GitHub. Added 2026-07-19 at the Captain's direct
     request: waiting on GitHub's own CI queue+3-OS-runner round trip to
     find out a change doesn't build/pass on Linux is slow; a local WSL
     Debian run is minutes faster and needs no network round trip.
     IMPORTANT — read this honestly, don't over-trust it: this step is a
     genuine, real Linux/glibc environment, so it WILL catch actual
     Linux-specific build/runtime defects (case-sensitive path bugs,
     platform-conditional code, P/Invoke/native-library differences,
     line-ending/locale issues). It is NOT a reliable substitute for CI's
     own ubuntu-latest runner for catching CPU-contention-dependent test
     flakiness — the incident that prompted adding this step (PR #90/#91,
     a UDP-datagram-capture race in ExternalReportingServiceTests that
     passed on Windows locally and on all three OSes' own PR checks, then
     failed only on the push-triggered main-branch CI run on
     ubuntu-latest) was deliberately stress-tested against this exact WSL
     Debian step after the fact — 64 runs (isolated test, full assembly,
     and full solution matching this gate's own invocation) — and never
     reproduced locally. GitHub-hosted runners are shared, often-throttled
     boxes; a local WSL VM on your own hardware is a different resource
     environment even though it's the same kernel family. Treat a PASS
     here as "builds and passes on Linux," not as "guaranteed to pass on
     GitHub's ubuntu-latest too." Best-effort: if WSL itself, the named
     distro, or a working `dotnet` inside it isn't found, this step is
     reported as INCONCLUSIVE rather than FAIL (an environment gap, not a
     code regression) — see --skip-wsl to skip it outright.

Flags:
  --skip-native-refresh  Skip step 0 entirely (no INCONCLUSIVE/FAIL distinction
                     — just not run, exactly like a stale-binary check never
                     happened). Use when you've already refreshed the binaries
                     yourself and don't want this step re-checking/rebuilding.
  --skip-aot        Skip step 8 entirely (no INCONCLUSIVE/FAIL distinction —
                     just not run). Use when you know the local toolchain is
                     unavailable and don't want the noise.
  --skip-selfcontained  Skip step 7 entirely, same semantics as --skip-aot.
  --skip-tests       Skip step 3 (the full test suite). Rarely appropriate.
  --skip-openspec     Skip step 6. Only appropriate for a PR that touches no
                     openspec/ content.
  --skip-wsl         Skip step 9 entirely, same semantics as --skip-aot. Use
                     when you know WSL/the named distro/dotnet inside it
                     isn't available and don't want the noise, or the change
                     genuinely touches nothing that could differ by platform
                     (e.g. a single markdown file).
  --base-ref=<ref>   Base ref for step 1b's mandatory-VERSION-bump check
                     (tools/check_version_bump.py), e.g. --base-ref=origin/develop
                     for a PR not targeting main (HK-008 stacked-PR case).
                     Defaults to origin/main, matching CI's own
                     origin/${{ github.base_ref }} for the overwhelming
                     majority of PRs in this project.

Exit codes
  0  every gate that ran passed (INCONCLUSIVE results do not fail the run)
  1  at least one gate failed
  2  usage / environment error (e.g. `openspec` not on PATH)
"""
import os
import platform
import re
import shutil
import subprocess
import sys
import glob
import tempfile

# CPython only auto-flushes stdout line-by-line when it's attached to an
# interactive terminal; the moment it's redirected to a file or a pipe (a
# background run, `| tee`, a log capture — exactly how this script gets run
# by anything other than a human typing it directly) it silently switches to
# full block buffering (~8KB). Every step in this script streams its
# subprocess output incrementally already (see _run() below), but without
# this, none of it would actually reach a redirected destination until the
# whole process exits — the live feedback during the (often slow) WSL and
# test-suite steps would silently vanish for any non-interactive invocation.
# Confirmed with a standalone repro (2026-07-21, Captain's request after
# reporting "no feedback" while WSL was running): identical script, same
# print() calls, redirected to a file — nothing appears until process exit
# without this line; each line appears in real time with it.
sys.stdout.reconfigure(line_buffering=True)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Toolchain-missing signatures we recognise in a failed AOT publish's output —
# these mean "this machine can't verify this step," not "the code is broken."
_TOOLCHAIN_MISSING_SIGNATURES = (
    "vswhere.exe",
    "is not recognized as an internal or external command",
    "clang: command not found",
    "unable to find a c compiler",
    "link.exe",
)

# The WSL distro step_wsl_debian() targets — hardcoded per the Captain's explicit
# request ("wsl debian"), not made configurable, to keep this gate's behaviour
# predictable rather than silently picking whatever distro happens to be default.
_WSL_DISTRO = "Debian"

# Written to a temp .sh file and run as `bash <path>`, deliberately NOT passed
# inline as a `bash -c "<script>"` argv element — a multi-line script with
# embedded quotes and $-expansions round-tripped through Python's subprocess
# list -> Windows' own list2cmdline argv reconstruction -> wsl.exe -> Linux
# bash -c was observed to silently mangle the script (a DOTNET variable that
# should have been set came out empty, with no error indicating why) when
# this was developed. A file path is a single, simple argument with none of
# that multi-hop re-quoting risk. The temp file is written with explicit `\n`
# line endings (see step_wsl_debian) — Python's default text-mode write on
# Windows uses CRLF, and bash chokes on a CR at the end of every line
# ("$'\r': command not found").
#
# Non-interactive, non-login WSL invocations do NOT reliably inherit a
# `dotnet` on PATH (confirmed: neither `bash -c` nor `bash -lc` picked it up
# in the environment this was developed against, even though an interactive
# shell would via .bashrc/.profile) — so this probes a short list of known
# install locations itself rather than assuming PATH is set up. Extend the
# elif chain if your WSL dotnet installs somewhere else. `set -e` so any real
# build/test failure propagates as a non-zero exit without needing `&&`
# chains between every line.
_WSL_BASH_SCRIPT = """
set -e
if command -v dotnet >/dev/null 2>&1; then
  DOTNET=dotnet
elif [ -x "$HOME/.dotnet/dotnet" ]; then
  DOTNET="$HOME/.dotnet/dotnet"
elif [ -x /usr/local/dotnet/dotnet ]; then
  DOTNET=/usr/local/dotnet/dotnet
elif [ -x /usr/share/dotnet/dotnet ]; then
  DOTNET=/usr/share/dotnet/dotnet
else
  echo "OWSFZ_NO_DOTNET_FOUND"
  exit 127
fi
cd "{repo_path}" || {{ echo "OWSFZ_CD_FAILED"; exit 126; }}
"$DOTNET" build OpenWSFZ.slnx -c Release
"$DOTNET" test OpenWSFZ.slnx -c Release --no-build
""".strip()


def _wsl_path(win_path):
    """Translates an absolute Windows drive-letter path (e.g. D:\\Projects\\Foo)
    into its WSL drvfs auto-mount equivalent (e.g. /mnt/d/Projects/Foo). Returns
    None for anything that isn't a plain drive-letter path (e.g. a UNC path),
    since that can't be reliably auto-mounted this way."""
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", win_path)
    if not match:
        return None
    drive = match.group(1).lower()
    rest = match.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


class GateResult:
    def __init__(self, name):
        self.name = name
        self.status = None   # "PASS", "FAIL", "INCONCLUSIVE", "SKIPPED"
        self.detail = ""


def _run(cmd, cwd=None):
    """Runs cmd, streaming output live, and returns (exit_code, combined_output)."""
    print(f"$ {' '.join(cmd)}")
    # Every command run through here (dotnet build/test, wsl.exe, openspec.cmd,
    # the publish steps) is non-interactive and already has stdout/stderr fully
    # redirected to a pipe below — but on Windows, a console-subsystem child
    # process that doesn't cleanly inherit an existing console from this
    # process's own ancestry gets a brand-new, empty console window allocated
    # for it by default (Captain's report, 2026-07-21: "a terminal window
    # opens, sometimes several in sequence, but I never see any output" — the
    # window is empty by construction, since the real output goes through the
    # pipe instead; CREATE_NO_WINDOW stops it from being allocated at all).
    popen_kwargs = {}
    if platform.system() == "Windows":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(
        cmd, cwd=cwd or REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, **popen_kwargs)
    lines = []
    for line in proc.stdout:
        print(line, end="")
        lines.append(line)
    proc.wait()
    return proc.returncode, "".join(lines)


def _local_rid():
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "win-x64"
    if system == "Linux":
        return "linux-x64"
    if system == "Darwin":
        return "osx-arm64" if machine in ("arm64", "aarch64") else "osx-x64"
    return None


# ---------------------------------------------------------------------------
# Step 0: native binary freshness check + auto-rebuild
# ---------------------------------------------------------------------------

# (platform-key, committed binary path, human label)
_NATIVE_BINARIES = (
    ("win-x64", os.path.join("src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll"), "Windows DLL"),
    ("linux-x64", os.path.join("src", "OpenWSFZ.Ft8", "Native", "linux-x64", "libft8.so"), "Linux .so"),
    ("osx-arm64", os.path.join("src", "OpenWSFZ.Ft8", "Native", "osx-arm64", "libft8.dylib"), "macOS .dylib"),
)


def _expected_shim_version():
    """Reads ExpectedShimVersion straight from Ft8LibInterop.cs — the same
    single source of truth ci.yml's own staleness checks parse (see its
    "Check committed Linux/macOS .../dylib is current" steps)."""
    path = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Interop", "Ft8LibInterop.cs")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    match = re.search(r"ExpectedShimVersion\s*=\s*(\d+)", src)
    if not match:
        raise RuntimeError(f"could not find ExpectedShimVersion in {path}")
    return int(match.group(1))


def _binary_is_current(binary_path, expected):
    code, output = _run([sys.executable, os.path.join("tools", "check_native_version.py"),
                          binary_path, str(expected)])
    return code == 0, output


def _rebuild_win_x64():
    """Rebuilds the Windows DLL via the authoritative native/ft8_lib_build/
    rebuild_shim.bat (r0-reproducible-native-build) — Windows-only (MSVC via
    vcvars64.bat)."""
    if platform.system() != "Windows":
        return None, f"not running on Windows (this machine is {platform.system()})"
    bat = os.path.join(REPO_ROOT, "native", "ft8_lib_build", "rebuild_shim.bat")
    code, output = _run(["cmd", "/c", bat])
    return (code == 0), output


def _rebuild_linux_x64():
    """Rebuilds the Linux .so via native/ft8_lib_build/build_linux.sh — natively
    if this machine already IS Linux, otherwise via `wsl -d Debian` (same
    /mnt/<drive> auto-mount approach as step_wsl_debian(), reusing _wsl_path())."""
    script = os.path.join(REPO_ROOT, "native", "ft8_lib_build", "build_linux.sh")
    if platform.system() == "Linux":
        code, output = _run(["bash", script])
        return (code == 0), output

    wsl_exe = shutil.which("wsl")
    if wsl_exe is None:
        return None, "wsl.exe not found on PATH — cannot reach a Linux toolchain from here"
    wsl_script_path = _wsl_path(script)
    if wsl_script_path is None:
        return None, f"could not translate {script} to a WSL /mnt path"
    code, output = _run([wsl_exe, "-d", _WSL_DISTRO, "--", "bash", wsl_script_path])
    return (code == 0), output


def _rebuild_osx_arm64():
    """Rebuilds the macOS dylib — ONLY possible natively on macOS with clang
    present. Mirrors ci.yml's "Build native macOS dylib (ARM64, Clang)" step
    exactly (same flags, same tools/zero_dylib_uuid.py re-sign so the result is
    deterministic), but built from the vendored tree (native/ft8_lib_vendor/,
    r0-reproducible-native-build) rather than a live clone of frank001/ft8_lib —
    same reasoning as build_linux.sh's own r0-followup fix: the vendored tree is
    already proven content-identical (PROVENANCE.md) and needs no network fetch.
    ⚠️ UNTESTED end-to-end — this project's own development happens on Windows/
    WSL and no macOS machine was available when this was written. The command
    sequence is transcribed from ci.yml's proven recipe, not independently
    verified on real hardware; if it misbehaves, that is a bug report against
    this function, not a mystery to re-derive from scratch."""
    if platform.system() != "Darwin":
        return None, f"not running on macOS (this machine is {platform.system()})"
    if shutil.which("clang") is None:
        return None, "clang not found on PATH — Xcode Command Line Tools not installed"

    vendor = os.path.join(REPO_ROOT, "native", "ft8_lib_vendor")
    patched_decode = os.path.join(REPO_ROOT, "native", "ft8_lib_build", "patched", "ft8", "decode.c")
    patched_monitor = os.path.join(REPO_ROOT, "native", "ft8_lib_build", "patched", "common", "monitor.c")
    shim_c = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "ft8_shim.c")
    out_dylib = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "osx-arm64", "libft8.dylib")

    with tempfile.TemporaryDirectory(prefix="owsfz_macos_rebuild_") as work:
        clang = ["clang", "-std=c11", "-D_GNU_SOURCE", "-O2", "-Wall", "-fPIC",
                 "-I", vendor, "-target", "arm64-apple-macos11.0"]
        sources = [
            os.path.join(vendor, "ft8", n) for n in
            ("constants.c", "crc.c", "encode.c", "ldpc.c", "message.c", "text.c")
        ] + [patched_decode, patched_monitor,
             os.path.join(vendor, "fft", "kiss_fft.c"), os.path.join(vendor, "fft", "kiss_fftr.c")]
        code, output = _run(clang + ["-c"] + sources, cwd=work)
        if code != 0:
            return False, output
        code2, output2 = _run(clang + ["-c", shim_c], cwd=work)
        if code2 != 0:
            return False, output2
        objs = [os.path.splitext(os.path.basename(s))[0] + ".o" for s in sources + [shim_c]]
        link_code, link_output = _run(
            ["clang", "-dynamiclib", "-target", "arm64-apple-macos11.0", "-o", out_dylib, *objs],
            cwd=work)
        if link_code != 0:
            return False, link_output
        uuid_code, uuid_output = _run(
            [sys.executable, os.path.join(REPO_ROOT, "tools", "zero_dylib_uuid.py"), out_dylib])
        return (uuid_code == 0), (output + output2 + link_output + uuid_output)


_NATIVE_REBUILDERS = {
    "win-x64": _rebuild_win_x64,
    "linux-x64": _rebuild_linux_x64,
    "osx-arm64": _rebuild_osx_arm64,
}


def step_native_binary_freshness():
    """
    Runs FIRST, before every other gate (see the module docstring's "Gap found
    2026-08-14"). Checks all three committed platform binaries against
    Ft8LibInterop.cs's ExpectedShimVersion via the existing
    tools/check_native_version.py (a pure byte scan — works cross-platform
    regardless of which OS this script itself is running on), and REBUILDS any
    binary found stale that this machine has a toolchain for, so the expensive
    steps below (full build+test, WSL, AOT/self-contained publish) never waste
    a run discovering what a five-second check already knew.

    A binary that's stale but can't be rebuilt here (wrong OS, missing
    toolchain — most commonly macOS, since this project's own dev happens on
    Windows/WSL) is INCONCLUSIVE, not FAIL — same convention as the AOT/
    self-contained toolchain-missing case. A binary that's stale, gets rebuilt,
    and is STILL stale afterward is a real FAIL — the rebuild script itself
    didn't do what it claims to.

    🛑 WRITES to the working tree when it rebuilds — does not commit. Review
    and commit the result yourself (a `chore(native): rebuild ... to shim
    NNNNN` commit, matching this project's established pattern) before
    pushing.
    """
    result = GateResult("Native binary freshness (check + auto-rebuild)")
    try:
        expected = _expected_shim_version()
    except (OSError, RuntimeError) as exc:
        result.status = "FAIL"
        result.detail = f"could not determine ExpectedShimVersion: {exc}"
        return result

    print(f"Expected FT8_SHIM_VERSION = {expected} (from Ft8LibInterop.cs)")

    notes = []
    any_fail = False
    any_inconclusive = False
    for platform_key, rel_path, label in _NATIVE_BINARIES:
        abs_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.exists(abs_path):
            notes.append(f"{label}: MISSING at {rel_path} (not this gate's concern to create — "
                         f"see BUILD.md)")
            any_inconclusive = True
            continue

        current, _ = _binary_is_current(abs_path, expected)
        if current:
            notes.append(f"{label}: already current ({expected})")
            continue

        print(f"\n{label} is STALE (expected {expected}) — attempting a rebuild...")
        rebuilder = _NATIVE_REBUILDERS[platform_key]
        rebuilt, detail = rebuilder()
        if rebuilt is None:
            notes.append(f"{label}: STALE, could not rebuild here — {detail}")
            any_inconclusive = True
            continue
        if not rebuilt:
            notes.append(f"{label}: STALE, rebuild FAILED — see output above")
            any_fail = True
            continue

        current_after, _ = _binary_is_current(abs_path, expected)
        if current_after:
            notes.append(f"{label}: was STALE — rebuilt, now current ({expected}). "
                          f"REVIEW AND COMMIT {rel_path} before pushing.")
        else:
            notes.append(f"{label}: rebuild ran and exited 0 but the binary is STILL stale — "
                          f"the rebuild script itself is wrong, not an environment gap")
            any_fail = True

    result.detail = "; ".join(notes)
    if any_fail:
        result.status = "FAIL"
    elif any_inconclusive:
        result.status = "INCONCLUSIVE"
    else:
        result.status = "PASS"
    return result


def step_g9a():
    result = GateResult("G9a — doc/VERSION consistency")
    code, _ = _run([sys.executable, os.path.join("tools", "check_version_docs.py")])
    result.status = "PASS" if code == 0 else "FAIL"
    return result


def step_g9b(base_ref="origin/main"):
    """
    G9b — mandatory VERSION bump when a newly-introduced OpenSpec proposal
    declares **User-facing:** yes (tools/check_version_bump.py), mirroring
    CI's own version-governance job exactly (.github/workflows/ci.yml:
    `python3 tools/check_version_bump.py "origin/${{ github.base_ref }}"`).

    Refreshes the local base-ref remote-tracking branch first via
    `git fetch origin <branch>` — a stale cached ref (e.g. an origin/main
    from three days ago still sitting in .git/refs/remotes) would make the
    diff meaningless, silently comparing against the wrong commit rather
    than the real current base. A fetch failure (no network, no remote
    configured, ref doesn't exist) is reported INCONCLUSIVE, not FAIL — an
    environment gap, not a code regression — and the underlying check does
    not run in that case. check_version_bump.py's own exit code 2 ("usage /
    git error", e.g. base_ref not reachable even after a successful fetch)
    is likewise treated as INCONCLUSIVE rather than FAIL, per its own
    documented exit-code contract; only exit code 1 ("a rule was violated")
    is a real FAIL.
    """
    result = GateResult("G9b — mandatory VERSION bump on user-facing change")

    remote_branch = base_ref.split("/", 1)[1] if "/" in base_ref else base_ref
    fetch_code, fetch_output = _run(["git", "fetch", "origin", remote_branch])
    if fetch_code != 0:
        tail = fetch_output.strip().splitlines()[-1] if fetch_output.strip() else "no output"
        result.status = "INCONCLUSIVE"
        result.detail = (
            f"could not `git fetch origin {remote_branch}` ({tail}) — an environment/network "
            "gap, not a code regression. Re-run once network access is available, or pass "
            "--base-ref to point at a ref you can reach.")
        return result

    code, _ = _run([sys.executable, os.path.join("tools", "check_version_bump.py"), base_ref])
    if code == 0:
        result.status = "PASS"
    elif code == 2:
        result.status = "INCONCLUSIVE"
        result.detail = "check_version_bump.py reported a usage/git error (exit 2), not a rule violation — see output above."
    else:
        result.status = "FAIL"
    return result


def step_build():
    result = GateResult("Solution build (Release)")
    code, _ = _run(["dotnet", "build", "OpenWSFZ.slnx", "-c", "Release"])
    result.status = "PASS" if code == 0 else "FAIL"
    return result


def step_tests():
    result = GateResult("Full test suite (Release)")
    code, _ = _run(["dotnet", "test", "OpenWSFZ.slnx", "-c", "Release", "--no-build"])
    result.status = "PASS" if code == 0 else "FAIL"
    return result


def step_g3():
    result = GateResult("G3 — requirement traceability")
    pattern = os.path.join(REPO_ROOT, "**", "bin", "Release", "net10.0", "*.Tests.dll")
    assemblies = [
        p for p in glob.glob(pattern, recursive=True)
        # Exclude RID-specific publish output (win-x64/linux-x64/...) — the
        # plain framework-dependent build output is what CI's own find
        # expression targets too.
        if not re.search(r"[\\/](win|linux|osx)-(x64|arm64)[\\/]", p)
    ]
    if not assemblies:
        result.status = "FAIL"
        result.detail = "no *.Tests.dll found under bin/Release/net10.0 — did the build step run?"
        return result

    code, _ = _run([
        "dotnet", "run", "--project", os.path.join("tools", "TraceabilityCheck"),
        "-c", "Release", "--no-build", "--",
        "--requirements", "REQUIREMENTS.md",
        "--assemblies", *assemblies,
        "--report", "traceability.md",
        "--debt-file", "traceability-debt.md",
    ])
    result.status = "PASS" if code == 0 else "FAIL"
    # traceability.md is a scratch artifact of this run — CI uploads it as an
    # artifact; locally, remove it so it doesn't show up as an untracked file.
    try:
        os.remove(os.path.join(REPO_ROOT, "traceability.md"))
    except OSError:
        pass
    return result


def step_udp_capture_margin():
    result = GateResult("Lint — UDP capture margin check")
    code, _ = _run([sys.executable, os.path.join("tools", "check_udp_capture_margin.py")])
    result.status = "PASS" if code == 0 else "FAIL"
    return result


def step_g10():
    result = GateResult("G10 — test-delay-synchronization lint")
    code, _ = _run([sys.executable, os.path.join("tools", "check_test_delay_sync.py")])
    result.status = "PASS" if code == 0 else "FAIL"
    return result


def step_g8():
    result = GateResult("G8 — OpenSpec strict validation")
    # shutil.which (not a bare "openspec" argv) because a global npm install puts
    # a .cmd/.ps1 shim on Windows PATH, not a directly-executable "openspec" —
    # subprocess.Popen bypasses the shell's PATHEXT-aware resolution and fails
    # to find it with a bare name, even though it resolves fine in an
    # interactive/bash shell. shutil.which does the PATHEXT-aware lookup itself.
    openspec_path = shutil.which("openspec")
    if openspec_path is None:
        result.status = "FAIL"
        result.detail = "`openspec` not found on PATH — install it (see HK-002 memory note)."
        return result
    code, _ = _run([openspec_path, "validate", "--strict", "--all"])
    result.status = "PASS" if code == 0 else "FAIL"
    return result


def step_selfcontained():
    """
    Self-contained NON-AOT publish gate (dev-tasks/2026-07-18-self-contained-non-aot-
    working-binary.md). Overrides PublishAot=false at the command line and publishes to
    the DEFAULT output directory (bin/Release/net10.0/<rid>/publish/) via
    tools/publish_selfcontained.py — this is the one standalone binary this project
    actually ships and expects people to run (see step_aot()'s PASS-meaning note below,
    which is the one that gets diverted out of the way instead).

    Scope of this gate, deliberately: confirms the PUBLISH succeeds locally. It does not
    re-run the functional (banner / /api/v1/status / audio-device-endpoints) proof —
    that's CI's SelfContainedNonAotE2ETests, which has the full three-OS matrix this
    single local machine can't provide.
    """
    result = GateResult("Self-contained non-AOT publish (local platform)")
    rid = _local_rid()
    if rid is None:
        result.status = "INCONCLUSIVE"
        result.detail = f"unrecognised platform ({platform.system()}/{platform.machine()})"
        return result

    code, output = _run([sys.executable, os.path.join("tools", "publish_selfcontained.py"), "--rid", rid])
    if code == 0:
        result.status = "PASS"
        result.detail = (
            "publish succeeded locally; the functional proof (banner, /api/v1/status, "
            "both audio-device endpoints against this binary) runs in CI, not here.")
        return result

    lowered = output.lower()
    if any(sig.lower() in lowered for sig in _TOOLCHAIN_MISSING_SIGNATURES):
        result.status = "INCONCLUSIVE"
        result.detail = (
            "the local native linker toolchain appears to be missing — this is an "
            "environment gap, not necessarily a code regression. Fix the toolchain "
            "or re-run with --skip-selfcontained once you've confirmed the failure is "
            "toolchain-related, not code-related.")
    else:
        result.status = "FAIL"
    return result


def step_aot():
    """
    Native AOT structural-prove-out gate. Deliberately publishes to a SEPARATE output
    directory (publish-aot/, never the default publish/ step_selfcontained() above uses)
    so it can never clobber the working binary. PASS here means only that the AOT
    toolchain compiled the binary — see the detail string below.
    """
    result = GateResult("AOT publish (local platform)")
    rid = _local_rid()
    if rid is None:
        result.status = "INCONCLUSIVE"
        result.detail = f"unrecognised platform ({platform.system()}/{platform.machine()})"
        return result

    out_dir = os.path.join("src", "OpenWSFZ.Daemon", "bin", "Release", "net10.0", rid, "publish-aot") + os.sep
    code, output = _run([
        "dotnet", "publish", os.path.join("src", "OpenWSFZ.Daemon", "OpenWSFZ.Daemon.csproj"),
        "-c", "Release", "-r", rid, "--self-contained", "-p:PublishAot=true", "-o", out_dir,
    ])
    if code == 0:
        result.status = "PASS"
        result.detail = (
            "compiles only — does NOT verify Windows WASAPI audio works under AOT "
            "(known-broken; see dev-tasks/2026-07-18-aot-comwrappers-audio-migration.md). "
            "The self-contained non-AOT gate above is the binary that actually works.")
        return result

    lowered = output.lower()
    if any(sig.lower() in lowered for sig in _TOOLCHAIN_MISSING_SIGNATURES):
        result.status = "INCONCLUSIVE"
        result.detail = (
            "the local native linker toolchain (MSVC on Windows / clang on Linux / "
            "Xcode command line tools on macOS) appears to be missing — this is an "
            "environment gap, not necessarily a code regression. Fix the toolchain "
            "or re-run with --skip-aot once you've confirmed the failure is "
            "toolchain-related, not code-related.")
    else:
        result.status = "FAIL"
    return result


def step_wsl_debian(distro=_WSL_DISTRO):
    """
    Real Linux/glibc build+test via `wsl -d Debian`, operating directly on this
    same working tree through the /mnt/<drive> auto-mount (no copy step, so
    uncommitted changes are covered too, same as every other gate in this
    script). See the module docstring's step 9 for the honest scope of what
    this does and does not catch — added at the Captain's request as a fast
    local substitute for waiting on GitHub CI's own ubuntu-latest runner,
    while being explicit that it is not a reliable substitute for that
    runner's specific CPU-contention-driven flakiness.
    """
    result = GateResult(f"WSL {distro} compile + test")

    if platform.system() != "Windows":
        result.status = "INCONCLUSIVE"
        result.detail = (
            f"WSL is Windows-only — this gate is a no-op on {platform.system()} "
            f"(already native Linux/macOS here, nothing to add).")
        return result

    wsl_exe = shutil.which("wsl")
    if wsl_exe is None:
        result.status = "INCONCLUSIVE"
        result.detail = "wsl.exe not found on PATH — Windows Subsystem for Linux is not installed."
        return result

    wsl_repo_path = _wsl_path(REPO_ROOT)
    if wsl_repo_path is None:
        result.status = "INCONCLUSIVE"
        result.detail = f"could not translate REPO_ROOT ({REPO_ROOT}) to a /mnt/<drive> WSL path."
        return result

    script_content = _WSL_BASH_SCRIPT.format(repo_path=wsl_repo_path)
    fd, script_win_path = tempfile.mkstemp(suffix=".sh", prefix="owsfz_pre_merge_wsl_")
    try:
        # newline="\n" forces LF-only line endings — Python's default text-mode
        # write on Windows uses CRLF, which bash reads as a literal trailing \r
        # on every line and fails on ("$'\r': command not found").
        with os.fdopen(fd, "w", newline="\n") as f:
            f.write(script_content)

        script_wsl_path = _wsl_path(script_win_path)
        if script_wsl_path is None:
            result.status = "INCONCLUSIVE"
            result.detail = f"could not translate temp script path ({script_win_path}) to a WSL path."
            return result

        code, output = _run([wsl_exe, "-d", distro, "--", "bash", script_wsl_path])
    finally:
        try:
            os.remove(script_win_path)
        except OSError:
            pass

    if code == 0:
        result.status = "PASS"
        result.detail = (
            f"compiled and the full test suite passed under a real Linux/glibc runtime "
            f"(WSL {distro}) — same kernel family as CI's ubuntu-latest runner, minutes "
            f"faster than waiting on GitHub's own queue. See the module docstring's step 9 "
            f"for what this does and does not guarantee.")
        return result

    # wsl.exe's OWN error text (distro not registered, etc. — anything raised before
    # control ever reaches the Linux side) comes back UTF-16LE, decoded by _run()'s
    # text-mode capture as one real character followed by a literal NUL (\x00) byte
    # per character — "There is no distribution..." becomes "T\x00h\x00e\x00r\x00e..."
    # (visually renders as "T h e r e" when printed, which is what makes this easy to
    # miss). Signatures that originate from wsl.exe itself (as opposed to the bash
    # script's own `echo` markers, which are genuine UTF-8 from the Linux side and
    # need no special handling) are matched against a NUL-and-whitespace-stripped
    # copy of the output for this reason.
    lowered = output.lower()
    despaced = re.sub(r"[\s\x00]+", "", lowered)
    if "owsfz_no_dotnet_found" in lowered:
        result.status = "INCONCLUSIVE"
        result.detail = (
            f"no working `dotnet` found inside the {distro} WSL distro (checked PATH, "
            f"$HOME/.dotnet, /usr/local/dotnet, /usr/share/dotnet) — install the .NET SDK "
            f"there, or extend _WSL_BASH_SCRIPT's probe list in this file.")
    elif "owsfz_cd_failed" in lowered \
            or "thereisnodistribution" in despaced \
            or "0x80370102" in despaced \
            or "wsl_e_distro_not_found" in despaced \
            or "thesystemcannotfindthepathspecified" in despaced:
        result.status = "INCONCLUSIVE"
        result.detail = (
            f"could not reach the repo inside WSL at {wsl_repo_path}, or the '{distro}' "
            f"distro isn't registered (`wsl --install -d {distro}` to add it) — environment "
            f"gap, not a code regression.")
    else:
        result.status = "FAIL"
        result.detail = "a real Linux/glibc build or test failure — see output above."
    return result


def main():
    args = sys.argv[1:]
    skip_native_refresh = "--skip-native-refresh" in args
    skip_aot = "--skip-aot" in args
    skip_selfcontained = "--skip-selfcontained" in args
    skip_tests = "--skip-tests" in args
    skip_openspec = "--skip-openspec" in args
    skip_wsl = "--skip-wsl" in args
    base_ref = "origin/main"
    for arg in args:
        if arg.startswith("--base-ref="):
            base_ref = arg[len("--base-ref="):]

    results = []

    # Runs FIRST, ahead of every other gate — see the module docstring's
    # "Gap found 2026-08-14." A stale binary rebuilt here means the expensive
    # steps below (build+test, WSL, publish) run against a current binary
    # instead of discovering the staleness themselves, minutes later.
    if skip_native_refresh:
        skipped = GateResult("Native binary freshness (check + auto-rebuild)")
        skipped.status = "SKIPPED"
        skipped.detail = "--skip-native-refresh"
        results.append(skipped)
    else:
        results.append(step_native_binary_freshness())

    results.append(step_g9a())
    results.append(step_g9b(base_ref))
    build_result = step_build()
    results.append(build_result)

    # Pure text scan over test source files — doesn't depend on the build having
    # succeeded, so it runs unconditionally and early (fails fast, cheaply).
    results.append(step_udp_capture_margin())
    results.append(step_g10())

    if build_result.status != "PASS":
        print("\nBuild failed — skipping every step that depends on it "
              "(tests, G3 traceability, WSL Debian compile+test).", file=sys.stderr)
        for name in ("Full test suite (Release)", "G3 — requirement traceability",
                     f"WSL {_WSL_DISTRO} compile + test"):
            skipped = GateResult(name)
            skipped.status = "SKIPPED"
            skipped.detail = "solution build failed"
            results.append(skipped)
    else:
        if skip_tests:
            skipped = GateResult("Full test suite (Release)")
            skipped.status = "SKIPPED"
            skipped.detail = "--skip-tests"
            results.append(skipped)
        else:
            results.append(step_tests())

        results.append(step_g3())

        if skip_wsl:
            skipped = GateResult(f"WSL {_WSL_DISTRO} compile + test")
            skipped.status = "SKIPPED"
            skipped.detail = "--skip-wsl"
            results.append(skipped)
        else:
            results.append(step_wsl_debian())

    if skip_openspec:
        skipped = GateResult("G8 — OpenSpec strict validation")
        skipped.status = "SKIPPED"
        skipped.detail = "--skip-openspec"
        results.append(skipped)
    else:
        results.append(step_g8())

    if skip_selfcontained:
        skipped = GateResult("Self-contained non-AOT publish (local platform)")
        skipped.status = "SKIPPED"
        skipped.detail = "--skip-selfcontained"
        results.append(skipped)
    else:
        results.append(step_selfcontained())

    if skip_aot:
        skipped = GateResult("AOT publish (local platform)")
        skipped.status = "SKIPPED"
        skipped.detail = "--skip-aot"
        results.append(skipped)
    else:
        results.append(step_aot())

    print("\n" + "=" * 72)
    print("PRE-MERGE CHECK SUMMARY")
    print("=" * 72)
    any_fail = False
    for r in results:
        marker = {
            "PASS": "PASS ",
            "FAIL": "FAIL ",
            "INCONCLUSIVE": "WARN ",
            "SKIPPED": "SKIP ",
        }[r.status]
        line = f"[{marker}] {r.name}"
        if r.detail:
            line += f" — {r.detail}"
        print(line)
        if r.status == "FAIL":
            any_fail = True

    print("=" * 72)
    if any_fail:
        print("Result : NOT READY — at least one gate failed. Fix and re-run.")
        return 1

    inconclusive = [r for r in results if r.status == "INCONCLUSIVE"]
    if inconclusive:
        print("Result : PASS WITH WARNINGS — no gate failed outright, but "
              f"{len(inconclusive)} could not be conclusively verified on this "
              "machine (see WARN lines above). Use judgement before declaring "
              "ready for merge.")
        return 0

    print("Result : READY — every gate that ran passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
