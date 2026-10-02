"""S3c: build the scenario JSON (the artefact whose SHA-256 is committed BEFORE the first battery that
includes S3c, spec 2026-10-02-1730 section 2): the four L values, both decoders' r_ref and k*, the edge
run's commit and build, the design (manifest) and the renders index (SHA-256 of each rendered cycle).

    python s3c_build_scenario.py --out ../scenarios/s3c-edge-guard.json
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s3c_design as S  # noqa: E402
import s3c_render as R  # noqa: E402


def build() -> dict:
    points, ref, edge_sha = S.load_points_and_reference()
    design = S.build_design(points)
    _, index = R.render_all(design)
    return {
        "_comment": ("S3c: lean start-time edge guard (spec qa/rr-study/2026-10-02-1730-architect-to-qa-spec-194-s3c-"
                     "start-time-edge-guard.md; points ruled in 2026-10-02-2225-architect-lateness-edge-ruling.md). "
                     "Points picked mechanically from the edge run by s3c/s3c_design.py:pick_points. "
                     "Rows with k_star = 0 cannot fail and are DESCRIPTIVE."),
        "id": S.SCENARIO_ID,
        "edge_run": {"result_file": S.EDGE_RESULT_RELPATH, "result_sha256": edge_sha,
                     "freeze_commit": S.EDGE_RUN_COMMIT_FREEZE, "build_measured": S.EDGE_RUN_BUILD,
                     "decoders_flag_state": "flag OFF (subtractionEnabled false), both markers true"},
        "snr_db": S.SNR_DB, "signals_per_part": S.SIGNALS_PER_PART,
        "alpha_one_sided": S.ALPHA_ONE_SIDED,
        "points": points, "reference": ref,
        "renders_index": index, "design": design,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    scen = build()
    data = S.canonical_json(scen)
    Path(a.out).write_bytes(data)                       # LF bytes (SHA verifies from any checkout)
    print(hashlib.sha256(data).hexdigest(), a.out)


if __name__ == "__main__":
    main()
