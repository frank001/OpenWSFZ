#!/usr/bin/env python
"""DENSITY-REMEDY Stage 3 -- live-replay pricing of the Stage 2 finalists on real C2 audio.

================================================================================
PRE-REGISTRATION -- committed BEFORE any leg is decoded (HK-021: mechanical bars)
================================================================================
Spec  : qa/rr-study/2026-09-19-1228-architect-to-qa-spec-density-remedy-suppression.md S6, AS RULED BY S17 + S18 (arch/density 6bf2bd03).
        Captain's go: "start stage 3" (2026-09-20).  Stage 3 PRICES; it ships nothing; NO default changes anywhere in this arm.
Binary: decoding_improvement fa8a56ae, libft8.dll SHA-256 38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba, shim 20260054.  ONE DLL for
        every leg (extracted with `git show`, SHA-verified in every leg process; the working-tree DLL is never used).
Corpus: C2 = live-gap-now `corpus.c2_cycles()` (sorted by timestamp), audio path = p23_common.read_wav + normalise_rms(0.20) (the production-mirroring path
        LIVE-GAP-NOW used).  REF = WSJT-X #1 (C2_DIR/wsjtx-1-ft991a/ALL.TXT) via analyse.load_ref_c2(); live = analyse.load_live_c2_openwsfz().
        DENOMINATOR (S18(e)): the leg's OWN EXECUTED cycle count, mechanically recorded, is the denominator of every rate.  Catalogue figures are CONTEXT ONLY:
        corpus.c2_cycles() = 5,222 vs DENSITY-LIVE S1 = 4,113 (a 21% disagreement) is an OPEN RECONCILIATION ITEM, stated, neither chosen.
NFR-021: C2 carries REAL callsigns.  Every leg output lives in gitignored artefacts/; committed files and reports carry COUNTS only; message text is held in
        memory for matching and NEVER printed.  Never print a `<...>`-versus-resolved rendering as an illustration (the resolved side is a real callsign, S18(f)).

LEGS (one PROCESS per leg, fresh; decode params (10, 0.10, nhard) set ONCE before the first decode and READ BACK through ft8_get_decoder_params):
  V60   nhard 60, suppression setter NEVER called   -- 0a-pipeline (reproduce C2 on the current DLL at the LIVE nhard).  NOT a Stage 3 measure leg.
  V0    nhard 40, setter never called               -- the baseline leg (S6.1 params (10, 0.10, 40)).
  VN    nhard 40, setter called ONCE with (-5,+15,1.0) -- the NULL leg (HK-021(z)); same inputs, same order, same params as V0.
  F1    nhard 40, setter ONCE with (-5,+15,0.0)     -- finalist 1  (side weight 0.0).   F2  nhard 40, (-5,+15,0.5) -- finalist 2.
  S1,S2 nhard 40, setter never called, on the 100-CYCLE SUBSET, two fresh processes -- 0b determinism.
  SUBSET = cycles[::len(cycles)//100][:100] of the sorted C2 list.  The setter is called once, before the first decode, and read back with ft8_get_supp_params.
  🛑 F1 and F2 REFUSE TO RUN until results/stage3_ratified.json exists (Captain's ratification of the U_base rule and GAIN_BAR, S6.4 / S18(d)).

ROW 0 (any fires => STOP, report, NO re-cut):
  0a-pipeline (GATES, S18(c)): the share of OpenWSFZ's LIVE-EMITTED C2 decodes that the V60 leg reproduces, E3-0's rule: a live decode (cycle, freq, text) is
      reproduced iff V60 has a decode in the SAME cycle with |dfreq| <= 3 Hz and wildcard_match(live_text, replay_text).  share >= 0.90 or it FIRES.
      Measured on the V60 leg FIRST.  PRE-COMMITMENT (written now): if it fires we FIND THE LOSS; we do NOT lower the bar.  A value in [0.90, 0.93] is reported as NEAR-BAR.
  0a-delta (REPORTED, never gated): the same share for the V0 (nhard 40) leg, i.e. the decoder delta since C2, interesting in itself.
  0b  S1 and S2 (fresh processes, the 100-cycle subset) are BYTE-IDENTICAL, text included.
  0c  DENSITY-LIVE S4.1's placebo D(PL,PF) with TEST = the V0 leg, density_live's own predicate verbatim: CI95 within +-0.05 (lo >= -0.05 and hi <= +0.05).
  0d  every leg's header: SHA + version == pin; decode params read back == (10, 0.10 as float32, nhard); suppression triple read back == the registered triple
      (V60/V0/S1/S2: the defaults (-5,15,1.0), setter never called); F1/F2 headers agree; all legs executed the SAME cycle list (sha256 of the timestamps).
  0e  NULL (S18(b), ASSERTION SPLIT): VN vs V0 per cycle.  OUTCOME FIELDS (frequency, SNR, dt, and the number of decodes) identical on EVERY cycle, else STOP;
      u_add = k_add = k_rem = 0 and DeltaR = 0 EXACTLY.  TEXT equality is asserted too: if it fires => STOP AND HAND IT TO THE ARCHITECT.  With the history matched
      (same audio, same order, same params) a text difference means an unidentified history channel, which is NEW INFORMATION: NEVER waved through by citing S16.
      VN can never be a finalist.
  Ordering: V60 + V0 (+VN, S1, S2) first; 0a/0b/0c/0d/0e are evaluated and U_base is computed from the V0 leg ALONE.  No finalist leg exists yet.

PAIRING between legs (S18(a); the key is HISTORY-FREE, text is a tie-break only):
  Per cycle, decodes of V0 are processed in ascending (freq, text, dt) order against the still-unmatched decodes of the variant leg.  Candidates = variant decodes
  with |dfreq| <= 3 Hz.  0 candidates => the V0 decode is REMOVED.  1 candidate => paired.  >1 => TIE-BREAK: keep candidates for which wildcard_match holds in
  EITHER direction (if none, keep all), then take the smallest |dfreq|, then the lowest (freq, text).  Every variant decode left unpaired is ADDED.
  REPORTED: the number of tie-break events and how many used text.  No SNR band in the key (live SNR wanders and would split true pairs).
CORROBORATION (S18(a) asymmetry): a decode is corroborated iff REF (WSJT-X #1) has a row in the SAME cycle, |dfreq| <= 3 Hz, and EXACTLY the same
  whitespace-normalised text ("K").  A match that succeeds ONLY through wildcard_match is "W": it counts as UNCORROBORATED and is REPORTED as the
  wildcard-dependent share of u_add / k_add / k_rem.  Generous wildcard matching is right for PAIRING and wrong for CORROBORATION (it manufactures corroboration,
  shrinks u_add and hides FP in the arm whose purpose is pricing FP).
MEASURES per finalist (against V0):
  u_add = added decodes not "K";  k_add = added decodes that are "K";  k_rem = removed decodes that are "K" (a removed "W" is uncorroborated and is REPORTED, not counted).
  U_base = (V0 decodes not "K") / (all V0 decodes)  -- a POINT estimate, the V0 leg's own executed decodes, computed ONCE from the V0 leg BEFORE any finalist leg
           and FROZEN on ratification.  (S6.3)
  DeltaR = R_wild(variant) - R_wild(V0) in percentage points, matcher.recovery() vs REF, verbatim (net: gains minus corroborated losses).
  DeltaC = C(V0) - C(variant), density_live's classifier and standardisation, C = D_primary(EXPOSED,PL) * n_EXPOSED / 91,046 * 100 with TEST = each leg.  REPORTED.
  CHURN (reported, never gated): total added and total removed, and the same split by K / W / U.
VERDICT per finalist, FP first, first match wins (S6.4, verbatim):
    row0_fires                                        => "ROW 0 STOP"
    u_add + k_add == 0                                => "ROW N - REJECT: adds nothing"
    clopper_pearson_95(u_add, u_add + k_add)[1] > U_base  => "ROW F - REJECT: the additions are dirtier than what we already emit"
    DeltaR < GAIN_BAR                                 => "ROW N - REJECT: FP-clean but not worth it"
    else                                              => "ROW S - SHIP-ELIGIBLE (Captain, HK-010)"
  GAIN_BAR (proposed 0.5 pp of R_wild) and the U_base RULE need the CAPTAIN'S RATIFICATION after the V0 leg and before any finalist leg; the ratified GAIN_BAR is
  recorded BESIDE the U_base value it was derived from (results/stage3_ratified.json); moving either after a finalist leg exists VOIDS Stage 3 (S6.4, S18(d)).
STRATIFICATIONS (S18.7, PRE-REGISTERED, MANDATORY TO REPORT, FORBIDDEN TO READ A VERDICT FROM):  for each finalist, over the REF rows that variant recovers and
  V0 does not (gained) and the reverse (lost), by hit_set difference, each with Stage 0's dominant_neighbour (highest SNR within 18 Hz, SNR >= the victim's):
  (1) by the BLOCKER'S REPORTED SNR IN THE V0 LEG:  >= +5,  < +5,  blocker not decoded by V0 ("N0"),  ambiguous,  no neighbour;
  (2) by DELTA-F band (Stage 0's df_band: 0-6, 7-12, 13-18 Hz) or "no neighbour".   Reported as gained / lost / net.  They arbitrate the Stage 0 / Stage 2 tension.
NOT A GATE: churn, tie-break counts, wildcard-dependent shares, the stratifications, DeltaC, the 0a-delta share.

WHAT THIS CANNOT SEE (S7 + QA): one corpus (C2, 20 m, two days), a replay is not the live path, neighbours WSJT-X did not decode are invisible, the C2 live leg ran
an older binary at nhard 60, raw C-ABI replay WITHOUT IsPlausibleMessage or text dedup (junk the app would filter counts against BOTH legs), corroboration bounds
genuine gain from below and u_add bounds FP from above (uncorroborated != false), and the Stage 2 bench footprint effect is a SWITCH in strong-blocker cells
while Stage 0 found live RB flat in delta-f: this stage TESTS that, it does not assume it.  Windows DLL only.
"""
import argparse
import collections
import ctypes
import hashlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage1_accept_readout as H  # noqa: E402  (re-pinned instrument; sets sys.path for the rr-study helpers)

S1 = H.S1
REPO_ROOT = H.REPO_ROOT
QA_RR = os.path.join(REPO_ROOT, "qa", "rr-study")
for _p in (os.path.join(QA_RR, "live-gap-now"), os.path.join(QA_RR, "density-live"), os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
import corpus  # noqa: E402
import matcher  # noqa: E402
import analyse as AN  # noqa: E402
import leg_output as LO  # noqa: E402
import p23_common  # noqa: E402
import density_live as DL  # noqa: E402
from h1_hash_token_contamination import wildcard_match  # noqa: E402
import stage0_census as S0  # noqa: E402

OUT_DIR = os.path.join(REPO_ROOT, "artefacts", "density-remedy-stage3")
RESULTS = os.path.join(HERE, "results")
RATIFIED = os.path.join(RESULTS, "stage3_ratified.json")
DLL_SHA, DLL_VER = H.NEW_SHA, H.NEW_VER
TOL_HZ = 3.0
REPRO_BAR, REPRO_NEAR_HI = 0.90, 0.93
PLACEBO_BAR = DL.BAR_0A
SUBSET_N = 100
MAX_RESULTS = p23_common.MAX_RESULTS
CATALOGUE_C2, DENSITY_LIVE_C2 = 5222, 4113
DEFAULT_TRIPLE = (-5.0, 15.0, 1.0)
LEGS = {
    "V60": {"nhard": 60, "supp": None, "subset": False},
    "V0": {"nhard": 40, "supp": None, "subset": False},
    "VN": {"nhard": 40, "supp": (-5.0, 15.0, 1.0), "subset": False},
    "F1": {"nhard": 40, "supp": (-5.0, 15.0, 0.0), "subset": False},
    "F2": {"nhard": 40, "supp": (-5.0, 15.0, 0.5), "subset": False},
    "S1": {"nhard": 40, "supp": None, "subset": True},
    "S2": {"nhard": 40, "supp": None, "subset": True},
}
FINALISTS = ("F1", "F2")


def log(m):
    print(m, flush=True)


def norm(msg):
    return " ".join(msg.split())


def leg_paths(leg):
    return os.path.join(OUT_DIR, "%s.jsonl" % leg), os.path.join(OUT_DIR, "%s.meta.json" % leg)


def cycle_list(subset):
    cycles, dup = corpus.c2_cycles()
    cycles = sorted(cycles)
    if subset:
        cycles = cycles[::len(cycles) // SUBSET_N][:SUBSET_N]
        assert len(cycles) == SUBSET_N, len(cycles)
    return cycles, dup


# ── leg runner ─────────────────────────────────────────────────────────────────
def cmd_leg(a):
    cfg = LEGS[a.leg]
    if a.leg in FINALISTS and not os.path.exists(RATIFIED):
        raise SystemExit("REFUSED: %s is a finalist leg and %s does not exist (Captain's ratification of the U_base rule and GAIN_BAR comes first)" % (a.leg, RATIFIED))
    os.makedirs(OUT_DIR, exist_ok=True)
    out, meta_p = leg_paths(a.leg)
    for p in (out, meta_p):
        S1.ensure_ignored(p)
    cycles, dup = cycle_list(cfg["subset"])
    d, sha = H.load_new_dll()                                              # SHA + version pin or STOP
    dec = p23_common.Decoder(path=os.path.join(H.BIN_DIR, "libft8_NEW.dll"), verify=True, expected_sha256=DLL_SHA, expected_shim_version=DLL_VER)
    dec.dll.ft8_set_decode_params(10, ctypes.c_float(0.10), cfg["nhard"])  # ONCE, before the first decode
    tbl = {e["name"]: e for e in H.read_table(d)}
    table_ok = (tbl["k_min_score_pass2"]["value"] == 10.0 and tbl["osd_nhard_max"]["value"] == float(cfg["nhard"])
                and tbl["osd_corr_threshold"]["value"] == H.f32(0.10))
    if cfg["supp"] is not None:
        assert H.set_supp(d, *cfg["supp"]) == 0
    rc, got = H.get_supp(d)
    want = cfg["supp"] if cfg["supp"] is not None else DEFAULT_TRIPLE
    supp_ok = (rc == 0 and H.bits3(got) == H.bits3(want))
    t0 = time.time()
    n_trunc = n_av = 0
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for i, (ts, wav) in enumerate(cycles):
            pcm = p23_common.normalise_rms(p23_common.read_wav(wav), p23_common.PROD_TARGET_RMS)
            res = dec.decode(pcm)
            rec = {"ts": ts, "results": (res if res is not None else [])}
            if res is None:
                rec["note"] = "AV"
                n_av += 1
            if res is not None and len(res) == MAX_RESULTS:
                n_trunc += 1
            fh.write(json.dumps(rec) + "\n")
            if (i + 1) % 250 == 0:
                fh.flush()
                log("[%s] %d/%d cycles (%.1f/s)" % (a.leg, i + 1, len(cycles), (i + 1) / (time.time() - t0)))
    meta = {"leg": a.leg, "sha": sha, "version": DLL_VER, "nhard": cfg["nhard"], "supp_registered": list(want), "supp_readback": list(got),
            "table_ok": bool(table_ok), "supp_ok": bool(supp_ok), "n_cycles_executed": len(cycles), "n_truncated_at_max": n_trunc, "n_av": n_av,
            "cycle_list_sha256": hashlib.sha256("\n".join(c[0] for c in cycles).encode()).hexdigest(), "catalogue_c2": len(cycle_list(False)[0]),
            "dup_excluded": dup, "elapsed_s": time.time() - t0}
    with open(meta_p, "w") as f:
        json.dump(meta, f, indent=1)
    log("DONE %s: %d cycles in %.0f s (table_ok=%s supp_ok=%s truncated=%d av=%d)" % (a.leg, len(cycles), meta["elapsed_s"], table_ok, supp_ok, n_trunc, n_av))


# ── loading / pairing / corroboration ─────────────────────────────────────────────
def load_meta(leg):
    with open(leg_paths(leg)[1]) as f:
        return json.load(f)


def load_full(leg):
    return LO.load_leg_full(leg_paths(leg)[0])          # {ts: [(freq_hz, dt, snr, message)]}


def load_dict(leg):
    return LO.load_leg_jsonl(leg_paths(leg)[0])         # {(ts, message): (snr, freq_hz)}


def ref_by_ts(ref_all):
    out = {}
    for (ts, msg), (_snr, f) in ref_all.items():
        out.setdefault(ts, []).append((msg, f))
    return out


def corr_class(rb, ts, msg, freq):
    """'K' strictly corroborated (exact normalised text), 'W' corroborated ONLY through the wildcard (counts UNCORROBORATED), 'U' no match."""
    wild = False
    for rmsg, rf in rb.get(ts, []):
        if abs(freq - rf) > TOL_HZ:
            continue
        if norm(msg) == norm(rmsg):
            return "K"
        if wildcard_match(msg, rmsg):
            wild = True
    return "W" if wild else "U"


def pair_cycle(v0, vf):
    """S18(a). v0, vf: lists of (freq, dt, snr, msg). Returns (pairs, added_idx, removed_idx, tiebreak_events, tiebreak_used_text)."""
    A = sorted(range(len(v0)), key=lambda i: (v0[i][0], v0[i][3], v0[i][1]))
    used, pairs, removed, tb, tbt = set(), [], [], 0, 0
    for ia in A:
        a = v0[ia]
        cands = [ib for ib in range(len(vf)) if ib not in used and abs(vf[ib][0] - a[0]) <= TOL_HZ]
        if not cands:
            removed.append(ia)
            continue
        if len(cands) > 1:
            tb += 1
            wc = [ib for ib in cands if wildcard_match(a[3], vf[ib][3]) or wildcard_match(vf[ib][3], a[3])]
            if wc:
                tbt += 1
                cands = wc
            ib = min(cands, key=lambda i: (abs(vf[i][0] - a[0]), vf[i][0], vf[i][3]))
        else:
            ib = cands[0]
        used.add(ib)
        pairs.append((ia, ib))
    added = [ib for ib in range(len(vf)) if ib not in used]
    return pairs, added, removed, tb, tbt


def cp95(k, n, alpha=0.05):
    from scipy.stats import beta as B
    lo = 0.0 if k == 0 else float(B.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(B.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def repro_share(leg, live):
    """E3-0's rule on the leg's OWN executed cycles."""
    full = load_full(leg)
    n = rep = 0
    for (ts, msg), (_snr, f) in live.items():
        if ts not in full:
            continue
        n += 1
        if any(abs(rf - f) <= TOL_HZ and wildcard_match(msg, rm) for rf, _dt, _s, rm in full[ts]):
            rep += 1
    return rep, n


def C_of(leg_dict, ref_all, by_cycle, classes):
    rec = matcher.recovery(leg_dict, ref_all)
    per_class = DL.build_rows(classes, ref_all, rec["hit_set"])
    D, *_ = DL.point_estimate(per_class, "EXPOSED", "PL")
    n_exp = len(per_class.get("EXPOSED", []))
    return D * n_exp / 91046.0 * 100.0, D, rec, per_class


# ── ROW 0 + U_base (V0-side only; no finalist leg is read) ────────────────────────────
def cmd_row0(a):
    R, fails = {"dll_sha256": DLL_SHA, "catalogue_c2_cycles": CATALOGUE_C2, "density_live_c2_cycles": DENSITY_LIVE_C2, "open_reconciliation_item": "5,222 vs 4,113 (21%)"}, []
    metas = {l: load_meta(l) for l in ("V60", "V0", "VN", "S1", "S2")}
    # 0d
    row0d = all(m["sha"] == DLL_SHA and m["version"] == DLL_VER and m["table_ok"] and m["supp_ok"] for m in metas.values())
    row0d = row0d and len({metas[l]["cycle_list_sha256"] for l in ("V60", "V0", "VN")}) == 1 and metas["S1"]["cycle_list_sha256"] == metas["S2"]["cycle_list_sha256"]
    # 0b
    row0b = open(leg_paths("S1")[0], "rb").read() == open(leg_paths("S2")[0], "rb").read()
    live = AN.load_live_c2_openwsfz()
    ref_all = AN.load_ref_c2()
    # 0a-pipeline (gates) and 0a-delta (reported)
    rep60, n60 = repro_share("V60", live)
    rep40, n40 = repro_share("V0", live)
    share60, share40 = rep60 / float(n60), rep40 / float(n40)
    row0a = share60 >= REPRO_BAR
    # 0c placebo on V0
    by_cycle = DL.build_by_cycle(ref_all)
    classes = DL.classify_population(ref_all, by_cycle)
    v0d = load_dict("V0")
    rec0 = matcher.recovery(v0d, ref_all)
    per_class = DL.build_rows(classes, ref_all, rec0["hit_set"])
    D0, *_ = DL.point_estimate(per_class, "PL", "PF")
    boot, _nf = DL.bootstrap_D(per_class, [("PL", "PF")])
    lo, hi = DL.ci95(boot[("PL", "PF")])
    row0c = (lo >= -PLACEBO_BAR) and (hi <= PLACEBO_BAR)
    # 0e null
    f0, fn = load_full("V0"), load_full("VN")
    outcome_eq = (set(f0) == set(fn)) and all(sorted((f, dt, s) for f, dt, s, _m in f0[t]) == sorted((f, dt, s) for f, dt, s, _m in fn[t]) for t in f0)
    text_eq = (set(f0) == set(fn)) and all(sorted(m for *_x, m in f0[t]) == sorted(m for *_x, m in fn[t]) for t in f0)
    ndiff_text = sum(1 for t in f0 if sorted(m for *_x, m in f0[t]) != sorted(m for *_x, m in fn[t]))
    R["row0"] = {"0a_pipeline": bool(row0a), "0b": bool(row0b), "0c": bool(row0c), "0d": bool(row0d), "0e_outcome": bool(outcome_eq), "0e_text": bool(text_eq)}
    R["0a_pipeline"] = {"reproduced": rep60, "live_decodes_in_executed_cycles": n60, "share": share60, "bar": REPRO_BAR,
                        "near_bar": bool(REPRO_BAR <= share60 <= REPRO_NEAR_HI)}
    R["0a_delta_reported"] = {"reproduced": rep40, "live_decodes_in_executed_cycles": n40, "share": share40}
    R["0c_placebo"] = {"D_PL_PF": D0, "ci95": [lo, hi], "bar": PLACEBO_BAR}
    R["0e_null"] = {"outcome_fields_identical_every_cycle": bool(outcome_eq), "text_identical_every_cycle": bool(text_eq), "cycles_with_text_difference": ndiff_text}
    R["executed_cycles"] = {l: metas[l]["n_cycles_executed"] for l in metas}
    R["truncated_at_max_results"] = {l: metas[l]["n_truncated_at_max"] for l in metas}
    # U_base from the V0 leg ALONE (strict corroboration)
    rb = ref_by_ts(ref_all)
    K = W = U = 0
    for ts, lst in load_full("V0").items():
        for f, _dt, _s, m in lst:
            c = corr_class(rb, ts, m, f)
            K += c == "K"; W += c == "W"; U += c == "U"
    tot = K + W + U
    R["U_base"] = {"value": (W + U) / float(tot), "V0_decodes": tot, "corroborated_K": K, "uncorroborated_U": U, "wildcard_only_W_counted_uncorroborated": W,
                   "rule": "(V0 decodes not strictly corroborated) / (all V0 decodes); point estimate; frozen on ratification"}
    R["V0_R_wild_pct"] = rec0["R_wild"]
    fired = [k for k, v in R["row0"].items() if not v]
    R["verdict"] = "ROW 0 clean; U_base measured; awaiting the Captain's ratification (GAIN_BAR + U_base rule)" if not fired else "ROW 0 FIRES: " + ",".join(fired)
    if not R["row0"]["0e_text"] and R["row0"]["0e_outcome"]:
        R["verdict"] += "  [0e TEXT differs with outcome identical: STOP AND HAND TO THE ARCHITECT, never cite S16]"
    p = os.path.join(RESULTS, "stage3_row0.json")
    with open(p, "w") as f:
        json.dump(R, f, indent=1, default=str)
    log(json.dumps({k: R[k] for k in ("verdict", "row0", "0a_pipeline", "0a_delta_reported", "0c_placebo", "0e_null", "executed_cycles", "U_base", "V0_R_wild_pct")}, indent=1, default=str))
    sys.exit(0 if not fired else 1)


# ── measures (finalists) ─────────────────────────────────────────────────────────────────
def cmd_measure(a):
    if not os.path.exists(RATIFIED):
        raise SystemExit("REFUSED: %s missing (ratification comes before any finalist measure)" % RATIFIED)
    with open(RATIFIED) as f:
        RAT = json.load(f)
    GAIN_BAR = float(RAT["gain_bar_pp"])
    with open(os.path.join(RESULTS, "stage3_row0.json")) as f:
        R0 = json.load(f)
    U_base = float(R0["U_base"]["value"])
    assert abs(U_base - float(RAT["u_base_value"])) < 1e-12, "ratified U_base != the V0-derived value: the ratification does not refer to this V0 leg"
    ref_all = AN.load_ref_c2()
    by_cycle = DL.build_by_cycle(ref_all)
    classes = DL.classify_population(ref_all, by_cycle)
    rb = ref_by_ts(ref_all)
    fullV0, dV0 = load_full("V0"), load_dict("V0")
    C0, D0, rec0, _pc0 = C_of(dV0, ref_all, by_cycle, classes)
    row0_fires = not all(R0["row0"].values())
    OUT = {"gain_bar_pp": GAIN_BAR, "U_base": U_base, "ratified": RAT, "row0_fires": row0_fires, "denominator_cycles_V0": len(fullV0), "finalists": {}}
    for leg in FINALISTS:
        meta = load_meta(leg)
        assert meta["sha"] == DLL_SHA and meta["table_ok"] and meta["supp_ok"] and meta["cycle_list_sha256"] == load_meta("V0")["cycle_list_sha256"], "0d fires for " + leg
        fullF, dF = load_full(leg), load_dict(leg)
        cnt = collections.Counter()
        tbe = tbt = 0
        for ts in sorted(fullV0):
            pairs, added, removed, tb, tt = pair_cycle(fullV0[ts], fullF.get(ts, []))
            tbe += tb; tbt += tt
            for ib in added:
                f, _dt, _s, m = fullF[ts][ib]
                cnt["add_" + corr_class(rb, ts, m, f)] += 1
            for ia in removed:
                f, _dt, _s, m = fullV0[ts][ia]
                cnt["rem_" + corr_class(rb, ts, m, f)] += 1
        u_add, k_add, k_rem = cnt["add_U"] + cnt["add_W"], cnt["add_K"], cnt["rem_K"]
        CF, DF_, recF, _pcF = C_of(dF, ref_all, by_cycle, classes)
        dR = recF["R_wild"] - rec0["R_wild"]
        if row0_fires:
            verdict = "ROW 0 STOP"
        elif u_add + k_add == 0:
            verdict = "ROW N - REJECT: adds nothing"
        elif cp95(u_add, u_add + k_add)[1] > U_base:
            verdict = "ROW F - REJECT: the additions are dirtier than what we already emit"
        elif dR < GAIN_BAR:
            verdict = "ROW N - REJECT: FP-clean but not worth it"
        else:
            verdict = "ROW S - SHIP-ELIGIBLE (Captain, HK-010)"
        # stratifications (reported, NEVER gated)
        gained, lost = recF["hit_set"] - rec0["hit_set"], rec0["hit_set"] - recF["hit_set"]
        strat_snr, strat_df = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
        for which, keys in ((0, gained), (1, lost)):
            for k in keys:
                n = S0.dominant_neighbour(k, ref_all, by_cycle)
                if n is None:
                    sb, db = "no neighbour", "no neighbour"
                else:
                    kind, our, _lk = S0.our_row(n["key"], rec0, dV0)
                    sb = "ambiguous" if kind == "amb" else "N0 (blocker not decoded by V0)" if kind == "none" else (">= +5" if int(our[0]) >= 5 else "< +5")
                    db = S0.df_band(n["df"])
                strat_snr[sb][which] += 1
                strat_df[db][which] += 1
        OUT["finalists"][leg] = {
            "supp": meta["supp_registered"], "verdict": verdict, "u_add": u_add, "k_add": k_add, "k_rem": k_rem,
            "u_add_cp95": list(cp95(u_add, u_add + k_add)) if u_add + k_add else None, "dR_pp": dR, "R_wild_V0": rec0["R_wild"], "R_wild_variant": recF["R_wild"],
            "dC_pp": C0 - CF, "C_V0_pp": C0, "C_variant_pp": CF,
            "churn": {"added_K": cnt["add_K"], "added_W": cnt["add_W"], "added_U": cnt["add_U"], "removed_K": cnt["rem_K"], "removed_W": cnt["rem_W"], "removed_U": cnt["rem_U"]},
            "wildcard_dependent": {"added_W": cnt["add_W"], "share_of_u_add": (cnt["add_W"] / float(u_add) if u_add else None), "removed_W": cnt["rem_W"]},
            "pairing": {"tiebreak_events": tbe, "tiebreak_used_text": tbt},
            "stratification_by_blocker_snr_V0_REPORT_ONLY": {k: {"gained": v[0], "lost": v[1], "net": v[0] - v[1]} for k, v in sorted(strat_snr.items())},
            "stratification_by_df_band_REPORT_ONLY": {k: {"gained": v[0], "lost": v[1], "net": v[0] - v[1]} for k, v in sorted(strat_df.items())},
            "executed_cycles": meta["n_cycles_executed"]}
    p = os.path.join(RESULTS, "stage3_verdict.json")
    with open(p, "w") as f:
        json.dump(OUT, f, indent=1, default=str)
    log(json.dumps(OUT, indent=1, default=str))


def cmd_nullcheck(a):
    """Pairing/corroboration plumbing on the NULL leg: VN vs V0 must give u_add = k_add = k_rem = 0 exactly (no finalist leg is read)."""
    ref_all = AN.load_ref_c2()
    rb = ref_by_ts(ref_all)
    f0, fn = load_full("V0"), load_full("VN")
    cnt = collections.Counter()
    for ts in sorted(f0):
        pairs, added, removed, tb, tt = pair_cycle(f0[ts], fn.get(ts, []))
        cnt["added"] += len(added); cnt["removed"] += len(removed); cnt["pairs"] += len(pairs)
    d0, dn = load_dict("V0"), load_dict("VN")
    dR = matcher.recovery(dn, ref_all)["R_wild"] - matcher.recovery(d0, ref_all)["R_wild"]
    log(json.dumps({"pairs": cnt["pairs"], "added": cnt["added"], "removed": cnt["removed"], "dR_pp": dR}))
    sys.exit(0 if cnt["added"] == 0 and cnt["removed"] == 0 and dR == 0.0 else 1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("leg")
    lg.add_argument("--leg", choices=sorted(LEGS), required=True)
    lg.set_defaults(fn=cmd_leg)
    sub.add_parser("row0").set_defaults(fn=cmd_row0)
    sub.add_parser("measure").set_defaults(fn=cmd_measure)
    sub.add_parser("nullcheck").set_defaults(fn=cmd_nullcheck)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
