#!/usr/bin/env python
"""OSD-FIX TEST: freeze selection.json for the decision replay (spec section 5.3, ruling 2026-10-09 0615: n* = 24).

Corpus (chosen from the full artefacts/ inventory, feedback rule 2026-10-03; the choice and the rejected candidates are in the TEST-readiness report):
  night 20260930_1930, 40 m (7.074 MHz), Voicemeeter Out B1 capture chain (the chain TRAIN's night 20261004_1634 used), WSJT-X FT-991A ALL.TXT of the same night,
  4,299 archived cycle WAVs. A night other than 20261004_1634, so no TEST cycle played any part in choosing n*.

Cycle list: taken FROM the frozen SUB-FEAS replay selection of this night (its LF SHA-256 is pinned below; 4,298 included cycles, one warm-up stamp, two window-edge
exclusions), not recomputed. TEST = systematic 1-in-5 by POSITION, as two residues of 1-in-10:

  SAMPLE   = positions i mod 10 == 0   (one residue, 430 cycles)
  SAMPLE_B = positions i mod 10 == 5   (a second residue, 430 cycles)
  TEST     = SAMPLE + SAMPLE_B, ordered by position in the included list (860 cycles).
The Captain may choose to run SAMPLE alone (430 cycles, still >= 300) at his go; both lists are frozen here BEFORE any decode and neither depends on any data.

No decode happens here. Only the frozen selection.json is read; no WAV, message text, callsign or ALL.TXT content (HK-037 / NFR-021).
Output is deterministic (sorted keys, indent 1, LF); its LF-normalised SHA-256 is printed and committed BEFORE any decode.

  python qa/rr-study/osd-fix/osd_fix_test_select.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-01-sub-feas-offline-onoff-replay", "selection.json")
SRC_SHA256 = "55a951c86147e92a8262be9d84ffd29362ecd7b63995f62caa7981bd53c977cf"   # LF-normalised bytes (the SUB-FEAS replay pin)
OUT_DIR = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-09-osd-fix-test")
OUT = os.path.join(OUT_DIR, "selection.json")
RUN = "20260930_1930"
STEP = 10
RESIDUES_A, RESIDUES_B = (0,), (5,)
EXPECT_INCLUDED = 4298
EXPECT_SAMPLE, EXPECT_SAMPLE_B = 430, 430
MIN_CYCLES = 300   # spec 5.3


def lf_sha(path):
    return hashlib.sha256(open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def build(src_path=SRC, check_pin=True):
    if check_pin:
        assert lf_sha(src_path) == SRC_SHA256, "the SUB-FEAS selection.json differs from its pin"
    src = json.load(open(src_path, encoding="utf-8"))
    run = src["runs"][RUN]
    full = run["ALL"]
    assert len(full) == EXPECT_INCLUDED and len(set(full)) == len(full) and full == sorted(full), "ALL must be unique and time-ordered"
    pos = {s: i for i, s in enumerate(full)}
    by_res = lambda residues: [s for i, s in enumerate(full) if i % STEP in residues]
    a, b = by_res(RESIDUES_A), by_res(RESIDUES_B)
    assert len(a) == EXPECT_SAMPLE and len(b) == EXPECT_SAMPLE_B, (len(a), len(b))
    assert not set(a) & set(b)
    test = sorted(set(a) | set(b), key=pos.__getitem__)
    assert len(test) >= MIN_CYCLES and len(a) >= MIN_CYCLES
    assert run["warmup"] not in set(test), "the warm-up stamp must not be scored"
    return {
        "spec": "qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md (branch arch/osd-fix) section 5.3; ruling qa/rr-study/2026-10-09-0615-architect-osd-fix-train-nstar-ruling.md (n* = 24)",
        "run": RUN,
        "source": {"file": "qa/rr-study/results/2026-10-01-sub-feas-offline-onoff-replay/selection.json", "sha256_lf": SRC_SHA256},
        "source_dir": src["source_dir"],
        "wav_dir": "artefacts/20260930_1930_endurance_run-gathered/owsfz/wav",
        "wsjtx_alltxt": "artefacts/20260930_1930_endurance_run-gathered/wsjt-x/ALL.TXT",
        "rule": {"SAMPLE": f"positions i mod {STEP} in {list(RESIDUES_A)} of the included list (ALL)",
                 "SAMPLE_B": f"positions i mod {STEP} in {list(RESIDUES_B)}", "TEST": "SAMPLE + SAMPLE_B ordered by position (860 cycles); SAMPLE alone is the 430-cycle option"},
        "counts": {"included": len(full), "SAMPLE": len(a), "SAMPLE_B": len(b), "TEST": len(test)},
        "excluded": src["excluded"],
        "warmup": run["warmup"],
        "SAMPLE": a,
        "SAMPLE_B": b,
        "TEST": test,
    }


def render(obj):
    return (json.dumps(obj, sort_keys=True, indent=1) + "\n").encode("utf-8")


def main():
    data = render(build())
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(data)
    print(f"wrote {OUT}")
    print(f"selection_sha256_lf {hashlib.sha256(data).hexdigest()}")
    c = json.loads(data)["counts"]
    print(c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
