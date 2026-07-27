#!/usr/bin/env python3
"""D-001 R.6 diagnostic -- absolute level sensitivity sweep.

Tests the hypothesis in `2026-07-27-1921-architect-to-qa-r6-handoff.md` Sec.5: R.6's AWGN control
arm decodes 0.0% at -14/-10/-6 dB in-band SNR while the real arm reaches 63% at -6 dB. R.6's AWGN
buffer has broadband RMS ~3.1e-3; every synthetic rung this study has run before (B.2, R.4, R.5
rungs 0-2) used `noise_std_ref = 0.53` (R5's REFERENCE_SNR_DB=-14dB working point) -- ~170x
louder. If either decoder is sensitive to ABSOLUTE input level at matched in-band SNR, that is the
explanation for R.6's broken control, and the fix is to scale both R.6 arms to a common working
level rather than chase anything else.

Method (handoff Sec.5, run verbatim): pure AWGN, in-band SNR fixed at -6 dB (the point where R.6's
real arm was 63% and its AWGN arm was 0%), sweep BROADBAND sigma over ~45 dB spanning R.6's quiet
control up to R5's loud reference level. At each sigma, plant messages at 4 well-separated
frequencies (400/1000/1800/2500 Hz per the handoff), repeat with fresh RNG draws for a Wilson CI,
decode with both ours and jt9 (the handoff's fallback #2 needs jt9 for comparison since our
decoder reads the float buffer directly and jt9 reads the 16-bit WAV -- a level effect that
appears in jt9 only would point at quantisation, not decoder-level-sensitivity).

Verdict rule: hit-rate RISES with sigma at fixed in-band SNR -> decoder is level-sensitive (a
finding in its own right, to be checked against the real corpus's own levels before it is called a
defect). Hit-rate FLAT across the sweep -> the level hypothesis is dead; move to the handoff's
fallback list (write_wav peak normalisation, 16-bit quantisation floor, b2.synth_signal amplitude
convention vs in-band SNR definition).

NFR-021: Q-prefix synthetic messages only, message text never printed. ASCII-only console output
(HK-009).
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import b2_synthetic_calibration as b2
import b1_jt9_ablation as b1
import r5_hybrid_ladder as r5

SR = float(b2.SR)
NYQ = SR / 2.0
SIG_OCCUPIED_HZ = 43.75   # 7 * 6.25 Hz, 8-tone alphabet -- same convention as r6_clean_graft.py
OUT_DIR = os.path.join(b1.REPO, "artefacts", "d001_r6_level_sweep")

SNR_DB = -6.0             # the SNR at which R.6's real/awgn arms diverged 63% vs 0%
FREQS = [400.0, 1000.0, 1800.0, 2500.0]
SIGMAS = [3.1e-3, 3.1e-2, 3.1e-1, 5.3e-1]   # spans R.6's AWGN control up to R5's noise_std_ref
REPEATS = int(os.environ.get("R6LS_REPEATS", "8"))
PLANT_DT = 0.6
SEED = 20260727
RISE_THRESHOLD_PT = 0.10   # 10 percentage points, low-to-high sigma, to call "rises"


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    rng_py = random.Random(SEED)

    print(f"Loading DLL: {b2.DLL_PATH}")
    native = b2.Native(b2.DLL_PATH)

    print(f"Fixed in-band SNR = {SNR_DB:+.0f} dB; sweeping broadband sigma over "
          f"{20*math.log10(SIGMAS[-1]/SIGMAS[0]):.0f} dB ({SIGMAS[0]:.1e} .. {SIGMAS[-1]:.1e}); "
          f"{REPEATS} repeats x {len(FREQS)} grafts/repeat = {REPEATS*len(FREQS)} signals/sigma")
    print()
    print(f"{'sigma':>10} | {'ours':>16} | {'jt9':>16}")
    print("-" * 50)

    results = []
    for sigma in SIGMAS:
        inband = sigma * math.sqrt(SIG_OCCUPIED_HZ / NYQ)
        amp = math.sqrt(2.0) * inband * (10 ** (SNR_DB / 20.0))
        ours_hits = jt9_hits = n = 0

        for rep in range(REPEATS):
            rng_np = np.random.default_rng(SEED * 1_000_003 + rep + int(round(sigma * 1e7)))
            buf = rng_np.normal(0.0, sigma, size=b2.BUFFER_SAMPLES)
            planted = []
            for f in FREQS:
                msg = b2.make_message(rng_py)
                tones = native.encode(msg)
                sig = b2.synth_signal(tones, f, amp, rng_np)
                b2.plant(buf, sig, PLANT_DT)
                planted.append(msg)

            ours_msgs = r5.decode_all_with_messages(native, buf)
            wav_path = os.path.join(OUT_DIR, "buf.wav")
            r5.write_wav(wav_path, buf)
            jt9_msgs = r5.run_jt9_single(wav_path, os.path.join(OUT_DIR, "jt9"))
            os.remove(wav_path)

            for msg in planted:
                nmsg = b1.normalize_hash_tokens(msg)
                n += 1
                if msg in ours_msgs or nmsg in ours_msgs:
                    ours_hits += 1
                if msg in jt9_msgs or nmsg in jt9_msgs:
                    jt9_hits += 1

        p_ours, lo_o, hi_o = b2.wilson_interval(ours_hits, n)
        p_jt9, lo_j, hi_j = b2.wilson_interval(jt9_hits, n)
        print(f"{sigma:>10.1e} | {100*p_ours:5.1f}% ({ours_hits:3d}/{n:3d})  | "
              f"{100*p_jt9:5.1f}% ({jt9_hits:3d}/{n:3d})")
        results.append({"sigma": sigma, "inband_snr_db": SNR_DB,
                         "ours": {"k": ours_hits, "n": n, "p": p_ours,
                                  "ci_lo": lo_o, "ci_hi": hi_o},
                         "jt9": {"k": jt9_hits, "n": n, "p": p_jt9,
                                 "ci_lo": lo_j, "ci_hi": hi_j}})

    with open(os.path.join(OUT_DIR, "results.json"), "w", encoding="utf-8") as fh:
        json.dump({"snr_db": SNR_DB, "sigmas": SIGMAS, "repeats": REPEATS,
                    "results": results}, fh, indent=2)

    print()
    d_ours = results[-1]["ours"]["p"] - results[0]["ours"]["p"]
    d_jt9 = results[-1]["jt9"]["p"] - results[0]["jt9"]["p"]
    rising_ours = d_ours > RISE_THRESHOLD_PT
    rising_jt9 = d_jt9 > RISE_THRESHOLD_PT
    print(f"low-to-high-sigma delta: ours {100*d_ours:+.1f} pt   jt9 {100*d_jt9:+.1f} pt")
    verdict = "HYPOTHESIS SUPPORTED" if (rising_ours or rising_jt9) else "HYPOTHESIS DEAD (flat)"
    print(f"[{verdict}] ours rises >= {100*RISE_THRESHOLD_PT:.0f}pt: {rising_ours}   "
          f"jt9 rises >= {100*RISE_THRESHOLD_PT:.0f}pt: {rising_jt9}")
    if verdict == "HYPOTHESIS DEAD (flat)":
        print("Next: handoff Sec.5 fallback list in order -- (1) write_wav peak normalisation,")
        print("(2) 16-bit quantisation floor, (3) b2.synth_signal amplitude vs in-band SNR "
              "definition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
