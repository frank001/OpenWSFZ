# Developer task: LATE-SUB L1′, a late subtract-and-decode round (batch 5), behind `decoder.lateSubtractionRound` (default OFF)

**To:** Developer · **From:** QA · **Date:** 2026-10-30T14:36:00Z (`date -u`) · **Base:** `main` `c2c85c45` (v0.67). Branch suggestion: `dev/late-sub-round`.
**Authority:** the Captain, "go" (2026-10-30, after the Architect's "go, write the build spec").
**Read first, in this order:**
1. Build spec `qa/rr-study/2026-10-30-1322-architect-to-qa-build-spec-late-sub-l1p.md`, **with §7 Amendment 1 (F1 to F5)**. Both are on branch `arch/late-sub`, commit `33c50bd6`. Read them with `git show 33c50bd6:qa/rr-study/2026-10-30-1322-architect-to-qa-build-spec-late-sub-l1p.md`. **Where §7 names a part of §1 or §3, §7 replaces it.**
2. QA's (k) review `qa/rr-study/2026-10-30-1325-qa-to-architect-build-spec-late-sub-l1p-k-review.md` (on `qa/refset`, `106980f8`): it holds the code findings behind F1 to F5.
3. The reference implementation: `qa/rr-study/sub-feas/replay81/LateSub.cs`, mode `l1p` (`qa/refset`, `b7c17464`). The acceptance row B-EQ-2 compares your batch 5 with its published rows.

**You do not push.** Path afterwards: QA's HK-039 review of your commit; the acceptance rows on the PC; `pre_merge_check.py` from a clean checkout (QA runs it, HK-006); the third night on sol; the Captain's push go (HK-033) and merge sign-off (HK-010).

## What to build (C# only)

1. **The setting** `decoder.lateSubtractionRound` (bool; absent = false). `DecoderConfig`, a volatile field on `Ft8Decoder` set by the daemon before the first window, read once per window; overlay semantics of HK-035 (a partial post leaves it as it was); no Settings-page control. Model it on `decoder.coherentFallbackResidualUngated` (`Ft8Decoder.cs:246-257`). **OFF means every code path is today's, byte for byte.**
2. **When the round runs** (spec R2, with F2): setting ON, depth **Deep**, the coherent fallback ran this cycle (`fallbackReady`, whether or not it published), and **`CohFallbackAudioSelector.Select(...)` (`:43-64`) returns a residual buffer** (the same call the fallback makes; do not re-implement its rule). If `Select` returns the original audio or `Unavailable`, the round is skipped as `skipped-no-residual`. It does not run when pass 0 decoded nothing. Every other skip is counted and logged.
3. **Inputs** (spec R3 with **F1**):
   - **Buffer B** = what `Select` returned. No copy is needed: cite `SubtractionPass.cs:425` (clone) and the documentation at `:215` (input not modified) in the commit.
   - **Fit list** = the natives behind the decodes **`MapNative` published in batches 3 and 4**: the first occurrence of each text in the cycle, not already in `seen`, `IsPlausibleMessage` true. `FreqHz = round(OutFreqHz)`, `Dt = OutDtS` unrounded, plus `Snr` and `Message` as the fallback builds them (`:1114`). Not the raw `third.NewResults`. Add a small helper beside `MapNative` that returns the natives it kept alongside the `DecodeResult`s.
   - **`alsoKnown`** = batch-1 natives ∪ the **raw** batch-2 natives (`newFromResidual`).
   - Fit entries that fail `IsReencodable`/`EncodeMessage` are skipped exactly as in the third pass (`SubtractionPass.cs:331-343`, `:498`); the count goes in the log line.
4. **The call** (spec R4): `SubtractionPass.RunThirdPassAsync(_interop, B, fit, alsoKnown, EffectiveSubtractionThreads, _logger, _apConstraints, SubtractionCycleBudget - sw.Elapsed, ct)`. No new budget constant; the pass's own deadline and reserve logic is the guard (all-or-nothing). `SkippedNoNew`, `Abandoned` and `Failed` are counted like the third pass's (`:1018-1032`), beside `_thirdPass*`.
5. **Publication** (spec R5 with **F4**): new decodes go through `MapNative(…, PathResidual)` with the same per-cycle text de-duplication set, and are handed off as **batch 5** through the **existing** `onFallbackBatch` delegate (`Ft8Decoder.cs:554, :1133`; staged delegate `DecodePump.cs:166`) with the number 5, only when non-empty. **No new callback, no change to `DecodeStaged`'s signature (`DecodePump.cs:45`).** Ordering: after the fallback's batch is handed off, so batches 1 to 4 and their timing do not move. The round's unpack is the cycle's last hash-table access, under the decode gate. QA found no consumer that switches on a specific batch value (`DecodePump.cs:166-168` sends every number other than 1 to `PublishSecondAsync`; the QSO services test `BatchNumber > 1`; `LateBatch` logs only); confirm that and list anything else you find with FILE:LINE. Update the four doc comments that say "2, 3 or 4" (`DecodeBatch.cs:12`, `DecodePump.cs:83, :247`, and the one you find).
6. **The log line** (spec R6, once per Deep cycle while the setting is ON), with `fbEndMs` added (§7):
   `Late subtraction round: outcome={ran|skipped-<reason>|abandoned|failed|no-new}, buffer={R3|R2}, fit={n}, refused={n}, new={n}, published={n}, fbEndMs={…}, startMs={…}, elapsedMs={…}, endMs={…}, batch=5, batch5PublishMs={…|-1}`. `startMs`/`endMs` are on the decode's own clock, as `fbStartMs`.
7. 🔴 **No native change.** `git diff --stat origin/main -- native/ src/OpenWSFZ.Ft8/Native/` must be empty and the built `libft8.dll` SHA-256 must equal `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`. If a native change looks unavoidable, STOP and tell QA.

## Tests (TESTING_STRATEGY §11: no fixed sleeps; CI runs macOS)

OFF is a no-op; each skip reason (setting OFF, Normal depth, fallback not run, no residual from `Select`, nothing decoded in pass 0); an abandoned or failed round publishes nothing and does not throw; batch-5 number and ordering (after the fallback's batch); the fit list is the published batch 3 ∪ published batch 4 with unrounded Dt, and a batch-3 text that repeats a batch-1/2 text or is implausible is **not** in it (the F1 case); the refusal count; absent key = OFF, explicit round trip, a partial post leaves it as it was; the log line fields; and **the hash-table ordering: the round's unpack happens after the fallback's, under the decode gate** (a test, not a statement). Control the clock through the existing `BudgetClock`/`TimeProvider` seam where time matters (stub backend, named budget constants, no sleeps).

## Housekeeping

- `VERSION` 0.67 → 0.68 in every place the gates check (the `REQUIREMENTS.md` anchor too). Run `check_version_bump.py` and G9a/G9b (**G9b reads the proposal from git**).
- `REQUIREMENTS.md`: a new FR at the next free number on `origin/main` (FR-101 + 1 at the time of writing) and a changelog row. The FR covers the setting, the R2 gate, batch 5 and the budget rule, states "Deep only, needs the fallback ON, default OFF, turning it ON starts a new era", and has one sentence on lateness: a batch 5 is published to the panel, `ALL.TXT` and reporting but can arrive too late to affect that cycle's TX decision, as batch 4 can today.
- **OpenSpec change `late-sub-round`:** it does not exist yet. Write `proposal.md`, `design.md` and the delta spec with scenarios under `openspec/changes/late-sub-round/` from the spec. `tasks.md` is QA's (HK-015): leave it out and tell QA when the folder is ready, so QA adds it and commits the change on `qa/refset` before you run G9b. `openspec validate late-sub-round --strict` before committing.
- `pre_merge_check.py` is QA's gate, not yours.

## Not in this round

No fallback on B or on R4; no change to batches 1 to 4, T1, R-F4 or multi-set; no payload subtraction (#273); no default ON; no Settings control; no re-measurement (QA runs the rows).

## Report back (HK-001 sections), then STOP

The commit hash; points 1 to 7 answered with FILE:LINE (and the line drift against `c2c85c45`); the consumer list of point 5; the full Windows suite counts; the new tests named, with how the clock is controlled; `git diff --stat origin/main -- native/ src/OpenWSFZ.Ft8/Native/` (empty) and the DLL SHA-256; the property name as spelled in `DecoderConfig`, which QA needs for the harness setter. Do not push.
