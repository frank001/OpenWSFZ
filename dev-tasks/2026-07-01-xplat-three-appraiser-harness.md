# Developer Handoff — Cross-Platform R&R: Three-Appraiser Harness Extension

**Date:** 2026-07-01  
**Branch:** `chore/xplat-rr-three-appraiser`  
**Context:** The 2026-07-01 pilot R&R run (`results/2026-07-01-b03998f`) compared
Windows daemon vs Linux/WSL2 daemon as two appraisers. The Captain has directed
that WSJT-X be added as a third appraiser, allowing separation of the decoder
effect (libft8 vs Fortran) from the audio-chain effect (ft8loopback vs Voicemeeter).
All three appraisers receive audio from the same Voicemeeter Out B2 device (Windows
WASAPI shared mode), so WSJT-X vs Windows daemon is a pure decoder comparison.

---

## 1. Context

The existing xplat harness lives in `qa/rr-study/harness/`:

| File | Role |
|---|---|
| `run_study_xplat.py` | Orchestrator — drives WSL2 synthesiser, collects logs |
| `harness/matcher_xplat.py` | Matches decode logs against truth per scenario |
| `harness/analyse_xplat.py` | GR&R ANOVA, bias gates, report writer |
| `harness/common.py` | `parse_all_txt()` — parses ALL.TXT format (shared) |

`APPRAISERS = ("Windows", "Linux")` is the sole source of truth for appraiser
identity in both matcher and analyser. Extending to three appraisers requires
changing this tuple and all downstream code that assumes exactly two entries.

**WSJT-X ALL.TXT location:** `C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT`
(confirmed by Captain). The file is appended across WSJT-X sessions; the
matcher's cycle_utc filter handles this correctly.

**WSJT-X DT convention:** WSJT-X reports DT using its own convention (offset
from the nominal 15-second cycle boundary). The original `harness/matcher.py`
applied a `WSJT_DT_CORRECTION` constant; check that file before finalising the
S3 DT-bias gate logic for the WSJT-X appraiser. If the correction is still
needed, apply it in `matcher_xplat.py` only for the `"WSJT-X"` appraiser path.

---

## 2. Branch name

`chore/xplat-rr-three-appraiser`

---

## 3. Actions

### 3.1 `run_study_xplat.py` — add WSJT-X log collection

**Location:** near the top of the file alongside the existing `_WIN_ALL_TXT` and
`_LINUX_ALL_TXT` constants.

Add:
```python
# WSJT-X ALL.TXT — appended across sessions; matcher filters by cycle_utc
_WSJT_ALL_TXT = Path(r"C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT")
```

In the log-collection block (currently copies Windows and Linux logs to the run
directory), add:
```python
if _WSJT_ALL_TXT.exists():
    shutil.copy(_WSJT_ALL_TXT, run_dir / "wsjt-all.txt")
    print(f"  Copied WSJT-X   → wsjt-all.txt")
else:
    print(f"  WARNING: WSJT-X ALL.TXT not found at {_WSJT_ALL_TXT} — skipping")
```

In the per-scenario matcher invocation, add `--wsjt wsjt-all.txt` (or equivalent
flag, once matcher_xplat.py is updated to accept it).

Add a WSJT-X pre-run check to the `_preflight()` function (or equivalent):
```python
if not _WSJT_ALL_TXT.exists():
    print(f"  WARNING: WSJT-X ALL.TXT not found — WSJT-X will be skipped")
```

### 3.2 `harness/matcher_xplat.py` — add WSJT-X as third appraiser

**Change 1:** APPRAISERS tuple
```python
APPRAISERS = ("Windows", "Linux", "WSJT-X")
```

**Change 2:** `_resolve_paths` — add `wsjt_path` resolution:
```python
def _resolve_paths(args):
    ...
    wsjt_path = run_dir / "wsjt-all.txt" if args.run_dir else None
    if args.wsjt:
        wsjt_path = Path(args.wsjt)
    # wsjt_path may be None/missing — treat WSJT-X as optional
    return truth_path, windows_path, linux_path, wsjt_path
```

**Change 3:** Argument parser — add `--wsjt` optional argument.

**Change 4:** Main body — add WSJT-X matching:
```python
wsjt_rows = []
if wsjt_path and wsjt_path.exists():
    wsjt_records, wsjt_skipped = parse_all_txt(wsjt_path)
    print(f"  WSJT-X:   {len(wsjt_records)} FT8 lines parsed, {wsjt_skipped} skipped")
    wsjt_rows = _match_appraiser(truth_rows, wsjt_records, "WSJT-X", scenario_id)
else:
    print(f"  WSJT-X:   not available — skipped")
all_rows = win_rows + lin_rows + wsjt_rows
```

**Change 5 (if needed):** WSJT-X DT correction. Check `harness/matcher.py` for
`WSJT_DT_CORRECTION`. If it applies to the xplat study context, apply it to the
`wsjt_records` timestamps before calling `_match_appraiser`.

**Frequency tolerance:** The existing `XPLAT_FREQ_TOLERANCE_HZ = 20.0` override
applies to all appraisers. This is appropriate since WSJT-X may also have a
slight frequency offset (WSJT-X uses its own FFT and may report differently). If
WSJT-X consistently matches within 4 Hz, the wider tolerance is harmless.

### 3.3 `harness/analyse_xplat.py` — generalise to N appraisers

**Change 1:** APPRAISERS tuple
```python
APPRAISERS = ("Windows", "Linux", "WSJT-X")
```

The majority of the analyser code already iterates over `APPRAISERS` rather than
hard-coding two names. Audit each function for hard-coded `"Windows"` / `"Linux"`
references; replace with `APPRAISERS[0]` / `APPRAISERS[1]` where semantically
correct, or loop over `APPRAISERS` where all appraisers are treated equally.

**Change 2:** `_platform_bias_metrics` — currently computes `Linux − Windows`
only. Extend to compute all N×(N-1)/2 pairwise biases. Suggested signature:

```python
def _platform_bias_metrics_all(
    df_matched: pd.DataFrame,
    response: str,
    appraisers: tuple[str, ...]
) -> dict[tuple[str, str], dict]:
    """Returns {(appraiser_a, appraiser_b): bias_dict} for all pairs."""
```

Gates to apply (STUDY-SPEC-XPLAT §8.1):
- `Windows − WSJT-X`: same thresholds as Linux-Windows (SNR ≤ 1 dB, freq ≤ 2 Hz, DT ≤ 0.1 s)
- `Linux − Windows`: existing thresholds unchanged
- `Linux − WSJT-X`: same thresholds

**Change 3:** `_bias_linearity` — currently plots Windows and Linux as separate
series. Extend to plot all three appraisers.

**Change 4:** `_platform_bias_chart` — extend to plot pairwise SNR bias.
Suggested: one chart per pair, or three series on one chart.

**Change 5:** `_dt_jitter_timeseries` — extend to show all pairwise DT
differences, or plot three series (one per appraiser) vs time.

**Change 6:** `_fp_rate`, `_fp_parity_fisher` — `_fp_rate` already iterates
over `APPRAISERS` so will work with 3. `_fp_parity_fisher` computes a single
Windows vs Linux Fisher test; extend to all pairwise combinations.

**Change 7:** `_attribute_agreement` — iterates over `APPRAISERS`; should work
with 3. The between-appraiser kappa currently computes one pair; extend to all
pairwise combinations and report separately.

**Change 8:** `_mcnemar_test` — currently pivots on two appraisers. Generalise
to all pairs: compute McNemar for each pair `(A, B)` with discordants `n_AB`
(A decodes, B does not) and `n_BA` (B decodes, A does not).

**Change 9:** `_write_report` and `_collect_verdicts` — extend verdict rows
and section 3 report content to cover all pairwise bias gates and McNemar
results. Use a loop over `itertools.combinations(APPRAISERS, 2)`.

**Change 10:** `_TREND_COLUMNS_XPLAT` — add WSJT-X columns:
```python
"pct_grr_snr_wsjt", "fp_events_wsjt",
"win_wsjt_snr_bias_db", "linux_wsjt_snr_bias_db",
```

### 3.4 `harness/common.py` — verify WSJT-X ALL.TXT compatibility

Run `parse_all_txt` against a live WSJT-X `ALL.TXT` from
`C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT`. Confirm:
- UTC timestamps parse correctly
- Frequency (Hz), SNR (dB), DT (s), message text are extracted
- No systematic parse failures or skipped lines

If WSJT-X uses a slightly different column layout or date format in newer
versions, update the parser to handle both.

### 3.5 Smoke-test update (`smoke_test_null_sink.py`)

Add WSJT-X as a third check in the smoke test:
```python
_WSJT_ALL_TXT = Path(r"C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT")
...
wsjt_hits = _check_log(_WSJT_ALL_TXT, "WSJT-X")
```

Update the verdict logic to report PASS/PARTIAL/FAIL across all three appraisers.

---

## 4. Acceptance criteria

The QA engineer will verify the following before merging:

1. **`run_study_xplat.py`** — `wsjt-all.txt` is copied to the run directory
   after all scenarios complete; a WARNING (not an error) is emitted if WSJT-X
   is not running and `ALL.TXT` is absent.

2. **`matcher_xplat.py`** — running against a test run directory produces
   `S*_matched.csv` files containing rows for all three appraisers; `_print_summary`
   shows Windows / Linux / WSJT-X match counts.

3. **`analyse_xplat.py`** — the generated `report.md` contains:
   - Pairwise platform bias tables for all 3 pairs
   - Kappa table with all pairwise entries
   - McNemar result for each pair
   - All three appraisers in the S7 recovery table and chart

4. **Backward compatibility** — if `wsjt-all.txt` is absent from a run
   directory, the analyser runs cleanly with the two appraisers present
   (graceful degradation, not a crash).

5. **Unit tests** — at least one test covering the 3-appraiser ANOVA path
   (synthetic matched CSV with three appraiser names) and one test confirming
   graceful degradation when WSJT-X rows are absent.

---

## 5. References

- Pilot run report: `qa/rr-study/results/2026-07-01-b03998f/report.md`
- STUDY-SPEC-XPLAT: `qa/rr-study/STUDY-SPEC-XPLAT.md`
- RUNBOOK §5: `qa/rr-study/RUNBOOK.md`
- Original 2-appraiser xplat harness: commit `e94beff` (2026-07-01)
- Original WSJT-X vs OpenWSFZ harness (reference for DT correction):
  `qa/rr-study/harness/matcher.py`
