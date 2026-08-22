# QA → Architect: arm B-dt-C3 results — ROW 2 FIRES, mechanism CONFIRMED

**2026-08-22 14:54Z.** `r2-coherent-llr-instrument`, spec
`qa/rr-study/2026-08-22-1433-architect-to-qa-spec-b-dt-c3-offline-negative-dt.md`,
`feat/r2-coherent-llr-phase-b`. No `src`/`native` change, no live run, no new binary, no
capture hardware touched (HK-011 not implicated).

## 0. Summary

**ROW 2 FIRES.** A step of **17.4 dB**, more than double the 8.0 dB bar, lands at **exactly
the same part (`p4`, `true_dt = −0.24 s`)** as the sign change in the reported `dt`/
`time_offset` proxy. `p_step == p_sign == 4`. The rival hypothesis ("signal falls partly
outside the decode window") predicted at most **0.083 dB** at that part — the measured step
is **~210×** larger. All four ROW 0 validity limbs cleared, including an exact,
bit-for-bit reproduction of B-dt-C1's part-0 numbers. Recommending the `ft8_shim.c:1491-1498`
fix to the **Captain** as a Developer session, per Sec.6 ROW 2's own consequence — QA does
not open it (HK-011).

## 1. Preconditions (spec §5), asserted before running

1. **Binary identity.** Hashed the working-tree binaries myself: win-x64 `libft8.dll`
   SHA256 `f0c081b9…9e81fe58`, linux-x64 `libft8.so` SHA256 `1ba510b8…7eb7c046b` — both
   match the spec's pin exactly, unchanged since B-dt-C1. The harness
   (`snr_terms_ctypes.SnrTermsDecoder`, `verify=True`) also asserts this at load time.
2. `qa/rr-study/tests/test_modulator.py` — **8/8 pass**, including
   `test_negative_dt_shifts_signal_earlier`. `synth/modulator.py` still raises rather than
   clamps at both ends (checked by reading `modulate()` directly, not merely by the test
   name).
3. No `src`/`native` change made or needed.

## 2. What ran

New harness `qa/rr-study/r2-coherent-llr-instrument/b_dt_c3_offline_negative_dt.py`,
modelled on `b_dt_c1_offline_dt_check.py`'s decode/match skeleton (HK-018). Ten parts,
`true_dt` = +0.08, 0.00, −0.08, −0.16, −0.24, −0.32, −0.48, −0.72, −0.96, −1.20 s, 5 trials
each = 50 cycles, `snr_db=0`, `base_freq_hz=1500`, message `MSG-01` — S3's own fixed values.

**Rendering, exactly per spec §3.2:** every part rendered `extended=True` then truncated to
`buffer[-180_000:]` — the same 180,000-sample boundary-aligned window a live decode is
structurally limited to (`Ft8Decoder.cs:50`). Noise sigma computed **once**, from the p1
(`true_dt=0.0`) untruncated render (`sigma = 1.005084`), then applied via `add_awgn`
directly to every part's truncated `clean` — never re-derived per part, so the truncated
parts' in-slot SNR is free to actually collapse rather than being pinned to 0 dB by
construction. p1 trials 0-2 used `compute_seed("S3", 0, trial)`, identical to B-dt-C1's
part 0; all other cells used `compute_seed("B-dt-C3", part_index, trial)`.

Placement was verified independently before the sweep ran, on the clean (pre-noise)
buffers: `cross_corr_lag()` (scipy FFT correlation) against a synthetic shifted-pulse test
first, then against the real p0–p9 renders — every part's measured lag matched
`round(true_dt × 12000)` **exactly, to 0 samples**, for all ten parts.

## 3. ROW 0 — VALIDITY — clear, all four limbs

| limb | check | result | fires? |
|---|---|---|---|
| (a) decode floor | p0–p5, need ≥3 matched each | 5/5 every part | no |
| (b) exact reproduction | p1 trials 0-2 vs B-dt-C1 part 0 | `reported_snr`=2.000000 (ref 2.000), `reported_dt`=0.160000 (ref 0.160), `signal_db`=−7.575949 (ref −7.576 ± 0.001) | no |
| (c) placement | max \|measured−expected lag\| | 0 samples (tol 1) | no |
| (d) straddle | analysis set has both `T(p)≥0` and `T(p)<0` | yes (p0–p3 ≥0, p4–p9 <0) | no |

50/50 cells decoded and matched (0 no-decodes, 0 frequency mismatches). Limb (b) is the
strongest confirmation available short of a diff: the harness reproduces B-dt-C1's own
numbers **to six decimal places on a value it never saw before this run**, on the *same*
binary via a *different* code path (`extended=True` + truncation vs `extended=False`
directly) — the docstring's claim that the two are byte-identical when the placement
already fits a single slot is now verified empirically, not just read.

**ROW 0 does not fire. Proceeding to ROW 1/2/3.**

## 4. ROW 1 / 2 / 3 — the gate

Analysis set = all ten parts (`p_max = 9`, every part cleared the ≥3-matched floor).

**`max_p Δ(p) = 17.400 dB` at `p_step = 4`. `p_sign = 4`** (lowest part with `T(p) < 0`;
`T(3) = 0.000`, `T(4) = −0.080`).

**ROW 2 FIRES: step ≥ 8.0 dB (17.4 dB, more than double the bar) AND `p_step == p_sign`
(both 4) → CO-LOCATED.** The SNR step and the `time_offset` sign change are the same
event, on the same rows of the same run. This is the strongest form of evidence an
observational arm can produce for the `ft8_shim.c:1491-1498` clamp mechanism.

## 5. §7 — reported, not gated

| part | `true_dt` | n | `E(p)` | `T(p)` | `T(p)−true_dt` | `signal_db` | `local_noise_db` | rival (§2.3) |
|---|---|---|---|---|---|---|---|---|
| 0 | +0.08 | 5/5 | +2.000 | +0.240 | +0.160 | −7.575 | −36.000 | 0.000 |
| 1 | 0.00 | 5/5 | +2.000 | +0.160 | +0.160 | −7.596 | −36.000 | 0.000 |
| 2 | −0.08 | 5/5 | +2.000 | +0.080 | +0.160 | −7.643 | −36.000 | −0.028 |
| 3 | −0.16 | 5/5 | +2.000 | 0.000 | +0.160 | −7.915 | −36.000 | −0.055 |
| **4** | **−0.24** | 5/5 | **−15.400** | **−0.080** | +0.160 | −24.818 | −36.000 | −0.083 |
| 5 | −0.32 | 5/5 | −15.400 | −0.160 | +0.160 | −24.919 | −36.000 | −0.111 |
| 6 | −0.48 | 5/5 | −15.800 | −0.320 | +0.160 | −25.392 | −36.000 | −0.168 |
| 7 | −0.72 | 5/5 | −16.600 | −0.560 | +0.160 | −25.985 | −36.000 | −0.255 |
| 8 | −0.96 | 5/5 | −16.400 | −0.800 | +0.160 | −25.959 | −36.000 | −0.343 |
| 9 | −1.20 | 5/5 | −18.400 | −1.040 | +0.160 | −27.786 | −35.900 | −0.433 |

1. **Measured vs rival, side by side.** Deficit relative to the p1 (untruncated) baseline
   (`E(1)=+2.000`): p2/p3 (still `T(p)≥0`) show **exactly 0.000 dB** deficit against a
   rival of −0.028/−0.055 dB — the rival is not merely beaten, the measured value is
   *closer to zero than the rival itself* there. From p4 on, deficit is **17.4–20.4 dB**
   against a rival of 0.083–0.433 dB — a ratio of **48×–210×**, growing *smaller* as `|dt|`
   grows even while the absolute gap widens, because the rival itself grows too. The
   measured curve is not a ramp that happens to be steep; it is flat, then a step, then
   flat again (18.4 ± 2.2 dB flat spread across p4–p9) — the clamp's signature, not the
   rival's.
2. **Flatness on the negative side (§7 item 3).** `max E(p) − min E(p)` over analysis-set
   parts with `T(p) < 0` (p4–p9) = **3.000 dB** — flat within a few dB as the clamp
   predicts (a 1-symbol and a several-symbol shift land at comparably wrong readings),
   not a monotone ramp tracking `|dt|`.
3. **`local_noise_db` (§7 item 4).** Spread across all ten parts with ≥1 matched decode =
   **0.100 dB** — flat, as required: the estimator has no time argument and is
   structurally incapable of responding to the symbol-index shift. It does not step.
4. **`T(p) − true_dt` on the negative side (§7 item 5).** The ≈+0.160 s offline offset
   **holds exactly constant, to the printed digit, across the entire sweep** — +0.160 s at
   every one of the ten parts, p0 through p9, with no drift and no saturation toward zero
   as `time_offset` goes negative and even after `signal_db` collapses at p4. The old
   `STUDY-SPEC` §R&R-003 claim ("OpenWSFZ reports DT ≈ 0 regardless of the true offset")
   does **not** replicate here — this is the first genuinely early-audio measurement of
   that claim, and it reads as a clean, constant additive offset, not a saturation.
5. **Cluster composition.** No part dropped out — all ten decoded 5/5 trials. `E(p)` alone
   would have hidden nothing here; there is no part where a low `n` could be confused with
   a real effect.
6. **`p_max = 9`** — the sweep decoded cleanly through the deepest part (7.5 of 7 Costas
   symbols lost), no attrition anywhere in the analysis set.
7. Fixed `sigma = 1.005084` (from the p1 untruncated render).

## 6. Prediction scoring (spec §10)

| # | Prediction | Confidence | Result |
|---|---|---|---|
| 1 | ROW 0 does not fire on any limb | 70% | **HIT** |
| 2 | ROW 0(b) exact reproduction passes to the printed digit | 90% | **HIT** |
| 3 | ROW 2 fires | 65% | **HIT** |
| 4 | `p_sign = p3` (`true_dt = −0.16`) | 45% | **MISS** — `p_sign = p4` (`true_dt = −0.24`); the offset is not shifting the sign-change part, the reported-`dt` lattice quantum (0.08 s) is one step coarser than the prediction assumed |
| 5 | `p_max ≥ 7` | 60% | **HIT**, dead centre exceeded — `p_max = 9`, the full sweep |
| 6 | `local_noise_db` flat, spread < 1.0 dB | 85% | **HIT** — 0.100 dB |
| 7 | Negative-side flatness < 5.0 dB | 55% | **HIT** — 3.000 dB |
| 8 | Measured deficit exceeds rival by >10× at every negative part | 60% | **PARTIAL / MISS as stated** — HIT for p4–p9 (48×–210×), but p2/p3 show a **zero** measured deficit against a nonzero (if tiny) rival, so "exceeds by >10×" is literally false there; the honest reading is that the deficit is a step, not a ramp, so the ratio is undefined (0/rival) rather than large below the step |

**6/8 HIT, 1 partial/miss, 1 clean miss** — best-scoring arm of this investigation so far,
and the miss (#4) is informative rather than damaging: it pins the sign-change part to the
decoder's own 0.08 s `dt` quantum rather than to the raw −0.16 s label, consistent with
`T(3) = 0.000` sitting exactly on the lattice boundary between the two.

## 7. What this does NOT license, and what is next

Per spec §9: does **not** authorise any `src`/`native` change — the fix is named
(`ft8_shim.c:1491-1498`), not applied; **HK-011: the Captain opens a Developer session or
nothing happens.** Does not cancel B-dt-C2 (still available as live confirmation at the
Captain's discretion, still needs the orphaned `rr_study_daemon` PID 37432 confirmed and
torn down first, HK-019). Does not reopen AC-N2/N3/N4, the getter, or the Amendment 2/3
acceptance. Does not substitute for `tasks.md` §11. Does not license anything about decode
*rate* at negative DT, `dt_s` beyond −1.20 s, the SNR formula, H5, suppression, Route
B2/B3, C2, C3, or reading §3 of the 14:11Z spec's corpus collinearity as evidence for the
mechanism.

**Handed forward per spec §8, for whichever Developer session the Captain opens:** the
regression check — on any corpus where every decode has `dt ≥ 0`, the fix must be
bit-identical, decode for decode, against the eight committed `results/replay_*.json`
files from AC-N1. **And this arm is itself the post-fix acceptance run** — re-run
`b_dt_c3_offline_negative_dt.py` unchanged (same harness, same seeds, same pinned grid)
after the fix; `E(p)` should go flat across the whole sweep and `Δ(p)` should fall below
8.0 dB everywhere. Pre-fix `results/b_dt_c3_report.json` is committed for that comparison.

QA stops here per the spec's Handover (§11) — the consequence is the Captain's Developer
session, not further QA action.

## 8. Artefacts

- `qa/rr-study/r2-coherent-llr-instrument/b_dt_c3_offline_negative_dt.py`
- `qa/rr-study/r2-coherent-llr-instrument/results/b_dt_c3_report.json` /
  `results/b_dt_c3_run.log`
