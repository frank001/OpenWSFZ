#!/usr/bin/env python3
"""NFR-021 redaction pass -- ROW 0r's fresh 20260050 decode CSV
(qa/rr-study/fp-parity/results/m1m4_s5_20260050_decodes.csv) and its raw results.txt.

Same method as qa/rr-study/awgn-fp-replay/redact_m1_m4_decodes.py (which redacted the "before"
20260049 CSV this file is being diffed against) -- import the project's own scanner
(qa/rr-study/nfr021_pre_merge_scan.py) rather than reimplementing it (HK-022), guard every
flagged token against the render's own injected truth message texts BEFORE rewriting, then do a
byte-level rewrite (UTF-8-with-BOM, CRLF) so line endings are not silently normalised.

Placeholders use an `R` infix (`<RDCTRnn>`), distinct from ROW 0's `<RDCTnn>` and M1-M4's
`<RDCTMnn>`, so all three passes' tokens are never confused if the CSVs are read together.

Usage:
    python redact_row0r_decodes.py
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
_QA_ROOT = _HERE.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

import nfr021_pre_merge_scan as scanner  # noqa: E402  (reused, not reimplemented -- HK-022)

_DECODES_CSV = _HERE / "results" / "m1m4_s5_20260050_decodes.csv"
_RESULTS_TXT = _HERE / "row0r_carry_forward_results.txt"
_TRUTH_FILE = _QA_ROOT / "awgn-fp-replay" / "_work" / "m1m4_s5_truth" / "truth.csv"


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
          f"({_TRUTH_FILE}, exists={_TRUTH_FILE.is_file()}).")

    targets = [p for p in (_DECODES_CSV, _RESULTS_TXT) if p.is_file()]
    all_flagged: dict[str, int] = {}
    per_file_flagged: dict[str, dict[str, int]] = {}

    for path in targets:
        flagged, grid_excluded = scanner.scan(path)
        per_file_flagged[str(path)] = flagged
        for tok, n in flagged.items():
            all_flagged[tok] = all_flagged.get(tok, 0) + n
        print(f"{path.name}: {len(flagged)} distinct flagged tokens, "
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
          f"message text. All flagged tokens are decoder output (this population is noise-only, "
          f"S5 parts 0/1 -- every decode here is by construction a false accept).")

    sorted_tokens = sorted(all_flagged.keys(), key=scanner.fp)
    placeholder_of: dict[str, str] = {}
    for i, tok in enumerate(sorted_tokens, start=1):
        placeholder_of[tok] = f"<RDCTR{i:02d}>"

    print(f"\n=== Assigning {len(placeholder_of)} placeholders ===")
    map_lines = [
        "# NFR-021 redaction map -- ROW 0r fresh 20260050 decode CSV + results.txt",
        "",
        "Same method as `awgn-fp-replay/redact_m1_m4_decodes.py` (which redacted the '20260049' "
        "CSV this pass is diffed against) -- imported from the project's own scanner "
        "(`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is decoder "
        "output on the noise-only S5 parts 0/1 population (every decode here is by construction a "
        "false accept), never injected truth -- verified against the render's own `truth.csv` "
        "`message_text` column before rewriting.",
        "",
        "Placeholders use an `R` infix (`<RDCTRnn>`), distinct from ROW 0's `<RDCTnn>` and "
        "M1-M4's `<RDCTMnn>`, so all three passes' tokens are never confused if read together.",
        "",
        "Fingerprint is `\"CS-\" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by "
        "construction.",
        "",
        "| placeholder | token fingerprint |",
        "|---|---|",
    ]
    for tok in sorted_tokens:
        map_lines.append(f"| `{placeholder_of[tok]}` | `{scanner.fp(tok)}` |")

    for path in targets:
        flagged = per_file_flagged.get(str(path), {})
        if not flagged:
            print(f"{path.name}: nothing to redact, left byte-identical.")
            continue

        raw = path.read_bytes()
        had_bom = raw.startswith(b"\xef\xbb\xbf")
        crlf_before = raw.count(b"\r\n")

        text = raw.decode("utf-8-sig" if had_bom else "utf-8")

        def _replace(m, _flagged=flagged, _placeholder_of=placeholder_of):
            tok = m.group(1)
            if tok in _flagged:
                return m.group(0).replace(tok, _placeholder_of[tok])
            return m.group(0)

        new_text = scanner.CALL_RE.sub(_replace, text)

        new_bytes = (b"\xef\xbb\xbf" if had_bom else b"") + new_text.encode("utf-8")
        crlf_after = new_bytes.count(b"\r\n")
        path.write_bytes(new_bytes)

        print(f"{path.name}: rewrote, BOM={had_bom} (preserved), CRLF {crlf_before} -> {crlf_after} "
              f"(must match)")
        assert crlf_before == crlf_after, \
            f"{path.name}: CRLF count changed ({crlf_before} -> {crlf_after}) -- STOP, investigate"

    print("\n=== Re-scan after redaction ===")
    remaining_total = 0
    for path in targets:
        flagged, _ = scanner.scan(path)
        remaining_total += sum(flagged.values())
        print(f"{path.name}: {sum(flagged.values())} remaining flagged occurrences")

    map_path = _HERE / "REDACTION-MAP-ROW0R.md"
    map_path.write_text("\n".join(map_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {map_path}")
    print(f"TOTAL remaining after redaction: {remaining_total} (must be 0)")
    return 0 if remaining_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
