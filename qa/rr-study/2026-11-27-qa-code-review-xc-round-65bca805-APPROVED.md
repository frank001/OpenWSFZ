# QA code review (HK-039): XC-ROUND, one more native round after the cross-cycle stage

**Reviewed commit:** `65bca8056887294f5cce64fef242f0a6dd3a472c` (`feat/xc-round`, one commit on `f20ae680` = PAYLOAD-FIT, not pushed)
**Reviewed-commit:** 65bca8056887294f5cce64fef242f0a6dd3a472c
**Verdict:** APPROVED, with 5 minor notes (none blocks) and 1 harness hazard that QA has already closed
**Reviewer:** QA, 2026-11-27. Read: the native diff (`ftz_decoder.c`, `ftz_decoder.h`, the fuzz driver), the managed diff (`Ft8Decoder.cs`, `Ft8LibInterop.cs`, `LeanCycle.cs`, `IFt8NativeInterop.cs`, the adapter), `ft8_shim.h`, `libft8.version.txt`, the OpenSpec change and the `REQUIREMENTS.md` FR-108 words, and both new test files, against `dev-tasks/2026-11-27-xc-round-subtract-cross-cycle-detections.md` and the Architect's `spec-xc-round.md` (`6e4e8bec`).

## Tests and checks QA ran (clean worktree at the commit, `D:\Projects\claude\_qa-scratch\xc-rev65`, Release, whole projects, no `--filter`, HK-022)

- OpenWSFZ.Config.Tests: **Passed: 237, Failed: 0**. OpenWSFZ.Web.Tests: **Passed: 464, Failed: 0**. OpenWSFZ.Daemon.Tests: **Passed: 963, Failed: 0**.
- `DOTNET_PROCESSOR_COUNT=4`, OpenWSFZ.Ft8.Tests (6 m 31 s): **Passed: 928, Failed: 0** (919 plus the 9 new: 4 native, 5 managed).
- JavaScript, `node --test web/js/*.test.js`: **tests 131, pass 131, fail 0**.
- `libft8.dll` SHA256 `fa0b96c1c8a220b363db80977c0f741b6b7898a89bce3b98fe56e51691442504` = the Developer's; `check_native_version.py ... 20260082`: OK.
- All equal the Developer's figures. **From the Developer's report, not re-run by QA:** ASan + UBSan fuzz (10,000 runs, 2,467 of them calling the round, exactly-sized probe buffer, the residual never written, 90,458 probe rows, 700 overflows; CI repeats it), `check_version_bump.py` (no bump required), `openspec validate lean-decoder --strict`, `check_version_docs.py`, G3 against the Debug assemblies (QA runs G3 in `pre_merge_check` at the sprint PR).

## What was checked and found sound

- **The cycle path is untouched when `xc` is NULL.** Every native change is guarded by `xc != NULL` (the round loop bounds, the first spectrogram and noise floor, the fit selection, the residual copy, the tones source, the probe round tag); `ftz_decode_cycle` is now a one-line wrapper over `ftz_entry(..., NULL, ...)`. QA's free check in the replay (batches 1-3 byte-identical to the PAYLOAD-FIT runs in every cycle) tests exactly this.
- **The round is the same code as a round 1 to 3** (one `ftz_decode_cycle_impl`, an `xc` argument), so the fit, the sorted-order sum, the patch window `[f - 50, f + 100]`, the candidate floor, the tiers and the accept rules are shared, not copied. The noise floor is recomputed on the residual's spectrogram in the round (`:1144`, as for rounds 1 to 3), so the SNR of batch-4 decodes is on the same scale; skipping the first spectrogram and the first noise floor in an XC call is correct because nothing reads them.
- **Budget and cancel:** the "not started with less than `FTZ_RESIDUAL_RESERVE_MS` left" and the all-or-nothing cancel are the rounds' own lines; a test (`BudgetMs: 0`) shows nothing published and `Abandoned` set. Results are sorted before the callsign table is touched (the shared publish path); a determinism test at 1, 2 and 16 threads covers results and probe rows.
- **Safety of the new entry:** a NULL or short `xc`, a missing array with a detection, `n <= 0` or a NULL `pcm` return `FTZ_ERR_ARG` before anything is read; `n_det` is clamped to `rcap`, the capacity of `fit_ix`; the tones are copied from a caller array of `n_det * 79` bytes; a tone above 7 is refused by the fit (`subfeas_fit.c:1097` returns -1), which the round turns into an error code, not an out-of-range read.
- **Managed placement:** the round runs after the stage, once, only with at least one published live batch-3 detection, a residual and effort not Fast; a failure costs only batch 4 (the log line says so); `OperationCanceledException` still propagates. The detections are the ones that survived the mapping, with their published (integer-Hz) frequency and dt and the template tones, the same convention the cycle's fits use (`fitjob->freq = (float)results[k].freq_hz`). Batch 4 goes through `MapLean` (text de-duplication across the whole cycle, plausibility, region, worked-before), is stored as priors like batch 2, and is delivered only when non-empty. A cycle that does not call the round logs exactly what it did before.
- **Tests are real tests:** (a) the weak message is undecoded without the round (a precondition inside the test, the red-before for a new entry) and decoded with it, with a round-4 `SUB` row at the strong signal's frequency, `Fits == 1`, `FitNone == 0`, every probe row round 4; no detection leaves the residual byte-identical; (b) determinism; (c) five managed cases (stage off, no detection, Fast and no residual, one call with the published detections and batch 4 after batch 3 with repeated texts dropped, an empty round and a throwing round). No delays; synthetic `Q`-prefix content only (NFR-021).
- **Documents:** FR-108 now says four batches, describes the round, lists 20260082, and has changelog row 1.79 (the lesson of PAYLOAD-FIT applied); OpenSpec tasks 14 and a delta requirement are in step. The classic decoder is not touched.

## Harness hazard (QA's, closed before the replay)

`IFt8NativeInterop.DecodeLeanXcRound` is a **default interface member returning an empty outcome**, so any wrapper that does not forward it silently never runs the round. QA's replay harness wraps the interface (`StageProbeInterop`); without a forward the XC replay would have produced **no batch 4 and no error** (a filtered-out suite is silent, HK-022). QA's harness commit adds the forward (`HasXcRound`, with the probe rows going to `--probe-out` under the cycle's stamp) and records the round's counters in `lean.csv`. The Developer's interface choice is sound for the daemon (the real adapter forwards) and for fakes (no batch 4); the hazard is only for wrappers, and is now written down here.

## Minor notes (none blocks)

1. **The duplicate rule sees only the call's own results.** The round does not know the cycle's earlier payloads, so the native payload-level and RR73-aware same-transmission rules cannot drop a decode that repeats an earlier result of the cycle; only the managed text de-duplication does (equal text). A different text for the same transmission (the RR73 sentinel against the on-air form) could slip through; the replay's batch-4 decodes will show it as a repeat of an earlier text if it happens (QA will count).
2. **Dangling `else` without braces** in the fit selection (`if (xc != NULL) for (...) ...; else for (...) { ... }`): correct as written, easy to misread; braces would be kinder.
3. **A tone above 7 is reported as `FTZ_ERR_NOMEM`** (the fit's `-1` goes down the existing "bad argument or no workspace" branch), which names the wrong cause; harmless, the managed side always passes template tones.
4. **A pinned handle can leak** if an exception is thrown between allocating the probe pins and the `try` that frees the detection pins (`DecodeLeanXcRound`); the same pattern as the cycle's entry, and only with the probe on.
5. **The cost per call is measured on a 15 s fixture with one detection** (233 ms wall, 250 ms CPU, almost all the fit and the analytic signal); the station figure comes from the replay's `xcRound[...]` log fields (`lean.csv`'s `xr_*` columns).

## Next (QA)

Merge `origin/main` into `qa/sprint-xc-round`, build the harness from this commit (`HasXcRound`, pin the DLL hash above), then the one replay (the PAYLOAD-FIT arm on S40, H40, H20), free check first: batches 1-3 byte-identical to `pf_*` in every cycle; if not, stop and tell the Architect.
