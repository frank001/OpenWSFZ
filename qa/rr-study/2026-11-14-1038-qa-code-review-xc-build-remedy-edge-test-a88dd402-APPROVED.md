# HK-039 review: the R05 edge test, tests-only commit `a88dd402` on top of `4b70e418`. APPROVED

Reviewed-commit: a88dd40210bec76ffd260be91c6f035a2a497e42
Verdict: APPROVED

**Written:** 2026-11-14, `date -u` read 10:36:40Z. **Reviewer:** QA. **Parent:** `4b70e418`, APPROVED in `2026-11-14-0256-qa-code-review-xc-build-remedy-4b70e418-APPROVED.md`. **Why this commit exists:** that review's one surviving mutant (R05, the veto window's 1e-9 edge tolerance removed) was a test gap; the Developer added the test.

## Checks

| check | result |
|---|---|
| Diff | `git diff 4b70e418 a88dd402`: one file, `tests/OpenWSFZ.Ft8.Tests/CrossCyclePriorTests.cs`, 16 insertions (four boundary rows: +0.20 s, -0.20 s, +3.125 Hz, -3.125 Hz, each expecting a veto; one unit test `Colocation_ExactEdge_IsInside`) |
| **`src/` and `native/` diff** | **empty (0 lines)**; the build the arms ran on (`4b70e418`) is therefore the same product code |
| Full unfiltered Ft8 suite (QA, clean detached tree) | **820 of 820 passed, 0 failed** (815 before, plus the five new rows and test) |
| **R05 on this commit** | unmutated: the CrossCycle filter passes 86 of 86; with `ColocationEdgeToleranceUnits = 0.0` the new test **fails** ("a decode exactly ON the window edge (0.20 s, 3.125 Hz) is co-located, even where the double difference is a few ulps over 0.2 (0.1 + 0.2 - 0.1), which only the edge tolerance admits"). **R05 is killed; all 41 mutants of the remedy set are now killed** (40 on `4b70e418`, R05 here) |
| Test quality | no sleeps, clock reads or delay literals; it also asserts that 1e-6 beyond the edge is NOT co-located, so the window does not silently widen |

## Not established

macOS and Linux CI have not run this commit (not pushed). The other nine test projects were not re-run by QA. `pre_merge_check` is owed on the exact commit before any push (HK-006).
