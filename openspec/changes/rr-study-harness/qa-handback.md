# QA Handback — `rr-study-harness`

**Date:** 2026-06-06  
**Branch:** `feat/rr-study-harness`  
**Reviewer:** QA  
**Status:** RETURNED — fixes required before merge

---

## Overview

Six items require attention: two CI infrastructure failures (pre-existing, inherited from the
`feat/rr-study-synth` merge), two functional defects in the harness, and two minor nits.
Items marked 🔴 are **required**. Items marked 🟡 are **expected** in the same revision.
Items marked 🔵 are **nits** — fix them while you are in the file.

---

## Required Fixes

### CI-001 🔴 — macOS: wrong submodule path in `ci.yml`

**File:** `.github/workflows/ci.yml`

The macOS build step hard-codes `native/ft8_lib` but the submodule directory is
`native/ft8_lib_build`. The macOS runner fails immediately with
`cd: native/ft8_lib: No such file or directory` before dotnet is even invoked.

Find the macOS-only step (search for `cd native/ft8_lib`) and replace every occurrence
of `native/ft8_lib` within that step with `native/ft8_lib_build`:

```yaml
# BEFORE
- name: Build native macOS dylib (ARM64, Clang)
  if: runner.os == 'macOS'
  run: |
    cd native/ft8_lib
    ...
    clang ... ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c
    ...
    cp libft8.dylib ../../src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib

# AFTER
- name: Build native macOS dylib (ARM64, Clang)
  if: runner.os == 'macOS'
  run: |
    cd native/ft8_lib_build
    ...
    clang ... ../../src/OpenWSFZ.Ft8/Native/ft8_shim.c
    ...
    cp libft8.dylib ../../src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib
```

Only the `cd` path and any relative paths inside the step need changing; the clang
invocations and the `cp` destination are unaffected.

---

### CI-002 🔴 — Ubuntu: missing LICENSE file in `native/ft8_lib_build`

**File:** `native/ft8_lib_build/LICENSE` *(create this file)*

Gate G5 (`LicenseInventoryCheck`) fails with:

```
error: Native submodule 'ft8_lib_build' has no recognised licence file at './native/ft8_lib_build'.
```

The tool looks for one of: `LICENSE`, `LICENCE`, `LICENSE.txt`, `LICENCE.txt`.

Create `native/ft8_lib_build/LICENSE` containing the MIT licence for kgoba/ft8_lib.
The canonical text (from the upstream repository) is:

```
MIT License

Copyright (c) 2018-2023 Kārlis Goba

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Verify the text against the upstream repository before committing.

---

### H-001 🔴 — `compute_seed()` is not reproducible across sessions

**Files:** `qa/rr-study/harness/common.py` (fix here); `qa/rr-study/harness/run_scenario.py` (remove the dead env call)

**The problem:** `os.environ.setdefault("PYTHONHASHSEED", "0")` at the top of
`run_scenario.py` does nothing to `hash()` in the current process. Python's hash seed
is fixed at interpreter startup; modifying `os.environ` after that point only affects
child processes. Every session launched without `PYTHONHASHSEED=0` pre-set in the shell
will produce a **different** seed, generating **different** audio, silently breaking the
study's reproducibility guarantee.

**The fix:** replace Python's built-in `hash()` with a stable hash function that
is independent of `PYTHONHASHSEED`.

In `qa/rr-study/harness/common.py`, change `compute_seed()`:

```python
# BEFORE
def compute_seed(scenario_id: str, part_index: int, trial_index: int) -> int:
    raw = hash(f"{scenario_id},{part_index},{trial_index}")
    return abs(raw) % (2 ** 31)
```

```python
# AFTER
import hashlib

def compute_seed(scenario_id: str, part_index: int, trial_index: int) -> int:
    """Return the deterministic seed for a given (scenario, part, trial) triple.

    Uses SHA-256 so the result is stable across Python sessions regardless of
    PYTHONHASHSEED. The 2**31 modulus keeps seeds in numpy's default int32 range.
    """
    key = f"{scenario_id},{part_index},{trial_index}".encode("utf-8")
    return int(hashlib.sha256(key).hexdigest(), 16) % (2 ** 31)
```

Also update the module docstring on line 4 — remove the `(PYTHONHASHSEED=0 required)`
note since it no longer applies.

In `qa/rr-study/harness/run_scenario.py`, remove the now-redundant lines 16–18:

```python
# REMOVE these three lines entirely:
# Set PYTHONHASHSEED=0 FIRST so that compute_seed() is stable across sessions.
import os
os.environ.setdefault("PYTHONHASHSEED", "0")
```

`os` is still needed elsewhere in the file — keep the regular `import os` that appears
later with the other stdlib imports; just remove the early block and its comment.

---

### H-002 🔴 — S4 matching never produces a hit

**File:** `qa/rr-study/harness/matcher.py`, lines ~164–171 inside `_match_appraiser()`

**The problem:** `run_scenario.py` writes S4 truth rows with `message_text` equal to a
semicolon-joined pool string, e.g.:

```
CQ Q1ABC FN42; CQ DX Q9XYZ EN52; Q9ZZZ Q8DEF EN52
```

Inside `_match_appraiser()`, the S4/S5 branch compares a single decoded record against
that joined string:

```python
if not true_freq_str:
    if _text_matches(cand.message, truth_msg):   # "CQ Q1ABC FN42" == "CQ Q1ABC FN42; ..." → False
```

A decoded record always has a single message; the joined string never matches it.
**Every S4 part will always be a miss**, and Kappa for S4 will be meaningless.

S5 (where `truth_msg` is `""`) is unaffected — the empty-string comparison is
intentional for signal-free slots and should be preserved.

**The fix:** split the joined truth message and test membership for S4:

```python
# BEFORE
if not true_freq_str:
    # S4 or S5 — just check any message match within the slot
    if _text_matches(cand.message, truth_msg):
        consumed.add((cycle_dt, idx))
        output_rows.append(_matched_row(truth, appraiser, scenario_id, cand))
        match_found = True
        break
```

```python
# AFTER
if not true_freq_str:
    if truth_msg == "":
        # S5: signal-free slot — nothing is expected; no match possible
        pass
    else:
        # S4: truth_msg is a "; "-joined pool of individual messages.
        # A candidate matches if its decoded text equals any one pool entry.
        pool_msgs = [m.strip() for m in truth_msg.split(";")]
        if any(_text_matches(cand.message, m) for m in pool_msgs):
            consumed.add((cycle_dt, idx))
            output_rows.append(_matched_row(truth, appraiser, scenario_id, cand))
            match_found = True
            break
```

---

## Expected Fixes (same revision)

### M-001 🟡 — S5 FP rate uses wrong denominator

**File:** `qa/rr-study/harness/analyse.py`, `_fp_rate()` function

The denominator `n_total = len(sub)` includes both the truth-miss rows (Pass 1) and the
FP rows (Pass 2), making the FP rate smaller than it should be. The correct denominator
is the number of signal-free cycles, i.e. the truth rows alone. There is also a dead
variable (`total_cycles_df`) that is computed but never referenced.

```python
# BEFORE
def _fp_rate(df_matched: pd.DataFrame) -> dict[str, float]:
    results: dict[str, float] = {}
    total_cycles_df = df_matched[df_matched["false_positive"] == False]  # ← never used
    for appr in APPRAISERS:
        sub = df_matched[df_matched["appraiser"] == appr]
        n_fp = int((sub["false_positive"] == True).sum())
        n_total = len(sub)                                                # ← wrong
        if n_total == 0:
            print(f"WARNING: S5 — zero app-log rows for {appr}; FP rate undefined", file=sys.stderr)
            results[appr] = float("nan")
        else:
            results[appr] = 100.0 * n_fp / n_total
    return results
```

```python
# AFTER
def _fp_rate(df_matched: pd.DataFrame) -> dict[str, float]:
    """Compute false-positive rate per appraiser for S5.

    Denominator is the number of signal-free cycles (truth rows), not the
    total row count. FP rows from Pass 2 are the numerator.
    """
    results: dict[str, float] = {}
    for appr in APPRAISERS:
        sub = df_matched[df_matched["appraiser"] == appr]
        n_fp = int((sub["false_positive"] == True).sum())
        n_cycles = int((sub["false_positive"] == False).sum())
        if n_cycles == 0:
            print(f"WARNING: S5 — zero signal-free cycles for {appr}; FP rate undefined",
                  file=sys.stderr)
            results[appr] = float("nan")
        else:
            results[appr] = 100.0 * n_fp / n_cycles
    return results
```

---

## Nits (fix in the same pass)

### N-001 🔵 — Wrong return-type annotation on `_collect_verdicts`

**File:** `qa/rr-study/harness/analyse.py`, line ~581

The type hint says `-> tuple[list[...], str]` (2-tuple) but the function returns
`(verdict_rows, overall, fails)` — a 3-tuple. Fix the annotation:

```python
# BEFORE
) -> tuple[list[tuple[str, str, float | str, str]], str]:

# AFTER
) -> tuple[list[tuple[str, str, float | str, str]], str, list[str]]:
```

---

### N-002 🔵 — Dead comment in `analyse.py:main()`

**File:** `qa/rr-study/harness/analyse.py`, near the bottom of `main()`

Remove these two lines — the trend row was already appended above them:

```python
# --- Append trend row ---
# (already done above)
```

---

### N-003 🔵 — Status line prints `SNR= dB` for S4/S5

**File:** `qa/rr-study/harness/run_scenario.py`, line ~342

When `true_snr_db` is `""` the status line reads `SNR= dB`. Suppress the unit suffix
when the value is not applicable:

```python
# BEFORE
f"SNR={true_snr_db} dB  seed={seed}  cycle={cycle_utc_str}"

# AFTER
snr_str = f"SNR={true_snr_db} dB" if true_snr_db != "" else "SNR=N/A"
...
f"{snr_str}  seed={seed}  cycle={cycle_utc_str}"
```

---

## Checklist for resubmission

- [ ] CI-001: `ci.yml` — `native/ft8_lib` → `native/ft8_lib_build`
- [ ] CI-002: `native/ft8_lib_build/LICENSE` created with correct MIT text
- [ ] H-001: `compute_seed()` rewritten to use `hashlib.sha256`; dead env block removed from `run_scenario.py`
- [ ] H-002: S4 matching fixed to compare against individual pool messages
- [ ] M-001: `_fp_rate()` denominator corrected; dead variable removed
- [ ] N-001: `_collect_verdicts` return type annotation corrected
- [ ] N-002: Dead comment removed from `analyse.py:main()`
- [ ] N-003: `SNR= dB` status line corrected for S4/S5

Push the fixes to `feat/rr-study-harness` and confirm CI goes green on all three legs
(Windows, Ubuntu, macOS) before requesting re-review.
