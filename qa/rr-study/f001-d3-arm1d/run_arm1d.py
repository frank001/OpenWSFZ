#!/usr/bin/env python3
"""F-001 D3 ARM 1D -- the unique-match trade, measured with BOUNDS instead of
a FILTER.

Spec: qa/rr-study/2026-08-26-1743-architect-to-qa-spec-f001-d3-arm1d-unique-match-trade-bounded.md

This is a NEW pre-registration, not a re-run of ARM 1C and not ARM 1C with
Sec.3.2 deleted. ARM 1C is VOID at ROW 0d and stays VOID -- its gates were
never computed and nothing here is read against them.

Per Sec.0.2 (HK-021(p)): no unique-match binary exists or is authorised, so
this arm measures NO treatment. It measures a property of the build we
already ran -- of the names it printed on the 12-bit path, how many were
AMBIGUOUS at print time. No row and no line of this script's output may be
read as "the fixed build would...".

All 243 decodes enter. The 37 whose replay does not reproduce the printed
name are labelled UNKNOWN (never filtered out) and their ambiguity is
assigned ADVERSARIALLY in both directions, producing an INTERVAL rather than
a point. Sec.3.4: each row's own claim is tested against the assignment
LEAST FAVOURABLE to that claim; rescued_min/lost_max are per-quantity
partial-identification bounds from DIFFERENT passes, never one joint world.

Pure re-analysis of dumps already on disk (no rebuild, no replay, no capture,
no src/ or native/ edit -- Sec.8). Reuses common_arm1b.py / run_arm1b.py /
common_arm1c.py unmodified (Sec.2). The only new code is common_arm1d.py's
Sec.3 four functions (shipped verbatim, HK-021(r)) and the two-pass
adversarial driver below.

NFR-021: real callsign strings and message text live in memory only.
result.json / run.log / the report carry only counts, cycle timestamps,
frequencies, and sha256[:6]-redacted CS-xxxxxx tokens (common_arm1d.redact).

Usage:
    python run_arm1d.py --out-dir <dir>          # normal run, writes result.json/run.log
    python run_arm1d.py --emit-core-json         # ROW 0f worker mode: prints the
                                                  # deterministic result dict as one
                                                  # line of sort_keys JSON, nothing else
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_arm1d as C   # noqa: E402
import common_arm1 as A    # noqa: E402
import common_b1 as B      # noqa: E402
import run_arm1b as R1B    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# Two arbitrary, fixed, DIFFERENT seeds for ROW 0f's out-of-process check.
# Neither is "the" seed of any other run in this study -- the row only
# claims that two fresh processes under two different seeds agree.
HASHSEED_A = "11111"
HASHSEED_B = "999983"


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, check=True,
                               cwd=C.REPO_ROOT).stdout.strip()
    except Exception:
        return "unknown"


# =============================================================================
# Core analysis -- deterministic given the on-disk dumps. Called both by the
# normal run and by --emit-core-json (ROW 0f's out-of-process worker).
# =============================================================================
def compute_all(log):
    void_rows = []

    def void(row, reason):
        void_rows.append((row, reason))
        log("  -> VOID at ROW %s: %s" % (row, reason))

    log("Loading decode dumps + reference ALL.TXT (no rebuild, no replay)...")
    l2run1_dump, ours_rows_1 = C.load_l2run1_ours_rows()
    theirs_rows = C.load_theirs_rows()

    # ---------------- ROW 0a: input identity --------------------------------
    log("-" * 78); log("ROW 0a -- input identity")
    ident1 = B.check_dump_identity(l2run1_dump)
    ok0a = (ident1["dll_sha256"] == C.EXPECTED_L2_SHA256
            and ident1["shim_version"] == C.EXPECTED_L2_SHIM_VERSION
            and ident1["n_decodes"] == C.EXPECTED_N_DECODES
            and ident1["n_records"] == C.EXPECTED_N_DECODES
            and len(theirs_rows) == C.EXPECTED_N_THEIRS_ROWS)
    log("  L2_run1: %s ; reference rows=%d (expect %d)" % (ident1, len(theirs_rows), C.EXPECTED_N_THEIRS_ROWS))
    log("  ROW 0a: %s" % ("PASS" if ok0a else "FAIL"))
    if not ok0a:
        void("0a", "input identity does not match the pinned spec inputs")
        return {"row0": {"0a": "VOID"}}, void_rows

    stream = C.sorted_stream(ours_rows_1)
    theirs_index = C.build_theirs_index(theirs_rows)

    # ---------------- ROW 0b: population + label reproduction --------------
    log("-" * 78); log("ROW 0b -- population + label reproduction (REPRODUCTION row, not discovery)")
    ours_pairs, resolved_both, coverage = R1B.build_part_a(ours_rows_1, theirs_index)
    kept_pairs, n_disagree_total, n_dropped = R1B.apply_row0d(resolved_both)
    k_arm1b = len(kept_pairs)
    by_cs: dict = {}
    for p in kept_pairs:
        by_cs.setdefault(p["o_payload"], []).append(p)
    n_arm1b = len(by_cs)
    n_disagree_pairs = sum(1 for p in kept_pairs if p["disagree"])
    log("  ARM 1B reproduction: k=%d (expect %d) n=%d (expect %d) disagreeing=%d (expect %d)"
        % (k_arm1b, C.EXPECTED_ARM1B_K, n_arm1b, C.EXPECTED_ARM1B_N_CS,
           n_disagree_pairs, C.EXPECTED_ARM1B_N_DISAGREE_PAIRS))
    arm1b_exact = (k_arm1b == C.EXPECTED_ARM1B_K and n_arm1b == C.EXPECTED_ARM1B_N_CS
                   and n_disagree_pairs == C.EXPECTED_ARM1B_N_DISAGREE_PAIRS)
    if not arm1b_exact:
        void("0b", "ARM 1B's own pairing did not reproduce exactly -- reused helpers moved")
        return {"row0": {"0a": "PASS", "0b": "VOID"}}, void_rows

    # Sec.0.3: NO fidelity filter -- every one of the 243 decodes enters.
    leg, _ = C.run_12bit_leg_c(stream, C.CUR_SIZE)
    n_in_leg = sum(1 for p in kept_pairs if C.key_of(p) in leg)
    known_flags = {C.key_of(p): C.is_known(p, leg) for p in kept_pairs}
    n_known = sum(1 for p in kept_pairs if known_flags[C.key_of(p)])
    n_unknown_disagree = sum(1 for p in kept_pairs if p["disagree"] and not known_flags[C.key_of(p)])
    n_unknown_agree = sum(1 for p in kept_pairs if not p["disagree"] and not known_flags[C.key_of(p)])

    rowc_units_list = C.rowc_units(by_cs)
    rowd_units_list = C.rowd_units(by_cs)
    n_rowc = len(rowc_units_list)
    n_rowd = len(rowd_units_list)

    log("  all decodes present in the leg: %d/%d (expect %d/%d)" % (n_in_leg, k_arm1b, C.EXPECTED_N_IN_LEG, k_arm1b))
    log("  KNOWN=%d (expect %d) ; UNKNOWN disagreeing=%d (expect %d) agreeing=%d (expect %d)"
        % (n_known, C.EXPECTED_KNOWN, n_unknown_disagree, C.EXPECTED_UNKNOWN_DISAGREE,
           n_unknown_agree, C.EXPECTED_UNKNOWN_AGREE))
    log("  ROW C units=%d (expect %d) ; ROW D units=%d (expect %d)"
        % (n_rowc, C.EXPECTED_ROWC_UNITS, n_rowd, C.EXPECTED_ROWD_UNITS))
    ok0b = (n_in_leg == C.EXPECTED_N_IN_LEG and n_known == C.EXPECTED_KNOWN
            and n_unknown_disagree == C.EXPECTED_UNKNOWN_DISAGREE
            and n_unknown_agree == C.EXPECTED_UNKNOWN_AGREE
            and n_rowc == C.EXPECTED_ROWC_UNITS and n_rowd == C.EXPECTED_ROWD_UNITS)
    log("  ROW 0b: %s" % ("PASS" if ok0b else "FAIL"))
    if not ok0b:
        void("0b", "population/label reproduction did not match the pre-registered exposure exactly")
        return {"row0": {"0a": "PASS", "0b": "VOID"},
                "row0b_detail": {"n_in_leg": n_in_leg, "n_known": n_known,
                                  "n_unknown_disagree": n_unknown_disagree, "n_unknown_agree": n_unknown_agree,
                                  "n_rowc": n_rowc, "n_rowd": n_rowd}}, void_rows

    # ---------------- ROW 0c: predicate coherence, STRUCTURAL ONLY ---------
    # Sec.4: ARM 1C's second clause ("matches12 >= 1 wherever the real build
    # resolved") is DELETED, not moved -- it belongs to no row in this arm.
    # Only clause 1 (none <=> zero) is checked here.
    log("-" * 78); log("ROW 0c -- predicate coherence, STRUCTURAL ONLY")
    n_checked = 0
    n_coherence_fail = 0
    for v in leg.values():
        n_checked += 1
        none_iff_zero = (v["sim_name"] is None) == (v["matches12"] == 0)
        if not none_iff_zero:
            n_coherence_fail += 1
    log("  queries checked=%d ; clause1 (none<=>zero) exceptions=%d" % (n_checked, n_coherence_fail))
    ok0c = (n_coherence_fail == 0)
    log("  ROW 0c: %s (bar: 100%%, zero exceptions)" % ("PASS" if ok0c else "FAIL"))
    if not ok0c:
        void("0c", "matches12 does not walk the same chain lookup12 does")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "VOID"},
                "row0c_detail": {"n_checked": n_checked, "n_coherence_fail": n_coherence_fail}}, void_rows

    # ---------------- ROW 0d: ignorance-width reproduction -----------------
    log("-" * 78); log("ROW 0d -- ignorance-width reproduction")
    rowc_by_cs = {cs: ps for cs, ps in by_cs.items() if cs in set(rowc_units_list)}
    rowd_by_cs = {cs: ps for cs, ps in by_cs.items() if cs in set(rowd_units_list)}
    c_unknown_units = sum(1 for cs, ps in rowc_by_cs.items()
                           if any(not known_flags[C.key_of(q)] for q in ps if q["disagree"]))
    d_unknown_units = sum(1 for cs, ps in rowd_by_cs.items()
                           if any(not known_flags[C.key_of(q)] for q in ps))
    log("  ROW C units carrying an UNKNOWN disagreeing decode = %d (expect %d)"
        % (c_unknown_units, C.EXPECTED_ROWC_UNKNOWN_UNITS))
    log("  ROW D units carrying any UNKNOWN decode            = %d (expect %d)"
        % (d_unknown_units, C.EXPECTED_ROWD_UNKNOWN_UNITS))
    ok0d = (c_unknown_units == C.EXPECTED_ROWC_UNKNOWN_UNITS and d_unknown_units == C.EXPECTED_ROWD_UNKNOWN_UNITS)
    log("  ROW 0d: %s (bar: exact match)" % ("PASS" if ok0d else "FAIL"))
    if not ok0d:
        void("0d", "ignorance width did not reproduce exactly")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "VOID"},
                "row0d_detail": {"c_unknown_units": c_unknown_units, "d_unknown_units": d_unknown_units}}, void_rows

    # ---------------- ROW 0e: assignment-leak check + two-pass driver ------
    log("-" * 78); log("ROW 0e -- assignment-leak check + two-pass adversarial driver")
    n_leak = 0
    for p in kept_pairs:
        if not known_flags[C.key_of(p)]:
            continue
        if C.ambiguous(p, leg, True) != C.ambiguous(p, leg, False):
            n_leak += 1
    counts = {}
    for unknown_as in (False, True):
        rescued_n = sum(1 for cs, ps in rowc_by_cs.items() if C.is_rescued(ps, leg, unknown_as))
        lost_n = sum(1 for cs, ps in rowd_by_cs.items() if C.is_lost(ps, leg, unknown_as))
        counts[unknown_as] = (rescued_n, lost_n)
    rescued_min, lost_min = counts[False]
    rescued_max, lost_max = counts[True]
    log("  KNOWN-decode assignment-leak exceptions = %d (expect 0)" % n_leak)
    log("  rescued_min=%d (unknown_as=False) rescued_max=%d (unknown_as=True) [n=%d]"
        % (rescued_min, rescued_max, n_rowc))
    log("  lost_min=%d (unknown_as=False) lost_max=%d (unknown_as=True) [n=%d]"
        % (lost_min, lost_max, n_rowd))
    ok0e = (n_leak == 0 and rescued_min <= rescued_max and lost_min <= lost_max)
    log("  ROW 0e: %s" % ("PASS" if ok0e else "FAIL"))
    if not ok0e:
        void("0e", "assignment leak on a KNOWN decode, or bound ordering violated")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "VOID"},
                "row0e_detail": {"n_leak": n_leak, "rescued_min": rescued_min, "rescued_max": rescued_max,
                                  "lost_min": lost_min, "lost_max": lost_max}}, void_rows

    # ---------------- ROW 0g: predicate-movement exhibit (HK-021(q)) -------
    # Reused verbatim from ARM 1C's ROW 0f exhibit.
    log("-" * 78); log("ROW 0g -- predicate-movement exhibit (HK-021(q))")
    candidates = sorted(
        (p for p in kept_pairs if known_flags[C.key_of(p)] and leg[C.key_of(p)]["matches12"] == 1),
        key=lambda p: C.key_of(p),
    )
    ok0g = False
    row0g_detail = {}
    n_candidates_tried = 0
    for cand in candidates:
        n_candidates_tried += 1
        key = C.key_of(cand)
        _, snap = C.run_12bit_leg_c(stream, C.CUR_SIZE, capture_key=key)
        if snap is None:
            continue
        tbl_snapshot, n12 = snap
        before = tbl_snapshot.matches12(n12)
        n22_orig = A.n22_of(cand["o_payload"])
        low10 = n22_orig & 0x3FF
        synthetic_n22 = (n22_orig & ~0x3FF) | (low10 ^ 0x3FF)
        count_before = tbl_snapshot.count
        tbl_snapshot.add("SYNTHETIC-PROBE-ENTRY", synthetic_n22)
        inserted = tbl_snapshot.count == count_before + 1
        after = tbl_snapshot.matches12(n12)
        moved = (before == 1 and after == 2)
        if moved and inserted:
            ok0g = True
            row0g_detail = {
                "candidates_tried": n_candidates_tried,
                "original_redacted": C.redact(cand["o_payload"]),
                "matches12_before": before, "matches12_after": after,
                "unit_before": "unambiguous", "unit_after": "ambiguous",
                "synthetic_entry_inserted": inserted,
            }
            log("  worked example (candidate #%d): original=%s matches12 %d -> %d ; unit unambiguous -> ambiguous"
                % (n_candidates_tried, C.redact(cand["o_payload"]), before, after))
            break
        log("  candidate #%d (%s) did not move cleanly (before=%d after=%d inserted=%s) -- trying next"
            % (n_candidates_tried, C.redact(cand["o_payload"]), before, after, inserted))
    log("  ROW 0g: %s" % ("PASS" if ok0g else "FAIL"))
    if not ok0g:
        void("0g", "no unambiguous known query could be moved to ambiguous by injection -- classifier is not measuring anything")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "PASS", "0g": "VOID"},
                "row0g_detail": {"candidates_tried": n_candidates_tried}}, void_rows

    # ---------------- ROW 0h: stated, not gated -----------------------------
    log("-" * 78); log("ROW 0h -- stated, not gated")
    frozen_share = sum(1 for p in kept_pairs if C.key_of(p) in leg and leg[C.key_of(p)]["frozen"])
    n_sim_none_but_real_resolved = sum(1 for v in leg.values() if v["sim_name"] is None)
    log("  table-freeze exposure: %d/%d = %.1f%% of gate decodes issued AFTER the table froze (expect %d/%d)"
        % (frozen_share, k_arm1b, 100.0 * frozen_share / max(1, k_arm1b), C.EXPECTED_FROZEN_NUM, C.EXPECTED_FROZEN_DEN))
    log("  carried error channel: simulator found NOTHING where the real build resolved = %d/%d = %.1f%% (expect %d/%d)"
        % (n_sim_none_but_real_resolved, n_checked, 100.0 * n_sim_none_but_real_resolved / max(1, n_checked),
           C.EXPECTED_SIM_NONE_BUT_REAL_RESOLVED_NUM, C.EXPECTED_SIM_NONE_BUT_REAL_RESOLVED_DEN))

    row0 = {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "PASS", "0g": "PASS", "0h": "STATED"}

    # ==================== Sec.5 -- gates, interval versions ================
    log("=" * 78); log("Sec.5 -- gates, unit=callsign, interval bounds from the two-pass driver")

    # ---------------- ROW C: rescue --------------------------------------
    log("-" * 78); log("ROW C -- rescue (n=%d)" % n_rowc)
    gate_c = None
    p_rescue_min = p_rescue_max = cp_lo_min_c = cp_hi_max_c = None
    if n_rowc < 40:
        log("  n=%d < 40 -- UNDER-POWERED, no verdict (HK-021(m))" % n_rowc)
        gate_c = "UNDER-POWERED"
    else:
        p_rescue_min = rescued_min / n_rowc
        p_rescue_max = rescued_max / n_rowc
        cp_lo_min_c = C.cp_lower_one_sided(rescued_min, n_rowc)
        cp_hi_max_c = C.cp_upper_one_sided(rescued_max, n_rowc)
        log("  rescued_min=%d (%.1f%%) CP one-sided 95%% lower=%.4f  |  rescued_max=%d (%.1f%%) CP one-sided 95%% upper=%.4f"
            % (rescued_min, 100.0 * p_rescue_min, cp_lo_min_c, rescued_max, 100.0 * p_rescue_max, cp_hi_max_c))
        if cp_lo_min_c > 0.50:
            gate_c = "C1"
        elif cp_hi_max_c < 0.50:
            gate_c = "C2"
        else:
            gate_c = "C3"
        log("  -> ROW %s" % gate_c)

    # ---------------- ROW D: cost ------------------------------------------
    log("-" * 78); log("ROW D -- cost (n=%d)" % n_rowd)
    gate_d = None
    p_lost_min = p_lost_max = cp_lo_min_d = cp_hi_max_d = None
    if n_rowd < 40:
        log("  n=%d < 40 -- UNDER-POWERED, no verdict (HK-021(m))" % n_rowd)
        gate_d = "UNDER-POWERED"
    else:
        p_lost_min = lost_min / n_rowd
        p_lost_max = lost_max / n_rowd
        cp_lo_min_d = C.cp_lower_one_sided(lost_min, n_rowd)
        cp_hi_max_d = C.cp_upper_one_sided(lost_max, n_rowd)
        log("  lost_min=%d (%.1f%%) CP one-sided 95%% lower=%.4f  |  lost_max=%d (%.1f%%) CP one-sided 95%% upper=%.4f"
            % (lost_min, 100.0 * p_lost_min, cp_lo_min_d, lost_max, 100.0 * p_lost_max, cp_hi_max_d))
        if cp_lo_min_d > 0.50:
            gate_d = "D1"
        elif cp_hi_max_d < 0.50:
            gate_d = "D2"
        else:
            gate_d = "D3"
        log("  -> ROW %s" % gate_d)

    # ---------------- Sec.6: ROW E, contingency, Part B ----------------------
    log("-" * 78); log("ROW E -- post-rule agreement among survivors (descriptive, ungated, INTERVAL)")
    row_e_passes = {}
    for unknown_as in (False, True):
        ua = sum(1 for p in kept_pairs if not p["disagree"] and not C.ambiguous(p, leg, unknown_as))
        ud = sum(1 for p in kept_pairs if p["disagree"] and not C.ambiguous(p, leg, unknown_as))
        denom = ua + ud
        pe = (ua / denom) if denom else None
        row_e_passes[unknown_as] = {"unambig_agree": ua, "unambig_disagree": ud, "p": pe}
    pe_vals = [v["p"] for v in row_e_passes.values() if v["p"] is not None]
    e_lo = min(pe_vals) if pe_vals else None
    e_hi = max(pe_vals) if pe_vals else None
    log("  unknown_as=False: agree=%d disagree=%d p=%s" % (row_e_passes[False]["unambig_agree"],
        row_e_passes[False]["unambig_disagree"],
        ("%.1f%%" % (100.0 * row_e_passes[False]["p"])) if row_e_passes[False]["p"] is not None else "N/A"))
    log("  unknown_as=True : agree=%d disagree=%d p=%s" % (row_e_passes[True]["unambig_agree"],
        row_e_passes[True]["unambig_disagree"],
        ("%.1f%%" % (100.0 * row_e_passes[True]["p"])) if row_e_passes[True]["p"] is not None else "N/A"))
    log("  interval: [%s, %s]" % (("%.1f%%" % (100.0 * e_lo)) if e_lo is not None else "N/A",
                                    ("%.1f%%" % (100.0 * e_hi)) if e_hi is not None else "N/A"))
    log("  HK-021(u) -- ARM 1B baseline, SAME sentence: 62.1%% (151/243)")

    log("-" * 78)
    ceiling_unreachable = sum(1 for p in kept_pairs
                               if known_flags[C.key_of(p)] and p["disagree"] and leg[C.key_of(p)]["matches12"] == 1)
    log("Contingency -- KNOWN, matches12==1 (unique match), and WRONG: %d" % ceiling_unreachable)
    log("  (ceiling on any suppression-based remedy: the correct entry was never resident)")

    # ==================== Part B -- descriptive only, 32768 ================
    log("=" * 78); log("Part B -- multiplicity distribution at 32,768 (descriptive, NOT adjudicated)")
    leg_sz8, _ = C.run_12bit_leg_c(stream, C.SZ8_SIZE)
    n_ambig_cur = sum(1 for v in leg.values() if v["matches12"] >= 2)
    n_ambig_sz8 = sum(1 for v in leg_sz8.values() if v["matches12"] >= 2)
    log("  ambiguous share @4096 = %d/%d = %.1f%%" % (n_ambig_cur, len(leg), 100.0 * n_ambig_cur / max(1, len(leg))))
    log("  ambiguous share @32768 = %d/%d = %.1f%%" % (n_ambig_sz8, len(leg_sz8), 100.0 * n_ambig_sz8 / max(1, len(leg_sz8))))

    result = {
        "row0": row0,
        "row0b_detail": {
            "arm1b_k": k_arm1b, "arm1b_n_cs": n_arm1b, "arm1b_n_disagree_pairs": n_disagree_pairs,
            "n_in_leg": n_in_leg, "n_known": n_known,
            "n_unknown_disagree": n_unknown_disagree, "n_unknown_agree": n_unknown_agree,
            "n_rowc": n_rowc, "n_rowd": n_rowd,
        },
        "row0c_detail": {"n_checked": n_checked, "n_coherence_fail": n_coherence_fail},
        "row0d_detail": {"c_unknown_units": c_unknown_units, "d_unknown_units": d_unknown_units},
        "row0e_detail": {"n_leak": n_leak, "rescued_min": rescued_min, "rescued_max": rescued_max,
                          "lost_min": lost_min, "lost_max": lost_max},
        "row0g_detail": row0g_detail,
        "row0h_detail": {"frozen_share": frozen_share, "n_gate_decodes": k_arm1b,
                          "n_sim_none_but_real_resolved": n_sim_none_but_real_resolved, "n_checked": n_checked},
        "row_c": {
            "n": n_rowc, "rescued_min": rescued_min, "rescued_max": rescued_max,
            "p_rescue_min": p_rescue_min, "p_rescue_max": p_rescue_max,
            "cp_lower_one_sided_95_of_min": cp_lo_min_c, "cp_upper_one_sided_95_of_max": cp_hi_max_c,
            "gate": gate_c,
        },
        "row_d": {
            "n": n_rowd, "lost_min": lost_min, "lost_max": lost_max,
            "p_lost_min": p_lost_min, "p_lost_max": p_lost_max,
            "cp_lower_one_sided_95_of_min": cp_lo_min_d, "cp_upper_one_sided_95_of_max": cp_hi_max_d,
            "gate": gate_d,
        },
        "row_e": {
            "pass_unknown_as_false": row_e_passes[False], "pass_unknown_as_true": row_e_passes[True],
            "interval_lo": e_lo, "interval_hi": e_hi,
            "arm1b_baseline_p": 151 / 243, "arm1b_baseline_n": 243, "arm1b_baseline_agree": 151,
        },
        "contingency_unique_but_wrong": ceiling_unreachable,
        "part_b": {
            "cur_size": C.CUR_SIZE, "sz8_size": C.SZ8_SIZE,
            "n_ambiguous_cur": n_ambig_cur, "n_total_cur": len(leg),
            "n_ambiguous_sz8": n_ambig_sz8, "n_total_sz8": len(leg_sz8),
        },
    }
    return result, void_rows


# =============================================================================
# ROW 0f: out-of-process determinism check
# =============================================================================
def emit_core_json():
    def noop_log(_msg=""):
        pass
    result, _void = compute_all(noop_log)
    sys.stdout.write(json.dumps(result, sort_keys=True))
    sys.stdout.flush()


def run_row0f_check(script_path: str) -> tuple[bool, str, str]:
    def run_with_seed(seed: str) -> str:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        proc = subprocess.run(
            [sys.executable, script_path, "--emit-core-json"],
            capture_output=True, text=True, check=True, cwd=HERE, env=env,
        )
        return proc.stdout
    out_a = run_with_seed(HASHSEED_A)
    out_b = run_with_seed(HASHSEED_B)
    return (out_a == out_b), out_a, out_b


# =============================================================================
def finish(args, log_lines, result, void_rows):
    result_path = os.path.join(args.out_dir, "result.json")
    tmp = result_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    os.replace(tmp, result_path)
    log_path = os.path.join(args.out_dir, "run.log")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    print("=" * 78)
    print("DONE -- result: %s" % result_path)
    if void_rows:
        print("VOID at: %s" % void_rows)
    print("=" * 78)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir")
    ap.add_argument("--emit-core-json", action="store_true")
    args = ap.parse_args()

    if args.emit_core_json:
        emit_core_json()
        return 0

    if not args.out_dir:
        print("error: --out-dir is required for a normal run", file=sys.stderr)
        return 2
    os.makedirs(args.out_dir, exist_ok=True)
    log_lines = []

    def log(msg=""):
        print(msg, flush=True)
        log_lines.append(msg)

    log("=" * 78)
    log("F-001 D3 ARM 1D -- run_arm1d.py -- repo main @ %s" % git_sha())
    log("=" * 78)

    result, void_rows = compute_all(log)

    # ROW 0f is spliced in here (after 0a-0e/0g/0h succeed, before reporting)
    # rather than inside compute_all, because compute_all IS the thing being
    # checked for determinism -- it cannot check itself recursively without
    # an unbounded process tree. Same pattern as ARM 1C's ROW 0e.
    if not void_rows:
        log("-" * 78); log("ROW 0f -- determinism, OUT OF PROCESS, different PYTHONHASHSEED")
        script_path = os.path.abspath(__file__)
        det_ok, out_a, out_b = run_row0f_check(script_path)
        log("  seed A=%s seed B=%s -- result.json byte-identical: %s" % (HASHSEED_A, HASHSEED_B, det_ok))
        log("  ROW 0f: %s" % ("PASS" if det_ok else "FAIL"))
        result["row0"]["0f"] = "PASS" if det_ok else "VOID"
        result["row0f_detail"] = {"hashseed_a": HASHSEED_A, "hashseed_b": HASHSEED_B, "byte_identical": det_ok}
        if not det_ok:
            void_rows.append(("0f", "out-of-process rerun under a different PYTHONHASHSEED was not byte-identical"))
            log("  -> VOID at ROW 0f: hash-randomised-iteration hazard reproduced")

    return finish(args, log_lines, result, void_rows)


if __name__ == "__main__":
    sys.exit(main())
