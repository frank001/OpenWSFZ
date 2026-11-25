# Developer task: DR-2 step 2d, the lean engine's three batches, XC (S4) and `decoder.effort`

**Date:** 2026-11-25
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** `docs/decoder-rebuild/spec-dr2-lean-decoder.md` §2.1, §2.3 (S4, effort), §3 step 2d (read with `git show arch/decoder-rebuild:docs/decoder-rebuild/<file>`); the Captain approved the plan on 2026-11-24.
**Status:** Proposed. HK-011: `src/` and `native/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). Do not push, open a PR or merge; QA pushes.
**Branch:** `feat/lean-2d`, a child of `feat/lean-2c` (tip `0c2db3b2`, reviewed, APPROVED, record `qa/rr-study/2026-11-25-qa-code-review-dr2c-lean-subtract-retry-0c2db3b2-APPROVED.md` on `qa/same-chain`). If CI on `feat/lean-2c` turns red, QA tells you before you build on it.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. **You run no replay.** QA runs the one Slice 40 replay after the review (§6). Run tests per project (HK-022) and read the per-assembly "Passed: N" lines. Run the golden and lean tests once with `DOTNET_PROCESSOR_COUNT=4` as well.

---

## 0. Why

Steps 2a to 2c built the whole decode inside `ftz_decode_cycle`, but the C# side still publishes one list at the end of the call. This step makes the lean engine a complete engine: batch 1 leaves **before** the subtract loop starts (so the panel and the QSO logic see round 0 at about the same time as today), batch 2 carries rounds 1 to 3, and the cross-cycle stage (XC) runs on the final residual and publishes batch 3. It also adds `decoder.effort`. After this step the lean engine does everything the classic one does, and QA measures T1 to T4 once.

## 1. What to build

| Id | What |
|---|---|
| **D1 Three batches** | With `decoder.engine = lean` the cycle goes through the existing entry `Ft8Decoder.DecodeStagedAsync` (callback per batch). **Batch 1** = the results of round 0, delivered exactly once, always (an empty batch 1 is a real cycle), and delivered **before round 1 starts**. **Batch 2** = the results of rounds 1 to 3, only when non-empty. **Batch 3** = XC detections, only when non-empty (D3). One shared per-cycle text set across the batches (a text is published once per cycle), the same plausibility filter, region and worked-before lookups and `Path` tags as `DecodeLeanAsync` has today. |
| **D2 How batch 1 leaves early** | Your choice (spec §2.1): two native calls on a context handle (`ftz_decode_first` / `ftz_decode_rest`), or a callback from native after round 0. **State which, and why, in the result.** Constraints either way: (a) native must not be re-entered while it holds `ftz_call_lock` (the callback must not call any `ftz_*` or other native function); (b) nothing may throw across the native boundary; (c) the publish of batch 1 must not make the S3 wait on the consumer (the daemon's publish awaits subscribers; if you use a callback, hand the batch to the managed side and let native go on); (d) a native error or fault after round 0 still leaves batch 1 delivered and logged; (e) the early-return paths (silent cycle, native error with nothing written) still deliver batch 1 once, empty or not, as `DecodeStagedAsync` does for classic. |
| **D3 The residual buffer and XC (S4)** | Native returns the **final residual buffer** to C# (a caller-allocated `out_residual` of `FT8_EXPECTED_SAMPLES` floats, may be NULL; a flag or return code says whether it holds a residual). The residual is the buffer as of the **last subtraction made**: results found in the last round are **not** subtracted for XC's sake (that would be a further round of fits; T1). A cycle in which nothing was subtracted has **no residual**: XC is a counted, logged skip (`XcOutcomeNoResidual`), as classic's "nothing decoded". Then run `CrossCycleTemplateStage` **unchanged** on that buffer: same settings (`crossCyclePrior`, shadow, threshold, parity threshold, colocation veto, all read once per cycle), same `Expired` budget rule, `workers` = the lean thread count, same log line and probe records as classic's `RunCrossCycleStageAsync`, detections published as **batch 3** with `PathTemplate`, mapped with `xcBatch: 0` so they never enter the prior store (no chaining). Reuse the existing code: extract `RunCrossCycleStageAsync` or share its body; do not copy it. |
| **D4 Priors** | Priors are recorded from batch 1 and batch 2 of the lean cycle (`Prior.Batch` = 1 or 2). The R14 co-location veto and the shadow null read "the decodes of this cycle's earlier batches" as batches 1 and 2. Update the doc comments of `CrossCyclePriorStore` / `PriorBatch` ("1 to 5", "batch 6") so they say what is true for both engines; classic's numbering is unchanged. |
| **D5 `decoder.effort`** | New setting `decoder.effort`: `normal` (default; absent key = `normal`) or `fast`. Read once per cycle, takes effect on the next cycle, applies **only** with `engine = lean`. `fast` = **no tier B** and **S3 limited to 1 round** (spec §2.3); CQ-AP and XC are unchanged in `fast`. Native: a new flag (for example `FTZ_FLAG_NO_TIER_B`) and `max_rounds = 1`; `FTZ_PARAMS_VERSION` and the shim version move as in 2b and 2c. Config: `DecoderConfig` key with a names class like `DecoderEngineNames`, validation exactly as `engine` has it (follow 2a: what an unknown value does, the settings page and API if `engine` has them, `config.example.json`). An unknown value reads as `normal`; say how you handled it. |
| **D6 Routing** | `DecodePump` today picks `DecodeSingleBatch` / `DecodeTwoStage` / `DecodeStaged` from `SubtractionEnabled`, `DecodingDeep` and `CoherentFallbackOn` (`DecodePump.cs:154-174`). With the lean engine those classic keys are ignored (spec §2.5): add a `LeanEngine` hook (`Func<bool>?`, null = false) and route a lean cycle to `DecodeStaged` **whatever the classic flags say**. With it false or absent the pump is statement-for-statement what it is today. |
| **D7 Budget and abandoned** | The cycle budget is today's (13 s less the publish reserve). XC gets what is left, with the same `Expired` rule as classic. An XC stage the budget stops publishes nothing and is logged as classic logs it; batches 1 and 2 stand. The `abandoned` flag of the `lean:` line stays the native one. |
| **D8 Log line** | The `lean:` line gains aggregates only (HK-037): effort, batches delivered (1 / 2 / 3, as 0 or 1 each), XC outcome and detection count. The XC stage keeps **its own existing log line and probe records unchanged** (QA's replay harness reads them). |
| **D9 Documents** | `REQUIREMENTS.md`: extend FR-108, **without writing any other FR number in prose** (Gate G3 counts them). The OpenSpec change `lean-decoder` (tasks, delta spec) updated and validated `--strict`. **VERSION:** none, the engine stays internal and default `classic` (DR-3 bumps it); run `check_version_bump.py` after committing. |

## 2. Tests (unit tests only)

1. **Batch 1 before round 1.** With the 2c fixture (a strong and a masked weak signal): batch 1 holds the strong one only and is delivered **while the native cycle is still running or at least before round 1's results exist**. Prove the ordering mechanically (for example the publish callback records whether the interop call has returned, or a test hook blocks S3 until batch 1 was observed). Batch 2 holds the weak one. Batch 3 is empty and not delivered.
2. **Empty batch 1 is still delivered once.** A cycle with nothing to decode (and a native-error cycle) delivers batch 1 exactly once and nothing else.
3. **One text, once per cycle across batches.** The same text in round 0 and a later round is published in batch 1 only.
4. **Priors.** After the cycle the store holds the batch-1 and batch-2 messages with `Batch` = 1 and 2; a batch-3 detection never enters it (assert the counts, as the classic tests do).
5. **XC on the lean residual.** A message published in an earlier cycle of the same parity, present below the decode threshold in this cycle's audio and detectable on the residual, is published as batch 3 with `PathTemplate`. Build the fixture from the existing XC tests (`CrossCycleTemplateStage` tests) and say how. Also: a cycle with no subtraction has no residual and XC is a counted skip; the shadow null and the co-location veto read the lean cycle's decodes (one test each).
6. **`effort = fast`.** Stats show tier B not attempted and at most 1 round; `normal` is unchanged (tier B attempted, up to 3 rounds); an absent or unknown value reads `normal`; the setting is read once per cycle.
7. **Routing.** The pump sends a lean cycle to `DecodeStaged` with `SubtractionEnabled` false, with depth Normal and with the fallback off; with the lean hook false or absent every existing pump test passes unchanged.
8. **Determinism and the residual.** Same audio and starting hash state: byte-identical batches, tiers, rounds **and residual buffer** at `threads` = 1, 2 and 4 (diff the residual bytes mechanically).
9. **Memory safety.** The ASan + UBSan fuzz harness extended so the 10,000-run fuzz includes the new native entry (with `out_residual` NULL and non-NULL, with and without the no-tier-B flag), on random, clipped, silent, DC and truncated audio; the determinism run includes it. The CI `native-asan` job runs it.
10. **Steps 2a to 2c unchanged.** Their tests and the classic golden stay green at `DOTNET_PROCESSOR_COUNT` 4 and at the host's own; existing suites per project.

## 3. Things settled for you (do not reopen)

1. **The 2c residual-candidates ruling stands** (QA's record, "Ruling on the Developer's item 1"): leave `ftz_residual_b_accept` as it is. The replay reads its effect.
2. The patch window, the accept rules, the 1,500 ms reserve, the 16-fit chunk: unchanged.
3. XC's detector, thresholds and window are **not touched** (closed family).
4. The lean engine still has no early decode; `DecodeEarlyAsync` stays as is.
5. Nothing here tries to make the fits cheaper. The S3 cost (about 0.6 CPU-s per subtracted signal, QA's review) is what the replay measures first; do not pre-empt it.

## 4. Out of scope

OSD, any new gate or threshold, any closed arm (window, input scaling, OSR, candidate budgets), changing the default engine (DR-3), deleting classic code (DR-4), making the fit cheaper.

## 5. Report back

The commit SHA; the per-project "Passed: N" lines; the `DOTNET_PROCESSOR_COUNT=4` result; **how batch 1 leaves early (D2) and why**; how test 1 proves the ordering; how test 5's XC fixture was built; what an unknown `effort` value does; any place where the lean cycle's publishing differs from classic's staged decode; the rebuilt `libft8.dll` SHA and the shim number.

## 6. What QA does afterwards (for your information, not your work)

After the HK-039 review and the push, QA extends the replay harness (`--engine lean`, `--effort`), pins the lean build, and runs **one** Slice 40 replay (170 cycles) of the lean engine against the DR-0 A6 baseline: T1 `cpu_net` ≤ 6.31 CPU-s per cycle, T2 rate ≥ 83.39 %, T3 `ours_only` ≤ 4.27 %, T4 `last_p95` ≤ 3,000 ms and `abandoned = 0`. They are targets to report, not gates; the Captain decides on the numbers. A run over 2 hours needs his explicit go.
