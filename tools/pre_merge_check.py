#!/usr/bin/env python3
"""
pre_merge_check.py — run every locally-runnable CI gate in one command before
declaring a change "ready for merge."

Usage:
  python3 tools/pre_merge_check.py [--skip-aot] [--skip-selfcontained] [--skip-tests] [--skip-openspec] [--skip-wsl]

Background (HK-006, see the QA memory note this script exists to satisfy):
`daemon-background-mode` (PR #78) was declared "ready for merge" after only
reading REQUIREMENTS.md's content — not running the scripts that actually
verify it. CI immediately failed Gate G9a (doc/VERSION drift) and Gate G3
(a new requirement with no test carrying its "FR-###:" DisplayName prefix).
Both gates are trivially runnable locally and would have failed instantly.
This script exists so there is exactly ONE command to run — not four
separately-remembered ones — before telling anyone a change is ready.

What this runs, in order:
  1. Gate G9a — doc/VERSION consistency        (tools/check_version_docs.py)
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


def step_g9a():
    result = GateResult("G9a — doc/VERSION consistency")
    code, _ = _run([sys.executable, os.path.join("tools", "check_version_docs.py")])
    result.status = "PASS" if code == 0 else "FAIL"
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
    skip_aot = "--skip-aot" in args
    skip_selfcontained = "--skip-selfcontained" in args
    skip_tests = "--skip-tests" in args
    skip_openspec = "--skip-openspec" in args
    skip_wsl = "--skip-wsl" in args

    results = []

    results.append(step_g9a())
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
