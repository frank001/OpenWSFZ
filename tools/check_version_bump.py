#!/usr/bin/env python3
"""
check_version_bump.py — enforce the "one user-facing feature = one minor bump"
rule at the point a change's proposal FIRST enters `main`'s history — i.e.
pre-merge, not deferred to a later archiving pull request.

Usage:
  python3 tools/check_version_bump.py <base_ref>

  <base_ref>  the ref to diff against, e.g. origin/main (in CI, pass
              origin/${{ github.base_ref }}).

This is the mandatory-bump half of CI gate G9 (see .github/workflows/ci.yml).
It inspects the pull request's diff against <base_ref> and enforces:

  1. Every `proposal.md` newly added anywhere under `openspec/changes/` by this
     PR — whether at the active `openspec/changes/<name>/` path or directly
     under `openspec/changes/archive/<date>-<name>/` — SHALL declare
     `**User-facing:**` as exactly `yes` or `no`. Missing or malformed → fail.
  2. If any such newly-introduced proposal declares `yes`, VERSION SHALL
     differ from its content on <base_ref>.

Corrected 2026-07-18 (see openspec/changes/fix-version-bump-gate-timing):
previously this script only looked under `openspec/changes/archive/`, which
meant the bump was enforced at archive time. In practice this project almost
always merges a fully (or partially) implemented change and archives it in a
*separate*, later pull request — so the archive-only check let a user-facing
feature merge to `main` with no VERSION bump for days, only caught whenever
someone got around to archiving it. The Captain's directive: the bump is only
acceptable pre-merge. This version checks BOTH the active and archived path
for a *first-time introduction* of a given change's proposal.md, and
explicitly exempts a later pull request that merely relocates an
already-introduced change from the active path to the archive path (ordinary
archiving) — that change was already checked when it first appeared, and
re-checking it here would spuriously demand a second bump for one feature.

Follows the style of tools/check_native_version.py: clear stdout progress
lines, a specific actionable stderr message on failure, explicit exit codes.

Exit codes
  0  compliant (no newly-introduced user-facing proposal, or one + a VERSION bump)
  1  a rule was violated (missing/malformed declaration, or missing bump)
  2  usage / git error
"""
import os
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

# openspec/changes/<name>/proposal.md — the active (not-yet-archived) path.
ACTIVE_RE = re.compile(r"^openspec/changes/(?!archive/)([^/]+)/proposal\.md$")

# openspec/changes/archive/<date>-<name>/proposal.md — the archived path.
# The archived directory name is conventionally "<YYYY-MM-DD>-<change-name>";
# strip that date prefix to recover the bare change name for comparison
# against an active-path directory name.
ARCHIVE_RE = re.compile(r"^openspec/changes/archive/([^/]+)/proposal\.md$")
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")


def _git(args):
    """Run a git command, returning (exit_code, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _added_proposal_paths(base_ref):
    """List every proposal.md path newly added anywhere under openspec/changes/
    in this diff (active or archived)."""
    code, out, err = _git([
        "diff", "--name-only", "--diff-filter=A",
        f"{base_ref}...HEAD",
        "--", "openspec/changes/**/proposal.md",
    ])
    if code != 0:
        print(f"ERROR: git diff failed: {err.strip()}", file=sys.stderr)
        sys.exit(2)
    return [line for line in out.splitlines() if line.strip()]


def _file_at_ref(ref, path):
    code, out, _ = _git(["show", f"{ref}:{path}"])
    return out if code == 0 else None


def _file_at_head(path):
    return _file_at_ref("HEAD", path) or ""


def _change_name(path):
    """Return the derived change name for a newly-added proposal.md path, or
    None if the path doesn't match either the active or archived shape."""
    m = ACTIVE_RE.match(path)
    if m:
        return m.group(1)
    m = ARCHIVE_RE.match(path)
    if m:
        archived_dir = m.group(1)
        date_m = DATE_PREFIX_RE.match(archived_dir)
        return date_m.group(1) if date_m else archived_dir
    return None


def _already_introduced_at_base(name, base_ref):
    """True if openspec/changes/<name>/proposal.md already existed at
    base_ref — i.e. this change was already on main at the active path before
    this PR, so an archive-path addition here is a pure relocation."""
    return _file_at_ref(base_ref, f"openspec/changes/{name}/proposal.md") is not None


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

    added_paths = _added_proposal_paths(base_ref)
    if not added_paths:
        print("Result : OK — this PR introduces no new OpenSpec change proposals; "
              "no version bump required.")
        return 0

    # Filter out archive-path additions that are really just a relocation of a
    # change already introduced (at the active path) before this PR.
    checked = []  # (path, name)
    skipped_relocations = []
    for path in added_paths:
        name = _change_name(path)
        if name is None:
            # Not a recognised proposal.md shape — ignore defensively rather
            # than crash on an unexpected path.
            continue
        if ARCHIVE_RE.match(path) and _already_introduced_at_base(name, base_ref):
            skipped_relocations.append(path)
            continue
        checked.append((path, name))

    for path in skipped_relocations:
        print(f"  (skip) {path}: already introduced at the active path before "
              f"this PR — ordinary archiving relocation, not re-checked")

    if not checked:
        print("Result : OK — every newly-added proposal.md in this PR is an "
              "ordinary archiving relocation of an already-introduced change; "
              "no version bump required.")
        return 0

    print(f"Newly-introduced proposals ({len(checked)}):")

    malformed = []    # proposals missing/with a bad declaration
    user_facing = []  # proposals declaring yes

    for path, name in checked:
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
        print("Result : FAIL — a newly-introduced proposal is missing a valid "
              "user-facing declaration.", file=sys.stderr)
        print("Every proposal.md SHALL declare, before its `## Why` heading, "
              "exactly one of:", file=sys.stderr)
        print("    **User-facing:** yes", file=sys.stderr)
        print("    **User-facing:** no", file=sys.stderr)
        print("Add (or correct) that line in the offending file(s) above.",
              file=sys.stderr)
        return 1

    if not user_facing:
        print("Result : OK — all newly-introduced changes declare "
              "User-facing = no; no version bump required.")
        return 0

    print(f"User-facing changes newly introduced: {len(user_facing)}")
    if _version_changed(base_ref):
        print(f"VERSION differs from {base_ref} — bump present.")
        print("Result : OK — user-facing change(s) introduced with a VERSION "
              "bump in this same pull request.")
        return 0

    # User-facing change merged with no bump — the exact failure mode this
    # gate exists to prevent (originally issue #49; timing corrected by
    # fix-version-bump-gate-timing so it fires pre-merge, not at archive).
    print("", file=sys.stderr)
    print("Result : FAIL — a user-facing OpenSpec change is being merged to "
          "main without a VERSION bump.", file=sys.stderr)
    print("The following newly-introduced change(s) declare **User-facing:** yes:",
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
