#!/usr/bin/env python3
"""OSD-FA-A Part D, RE-RUN on the correct corpus (Architect's ruling, arch/osd-fa-a
4998b2a, 2026-09-11 16:52Z: `qa/rr-study/2026-09-11-1652-architect-osd-fa-a-part-d-ruling.md`).

Supersedes part_d.py's own run, which used the BASE spec's corpus
(artefacts/20260803_live_run_1713/) -- Amendment 1 sec.3 replaced it with
FP-FLOOR-LIVE-2, and the Captain's go message named it explicitly. part_d.py's
disclosed +0.16s-offset correction and its five structural fidelity categories are
BOTH reused verbatim here (HK-018, and the ruling's own sec.3.2 instruction to keep
the categories). What changes: the corpus, and ROW 0e (ruling sec.3.1).

HK-020 critical config, sourced from the AMENDMENT (arch/osd-fa-a bb26778 sec.3,
25078b2, 4998b2a sec.4), not the base spec:
  - population: artefacts/20260908_live_run_1827-fp-floor-live-2/
  - span: [2026-09-08T19:36:45Z, 2026-09-09T17:22:00Z) -- Amendment 3's own boundary
  - decodes: OpenWSFZ's own openwsfz/ALL.TXT in that span
  - NO +0.16s offset -- live ALL.TXT dt is already decoder-reported (ruling sec.2)
  - 1,000 cycles, seeded, sorted at construction (base sec.2.4 hazard 2)
  - PCM: read_wav + normalise_rms(0.20), same convention as part_d.py, disclosed

ROW 0e, corrected (ruling sec.3.1):
  - eligible decodes: production text contains NO '<' token
  - control subset: 200 eligible decodes, seeded, sorted at construction
  - pass: probe converges (out_path in {0,1}) AND payload == true_codeword(text)
  - fail: anything else, INCLUDING out_path == -1
  - >=0.90 => Part D readable; <0.90 => VOID. Not refusable on the hash-packing
    ground (ruling: that ground does not apply here by construction).

NFR-021: ALL.TXT/WSJT-X ALL.TXT carry real off-air callsigns. Message text held in
memory only (true_codeword comparison, wildcard corroboration matching, structural
categorisation) -- never printed, logged, or written. Output is counts/booleans only.

Usage:
    python part_d2.py <label> <out_json>
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "harness"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, HERE)

import dll_pin as P  # noqa: E402
from common import compute_seed  # noqa: E402
from part_d import LINE_RE, read_wav_normalised, decode_one, cycle_clustered_bootstrap_ci  # noqa: E402


def parse_all_txt_with_snr(path: str) -> dict:
    """Like part_d.parse_all_txt, but also keeps snr (needed for the Amendment
    sec.3 snr<=-24 vs >-24 descriptive split) -- reuses the same LINE_RE, not a
    second regex."""
    by_cycle: dict[str, list] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE_RE.match(line.rstrip("\n"))
            if not m:
                continue
            cycle_ts, freq_mhz, snr, dt, freq_hz, message = m.groups()
            if not freq_mhz.startswith("14.074"):  # dial filter, matches fp_floor_live_2_part_b.load
                continue
            try:
                dt_f, freq_f, snr_i = float(dt), float(freq_hz), int(snr)
            except ValueError:
                continue
            by_cycle.setdefault(cycle_ts, []).append((freq_f, dt_f, message, snr_i))
    return by_cycle
from h1_hash_token_contamination import wildcard_match  # noqa: E402 -- reused, not reimplemented

# HK-020: sourced from Amendment 1 sec.3 / the ruling sec.4, NOT the base spec.
CORPUS_ROOT = r"D:\Projects\claude\OpenWSFZ\artefacts\20260908_live_run_1827-fp-floor-live-2"
ALL_TXT = os.path.join(CORPUS_ROOT, "openwsfz", "ALL.TXT")
WAV_DIR = os.path.join(CORPUS_ROOT, "cycle-audio")
WSJTX_A_ALL = r"C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT"  # REF = A, FP-FLOOR-LIVE-2 Amendment 1

BOUNDARY_LO = "260908_193645"   # inclusive, Amendment 3's own frozen boundary
BOUNDARY_HI = "260909_172200"   # exclusive, corpus close
TOL_HZ = 3                       # FP-FLOOR-LIVE-2 Part B's own matcher tolerance

N_SAMPLE_CYCLES = 1000
SAMPLE_SEED = compute_seed("OSD-FA-A-PART-D2", 0, 0)
N_ROW0E_SUBSET = 200
ROW0E_SEED = compute_seed("OSD-FA-A-PART-D2-ROW0E", 0, 0)
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = compute_seed("OSD-FA-A-PART-D2-BOOTSTRAP", 0, 0)


def categorize(message: str) -> str:
    """Reused verbatim from the disclosed categorisation in the August-corpus report
    (part_d.py's own analysis) -- kept per the ruling sec.3.2's explicit instruction."""
    toks = message.split()
    if toks and toks[0] == "CQ":
        return "CQ"
    if any(t in ("RR73", "73") for t in toks):
        return "sign_off"
    if any(t.startswith("R") and t[1:].lstrip("-").isdigit() for t in toks):
        return "report_R"
    if toks and toks[-1].lstrip("-").isdigit():
        return "report_plain"
    return "other"


def load_ref_a(path: str, ts_lo: str) -> dict:
    """ts -> list of (message, freq_hz). Mirrors fp_floor_live_2_part_b.load's own
    parsing (dial-freq filter, ts >= ts_lo), reused rather than reimplemented."""
    out: dict[str, list] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if not f[1].startswith("14.074"):
                continue
            ts = f[0]
            if ts < ts_lo:
                continue
            try:
                freq_hz = int(f[6])
            except ValueError:
                continue
            out.setdefault(ts, []).append((" ".join(f[7:]), freq_hz))
    return out


def is_corroborated(ref_by_ts: dict, ts: str, msg: str, freq: float) -> bool:
    for cand_msg, cand_freq in ref_by_ts.get(ts, []):
        if abs(freq - cand_freq) > TOL_HZ:
            continue
        if wildcard_match(msg, cand_msg):
            return True
    return False


def main() -> int:
    label, out_json = sys.argv[1], sys.argv[2]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    by_cycle = parse_all_txt_with_snr(ALL_TXT)
    by_cycle = {ts: v for ts, v in by_cycle.items() if BOUNDARY_LO <= ts < BOUNDARY_HI}
    wav_cycles = set(fn[:-4] for fn in os.listdir(WAV_DIR)
                      if fn.endswith(".wav") and not fn.endswith("_2.wav"))
    # The Part D POPULATION is every archived cycle in-span (~5,221, matching F-001 L3's own
    # 5,222-cycle figure for this exact span almost exactly) -- NOT just the ~4,099 cycles that
    # happen to carry >=1 live decode. A cycle with zero live decodes contributes 0/0 to U either
    # way, but sampling only from decode-bearing cycles would under-represent the true cycle
    # population and mismatch E3's own population definition (caught before sampling, not after).
    all_cycles = sorted(c for c in wav_cycles if BOUNDARY_LO <= c < BOUNDARY_HI)
    n_all_txt_decodes = sum(len(v) for v in by_cycle.values())
    print(f"[{label}] span [{BOUNDARY_LO},{BOUNDARY_HI}): {len(by_cycle)} cycles with >=1 decode, "
          f"{len(all_cycles)} total archived cycles (the sampling population), "
          f"{n_all_txt_decodes} total decodes in span", flush=True)

    rng = random.Random(SAMPLE_SEED)
    sample_cycles = sorted(rng.sample(all_cycles, min(N_SAMPLE_CYCLES, len(all_cycles))))
    print(f"[{label}] sampled {len(sample_cycles)} cycles, seed={SAMPLE_SEED}", flush=True)

    ref_a = load_ref_a(WSJTX_A_ALL, BOUNDARY_LO)

    dec = P.load_decoder(verify=True)
    print(f"[{label}] shim={dec.version}", flush=True)

    per_cycle_osd, per_cycle_bp_or_osd = [], []
    n_neither = 0
    n_total_decodes = 0
    all_records = []  # (cycle, idx, path, fidelity(None/bool), has_bracket, category, corroborated, snr)

    t0 = time.perf_counter()
    for ci, cycle_ts in enumerate(sample_cycles):
        wav_path = os.path.join(WAV_DIR, cycle_ts + ".wav")
        pcm = read_wav_normalised(wav_path)
        osd_n = bp_or_osd_n = 0
        for di, (freq_hz, dt_s, message, snr) in enumerate(by_cycle.get(cycle_ts, [])):
            n_total_decodes += 1
            r = decode_one(dec, pcm, freq_hz, dt_s, message)
            path = r["path"]
            has_bracket = "<" in message
            cat = categorize(message)
            corrob = is_corroborated(ref_a, cycle_ts, message, freq_hz)
            all_records.append((cycle_ts, di, path, r["fidelity"], has_bracket, cat, corrob, snr))
            if path == 1:
                osd_n += 1
                bp_or_osd_n += 1
            elif path == 0:
                bp_or_osd_n += 1
            else:
                n_neither += 1
        per_cycle_osd.append(osd_n)
        per_cycle_bp_or_osd.append(bp_or_osd_n)

        if (ci + 1) % 100 == 0:
            print(f"  [{label}] {ci + 1}/{len(sample_cycles)} cycles, "
                  f"{n_total_decodes} decodes so far ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    total_osd, total_bp_or_osd = sum(per_cycle_osd), sum(per_cycle_bp_or_osd)
    U = total_osd / total_bp_or_osd if total_bp_or_osd else None
    ci_lo, ci_hi = cycle_clustered_bootstrap_ci(
        per_cycle_osd, per_cycle_bp_or_osd, N_BOOTSTRAP, BOOTSTRAP_SEED)

    # --- ROW 0e, CORRECTED (ruling sec.3.1) ---------------------------------
    eligible = [rec for rec in all_records if not rec[4]]  # no '<' token

    def row0e_pass(rec) -> bool:
        path, fidelity = rec[2], rec[3]
        if path == -1:
            return False
        return fidelity is True

    erng = random.Random(ROW0E_SEED)
    subset_idx = sorted(erng.sample(range(len(eligible)), min(N_ROW0E_SUBSET, len(eligible))))
    subset = [eligible[i] for i in subset_idx]
    row0e_subset_pass = sum(1 for rec in subset if row0e_pass(rec))
    row0e_subset_rate = row0e_subset_pass / len(subset) if subset else None
    row0e_full_pass = sum(1 for rec in eligible if row0e_pass(rec))
    row0e_full_rate = row0e_full_pass / len(eligible) if eligible else None
    row0e_readable = row0e_subset_rate is not None and row0e_subset_rate >= 0.90

    # --- descriptive: fidelity by structural category (kept, ruling sec.3.2) ---
    cat_total, cat_pass = {}, {}
    for rec in eligible:
        cat = rec[5]
        cat_total[cat] = cat_total.get(cat, 0) + 1
        if row0e_pass(rec):
            cat_pass[cat] = cat_pass.get(cat, 0) + 1

    # --- descriptive: U split by fidelity verdict (ruling sec.3 table) ---------
    def u_of(recs):
        bp_or_osd = sum(1 for r in recs if r[2] in (0, 1))
        osd = sum(1 for r in recs if r[2] == 1)
        return osd, bp_or_osd, (osd / bp_or_osd if bp_or_osd else None)

    fid_pass_recs = [r for r in eligible if r[3] is True and r[2] != -1]
    fid_fail_recs = [r for r in all_records if not (r[3] is True and r[2] != -1)]  # everything else incl. non-eligible/-1
    osd_pass, bp_pass, u_pass = u_of(fid_pass_recs)
    osd_fail, bp_fail, u_fail = u_of(fid_fail_recs)
    worst_numerator = osd_pass + (total_bp_or_osd - bp_pass)
    u_worst = worst_numerator / total_bp_or_osd if total_bp_or_osd else None

    # --- Amendment sec.3 descriptive splits: REF-corroborated vs not, snr split ---
    corrob_recs = [r for r in all_records if r[6]]
    noncorrob_recs = [r for r in all_records if not r[6]]
    osd_c, bp_c, u_c = u_of(corrob_recs)
    osd_nc, bp_nc, u_nc = u_of(noncorrob_recs)

    le24_recs = [r for r in all_records if r[7] <= -24]
    gt24_recs = [r for r in all_records if r[7] > -24]
    osd_le24, bp_le24, u_le24 = u_of(le24_recs)
    osd_gt24, bp_gt24, u_gt24 = u_of(gt24_recs)

    tmp = out_json + ".tmp"
    out = {
        "label": label, "dll_sha256": P.PINNED_DLL_SHA256, "shim_version": dec.version,
        "corpus": CORPUS_ROOT, "span": [BOUNDARY_LO, BOUNDARY_HI],
        "n_cycles_sampled": len(sample_cycles), "sample_seed": SAMPLE_SEED,
        "n_total_decodes": n_total_decodes, "n_osd": total_osd, "n_bp_or_osd": total_bp_or_osd,
        "n_neither": n_neither, "U": U, "U_ci_lo": ci_lo, "U_ci_hi": ci_hi,
        "n_bootstrap": N_BOOTSTRAP,
        "row0e_eligible_n": len(eligible), "row0e_full_pass": row0e_full_pass,
        "row0e_full_rate": row0e_full_rate,
        "row0e_subset_n": len(subset), "row0e_subset_pass": row0e_subset_pass,
        "row0e_subset_rate": row0e_subset_rate, "row0e_readable": row0e_readable,
        "cat_total": cat_total, "cat_pass": cat_pass,
        "u_by_fidelity": {"pass": {"osd": osd_pass, "n": bp_pass, "U": u_pass},
                           "fail_or_unverifiable_or_neg1": {"osd": osd_fail, "n": bp_fail, "U": u_fail}},
        "u_worst": u_worst,
        "u_by_corroboration": {"corroborated": {"osd": osd_c, "n": bp_c, "U": u_c},
                                "not_corroborated": {"osd": osd_nc, "n": bp_nc, "U": u_nc}},
        "u_by_snr": {"le_-24": {"osd": osd_le24, "n": bp_le24, "U": u_le24},
                     "gt_-24": {"osd": osd_gt24, "n": bp_gt24, "U": u_gt24}},
        "total_wall_s": total_wall,
        "records": [{"c": c, "i": i, "p": p, "f": f, "br": br, "cat": cat, "co": co, "snr": snr}
                    for c, i, p, f, br, cat, co, snr in all_records],
    }
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    os.replace(tmp, out_json)

    print(f"[{label}] DONE decodes={n_total_decodes} osd={total_osd} bp_or_osd={total_bp_or_osd} "
          f"neither={n_neither} U={U} CI=[{ci_lo:.5f},{ci_hi:.5f}] "
          f"ROW0e: eligible={len(eligible)} subset={len(subset)} "
          f"subset_rate={row0e_subset_rate} readable={row0e_readable} "
          f"wall={total_wall:.0f}s -> {out_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
