#!/usr/bin/env python3
"""
cut_version_tag.py — cut (and push) an annotated git tag matching the
canonical VERSION file, if one does not already exist.

Usage:
  python3 tools/cut_version_tag.py [--dry-run]

This is the tag-automation leg of CI gate G9 (see .github/workflows/ci.yml,
job `tag-release-version`). It runs on every push to `main` (after gate G1
passes) and closes a gap the original gate G9 left as a manual step: VERSION
drifted from 0.30 to 0.31 in commit d36f711 (archiving
adopt-canonical-version-source itself), but no v0.31 tag was ever cut,
because tagging was a remembered-not-automated action (see design.md
Non-Goals in that change, and g9-automate-release-tagging's proposal.md for
how the gap was discovered).

Behaviour
  1. Read VERSION at the repository root, trim whitespace.
  2. Compute TAG = f"v{version}".
  3. If refs/tags/TAG already exists, do nothing and exit 0 — idempotent, so
     it is safe to run unconditionally on every push to main.
  4. Otherwise create an annotated tag TAG at HEAD and push it to origin.

--dry-run prints what would happen without creating or pushing anything.

Exit codes
  0  tag already present, or newly cut and pushed successfully (or would be,
     under --dry-run)
  1  git command failure (tag creation or push)
  2  usage / VERSION file missing or empty
"""
import argparse
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(args):
    """Run a git command from the repo root, returning (exit_code, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would happen without creating or pushing a tag",
    )
    args = parser.parse_args()

    version_path = os.path.join(REPO_ROOT, "VERSION")
    if not os.path.exists(version_path):
        print(f"MISSING: {version_path}", file=sys.stderr)
        print("The canonical VERSION file was not found at the repository root.",
              file=sys.stderr)
        return 2

    with open(version_path, "r", encoding="utf-8") as fh:
        version = fh.read().strip()

    if not version:
        print("ERROR: VERSION file is empty.", file=sys.stderr)
        return 2

    tag = f"v{version}"
    print(f"Canonical VERSION : {version}")
    print(f"Target tag        : {tag}")

    code, _, _ = _git(["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"])
    if code == 0:
        print(f"Result : OK — tag {tag} already exists; nothing to do.")
        return 0

    head_code, head_sha, head_err = _git(["rev-parse", "HEAD"])
    if head_code != 0:
        print(f"ERROR: git rev-parse HEAD failed: {head_err}", file=sys.stderr)
        return 1
    print(f"HEAD              : {head_sha}")

    if args.dry_run:
        print(f"Result : DRY RUN — would create and push annotated tag {tag} at {head_sha}.")
        return 0

    message = f"{tag} — cut automatically by CI gate G9 (release-versioning capability)."
    code, _, err = _git(["tag", "-a", tag, "-m", message])
    if code != 0:
        print(f"ERROR: git tag failed: {err}", file=sys.stderr)
        return 1

    code, _, err = _git(["push", "origin", f"refs/tags/{tag}"])
    if code != 0:
        print(f"ERROR: git push tag failed: {err}", file=sys.stderr)
        return 1

    print(f"Result : OK — created and pushed annotated tag {tag} at {head_sha}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
