# QA code review: RF4 + L1' default ON, `51069e34` (branch `feat/rf4-l1p-default-on`, base `origin/main` `ef2fc84b`, v0.69): APPROVED with notes

Reviewed-commit: 51069e34daf1c522479dddc5cbd6c8906fb6152f
Verdict: APPROVED

Reviewed 2026-11-09 17:29Z (`date -u`). Spec: `arch/rf4-l1p-default-on` `qa/rr-study/2026-11-09-1634-architect-to-qa-spec-rf4-l1p-default-on.md`; QA's task `dev-tasks/2026-11-09-rf4-l1p-default-on.md` (`d35deba0`). Diff `git diff origin/main 51069e34`: 18 files, +188/-70. **`git diff origin/main 51069e34 -- native` is empty.** Under `src/`: `DecoderConfig.cs`, `Program.cs`, `Ft8Decoder.cs`, comments and defaults only.

## What was checked, and found correct
- **Both defaults at both sites.** `[JsonConstructor]` parameters `coherentFallbackResidualUngated = true` and `lateSubtractionRound = true`; property initialisers `= true`; doc comments and the `Program.cs:855-856` and `Ft8Decoder.cs` comments say what is now true. The daemon reads `configStore.Current.Decoder ?? new DecoderConfig()` at startup (`Program.cs:838`) and on every change (`:954`), so a missing `decoder` section also reads true; a test pins it.
- **`Ft8Decoder` backing fields stay `false` (spec §1.4): agreed.** QA grepped `src/`: there is ONE product `Ft8Decoder` (`Program.cs:306`), and its two setters are called only from `Program.cs:855-856` (before the first cycle) and `:964-965` (every config change), both with the configured value. Tests that build a decoder directly keep today's behaviour.
- **Explicit `false` and the overlay (HK-035).** The two API overlay tests now seed an explicit `false`, so the steps cannot pass on the new default, and gain a step that a body without the key keeps it. The explicit-false and overlay tests pass in both states.
- **Tests changed only where they asserted the old default** (six files; each reviewed in the diff). No other test needed an edit; the Developer's full unfiltered `dotnet test OpenWSFZ.slnx` was green (Config 195, Web 441, Daemon 930, Ft8 683, E2E 9, Audio 40, Rig 41, TestSupport 12, Traceability 34, LicenseInventory 24).
- **VERSION 0.69**, README/REQUIREMENTS anchors, FR-101/FR-102 text, changelog row 1.65; OpenSpec change `rf4-l1p-default-on` (proposal User-facing yes, design, tasks, delta for `ft8-late-subtraction` as RENAMED + MODIFIED); the R-F4 requirement amended in place in the active change `coh-gate-r-f4` (it has no main spec yet), and the main `ft8-late-subtraction` Purpose line.

## QA's own runs (clean checkout of the exact commit: `_qa-scratch\premerge-51069e34`, detached at `51069e34`)
- **`python tools/pre_merge_check.py --skip-openspec`: PASS WITH WARNINGS.** PASS: native freshness (shim 20260071, the pin), G9a, G9b, solution build (Release), UDP margin lint, G10, **full test suite (Release)**, G3, self-contained publish. WARN (environment gaps, both pre-existing): WSL Debian not reachable, AOT linker toolchain missing; CI covers them.
- **G8, run separately after `openspec` 1.3.1 (the CI pin) was installed under `frans` by the Captain: `openspec validate --strict --all` = 80 passed, 0 failed**, including the new change and the RENAMED/MODIFIED delta (the Developer could not run it).
- **D1 against the OLD default** (`DecoderConfig.cs` from `ef2fc84b` with the new tests): Config.Tests 6 failed / 189 passed, Ft8.Tests (filtered to the touched tests) 2 failed, Web.Tests (filtered) 2 failed: the Developer's counts, reproduced. All green on `51069e34`.
- **D3 mutations (all reverted; checkout clean at `51069e34` afterwards).** Filters: Config.Tests whole project; Ft8.Tests `~LateSubtractionRound|~CoherentFallbackWiring`; Web.Tests `~LateSubtractionRoundApi|~CoherentFallbackResidualUngatedApi`. Baseline 195 / 78 / 4 all pass.

| mutation | Config | Ft8 | Web | result |
|---|---|---|---|---|
| M1 R-F4 constructor default back to `false` | 3 fail | 1 fail | 1 fail | killed |
| M2 L1' constructor default back to `false` | 3 fail | 1 fail | 1 fail | killed |
| M3 R-F4 explicit `false` ignored (constructor assigns `true`) | 2 fail | 0 | 2 fail | killed |
| M4 L1' explicit `false` ignored | 2 fail | 0 | 2 fail | killed |
| M1b R-F4 property initialiser back to `false` | 0 | 0 | 0 | survives (N-1: equivalent) |
| M2b L1' property initialiser back to `false` | 0 | 0 | 0 | survives (N-1: equivalent) |

## Notes (none blocks the merge)
- **N-1 (M1b and M2b are equivalent mutants, not a test gap).** The `[JsonConstructor]` body assigns both properties from its parameters (`DecoderConfig.cs:76-77`), and `new DecoderConfig()` and every object initialiser run that constructor first, so the `= true` property initialisers are overwritten and cannot be observed. The spec's premise ("no initialiser, so the CLR `false` on the non-JSON path") was wrong; the initialisers are harmless and consistent, and the code is correct either way. Worth one sentence in the PR so nobody reads them as load-bearing.
- **N-2 (what D1(a) covers).** The Ft8 tests reproduce the daemon's wiring by calling the setter with the config value, as the daemon does; a mutation in `Program.cs` that stopped passing the value would not fail a test. QA verified that wiring by reading (above), the same convention as #264.
- **N-3 (the key is written back).** A save writes both keys explicitly as `true` (tests pin it), so after the station's first config save the keys are explicit and a later change of the default would not reach it. Turning either lever off is an explicit `false` POST (overlay), as the spec says.
- **N-4.** `tasks.md` 3.1 to 3.3 are open (normal mid-change); 3.3 is QA's, at deploy.

## Addendum 2026-11-09 20:13Z (`date -u`): the Linux gate and the remaining gaps
- **WSL Debian compile + test: PASS** on the exact commit (clean checkout `_qa-scratch\premerge-51069e34`, Debian 13 under WSL2, SDK 10.0.201, 178 s): a real Release build and the full suite with `Category!=AwgnFpReplay`, 0 failures in every project (Ft8 683, Daemon 898, Web 441, Config 195, Rig 41, Audio 37, LicenseInventory 24, Traceability 34, E2E 9, TestSupport 12). It had returned WARN in the first run (no `Debian` distro on the `frans` account); the distro was installed afterwards.
- **Not run locally:** the AOT publish (the MSVC C++ build tools and a Windows SDK are not installed under `frans`; the gate is compile-only, CI runs the same compile check) and macOS (CI only). The self-contained non-AOT publish passed.

## Still to do (QA, at deploy, after the Captain merges)
Read the station configuration back under `frans` (last read 2026-11-09 16:39Z: no explicit key for either setting; `coherentFallbackAudio` Both, `decodingDepth` Deep, `coherentFallbackEnabled` true), stamp the new era "RF4+L1' ON" with `date -u`, then report the first live session (not gated).
