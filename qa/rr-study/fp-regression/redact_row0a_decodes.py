#!/usr/bin/env python3
"""NFR-021 redaction pass -- E2/ROW 0a decode CSVs (row0a_B1_decodes.csv, row0a_B8_decodes.csv).

Same method as `awgn-fp-replay/redact_m1_m4_decodes.py` and `results/REDACTION-MAP.md`'s ROW 0
pass: import the project's own scanner (qa/rr-study/nfr021_pre_merge_scan.py -- CALL_RE,
classify(), fp()) rather than reimplementing it (HK-022), guard that every flagged token is
decoder output and not injected truth BEFORE rewriting, then do a byte-level rewrite
(UTF-8-with-BOM, CRLF) so line endings are not silently normalised.

Placeholder infix `G` (<RDCTGnn>) -- deliberately distinct from the three infixes the execution
pack names explicitly (bare <RDCTnn>, <RDCTMnn>, <RDCTRnn>) AND from the two already in use
elsewhere in the repo (<RDCTKnn>, <RDCTSnn>) that the pack's list happens not to mention.

Usage:
    python redact_row0a_decodes.py
"""
from __future__ import annotations

import csv
import pathlib
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
_RESULTS = _HERE / "results"
_QA_ROOT = _HERE.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

import nfr021_pre_merge_scan as scanner  # noqa: E402  (reused, not reimplemented -- HK-022)

_TARGET_FILES = ["row0a_B1_decodes.csv", "row0a_B8_decodes.csv"]
_TRUTH_FILE = _QA_ROOT.parent / "rr-study" / "awgn-fp-replay" / "_work" / "m1m4_s5_truth" / "truth.csv"


def _load_truth_message_texts() -> set[str]:
    texts: set[str] = set()
    if _TRUTH_FILE.is_file():
        with open(_TRUTH_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("message_text"):
                    texts.add(row["message_text"])
    return texts


def main() -> int:
    truth_texts = _load_truth_message_texts()
    print(f"Loaded {len(truth_texts)} distinct injected truth message texts as the guard set "
          f"(S5 is a noise-only scenario -- expected to be 0).")

    all_flagged: dict[str, int] = {}
    per_file_flagged: dict[str, dict[str, int]] = {}

    for name in _TARGET_FILES:
        path = _RESULTS / name
        if not path.is_file():
            print(f"SKIP (not found): {path}")
            continue
        flagged, grid_excluded = scanner.scan(path)
        per_file_flagged[name] = flagged
        for tok, n in flagged.items():
            all_flagged[tok] = all_flagged.get(tok, 0) + n
        print(f"{name}: {len(flagged)} distinct flagged tokens, "
              f"{sum(flagged.values())} occurrences; {len(grid_excluded)} grid-square exclusions")

    if not all_flagged:
        print("\nNo flagged tokens in any target file. Nothing to redact.")
        return 0

    print("\n=== GUARD: checking every flagged token against injected truth message texts ===")
    violations = []
    for tok in all_flagged:
        for truth_msg in truth_texts:
            if tok in truth_msg:
                violations.append((tok, truth_msg))
    if violations:
        print(f"GUARD FAILED: {len(violations)} flagged token(s) appear inside an injected "
              f"truth message. STOPPING -- do not redact until this is understood.")
        for tok, msg in violations[:20]:
            print(f"  token={tok!r} found inside truth message={msg!r}")
        return 1
    print(f"GUARD PASSED: 0 of {len(all_flagged)} flagged tokens appear in any injected truth "
          f"message text. All flagged tokens are decoder output on a noise-only corpus.")

    sorted_tokens = sorted(all_flagged.keys(), key=scanner.fp)  # deterministic order
    placeholder_of: dict[str, str] = {}
    for i, tok in enumerate(sorted_tokens, start=1):
        placeholder_of[tok] = f"<RDCTG{i:02d}>"

    print(f"\n=== Assigning {len(placeholder_of)} placeholders ===")
    map_lines = [
        "# NFR-021 redaction map -- FP-REGRESSION E2/ROW 0a decode CSVs",
        "",
        "Same method as `awgn-fp-replay/results/REDACTION-MAP-M1-M4.md` -- imported from the "
        "project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every "
        "token below is decoder output from the paired B1/B8 offline replay of the noise-only "
        "(S5) M1 corpus, never injected truth -- verified against `_work/m1m4_s5_truth/truth.csv`'s "
        "`message_text` column (empty for S5, as expected) before rewriting.",
        "",
        "Placeholders use a `G` infix (`<RDCTGnn>`) -- distinct from the three the execution pack "
        "names explicitly (`<RDCTnn>`, `<RDCTMnn>`, `<RDCTRnn>`) and from the two already in use "
        "elsewhere in the repo that the pack's list does not mention (`<RDCTKnn>`, `<RDCTSnn>`).",
        "",
        "Fingerprint is `\"CS-\" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by "
        "construction.",
        "",
        "| placeholder | token fingerprint |",
        "|---|---|",
    ]
    for tok in sorted_tokens:
        map_lines.append(f"| `{placeholder_of[tok]}` | `{scanner.fp(tok)}` |")

    for name in _TARGET_FILES:
        path = _RESULTS / name
        if not path.is_file():
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8")
        for tok, placeholder in placeholder_of.items():
            text = text.replace(tok, placeholder)
        new_raw = ("﻿" + text).encode("utf-8") if raw.startswith(b"\xef\xbb\xbf") else text.encode("utf-8")
        path.write_bytes(new_raw)
        print(f"Rewrote {name} in place ({len(raw)} -> {len(new_raw)} bytes).")

    map_path = _RESULTS / "REDACTION-MAP-ROW0A.md"
    map_path.write_text("\n".join(map_lines) + "\n", encoding="utf-8")
    print(f"Wrote {map_path}")

    print("\n=== Re-scanning after redaction ===")
    all_clean = True
    for name in _TARGET_FILES:
        path = _RESULTS / name
        if not path.is_file():
            continue
        flagged, _ = scanner.scan(path)
        if flagged:
            all_clean = False
            print(f"{name}: STILL FLAGGED -- {flagged}")
        else:
            print(f"{name}: clean (0 flagged)")
    return 0 if all_clean else 1


if __name__ == "__main__":
    sys.exit(main())
