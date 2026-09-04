#!/usr/bin/env python3
"""S5-BASELINE -- reconstruct the S5 AWGN false-positive baseline (QA task).

Spec: qa/rr-study/2026-09-04-1911-architect-to-qa-spec-s5-baseline-reconstruction.md
(Architect -> QA, 2026-09-04 19:11Z). Ships every ROW predicate below as code (HK-021(r))
rather than leaving them as prose to re-derive by hand.

No decode. No capture. No playback. No `src/`/`native/` change. Pure re-analysis of
already-committed run directories under qa/rr-study/results/, plus one in-process render
(ROW 0b) that reuses the harness's own rendering functions -- it does not reimplement them
(the ACTION B ruling's lesson).

Rows, evaluated in order:
  ROW 0a -- reproduction gate. Recompute each admissible run's FP event count and N from its
            own truth.csv + S5_matched.csv, compare against that run's own report.md gate
            line. FIRES -> STOP.
  ROW 0b -- audio-condition equivalence. Render s5-noise.json part 0 and s5-noise-wide.json
            part 0 for trial_index 0..29 via the harness's own compute_seed / _render_noise /
            _finalize_playback_samples, SHA256 each buffer. FIRES -> July runs inadmissible.
  ROW 0c -- census completeness. Enumerate every S5-bearing run directory DIRECTLY FROM DISK
            under qa/rr-study/results/ (recursively; a truth.csv with a scenario_id=="S5" row
            is the criterion -- NOT the presence of S5_matched.csv, which four dirs on disk
            lack despite carrying real S5 truth rows). FIRES -> add the run(s), rebuild the
            series.
  ROW 0d -- identifiability of battery context. Cross-tabulate era x context for every
            admissible run. FIRES -> ROW 1 may not be reported as a ratio or p-value.
  ROW 1  -- is the pre-window below the shipped-configuration July baseline?
  ROW 2  -- boundary-free trend: conditional permutation test, no change point.

Usage:
    python qa/rr-study/s5_baseline_reconstruction.py
Writes qa/rr-study/s5_baseline_reconstruction_results.txt (this stdout transcript) alongside
qa/rr-study/s5_baseline_reconstruction_result.json (machine-readable row outcomes).

HARD STOP (spec Section 6): the session stops after ROW 2, on either branch. This script
computes and reports; it draws no conclusion about the arm, the re-scope, or the regression
(spec Section 6: "QA reports the table and the mechanical row outcomes... does NOT rule on
what this means").
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import numpy as np
from scipy import stats

# Reuse, don't reimplement (ACTION B's lesson) -- these two functions are the ROW-C1-verified
# join from FP-COMPOSITION (2026-09-04 18:48Z, 18/18 pairs reproduced exactly).
from fp_composition_per_part import load_s5_part_map, scoped_fp_events

# Reuse the harness's own rendering functions for ROW 0b (spec's explicit instruction).
from harness.common import compute_seed
from harness.run_scenario import _render_noise, _finalize_playback_samples

RESULTS = _HERE / "results"
SCENARIOS = _HERE / "scenarios"
RESULTS_TXT = _HERE / "s5_baseline_reconstruction_results.txt"
RESULT_JSON = _HERE / "s5_baseline_reconstruction_result.json"

RANDR004_DATE = "2026-07-04"          # R&R-004 ratified UB gate
PRE_WINDOW = ("2026-08-05", "2026-08-21")
POST_WINDOW = ("2026-08-22", "2026-09-03")
MIN_N_AWGN = 49                        # below this the gate is INFO by construction
AWGN_PARTS = {"0", "1"}                # s5-noise.json family; the wide family has only part 0,
                                        # already AWGN, so this set applies uniformly.
ROW0B_N_TRIALS = 30
ROW2_SEED = 20260904
ROW2_MC_DRAWS = 2_000_000

_RUN_DATE_LINE_RE = re.compile(r"\|\s*Run date\s*\|([^|]*)\|")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def log(lines: list, msg: str = "") -> None:
    print(msg)
    lines.append(msg)


# ---------------------------------------------------------------------------
# Disk primitives
# ---------------------------------------------------------------------------

def scenario_ids_present(run_dir: Path) -> Counter:
    ids: Counter = Counter()
    with (run_dir / "truth.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ids[row["scenario_id"]] += 1
    return ids


def discover_s5_dirs() -> list[Path]:
    """Every run directory under results/ (any depth) whose truth.csv contains at least one
    scenario_id=='S5' row. NOT gated on S5_matched.csv presence -- four dirs on disk carry
    real S5 truth rows with no matched.csv at all (d009-k10-confirm-s5[-clean],
    2026-06-20-ccda50c-s5-wide, diag-nhard-2026-06-20); gating on the matched file would have
    silently repeated the exact blind spot ROW 0c exists to catch."""
    dirs = []
    for truth_path in sorted(RESULTS.rglob("truth.csv")):
        run_dir = truth_path.parent
        try:
            ids = scenario_ids_present(run_dir)
        except (OSError, KeyError, csv.Error):
            continue
        if ids.get("S5", 0) > 0:
            dirs.append(run_dir)
    return dirs


def parse_ratified_gate(report_text: str) -> dict | None:
    """{'OpenWSFZ': (k, n, verdict), 'WSJT-X': (k, n, verdict)} from the FIRST
    '### False-positive rate (S5)' table, only if it uses the ratified 6-column format
    ('FP events / slots' + '95% UB' headers present). Pre-ratification reports use a
    3-column 'FP rate' table (no event/slot breakdown, no UB) and read as None here --
    this IS admissibility criterion 1, expressed mechanically rather than by date alone,
    since date and metric-format agree in every case checked but the format is the more
    direct predicate."""
    idx = report_text.find("### False-positive rate (S5)")
    if idx == -1:
        return None
    chunk = report_text[idx: idx + 3000]
    table_lines = [l for l in chunk.splitlines() if l.strip().startswith("|")]
    if len(table_lines) < 3:
        return None
    header = [c.strip() for c in table_lines[0].strip("|").split("|")]
    if "FP events / slots" not in header or "95% UB" not in header:
        return None
    out = {}
    for line in table_lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != len(header):
            break
        rec = dict(zip(header, cells))
        m = re.match(r"(\d+)\s*/\s*(\d+)", rec.get("FP events / slots", ""))
        if not m:
            continue
        out[rec.get("Appraiser", "")] = (int(m.group(1)), int(m.group(2)), rec.get("Verdict", ""))
    return out or None


def rel(run_dir: Path) -> str:
    return run_dir.relative_to(RESULTS).as_posix()


def find_run_date(run_dir: Path, report_text: str) -> str | None:
    """A YYYY-MM-DD date, searched for (not anchored) in: the report.md 'Run date' table
    cell (which is free text, e.g. 'd011-fp-recheck (2026-07-04)', not always a bare date);
    then the leaf directory name; then each ancestor up to RESULTS (a nested run dir, e.g.
    d009-ablation-2026-06-21/cfg1-s5, carries its date on the PARENT, not the leaf)."""
    if report_text:
        m = _RUN_DATE_LINE_RE.search(report_text)
        if m:
            dm = _DATE_RE.search(m.group(1))
            if dm:
                return dm.group(1)
    node = run_dir
    while True:
        dm = _DATE_RE.search(node.name)
        if dm:
            return dm.group(1)
        if node == RESULTS or node.parent == node:
            return None
        node = node.parent


def era_of(date: str) -> str:
    if date < "2026-08-05":
        return "2026-07"
    if PRE_WINDOW[0] <= date <= PRE_WINDOW[1]:
        return "pre-window"
    if POST_WINDOW[0] <= date <= POST_WINDOW[1]:
        return "post-window"
    return "unclassified-era"


def cp_interval(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Exact two-sided Clopper-Pearson interval (HK-021(o): no bootstrap SE)."""
    if n == 0:
        return (float("nan"), float("nan"))
    alpha = 1.0 - conf
    lo = 0.0 if k == 0 else stats.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


# ---------------------------------------------------------------------------
# ROW 0a -- reproduction gate
# ---------------------------------------------------------------------------

def row0a(lines: list, dirs: list[Path]) -> tuple[bool, dict]:
    log(lines, "\n=== ROW 0a: reproduction gate (evaluated first) ===")
    log(lines, "Cannot detect: an error present identically in both the generator and the "
                "report (shared-code blind spot). ROW 0b is the independent check on the "
                "stimulus side.")
    fires = False
    facts: dict[str, dict] = {}
    for run_dir in dirs:
        report_path = run_dir / "report.md"
        report_text = report_path.read_text(encoding="utf-8", errors="replace") if report_path.is_file() else ""
        gate = parse_ratified_gate(report_text)
        if gate is None:
            continue  # not ratified-gate format -- ROW 0a has nothing to reproduce against
        try:
            part_map = load_s5_part_map(run_dir)
        except (OSError, ValueError):
            continue
        s5_cycles = set(part_map)
        n_total = len(s5_cycles)
        row_facts = {"n_total": n_total, "gate": gate, "part_map_size": len(part_map)}
        for appraiser, (k_reported, n_reported, verdict) in gate.items():
            events = scoped_fp_events(run_dir, appraiser, s5_cycles)
            recomputed = (len(events), n_total)
            ok = recomputed == (k_reported, n_reported)
            if not ok:
                fires = True
            log(lines, f"  {rel(run_dir):36s} {appraiser:8s} recomputed={recomputed} "
                        f"reported=({k_reported}, {n_reported}) {'OK' if ok else '*** MISMATCH -- STOP ***'}")
            row_facts[appraiser] = {"recomputed": recomputed, "reported": (k_reported, n_reported), "ok": ok}
        facts[rel(run_dir)] = row_facts
    log(lines, f"ROW 0a: {'FIRES -- STOP' if fires else 'does not fire'}")
    return fires, facts


# ---------------------------------------------------------------------------
# ROW 0b -- audio-condition equivalence
# ---------------------------------------------------------------------------

def row0b(lines: list) -> tuple[bool, list]:
    log(lines, "\n=== ROW 0b: audio-condition equivalence (THE LOAD-BEARING ROW) ===")
    s5_data = json.loads((SCENARIOS / "s5-noise.json").read_text(encoding="utf-8"))
    wide_data = json.loads((SCENARIOS / "s5-noise-wide.json").read_text(encoding="utf-8"))
    log(lines, f"  s5-noise.json id={s5_data['id']!r}  s5-noise-wide.json id={wide_data['id']!r}")
    if s5_data["id"] != wide_data["id"]:
        log(lines, "  NOTE: scenario ids differ -- compute_seed will NOT agree by construction; "
                    "a byte match, if any, would be a genuine coincidence, not a corollary.")
    else:
        log(lines, "  NOTE: both files declare id=='S5'. compute_seed(scenario_id, part_index, "
                    "trial_index) is keyed on this string, not the filename -- so the per-trial "
                    "seed is IDENTICAL for both files by construction. What this row actually "
                    "tests is whether the two files' part-0 CONFIGURATION (noise_type, and "
                    "whatever level_dbfs each declares or omits) renders to the same buffer "
                    "given that shared seed -- disclosed, not hidden.")
    part_s5 = next(p for p in s5_data["parts"] if p["part_index"] == 0)
    part_wide = next(p for p in wide_data["parts"] if p["part_index"] == 0)
    log(lines, f"  s5-noise.json part 0 config: {part_s5}")
    log(lines, f"  s5-noise-wide.json part 0 config: {part_wide}")

    pairs = []
    mismatches = 0
    for t in range(ROW0B_N_TRIALS):
        seed_a = compute_seed(s5_data["id"], 0, t)
        seed_b = compute_seed(wide_data["id"], 0, t)
        buf_a = _finalize_playback_samples(_render_noise(part_s5, seed_a))
        buf_b = _finalize_playback_samples(_render_noise(part_wide, seed_b))
        h_a = hashlib.sha256(buf_a.tobytes()).hexdigest()
        h_b = hashlib.sha256(buf_b.tobytes()).hexdigest()
        match = h_a == h_b
        if not match:
            mismatches += 1
        pairs.append(dict(trial=t, seed_a=seed_a, seed_b=seed_b, sha_s5=h_a, sha_wide=h_b, match=match))
        log(lines, f"  trial {t:2d}: seed={seed_a} sha_s5={h_a[:16]}... sha_wide={h_b[:16]}... "
                    f"{'MATCH' if match else '*** MISMATCH ***'}")

    fires = mismatches > 0
    log(lines, f"ROW 0b: {ROW0B_N_TRIALS - mismatches}/{ROW0B_N_TRIALS} trial pairs byte-identical. "
                f"{'FIRES -- July runs INADMISSIBLE' if fires else 'does not fire'}")
    return fires, pairs


# ---------------------------------------------------------------------------
# ROW 0c -- census completeness / admissibility classification
# ---------------------------------------------------------------------------

def classify_run(run_dir: Path) -> dict:
    report_path = run_dir / "report.md"
    report_text = report_path.read_text(encoding="utf-8", errors="replace") if report_path.is_file() else ""
    date = find_run_date(run_dir, report_text)
    gate = parse_ratified_gate(report_text) if report_text else None

    try:
        part_map = load_s5_part_map(run_dir)
    except (OSError, ValueError) as exc:
        return dict(run=rel(run_dir), date=date, admissible=False,
                    reasons=[f"load_s5_part_map failed: {exc}"])

    awgn_cycles = {c for c, p in part_map.items() if p in AWGN_PARTS}
    n_awgn = len(awgn_cycles)
    ids = None
    try:
        ids = scenario_ids_present(run_dir)
        context = "standalone" if set(ids) == {"S5"} else "battery"
    except (OSError, csv.Error):
        context = "unknown"

    reasons = []
    if date is None:
        reasons.append("no run date found (no report.md 'Run date' row, no dated dirname)")
    elif date < RANDR004_DATE:
        reasons.append(f"pre-R&R-004 ({date} < {RANDR004_DATE}) -- plain decode-rate metric, "
                        "not the ratified event-rate gate")
    if gate is None:
        reasons.append("report.md missing, or its S5 table is not the ratified 6-column format")
    if n_awgn < MIN_N_AWGN:
        reasons.append(f"AWGN slot count {n_awgn} < {MIN_N_AWGN} -- gate is INFO by construction "
                        "at this N")
    contamination_flag = (run_dir / "CONTAMINATED.md").is_file()
    if contamination_flag:
        reasons.append("run directory carries its own CONTAMINATED.md -- excluded on the "
                        "record's own say-so, not this script's judgement")
    incomplete_flag = (run_dir / "INCOMPLETE.md").is_file()
    if incomplete_flag:
        reasons.append("run directory carries its own INCOMPLETE.md")

    k_awgn = n_awgn_events = None
    if not reasons:
        events = scoped_fp_events(run_dir, "OpenWSFZ", awgn_cycles)
        k_awgn = len(events)
        events_ref = scoped_fp_events(run_dir, "WSJT-X", awgn_cycles)
        k_awgn_ref = len(events_ref)
    else:
        k_awgn_ref = None

    era = era_of(date) if date else None

    return dict(
        run=rel(run_dir), date=date, era=era, context=context,
        scenario_ids=dict(ids) if ids else {}, n_awgn=n_awgn,
        k_awgn_openwsfz=k_awgn, k_awgn_wsjtx=k_awgn_ref,
        admissible=not reasons, reasons=reasons,
    )


def row0c(lines: list) -> tuple[bool, list, list]:
    log(lines, "\n=== ROW 0c: census completeness (enumerated directly from disk, "
                "qa/rr-study/results/, never from ARTEFACT_INVENTORY.md or Section 6) ===")
    dirs = discover_s5_dirs()
    log(lines, f"  {len(dirs)} run directories under results/ carry a truth.csv with >=1 "
                f"scenario_id=='S5' row.")
    census = [classify_run(d) for d in dirs]
    admissible = [c for c in census if c["admissible"]]
    excluded = [c for c in census if not c["admissible"]]

    log(lines, f"\n  Admissible ({len(admissible)}):")
    for c in sorted(admissible, key=lambda c: c["date"] or ""):
        log(lines, f"    {c['run']:36s} date={c['date']} era={c['era']:12s} context={c['context']:10s} "
                    f"n_awgn={c['n_awgn']:3d} k_awgn(OpenWSFZ)={c['k_awgn_openwsfz']}")

    log(lines, f"\n  Excluded ({len(excluded)}):")
    for c in sorted(excluded, key=lambda c: c["date"] or ""):
        log(lines, f"    {c['run']:36s} date={c['date']}: {'; '.join(c['reasons'])}")

    fires = len(admissible) > 0  # see note below: 'fires' iff any admissible run was not
    # already accounted for in the pre-registered inventory. Evaluated by the caller against
    # the known table, since this function only produces the disk-side half of the check.
    return fires, admissible, excluded


# ---------------------------------------------------------------------------
# ROW 0d -- identifiability of battery context
# ---------------------------------------------------------------------------

def row0d(lines: list, admissible: list) -> tuple[bool, dict]:
    log(lines, "\n=== ROW 0d: identifiability of battery context "
                "(THE ROW THAT DECIDES WHAT MAY BE REPORTED) ===")
    eras = ["2026-07", "pre-window", "post-window"]
    contexts = ["standalone", "battery"]
    table: dict[tuple[str, str], list] = {(e, c): [] for e in eras for c in contexts}
    for run in admissible:
        key = (run["era"], run["context"])
        if key in table:
            table[key].append(run["run"])
        else:
            table.setdefault(key, []).append(run["run"])

    log(lines, "  era x context cross-tabulation (run count):")
    for e in eras:
        row = " | ".join(f"{c}={len(table.get((e, c), []))}" for c in contexts)
        log(lines, f"    {e:12s}: {row}")
        for c in contexts:
            names = table.get((e, c), [])
            if names:
                log(lines, f"      {e}/{c}: {names}")

    fires = False
    fired_cells = []
    for e in eras:
        populated = [c for c in contexts if table.get((e, c))]
        empty = [c for c in contexts if not table.get((e, c))]
        if populated and empty:
            fires = True
            fired_cells.append((e, populated, empty))

    if fires:
        log(lines, "  ROW 0d FIRES -- for at least one era, one context is fully unpopulated:")
        for e, populated, empty in fired_cells:
            log(lines, f"    era={e}: populated={populated} empty={empty}")
        log(lines, "  Consequence: ROW 1's cross-era contrast MUST NOT be reported as a "
                    "p-value or a ratio. Reporting as counts + exact CP intervals, labelled "
                    "'not identifiable -- context confounded with era'.")
    else:
        log(lines, "  ROW 0d does not fire -- every era has both contexts represented; "
                    "ROW 1 proceeds stratified by context, never pooled across it.")
    return fires, table


# ---------------------------------------------------------------------------
# ROW 1 -- pre-window vs shipped-configuration baseline
# ---------------------------------------------------------------------------

def row1(lines: list, admissible: list, row0d_fires: bool) -> dict:
    log(lines, "\n=== ROW 1: is the pre-window below the shipped-configuration baseline? ===")
    pre = [r for r in admissible if r["era"] == "pre-window"]
    july_standalone_shipped = [r for r in admissible
                                 if r["era"] == "2026-07" and r["context"] == "standalone"
                                 and r["run"] != "d011-fp-recheck-2026-07-04"]  # pre-f-002 excluded
    july_battery = [r for r in admissible if r["era"] == "2026-07" and r["context"] == "battery"]

    def totals(rs):
        k = sum(r["k_awgn_openwsfz"] for r in rs)
        n = sum(r["n_awgn"] for r in rs)
        return k, n

    k_pre, n_pre = totals(pre)
    k_jul, n_jul = totals(july_standalone_shipped)
    k_jb, n_jb = totals(july_battery)

    ci_pre = cp_interval(k_pre, n_pre)
    ci_jul = cp_interval(k_jul, n_jul)
    ci_jb = cp_interval(k_jb, n_jb) if n_jb else (float("nan"), float("nan"))

    log(lines, f"  Pre-window (battery context):        {k_pre}/{n_pre} = {100*k_pre/n_pre:.3f}%  "
                f"95% CP CI [{100*ci_pre[0]:.3f}%, {100*ci_pre[1]:.3f}%]  runs={[r['run'] for r in pre]}")
    log(lines, f"  July shipped-config (standalone):    {k_jul}/{n_jul} = {100*k_jul/n_jul:.3f}%  "
                f"95% CP CI [{100*ci_jul[0]:.3f}%, {100*ci_jul[1]:.3f}%]  runs={[r['run'] for r in july_standalone_shipped]}")
    if n_jb:
        log(lines, f"  July shipped-config (battery, informational only -- n=1 run, does not "
                    f"resolve the confound alone): {k_jb}/{n_jb} = {100*k_jb/n_jb:.3f}%  "
                    f"95% CP CI [{100*ci_jb[0]:.3f}%, {100*ci_jb[1]:.3f}%]  "
                    f"runs={[r['run'] for r in july_battery]}")

    result = dict(pre=(k_pre, n_pre, ci_pre), july_standalone=(k_jul, n_jul, ci_jul),
                  july_battery=(k_jb, n_jb, ci_jb) if n_jb else None)

    if row0d_fires:
        log(lines, "  ROW 0d FIRED: reporting as counts + exact CP intervals ONLY. "
                    "Label: 'not identifiable -- context confounded with era'.")
        log(lines, "  Position (HK-021(w)): the pre-window CI "
                    f"[{100*ci_pre[0]:.3f}%, {100*ci_pre[1]:.3f}%] and the July shipped-config CI "
                    f"[{100*ci_jul[0]:.3f}%, {100*ci_jul[1]:.3f}%] "
                    f"{'DO' if ci_pre[1] >= ci_jul[0] and ci_jul[1] >= ci_pre[0] else 'DO NOT'} overlap.")
        result["label"] = "not identifiable -- context confounded with era"
        result["fisher_p"] = None
    else:
        table = [[k_pre, n_pre - k_pre], [k_jul, n_jul - k_jul]]
        odds, p = stats.fisher_exact(table, alternative="less")
        log(lines, f"  ROW 0d did not fire: Fisher exact one-sided (pre-window LOWER) p={p:.4f}")
        result["fisher_p"] = float(p)
        result["label"] = None
    return result


# ---------------------------------------------------------------------------
# ROW 2 -- boundary-free trend
# ---------------------------------------------------------------------------

def row2(lines: list, admissible: list) -> dict:
    log(lines, "\n=== ROW 2: boundary-free trend (conditional permutation test, no change point) ===")
    pool = sorted(
        (r for r in admissible if r["context"] == "battery" and r["era"] in ("pre-window", "post-window")),
        key=lambda r: r["date"],
    )
    names = [r["run"] for r in pool]
    dates = [r["date"] for r in pool]
    ks = np.array([r["k_awgn_openwsfz"] for r in pool], dtype=np.int64)
    ns = np.array([r["n_awgn"] for r in pool], dtype=np.int64)
    ranks = np.arange(len(pool), dtype=np.float64)  # chronological rank, 0-indexed
    total_events = int(ks.sum())

    log(lines, f"  Population: {len(pool)} battery-context runs, pre-window+post-window eras: {names}")
    log(lines, f"  Per-run (date, N_awgn, k_awgn): "
                f"{list(zip(dates, ns.tolist(), ks.tolist()))}")
    log(lines, f"  Total events (condition on this): {total_events}")

    def observed_stat(ks_arr, ranks_arr):
        return float(np.dot(ks_arr, ranks_arr))

    def mc_pvalue(ns_arr, ranks_arr, total, obs_stat, seed):
        probs = ns_arr / ns_arr.sum()
        rng = np.random.default_rng(seed)
        draws = rng.multinomial(total, probs, size=ROW2_MC_DRAWS)
        stats_sim = draws @ ranks_arr
        p = float(np.mean(stats_sim >= obs_stat))
        return p

    obs = observed_stat(ks, ranks)
    p_full = mc_pvalue(ns, ranks, total_events, obs, ROW2_SEED)
    log(lines, f"  Observed statistic (sum of events * chronological rank): {obs:.1f}")
    log(lines, f"  Conditional permutation p (one-sided, later-than-expected), "
                f"N={ROW2_MC_DRAWS:,} draws, seed={ROW2_SEED}: p={p_full:.7f} "
                f"(MC quantum {1/ROW2_MC_DRAWS:.1e})")

    loo = []
    for i, name in enumerate(names):
        ks_i = np.delete(ks, i)
        ns_i = np.delete(ns, i)
        ranks_i = np.arange(len(ks_i), dtype=np.float64)  # re-rank remaining runs 0..n-2
        total_i = int(ks_i.sum())
        if total_i == 0 or len(ks_i) == 0:
            loo.append((name, None))
            continue
        obs_i = observed_stat(ks_i, ranks_i)
        p_i = mc_pvalue(ns_i, ranks_i, total_i, obs_i, ROW2_SEED + i + 1)
        loo.append((name, p_i))
        log(lines, f"    drop {name:24s} -> p={p_i:.4f}")

    any_loo_above_010 = any(p is not None and p > 0.10 for _, p in loo)
    fires = (p_full < 0.05) and (not any_loo_above_010)
    log(lines, f"ROW 2: {'FIRES' if fires else 'does not fire'} "
                f"(p_full<0.05: {p_full < 0.05}; any leave-one-out p>0.10: {any_loo_above_010})")
    if fires:
        log(lines, "  Consequence: the upward trend survives without a change point.")
    else:
        log(lines, "  Consequence: the trend is load-bearing on individual runs (named above). "
                    "This does NOT restore 'no regression' -- direction is unchanged (18:11Z).")

    return dict(population=names, dates=dates, n_awgn=ns.tolist(), k_awgn=ks.tolist(),
                total_events=total_events, observed_stat=obs, p_full=p_full,
                leave_one_out=loo, fires=fires, seed=ROW2_SEED, mc_draws=ROW2_MC_DRAWS)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

# The pre-registration's own §0.2(B) table -- the runs known BEFORE this script ran. Used only
# to state, mechanically, whether ROW 0c's disk census found anything beyond it (never used to
# filter the census itself -- the census is unconditional over disk).
KNOWN_BEFORE_THIS_TASK = {
    "d011-fp-recheck-2026-07-04",
    "2026-07-04-a3738fc-f002-s5-n300",
    "2026-08-05-3bd4cd0",
    "2026-08-15-8d6e1b1",
    "2026-08-21-7d36038",
    "2026-08-22-f5dec23",
    "2026-08-27-22b749c",
    "2026-08-29-872ba65",
    "2026-08-30-2e60949",
    "2026-09-02-3b52608",
    "2026-09-03-35378b9",
}


def main() -> int:
    lines: list = []
    log(lines, "S5-BASELINE -- reconstruct the S5 AWGN false-positive baseline")
    log(lines, "Spec: qa/rr-study/2026-09-04-1911-architect-to-qa-spec-s5-baseline-reconstruction.md")

    # ROW 0c is run before 0a so that 0a's population is the disk census, not a hand-typed list.
    _, admissible, excluded = row0c(lines)

    new_admissible = sorted(c["run"] for c in admissible if c["run"] not in KNOWN_BEFORE_THIS_TASK)
    row0c_fires = len(new_admissible) > 0
    log(lines, f"\nROW 0c (vs the pre-registration's own known table): "
                f"{'FIRES' if row0c_fires else 'does not fire'}")
    if row0c_fires:
        log(lines, f"  New admissible run(s) not in the pre-registration's table: {new_admissible}")
        log(lines, "  Consequence: NOT a stop. Added above; ROW 0d/ROW 1/ROW 2 run on the full set.")

    admissible_dirs = [RESULTS / c["run"] for c in admissible]
    row0a_fires, row0a_facts = row0a(lines, admissible_dirs)
    if row0a_fires:
        log(lines, "\nROW 0a FIRED. STOP. Nothing downstream may be cited.")
        _write_outputs(lines, dict(row0a_fires=True))
        return 1

    row0b_fires, row0b_pairs = row0b(lines)
    if row0b_fires:
        log(lines, "\nROW 0b FIRED. July runs (standalone, wide-family) are INADMISSIBLE; "
                    "§0.2(B) is withdrawn. Re-filtering admissible set to drop era=='2026-07'.")
        admissible = [c for c in admissible if c["era"] != "2026-07"]

    row0d_fires, cross_tab = row0d(lines, admissible)
    row1_result = row1(lines, admissible, row0d_fires)
    row2_result = row2(lines, admissible)

    log(lines, "\n=== SUMMARY (mechanical row outcomes only -- no adjudication; "
                "spec Section 6) ===")
    log(lines, f"  ROW 0a (reproduction):            {'FIRES' if row0a_fires else 'does not fire'}")
    log(lines, f"  ROW 0b (audio equivalence):       {'FIRES' if row0b_fires else 'does not fire'}")
    log(lines, f"  ROW 0c (census vs known table):   {'FIRES' if row0c_fires else 'does not fire'}"
                + (f" -- new: {new_admissible}" if row0c_fires else ""))
    log(lines, f"  ROW 0d (context x era confound):  {'FIRES' if row0d_fires else 'does not fire'}")
    row1_summary = row1_result.get("label") or f"Fisher p={row1_result.get('fisher_p')}"
    log(lines, f"  ROW 1 label:                      {row1_summary}")
    log(lines, f"  ROW 2 (boundary-free trend):      {'FIRES' if row2_result['fires'] else 'does not fire'} "
                f"(p={row2_result['p_full']:.4f})")

    log(lines, "\n=== HARD STOP per spec Section 6 -- pausing and handing back here (HK-030) ===")

    _write_outputs(lines, dict(
        row0a_fires=row0a_fires,
        row0b_fires=row0b_fires,
        row0b_pairs=row0b_pairs,
        row0c_fires=row0c_fires,
        row0c_new_admissible=new_admissible,
        row0c_admissible=[c["run"] for c in admissible],
        row0c_excluded={c["run"]: c["reasons"] for c in excluded},
        row0d_fires=row0d_fires,
        row1=row1_result,
        row2={k: v for k, v in row2_result.items()},
    ))
    return 0


def _write_outputs(lines: list, summary: dict) -> None:
    RESULTS_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    RESULT_JSON.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nWrote {RESULTS_TXT}")
    print(f"Wrote {RESULT_JSON}")


if __name__ == "__main__":
    sys.exit(main())
