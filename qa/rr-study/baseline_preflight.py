"""R&R baseline PRE-FLIGHT (attended or not): chain-quiet measurement + the standard warm-up cycle,
checked mechanically instead of by a human typing 'y'.

    python baseline_preflight.py --device "Voicemeeter AUX Input" --capture "Voicemeeter Out B1" \
        --wsjt-all-txt <path> --owsfz-all-txt <path> --out <preflight.json>

1. CHAIN QUIET: with NOTHING playing, capture ~QUIET_S seconds from the B1 capture device (the device both
   decoders listen to) and require RMS below QUIET_RMS_MAX. A hot chain (the radio still in it) would put
   off-air audio and real callsigns into the run (NFR-021) and into S5's noise-floor gates.
2. WARM-UP: play the harness's own warm-up cycle (harness/warmup.py: _render_warmup_cycle, +6 dB, fixed
   seed) at the next boundary; after the settle time require BOTH ALL.TXT files to have gained a line
   carrying the warm-up message (counted, never printed: HK-037).
Writes <out> (counts and verdicts only). Exit 0 = PASS, 1 = FAIL, 2 = environment error.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

QUIET_S = 12.0
QUIET_RMS_MAX = 1.0e-4            # full-scale float; the edge run's chain-quiet reading was 0.000
SETTLE_S = 8.0
MAX_ATTEMPTS = 3


def _count_message_lines(path: Path, message: str) -> int:
    try:
        return sum(1 for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
                   if message in ln)
    except OSError:
        return -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="Voicemeeter AUX Input", help="playback device substring")
    ap.add_argument("--capture", default="Voicemeeter Out B1", help="capture device substring (B1)")
    ap.add_argument("--wsjt-all-txt", required=True)
    ap.add_argument("--owsfz-all-txt", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import numpy as np
    import sounddevice as sd
    from harness import warmup as W
    from harness import run_scenario as rs

    res: dict = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # ---- 1. chain quiet
    cands = [i for i, d in enumerate(sd.query_devices())
             if a.capture.lower() in d["name"].lower() and d["max_input_channels"] > 0]
    # several host APIs expose the same endpoint: prefer the 48 kHz one (the chain's shared format)
    cands.sort(key=lambda i: (int(sd.query_devices(i)["default_samplerate"]) != 48000, i))
    cap_idx = cands[0] if cands else None
    if cap_idx is None:
        res["chain_quiet"] = {"pass": False, "error": "capture device not found"}
        Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
        return 2
    info = sd.query_devices(cap_idx)
    sr = int(info["default_samplerate"])
    rec = sd.rec(int(QUIET_S * sr), samplerate=sr, channels=1, device=cap_idx, dtype="float32")
    sd.wait()
    rms = float(np.sqrt(np.mean(np.square(rec.astype("float64")))))
    peak = float(np.max(np.abs(rec)))
    res["chain_quiet"] = {"device": info["name"], "seconds": QUIET_S, "rms": rms, "peak": peak,
                          "rms_max": QUIET_RMS_MAX, "pass": rms < QUIET_RMS_MAX}

    # ---- 2. warm-up
    msg = W._WARMUP_MESSAGE
    wj, ow = Path(a.wsjt_all_txt), Path(a.owsfz_all_txt)
    samples = W._render_warmup_cycle()
    dev = rs._select_device(a.device)
    attempts = []
    ok = False
    for n in range(1, MAX_ATTEMPTS + 1):
        before = (_count_message_lines(wj, msg), _count_message_lines(ow, msg))
        b = W._next_cycle_boundary()
        W._wait_for_cycle(b)
        sd.play(samples, samplerate=W.DEFAULT_SAMPLE_RATE_HZ, device=dev, blocking=False)
        sd.wait()
        time.sleep(SETTLE_S)
        after = (_count_message_lines(wj, msg), _count_message_lines(ow, msg))
        got = (after[0] > max(before[0], 0) or (before[0] <= 0 < after[0]),
               after[1] > max(before[1], 0) or (before[1] <= 0 < after[1]))
        attempts.append({"attempt": n, "wsjtx_gained": got[0], "owsfz_gained": got[1],
                         "wsjtx_lines": after[0], "owsfz_lines": after[1]})
        if got[0] and got[1]:
            ok = True
            break
    res["warmup"] = {"attempts": attempts, "pass": ok}
    res["pass"] = bool(res["chain_quiet"]["pass"] and ok)
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({"chain_quiet": res["chain_quiet"], "warmup_pass": ok, "pass": res["pass"]}))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
