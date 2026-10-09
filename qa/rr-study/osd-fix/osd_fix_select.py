#!/usr/bin/env python
"""OSD-FIX: freeze selection.json for the TRAIN calibration (spec section 5.2) and reserve the TEST residues (section 5.3).

Spec (PRE-REGISTERED, Architect 2026-10-07 15:45Z; amended by the ruling 2026-10-08 15:45Z):
  qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md   (read on branch arch/osd-fix)

  TRAIN : corpus 20261004_1634, systematic 1-in-10 cycles at residues {0, 5} of the NHARD-REP included list (by POSITION).
          Both lists are taken FROM the NHARD-REP selection.json (pinned by SHA below), not recomputed: SAMPLE (i mod 10 == 0,
          311 cycles) and SAMPLE_B (i mod 10 == 5, 310 cycles). Ordered by position in FULL. 621 cycles. (The spec says "622";
          the frozen lists hold 311 + 310 = 621. The spec's figure is an approximation, stated in the report.)
  TEST  : reserve only. Residues {1, 2, 4, 6, 8, 9} of the same list (disjoint from TRAIN). The fallback of spec 5.3 if no second
          40 m night with full cycle audio exists; the corpus inventory (feedback rule 2026-10-03) decides, and TEST's own
          selection.json is frozen separately, before any FIX decode on TEST. Nothing here chooses TEST.
  WARM-UP : the NHARD-REP warm-up stamp (an excluded edge cycle), decoded and discarded at every process start.
  NOISE : the NHARD-REP 200-WAV noise manifest, referenced by the SHA of its source selection.json (V5).

No decode happens here. Only the frozen NHARD-REP selection.json is read; no WAV, message text, callsign or ALL.TXT content
(HK-037 / NFR-021). Output is deterministic (sorted keys, indent 1, LF); its LF-normalised SHA-256 is printed and must be
committed BEFORE any decode (Architect, 2026-10-08).

  python qa/rr-study/osd-fix/osd_fix_select.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-06-nhard-rep", "selection.json")
SRC_SHA256 = "3cf04abb6b653bac5df70ce587ad48bd5d3bef7205eee6c040f8e2951cb13872"   # LF-normalised bytes (NHARD-REP pin)
OUT_DIR = os.path.join(REPO, "qa", "rr-study", "results", "2026-10-08-osd-fix")
OUT = os.path.join(OUT_DIR, "selection.json")
RUN = "20261004_1634"
TRAIN_RESIDUES = (0, 5)
TEST_RESERVE_RESIDUES = (1, 2, 4, 6, 8, 9)
STEP = 10
EXPECT_FULL, EXPECT_SAMPLE, EXPECT_SAMPLE_B = 3104, 311, 310


def lf_sha(path):
    return hashlib.sha256(open(path, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def build(src_path=SRC):
    assert lf_sha(src_path) == SRC_SHA256, "NHARD-REP selection.json differs from its pin"
    src = json.load(open(src_path, encoding="utf-8"))
    run = src["runs"][RUN]
    full = run["FULL"]
    assert len(full) == EXPECT_FULL and len(run["SAMPLE"]) == EXPECT_SAMPLE and len(run["SAMPLE_B"]) == EXPECT_SAMPLE_B
    assert len(set(full)) == len(full) and full == sorted(full), "FULL must be unique and time-ordered"
    pos = {s: i for i, s in enumerate(full)}
    # the frozen lists must be exactly the residue classes of FULL (guards a mis-pinned source)
    by_res = lambda residues: [s for i, s in enumerate(full) if i % STEP in residues]
    assert run["SAMPLE"] == by_res((0,)) and run["SAMPLE_B"] == by_res((5,)), "SAMPLE/SAMPLE_B are not residues 0/5 of FULL"
    train = sorted(set(run["SAMPLE"]) | set(run["SAMPLE_B"]), key=pos.__getitem__)
    reserve = by_res(TEST_RESERVE_RESIDUES)
    assert not set(train) & set(reserve), "TRAIN and the TEST reserve must be disjoint"
    assert len(train) == EXPECT_SAMPLE + EXPECT_SAMPLE_B
    return {
        "spec": "qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md (branch arch/osd-fix) section 5.2/5.3, ruling 2026-10-08-1545",
        "run": RUN,
        "source": {"file": "qa/rr-study/results/2026-10-06-nhard-rep/selection.json", "sha256_lf": SRC_SHA256},
        "source_dir": src["source_dir"],
        "rule": {"train": f"positions i mod {STEP} in {list(TRAIN_RESIDUES)} of the NHARD-REP included list (FULL)",
                 "test_reserve": f"positions i mod {STEP} in {list(TEST_RESERVE_RESIDUES)} (fallback only; TEST freezes its own selection)"},
        "counts": {"full": len(full), "train": len(train), "test_reserve": len(reserve)},
        "warmup": run["warmup"],
        "TRAIN": train,
        "TEST_RESERVE": reserve,
        "noise_source": "NHARD-REP selection.json 'noise' (200 scored + 1 warm-up, label NHARD-REP-PC)",
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
    print(f"train {len(json.loads(data)['TRAIN'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
