#!/usr/bin/env python3
"""Task 4 completion -- cross-source penalty calibration, per
`2026-07-31-1148-architect-ruling-task4-row2-suspended-reference-asymmetry.md` S3.

Measures the "cross-source handicap": how much lower parity reads when the reference decoder
(jt9) decodes a DIFFERENT recording of the same over-the-air signal than the decoder under
test used, versus when both decode the identical recording. This is the confound S2 of that
ruling identified between the density law's three same-source anchor points and 489135a's
cross-source recompute.

Design (ruling S3, reusing Measurement C's already-selected healthy stratum verbatim -- do
NOT re-cut it):
  - 150 healthy-window cycles (|predicted lag| < 0.5s), from `measurement_c_manifest.csv`.
  - "our decodes" = OpenWSFZ's own decode of its own unshifted WAV for these cycles, already
    on disk at `_work/measurement_c/decoded/unshifted/k10_c0.10_n60/ALL.TXT` (Measurement C's
    own output -- reused, not re-run).
  - arm (a) same-source: jt9 decodes OUR unshifted WAV (the identical recording "our decodes"
    came from) -- NEW jt9 run, ~150 WAVs.
  - arm (b) cross-source: jt9 decodes WSJT-X's WAV for the SAME 150 cycles -- NEW jt9 run.
  - Both arms matched against the SAME "our decodes" set, both using jt9 as the reference
    (denominator) -- NOT WSJT-X's live ALL.TXT, which is what Measurement C's own published
    table used as its reference throughout. That distinction matters: 489135a's own recompute
    (and the density-law table) both use jt9-as-reference parity, so this calibration must use
    the identical convention to be comparable -- reusing Measurement C's PUBLISHED 61.4%
    figure (which is ours-vs-WSJT-X-live, a different reference decoder entirely) would be an
    apples-to-oranges substitution for arm (a), not a same-source/cross-source comparison.
    Verified this distinction by inspection before running anything (see the QA write-up).

NFR-021: message text used only for match keys via anova_common's own convention; never
printed beyond aggregate counts. WAVs and jt9 raw output stay under git-ignored paths.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "endurance"))
import anova_common as ac          # noqa: E402
import endurance_anova_jt9 as ej9  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

MANIFEST = os.path.join(HERE, "measurement_c_manifest.csv")
OURS_UNSHIFTED_WAV_DIR = os.path.join(HERE, "_work", "measurement_c", "unshifted")
OURS_UNSHIFTED_ALL_TXT = os.path.join(
    HERE, "_work", "measurement_c", "decoded", "unshifted", "k10_c0.10_n60", "ALL.TXT")
WSJTX_WAV_DIR = os.path.normpath(os.path.join(
    HERE, "..", "..", "artefacts", "20260729_live_run_1831-8080", "wsjt-x", "wav"))

JT9_EXE = ej9.DEFAULT_JT9_EXE


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def main() -> int:
    healthy_stems = [r["stem"] for r in csv.DictReader(open(MANIFEST, encoding="ascii"))
                      if r["stratum"] == "healthy"]
    print(f"healthy stems (reused from measurement_c_manifest.csv, not re-cut): "
          f"{len(healthy_stems)}")

    ours_all = ac.parse_all_txt(OURS_UNSHIFTED_ALL_TXT)
    stem_set = set(healthy_stems)
    ours_rows = [r for r in ours_all if r["ts"] in stem_set]
    print(f"our decodes (healthy, unshifted, from Measurement C's own output): {len(ours_rows)}")

    ours_wav_paths = [os.path.join(OURS_UNSHIFTED_WAV_DIR, f"{s}.wav") for s in healthy_stems]
    wsjtx_wav_paths = [os.path.join(WSJTX_WAV_DIR, f"{s}.wav") for s in healthy_stems]
    assert all(os.path.isfile(p) for p in ours_wav_paths), "missing our unshifted WAV"
    assert all(os.path.isfile(p) for p in wsjtx_wav_paths), "missing WSJT-X WAV"

    print(f"\n=== arm (a) same-source: jt9 decoding OUR own WAV (n={len(ours_wav_paths)}) ===")
    jt9_on_ours = ej9.run_jt9(JT9_EXE, ours_wav_paths, depth=3, batch_size=150)
    print(f"jt9-on-our-WAV decodes: {len(jt9_on_ours)}")

    print(f"\n=== arm (b) cross-source: jt9 decoding WSJT-X's WAV, same cycles "
          f"(n={len(wsjtx_wav_paths)}) ===")
    jt9_on_wsjtx = ej9.run_jt9(JT9_EXE, wsjtx_wav_paths, depth=3, batch_size=150)
    print(f"jt9-on-WSJT-X-WAV decodes: {len(jt9_on_wsjtx)}")

    pairs_a = ac.match_pairs(ours_rows, jt9_on_ours)
    pairs_b = ac.match_pairs(ours_rows, jt9_on_wsjtx)

    matched_a, ref_a = len(pairs_a), len(jt9_on_ours)
    matched_b, ref_b = len(pairs_b), len(jt9_on_wsjtx)
    parity_a = matched_a / ref_a if ref_a else float("nan")
    parity_b = matched_b / ref_b if ref_b else float("nan")
    ci_a = wilson_interval(matched_a, ref_a)
    ci_b = wilson_interval(matched_b, ref_b)

    penalty_pts = (parity_a - parity_b) * 100

    print(f"\narm (a) same-source (jt9 on our WAV):    matched={matched_a} ref={ref_a} "
          f"parity={parity_a*100:.1f}% CI=[{ci_a[0]*100:.1f}%,{ci_a[1]*100:.1f}%]")
    print(f"arm (b) cross-source (jt9 on WSJT-X WAV): matched={matched_b} ref={ref_b} "
          f"parity={parity_b*100:.1f}% CI=[{ci_b[0]*100:.1f}%,{ci_b[1]*100:.1f}%]")
    print(f"\npenalty = (a) - (b) = {penalty_pts:+.2f} points")
    print(f"CI overlap check: arm(a) CI={ci_a}, arm(b) CI={ci_b}, "
          f"overlap={'YES' if ci_a[0] < ci_b[1] and ci_b[0] < ci_a[1] else 'NO'}")

    out_path = os.path.join(HERE, "measurement_task4_calibration_penalty_report.md")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("# Task 4 completion -- cross-source penalty calibration\n\n")
        fh.write(f"Healthy stratum: {len(healthy_stems)} cycles, reused verbatim from "
                 f"`measurement_c_manifest.csv` (not re-cut).\n\n")
        fh.write("| arm | matched | ref (jt9) | parity | 95% CI |\n")
        fh.write("|---|---:|---:|---:|---|\n")
        fh.write(f"| (a) same-source: jt9 on our WAV | {matched_a} | {ref_a} | "
                 f"{parity_a*100:.1f}% | [{ci_a[0]*100:.1f}%,{ci_a[1]*100:.1f}%] |\n")
        fh.write(f"| (b) cross-source: jt9 on WSJT-X WAV | {matched_b} | {ref_b} | "
                 f"{parity_b*100:.1f}% | [{ci_b[0]*100:.1f}%,{ci_b[1]*100:.1f}%] |\n\n")
        fh.write(f"**Penalty = (a) - (b) = {penalty_pts:+.2f} points.**\n\n")
        fh.write(f"CI overlap: {'YES' if ci_a[0] < ci_b[1] and ci_b[0] < ci_a[1] else 'NO'}\n")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
