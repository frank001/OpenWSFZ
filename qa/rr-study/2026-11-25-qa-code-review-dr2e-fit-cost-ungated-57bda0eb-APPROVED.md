# QA code review (HK-039): DR-2 step 2e, the cheaper fit, the fit-skip rule, the ungated rows

**Reviewed commit:** `57bda0eb3d97643f45efdf29eb77e4c0eef05bc3` (`feat/lean-2e`, one commit on `6c746029`, not pushed)
**Verdict:** APPROVED, with 5 minor notes
**Reviewer:** QA, 2026-11-25. Read: the whole `subfeas_fit.c` diff, the `ftz_decoder.c` and `.h` diff, the `Ft8Decoder.cs` and `Ft8LibInterop.cs` changes, against the task `dev-tasks/2026-11-25-dr2e-lean-fit-cost-and-residual-rule.md`.

## Tests QA ran (clean worktree at the commit, `D:\Projects\claude\_qa-scratch\dr2e-review`)

- `DOTNET_PROCESSOR_COUNT=4`, OpenWSFZ.Ft8.Tests, `--filter "FullyQualifiedName~Golden|FullyQualifiedName~LeanEngine|FullyQualifiedName~Subfeas|FullyQualifiedName~SubtractionPass|FullyQualifiedName~HashState"`: **Passed: 125, Failed: 0**. This includes the classic golden, the classic subtraction tests (they use the same fit) and the HashState manifest.
- From the Developer's report, not re-run by QA: Ft8 899, Daemon 963, Config 219, Web 448, ASan+UBSan 10,000 runs clean, openspec strict 84. CI on the pushed branch repeats ASan, Linux and macOS.

## What was checked and found sound

- **D1 profile** is credible and changes the picture: the Δt search is not the cost; step 2 (41 drift candidates, each recomputing a cos/sin template and a cos/sin frequency shift) is 59 % of a fit, and 69 ms of it recomputed the same shift table 42 times. The Developer correctly did not narrow any range.
- **D2 exact speedups** are what they claim, from the code: the shift table is built once per fit with the same expressions (`fill_shift_table`, `apply_freq_shift_cached`); copy, mix and decimation are fused with the same float expressions in the same order (`freq_search_fused`, sharing `freq_search_finish` with the old path so the two cannot drift); step 3 sums four candidates per pass, each with its own accumulators in the old sample order, and the argmax scan keeps the first-maximum tie-break. The old code stays verbatim behind `ft8_subfeas_set_reference_mode(1)`, so a test compares both in one process: 38 signals byte for byte. The scratch `seg` copy is skipped only in the fast path, and `seg` is read nowhere else (checked).
- **D4** is as the task says: `ftz_residual_b_accept` publishes an F1b-passed row, or any row with the ungating on, at any frequency; `rescand_on` is kept in the signature and the ABI and documented as having no effect.
- **D5 (1)** the `try` now covers only `await native`; a publisher exception awaits the native task and then propagates.
- **D3** is flagged, aggregates-only in the `lean:` line (`fitSkipped`, per-round `skipped`), and the rule is a named exported function. The Developer's own finding (below) is honest and matters more than the code.

## Minor notes (none blocks)

1. **D5 (2) has a side effect.** `resid_valid` is now cleared at the start of each round's subtraction. If every fit of a round answers -3 (`n_sub_round == 0`), the loop breaks with the buffer unchanged, but `resid_valid` is now 0, so the residual of the previous round is no longer exported and XC becomes a counted "no residual" skip. Before this commit the earlier residual survived. Rare (rounds 2 and 3 only, all fits invalid), and the fix is one line (restore the previous value before that `break`). Fix it with the next change; do not hold the replay.
2. **Bit-identity is proven per platform, not in general.** The reference-mode test runs on every CI platform, which is the real check for Linux and macOS arm64 (the compilers there may contract float multiply-adds differently across the fused and the separate loops); the whole-cycle golden digest is asserted on Windows x64 only. If CI is green on all three, the claim stands.
3. **D3 is close to a no-op on real audio, by the Developer's own finding.** With the real cap of 140 candidates the band is full of failed noise candidates, so almost every result has a failed candidate in its window and nothing is skipped; it fires only when the list is capped near the result. It is on by default in the lean cycle, so it adds a loss path (a masked signal that was never a candidate) for almost no saving. The replay's `fitSkipped` counts will say. If they are near zero, remove it rather than keep a rule that only costs outcomes.
4. **D4 is covered at the function level only.** The Developer could not construct an end-to-end fixture with a real F1b-failed residual row. The replay measures it (the `ungated` count in the `lean:` line was 0 before).
5. **A production global for a test seam.** `g_ref_mode` is a process-global `volatile int` read in the fit's hot paths. Benign (default 0, one load per search), but it is test-only state in production code; delete it with the old code paths once the fast path has shipped.

## What this will and will not do to the bars (QA's arithmetic, not a measurement)

D2 is 265 to 165 ms CPU per fit (1.5 times). At about 30 fits per cycle the fits fall from 12.16 to about 7.7 CPU-s, so `cpu_net` from 16.3 to about 11.9 CPU-s against the 6.31 bar. T1 and T4 will very likely still miss. The remaining cost is trigonometry (the 41 drift templates, 66 ms) and the envelope and step-1 search, which the Developer says cannot go further without changing bits.

## Next

Push of `feat/lean-2e` needs the Captain's go (HK-033) and his word on `pre_merge_check` first (HK-006). Then one replay of the same 170-cycle slice (about 25 minutes).
