#!/usr/bin/env python3
"""NFR-021 redaction pass -- full S1-S8 sweep, results/2026-09-12-fbf8c0b/.

Same method as redact_s1s8_20260907_decodes.py / redact_s1s8_20260906_decodes.py /
redact_s1s8_20260903_decodes.py / redact_row0k_decodes.py / redact_m1_m4_decodes.py /
results/REDACTION-MAP.md's ROW 0 pass (RUNBOOK.md Sec.7.5): import the project's own scanner
(qa/rr-study/nfr021_pre_merge_scan.py -- CALL_RE, classify(), scan(), fp()) rather than
reimplementing it (HK-022), guard every flagged token against this run's own truth.csv
message_text column BEFORE rewriting (only S5/S7 are expected to carry noise-hallucinated
callsign-shaped decoder output; every other scenario's flagged set is expected empty), then do
a byte-level rewrite (UTF-8-with-BOM, CRLF) so line endings are not silently normalised.

This run is the routine post-merge S1-S8 sweep against `fbf8c0b5` (NHARD40-DEFAULT 60->40
default + M2 migration fix + NFR-021 clobber-guard dev-task, PRs #161/#162/#163). Gate A read
0/120 both appraisers (INFO only, superseded by R&R-011's Gate A-W/Gate A-Delta) -- but two S5
noise-floor CRC coincidences (-19/-22 dB, RUNBOOK Sec.7.5 phenomenon) still produced
callsign-shaped decoder output that was never injected, and must not reach git in raw form.

Usage:
    python redact_s1s8_20260912_decodes.py
"""
from __future__ import annotations

import csv
import pathlib
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
_RUN_DIR = _HERE / "results" / "2026-09-12-fbf8c0b"

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import nfr021_pre_merge_scan as scanner  # noqa: E402  (reused, not reimplemented -- HK-022)

_TARGET_FILES = [
    "owsfz-all.txt",
    "wsjt-all.txt",
    "truth.csv",
    "S8_matched.csv",
    "S1_matched.csv",
    "S1b_matched.csv",
    "S2_matched.csv",
    "S3_matched.csv",
    "S4_matched.csv",
    "S5_matched.csv",
    "S7_matched.csv",
    "report.md",
]
_TRUTH_FILE = _RUN_DIR / "truth.csv"


def _load_truth_message_texts() -> set[str]:
    texts: set[str] = set()
    if not _TRUTH_FILE.is_file():
        return texts
    with open(_TRUTH_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("message_text"):
                texts.add(row["message_text"])
    return texts


def main() -> int:
    truth_texts = _load_truth_message_texts()
    print(f"Loaded {len(truth_texts)} distinct injected truth message texts as the guard set "
          f"(from {_TRUTH_FILE.name}).")

    all_flagged: dict[str, int] = {}
    per_file_flagged: dict[str, dict[str, int]] = {}

    for name in _TARGET_FILES:
        path = _RUN_DIR / name
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

    # -- Guard: every flagged token must be decoder output, not injected truth --------------
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
          f"message text. All flagged tokens are decoder output (noise-floor CRC coincidences, "
          f"RUNBOOK.md Sec.7.5).")

    # -- Assign placeholders (deliberately NOT Q-prefix, same reasoning as REDACTION-MAP.md) --
    # "912" infix ties this pass to 2026-09-12, distinct from RDCT (ROW 0), RDCTM (M1-M4),
    # RDCTK (ROW 0k), RDCTS (2026-09-03 S1-S8), RDCT906 (2026-09-06 S1-S8), RDCT7 (2026-09-07
    # S1-S8).
    sorted_tokens = sorted(all_flagged.keys(), key=scanner.fp)  # deterministic order
    placeholder_of: dict[str, str] = {}
    for i, tok in enumerate(sorted_tokens, start=1):
        placeholder_of[tok] = f"<RDCT912{i:02d}>"

    print(f"\n=== Assigning {len(placeholder_of)} placeholders ===")
    map_lines = [
        "# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-12 (`fbf8c0b5`)",
        "",
        "Same method as `results/REDACTION-MAP.md` (ROW 0's own redaction pass), "
        "`REDACTION-MAP-M1-M4.md`, `REDACTION-MAP-ROW0K.md`, and the 2026-09-03/09-06/09-07 "
        "sweeps' own maps -- imported from the project's own scanner "
        "(`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is "
        "decoder output at S5 noise-floor SNR (RUNBOOK.md Sec.7.5's documented phenomenon: the "
        "FT8 CRC occasionally passes for a random bit pattern that happens to be "
        "callsign-shaped), never injected truth -- verified against this run's own `truth.csv` "
        "`message_text` column before rewriting (see `redact_s1s8_20260912_decodes.py`'s guard "
        "step). This run is the routine post-merge sweep against `fbf8c0b5` "
        "(`NHARD40-DEFAULT` 60->40 default, PRs #161/#162/#163); the flagged tokens are the two "
        "S5 Gate A noise-floor events (both AWGN, -19/-22 dB) that Gate A's own per-sweep "
        "reading counts as 0/120 FP events on the ratified scoring (they fall outside Gate A's "
        "own event definition) but which still appear verbatim in the raw decoder logs and "
        "matched CSVs and must not reach git unredacted.",
        "",
        "Placeholders use a `912` infix (`<RDCT912nn>`) distinct from ROW 0's own `<RDCTnn>`, "
        "M1-M4's `<RDCTMnn>`, ROW 0k's `<RDCTKnn>`, the 2026-09-03 sweep's `<RDCTSnn>`, the "
        "2026-09-06 sweep's `<RDCT906nn>`, and the 2026-09-07 sweep's `<RDCT7nn>` placeholders "
        "so tokens from different redaction passes are never confused if files are read "
        "together. Deliberately NOT Q-prefix, for the same reason as the other maps: a "
        "Q-prefix placeholder would be indistinguishable from a legitimately injected synthetic "
        "call and would corrupt a future `truth.csv` join.",
        "",
        "Fingerprint is `\"CS-\" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by "
        "construction.",
        "",
        "| placeholder | token fingerprint |",
        "|---|---|",
    ]
    for tok in sorted_tokens:
        map_lines.append(f"| `{placeholder_of[tok]}` | `{scanner.fp(tok)}` |")

    # -- Byte-level rewrite (CRLF/BOM-preserving) --------------------------------------------
    for name in _TARGET_FILES:
        path = _RUN_DIR / name
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

    # -- Re-scan to confirm zero remaining -----------------------------------------------------
    print("\n=== Re-scan after redaction ===")
    remaining_total = 0
    for name in _TARGET_FILES:
        path = _RUN_DIR / name
        if not path.is_file():
            continue
        flagged, _ = scanner.scan(path)
        remaining_total += sum(flagged.values())
        print(f"{name}: {sum(flagged.values())} remaining flagged occurrences")

    map_path = _RUN_DIR / "REDACTION-MAP.md"
    map_path.write_text("\n".join(map_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {map_path}")
    print(f"TOTAL remaining after redaction: {remaining_total} (must be 0)")
    return 0 if remaining_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
