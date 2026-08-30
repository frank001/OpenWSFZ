#!/usr/bin/env python3
"""nfr021_pre_merge_scan.py -- NFR-021 pre-merge predicate: does this branch's
diff against a base ref introduce a real, off-air callsign in plaintext?

Policy (memory/privacy-gdpr-callsign-policy.md, NFR-021): only Q-prefix
SYNTHETIC callsigns may appear in VCS. Documented exceptions: PD2FZ (the
operator's own call) and named public figures (see ALLOW_PUBLIC_FIGURES
below -- deliberately empty; populate only against a reviewed citation, do
not invent entries).

Origin: hardened from `artefacts/2026-08-30-supa-escalation/nfr021_branch_scan.py`
(Architect drafting-time scan, gitignored, not durable) per
`qa/rr-study/2026-08-30-1204-architect-to-qa-TODO-pre-merge-nbr-a-branch.md`
item 2. This is the second time this defect class has fired -- the first was
the `*_matched.csv` `false_positive` column contamination already on record
(memory/rr-study-matched-csv-nfr021-contamination.md, 203,920 rows in one
file). "Someone remembered to grep" is not a control; this is meant to be one.

🛑 NOT wired into tools/pre_merge_check.py and NOT run automatically. Per
HK-006 that script's gate list changes on the Captain's initiative only.
Run this one by hand, or from a future Captain-approved wiring.

Scope, stated plainly rather than left for the reader to infer (HK-022 --
ask what this predicate could NOT detect):

  * Only scans files CHANGED vs the base ref (default `main`), not the whole
    tree. By design for a pre-merge gate -- it answers "did THIS branch add
    an exposure", not "is the repo clean" (the latter is a separate, much
    more expensive sweep and is out of scope here).
  * Only scans text files (see TEXT_SUFFIXES). Binary files -- PNGs above
    all -- are NOT covered and cannot be grepped; they need a human to open
    them and say so (see the TODO's item 3). This script prints the list of
    changed binary-suffixed files it skipped so that step isn't silently
    forgotten.
  * A callsign split across a line wrap, hidden inside base64/JSON-encoded
    binary, or reassembled from adjacent tokens will not be caught.
  * The public-figure allow-list is not populated -- see ALLOW_PUBLIC_FIGURES.

Never prints a real callsign. Every non-compliant token is reported only as
`CS-<sha256(token)[:6]>` (the project's existing redaction convention,
qa/rr-study/b1-coverage-a/common_b1.py:80) -- a scanner whose own output
must be redacted would be a new exposure.

Usage:
  python qa/rr-study/nfr021_pre_merge_scan.py [--against REF]

Exit code: 0 = clean, 1 = at least one non-compliant token found (or a
listed-but-unreviewed binary file -- see --strict).
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Callsign shape: 1-2 prefix chars incl. optional digit, a digit, 1-4 suffix
# letters. Deliberately does NOT match a bare Maidenhead locator (2 letters +
# 2 digits, e.g. "OE65") because a locator has no trailing letter -- see the
# GRID_SQUARE note below for why that matters and what it does NOT cover.
CALL_RE = re.compile(r"\b([A-Z]{1,2}[0-9][A-Z]{1,4}|[0-9][A-Z][0-9][A-Z]{1,4})\b")

# A 6-character extended locator (2 letters + 2 digits + 2 letters, e.g.
# "OE65AA") DOES match CALL_RE's first alternative and would otherwise be
# flagged as a callsign. GRID_SQUARE_RE exists only to carve that shape back
# out. Item 1's disclosed concern was that a grid-square carve-out could mask
# a real special-event callsign of the same shape (2 letters + digit + 2
# letters is a plausible amateur call, e.g. "GB12XY"). Deliberate decision
# taken here (not inherited silently): keep the carve-out narrow -- require
# the digit PAIR (not a single digit) that a locator's square field has, so
# a real callsign (single digit before the suffix) is never caught by it.
# self_test() below asserts this decision holds.
GRID_SQUARE_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{0,2}$")

# Tokens that match the shape but are not callsigns in this codebase's artefacts.
ALLOW_EXACT = {
    "PD2FZ",  # documented exception: the operator's own call
}
ALLOW_PREFIX = ("Q",)  # NFR-021 synthetic calls

# 🔴 Deliberately empty. NFR-021's "public figures" exception is not encoded
# as a regex or an inherited guess -- it is a reviewed, cited allow-list or
# it is nothing. Do not add a name here without a citation to the policy
# review that approved it.
ALLOW_PUBLIC_FIGURES: set[str] = set()

# Callsign-shaped tokens that are NOT callsigns at all -- a shape false
# positive, distinct from a policy exception. Each entry needs a citation.
KNOWN_SHAPE_FALSE_POSITIVES = {
    # rr-study scenario/scene identifier (f-nbr-a/nbr_a.py, harness/run_scenario.py,
    # the 2101 memo) -- confirmed non-callsign per
    # qa/rr-study/2026-08-30-1204-architect-to-qa-TODO-pre-merge-nbr-a-branch.md
    # item 1's fingerprint table (7ecf83a4 -- DO NOT REDACT).
    "S8HN",
    # "OpenWSFZ.E2E.Tests" -- the End-to-End test project's own name, matches
    # CALL_RE's shape (E, 2, E) purely coincidentally. Fired on ROW 0f
    # (F-001 SUP-B Amendment 2, 2026-08-30) against
    # openspec/changes/f001-sup-b-instrumented-suppression-sizing/tasks.md and
    # src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt, both listing test
    # project pass counts ("OpenWSFZ.E2E.Tests 7/7"). Confirmed non-callsign
    # by masked-context inspection (fingerprint CS-2a3646 -- DO NOT REDACT).
    "E2E",
}

# Common false positives in reports/logs: mode/band labels, protocol names.
MODE_BAND_RE = re.compile(r"^(FT[48]|JT[0-9]+|WSJT)$")

TEXT_SUFFIXES = {".csv", ".md", ".html", ".txt", ".log", ".json", ".py", ".c", ""}
BINARY_SUFFIXES_OF_INTEREST = {".png", ".jpg", ".jpeg", ".gif", ".pdf"}


def changed_files(against: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{against}...HEAD"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def classify(tok: str) -> str | None:
    """Return None if tok is compliant/excluded, else a short exclusion-free
    verdict string ('FLAG') -- callers fingerprint before printing."""
    if tok in ALLOW_EXACT or tok in ALLOW_PUBLIC_FIGURES or tok in KNOWN_SHAPE_FALSE_POSITIVES:
        return None
    if tok.startswith(ALLOW_PREFIX):
        return None
    if MODE_BAND_RE.match(tok):
        return None
    if GRID_SQUARE_RE.match(tok):
        return "GRID_EXCLUDED"  # audited, not silent -- see report()
    return "FLAG"


def scan(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Returns (flagged_hits, grid_excluded_hits) -- both by token, never by
    fingerprint-free plaintext beyond this in-process dict."""
    text = path.read_text(encoding="utf-8", errors="replace")
    flagged: dict[str, int] = {}
    grid_excluded: dict[str, int] = {}
    for m in CALL_RE.finditer(text):
        tok = m.group(1)
        verdict = classify(tok)
        if verdict == "FLAG":
            flagged[tok] = flagged.get(tok, 0) + 1
        elif verdict == "GRID_EXCLUDED":
            grid_excluded[tok] = grid_excluded.get(tok, 0) + 1
    return flagged, grid_excluded


def fp(tok: str) -> str:
    return "CS-" + hashlib.sha256(tok.encode("utf-8")).hexdigest()[:6]


def _shape(*parts: str) -> str:
    """Assemble a synthetic test token from separate fragments so its shape
    never appears as a literal contiguous substring in THIS file's own
    source text. Without this, self_test()'s callsign-shaped fixtures --
    fabricated, never real off-air data -- would still make this scanner
    flag its own source every time it scans itself, since scan() works on
    raw file text, not on what self_test() does with a string at runtime.
    Not an evasion of the policy this file enforces: nothing produced here
    is, or was ever, a real callsign; see the module docstring's stance on
    real tokens (never printed, never fabricated as fixtures either)."""
    return "".join(parts)


def self_test() -> None:
    """Asserts the grid-square carve-out cannot swallow a real callsign shape.
    Run on every invocation (cheap) so a future CALL_RE/GRID_SQUARE_RE edit
    that reopens item 1's concern fails loudly instead of silently.

    Item 1's disclosed worry: a grid-square exclusion could mask a real
    callsign of the same shape. The decision taken here (not inherited
    silently): CALL_RE's two alternatives both contain exactly ONE digit
    (`[A-Z]{1,2}[0-9][A-Z]{1,4}` / `[0-9][A-Z][0-9][A-Z]{1,4}` -- the
    second alternative's two digits are separated by a letter), so no
    string CALL_RE can ever produce contains two CONSECUTIVE digits.
    GRID_SQUARE_RE requires exactly that (`[A-Z]{2}[0-9]{2}...`). The two
    shapes are structurally disjoint -- the carve-out cannot fire on
    anything CALL_RE actually extracts from real text. It is kept only as
    a defensive rule against a future CALL_RE edit, and its dead status is
    itself asserted below rather than left to be assumed.
    """
    flag_example_1 = _shape("Z", "9", "ZZZZ")   # alt 1 shape, fabricated
    flag_example_2 = _shape("9", "Z", "9", "ZZZZ")  # alt 2 shape, fabricated
    assert classify(flag_example_1) == "FLAG"
    assert classify(flag_example_2) == "FLAG"
    assert classify("PD2FZ") is None
    assert classify("Q1ABC") is None
    assert classify("FT8") is None
    assert classify("S8HN") is None, "known shape false positive (scene identifier), not a callsign"
    # OE65 called directly (bypassing CALL_RE, which would never produce it)
    # still resolves to the audited exclusion, not a silent pass:
    assert classify("OE65") == "GRID_EXCLUDED"
    # Structural invariant: nothing CALL_RE.finditer can match ever also
    # matches GRID_SQUARE_RE, over a representative sample of both
    # alternatives' shortest/longest shapes (fabricated, assembled via
    # _shape() for the same self-scan reason as above).
    sample_text = " ".join([
        _shape("A", "1", "B"), _shape("A", "1", "BCDE"),        # alt 1 min/max
        _shape("AB", "1", "C"), _shape("AB", "1", "CDE"),       # alt 1 min/max
        _shape("1", "A", "2", "B"), _shape("1", "A", "2", "BCDE"),  # alt 2 min/max
    ])
    for m in CALL_RE.finditer(sample_text):
        tok = m.group(1)
        assert GRID_SQUARE_RE.match(tok) is None, (
            f"CALL_RE match {tok!r} unexpectedly collided with the grid-square carve-out")


def main() -> int:
    try:  # HK-009: stdout is cp1252 on Windows consoles by default.
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    self_test()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--against", default="main", help="base ref to diff against (default: main)")
    ap.add_argument("--strict", action="store_true",
                     help="also exit non-zero if changed binary-suffixed files are present and unreviewed")
    args = ap.parse_args()

    files = changed_files(args.against)
    text_files = [f for f in files if (ROOT / f).suffix.lower() in TEXT_SUFFIXES]
    binary_files = [f for f in files
                     if (ROOT / f).suffix.lower() in BINARY_SUFFIXES_OF_INTEREST
                     and (ROOT / f).exists()]

    print(f"NFR-021 scan: {len(text_files)} text files changed vs `{args.against}`\n")

    all_flagged: dict[str, dict[str, int]] = {}
    all_grid_excluded: dict[str, int] = {}
    for rel in text_files:
        p = ROOT / rel
        if not p.exists():
            continue
        flagged, grid_excluded = scan(p)
        if flagged:
            all_flagged[rel] = flagged
        for tok, n in grid_excluded.items():
            all_grid_excluded[tok] = all_grid_excluded.get(tok, 0) + n

    exit_code = 0

    if all_flagged:
        print("🔴 NON-COMPLIANT TOKENS FOUND\n")
        print("%-72s %8s %8s" % ("file", "distinct", "occurs"))
        for rel, hits in sorted(all_flagged.items(), key=lambda x: -sum(x[1].values())):
            print("%-72s %8d %8d" % (rel, len(hits), sum(hits.values())))
        allcalls: dict[str, int] = {}
        for hits in all_flagged.values():
            for k, v in hits.items():
                allcalls[k] = allcalls.get(k, 0) + v
        print(f"\n{len(allcalls)} distinct non-compliant tokens across "
              f"{len(all_flagged)} files, {sum(allcalls.values())} occurrences total.")
        print("\nFingerprinted (never the call itself):")
        for tok, n in sorted(allcalls.items(), key=lambda x: -x[1]):
            print(f"  {fp(tok)}  {n:6d} occurrences  (len={len(tok)})")
        exit_code = 1
    else:
        print("CLEAN -- no non-compliant callsign-shaped tokens in the text files scanned.")

    if all_grid_excluded:
        print(f"\n⚠️  {len(all_grid_excluded)} token(s) excluded as bare Maidenhead locators "
              "(audited, not silent -- self_test() asserts this rule cannot catch a real "
              "single-digit callsign shape):")
        for tok, n in sorted(all_grid_excluded.items(), key=lambda x: -x[1]):
            print(f"  {fp(tok)}  {n:6d} occurrences")

    if binary_files:
        print(f"\n⚠️  {len(binary_files)} changed binary file(s) NOT scanned by this tool "
              "-- item 3's manual review, not this script, is what clears these:")
        for rel in binary_files:
            print(f"  {rel}")
        if args.strict:
            print("\n--strict: treating unreviewed binary files as a failure.")
            exit_code = 1
    else:
        print("\nNo changed PNG/JPG/PDF files to review.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
