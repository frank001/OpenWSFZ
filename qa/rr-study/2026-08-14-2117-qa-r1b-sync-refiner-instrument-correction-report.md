# QA → Architect report: r1b-sync-refiner-instrument-correction

**Date (UTC):** 2026-08-14 21:17 (`date -u`)
**Change:** `r1b-sync-refiner-instrument-correction`
**Branch:** `feat/r1b-sync-refiner-instrument-correction` (branched off `feat/r1-sync-refiner-instrument-validation`; not pushed, not merged — HK-014/HK-010/HK-006)
**Session role:** Developer session via `/opsx:apply` (HK-011 flow)

## 1. Outcome, up front

**D3 reproduced exactly (with one method fix) · D1 export shipped and verified end-to-end · AC-1 PASS · AC-2 PASS · AC-3 FAIL, now LOCALISED to Stage C alone · AC-4 PASS (no longer void-by-construction) · AC-5 PASS · AC-6 measured, not gated · production-decode-equality PASS (zero bytes differ) · `dotnet build`/`dotnet test` green.**

This change did exactly what it set out to do: fix the instrument, not the refiner. D1's new export makes AC-3's two search stages independently testable for the first time, and the result is a genuine, sharp finding: **the noise-only time asymmetry the Captain's ruling flagged on R1 lives almost entirely in Stage C (the fine-time search), not Stage A+B (the joint coarse time×frequency search).** Stage A+B alone is clean (p=0.454, KS=0.035 — indistinguishable from a fair symmetric selection). Stage C alone is almost totally one-sided (p≈0, KS=0.973 — 98.6% of noise trials select a negative fine-time offset). This is the single most useful outcome of this change: R2 is **still blocked**, but the blocker is now a precisely-located one-stage defect, not an unlocalised "somewhere in the refiner" finding.

AC-4's retirement/replacement also did what design.md predicted: the old per-stratum any-adjacent-pair rule was void by construction (the ruling's own finding); the new pooled Spearman trend test passes cleanly, confirming the refiner really does show genuine SNR-dependent time-error shrinkage — R1's own measurement was correct, R1's *gate* was the defect.

## 2. D3 — stratification reproduced (task 1)

`qa/rr-study/r1-sync-refiner/stratify_noise.py` (new) reproduces proposal.md's Impact section numbers from `run_a.json` (R1's own committed 1,200-trial noise population) exactly:

| statistic | proposal.md | reproduced |
|---|---|---|
| mean(Δt) | −5.42 ms | **−5.416 ms** |
| median(Δt) | −5.00 ms | **−5.000 ms** |
| sign test (non-zero trials) | 637 neg / 555 pos, p=0.019 | **637 neg / 555 pos, p=0.0189** |
| KS(x, −x) | p=4.9×10⁻⁷ | **p=4.943×10⁻⁷** |
| decile range | −1.96 ms .. −14.06 ms | **−1.962 ms .. −14.058 ms** |
| r(cell position, Δt) | −0.067 | **−0.0672** |
| r(raw offset, Δt) | −0.033 | **−0.0333** |
| r(freq, Δt) | −0.007 | **−0.0070** |

**One real method bug found and fixed while reproducing this** (not a data problem — reported per HK-018/task 1.2's explicit "if they do not reproduce, STOP" instruction): the first implementation binned `coarse_time_offset_s`'s fractional cell-position into **fixed-width** `[0, 0.1), [0.1, 0.2), …` bins. That put unequal trial counts per bin and flipped decile 0's sign (+0.39 ms instead of the claimed −1.96 ms) relative to proposal.md. Switching to **quantile-based (equal-count) deciles** reproduced every figure above exactly on the next run. `stratify_noise.py`'s docstring records this so it isn't silently rediscovered.

Confirms the ruling's D3 reading: the bias is **pervasive across the search space**, not a boundary/edge artefact tied to one injected time or frequency position — negative in every decile, negligible correlation to either field.

## 3. D1 — the (coarse, fine) decomposition export (task 2)

`ft8_refine_candidate` gains two new out-parameters, `out_coarse_dt_samp` and `out_fine_dt_samp`, populated directly from the existing `best_dt_samp`/`best_fine_samp` locals in `sync_refiner.c` — **zero change to the search/correlation logic itself**. Shim bumped `20260040` → `20260041`.

- **Native**: `native/ft8_lib_vendor/refine/sync_refiner.c`, `src/OpenWSFZ.Ft8/Native/ft8_shim.h`.
- **Managed**: `Ft8LibInterop.RefineCandidate`'s P/Invoke declaration and public tuple return, `IFt8NativeInterop.RefineCandidate`'s interface signature, `Ft8NativeInteropAdapter`. All **10** implementers of `IFt8NativeInterop.RefineCandidate` updated: the 8 pre-existing test doubles R1's own task 2.1 counted (`WorkedBeforeLookupTests`, `RegionLookupTests`, `D011NonstandardCallsignFpGuardTests`, `D009FpFilterTests`, `D005MessageTrimTests`, `SetDecodeParamsTests`, `HashTableRejectCountLoggingTests`, `AvContainmentTests`), plus `Ft8NativeInteropAdapter` (production) and `RefineCandidateTests`' own `CapturingInterop` (the 9th/10th, both added by R1 for its own tests).
- **Python harness**: `refiner_ctypes.py` (`ft8_refine_candidate` ctypes signature extended, `expected_shim_version` default → 20260041) and `run_harness.py` (both signal and noise trial loops record `coarse_dt_samp`/`fine_dt_samp` as additive fields).
- **Tests**: `RefineCandidateTests.cs` extended — 2.1a now asserts the two new fields round-trip through a fake; new 2.4a proves the decomposition-sum arithmetic on a fake with deliberately consistent stub values; 2.1b (real-binary smoke test) now asserts `CoarseDtSamp ∈ [-12,12]`, `FineDtSamp ∈ [-20,20]`, and that `CoarseDtSamp/200.0 + FineDtSamp/2000.0 ≈ DeltaTimeS` against the **real 20260041 binary** — this is the spec's own "Decomposition sums to the previously-reported total" scenario, verified end to end, not just in a fake.

**Verified**: `dumpbin /exports` (Windows) / `nm -D` (Linux) both show all 12 exported symbols, unchanged set (`ft8_refine_candidate`'s RVA moved as expected for a signature change; nothing added or removed).

## 4. D2 — reflection-symmetry evaluator, and what it found (task 3)

`reflection_symmetry_test()` (new, `evaluate_acs.py`) implemented exactly as design.md drafted it — a two-sample KS test of a sample against its own negation, `instrument_failure` (not a silent PASS) on zero variance. Run three times over the full `n=1,200` noise population at `α = 0.01/3` (Bonferroni): combined `Δt`, `coarse_dt_samp` alone, `fine_dt_samp` alone.

| sub-test | n | KS statistic | p-value | verdict (α=0.00333) |
|---|---|---|---|---|
| combined (`Δt`) | 1,200 | 0.1125 | 4.94×10⁻⁷ | **FAIL** |
| coarse stage (`coarse_dt_samp`) | 1,200 | **0.035** | **0.454** | **PASS** |
| fine stage (`fine_dt_samp`) | 1,200 | **0.973** | **≈0** | **FAIL** |

Frequency dimension (chi-squared, unchanged from R1): p=0.942, **PASS**, as before.

**This is the finding.** Stage A+B's own coarse time×frequency selection is essentially indistinguishable from fair (KS=0.035 is tiny; p=0.454 is nowhere near significant). Stage C's fine-time selection is almost maximally asymmetric — a KS statistic of 0.973 is close to the theoretical ceiling of 1.0. Looking at the raw distribution (informal, exploratory, not part of any gate):

- `fine_dt_samp` is **negative in 1,183/1,200 trials (98.6%)**, positive in only 15, zero in 2.
- The modal value is **−20** (115 trials) — the search range's own extreme (`REFINE_FINE_TIME_HALF_MS = 10.0 ms`, step `0.5 ms`, so `[-20, 20]` samples) — and counts decay roughly monotonically from there toward 0.
- `coarse_dt_samp`, by contrast, looks close to flat across its own `[-12, 12]` range (74 at −12, 76 at +12 in one run — no visible skew).

This directly answers the ruling's open question: the mechanism is **not** an interaction that's diffuse across both stages — it is concentrated almost entirely in Stage C. It is consistent with either H-A (argmax tie-break/plateau convention — the pile-up at the range's own boundary is exactly the signature a boundary-favoring scan would produce) or H-C (a genuine selection-bias interaction specific to Stage C's re-derivation from an already-noise-optimised carrier); it does not obviously match H-B (coarse-filter aliasing) as cleanly, since that would be expected to leave *some* trace in Stage A+B's own selection too, and Stage A+B looks clean. **Per design.md's explicit Non-Goals and the Architect's own DIRECTIONAL calibration (1.5/3.5, the weakest class), this report does NOT conclude which of H-A/H-B/H-C is the mechanism — that determination is out of this change's scope by design.** The observation is reported because D1/D2 were built specifically to make it visible; discriminating between the three remains a follow-up.

## 5. D4 — pooled SNR trend evaluator (task 4)

`snr_trend_test()` (new) replaces the old per-stratum any-adjacent-pair-increases-fails rule for the time dimension — **deleted, not merely stopped-calling** (verified: zero remaining references to the old `broken_pairs` logic anywhere in `evaluate_acs.py`). One-sided Spearman rank-correlation, pooled across all six SNR strata's per-trial absolute time error (n=2,400, not six collapsed RMS numbers), pre-registered `α = 0.01`.

| | measured | bar | verdict |
|---|---|---|---|
| Spearman ρ | **−0.0754** | ρ < 0 | ✓ |
| one-sided p | **0.00011** | < 0.01 | ✓ |
| n pooled | 2,400 | — | — |
| underpowered strata | none | — | — |

**PASS.** R1's own measurement (error shrinking from 1.515 ms at −20 dB to 1.109 ms at +5 dB) was real; the *old gate* — one RMS number per stratum with zero tolerance for the ≈3.5% relative sampling noise that collapse introduces at n=400 — was the defect, exactly as the ruling's HK-021(k) finding predicted (a ~99.9% chance of failing a flawless refiner). Frequency dimension is retired permanently per R-1 (RMS(Δf) is flat by construction against the 0.5 Hz grid, reported informationally only, contributes to no pass/fail field — confirmed in the report JSON's `per_stratum_note`).

## 6. D5 — frequency-floor finding carried forward (task 5)

No code. design.md's D5 section states plainly, for whoever proposes R2: **the refiner has no sub-0.5 Hz frequency capability** — `REFINE_FREQ_STEP_HZ = 0.5f`, no fine-frequency stage exists anywhere in `sync_refiner.c`. Confirmed as written; no new artefact needed (task 5.1).

## 7. Full re-run against the rebuilt binary (task 6)

- **Shim bump**: `FT8_SHIM_VERSION` (`ft8_shim.h`) and `ExpectedShimVersion` (`Ft8LibInterop.cs`) → **20260041**.
- **Windows x64** (`rebuild_shim.bat`, MSVC 19.44.35223): SHA256 `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf`.
- **Linux x64** (`build_linux.sh`, GCC 14.2.0 via WSL2 Debian): SHA256 `6f0c541964b17f71b820937c887a63df10db6adb4831ec08ee137b767ad91edd`.
- **macOS ARM64**: NOT rebuilt — no Mac available, third consecutive shim version with this gap (R0, R1, now R1b), named explicitly per the ruling's own instruction not to inherit it silently again. Non-blocking; CI rebuilds from source.
- **Build-tooling defect found and fixed en route (unrelated to the refiner)**: `native/ft8_lib_build/build_linux.sh` had CRLF line endings (a Windows checkout/edit artefact), which broke bash execution under WSL2 on the first attempt (`$'\r': command not found` on every line; produced no `.so`). Fixed by normalising to LF. Purely a build-tooling fix — zero effect on any compiled output. Recorded in `libft8.version.txt`.
- Three independent `run_harness.py` invocations against the new binary, same seed (20260815) and population as R1 (2,400 signal + 1,200 noise trials each) → `results/2026-08-14/{run_a,run_b,run_c}_20260041.json`.

### AC-1 / AC-2 — reproduced byte-for-byte

| | R1 (20260040) | R1b (20260041) |
|---|---|---|
| RMS(Δf) | 0.1430 Hz | **0.1430 Hz** |
| RMS(Δt) | 1.135 ms | **1.135 ms** |
| mean(Δf err) | −0.0019 Hz | **−0.0019 Hz** |
| mean(Δt err) | +0.429 ms | **+0.429 ms** |

Identical to four significant figures — confirms D1 is genuinely pure instrumentation; the search/correlation algorithm was not touched.

### AC-5 (determinism) — PASS

Three runs byte-identical (mechanical `filecmp`, not eyeballed).

### AC-6 (cost, not gated)

Mean 20.33 ms/candidate (vs. R1's 21.5 ms — both informational only, wall-clock jitter, no gate). Projected full-corpus time comfortably under the 8 h escalation threshold at both the 100 and 340 candidates/cycle bounds; no escalation.

### Production-decode-equality replay — PASS, zero bytes differ

Same tooling and range R0/R1 established (`qa/cycleframer-alignment-replay/r0_ac1_ac2_replay.py` + `r0_ac1_ac2_diff.py`), 250 contiguous cycles, pinned 20 m corpus (`260808_004000`..`260808_014215`). Pre-change binary extracted from git commit `af2f466` (SHA256 confirmed to match R1's own shipped pin exactly) vs. the freshly built `20260041`:

**`RESULT: PASS — zero differences across 250 cycles`.**

D1's instrumentation did not alter `ft8_decode_all`'s production output by a single byte, as expected for a diagnostic-only, no-production-call-site change.

### .NET build/test

`dotnet build` on `OpenWSFZ.Ft8.csproj` and `OpenWSFZ.Ft8.Tests.csproj`: **0 Warning(s), 0 Error(s)**.
`dotnet test`: **310/310 passed**, 0 failed, 0 skipped (309 R1 baseline + 1 new `RefineCandidateTests` scenario — 2.4a; the 2.1a/2.1b/2.1c scenarios were extended in place rather than added as new facts). Includes the `RequiresNativeBinary`-tagged real-binary smoke tests against the freshly built 20260041 DLL.

## 8. Is R2 unblocked? (task 7.2)

**No — R2 remains blocked**, per the same disposition design.md's D2 scenario names ("SHALL NOT proceed to unblock R2 until resolved"). AC-1/AC-2/AC-5/AC-6 all reproduce cleanly, and AC-4 now passes (both necessary preconditions design.md's Impact section named). But **D2's own gate requires all three sub-tests to PASS, and one does not**: `fine_dt_samp` alone fails at KS=0.973, p≈0 — as unambiguous a rejection as a statistical test produces. This is not the diffuse, hard-to-interpret finding R1 left behind; it is a precisely localised one. That is real forward progress even though the formal gate stays FAIL: **whoever next works this problem now knows the defect lives in Stage C's own search/selection, not in Stage A+B, not in an interaction that's spread across both.** The three non-gating discriminator hypotheses (H-A argmax convention, H-B coarse-filter aliasing, H-C selection-bias interaction) named in design.md are now testable with D1's export in hand — H-B looks like the weakest fit given Stage A+B's own cleanliness, but per design.md's explicit Non-Goals this report does not adjudicate between them.

## 9. Stop (task 7.3)

No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006). This report does not declare readiness for merge. The Captain reviews the diff and decides — including the open sequencing question design.md's Open Questions §1 flagged (R1 has not yet been archived; this change's spec deltas are written against R1's requirement text as committed, not an archived baseline).

## Appendix: artefact locations

- Native source: `native/ft8_lib_vendor/refine/sync_refiner.c` (D1 additions), `src/OpenWSFZ.Ft8/Native/ft8_shim.h`.
- Managed binding: `src/OpenWSFZ.Ft8/Interop/{Ft8LibInterop.cs, IFt8NativeInterop.cs, Ft8NativeInteropAdapter.cs}`.
- Validation harness: `qa/rr-study/r1-sync-refiner/{population.py (unchanged), refiner_ctypes.py, run_harness.py, evaluate_acs.py, stratify_noise.py (new)}`.
- Raw results: `qa/rr-study/r1-sync-refiner/results/2026-08-14/{run_a,run_b,run_c}_20260041.json` + `.timing.json` sidecars + `ac_evaluation_report_20260041.json` + `stratify_report_run_a.json` + `replay_20260040_pre.json` / `replay_20260041_post.json`. R1's own `run_a/b/c.json` (no suffix) and `ac_evaluation_report.json` left untouched as R1's pinned evidence.
- New/updated tests: `tests/OpenWSFZ.Ft8.Tests/RefineCandidateTests.cs` (extended) and the 9 other `IFt8NativeInterop` implementers (signature-only updates).
- Binary provenance: `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` (new top entry).
- `openspec/changes/r1b-sync-refiner-instrument-correction/tasks.md` — all 24 tasks checked off with implementation notes.
