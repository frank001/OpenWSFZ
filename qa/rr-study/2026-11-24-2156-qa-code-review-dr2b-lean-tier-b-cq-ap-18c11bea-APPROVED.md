# HK-039 code review: DR-2 step 2b, tier B and CQ-AP in the lean engine, `18c11bea` (QA, 2026-11-24)

Reviewed-commit: 18c11bea22c7a2c4acf7901e64838304542b66f9
Verdict: APPROVED

Developer branch `feat/lean-2b`, a child of `19d8f9fb`. Task: `dev-tasks/2026-11-24-dr2b-lean-decoder-tier-b-cq-ap.md` (`d3d0ee06`). Counts only; no message text (HK-037). The branch tip is `2de6fb75`: one docs-only commit on top (REQUIREMENTS.md, one line: the changelog sentence no longer contains the literal IDs FR-106 and FR-107 that failed the traceability gate on step 2a's CI run). The reviewed commit is `18c11bea`; the tip adds nothing to `src/` or `native/` (`git diff --stat 18c11bea 2de6fb75`: 1 file).

## What was checked

- **Diff** `19d8f9fb..18c11bea`: 19 files, +1,086/-145; `native/` and `src/` 11 files, +541/-125. Read in full: `native/ftz_decoder/ftz_decoder.c` (all of the change: pool with worker ids, per-worker coherent contexts, the three tier jobs, the union sort, the one-row-per-payload rule, the budget). Skimmed: `LeanCycle.cs`, `Ft8Decoder.cs`, interop changes, the OpenSpec and REQUIREMENTS edits. **Not read line by line:** `LeanEngineTierBTests.cs` (415 lines) and the two edited test files.
- **QA's own runs,** clean detached worktree `_qa-scratch\qa-lean2a-review` at `18c11bea`, Release, `--filter "FullyQualifiedName~ClassicEngineGolden|FullyQualifiedName~LeanEngine"`: **34 of 34 at `DOTNET_PROCESSOR_COUNT=4` and 34 of 34 at 16** (the host-count dependency that failed step 2a's CI is closed). **Not re-run by QA:** the full Ft8 project and the other projects (the Developer reports Ft8 856, Config 215, Daemon 961, Web 448, Audio 40, Rig 41, TestSupport 12), and the ASan run (the Developer ran it in WSL Debian, 10,000 fuzz runs with tiers B and CQ-AP plus determinism at 1, 2 and 4 threads, no report; CI will be the check).
- **`libft8.dll`:** its SHA256 (`dd8f723a...9b40b9596`) appears in `libft8.version.txt`.

## Findings

Correct, as read: the tier-B body is the classic per-candidate fallback's (`cf_process_one`, with F1b computed only for a CRC-valid new payload, `f1b <= CF_T1_DB`, a NaN gated out); the eligibility rule is the classic one (not decoded by tier A, not a duplicate position); one coherent context per worker created on the calling thread, freed in `ftz_shutdown`; the sort now covers the union of the tiers with a tier tie-break (A before B before CQ-AP) so cross-tier duplicates resolve deterministically; the one-row-per-payload edge rule matches `CoherentFallbackSelector.Select`; the tier-B published frequency uses banker's rounding as the managed `Math.Round` does; the budget is checked between items and flags `abandoned`; allocations are checked and freed on every exit; `hits` has twice the candidate capacity though at most one hit per candidate exists (harmless).

Minor notes (none blocks):
1. **A tier-B candidate that is CRC-valid but F1b-gated out (or known) is not tried by CQ-AP** (`ftz_decoder.c`, the CQ-AP eligibility test). Classic runs CQ-AP before the fallback, so it would have tried it. The effect is limited to a candidate whose tier-B payload was a likely false positive; the spec's order (A, B, CQ-AP) allows either reading. Recorded so step 2d's replay is not surprised.
2. **The reject side of the F1b gate has no test** (the Developer could not make the classic fallback produce a gated-out row on synthetic audio and said so). The lean comparison is the same single expression as classic's, checked by reading.
3. **A budgeted run is only asserted to be a subset of the full run**, not a prefix (task test 5): timing decides which items are skipped. Acceptable.
4. **Tier-B equality (task test 1) is a single payload on three seeds** of one weak-signal fixture; CQ-AP is covered by 13 CQ-AP-only decodes over 80 drifting-carrier cases. That is thin but is what the unit-test-only rule allows; step 2d's one replay is the real equivalence check.
5. **The CQ-AP switch** is `decoder.cqApEnabled`, which defaults to false in code (the task said "default on", meaning the station's setting). The lean engine follows the setting; DR-0's baseline A6 ran with CQ-AP on, so the step-2d replay must too.
6. **`ftz_decode_cycle` changed signature** and the stats and params structs grew; step 2a was not released (it is on `feat/lean-2a` only), so no compatibility is kept. Fine.

## Not verified, and why

- ASan on this commit has not run in CI (nothing of 2b is pushed). The first CI run decides.
- Full Ft8 project not re-run by QA (about 4 minutes; the user asked for no long runs tonight and the targeted filter covers every changed behaviour).
- `pre_merge_check.py`: once per PR, not run.

Nothing pushed.
