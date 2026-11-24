# HK-039 review of the last two Developer commits on `feat/xc-template-prior` (`4fe85cc5` the frozen thresholds, `fcee3aa1` the CAT/PTT flake fix), the shipped-defaults comparison, and `pre_merge_check` on the final hash. APPROVED

Reviewed-commit: 4fe85cc50dabc964bb41f6e944cb7bf60d83a655
Reviewed-commit: fcee3aa19a191f5d4a9fab1ea321f9382749d55f
Verdict: APPROVED

**Written:** 2026-11-14, `date -u` read 12:44:36Z. **Reviewer:** QA. **Parents:** `3add5442` (the QSO rule, APPROVED in `2026-11-14-1145-…-3add5442-APPROVED.md`), then `4fe85cc5`, then `fcee3aa1`. **Spec:** R6 and Amendment 6 §A6.3 (the measured thresholds go in before any merge), the Architect's reply to the dev task (his E200) and his exact-comparison requirement; dev task `dev-tasks/2026-11-14-xc-freeze-thresholds.md`. **PR:** #285 (`feat/xc-template-prior`, opened at `3add5442`).

## 1. Verdict

**APPROVED, both commits.** `4fe85cc5` replaces the two placeholder defaults with QA's frozen TR2 values and pins them; the product behaves exactly as the acceptance arms did (exact comparison below). `fcee3aa1` is a tests-only fix of a timing flake that PR #285's first CI run exposed on one Windows job; it weakens no assertion. `pre_merge_check` on the final hash: the same result as on `3add5442`, every gate passes except the WSL leg (the committed Linux `.so` already on `origin/main`) and an AOT environment warning.

## 2. `4fe85cc5`, the frozen thresholds

- **The change** (`Ft8Decoder.cs`, 13 lines): `CrossCyclePriorThresholdDefault = 3.076041980658299` and `CrossCyclePriorParityThresholdDefault = 2.2220253019230114`, comments citing TR2 and `qa/xc-build/results/xc_te_v2_full_2026-11-14.json`; the OpenSpec wording says the same; the tests that asserted the placeholders as defaults were updated, the setter-based tests (including +infinity and 0.0) are kept, and a new pin test `ShippedThresholds_AreTheFrozenTr2Values` asserts both constants and the read-backs against the literals.
- **Checked:** `git diff 3add5442 HEAD -- native src/OpenWSFZ.Daemon src/OpenWSFZ.Abstractions` **0 lines**; **both literals equal the frozen file's `T_E` and `T_P` to the last digit** (read back as Python floats from `xc_te_v2_full_2026-11-14.json`, `valid` true, V_TE and V_TR_P true).
- **Full unfiltered suite** (QA, clean detached tree, `dotnet test OpenWSFZ.slnx -c Release`): **0 failures in every project**: TraceabilityCheck 34, LicenseInventoryCheck 24, Rig 41, TestSupport 12, Config 204, Audio 40, E2E 9, Web 448, Daemon 961, **Ft8 822** (one more than before: the pin test).
- **Mutation** (`xc_mutate5.py`, 7 mutants on the two constants, the Ft8 CrossCycle tests; `xc-build-4fe85cc5-mutants.json`): **6 killed** (T_E rounded to 3.08, T_E off in the last digit, T_E back to +infinity, T_P rounded to 2.23, T_P back to 0.0, T_P the desk value 1.899); **1 survivor, T05 (T_P `…0115` for `…0114`), is an equivalent mutant**: the two decimal literals parse to the same double (`2.2220253019230114`; the spacing of doubles near 2.2 is 4.4e-16 and the literals differ by 1e-16). The T_E last-digit mutant differs by a full ulp and was killed.

## 3. The shipped-defaults comparison (the Architect's exact check)

Harness `Replay81` built from the `4fe85cc5` tree (`--xc-defaults 1` added: no `--xc-te`, `--xc-tp` or `--xc-veto` setter is called, so the product's own defaults are in force); `libft8.dll` SHA-256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`; TEST night `20260808_0016`, the same warm-up cycle, the **first 100 FULL cycles** (`sel_test_100.json`, sha prefix `8f8073f806dcc9a9`); both arms with `crossCyclePrior` and the shadow ON, all other flags identical (the acceptance ON-T flags). Two replays: **REF** (setters T_E 3.076041980658299, T_P 2.2220253019230114, veto 1) and **DEF** (`--xc-defaults 1`). The final hash `fcee3aa1` differs from the replayed tree only by test files (`git diff 4fe85cc5 fcee3aa1 -- src native` is 0 lines), so the product code replayed is the final one.

| check (first 100 cycles) | result |
|---|---|
| DEF readback with no setter called | `xcprior=True xcshadow=True xcte=3.076041980658299 xcveto=True xctp=2.2220253019230114` (at start and end) |
| **A3.3 identity** (per-cycle multiset of (batch, text, freq, dt, snr), all batches) DEF against REF | **0 of 100 cycles differ**; 3,304 published rows in each |
| per-batch counts (b1 to b6), `matchedbatch`, `testb` | **0 of 100 cycles differ**, DEF against REF **and** DEF against the acceptance ON-T arm's surviving numeric files (its text files were released at the HK-037 close, so the text-level reference is the REF run on the same build, which is deterministic) |
| **batch 6 non-empty** | **89 of 100 cycles, 284 batch-6 rows in each arm** (so the comparison exercises the stage) |
| budget | 0 abandoned in both arms |

**EQUAL: the defaults are the setter values.** Tool: `qa/xc-build/xc_defaults_cmp.py` (self-test ALL PASS, including four cases that must fail); counts-only result `qa/xc-build/results/xc_defaults_compare_2026-11-14.json`. The text-bearing replay outputs were deleted after the comparison (0 remain, HK-037).

## 4. `fcee3aa1`, the flake fix

PR #285's first CI run (tip `3add5442`): macOS and Linux **passed on both runs** (the first time these commits ran there; the numeric fixtures hold); one of two Windows jobs failed on `CatTx-Ptt: poll loop reads and SetPttAsync commands never overlap on the shared connection` with `TimeoutException: Expected value to be Connected but was Connected after 1.0s`: a positive-condition wait with an explicit 1 s deadline that the condition met at the deadline on a loaded runner (the same commit passed the other Windows run; nothing in our diff touches CAT or PTT). The Developer removed the **explicit 1 s timeout** from four positive-condition waits (three in `CatPollingServiceTests`, one in `PttWatchdogTests`; the default 5 s applies). **Reviewed:** the diff is 4 insertions and 8 deletions in two test files, only the `timeout:` arguments; **no assertion changed**; `src` and `native` diff 0 lines. The waits left alone are correct: `WebSocketTests.cs:438` (1 s) and the 300 to 600 ms waits expect a timeout (negative waits), where lengthening them would only slow the test. Other short waits elsewhere (QSO answerer, CAT PTT controller, external reporting) were not in scope; a sweep is the Developer's offer, QA's call later.

## 5. `pre_merge_check.py` on `fcee3aa19a191f5d4a9fab1ea321f9382749d55f` (HK-006)

Clean `git worktree add --detach` at `D:\Projects\claude\_qa-scratch\premerge-fcee3aa1`, started 12:34:47Z, summary read 12:44:31Z. **PASS:** native binary freshness (all at 20260072), G9a, G9b, solution build, UDP capture margin lint, G10, **full test suite on the Windows leg (0 failed: 34, 24, 41, 12, 204, 40, 9, 448, 961, 822)**, G3, G8, non-AOT publish. **FAIL: WSL Debian compile + test**, the glibc defect already on `origin/main`: the same committed Linux `libft8.so` (SHA-256 prefix `e8cb81805322`, `git diff --stat ce5734b6 HEAD -- native src/OpenWSFZ.Ft8/Native` **0 lines**), `GLIBC_2.43` not found by Debian 13 (glibc 2.41); the WSL leg's failures are identical in number to the previous run (Web 188, Ft8 272, Daemon 189, E2E 8; 362 mentions of GLIBC_2.43, 356 `DllNotFoundException`, the rest knock-on). **WARN: AOT publish**, no `vswhere` on this PC (environment gap; CI runs the functional proof). The fix of the blob is the separate change `ci/force-native-rebuild`.

## 6. Not established

Whether CI on the updated PR is green: `fcee3aa1` is not on the remote yet; the pushed tip is `3add5442`, whose Windows flake the commit fixes. The other test projects were run by QA on the Windows leg only (the WSL leg cannot load the native blob).
