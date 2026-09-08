"""Gage R&R analyser and report generator for the OpenWSFZ R&R study harness.

Usage:
    python harness/analyse.py --run-dir <dir> [--scenario S1,S2]

Reads all *_matched.csv files in the run directory (or the specified subset),
computes ANOVA-method Gage R&R variance components for continuous scenarios
(S1, S2, S3), Attribute Agreement Analysis for attribute scenarios (S4, S5),
writes six-panel charts and a report.md, and appends a row to trend.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Windows consoles default to cp1252 which cannot encode Unicode characters
# used in defect notices (≤, —, ❌).  Reconfigure stdout/stderr to UTF-8 so
# the process does not crash on the final summary print.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from scipy.stats import beta as _beta_dist
from scipy.stats import fisher_exact as _fisher_exact

# Matplotlib in non-interactive mode
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Resolve qa/rr-study as package root
_QA_ROOT = Path(__file__).resolve().parent.parent
if str(_QA_ROOT) not in sys.path:
    sys.path.insert(0, str(_QA_ROOT))

from harness.common import parse_all_txt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTINUOUS_SCENARIOS = {"S1", "S2", "S3"}
ATTRIBUTE_SCENARIOS = {"S4", "S5"}
# S3b / S1b are attribute decode-rate studies (not continuous Gage R&R).
DECODE_RATE_SCENARIOS = {"S3b", "S1b"}
# S11 (rr-linked-cycle-effectiveness-scenario, D1 path 1): Type 4 decode-rate
# sweep — reuses _analyse_decode_rate/_decode_rate_report_lines unchanged
# (see DECODE_RATE_CONFIG below), same as S3b/S1b. ("S10" is already reserved
# in STUDY-SPEC.md §17 for the deferred QSO Context-Awareness Study, hence S11.)
DECODE_RATE_SCENARIOS = DECODE_RATE_SCENARIOS | {"S11"}
# S9 (rr-linked-cycle-effectiveness-scenario, D1 path 2): linked-pair
# confirmatory resolution check. Not matched-CSV-driven like every other
# scenario here — its truth rows span two cycles (announce + reference), so
# _analyse_hashed_callsign_resolution reads truth.csv and the raw ALL.TXT
# logs directly instead of going through matcher.py's per-message model.
LINKED_PAIR_SCENARIOS = {"S9"}

DECODE_RATE_CONFIG: dict[str, dict] = {
    "S3b": {
        "part_var":      "true_dt_s",
        "part_label":    "True DT (s)",
        "section_title": "Negative-DT decode boundary",
        "section_intro": (
            "Decode rate (% of injected messages recovered) as DT sweeps from 0.0 s "
            "down to −2.7 s.  Companion to S3; separates 'does it decode?' from "
            "'does it report DT accurately?'.  Informational — no AIAG threshold."
        ),
        "chart_ref_line": 0.0,   # vertical line at DT = 0
    },
    "S1b": {
        "part_var":      "true_snr_db",
        "part_label":    "True SNR (dB)",
        "section_title": "Low-SNR threshold study",
        "section_intro": (
            "Decode rate (% of injected messages recovered) at SNRs excluded from the "
            "redesigned S1 ladder (−24 to −15 dB).  Companion to S1; separates "
            "'does it decode at this SNR?' from 'how accurately does it measure SNR?'.  "
            "Informational — no AIAG threshold."
        ),
        "chart_ref_line": None,  # no reference line on SNR axis
    },
    "S11": {
        "part_var":      "true_snr_db",
        "part_label":    "True SNR (dB)",
        "section_title": "Type 4 nonstandard-callsign decode-rate sweep",
        "section_intro": (
            "Decode rate (% of injected CQ <nonstandard callsign> announcements recovered) "
            "across an SNR sweep (rr-linked-cycle-effectiveness-scenario, design D1 path 1: "
            "'does a genuine Type 4 announcement decode reliably at realistic SNR?', modelled "
            "on the S1/S1b decode-rate methodology). Companion to S9, which answers the "
            "separate question of whether a decoded announcement then resolves correctly — "
            "kept apart per D1 so a low number here is never mistaken for a resolution-table "
            "defect. Informational — no AIAG threshold."
        ),
        "chart_ref_line": None,
    },
}

# Response variable per continuous scenario
RESPONSE_VAR = {
    "S1": "reported_snr_db",
    "S2": "reported_freq_hz",
    "S3": "reported_dt_s",
}

# Tolerance half-widths (STUDY-SPEC §10)
TOLERANCE_HALF = {
    "S1": 5.0,   # ±5 dB  (revised 2026-06-06, STUDY-SPEC §7)
    "S2": 4.0,   # ±4 Hz
    "S3": 0.2,   # ±0.2 s
}

REQUIRED_COLUMNS = {
    "scenario_id", "part_index", "trial_index", "seed", "appraiser", "message_text",
    "true_snr_db", "true_dt_s", "true_freq_hz",
    "reported_snr_db", "reported_dt_s", "reported_freq_hz",
    "matched", "false_positive", "cycle_utc",
}

# STUDY-SPEC §10 verdict thresholds
THRESH_GRR_PASS = 10.0      # %GR&R < 10% → PASS
THRESH_GRR_MARGINAL = 30.0  # %GR&R 10–30% → MARGINAL; > 30% → FAIL
NDC_FAIL = 2                 # ndc < 2 → FAIL
NDC_PASS = 5                 # ndc ≥ 5 → PASS
THRESH_KAPPA_PASS = 0.90
THRESH_KAPPA_MARGINAL = 0.70
THRESH_FP_UB95 = 6.0        # FP gate (STUDY-SPEC §10, ratified 2026-07-04, R&R-004):
                            # PASS iff the one-sided 95% Clopper–Pearson UPPER BOUND on
                            # the per-slot FP event rate is ≤ 6%.  Gates the true rate at
                            # 95% confidence, not the Poisson-noisy point estimate.
                            # Supersedes the retired interim zero-event gate (n_fp_events==0)
                            # and the legacy decode-rate threshold (kept only as reference).
FP_UB_CONF = 0.95           # one-sided confidence level for the CP upper bound
THRESH_BIAS_PASS = 2.0      # |bias| ≤ 2 dB → PASS; > 2 dB → FAIL

# S5-GATE-SIZING, Amendment 1 (PO ruling Option 3, 2026-09-06 20:29 UTC): S5's
# single gate is split into two, each scored on its OWN denominator and NEVER
# pooled into one rate, one denominator, or one verdict line -- pooling is the
# defect the amendment removes. CORRECTED 2026-09-08 (R&R-011 section 8 task 5):
# the same 180 slots scored as one gate FAIL 21% of the time under no change;
# scored as two, Gate A alone FAILs 77% of the time under no change. That 77%
# is Gate A's OWN FALSE-ALARM RATE at N=120, not "detects a problem" -- see
# STUDY-SPEC.md Sec.16 R&R-010 entry and the ruling this corrects.
S5_AWGN_PARTS = (0, 1)          # Gate A — regression tripwire, ratified 6% UB (unchanged)
S5_NARROWBAND_PARTS = (2, 3)    # Check B — coverage net, FAIL iff events >= THRESH_S5_NARROWBAND_FAIL
THRESH_S5_NARROWBAND_FAIL = 2   # derived in A1.2 from the measured all-history per-slot narrowband
                                # base rate (0.2347%, qa/rr-study/s5_narrowband_exposure_verify.py,
                                # 2026-09-06 ROW 0 clearance) -- well under A1.2's ~1% re-derivation
                                # trigger. NOT a Clopper-Pearson UB gate: the readout quantum IS the
                                # threshold (HK-021(o)), so MIN_N_FOR_FP_GATE's INFO demotion does
                                # not apply to this check.

# S5-GATE, R&R-011 (PO ruling Option A, 2026-09-08): supersedes R&R-010's
# per-sweep scoring of Gate A. Per-sweep Gate A (N=120, THRESH_FP_UB95) becomes
# INFO -- see `_verdict_fp` -- reported but never gating. In its place, TWO
# separate rows, never pooled into one S5 verdict (R&R-010's prohibition,
# carried forward): Gate A-W (compliance, trailing window) and Gate A-Delta
# (change, newest sweep vs the rest of the window). Spec:
# qa/rr-study/2026-09-08-1452-architect-to-qa-spec-rr-011-s5-trailing-window-gate.md
S5_WINDOW_SLOTS = 480      # fixed at ratification (spec Sec.4.4) -- NEVER re-tuned off a verdict
S5_WINDOW_ALPHA_CHANGE = 0.05  # Gate A-Delta one-sided Fisher significance level

# The trailing window's seed (spec Sec.2), fixed at ratification and NOT to be
# re-derived: the seven most recent runs contributing AWGN slots, NEWEST FIRST,
# each count taken from that run's own Section 10 gate line (never back-computed
# from a report's mixed Section 6 "S5 FP" column). Every entry reproduces
# against its committed report via fp_composition_per_part.py (ROW C1, 18/18).
S5_WINDOW_SEED: list[tuple[str, int, int]] = [
    ("4cc1984", 3, 120),
    ("4c7d5ad", 3, 60),
    ("35378b9", 2, 60),
    ("3b52608", 4, 60),
    ("2e60949", 2, 60),
    ("872ba65", 1, 60),
    ("22b749c", 0, 60),
]
# Section 5's worked example is the reproduction test for the whole design --
# assert the inherited seed totals in code rather than trust the prose (HK rule:
# inherited constants belong in the code as assertions, not as reminders).
assert sum(sl for _, _, sl in S5_WINDOW_SEED) == 480, "S5_WINDOW_SEED slot total drifted"
assert sum(ev for _, ev, _ in S5_WINDOW_SEED) == 15, "S5_WINDOW_SEED event total drifted"

# Decodable-SNR floor for the informational restricted-population attribute-Kappa
# variant (rr-density-qrm-scenario / R&R-007).  Established by R&R-005 for the
# redesigned S1 ladder as "the reliable decode floor for both apps"; reused here to
# separate agreement-on-decodable-signals from agreement-including-signals-below-the-
# decode-capability-boundary.  Informational only — does NOT feed the §10 gate or the
# overall verdict (see _collect_verdicts, which is never passed this variant).
S4_DECODABLE_SNR_FLOOR_DB: float = -12.0

APPRAISERS = ("WSJT-X", "OpenWSFZ")

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def _verdict_grr(pct: float) -> str:
    if pct < THRESH_GRR_PASS:
        return "PASS"
    if pct <= THRESH_GRR_MARGINAL:
        return "MARGINAL"
    return "FAIL"


def _verdict_ndc(ndc: int) -> str:
    if ndc >= NDC_PASS:
        return "PASS"
    if ndc >= NDC_FAIL:
        return "MARGINAL"
    return "FAIL"


def _verdict_kappa(kappa: float) -> str:
    if kappa >= THRESH_KAPPA_PASS:
        return "PASS"
    if kappa >= THRESH_KAPPA_MARGINAL:
        return "MARGINAL"
    return "FAIL"


def _cp_upper_95(k: int, n: int, conf: float = FP_UB_CONF) -> float:
    """One-sided upper Clopper–Pearson confidence bound on a binomial proportion.

    Returns the upper bound (as a fraction 0–1) on p given *k* successes in *n*
    trials at confidence *conf*.  Collapses to the rule-of-three (≈ 3/n) at k=0
    and to 1.0 at k=n.  This is the statistically honest FP gate quantity: it
    bounds the *true* per-slot FP probability rather than reacting to the
    Poisson-noisy point estimate at the study's small N.
    """
    if n <= 0:
        return float("nan")
    if k >= n:
        return 1.0
    return float(_beta_dist.ppf(conf, k + 1, n - k))


def _min_n_for_fp_gate(threshold_pct: float = THRESH_FP_UB95,
                        conf: float = FP_UB_CONF,
                        max_n: int = 100_000) -> int:
    """Smallest slot count at which a *clean* run (zero observed FP events) can
    still clear the §10 gate.

    Below this N, ``_cp_upper_95(0, n)`` exceeds ``threshold_pct`` no matter how
    clean the decoder actually is — the gate is not merely strict, it is
    *unevaluable*: no observed outcome at that N can produce a PASS. Routine
    runs below this size are reported informationally (see `_verdict_fp`)
    rather than gated, so a small default trial count never manufactures a
    FAIL that reflects sample size rather than decoder behaviour.
    """
    threshold = threshold_pct / 100.0
    n = 1
    while n <= max_n:
        if _cp_upper_95(0, n, conf) <= threshold:
            return n
        n += 1
    return max_n  # pragma: no cover — would require an implausibly tight threshold


MIN_N_FOR_FP_GATE = _min_n_for_fp_gate()


def _verdict_fp(fp_info: dict) -> str:
    """Per-sweep Gate A (S5 AWGN, N=120) — SUPERSEDED as a gate by R&R-011.

    Unconditionally "INFO": R&R-011 (PO ruling Option A, 2026-09-08) took this
    row out of the gating path entirely because at N=120 it cannot separate
    "unchanged" (P(FAIL)=0.739 at the established 3.182% rate) from "twice as
    bad" (P(FAIL)=0.984) -- see the ruling
    `2026-09-08-1429-architect-to-qa-ruling-s5-gate-a-first-point-and-gate-form.md`
    Sec.3-4. It still runs every sweep and still feeds the trailing window (see
    `_verdict_s5_window`/`S5_WINDOW_SEED`), which is the ratified compliance
    gate now. Never resurrect a PASS/FAIL verdict from this row without a new
    pre-registration (spec Sec.4.4 prohibition).

    `MIN_N_FOR_FP_GATE`/`THRESH_FP_UB95` are retained only as the still-current
    definitions of the underlying per-slot CP-upper-bound quantity this row
    reports (and which Gate A-W now gates on at N=480), not as a threshold this
    function evaluates any more.
    """
    return "INFO"


def _verdict_s5_narrowband(fp_info: dict) -> str:
    """Check B (S5-GATE-SIZING Amendment 1, PO ruling Option 3, 2026-09-06):
    FAIL iff the narrowband (S5 parts 2/3) FP event count on its OWN 60-slot
    denominator is >= THRESH_S5_NARROWBAND_FAIL. Never pooled with Gate A's
    AWGN slots -- that pooling is exactly the defect Amendment 1 removes.

    Not a Clopper-Pearson UB gate like `_verdict_fp`: A1.2 derives the
    threshold directly on the readout quantum (whole events), so there is no
    small-N STATISTICAL "unevaluable" regime analogous to `MIN_N_FOR_FP_GATE`
    here -- a clean run (0 or 1 events) genuinely PASSes at any N this
    scenario actually runs.

    There IS a separate, non-statistical regime: zero narrowband slots
    injected at all (`n_slots == 0`), meaning Check B did not run this
    battery -- e.g. a targeted --parts 0,1 recheck, or a future battery
    override reintroducing R&R-009's restriction. Asserting PASS there would
    reproduce EXACTLY the coverage blindness Amendment 1 exists to remove
    (Section 1.2 / HK-026: a control that never ran is not the same as a
    control that ran clean, and nothing would announce the difference).
    INFO -- mirroring `_verdict_fp`'s actual convention, not the inverse of
    it -- excluded from the overall verdict, raw counts still reported.
    Caught in PR #144 review before merge; a zero-slot Check B input must
    never read PASS (see the regression tests pinning this).
    """
    n_slots = fp_info.get("n_slots", 0)
    if not n_slots:
        return "INFO"
    n_events = fp_info.get("n_fp_events", float("nan"))
    if isinstance(n_events, float) and math.isnan(n_events):
        return "INFO"  # defensive -- should be unreachable once n_slots > 0
    return "FAIL" if n_events >= THRESH_S5_NARROWBAND_FAIL else "PASS"


def _verdict_s5_window(window: list[tuple[str, int, int]]) -> tuple[str, int, int, list]:
    """Gate A-W (R&R-011 Sec.3): compliance on the trailing S5_WINDOW_SLOTS AWGN
    slots -- the ratified 6% UB, unchanged, evaluated at a sample size that can
    actually discriminate (spec Sec.4).

    ``window`` is [(sha, events, slots), ...], NEWEST FIRST -- the current
    sweep's own AWGN reading MUST be window[0] (see `_s5_window_history`).
    Accumulates newest-first until S5_WINDOW_SLOTS is reached; if the window
    is exhausted first, returns "INFO" (ROW 0c -- not a PASS: "no outcome at
    this N" is not the same claim as "a properly powered outcome"; contrast
    `_verdict_fp`, whose superseded INFO now means something else).

    Returns (verdict, k, n, used) where ``used`` is the (possibly truncated)
    newest-first sub-list actually inside the compliance window -- pass this
    same list to `_verdict_s5_change`/`_s5_window_loo` so all three questions
    are asked of the identical population (spec Sec.4.7).
    """
    used: list[tuple[str, int, int]] = []
    k = n = 0
    for sha, ev, sl in window:
        if n >= S5_WINDOW_SLOTS:
            break
        used.append((sha, ev, sl))
        k += ev
        n += sl
    if n < S5_WINDOW_SLOTS:
        return "INFO", k, n, used
    ub = _cp_upper_95(k, n) * 100.0
    return ("PASS" if ub <= THRESH_FP_UB95 else "FAIL"), k, n, used


def _verdict_s5_change(used: list[tuple[str, int, int]]) -> tuple[str, float, tuple, tuple]:
    """Gate A-Delta (R&R-011 Sec.3): is the newest sweep significantly WORSE
    than the rest of the (already-windowed) population? One-sided Fisher,
    alpha=S5_WINDOW_ALPHA_CHANGE. This is what covers the trailing window's
    own lag (spec Sec.4.7) -- blind below ~2x by construction, never read a
    PASS here as "nothing moved".

    ``used`` MUST be `_verdict_s5_window`'s own returned ``used`` list (newest
    first) so Gate A-W and Gate A-Delta are never asking about two different
    populations. Returns (verdict, p, (k1, n1), (k0, n0)) -- newest sweep vs
    the rest of the window. A window of a single sweep (nothing to compare
    against) returns "INFO", not PASS -- there is no "rest" to test against.
    """
    if len(used) < 2:
        return "INFO", float("nan"), (None, None), (None, None)
    _, k1, n1 = used[0]
    k0 = sum(ev for _, ev, _ in used[1:])
    n0 = sum(sl for _, _, sl in used[1:])
    _, p = _fisher_exact([[k1, n1 - k1], [k0, n0 - k0]], alternative="greater")
    verdict = "FAIL" if p <= S5_WINDOW_ALPHA_CHANGE else "PASS"
    return verdict, float(p), (k1, n1), (k0, n0)


def _s5_window_loo(used: list[tuple[str, int, int]]) -> tuple[bool, list[dict]]:
    """R&R-011 Sec.4.7: leave-one-sweep-out on Gate A-W's verdict, over the
    same windowed population `_verdict_s5_window` returned as ``used``.
    FRAGILE iff removing any single contributing sweep flips PASS<->FAIL --
    the stated maximum for the cross-build confound (up to seven builds in one
    window). A FRAGILE verdict must be reported alongside its value and never
    stand alone as evidence about any one build (spec Sec.4.7, sibling (p)).
    """
    if not used:
        return False, []
    base_k = sum(ev for _, ev, _ in used)
    base_n = sum(sl for _, _, sl in used)
    base_ub = _cp_upper_95(base_k, base_n) * 100.0
    base_verdict = "PASS" if base_ub <= THRESH_FP_UB95 else "FAIL"
    deletions: list[dict] = []
    fragile = False
    for sha, ev, sl in used:
        k, n = base_k - ev, base_n - sl
        if n <= 0:
            continue  # deleting the only sweep leaves nothing to gate
        ub = _cp_upper_95(k, n) * 100.0
        v = "PASS" if ub <= THRESH_FP_UB95 else "FAIL"
        deletions.append({"sha": sha, "verdict": v, "ub": ub, "k": k, "n": n})
        fragile = fragile or (v != base_verdict)
    return fragile, deletions


def _verdict_bias(bias: float) -> str:
    return "PASS" if abs(bias) <= THRESH_BIAS_PASS else "FAIL"


# ---------------------------------------------------------------------------
# S3 — WSJT-X DT convention correction
# ---------------------------------------------------------------------------

def _apply_wsjt_dt_correction(df: pd.DataFrame, correction_s: float) -> pd.DataFrame:
    """Add *correction_s* to WSJT-X reported_dt_s in an S3 matched DataFrame.

    WSJT-X defines DT relative to the nominal FT8 TX start (≈ 0.5–1.0 s into
    the 15 s slot) rather than the UTC slot boundary used as the harness truth
    convention (DT = 0 ↔ signal starts exactly at the slot boundary).  This
    produces a systematic ≈ −0.55 s offset in all WSJT-X DT reports and
    dominates the SS_appraiser term in the ANOVA, inflating %GR&R.

    Adding the measured offset removes the calibration artefact so the Gage
    R&R Reproducibility term captures genuine app-to-app measurement
    disagreement on the same signal, not a convention mismatch.

    The correction value is read from the scenario JSON field
    ``wsjt_dt_correction_s`` (positive = add to WSJT-X DT).  Raw reported_dt_s
    values in the matched CSV are never altered; correction is applied only to
    the analysis copy.
    """
    df = df.copy()
    mask = df["appraiser"] == "WSJT-X"
    df.loc[mask, "reported_dt_s"] = df.loc[mask, "reported_dt_s"] + correction_s
    return df


# ---------------------------------------------------------------------------
# Task 4.1 — Matched CSV loading
# ---------------------------------------------------------------------------

def _load_scenario_meta(scenarios_dir: Path) -> dict[str, dict]:
    """Return {scenario_id: metadata} from all scenarios/*.json files."""
    meta = {}
    for p in sorted(scenarios_dir.glob("*.json")):
        if p.stem == "study-messages":
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if "id" in d:
                meta[d["id"]] = d
        except (json.JSONDecodeError, KeyError):
            pass
    return meta


def _load_matched_csvs(run_dir: Path, scenario_filter: list[str] | None,
                       scenarios_dir: Path) -> dict[str, pd.DataFrame]:
    """Discover and load all *_matched.csv files in run_dir.

    Returns {scenario_id: DataFrame}.
    """
    found: dict[str, pd.DataFrame] = {}
    for p in sorted(run_dir.glob("*_matched.csv")):
        scen_id = p.stem.replace("_matched", "")
        if scenario_filter and scen_id not in scenario_filter:
            continue
        try:
            df = pd.read_csv(p, dtype=str)
        except Exception as exc:
            sys.exit(f"ERROR: cannot read {p.name}: {exc}")
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            sys.exit(
                f"ERROR: {p.name} missing required column: {', '.join(sorted(missing))}"
            )
        # Parse numeric columns (NaN for empty/missing)
        for col in ("part_index", "trial_index"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in ("reported_snr_db", "reported_dt_s", "reported_freq_hz",
                    "true_snr_db", "true_dt_s", "true_freq_hz"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["matched"] = df["matched"].map({"True": True, "False": False, True: True, False: False})
        df["false_positive"] = df["false_positive"].map(
            {"True": True, "False": False, True: True, False: False}
        )
        found[scen_id] = df
    return found


# ---------------------------------------------------------------------------
# Task 4.2 — Two-way crossed ANOVA (Part × Appraiser)
# ---------------------------------------------------------------------------

def _two_way_anova(df_matched: pd.DataFrame, response: str,
                   scenario_id: str) -> dict | None:
    """Compute AIAG MSA 4th ed. two-way crossed ANOVA variance components.

    Returns a dict of components, or None if insufficient data.
    """
    df = df_matched[df_matched["matched"] == True].copy()
    df[response] = pd.to_numeric(df[response], errors="coerce")
    df = df.dropna(subset=[response, "part_index", "trial_index", "appraiser"])

    parts = df["part_index"].unique()
    appraisers = df["appraiser"].unique()
    n_parts = len(parts)
    n_appraisers = len(appraisers)
    # n_trials per cell
    cell_counts = df.groupby(["part_index", "appraiser"])[response].count()
    if cell_counts.min() < 2:
        print(
            f"WARNING: {scenario_id} — insufficient matched data for Gage R&R; skipping.",
            file=sys.stderr,
        )
        return None
    n_trials = int(cell_counts.min())  # use minimum trials per cell

    grand_mean = df[response].mean()
    n_total = len(df)

    # Cell means
    cell_means = df.groupby(["part_index", "appraiser"])[response].mean()
    part_means = df.groupby("part_index")[response].mean()
    appraiser_means = df.groupby("appraiser")[response].mean()

    # SS decomposition
    # SS_Total
    SS_total = float(((df[response] - grand_mean) ** 2).sum())

    # SS_Part
    SS_part = float(n_appraisers * n_trials * sum(
        (part_means[p] - grand_mean) ** 2 for p in parts
    ))

    # SS_Appraiser
    SS_appraiser = float(n_parts * n_trials * sum(
        (appraiser_means[a] - grand_mean) ** 2 for a in appraisers
    ))

    # SS_Interaction (Part × Appraiser)
    SS_cells = float(n_trials * sum(
        (cell_means.get((p, a), grand_mean) - part_means[p] - appraiser_means[a] + grand_mean) ** 2
        for p in parts for a in appraisers
    ))
    SS_interaction = SS_cells

    # SS_Error (within-cell residual)
    SS_error = SS_total - SS_part - SS_appraiser - SS_interaction

    # Degrees of freedom
    df_part = n_parts - 1
    df_appraiser = n_appraisers - 1
    df_interaction = df_part * df_appraiser
    df_error = n_parts * n_appraisers * (n_trials - 1)

    # Mean squares (guard against zero df)
    MS_part = SS_part / df_part if df_part > 0 else 0.0
    MS_appraiser = SS_appraiser / df_appraiser if df_appraiser > 0 else 0.0
    MS_interaction = SS_interaction / df_interaction if df_interaction > 0 else 0.0
    MS_error = SS_error / df_error if df_error > 0 else 0.0

    # Variance components (AIAG MSA 4th ed.)
    var_repeatability = max(0.0, MS_error)
    var_reproducibility_no_interact = max(
        0.0, (MS_appraiser - MS_interaction) / (n_parts * n_trials)
    )
    var_interaction = max(0.0, (MS_interaction - MS_error) / n_trials)
    # Reproducibility includes interaction
    var_reproducibility = var_reproducibility_no_interact + var_interaction
    var_part = max(0.0, (MS_part - MS_interaction) / (n_appraisers * n_trials))
    var_grr = var_repeatability + var_reproducibility
    var_total = var_grr + var_part

    return {
        "n_parts": n_parts,
        "n_appraisers": n_appraisers,
        "n_trials": n_trials,
        "SS_part": SS_part,
        "SS_appraiser": SS_appraiser,
        "SS_interaction": SS_interaction,
        "SS_error": SS_error,
        "MS_part": MS_part,
        "MS_appraiser": MS_appraiser,
        "MS_interaction": MS_interaction,
        "MS_error": MS_error,
        "var_repeatability": var_repeatability,
        "var_reproducibility": var_reproducibility,
        "var_interaction": var_interaction,
        "var_part": var_part,
        "var_grr": var_grr,
        "var_total": var_total,
    }


# ---------------------------------------------------------------------------
# Task 4.3 — Derived metrics
# ---------------------------------------------------------------------------

def _derived_metrics(anova: dict, tol_half: float) -> dict:
    vt = anova["var_total"]
    vgrr = anova["var_grr"]
    vrep = anova["var_repeatability"]
    vreprod = anova["var_reproducibility"]
    vp = anova["var_part"]

    def pct_contribution(v: float) -> float:
        return 100.0 * v / vt if vt > 0 else 0.0

    sigma_total = math.sqrt(vt) if vt > 0 else 0.0
    sigma_grr = math.sqrt(vgrr) if vgrr > 0 else 0.0
    sigma_part = math.sqrt(vp) if vp > 0 else 0.0

    def pct_study_var(v: float) -> float:
        return 100.0 * math.sqrt(v) / sigma_total if sigma_total > 0 else 0.0

    pct_tol = (6.0 * sigma_grr / (2.0 * tol_half) * 100.0) if tol_half > 0 else float("nan")
    ndc = max(1, math.floor(1.41 * sigma_part / sigma_grr)) if sigma_grr > 0 else 1

    return {
        "pct_contribution_repeat": pct_contribution(vrep),
        "pct_contribution_reprod": pct_contribution(vreprod),
        "pct_contribution_part": pct_contribution(vp),
        "pct_contribution_grr": pct_contribution(vgrr),
        "pct_study_var_repeat": pct_study_var(vrep),
        "pct_study_var_reprod": pct_study_var(vreprod),
        "pct_study_var_part": pct_study_var(vp),
        "pct_study_var_grr": pct_study_var(vgrr),
        "pct_tolerance": pct_tol,
        "ndc": ndc,
        "sigma_grr": sigma_grr,
        "sigma_part": sigma_part,
        "sigma_total": sigma_total,
    }


# ---------------------------------------------------------------------------
# Task 4.4 — Six-panel Gage R&R figure
# ---------------------------------------------------------------------------

def _plot_grr_panel(df_matched: pd.DataFrame, response: str,
                    anova: dict, metrics: dict,
                    scenario_id: str, run_dir: Path) -> Path:
    df = df_matched[df_matched["matched"] == True].copy()
    df[response] = pd.to_numeric(df[response], errors="coerce")
    df = df.dropna(subset=[response, "part_index", "appraiser"])
    df["part_index"] = df["part_index"].astype(int)

    fig, axes = plt.subplots(2, 3, figsize=(12, 10))
    fig.suptitle(f"{scenario_id} — Gage R&R Panel ({response})", fontsize=13)

    # 1. Components of Variation
    ax = axes[0, 0]
    components = ["Repeatability", "Reproducibility", "Part-to-Part", "GR&R"]
    pct_contrib = [
        metrics["pct_contribution_repeat"],
        metrics["pct_contribution_reprod"],
        metrics["pct_contribution_part"],
        metrics["pct_contribution_grr"],
    ]
    colors = ["steelblue", "orange", "green", "red"]
    ax.barh(components, pct_contrib, color=colors)
    ax.set_xlabel("% Contribution")
    ax.set_title("Components of Variation")
    ax.axvline(10, color="green", linestyle="--", lw=0.8, label="10%")
    ax.axvline(30, color="red", linestyle="--", lw=0.8, label="30%")
    ax.legend(fontsize=7)

    # 2. R-chart by Appraiser
    ax = axes[0, 1]
    for appr in sorted(df["appraiser"].unique()):
        sub = df[df["appraiser"] == appr]
        ranges = sub.groupby("part_index")[response].apply(lambda x: x.max() - x.min())
        ax.plot(ranges.index, ranges.values, marker="o", label=appr)
    # UCL ≈ D4 × R-bar (for n_trials=3, D4=2.575)
    if len(df) > 0:
        n_t = anova.get("n_trials", 3)
        D4 = {2: 3.267, 3: 2.575, 4: 2.282, 5: 2.115}.get(n_t, 2.575)
        all_ranges = df.groupby(["appraiser", "part_index"])[response].apply(
            lambda x: x.max() - x.min()
        )
        r_bar = all_ranges.mean()
        ucl = D4 * r_bar
        ax.axhline(ucl, color="red", linestyle="--", lw=0.8, label=f"UCL={ucl:.2f}")
    ax.set_title("R-chart by Appraiser")
    ax.set_xlabel("Part")
    ax.set_ylabel("Range")
    ax.legend(fontsize=7)

    # 3. Xbar-chart by Appraiser
    ax = axes[0, 2]
    grand_mean = df[response].mean()
    for appr in sorted(df["appraiser"].unique()):
        sub = df[df["appraiser"] == appr]
        means = sub.groupby("part_index")[response].mean()
        ax.plot(means.index, means.values, marker="s", label=appr)
    ax.axhline(grand_mean, color="black", linestyle="--", lw=0.8, label="Grand mean")
    ax.set_title("Xbar-chart by Appraiser")
    ax.set_xlabel("Part")
    ax.set_ylabel("Mean")
    ax.legend(fontsize=7)

    # 4. Measurement by Part
    ax = axes[1, 0]
    parts = sorted(df["part_index"].unique())
    data_by_part = [df[df["part_index"] == p][response].dropna().values for p in parts]
    ax.boxplot(data_by_part, positions=parts, widths=0.6)
    ax.set_title("Measurement by Part")
    ax.set_xlabel("Part")
    ax.set_ylabel(response)

    # 5. Measurement by Appraiser
    ax = axes[1, 1]
    appraisers = sorted(df["appraiser"].unique())
    data_by_app = [df[df["appraiser"] == a][response].dropna().values for a in appraisers]
    ax.boxplot(data_by_app, tick_labels=appraisers)
    ax.set_title("Measurement by Appraiser")
    ax.set_ylabel(response)

    # 6. Appraiser × Part Interaction
    ax = axes[1, 2]
    for appr in sorted(df["appraiser"].unique()):
        sub = df[df["appraiser"] == appr]
        means = sub.groupby("part_index")[response].mean()
        ax.plot(means.index, means.values, marker="^", label=appr)
    ax.set_title("Appraiser × Part Interaction")
    ax.set_xlabel("Part")
    ax.set_ylabel(f"Mean {response}")
    ax.legend(fontsize=7)

    plt.tight_layout()
    out_path = run_dir / f"{scenario_id}_grr_panel.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Task 4.5 — S1 Bias & Linearity
# ---------------------------------------------------------------------------

def _bias_linearity(df_matched: pd.DataFrame, run_dir: Path) -> dict:
    df = df_matched[df_matched["matched"] == True].copy()
    df["reported_snr_db"] = pd.to_numeric(df["reported_snr_db"], errors="coerce")
    df["true_snr_db"] = pd.to_numeric(df["true_snr_db"], errors="coerce")
    df = df.dropna(subset=["reported_snr_db", "true_snr_db"])
    df["bias"] = df["reported_snr_db"] - df["true_snr_db"]

    results: dict[str, dict] = {}

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(0, color="black", linestyle="--", lw=0.8)

    for appr in APPRAISERS:
        sub = df[df["appraiser"] == appr]
        if sub.empty:
            continue
        x = sub["true_snr_db"].values
        y = sub["bias"].values
        mean_bias = float(np.mean(y))
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = float(coeffs[0]), float(coeffs[1])
        y_pred = np.polyval(coeffs, x)
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        results[appr] = {
            "mean_bias": mean_bias,
            "slope": slope,
            "intercept": intercept,
            "r2": r2,
        }

        x_line = np.linspace(x.min(), x.max(), 50)
        ax.scatter(x, y, label=f"{appr} (bias)", alpha=0.6, s=20)
        ax.plot(x_line, np.polyval(coeffs, x_line),
                label=f"{appr} fit (slope={slope:.3f})")

    ax.set_xlabel("True SNR (dB)")
    ax.set_ylabel("Bias = Reported − True (dB)")
    ax.set_title("S1 Bias & Linearity")
    ax.legend(fontsize=8)
    plt.tight_layout()
    out_path = run_dir / "S1_bias_linearity.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    return results


# ---------------------------------------------------------------------------
# Task 4.7b — S5 Gate A trailing-window gate (R&R-011)
# ---------------------------------------------------------------------------
# Orchestrates the ROW 0 preconditions (spec Sec.3) around `_verdict_s5_window`
# / `_verdict_s5_change` / `_s5_window_loo` above, and persists the window via
# trend.csv's `fp_events_s5`/`fp_slots_s5` columns (Sec.8 task 2: "seed it from
# Sec.2 and let the window be DERIVED from it rather than hand-maintained").

_TREND_S5_EVENTS_COL = "fp_events_s5"
_TREND_S5_SLOTS_COL = "fp_slots_s5"


def _s5_row0a_void(attr_results: dict | None) -> tuple[bool, str]:
    """ROW 0a (spec Sec.3, sibling (n)): the positive control. S5 slots are
    signal-free, so S5 has no true positives of its own -- a dead audio chain
    yields 0 events and Gate A-W PASSES vacuously. The control has to sit
    outside S5: S4 OpenWSFZ recall (TP/(TP+FN)) == 0 in the SAME session VOIDs
    the S5 reading. A session that never ran S4 at all provides no positive
    control either and is treated the same way -- a control that never ran is
    not the same as a control that ran clean (HK-026), and this row must not
    silently read as "does not fire" when it was simply never evaluated.

    Returns (fires, detail).
    """
    if not attr_results:
        return True, "S4 did not run this session -- no positive control available"
    confusion = attr_results.get("confusion", {}).get("OpenWSFZ")
    if not confusion:
        return True, "S4/OpenWSFZ confusion counts unavailable -- no positive control"
    tp, fn = confusion.get("TP", 0), confusion.get("FN", 0)
    if (tp + fn) == 0:
        return True, "S4 injected zero messages this session -- no positive control"
    if tp == 0:
        return True, f"S4 OpenWSFZ recall == 0 ({tp}/{tp + fn}) -- dead audio chain"
    return False, f"S4 OpenWSFZ recall {tp}/{tp + fn} > 0"


def _s5_row0b_scoping_ok(s5_df: pd.DataFrame, fp_info: dict) -> tuple[bool, int, int]:
    """ROW 0b (spec Sec.3): re-derive the scoped AWGN FP event count
    independently of `_fp_rate_for_parts`'s cached figure, straight from
    ``s5_df``, and confirm it matches. Guards against a future code path
    changing `_fp_rate_for_parts`'s scoping without this gate noticing --
    HK-026: an instrument cannot certify its own blind spot by re-running the
    exact same code path that produced the number in the first place.

    Returns (ok, unscoped_n_events, scoped_n_events) for OpenWSFZ.
    """
    part_map = _s5_cycle_part_map(s5_df)
    awgn_cycles = {c for c, p in part_map.items() if p in S5_AWGN_PARTS}
    sub = s5_df[s5_df["appraiser"] == "OpenWSFZ"]
    fp_sub = sub[sub["false_positive"] == True]
    unscoped_n = int(fp_sub["cycle_utc"].nunique())
    scoped_n = int(fp_sub[fp_sub["cycle_utc"].isin(awgn_cycles)]["cycle_utc"].nunique())
    ok = scoped_n == fp_info.get("n_fp_events", -1)
    return ok, unscoped_n, scoped_n


def _s5_window_history(qa_rr_root: Path) -> list[tuple[str, int, int]]:
    """Everything the window has learned SINCE the R&R-011 seed, newest first,
    read from trend.csv's `fp_events_s5`/`fp_slots_s5` columns. Rows whose SHA
    already appears in S5_WINDOW_SEED are skipped (the seed already covers
    them at its own, separately-reconciled counts -- see the spec Sec.2 note
    that these do NOT always match an era's raw trend.csv figure, e.g. a
    resumed session's part-scoping anomaly; the seed is the reconciled truth
    and is never re-derived from trend.csv).
    """
    trend_path = qa_rr_root / "trend.csv"
    if not trend_path.exists():
        return []
    seed_shas = {sha for sha, _, _ in S5_WINDOW_SEED}
    rows: list[tuple[str, int, int]] = []
    with open(trend_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            sha = (row.get("git_sha") or "")[:7]
            ev_s = row.get(_TREND_S5_EVENTS_COL, "")
            sl_s = row.get(_TREND_S5_SLOTS_COL, "")
            if not sha or not ev_s or not sl_s or sha in seed_shas:
                continue
            try:
                rows.append((sha, int(float(ev_s)), int(float(sl_s))))
            except ValueError:
                continue
    rows.reverse()  # trend.csv is chronological (oldest first) -> newest first
    return rows


def _s5_window_gate(
    qa_rr_root: Path,
    git_sha: str,
    fp_results: dict[str, dict],
    attr_results: dict | None,
    s5_df: pd.DataFrame,
) -> dict:
    """Full R&R-011 orchestration for one sweep. ROW 0 first, in strict order;
    if any ROW 0 fires, neither Gate A-W nor Gate A-Delta is evaluated and no
    S5 window verdict of any kind is reported (spec Sec.3) -- callers must
    check ``status`` before reading ``window``/``change``/``loo``.
    """
    info = fp_results.get("OpenWSFZ")
    if not info or (isinstance(info.get("n_fp_events"), float) and math.isnan(info["n_fp_events"])):
        return {"status": "NOT_RUN"}

    void0a, detail0a = _s5_row0a_void(attr_results)
    if void0a:
        return {"status": "VOID", "row": "0a", "detail": detail0a}

    ok0b, unscoped_n, scoped_n = _s5_row0b_scoping_ok(s5_df, info)
    if not ok0b:
        return {
            "status": "VOID", "row": "0b",
            "detail": f"unscoped OpenWSFZ FP events {unscoped_n}, scoped (parts 0/1) "
                      f"{scoped_n}, but Gate A's own count is {info.get('n_fp_events')} -- "
                      f"scoping mismatch, do not trust this reading",
        }

    today = (git_sha[:7], int(info["n_fp_events"]), int(info["n_slots"]))
    history = [t for t in _s5_window_history(qa_rr_root) if t[0] != today[0]]
    window = [today] + history + list(S5_WINDOW_SEED)

    verdict_w, k, n, used = _verdict_s5_window(window)
    if verdict_w == "INFO":
        return {"status": "INFO", "row": "0c", "k": k, "n": n, "used": used}

    verdict_c, p, (k1, n1), (k0, n0) = _verdict_s5_change(used)
    fragile, deletions = _s5_window_loo(used)
    return {
        "status": "SCORED",
        "window": {"verdict": verdict_w, "k": k, "n": n,
                   "ub": _cp_upper_95(k, n) * 100.0, "used": used},
        "change": {"verdict": verdict_c, "p": p, "k1": k1, "n1": n1, "k0": k0, "n0": n0},
        "loo": {"fragile": fragile, "deletions": deletions},
    }


# ---------------------------------------------------------------------------
# Task 4.6 — Attribute Kappa
# ---------------------------------------------------------------------------
# Superseded: the old per-scenario `_compute_kappa` always returned NaN because
# its truth vector had a single class (a signal was always injected in S4, and S5
# was mislabelled as positive).  Replaced by the pooled `_attribute_agreement`
# (S4 positives + S5 negatives) defined below in Task 4.6b.


# ---------------------------------------------------------------------------
# Task 4.7 — False-positive rate (S5)
# ---------------------------------------------------------------------------

def _s5_cycle_part_map(df_matched: pd.DataFrame) -> dict:
    """cycle_utc -> part_index for S5, built ONLY from the false_positive ==
    False (per-slot baseline) rows.

    S5's false-positive DECODE rows (false_positive == True) do NOT carry a
    usable part_index: matcher.py cannot attribute an unmatched extra decode
    to any specific truth row, so that field is written NaN for them (verified
    directly against a committed run's S5_matched.csv, 2026-09-06 --
    `qa/rr-study/s5_narrowband_exposure_verify.py`'s report). Filtering
    df_matched on ITS OWN part_index column before computing an FP rate would
    therefore silently discard every FP event -- exactly the instrument blind
    spot HK-026 warns about, and the reason `fp_composition_per_part.py` joins
    against truth.csv by cycle_utc rather than trusting S5_matched.csv's own
    column. Baseline rows DO carry a correct part_index (confirmed: 30 per
    part per appraiser at N=120), so build the map from those and look up any
    row -- baseline or FP decode alike -- by its cycle_utc instead.
    """
    truth_rows = df_matched[df_matched["false_positive"] == False]
    return dict(zip(truth_rows["cycle_utc"], truth_rows["part_index"]))


def _fp_rate_for_parts(df_matched: pd.DataFrame, parts: tuple[int, ...]) -> dict[str, dict]:
    """`_fp_rate`, scoped to the given S5 part_index values via cycle_utc
    membership rather than df_matched's own (unreliable for FP rows)
    part_index column -- see `_s5_cycle_part_map`'s docstring."""
    part_map = _s5_cycle_part_map(df_matched)
    cycles = {c for c, p in part_map.items() if p in parts}
    return _fp_rate(df_matched[df_matched["cycle_utc"].isin(cycles)])


def _fp_rate(df_matched: pd.DataFrame) -> dict[str, dict]:
    """Compute false-positive metrics per appraiser for S5.

    Because all scenarios share a single ALL.TXT log file, the matcher's
    Pass-2 step assigns every decode from S1–S4 cycles as a false-positive
    relative to S5 (since those cycles have no S5 truth row).  To avoid
    inflating the FP count we scope all calculations to cycles that actually
    overlap with the S5 injection window — i.e. cycle_utc values that appear
    in at least one S5 truth row.

    Returns per-appraiser dict with:
        decode_rate      float       — total FP decodes / n_slots (%), reference metric
        event_rate       float       — slots-with-any-FP / n_slots (%), the gate metric's
                                       point estimate
        event_rate_ub95  float       — one-sided 95% Clopper–Pearson UPPER BOUND on the
                                       per-slot FP event rate (%). THIS is the §10 gate
                                       quantity (PASS iff ≤ THRESH_FP_UB95). Defined for
                                       all k (collapses to ≈ 3/n at k=0).
        n_fp_events      int         — number of slots that produced ≥ 1 FP decode
        n_fp_decodes     int         — total individual FP decodes (a slot can have > 1)
        n_slots          int         — total signal-free S5 slots
    """
    _NAN: dict = {
        "decode_rate":     float("nan"),
        "event_rate":      float("nan"),
        "event_rate_ub95": float("nan"),
        "n_fp_events":     float("nan"),
        "n_fp_decodes":    float("nan"),
        "n_slots":         0,
    }
    results: dict[str, dict] = {}

    # Identify the set of cycle_utc slots that S5 actually injected into.
    s5_truth_rows = df_matched[df_matched["false_positive"] == False]
    s5_cycles: set = set(s5_truth_rows["cycle_utc"].dropna().unique())

    for appr in APPRAISERS:
        sub = df_matched[df_matched["appraiser"] == appr]
        truth_sub = sub[sub["false_positive"] == False]
        fp_sub    = sub[sub["false_positive"] == True]

        n_slots = int(len(truth_sub))

        # Scope FPs to the S5 injection window.
        fp_in_window = (fp_sub[fp_sub["cycle_utc"].isin(s5_cycles)]
                        if s5_cycles else fp_sub)

        if n_slots == 0:
            print(f"WARNING: S5 — zero signal-free cycles for {appr}; FP rate undefined",
                  file=sys.stderr)
            results[appr] = _NAN.copy()
            continue

        n_fp_decodes = int(len(fp_in_window))
        # Event count: distinct cycle_utc values with ≥ 1 FP decode.
        n_fp_events  = int(fp_in_window["cycle_utc"].nunique())
        decode_rate  = 100.0 * n_fp_decodes / n_slots
        event_rate   = 100.0 * n_fp_events  / n_slots
        # One-sided 95% Clopper–Pearson upper bound on the per-slot FP event
        # rate — the §10 gate quantity (valid for all k; ≈ 3/n at k=0).
        event_rate_ub95 = 100.0 * _cp_upper_95(n_fp_events, n_slots)

        results[appr] = {
            "decode_rate":     decode_rate,
            "event_rate":      event_rate,
            "event_rate_ub95": event_rate_ub95,
            "n_fp_events":     n_fp_events,
            "n_fp_decodes":    n_fp_decodes,
            "n_slots":         n_slots,
        }
    return results


# ---------------------------------------------------------------------------
# Task 4.6b — Pooled Attribute Agreement Analysis (S4 positives + S5 negatives)
# ---------------------------------------------------------------------------
#
# Why pooled: Cohen's κ vs truth is undefined when the truth vector has a single
# class.  S4 alone is all-positive (a signal is always injected), so κ vs truth
# was always NaN.  S5's signal-free slots are the missing *negative* class.
# Pooling S4 (truth=present) with S5 (truth=absent) yields a proper 2×2 confusion
# matrix per appraiser, so κ vs truth, between-app κ, and within-app
# repeatability all become well-defined.
#
# Unit of analysis: one decode decision per (scenario, part, trial, cycle, msg)
# realization, aligned across appraisers by that key.  Positives carry call =
# "did the app decode this message"; negatives carry call = "did the app emit any
# false-positive decode in this signal-free slot".


def _cohen_kappa_ci(labels_a: list, labels_b: list,
                    n_boot: int = 1000) -> dict:
    """Cohen's κ with a bootstrap 95% CI; NaN (gracefully) if a vector is single-class."""
    from sklearn.metrics import cohen_kappa_score

    if len(labels_a) != len(labels_b) or not labels_a:
        return {"kappa": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan")}
    if len(set(labels_a)) < 2 or len(set(labels_b)) < 2:
        return {"kappa": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan")}

    kappa = float(cohen_kappa_score(labels_a, labels_b))
    rng = np.random.default_rng(seed=42)
    n = len(labels_a)
    boot: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        a_b = [labels_a[i] for i in idx]
        b_b = [labels_b[i] for i in idx]
        if len(set(a_b)) < 2 or len(set(b_b)) < 2:
            continue
        try:
            boot.append(float(cohen_kappa_score(a_b, b_b)))
        except Exception:
            pass
    if boot:
        return {"kappa": kappa,
                "ci_lo": float(np.percentile(boot, 2.5)),
                "ci_hi": float(np.percentile(boot, 97.5))}
    return {"kappa": kappa, "ci_lo": kappa, "ci_hi": kappa}


def _confusion_kappa_repeatability(units: dict[str, dict[tuple, tuple]]) -> dict:
    """Compute confusion counts, κ (vs truth + between-app), and within-app
    repeatability from a ``units`` mapping of ``appr -> {unit_key: (truth, call, group)}``.

    Shared by the full-population and decodable-SNR-restricted attribute-agreement
    computations (rr-density-qrm-scenario / R&R-007) so both variants are computed
    identically save for which units are included.
    """
    # --- Confusion counts ---
    confusion: dict[str, dict] = {}
    for appr in APPRAISERS:
        tp = fp = fn = tn = 0
        for truth, call, _ in units[appr].values():
            if truth and call:
                tp += 1
            elif truth and not call:
                fn += 1
            elif (not truth) and call:
                fp += 1
            else:
                tn += 1
        confusion[appr] = {"TP": tp, "FN": fn, "FP": fp, "TN": tn,
                           "n_pos": tp + fn, "n_neg": fp + tn}

    # --- κ vs truth (each appraiser) ---
    kappa: dict[str, dict] = {}
    for appr in APPRAISERS:
        keys = sorted(units[appr].keys())
        truth = [units[appr][k][0] for k in keys]
        call = [units[appr][k][1] for k in keys]
        kappa[f"{appr}_vs_truth"] = _cohen_kappa_ci(truth, call)

    # --- between-app κ (aligned on shared units) ---
    a0, a1 = APPRAISERS[0], APPRAISERS[1]
    common = sorted(set(units[a0].keys()) & set(units[a1].keys()))
    c0 = [units[a0][k][1] for k in common]
    c1 = [units[a1][k][1] for k in common]
    ba = _cohen_kappa_ci(c0, c1)
    kappa["between_appraisers"] = {"kappa": ba["kappa"]}

    # --- within-app repeatability (self-consistency across trials per group) ---
    repeatability: dict[str, float] = {}
    for appr in APPRAISERS:
        groups: dict[tuple, list[bool]] = {}
        for truth, call, grp in units[appr].values():
            groups.setdefault(grp, []).append(call)
        if groups:
            consistent = sum(1 for v in groups.values() if len(set(v)) == 1)
            repeatability[appr] = 100.0 * consistent / len(groups)
        else:
            repeatability[appr] = float("nan")

    return {"kappa": kappa, "repeatability": repeatability, "confusion": confusion}


def _attribute_agreement(matched: dict[str, pd.DataFrame], run_dir: Path) -> dict:
    """Pooled attribute agreement: S4 positives + S5 negatives.

    Returns a dict with κ (each-app-vs-truth, between-app), within-app
    repeatability, and the per-appraiser confusion counts for the full population,
    plus an **informational** ``restricted`` variant computed over only those S4
    positives at or above ``S4_DECODABLE_SNR_FLOOR_DB`` (all S5 negatives are kept
    in both — SNR does not apply to a signal-free slot). The restricted variant
    operationalises STUDY-SPEC.md §9.3's second ratification condition for
    evaluation; it does not change the full population's gate status, and is never
    passed to ``_collect_verdicts`` (see call site in ``main()``).
    """
    pos_df = matched.get("S4")
    neg_df = matched.get("S5")

    # units[appr][unit_key] = (truth_bool, call_bool, group_key)
    units: dict[str, dict[tuple, tuple]] = {a: {} for a in APPRAISERS}
    units_restricted: dict[str, dict[tuple, tuple]] = {a: {} for a in APPRAISERS}

    # --- Positives (S4): truth present; call = decoded? ---
    if pos_df is not None:
        d = pos_df[pos_df["false_positive"] == False]
        for _, r in d.iterrows():
            appr = r["appraiser"]
            if appr not in units:
                continue
            key = ("S4", r["part_index"], r["trial_index"], r["cycle_utc"], r["message_text"])
            group = ("S4", r["part_index"], r["message_text"])
            entry = (True, bool(r["matched"]), group)
            units[appr][key] = entry

            snr = pd.to_numeric(r.get("true_snr_db"), errors="coerce")
            if pd.notna(snr) and float(snr) >= S4_DECODABLE_SNR_FLOOR_DB:
                units_restricted[appr][key] = entry

    # --- Negatives (S5): truth absent; call = emitted a false positive in slot? ---
    # Included unfiltered in both the full and restricted populations — SNR is not
    # a meaningful concept for a signal-free slot.
    if neg_df is not None:
        truth_rows = neg_df[neg_df["false_positive"] == False]
        s5_cycles = set(truth_rows["cycle_utc"].dropna().unique())
        for appr in APPRAISERS:
            sub = neg_df[neg_df["appraiser"] == appr]
            fp_cycles = set(sub[sub["false_positive"] == True]["cycle_utc"]) & s5_cycles
            for _, r in sub[sub["false_positive"] == False].iterrows():
                cyc = r["cycle_utc"]
                key = ("S5", r["part_index"], r["trial_index"], cyc, "")
                group = ("S5", r["part_index"], "")
                entry = (False, cyc in fp_cycles, group)
                units[appr][key] = entry
                units_restricted[appr][key] = entry

    result = _confusion_kappa_repeatability(units)
    result["restricted"] = _confusion_kappa_repeatability(units_restricted)
    result["restricted"]["snr_floor_db"] = S4_DECODABLE_SNR_FLOOR_DB
    return result


def _attribute_report_lines(attr: dict) -> list[str]:
    """Render the pooled Attribute Agreement section of report.md."""
    lines: list[str] = ["## Attribute Agreement Analysis (S4 positives + S5 negatives)", ""]
    lines += [
        "_κ is computed over a pooled population: S4 injected messages (truth = "
        "present) and S5 signal-free slots (truth = absent), so the truth vector "
        "has both classes. **κ verdicts below are advisory** — the §10 attribute "
        "gate is pending Captain ratification of this pooled method._",
        "",
    ]

    # Confusion matrix
    lines += ["### Confusion vs truth", ""]
    lines += ["| Appraiser | TP | FN | FP | TN | Recovery | Specificity |",
              "|---|---|---|---|---|---|---|"]
    for appr in APPRAISERS:
        c = attr["confusion"].get(appr, {})
        tp, fn, fp, tn = c.get("TP", 0), c.get("FN", 0), c.get("FP", 0), c.get("TN", 0)
        rec = 100.0 * tp / (tp + fn) if (tp + fn) else float("nan")
        spec = 100.0 * tn / (tn + fp) if (tn + fp) else float("nan")
        lines.append(
            f"| {appr} | {tp} | {fn} | {fp} | {tn} | "
            f"{_fmt_num(rec)}% | {_fmt_num(spec)}% |"
        )
    lines += [""]

    # Kappa
    lines += ["### Kappa (advisory)", ""]
    lines += ["| Pair | κ | 95% CI | Verdict (advisory) |", "|---|---|---|---|"]
    for label, info in sorted(attr["kappa"].items()):
        k = info.get("kappa", float("nan"))
        if "ci_lo" in info and not (isinstance(info["ci_lo"], float) and math.isnan(info["ci_lo"])):
            ci = f"[{_fmt_num(info['ci_lo'])}, {_fmt_num(info['ci_hi'])}]"
        else:
            ci = "—"
        v = _verdict_kappa(k) if not math.isnan(k) else "—"
        lines.append(f"| {label} | {_fmt_num(k, '.3f')} | {ci} | {v} |")
    lines += [""]

    # Within-app repeatability
    lines += ["### Within-app repeatability (decision consistency across trials)", ""]
    lines += ["| Appraiser | Consistent groups |", "|---|---|"]
    for appr in APPRAISERS:
        lines.append(f"| {appr} | {_fmt_num(attr['repeatability'].get(appr, float('nan')))}% |")
    lines += [""]

    # Decodable-SNR-restricted κ (informational; rr-density-qrm-scenario / R&R-007).
    # Operationalises STUDY-SPEC.md §9.3's second ratification condition for
    # evaluation only — this figure never contributes to the overall verdict.
    restricted = attr.get("restricted")
    if restricted:
        floor_db = restricted.get("snr_floor_db", S4_DECODABLE_SNR_FLOOR_DB)
        lines += [
            f"### Kappa — decodable-SNR-restricted positives (informational, floor {floor_db:g} dB)",
            "",
            "_S4 positives below the decodable-SNR floor are excluded (S5 negatives "
            "unchanged); shown alongside the full-population figures above per "
            "STUDY-SPEC.md §9.3's second ratification condition. **Informational "
            "only — does not affect the §10 gate or the overall verdict.**",
            "",
        ]
        lines += ["| Appraiser | TP | FN | FP | TN | Recovery | Specificity |",
                  "|---|---|---|---|---|---|---|"]
        for appr in APPRAISERS:
            c = restricted["confusion"].get(appr, {})
            tp, fn, fp, tn = c.get("TP", 0), c.get("FN", 0), c.get("FP", 0), c.get("TN", 0)
            rec = 100.0 * tp / (tp + fn) if (tp + fn) else float("nan")
            spec = 100.0 * tn / (tn + fp) if (tn + fp) else float("nan")
            lines.append(
                f"| {appr} | {tp} | {fn} | {fp} | {tn} | "
                f"{_fmt_num(rec)}% | {_fmt_num(spec)}% |"
            )
        lines += ["", "| Pair | κ | 95% CI | Verdict (informational) |", "|---|---|---|---|"]
        for label, info in sorted(restricted["kappa"].items()):
            k = info.get("kappa", float("nan"))
            if "ci_lo" in info and not (isinstance(info["ci_lo"], float) and math.isnan(info["ci_lo"])):
                ci = f"[{_fmt_num(info['ci_lo'])}, {_fmt_num(info['ci_hi'])}]"
            else:
                ci = "—"
            v = _verdict_kappa(k) if not math.isnan(k) else "—"
            lines.append(f"| {label} | {_fmt_num(k, '.3f')} | {ci} | {v} |")
        lines += [""]

    return lines


# ---------------------------------------------------------------------------
# S7 — Compounding / co-channel per-message recovery
# ---------------------------------------------------------------------------

def _analyse_compounding(df_matched: pd.DataFrame, scen_meta: dict | None,
                         run_dir: Path) -> dict:
    """Per-message recovery analysis for the S7 compounding scenario.

    S7 logs one truth row per compounded signal (as S4 and S8 also do — see
    rr-density-qrm-scenario / R&R-007 for S4's history), so we can measure genuine
    per-message recovery (matched / injected) instead of the degenerate single-class
    Kappa.  Reports recovery per appraiser, per overlap family, per part, the
    capture-effect strong-vs-weak split, and between-app agreement.
    """
    df = df_matched[df_matched["false_positive"] == False].copy()
    df["matched"] = df["matched"].astype(bool)
    df["part_index"] = pd.to_numeric(df["part_index"], errors="coerce")
    df["true_snr_db"] = pd.to_numeric(df["true_snr_db"], errors="coerce")

    # Map part_index → metadata from the scenario JSON.
    part_meta: dict[int, dict] = {}
    for p in (scen_meta or {}).get("parts", []):
        part_meta[int(p["part_index"])] = {
            "overlap_type": p.get("overlap_type", "?"),
            "label": p.get("label", ""),
            "n_signals": len(p.get("signals", [])),
        }

    df["overlap_type"] = df["part_index"].map(
        lambda i: part_meta.get(int(i), {}).get("overlap_type", "?")
        if pd.notna(i) else "?"
    )

    # Overall recovery per appraiser.
    overall: dict[str, float] = {}
    for appr in APPRAISERS:
        sub = df[df["appraiser"] == appr]
        overall[appr] = 100.0 * sub["matched"].mean() if len(sub) else float("nan")

    # Recovery per overlap family per appraiser.
    by_type: dict[str, dict[str, float]] = {}
    for ot in sorted(df["overlap_type"].unique()):
        by_type[ot] = {}
        for appr in APPRAISERS:
            sub = df[(df["overlap_type"] == ot) & (df["appraiser"] == appr)]
            by_type[ot][appr] = 100.0 * sub["matched"].mean() if len(sub) else float("nan")

    # Recovery per part per appraiser (recovered, total).
    per_part: list[dict] = []
    for pi in sorted(df["part_index"].dropna().unique()):
        meta = part_meta.get(int(pi), {})
        row: dict = {
            "part_index": int(pi),
            "overlap_type": meta.get("overlap_type", "?"),
            "label": meta.get("label", ""),
        }
        for appr in APPRAISERS:
            sub = df[(df["part_index"] == pi) & (df["appraiser"] == appr)]
            row[appr] = (int(sub["matched"].sum()), int(len(sub)))
        per_part.append(row)

    # Capture effect: strong vs weak recovery across capture parts.
    capture: dict[str, dict[str, float]] = {}
    df_cap = df[df["overlap_type"] == "capture"].copy()
    if not df_cap.empty:
        part_max = df_cap.groupby("part_index")["true_snr_db"].transform("max")
        df_cap["role"] = np.where(
            np.isclose(df_cap["true_snr_db"], part_max), "strong", "weak"
        )
        for appr in APPRAISERS:
            capture[appr] = {}
            for role in ("strong", "weak"):
                sub = df_cap[(df_cap["appraiser"] == appr) & (df_cap["role"] == role)]
                capture[appr][role] = (
                    100.0 * sub["matched"].mean() if len(sub) else float("nan")
                )

    # Between-app agreement on the per-signal decode decision.
    keyed: dict[str, dict[tuple, bool]] = {}
    for appr in APPRAISERS:
        sub = df[df["appraiser"] == appr]
        d: dict[tuple, bool] = {}
        for _, r in sub.iterrows():
            key = (r["part_index"], r["trial_index"], r["message_text"], r["true_freq_hz"])
            d[key] = bool(r["matched"])
        keyed[appr] = d
    common = set(keyed.get(APPRAISERS[0], {})) & set(keyed.get(APPRAISERS[1], {}))
    if common:
        agree = sum(
            1 for k in common
            if keyed[APPRAISERS[0]][k] == keyed[APPRAISERS[1]][k]
        )
        between_app = 100.0 * agree / len(common)
    else:
        between_app = float("nan")

    # Chart: per-message recovery by part, grouped by appraiser.
    chart_path = None
    if per_part:
        fig, ax = plt.subplots(figsize=(13, 5))
        x = np.arange(len(per_part))
        width = 0.38
        for i, appr in enumerate(APPRAISERS):
            vals = [
                (100.0 * r[appr][0] / r[appr][1]) if r[appr][1] else 0.0
                for r in per_part
            ]
            ax.bar(x + (i - 0.5) * width, vals, width, label=appr)
        ax.set_xticks(x)
        ax.set_xticklabels(
            [f"P{r['part_index']}\n{r['overlap_type']}\n{r['label']}" for r in per_part],
            fontsize=6.5,
        )
        ax.set_ylabel("Per-message recovery (%)")
        ax.set_ylim(0, 105)
        ax.set_title("S7 — Compounding / co-channel per-message recovery")
        ax.legend(fontsize=8)
        ax.grid(axis="y", linestyle=":", lw=0.5)
        plt.tight_layout()
        chart_path = run_dir / "S7_recovery.png"
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)

    return {
        "overall": overall,
        "by_type": by_type,
        "per_part": per_part,
        "capture": capture,
        "between_app": between_app,
        "chart": chart_path.name if chart_path else None,
    }


def _compounding_report_lines(results: dict) -> list[str]:
    """Render the S7 section of report.md from `_analyse_compounding` output."""
    lines: list[str] = ["## S7 — Compounding / co-channel overlap", ""]
    lines += [
        "_Per-message recovery when 2–3 signals occupy the same or near-same "
        "audio frequency / time slot (the pileup case S4 does not exercise). "
        "Informational — no AIAG threshold is defined for co-channel separation._",
        "",
    ]

    # Overall + by-family
    lines += ["### Recovery by overlap family", ""]
    lines += ["| Overlap family | WSJT-X | OpenWSFZ |", "|---|---|---|"]
    for ot, d in results["by_type"].items():
        lines.append(
            f"| {ot} | {_fmt_num(d.get('WSJT-X', float('nan')))}% "
            f"| {_fmt_num(d.get('OpenWSFZ', float('nan')))}% |"
        )
    ov = results["overall"]
    lines.append(
        f"| **all** | **{_fmt_num(ov.get('WSJT-X', float('nan')))}%** "
        f"| **{_fmt_num(ov.get('OpenWSFZ', float('nan')))}%** |"
    )
    lines += [""]

    # Capture effect
    cap = results.get("capture") or {}
    if cap:
        lines += ["### Capture effect (co-channel, unequal SNR)", ""]
        lines += ["| Signal | WSJT-X | OpenWSFZ |", "|---|---|---|"]
        for role in ("strong", "weak"):
            lines.append(
                f"| {role} | "
                f"{_fmt_num(cap.get('WSJT-X', {}).get(role, float('nan')))}% | "
                f"{_fmt_num(cap.get('OpenWSFZ', {}).get(role, float('nan')))}% |"
            )
        lines += [""]

    # Between-app agreement
    lines += [
        f"**Between-app per-signal agreement:** "
        f"{_fmt_num(results.get('between_app', float('nan')))}%",
        "",
    ]

    # Per-part detail
    lines += ["### Per-part detail", ""]
    lines += ["| Part | Family | Condition | WSJT-X | OpenWSFZ |", "|---|---|---|---|---|"]
    for r in results["per_part"]:
        w_rec, w_tot = r["WSJT-X"]
        o_rec, o_tot = r["OpenWSFZ"]
        lines.append(
            f"| P{r['part_index']} | {r['overlap_type']} | {r['label']} "
            f"| {w_rec}/{w_tot} | {o_rec}/{o_tot} |"
        )
    lines += [""]

    if results.get("chart"):
        lines += [f"![S7 recovery]({results['chart']})", ""]

    return lines


# ---------------------------------------------------------------------------
# S8 — Realistic Band Scene holistic decode rate
# ---------------------------------------------------------------------------

def _analyse_band_scene(df_matched: pd.DataFrame,
                        scen_meta: dict | None,
                        run_dir: Path) -> dict:
    """Holistic decode-rate analysis for S8.

    S8 has 12 fixed stations × 5 trials = 60 injected messages.  There are no
    PASS/FAIL thresholds — this is an informational benchmark only.

    Returns a dict with:
      - ``overall``: {appraiser: decode_rate_pct}
      - ``injected``: total truth rows per appraiser
      - ``decoded``:  total matched rows per appraiser
      - ``per_station``: list of {station_label, freq_hz, snr_db, WSJT-X: (n,d), OpenWSFZ: (n,d)}
    """
    df = df_matched[df_matched["false_positive"] == False].copy()
    df["matched"] = df["matched"].astype(bool)
    df["true_freq_hz"] = pd.to_numeric(df["true_freq_hz"], errors="coerce")
    df["true_snr_db"]  = pd.to_numeric(df["true_snr_db"],  errors="coerce")

    # Build station label map from scenario metadata ((freq_hz, snr_db) → station
    # letter).
    #
    # Keyed on the PAIR, never on frequency alone: S8's capture pair (G/H) is
    # deliberately CO-FREQUENCY (both 1500 Hz, 0 dB and -6 dB — that is the whole
    # point of them).  A frequency-only key silently overwrote one station with
    # the other, and the per-station breakdown below then pooled both into a
    # single row carrying the surviving station's label, the *other* station's
    # SNR (via .iloc[0]) and both stations' counts — so a 12-station scenario
    # rendered as 11 rows and the capture pair, the one case the breakdown exists
    # to resolve, was the one case it could not.  Found by Architect review
    # 2026-08-27 (R2, qa/rr-study/2026-08-27-2043-architect-to-qa-review-*.md).
    station_map: dict[tuple[float, float], str] = {}
    for sig in (scen_meta or {}).get("signals", []):
        try:
            station_map[(float(sig["freq_hz"]), float(sig["snr_db"]))] = sig.get("station", "?")
        except (KeyError, ValueError, TypeError):
            pass

    # Overall decode rate per appraiser
    overall: dict[str, float] = {}
    injected: dict[str, int]  = {}
    decoded:  dict[str, int]  = {}
    for appr in APPRAISERS:
        sub = df[df["appraiser"] == appr]
        injected[appr] = len(sub)
        decoded[appr]  = int(sub["matched"].sum())
        overall[appr]  = 100.0 * decoded[appr] / injected[appr] if injected[appr] else float("nan")

    # Per-station breakdown (unique (freq_hz, snr_db) PAIRS — see station_map above).
    # Ordered by frequency, then by descending SNR so a co-frequency capture pair
    # lists the strong member first, matching the scenario's own signal order.
    pairs = sorted(
        set(
            df[["true_freq_hz", "true_snr_db"]]
            .dropna()
            .itertuples(index=False, name=None)
        ),
        key=lambda p: (p[0], -p[1]),
    )
    per_station: list[dict] = []
    for freq, snr in pairs:
        sel = (df["true_freq_hz"] == freq) & (df["true_snr_db"] == snr)
        row: dict = {
            "station":  station_map.get((freq, snr), "?"),
            "freq_hz":  int(freq),
            "snr_db":   snr,
        }
        for appr in APPRAISERS:
            sub = df[sel & (df["appraiser"] == appr)]
            row[appr] = (int(sub["matched"].sum()), len(sub))
        per_station.append(row)

    # Bar chart: per-station decode rate per appraiser
    chart_path = None
    if per_station:
        labels = [f"{r['station']}\n{r['freq_hz']}Hz\n{_fmt_num(r['snr_db'])}dB"
                  for r in per_station]
        x = np.arange(len(per_station))
        width = 0.38
        fig, ax = plt.subplots(figsize=(14, 5))
        for i, appr in enumerate(APPRAISERS):
            vals = [
                (100.0 * r[appr][0] / r[appr][1]) if r[appr][1] else 0.0
                for r in per_station
            ]
            ax.bar(x + (i - 0.5) * width, vals, width, label=appr)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylabel("Decode rate (%)")
        ax.set_ylim(0, 105)
        ax.set_title("S8 — Realistic Band Scene: per-station decode rate")
        ax.legend(fontsize=8)
        ax.grid(axis="y", linestyle=":", lw=0.5)
        plt.tight_layout()
        chart_path = run_dir / "S8_band_scene.png"
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)

    return {
        "overall":     overall,
        "injected":    injected,
        "decoded":     decoded,
        "per_station": per_station,
        "chart":       chart_path.name if chart_path else None,
    }


def _band_scene_report_lines(results: dict) -> list[str]:
    """Render the S8 section of report.md. No PASS/FAIL verdict is emitted."""
    lines: list[str] = ["## S8 — Realistic Band Scene", ""]
    lines += [
        "_Holistic decode-rate benchmark: 12 simultaneous stations across 450–2550 Hz "
        "at realistic SNR spread (−15 to +3 dB), including a near-collision pair (E/F, "
        "12 Hz apart) and a capture pair (G/H, co-frequency, 6 dB ratio). "
        "**Informational only — no PASS/FAIL gate.**_",
        "",
    ]

    # Overall summary table
    lines += ["### Overall decode rate", ""]
    lines += ["| Appraiser | Decoded | Injected | Rate |", "|---|---|---|---|"]
    for appr in APPRAISERS:
        dec  = results["decoded"].get(appr, 0)
        inj  = results["injected"].get(appr, 0)
        rate = results["overall"].get(appr, float("nan"))
        lines.append(f"| {appr} | {dec} | {inj} | {_fmt_num(rate)}% |")

    # Between-appraiser delta
    ov = results["overall"]
    w_rate = ov.get("WSJT-X",    float("nan"))
    o_rate = ov.get("OpenWSFZ",  float("nan"))
    if not (math.isnan(w_rate) or math.isnan(o_rate)):
        delta = o_rate - w_rate
        lines += ["", f"**Between-appraiser delta (OpenWSFZ − WSJT-X): {delta:+.1f} pp**", ""]
    else:
        lines += [""]

    # Per-station breakdown table
    lines += ["### Per-station breakdown", ""]
    lines += [
        "| Stn | Freq (Hz) | SNR (dB) | WSJT-X decoded/total | OpenWSFZ decoded/total |",
        "|---|---|---|---|---|",
    ]
    for r in results["per_station"]:
        w_dec, w_tot = r.get("WSJT-X",   (0, 0))
        o_dec, o_tot = r.get("OpenWSFZ", (0, 0))
        lines.append(
            f"| {r['station']} | {r['freq_hz']} | {_fmt_num(r['snr_db'])} "
            f"| {w_dec}/{w_tot} | {o_dec}/{o_tot} |"
        )
    lines += [""]

    if results.get("chart"):
        lines += [f"![S8 band scene]({results['chart']})", ""]

    return lines


# ---------------------------------------------------------------------------
# S9 — Hashed-callsign cross-cycle resolution (rr-linked-cycle-effectiveness-scenario)
# ---------------------------------------------------------------------------
# Not matched-CSV-driven like every other analyser in this module: a linked
# pair's truth row spans TWO decode cycles (announce + reference) and two
# distinct message texts, which does not fit matcher.py's one-truth-row-per-
# single-message model (see design D2/D3). This analyser therefore reads
# truth.csv's pair rows and the raw WSJT-X/OpenWSFZ ALL.TXT logs directly,
# doing its own (bespoke, per the established one-analyser-per-scenario-type
# convention) slot-bucketed text/frequency matching — the same black-box
# decode-text-comparison approach every other scenario here already uses,
# per D3's rejection of a new app-exposed diagnostic surface.

_HCR_FREQ_TOLERANCE_HZ = 4.0   # matches matcher.py's FREQ_TOLERANCE_HZ convention

# Fallback only — the harness (run_scenario.py's UNRESOLVED_CALLSIGN_PLACEHOLDER)
# always populates truth.csv's unresolved_placeholder column, so this constant
# is a defensive default for a truth.csv written by an older harness version,
# not the normal code path. Value matches ft8_lib's lookup_callsign() sentinel
# (confirmed by inspection; see run_scenario.py's own constant for the citation).
UNRESOLVED_PLACEHOLDER_DEFAULT = "<...>"


def _hcr_text_matches(candidate_msg: str, truth_msg: str) -> bool:
    """Case-sensitive whitespace-normalised message equality (matcher.py convention)."""
    return " ".join(candidate_msg.split()) == " ".join(truth_msg.split())


def _hcr_freq_matches(candidate_freq: float, true_freq: float) -> bool:
    return abs(candidate_freq - true_freq) <= _HCR_FREQ_TOLERANCE_HZ


def _hcr_load_pair_truth(run_dir: Path, scen_id: str) -> list[dict]:
    """Load truth.csv rows for *scen_id* that carry a populated resolved_expected flag."""
    truth_path = run_dir / "truth.csv"
    if not truth_path.exists():
        return []
    rows: list[dict] = []
    with open(truth_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("scenario_id") != scen_id:
                continue
            if str(row.get("resolved_expected", "")).strip().lower() not in ("true", "1"):
                continue
            rows.append(row)
    return rows


def _hcr_parse_cycle(cycle_str: str):
    try:
        return datetime.strptime(cycle_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _analyse_hashed_callsign_resolution(run_dir: Path, scen_id: str = "S9") -> dict | None:
    """Score each linked pair's announce-decode and conditional resolution outcome.

    Returns a dict with per-appraiser aggregate rates plus a per-pair detail
    table, or None if truth.csv has no pair rows for *scen_id* or the
    WSJT-X/OpenWSFZ ALL.TXT logs are not present in *run_dir* (e.g. the
    scenario has only been --dry-run'd, never actually played on the rig).
    """
    pair_rows = _hcr_load_pair_truth(run_dir, scen_id)
    if not pair_rows:
        return None

    wsjt_path = run_dir / "wsjt-all.txt"
    owsfz_path = run_dir / "owsfz-all.txt"
    if not wsjt_path.exists() or not owsfz_path.exists():
        print(
            f"WARNING: {scen_id} — ALL.TXT log(s) not found in {run_dir}; "
            "skipping hashed-callsign resolution analysis (needs a live-rig run, not --dry-run)",
            file=sys.stderr,
        )
        return None

    records_by_appraiser = {
        "WSJT-X":   parse_all_txt(wsjt_path)[0],
        "OpenWSFZ": parse_all_txt(owsfz_path)[0],
    }
    # Slot buckets: dict[normalised cycle utc] -> list[AllTxtRecord].
    buckets_by_appraiser: dict[str, dict] = {}
    for appr, recs in records_by_appraiser.items():
        buckets: dict = {}
        for rec in recs:
            buckets.setdefault(rec.utc, []).append(rec)
        buckets_by_appraiser[appr] = buckets

    per_pair_rows: list[dict] = []
    counts: dict[str, dict[str, int]] = {
        appr: {"n_pairs": 0, "n_announce_decoded": 0, "n_resolved": 0,
               "n_placeholder": 0, "n_not_decoded": 0}
        for appr in APPRAISERS
    }

    for row in pair_rows:
        announce_text = row["announce_text"]
        announce_freq = float(row["announce_freq_hz"])
        announce_dt = _hcr_parse_cycle(row["announce_cycle_utc"])
        reference_text = row["reference_text"]
        reference_freq = float(row["reference_freq_hz"])
        reference_dt = _hcr_parse_cycle(row["reference_cycle_utc"])
        resolved_callsign = row["resolved_callsign"]
        placeholder = row.get("unresolved_placeholder") or UNRESOLVED_PLACEHOLDER_DEFAULT
        placeholder_text = reference_text.replace(resolved_callsign, placeholder)
        # A hash-resolved callsign is NOT rendered bare — ft8_lib's lookup_callsign()
        # (message.c) calls add_brackets() for every hash lookup result, resolved or
        # not; only the *content* differs ("<...>" unresolved vs "<REALCALL>"
        # resolved). Confirmed 2026-07-04 against both the recovered ft8_lib
        # reference source and this scenario's own live-rig run: both WSJT-X and
        # OpenWSFZ decoded the reference cycle as "Q1TST <Q0ABCDEF> RR73", never
        # bare "Q1TST Q0ABCDEF RR73" — matching bare text here would (and, before
        # this fix, did) misclassify every genuinely-resolved pair as
        # reference_not_decoded. The bare form is still accepted as a defensive
        # fallback in case some other decoder ever renders without brackets.
        resolved_bracketed_text = reference_text.replace(
            resolved_callsign, f"<{resolved_callsign}>"
        )

        pair_detail: dict = {
            "pair_index": row.get("part_index", ""),
            "trial_index": row.get("trial_index", ""),
        }

        for appr in APPRAISERS:
            counts[appr]["n_pairs"] += 1
            buckets = buckets_by_appraiser[appr]

            announce_decoded = False
            if announce_dt is not None:
                announce_decoded = any(
                    _hcr_text_matches(c.message, announce_text)
                    and _hcr_freq_matches(c.freq_hz, announce_freq)
                    for c in buckets.get(announce_dt, [])
                )

            outcome = "announce_not_decoded"
            if announce_decoded:
                counts[appr]["n_announce_decoded"] += 1
                ref_candidates = buckets.get(reference_dt, []) if reference_dt is not None else []
                resolved = any(
                    (_hcr_text_matches(c.message, resolved_bracketed_text)
                     or _hcr_text_matches(c.message, reference_text))
                    and _hcr_freq_matches(c.freq_hz, reference_freq)
                    for c in ref_candidates
                )
                if resolved:
                    counts[appr]["n_resolved"] += 1
                    outcome = "resolved"
                else:
                    is_placeholder = any(
                        _hcr_text_matches(c.message, placeholder_text)
                        and _hcr_freq_matches(c.freq_hz, reference_freq)
                        for c in ref_candidates
                    )
                    if is_placeholder:
                        counts[appr]["n_placeholder"] += 1
                        outcome = "not_resolved_placeholder"
                    else:
                        counts[appr]["n_not_decoded"] += 1
                        outcome = "reference_not_decoded"

            pair_detail[appr] = outcome

        per_pair_rows.append(pair_detail)

    rates: dict[str, dict] = {}
    for appr in APPRAISERS:
        c = counts[appr]
        n_pairs = c["n_pairs"]
        n_ann = c["n_announce_decoded"]
        rates[appr] = {
            **c,
            "announce_decode_rate": 100.0 * n_ann / n_pairs if n_pairs else float("nan"),
            # Conditional on the announce cycle having decoded (spec requirement):
            # denominator is n_announce_decoded, not n_pairs.
            "resolution_rate": 100.0 * c["n_resolved"] / n_ann if n_ann else float("nan"),
            "placeholder_rate": 100.0 * c["n_placeholder"] / n_ann if n_ann else float("nan"),
            "not_decoded_rate": 100.0 * c["n_not_decoded"] / n_ann if n_ann else float("nan"),
        }

    # Chart: announce-decode rate vs. conditional resolution-outcome breakdown.
    chart_path = None
    if any(rates[appr]["n_pairs"] for appr in APPRAISERS):
        fig, ax = plt.subplots(figsize=(8, 5))
        x = np.arange(len(APPRAISERS))
        width = 0.2
        metrics = [
            ("announce_decode_rate", "Announce decoded"),
            ("resolution_rate", "Resolved | announce decoded"),
            ("placeholder_rate", "Placeholder | announce decoded"),
            ("not_decoded_rate", "Ref not decoded | announce decoded"),
        ]
        for i, (key, label) in enumerate(metrics):
            vals = [rates[appr][key] for appr in APPRAISERS]
            vals = [0.0 if (isinstance(v, float) and math.isnan(v)) else v for v in vals]
            ax.bar(x + (i - 1.5) * width, vals, width, label=label)
        ax.set_xticks(x)
        ax.set_xticklabels(APPRAISERS)
        ax.set_ylabel("Rate (%)")
        ax.set_ylim(0, 105)
        ax.set_title(f"{scen_id} — Hashed-callsign cross-cycle resolution")
        ax.legend(fontsize=7)
        ax.grid(axis="y", linestyle=":", lw=0.5)
        plt.tight_layout()
        chart_path = run_dir / f"{scen_id}_hashed_resolution.png"
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)

    return {
        "scenario_id": scen_id,
        "rates": rates,
        "per_pair": per_pair_rows,
        "chart": chart_path.name if chart_path else None,
    }


def _hashed_callsign_resolution_report_lines(results: dict) -> list[str]:
    """Render the S9 hashed-callsign resolution section of report.md."""
    scen_id = results["scenario_id"]
    lines: list[str] = [f"## {scen_id} — Hashed-callsign cross-cycle resolution", ""]
    lines += [
        "_Confirmatory check (design D1 path 2): does a genuinely-decoded Type 4 "
        "announcement's nonstandard callsign resolve correctly when referenced by hash in a "
        "later cycle, over the real live-audio channel? The resolution rate's denominator is "
        "restricted to pairs where the announcement decoded, so a low number here is never "
        "conflated with a low announcement-decode rate (see the companion S11 decode-rate "
        "sweep for that separate question). Informational — no AIAG threshold; the table "
        "mechanism itself is already proven deterministic by "
        "f-001-hashed-callsign-resolution's unit tests._",
        "",
    ]

    lines += [
        "### Outcome rates", "",
        "| Appraiser | Announce decoded | Resolved | Placeholder (not resolved) | "
        "Ref not decoded | Denominator |",
        "|---|---|---|---|---|---|",
    ]
    for appr in APPRAISERS:
        r = results["rates"][appr]
        lines.append(
            f"| {appr} | {_fmt_num(r['announce_decode_rate'])}% "
            f"({r['n_announce_decoded']}/{r['n_pairs']}) "
            f"| {_fmt_num(r['resolution_rate'])}% "
            f"| {_fmt_num(r['placeholder_rate'])}% "
            f"| {_fmt_num(r['not_decoded_rate'])}% "
            f"| n={r['n_announce_decoded']} (announce-decoded pairs) |"
        )
    lines += [
        "",
        "_Resolved / Placeholder / Ref-not-decoded are each a % of the announce-decoded "
        "denominator (n in the last column), per the spec's conditional-scoring requirement._",
        "",
    ]

    if results.get("chart"):
        lines += [f"![{scen_id} hashed-callsign resolution]({results['chart']})", ""]

    if results.get("per_pair"):
        lines += ["### Per-pair detail", "", "| Pair | Trial | WSJT-X | OpenWSFZ |", "|---|---|---|---|"]
        for r in results["per_pair"]:
            lines.append(
                f"| {r['pair_index']} | {r['trial_index']} "
                f"| {r.get('WSJT-X', '—')} | {r.get('OpenWSFZ', '—')} |"
            )
        lines += [""]

    return lines


# ---------------------------------------------------------------------------
# S3b — Negative-DT decode-rate analysis
# ---------------------------------------------------------------------------

def _analyse_decode_rate(df_matched: pd.DataFrame, scen_id: str,
                         run_dir: Path, part_var: str = "true_dt_s",
                         part_label: str = "True DT (s)") -> dict:
    """Per-part decode-rate analysis for attribute-style scenarios (e.g. S3b, S1b).

    Measures what fraction of injected messages were decoded by each appraiser
    at each part.  The part variable (x-axis) is configurable via *part_var*
    (column name in the matched CSV) and *part_label* (axis/header label).
    Returns a dict suitable for report rendering.
    No Gage R&R is computed — this is a decode-rate (sensitivity) study.
    """
    df = df_matched[df_matched["false_positive"] == False].copy()
    df["matched"] = df["matched"].astype(bool)
    df["part_index"] = pd.to_numeric(df["part_index"], errors="coerce")
    df[part_var] = pd.to_numeric(df[part_var], errors="coerce")

    parts = sorted(df["part_index"].dropna().unique())

    # Per-part decode rate per appraiser
    per_part: list[dict] = []
    for pi in parts:
        part_sub = df[df["part_index"] == pi]
        part_val = part_sub[part_var].dropna().iloc[0] if not part_sub.empty else float("nan")
        row: dict = {"part_index": int(pi), "part_val": part_val}
        for appr in APPRAISERS:
            sub = part_sub[part_sub["appraiser"] == appr]
            n_total = len(sub)
            n_matched = int(sub["matched"].sum())
            rate = 100.0 * n_matched / n_total if n_total > 0 else float("nan")
            row[f"{appr}_decoded"] = n_matched
            row[f"{appr}_total"] = n_total
            row[f"{appr}_rate"] = rate
        per_part.append(row)

    # Overall per-appraiser
    overall: dict[str, float] = {}
    for appr in APPRAISERS:
        sub = df[df["appraiser"] == appr]
        overall[appr] = 100.0 * sub["matched"].mean() if len(sub) else float("nan")

    # Chart: decode rate vs part variable per appraiser
    chart_path = None
    if per_part:
        fig, ax = plt.subplots(figsize=(10, 5))
        x_vals = [r["part_val"] for r in per_part]
        for appr in APPRAISERS:
            rates = [r[f"{appr}_rate"] for r in per_part]
            ax.plot(x_vals, rates, marker="o", label=appr)
        ax.set_xlabel(part_label)
        ax.set_ylabel("Decode rate (%)")
        ax.set_ylim(-5, 105)
        ax.set_title(f"{scen_id} — Decode rate vs {part_label}")
        ax.legend(fontsize=9)
        cfg = DECODE_RATE_CONFIG.get(scen_id, {})
        if cfg.get("chart_ref_line") is not None:
            ax.axvline(cfg["chart_ref_line"], color="grey", linestyle=":", lw=0.8)
        ax.grid(axis="y", linestyle=":", lw=0.5)
        plt.tight_layout()
        chart_path = run_dir / f"{scen_id}_decode_rate.png"
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)

    return {
        "scenario_id": scen_id,
        "part_var": part_var,
        "part_label": part_label,
        "per_part": per_part,
        "overall": overall,
        "chart": chart_path.name if chart_path else None,
    }


def _decode_rate_report_lines(results: dict) -> list[str]:
    """Render a decode-rate section of report.md (generic: S3b, S1b, ...)."""
    scen_id = results["scenario_id"]
    part_label = results.get("part_label", "Part value")
    cfg = DECODE_RATE_CONFIG.get(scen_id, {})
    section_title = cfg.get("section_title", f"{scen_id} decode-rate study")
    section_intro = cfg.get(
        "section_intro",
        "Decode rate (% of injected messages recovered) per appraiser. "
        "Informational — no AIAG threshold.",
    )
    lines: list[str] = [
        f"## {scen_id} — {section_title}", "",
        f"_{section_intro}_",
        "",
        "### Per-part decode rate", "",
        f"| Part | {part_label} | WSJT-X decoded | WSJT-X rate | OpenWSFZ decoded | OpenWSFZ rate |",
        "|---|---|---|---|---|---|",
    ]
    for r in results["per_part"]:
        w_dec = r.get("WSJT-X_decoded", "—")
        w_tot = r.get("WSJT-X_total", "—")
        w_rate = _fmt_num(r.get("WSJT-X_rate", float("nan")))
        o_dec = r.get("OpenWSFZ_decoded", "—")
        o_tot = r.get("OpenWSFZ_total", "—")
        o_rate = _fmt_num(r.get("OpenWSFZ_rate", float("nan")))
        lines.append(
            f"| P{r['part_index']} | {_fmt_num(r['part_val'])} "
            f"| {w_dec}/{w_tot} | {w_rate}% "
            f"| {o_dec}/{o_tot} | {o_rate}% |"
        )
    ov = results["overall"]
    lines += [
        "",
        f"**Overall decode rate — WSJT-X: {_fmt_num(ov.get('WSJT-X', float('nan')))}%  "
        f"OpenWSFZ: {_fmt_num(ov.get('OpenWSFZ', float('nan')))}%**",
        "",
    ]
    if results.get("chart"):
        lines += [f"![{results['scenario_id']} decode rate]({results['chart']})", ""]
    return lines


# ---------------------------------------------------------------------------
# Task 4.8 — Verdict engine
# ---------------------------------------------------------------------------

def _collect_verdicts(
    continuous_results: dict[str, dict],
    kappa_results: dict[str, dict],
    fp_results: dict[str, dict],
    bias_results: dict[str, dict],
    fp_narrowband_results: dict[str, dict] | None = None,
    s5_window_result: dict | None = None,
) -> tuple[list[tuple[str, str, float | str, str]], str, list[str], list[str]]:
    """Collect all metric verdicts and return (rows, overall_verdict, fails, notes)."""
    verdict_rows: list[tuple[str, str, float | str, str]] = []
    # (metric_name, scenario/appraiser, value, verdict)
    fails: list[str] = []
    marginals: list[str] = []
    notes: list[str] = []

    for scen_id, res in continuous_results.items():
        if res is None:
            continue
        pct_grr = res["metrics"]["pct_contribution_grr"]
        ndc = res["metrics"]["ndc"]
        v_grr = _verdict_grr(pct_grr)
        v_ndc = _verdict_ndc(ndc)
        verdict_rows.append(("%GR&R", scen_id, f"{pct_grr:.1f}%", v_grr))
        verdict_rows.append(("ndc", scen_id, str(ndc), v_ndc))
        if v_grr == "FAIL":
            fails.append(f"%GR&R ({scen_id}) = {pct_grr:.1f}% (threshold: < {THRESH_GRR_PASS}% Acceptable)")
        elif v_grr == "MARGINAL":
            marginals.append(f"%GR&R ({scen_id}) = {pct_grr:.1f}%")

    for label, info in kappa_results.items():
        kappa = info.get("kappa", float("nan"))
        if math.isnan(kappa):
            continue
        # Advisory only — the pooled attribute κ gate is pending §10 ratification,
        # so it is reported but does NOT drive the overall verdict.
        v = _verdict_kappa(kappa)
        verdict_rows.append(("Kappa (advisory)", label, f"{kappa:.3f}", v))

    for appr, info in fp_results.items():
        n_events = info.get("n_fp_events", float("nan"))
        if isinstance(n_events, float) and math.isnan(n_events):
            continue
        event_rate  = info["event_rate"]
        decode_rate = info["decode_rate"]
        n_slots     = info["n_slots"]
        ub95        = info["event_rate_ub95"]
        v = _verdict_fp(info)
        value_str = (f"{int(n_events)}/{n_slots} slots "
                     f"(event {event_rate:.1f}%; 95% UB {ub95:.2f}%; decode {decode_rate:.1f}%)")
        # R&R-011 (PO ruling Option A, 2026-09-08): per-sweep Gate A is now
        # UNCONDITIONALLY "INFO" -- superseded as a gate, not underpowered.
        # It still feeds the trailing window (see the Gate A-W/A-Delta rows
        # below, this same function) -- three separate lines, never combined
        # into one S5 verdict (R&R-010's prohibition, carried forward).
        assert v == "INFO", "_verdict_fp must be unconditionally INFO post-R&R-011"
        notes.append(
            f"FP event rate (S5/{appr}) not gated at N={n_slots}: {value_str} — "
            f"per-sweep Gate A was superseded by R&R-011 (2026-09-08): at N=120 "
            f"it cannot separate 'unchanged' from 'twice as bad'. See Gate A-W "
            f"below for the ratified compliance verdict."
        )

    # Gate A-W / Gate A-Delta (R&R-011) — the trailing-window compliance and
    # change gates that replace per-sweep Gate A above. Two separate rows,
    # never pooled into each other or into the per-sweep INFO row above.
    if s5_window_result:
        status = s5_window_result.get("status")
        if status == "VOID":
            notes.append(
                f"S5 window gate (Gate A-W/Gate A-Δ) VOID — ROW {s5_window_result['row']}: "
                f"{s5_window_result['detail']}. Neither gate is evaluated; no S5 window "
                f"verdict of any kind is reported this sweep (R&R-011 Sec.3)."
            )
        elif status == "INFO":
            notes.append(
                f"S5 window gate: INFO — trailing window not yet full "
                f"({s5_window_result['k']}/{s5_window_result['n']} of "
                f"{S5_WINDOW_SLOTS} AWGN slots accumulated). Not a PASS."
            )
        elif status == "SCORED":
            w = s5_window_result["window"]
            c = s5_window_result["change"]
            loo = s5_window_result["loo"]
            fragile_tag = " [FRAGILE]" if loo["fragile"] else ""
            w_value = (f"{w['k']}/{w['n']} slots (event {100.0*w['k']/w['n']:.3f}%; "
                       f"95% UB {w['ub']:.3f}%){fragile_tag}")
            verdict_rows.append(("FP event rate (95% UB), Gate A-W", "S5/OpenWSFZ", w_value, w["verdict"]))
            if w["verdict"] == "FAIL":
                fails.append(
                    f"Gate A-W (S5 trailing {S5_WINDOW_SLOTS}-slot window) = {w['k']}/{w['n']} "
                    f"events (95% UB {w['ub']:.3f}%); gate requires 95% UB ≤ {THRESH_FP_UB95:.0f}%"
                )
            if c["verdict"] == "INFO":
                notes.append("Gate A-Δ: INFO — window holds a single sweep, nothing to compare against.")
            else:
                c_value = f"{c['k1']}/{c['n1']} vs {c['k0']}/{c['n0']} (Fisher p={c['p']:.4f}){fragile_tag}"
                verdict_rows.append(("FP event rate change, Gate A-Δ", "S5/OpenWSFZ", c_value, c["verdict"]))
                if c["verdict"] == "FAIL":
                    fails.append(
                        f"Gate A-Δ (S5 newest sweep vs trailing window) = {c['k1']}/{c['n1']} vs "
                        f"{c['k0']}/{c['n0']}, Fisher(greater) p={c['p']:.4f} ≤ "
                        f"{S5_WINDOW_ALPHA_CHANGE}; blind below ~2x, a PASS elsewhere is not "
                        f"'nothing moved'"
                    )

    # Check B — narrowband (S5 parts 2/3), S5-GATE-SIZING Amendment 1. Scored on
    # its OWN 60-slot denominator, its own row, its own line in `fails` — NEVER
    # merged with Gate A above into one S5 verdict (that pooling is the defect
    # this design removes). No STATISTICAL small-N demotion (see
    # `_verdict_s5_narrowband`'s docstring) — but zero narrowband slots injected
    # (Check B did not run this battery) DOES demote to INFO, same convention
    # as Gate A's MIN_N_FOR_FP_GATE path above: excluded from the gate table
    # and the overall verdict, traced in `notes`, never a manufactured PASS.
    for appr, info in (fp_narrowband_results or {}).items():
        n_slots = info.get("n_slots", 0)
        v = _verdict_s5_narrowband(info)
        if v == "INFO":
            notes.append(
                f"FP events Check B (narrowband, S5/{appr}) not evaluated: "
                f"0 narrowband slots injected — Check B did not run this "
                f"battery (e.g. a --parts 0,1 targeted recheck). This is a "
                f"coverage gap, not a PASS — see a run that includes S5 "
                f"parts 2/3 for real coverage."
            )
            continue
        n_events = info["n_fp_events"]
        value_str = f"{int(n_events)}/{n_slots} slots (FAIL iff >= {THRESH_S5_NARROWBAND_FAIL})"
        verdict_rows.append(("FP events, Check B (narrowband)", f"S5/{appr}", value_str, v))
        if v == "FAIL":
            fails.append(
                f"FP events Check B narrowband ({appr}) = {int(n_events)} events in "
                f"{n_slots} slots; check requires < {THRESH_S5_NARROWBAND_FAIL}"
            )

    for appr, info in bias_results.items():
        bias = info.get("mean_bias", float("nan"))
        if math.isnan(bias):
            continue
        v = _verdict_bias(bias)
        verdict_rows.append(("SNR bias", f"S1/{appr}", f"{bias:+.2f} dB", v))
        if v == "FAIL":
            fails.append(
                f"SNR bias ({appr}) = {bias:+.2f} dB (threshold: ≤ ±{THRESH_BIAS_PASS} dB)"
            )

    if fails:
        overall = "FAIL"
    elif marginals:
        overall = "MARGINAL"
    else:
        overall = "PASS"

    return verdict_rows, overall, fails, notes


# ---------------------------------------------------------------------------
# Task 4.9 — Write report.md
# ---------------------------------------------------------------------------

def _fmt_num(v: Any, fmt: str = ".2f") -> str:
    if isinstance(v, float) and math.isnan(v):
        return "—"
    try:
        return format(float(v), fmt)
    except (TypeError, ValueError):
        return str(v)


def _s5_window_report_lines(s5_window_result: dict | None) -> list[str]:
    """Render Gate A-W (compliance) / Gate A-Delta (change) — R&R-011, the
    trailing-window gates that replace per-sweep Gate A's PASS/FAIL. Renders
    ROW 0's VOID/INFO outcomes distinctly from a scored verdict; never renders
    a combined S5 line (R&R-010's prohibition, carried forward)."""
    lines: list[str] = ["### False-positive rate (S5) — Gate A-W / Gate A-Δ (trailing window, R&R-011)", ""]
    if not s5_window_result or s5_window_result.get("status") == "NOT_RUN":
        lines += ["_Not evaluated — Gate A (S5 AWGN) did not run this sweep._", ""]
        return lines

    status = s5_window_result["status"]
    if status == "VOID":
        lines += [
            f"**VOID — ROW {s5_window_result['row']}.** {s5_window_result['detail']}. "
            f"Neither gate is evaluated; no S5 window verdict of any kind is reported this "
            f"sweep (R&R-011 spec Sec.3). This is not a PASS and not a FAIL.",
            "",
        ]
        return lines
    if status == "INFO":
        lines += [
            f"**INFO — ROW 0c, window not yet full.** "
            f"{s5_window_result['k']}/{s5_window_result['n']} of {S5_WINDOW_SLOTS} AWGN "
            f"slots accumulated. Not a PASS.",
            "",
        ]
        return lines

    w, c, loo = s5_window_result["window"], s5_window_result["change"], s5_window_result["loo"]
    lines += [
        "| Gate | Value | Verdict |",
        "|---|---|---|",
        f"| **Gate A-W** (compliance) | {w['k']}/{w['n']} = {100.0*w['k']/w['n']:.3f}%, "
        f"95% UB {w['ub']:.3f}% (PASS iff ≤ {THRESH_FP_UB95:.0f}%) | **{w['verdict']}** |",
    ]
    if c["verdict"] == "INFO":
        lines.append("| Gate A-Δ (change) | window holds a single sweep | **INFO** |")
    else:
        lines.append(
            f"| **Gate A-Δ** (change) | {c['k1']}/{c['n1']} (newest) vs {c['k0']}/{c['n0']} "
            f"(rest of window), Fisher(greater) p={c['p']:.4f} (FAIL iff ≤ "
            f"{S5_WINDOW_ALPHA_CHANGE}) | **{c['verdict']}** |"
        )
    lines += [
        "",
        f"_Gate A-W (R&R-011, PO ruling Option A, 2026-09-08) — the ratified 6% UB "
        f"(STUDY-SPEC §10, unchanged, not re-ratified) read on a trailing "
        f"{S5_WINDOW_SLOTS}-AWGN-slot window (unit is the slot, not the sweep). Gate A-Δ — "
        f"newest sweep vs the rest of that same window, one-sided Fisher at "
        f"{S5_WINDOW_ALPHA_CHANGE}. **Two separate rows, never pooled**: ROW 1 (Gate A-W "
        f"FAIL) and ROW 2 (Gate A-Δ FAIL) can both fire independently. **Honest costs**: the "
        f"window lags — a regression introduced this sweep is diluted 1:4 and takes up to "
        f"four sweeps to reach full weight; Gate A-Δ is blind below ~2× (power 0.40 at 2×, "
        f"0.82 at 3×). **A PASS may not be read as \"nothing moved\".**",
        "",
    ]
    lines += [
        f"_Leave-one-sweep-out (spec Sec.4.7): "
        + ("**FRAGILE** — removing at least one contributing sweep flips Gate A-W's "
           "verdict; this bounds the up-to-seven-build cross-build confound, do not read "
           "the verdict as evidence about any single build."
           if loo["fragile"] else
           f"all {len(loo['deletions'])} single-sweep deletions leave Gate A-W's verdict "
           f"unchanged — **not FRAGILE**.")
        + "_",
        "",
    ]
    return lines


def _write_report(
    run_dir: Path,
    git_sha: str,
    continuous_results: dict,
    kappa_results: dict,
    fp_results: dict,
    bias_results: dict,
    verdict_rows: list,
    overall: str,
    fails: list[str],
    notes: list[str] | None = None,
    s7_results: dict | None = None,
    s8_results: dict | None = None,
    attr_results: dict | None = None,
    decode_rate_results: list[dict] | None = None,
    hcr_results: dict | None = None,
    fp_narrowband_results: dict | None = None,
    s5_window_result: dict | None = None,
) -> Path:
    lines: list[str] = []
    run_date = run_dir.name.split("-")[0:3]
    run_date_str = "-".join(run_date) if len(run_date) >= 3 else run_dir.name

    # WSJT-X version
    ver_path = run_dir / "wsjt-version.txt"
    wsjt_ver = ver_path.read_text(encoding="utf-8").strip() if ver_path.exists() else "unknown"

    lines += [
        "# OpenWSFZ R&R Study Report",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Run date | {run_date_str} |",
        f"| OpenWSFZ SHA | `{git_sha}` |",
        f"| WSJT-X version | {wsjt_ver} |",
        "",
    ]

    # Continuous scenarios
    for scen_id, res in sorted(continuous_results.items()):
        if res is None:
            lines += [f"## {scen_id}", "", "_Insufficient data — skipped._", ""]
            continue
        anova = res["anova"]
        metrics = res["metrics"]
        response = res["response"]
        tol_half = res["tol_half"]

        lines += [
            f"## {scen_id} — {response}",
            "",
            "### Variance Components",
            "",
            "| Component | σ² | %Contribution |",
            "|---|---|---|",
            f"| Repeatability | {_fmt_num(anova['var_repeatability'])} | {_fmt_num(metrics['pct_contribution_repeat'])}% |",
            f"| Reproducibility | {_fmt_num(anova['var_reproducibility'])} | {_fmt_num(metrics['pct_contribution_reprod'])}% |",
            f"| Part-to-Part | {_fmt_num(anova['var_part'])} | {_fmt_num(metrics['pct_contribution_part'])}% |",
            f"| Total GR&R | {_fmt_num(anova['var_grr'])} | {_fmt_num(metrics['pct_contribution_grr'])}% |",
            f"| Total | {_fmt_num(anova['var_total'])} | 100.00% |",
            "",
            "### Study Metrics",
            "",
            "| Metric | Value | Verdict |",
            "|---|---|---|",
            # The §10 gate is %Contribution, so %Contribution is the row that
            # carries the verdict.  %Tolerance and %Study Var are reported for
            # reference with an explicit "—", never beside a verdict computed
            # from a different number: this row previously printed the
            # %Tolerance VALUE next to the %CONTRIBUTION VERDICT, so S3 rendered
            # as "89.79% | PASS" — a figure AIAG would call unacceptable sitting
            # next to the word PASS.  Architect review 2026-08-27 (R4).
            f"| %Contribution (GR&R) | {_fmt_num(metrics['pct_contribution_grr'])}% | {_verdict_grr(metrics['pct_contribution_grr'])} |",
            f"| %Tolerance (GR&R) | {_fmt_num(metrics['pct_tolerance'])}% | — |",
            f"| %Study Var (GR&R) | {_fmt_num(metrics['pct_study_var_grr'])}% | — |",
            f"| ndc | {metrics['ndc']} | {_verdict_ndc(metrics['ndc'])} |",
            "",
        ]
        # Embedded PNG
        png_name = f"{scen_id}_grr_panel.png"
        lines += [f"![{scen_id} GR&R panel]({png_name})", ""]

        if scen_id == "S1" and bias_results:
            lines += ["### Bias & Linearity (S1)", ""]
            lines += ["| Appraiser | Mean Bias (dB) | Slope | Intercept | R² | Verdict |",
                      "|---|---|---|---|---|---|"]
            for appr, bi in bias_results.items():
                v = _verdict_bias(bi["mean_bias"])
                lines.append(
                    f"| {appr} | {bi['mean_bias']:+.2f} | {bi['slope']:.3f} | "
                    f"{bi['intercept']:.3f} | {bi['r2']:.3f} | {v} |"
                )
            lines += ["", f"![S1 Bias & Linearity](S1_bias_linearity.png)", ""]

        if scen_id == "S3":
            corr = continuous_results.get("S3", {})
            if corr and corr.get("s3_correction_applied"):
                lines += [
                    "> **WSJT-X DT correction applied.** A +0.55 s offset was added to "
                    "WSJT-X `reported_dt_s` before ANOVA to remove the ≈ −0.55 s "
                    "convention difference between WSJT-X (DT relative to nominal FT8 "
                    "TX start) and the harness (DT relative to UTC slot boundary). "
                    "This correction removes the calibration artefact from "
                    "SS_appraiser so %GR&R measures genuine app-to-app measurement "
                    "disagreement. Raw reported values are preserved in the matched CSV. "
                    "See scenario `wsjt_dt_correction_s` field and R&R-003 (GitHub #1).",
                    "",
                ]

    # Decode-rate companion studies (S3b, S1b, ...)
    for dr in (decode_rate_results or []):
        lines += _decode_rate_report_lines(dr)

    # Attribute scenarios — pooled S4 positives + S5 negatives
    if attr_results:
        lines += _attribute_report_lines(attr_results)

    if fp_results:
        lines += ["### False-positive rate (S5) — Gate A (AWGN, parts 0/1)", ""]
        lines += ["| Appraiser | FP events / slots | Event rate | 95% UB | Decode rate | Verdict |",
                  "|---|---|---|---|---|---|"]
        for appr, info in fp_results.items():
            n_events = info.get("n_fp_events", float("nan"))
            if isinstance(n_events, float) and math.isnan(n_events):
                lines.append(f"| {appr} | — | — | — | — | — |")
                continue
            n_slots     = info["n_slots"]
            event_rate  = info["event_rate"]
            decode_rate = info["decode_rate"]
            ub95        = info["event_rate_ub95"]
            v = _verdict_fp(info)
            lines.append(
                f"| {appr} | {int(n_events)} / {n_slots} "
                f"| {_fmt_num(event_rate)}% "
                f"| {_fmt_num(ub95)}% "
                f"| {_fmt_num(decode_rate)}% "
                f"| {v} |"
            )
        lines += [
            "",
            f"_Per-sweep reading (STUDY-SPEC §10, ratified 2026-07-04, R&R-004; population "
            f"re-affirmed S5-GATE-SIZING Amendment 1, 2026-09-06) of the per-slot FP **event "
            f"rate** on AWGN slots (parts 0/1) ONLY, one-sided 95% Clopper–Pearson **upper "
            f"bound** shown for reference. Decode rate is reported for reference only. "
            f"**SUPERSEDED as a gate by R&R-011 (2026-09-08): always INFO.** At N=120 this "
            f"reading cannot separate 'unchanged' (P(FAIL)=0.739 at the established 3.182% "
            f"rate) from 'twice as bad' (P(FAIL)=0.984) — see the ratified compliance verdict "
            f"in **Gate A-W** below, which reads this same quantity on a trailing "
            f"{S5_WINDOW_SLOTS}-slot window instead. **Never pooled with Check B below, nor "
            f"with Gate A-W/Gate A-Δ** — see those tables' own notes._",
            "",
        ]

    if fp_results and fp_results.get("OpenWSFZ") is not None:
        lines += _s5_window_report_lines(s5_window_result)

    if fp_narrowband_results:
        lines += ["### False-positive rate (S5) — Check B (narrowband, parts 2/3)", ""]
        lines += ["| Appraiser | FP events / slots | Verdict |",
                  "|---|---|---|"]
        for appr, info in fp_narrowband_results.items():
            v = _verdict_s5_narrowband(info)
            if v == "INFO":
                lines.append(f"| {appr} | — | INFO |")
                continue
            n_events = info["n_fp_events"]
            n_slots = info["n_slots"]
            lines.append(f"| {appr} | {int(n_events)} / {n_slots} | {v} |")
        lines += [
            "",
            f"_Check (S5-GATE-SIZING Amendment 1, PO ruling Option 3, 2026-09-06 20:29 UTC): "
            f"a coverage net for narrowband hallucination (steady carrier / birdies), scored "
            f"on its OWN {60}-slot denominator — FAIL iff events ≥ {THRESH_S5_NARROWBAND_FAIL}. "
            f"Threshold derived in the spec's A1.2 from the measured all-history per-slot "
            f"narrowband base rate (0.2347%, `s5_narrowband_exposure_verify.py`, ROW 0 "
            f"cleared 2026-09-06), well under the ~1% re-derivation trigger. This is a raw "
            f"event-count check, not a Clopper–Pearson UB gate, so there is no STATISTICAL "
            f"small-N demotion analogous to `MIN_N_FOR_FP_GATE` — but **INFO** here means "
            f"something distinct: zero narrowband slots were injected at all (Check B did not "
            f"run this battery, e.g. a targeted `--parts 0,1` recheck). That is a coverage "
            f"gap, never a PASS — asserting PASS with no slots run would reproduce the exact "
            f"blindness this design exists to remove. **Never pooled with Gate A above into "
            f"one S5 rate or one verdict line** — the same 180 slots FAIL under no change 21% "
            f"of the time scored as one gate; scored as two, Gate A alone FAILs under no "
            f"change 77% of the time (its own false-alarm rate at N=120, corrected 2026-09-08 "
            f"— see R&R-011; not a detection rate)._",
            "",
        ]

    # S7 — compounding / co-channel overlap
    if s7_results:
        lines += _compounding_report_lines(s7_results)

    # S8 — realistic band scene (informational; no PASS/FAIL verdict)
    if s8_results:
        lines += _band_scene_report_lines(s8_results)

    # S9 — hashed-callsign cross-cycle resolution (informational; no PASS/FAIL verdict)
    if hcr_results:
        lines += _hashed_callsign_resolution_report_lines(hcr_results)

    # Summary
    lines += [
        "## Summary",
        "",
        "| Metric | Scope | Value | Verdict |",
        "|---|---|---|---|",
    ]
    for row in verdict_rows:
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
    lines += [
        "",
        f"**Overall verdict: {overall}**",
        "",
    ]

    if notes:
        lines += ["### Excluded From Gate (Informational)", ""]
        for n in notes:
            lines.append(f"- ℹ️ {n}")
        lines += [""]

    if fails:
        lines += ["### Defect Notices", ""]
        for f in fails:
            lines.append(f"- ❌ FAIL — {f}")
        lines += [""]

    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Task 4.10 — Append trend.csv
# ---------------------------------------------------------------------------

_TREND_COLUMNS = [
    "run_date", "git_sha", "pct_grr_snr", "ndc_snr", "bias_snr_owsfz",
    "kappa_s4", "fp_rate_s5",
    # R&R-011 (2026-09-08): the raw Gate A AWGN (parts 0/1) count/denominator
    # feeding the trailing window (S5_WINDOW_SEED, `_s5_window_history`).
    # `fp_rate_s5` above is the derived 95% UB, not sufficient on its own to
    # reconstruct the window (it does not disambiguate N=60 vs N=120 eras).
    # Header migration for the already-committed file: see the note this
    # supersedes at STUDY-SPEC.md Sec.16, R&R-010 entry.
    _TREND_S5_EVENTS_COL, _TREND_S5_SLOTS_COL,
]


def _append_trend(qa_rr_root: Path, run_dir: Path, git_sha: str,
                  continuous_results: dict, kappa_results: dict,
                  fp_results: dict, bias_results: dict) -> None:
    trend_path = qa_rr_root / "trend.csv"
    write_header = not trend_path.exists()

    run_date = run_dir.name.split("-")[0:3]
    run_date_str = "-".join(run_date) if len(run_date) >= 3 else run_dir.name

    def _safe(v: Any) -> str:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return ""
        return str(v)

    pct_grr_snr = ""
    ndc_snr = ""
    if "S1" in continuous_results and continuous_results["S1"] is not None:
        pct_grr_snr = _safe(continuous_results["S1"]["metrics"]["pct_contribution_grr"])
        ndc_snr = _safe(continuous_results["S1"]["metrics"]["ndc"])

    bias_snr_owsfz = ""
    if "OpenWSFZ" in bias_results:
        bias_snr_owsfz = _safe(bias_results["OpenWSFZ"].get("mean_bias"))

    kappa_s4 = ""
    for label, info in kappa_results.items():
        if "OpenWSFZ_vs_truth" in label:
            kappa_s4 = _safe(info.get("kappa"))
            break

    # Track the gate quantity (95% CP upper bound on per-slot FP event rate),
    # not the reference decode_rate, so trend regressions match the §10 gate.
    fp_rate_s5 = ""
    fp_events_s5 = ""
    fp_slots_s5 = ""
    if "OpenWSFZ" in fp_results:
        info = fp_results["OpenWSFZ"]
        fp_rate_s5 = _safe(info.get("event_rate_ub95"))
        # R&R-011: raw (events, slots) -- what `_s5_window_history` needs to
        # rebuild the trailing window. `n_fp_events`/`n_slots` are NaN/absent
        # when this run injected no AWGN slots at all (e.g. a --parts 2,3
        # targeted recheck); leave both empty rather than write a false 0.
        n_events = info.get("n_fp_events", float("nan"))
        if not (isinstance(n_events, float) and math.isnan(n_events)):
            fp_events_s5 = _safe(int(n_events))
            fp_slots_s5 = _safe(int(info.get("n_slots", 0)))

    row = {
        "run_date": run_date_str,
        "git_sha": git_sha,
        "pct_grr_snr": pct_grr_snr,
        "ndc_snr": ndc_snr,
        "bias_snr_owsfz": bias_snr_owsfz,
        "kappa_s4": kappa_s4,
        "fp_rate_s5": fp_rate_s5,
        _TREND_S5_EVENTS_COL: fp_events_s5,
        _TREND_S5_SLOTS_COL: fp_slots_s5,
    }

    with open(trend_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_TREND_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Task 4.11 — Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="R&R study analyser — compute Gage R&R and write report.md"
    )
    parser.add_argument("--run-dir", required=True, help="Run directory containing *_matched.csv files")
    parser.add_argument(
        "--scenario",
        help="Comma-separated scenario IDs to analyse (default: all found in run-dir)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        sys.exit(f"ERROR: run directory does not exist: {run_dir}")

    scenario_filter = [s.strip() for s in args.scenario.split(",")] if args.scenario else None
    scenarios_dir = _QA_ROOT / "scenarios"

    # Load matched CSVs
    matched = _load_matched_csvs(run_dir, scenario_filter, scenarios_dir)

    # Linked-pair scenarios (S9) never produce a *_matched.csv — their truth
    # rows span two cycles and are scored directly from truth.csv + the raw
    # ALL.TXT logs (see LINKED_PAIR_SCENARIOS' docstring) — so their presence
    # alone is enough to proceed even when `matched` is otherwise empty.
    _pair_scenario_ids = [
        sid for sid in sorted(LINKED_PAIR_SCENARIOS)
        if (not scenario_filter or sid in scenario_filter)
        and _hcr_load_pair_truth(run_dir, sid)
    ]

    if not matched and not _pair_scenario_ids:
        sys.exit(f"ERROR: no *_matched.csv files found in {run_dir}")

    if matched:
        print(f"Analysing: {', '.join(sorted(matched.keys()))}")
    if _pair_scenario_ids:
        print(f"Analysing (linked-pair): {', '.join(_pair_scenario_ids)}")

    git_sha = _git_sha()
    continuous_results: dict = {}
    kappa_results: dict = {}
    fp_results: dict = {}               # Gate A — S5 parts 0/1 (AWGN), ratified 6% UB
    fp_narrowband_results: dict = {}    # Check B — S5 parts 2/3 (narrowband), FAIL iff events >= 2
    bias_results: dict = {}

    # Load scenario metadata upfront — used for per-scenario correction fields
    # (e.g. wsjt_dt_correction_s in S3) and S7 part metadata.
    scenario_meta = _load_scenario_meta(scenarios_dir)

    # --- Continuous scenarios ---
    for scen_id, df in matched.items():
        if scen_id not in CONTINUOUS_SCENARIOS:
            continue
        response = RESPONSE_VAR[scen_id]
        tol_half = TOLERANCE_HALF[scen_id]

        # S3 — apply WSJT-X DT convention correction before ANOVA.
        # WSJT-X reports DT relative to the nominal FT8 TX start rather than the
        # UTC slot boundary; the scenario JSON carries wsjt_dt_correction_s (≈ +0.55 s)
        # to remove this calibration offset from the Reproducibility term.
        s3_correction_applied = False
        if scen_id == "S3":
            s3_meta = scenario_meta.get("S3", {})
            correction_s = s3_meta.get("wsjt_dt_correction_s")
            if correction_s is not None:
                df = _apply_wsjt_dt_correction(df, float(correction_s))
                print(
                    f"  S3: WSJT-X DT correction applied (+{correction_s} s) "
                    f"- removes ~-0.55 s convention offset from SS_appraiser"
                )
                s3_correction_applied = True

        anova = _two_way_anova(df, response, scen_id)
        if anova is None:
            continuous_results[scen_id] = None
            continue
        metrics = _derived_metrics(anova, tol_half)
        continuous_results[scen_id] = {
            "anova": anova,
            "metrics": metrics,
            "response": response,
            "tol_half": tol_half,
            "s3_correction_applied": s3_correction_applied,
        }
        print(f"  {scen_id}: %GR&R={metrics['pct_contribution_grr']:.1f}%  ndc={metrics['ndc']}")
        # Six-panel chart
        png = _plot_grr_panel(df, response, anova, metrics, scen_id, run_dir)
        print(f"    -> {png.name}")

    # --- S1 Bias & Linearity ---
    if "S1" in matched and continuous_results.get("S1") is not None:
        bias_results = _bias_linearity(matched["S1"], run_dir)
        for appr, info in bias_results.items():
            print(f"  S1 bias ({appr}): {info['mean_bias']:+.2f} dB  slope={info['slope']:.3f}")

    # --- Decode-rate scenarios (S3b, S1b, ...) ---
    decode_rate_results: list[dict] = []
    for sid in sorted(DECODE_RATE_SCENARIOS):
        if sid not in matched:
            continue
        cfg = DECODE_RATE_CONFIG[sid]
        dr = _analyse_decode_rate(
            matched[sid], sid, run_dir,
            part_var=cfg["part_var"],
            part_label=cfg["part_label"],
        )
        decode_rate_results.append(dr)
        for appr in APPRAISERS:
            rate = dr["overall"].get(appr, float("nan"))
            print(f"  {sid} decode rate ({appr}): {_fmt_num(rate)}%  (informational)")

    # --- Attribute scenarios ---
    # False-positive rate (S5) — S5-GATE-SIZING Amendment 1 (2026-09-06, PO ruling
    # Option 3): TWO separate checks, each on its own part_index-scoped slice of
    # matched["S5"], each with its own denominator. NEVER pool these into one rate
    # or one combined S5 verdict — that pooling is exactly the defect this design
    # removes (see the constants' comment above and s5_narrowband_exposure_verify.py).
    if "S5" in matched:
        s5_df = matched["S5"]

        # Gate A — AWGN (parts 0/1), ratified §10 6% UB gate, unchanged population
        # definition (only R&R-009's default-battery restriction is superseded).
        fp_results = _fp_rate_for_parts(s5_df, S5_AWGN_PARTS)
        for appr, info in fp_results.items():
            n_events = info.get("n_fp_events", float("nan"))
            if isinstance(n_events, float) and math.isnan(n_events):
                print(f"  S5 Gate A FP ({appr}): undefined (no AWGN slots injected)")
                continue
            n_slots     = info["n_slots"]
            event_rate  = info["event_rate"]
            decode_rate = info["decode_rate"]
            ub95        = info["event_rate_ub95"]
            print(
                f"  S5 Gate A FP events ({appr}): {int(n_events)}/{n_slots} slots "
                f"(event rate {_fmt_num(event_rate)}%; 95% UB {_fmt_num(ub95)}%; "
                f"decode rate {_fmt_num(decode_rate)}%)"
            )

        # Check B — narrowband (parts 2/3), coverage net, FAIL iff events >= 2 on
        # its own 60-slot denominator (A1.2). Absent entirely from a run that only
        # exercised parts 0/1 (e.g. a targeted --parts 0,1 recheck) — _fp_rate's
        # own n_slots==0 branch reports NaN, handled the same way as Gate A above.
        fp_narrowband_results = _fp_rate_for_parts(s5_df, S5_NARROWBAND_PARTS)
        for appr, info in fp_narrowband_results.items():
            n_events = info.get("n_fp_events", float("nan"))
            if isinstance(n_events, float) and math.isnan(n_events):
                print(f"  S5 Check B FP ({appr}): undefined (no narrowband slots injected)")
                continue
            n_slots = info["n_slots"]
            print(
                f"  S5 Check B FP events ({appr}): {int(n_events)}/{n_slots} slots "
                f"(FAIL iff >= {THRESH_S5_NARROWBAND_FAIL})"
            )

    # Pooled attribute agreement (S4 positives + S5 negatives) — advisory κ.
    attr_results: dict | None = None
    if "S4" in matched or "S5" in matched:
        attr_results = _attribute_agreement(matched, run_dir)
        kappa_results = attr_results["kappa"]
        for label, info in kappa_results.items():
            print(f"  Kappa {label}: {_fmt_num(info.get('kappa', float('nan')), '.3f')} (advisory)")
        # Informational only (rr-density-qrm-scenario / R&R-007) — never passed to
        # _collect_verdicts, so it cannot affect the overall verdict.
        for label, info in attr_results["restricted"]["kappa"].items():
            print(
                f"  Kappa {label} (SNR>={S4_DECODABLE_SNR_FLOOR_DB:g}dB only): "
                f"{_fmt_num(info.get('kappa', float('nan')), '.3f')} (informational)"
            )

    # --- S5 Gate A trailing-window gate (R&R-011) ---
    # Only for a full, unfiltered battery: the window is persisted via
    # trend.csv, and a --scenario-filtered run must not touch that series
    # (same reasoning as the trend-append guard below).
    s5_window_result: dict | None = None
    if "S5" in matched and not scenario_filter:
        s5_window_result = _s5_window_gate(
            _QA_ROOT, git_sha, fp_results, attr_results, matched["S5"],
        )
        status = s5_window_result.get("status")
        if status == "VOID":
            print(f"  S5 window gate: VOID (ROW {s5_window_result['row']}) — "
                  f"{s5_window_result['detail']}")
        elif status == "INFO":
            print(f"  S5 window gate: INFO — window not yet full "
                  f"({s5_window_result['k']}/{s5_window_result['n']} of "
                  f"{S5_WINDOW_SLOTS} slots)")
        elif status == "SCORED":
            w, c, loo = s5_window_result["window"], s5_window_result["change"], s5_window_result["loo"]
            print(f"  Gate A-W: {w['k']}/{w['n']} = {_fmt_num(100.0*w['k']/w['n'])}% "
                  f"95% UB {_fmt_num(w['ub'])}% -> {w['verdict']}"
                  f"{' [FRAGILE]' if loo['fragile'] else ''}")
            print(f"  Gate A-Δ: {c['k1']}/{c['n1']} vs {c['k0']}/{c['n0']} "
                  f"Fisher(greater) p={_fmt_num(c['p'], '.4f')} -> {c['verdict']}")

    # --- S7 compounding / co-channel overlap ---
    s7_results: dict | None = None
    if "S7" in matched:
        s7_results = _analyse_compounding(matched["S7"], scenario_meta.get("S7"), run_dir)
        print(
            "  S7 recovery (per-message): "
            f"WSJT-X {_fmt_num(s7_results['overall'].get('WSJT-X', float('nan')))}%  "
            f"OpenWSFZ {_fmt_num(s7_results['overall'].get('OpenWSFZ', float('nan')))}%"
        )

    # --- S8 realistic band scene (informational, no gate) ---
    s8_results: dict | None = None
    if "S8" in matched:
        s8_results = _analyse_band_scene(matched["S8"], scenario_meta.get("S8"), run_dir)
        print(
            "  S8 holistic decode rate: "
            f"WSJT-X {_fmt_num(s8_results['overall'].get('WSJT-X', float('nan')))}%  "
            f"OpenWSFZ {_fmt_num(s8_results['overall'].get('OpenWSFZ', float('nan')))}%"
            "  (informational)"
        )

    # --- S9 hashed-callsign cross-cycle resolution (linked-pair, informational) ---
    hcr_results: dict | None = None
    for sid in _pair_scenario_ids:
        hcr_results = _analyse_hashed_callsign_resolution(run_dir, sid)
        if hcr_results is None:
            continue
        for appr in APPRAISERS:
            r = hcr_results["rates"][appr]
            print(
                f"  {sid} hashed-callsign resolution ({appr}): "
                f"announce decoded {_fmt_num(r['announce_decode_rate'])}% "
                f"({r['n_announce_decoded']}/{r['n_pairs']})  "
                f"resolved {_fmt_num(r['resolution_rate'])}% of announce-decoded  "
                "(informational)"
            )

    # --- Verdicts ---
    verdict_rows, overall, fails, notes = _collect_verdicts(
        continuous_results, kappa_results, fp_results, bias_results,
        fp_narrowband_results=fp_narrowband_results,
        s5_window_result=s5_window_result,
    )

    # --- Write report ---
    report_path = _write_report(
        run_dir, git_sha, continuous_results, kappa_results,
        fp_results, bias_results, verdict_rows, overall, fails,
        notes=notes,
        s7_results=s7_results,
        s8_results=s8_results,
        attr_results=attr_results,
        decode_rate_results=decode_rate_results,
        hcr_results=hcr_results,
        fp_narrowband_results=fp_narrowband_results,
        s5_window_result=s5_window_result,
    )
    print(f"\nReport written: {report_path}")
    print(f"Overall verdict: {overall}")

    if fails:
        print("\n[!] DEFECT NOTICES:")
        for f in fails:
            print(f"  FAIL — {f}")

    # --- Trend CSV ---
    # Item 2, 2026-08-27 Architect work order: a --scenario-filtered run is by
    # definition not a full battery, so it must not append a row to the
    # historical trend series -- silently appending from an ad-hoc/partial
    # regeneration corrupts a series everyone else reads (observed this
    # session: an S8-only regen into a scratch directory dirtied the real
    # trend.csv; caught and reverted by hand only because someone looked).
    # Safe-by-default: suppression is automatic, not an opt-in flag.
    if scenario_filter:
        print(
            f"Trend row NOT appended -- this was a --scenario-filtered run "
            f"({', '.join(scenario_filter)}), not a full battery."
        )
    else:
        _append_trend(_QA_ROOT, run_dir, git_sha, continuous_results,
                      kappa_results, fp_results, bias_results)
        print(f"Trend row appended: {_QA_ROOT / 'trend.csv'}")


if __name__ == "__main__":
    main()
