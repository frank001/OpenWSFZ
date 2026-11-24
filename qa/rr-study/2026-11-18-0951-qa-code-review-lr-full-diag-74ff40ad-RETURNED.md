# HK-039 code review: LR-FULL diagnostic switches, `74ff40ad` (QA, 2026-11-18 09:51Z `date -u`)

Reviewed-commit: 74ff40ade9750260ee0755a14da0f8655bee17e9
Verdict: RETURNED (two required changes, C1 and C2; the OFF path itself is sound)

Task `dev-tasks/2026-11-18-lr-full-diagnostic-switches.md` (`qa/same-chain` c811f498). Developer worktree `worktrees\dev`, branch `feat/lr-full-diag`, base `66b3ddf1` (merge-base verified). Counts only; no message text (HK-037).

## 1. Scope fence: respected
`git diff --stat 66b3ddf1 74ff40ad`: 13 files, +1223 / -5. `src/`: `DecoderConfig.cs` (+2 keys, appended optional constructor parameters), `Program.cs` (+4 setter calls, same pattern as the v2 and XC setters), `Ft8Decoder.cs` (+217). `native/` diff empty. Tests in Ft8.Tests, Config.Tests, Web.Tests; an OpenSpec change `lr-full-diag` and `REQUIREMENTS.md` FR-106 (the repo's gates). No change to `DecodeResult`, `Path`, the QSO services, PSK Reporter, the panel, `LateBatch.cs` or any batch constant.

## 2. The OFF path (read line by line)
Every new statement is behind `diagX1On`, `diagX2On` or a null `diagSink`:
- `diagX1On = resCandOn && _diagThirdRunUngated`, `diagX2On = lateOn && _diagLateFallbackOnResidual`, `diagSink = DiagRowTagSink`: three reads, no behaviour.
- The late round's third pass gets `captureCohSnapshot: diagX2On`: `false` OFF, which is the default parameter value, so the call is the one of today.
- `primaryCount = batch5.Count` taken before the X2 call; OFF it equals the old `batch5.Count` everywhere it replaces it (`_lateRoundDecodes`, `LogLateRound`).
- The gate site keeps the same `resNewGated++; continue;` for `!diagX1On`.
- `LogLateSkip` adds a call only `if (diagX2On)`.
- With a sink attached and both switches OFF only the sink is called; no row, call or log line changes.
- **Independent proof, by QA:** the two golden captures were run against the **unmodified 66b3ddf1 source** (scratch checkout `_qa-scratch\fd-proxy\tree`, only `LrFullFixture.cs` and `LrFullOffIdentityTests.cs` copied in, the two `SetDiag...` lines and the explicit-false test reduced to `d => d`): `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --filter "FullyQualifiedName~LrFullOffIdentity"`, **3 passed, 0 failed** at 09:50:59Z. So the goldens ARE the base behaviour, not only the Developer's recording of it.

## 3. X1, X2, tags: correct, except C1
- **X1:** only F1b-passed rows reach the gate (`ThirdRunCandidates`, `NewGated` only); with X1 ON an above-gate row is kept and tagged `X1ThirdRunAboveGate`, at or below it `V2ThirdRunAtOrBelowGate`; `resNewGated` stays 0 ON, as the Developer says; effective only where `resCandOn`.
- **X2 mechanics match the product's own runs:** `Merge(null, run.Rows, ungatedOn)` then `CoherentFallbackSelector.Select(merged.Rows)` is the first two runs' path (`:1745`, `:1760`); `ungatedOn` is the product's own (setting ON and Both mode); the run is `RunCoherentFallback(r4, snap4, leftMs, workers, multiSetOn, timeStr, ct)` as the other runs call it; `seen` is the per-cycle set `MapNative` fills, so by that point it holds batches 1-4 and batch 5's primary rows (the de-duplication the task asks for), and `MapNative` de-duplicates again; the rows are appended to `batch5` and go out in the same `onFallbackBatch(LateRoundBatch, ...)`; the late round's fit and counters are untouched; skips are counted and never throw; tags go out before the publish; `x2Steps` is only touched with a sink.
- **Tags:** an `internal` sink, `DecodeResult` and `Path` untouched (the task's constraint), a throwing sink is logged and ignored.

## 4. Required changes

### C1. X2 must not withhold the rows of an abandoned run (the product never does)
`Ft8Decoder.cs:1430` (`if (run.Stats.Abandoned > 0) { ... x2Run = "abandoned"; }` with no row published). In the product `Stats.Abandoned` **counts candidates left unstarted on the run's deadline**; every fallback run (first, second, third) publishes the rows that completed and only logs the count. X2 is the only run that discards them. The Developer's design note D6 reads "all-or-nothing, as the late pass itself is", but the late PASS (the primary third pass, outcome `Abandoned`) is a different mechanism from a fallback run's candidate count. The ambiguity was in QA's task ("an abandoned run publishes nothing from it"); QA's intent was a run that FAILED or did not run, and this is QA's correction. **Why it matters:** NET(X2) must measure the step as the product would run it. With the shared budget, an abandoned candidate is exactly what happens when time is short, so all-or-nothing makes X2 lose its completed rows on the cycles where it was already under time pressure, and biases NET(X2) down against the step under test. **Change:** publish the rows of a run that returned, whatever `Stats.Abandoned` is; keep `DiagX2Abandoned` as a count of runs with at least one abandoned candidate and add the abandoned-candidate count to the `Diagnostic X2` line (`abandonedCandidates=`); a `null` result (failed) still publishes nothing. Update the test that pins the old behaviour, design D6 and the delta spec.

### C2. The OFF-identity goldens depend on the checkout's line endings (3 of 21 LR-FULL tests FAIL on a clean checkout of `74ff40ad`)
This repository's blobs are CRLF (`git show 74ff40ad:tests/OpenWSFZ.Ft8.Tests/LrFullOffIdentityTests.cs`: 76 lines, 76 CR; the base `Ft8Decoder.cs` blob has 2,317 CR). The goldens are C# raw string literals, which take the file's line endings, while `LrFull.Capture` joins with LF (`(char)10`). On a clean checkout:
`git worktree add --detach D:/Projects/claude/_qa-scratch/lr-full/rev-74ff40ad 74ff40ad` then `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --filter "FullyQualifiedName~LrFull"` (09:49:39Z): **Failed: 3, Passed: 18, Total: 21**, all three `OffIdentity_*` tests, the string lengths 1,088 vs 1,073 and 1,281 vs 1,265 (one CR per line), first difference at the first line break. With the CRs stripped from the test files (scratch only) the same command gives **21 of 21 passed**, so line endings are the whole cause. The Developer's report says the full suite passed (all projects, 0 failed); on this blob the LR-FULL filter does not pass (QA ran only that filter on the clean checkout, not the other projects), so the report cannot have been produced from this exact content (QA cannot say why; both worktrees have `core.autocrlf=true`). These are the very tests that pin OFF identity, and they would fail on CI too. **Change:** make the comparison independent of line endings (normalise `\r\n` to `\n` on the golden and on the capture), look for the same dependency in the other new tests, and **re-run on a clean checkout of the NEW commit**: the LR-FULL filter and the full unfiltered suite, quoting the exact command lines, the worktree and the per-project counts (HK-022).

## 5. Observations (no change required)
- **O1 budget reserve:** X2's budget is `SubtractionCycleBudget - sw.Elapsed` with no `CoherentFallbackPublishReserve` (250 ms) taken off, as the late round's own pass; the product's other fallback runs subtract it. This follows QA's task text ("as the late round computes it"); X2 may therefore delay batch 5's publish by up to 250 ms. QA reports it beside LATE and V-RUN; no change.
- **O2 de-duplication:** against earlier batches it is by text (via `seen`), within the run by payload (`Select`). Equal payloads give equal text, so no difference in practice.
- **O3:** saved configs will now carry two explicit `false` keys; the config tests cover round trip, absent key, overlay POST (HK-035).
- **O4:** rows of the first two runs carry no tag (they are the ordinary path); that is as designed.

## 6. What QA does on the corrected commit (before any acceptance run)
The mutation pass the task lists (gate bypass, F1b condition, de-duplication, the budget check, batch-5 publication, admission, `captureCohSnapshot`, the abandoned handling), a replay **V-OFF** (20 cycles, `nc.tsv` and outcomes identical to the `66b3ddf1` harness build), the full unfiltered suite on a clean tree, then the harness build and the pilot. Nothing is run on `74ff40ad`.
