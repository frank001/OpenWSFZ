#!/usr/bin/env python3
"""D-001 C.2 Phase 2a -- ceiling re-derivation against the K=4 candidate set.

(dev-tasks/2026-07-26-d001-c2-phase2-llr-shrinkage.md Sec.2; QA-authored analysis only --
no native/managed code touched, reuses already-committed C.2/C.3/C.4 artefacts, so no
dev-task/Developer session is needed per HK-000/HK-015/HK-011.)

WHY THIS EXISTS
---------------
C.2 Phase 1 bounded the LLR-normalisation avenue's realistic ceiling at "~17% of the
remaining gap" (135 of the 793 WSJT-X messages missed on the fixed 68-cycle corpus) --
but that bound only covers messages that already had a FAILED candidate of ours at the
shipped K_MIN_SCORE=10/K_MAX_CANDIDATES=140. The other 648 (C.3's candidate-generation-
gap population) were assumed out of reach, because LLR normalisation only ever applies
to a candidate that exists.

C.4's min-score sweep, verified by the Architect's ruling
(2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md Sec.2), found that
assumption doubtful: at K_MIN_SCORE=4/K_MAX_CANDIDATES=2000, 618 of the 648 gain a
candidate near the right frequency/time, and only +2 of them actually decode. That is
not "no candidate exists" -- it is "a candidate exists and fails," which is exactly the
shape of question C.2 Phase 1 already knows how to answer. The ruling's Sec.5.1 calls
re-deriving Phase 2's ceiling against this K=4 candidate set "the cheapest way to test
it." This script does that re-derivation.

METHOD (dev-task Sec.2)
------------------------
1. Reproduce the 648-message population identity exactly as
   c3_candidate_generation_gap_analysis.py / c4_min_score_sweep_analysis.py did, from
   C.2 Phase 1's own (owsfz-audio, K10/cap140) artefacts -- that identity is frozen and
   does not change with the candidate set being probed.
2. For each of the 648, look up whether a candidate now exists nearby in the committed
   K=4/cap2000 candidate_diag.csv (same +/-10 Hz / +/-0.5 s tolerance C.2/C.3/C.4 all
   used). Classify each into: still no candidate / matched a decoded candidate / matched
   a failed candidate (the expanded matched-missed population).
3. SELF-CHECK FIRST: the "matched a decoded candidate" count must be small and roughly
   consistent with the ruling's own independently-measured +2 (Sec.2 table, "K=4 @2000"
   row, Delta matched). If it diverges materially, the matching logic here has drifted
   from C.4's and nothing downstream should be trusted.
4. Compare the expanded matched-missed population's prenorm_var / postnorm_mean_abs_llr
   against a matched-hit control population drawn from the SAME K=4/cap2000 capture (all
   decoded=1 pass-0 candidates on the same cycles), score-banded exactly as C.2 Sec.4 did.
5. Re-check C.2 Sec.6's floor/clamp-infeasibility finding (matched-hit population's own
   minimum sits BELOW matched-missed population's minimum) against this larger sample.

ASCII-only console output per HK-009. NFR-021: this corpus contains real off-air
callsigns (public FT8 CQ/QSO traffic); this script only reports aggregate statistics,
never quotes an individual callsign/message, and all inputs/outputs live under the
git-ignored artefacts/ tree.
"""
from __future__ import annotations

import csv
import os
import re
import statistics as st
import sys
from math import isfinite

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from scipy.stats import mannwhitneyu
except ImportError:
    mannwhitneyu = None

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "artefacts", "20260725_live_run_1806")
WSJTX_ALL_TXT = os.path.join(BASE, "wsjt-x", "ALL.TXT")
WAV68_DIR     = os.path.join(BASE, "owsfz", "wav68")

# The 648 population's frozen ORIGIN (C.2 Phase 1, owsfz audio, K10/cap140) -- identical
# to c4_min_score_sweep_analysis.py's compute_648_population() inputs. This identity does
# not change just because a different candidate set is being probed.
C2_MINE_ALL_TXT = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "ALL.TXT")
C2_DIAG_CSV     = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "candidate_diag.csv")

# The K=4/cap2000 candidate set Phase 2a probes -- least-confounded, highest-recovery
# C.4 setting (dev-task Sec.2), already committed with C.2's --candidate-diag-csv fields.
K4_DIAG_CSV = os.path.join(BASE, "c4_min_score", "k4_cap2000", "k10_c0.10_n60", "candidate_diag.csv")
K4_ALL_TXT  = os.path.join(BASE, "c4_min_score", "k4_cap2000", "k10_c0.10_n60", "ALL.TXT")
# The ruling's own Delta-matched is relative to the K=10/cap=600 BASELINE (wsjt-x audio,
# same audio source as K=4/cap2000), not relative to C.2 Phase 1's original owsfz-audio
# identity run. The two audio sources already differ by ~0.5% (dev-task Sec.3's own
# capture-chain note), so the correct apples-to-apples self-check re-derives that same
# baseline-relative delta, restricted to the 648 population, rather than comparing an
# absolute count against a population identity built from a DIFFERENT audio source.
K10_BASELINE_ALL_TXT = os.path.join(BASE, "c4_min_score", "k10", "k10_c0.10_n60", "ALL.TXT")

# Same tolerances C.2/C.3/C.4 all used (one FT8 tone spacing (6.25 Hz) plus slop for two
# independent frequency estimators; dt is a secondary discriminator only).
FREQ_TOL_HZ = 10.0
DT_TOL_S = 0.5

# The Architect's ruling's own independently-measured Delta-matched for K=4/cap2000
# (2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md Sec.2 table) --
# the self-check target for step 3. Not a hard equality (that ruling's "matched" is over
# ALL of WSJT-X's 2028 messages, not just the 648; a handful could come from the separate
# ~10-message "near decoded" population instead) -- but this script's matched-decoded
# count must land in the same small neighbourhood, or the matching logic has diverged.
RULING_K4_CAP2000_DELTA_MATCHED = 2
SELF_CHECK_TOLERANCE = 5  # absolute messages either side before flagging a divergence

_HASH_BRACKET_RE = re.compile(r"<[^>]*>")


def normalize_hash_tokens(message: str) -> str:
    """Canonicalize angle-bracketed hash-callsign tokens (see score_recall.py / C.2 for
    the full rationale -- session-scoped hash-table order-dependence)."""
    return _HASH_BRACKET_RE.sub("<HASH>", message)


def parse_all_txt(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            tok = line.split()
            if len(tok) < 8:
                print(f"[WARN] unparsable ALL.TXT line in {path}: {line!r}", file=sys.stderr)
                continue
            ts, snr, dt, freq, message = tok[0], tok[4], tok[5], tok[6], " ".join(tok[7:])
            rows.append({"ts": ts, "snr": float(snr), "dt": float(dt),
                         "freq": float(freq), "message": message})
    return rows


def load_candidate_diag(path: str) -> dict[str, list[dict]]:
    by_cycle: dict[str, list[dict]] = {}
    with open(path, newline="", encoding="ascii", errors="replace") as fh:
        for row in csv.DictReader(fh):
            rec = {
                "freq_hz": float(row["freq_hz"]),
                "dt": float(row["dt"]),
                "score": int(row["score"]),
                "decoded": row["decoded"] == "1",
                "prenorm_var": float(row["prenorm_var"]),
                "postnorm_mean_abs_llr": float(row["postnorm_mean_abs_llr"]),
            }
            by_cycle.setdefault(row["cycle_ts"], []).append(rec)
    return by_cycle


def has_any_candidate_nearby(freq: float, dt: float, cands: list[dict]) -> bool:
    for c in cands:
        if abs(c["freq_hz"] - freq) <= FREQ_TOL_HZ and abs(c["dt"] - dt) <= DT_TOL_S:
            return True
    return False


def nearest_candidate(freq: float, dt: float, cands: list[dict]) -> dict | None:
    """Nearest-by-frequency candidate within tolerance, irrespective of decoded status --
    step 2 needs to know WHICH candidate (decoded or not) sits nearest, not just whether
    one exists."""
    best, best_fd = None, None
    for c in cands:
        fd = abs(c["freq_hz"] - freq)
        dd = abs(c["dt"] - dt)
        if fd <= FREQ_TOL_HZ and dd <= DT_TOL_S:
            if best is None or fd < best_fd:
                best, best_fd = c, fd
    return best


def compute_648_population(cycles: list[str]) -> list[dict]:
    """Reproduces c3_candidate_generation_gap_analysis.py's Step 1 / c4's
    compute_648_population() exactly, against the frozen C.2 Phase 1 (owsfz-audio)
    artefacts -- the fixed population Phase 2a re-derives a ceiling for."""
    wsjtx_rows = parse_all_txt(WSJTX_ALL_TXT)
    wsjtx_by_cycle: dict[str, list[dict]] = {}
    cycle_set = set(cycles)
    for r in wsjtx_rows:
        if r["ts"] in cycle_set:
            wsjtx_by_cycle.setdefault(r["ts"], []).append(r)

    mine_rows = parse_all_txt(C2_MINE_ALL_TXT)
    mine_msgset_by_cycle: dict[str, set[str]] = {}
    for r in mine_rows:
        key = normalize_hash_tokens(r["message"])
        mine_msgset_by_cycle.setdefault(r["ts"], set()).add(key)

    cand_by_cycle = load_candidate_diag(C2_DIAG_CSV)

    no_candidate_anywhere: list[dict] = []
    matched_missed_failed = 0
    near_decoded = 0
    shared_hit = 0

    for ts in cycles:
        my_msgs = mine_msgset_by_cycle.get(ts, set())
        cands = cand_by_cycle.get(ts, [])
        failed_cands = [c for c in cands if not c["decoded"]]
        decoded_cands = [c for c in cands if c["decoded"]]

        for row in wsjtx_by_cycle.get(ts, []):
            key = normalize_hash_tokens(row["message"])
            if key in my_msgs:
                shared_hit += 1
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], failed_cands):
                matched_missed_failed += 1
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], decoded_cands):
                near_decoded += 1
                continue
            no_candidate_anywhere.append({**row, "ts": ts})

    print("648-population re-derivation (from C.2 Phase 1 owsfz-audio artefacts):")
    print(f"  shared_hit={shared_hit} matched_missed_failed={matched_missed_failed} "
          f"near_decoded={near_decoded} no_candidate_anywhere={len(no_candidate_anywhere)}")
    print("  (C.3/C.4 findings both report 1235 / 135 / 10 / 648 respectively -- expect "
          "exact agreement, same script logic against the same frozen artefacts.)")
    return no_candidate_anywhere


def stats(label: str, vals: list[float]) -> None:
    vals = sorted(v for v in vals if isfinite(v))
    if not vals:
        print(f"  {label}: no finite values")
        return
    n = len(vals)
    print(f"  {label}: n={n} median={st.median(vals):.4f} mean={st.mean(vals):.4f} "
          f"q1={vals[n // 4]:.4f} q3={vals[(3 * n) // 4]:.4f} "
          f"min={vals[0]:.4f} max={vals[-1]:.4f}")


def mwu(label: str, a: list[float], b: list[float], a_name: str, b_name: str) -> None:
    a = [v for v in a if isfinite(v)]
    b = [v for v in b if isfinite(v)]
    if mannwhitneyu is None:
        print(f"  [WARN] scipy not available -- skipping Mann-Whitney U for {label}.")
        return
    if len(a) < 5 or len(b) < 5:
        print(f"  {label}: too few samples for a test ({a_name} n={len(a)}, {b_name} n={len(b)})")
        return
    u, p = mannwhitneyu(a, b, alternative="two-sided")
    direction = f"{a_name} LOWER" if st.median(a) < st.median(b) else f"{a_name} HIGHER or EQUAL"
    print(f"  {label}: U={u:.1f} p={p:.6g}  ({direction} than {b_name})")


def main() -> None:
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(WAV68_DIR) if f.endswith(".wav"))
    print(f"corpus: {len(cycles)} cycles (owsfz/wsjt-x filename intersection)\n")

    population_648 = compute_648_population(cycles)
    print()

    k4_cand_by_cycle = load_candidate_diag(K4_DIAG_CSV)
    k4_msgset_by_cycle: dict[str, set[str]] = {}
    for r in parse_all_txt(K4_ALL_TXT):
        k4_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))
    k10_baseline_msgset_by_cycle: dict[str, set[str]] = {}
    for r in parse_all_txt(K10_BASELINE_ALL_TXT):
        k10_baseline_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    # ── Step 2: classify each of the 648 against the K=4/cap2000 candidate set ──────────
    still_no_candidate: list[dict] = []
    matched_decoded: list[dict] = []      # step 3 self-check population
    expanded_matched_missed: list[dict] = []  # step 3/4: the population this script exists for

    for row in population_648:
        cands = k4_cand_by_cycle.get(row["ts"], [])
        found = nearest_candidate(row["freq"], row["dt"], cands)
        if found is None:
            still_no_candidate.append(row)
        elif found["decoded"]:
            matched_decoded.append({**found, "ts": row["ts"], "_src_row": row})
        else:
            expanded_matched_missed.append({**found, "ts": row["ts"], "_src_row": row})

    n648 = len(population_648)
    print(f"K=4/cap2000 classification of the {n648}-message candidate-generation-gap population:")
    print(f"  still no candidate anywhere within tolerance : {len(still_no_candidate)} "
          f"({100.0 * len(still_no_candidate) / max(1, n648):.1f}%)")
    print(f"  matched a DECODED candidate (self-check pop.) : {len(matched_decoded)} "
          f"({100.0 * len(matched_decoded) / max(1, n648):.1f}%)")
    print(f"  matched a FAILED candidate (expanded pop.)    : {len(expanded_matched_missed)} "
          f"({100.0 * len(expanded_matched_missed) / max(1, n648):.1f}%)")
    print(f"  (C.4's own recov648 for k4_cap2000 reports 95.4% gaining ANY candidate -- "
          f"expect {len(matched_decoded) + len(expanded_matched_missed)}/{n648} = "
          f"{100.0 * (len(matched_decoded) + len(expanded_matched_missed)) / max(1, n648):.1f}% here "
          f"to be in close agreement.)")

    # ── Step 3: self-check against the ruling's own +2 ──────────────────────────────────
    # "matched a DECODED candidate" (freq/dt proximity, above) is a WEAKER test than the
    # ruling's own "matched" metric: candidate_diag.csv's decoded=1 flag says A candidate
    # near that frequency/time decoded SOMETHING, not that it decoded THIS specific
    # WSJT-X message. A stronger, directly comparable check re-derives c4_matched_decode_
    # verification.py's own methodology (exact hash-normalized message-TEXT intersection,
    # not frequency proximity) restricted to just the 648 population, against K=4/cap2000's
    # own committed ALL.TXT.
    text_matched = [row for row in population_648
                    if normalize_hash_tokens(row["message"]) in k4_msgset_by_cycle.get(row["ts"], set())]
    text_matched_baseline = [row for row in population_648
                              if normalize_hash_tokens(row["message"])
                              in k10_baseline_msgset_by_cycle.get(row["ts"], set())]
    print(f"\n[SELF-CHECK] freq/dt-proximity \"matched a decoded candidate\" count = "
          f"{len(matched_decoded)} (weaker test -- does not confirm the decoded candidate's "
          f"message equals the target WSJT-X message).")
    print(f"[SELF-CHECK] exact message-TEXT match against K=4/cap2000's own ALL.TXT, restricted "
          f"to the 648 population = {len(text_matched)} (absolute count, same audio source as "
          f"the ruling's own verification but NOT yet baseline-relative).")
    print(f"[SELF-CHECK] same exact match against the K=10/cap=600 BASELINE's own ALL.TXT (same "
          f"wsjt-x audio source, no K_MIN_SCORE/cap change), restricted to the 648 population = "
          f"{len(text_matched_baseline)} -- this is the quantity the ruling's own Delta-matched "
          f"is relative TO, not the C.2 Phase 1 owsfz-audio identity run (which already differs "
          f"from wsjt-x audio by the ~0.5% capture-chain gap the dev-task's Sec.3 flags).")
    baseline_relative_delta = len(text_matched) - len(text_matched_baseline)
    print(f"  baseline-relative delta (the apples-to-apples number) = "
          f"{len(text_matched)} - {len(text_matched_baseline)} = {baseline_relative_delta:+d}")
    delta = baseline_relative_delta - RULING_K4_CAP2000_DELTA_MATCHED
    print(f"  ruling's own independently-measured Delta-matched for K=4/cap2000 (over all of "
          f"WSJT-X's 2028 messages) = {RULING_K4_CAP2000_DELTA_MATCHED} "
          f"(2026-07-26-1700-architect-c4-ruling... Sec.2 table). Difference = {delta:+d}.")
    if abs(delta) > SELF_CHECK_TOLERANCE:
        print(f"[SELF-CHECK FAILED] Baseline-relative delta differs from the ruling's own count by "
              f"more than +/-{SELF_CHECK_TOLERANCE} messages -- this script's matching logic has "
              f"diverged from C.4's own verification. DO NOT TRUST the LLR comparison below until "
              f"this is resolved.")
    else:
        print(f"[SELF-CHECK OK] Baseline-relative delta is within +/-{SELF_CHECK_TOLERANCE} "
              f"messages of the ruling's own count (the small residual is expected -- the "
              f"ruling's +2 is measured over all of WSJT-X's 2028 messages and could include a "
              f"message from the separate ~10-message \"near decoded\" population instead of the "
              f"648). Proceeding.")
    print(f"  (The gap between the freq/dt count ({len(matched_decoded)}) and the absolute "
          f"text-match count ({len(text_matched)}) is itself informative: most candidates that "
          f"exist near a missed message's frequency/time and show decoded=1 are decoding a "
          f"DIFFERENT message -- almost certainly the stronger co-channel signal C.3 already "
          f"showed these messages sit near -- not recovering the target message itself. Separately, "
          f"{len(text_matched_baseline)} of the 648 already text-match at the UNCHANGED K=10/"
          f"cap=600 baseline purely from the owsfz-vs-wsjt-x audio-source switch -- this is the "
          f"capture-chain effect, not a K_MIN_SCORE effect, and is why the raw absolute count is "
          f"not directly comparable to the ruling's Delta-matched.)")

    # Belt-and-braces: nearest_candidate() picks the CLOSEST-by-frequency candidate, which
    # is not always the one that actually decoded the target message when several sit
    # within tolerance of each other. Drop any row whose SOURCE WSJT-X message text-
    # matched (i.e. really was recovered, per the exact check above) from the expanded
    # matched-missed population before the LLR comparison -- each row still carries its
    # originating population_648 record in "_src_row", so this exclusion is exact, not
    # a frequency-proximity approximation.
    text_matched_row_ids = {id(row) for row in text_matched}
    before = len(expanded_matched_missed)
    expanded_matched_missed = [m for m in expanded_matched_missed
                                if id(m["_src_row"]) not in text_matched_row_ids]
    dropped = before - len(expanded_matched_missed)
    if dropped:
        print(f"\n[NOTE] dropped {dropped} row(s) from the expanded matched-missed population "
              f"whose source WSJT-X message text-matched K=4/cap2000's own ALL.TXT (i.e. was "
              f"genuinely recovered via a different, non-nearest candidate) -- "
              f"{before} -> {len(expanded_matched_missed)}.")

    if not expanded_matched_missed:
        print("\n[VERDICT] Empty expanded matched-missed population -- cannot reach a verdict.")
        return

    # ── Step 4: score-banded LLR comparison, expanded matched-missed vs. matched-hit ────
    expanded_cycles = {m["ts"] for m in expanded_matched_missed}
    hit_pop = [c for ts in expanded_cycles for c in k4_cand_by_cycle.get(ts, []) if c["decoded"]]
    print(f"\nexpanded matched-missed population : n={len(expanded_matched_missed)} "
          f"(across {len(expanded_cycles)} cycles)")
    print(f"matched-hit population (K=4/cap2000): n={len(hit_pop)} "
          f"(all decoded=1 candidates on those same {len(expanded_cycles)} cycles)")

    if not hit_pop:
        print("\n[VERDICT] Empty matched-hit control population -- cannot reach a verdict.")
        return

    print("\n-- score (sync score, uncontrolled) --")
    stats("expanded matched-missed", [c["score"] for c in expanded_matched_missed])
    stats("matched-hit            ", [c["score"] for c in hit_pop])

    print("\n-- prenorm_var (raw, uncontrolled for score) --")
    stats("expanded matched-missed", [c["prenorm_var"] for c in expanded_matched_missed])
    stats("matched-hit            ", [c["prenorm_var"] for c in hit_pop])

    print("\n-- postnorm_mean_abs_llr (raw, uncontrolled for score) --")
    stats("expanded matched-missed", [c["postnorm_mean_abs_llr"] for c in expanded_matched_missed])
    stats("matched-hit            ", [c["postnorm_mean_abs_llr"] for c in hit_pop])

    print("\n-- Mann-Whitney U (two-sided; raw populations, uncontrolled for score) --")
    for label, key in [("prenorm_var", "prenorm_var"), ("postnorm_mean_abs_llr", "postnorm_mean_abs_llr")]:
        mwu(label, [c[key] for c in expanded_matched_missed], [c[key] for c in hit_pop],
            "expanded matched-missed", "matched-hit")

    # ── Score-banded breakdown (the sync-score-controlled comparison, C.2 Sec.4's test) ─
    print("\n-- score-banded comparison (bands of width 10) --")
    print("score_band |  n_missed | med_prenorm_var(missed) | med_postnorm(missed) "
          "|  n_hit | med_prenorm_var(hit) | med_postnorm(hit)")
    print("-----------+-----------+--------------------------+-----------------------"
          "+--------+-----------------------+-------------------")
    all_scores = [c["score"] for c in expanded_matched_missed] + [c["score"] for c in hit_pop]
    lo_band = (min(all_scores) // 10) * 10
    hi_band = (max(all_scores) // 10) * 10
    band = lo_band
    band_results = []
    while band <= hi_band:
        band_missed = [c for c in expanded_matched_missed if band <= c["score"] < band + 10]
        band_hit = [c for c in hit_pop if band <= c["score"] < band + 10]
        if band_missed or band_hit:
            mv = [c["prenorm_var"] for c in band_missed if isfinite(c["prenorm_var"])]
            mp = [c["postnorm_mean_abs_llr"] for c in band_missed if isfinite(c["postnorm_mean_abs_llr"])]
            hv = [c["prenorm_var"] for c in band_hit if isfinite(c["prenorm_var"])]
            hp = [c["postnorm_mean_abs_llr"] for c in band_hit if isfinite(c["postnorm_mean_abs_llr"])]
            print("  [%3d,%3d) | %9d | %24s | %21s | %6d | %21s | %17s"
                  % (band, band + 10, len(band_missed),
                     ("%.2f" % st.median(mv)) if mv else "n/a",
                     ("%.3f" % st.median(mp)) if mp else "n/a",
                     len(band_hit),
                     ("%.2f" % st.median(hv)) if hv else "n/a",
                     ("%.3f" % st.median(hp)) if hp else "n/a"))
            if mv and hv:
                band_results.append((band, st.median(mv) < st.median(hv)))
        band += 10

    n_bands_lower = sum(1 for _, lower in band_results if lower)
    print(f"\n  bands where missed median prenorm_var < hit median prenorm_var: "
          f"{n_bands_lower}/{len(band_results)}")

    # ── Finer-grained (width=1) score breakdown -- width-10 bands are C.2 Phase 1's own
    # convention, calibrated to a population spread across score 10-40+. This expanded
    # population is concentrated almost entirely in a single width-10 bin (K_MIN_SCORE=4
    # admits scores as low as 4-9), so that bin alone is too coarse to "control for score"
    # in any meaningful sense -- it would silently average away exactly the resolution this
    # comparison needs. Re-run the same comparison at width=1 over the range that actually
    # contains the bulk of the expanded population.
    dominant_lo = int(min(c["score"] for c in expanded_matched_missed))
    dominant_hi = int(max(c["score"] for c in expanded_matched_missed))
    print(f"\n-- finer-grained (width=1) score comparison, score in [{dominant_lo},{dominant_hi}] "
          f"(the expanded population's own full range -- the resolution the width-10 table above "
          f"cannot provide) --")
    print("score |  n_missed | med_prenorm_var(missed) | med_postnorm(missed) "
          "|  n_hit | med_prenorm_var(hit) | med_postnorm(hit)")
    print("------+-----------+--------------------------+-----------------------"
          "+--------+-----------------------+-------------------")
    fine_results = []
    for s in range(dominant_lo, dominant_hi + 1):
        band_missed = [c for c in expanded_matched_missed if c["score"] == s]
        band_hit = [c for c in hit_pop if c["score"] == s]
        if not band_missed and not band_hit:
            continue
        mv = [c["prenorm_var"] for c in band_missed if isfinite(c["prenorm_var"])]
        mp = [c["postnorm_mean_abs_llr"] for c in band_missed if isfinite(c["postnorm_mean_abs_llr"])]
        hv = [c["prenorm_var"] for c in band_hit if isfinite(c["prenorm_var"])]
        hp = [c["postnorm_mean_abs_llr"] for c in band_hit if isfinite(c["postnorm_mean_abs_llr"])]
        print("  %3d | %9d | %24s | %21s | %6d | %21s | %17s"
              % (s, len(band_missed),
                 ("%.2f" % st.median(mv)) if mv else "n/a",
                 ("%.3f" % st.median(mp)) if mp else "n/a",
                 len(band_hit),
                 ("%.2f" % st.median(hv)) if hv else "n/a",
                 ("%.3f" % st.median(hp)) if hp else "n/a"))
        if mv and hv:
            fine_results.append((s, len(band_missed), st.median(mv) < st.median(hv)))

    n_weighted_lower = sum(n for _, n, lower in fine_results if lower)
    n_weighted_total = sum(n for _, n, _ in fine_results)
    print(f"\n  fine-grained scores where missed median prenorm_var < hit median prenorm_var: "
          f"{sum(1 for _, _, lower in fine_results if lower)}/{len(fine_results)} distinct scores, "
          f"covering {n_weighted_lower}/{max(1, n_weighted_total)} missed candidates "
          f"({100.0 * n_weighted_lower / max(1, n_weighted_total):.1f}% of the population that has "
          f"a same-score hit control at all).")

    # ── Score-overlap-restricted Mann-Whitney (stricter control, same as C.2) ───────────
    missed_scores = [c["score"] for c in expanded_matched_missed]
    hit_scores = [c["score"] for c in hit_pop]
    overlap_lo = max(min(missed_scores), min(hit_scores))
    overlap_hi = min(max(missed_scores), max(hit_scores))
    r_missed = [c for c in expanded_matched_missed if overlap_lo <= c["score"] <= overlap_hi]
    r_hit = [c for c in hit_pop if overlap_lo <= c["score"] <= overlap_hi]
    print(f"\n-- score-overlap-restricted comparison (score in [{overlap_lo},{overlap_hi}], "
          f"n_missed={len(r_missed)}, n_hit={len(r_hit)}) --")
    stats("expanded matched-missed prenorm_var", [c["prenorm_var"] for c in r_missed])
    stats("matched-hit             prenorm_var", [c["prenorm_var"] for c in r_hit])
    stats("expanded matched-missed postnorm   ", [c["postnorm_mean_abs_llr"] for c in r_missed])
    stats("matched-hit             postnorm   ", [c["postnorm_mean_abs_llr"] for c in r_hit])
    for label, key in [("prenorm_var", "prenorm_var"), ("postnorm_mean_abs_llr", "postnorm_mean_abs_llr")]:
        mwu(f"[score-overlap] {label}", [c[key] for c in r_missed], [c[key] for c in r_hit],
            "expanded matched-missed", "matched-hit")

    # ── Step 5: re-check C.2 Sec.6's floor/clamp-infeasibility finding ──────────────────
    missed_var = [c["prenorm_var"] for c in expanded_matched_missed if isfinite(c["prenorm_var"])]
    hit_var = [c["prenorm_var"] for c in hit_pop if isfinite(c["prenorm_var"])]
    print("\n-- floor/clamp-infeasibility re-check (C.2 Sec.6) --")
    if missed_var and hit_var:
        missed_min, hit_min = min(missed_var), min(hit_var)
        print(f"  expanded matched-missed prenorm_var min = {missed_min:.4f}")
        print(f"  matched-hit             prenorm_var min = {hit_min:.4f}")
        if hit_min < missed_min:
            print("  -> matched-hit's own minimum sits BELOW matched-missed's minimum, same as "
                  "C.2 Sec.6's original 135-message finding: populations overlap across the whole "
                  "range, a naive floor/clamp would not separate them at this larger sample either.")
        else:
            print("  -> matched-hit's minimum no longer sits below matched-missed's minimum at "
                  "this larger sample -- C.2 Sec.6's floor/clamp-infeasibility conclusion does NOT "
                  "hold unchanged here and should be re-examined before Phase 2b design assumes it.")

    # ── Decisive verdict, per dev-task Sec.2 ────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("VERDICT (dev-task 2026-07-26-d001-c2-phase2-llr-shrinkage.md Sec.2 decision rule)")
    print("=" * 78)
    missed_med_var = st.median(missed_var) if missed_var else float("nan")
    hit_med_var = st.median(hit_var) if hit_var else float("nan")
    missed_post = [c["postnorm_mean_abs_llr"] for c in expanded_matched_missed if isfinite(c["postnorm_mean_abs_llr"])]
    hit_post = [c["postnorm_mean_abs_llr"] for c in hit_pop if isfinite(c["postnorm_mean_abs_llr"])]
    missed_med_post = st.median(missed_post) if missed_post else float("nan")
    hit_med_post = st.median(hit_post) if hit_post else float("nan")
    print(f"  median prenorm_var            : missed={missed_med_var:.3f} hit={hit_med_var:.3f}")
    print(f"  median postnorm_mean_abs_llr   : missed={missed_med_post:.3f} hit={hit_med_post:.3f}")
    print(f"  width-10 score-banded: missed < hit prenorm_var in {n_bands_lower}/{len(band_results)} bands")
    print(f"  width-1 fine-grained : missed < hit prenorm_var for "
          f"{n_weighted_lower}/{max(1, n_weighted_total)} candidates "
          f"({100.0 * n_weighted_lower / max(1, n_weighted_total):.1f}%) at their own exact score "
          f"-- THIS is the real score-controlled test for a population concentrated in one "
          f"width-10 bin; the width-10 row alone would have overstated the control.")
    print(f"  population size: n={len(expanded_matched_missed)} (vs. C.2 Phase 1's original 135)")
    print()
    print("  Read the printed medians, Mann-Whitney p-values, and score-banded table above")
    print("  and record the verdict explicitly in the findings doc: does the expanded")
    print("  population show the same weak-LLR signature (lower prenorm_var/postnorm_")
    print("  mean_abs_llr than matched-hit, surviving score-banding, same direction/rough")
    print("  magnitude as the original 135-message result) -- ceiling revised upward, up to")
    print("  ~%d messages -- or is there no consistent signature / a materially weaker one --"
          % len(expanded_matched_missed))
    print("  ceiling stays bounded near the original 135. This script prints the evidence;")
    print("  per the dev-task, do not leave the call ambiguous in the findings doc.")


if __name__ == "__main__":
    main()
