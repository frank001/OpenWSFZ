# QA code review: COH-RES-CAND v2, `a943512e` (branch `feat/coh-res-cand-v2`, base `origin/main` `70bc72b1`, v0.71, shim 20260072): RETURNED with three small required changes

Reviewed-commit: a943512e47339b38c96c7a7dfa2871d041f2c3d7
Verdict: RETURNED

Reviewed 2026-11-12 (`date -u` read 14:24:19Z at the last check). Spec: `arch/coh-res-cand-v2` `qa/rr-study/2026-11-12-1340-architect-to-qa-spec-coh-res-cand-v2.md` §2 R1 to R8, §8 A1.2, §9 A2.1 (`538ecc29`); QA's task `dev-tasks/2026-11-12-coh-res-cand-v2.md` (`f3d04f17`). Diff `git diff 70bc72b1 a943512e`: 14 files, +984 / −18; `src/` 5 files (about 180 lines), tests 3 files, docs 5.
This review gates the replay runs (HK-039). **A delta review of the three changes below is enough; I do not need to re-review the rest.** Not yet run (QA, before any push, HK-006): `pre_merge_check.py`, G8 with QA's `tasks.md`, the WSL Debian compile.

## Verdict in one paragraph

The design is implemented as specified and the implementation is clean: the first two runs are untouched, the third run's rows never enter `Merge` (so R-F4 cannot reach them), the gate sits on the one place the published integer Hz is formed, OFF takes no snapshot and writes an identical log line, and the tests are well aimed (28 cases; of my 17 individual mutants 12 were killed, and the Developer's own three). **Three things stop an approval:** (1) the guard that tells a re-found batch-1 text from a new one is not pinned by any test (and can make B-WIRE row (ii) pass on nothing); (2) the third run's budget arithmetic, R3's own sentence, is not pinned either; (3) the log line's `abandoned` figure cannot see the third run, so the registered row B-AB cannot see the lever's own deadline behaviour. All three are small.

## Mechanical checks (clean checkout of `a943512e`, `_qa-scratch\review-a943512e`)

| check | result |
|---|---|
| `git diff --stat 70bc72b1 a943512e -- native/ src/OpenWSFZ.Ft8/Native` | **empty** (B-NAT precondition holds); committed Windows DLL SHA-256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` = the pin |
| `dotnet test OpenWSFZ.slnx -c Release`, unfiltered | **all green**; counts: TraceabilityCheck 34, LicenseInventory 24, Rig 41, TestSupport 12, Audio 40, Config 202, E2E 9, Web 445, Daemon 935, **Ft8 734**. Identical to the Developer's report in every project |
| Developer's R2 citations (`ft8_shim.c:1993-1998`, `:2027-2030`, `:2039`, `:2769-2772`, `:2936`) | read and **accurate**: candidates and payloads are recorded before the diagnostics switch is consulted, so the snapshot is complete with diagnostics off; a CRC-valid payload is `KNOWN` iff it is in the snapshot's payloads |

## R rows against the diff

- **R1 setting:** `decoder.coherentFallbackResidualCandidates`, default false in the record and the constructor; setter `SetCoherentFallbackResidualCandidates` (the harness name); read once per cycle (`resCandOn`, `Ft8Decoder.cs:669`); two daemon setter calls (initial and per config change); overlay tests in Config and Web. ✅
- **R2 snapshot:** taken on the `DecodeAll` thread right after the call (`SubtractionPass.cs:463-475`), only when requested; a failed snapshot is swallowed, logged, and leaves the cycle on the two runs of today. ✅ The port from `b0d01f4f` is described honestly (what was and was not taken).
- **R3 the new run:** after the two runs (unchanged code above it), `choice.Pcm` with `choice.CohSnapshot` (chosen by the same step-down as the audio, so list and buffer cannot come from different buffers), budget `budgetMs − (sw.Elapsed − fbStart)`, the same arithmetic as the second run (`:1314-1316`); `skipped-budget`, `no-snapshot`, `no-residual` as specified. ✅ The Developer added a fifth token `failed` (the third run returned null); harmless, and it is not a `no-snapshot` for B-WIRE (i). **Budget value untested: required change 2.**
- **R-F4:** acts only inside `Merge` on the first two runs' rows. The third run's rows go through `ThirdRunCandidates` (`NewGated` only, then the selector's one-row-per-payload rule). I mutated the filter (M7) and the admitted map (M15): both killed. ✅
- **R4 gate:** `ResidualRunMaxFreqHz = 1097` with its source; `PublishedFreqHz(row) = (int)Math.Round(row.OutFreqHz)` is the ONE place the value is formed, used by the first two runs' publication (`:1372`) and the third run's; the gate takes that same integer, `<=`. Boundary and rounding tests exist. ✅ Mutants M6, M14 killed. **The "new text" guard in front of the gate is unpinned: required change 1.**
- **R5 publication:** third-run rows appended after the first two runs' rows, same `MapNative`, same de-duplication; they feed L1′'s kept list like any batch-4 row. ✅
- **R6 log:** only when `resRun` is non-null (setting ON, Both mode, fallback running); with the setting OFF the format string gets an empty argument and the line is byte-identical (the Developer's regex test, and M8/M9 killed). ✅ **One field is missing for B-AB: required change 3.**
- **R7 docs:** VERSION 0.71, FR-104 (FR-103 was CQ-AP), changelog 1.67, OpenSpec `coh-res-cand-v2` (proposal, design, delta spec; `tasks.md` is mine), no `native/`. ✅
- **R8 tests:** the 28-case class plus Config and Web overlay tests, all `FR-104:`; no fixed delays (manual clock). ✅ with the gaps below.

## Mutation results (QA's own, on `a943512e`; each mutant applied to a clean tree, `CohResCandV2Tests` run, reverted)

| # | mutant | result |
|---|---|---|
| M1 | third run reads pass 0's snapshot instead of its own | **killed** (2) |
| M2 | skipped-budget guard removed | **killed** (2) |
| **M3** | **third run gets the FULL budget (`budgetMs`) instead of what is left** | **SURVIVED** |
| **M4** | **`seen.Contains(trimmed)` (the batch 1 to 3 "already published" test) removed** | **SURVIVED** |
| M5, M17 | the first-two-runs text guard alone / the payload skip alone | survived: **redundant with each other**. Removing BOTH is **killed** (`On_TextAlreadyPublished_NotNew_NoDuplicate`), so that pair is covered |
| M6 | gate constant 1097 → 1098 | **killed** (7) |
| M7 | `ThirdRunCandidates` also takes `GatedOut` rows (R-F4 leak) | **killed** (1) |
| M8 | OFF takes the residual snapshot too | **killed** (3) |
| M9 | the setting acts outside `Both` mode | **killed** (2) |
| M10 | `resNewGated` not counted | **killed** (2) |
| M11 | `resRun` always `ran` | **killed** (1) |
| M12 | `resCand` R2 / R3 tokens swapped | **killed** (8) |
| M13 | third-pass buffer's snapshot not captured | **killed** (10) |
| M14 | gate on the unrounded frequency | **killed** (1) |
| M15 | R-F4 flag leaks into the third run's admitted map | **killed** (1) |
| M16 | kept third-run rows lose their `Edge` flag | survived (minor, see notes) |

The Developer's own mutants (`<` for `<=`, truncation for rounding, an R-F4 leak) are not repeated here.

## Required changes (small; a delta review follows)

**RC1: pin the "already published in batches 1 to 3" guard (M4).** `On_TextAlreadyPublished_NotNew_NoDuplicate` puts the batch-1 text (id 7) among the third run's rows, but that payload is also one the first two runs publish, so the payload skip fires before the `seen` guard is reached. In production the `seen` guard exists for the opposite case, which the Developer's own report names ("the third run can re-find a batch 1-3 text as NewGated"): the residual snapshot does not contain a subtracted batch-1 payload, so the third run can re-find it, and the first two runs never publish it (it is `KNOWN` in pass 0's snapshot). **Add a test where the third run returns a row whose payload is NOT in the first two runs' rows but whose text IS in batch 1 (and one in batch 2 or 3), above and below 1097 Hz, and assert `resNew`, `resNewGated` and `resNewKept` exclude it.** It must fail under M4. *Why it matters beyond tidiness:* without the guard such a row is counted in `resNew` and, below 1097 Hz, in `resNewKept`; **the registered B-WIRE row (ii) ("`resNewGated > 0` or `resNewKept > 0` in at least one cycle") could then be met by re-found batch-1 texts alone**, and the descriptive `resNew*` totals in the Stage 2 report would be wrong.

**RC2: pin the third run's budget (M3).** R3 says "on `leftMs` recomputed after the second run". No test reads the budget the third `RunCoherentFallback` call is given (the first two runs' budgets are pinned, the third is not). On the manual clock the tests already use: advance it during the two runs and assert the third run's budget equals `budgetMs` minus the fallback time already spent, and is smaller than the second run's. It must fail under M3.

**RC3: make the third run's deadline visible (B-AB).** `outcome.Stats` is `CombineStats` of the first two runs only (`Ft8Decoder.cs:1343-1351`), so the line's `abandoned=` cannot show the third run abandoning candidates at the fallback's deadline. B-AB ("cycles with fallback `abandoned > 0`: B ≤ A") therefore cannot see the one thing the lever adds; `fbWallMs` includes the third run but is not a predicate. **Add `resAbandoned={n}` to the ON-only fields: the third run's `Stats.Abandoned` (0 when it did not run; for `skipped-budget`, the cycle's third-run eligible count is unknown, so leave it 0 and let `resRun=skipped-budget` carry that case).** One field, ON only, the line with the setting OFF stays byte-identical; extend the OFF regex test and add an ON case. This is a diagnostic field beyond R6's seven; it changes no behaviour, and I will add the matching predicate to B-AB's reading in the freeze. *The Architect should be told, not asked: it does not alter a row, it lets one see.*

## Notes (no action required)

- **Hash table:** the third run's rows are unpacked before the gate (the gate needs "new text"), so a gated-out row's hashed calls still enter the process-global table. This is the case B-KEEP already allows (the spec, §3), and QA will list every excepted row.
- **M16 (`Edge` flag on kept rows) survives.** `ThirdRunCandidates` prefers the first non-edge row per payload, so the flag is rarely true on a third-run row and only feeds the `publishedEdge` count on the existing fields. I do not ask for a test; the Developer may add one if cheap.
- `resEligible` is the third run's own count; the existing `eligible`, `attempted` and `crcOk` describe the first two runs only, while `published`, `fbWallMs` and `batch4Published` include the third. The freeze's analysis code must read them that way. QA noted it.
- The Developer's claim that `check_version_bump.py origin/main` passes because the proposal says `User-facing: no`: not re-run here; it is the pre-merge gate's job.

## What this review does not conclude

It says nothing about whether the gate works (Stage 2). It does not replace `pre_merge_check.py`, the WSL compile or G8, which run on a clean checkout of the FINAL commit before any push.

## Next

Developer: RC1 to RC3 on `feat/coh-res-cand-v2` (new commit on top, no history rewrite), report the new hash and the three test names. QA then does a delta review (the mutants M3, M4 and one for RC3 must be killed; the full suite re-run), writes `tasks.md` for the OpenSpec change, and records **APPROVED**; only then the freeze, B-OFF and arm B.
