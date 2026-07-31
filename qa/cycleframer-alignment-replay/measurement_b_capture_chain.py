#!/usr/bin/env python3
"""D-001 Measurement B (S6 of the 2026-07-30-2253 Architect ruling, PRIMARY ARM ONLY) --
capture-chain replication at n=300, restricted to |drift| < 0.5 s cycles (S6.2's
"only arm that measures the capture chain" -- pooling drifted cycles would confound this
with the capture-clock-drift defect per S6.2's own explicit warning about the original
design).

Arms (S6.2, unchanged from QA's original 30-cycle 2x2): (our WAV / WSJT-X WAV) x
(our decoder / jt9). Reports the pooled 2x2 for comparability with the original sample, but
the decisive test is PAIRED per-cycle (Wilcoxon signed-rank on per-cycle decode counts,
comparing WAV source within each decoder) -- pooled ratios ignore intra-cycle correlation
and overstate significance (S6.2).

Reading rule (S6.3) is PRE-REGISTERED and reproduced verbatim below -- applied mechanically,
no discretion. Applies to this primary (|drift|<0.5s) arm ONLY.

NFR-021: message text is read only to build per-cycle unique-decode counts (dedup by
normalised message text within each cycle, matching anova_common.py's own convention) and is
never printed or written anywhere. Only aggregate counts and statistics reach output.
ASCII-only console output (HK-009).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="ascii", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "endurance"))
import endurance_anova_jt9 as ejt9  # noqa: E402
import anova_common as ac           # noqa: E402

ROOT = HERE.parents[1] / "artefacts" / "20260729_live_run_1831-8080"
OURS_WAV_DIR = ROOT / "owsfz" / "wav"
WSJTX_WAV_DIR = ROOT / "wsjt-x" / "wav"
OURS_ALL_TXT = ROOT / "owsfz" / "ALL.TXT"

WORK = HERE / "_work" / "measurement_b"
OURS_WAV_SEL = WORK / "ours_wav"
WSJTX_WAV_SEL = WORK / "wsjtx_wav"
OUT_DIR = WORK / "decoded"

N_PRIMARY = int(os.environ.get("MEAS_B_N", "300"))
HEALTHY_LAG_BOUND = 0.5
INTERCEPT = -0.2366
SLOPE = -0.1744  # s/h -- same regression as measure_drift_8080_session.py / Measurement C

DIAL_MHZ = "7.074"
JT9_EXE = r"D:\WSJT\wsjtx\bin\jt9.exe"
HARNESS_EXE = HERE.parents[0] / "rr-study" / "d001-param-sweep-2026-07-22" / "bin" / "Release" / "net10.0" / "D001ParamSweep.exe"
GRID_POINT = "k10_c0.10_n60"


def cycle_ts_to_seconds(stem: str) -> int:
    date_part, time_part = stem.split("_")
    hh, mm, ss = int(time_part[0:2]), int(time_part[2:4]), int(time_part[4:6])
    day_offset = 0 if date_part == "260729" else 1
    return day_offset * 86400 + hh * 3600 + mm * 60 + ss


def select_cycles() -> list[str]:
    common = sorted(
        p.stem for p in OURS_WAV_DIR.glob("*.wav")
        if (WSJTX_WAV_DIR / p.name).exists()
    )
    t0 = cycle_ts_to_seconds(common[0])
    pool = []
    for stem in common:
        elapsed_h = (cycle_ts_to_seconds(stem) - t0) / 3600.0
        predicted = INTERCEPT + SLOPE * elapsed_h
        if abs(predicted) < HEALTHY_LAG_BOUND:
            pool.append(stem)
    if len(pool) <= N_PRIMARY:
        sel = pool
    else:
        stride = len(pool) / N_PRIMARY
        sel = [pool[int(i * stride)] for i in range(N_PRIMARY)]
    print(f"|drift|<{HEALTHY_LAG_BOUND}s pool: {len(pool)} -> sampled {len(sel)}")
    return sel


def run_harness(wav_dir: Path, out_dir: Path) -> None:
    cmd = [str(HARNESS_EXE), "--wav-dir", str(wav_dir), "--out-dir", str(out_dir),
           "--all-txt-name", "ALL.TXT", "--points", GRID_POINT, "--dial-mhz", DIAL_MHZ,
           "--progress-every", "50"]
    print(f"  running harness: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        print(f"[WARN] harness exited {result.returncode}\n{result.stdout[-1500:]}\n{result.stderr[-1500:]}")
    else:
        print(f"  harness done ({len(result.stdout.splitlines())} stdout lines)")


def unique_decodes_per_cycle(rows: list[dict]) -> dict[str, int]:
    """De-dup by (cycle, normalised message) within a single run -- matches
    anova_common.py's own match-key convention -- then counts uniques per cycle."""
    seen = defaultdict(set)
    for r in rows:
        seen[r["ts"]].add(ac.normalize_hash_tokens(r["message"]))
    return {ts: len(msgs) for ts, msgs in seen.items()}


def wilcoxon_signed_rank(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    from scipy.stats import wilcoxon
    diffs = y - x
    nz = diffs[diffs != 0]
    if len(nz) < 5:
        return float("nan"), float("nan")
    stat, p = wilcoxon(x, y, zero_method="wilcox", alternative="two-sided")
    return float(stat), float(p)


def interaction_ci(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    """ad/bc with log-scale 95% CI via independent-Poisson SE, matching the ruling S4.1's
    own method (reused, not reinvented)."""
    import math
    ratio = (a * d) / (b * c)
    se_log = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    z = 1.959963984540054
    lo = ratio * math.exp(-z * se_log)
    hi = ratio * math.exp(z * se_log)
    return ratio, lo, hi


def main() -> int:
    OURS_WAV_SEL.mkdir(parents=True, exist_ok=True)
    WSJTX_WAV_SEL.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sel = select_cycles()
    print(f"\nCopying {len(sel)} WAVs into working dirs...")
    for stem in sel:
        shutil.copy(OURS_WAV_DIR / f"{stem}.wav", OURS_WAV_SEL / f"{stem}.wav")
        shutil.copy(WSJTX_WAV_DIR / f"{stem}.wav", WSJTX_WAV_SEL / f"{stem}.wav")

    print("\n=== jt9 on our WAV ===")
    jt9_on_ours = ejt9.run_jt9(JT9_EXE, [str(OURS_WAV_SEL / f"{s}.wav") for s in sel],
                                depth=3, batch_size=25)
    print(f"jt9-on-ours decodes: {len(jt9_on_ours)}")

    print("\n=== jt9 on WSJT-X WAV ===")
    jt9_on_wsjtx = ejt9.run_jt9(JT9_EXE, [str(WSJTX_WAV_SEL / f"{s}.wav") for s in sel],
                                 depth=3, batch_size=25)
    print(f"jt9-on-wsjtx decodes: {len(jt9_on_wsjtx)}")

    print("\n=== our decoder on our WAV ===")
    run_harness(OURS_WAV_SEL, OUT_DIR / "ours_on_ours")
    print("\n=== our decoder on WSJT-X WAV ===")
    run_harness(WSJTX_WAV_SEL, OUT_DIR / "ours_on_wsjtx")

    ours_on_ours = ac.parse_all_txt(str(OUT_DIR / "ours_on_ours" / GRID_POINT / "ALL.TXT"))
    ours_on_wsjtx = ac.parse_all_txt(str(OUT_DIR / "ours_on_wsjtx" / GRID_POINT / "ALL.TXT"))

    sel_set = set(sel)

    def restrict(rows):
        return [r for r in rows if r["ts"] in sel_set]

    series = {
        "a_ours_ourwav": restrict(ours_on_ours),
        "b_ours_wsjtxwav": restrict(ours_on_wsjtx),
        "c_jt9_ourwav": restrict(jt9_on_ours),
        "d_jt9_wsjtxwav": restrict(jt9_on_wsjtx),
    }

    counts = {k: unique_decodes_per_cycle(v) for k, v in series.items()}
    totals = {k: sum(c.values()) for k, c in counts.items()}
    a, b, c, d = totals["a_ours_ourwav"], totals["b_ours_wsjtxwav"], totals["c_jt9_ourwav"], totals["d_jt9_wsjtxwav"]

    print("\n=== Pooled 2x2 (unique cycle,message decodes) ===")
    print(f"  a) ours / our WAV    = {a}")
    print(f"  b) ours / WSJT-X WAV = {b}")
    print(f"  c) jt9  / our WAV    = {c}")
    print(f"  d) jt9  / WSJT-X WAV = {d}")

    ratio_ab = b / a
    ratio_cd = d / c
    print(f"\n  capture-chain effect, our decoder: WSJT-X-WAV/our-WAV = {ratio_ab:.4f} ({(ratio_ab-1)*100:+.1f}%)")
    print(f"  capture-chain effect, jt9 decoder: WSJT-X-WAV/our-WAV = {ratio_cd:.4f} ({(ratio_cd-1)*100:+.1f}%)")

    interaction, ilo, ihi = interaction_ci(a, b, c, d)
    print(f"\n  interaction ad/bc = {interaction:.4f}  95% CI [{ilo:.4f}, {ihi:.4f}]")

    # ---- paired per-cycle Wilcoxon: our-WAV vs WSJT-X-WAV, within each decoder ----
    def paired_arrays(count_a: dict, count_b: dict, cycles: list[str]) -> tuple[np.ndarray, np.ndarray]:
        xa = np.array([count_a.get(s, 0) for s in cycles], dtype=float)
        xb = np.array([count_b.get(s, 0) for s in cycles], dtype=float)
        return xa, xb

    xa, xb = paired_arrays(counts["a_ours_ourwav"], counts["b_ours_wsjtxwav"], sel)
    stat_ours, p_ours = wilcoxon_signed_rank(xa, xb)
    xc, xd = paired_arrays(counts["c_jt9_ourwav"], counts["d_jt9_wsjtxwav"], sel)
    stat_jt9, p_jt9 = wilcoxon_signed_rank(xc, xd)

    print(f"\n=== Paired Wilcoxon signed-rank (our-WAV vs WSJT-X-WAV per cycle) ===")
    print(f"  our decoder: mean(a)={xa.mean():.3f} mean(b)={xb.mean():.3f}  W={stat_ours:.1f} p={p_ours:.4f}")
    print(f"  jt9 decoder: mean(c)={xc.mean():.3f} mean(d)={xd.mean():.3f}  W={stat_jt9:.1f} p={p_jt9:.4f}")

    # ---- apply the pre-registered reading rule mechanically ----
    p_combined = max(p_ours, p_jt9)  # conservative: BOTH must clear the bar to "confirm"
    direction_consistent = (ratio_ab > 1.0) and (ratio_cd > 1.0)
    if p_combined < 0.01 and direction_consistent:
        outcome = "EFFECT CONFIRMED (both arms p<0.01, consistent direction) -> fold into row 4 decomposition WITH measured magnitude+CI."
    elif ilo <= 1.0 <= ihi and p_combined >= 0.05:
        outcome = "EFFECT REFUTED (interaction CI spans no-effect, p>=0.05) -> DROP. Strike S3's percentages."
    elif 0.01 <= p_combined < 0.05:
        outcome = "AMBIGUOUS (0.01<=p<0.05) -> report as bounded-small. Do NOT escalate n further."
    else:
        outcome = "AMBIGUOUS/borderline -- does not cleanly match a reading-rule row. Report descriptively, escalate interpretation."

    report_lines = [
        "# Measurement B -- capture-chain replication, primary arm (D-001 ruling S6)\n",
        f"n = {len(sel)} cycles, |drift| < {HEALTHY_LAG_BOUND}s (drift-free primary arm per S6.2).\n",
        "## Pooled 2x2 (unique cycle,message decodes)\n",
        "| | our WAV | WSJT-X WAV |",
        "|---|---:|---:|",
        f"| **our decoder** | {a} (a) | {b} (b) |",
        f"| **jt9** | {c} (c) | {d} (d) |",
        f"\ncapture-chain ratio, our decoder: {ratio_ab:.4f} ({(ratio_ab-1)*100:+.1f}%)",
        f"\ncapture-chain ratio, jt9: {ratio_cd:.4f} ({(ratio_cd-1)*100:+.1f}%)",
        f"\ninteraction ad/bc = {interaction:.4f}, 95% CI [{ilo:.4f}, {ihi:.4f}]",
        "\n## Paired per-cycle Wilcoxon signed-rank (decisive test, S6.2)\n",
        f"our decoder: mean(our WAV)={xa.mean():.3f}, mean(WSJT-X WAV)={xb.mean():.3f}, "
        f"W={stat_ours:.1f}, p={p_ours:.4f}",
        f"\njt9: mean(our WAV)={xc.mean():.3f}, mean(WSJT-X WAV)={xd.mean():.3f}, "
        f"W={stat_jt9:.1f}, p={p_jt9:.4f}",
        "\n## Pre-registered reading rule (S6.3, applies to this primary arm only)\n",
        "| outcome | reading | consequence |",
        "|---|---|---|",
        "| Effect confirmed, paired p<0.01, direction as in S3 | The capture chain really does cost us decodes. | Folds into row 4 decomposition with measured magnitude and CI |",
        "| Effect refuted, CI comfortably spans zero | n=30 was noise. | Drop it. Strike S3's percentages. |",
        "| Ambiguous (0.01<=p<0.05, or CI includes zero but point estimate holds) | Underpowered even at n=300. | Report as bounded-small. Do not escalate n further. |",
        f"\n**Mechanical outcome: {outcome}**\n",
    ]
    report_path = HERE / "measurement_b_capture_chain_report.md"
    with open(report_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write("\n".join(report_lines) + "\n")
    print(f"\nWrote: {report_path}")
    print(f"\n>>> MECHANICAL OUTCOME: {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
