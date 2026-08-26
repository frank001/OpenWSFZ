#!/usr/bin/env python3
"""B1-COVERAGE-A -- when we render `<...>`, had our own stream ever learnt
that callsign, and was the table still accepting entries at the time?

Spec: qa/rr-study/2026-08-25-1836-architect-to-qa-spec-b1-coverage-a.md

Pure re-analysis of decode dumps already on disk (no rebuild, no replay, no
capture run). Reuses gap-census-a's Population/classify_partition and
g2a-remeasure-a's corrected-predicate row-builder unmodified (HK-018).

NFR-021: only counts, cycle timestamps, frequencies, and sha256[:6]-redacted
callsign tokens ever reach result.json / run.log / the report. No message
text and no real callsign in any of them.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_b1 as B  # noqa: E402
import common_g2a as G  # noqa: E402
from partition import classify_partition, ours_lookup_from_population  # noqa: E402


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, check=True,
                               cwd=G.REPO_ROOT).stdout.strip()
    except Exception:
        return "unknown"


# ------------------------------------------------------------------------
# core: build the B1 population, name each key, split by the freeze cycle
# ------------------------------------------------------------------------

def build_ours_by_cycle(ours_rows_corrected: list) -> dict:
    out = {}
    for r in ours_rows_corrected:
        out.setdefault(r["ts"], []).append(r)
    for ts in out:
        out[ts].sort(key=lambda r: (r["freq_hz"], r["message_norm"]))  # hazard 1
    return out


def classify_b1(ours_rows_corrected: list, theirs_rows: list):
    """Returns (bucket_of, n_theirs_only, b1_keys_sorted, per_key) where
    per_key[key] = dict with category/named/candidates_n etc. No message
    text or real callsign is retained past this function's local scope
    except inside `named` (a real callsign string) -- caller must redact
    before it touches a result dict, a print, or a log line."""
    pop = G.gc.Population(ours_rows_corrected, theirs_rows)
    lookup = ours_lookup_from_population(pop)
    bucket_of = classify_partition(pop, lookup)
    b1_keys = sorted(k for k, v in bucket_of.items() if v == "B1")  # hazard 1

    ours_by_cycle = build_ours_by_cycle(ours_rows_corrected)

    per_key = {}
    for key in b1_keys:
        ts, r_norm = key
        rep_freq = pop.theirs_only_rep_freq[key]
        r_tokens = r_norm.split()
        candidates = [r for r in ours_by_cycle.get(ts, [])
                      if r["has_hash"] and abs(r["freq_hz"] - rep_freq) <= 4.0]

        # Sec.2.2 descriptive classifier (best-candidate mismatch count)
        mismatches = []
        for c in candidates:
            m = B.mismatch_count(c["message_norm"].split(), r_tokens)
            if m is not None:
                mismatches.append(m)
        if not mismatches:
            category = "token_count_differs"
        else:
            best = min(mismatches)
            category = {0: "nameable", 1: "one_diff_ambiguous", 2: "two_diff"}.get(best, "other_diff")

        # Sec.2.4 naming rule -- strict, ALL other tokens byte-equal.
        # QA correction (disclosed in the report): the reference token at the
        # hash position is a hash-type message field and is therefore itself
        # bracket-wrapped by ft8_lib's add_brackets() convention regardless of
        # resolution outcome (common_g2a.py Sec.1 note) -- strip one enclosing
        # <...> layer before the Sec.2.5 shape test. See
        # common_b1.strip_enclosing_brackets docstring for the empirical check.
        named_set = set()
        for c in candidates:
            pos = B.template_match(c["message_norm"].split(), r_tokens)
            if pos is not None:
                tok = B.strip_enclosing_brackets(r_tokens[pos])
                if B.is_callsign_token(tok):
                    named_set.add(tok)

        if len(named_set) == 1:
            named = next(iter(named_set))
            amb = False
        else:
            named = None
            amb = True  # 0 or >1 distinct callsigns named

        per_key[key] = {
            "ts": ts,
            "category": category,
            "n_candidates": len(candidates),
            "amb": amb,
            "named": named,  # real callsign text -- redact before it leaves this process
        }

    return bucket_of, pop.n_theirs_only, b1_keys, per_key


def key_and_callsign_buckets(b1_keys, per_key, t_plain: dict, freeze_ts: str):
    """Sec.4 (per-key) and Sec.5 (per-callsign) bucketing."""
    key_bucket = {}
    callsign_keys = {}  # named callsign -> list of key ts's
    for key in b1_keys:
        info = per_key[key]
        if info["amb"]:
            key_bucket[key] = "B1-amb"
            continue
        x = info["named"]
        tplain = t_plain.get(x)
        ts = info["ts"]
        if tplain is None:
            key_bucket[key] = "B1-cov"
        elif tplain >= ts:
            key_bucket[key] = "B1-ord"
        else:
            key_bucket[key] = "B1-cap"
        callsign_keys.setdefault(x, []).append(ts)

    cs_bucket = {}
    for x, ts_list in callsign_keys.items():
        tplain = t_plain.get(x)
        if tplain is None:
            cs_bucket[x] = "CS-cov"
        elif any(ts > tplain for ts in ts_list):
            cs_bucket[x] = "CS-cap"
        else:
            cs_bucket[x] = "CS-ord"

    return key_bucket, callsign_keys, cs_bucket


def cap_frozen_split(cs_cap_callsigns: list, t_plain: dict, freeze_ts: str):
    out = {}
    for x in cs_cap_callsigns:
        out[x] = "cap-frozen" if t_plain[x] >= freeze_ts else "cap-resident"
    return out


# ------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--l2run1", default=G.L2_RUN1_JSON)
    ap.add_argument("--l2run2", default=G.L2_RUN2_JSON)
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
    log("B1-COVERAGE-A -- run_b1_coverage_a.py -- repo main @ %s" % git_sha())
    log("=" * 78)

    log("Loading decode dumps (no rebuild, no replay)...")
    l2run1_dump = G.load_decode_dump(args.l2run1)
    l2run2_dump = G.load_decode_dump(args.l2run2)
    theirs_rows = G.load_theirs_rows()

    # ---------------- ROW 0a: dump identity ----------------
    log("-" * 78); log("ROW 0a -- dump identity")
    ident1 = B.check_dump_identity(l2run1_dump)
    log("  L2_run1: %s" % ident1)
    ok0a = (ident1["dll_sha256"] == B.EXPECTED_L2_SHA256
            and ident1["shim_version"] == B.EXPECTED_L2_SHIM_VERSION
            and ident1["n_decodes"] == B.EXPECTED_N_DECODES
            and ident1["n_records"] == B.EXPECTED_N_DECODES)
    n_theirs = len(theirs_rows)
    log("  n_theirs (reference ALL.TXT rows) = %d (pinned %d)" % (n_theirs, B.N_THEIRS_PINNED))
    ok0a = ok0a and (n_theirs == B.N_THEIRS_PINNED)
    log("  ROW 0a: %s" % ("PASS" if ok0a else "FAIL"))
    if not ok0a:
        void("0a", "dump identity does not match the pinned spec inputs")
        return finish(args, log_lines, {"row0": {"0a": "VOID"}}, void_rows)

    # ---------------- build population, classify B1 (run1) ----------------
    ours_rows_1 = G.rows_from_dump_corrected(l2run1_dump)
    bucket_of_1, n_theirs_only_1, b1_keys_1, per_key_1 = classify_b1(ours_rows_1, theirs_rows)

    log("-" * 78); log("ROW 0b -- population reproduction")
    log("  n_theirs_only = %d (expect %d)" % (n_theirs_only_1, B.EXPECTED_N_THEIRS_ONLY))
    log("  |B1| = %d (expect %d)" % (len(b1_keys_1), B.EXPECTED_B1_COUNT))
    ok0b = (n_theirs_only_1 == B.EXPECTED_N_THEIRS_ONLY and len(b1_keys_1) == B.EXPECTED_B1_COUNT)
    log("  ROW 0b: %s" % ("PASS" if ok0b else "FAIL"))
    if not ok0b:
        void("0b", "population does not reproduce QA's own 17:56Z re-derivation")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "VOID"}}, void_rows)

    # ---------------- Sec.2.2 descriptive corroboration table ----------------
    cat_counts = {}
    for key in b1_keys_1:
        cat_counts[per_key_1[key]["category"]] = cat_counts.get(per_key_1[key]["category"], 0) + 1
    log("-" * 78); log("Sec.2.2 -- textual corroboration of B1 (independent re-derivation)")
    for cat in ("nameable", "one_diff_ambiguous", "two_diff", "token_count_differs", "other_diff"):
        if cat in cat_counts:
            log("  %-22s %4d" % (cat, cat_counts[cat]))
    n_nameable = cat_counts.get("nameable", 0)
    n_amb_total = len(b1_keys_1) - n_nameable
    log("  nameable=%d (%.1f%% of B1) vs Architect's disclosed 339 (72.1%%)"
        % (n_nameable, 100.0 * n_nameable / len(b1_keys_1)))

    # ---------------- T_plain index (session-wide, run1) ----------------
    t_plain_1 = B.build_t_plain_index(ours_rows_1)
    log("-" * 78); log("Sec.2.5 -- plaintext-emission index: %d distinct callsign-shaped tokens, whole session"
                        % len(t_plain_1))

    key_bucket_1, callsign_keys_1, cs_bucket_1 = key_and_callsign_buckets(
        b1_keys_1, per_key_1, t_plain_1, B.FREEZE_CYCLE_TS)

    k = len(callsign_keys_1)
    log("  distinct named callsigns in B1 (k) = %d" % k)

    # ---------------- ROW 0c: predicate-movement exhibit ----------------
    log("-" * 78); log("ROW 0c -- predicate-movement exhibit (HK-021(q))")
    named_example = next((key for key in b1_keys_1 if not per_key_1[key]["amb"]), None)
    amb_example = next((key for key in b1_keys_1 if per_key_1[key]["amb"]), None)
    plain_example = next(iter(sorted(t_plain_1.items(), key=lambda kv: kv[1])), None)
    ok0c = named_example is not None and amb_example is not None and plain_example is not None
    if named_example is not None:
        log("  NAMED example: key ts=%s -> %s (bucket=%s)"
            % (named_example[0], B.redact(per_key_1[named_example]["named"]), key_bucket_1[named_example]))
    if amb_example is not None:
        log("  B1-amb example: key ts=%s, category=%s, n_candidates=%d (declined -- %s)"
            % (amb_example[0], per_key_1[amb_example]["category"], per_key_1[amb_example]["n_candidates"],
               "no unique template-consistent candidate" if per_key_1[amb_example]["n_candidates"] == 0
               or per_key_1[amb_example]["category"] != "nameable" else "ambiguous"))
    if plain_example is not None:
        tok, ts = plain_example
        log("  Session-wide plaintext emission example: %s first seen plaintext at ts=%s" % (B.redact(tok), ts))
    log("  ROW 0c: %s" % ("PASS" if ok0c else "FAIL"))
    if not ok0c:
        void("0c", "classifier could not produce all three required exhibits -- decorative")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "VOID"}}, void_rows)

    # ---------------- ROW 0d: proxy calibration ----------------
    log("-" * 78); log("ROW 0d -- proxy calibration against known table occupancy at freeze")
    d_count = sum(1 for tok, ts in t_plain_1.items() if ts <= B.FREEZE_CYCLE_TS)
    ratio = d_count / B.HASH_TABLE_SIZE
    log("  D (distinct plaintext callsign-shaped tokens, ts <= %s) = %d" % (B.FREEZE_CYCLE_TS, d_count))
    log("  D / %d = %.4f" % (B.HASH_TABLE_SIZE, ratio))
    ok0d = 0.75 <= ratio <= 1.25
    log("  ROW 0d: %s (bar 0.75 <= D/4096 <= 1.25)" % ("PASS" if ok0d else "FAIL"))
    proxy_is_lower_bound_only = not ok0d and ratio < 0.75

    # ---------------- ROW 0e: determinism, mechanically diffed ----------------
    log("-" * 78); log("ROW 0e -- determinism (same input, run twice)")
    bucket_of_1b, n_theirs_only_1b, b1_keys_1b, per_key_1b = classify_b1(ours_rows_1, theirs_rows)
    key_bucket_1b, callsign_keys_1b, cs_bucket_1b = key_and_callsign_buckets(
        b1_keys_1b, per_key_1b, B.build_t_plain_index(ours_rows_1), B.FREEZE_CYCLE_TS)
    det_ok = (b1_keys_1 == b1_keys_1b
              and key_bucket_1 == key_bucket_1b
              and {k_: v["named"] for k_, v in per_key_1.items()} == {k_: v["named"] for k_, v in per_key_1b.items()})
    log("  byte-identical (b1 keys, key buckets, named callsigns): %s" % ("PASS" if det_ok else "FAIL"))
    if not det_ok:
        void("0e", "classifier is non-deterministic on identical input")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS" if ok0d else "FAIL(non-void)", "0e": "VOID"}}, void_rows)

    # ---------------- ROW 0f: independent-input replicate ----------------
    log("-" * 78); log("ROW 0f -- independent-input replicate (L2_run2)")
    ours_rows_2 = G.rows_from_dump_corrected(l2run2_dump)
    bucket_of_2, n_theirs_only_2, b1_keys_2, per_key_2 = classify_b1(ours_rows_2, theirs_rows)
    t_plain_2 = B.build_t_plain_index(ours_rows_2)
    key_bucket_2, callsign_keys_2, cs_bucket_2 = key_and_callsign_buckets(
        b1_keys_2, per_key_2, t_plain_2, B.FREEZE_CYCLE_TS)
    keys_match = (b1_keys_1 == b1_keys_2)
    named_match = ({k_: v["named"] for k_, v in per_key_1.items()} == {k_: v["named"] for k_, v in per_key_2.items()})
    bucket_match = (key_bucket_1 == key_bucket_2)
    log("  |B1| run1=%d run2=%d, key sets identical: %s" % (len(b1_keys_1), len(b1_keys_2), keys_match))
    log("  named callsigns identical key-for-key: %s" % named_match)
    log("  key buckets identical key-for-key: %s" % bucket_match)
    ok0f = keys_match and named_match and bucket_match
    log("  ROW 0f: %s" % ("PASS" if ok0f else "FAIL"))
    if not ok0f:
        void("0f", "independent replicate (L2_run2) disagrees with L2_run1 -- key-for-key")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS" if ok0d else "FAIL(non-void)", "0e": "PASS", "0f": "VOID"}}, void_rows)

    row0 = {"0a": "PASS", "0b": "PASS", "0c": "PASS",
            "0d": "PASS" if ok0d else ("FAIL(<0.75, lower-bound-only)" if proxy_is_lower_bound_only else "FAIL(>1.25, contaminated)"),
            "0e": "PASS", "0f": "PASS"}

    # ==================== PART A ====================
    log("=" * 78); log("PART A -- addressability, unit = named callsign")
    cs_cov = [x for x, b in cs_bucket_1.items() if b == "CS-cov"]
    cs_cap = [x for x, b in cs_bucket_1.items() if b == "CS-cap"]
    cs_ord = [x for x, b in cs_bucket_1.items() if b == "CS-ord"]
    log("  k = %d   CS-cov=%d  CS-cap=%d  CS-ord=%d" % (k, len(cs_cov), len(cs_cap), len(cs_ord)))

    part_a_row = None
    p_cap_point = p_cap_lo = p_cap_hi = None
    if k < 20:
        part_a_row = "A0"
        log("  ROW A0: UNRESOLVED -- insufficient units (k=%d < 20)" % k)
    else:
        flags = {x: (cs_bucket_1[x] == "CS-cap") for x in cs_bucket_1}
        p_cap_point, p_cap_lo, p_cap_hi = B.bootstrap_proportion_ci(flags)
        log("  p_cap = %.4f (95%% CI [%.4f, %.4f], callsign-level bootstrap n_boot=2000)"
            % (p_cap_point, p_cap_lo, p_cap_hi))
        if p_cap_lo > 0.50:
            part_a_row = "A1"
        elif p_cap_hi < 0.20:
            part_a_row = "A2"
        else:
            part_a_row = "A3"
        log("  ROW %s fires" % part_a_row)

    # ==================== PART B ====================
    part_b_row = None
    p_frozen_point = p_frozen_lo = p_frozen_hi = None
    cap_frozen_list = cap_resident_list = None
    if part_a_row == "A1":
        log("=" * 78); log("PART B -- capacity vs bit-error, unit = named callsign in CS-cap")
        split = cap_frozen_split(cs_cap, t_plain_1, B.FREEZE_CYCLE_TS)
        cap_frozen_list = [x for x, b in split.items() if b == "cap-frozen"]
        cap_resident_list = [x for x, b in split.items() if b == "cap-resident"]
        log("  |CS-cap| = %d   cap-frozen=%d  cap-resident=%d"
            % (len(cs_cap), len(cap_frozen_list), len(cap_resident_list)))
        if len(cs_cap) < 10:
            part_b_row = "B0"
            log("  ROW B0: UNRESOLVED -- insufficient units (|CS-cap|=%d < 10)" % len(cs_cap))
        else:
            flags_b = {x: (split[x] == "cap-frozen") for x in split}
            p_frozen_point, p_frozen_lo, p_frozen_hi = B.bootstrap_proportion_ci(flags_b)
            log("  p_frozen = %.4f (95%% CI [%.4f, %.4f])" % (p_frozen_point, p_frozen_lo, p_frozen_hi))
            if p_frozen_lo > 0.50:
                part_b_row = "B1"
            elif p_frozen_hi < 0.50:
                part_b_row = "B2"
            else:
                part_b_row = "B3"
            log("  ROW %s fires" % part_b_row)
    else:
        log("=" * 78); log("PART B -- NOT RUN (Part A did not fire A1)")

    # ==================== PART C (descriptive) ====================
    log("=" * 78); log("PART C -- descriptive")
    key_bucket_counts = {}
    for key in b1_keys_1:
        key_bucket_counts[key_bucket_1[key]] = key_bucket_counts.get(key_bucket_1[key], 0) + 1
    log("  Four-way B1 partition (decode counts): %s" % key_bucket_counts)

    decodes_per_callsign = sorted((len(v) for v in callsign_keys_1.values()), reverse=True)
    log("  Decodes-per-named-callsign histogram (descending): %s" % decodes_per_callsign)

    corroborated_pp = 100.0 * n_nameable / B.N_THEIRS_PINNED
    log("  Textually-corroborated B1 = %d decodes = %.4f pp of D-001 (n_theirs=%d)"
        % (n_nameable, corroborated_pp, B.N_THEIRS_PINNED))

    same_cycle_ord = sum(1 for key in b1_keys_1
                          if key_bucket_1[key] == "B1-ord"
                          and not per_key_1[key]["amb"]
                          and t_plain_1.get(per_key_1[key]["named"]) == per_key_1[key]["ts"])
    log("  |B1-ord and same-cycle| = %d" % same_cycle_ord)

    dominant = max(callsign_keys_1.items(), key=lambda kv: len(kv[1]), default=None)
    if dominant is not None:
        x, ts_list = dominant
        tplain = t_plain_1.get(x)
        log("  Dominant callsign: %s, %d B1 decodes, T_plain=%s, bucket=%s, vs freeze %s (%s)"
            % (B.redact(x), len(ts_list), tplain, cs_bucket_1.get(x),
               B.FREEZE_CYCLE_TS,
               "post-freeze" if (tplain and tplain >= B.FREEZE_CYCLE_TS) else "pre-freeze" if tplain else "never"))

    n_distinct_session = len(t_plain_1)
    log("  Distinct plaintext callsign-shaped tokens, whole session = %d vs HASH_TABLE_SIZE=%d (x%.1f)"
        % (n_distinct_session, B.HASH_TABLE_SIZE, n_distinct_session / B.HASH_TABLE_SIZE))

    result = {
        "row0": row0,
        "row0d": {"D": d_count, "ratio": ratio, "freeze_cycle_ts": B.FREEZE_CYCLE_TS},
        "part_a": {
            "k": k, "cs_cov": len(cs_cov), "cs_cap": len(cs_cap), "cs_ord": len(cs_ord),
            "row": part_a_row,
            "p_cap": None if p_cap_point is None else {"point": p_cap_point, "ci": [p_cap_lo, p_cap_hi]},
        },
        "part_b": {
            "row": part_b_row,
            "n_cs_cap": None if cs_cap is None else len(cs_cap),
            "cap_frozen": None if cap_frozen_list is None else len(cap_frozen_list),
            "cap_resident": None if cap_resident_list is None else len(cap_resident_list),
            "p_frozen": None if p_frozen_point is None else {"point": p_frozen_point, "ci": [p_frozen_lo, p_frozen_hi]},
        },
        "part_c": {
            "b1_total": len(b1_keys_1),
            "sec2_2_categories": cat_counts,
            "key_bucket_counts": key_bucket_counts,
            "decodes_per_callsign_desc": decodes_per_callsign,
            "corroborated_b1_decodes": n_nameable,
            "corroborated_b1_pp_of_d001": corroborated_pp,
            "b1_ord_same_cycle": same_cycle_ord,
            "distinct_plaintext_tokens_session": n_distinct_session,
            "hash_table_size": B.HASH_TABLE_SIZE,
        },
    }
    return finish(args, log_lines, result, void_rows)


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


if __name__ == "__main__":
    sys.exit(main())
