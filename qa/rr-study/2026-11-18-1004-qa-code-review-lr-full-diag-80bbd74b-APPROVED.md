# HK-039 code review: LR-FULL diagnostic switches, `80bbd74b` (QA, 2026-11-18 10:03Z `date -u`)

Reviewed-commit: 80bbd74b853c4c3af2b49d275f617d61a9277cc3
Verdict: APPROVED

Second review of the same work: the first, `74ff40ad`, was RETURNED (`2026-11-18-0951-qa-code-review-lr-full-diag-74ff40ad-RETURNED.md`, `qa/same-chain` 26e42a12, QA error Q83 for the ambiguity behind C1). Developer branch `feat/lr-full-diag` (Developer's worktree, local, not pushed), base `66b3ddf1`; `74ff40ad` is an ancestor of `80bbd74b` (verified). `git diff --stat 66b3ddf1 80bbd74b`: 13 files, +1227 / -5; `native/` diff empty. Counts only; no message text.

## 1. The two required changes
- **C1 (abandoned rows): fixed.** `Ft8Decoder.cs` delta from `74ff40ad`: `x2Abandoned = run.Stats.Abandoned;` is read from the run; `DiagX2Abandoned` counts runs with at least one abandoned candidate; the rows of a run that returned are published whatever the count (the old all-or-nothing branch is gone); `abandonedCandidates=` is on the `Diagnostic X2` line and on the round-skipped line (=0); a `null` result (failed) still publishes nothing. The test now pins that an abandoned=3 run publishes its row with `run=ran, abandonedCandidates=3`. design D6, the delta spec, the proposal and FR-106 follow. (Style only: the old `else` brace is now a bare block after the counter line; harmless, compiles under TreatWarningsAsErrors, no change required.)
- **C2 (line endings): fixed.** The goldens are compared through `Lf()`. **QA verified on its own clean checkout** (`git worktree add --detach D:/Projects/claude/_qa-scratch/lr-full/clean-80bbd74b 80bbd74b`, `git status` clean, CRLF files: 79 of 79 lines of `LrFullOffIdentityTests.cs` carry CR): `dotnet test tests/OpenWSFZ.Ft8.Tests/OpenWSFZ.Ft8.Tests.csproj -c Release --filter "FullyQualifiedName~LrFull"` at 09:57:50Z: **Passed 21, Failed 0, Total 21.**

## 2. Full unfiltered suite, QA's own run (HK-022)
Same clean checkout: `dotnet test OpenWSFZ.slnx -c Release` (no filter), started 09:58:03Z, log `_qa-scratch\lr-full\qa-full-80bbd74b.log`. Per project, all **0 failed, 0 skipped**: LicenseInventoryCheck.Tests 24, TraceabilityCheck.Tests 34, Rig 41, TestSupport 12, Audio 40, Config 206, E2E 9, Web 451, Daemon 961, **Ft8 843 (3 m 41 s)**. Same counts as the Developer's report.

## 3. Mutation pass (the task's list, on `80bbd74b`, scratch worktree `mut-80bbd74b`, restored clean after: `git status --short` empty)
Filter for every mutant: `FullyQualifiedName~LrFull|FullyQualifiedName~CohResCand` (52 tests). **12 of 12 mutants KILLED** (at least one test fails): M1 X1 never bypasses the gate (2 fail); M2 X1 bypass always, leaking when OFF (5); M3 X1 without the v2 switch (1); M4 X2 text de-duplication removed (1); M5 X2 admission off (2); M6 X2 budget check never skips (1); M7 batch 5 not published when only X2 produced rows (1); M8 snapshot always requested, leaking when X2 is OFF (3); M9 X2 on whenever the late round is on, leaking when OFF (7); M10 abandoned-candidate count not reported (1); M11 admitted-only tag inverted (4); M12 F1b widened to also take GatedOut rows in the third-run candidates (1). Three mutants (M1, M2, M4) first failed to COMPILE (a constant `if (true/false)` makes unreachable code, an error under TreatWarningsAsErrors); they are not valid mutants, so they were redone with non-constant conditions and are the kills listed. The mutation script is `lr_mutate.py` in the QA scratchpad (patterns replaced exactly once, file restored byte-for-byte after each).

## 4. OFF identity
Read in the first review (every new statement behind `diagX1On`, `diagX2On` or a null sink) and unchanged by the delta except inside X2's body. **Independent proof (first review, repeated unchanged):** the two golden captures pass 3 of 3 against the unmodified `66b3ddf1` source (`--filter "FullyQualifiedName~LrFullOffIdentity"`, 09:50:59Z).

## 5. Notes carried forward (no change required)
O1: X2's budget has no 250 ms `CoherentFallbackPublishReserve` (the task text said "as the late round computes it"); reported beside LATE. O2: de-duplication against earlier batches is by text via `seen`. O3: saved configs carry two explicit `false` keys. O4: rows of the first two runs carry no tag.

## 6. What this approval does NOT cover
No replay has been run. **Still to do before any acceptance run, by QA:** the harness (flags for the two switches, the tag columns in `nc.tsv`, the read-backs), a **V-OFF replay of 20 cycles** (`nc.tsv` and outcomes identical to the `66b3ddf1` harness build), then the pilot. Runs over 2 hours need the Captain's explicit go (his rule of 2026-11-18).
