#!/usr/bin/env python3
"""F-001 D3 ARM 1 -- offline hash-table policy simulation.

Spec: qa/rr-study/2026-08-26-1149-architect-to-qa-spec-f001-d3-arm1-policy-simulation.md

Pure re-analysis of decode dumps already on disk (no rebuild, no replay, no
capture run, no src/ or native/ edit -- Sec.8). Reuses B1-COVERAGE-A's
classifier (run_b1_coverage_a.classify_b1 / key_and_callsign_buckets) and
common_b1's predicates unmodified (Sec.4 ROW 0d; HK-018).

NFR-021: real callsign strings and n22 values live in memory only. result.json
/ run.log / the report carry only counts, cycle timestamps, and sha256[:6]
-redacted CS-xxxxxx tokens (common_b1.redact).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_arm1 as A   # noqa: E402
import common_b1 as B     # noqa: E402
import common_g2a as G    # noqa: E402
import run_b1_coverage_a as RB  # noqa: E402

POLICIES = [
    # id       size    eviction
    ("CUR",    4096,   None),
    ("SZ2",    8192,   None),
    ("SZ4",    16384,  None),
    ("SZ8",    32768,  None),
    ("LRU",    4096,   "LRU"),
    ("LFU",    4096,   "LFU"),
    ("LRU-S",  1024,   "LRU"),
]


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, check=True,
                               cwd=G.REPO_ROOT).stdout.strip()
    except Exception:
        return "unknown"


def sorted_stream(ours_rows):
    return sorted(ours_rows, key=lambda r: (r["ts"], r["freq_hz"], r["message_norm"]))


def simulate(stream, size, eviction, lfail_by_id, cs_cap_set):
    """Replays the insert stream S and lookup stream L (Sec.3) against a
    SimTable(size, eviction). Returns aggregate + per-callsign(cs_cap) tallies.
    `gained`/`lost`/`false_res` are decode-level, whole-session (Sec.5.2);
    `per_cs_gain`/`per_cs_loss` restrict to the 40 CS-cap callsigns (Sec.5.1).
    """
    tbl = A.SimTable(size, eviction)
    gained = lost = false_res = n_lookups = n_charset_fail = 0
    per_cs_gain: dict[str, int] = {}
    per_cs_loss: dict[str, int] = {}
    example = None
    freeze_row_ts = None
    reject_seen = False

    for row in stream:
        for t in row["message_norm"].split():
            if not B.is_callsign_token(t):
                continue
            n22 = A.n22_of(t)
            if n22 is None:
                n_charset_fail += 1
                continue
            before = tbl.reject_count
            tbl.add(t, n22)
            if not reject_seen and tbl.reject_count > before:
                reject_seen = True
                freeze_row_ts = row["ts"]

        target = lfail_by_id.get(id(row))
        if target is not None:
            n22 = A.n22_of(target)
            n_lookups += 1
            res = tbl.lookup(n22) if n22 is not None else None
            if res == target:
                gained += 1
                if target in cs_cap_set:
                    per_cs_gain[target] = per_cs_gain.get(target, 0) + 1
                if example is None:
                    example = {"target": target, "ts": row["ts"], "kind": "L_fail-gained"}
            elif res is not None:
                false_res += 1
            continue

        kind, payload = A.hash_field_in(row["message_norm"])
        if kind == "resolved" and B.is_callsign_token(payload):
            n22 = A.n22_of(payload)
            n_lookups += 1
            res = tbl.lookup(n22) if n22 is not None else None
            if res is None:
                lost += 1
                if payload in cs_cap_set:
                    per_cs_loss[payload] = per_cs_loss.get(payload, 0) + 1
            elif res != payload:
                false_res += 1
            # else: still resolves correctly -- no change

    return {
        "gained": gained, "lost": lost, "false_res": false_res,
        "net": gained - lost - false_res,
        "n_lookups": n_lookups, "n_charset_fail_inserts": n_charset_fail,
        "per_cs_gain": per_cs_gain, "per_cs_loss": per_cs_loss,
        "table_count": tbl.count, "reject_count": tbl.reject_count,
        "freeze_row_ts": freeze_row_ts, "example": example,
    }


def sign_test_two_sided(n_improved: int, n_worsened: int):
    n = n_improved + n_worsened
    if n == 0:
        return None
    k = min(n_improved, n_worsened)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
    return min(1.0, 2.0 * tail)


def classify_callsigns(per_cs_gain, per_cs_loss, callsigns):
    improved = []
    worsened = []
    unchanged = []
    for c in callsigns:
        delta = per_cs_gain.get(c, 0) - per_cs_loss.get(c, 0)
        if delta > 0:
            improved.append(c)
        elif delta < 0:
            worsened.append(c)
        else:
            unchanged.append(c)
    return improved, worsened, unchanged


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
    log("F-001 D3 ARM 1 -- run_arm1.py -- repo main @ %s" % git_sha())
    log("=" * 78)

    log("Loading decode dumps + wav cycle index (no rebuild, no replay)...")
    l2run1_dump, ours_rows_1 = A.load_l2run1_ours_rows()
    theirs_rows = G.load_theirs_rows()
    cycle_list, ts_to_idx = A.load_cycle_index()
    log("  cycle index: %d wav cycles (expect %d)" % (len(cycle_list), A.EXPECTED_N_WAVS))

    # ---------------- ROW 0a: dump identity ----------------
    log("-" * 78); log("ROW 0a -- dump identity")
    ident1 = B.check_dump_identity(l2run1_dump)
    log("  L2_run1: %s" % ident1)
    ok0a = (ident1["dll_sha256"] == B.EXPECTED_L2_SHA256
            and ident1["shim_version"] == B.EXPECTED_L2_SHIM_VERSION
            and ident1["n_decodes"] == B.EXPECTED_N_DECODES
            and ident1["n_records"] == B.EXPECTED_N_DECODES)
    log("  ROW 0a: %s" % ("PASS" if ok0a else "FAIL"))
    if not ok0a:
        void("0a", "dump identity does not match the pinned spec inputs")
        return finish(args, log_lines, {"row0": {"0a": "VOID"}}, void_rows)

    stream = sorted_stream(ours_rows_1)

    # ---------------- build B1-cap population (needed by 0e/0f/0g/Sec.5) ----
    pop_info = A.build_b1cap_population(ours_rows_1, theirs_rows)
    cs_cap = pop_info["cs_cap"]
    cs_cap_set = set(cs_cap)
    lfail_by_id, missing = A.locate_lfail_rows(ours_rows_1, theirs_rows, pop_info)
    t_plain_1 = pop_info["t_plain"]

    # ---------------- ROW 0b: simulator fidelity (load-bearing) ------------
    log("-" * 78); log("ROW 0b -- simulator fidelity (load-bearing)")
    res_cur_l2 = simulate(stream, 4096, None, {}, set())
    freeze_idx_l2 = ts_to_idx.get(res_cur_l2["freeze_row_ts"]) if res_cur_l2["freeze_row_ts"] else None
    log("  CUR @ N=4096 on L2_run1: freeze ts=%s -> cycle index %s (bar [767,1150])"
        % (res_cur_l2["freeze_row_ts"], freeze_idx_l2))
    ok0b_l2 = freeze_idx_l2 is not None and 767 <= freeze_idx_l2 <= 1150

    l1_dump, ours_rows_l1 = A.load_l1_ours_rows()
    stream_l1 = sorted_stream(ours_rows_l1)
    res_cur_l1 = simulate(stream_l1, 256, None, {}, set())
    freeze_idx_l1 = ts_to_idx.get(res_cur_l1["freeze_row_ts"]) if res_cur_l1["freeze_row_ts"] else None
    log("  CUR @ N=256 on L1: freeze ts=%s -> cycle index %s (bar [25,40])"
        % (res_cur_l1["freeze_row_ts"], freeze_idx_l1))
    ok0b_l1 = freeze_idx_l1 is not None and 25 <= freeze_idx_l1 <= 40

    ok0b = ok0b_l2 and ok0b_l1
    log("  ROW 0b: %s" % ("PASS" if ok0b else "FAIL"))
    if not ok0b:
        void("0b", "simulator does not reproduce the two independently measured freeze cycles")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "VOID"},
                                         "row0b_detail": {"freeze_idx_l2_n4096": freeze_idx_l2,
                                                           "freeze_idx_l1_n256": freeze_idx_l1}}, void_rows)

    # ---------------- ROW 0c: hash-port sanity ----------------
    log("-" * 78); log("ROW 0c -- hash-port sanity")
    distinct_tokens = list(t_plain_1.keys())
    n_distinct = len(distinct_tokens)
    n22_map = {}
    n_none = 0
    for tok in distinct_tokens:
        v = A.n22_of(tok)
        if v is None:
            n_none += 1
        else:
            n22_map.setdefault(v, []).append(tok)
    frac_ok = (n_distinct - n_none) / n_distinct if n_distinct else 0.0
    n_collision_pairs = sum(math.comb(len(v), 2) for v in n22_map.values() if len(v) >= 2)
    n_colliding_buckets = sum(1 for v in n22_map.values() if len(v) >= 2)
    log("  distinct session plaintext callsign-shaped tokens = %d (expect 16320)" % n_distinct)
    log("  n22_of() non-None rate = %.4f%% (%d charset failures)" % (100.0 * frac_ok, n_none))
    log("  n22 collisions: %d colliding buckets, %d colliding pairs (birthday expectation ~32)"
        % (n_colliding_buckets, n_collision_pairs))
    ok0c = (frac_ok >= 0.99) and (10 <= n_collision_pairs <= 100)
    log("  ROW 0c: %s (bar: >=99%% non-None; 10<=collision pairs<=100)" % ("PASS" if ok0c else "FAIL"))
    if not ok0c:
        void("0c", "hash port sanity failed -- charset/mask defect suspected")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "VOID"}}, void_rows)

    # ---------------- ROW 0d: predicate reuse ----------------
    log("-" * 78); log("ROW 0d -- predicate reuse (assert by import)")
    ok0d = (RB.B.is_callsign_token is B.is_callsign_token) and (A.B.is_callsign_token is B.is_callsign_token)
    log("  is_callsign_token is the SAME function object across common_arm1/common_b1/run_b1_coverage_a: %s" % ok0d)
    log("  ROW 0d: %s" % ("PASS" if ok0d else "FAIL"))
    if not ok0d:
        void("0d", "token predicate was re-implemented rather than imported")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "VOID"}}, void_rows)

    # ---------------- ROW 0e: determinism + independent input ----------------
    log("-" * 78); log("ROW 0e -- determinism + independent input")
    cur_a = simulate(stream, 4096, None, lfail_by_id, cs_cap_set)
    cur_b = simulate(stream, 4096, None, lfail_by_id, cs_cap_set)
    det_cur = (cur_a["per_cs_gain"] == cur_b["per_cs_gain"] and cur_a["per_cs_loss"] == cur_b["per_cs_loss"]
               and cur_a["gained"] == cur_b["gained"] and cur_a["lost"] == cur_b["lost"]
               and cur_a["false_res"] == cur_b["false_res"])
    lru_a = simulate(stream, 4096, "LRU", lfail_by_id, cs_cap_set)
    lru_b = simulate(stream, 4096, "LRU", lfail_by_id, cs_cap_set)
    det_lru = (lru_a["per_cs_gain"] == lru_b["per_cs_gain"] and lru_a["per_cs_loss"] == lru_b["per_cs_loss"]
               and lru_a["gained"] == lru_b["gained"] and lru_a["lost"] == lru_b["lost"]
               and lru_a["false_res"] == lru_b["false_res"])
    log("  CUR byte-identical on rerun: %s ; LRU byte-identical on rerun: %s" % (det_cur, det_lru))

    l2run2_dump, ours_rows_2 = A.load_l2run2_ours_rows()
    stream_2 = sorted_stream(ours_rows_2)
    res_cur_l2run2 = simulate(stream_2, 4096, None, {}, set())
    freeze_idx_l2run2 = ts_to_idx.get(res_cur_l2run2["freeze_row_ts"]) if res_cur_l2run2["freeze_row_ts"] else None
    indep_ok = (freeze_idx_l2run2 == freeze_idx_l2)
    log("  L2_run2 CUR freeze cycle index = %s vs L2_run1's %s: reproduces = %s"
        % (freeze_idx_l2run2, freeze_idx_l2, indep_ok))

    ok0e = det_cur and det_lru and indep_ok
    log("  ROW 0e: %s" % ("PASS" if ok0e else "FAIL"))
    if not ok0e:
        void("0e", "non-deterministic simulator, or independent-input replicate disagrees")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "VOID"}}, void_rows)

    # ---------------- ROW 0f: population reproduction ----------------
    log("-" * 78); log("ROW 0f -- population reproduction")
    n_b1cap = len(pop_info["b1cap_keys"])
    n_cs_cap = len(cs_cap)
    log("  |L_fail| (B1-cap decodes) = %d (expect 307)   distinct CS-cap callsigns = %d (expect 40)"
        % (n_b1cap, n_cs_cap))
    log("  rows located for lookup replay = %d, missing (candidate-search failed) = %d"
        % (len(lfail_by_id), len(missing)))
    ok0f = (n_b1cap == 307) and (n_cs_cap == 40) and (len(missing) == 0)
    log("  ROW 0f: %s" % ("PASS" if ok0f else "FAIL"))
    if not ok0f:
        void("0f", "population does not reproduce B1-COVERAGE-A's own result.json (307/40)")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "PASS", "0f": "VOID"},
                                         "row0f_detail": {"n_b1cap": n_b1cap, "n_cs_cap": n_cs_cap, "n_missing": len(missing)}}, void_rows)

    # ---------------- ROW 0g: predicate-movement exhibit ----------------
    log("-" * 78); log("ROW 0g -- predicate-movement exhibit (HK-021(q))")
    res_sz8 = simulate(stream, 32768, None, lfail_by_id, cs_cap_set)
    log("  SZ8 (32768 slots) final table occupancy = %d / 32768 against %d distinct session callsigns (never fills)"
        % (res_sz8["table_count"], len(t_plain_1)))
    log("  SZ8 reject_count = %d (must be 0)" % res_sz8["reject_count"])
    log("  SZ8 gained = %d / %d L_fail decodes (bar: 100%%)" % (res_sz8["gained"], n_b1cap))
    ok0g = (res_sz8["reject_count"] == 0) and (res_sz8["gained"] == n_b1cap)
    if res_sz8["example"] is not None:
        ex_target = res_sz8["example"]["target"]
        ex_ts = res_sz8["example"]["ts"]
        ex_tplain = t_plain_1.get(ex_target)
        log("  WORKED EXAMPLE: %s  T_plain=%s  B1 ts=%s  resolved-under-SZ8=True  failed-under-CUR(empirical B1-cap)=True"
            % (B.redact(ex_target), ex_tplain, ex_ts))
    log("  ROW 0g: %s" % ("PASS" if ok0g else "FAIL"))
    if not ok0g:
        void("0g", "a table that structurally cannot fill still failed to resolve a resident callsign -- lookup path broken")
        return finish(args, log_lines, {"row0": {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS",
                                                   "0e": "PASS", "0f": "PASS", "0g": "VOID"},
                                         "row0g_detail": {"gained": res_sz8["gained"], "reject_count": res_sz8["reject_count"]}}, void_rows)

    row0 = {"0a": "PASS", "0b": "PASS", "0c": "PASS", "0d": "PASS", "0e": "PASS", "0f": "PASS", "0g": "PASS"}

    # ==================== Sec.5: run every policy ====================
    log("=" * 78); log("Sec.5 -- running all policies")
    policy_results = {}
    for pid, size, evict in POLICIES:
        r = simulate(stream, size, evict, lfail_by_id, cs_cap_set)
        policy_results[pid] = r
        log("  %-6s N=%-6d evict=%-4s  gained=%3d lost=%3d false=%3d net=%4d  table_count=%d reject=%d"
            % (pid, size, evict or "-", r["gained"], r["lost"], r["false_res"], r["net"], r["table_count"], r["reject_count"]))

    # identify the dominant callsign (redacted "CS-235335" per the ruling) for leave-one-out
    dominant = None
    for c in cs_cap:
        if B.redact(c) == "CS-235335":
            dominant = c
            break
    log("  Leave-one-out target located: %s" % (B.redact(dominant) if dominant else "NOT FOUND"))

    # ==================== Sec.5.1: primary gate (k=40) ====================
    log("=" * 78); log("Sec.5.1 -- PRIMARY: callsign-level net recall (k=40)")
    primary = {}
    fired_rows = []
    for pid, size, evict in POLICIES:
        if pid == "CUR":
            continue
        r = policy_results[pid]
        improved, worsened, unchanged = classify_callsigns(r["per_cs_gain"], r["per_cs_loss"], cs_cap)
        n_imp, n_wor = len(improved), len(worsened)
        n_disc = n_imp + n_wor
        p_val = sign_test_two_sided(n_imp, n_wor)
        all_one_way = (n_wor == 0 and n_imp > 0) or (n_imp == 0 and n_wor > 0)

        # leave-one-out
        loo_callsigns = [c for c in cs_cap if c != dominant] if dominant else cs_cap
        imp_loo, wor_loo, unc_loo = classify_callsigns(r["per_cs_gain"], r["per_cs_loss"], loo_callsigns)
        n_imp_loo, n_wor_loo = len(imp_loo), len(wor_loo)
        p_loo = sign_test_two_sided(n_imp_loo, n_wor_loo)

        if n_disc < 6:
            row = "P0"
        elif all_one_way and n_disc >= 6 and p_val is not None and p_val < 0.05 and r["net"] > 0:
            row = "P1"
        elif r["net"] <= 0 and pid == max(policy_results, key=lambda k: policy_results[k]["net"]):
            row = "P2"
        else:
            row = "P3"
        fired_rows.append((pid, row))

        primary[pid] = {
            "n_improved": n_imp, "n_worsened": n_wor, "n_unchanged": len(unchanged),
            "n_discordant": n_disc, "p_value_two_sided": p_val, "row": row,
            "net_decode_level": r["net"],
            "leave_one_out": {"n_improved": n_imp_loo, "n_worsened": n_wor_loo,
                               "n_discordant": n_imp_loo + n_wor_loo, "p_value_two_sided": p_loo},
        }
        log("  %-6s improved=%2d worsened=%2d unchanged=%2d n_discordant=%2d p=%s net=%4d -> ROW %s"
            % (pid, n_imp, n_wor, len(unchanged), n_disc,
               ("%.4f" % p_val if p_val is not None else "n/a"), r["net"], row))
        log("       leave-one-out (CS-235335 removed, k=39): improved=%d worsened=%d n_discordant=%d p=%s"
            % (n_imp_loo, n_wor_loo, n_imp_loo + n_wor_loo, ("%.4f" % p_loo if p_loo is not None else "n/a")))

    best_net_policy = max((pid for pid, _, _ in POLICIES if pid != "CUR"), key=lambda k: policy_results[k]["net"])
    overall_p2 = policy_results[best_net_policy]["net"] <= 0
    log("  Best net policy: %s (net=%d) -> overall P2 (CLOSE F-001 D3): %s"
        % (best_net_policy, policy_results[best_net_policy]["net"], overall_p2))

    # ==================== Sec.5.3: descriptive ====================
    log("=" * 78); log("Sec.5.3 -- descriptive (ungated)")
    for pid, size, evict in POLICIES:
        r = policy_results[pid]
        role = "enlargement/bounded-session" if evict is None and pid != "CUR" else ("eviction/unbounded-daemon" if evict else "baseline")
        log("  %-6s (%s): recovers %d/%d addressable B1-cap decodes, net=%d" % (pid, role, r["gained"], n_b1cap, r["net"]))

    result = {
        "row0": row0,
        "inputs": {
            "n_decodes_l2run1": ident1["n_decodes"],
            "n_b1cap_decodes": n_b1cap, "n_cs_cap": n_cs_cap,
            "n_distinct_session_tokens": len(t_plain_1),
            "freeze_idx_l2run1_n4096": freeze_idx_l2, "freeze_idx_l1_n256": freeze_idx_l1,
        },
        "hash_type_note": "100 percent of lookups used the 22-bit fallback (see common_arm1.py module docstring); "
                           "residency (Sec.5.1) is unaffected, Sec.5.2 false-resolution counts are indicative only.",
        "policies": {pid: {"size": size, "eviction": evict, **{k: v for k, v in policy_results[pid].items()
                                                                  if k not in ("per_cs_gain", "per_cs_loss", "example")}}
                     for pid, size, evict in POLICIES},
        "primary_sec5_1": primary,
        "best_net_policy": best_net_policy,
        "overall_p2_close_f001_d3": overall_p2,
        "dominant_callsign_redacted": B.redact(dominant) if dominant else None,
    }
    return finish(args, log_lines, result, void_rows)


if __name__ == "__main__":
    sys.exit(main())
