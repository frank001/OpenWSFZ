## Context

`fix-d001-pcm-sic` (merged to `main` at `497996f`) added a three-pass decode structure to `ft8_shim.c`: pass 0 (full waterfall), PCM-domain SIC between passes 0 and 1 (carrier estimation → CP-FSK synthesis → subtraction → waterfall rebuild), and pass 2 (spectrogram suppression on the PCM-cleaned waterfall). `FT8_SHIM_VERSION` was bumped to `20260003`. The managed layer was updated accordingly: `ExpectedShimVersion`, `MaxDecodePasses`, `MaxResults`, and per-pass debug logging.

Two `0xC0000005` fatal crashes occurred in production:
1. Stack overflow: the 720 KB `float[180000]` `pcm_residual` stack allocation exhausted the .NET thread pool thread's 1 MB stack. A heap-allocation fix was prepared on `fix/native-stack-overflow-pcm-residual` (rev3 DLL).
2. With the rev3 DLL deployed, a second `0xC0000005` occurred — a different memory access violation in the SIC code path. Root cause unidentified; not investigated further given zero R&R benefit.

The R&R study (synthetic S7 + 185-file real-signal baseline) returned −0.1 pp: no measurable improvement. D-001 remains Open.

The stable pre-SIC baseline is the two-pass spectrogram-suppression shim at `FT8_SHIM_VERSION = 20260002`, which achieved 69.1% WSJT-X decode parity.

## Goals / Non-Goals

**Goals:**
- Remove all PCM-SIC code from `ft8_shim.c` and return to the stable `20260002` two-pass structure.
- Restore a crash-free application.
- Keep managed-layer constants, tests, and spec documents consistent with the reverted shim.
- Preserve the R&R study artefacts, the DEFECT document, and all other non-SIC changes.

**Non-Goals:**
- Diagnosing the root cause of the second `0xC0000005` — not worth the effort given zero benefit.
- Improving decode rate — that is D-001 scope, deferred to a future change.
- Removing `ft8_get_last_pass_counts` / `ft8_get_max_passes` exports — these are kept (return 2 passes); removing them would be an unnecessary ABI breakage.
- Reverting the CAT fix (`9ecc170`) or any other post-merge changes unrelated to PCM-SIC.

## Decisions

### D1 — Rewrite `ft8_shim.c` rather than `git revert`

**Decision:** Produce a clean `ft8_shim.c` that targets the 20260002 functional state rather than using `git revert` on the fix-d001-pcm-sic commits.

**Rationale:** The fix-d001 commits span multiple review-finding fixups (phase pre-advancement, buffer-full guard, dead code removal) interleaved with the SIC code. A `git revert` would restore the pre-review-findings state and lose those clean-ups. A manual rewrite starts from the current `ft8_shim.c` and surgically removes only the SIC additions, retaining every improvement that is independent of SIC (hash table, noise floor helper, clean pass-loop structure, `suppress_candidate_tiles`).

**Alternative considered:** `git revert <merge-commit>` — rejected; would reintroduce dead code and pre-review-finding bugs.

### D2 — Keep `ft8_get_last_pass_counts` and `ft8_get_max_passes` exports

**Decision:** Retain both exported functions; `ft8_get_max_passes` returns 2, `ft8_get_last_pass_counts` populates two entries.

**Rationale:** Removing them would require a managed-side change to `Ft8LibInterop.cs` (removing the P/Invoke declarations) and a shim-version bump purely to reflect a removal, with no benefit. The overhead is two trivial functions. The managed layer can safely call them with `capacity=2`.

### D3 — `FT8_SHIM_VERSION` reverts to `20260002`

**Decision:** Reuse version `20260002`, not introduce `20260004`.

**Rationale:** The ABI at `20260002` is what `ExpectedShimVersion` on the managed side will check against. After this change, the shim is functionally identical to the pre-SIC `20260002` shim. Re-using the same version number communicates this clearly. A new version number would imply a new capability, which is not the case.

### D4 — `PcmSicTests.cs` deleted, not skipped

**Decision:** Delete the file outright.

**Rationale:** Skipped tests are dead weight that accumulates confusion. The tested functionality will not exist. Deletion is the honest option; the test logic is preserved in git history if ever needed.

### D5 — `Ft8Decoder.cs` log loop: replace three-pass loop with two summary lines

**Decision:** Replace the `for (pass in passes)` debug-log loop with two `LogDebug` lines, one per pass, logged only when `passCount > 0`.

**Rationale:** The two-pass structure is simple enough that a loop adds no value. Two explicit lines are easier to read. The total-decode `LogInformation` line at cycle end is unchanged.

## Risks / Trade-offs

- **[Risk] NFR-018 (≥ 80% decode parity for v1.0) is further from reach** — the SIC approach was the planned mechanism. Reverting leaves D-001 open with no current fix strategy. → _Mitigation: D-001 is now documented as a research item; v1.0 is not blocked by it in the short term, and the 69.1% baseline is stable._

- **[Risk] `libft8.version.txt` entry for 20260002 will show a second build date** — the original 20260002 binaries were built in May/June 2026; the reverted binaries will carry a new build date for the same version number. → _Mitigation: Append a note in version.txt explaining the re-build ("revert-pcm-sic build"); this is a documentation-only concern._

- **[Risk] macOS ARM64 binary must be produced by CI** — as with previous rebuilds, the macOS dylib is produced by the `macos-latest` CI leg and must be downloaded and committed before merging. → _Mitigation: tasks.md includes an explicit step for this; CI workflow already handles it._

## Migration Plan

1. Branch `revert/fix-d001-pcm-sic` from `main`.
2. Edit `ft8_shim.c` and `ft8_shim.h` (SIC removal + version revert).
3. Rebuild `libft8.dll` (Windows, `rebuild_monitor_and_shim.bat`) and `libft8.so` (Linux, WSL2).
4. Update managed layer (`Ft8LibInterop.cs`, `Ft8Decoder.cs`).
5. Delete `PcmSicTests.cs`; confirm full test suite green.
6. Push branch; CI produces `libft8.dylib` (macOS); download and commit.
7. Update spec docs (`iterative-subtraction`, `ft8lib-interop`).
8. Close PR #5.
9. QA review → merge.

**Rollback:** Not applicable — this change _is_ the rollback of fix-d001-pcm-sic. If the reverted state is also found to be unstable (highly unlikely; it was the stable baseline), `git revert` of this change would restore 20260003.

## Open Questions

*(none — scope is fully defined)*
