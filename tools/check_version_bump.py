#!/usr/bin/env python3
"""
check_version_bump.py — enforce the "one user-facing feature = one minor bump"
rule at merge time.

Usage:
  python3 tools/check_version_bump.py <base_ref>

  <base_ref>  the ref to diff against, e.g. origin/main (in CI, pass
              origin/${{ github.base_ref }}).

This is the mandatory-bump half of CI gate G9 (see .github/workflows/ci.yml).
It inspects the pull request's diff against <base_ref> and enforces:

  1. Every proposal.md newly added under openspec/changes/archive/ by this PR
     SHALL declare `**User-facing:**` as exactly `yes` or `no`. Missing or
     malformed → fail.
  2. If any such newly-archived proposal declares `yes`, VERSION SHALL differ
     from its content on <base_ref>. Unchanged → fail.

Only files the PR itself *adds* under the archive path are inspected (git diff
--diff-filter=A), so history archived before gate G9 existed is never
retroactively checked (design.md Non-Goals).

Follows the style of tools/check_native_version.py: clear stdout progress
lines, a specific actionable stderr message on failure, explicit exit codes.

Exit codes
  0  compliant (no user-facing archive, or user-facing archive + VERSION bump)
  1  a rule was violated (missing/malformed declaration, or missing bump)
  2  usage / git error
"""
import re
import subprocess
import sys

# Matches the declaration line, capturing the yes/no value.
# Tolerant of surrounding whitespace and case; strict about the value.
DECL_RE = re.compile(r"\*\*User-facing:\*\*\s*(\w+)", re.IGNORECASE)

# How many leading lines of a proposal to scan for the declaration. The
# convention is "before the ## Why heading" (i.e. the very top), but we search
# a small window rather than pinning an exact line number so a blank line or a
# stray comment above it doesn't break the check.
SCAN_LINES = 15


def _git(args, base_ref=None):
    """Run a git command, returning (exit_code, stdout). Raises on git error."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _added_proposals(base_ref):
    """List proposal.md paths newly added under the archive dir in this diff."""
    code, out, err = _git([
        "diff", "--name-only", "--diff-filter=A",
        f"{base_ref}...HEAD",
        "--", "openspec/changes/archive/**/proposal.md",
    ])
    if code != 0:
        print(f"ERROR: git diff failed: {err.strip()}", file=sys.stderr)
        sys.exit(2)
    return [line for line in out.splitlines() if line.strip()]


def _file_at_head(path):
    code, out, _ = _git(["show", f"HEAD:{path}"])
    return out if code == 0 else ""


def _version_changed(base_ref):
    """True if VERSION differs between <base_ref> and HEAD."""
    # --quiet exits 1 when there IS a difference, 0 when there is none.
    code, _, err = _git([
        "diff", "--quiet", f"{base_ref}...HEAD", "--", "VERSION",
    ])
    if code not in (0, 1):
        print(f"ERROR: git diff VERSION failed: {err.strip()}", file=sys.stderr)
        sys.exit(2)
    return code == 1


def _declaration(text):
    """Return 'yes', 'no', or None (missing/malformed) from a proposal body."""
    head = "\n".join(text.splitlines()[:SCAN_LINES])
    match = DECL_RE.search(head)
    if match is None:
        return None
    value = match.group(1).lower()
    return value if value in ("yes", "no") else None


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <base_ref>", file=sys.stderr)
        return 2

    base_ref = sys.argv[1]
    print(f"Base ref : {base_ref}")

    proposals = _added_proposals(base_ref)
    if not proposals:
        print("Result : OK — this PR archives no new OpenSpec changes; "
              "no version bump required.")
        return 0

    print(f"Newly-archived proposals ({len(proposals)}):")

    malformed = []   # proposals missing/with a bad declaration
    user_facing = []  # proposals declaring yes

    for path in proposals:
        decl = _declaration(_file_at_head(path))
        if decl is None:
            print(f"  - {path}: MISSING/MALFORMED **User-facing:** line",
                  file=sys.stderr)
            malformed.append(path)
        else:
            print(f"  - {path}: User-facing = {decl}")
            if decl == "yes":
                user_facing.append(path)

    if malformed:
        print("", file=sys.stderr)
        print("Result : FAIL — a newly-archived proposal is missing a valid "
              "user-facing declaration.", file=sys.stderr)
        print("Every proposal.md SHALL declare, before its `## Why` heading, "
              "exactly one of:", file=sys.stderr)
        print("    **User-facing:** yes", file=sys.stderr)
        print("    **User-facing:** no", file=sys.stderr)
        print("Add (or correct) that line in the offending file(s) above.",
              file=sys.stderr)
        return 1

    if not user_facing:
        print("Result : OK — all newly-archived changes declare "
              "User-facing = no; no version bump required.")
        return 0

    print(f"User-facing changes archived: {len(user_facing)}")
    if _version_changed(base_ref):
        print(f"VERSION differs from {base_ref} — bump present.")
        print("Result : OK — user-facing change(s) archived with a VERSION "
              "bump.")
        return 0

    # User-facing archive with no bump — the exact failure mode issue #49 exists
    # to prevent.
    print("", file=sys.stderr)
    print("Result : FAIL — a user-facing OpenSpec change is being archived "
          "without a VERSION bump.", file=sys.stderr)
    print("The following newly-archived change(s) declare **User-facing:** yes:",
          file=sys.stderr)
    for path in user_facing:
        print(f"  - {path}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Per the minor-version-per-user-facing-feature rule, bump the root "
          "VERSION file (increment the minor component) in this PR before "
          "merging. If none of these changes is actually operator-visible, "
          "correct its **User-facing:** declaration to `no` instead.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
