#!/usr/bin/env python3
"""F-001 D3 ARM 1B -- is the current build printing WRONG callsigns on the
12-bit hash-lookup path?

Spec: qa/rr-study/2026-08-26-1352-architect-to-qa-spec-f001-d3-arm1b-twelve-bit-correctness.md

Pure re-analysis of decode dumps already on disk (no rebuild, no replay, no
capture run, no src/ or native/ edit -- Sec.8). Reuses common_arm1.py /
common_b1.py / common_g2a.py unmodified (Sec.2 "reuse, do not re-implement";
ROW 0c asserts this by object identity).

NFR-021: real callsign strings and message text live in memory only.
result.json / run.log / the report carry only counts, cycle timestamps,
frequencies, and sha256[:6]-redacted CS-xxxxxx tokens (common_b1.redact).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_arm1b as C   # noqa: E402
import common_arm1 as A    # noqa: E402
import common_b1 as B      # noqa: E402
import common_g2a as G     # noqa: E402

CUR_SIZE, SZ4_SIZE, SZ8_SIZE = 4096, 16384, 32768


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, check=True,
                               cwd=G.REPO_ROOT).stdout.strip()
    except Exception:
        return "unknown"


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


def build_part_a(ours_rows, theirs_index):
    """Returns (ours_pairs, resolved_both, coverage_counter)."""
    t4 = C.type4_rows(ours_rows)
    ours_pairs = C.pair_all(t4, theirs_index)
    resolved_both = [p for p in ours_pairs if p["matched"] and p["o_kind"] == "resolved" and p["t_kind"] == "resolved"]
    coverage = Counter()
    for p in ours_pairs:
        t_label = p["t_kind"] if p["matched"] else "no_match"
        coverage[(p["o_kind"], t_label)] += 1
    return ours_pairs, resolved_both, coverage


def apply_row0d(resolved_both):
    """Sec.3.3/ROW 0d. Returns (kept_pairs, n_disagree_total, n_dropped,
    drop_examples) where kept_pairs is agree+validated-disagree only."""
    kept = []
    n_disagree_total = 0
    n_dropped = 0
    for p in resolved_both:
        o, t = p["o_payload"], p["t_payload"]
        if o == t:
            kept.append({**p, "disagree": False})
            continue
        n_disagree_total += 1
        n22_o, n22_t = A.n22_of(o), A.n22_of(t)
        valid = (n22_o is not None and n22_t is not None and A.n12_of(n22_o) == A.n12_of(n22_t))
        if valid:
            kept.append({**p, "disagree": True})
        else:
            n_dropped += 1
    return kept, n_disagree_total, n_dropped


def callsign_flags(kept_pairs):
    """Unit = the callsign THIS BUILD named (o_payload). A callsign is
    cs-disagree if >=1 of its kept paired decodes disagreed."""
    flags: dict[str, bool] = {}
    n_pairs_per_cs: dict[str, int] = {}
    for p in kept_pairs:
        cs = p["o_payload"]
        n_pairs_per_cs[cs] = n_pairs_per_cs.get(cs, 0) + 1
        flags[cs] = flags.get(cs, False) or p["disagree"]
    return flags, n_pairs_per_cs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    log_lines = []

    def log(msg=""):
        print(msg, flush=True)
        log_lines.append(msg)

    void_rows = []

    def void(row, reason):
        void_rows.append((row, reason))
        log("  -> VOID at ROW %s: %s" % (row, reason))

    log("=" * 78)
    log("F-001 D3 ARM 1B -- run_arm1b.py -- repo main @ %s" % git_sha())
    log("=" * 78)

    log("Loading decode dumps + reference ALL.TXT (no rebuild, no replay)...")
    l2run1_dump, ours_rows_1 = C.load_l2run1_ours_rows()
    theirs_rows = C.load_theirs_rows()

    # ---------------- ROW 0a: dump identity ----------------
    log("-" * 78); log("ROW 0a -- dump identity")
    ident1 = B.check_dump_identity(l2run1_dump)
    log("  L2_run1: %s" % ident1)
    log("  reference ALL.TXT rows = %d (expect %d)" % (len(theirs_rows), C.EXPECTED_N_THEIRS_ROWS))
    ok0a = (ident1["dll_sha256"] == C.EXPECTED_L2_SHA256
            and ident1["shim_version"] == C.EXPECTED_L2_SHIM_VERSION
            and ident1["n_decodes"] == C.EXPECTED_N_DECODES
            and ident1["n_records"] == C.EXPECTED_N_DECODES
            and len(theirs_rows) == C.EXPECTED_N_THEIRS_ROWS)
    log("  ROW 0a: %s" % ("PASS" if ok0a else "FAIL"))
    if not ok0a:
        void("0a", "dump identity does not match the pinned spec inputs")
        return finish(args, log_lines, {"row0": {"0a": "VOID"}}, void_rows)

    stream = C.sorted_stream(ours_rows_1)
    theirs_index = C.build_theirs_index(theirs_rows)

    ours_pairs, resolved_both, coverage = build_part_a(ours_rows_1, theirs_index)

    # ---------------- ROW 0b: population reproduction (load-bearing) -------
    log("-" * 78); log("ROW 0b -- population reproduction (load-bearing)")
    n_resolved_type4 = sum(1 for r in ours_rows_1
                            for s in [C.slot(r["message_norm"])]
                            if s is not None and s[3] and s[0] == "resolved")
    n_resolved_std = sum(1 for r in ours_rows_1
                          for s in [C.slot(r["message_norm"])]
                          if s is not None and not s[3] and s[0] == "resolved")
    log("  resolved type-4 (nonstd) decodes = %d (bar [1850,1950])" % n_resolved_type4)
    log("  resolved standard decodes        = %d (bar [1400,1500])" % n_resolved_std)
    ok0b = (1850 <= n_resolved_type4 <= 1950) and (1400 <= n_resolved_std <= 1500)
    log("  ROW 0b: %s" % ("PASS" if ok0b else "FAIL"))
    if not ok0b:
        void("0b", "slot() predicate population does not match the pre-registered bars -- predicate mismatch")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "VOID"},
                                         "row0b_detail": {"n_resolved_type4": n_resolved_type4,
                                                           "n_resolved_std": n_resolved_std}}, void_rows)

    # ---------------- ROW 0c: predicate reuse (object identity) ------------
    log("-" * 78); log("ROW 0c -- predicate reuse (assert by import)")
    ok0c = (C.B.is_callsign_token is B.is_callsign_token
            and C.A.n22_of is A.n22_of
            and C.A.SimTable is A.SimTable)
    log("  is_callsign_token / n22_of / SimTable are the SAME objects as common_b1/common_arm1's: %s" % ok0c)
    log("  ROW 0c: %s" % ("PASS" if ok0c else "FAIL"))
    if not ok0c:
        void("0c", "predicate/simulator was re-implemented rather than imported")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "VOID"}}, void_rows)

    # ---------------- ROW 0d: the free validity test (load-bearing) --------
    log("-" * 78); log("ROW 0d -- free validity test (Sec.0.3 fact 3)")
    kept_pairs, n_disagree_total, n_dropped = apply_row0d(resolved_both)
    drop_frac = (n_dropped / n_disagree_total) if n_disagree_total else 0.0
    log("  resolved-both pairs = %d ; disagreeing = %d ; failed n12 test (matching failures, dropped) = %d (%.1f%%)"
        % (len(resolved_both), n_disagree_total, n_dropped, 100.0 * drop_frac))
    ok0d = drop_frac <= 0.10
    log("  ROW 0d: %s (bar: dropped disagreements <=10%%)" % ("PASS" if ok0d else "FAIL"))
    if not ok0d:
        void("0d", "more than 10%% of disagreeing pairs fail the n12 identity -- pairing rule is broken")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "VOID"},
                                         "row0d_detail": {"n_disagree_total": n_disagree_total, "n_dropped": n_dropped}}, void_rows)

    flags, n_pairs_per_cs = callsign_flags(kept_pairs)
    k_decodes = len(kept_pairs)
    n_callsigns = len(flags)
    cs_disagree_list = sorted(cs for cs, dis in flags.items() if dis)
    cs_agree_list = sorted(cs for cs, dis in flags.items() if not dis)
    x_dis = len(cs_disagree_list)

    # ---------------- ROW 0e: determinism + independent input --------------
    log("-" * 78); log("ROW 0e -- determinism + independent input")
    ours_pairs_b, resolved_both_b, _ = build_part_a(ours_rows_1, theirs_index)
    kept_pairs_b, n_dis_b, n_drop_b = apply_row0d(resolved_both_b)
    flags_b, _ = callsign_flags(kept_pairs_b)
    det_ok = (flags == flags_b and k_decodes == len(kept_pairs_b) and n_disagree_total == n_dis_b)
    log("  rerun byte-identical (flags/k/n_disagree_total all equal): %s" % det_ok)

    l2run2_dump, ours_rows_2 = C.load_l2run2_ours_rows()
    ours_pairs_2, resolved_both_2, _ = build_part_a(ours_rows_2, theirs_index)
    kept_pairs_2, n_dis_2, n_drop_2 = apply_row0d(resolved_both_2)
    flags_2, _ = callsign_flags(kept_pairs_2)
    k2 = len(kept_pairs_2)
    indep_ok = (k_decodes - 15) <= k2 <= (k_decodes + 15)
    log("  L2_run2 independent replicate: k=%d vs L2_run1's k=%d (bar [%d,%d]): %s"
        % (k2, k_decodes, k_decodes - 15, k_decodes + 15, indep_ok))

    ok0e = det_ok and indep_ok
    log("  ROW 0e: %s" % ("PASS" if ok0e else "FAIL"))
    if not ok0e:
        void("0e", "non-deterministic rerun, or independent-input replicate disagrees")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "VOID"}}, void_rows)

    # ---------------- ROW 0f: predicate-movement exhibit --------------------
    log("-" * 78); log("ROW 0f -- predicate-movement exhibit (HK-021(q))")
    agree_example = next((p for p in kept_pairs if not p["disagree"]), None)
    ok0f = False
    row0f_detail = {}
    if agree_example is not None:
        orig = agree_example["o_payload"]
        ref = agree_example["t_payload"]
        last = orig[-1]
        mutated = orig[:-1] + ("0" if last != "0" else "1")
        moved_to_disagree = (mutated != ref)
        n22_mut, n22_ref = A.n22_of(mutated), A.n22_of(ref)
        mutated_fails_0d = not (n22_mut is not None and n22_ref is not None and A.n12_of(n22_mut) == A.n12_of(n22_ref))
        ok0f = moved_to_disagree and mutated_fails_0d
        row0f_detail = {
            "original_redacted": C.redact(orig), "reference_redacted": C.redact(ref),
            "mutated_redacted": C.redact(mutated),
            "moved_agree_to_disagree": moved_to_disagree,
            "mutated_pair_fails_row0d_n12_test": mutated_fails_0d,
        }
        log("  worked example: original=%s reference=%s (agree) -> mutated=%s"
            % (C.redact(orig), C.redact(ref), C.redact(mutated)))
        log("  classifier moved agree->disagree: %s ; mutated pair now FAILS ROW 0d's n12 test: %s"
            % (moved_to_disagree, mutated_fails_0d))
    else:
        log("  NO agreeing pair found to mutate -- cannot run the exhibit")
    log("  ROW 0f: %s" % ("PASS" if ok0f else "FAIL"))
    if not ok0f:
        void("0f", "predicate-movement exhibit did not move as required -- classifier is not measuring anything")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "PASS", "0f": "VOID"},
                                         "row0f_detail": row0f_detail}, void_rows)

    # ---------------- ROW 0g: 12-bit simulator fidelity (Part B only) ------
    log("-" * 78); log("ROW 0g -- 12-bit simulator fidelity (Part B only; Part A is proxy-free)")
    cur_leg = C.run_12bit_leg(stream, CUR_SIZE)
    n_q = len(cur_leg)
    n_reproduce = sum(1 for v in cur_leg.values() if v[0] == v[1])
    fidelity = n_reproduce / n_q if n_q else 0.0
    log("  simulated CUR (N=%d) queries=%d  reproduces-real-name=%d  fidelity=%.1f%% (bar >=85%%, Architect probe: 92.5%%)"
        % (CUR_SIZE, n_q, n_reproduce, 100.0 * fidelity))
    ok0g = fidelity >= 0.85
    log("  ROW 0g: %s" % ("PASS" if ok0g else "VOID (Part B only -- Part A unaffected)"))
    row0 = {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "PASS", "0f": "PASS",
            "0g": "PASS" if ok0g else "VOID"}
    if not ok0g:
        void("0g", "12-bit simulator fidelity below 85%% -- Part B voided, Part A stands")

    # ==================== Part A: gates (Sec.5) ============================
    log("=" * 78); log("Part A -- Sec.5 gates, unit = callsign")
    log("  k (kept paired decodes) = %d ; distinct callsigns (n) = %d" % (k_decodes, n_callsigns))
    top5 = sorted(n_pairs_per_cs.values(), reverse=True)[:5]
    log("  top-5 decode concentration = %s = %.1f%% of k" % (top5, 100.0 * sum(top5) / max(1, k_decodes)))
    log("  cs-disagree = %d ; cs-agree = %d" % (x_dis, n_callsigns - x_dis))

    under_powered = n_callsigns < 60
    gate_row = None
    p_dis = cp_lo = cp_hi = None
    if under_powered:
        log("  n=%d < 60 -- STOP, UNDER-POWERED, no verdict either way (HK-021(m))" % n_callsigns)
        gate_row = "UNDER-POWERED"
    else:
        p_dis = x_dis / n_callsigns
        cp_lo = C.cp_lower_one_sided(x_dis, n_callsigns)
        cp_hi = C.cp_upper_one_sided(x_dis, n_callsigns)
        log("  p_dis = %.4f  CP one-sided 95%% lower=%.4f upper=%.4f" % (p_dis, cp_lo, cp_hi))
        if cp_lo > 0.05:
            gate_row = "A1"
        elif cp_hi < 0.05:
            gate_row = "A2"
        else:
            gate_row = "A3"
        log("  -> ROW %s" % gate_row)

    # ---- Sec.6 coverage table (descriptive, ungated) ----
    log("-" * 78); log("Sec.6 -- coverage table (descriptive, NOT folded into p_dis)")
    for (ok, tk), n in sorted(coverage.items()):
        log("  ours=%-10s theirs=%-10s : %d" % (ok, tk, n))
    n_multi_bracket = sum(1 for r in ours_rows_1 if len([t for t in r["message_norm"].split() if t.startswith('<')]) >= 2)
    log("  ours decodes with >1 bracket slot (excluded by slot()): %d" % n_multi_bracket)

    # ---- plaintext-appears-elsewhere tiebreaker (descriptive only) ----
    t_ours_plain = set()
    for r in ours_rows_1:
        for t in r["message_norm"].split():
            if not t.startswith('<') and B.is_callsign_token(t):
                t_ours_plain.add(t)
    t_theirs_plain = set()
    for r in theirs_rows:
        for t in r["message_norm"].split():
            if not t.startswith('<') and B.is_callsign_token(t):
                t_theirs_plain.add(t)
    disagree_pairs_detail = []
    for p in kept_pairs:
        if not p["disagree"]:
            continue
        disagree_pairs_detail.append({
            "ours_redacted": C.redact(p["o_payload"]), "theirs_redacted": C.redact(p["t_payload"]),
            "ours_name_appears_plaintext_in_theirs_corpus": p["o_payload"] in t_theirs_plain,
            "theirs_name_appears_plaintext_in_ours_corpus": p["t_payload"] in t_ours_plain,
        })
    log("  disagreeing pairs (n=%d), plaintext tiebreaker (descriptive, NOT attribution):" % len(disagree_pairs_detail))
    for d in disagree_pairs_detail:
        log("    ours=%s theirs=%s  ours-seen-in-theirs-plain=%s  theirs-seen-in-ours-plain=%s"
            % (d["ours_redacted"], d["theirs_redacted"],
               d["ours_name_appears_plaintext_in_theirs_corpus"], d["theirs_name_appears_plaintext_in_ours_corpus"]))

    # ==================== Part B (Sec.3.4 / ROW B) ==========================
    log("=" * 78); log("Part B -- enlargement counter-metric, adjudicated against the reference")
    part_b = {}
    if ok0g:
        sz4_leg = C.run_12bit_leg(stream, SZ4_SIZE)
        sz8_leg = C.run_12bit_leg(stream, SZ8_SIZE)
        for name, leg in (("SZ4", sz4_leg), ("SZ8", sz8_leg)):
            keys, disc = C.paired_discordance(cur_leg, leg)
            cur_none = leg_none = both_differ = 0
            ref_confirms = ref_contradicts = no_ref = 0
            for key in disc:
                cv = cur_leg[key][0]
                lv = leg[key][0]
                if cv is None and lv is not None:
                    cur_none += 1
                    row = cur_leg[key][2]
                    others = cur_leg[key][3]
                    ntok = cur_leg[key][4]
                    m = C.best_match(row, others, ntok, theirs_index)
                    if m is not None and m["kind"] == "resolved":
                        if m["payload"] == lv:
                            ref_confirms += 1
                        else:
                            ref_contradicts += 1
                    else:
                        no_ref += 1
                elif lv is None and cv is not None:
                    leg_none += 1
                else:
                    both_differ += 1
            log("  %s vs CUR: paired=%d discordant=%d (CUR-had-none=%d %s-had-none=%d both-named-differ=%d)"
                % (name, len(keys), len(disc), cur_none, name, leg_none, both_differ))
            log("     of the CUR-had-none new resolutions: reference confirms=%d contradicts=%d no-reference=%d"
                % (ref_confirms, ref_contradicts, no_ref))
            part_b[name] = {
                "paired_queries": len(keys), "discordant": len(disc),
                "cur_had_none": cur_none, "leg_had_none": leg_none, "both_named_differ": both_differ,
                "new_resolution_reference_confirms": ref_confirms,
                "new_resolution_reference_contradicts": ref_contradicts,
                "new_resolution_no_reference": no_ref,
            }
    else:
        log("  SKIPPED -- ROW 0g VOID")

    result = {
        "row0": row0,
        "inputs": {
            "n_decodes_l2run1": ident1["n_decodes"], "n_theirs_rows": len(theirs_rows),
            "n_resolved_type4": n_resolved_type4, "n_resolved_std": n_resolved_std,
        },
        "row0d_detail": {"n_disagree_total": n_disagree_total, "n_dropped": n_dropped, "drop_frac": drop_frac},
        "row0f_detail": row0f_detail,
        "row0g_detail": {"n_queries": n_q, "n_reproduce": n_reproduce, "fidelity": fidelity},
        "part_a": {
            "k_decodes": k_decodes, "n_callsigns": n_callsigns,
            "cs_disagree": x_dis, "cs_agree": n_callsigns - x_dis,
            "top5_concentration": top5,
            "p_dis": p_dis, "cp_lower_one_sided_95": cp_lo, "cp_upper_one_sided_95": cp_hi,
            "under_powered": under_powered, "gate_row": gate_row,
        },
        "sec6_coverage_table": {"%s|%s" % k: v for k, v in coverage.items()},
        "sec6_n_multi_bracket_excluded": n_multi_bracket,
        "sec6_disagreeing_pairs_plaintext_tiebreaker": disagree_pairs_detail,
        "part_b": part_b,
    }
    return finish(args, log_lines, result, void_rows)


if __name__ == "__main__":
    sys.exit(main())
