"""S3c: render the 8 planted cycles with the EDGE TEST's own render code (imported, not copied).

    python s3c_render.py --scenario ../scenarios/s3c-edge-guard.json --out <dir> [--verify]

The edge test's `render.render_cycle` draws the noise seed from its module-level `cycle_seed`
(lateness|seed|index). S3c needs its own seeds (harness.common.compute_seed with 'S3c' as the
scenario key, the battery's formula), so that one name is rebound here before rendering; nothing
else of the render path changes (clean_render, truncation at the slot end for late signals, the
shared 4 700 Hz band-limited noise floor with ONE sigma from an untruncated L = 0 unit render, the
harness's `_finalize_playback_samples`).  `--verify` re-renders and compares each cycle's SHA-256 with
the one in the scenario JSON: the audio played in a battery is mechanically the audio that was frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RR = HERE.parent
for p in (str(HERE), str(RR), str(RR / "lateness-edge")):
    if p not in sys.path:
        sys.path.insert(0, p)

import s3c_design as S  # noqa: E402
import render as ER  # noqa: E402  (the edge test's render.py)
from harness.common import compute_seed  # noqa: E402

REFERENCE_SIGMA = 2.0101724620706807         # the edge test's frozen sigma (freeze report section 2)


def s3c_cycle_seed(index: int) -> int:
    return compute_seed("S3c", 0, index)


def render_all(design: dict) -> tuple[dict[int, np.ndarray], dict]:
    sigma = ER.reference_sigma()
    assert sigma == REFERENCE_SIGMA, f"reference sigma moved: {sigma!r}"
    ER.cycle_seed = s3c_cycle_seed                    # see the module docstring
    bufs: dict[int, np.ndarray] = {}
    index: dict[str, dict] = {}
    for c in design["cycles"]:
        i = c["index"]
        if not c["planted"]:
            index[str(i)] = {"planted": False}
            continue
        buf, info = ER.render_cycle(design, i, sigma)
        for r in info["p2"]:
            if "zero_after_end" in r:
                assert r["zero_after_end"] and r["identical_before_end"], r
        bufs[i] = buf
        index[str(i)] = {"planted": True, "sha256": hashlib.sha256(buf.tobytes()).hexdigest(),
                         "n_samples": int(len(buf)), "buffer_start_s": info["buffer_start_s"]}
    return bufs, index


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--out", default=None, help="write cycle_NNN.npy here")
    ap.add_argument("--verify", action="store_true", help="compare with the scenario JSON's renders index")
    a = ap.parse_args()
    scen = json.loads(Path(a.scenario).read_text(encoding="utf-8"))
    design = scen["design"]
    bufs, index = render_all(design)
    if a.verify:
        want = scen["renders_index"]
        bad = [i for i in index if index[i] != want.get(i)]
        print(json.dumps({"verified_cycles": len(index), "mismatch": bad}))
        sys.exit(1 if bad else 0)
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for i, b in bufs.items():
            np.save(out / f"cycle_{i:03d}.npy", b)
    print(json.dumps({"renders_index": index}, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
