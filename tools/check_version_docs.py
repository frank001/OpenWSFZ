#!/usr/bin/env python3
"""
check_version_docs.py — verify that the version cited in the docs matches the
canonical VERSION file.

Usage:
  python3 tools/check_version_docs.py

Takes no arguments: it reads VERSION, README.md, and REQUIREMENTS.md from the
repository root (resolved relative to this script's location, so it works from
any working directory). It extracts the version each document cites in its
"current release" anchor sentence and fails loudly if either disagrees with
VERSION.

This is the doc-drift half of CI gate G9 (see .github/workflows/ci.yml). It
follows the style of tools/check_native_version.py: clear stdout progress
lines, a specific actionable stderr message on failure, explicit exit codes.

Anchor sentence
  Both README.md and REQUIREMENTS.md state the version in a sentence matching
  `The current release is **v<VERSION>**.` (bold markers optional), e.g.
  `The current release is v0.30.`. The version is captured as MAJOR.MINOR with
  an optional PATCH component. If a document is reworded so this pattern no
  longer matches, the check fails closed (CI red) rather than silently passing
  — a deliberate design choice (design.md Risks/Trade-offs).

Exit codes
  0  all cited versions match VERSION
  1  a document disagrees with VERSION, or the anchor sentence is missing
  2  a required file is missing / usage error
"""
import os
import re
import sys

# Repo root is the parent of the tools/ directory this script lives in.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Documents that cite the version and the anchor sentence pattern they use.
DOCS = ("README.md", "REQUIREMENTS.md")

# `The current release is` optionally followed by `**`, a `v`, then the version.
ANCHOR_RE = re.compile(
    r"The current release is\s+\*{0,2}v(\d+\.\d+(?:\.\d+)?)\*{0,2}",
    re.IGNORECASE,
)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    version_path = os.path.join(REPO_ROOT, "VERSION")

    if not os.path.exists(version_path):
        print(f"MISSING: {version_path}", file=sys.stderr)
        print("The canonical VERSION file was not found at the repository root.",
              file=sys.stderr)
        return 2

    canonical = _read(version_path).strip()
    print(f"Canonical VERSION : {canonical}")

    if not canonical:
        print("ERROR: VERSION file is empty.", file=sys.stderr)
        return 2

    failures = []

    for doc in DOCS:
        doc_path = os.path.join(REPO_ROOT, doc)
        if not os.path.exists(doc_path):
            print(f"MISSING: {doc_path}", file=sys.stderr)
            failures.append((doc, None, "file not found"))
            continue

        match = ANCHOR_RE.search(_read(doc_path))
        if match is None:
            print(f"{doc:16}: ANCHOR NOT FOUND", file=sys.stderr)
            failures.append((doc, None, "anchor sentence not found"))
            continue

        cited = match.group(1)
        status = "OK" if cited == canonical else "MISMATCH"
        print(f"{doc:16}: {status} — cites v{cited}")
        if cited != canonical:
            failures.append((doc, cited, "version mismatch"))

    if not failures:
        print(f"Result : OK — all docs cite v{canonical}")
        return 0

    # Doc drift — fail loudly with actionable remediation.
    print("", file=sys.stderr)
    print("Result : DRIFT — the docs disagree with the canonical VERSION file.",
          file=sys.stderr)
    for doc, cited, reason in failures:
        if reason == "version mismatch":
            print(f"  - {doc} cites v{cited} but VERSION says {canonical}.",
                  file=sys.stderr)
        elif reason == "anchor sentence not found":
            print(f"  - {doc} no longer contains the anchor sentence "
                  f"'The current release is v<VERSION>.' — restore it (bold "
                  f"optional) so the version can be mechanically checked.",
                  file=sys.stderr)
        else:
            print(f"  - {doc}: {reason}.", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"Fix: edit the offending document(s) so the anchor sentence reads "
          f"'The current release is v{canonical}.', or, if VERSION itself is "
          f"wrong, correct VERSION (the single canonical source) instead.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
