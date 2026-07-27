#!/usr/bin/env python3
"""D-001 R.6 -- absolute SNR calibration against jt9's own reported SNR.

Executes step 1 (and, by choice of grid, step 2) of
`2026-07-27-1946-architect-r6-control-audit-ruling.md` Sec.7.

The ruling's claim, unconfirmed when written:
  * R.6's SNR knob is a 43.75 Hz in-band ratio; jt9 reports SNR in the standard 2500 Hz
    reference bandwidth. The fixed conversion is  SNR_2500 = SNR_inband - 10*log10(2500/43.75)
    = SNR_inband - 17.57 dB.
  * If the AWGN arm's jt9-reported SNR tracks that prediction, the convention is right and the
    control arm is confirmed healthy by an independent instrument.
  * If the REAL arm's jt9-reported SNR comes in materially hotter than the prediction, the real
    arm is planting grafts louder than nominal (ruling Sec.3) and the mechanism is Sec.4.

`run_jt9_single` in r5_hybrid_ladder.py already parses jt9's `snr` field via
`b1.parse_jt9_stdout` and then discards it. This script keeps it. Nothing else about the
construction is changed: `r6.build_pair` is imported and called verbatim, so this measures the
harness as it actually stands, not a reimplementation of it.

Grid spans the FT8 decoding threshold (~-3.4 dB in R.6's in-band units) so the AWGN arm has
points at which it can decode at all -- the smoke grid it was previously run on did not.

NFR-021: messages are Q-prefix by construction (b2.make_message). ASCII-only output (HK-009).
"""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import b1_jt9_ablation as b1
import b2_synthetic_calibration as b2
import r5_hybrid_ladder as r5
import r6_clean_graft as r6

OUT_DIR = os.path.join(b1.REPO, "artefacts", "d001_r6_jt9_snr_calibration")
SCRATCH = os.path.join(OUT_DIR, "jt9")

N_CYCLES = int(os.environ.get("R6C_N_CYCLES", "4"))
SNR_GRID = [float(x) for x in os.environ.get("R6C_SNRS", "-6,0,6,10").split(",")]
SEED = 20260727

# The prediction under test.
BW_REF_HZ = 2500.0
CONVERSION_DB = 10.0 * math.log10(BW_REF_HZ / r6.SIG_OCCUPIED_HZ)


def run_jt9_rows(wav_path: str) -> list[dict]:
    """As r5.run_jt9_single, but returns the FULL parsed rows -- including the `snr` field that
    the original discards. This is the only behavioural difference."""
    os.makedirs(SCRATCH, exist_ok=True)
    cmd = [b1.JT9_EXE, "-8", "-d", "1", "-p", "15", "-a", SCRATCH, "-t", SCRATCH, wav_path]
    result = subprocess.run(cmd, cwd=SCRATCH, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  [WARN] jt9 exited {result.returncode} on {wav_path}", file=sys.stderr)
    return b1.parse_jt9_stdout(result.stdout, "buf")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "buffers"), exist_ok=True)
    rng_py = random.Random(SEED)
    rng_np = np.random.default_rng(SEED)

    print(f"Loading DLL: {b2.DLL_PATH}")
    native = b2.Native(b2.DLL_PATH)

    print(f"SIG_OCCUPIED_HZ = {r6.SIG_OCCUPIED_HZ} Hz  ->  predicted jt9-minus-nominal offset "
          f"= -{CONVERSION_DB:.2f} dB in BOTH arms if the convention is sound")
    print(f"FT8 threshold (~-21 dB in 2500 Hz) sits at {-21.0 + CONVERSION_DB:+.1f} dB "
          f"in R.6 in-band units\n")

    rows = list(b1.parse_all_txt(b1.WSJTX_ALL_TXT))
    by_cycle: dict[str, list[dict]] = {}
    for r in rows:
        by_cycle.setdefault(r["ts"], []).append(r)

    wav_names = sorted(os.path.splitext(f)[0] for f in os.listdir(r6.WSJTX_WAV68)
                       if f.endswith(".wav"))
    cyc = [t for t in wav_names if t in by_cycle]
    idx = sorted(set(int(round(x)) for x in np.linspace(0, len(cyc) - 1, min(N_CYCLES, len(cyc)))))
    sel = [cyc[i] for i in idx]
    print(f"cycles: {len(sel)} of {len(cyc)} matched; SNR grid (in-band): {SNR_GRID}\n")

    per_signal = []

    for ci, ts in enumerate(sel, 1):
        real_pcm = r5.read_real_wav_float(os.path.join(r6.WSJTX_WAV68, ts + ".wav"))
        real_freqs = [float(r["freq"]) for r in by_cycle[ts]]
        gaps = r6.find_gaps(real_freqs, r6.MAX_GRAFTS)
        if not gaps:
            continue

        for snr_db in SNR_GRID:
            # verbatim harness construction -- not a reimplementation
            real_buf, awgn_buf, awgn_bg, recs = r6.build_pair(
                native, rng_py, rng_np, real_pcm, gaps, snr_db)

            for arm, buf, ref in (("real", real_buf, real_pcm), ("awgn", awgn_buf, awgn_bg)):
                wav = os.path.join(OUT_DIR, "buffers", f"{ts}_s{snr_db:+.0f}_{arm}.wav")
                r5.write_wav(wav, buf)
                jt9_rows = run_jt9_rows(wav)
                os.remove(wav)

                by_msg = {}
                for jr in jt9_rows:
                    by_msg[b1.normalize_hash_tokens(jr["message"])] = jr

                for rec in recs:
                    nmsg = b1.normalize_hash_tokens(rec["message"])
                    jr = by_msg.get(nmsg)
                    m_snr = r6.measure_inband_snr(buf, ref, rec["freq"])
                    per_signal.append({
                        "cycle": ts, "arm": arm, "freq": rec["freq"],
                        "snr_nominal": snr_db,
                        "snr_measured_inband": m_snr,
                        "jt9_decoded": jr is not None,
                        "jt9_snr": float(jr["snr"]) if jr else None,
                        "jt9_freq": float(jr["freq"]) if jr else None,
                        "contam_db": rec["contam_db"],
                    })
        print(f"  [{ci}/{len(sel)}] {ts}: {len(gaps)} grafts x {len(SNR_GRID)} SNRs done")

    # -------------------- report --------------------
    print()
    print("=== jt9 REPORTED SNR vs R.6 NOMINAL ===")
    print(f"prediction if convention is sound: jt9_snr - nominal = {-CONVERSION_DB:+.2f} dB\n")
    print(f"{'SNR':>5} | {'arm':>4} | {'decoded':>12} | {'jt9 snr (med)':>13} | "
          f"{'jt9-nominal':>12} | {'vs predicted':>12}")
    print("-" * 78)

    summary = {}
    for snr_db in SNR_GRID:
        for arm in ("real", "awgn"):
            sel_rows = [p for p in per_signal
                        if p["snr_nominal"] == snr_db and p["arm"] == arm]
            if not sel_rows:
                continue
            dec = [p for p in sel_rows if p["jt9_decoded"]]
            frac = len(dec) / len(sel_rows)
            if dec:
                med = float(np.median([p["jt9_snr"] for p in dec]))
                off = med - snr_db
                excess = off + CONVERSION_DB
                print(f"{snr_db:>+5.0f} | {arm:>4} | {100*frac:5.1f}% ({len(dec):2d}/{len(sel_rows):2d}) | "
                      f"{med:>13.1f} | {off:>+12.2f} | {excess:>+12.2f}")
                summary[f"{arm}_{snr_db:+.0f}"] = {
                    "n": len(sel_rows), "k": len(dec), "p": frac,
                    "jt9_snr_median": med, "offset_db": off, "excess_vs_predicted_db": excess}
            else:
                print(f"{snr_db:>+5.0f} | {arm:>4} | {100*frac:5.1f}% ({len(dec):2d}/{len(sel_rows):2d}) | "
                      f"{'--':>13} | {'--':>12} | {'--':>12}")
                summary[f"{arm}_{snr_db:+.0f}"] = {
                    "n": len(sel_rows), "k": 0, "p": 0.0, "jt9_snr_median": None,
                    "offset_db": None, "excess_vs_predicted_db": None}

    print()
    print("READING: 'vs predicted' is the excess over the pure bandwidth conversion.")
    print("  ~0 dB      -> that arm's graft sits exactly where its nominal label says.")
    print("  strongly + -> that arm is planted HOTTER than nominal (ruling Sec.3/Sec.4).")

    reals = [v["excess_vs_predicted_db"] for k, v in summary.items()
             if k.startswith("real") and v["excess_vs_predicted_db"] is not None]
    awgns = [v["excess_vs_predicted_db"] for k, v in summary.items()
             if k.startswith("awgn") and v["excess_vs_predicted_db"] is not None]
    print()
    if awgns:
        print(f"AWGN arm excess: median {np.median(awgns):+.2f} dB over {len(awgns)} grid points")
    if reals:
        print(f"REAL arm excess: median {np.median(reals):+.2f} dB over {len(reals)} grid points")
    if reals and awgns:
        print(f"REAL-minus-AWGN excess = {np.median(reals) - np.median(awgns):+.2f} dB "
              f"<- the ruling Sec.3 estimate was +6 to +10 dB")

    with open(os.path.join(OUT_DIR, "calibration.json"), "w", encoding="utf-8") as fh:
        json.dump({"conversion_db": CONVERSION_DB, "sig_occupied_hz": r6.SIG_OCCUPIED_HZ,
                   "snr_grid": SNR_GRID, "n_cycles": len(sel),
                   "summary": summary, "per_signal": per_signal}, fh, indent=2)
    print(f"\nWrote {os.path.join(OUT_DIR, 'calibration.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
