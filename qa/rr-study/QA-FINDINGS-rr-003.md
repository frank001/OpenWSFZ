# QA Findings — `fix/rr-003-s3-dt-redesign`

**Review date:** 2026-06-06
**Branch:** `fix/rr-003-s3-dt-redesign`
**Commits reviewed:** `007f027`, `0523ef7`, `d8c3450`
**Reviewed by:** QA
**Status:** Conditional approval — 1 medium defect must be addressed before S3b is run; 2 minor items at developer discretion.

---

## D-001 — Medium — S3b generator produces silent invalid data if run

**File:** `harness/run_scenario.py` (and `scenarios/s3b-dt-boundary.json`)
**Commit introduced:** `d8c3450`

### What is wrong

`s3b-dt-boundary.json` defines parts with `dt_s` values from `0.0` down to `−2.7 s`. Two things must be true for a negative-DT trial to be physically meaningful:

1. The synthesised audio must begin before the slot boundary — but `modulator.py` line 66 silently clamps the sample offset to zero:
   ```python
   start = max(0, min(start, len(slot) - len(signal)))
   ```
   Any `dt_s < 0` therefore renders identical audio to `dt_s = 0`.

2. Playback must be armed `|dt_s|` seconds *before* the cycle boundary — but `run_scenario.py` always waits for `_next_cycle_boundary()` regardless of scenario.

Neither is implemented. `run_scenario.py` has no `is_s3b` flag and falls through to the `else` (single-signal) branch, so S3b silently executes as a series of DT=0 renders played at the normal boundary. The resulting decode rates will be near-100% for every part, which is the *opposite* of what the study is designed to measure. No warning is printed; no error is raised.

### Required fix

Pick **one** of the following:

**Option A — Guard at the generator (recommended):**
Add an early exit in `_run()` that detects S3b and prevents an inadvertent run:

```python
# In _run(), after scenario_id is set:
if scenario_id == "S3b":
    sys.exit(
        "ERROR: S3b negative-DT playback is not yet implemented.\n"
        "The playback layer must arm |dt_s| seconds early per part.\n"
        "See harness_note in scenarios/s3b-dt-boundary.json."
    )
```

Remove the guard once the early-playback timing is implemented.

**Option B — Raise a GitHub issue:**
Open a GitHub issue (e.g. `frank001/OpenWSFZ#N`) and add its reference to the `harness_note` field in `s3b-dt-boundary.json` with an explicit `"status": "not yet runnable"` marker. This makes the gap tracked and visible without blocking the merge.

### What a full implementation requires

When this is eventually built out, the changes will be:

- `synth/modulator.py`: allow negative `dt_s` to shift the signal to the *end* of a slot-sized buffer rather than clamping to the start. Or, more accurately, the negative-DT signal occupies the last `signal_length - |dt_s| * fs` samples of the buffer and the first `|dt_s| * fs` samples of the *next* buffer. The harness would need to split the render across two slots or pad.
- `harness/run_scenario.py`: when `is_s3b`, subtract `abs(part["dt_s"])` seconds from `_next_cycle_boundary()` before arming playback.

Both are non-trivial. The guard in Option A is the correct short-term action.

---

## D-002 — Minor — `DECODE_RATE_SCENARIOS` constant is dead code

**File:** `harness/analyse.py`, line 42
**Commit introduced:** `d8c3450`

### What is wrong

```python
DECODE_RATE_SCENARIOS = {"S3b"}
```

This constant is defined but never referenced anywhere in the file. The S3b dispatch uses a bare string literal instead:

```python
# line 1412
if "S3b" in matched:
```

A developer reading the constants block will assume `DECODE_RATE_SCENARIOS` governs S3b dispatch, which it does not.

### Required fix

Either use the constant:

```python
if any(sid in matched for sid in DECODE_RATE_SCENARIOS):
    scen_id = next(sid for sid in DECODE_RATE_SCENARIOS if sid in matched)
    s3b_results = _analyse_decode_rate(matched[scen_id], scen_id, run_dir)
```

Or, if the hardcoded `"S3b"` string is intentional (S3b is the only planned decode-rate scenario), remove the unused constant.

---

## D-003 — Minor — No test for the modulator's negative-DT clamping contract

**File:** `tests/test_modulator.py`
**Commit introduced:** `d8c3450` (via `s3b-dt-boundary.json` `harness_note`)

### What is wrong

`s3b-dt-boundary.json` `harness_note` explicitly relies on the modulator clamping negative `dt_s` to zero:

> "The synthesiser modulate() offset is clamped to 0 for negative values"

This behaviour exists in `modulator.py` line 66 but is not exercised by any test. If someone changes that line to support true negative offsets in the future (as D-001's full implementation would require), there is no regression guard to alert them that the S3b scenario relies on the old behaviour.

### Required fix

Add the following test to `tests/test_modulator.py`:

```python
def test_negative_dt_is_clamped_to_zero():
    """Negative dt_s must render identically to dt_s=0 (harness_note contract for S3b)."""
    tones = [0] * NUM_SYMBOLS
    for start in (0, 36, 72):
        tones[start:start + 7] = [3, 1, 4, 0, 6, 5, 2]

    at_zero = modulator.modulate(tones, base_freq_hz=1500.0, dt_s=0.0)
    at_neg  = modulator.modulate(tones, base_freq_hz=1500.0, dt_s=-1.5)

    assert np.array_equal(at_zero, at_neg), (
        "Negative dt_s must be clamped to 0 — S3b harness_note relies on this contract."
    )
```

Note: when D-001 is fully implemented (true negative-DT playback), this test will need to be **removed or updated**, as the clamping behaviour will no longer be correct. At that point D-003 and D-001 are resolved together.

---

## Summary

| ID | Severity | File(s) | Action required |
|---|---|---|---|
| D-001 | **Medium** | `run_scenario.py`, `s3b-dt-boundary.json` | Guard or track before S3b is ever run |
| D-002 | Minor | `harness/analyse.py` line 42 | Use or remove `DECODE_RATE_SCENARIOS` |
| D-003 | Minor | `tests/test_modulator.py` | Add negative-DT clamping test |

The core R&R-003 redesign (S3 positive-DT restriction and WSJT-X DT correction in `analyse.py`) is correct and approved. D-001 is the only finding that carries operational risk; D-002 and D-003 are code quality items.
