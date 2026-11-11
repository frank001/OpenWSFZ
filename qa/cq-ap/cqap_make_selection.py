"""Writes the two Replay81 selection files for the CQ-AP arms from the frozen cycle list (no message text, no decode involved).

  sel_500.json  every cycle of qa/cq-ap/live-session-cycle-list.txt, in order (the OFF / ON / OFF2 arms)
  sel_50.json   the FIRST 50 of them (the V-OFF reference run on 98332f2a)
The warm-up cycle (decoded once per process and discarded, as in every Replay81 run) is the archive cycle immediately BEFORE the first listed one;
it must have a WAV and must not be in the list. The list's SHA-256 is asserted against the freeze record's value.
"""
import hashlib, json, os, sys

LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live-session-cycle-list.txt")
LIST_SHA = "842e67909378a0d1dbf387b27d2e080b4f1e8c1dec3e9bd9770e2e3bac76c8f9"      # freeze Part 1, section 1 ("Cycle list")
WAVDIR = r"D:\Projects\claude\OpenWSFZ\artefacts\20261110_1817_cq-ap-live\owsfz\wav"
RUN = "20261110_1817"
OUT = r"D:\Projects\claude\_qa-scratch\cq-ap"


def main():
    raw = open(LIST, "rb").read()
    assert hashlib.sha256(raw).hexdigest() == LIST_SHA, "cycle list differs from the freeze"
    stamps = [x.strip().replace(".wav", "") for x in raw.decode().splitlines() if x.strip() and not x.startswith("#")]
    assert len(stamps) == 500 and stamps[0] == "261110_184745" and stamps[-1] == "261110_205230", (len(stamps), stamps[0], stamps[-1])
    wavs = sorted(f[:-4] for f in os.listdir(WAVDIR) if f.endswith(".wav"))
    assert all(s in set(wavs) for s in stamps), "a listed cycle has no WAV"
    warm = max(w for w in wavs if w < stamps[0])
    assert warm not in stamps
    for name, sel in (("sel_500.json", stamps), ("sel_50.json", stamps[:50])):
        doc = {"note": f"CQ-AP arms: {len(sel)} cycles of live-session-cycle-list.txt (sha {LIST_SHA[:8]}); warm-up {warm}", "outage_dropped": 0, "run": RUN,
               "runs": {RUN: {"FULL": sel, "warmup": warm}}}
        json.dump(doc, open(os.path.join(OUT, name), "w"), indent=1)
        print(name, len(sel), "warm-up", warm, "sha", hashlib.sha256(open(os.path.join(OUT, name), "rb").read()).hexdigest()[:12])


if __name__ == "__main__":
    sys.exit(main())
