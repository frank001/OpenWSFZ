"""E4-STAGE2 -- the live exposure census itself (spec Sec.2-3, run per Sec.10.6).

Builds the REF frame (C2, SNR >= -10 dB), draws the pre-registered 5,000-row
sample, extracts rho1 per row via the calibrated estimator (ROW 0a, rho* =
0.577), and writes ALL per-row (privacy-sensitive) output under artefacts/
(NFR-021: C2 callsigns are real). A separate report step reduces this to
aggregate, callsign-free numbers safe to commit under qa/rr-study/.

Usage:
    python harness/e4_stage2_census.py --out-dir <artefacts/...>

No src/ or native/ change. No decoder is run -- this measures the channel
from archived audio against known (REF) messages.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))
_LGN_ROOT = str(_QA_ROOT / "live-gap-now")
if _LGN_ROOT not in sys.path:
    sys.path.insert(0, _LGN_ROOT)

from corpus import c2_cycles  # qa/rr-study/live-gap-now/corpus.py, sys.path'd above
from synth import encoder
from synth.estimator import extract_channel_gains, rho1 as rho1_fn
from synth.wavio import read_wav

DIAL_PREFIX = "14.074"
SNR_FLOOR_DB = -10
SAMPLE_N = 5000
SAMPLE_SEED = 20260916


def load_all_txt(path: str, lo: str, hi: str, dial_prefix: str = DIAL_PREFIX) -> dict:
    """(ts, message) -> (snr, dt_s, freq_hz), Rx FT8 lines on the dial freq in
    [lo, hi]. Same field layout/semantics as live-gap-now's own load() (spec
    Sec.0.3's own warning: [4] SNR, [5] DT, [6] freq Hz), extended to also
    capture DT, which the census's estimator needs and the original loader
    doesn't return.
    """
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if not f[1].startswith(dial_prefix):
                continue
            ts = f[0]
            if not (lo <= ts <= hi):
                continue
            try:
                snr = int(f[4])
                dt_s = float(f[5])
                freq_hz = int(f[6])
            except ValueError:
                continue
            out[(ts, " ".join(f[7:]))] = (snr, dt_s, freq_hz)
    return out


def build_frame(ref_all_txt: str, cycles: "list[tuple[str, str]]"):
    lo = min(ts for ts, _ in cycles)
    hi = max(ts for ts, _ in cycles)
    ref = load_all_txt(ref_all_txt, lo, hi)
    frame_keys = sorted(k for k, v in ref.items() if v[0] >= SNR_FLOOR_DB)
    return ref, frame_keys, lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sample-n", type=int, default=SAMPLE_N)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    cycles, dup_report = c2_cycles()
    wav_by_ts = dict(cycles)
    c2_dir = os.path.dirname(os.path.dirname(list(wav_by_ts.values())[0]))
    ref_path = os.path.join(c2_dir, "wsjtx-1-ft991a", "ALL.TXT")
    owsfz_path = os.path.join(c2_dir, "openwsfz", "ALL.TXT")

    ref, frame_keys, lo, hi = build_frame(ref_path, cycles)
    n_ref_total = len(ref)

    print(f"C2 window: {lo} .. {hi}  ({len(cycles)} cycles, dup report {dup_report})")
    print(f"REF total rows (dial {DIAL_PREFIX}, window): {n_ref_total}")
    print(f"Frame (SNR >= {SNR_FLOOR_DB} dB): {len(frame_keys)} rows"
          f"  (spec expects 60,239)")

    # D3 hit/miss labelling, via the SAME matcher.recovery() the rest of the
    # programme uses (spec Sec.0.3) -- exact + wildcard-gained hit_set.
    from matcher import recovery  # live-gap-now/matcher.py, sys.path'd above
    ows = load_all_txt(owsfz_path, lo, hi)
    # matcher.load()'s tuple shape is (snr, freq_hz); adapt without re-deriving it.
    ows_pairs = {k: (v[0], v[2]) for k, v in ows.items()}
    ref_pairs = {k: (v[0], v[2]) for k, v in ref.items()}
    rec = recovery(ows_pairs, ref_pairs)
    hit_set = rec["hit_set"]
    print(f"D3 basis: matcher.recovery() R_wild={rec['R_wild']:.2f}% "
          f"(n_ref={rec['n_ref']}) -- reproduction check only")

    rng = np.random.default_rng(SAMPLE_SEED)
    n = min(args.sample_n, len(frame_keys))
    sample_idx = rng.choice(len(frame_keys), size=n, replace=False)
    sample_idx.sort()
    sample_keys = [frame_keys[i] for i in sample_idx]

    tones_cache: "dict[str, list[int] | None]" = {}
    rows_out = []
    n_dropped = 0
    n_wav_missing = 0

    for (ts, msg) in sample_keys:
        snr, dt_s, freq_hz = ref[(ts, msg)]
        if msg not in tones_cache:
            try:
                tones_cache[msg] = encoder.message_to_tones(msg)
            except Exception:
                tones_cache[msg] = None
        tones = tones_cache[msg]
        if tones is None:
            n_dropped += 1
            rows_out.append({
                "ts": ts, "snr_db": snr, "dt_s": dt_s, "freq_hz": freq_hz,
                "re_encodable": False, "rho1": None, "hit": None,
            })
            continue

        wav_path = wav_by_ts.get(ts)
        if wav_path is None or not os.path.exists(wav_path):
            n_wav_missing += 1
            rows_out.append({
                "ts": ts, "snr_db": snr, "dt_s": dt_s, "freq_hz": freq_hz,
                "re_encodable": True, "rho1": None, "hit": None, "wav_missing": True,
            })
            continue

        audio, fs = read_wav(wav_path)
        try:
            g = extract_channel_gains(audio, tones, float(freq_hz), dt_s=dt_s, sample_rate_hz=fs)
            r1 = rho1_fn(g)
        except Exception as e:
            n_dropped += 1
            rows_out.append({
                "ts": ts, "snr_db": snr, "dt_s": dt_s, "freq_hz": freq_hz,
                "re_encodable": False, "rho1": None, "hit": None,
                "extract_error": str(e),
            })
            continue

        rows_out.append({
            "ts": ts, "snr_db": snr, "dt_s": dt_s, "freq_hz": freq_hz,
            "re_encodable": True, "rho1": r1, "hit": (ts, msg) in hit_set,
        })

    dropped_share = n_dropped / len(sample_keys)
    print(f"Sample: {len(sample_keys)} rows. Dropped (not re-encodable / extract error): "
          f"{n_dropped} ({dropped_share:.4%}). WAV missing: {n_wav_missing}.")
    if dropped_share > 0.05:
        print("STOP: dropped share exceeds 5% -- per spec Sec.2, tell the Architect "
              "before computing phi.")

    out_path = os.path.join(args.out_dir, "e4_stage2_sample_rows.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "n_ref_total": n_ref_total,
            "n_frame": len(frame_keys),
            "n_sample": len(sample_keys),
            "n_dropped": n_dropped,
            "dropped_share": dropped_share,
            "n_wav_missing": n_wav_missing,
            "window": [lo, hi],
            "rows": rows_out,
        }, f, indent=2)
    print(f"Wrote {out_path} (NFR-021: artefacts/, gitignored -- ts/snr/dt/freq/rho1/hit "
          f"only, no message text or callsigns)")


if __name__ == "__main__":
    main()
