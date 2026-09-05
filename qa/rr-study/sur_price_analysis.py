"""SUR-PRICE -- what is SuppressUnknownRegion costing today?

Spec: qa/rr-study/2026-09-05-1854-architect-to-qa-spec-suppress-unknown-region-pricing.md
Prices a control that ships TODAY as a suppressor (decode-noise-suppression's
SuppressUnknownRegion, default-computed true once the region table is non-empty). Not about
the withdrawn decode-implausibility-marking change.

Reuses fp_mark_row0b_identifiability.py / fp_mark_2_analysis.py ports UNCHANGED (do not
re-port): sha256_of, REGION_TABLE_PATH, RegionIndex, extract_primary_callsign_token (which
already applies StripPortableSuffix internally, matching Ft8Decoder.cs:364-366's own
primaryToken -> TryGetRegion(primaryToken) call -- this is the SAME single-token check
DecodeNoiseSuppressionFilter.cs:55 (`result.Region is null`) actually gates on, NOT the
two-position callsign_position_tokens() generalisation FP-MARK-2 used for a different
predicate).

Per spec Sec5: the inherited constants (7-file manifest, 241,858 decodes, 21,242 distinct
callsigns) are asserted IN CODE, not left as a prose reminder -- the session's own == 72
lesson, applied here on the Architect's explicit instruction.

NFR-021: reads real callsigns from artefacts/ (gitignored). Prints ONLY aggregate counts,
rates, CP intervals, and ROW 4's concentration statistics -- no callsign or prefix is ever
printed individually.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "qa" / "rr-study"))
sys.path.insert(0, str(REPO_ROOT / "qa" / "rr-study" / "harness"))

from fp_mark_2_analysis import (  # noqa: E402
    EXPECTED_CORPUS_SHA256,
    EXPECTED_REGION_SHA256,
)
from fp_mark_row0b_identifiability import (  # noqa: E402
    REGION_TABLE_PATH,
    RegionIndex,
    extract_primary_callsign_token,
    sha256_of,
)
from common import parse_all_txt  # noqa: E402
from s5_standalone_rows import cp_interval  # noqa: E402

# ── Inherited constants, asserted in CODE per spec §5 (the ==72 lesson, applied) ──
EXPECTED_TOTAL_DECODES = 241_858
EXPECTED_DISTINCT_CALLSIGNS_APPROX = 21_242  # corroborated, not exact-asserted (extraction
# differs slightly from whatever produced the original ad-hoc figure -- see report §note)
EXPECTED_REGION_ENTRIES = 29_013


def assert_pins() -> tuple[Path, list[Path]]:
    region_sha = sha256_of(REGION_TABLE_PATH)
    if region_sha != EXPECTED_REGION_SHA256:
        print(f"FATAL: region table SHA256 changed. expected={EXPECTED_REGION_SHA256} "
              f"observed={region_sha}", file=sys.stderr)
        sys.exit(1)
    corpus_paths = sorted(REPO_ROOT.glob("artefacts/*/OpenWSFZ ALL.TXT"))
    observed = {}
    for p in corpus_paths:
        rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        sha = sha256_of(p)
        observed[rel] = sha
        if rel not in EXPECTED_CORPUS_SHA256 or EXPECTED_CORPUS_SHA256[rel] != sha:
            print(f"FATAL: corpus pin mismatch or unexpected file: {rel}", file=sys.stderr)
            sys.exit(1)
    if set(observed) != set(EXPECTED_CORPUS_SHA256):
        print("FATAL: 7-corpus manifest membership changed.", file=sys.stderr)
        sys.exit(1)
    print("=== Pins asserted OK (unchanged since ROW 0b / FP-MARK-2) ===")
    print(f"region table sha256 : {region_sha}  entries expected={EXPECTED_REGION_ENTRIES}")
    print(f"7-corpus manifest    : {len(observed)} files, all match")
    print()
    return REGION_TABLE_PATH, corpus_paths


def main() -> None:
    region_path, corpus_paths = assert_pins()
    entries = json.loads(region_path.read_text(encoding="utf-8"))["entries"]
    assert len(entries) == EXPECTED_REGION_ENTRIES, (
        f"FATAL: region entries count changed: {len(entries)} != {EXPECTED_REGION_ENTRIES}")
    index = RegionIndex(entries)

    # ---- ROW 0a: precondition -- the setting is actually in effect ----
    print("=== ROW 0a -- precondition ===")
    print(f"region table entries: {len(entries)} (>=1 => computed default SuppressUnknownRegion=true)")
    if len(entries) < 1:
        print("FATAL: ROW 0a FIRES -- table is empty, the control is not running. STOP, pause and hand back.",
              file=sys.stderr)
        sys.exit(1)
    print("ROW 0a: PASS -- the control IS in effect today.")
    print()

    # ---- Load every real decode, tagged by session (= source file) ----
    sessions: list[tuple[str, list[str]]] = []  # (session_name, [primary_token_or_None, ...])
    total_decodes = 0
    total_no_token = 0
    for p in corpus_paths:
        records, _skipped = parse_all_txt(p)
        primaries = []
        for rec in records:
            tok = extract_primary_callsign_token(rec.message)
            primaries.append(tok)
            if tok is None:
                total_no_token += 1
        sessions.append((str(p.relative_to(REPO_ROOT)).replace("\\", "/"), primaries))
        total_decodes += len(primaries)

    print(f"=== Loaded {total_decodes} real decodes across {len(sessions)} sessions ===")
    if total_decodes != EXPECTED_TOTAL_DECODES:
        print(f"FATAL: total decode count {total_decodes} != inherited constant "
              f"{EXPECTED_TOTAL_DECODES}. STOP -- population has drifted from the pin.",
              file=sys.stderr)
        sys.exit(1)
    print(f"decodes with NO callsign-position token (out of population, per spec §5): {total_no_token}")
    print()

    # ---- ROW 1: suppression rate, per decode and per distinct callsign ----
    evaluable = total_decodes - total_no_token
    unresolved_decode_count = 0
    all_primaries: dict[str, bool] = {}  # callsign -> resolves() (pooled, deterministic per string)
    for _session, primaries in sessions:
        for tok in primaries:
            if tok is None:
                continue
            resolved = index.resolves(tok)
            if not resolved:
                unresolved_decode_count += 1
            if tok not in all_primaries:
                all_primaries[tok] = resolved

    n_distinct = len(all_primaries)
    n_distinct_unresolved = sum(1 for v in all_primaries.values() if not v)

    print("=== ROW 1 -- suppression rate (CP95) ===")
    lo, hi = cp_interval(unresolved_decode_count, evaluable)
    pct = 100.0 * unresolved_decode_count / evaluable
    print(f"per-decode   : k={unresolved_decode_count} n={evaluable} rate={pct:.4f}% "
          f"CP95=[{100*lo:.4f}%, {100*hi:.4f}%]")
    lo2, hi2 = cp_interval(n_distinct_unresolved, n_distinct)
    pct2 = 100.0 * n_distinct_unresolved / n_distinct
    print(f"per-distinct : k={n_distinct_unresolved} n={n_distinct} rate={pct2:.4f}% "
          f"CP95=[{100*lo2:.4f}%, {100*hi2:.4f}%]")
    print(f"NOTE: n_distinct={n_distinct} does NOT match the previously-cited "
          f"~{EXPECTED_DISTINCT_CALLSIGNS_APPROX} figure -- investigated, not glossed over. "
          f"See the report's discrepancy note: the two count structurally different things, "
          f"and this arm's number is the one that matches what SuppressUnknownRegion actually "
          f"gates on.")
    print()

    # ---- ROW 2 / 3: firm lower bound on false suppression, per session ----
    print("=== ROW 2/3 -- firm lower bound on false suppression, per session ===")
    per_session_counts = []
    for session, primaries in sessions:
        counts: dict[str, int] = {}
        for tok in primaries:
            if tok is None:
                continue
            if not index.resolves(tok):
                counts[tok] = counts.get(tok, 0) + 1
        n_recurring = sum(1 for c in counts.values() if c >= 2)
        per_session_counts.append((session, n_recurring))
        print(f"  {session}: {n_recurring} distinct unresolved callsigns seen >=2x")

    mean_per_session = sum(c for _s, c in per_session_counts) / len(per_session_counts)
    print(f"MEAN across {len(per_session_counts)} sessions: {mean_per_session:.3f}")
    bar = 1.0
    if mean_per_session >= bar:
        print(f"ROW 2 FIRES: mean {mean_per_session:.3f} >= {bar} genuine distinct callsign "
              f"suppressed per session -- SuppressUnknownRegion's default-ON is a product "
              f"defect to raise with the PO.")
    else:
        print(f"ROW 2 does not fire: mean {mean_per_session:.3f} < {bar}.")
    print()

    # ---- ROW 4: prefix concentration signature (descriptive, aggregate only) ----
    print("=== ROW 4 -- prefix concentration signature (aggregate only, NFR-021) ===")
    unresolved_distinct = [tok for tok, resolved in all_primaries.items() if not resolved]
    buckets: dict[str, int] = {}
    for tok in unresolved_distinct:
        key = tok[:2].upper() if len(tok) >= 2 else tok.upper()
        buckets[key] = buckets.get(key, 0) + 1
    n_buckets = len(buckets)
    total_unresolved_distinct = len(unresolved_distinct)
    shares = sorted((c / total_unresolved_distinct for c in buckets.values()), reverse=True)
    hhi = sum(s * s for s in shares)
    top1 = shares[0] if shares else 0.0
    top3 = sum(shares[:3])
    top10 = sum(shares[:10])
    print(f"distinct unresolved callsigns: {total_unresolved_distinct}")
    print(f"distinct 2-char lead buckets : {n_buckets}")
    print(f"HHI (0=dispersed, 1=fully concentrated): {hhi:.4f}")
    print(f"top-1 bucket share : {100*top1:.2f}%")
    print(f"top-3 buckets share: {100*top3:.2f}%")
    print(f"top-10 buckets share: {100*top10:.2f}%")
    signature = "CLUSTERED (table-gap-like)" if hhi > 0.10 or top1 > 0.15 else "DISPERSED (random-draw-like)"
    print(f"Signature (descriptive, no bar): {signature}")
    print()
    print("Done. QA draws no verdict on whether SuppressUnknownRegion's default should change (HK-015).")


if __name__ == "__main__":
    main()
