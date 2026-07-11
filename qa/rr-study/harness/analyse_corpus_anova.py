"""S6 corpus replay — continuous Gage R&R ANOVA extension.

analyse_corpus.py already reports within-appraiser consistency and
between-appraiser Cohen's kappa for the *attribute* measurement (decoded /
not-decoded). That is the correct method for a binary outcome, but it is not
an ANOVA, and it does not decompose variance into "how much does an appraiser
disagree with itself across trials" (Repeatability) versus "how much do the
two appraisers disagree with each other" (Reproducibility).

This script adds that: a standard two-way crossed Gage R&R ANOVA (AIAG
method, with interaction) on the *continuous* SNR measurement, for the subset
of signals that both appraisers decoded in every trial (a balanced part x
appraiser x trial cube is required for the classic sum-of-squares formulas).
This mirrors the method already ratified for S1 in STUDY-SPEC.md section 9.1,
applied here to real off-air parts drawn from an endurance-run corpus instead
of synthetic ones.

Usage (from qa/rr-study/):
    python harness/analyse_corpus_anova.py --run-dir results/corpus-<date>

Output (in --run-dir):
    anova_snr.md   -- ANOVA table + Gage R&R variance-component breakdown
    anova_snr.csv  -- part x appraiser x trial SNR matrix (no message text)
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.analyse_corpus import _load_manifest, _build_observations  # noqa: E402


# ── Balanced-subset extraction ──────────────────────────────────────────────

def _balanced_snr_cube(rows: list[dict], n_runs: int) -> dict[tuple, dict[int, tuple[float, float]]]:
    """Return {(wav, sig_key): {run_index: (wsjt_snr, owsfz_snr)}} for parts
    where BOTH appraisers decoded the signal in EVERY run (a complete,
    balanced part x appraiser x trial cell -- required for the ANOVA formulas
    below). Parts with any missing cell are excluded and counted separately.
    """
    by_part: dict[tuple, dict[int, dict]] = defaultdict(dict)
    for r in rows:
        part = (r["wav"], r["sig_key"])
        by_part[part][r["run"]] = r

    cube: dict[tuple, dict[int, tuple[float, float]]] = {}
    for part, by_run in by_part.items():
        if len(by_run) != n_runs:
            continue
        complete = True
        cells: dict[int, tuple[float, float]] = {}
        for run_idx, r in by_run.items():
            if not (r["wsjt_decoded"] and r["owsfz_decoded"]):
                complete = False
                break
            if r["wsjt_snr"] is None or r["owsfz_snr"] is None:
                complete = False
                break
            cells[run_idx] = (float(r["wsjt_snr"]), float(r["owsfz_snr"]))
        if complete:
            cube[part] = cells

    return cube


# ── Two-way crossed ANOVA (AIAG Gage R&R with interaction) ─────────────────

def _gage_rr_anova(cube: dict[tuple, dict[int, tuple[float, float]]], n_runs: int) -> dict:
    """Compute the classic two-way crossed Gage R&R ANOVA on SNR.

    a = 2 appraisers (WSJT-X, OpenWSFZ), n = len(cube) parts, r = n_runs trials.
    """
    parts = sorted(cube.keys())
    n = len(parts)
    a = 2
    r = n_runs

    if n < 2:
        return {"error": f"only {n} balanced parts available; need >= 2 for ANOVA"}

    # x[part_idx][appraiser_idx][trial_idx] = value
    x: list[list[list[float]]] = []
    for part in parts:
        cell_wsjt  = [cube[part][run][0] for run in sorted(cube[part])]
        cell_owsfz = [cube[part][run][1] for run in sorted(cube[part])]
        x.append([cell_wsjt, cell_owsfz])

    all_vals = [v for p in x for app in p for v in app]
    grand_mean = sum(all_vals) / len(all_vals)

    part_means = [sum(p[0] + p[1]) / (a * r) for p in x]
    appraiser_means = [
        sum(x[i][j][k] for i in range(n) for k in range(r)) / (n * r)
        for j in range(a)
    ]
    cell_means = [[sum(x[i][j]) / r for j in range(a)] for i in range(n)]

    ss_part = a * r * sum((pm - grand_mean) ** 2 for pm in part_means)
    ss_appraiser = n * r * sum((am - grand_mean) ** 2 for am in appraiser_means)
    ss_interaction = r * sum(
        (cell_means[i][j] - part_means[i] - appraiser_means[j] + grand_mean) ** 2
        for i in range(n) for j in range(a)
    )
    ss_error = sum(
        (x[i][j][k] - cell_means[i][j]) ** 2
        for i in range(n) for j in range(a) for k in range(r)
    )
    ss_total = sum((v - grand_mean) ** 2 for v in all_vals)

    df_part = n - 1
    df_appraiser = a - 1
    df_interaction = df_part * df_appraiser
    df_error = n * a * (r - 1)
    df_total = n * a * r - 1

    ms_part = ss_part / df_part if df_part > 0 else 0.0
    ms_appraiser = ss_appraiser / df_appraiser if df_appraiser > 0 else 0.0
    ms_interaction = ss_interaction / df_interaction if df_interaction > 0 else 0.0
    ms_error = ss_error / df_error if df_error > 0 else 0.0

    # Variance components (AIAG two-way ANOVA method with interaction)
    ev2 = ms_error
    av2 = max(0.0, (ms_appraiser - ms_interaction) / (n * r))
    int2 = max(0.0, (ms_interaction - ms_error) / r)
    pv2 = max(0.0, (ms_part - ms_interaction) / (a * r))

    ev = ev2 ** 0.5
    av = av2 ** 0.5
    interaction_sd = int2 ** 0.5
    pv = pv2 ** 0.5

    reproducibility2 = av2 + int2
    reproducibility = reproducibility2 ** 0.5

    rr2 = ev2 + reproducibility2
    rr = rr2 ** 0.5

    tv2 = rr2 + pv2
    tv = tv2 ** 0.5

    def pct_contribution(v2: float) -> float:
        return 100.0 * v2 / tv2 if tv2 > 0 else 0.0

    def pct_study_var(v: float) -> float:
        return 100.0 * v / tv if tv > 0 else 0.0

    ndc = 1.41 * (pv / rr) if rr > 0 else float("inf")

    return {
        "n_parts": n, "n_appraisers": a, "n_trials": r,
        "ss": {"part": ss_part, "appraiser": ss_appraiser, "interaction": ss_interaction,
               "error": ss_error, "total": ss_total},
        "df": {"part": df_part, "appraiser": df_appraiser, "interaction": df_interaction,
               "error": df_error, "total": df_total},
        "ms": {"part": ms_part, "appraiser": ms_appraiser, "interaction": ms_interaction,
               "error": ms_error},
        "components": {
            "EV_repeatability": ev, "AV_appraiser": av, "INT_part_x_appraiser": interaction_sd,
            "reproducibility": reproducibility, "RR_combined": rr,
            "PV_part_to_part": pv, "TV_total": tv,
        },
        "pct_contribution": {
            "EV": pct_contribution(ev2), "AV": pct_contribution(av2),
            "INT": pct_contribution(int2), "Reproducibility": pct_contribution(reproducibility2),
            "RR": pct_contribution(rr2), "PV": pct_contribution(pv2),
        },
        "pct_study_var": {
            "EV": pct_study_var(ev), "AV": pct_study_var(av),
            "INT": pct_study_var(interaction_sd), "Reproducibility": pct_study_var(reproducibility),
            "RR": pct_study_var(rr), "PV": pct_study_var(pv),
        },
        "ndc": ndc,
        "appraiser_means": {"wsjt": appraiser_means[0], "owsfz": appraiser_means[1]},
        "grand_mean": grand_mean,
    }


def _write_matrix_csv(cube: dict[tuple, dict[int, tuple[float, float]]], out_path: Path, n_runs: int) -> None:
    """Part x appraiser x trial SNR matrix -- part identity is an opaque index,
    NOT the raw (wav, sig_key) tuple, since sig_key embeds decoded message text
    (may contain real callsigns). No message text or callsign leaves this file.
    """
    parts = sorted(cube.keys())
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["part_index", "wav"] + [f"wsjt_run{k}" for k in range(1, n_runs + 1)] \
                 + [f"owsfz_run{k}" for k in range(1, n_runs + 1)]
        writer.writerow(header)
        for idx, part in enumerate(parts):
            wav, _sig = part
            cells = cube[part]
            wsjt_vals  = [cells[run][0] for run in sorted(cells)]
            owsfz_vals = [cells[run][1] for run in sorted(cells)]
            writer.writerow([idx, wav, *wsjt_vals, *owsfz_vals])


def _write_report(result: dict, n_candidate_parts: int, n_runs: int, out_path: Path) -> None:
    if "error" in result:
        out_path.write_text(f"# Gage R&R ANOVA (SNR) -- FAILED\n\n{result['error']}\n", encoding="utf-8")
        return

    c = result["components"]
    pc = result["pct_contribution"]
    ps = result["pct_study_var"]
    lines = [
        "# Continuous Gage R&R ANOVA -- matched-decode SNR",
        "",
        "Two-way crossed ANOVA with interaction (AIAG Gage R&R method), computed on the",
        "subset of signals both appraisers decoded in every trial (a balanced part x",
        "appraiser x trial cube is required for the sum-of-squares formulas below).",
        "",
        f"- Candidate parts (decoded by either appraiser in any run): **{n_candidate_parts}**",
        f"- Balanced parts (decoded by both appraisers in all {n_runs} runs, used in this ANOVA): "
        f"**{result['n_parts']}** ({100.0 * result['n_parts'] / n_candidate_parts:.1f}% of candidates)",
        "",
        "## ANOVA table",
        "",
        "| Source | SS | df | MS |",
        "|---|---|---|---|",
        f"| Part | {result['ss']['part']:.4f} | {result['df']['part']} | {result['ms']['part']:.4f} |",
        f"| Appraiser | {result['ss']['appraiser']:.4f} | {result['df']['appraiser']} | {result['ms']['appraiser']:.4f} |",
        f"| Part x Appraiser | {result['ss']['interaction']:.4f} | {result['df']['interaction']} | {result['ms']['interaction']:.4f} |",
        f"| Repeatability (error) | {result['ss']['error']:.4f} | {result['df']['error']} | {result['ms']['error']:.4f} |",
        f"| Total | {result['ss']['total']:.4f} | {result['df']['total']} | |",
        "",
        "## Gage R&R variance components",
        "",
        "| Component | SD (dB) | %Contribution (variance) | %Study Variation |",
        "|---|---|---|---|",
        f"| Repeatability (EV) -- appraiser vs itself across trials | {c['EV_repeatability']:.3f} | {pc['EV']:.2f}% | {ps['EV']:.2f}% |",
        f"| Reproducibility (AV) -- appraiser vs appraiser | {c['AV_appraiser']:.3f} | {pc['AV']:.2f}% | {ps['AV']:.2f}% |",
        f"| Part x Appraiser interaction | {c['INT_part_x_appraiser']:.3f} | {pc['INT']:.2f}% | {ps['INT']:.2f}% |",
        f"| Reproducibility (total, AV+INT) | {c['reproducibility']:.3f} | {pc['Reproducibility']:.2f}% | {ps['Reproducibility']:.2f}% |",
        f"| **R&R (EV+Reproducibility combined)** | **{c['RR_combined']:.3f}** | **{pc['RR']:.2f}%** | **{ps['RR']:.2f}%** |",
        f"| Part-to-part (PV) | {c['PV_part_to_part']:.3f} | {pc['PV']:.2f}% | {ps['PV']:.2f}% |",
        f"| Total variation (TV) | {c['TV_total']:.3f} | 100.00% | 100.00% |",
        "",
        f"ndc (number of distinct categories) = **{result['ndc']:.2f}**",
        "",
        "## Appraiser means (matched-decode SNR, dB)",
        "",
        f"- WSJT-X mean: {result['appraiser_means']['wsjt']:.3f} dB",
        f"- OpenWSFZ mean: {result['appraiser_means']['owsfz']:.3f} dB",
        f"- Grand mean: {result['grand_mean']:.3f} dB",
        "",
        "## Interpretation guide (AIAG convention, informational -- not a pass/fail gate on real off-air data)",
        "",
        "- %Study Var(RR) < 10%: measurement system acceptable.",
        "- %Study Var(RR) 10-30%: may be acceptable depending on application.",
        "- %Study Var(RR) > 30%: measurement system needs improvement.",
        "- These AIAG thresholds were designed for manufacturing gauges, not radio decoders on a live",
        "  band; reported here for a standardised reference point, not as a formal acceptance gate.",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, type=Path)
    args = ap.parse_args()

    manifest = _load_manifest(args.run_dir)
    n_runs = len(manifest["runs"])
    rows = _build_observations(manifest)

    cube = _balanced_snr_cube(rows, n_runs)
    n_candidate_parts = len({(r["wav"], r["sig_key"]) for r in rows})

    result = _gage_rr_anova(cube, n_runs)

    csv_path = args.run_dir / "anova_snr.csv"
    _write_matrix_csv(cube, csv_path, n_runs)

    report_path = args.run_dir / "anova_snr.md"
    _write_report(result, n_candidate_parts, n_runs, report_path)

    print(f"Wrote {report_path}")
    print(f"Wrote {csv_path}")
    if "error" not in result:
        print(f"Balanced parts used: {result['n_parts']} / {n_candidate_parts} candidates")
        print(f"R&R %StudyVar: {result['pct_study_var']['RR']:.2f}%")


if __name__ == "__main__":
    main()
