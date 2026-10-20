#!/usr/bin/env python3
"""COH-FALLBACK step 3 (spec section 8, A1.4): freeze the decision-replay selection on 20261009_1752 BEFORE any decode.

Slots = every 15 s slot from the first to the last WAV of the night (gap-inclusive; the night is gap-free: 3,634 WAVs, 261009_175200 .. 261010_090015).
Selection = 1-in-k, k ODD (both slot parities are sampled; Q-GATE-2 A1.1), positions i mod k == R of the slot list. Here k = 3, R = 1 (position 0, the launch-edge cycle, is the warm-up).
V-P: even and odd cycle counts within 2 % of each other.
Output: selection.json in the Replay81 harness format ({"runs": {RUN: {STRATUM: [stamps], "warmup": stamp}}}) plus provenance; its LF-normalised SHA-256 is printed.
Numbers and stamps only (HK-037).   python cf_select.py <out dir>
"""
import hashlib
import json
import os
import sys
from datetime import datetime as D, timedelta as T

RUN, STRATUM = "20261009_1752", "Y40"
K, R = 3, 1
ART = os.environ.get("OPENWSFZ_ARTEFACTS", r"D:\Projects\claude\OpenWSFZ\artefacts")
GATHERED = os.path.join(ART, f"{RUN}_endurance_run-gathered")


def main():
    out = sys.argv[1]
    wavs = sorted(f[:-4] for f in os.listdir(os.path.join(GATHERED, "owsfz", "wav")) if f.endswith(".wav"))
    fmt = "%y%m%d_%H%M%S"
    a, b = D.strptime(wavs[0], fmt), D.strptime(wavs[-1], fmt)
    slots, t = [], a
    while t <= b:
        slots.append(t.strftime(fmt)); t += T(seconds=15)
    have = set(wavs)
    missing = [s for s in slots if s not in have]
    assert not missing, ("the night has gaps; the selection rule needs a gap-inclusive plan", len(missing))
    assert K % 2 == 1
    sel = [s for i, s in enumerate(slots) if i % K == R]
    even = sum(1 for s in sel if (int(s[-2:]) // 15) % 2 == 0)
    diff = abs(2 * even - len(sel)) / len(sel)
    spec = {"runs": {RUN: {STRATUM: sel, "warmup": slots[0]}},
            "rule": f"1-in-{K} of the gap-inclusive 15 s slot list, positions i mod {K} == {R}; k odd; warm-up = position 0",
            "slots": len(slots), "selected": len(sel), "even": even, "odd": len(sel) - even, "V-P_diff_pct": round(100 * diff, 3), "V-P": "PASS" if diff <= 0.02 else "FAIL",
            "first_100_selected": sel[:100], "spec": "qa/rr-study/2026-10-07-1330-architect-to-qa-spec-coh-fallback-step3-build.md section 8 (f0b36e54), A1.4"}
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, "selection.json")
    json.dump(spec, open(p, "w"))
    sha = hashlib.sha256(open(p, "rb").read().replace(b"\r\n", b"\n")).hexdigest()
    print(json.dumps({k: v for k, v in spec.items() if k not in ("runs", "first_100_selected")}), "sha256_lf", sha)


if __name__ == "__main__":
    main()
