#!/usr/bin/env python3
"""
check_udp_capture_margin.py — flag ReceiveAllAsync(...) calls that assert a
specific WSJT-X datagram type is present without a documented capture margin.

Usage:
  python3 tools/check_udp_capture_margin.py [path ...]

  With no arguments, scans every tests/**/*.cs in the repository. With
  explicit paths, scans only those.

Background: PR #90 (fix-external-reporting-clear-and-reply-filter) added a
Clear datagram send ahead of Close in ExternalReportingService.StopAsync.
The pre-existing test StopAsync_SendsCloseDatagram captured a fixed window
of 3 datagrams (the old maximum: an optional racing Heartbeat+Status burst
plus one Close) and asserted Close was present in that window. With Clear
now also in the mix, up to 4 datagrams can arrive — and on a slower or
differently-scheduled test runner, the 3-slot capture filled up before
Close arrived, silently dropping it and failing the assertion. This passed
every local run on the developer's machine and all three OSes on the PR's
own required checks, then failed on ubuntu-latest's push-triggered CI run
against `main` (see PR #91's fix — bumping the capture count to 4).

The defect class, not just this one instance: a `ReceiveAllAsync(listener,
N, timeout)` call whose result is later asserted to `.Contain(WsjtxDatagram.
MessageType.X)` is asserting presence of a SPECIFIC datagram type within a
capture window shared with other, unasserted "noise" datagrams (Heartbeat,
Status, Clear, ...) sent by the same code path. If N is set to exactly the
minimum ever observed rather than a value with deliberate headroom above
it, any future change that makes the code path send one more datagram type
before the asserted one (exactly what PR #90 did) can silently truncate the
capture and turn a correct implementation into a flaky test failure — often
one that never reproduces locally, because the race depends on CPU
contention/scheduling delay a quiet local machine rarely hits (confirmed:
stress-tested the pre-fix code 64 times under WSL Debian, including full
solution-wide runs matching CI's own invocation, and never reproduced it
locally — see the QA review that added this script).

This lint does not (and cannot, from static text alone) verify a capture
count is actually sufficient — it can only verify that whoever chose the
number left a `margin:`-tagged comment explaining the headroom, so a future
reader/reviewer changing the same code path is prompted to reconsider it
rather than silently invalidating an assumption baked into a bare integer
literal. It is deliberately narrow in scope: it flags exactly the
`ReceiveAllAsync(...)` → `.Should().Contain(WsjtxDatagram.MessageType.X)`
shape (the exact pattern of the incident above), not every possible
assertion shape over a captured datagram list (e.g. `.Should().HaveCount(`
after a `.Where(...)` filter is not covered) — matching this project's
existing "best-effort heuristic lint augmenting human review, not a
perfect parser" convention (see check_screenshot_task_order.py).

Fix for a flagged violation: add a comment within BACKWARD_WINDOW lines
above the ReceiveAllAsync(...) call (or trailing on the same line)
containing the word "margin", explaining what the requested count allows
for beyond the minimum needed. See any passing example in
tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs for the
established phrasing.

Exit codes
  0  no ReceiveAllAsync(...) → Contain(MessageType.X) call sites found, or
     every one found has a nearby margin comment
  1  at least one such call site has no nearby margin comment
  2  usage / no files found to scan
"""
import glob
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CALL_RE = re.compile(
    r"var\s+(?P<var>\w+)\s*=\s*await\s+ReceiveAllAsync\(\s*\w+\s*,\s*(?P<count>\d+)\s*,")

# How many lines forward from the call to look for a "Contain(WsjtxDatagram.
# MessageType.X)" assertion referencing the same variable, and how many
# lines back (from the call line, inclusive) to look for a margin comment.
FORWARD_WINDOW = 12
BACKWARD_WINDOW = 6

MARGIN_RE = re.compile(r"margin", re.IGNORECASE)


def _default_paths():
    return sorted(glob.glob(os.path.join(REPO_ROOT, "tests", "**", "*.cs"), recursive=True))


def _asserts_specific_type(lines, start_idx, varname):
    """Whether lines[start_idx+1 : start_idx+1+FORWARD_WINDOW] contains a
    `<varname>....Should().Contain(WsjtxDatagram.MessageType.X)` assertion.
    Matches on the exact variable name (word-boundary), so two back-to-back
    calls (e.g. recv1/recv2 declared next to each other before either's own
    assertions appear) don't need any "stop at the next call" heuristic —
    recv1's regex simply never matches a line that only mentions recv2."""
    var_contain_re = re.compile(
        rf"\b{re.escape(varname)}\b.*\.Should\(\)\.Contain\(WsjtxDatagram\.MessageType\.")
    end = min(len(lines), start_idx + 1 + FORWARD_WINDOW)
    for i in range(start_idx + 1, end):
        if var_contain_re.search(lines[i]):
            return True
    return False


def _has_margin_comment(lines, call_idx):
    """Whether a 'margin' comment appears on the call's own line or within
    BACKWARD_WINDOW lines immediately above it."""
    start = max(0, call_idx - BACKWARD_WINDOW)
    for i in range(start, call_idx + 1):
        if MARGIN_RE.search(lines[i]):
            return True
    return False


def check_file(path):
    """Returns a list of human-readable violation strings."""
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    violations = []
    for idx, line in enumerate(lines):
        match = CALL_RE.search(line)
        if not match:
            continue
        varname = match.group("var")
        count = match.group("count")
        if not _asserts_specific_type(lines, idx, varname):
            continue  # not asserting presence of a specific datagram type — out of scope
        if _has_margin_comment(lines, idx):
            continue
        violations.append(
            f"{path}:{idx + 1}: ReceiveAllAsync(..., {count}, ...) assigned to '{varname}' "
            f"asserts a specific WsjtxDatagram.MessageType is present in the capture, "
            f"but no 'margin' comment within {BACKWARD_WINDOW} lines above explains why "
            f"{count} was chosen — see this script's module docstring for the incident "
            f"this rule exists to catch (PR #90/#91).")
    return violations


def main():
    paths = sys.argv[1:] or _default_paths()
    if not paths:
        print("No tests/**/*.cs files found to scan.", file=sys.stderr)
        return 2

    all_violations = []
    for path in paths:
        if not os.path.exists(path):
            print(f"MISSING: {path}", file=sys.stderr)
            return 2
        all_violations += check_file(path)

    print(f"Scanned {len(paths)} file(s).")

    for v in all_violations:
        print(f"VIOLATION: {v}", file=sys.stderr)

    if all_violations:
        print(f"\nResult : {len(all_violations)} violation(s) — add a 'margin:' comment "
              f"explaining the chosen capture count before finalising.", file=sys.stderr)
        return 1

    print("\nResult : OK — every capture asserting a specific datagram type documents its margin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
