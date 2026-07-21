#!/usr/bin/env python3
"""
check_test_delay_sync.py — Gate G10: test-delay-synchronization lint.

Flags a bare fixed-duration `Task.Delay(<numeric literal>)` in test code — the dominant root cause
of the CI flakiness documented in `openspec/changes/fix-flaky-test-delay-synchronization/` (N8 on
2026-07-18; PR #93/#94 on 2026-07-20; four confirmed flakes so far). A fixed delay used as a
synchronization barrier before an assertion passes reliably on an idle dev machine but is
timing-sensitive under real CI load — the correct pattern is polling the actual condition via the
shared `OpenWSFZ.TestSupport` library (`Poll.UntilAsync` and its typed wrappers), not guessing how
long an asynchronous effect takes to land.

This gate is blocking from the moment it lands (design.md Decision 4) — but it only blocks
REGRESSIONS, not the pre-existing migration backlog. It works exactly like Gate G3's
`traceability-debt.md` mechanism: every currently-known bare-delay site is enumerated up front in a
companion debt file (`test-delay-debt.md`, at the repo root alongside `traceability-debt.md`);
anything in that file passes; anything NOT in that file is a hard failure, including on files that
haven't been migrated yet, if a genuinely NEW instance is added to them.

Matching is by (file, matched call text) — e.g. a file recording `Task.Delay(150)` twice in its
debt-file entries tolerates up to two `Task.Delay(150)` sites anywhere in that file, regardless of
which line they're on. This tolerates ordinary line-number drift from unrelated edits touching the
same files between migration phases (the same tolerance `traceability-debt.md` already gives G3),
while still catching a genuinely new bare-delay site: if a file's actual count of some exact
`Task.Delay(N...)` text exceeds how many the debt file records for that (file, text) pair, the
excess occurrence(s) are untracked and fail the gate.

Excluded from scanning entirely: `tests/OpenWSFZ.TestSupport/**` — the shared polling library's own
implementation, the one place a literal delay (the poll interval inside `Poll.UntilAsync`'s loop) is
the correct implementation detail rather than a per-test synchronization shortcut (design.md
Decision 1/2). Note this does NOT exclude `tests/OpenWSFZ.TestSupport.Tests/**` — `Poll`'s own
deterministic tests (design.md Decision 3) legitimately contain a few small literal delays too, but
by construction, not by folder-wide exemption, so they are tracked in the debt file like any other
explicitly-justified exception (see that file's own header).

Usage:
  python3 tools/check_test_delay_sync.py [--debt-file PATH] [--list]

  --debt-file PATH   Path to the debt file (default: test-delay-debt.md at the repo root,
                     alongside traceability-debt.md — see DEFAULT_DEBT_FILE below).
  --list             Print every currently-matching (file, line, text) site and exit 0, without
                     comparing against the debt file. Used to (re-)generate the debt file's
                     contents — not part of the gate's normal pass/fail run.

Exit codes
  0  every current bare-delay site is accounted for by the debt file (or --list was passed)
  1  at least one untracked bare-delay site was found
  2  usage / environment error (e.g. debt file not found)
"""
import glob
import os
import re
import sys
from collections import Counter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DEBT_FILE = os.path.join(REPO_ROOT, "test-delay-debt.md")

# Matches a bare fixed-duration delay call whose argument list starts with a numeric literal, in
# any of four equivalent shapes:
#   1. Task.Delay(150), Task.Delay(10, feedCts.Token) — a plain literal millisecond count.
#   2. Task.Delay(TimeSpan.FromSeconds(1)) — the same fixed-duration guess spelled via a TimeSpan
#      factory. Originally missed entirely (2026-07-21 G10 audit found two live, untracked sites in
#      ConsoleDetacherTests.cs): the outer call doesn't start with a digit, so pattern 1 alone never
#      matched it, and it silently passed the gate as if it didn't exist. The TimeSpan factory's own
#      argument must itself start with a digit — Task.Delay(TimeSpan.FromMilliseconds(interval)) is
#      deliberately NOT matched, same as Task.Delay(interval) isn't under pattern 1: a
#      variable/parameter is already the correct post-migration shape, not a literal guess.
#   3. Thread.Sleep(500) — the synchronous-code equivalent anti-pattern. No live sites existed at
#      audit time, but nothing stops a future test from introducing one; covered pre-emptively
#      rather than waiting for a second embarrassment like pattern 2's.
#   4. Thread.Sleep(TimeSpan.FromSeconds(1)) — pattern 3's TimeSpan-wrapped twin, added in the same
#      pass as pattern 2 (2026-07-21 review) rather than left as a residual blind spot: Thread.Sleep
#      has the identical TimeSpan-accepting overload Task.Delay does, so closing pattern 2 without
#      also closing this one would just be pattern 2's original gap recreated on the sync-code side.
#      No live sites exist for this shape either, same pre-emptive rationale as pattern 3.
# Each alternative tolerates one level of nested parens within its argument list (e.g. a cast like
# Task.Delay(100, (CancellationToken)c.Args()[0])) without needing a full balanced-paren parser.
DELAY_RE = re.compile(
    r"Task\.Delay\(\s*\d(?:[^()]|\([^()]*\))*\)"
    r"|Task\.Delay\(\s*TimeSpan\.From\w+\(\s*\d(?:[^()]|\([^()]*\))*\)(?:[^()]|\([^()]*\))*\)"
    r"|Thread\.Sleep\(\s*\d(?:[^()]|\([^()]*\))*\)"
    r"|Thread\.Sleep\(\s*TimeSpan\.From\w+\(\s*\d(?:[^()]|\([^()]*\))*\)(?:[^()]|\([^()]*\))*\)"
)

# The shared library's own implementation — the one legitimate place a literal poll-interval delay
# lives (design.md Decision 1/2). Deliberately NOT tests/OpenWSFZ.TestSupport.Tests/** — see module
# docstring.
_EXCLUDED_PREFIX = os.path.join(REPO_ROOT, "tests", "OpenWSFZ.TestSupport") + os.sep


def _default_paths():
    all_cs = glob.glob(os.path.join(REPO_ROOT, "tests", "**", "*.cs"), recursive=True)
    return sorted(p for p in all_cs if not p.startswith(_EXCLUDED_PREFIX))


def _relpath(path):
    return os.path.relpath(path, REPO_ROOT).replace("\\", "/")


def scan_file(path):
    """Returns a list of (line_number, matched_text) for every bare-delay site in the file."""
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    results = []
    for idx, line in enumerate(lines):
        for m in DELAY_RE.finditer(line):
            results.append((idx + 1, m.group(0)))
    return results


def scan_repo(paths):
    """Returns {relpath: [(line, text), ...]} for every scanned file with at least one match."""
    found = {}
    for path in paths:
        sites = scan_file(path)
        if sites:
            found[_relpath(path)] = sites
    return found


_DEBT_LINE_RE = re.compile(r"^(?P<path>[^:#\s][^:]*):(?P<line>\d+):\s*(?P<text>.+?)\s*$")


def parse_debt_file(debt_path):
    """Parses the debt file, returning {relpath: Counter(matched_text -> count)}.

    Ignores blank lines and markdown heading/comment lines (matching traceability-debt.md's own
    convention) — only lines of the exact form `path:line: matched-text` are counted as debt
    entries. Line numbers are recorded for human readability only; matching (see main()) is by
    (path, matched-text) count, not by line number, so ordinary line drift between phases doesn't
    invalidate an entry.
    """
    debt = {}
    with open(debt_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            m = _DEBT_LINE_RE.match(stripped)
            if not m:
                continue
            debt.setdefault(m.group("path"), Counter())[m.group("text")] += 1
    return debt


def find_untracked(found, debt):
    """Returns a list of human-readable violation strings for occurrences of a (file, text) pair
    beyond how many the debt file records for that exact pair."""
    violations = []
    for relpath, sites in found.items():
        actual_counts = Counter(text for _line, text in sites)
        debt_counts = debt.get(relpath, Counter())
        for text, actual_count in actual_counts.items():
            tracked = debt_counts.get(text, 0)
            excess = actual_count - tracked
            if excess <= 0:
                continue
            # Report the excess occurrence(s) by their actual line numbers, picking the ones not
            # "consumed" by tracked entries — since entries are fungible by text, just report the
            # last `excess` matching lines found (deterministic given scan_file's line order).
            matching_lines = [line for line, t in sites if t == text]
            for line in matching_lines[-excess:]:
                violations.append(
                    f"{relpath}:{line}: {text}  (untracked — {actual_count} occurrence(s) of this "
                    f"exact text found in this file, only {tracked} listed in "
                    f"{_relpath(DEFAULT_DEBT_FILE)})")
    return sorted(violations)


def main():
    args = sys.argv[1:]
    debt_file = DEFAULT_DEBT_FILE
    list_only = "--list" in args
    if "--debt-file" in args:
        idx = args.index("--debt-file")
        debt_file = args[idx + 1]

    paths = _default_paths()
    if not paths:
        print("No tests/**/*.cs files found to scan (outside tests/OpenWSFZ.TestSupport/).",
              file=sys.stderr)
        return 2

    found = scan_repo(paths)

    if list_only:
        total = 0
        for relpath in sorted(found):
            for line, text in found[relpath]:
                print(f"{relpath}:{line}: {text}")
                total += 1
        print(f"\n{total} bare-delay site(s) found across {len(found)} file(s).", file=sys.stderr)
        return 0

    if not os.path.exists(debt_file):
        print(f"error: debt file not found: {debt_file}", file=sys.stderr)
        return 2

    debt = parse_debt_file(debt_file)
    violations = find_untracked(found, debt)

    total_sites = sum(len(sites) for sites in found.values())
    print(f"Scanned {len(paths)} file(s) under tests/ (excluding tests/OpenWSFZ.TestSupport/); "
          f"{total_sites} bare-delay site(s) found across {len(found)} file(s).")

    for v in violations:
        print(f"VIOLATION: {v}", file=sys.stderr)

    if violations:
        print(f"\nResult : {len(violations)} untracked bare-delay site(s). Replace with a shared "
              f"OpenWSFZ.TestSupport polling helper, or if this is a reviewed, justified exception, "
              f"add it to {_relpath(debt_file)} (design.md Decision 4).", file=sys.stderr)
        return 1

    print("\nResult : OK — every bare-delay site is either migrated or explicitly tracked as debt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
