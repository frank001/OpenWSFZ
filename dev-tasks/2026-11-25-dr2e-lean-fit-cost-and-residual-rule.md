# Developer task: DR-2 step 2e, make the lean engine's subtraction cheap, and admit the ungated rows

**Date:** 2026-11-25
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-25 ("go with your recommendations") after the one Slice 40 replay of `6c746029` (`qa/decoder-rebuild/dr2d-result.md`); targets from `docs/decoder-rebuild/spec-dr2-lean-decoder.md` §1 (read with `git show arch/decoder-rebuild:docs/decoder-rebuild/<file>`).
**Status:** Proposed. HK-011: `src/` and `native/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). Do not push, open a PR or merge; QA pushes.
**Branch:** `feat/lean-2e`, a child of `feat/lean-2d` (tip `6c746029`, reviewed, APPROVED, CI green).
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. **You run no replay.** QA runs one replay after the review. Run tests per project (HK-022) and read the per-assembly "Passed: N" lines. Run the golden and lean tests once with `DOTNET_PROCESSOR_COUNT=4` as well.

---

## 0. Why

The replay of `6c746029` on Slice 40 (170 cycles) read: `cpu_net` **16.345** CPU-s per cycle (bar 6.31), `rate` **77.691 %** (bar 83.39 %), `ours_only` 3.248 % (met), `last_p95` **11,111 ms** with **4 abandoned cycles** (bar 3,000 ms and 0). Of the 16.345 CPU-s, the subtract loop is 14.36 and **the fits alone are 12.16** (about 30 fits per cycle, about 0.4 CPU-s each; candidate search is 0.006). Ungated rows published: **0**. So two things, both in your hands:

1. **The fit is too expensive.** It is the whole of T1 and T4.
2. **The 2c accept rule drops the ungated rows** whenever `coherentFallbackResidualCandidates` is on, which the baseline has on (`ftz_decoder.c:540`, `ftz_residual_b_accept`; QA's 2c record, "Ruling on the Developer's item 1", named this as the first lever for the decode rate).

## 1. What to build

| Id | What |
|---|---|
| **D1 Profile first** | Before changing anything, measure where one fit's CPU goes (`ft8_subfeas_fit_signal`, `native/ft8_lib_vendor/subfeas/subfeas_fit.c`: the workspace lease and `workspace_init_constants` (called at :717), `fine_fit_with_drift` (:498) with its Δt search (`DT_N_STEPS` 100, :64) and ḟ search (`FDOT_N_STEPS` 20, :68) and `freq_search` (:435), `lp_envelope` (:613), the final multiply). Report the split in ms per phase on one typical signal and the total per fit, in the result. A native timing build or `QueryPerformanceCounter` brackets in a scratch copy are fine; nothing of the profile stays in the product. |
| **D2 Exact speedups only** | Everything you can do that leaves `out_shat` **bit-identical** to today's fit for every input: for example constants computed once per workspace instead of per lease (the pool reuses workspaces), allocations and `memset`s that are not needed, a plan or twiddle table built per call, redundant passes, `double` where `float` was already the output, loop order and memory access. **Proof, mechanical:** a test that runs the old and new fit on at least 30 signals (synthetic with seeded noise at several SNRs and offsets, and the 2c fixtures) and asserts the `shat` arrays are equal byte for byte. The classic decoder uses the same fit, so the classic golden and every `SubtractionPass` test must stay green unchanged. State the speedup of D2 alone. |
| **D3 Subtract less** | Only if D2 does not bring the fits to about **2 CPU-s per cycle in total** (about 0.07 CPU-s per fit at 30 fits). The lean engine may skip the fit of a signal that **cannot unmask anything**: a signal subtracted in round r is only useful if the round's search can find something new within its patch window [f − 50, f + 100] Hz (`FTZ_PATCH_BELOW_HZ`, `FTZ_PATCH_ABOVE_HZ`). Rule to implement and test: **a round-0 result is fitted only if some candidate of the same round that did NOT decode lies within its patch window** (a failed candidate is the evidence that something is hiding there; it is in the arrays the round already holds). For rounds 1 to 3 the same rule applies to that round's own failed candidates. State the rule in the code as a function with a name, exported for the unit test. **This can lose decodes** (a masked signal that was never a candidate in the round-0 list); it is the only step of this task that changes outcomes, so: (a) it is a separate commit-sized change, off by a flag that defaults ON in the lean engine only and can be turned off through `ftz_params_t`/`LeanCycleParams` for QA's inspection; (b) the `lean:` line gains per-round counts of signals fitted and signals skipped by the rule (aggregates only, HK-037); (c) a unit test builds a fixture where the rule skips a fit and shows the cycle's published set is unchanged, and one where the skipped fit WOULD have unmasked a signal, and states honestly what is lost. |
| **D4 The residual accept rule** | Change `ftz_residual_b_accept` (`ftz_decoder.c:540`) so that, in a residual round, a CRC-valid new tier-B row is published when **F1b-passed, or ungated is on** (any frequency), whatever `rescand_on` says: the faithful union of classic's two paths (QA's 2c record gives the reasoning). `rescand_on` then no longer restricts a residual row; keep the parameter in the signature and the flag in the ABI, and document in the header that the flag is accepted and has no effect in the lean engine. Test 4d of `LeanEngineRoundsTests.cs` changes accordingly (the row with F1b failed and `rescand` on is now published as ungated, and counted in `n_ungated`). Say in the result that this reverses the 2c ruling at the Captain's direction. |
| **D5 Two tidies from QA's 2d review** | (1) In `DecodeLeanAsync`, narrow the `try` so that only `await native` is inside it; a publisher exception propagates as in classic, and the native task is always awaited. (2) In `ftz_decode_cycle_impl`, clear `resid_valid` when a round's subtraction starts, so that a non-fault error return after partial chunks does not export a half-subtracted buffer. One unit test each (a throwing publisher; a forced error after the first chunk). |
| **D6 Version and documents** | The shim version moves (native code changed), `libft8.dll` rebuilt, `libft8.version.txt` updated; the Linux and macOS binaries are for CI and QA. `REQUIREMENTS.md`: extend FR-108 **without writing any other FR number in prose** (Gate G3 counts them). The OpenSpec change `lean-decoder` (tasks, delta spec) updated and validated `--strict`. **VERSION:** none; run `check_version_bump.py` after committing. |

## 2. Tests (unit tests only)

1. **D2 equivalence:** the byte-for-byte `shat` comparison above, run in the Ft8 test project against the pre-change fit (keep a reference copy of the old function in the test native build, or record `shat` hashes from the old build on fixed seeds; say which).
2. **D3 rule:** the pure function tested at the window edges (−50, +100 Hz), with no failed candidate, with one inside, one outside; the two fixtures above; the flag off restores 2d's behaviour byte for byte (diff the batches, tiers, rounds and residual bytes of one fixture with the flag off against `6c746029`'s outputs recorded in the test).
3. **D4 rule:** the changed test 4d plus an end-to-end fixture with `rescand` on in which an F1b-failed row is published and counted ungated.
4. **D5:** the two tests above.
5. **Determinism and safety:** the 2d determinism test (1, 2 and 4 threads, byte-identical batches, tiers, rounds and residual) still passes; the ASan + UBSan fuzz (10,000 runs, `ftz_fuzz.c`) includes the changed paths, with D3 on and off; the CI `native-asan` job runs it.
6. **Steps 2a to 2d and classic unchanged:** their tests and the classic golden stay green at `DOTNET_PROCESSOR_COUNT` 4 and at the host's own; existing suites per project.

## 3. Settled for you (do not reopen)

1. The patch window, the 1,500 ms reserve, the 16-fit chunk, the lean engine's three batches, XC and `effort` are as in 2c and 2d.
2. **No new decode ideas** and no change to any gate except D4 (spec §6, closed arms: window, input scaling, OSR, candidate budgets). D3 is a cost rule, not a decode rule, and is flagged as the one step that can lose outcomes.
3. The fit's search ranges and constants stay as they are (inherited by design). If D1 shows the dominant cost is the Δt or ḟ search itself and D2 cannot touch it, **say so and stop at D2** instead of narrowing the ranges: QA takes that to the Captain.
4. The lean engine's thread count stays at its default of 2 (`decoder.threads`).

## 4. Out of scope

OSD, any other threshold, the classic decoder's behaviour (it must stay byte-identical), changing the default engine (DR-3), deleting classic code (DR-4), early decode.

## 5. Report back

The commit SHA; the per-project "Passed: N" lines; the `DOTNET_PROCESSOR_COUNT=4` result; **the D1 profile (ms per phase, per fit)**; the speedup of D2 alone and what the equivalence test compared; whether D3 was needed and, if so, what the fixtures show is lost; the rebuilt `libft8.dll` SHA and the shim number; anything in the lean cycle that differs from 2d outside D3 and D4.

## 6. What QA does afterwards (for your information)

After the HK-039 review and the push, QA runs **one** replay on the same Slice 40 slice (170 cycles, same flags, `lean-threads 2`, effort normal) and reports T1 to T4 against the same A6 numbers. The bars are targets, not gates; the Captain decides on the numbers. A run over 2 hours needs his explicit go (this one is about 25 minutes).
