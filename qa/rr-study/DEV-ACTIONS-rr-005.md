# Developer Action Plan — R&R-005 and Outstanding Study Items

**Issued by:** QA  
**Date:** 2026-06-06  
**Triggered by:** Run `4c34ef6` — S1 %GR&R = 32.0% (FAIL), ndc = 2 (MARGINAL)  
**Primary reference:** `RR-005.md`  
**Overall study status:** ❌ FAIL — blocked on S1 SNR ladder redesign

---

## Situation Summary

Run `4c34ef6` produced a severe S1 regression. The root cause is not a product defect —
it is a study design flaw: the S1 ladder extends into the sub-threshold SNR range where
neither application decodes reliably. Threshold misses at −24 to −15 dB create an
unbalanced ANOVA, inflating Reproducibility σ² from 3.63 to 26.10 and clamping
Repeatability to 0.00. The fix is a redesign of the scenario, not a change to the
product decoder.

Everything else in run `4c34ef6` is healthy:

| Scenario | Metric | Value | Verdict |
|---|---|---|---|
| S2 (frequency) | %GR&R | 0.0% | ✅ PASS |
| S3 (DT offset) | %GR&R | 3.8% | ✅ PASS |
| S4/S5 (attribute) | κ | 1.000 | ✅ PASS |
| S4/S5 (FP rate) | FP | 0.0% | ✅ PASS |
| S1 (SNR) | %GR&R | **32.0%** | ❌ **FAIL** |

---

## Required Changes

### Change 1 — `scenarios/s1-snr-ladder.json` — Restrict to reliable decode range

**Priority:** Blocking  
**Why:** The current 10-part ladder spans {−24 … +3} dB. At the four lowest levels both
apps miss trials non-deterministically, breaking the balanced ANOVA. The ladder must be
moved entirely above the decode floor.

**Required design** (10 parts at 3 dB spacing, both apps ≥ 95% decode at every part):

```json
"parts": [
  {"part_index": 0, "snr_db": -12},
  {"part_index": 1, "snr_db":  -9},
  {"part_index": 2, "snr_db":  -6},
  {"part_index": 3, "snr_db":  -3},
  {"part_index": 4, "snr_db":   0},
  {"part_index": 5, "snr_db":   3},
  {"part_index": 6, "snr_db":   6},
  {"part_index": 7, "snr_db":   9},
  {"part_index": 8, "snr_db":  12},
  {"part_index": 9, "snr_db":  15}
]
```

Update `_comment` and `description` to record the redesign date and reference R&R-005.

> **Note on upper-range saturation:** Parts at ≥ +9 dB will have near-zero within-cell
> variance (both apps always decode and report the same SNR). This is acceptable —
> zero-variance cells do not break the ANOVA; they simply contribute nothing to SS_error.
> The wide range remains valuable for the Bias & Linearity chart.

---

### Change 2 — `scenarios/s1b-snr-threshold.json` — New companion attribute scenario

**Priority:** Blocking (accompanies Change 1)  
**Why:** The four SNR levels excluded from the redesigned S1 ladder (−24 to −15 dB)
still carry useful information: they tell us *at what SNR the app stops decoding*. This
should be measured explicitly as a decode-rate (attribute) study, not silently discarded.

Create the file with the following structure:

```json
{
  "_comment": "S1b Low-SNR Threshold — decode-rate study for SNRs excluded from the redesigned S1 ladder (R&R-005).",
  "_format_version": "1",

  "id": "S1b",
  "name": "Low-SNR threshold",
  "response": "decode_rate",
  "description": "4 parts × 2 appraisers × 3 trials. Measures decode rate at SNRs excluded from the redesigned S1 ladder (-24 to -15 dB). Companion to S1; separates 'does it decode at this SNR?' from 'how accurately does it measure SNR?'. Raised by R&R-005 (2026-06-06).",

  "message_ids": ["MSG-01"],
  "fixed": {"base_freq_hz": 1500, "dt_s": 0.2},

  "analysis": "attribute_decode_rate",

  "parts": [
    {"part_index": 0, "snr_db": -24},
    {"part_index": 1, "snr_db": -21},
    {"part_index": 2, "snr_db": -18},
    {"part_index": 3, "snr_db": -15}
  ],

  "trials": 3,
  "seed_formula": "hash('S1b', part_index, trial_index)"
}
```

---

### Change 3 — `harness/analyse.py` — Generalise decode-rate analysis for S1b

**Priority:** Blocking (S1b cannot render a report without this)  
**Current state:** `_analyse_decode_rate()` and `_decode_rate_report_lines()` are
hard-coded for S3b: the x-axis label reads "True DT (s)", the chart draws a vertical
reference line at DT=0, and the report section header is "Negative-DT decode boundary".
S1b uses SNR as the part variable and requires none of these DT-specific elements.

Four targeted changes are required:

#### 3a — Add `DECODE_RATE_CONFIG` constant

Immediately below the existing `DECODE_RATE_SCENARIOS` set (line ~42), add:

```python
DECODE_RATE_SCENARIOS = {"S3b", "S1b"}   # extend existing line

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
}
```

#### 3b — Generalise `_analyse_decode_rate()`

Add `part_var: str = "true_dt_s"` and `part_label: str = "True DT (s)"` parameters.

- Replace every literal use of `"true_dt_s"` as a column key with `part_var`.
- In the `per_part` row dict, store the part value under the key `"part_val"` (not
  `"true_dt_s"`) so the render function can use it generically.
- In the chart: replace `ax.set_xlabel("True DT (s)")` with `ax.set_xlabel(part_label)`.
- Replace the unconditional `ax.axvline(0.0, ...)` with:
  ```python
  cfg = DECODE_RATE_CONFIG.get(scen_id, {})
  if cfg.get("chart_ref_line") is not None:
      ax.axvline(cfg["chart_ref_line"], color="grey", linestyle=":", lw=0.8)
  ```
- Add `"part_var"` and `"part_label"` to the returned dict.

#### 3c — Generalise `_decode_rate_report_lines()`

- Read `part_label` from `results["part_label"]`.
- Read `section_title` and `section_intro` from `DECODE_RATE_CONFIG[scen_id]`.
- Replace `r['true_dt_s']` in the table body with `r['part_val']`.
- Replace the hardcoded column header `"True DT (s)"` with `part_label`.

#### 3d — Update the dispatch loop in `main()`

The current dispatch handles only one decode-rate scenario (uses `next()`). Replace
with a loop:

```python
# OLD (lines ~1410–1455 region) — remove:
s3b_results: dict | None = None
if any(sid in matched for sid in DECODE_RATE_SCENARIOS):
    scen_id = next(sid for sid in DECODE_RATE_SCENARIOS if sid in matched)
    s3b_results = _analyse_decode_rate(matched[scen_id], scen_id, run_dir)
    ...

# REPLACEMENT:
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
```

Update the report-render call site similarly:

```python
# OLD:
if s3b_results:
    lines += _decode_rate_report_lines(s3b_results)

# REPLACEMENT:
for dr in decode_rate_results:
    lines += _decode_rate_report_lines(dr)
```

Also update the `_render_report()` signature: replace the `s3b_results` parameter with
`decode_rate_results: list[dict]`.

---

### Change 4 — `harness/run_study.py` — Add S1b to the run sequence

**Priority:** Blocking  

```python
SCENARIO_FILES = [
    _SCENARIOS / "s1-snr-ladder.json",
    _SCENARIOS / "s1b-snr-threshold.json",   # <-- insert here
    _SCENARIOS / "s2-freq-sweep.json",
    _SCENARIOS / "s3-dt-offset.json",
    _SCENARIOS / "s4-density.json",
    _SCENARIOS / "s5-noise.json",
    _SCENARIOS / "s7-compounding.json",
]

SCENARIO_IDS = ["S1", "S1b", "S2", "S3", "S4", "S5", "S7"]   # <-- add "S1b"
```

---

### Change 5 — `STUDY-SPEC.md` — Update §6 and §16

**Priority:** Blocking (documentation must reflect the live study)  

**§6 scenario table:**

- S1 row: append `(redesigned R&R-005, 2026-06-06)` to the parts description.
- Add S1b row immediately below S1:

| ID | Name | Response | Parts | Trials | Analysis |
|---|---|---|---|---|---|
| S1b | Low-SNR threshold | Decode rate | {−24, −21, −18, −15} dB; fixed freq=1500 Hz, DT=0.2 s | 3 | Per-SNR decode rate per appraiser; informational |

**§16 run history table:** add the `4c34ef6` row:

| Date | SHA | S1 verdict | S1 %GR&R | S1 ndc | S1 bias | S1b | Notes |
|---|---|---|---|---|---|---|---|
| 2026-06-06 | `4c34ef6` | ❌ FAIL | 32.0% | 2 | +1.10 dB / slope 0.036 | — | R&R-005 raised: S1 ANOVA contaminated by threshold misses. S3 redesign confirmed PASS (3.8%, ndc=7). S7 informational — see below. |

**§16 narrative:** add an R&R-005 sub-section parallel to the existing R&R-003 sub-section,
summarising the root cause (threshold misses → unbalanced ANOVA → Repeatability clamped
to 0.00, Reproducibility inflated ×7.2) and the prescribed fix.

---

## Acceptance Criteria

The implementation is complete when all of the following hold on the next run:

| Criterion | Required |
|---|---|
| S1 match rate (both apps) | ≥ 95% of 30 trials — no threshold misses |
| S1 Repeatability σ² | > 0.00 (not clamped) |
| S1 %GR&R | < 30% (exit fail); target < 10% (PASS) |
| S1 ndc | ≥ 2 (exit fail); target ≥ 5 (PASS) |
| S1b runs without error | `run_study.py` completes S1b cleanly |
| S1b report section rendered | `report.md` contains S1b per-SNR decode-rate table and chart |
| S3b unaffected | S3b decode-rate analysis still renders correctly (regression guard) |
| `analyse.py` unit tests | All pass, no regressions |

---

## Informational — S7 Co-Channel Gap (No Action Required from Developer)

Run `4c34ef6` S7 results show a material performance gap in the co-channel family:

| Family | WSJT-X | OpenWSFZ |
|---|---|---|
| co_channel (equal SNR) | 38.1% | **0.0%** |
| capture (unequal SNR, weak signal) | 75.0% | **0.0%** |
| time_freq (same freq, time-shifted) | 100.0% | **44.4%** |
| near_collision (freq-offset) | 86.7% | 80.0% |

The co-channel and weak-capture gaps are architecturally significant: WSJT-X's
soft-decision LDPC decoder can partially recover a weaker signal that co-occupies a
tone; the OpenWSFZ pipeline (backed by the same `libft8.dll`) recovers 0% in those
families.

**This is noted as informational only.** No product defect has been raised; whether
to raise one is a Captain decision. The S7 scenario is informational by design — there
is no AIAG threshold for co-channel recovery. The data will accumulate across runs and
be reviewed at a natural milestone.

---

## Items Confirmed Resolved (No Further Action)

The following defects from `QA-FINDINGS-rr-003.md` were addressed in commit `bff3e8e`
and require no further work:

| ID | Description | Resolution |
|---|---|---|
| D-001 (Medium) | S3b generator produced silent invalid data if run | `sys.exit()` guard added to `run_scenario.py` |
| D-002 (Minor) | `DECODE_RATE_SCENARIOS` constant was dead code | Wired into S3b dispatch block |
| D-003 (Minor) | No test for negative-DT clamping contract | `test_negative_dt_is_clamped_to_zero()` added |

> **Note on D-001 / D-003 lifetime:** Both the `sys.exit()` guard and the clamping
> regression test are *temporary* — they exist only until full negative-DT playback is
> implemented in `modulator.py` and `run_scenario.py`. When that implementation lands,
> both must be removed or updated as part of the same change.

---

*Document issued by QA. Queries to the QA persona; implementation to the Developer persona.*
