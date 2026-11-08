#!/usr/bin/env python3
"""Validity row V-F for the DI7COH2 R&R series (QA 2026-10-22; Architect K2): was the coherent fallback RUNNING in this sweep?

    python3 flag_readback.py --daemon-log <sweep supervisor dir>/daemon.stdout.log --config <sweep config> --out <flag_readback.json> [--bar 0.95]

Two things must agree, or the sweep's era row is VOID (the sweep's other results stay readable, but never as a DI7COH row):
  (a) the sweep config carries decoder.coherentFallbackEnabled = true EXPLICITLY (the build's default is true, but the read-back is compared with an explicit value);
  (b) the daemon wrote its per-cycle line `Coherent fallback: eligible=...` in at least BAR of the cycles. The DENOMINATOR is the per-cycle line
      `Cycle hh:mm:ss: N decode(s) found` (one per decoded cycle). The fallback line is written only when the flag is on and the decode snapshot exists
      (Ft8Decoder.cs, cohOn && snapshot), so a count near the denominator is a flag-EFFECTIVE read-back, not a config echo.
BAR 0.95 is the Architect's decision value (review K2, 2026-10-22). Where the evidence comes from: in the FULL R14 live window (2026-10-22 15:14:56Z to 17:20:50Z) the
fallback line was written in 504 of 504 cycle lines = 1.000. Counts only; no message text is read (the two line shapes are matched, nothing else is kept).
Prints VALID or VOID: <reason>; exits 0 / 3.
"""
import argparse
import json
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--daemon-log", required=True)
ap.add_argument("--config", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--bar", type=float, default=0.95)
ap.add_argument("--require-audio", default=None, help="COH-FB-AUDIO (2026-10-27): Original|Residual|Both; the config key must equal it and the fallback lines must carry the matching audio= label in >= BAR of the fallback lines")
a = ap.parse_args()

dec = json.load(open(a.config, encoding="utf8"))["decoder"]
flag = dec.get("coherentFallbackEnabled", "absent")
audio_cfg = dec.get("coherentFallbackAudio", "absent")
cycle_rx = re.compile(r"Cycle \d\d:\d\d:\d\d: \d+ decode\(s\) found")
cycles = coh = coh_audio = 0
label = {"Both": "audio=both(", "Residual": "audio=residual", "Original": "audio=original"}.get(a.require_audio)
with open(a.daemon_log, encoding="utf8", errors="replace") as fh:
    for ln in fh:
        if cycle_rx.search(ln):
            cycles += 1
        if "Coherent fallback: eligible=" in ln:
            coh += 1
            if label and label in ln:
                coh_audio += 1
frac = (coh / cycles) if cycles else None
res = {"config_audio": audio_cfg, "require_audio": a.require_audio, "fallback_lines_with_required_audio_label": coh_audio, "config_flag": flag, "cycle_lines": cycles, "fallback_lines": coh, "fraction": frac, "bar": a.bar}
if flag is not True:
    res["result"], res["reason"] = "VOID", "the sweep config does not carry decoder.coherentFallbackEnabled = true (read %r)" % (flag,)
elif a.require_audio and audio_cfg != a.require_audio:
    res["result"], res["reason"] = "VOID", "the sweep config carries decoder.coherentFallbackAudio = %r, required %r" % (audio_cfg, a.require_audio)
elif not cycles:
    res["result"], res["reason"] = "VOID", "no cycle lines in the daemon log"
elif frac < a.bar:
    res["result"], res["reason"] = "VOID", "the fallback line was written in %d of %d cycles (%.3f), below the bar %.2f" % (coh, cycles, frac, a.bar)
elif a.require_audio and (not coh or coh_audio / coh < a.bar):
    res["result"], res["reason"] = "VOID", "the required audio label %r was on %d of %d fallback lines, below the bar %.2f" % (label, coh_audio, coh, a.bar)
else:
    res["result"], res["reason"] = "VALID", "config flag true; the fallback line in %d of %d cycles (%.3f >= %.2f)" % (coh, cycles, frac, a.bar)
json.dump(res, open(a.out, "w", encoding="utf8"), indent=1)
print(res["result"] + ": " + res["reason"])
sys.exit(0 if res["result"] == "VALID" else 3)
