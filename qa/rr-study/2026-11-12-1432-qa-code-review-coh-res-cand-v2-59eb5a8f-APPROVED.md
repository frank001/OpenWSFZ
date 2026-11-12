# QA code review (delta): COH-RES-CAND v2, `59eb5a8f` (branch `feat/coh-res-cand-v2`, on top of `a943512e`, base `origin/main` `70bc72b1`, v0.71, shim 20260072): APPROVED

Reviewed-commit: 59eb5a8f4d9321b608b410f3d9226c1c927bb1db
Verdict: APPROVED

Reviewed 2026-11-12 (`date -u` read 14:31:16Z at the last check). Round 1 (`a943512e`): `qa/rr-study/2026-11-12-1430-qa-code-review-coh-res-cand-v2-a943512e-RETURNED.md` (`qa/same-chain` `158d610a`), three required changes. This record covers the fix commit and, with round 1, the whole build. Spec: `arch/coh-res-cand-v2` §2, A1.2, A2.1, and now Amendment 3 (`53cf80a6`, B-AB restated to read `resAbandoned`).
This review gates the replay runs (HK-039). **Not yet run (QA, before any push, HK-006):** `pre_merge_check.py`, the WSL Debian compile; G8 with QA's `tasks.md` is now done for this change (below).

## The delta

`git diff a943512e 59eb5a8f`: 2 files, +72 / −6. **Production code: one line** (`Ft8Decoder.cs`), the ON-only log field `resAbandoned={(thirdRun is null ? 0 : thirdRun.Stats.Abandoned)}` between `resNewKept` and `resWallMs`. Tests: `CohResCandV2Tests.cs` only. `git diff --stat 70bc72b1 59eb5a8f -- native/ src/OpenWSFZ.Ft8/Native` is **empty**; the committed DLL is unchanged (the pin `bbde6eb6…6528`).

## Required changes, one by one

| RC | what was asked | what was done | verified |
|---|---|---|---|
| **RC1** | pin the batch 1 to 3 "already published" guard | `On_TextPublishedInBatches1To3_UnderANewPayload_NotNew`: the third run returns the texts of batch 1, 2 and 3 under payloads (ids 12 to 14) that no first-two row has, below and above 1097 Hz, plus one genuinely new row below the gate; asserts `resNew=1`, `resNewGated=0`, `resNewKept=1`, no duplicate text | I read the test (it exercises exactly the case I described) and **my mutant M4 is now killed** (1 of 31 fails) |
| **RC2** | pin the third run's budget | `On_ThirdRunBudget_IsWhatIsLeftAfterTheSecondRun`: on the manual clock run 0 advances 3 s and run 1 advances 2 s; asserts the second run's budget is the first's minus 3000, the third's is the first's minus 5000 (±0.5 ms) and smaller than the second's | **M3 is now killed** (1 of 31 fails) |
| **RC3** | `resAbandoned` on the ON-only fields | the field above; `On_ResAbandoned_IsTheThirdRunsCount` asserts 4 when the third run ran with `Stats.Abandoned = 4`, 0 for `skipped-budget`, no field with the setting OFF, and that the combined `abandoned=` still counts the first two runs only; `Off_IsNoOp`'s regex now also rejects `resAbandoned`; the ON-R3 test asserts `resAbandoned=0, resWallMs=` | two new QA mutants: **M18 (`resAbandoned` always 0) killed, M19 (reports the first two runs' count, `outcome.Stats.Abandoned`) killed** |

## Mechanical checks (clean checkout of `59eb5a8f`, `_qa-scratch\review-59eb5a8f`)

- `dotnet test OpenWSFZ.slnx -c Release`, **unfiltered, all green:** TraceabilityCheck 34, LicenseInventory 24, Rig 41, TestSupport 12, Config 202, Audio 40, Web 445, Daemon 935, E2E 9, **Ft8 737** (734 in round 1 plus the three new tests). The Developer had run only the `CohResCandV2Tests` filter (31 of 31); I ran the whole solution.
- `openspec validate coh-res-cand-v2 --strict` with QA's `tasks.md` and the Developer's three files: **valid** (QA commit below). `openspec validate --all --strict` and `check_version_bump.py` belong to `pre_merge_check.py`, run on the final commit.
- My mutants on this build: M3, M4, M18, M19 killed. The earlier results stand (round 1: 12 of 17 killed; M5/M17 are a redundant pair whose removal together is killed; M16, the `Edge` flag on kept rows, remains a minor, accepted survivor).

## Notes for the freeze (what QA will read, now stated once)

- B-AB reads `abandoned > 0` **or** `resAbandoned > 0` per arm-B cycle against arm A's `abandoned > 0` count (Amendment 3). `resEligible`, `resNew*`, `resAbandoned` and `resWallMs` are the third run's own; `eligible`, `attempted`, `crcOk` are the first two runs'; `published`, `fbWallMs`, `batch4Published` include the third.
- The hash table: the third run's rows are unpacked before the gate, so a gated-out row's hashed calls enter the process-global table. B-KEEP already allows the re-rendering; QA lists every excepted row.
- Era: this build with the setting OFF is the CQ-AP build's behaviour; B-OFF (40 cycles against arm A's rows) is the proof, run after the freeze.

## What this review does not conclude

It says nothing about whether the gate works (Stage 2). It does not replace `pre_merge_check.py` or the WSL compile, which run on a clean checkout of the exact commit before any push.

## Next (QA)

The freeze (build `59eb5a8f`, DLL SHA-256 = the pin at the start and end of every leg, the cycle list `qa/cq-ap/live-session-cycle-list.txt` hash, arm A's folder hashes, the gate, the analysis code with a passing synthetic self-test, seed 20261112, B = 2000, the U′ classes frozen from arm A) in one commit **before any arm output exists**; then B-OFF (40 cycles, about 3.5 min), then arm B (500 cycles, about 42 to 46 min), PC exclusive with the station daemon stopped and WSJT-X closed or idle and recorded; then the report. The launches are on the Captain's word for PC time.
