# HK-039 code review: LATE-SUB L1' (`dev/late-sub-round`), a late subtract-and-decode round, batch 5, behind a setting (default OFF)

Reviewed-commit: b1d8a06e259efdfba62ed0f27cf29f5a58190613
Verdict: APPROVED

**Reviewer:** QA · **Date:** 2026-10-30T14:54:26Z (`date -u`) · **Base:** `main` `c2c85c45` (v0.67) · **Commit:** `b1d8a06e` (code, tests, OpenSpec change, VERSION 0.68, FR-102) · **Spec:** build spec `33c50bd6` (Amendment 1, F1 to F5), handoff `qa/rr-study/2026-10-30-1436-qa-to-developer-handoff-late-sub-l1p.md`.

## What I read
The whole `src/` diff (8 files, +207/-18): `Ft8Decoder.cs` in full, `DecoderConfig.cs`, `Program.cs` (both sites), `DecodePump.cs`, `DecodeBatch.cs`, `LateBatch.cs`, both QSO services (comments only), `VERSION`, `README.md`, `REQUIREMENTS.md` (FR-102, row 1.64), and the stat of the five new test files (+767 lines). Not read line by line: the OpenSpec text (validated by the Developer) and the test bodies beyond their names and the F1 case.

## What I ran (clean detached worktree at `b1d8a06e`, `_qa-scratch\late-sub\dev-tree`)
- `dotnet test` Ft8.Tests `--filter LateSubtractionRound`: **21 passed, 0 failed**. Daemon.Tests `--filter "LateSubtractionRound|DecodePumpTests"`: **16 passed, 0 failed**. (The Developer's full-suite counts, all green, are not re-run; QA runs the full gate at `pre_merge_check.py`.)
- `git diff --stat c2c85c45 b1d8a06e -- native/ src/OpenWSFZ.Ft8/Native/`: empty. Built `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` (equals the pin) in all three build and source locations.

## Findings against the amended spec
- **R1, OFF is today's path.** The only change reachable with the setting OFF is the optional `keptNatives` argument (null) and two empty lists; no new call, no log line, no counter. `lateOn = twoStage && _lateSubtractionRound` is read once per cycle. B-OFF will test it byte for byte.
- **R2 / F2.** The buffer comes from `CohFallbackAudioSelector.Select(audioMode, normalisedPcm, deepForFallback, reportForFallback, thirdResult)`, the fallback's own call and arguments; `!IsResidual` gives `skipped-no-residual`. Fallback not run, nothing decoded in pass 0 and Normal depth are separate counted skips. Deep only holds because the round function sits after the Deep-only code; Normal returns earlier with `skipped-normal-depth`.
- **R3 / F1.** The fit list is `batch3Kept` then `batch4Kept`, filled by `MapNative` at the point where it adds a decode to its result (`keptNatives?.Add(nr)` directly before `mapped.Add`), so it is the first occurrence of each text, not in `seen`, plausible: the harness rule. `alsoKnown` is batch-1 natives plus the raw `newFromResidual`. Batch 4's kept natives are the ones the fallback built (rounded Hz, unrounded Dt). No copy of the buffer; the Developer cites `SubtractionPass.cs:425` and `:215`, which I verified in the review of the spec.
- **R4.** `RunThirdPassAsync(_interop, choice.Pcm, fit, alsoKnown, EffectiveSubtractionThreads, _logger, _apConstraints, SubtractionCycleBudget - sw.Elapsed, ct)`: the same arithmetic as the third pass, no new constant. An empty fit list does not call the pass (`no-new`); that is a harmless difference from the harness, which would also find nothing to subtract.
- **R5 / F4.** `MapNative(newNatives, PathResidual)` with the cycle's `seen` set, then `onFallbackBatch!(LateRoundBatch = 5, batch5)` only when non-empty, after the fallback's hand-off. No new callback, no `DecodeStaged` signature change. `onFallbackBatch` cannot be null there: the round needs `fallbackReady`. The consumer list is the one I found in the spec review; the doc comments say "2, 3, 4 or 5". **I read the order claim as true** (the round starts after `RunCoherentFallbackBatchAsync` returned, so the fallback's unpack is done; the pump holds the gate around the whole staged call), but the Developer is right that no test goes through the pump with the real gate; the B-EQ rows are the real check.
- **R6.** The log line has every field named in the spec plus `fbEndMs`; `endMs` is taken after mapping and before the hand-off, and `elapsedMs = endMs - startMs`, which is what the timing rows need. The line is written in a `finally`, so it appears even if the hand-off throws.
- **R7.** VERSION 0.68, README and the REQUIREMENTS anchor read 0.68; FR-102 states Deep only, fallback required, default OFF, new era, and the lateness sentence; changelog row 1.64.

## Observations (none blocks acceptance)
1. **Two `Third pass:` lines in a cycle with the round.** `RunThirdPassAsync` writes its own. QA log parsers that count that line once per cycle (`cf_r14_log.py`, `third_pass_counters.py`, `ls_analyse.py`) would count twice with the setting ON. I accept this: no `SubtractionPass` change is wanted, and the sol analysis reads the `Late subtraction round:` line and the replay outputs, not the third-pass line. QA will say so in the §4 freeze record.
2. **`refused` for an abandoned round** is `fit - FittedSignals`, which can read as "all refused" if the pass did not count fits before abandoning. It is descriptive only (no row reads it); I will treat it as unreliable for `abandoned` cycles in the report.
3. **`skipped-normal-depth` is written on Normal cycles while the setting is ON.** One line more than "once per Deep cycle". Accepted; the sol arms run Deep, and QA filters on the token.
4. **Outcome tokens as the Developer defined them** (`ran` = a pass that completed, even with `new=0`; `no-new` = skipped-no-new or an empty fit list) are accepted and will be used in the timing rows.

## Verdict
**APPROVED.** The code matches the amended spec on every point I could check by reading and by the 37 tests I ran. What remains for the acceptance rows is what reading cannot show: B-OFF, B-EQ-1, B-EQ-2 and B-AB on the refset night. `tasks.md` for the OpenSpec change is added by QA on `qa/refset` with the change folder copied unedited from `b1d8a06e`.

Nothing pushed. This record does not authorise a push (HK-033) or a merge (HK-010).
