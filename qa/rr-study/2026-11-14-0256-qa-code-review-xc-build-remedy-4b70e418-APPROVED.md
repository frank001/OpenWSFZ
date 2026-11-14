# HK-039 code review: XC-BUILD remedy (Amendment 6: R14 veto, R15 parity gate) at `4b70e418`. APPROVED, with one minor test gap noted

Reviewed-commit: 4b70e41880da9f6e0813b142dc676f7f3a3ce445
Verdict: APPROVED

**Written:** 2026-11-14, `date -u` read 02:55:28Z. **To:** Architect, Developer (via the board). **Branch:** `feat/xc-template-prior` in the Developer's worktree (on `f82b6432`, one commit), local, not pushed. **Reviewer:** QA. **Spec:** `arch/cross-cycle-prior` §13 and §14 (Amendments 6 and 7); dev task `dev-tasks/2026-11-14-xc-template-remedy.md`; (k) review `2026-11-14-0231`. **Developer's report:** read (sections 1 and 5 answered, no deviations); every claim in it that I rely on was re-checked below.

## 1. Verdict

**APPROVED.** The code does what §13 and the dev task say; the tests are meaningful and can fail (40 of 41 mutants killed); the numbers match the desk reference to 2e-10; the native library is untouched. One mutant survives (R05, section 5) and is a test gap at the exact window edge, not a behaviour defect; it does not block the arms. Nothing launches on any other commit than this one without a new record (the hook enforces that).

## 2. What I read (every changed file under `src/`)

`CrossCycleTemplateDetector.cs` (S_P from the same per-symbol ratios, frame symbols 43 to 71, divided by 29, read at the S_E\* argmax from the same correlations; S_P never takes part in the argmax selection), `CrossCycleTemplateStage.cs` (R14 `IsColocated` and `IsVetoed`: the same text never vetoes, a different text within 3.125 Hz and 0.2 s does; the argmax is converted back with `PublishedMinusWsjtxDtS` BEFORE the comparison, so both sides are in our own dt; outcome partition parity-rejected, then vetoed, else detected, mutually exclusive; the SNR is computed only for a detection), `CrossCyclePriorStore.cs` (the sink record gains S_P, the prior's own position and batch, a `vetoed` flag: QA's K1; `CurrentCycleDecodes` snapshot under the lock), `Ft8Decoder.cs` (R14 default ON, T_P placeholder 0.0 with an internal setter and read-back, both read once per cycle behind `xcOn`; the log line gains `vetoedColocated`, `shadowVetoedColocated`, `parityRejected`, `shadowParityRejected`, `veto`, `parityThreshold`; the OFF path executes nothing new) and the test files and fixture.

## 3. Checks

| check | result |
|---|---|
| **B-NAT** (`git diff f82b6432 4b70e418 -- native src/OpenWSFZ.Ft8/Native`) | 0 lines |
| **Native pin** | `libft8.dll` `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528` in both the source tree and the build output, equal to the pin |
| **Suite** (QA's own run, clean detached tree, `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release`, no filter) | **815 of 815 passed, 0 failed** (the Developer's count; 3 m 39 s). I did not re-run the other nine projects; the Developer's per-project counts (Daemon 935, Web 447, Config 204, and so on, 0 failed) are theirs, and `pre_merge_check` is owed before any push (HK-006) |
| **Fixtures** | the Developer's embedded `xc-remedy-fixtures.json` equals mine (same cases, same stale tones); six cases pass at 1e-3 |
| **200-pair numerics** (the first comparison's 200 real (residual buffer, centre, tones) pairs; desk = `xc_sp_desk.py` on the xt_lib grid) | **S_E\* max relative difference 8.0e-11; S_P max relative difference 2.0e-10; argmax identical 200 of 200**; the desk S_E\* equals the first comparison's desk in 200 of 200 |
| **Mutation** (`xc_mutate2.py`, 41 mutants on R14, R15, the sink, the log and the defaults; filter `FullyQualifiedName~CrossCycle`) | **40 killed, 1 survived (R05)**; the list is in `qa/xc-build/xc-build-4b70e418-mutants.json` |
| **TESTING_STRATEGY section 11** | no sleeps, clock reads or delay literals in the 18 added test methods |
| **Harness plumbing** (3-cycle dry run through the chain's own command line, TR-style and ON-style) | `xcveto=` and `xctp=` read back at start and end; the sink header equals the classifier's column table; the K1 join maps 20 of 20 live tests uniquely (see section 4, the one thing the dry run found) |

## 4. Found by the dry run, not a defect of the build

The sink's prior dt is the store's **unrounded** value (0.96, 0.72, 1.12); `nc.tsv` carries the published dt **rounded to 0.1 s** (1.00, 0.70, 1.10). The K1 join therefore keys on (cycle, batch, integer frequency) and matches dt within 0.06, not on dt to two decimals. Fixed on QA's side in `xc_tp.py` (self-test ALL PASS); the Developer's choice (unrounded, as the stage uses it) is right and needs no change.

## 5. The one survivor (minor)

**R05: removing `ColocationEdgeToleranceUnits` (1e-9) survives.** No test places a decode exactly on the window edge (0.20 s or 3.125 Hz): the boundary theory tests 0.19 s and 3.0 Hz (inside) and 0.21 s and 3.2 Hz (outside). The tolerance is there so a decode on the edge counts as inside despite a few ulps in `r.Dt + 0.6`; without a test, its removal would go unnoticed. Not equivalent, low impact (only a decode landing exactly on the edge is affected). **Request, non-blocking:** one test at exactly 0.20 s and exactly 3.125 Hz expecting a veto, in the Developer's next test commit. It changes no product code and does not change the arms (they run on the frozen build copy of `4b70e418`).

## 6. Not established by this review

- **macOS and Linux CI have not seen this commit** (it is not pushed; pushing needs the Captain's go). The numeric fixtures use 1e-3 relative tolerance on a double-precision path; I expect them to hold, but I have not seen the result. Push the branch early when the Captain allows it (the CI result takes about 6 minutes).
- **The acceptance arms are not run.** T_P is the placeholder 0.0 and T_E +infinity until TR2 freezes them on TRAIN.
- The other nine test projects were not re-run by QA.

## 7. What happens next

Per the Architect's order: no arm before this record, which now exists. The chain script `xc_pc_chain_remedy.sh` (committed `d7ac2311`, a draft) still needs its dry run end to end; then the chain starts under the Captain's standing "QA starts the tests" plan: TR2, `te_v2.json` committed, OFF-T with V-OFF against `f82b6432`, ON-T, OFF-N, ON-N (about 6¾ h of PC). The hook `hk039_review_before_acceptance.py` finds this record by its name and its `Reviewed-commit` line.
