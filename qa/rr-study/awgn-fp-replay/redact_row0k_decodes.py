#!/usr/bin/env python3
"""NFR-021 redaction pass -- ROW 0k decode CSVs (row0k_before_decodes.csv, row0k_after_decodes.csv).

Same method as redact_m1_m4_decodes.py / results/REDACTION-MAP.md's ROW 0 pass: import the
project's own scanner (qa/rr-study/nfr021_pre_merge_scan.py -- CALL_RE, classify(), fp()) rather
than reimplementing it (HK-022), guard that every flagged token is decoder output and not injected
truth BEFORE rewriting (S5 is signal-free, so the truth guard set is expected to be empty message
texts -- the guard still runs, unconditionally), then do a byte-level rewrite (UTF-8-with-BOM,
CRLF) so line endings are not silently normalised.

ROW 0k (S5-LEVEL spec Amendment 1 A1.3) decoded the same 60 S5 seeds twice -- once from
row0b_baseline (level_dbfs present) and once from row0j_after (level_dbfs deleted, Option 2) -- to
confirm the 1-LSB byte difference ROW 0j found is decode-invisible. Both decode CSVs carry the
same class of noise-hallucinated callsign-shaped message text as every other AWGN-FP decode CSV.

Usage:
    python redact_row0k_decodes.py
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

_TARGET_FILES = ["row0k_before_decodes.csv", "row0k_after_decodes.csv"]
_TRUTH_FILES = [
    _HERE / "_work" / "row0b_baseline_truth" / "truth.csv",
    _HERE / "_work" / "row0j_after_truth" / "truth.csv",
]


def _load_truth_message_texts() -> set[str]:
    texts: set[str] = set()
    for tf in _TRUTH_FILES:
        if not tf.is_file():
            continue
        with open(tf, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("message_text"):
                    texts.add(row["message_text"])
    return texts


def main() -> int:
    truth_texts = _load_truth_message_texts()
    print(f"Loaded {len(truth_texts)} distinct injected truth message texts as the guard set "
          f"(S5 is signal-free -- expected to be 0).")

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

    # ── Guard: every flagged token must be decoder output, not injected truth ──────
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
          f"message text. All flagged tokens are decoder output.")

    # ── Assign placeholders (deliberately NOT Q-prefix, same reasoning as REDACTION-MAP.md) ──
    sorted_tokens = sorted(all_flagged.keys(), key=scanner.fp)  # deterministic order
    placeholder_of: dict[str, str] = {}
    for i, tok in enumerate(sorted_tokens, start=1):
        placeholder_of[tok] = f"<RDCTK{i:02d}>"

    print(f"\n=== Assigning {len(placeholder_of)} placeholders ===")
    map_lines = [
        "# NFR-021 redaction map -- S5-LEVEL ROW 0k decode CSVs",
        "",
        "Same method as `results/REDACTION-MAP.md` (ROW 0's own redaction pass) and "
        "`REDACTION-MAP-M1-M4.md` -- imported from the project's own scanner "
        "(`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is "
        "decoder output on a signal-free (S5) offline replay, never injected truth -- verified "
        "against both renders' own `truth.csv` `message_text` columns before rewriting (see "
        "`redact_row0k_decodes.py`'s guard step; S5 is signal-free so that guard set is empty).",
        "",
        "Placeholders use a `K` infix (`<RDCTKnn>`) distinct from ROW 0's own `<RDCTnn>` and "
        "M1-M4's `<RDCTMnn>` placeholders so the three passes' tokens are never confused if the "
        "CSVs are read together. Deliberately NOT Q-prefix, for the same reason as the other two "
        "maps: a Q-prefix placeholder would be indistinguishable from a legitimately injected "
        "synthetic call and would corrupt a future `truth.csv` join.",
        "",
        "Fingerprint is `\"CS-\" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by "
        "construction.",
        "",
        "| placeholder | token fingerprint |",
        "|---|---|",
    ]
    for tok in sorted_tokens:
        map_lines.append(f"| `{placeholder_of[tok]}` | `{scanner.fp(tok)}` |")

    # ── Byte-level rewrite (CRLF/BOM-preserving) ────────────────────────────────────
    for name in _TARGET_FILES:
        path = _RESULTS / name
        if not path.is_file():
            continue
        flagged = per_file_flagged.get(name, {})
        if not flagged:
            print(f"{name}: nothing to redact, left byte-identical.")
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

        print(f"{name}: rewrote, BOM={had_bom} (preserved), CRLF {crlf_before} -> {crlf_after} "
              f"(must match)")
        assert crlf_before == crlf_after, \
            f"{name}: CRLF count changed ({crlf_before} -> {crlf_after}) -- STOP, investigate"

    # ── Re-scan to confirm zero remaining ────────────────────────────────────────────
    print("\n=== Re-scan after redaction ===")
    remaining_total = 0
    for name in _TARGET_FILES:
        path = _RESULTS / name
        if not path.is_file():
            continue
        flagged, _ = scanner.scan(path)
        remaining_total += sum(flagged.values())
        print(f"{name}: {sum(flagged.values())} remaining flagged occurrences")

    map_path = _RESULTS / "REDACTION-MAP-ROW0K.md"
    map_path.write_text("\n".join(map_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {map_path}")
    print(f"TOTAL remaining after redaction: {remaining_total} (must be 0)")
    return 0 if remaining_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
