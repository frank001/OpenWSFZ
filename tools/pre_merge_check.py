#!/usr/bin/env python3
"""
pre_merge_check.py — run every locally-runnable CI gate in one command before
declaring a change "ready for merge."

Usage:
  python3 tools/pre_merge_check.py [--skip-aot] [--skip-tests] [--skip-openspec]

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
  5. Gate G8  — OpenSpec strict validation       (openspec validate --strict --all)
  6. A real AOT publish for the local platform   (dotnet publish -p:PublishAot=true)
     — the exact check that caught a real AOT-breaking defect in
     remote-daemon-restart after it was believed ready (tasks.md convention,
     every daemon-background-mode-style change since). Best-effort: if the
     local machine is missing the native linker toolchain (no MSVC / no
     clang), this step is reported as INCONCLUSIVE rather than FAIL — that is
     an environment gap, not a code regression — but it is never silently
     skipped by default; you have to pass --skip-aot to skip it outright.

Flags:
  --skip-aot        Skip step 6 entirely (no INCONCLUSIVE/FAIL distinction —
                     just not run). Use when you know the local toolchain is
                     unavailable and don't want the noise.
  --skip-tests       Skip step 3 (the full test suite). Rarely appropriate.
  --skip-openspec     Skip step 5. Only appropriate for a PR that touches no
                     openspec/ content.

Exit codes
  0  every gate that ran passed (INCONCLUSIVE AOT results do not fail the run)
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


class GateResult:
    def __init__(self, name):
        self.name = name
        self.status = None   # "PASS", "FAIL", "INCONCLUSIVE", "SKIPPED"
        self.detail = ""


def _run(cmd, cwd=None):
    """Runs cmd, streaming output live, and returns (exit_code, combined_output)."""
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd, cwd=cwd or REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)
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


def step_aot():
    result = GateResult("AOT publish (local platform)")
    rid = _local_rid()
    if rid is None:
        result.status = "INCONCLUSIVE"
        result.detail = f"unrecognised platform ({platform.system()}/{platform.machine()})"
        return result

    code, output = _run([
        "dotnet", "publish", os.path.join("src", "OpenWSFZ.Daemon", "OpenWSFZ.Daemon.csproj"),
        "-c", "Release", "-r", rid, "--self-contained", "-p:PublishAot=true",
    ])
    if code == 0:
        result.status = "PASS"
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


def main():
    args = sys.argv[1:]
    skip_aot = "--skip-aot" in args
    skip_tests = "--skip-tests" in args
    skip_openspec = "--skip-openspec" in args

    results = []

    results.append(step_g9a())
    build_result = step_build()
    results.append(build_result)

    if build_result.status != "PASS":
        print("\nBuild failed — skipping every step that depends on it "
              "(tests, G3 traceability, AOT publish).", file=sys.stderr)
        for name in ("Full test suite (Release)", "G3 — requirement traceability"):
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

    if skip_openspec:
        skipped = GateResult("G8 — OpenSpec strict validation")
        skipped.status = "SKIPPED"
        skipped.detail = "--skip-openspec"
        results.append(skipped)
    else:
        results.append(step_g8())

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
