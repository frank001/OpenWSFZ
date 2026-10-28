# HK-039 code review: COH-GATE-G R-F4 (`dev/coh-gate-r-f4`), the residual-run GatedOut rows publish behind a setting (default OFF)

Reviewed-commit: 7d93c1e77843bd6af2fa16edac98452db7e58755
Verdict: APPROVED

**Reviewer:** QA · **Date:** 2026-10-28T17:47:31Z (`date -u`) · **Base:** `origin/main` `95e69e87` · **Commits:** `a8c54794` (the OpenSpec change `coh-gate-r-f4`, unedited from `e86f6464`) and `7d93c1e7` (code, version, requirement) · **Spec:** build spec `15392e8d` + Amendment 1 (`15e0f838`), OpenSpec change `openspec/changes/coh-gate-r-f4/`, handoff `qa/rr-study/2026-10-28-1736-qa-to-developer-handoff-coh-gate-r-f4.md`.

## What I read
Every changed file under `src/` (6 files, +60/-9): `DecoderConfig.cs`, `Ft8Decoder.cs`, `CoherentFallbackSelector.cs`, `Interop/CohFallbackTypes.cs`, `Subfeas/CohFallbackAudioSelector.cs`, `Daemon/Program.cs`; and the stat of the four new test files (+344 lines).

## Findings
- **Semantics match the offline reference (`gg_lib.publish`).** `Merge(..., admitResidualGatedOut)` flags only residual-run `GatedOut` rows (`r with { Admitted = true }`, the caller's rows untouched); `residualKeys`, `originalKeys` and the original-row inclusion test use `IsPublishable`, so an admitted residual row joins the residual key set, displaces a same-payload original `NewGated` row, is counted in `fromResidual/inBoth`, and goes to `Select` (which reads `IsPublishable`). Order is by index within the run, residual before original, unchanged. Original-run `GatedOut` rows are never flagged. A lone original run leaves `residualRun` null, so nothing is admitted. When the original run is `NotRun`, the merge is unchanged and the residual rows are still admitted (B-2).
- **True state is kept.** `State` is never changed; `Admitted` is a separate flag read only by `IsPublishable`. `Gated` in the stats is untouched.
- **The setting is read once per cycle** (`ungatedOn = setting && audioMode == Both`), set by the daemon at start-up and on config change; with it OFF `Merge` is called with `false` and `IsPublishable` equals `State == NewGated`, so OFF is the old path (B-OFF to be proved by the replay).
- **Log:** `ungated=N` only when `ungatedOn`; N counts published messages from admitted rows (text-keyed, `TryAdd`, first row wins). With the setting ON in `Original` or `Residual` mode no field is printed (the Developer's judgment call: the setting is ineffective there; accepted, it matches "behave exactly as false").
- **No native change:** `git diff --stat 95e69e87 7d93c1e7 -- native src/OpenWSFZ.Ft8/Native` is empty; `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`.
- **Tests in a clean checkout of `7d93c1e7`** (`_qa-scratch\coh-gate-r-f4-review`), `dotnet test tests/OpenWSFZ.Ft8.Tests/OpenWSFZ.Ft8.Tests.csproj --filter "FullyQualifiedName~CohFallbackAudioTests|FullyQualifiedName~CoherentFallbackWiringTests|FullyQualifiedName~CoherentFallbackResidualUngated"`: **94 passed, 0 failed** (a filter that matches existing tests of those classes too; the Developer reports the full Windows suite green: Ft8 662, Daemon 929, Web 439, Config 190, E2E 9, Rig 41, Audio 40, TestSupport 12, Traceability 34, LicenseInventory 24).
- **Mutation check (3 mutants, each in the clean checkout, reverted after, clean rerun 94/94):**
  - M1 admit `GatedOut` rows of the original run too ⇒ **3 tests fail**;
  - M2 print `ungated=` whatever the setting ⇒ **11 tests fail**;
  - M3 admitted rows do not join the residual key set (no displacement) ⇒ **6 tests fail**.
- **Housekeeping:** VERSION/README/REQUIREMENTS anchor 0.66 to 0.67, FR-101, changelog row 1.63, `openspec validate coh-gate-r-f4 --strict` valid (the Developer's report; the gates are mine to run in `pre_merge_check.py`). `tasks.md` untouched. The clock in test 3(a) is the `ManualTimeProvider` + `BuildTimed` seam, no sleeps.

## Notes (none blocking)
- N-1 Line drift against the handoff: the log line is at `Ft8Decoder.cs:1140` (handoff 1122), the run bookkeeping at `:1075-1084` (handoff 1060-1069). Documentation only.
- N-2 `Merge` allocates a new list per Both cycle only when the setting is ON; negligible.
- N-3 The acceptance rows are the proof of the whole path: B-NAT, B-OFF (equal to `main`), B-EQ (exact on plain text, hashed text counted), B-AB, then the second night. Their order is fixed by the build spec; this record opens the first of them.

## Next
B-NAT, B-OFF, B-EQ, B-AB on the PC (Replay81 built against this commit with the recording extension), then the second-night freeze and replay on sol, `pre_merge_check.py` from a clean checkout of the exact commit, the Captain's push go.
