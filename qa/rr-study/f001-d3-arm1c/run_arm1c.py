#!/usr/bin/env python3
"""F-001 D3 ARM 1C -- what would a unique-match rule buy, and what would it cost?

Spec: qa/rr-study/2026-08-26-1619-architect-to-qa-spec-f001-d3-arm1c-unique-match-trade.md

Per Sec.0.2 (HK-021(p)): no unique-match binary exists or is authorised, so
this arm measures NO treatment. It measures a property of the build we
already ran -- of the names it printed on the 12-bit path, how many were
AMBIGUOUS at print time. No row and no line of this script's output may be
read as "the fixed build would...".

Pure re-analysis of dumps already on disk (no rebuild, no replay, no capture,
no src/ or native/ edit -- Sec.9). Reuses common_arm1b.py / run_arm1b.py /
common_arm1.py unmodified (Sec.2; ROW 0c is the coherence check, not a reuse
assertion -- reuse itself is enforced by import, checked structurally below).

NFR-021: real callsign strings and message text live in memory only.
result.json / run.log / the report carry only counts, cycle timestamps,
frequencies, and sha256[:6]-redacted CS-xxxxxx tokens (common_arm1c.redact).

Usage:
    python run_arm1c.py --out-dir <dir>          # normal run, writes result.json/run.log
    python run_arm1c.py --emit-core-json         # ROW 0e worker mode: prints the
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

import common_arm1c as C   # noqa: E402
import common_arm1 as A    # noqa: E402
import common_b1 as B      # noqa: E402
import run_arm1b as R1B    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# Two arbitrary, fixed, DIFFERENT seeds for ROW 0e's out-of-process check.
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
# normal run and by --emit-core-json (ROW 0e's out-of-process worker).
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

    # ---------------- ROW 0b: population reproduction (load-bearing) -------
    log("-" * 78); log("ROW 0b -- population reproduction (load-bearing)")
    ours_pairs, resolved_both, coverage = R1B.build_part_a(ours_rows_1, theirs_index)
    kept_pairs, n_disagree_total, n_dropped = R1B.apply_row0d(resolved_both)
    flags, n_pairs_per_cs = R1B.callsign_flags(kept_pairs)
    k_arm1b = len(kept_pairs)
    n_arm1b = len(flags)
    n_disagree_pairs = sum(1 for p in kept_pairs if p["disagree"])
    log("  ARM 1B reproduction: k=%d (expect %d) n=%d (expect %d) disagreeing=%d (expect %d)"
        % (k_arm1b, C.EXPECTED_ARM1B_K, n_arm1b, C.EXPECTED_ARM1B_N_CS,
           n_disagree_pairs, C.EXPECTED_ARM1B_N_DISAGREE_PAIRS))
    arm1b_exact = (k_arm1b == C.EXPECTED_ARM1B_K and n_arm1b == C.EXPECTED_ARM1B_N_CS
                   and n_disagree_pairs == C.EXPECTED_ARM1B_N_DISAGREE_PAIRS)
    if not arm1b_exact:
        void("0b", "ARM 1B's own pairing did not reproduce exactly -- reused helpers moved")
        return {"row0": {"0a": "PASS", "0b": "VOID"}}, void_rows

    leg, _ = C.run_12bit_leg_c(stream, C.CUR_SIZE)
    n_in_leg = 0
    n_verified = 0
    verified_cs = set()
    verified_pairs = []
    for p in kept_pairs:
        key = (p["ts"], p["freq_hz"], p["message_norm"])
        v = leg.get(key)
        if v is None:
            continue
        n_in_leg += 1
        if v["sim_name"] == p["o_payload"]:
            n_verified += 1
            verified_cs.add(p["o_payload"])
            verified_pairs.append({**p, "matches12": v["matches12"], "frozen": v["frozen"]})
    n_cs_verified = len(verified_cs)
    log("  VERIFIED survivors: %d over %d callsigns (bar [190,220] / [98,112])" % (n_verified, n_cs_verified))
    ok0b = (190 <= n_verified <= 220) and (98 <= n_cs_verified <= 112)
    log("  ROW 0b: %s" % ("PASS" if ok0b else "FAIL"))
    if not ok0b:
        void("0b", "VERIFIED-survivor population fell outside the pre-registered bars")
        return {"row0": {"0a": "PASS", "0b": "VOID"},
                "row0b_detail": {"n_verified": n_verified, "n_cs_verified": n_cs_verified}}, void_rows

    # ---------------- ROW 0c: predicate coherence (load-bearing) -----------
    # Reading note (disclosed, not silently resolved): Sec.4's ROW 0c states
    # two clauses -- (1) `lookup12(n12) is None` iff `matches12(n12)==0`, and
    # (2) `matches12 >= 1` "wherever the real build resolved". The row's own
    # stated purpose is that it "proves matches12 walks the SAME CHAIN
    # lookup12 does" -- a structural/code-coherence claim about these two
    # functions on THIS table, not an empirical claim about whether the
    # SIMULATED replay reproduces the REAL C DECODER'S name. That empirical
    # question is exactly ROW 0g/Sec.3.2's fidelity filter, already known
    # from ARM 1B (92.5% corpus-wide) and this arm's own Sec.0.4 drafting
    # fact (84.8% on this subpopulation) -- a check that voided on anything
    # short of 100% real-build-match fidelity would contradict a fact
    # already on the record in the same spec and could never pass. So
    # clause (2) is read as "wherever the SIMULATOR's OWN lookup12 resolved
    # (sim_name is not None), matches12 >= 1" -- implied by clause (1) and
    # therefore a pure internal-consistency check, exactly matching the
    # row's stated purpose. The separate, real empirical fact -- how often
    # the simulator resolves NOTHING where the real build resolved something
    # -- is reported below as a descriptive count, not gated here.
    log("-" * 78); log("ROW 0c -- predicate coherence (load-bearing)")
    n_checked = 0
    n_coherence_fail = 0
    n_clause2_fail = 0
    n_sim_none_but_real_resolved = 0
    for v in leg.values():
        n_checked += 1
        none_iff_zero = (v["sim_name"] is None) == (v["matches12"] == 0)
        if not none_iff_zero:
            n_coherence_fail += 1
        if v["sim_name"] is not None and v["matches12"] < 1:
            n_clause2_fail += 1
        if v["sim_name"] is None:   # descriptive only -- real build DID resolve (leg is resolved-only)
            n_sim_none_but_real_resolved += 1
    log("  queries checked=%d ; clause1 (none<=>zero) exceptions=%d ; clause2 (sim-resolved => matches>=1) exceptions=%d"
        % (n_checked, n_coherence_fail, n_clause2_fail))
    log("  descriptive only, NOT gated here: simulator found NOTHING where the real build resolved = %d/%d (%.1f%%)"
        % (n_sim_none_but_real_resolved, n_checked, 100.0 * n_sim_none_but_real_resolved / max(1, n_checked)))
    ok0c = (n_coherence_fail == 0) and (n_clause2_fail == 0)
    log("  ROW 0c: %s (bar: 100%%, zero exceptions on both structural clauses)" % ("PASS" if ok0c else "FAIL"))
    if not ok0c:
        void("0c", "matches12 does not walk the same chain lookup12 does")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "VOID"},
                "row0c_detail": {"n_checked": n_checked, "n_coherence_fail": n_coherence_fail,
                                  "n_clause2_fail": n_clause2_fail,
                                  "n_sim_none_but_real_resolved": n_sim_none_but_real_resolved}}, void_rows

    # ---------------- ROW 0d: differential-stratifier-error test -----------
    log("-" * 78); log("ROW 0d -- differential-stratifier-error test (load-bearing, HK-021(h))")
    dis_in_leg = [p for p in kept_pairs if p["disagree"] and (p["ts"], p["freq_hz"], p["message_norm"]) in leg]
    agr_in_leg = [p for p in kept_pairs if not p["disagree"] and (p["ts"], p["freq_hz"], p["message_norm"]) in leg]
    dis_verified = [p for p in dis_in_leg if leg[(p["ts"], p["freq_hz"], p["message_norm"])]["sim_name"] == p["o_payload"]]
    agr_verified = [p for p in agr_in_leg if leg[(p["ts"], p["freq_hz"], p["message_norm"])]["sim_name"] == p["o_payload"]]
    fid_dis = len(dis_verified) / len(dis_in_leg) if dis_in_leg else 0.0
    fid_agr = len(agr_verified) / len(agr_in_leg) if agr_in_leg else 0.0
    diff_pp = 100.0 * (fid_dis - fid_agr)
    log("  fidelity(disagree)=%.1f%% (%d/%d) ; fidelity(agree)=%.1f%% (%d/%d) ; signed diff=%.1fpp"
        % (100.0 * fid_dis, len(dis_verified), len(dis_in_leg),
           100.0 * fid_agr, len(agr_verified), len(agr_in_leg), diff_pp))
    ok0d = abs(diff_pp) <= 15.0
    cuts = ("N/A" if abs(diff_pp) < 1e-9 else
            ("rescue over-stated (filter preferentially drops WRONG names)" if diff_pp < 0 else
             "cost over-stated (filter preferentially drops RIGHT names)"))
    log("  which way it cuts: %s" % cuts)
    log("  ROW 0d: %s (bar: |diff| <= 15pp)" % ("PASS" if ok0d else "FAIL"))
    if not ok0d:
        void("0d", "differential stratifier error exceeds 15pp -- arm VOID beyond this bound")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "VOID"},
                "row0d_detail": {"fid_disagree": fid_dis, "fid_agree": fid_agr, "diff_pp": diff_pp}}, void_rows

    # ---------------- ROW 0f: predicate-movement exhibit --------------------
    log("-" * 78); log("ROW 0f -- predicate-movement exhibit (HK-021(q))")
    candidates = sorted(
        (p for p in verified_pairs if p["matches12"] == 1),
        key=lambda p: (p["ts"], p["freq_hz"], p["message_norm"]),
    )
    ok0f = False
    row0f_detail = {}
    n_candidates_tried = 0
    for cand in candidates:
        n_candidates_tried += 1
        key = (cand["ts"], cand["freq_hz"], cand["message_norm"])
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
            ok0f = True
            row0f_detail = {
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
    log("  ROW 0f: %s" % ("PASS" if ok0f else "FAIL"))
    if not ok0f:
        void("0f", "no unambiguous verified query could be moved to ambiguous by injection -- classifier is not measuring anything")
        return {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0f": "VOID"},
                "row0f_detail": {"candidates_tried": n_candidates_tried}}, void_rows

    # ---------------- ROW 0g: table-freeze exposure (stated, not gated) ----
    log("-" * 78); log("ROW 0g -- table-freeze exposure (stated, not gated)")
    frozen_share = sum(1 for p in verified_pairs if p["frozen"])
    log("  share of VERIFIED queries issued AFTER the table froze: %d/%d = %.1f%%"
        % (frozen_share, n_verified, 100.0 * frozen_share / max(1, n_verified)))

    row0 = {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0f": "PASS", "0g": "STATED"}

    # ==================== Sec.3.3 -- the 2x2 (VERIFIED only) ===============
    log("=" * 78); log("Sec.3.3 -- the 2x2, VERIFIED decodes only")
    unambig_agree = sum(1 for p in verified_pairs if p["matches12"] == 1 and not p["disagree"])
    unambig_disagree = sum(1 for p in verified_pairs if p["matches12"] == 1 and p["disagree"])
    ambig_agree = sum(1 for p in verified_pairs if p["matches12"] >= 2 and not p["disagree"])
    ambig_disagree = sum(1 for p in verified_pairs if p["matches12"] >= 2 and p["disagree"])
    log("  unambiguous & agree=%d ; unambiguous & disagree=%d ; ambiguous & agree=%d ; ambiguous & disagree=%d"
        % (unambig_agree, unambig_disagree, ambig_agree, ambig_disagree))

    # ---------------- ROW C: rescue (per-callsign, ALL-based) --------------
    log("-" * 78); log("ROW C -- rescue (unit=callsign, ALL verified disagreeing decodes ambiguous)")
    by_cs: dict = {}
    for p in verified_pairs:
        by_cs.setdefault(p["o_payload"], []).append(p)
    rowc_units = []
    rescued = 0
    for cs, ps in sorted(by_cs.items()):
        dis_ps = [p for p in ps if p["disagree"]]
        if not dis_ps:
            continue
        rowc_units.append(cs)
        if all(p["matches12"] >= 2 for p in dis_ps):
            rescued += 1
    n_rowc = len(rowc_units)
    log("  ROW C units (n)=%d ; rescued=%d" % (n_rowc, rescued))
    gate_c = None
    p_rescue = cp_lo_c = cp_hi_c = None
    if n_rowc < 40:
        log("  n=%d < 40 -- UNDER-POWERED, no verdict (HK-021(m))" % n_rowc)
        gate_c = "UNDER-POWERED"
    else:
        p_rescue = rescued / n_rowc
        cp_lo_c = C.cp_lower_one_sided(rescued, n_rowc)
        cp_hi_c = C.cp_upper_one_sided(rescued, n_rowc)
        log("  p_rescue=%.4f CP one-sided 95%% lower=%.4f upper=%.4f" % (p_rescue, cp_lo_c, cp_hi_c))
        if cp_lo_c > 0.50:
            gate_c = "C1"
        elif cp_hi_c < 0.50:
            gate_c = "C2"
        else:
            gate_c = "C3"
        log("  -> ROW %s" % gate_c)

    # ---------------- ROW D: cost (per-callsign, ANY-based) -----------------
    log("-" * 78); log("ROW D -- cost (unit=callsign, ANY verified decode ambiguous, all-agree callsigns only)")
    rowd_units = []
    lost = 0
    for cs, ps in sorted(by_cs.items()):
        if any(p["disagree"] for p in ps):
            continue   # ROW C unit, excluded from ROW D by construction
        rowd_units.append(cs)
        if any(p["matches12"] >= 2 for p in ps):
            lost += 1
    n_rowd = len(rowd_units)
    log("  ROW D units (n)=%d ; lost=%d" % (n_rowd, lost))
    gate_d = None
    p_lost = cp_lo_d = cp_hi_d = None
    if n_rowd < 40:
        log("  n=%d < 40 -- UNDER-POWERED, no verdict (HK-021(m))" % n_rowd)
        gate_d = "UNDER-POWERED"
    else:
        p_lost = lost / n_rowd
        cp_lo_d = C.cp_lower_one_sided(lost, n_rowd)
        cp_hi_d = C.cp_upper_one_sided(lost, n_rowd)
        log("  p_lost=%.4f CP one-sided 95%% lower=%.4f upper=%.4f" % (p_lost, cp_lo_d, cp_hi_d))
        if cp_lo_d > 0.50:
            gate_d = "D1"
        elif cp_hi_d < 0.50:
            gate_d = "D2"
        else:
            gate_d = "D3"
        log("  -> ROW %s" % gate_d)

    # ---------------- ROW E: post-rule agreement (descriptive) -------------
    log("-" * 78); log("ROW E -- post-rule agreement among survivors (descriptive, ungated)")
    n_survive = unambig_agree + unambig_disagree
    p_e = (unambig_agree / n_survive) if n_survive else None
    cp_lo_e = C.cp_lower_one_sided(unambig_agree, n_survive) if n_survive else None
    cp_hi_e = C.cp_upper_one_sided(unambig_agree, n_survive) if n_survive else None
    log("  survivors (unambiguous & verified)=%d ; agree among survivors=%d ; rate=%s"
        % (n_survive, unambig_agree, ("%.1f%%" % (100.0 * p_e) if p_e is not None else "N/A")))
    log("  ARM 1B baseline (all 243, unfiltered): 62.1%% (151/243)")

    # ---------------- Contingency: verified matches12==1 but WRONG ---------
    ceiling_unreachable = unambig_disagree  # same count -- named separately per Sec.7
    log("-" * 78)
    log("Contingency -- verified matches12==1 (unique match) but WRONG: %d"
        % ceiling_unreachable)
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
            "n_verified": n_verified, "n_cs_verified": n_cs_verified,
        },
        "row0c_detail": {"n_checked": n_checked, "n_coherence_fail": n_coherence_fail,
                          "n_clause2_fail": n_clause2_fail,
                          "n_sim_none_but_real_resolved": n_sim_none_but_real_resolved},
        "row0d_detail": {"fid_disagree": fid_dis, "fid_agree": fid_agr, "diff_pp": diff_pp, "cuts": cuts,
                          "n_dis_in_leg": len(dis_in_leg), "n_agr_in_leg": len(agr_in_leg)},
        "row0f_detail": row0f_detail,
        "row0g_detail": {"frozen_share": frozen_share, "n_verified": n_verified},
        "sec33_2x2": {
            "unambiguous_agree": unambig_agree, "unambiguous_disagree": unambig_disagree,
            "ambiguous_agree": ambig_agree, "ambiguous_disagree": ambig_disagree,
        },
        "row_c": {
            "n": n_rowc, "rescued": rescued, "p_rescue": p_rescue,
            "cp_lower_one_sided_95": cp_lo_c, "cp_upper_one_sided_95": cp_hi_c, "gate": gate_c,
        },
        "row_d": {
            "n": n_rowd, "lost": lost, "p_lost": p_lost,
            "cp_lower_one_sided_95": cp_lo_d, "cp_upper_one_sided_95": cp_hi_d, "gate": gate_d,
        },
        "row_e": {
            "n_survive": n_survive, "agree_among_survivors": unambig_agree, "p": p_e,
            "cp_lower_one_sided_95": cp_lo_e, "cp_upper_one_sided_95": cp_hi_e,
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
# ROW 0e: out-of-process determinism check
# =============================================================================
def emit_core_json():
    def noop_log(_msg=""):
        pass
    result, _void = compute_all(noop_log)
    sys.stdout.write(json.dumps(result, sort_keys=True))
    sys.stdout.flush()


def run_row0e_check(script_path: str) -> tuple[bool, str, str]:
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
    log("F-001 D3 ARM 1C -- run_arm1c.py -- repo main @ %s" % git_sha())
    log("=" * 78)

    result, void_rows = compute_all(log)

    # ROW 0e is spliced in here (after 0a-0d/0f/0g succeed, before reporting)
    # rather than inside compute_all, because compute_all IS the thing being
    # checked for determinism -- it cannot check itself recursively without
    # an unbounded process tree.
    if not void_rows:
        log("-" * 78); log("ROW 0e -- determinism, OUT OF PROCESS, different PYTHONHASHSEED")
        script_path = os.path.abspath(__file__)
        det_ok, out_a, out_b = run_row0e_check(script_path)
        log("  seed A=%s seed B=%s -- result.json byte-identical: %s" % (HASHSEED_A, HASHSEED_B, det_ok))
        log("  ROW 0e: %s" % ("PASS" if det_ok else "FAIL"))
        result["row0"]["0e"] = "PASS" if det_ok else "VOID"
        result["row0e_detail"] = {"hashseed_a": HASHSEED_A, "hashseed_b": HASHSEED_B, "byte_identical": det_ok}
        if not det_ok:
            void_rows.append(("0e", "out-of-process rerun under a different PYTHONHASHSEED was not byte-identical"))
            log("  -> VOID at ROW 0e: hash-randomised-iteration hazard reproduced")
            # Preserve everything computed so far but mark the arm VOID.
            result["row0"] = {k: ("VOID" if k == "0e" else v) for k, v in result["row0"].items()}

    return finish(args, log_lines, result, void_rows)


if __name__ == "__main__":
    sys.exit(main())
