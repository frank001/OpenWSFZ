#!/usr/bin/env python3
"""`AWGN-FP` Amendment 3, A3.2 -- ROW 0r: does the M1 S5 AWGN decode set survive the
20260049 -> 20260050 shim bump? Shipped as code (HK-021(r)).

Spec: qa/rr-study/2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md Amendment 3 A3.2.
Execution: qa/rr-study/2026-09-04-1322-architect-to-qa-execution-pack-post-shim-bump.md block P2.

Method (disclosed deviation from A3.2's literal "decode twice, once per binary" -- see
tests/OpenWSFZ.Ft8.Tests/Row0rCarryForwardTests.cs's own doc comment for the full reasoning):

  - "Before" (20260049): the ALREADY-RECORDED, git-tracked
    qa/rr-study/awgn-fp-replay/results/m1m4_s5_{slots,decodes}.csv from commit 4a7fb3d, which ran
    successfully under a build whose own ROW 0a (binary-identity pin) passed against 20260049 at
    the time. Confirmed byte-identical since (`git diff --stat 4a7fb3d HEAD -- <those two files>`,
    empty). This script independently re-verifies chain of custody: it extracts the 20260049
    win-x64 DLL as a real artefact (`git show 3b52608:...`) and asserts its SHA256 against the
    pinned value BEFORE trusting those CSVs as the "before" snapshot. Mismatch -> STOP.
  - "After" (20260050): a FRESH decode of the identical _work/m1m4_s5/ WAV population, run by
    Row0rCarryForwardTests.cs (a new xunit Fact, current main, current binary -- no worktree, no
    second checkout), same process configuration (SetApBits([],[]) clear, one DecodeAll per slot,
    no NormalisePcm -- that repair is ROW 0n, out of scope here).
  - Reason a live decode with the OLD binary was not attempted from the current source tree:
    Ft8LibInterop's ABI self-test (`ExpectedShimVersion`) is a hard-coded compile-time constant,
    now 20260050. Loading the 20260049 DLL through a CURRENT build throws in LoadAndVerify before
    any decode call is reachable -- there is no live "old binary, new source" combination available
    without a second checkout, which is disclosed here as a structural finding rather than worked
    around by patching src/ (not licensed) or re-pinning AwgnFpReplayTests.cs's own historical ROW
    0a (barred by AWGN-FP Amendment 3 Ruling 1).

FIRES iff any slot's decode SET differs (text/freq/SNR/DT, not counts) -- per A3.2 step 4-5.

Usage:
    python row0r_carry_forward.py
Writes qa/rr-study/fp-parity/row0r_carry_forward_results.txt alongside stdout output.
"""
from __future__ import annotations

import csv
import hashlib
import pathlib
import subprocess
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
_QA_ROOT = _HERE.parent
_REPO_ROOT = _QA_ROOT.parent.parent
_RESULTS_PATH = _HERE / "row0r_carry_forward_results.txt"

_BEFORE_SLOTS = _QA_ROOT / "awgn-fp-replay" / "results" / "m1m4_s5_slots.csv"
_BEFORE_DECODES = _QA_ROOT / "awgn-fp-replay" / "results" / "m1m4_s5_decodes.csv"
_AFTER_SLOTS = _HERE / "results" / "m1m4_s5_20260050_slots.csv"
_AFTER_DECODES = _HERE / "results" / "m1m4_s5_20260050_decodes.csv"

_PINNED_SHA_20260049 = "ce02c7ba10e216349c3cc6d2460a6106379a4593bb730c807dbe8128ecca153e"
_OLD_BINARY_SOURCE_COMMIT = "3b52608"
_OLD_BINARY_PATH_IN_REPO = "src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll"
_PROVENANCE_COMMIT = "4a7fb3d"  # the commit that produced the "before" CSVs


def _log(lines: list, msg: str) -> None:
    print(msg)
    lines.append(msg)


def _sha256_of_git_blob(commit: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=_REPO_ROOT, capture_output=True, check=True,
    )
    return hashlib.sha256(result.stdout).hexdigest()


def _load_decodes(path: pathlib.Path) -> dict[tuple, list[tuple]]:
    """slot key (scenario,part,trial,seed) -> sorted list of (message,freq_hz,dt_s,reported_snr_db)."""
    by_slot: dict[tuple, list[tuple]] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (row["scenario"], int(row["part"]), int(row["trial"]), int(row["seed"]))
            item = (row["message"], int(row["freq_hz"]), float(row["dt_s"]), int(row["reported_snr_db"]))
            by_slot.setdefault(key, []).append(item)
    for key in by_slot:
        by_slot[key].sort()
    return by_slot


def _load_slot_keys(path: pathlib.Path) -> set[tuple]:
    keys = set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            keys.add((row["scenario"], int(row["part"]), int(row["trial"]), int(row["seed"])))
    return keys


def main() -> int:
    lines: list = []
    _log(lines, "AWGN-FP A3.2 -- ROW 0r: M1 S5 decode-set carry-forward, 20260049 -> 20260050")
    _log(lines, "Spec: qa/rr-study/2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md Amendment 3 A3.2")

    # ── Step 1-2: obtain the 20260049 binary as a real artefact, assert its SHA before using it ──
    _log(lines, f"\nStep 1: extracting {_OLD_BINARY_PATH_IN_REPO} from commit {_OLD_BINARY_SOURCE_COMMIT}")
    actual_sha = _sha256_of_git_blob(_OLD_BINARY_SOURCE_COMMIT, _OLD_BINARY_PATH_IN_REPO)
    _log(lines, f"Step 2: actual SHA256  = {actual_sha}")
    _log(lines, f"        pinned SHA256  = {_PINNED_SHA_20260049}")
    if actual_sha != _PINNED_SHA_20260049:
        _log(lines, "STOP -- binary identity mismatch. Do not use these CSVs as the '20260049' "
                     "before-snapshot; no carry-forward claim of any kind may be made.")
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1
    _log(lines, "MATCH -- the 20260049 pin is confirmed as a real, hash-verified artefact.")

    # ── Confirm the "before" CSVs are genuinely untouched since the run that produced them ──
    diff = subprocess.run(
        ["git", "diff", "--stat", _PROVENANCE_COMMIT, "HEAD", "--",
         str(_BEFORE_SLOTS.relative_to(_REPO_ROOT)), str(_BEFORE_DECODES.relative_to(_REPO_ROOT))],
        cwd=_REPO_ROOT, capture_output=True, text=True, check=True,
    )
    _log(lines, f"\ngit diff --stat {_PROVENANCE_COMMIT} HEAD -- <before CSVs>: "
                 f"{'EMPTY (untouched)' if not diff.stdout.strip() else 'NOT EMPTY -- ' + diff.stdout.strip()}")
    if diff.stdout.strip():
        _log(lines, "STOP -- the 'before' CSVs have changed since the run that produced them; "
                     "cannot trust them as the 20260049 snapshot.")
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    for p in (_BEFORE_SLOTS, _BEFORE_DECODES, _AFTER_SLOTS, _AFTER_DECODES):
        if not p.is_file():
            _log(lines, f"STOP -- missing file: {p}")
            _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return 1

    # ── Step 3: population -- every M1 S5 slot, no sampling, no truncation ──
    before_slots = _load_slot_keys(_BEFORE_SLOTS)
    after_slots = _load_slot_keys(_AFTER_SLOTS)
    _log(lines, f"\nStep 3: population -- before={len(before_slots)} slots, after={len(after_slots)} slots")
    if before_slots != after_slots:
        missing_after = before_slots - after_slots
        missing_before = after_slots - before_slots
        _log(lines, f"STOP -- slot population mismatch: {len(missing_after)} in before-not-after, "
                     f"{len(missing_before)} in after-not-before. This is not a decode-set diff, it "
                     "is a population mismatch -- do not proceed to a per-slot compare.")
        _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    # ── Step 4-5: diff the decode SET per slot -- message/freq/SNR/DT, not counts ──
    before_decodes = _load_decodes(_BEFORE_DECODES)
    after_decodes = _load_decodes(_AFTER_DECODES)

    differing_slots = []
    for key in sorted(before_slots):
        b = before_decodes.get(key, [])
        a = after_decodes.get(key, [])
        if b != a:
            differing_slots.append((key, b, a))

    fires = len(differing_slots) > 0
    _log(lines, f"\n=== ROW 0r RESULT ===")
    _log(lines, f"Slots compared: {len(before_slots)}")
    _log(lines, f"Slots with a differing decode set: {len(differing_slots)}")
    _log(lines, f"ROW 0r FIRES (any slot's decode set differs) = {fires}")

    if fires:
        _log(lines, "\nFIRST 10 DIFFERING SLOTS (scenario,part,trial,seed):")
        for key, b, a in differing_slots[:10]:
            _log(lines, f"  {key}:")
            _log(lines, f"    before(20260049): {b}")
            _log(lines, f"    after (20260050): {a}")
        _log(lines, "\nROW 0r FIRES -> M1-M4, ROW 0q and ROW 0m are VOID on 20260050 and must be "
                     "re-run before P3 proceeds. Per A3.2: do NOT investigate why they differ here "
                     "-- that is a new pre-registration, not a patch to this one.")
    else:
        _log(lines, "\nROW 0r does NOT fire -> M1-M4, ROW 0q and ROW 0m carry forward to 20260050 "
                     "as DISCLOSED carry-forwards (decode-identical), exactly as S5-LEVEL Option 2 "
                     "landed. Scope note (A3.2 point 6): this population is NOISE-ONLY (M1); ROW 0d "
                     "/ M3's genuine population is NOT carried by this row.")
        _log(lines, f"  Before-binary SHA256 (verified artefact): {_PINNED_SHA_20260049}")
        _log(lines, f"  After-binary  SHA256 (current main win-x64): 6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c")
        _log(lines, f"  Slot count: {len(before_slots)}  Verdict: decode-identical")

    _RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {_RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
