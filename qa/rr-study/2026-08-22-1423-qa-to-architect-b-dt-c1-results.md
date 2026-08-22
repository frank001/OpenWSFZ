# QA → Architect: arm B-dt-C1 results — ROW 1 FIRES, mechanism supported at the offline off-diagonal cell

**2026-08-22 14:23Z.** `r2-coherent-llr-instrument`, spec
`qa/rr-study/2026-08-22-1411-architect-to-qa-spec-b-dt-c-reported-dt-sign.md` (§4, TASK 1),
`feat/r2-coherent-llr-phase-b`. No `src`/`native` change, no live run, no new binary
(HK-011 not implicated).

## 0. Summary

**ROW 1 FIRES: `dt_off_0 = +0.160 s`.** At `true_dt == 0`, offline synthesis with no
playback/capture displacement reports a **non-negative** `time_offset`-proxy DT and — per
the correction in §2 below — **no SNR deficit**. This is the exact opposite corner from
the live corpus's S3 part 0 (`reported_dt = −0.200 s`, error `−15.67 dB`). The
off-diagonal cell Section 3 of the spec found empty in both existing corpora is now
filled from the offline side: **`true_dt == 0` does not imply `reported_dt < 0`.** The two
stratifiers separate for the first time. Both ROW 0 validity limbs cleared. Recommending
TASK 2 (live, B-dt-C2) to the Captain as the next step — not run in this session (§4).

## 1. Corrections applied first (§2 of the spec, HK-015 — mine to write)

Before running TASK 1, applied the Architect's stated correction to the existing AC-N5
report, in place rather than by annotation, per the spec's own instruction:

- `qa/rr-study/2026-08-22-1349-qa-to-architect-amendment2-ac-n1-n5-results.md` — §0
  (Summary) and §5.2 rewritten to withdraw `−6.01 dB` as a measure of the live collapse's
  size, name the S3/S8 scenario confound (56/59 `dt=0` rows are S8, 21/26 `dt>0` rows are
  S3), and state the honest finding: `local_noise_db` does not move; `signal_db` is where
  any `dt`-dependence must live by construction of the formula; the pooled `−6.01 dB` is
  largely an S8-vs-S3 level contrast, not a clean `dt` effect. §6's prediction-scoring row
  annotated the same way rather than deleted, so the record shows what was claimed and
  what corrected it. AC-N2/N3/N4 and the getter's own acceptance are untouched — confirmed
  by re-reading those sections, no wording there depended on the `−6.01 dB` figure.
- Board one-liner: this report's own board entry (below, HK-024) states the corrected
  reading directly rather than repeating the withdrawn figure.

Not re-verified mechanically in this session: the Section 3 2×2 collinearity table
(both off-diagonal cells empty in both live corpora). The spec offered it as
independently re-checkable, not as a precondition of TASK 1, and TASK 1's own result
does not depend on it — noted, not re-run, to keep this arm to its stated "minutes" cost.

## 2. TASK 1 — arm B-dt-C1

### 2.1 Preconditions (§4.2), asserted before running

1. **Binary identity.** Hashed the working-tree binaries myself:
   win-x64 `libft8.dll` SHA256 `f0c081b9…9e81fe58`, matches the spec's pin exactly.
   linux-x64 `libft8.so` SHA256 `1ba510b8…7eb7c046b`, matches the spec's pin exactly
   (not exercised by this run — Windows only — but checked since the spec pins both).
   The harness (`snr_terms_ctypes.SnrTermsDecoder`) also asserts this at load time
   (`verify=True`); confirmed independently rather than trusted from the log alone.
2. `git diff d44ffea -- qa/rr-study/scenarios/s3-dt-offset.json` — empty.
   `fixed.snr_db` — confirmed `0` by direct grep, not inferred.

### 2.2 What ran

New harness `qa/rr-study/r2-coherent-llr-instrument/b_dt_c1_offline_dt_check.py` —
`ac_n5_dt_stratified_measurement.py`'s own `run_s3` (HK-018, reused not reimplemented)
plus the one addition the spec asked for: `results[i]["dt"]` (already a field of the
ctypes `FT8Result` struct, `extract_llrs_ctypes.py:37`/`:112`) recorded per row as
`reported_dt`, alongside `signal_db`/`local_noise_db`. S3 parts 0-7 only (`dt_s` 0.0
through 2.1), 3 trials/part = 24 cycles, same 12 kHz / 180,000-sample rendering AC-N5
used. S8 not run — out of scope for this arm per spec §4.1.

### 2.3 ROW 0 — VALIDITY — clear, both limbs

| check | value | bar | fires? |
|---|---|---|---|
| part-0 matched | 3 | ≥ 3 | no |
| parts 1-7 matched | 21 | ≥ 12 | no |
| `D_off` (part-0 reported SNR − true SNR 0) | **+2.000 dB** | `\|D_off − 2.0\| ≤ 1.0` | no |

24/24 cells decoded and matched (0 no-decodes, 0 frequency mismatches). `D_off` landed
exactly on the spec's own reference value from AC-N5 — the offline instrument is
reproducing itself run-to-run, which is what limb (b) exists to confirm.

**ROW 0 does not fire. Proceeding to ROW 1/ROW 2 per the spec's own strict order.**

### 2.4 ROW 1 / ROW 2 — the gate

**`dt_off_0 = +0.160 s`.**

**ROW 1 FIRES: `dt_off_0 ≥ 0.0` → MECHANISM SUPPORTED.** Same `true_dt` (0.0), opposite
`time_offset` sign from the live corpus, opposite outcome (no deficit vs. `−15.67 dB`).
The off-diagonal cell is filled: `true_dt == 0` no longer implies `reported_dt < 0`.

### 2.5 §4.5 — reported, not gated

| part | `true_dt` | n | `reported_dt` mean | `signal_db` mean | `local_noise_db` mean | `reported_snr` mean |
|---|---|---|---|---|---|---|
| 0 | 0.0 | 3 | 0.160 | −7.576 | −36.000 | 2.000 |
| 1 | 0.3 | 3 | 0.480 | −7.823 | −35.833 | 1.667 |
| 2 | 0.6 | 3 | 0.773 | −8.551 | −35.833 | 0.667 |
| 3 | 0.9 | 3 | 1.040 | −7.814 | −35.833 | 1.667 |
| 4 | 1.2 | 3 | 1.360 | −7.614 | −36.000 | 2.000 |
| 5 | 1.5 | 3 | 1.680 | −7.766 | −36.000 | 2.000 |
| 6 | 1.8 | 3 | 1.973 | −8.559 | −36.000 | 1.000 |
| 7 | 2.1 | 3 | 2.240 | −7.785 | −36.000 | 2.000 |

1. `reported_dt − true_dt` is `+0.16` at part 0, drifting to `+0.14` at part 7 — a
   roughly constant **≈ +0.14 .. +0.24 s offset**, consistent with the spec's own
   framing of this as the live path's alignment term (here, the offline harness's own
   render-to-origin convention, not a playback/capture term, since nothing is played
   back). Worth a number, not gated.
2. `signal_db` is flat across all 8 parts (range `−7.58` to `−8.56`, ≈1 dB spread) —
   **no step at part 0**, confirming AC-N5's corrected §5.2 finding (within S3, `true_dt
   == 0` shows no deficit) on an independently-collected sample.
3. `local_noise_db` likewise flat (`−35.83` to `−36.00`) — consistent with the mechanism
   (Section 1.2 of the spec): an estimator with no time argument cannot respond to a
   symbol-index shift, so it should not, and does not, move here either.
4. S8 not run (out of scope, §4.1) — no offline-`dt<0` S8 check to report this session.

## 3. Prediction scoring (spec §7, predictions 1-3 — the ones TASK 1 can score)

| # | Prediction | Confidence | Result |
|---|---|---|---|
| 1 | ROW 0 does not fire (both limbs clear) | 85% | **HIT** |
| 2 | ROW 1 fires — `dt_off_0 >= 0` | 80% | **HIT** |
| 3 | `dt_off_0` lands in `[0.00, +0.16]` | 65% | **HIT**, exactly on the upper edge |

3/3. Predictions 4-8 are TASK 2's to score.

## 4. What this does NOT license, and what is next

Per the spec §6: does not authorise any `src`/`native` change (HK-011 stands — the
Section 1.1 fix is named, not applied), does not reopen AC-N2/N3/N4 or the getter's
acceptance, does not substitute for `tasks.md` §11 (Phase B's own ROW 0g re-run, still
open/unscheduled), and does not license anything about negative `true_dt` or decode rate.

**TASK 2 (arm B-dt-C2) is licensed by this result (spec §5: "run this only if TASK 1
fires ROW 1") but is NOT run in this session.** It is a live run (~10 min of cycles,
`--device "Voicemeeter AUX Input"` explicit, `captureActive=true` confirmed, both
`ALL.TXT` cleared with pre-clear copies preserved) against real capture hardware — a
different category of action from this arm's offline minutes, and I noted an existing
`rr_study_daemon` process already running in this working directory
(`rr_study_daemon.pid` = 37432) logging `RMS 0.000E+000` / "Cycle skipped" repeatedly,
which reads as a stale/orphaned instance (HK-019) rather than one configured for this
scenario — it should be confirmed and torn down, not assumed usable, before TASK 2 arms
anything. Recommending TASK 2 to the Captain as the next step rather than starting it
unprompted.

## 5. Artefacts

- `qa/rr-study/r2-coherent-llr-instrument/b_dt_c1_offline_dt_check.py`
- `qa/rr-study/r2-coherent-llr-instrument/results/b_dt_c1_report.json` /
  `results/b_dt_c1_run.log`
- Correction: `qa/rr-study/2026-08-22-1349-qa-to-architect-amendment2-ac-n1-n5-results.md`
  §0/§5.2/§6 edited in place.
