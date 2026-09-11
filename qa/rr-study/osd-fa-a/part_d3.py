#!/usr/bin/env python3
"""OSD-FA-A Part D, THIRD run (Architect's ruling, arch/osd-fa-a 68c6a07, sec.3.1/3.3/3.4):
positions come from the same-binary REPLAY, not from ALL.TXT's rounded dt (Mechanism 1),
and sign-off messages are excluded from ROW 0e eligibility (Mechanism 2, demonstrated by
the bit-field diagnostic -- 578/578 sign-off mismatches confined to the g15 field alone).

HK-020 critical config:
  - corpus/span: unchanged from Part D2 (Amendment 1 sec.3) -- FP-FLOOR-LIVE-2,
    [260908_193645, 260909_172200)
  - positions: artefacts/2026-09-10-f001-l3-live-measurement/subject_20260050.json
    (ruling sec.3.1) -- SHA re-asserted in-run
  - matching: same cycle, wildcard message match, |delta_f| <= 3 Hz (ruling sec.3.1,
    reusing h1_hash_token_contamination.wildcard_match, same as part_d2's corroboration
    matcher)
  - reproduction share < 0.90 => Part D VOID (ruling sec.3.1, the E3-0 rule reused)
  - ROW 0e: 200 seeded eligible (no '<', category != sign_off) decodes, -1 counts as
    fail, >=0.90 bar (ruling sec.3.1 + sec.3.3 disposition)
  - PCM: read_wav + normalise_rms(0.20), unchanged, disclosed again here

NFR-021: message text held in memory only -- never printed, logged, or written. Output
is counts/booleans only.

Usage:
    python part_d3.py <label> <out_json>
"""
from __future__ import annotations

import hashlib
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
import part_d2 as PD2  # noqa: E402
from part_d import read_wav_normalised, decode_one, cycle_clustered_bootstrap_ci  # noqa: E402
from h1_hash_token_contamination import wildcard_match  # noqa: E402

REPLAY_JSON = os.path.join(
    REPO_ROOT, "artefacts", "2026-09-10-f001-l3-live-measurement", "subject_20260050.json")
REPLAY_EXPECTED_SHA256 = "6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c"

TOL_HZ = 3
N_SAMPLE_CYCLES = 1000
SAMPLE_SEED = compute_seed("OSD-FA-A-PART-D3", 0, 0)
N_ROW0E_SUBSET = 200
ROW0E_SEED = compute_seed("OSD-FA-A-PART-D3-ROW0E", 0, 0)
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = compute_seed("OSD-FA-A-PART-D3-BOOTSTRAP", 0, 0)
REPRODUCTION_BAR = 0.90


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_replay(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    by_cycle = {}
    for entry in d["per_file"]:
        by_cycle[entry["ts"]] = [(dec["f"], dec["dt"], dec["m"]) for dec in entry["decodes"]]
    return by_cycle, d


def match_replay(live_msg: str, live_freq: float, replay_decodes: list):
    """Same cycle (caller passes only that cycle's replay decodes), wildcard message
    match, |delta_f|<=TOL_HZ (ruling sec.3.1). If multiple candidates qualify, the
    closest in frequency is picked -- deterministic, disclosed; ties broken by list
    order (replay's own decode order, itself deterministic per F-001 L3 ROW 0d)."""
    candidates = [(rf, rdt, rm) for rf, rdt, rm in replay_decodes
                  if abs(rf - live_freq) <= TOL_HZ and wildcard_match(live_msg, rm)]
    if not candidates:
        return None
    candidates.sort(key=lambda c: abs(c[0] - live_freq))
    return candidates[0]


def main() -> int:
    label, out_json = sys.argv[1], sys.argv[2]
    if not os.path.realpath(out_json).startswith(
            os.path.join(REPO_ROOT, "artefacts") + os.sep):
        raise SystemExit("refusing to write outside artefacts/ (NFR-021)")

    replay_sha = sha256_of(os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native",
                                          "win-x64", "libft8.dll"))
    print(f"[{label}] current main DLL sha256={replay_sha[:16]}... "
          f"(the replay's own binary, re-asserted)", flush=True)
    if replay_sha != REPLAY_EXPECTED_SHA256:
        raise SystemExit(f"SHA mismatch: {replay_sha} != {REPLAY_EXPECTED_SHA256}")

    replay_by_cycle, replay_meta = load_replay(REPLAY_JSON)
    assert replay_meta["dll_sha256"] == REPLAY_EXPECTED_SHA256, replay_meta["dll_sha256"]
    assert replay_meta["window"] == [PD2.BOUNDARY_LO, PD2.BOUNDARY_HI], replay_meta["window"]
    print(f"[{label}] replay: {replay_meta['n_files']} files, window={replay_meta['window']}, "
          f"sha256={replay_meta['dll_sha256'][:16]}... (asserted)", flush=True)

    by_cycle = PD2.parse_all_txt_with_snr(PD2.ALL_TXT)
    by_cycle = {ts: v for ts, v in by_cycle.items() if PD2.BOUNDARY_LO <= ts < PD2.BOUNDARY_HI}
    wav_cycles = set(fn[:-4] for fn in os.listdir(PD2.WAV_DIR)
                      if fn.endswith(".wav") and not fn.endswith("_2.wav"))
    all_cycles = sorted(c for c in wav_cycles if PD2.BOUNDARY_LO <= c < PD2.BOUNDARY_HI)

    rng = random.Random(SAMPLE_SEED)
    sample_cycles = sorted(rng.sample(all_cycles, min(N_SAMPLE_CYCLES, len(all_cycles))))
    print(f"[{label}] sampled {len(sample_cycles)} cycles, seed={SAMPLE_SEED}", flush=True)

    ref_a = PD2.load_ref_a(PD2.WSJTX_A_ALL, PD2.BOUNDARY_LO)
    dec = P.load_decoder(verify=True)
    print(f"[{label}] shim={dec.version}", flush=True)

    per_cycle_osd, per_cycle_bp_or_osd = [], []
    n_neither = 0
    n_live_total = 0
    n_matched = 0
    all_records = []  # (cycle, idx, matched, path, fidelity, has_bracket, category, corroborated, snr)

    t0 = time.perf_counter()
    for ci, cycle_ts in enumerate(sample_cycles):
        wav_path = os.path.join(PD2.WAV_DIR, cycle_ts + ".wav")
        pcm = None
        rep_decodes = replay_by_cycle.get(cycle_ts, [])
        osd_n = bp_or_osd_n = 0
        for di, (freq_hz, dt_s, message, snr) in enumerate(by_cycle.get(cycle_ts, [])):
            n_live_total += 1
            m = match_replay(message, freq_hz, rep_decodes)
            cat = PD2.categorize(message)
            has_bracket = "<" in message
            corrob = PD2.is_corroborated(ref_a, cycle_ts, message, freq_hz)
            if m is None:
                all_records.append((cycle_ts, di, False, None, None, has_bracket, cat, corrob, snr))
                continue
            n_matched += 1
            rep_freq, rep_dt, _rep_msg = m
            if pcm is None:
                pcm = read_wav_normalised(wav_path)
            r = decode_one(dec, pcm, rep_freq, rep_dt, message)
            path = r["path"]
            all_records.append((cycle_ts, di, True, path, r["fidelity"], has_bracket, cat, corrob, snr))
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
                  f"{n_live_total} live decodes so far ({time.perf_counter() - t0:.0f}s)", flush=True)

    total_wall = time.perf_counter() - t0
    reproduction_share = n_matched / n_live_total if n_live_total else None
    void_reproduction = reproduction_share is None or reproduction_share < REPRODUCTION_BAR
    print(f"[{label}] reproduction share = {n_matched}/{n_live_total} = {reproduction_share}",
          flush=True)

    total_osd, total_bp_or_osd = sum(per_cycle_osd), sum(per_cycle_bp_or_osd)
    U = total_osd / total_bp_or_osd if total_bp_or_osd else None
    ci_lo = ci_hi = None
    if total_bp_or_osd:
        ci_lo, ci_hi = cycle_clustered_bootstrap_ci(
            per_cycle_osd, per_cycle_bp_or_osd, N_BOOTSTRAP, BOOTSTRAP_SEED)

    # --- ROW 0e, sign-off EXCLUDED from eligibility (Mechanism 2 diagnostic, ruling sec.3.3) ---
    eligible = [rec for rec in all_records
                if rec[2] and not rec[5] and rec[6] != "sign_off"]  # matched, no '<', not sign_off

    def row0e_pass(rec) -> bool:
        path, fidelity = rec[3], rec[4]
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

    def u_of(recs):
        bp_or_osd = sum(1 for r in recs if r[3] in (0, 1))
        osd = sum(1 for r in recs if r[3] == 1)
        return osd, bp_or_osd, (osd / bp_or_osd if bp_or_osd else None)

    matched_recs = [r for r in all_records if r[2]]
    corrob_recs = [r for r in matched_recs if r[7]]
    noncorrob_recs = [r for r in matched_recs if not r[7]]
    osd_c, bp_c, u_c = u_of(corrob_recs)
    osd_nc, bp_nc, u_nc = u_of(noncorrob_recs)
    le24_recs = [r for r in matched_recs if r[8] <= -24]
    gt24_recs = [r for r in matched_recs if r[8] > -24]
    osd_le24, bp_le24, u_le24 = u_of(le24_recs)
    osd_gt24, bp_gt24, u_gt24 = u_of(gt24_recs)

    out = {
        "label": label, "dll_sha256": P.PINNED_DLL_SHA256, "shim_version": dec.version,
        "n_cycles_sampled": len(sample_cycles), "sample_seed": SAMPLE_SEED,
        "n_live_total": n_live_total, "n_matched": n_matched,
        "reproduction_share": reproduction_share, "void_reproduction": void_reproduction,
        "n_osd": total_osd, "n_bp_or_osd": total_bp_or_osd, "n_neither": n_neither,
        "U": U, "U_ci_lo": ci_lo, "U_ci_hi": ci_hi, "n_bootstrap": N_BOOTSTRAP,
        "row0e_eligible_n": len(eligible), "row0e_full_pass": row0e_full_pass,
        "row0e_full_rate": row0e_full_rate, "row0e_subset_n": len(subset),
        "row0e_subset_pass": row0e_subset_pass, "row0e_subset_rate": row0e_subset_rate,
        "row0e_readable": row0e_readable,
        "u_by_corroboration": {"corroborated": {"osd": osd_c, "n": bp_c, "U": u_c},
                                "not_corroborated": {"osd": osd_nc, "n": bp_nc, "U": u_nc}},
        "u_by_snr": {"le_-24": {"osd": osd_le24, "n": bp_le24, "U": u_le24},
                     "gt_-24": {"osd": osd_gt24, "n": bp_gt24, "U": u_gt24}},
        "total_wall_s": total_wall,
        "records": [{"c": c, "i": i, "m": m, "p": p, "f": f, "br": br, "cat": cat, "co": co, "snr": snr}
                    for c, i, m, p, f, br, cat, co, snr in all_records],
    }
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    os.replace(tmp, out_json)

    print(f"[{label}] DONE live={n_live_total} matched={n_matched} repro={reproduction_share} "
          f"VOID_repro={void_reproduction} U={U} CI=[{ci_lo},{ci_hi}] "
          f"ROW0e_subset_rate={row0e_subset_rate} readable={row0e_readable} "
          f"wall={total_wall:.0f}s -> {out_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
