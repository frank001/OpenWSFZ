# QA code review: CQ-AP, `7ca00264` (branch `feat/cq-ap`, base `origin/main` `98332f2a`, v0.70, shim 20260072): APPROVED with notes

Reviewed-commit: 7ca00264a5a8d1af7a0f5ab4c8f97f60243572b1
Verdict: APPROVED

Reviewed 2026-11-10 16:5xZ (`date -u` read 16:52:59Z at the last check). Spec: `arch/cq-ap` `qa/rr-study/2026-11-10-1546-architect-to-qa-spec-cq-ap-build.md` with §8 Amendment 1; QA's task `dev-tasks/2026-11-10-cq-ap-build.md` (`64ca5a2c`). Diff `git diff origin/main 7ca00264`: 36 files, +1,863/-90 (native `decode.c`, `ft8_shim.c/.h`, `rebuild_shim.bat`, the committed `win-x64/libft8.dll`, managed wiring, 6 new test files, OpenSpec `cq-ap` proposal/design/spec).
This review gates the acceptance runs (HK-039). **Not yet run (QA, before any push, HK-006):** the full unfiltered suite on a clean checkout, `pre_merge_check.py`, G8 (needs QA's `tasks.md` first), the WSL Debian compile. They are not preconditions for the replay.

## D rows, checked against the diff
- **D1 (bits, A1.2):** `cq_ap_build_force` (`ft8_shim.c`) takes the 32 forced bit VALUES from ft8_lib's own encoder ("CQ Q1ABC JO22"), positions `[0,29)` and `[74,77)` only; `ftx_cq_ap_inject` (`decode.c`) writes them **after** `ftx_normalize_logl` at `1.01 ×` the largest |LLR| of the non-forced entries; sign is bp_decode's (positive = bit 1, `ldpc.c:68`). QSO-AP (`ftx_decode_candidate_ap`, ±40 before normalisation, OSD fallback) is not touched. Tests: `Pattern_ForcesExactly32Positions_EqualToTheEncodedBits`, `Pattern_FieldValues_AreTheCqTokenAndI3EqualsOne`, `ForcedLlrs_AreAfterNormalisation_At1p01TimesTheMaxNonForced`.
- **D1b (sign):** `Sign_RightDecodes_OppositeDoesNot`, through a probe export that flips the sign.
- **D2 (flag):** `decoder.cqApEnabled`, default false in the constructor and the property; read once per cycle (`Ft8Decoder`), **thread-local per-call flag set on the decoding thread before every native decode, including the early lambda, the residual pass and the third pass** (not a process-global); config overlay tested (Config and Web tests). OFF identity: the Developer's 239 cycle rows by hash against a `98332f2a` build (their claim; QA re-proves it in V-OFF on the window cycles).
- **D3 (placement):** the attempt is inside the `decoded` determination, `if (!decoded && cq_ap_on)`, before the `if (!decoded) { ...; continue; }` branch; so a CQ-AP decode goes through the cross-pass dedup, the text decode, the hash handling, sets the coherent-fallback eligibility and payload, and gets its `apKind` at the emission point (`tls_ap_kinds[num_decoded]`, aligned with `results[]`, the count set at the single positive return, `ft8_shim.c:2208`). `NeverInstead_...` and `Placement_...` cover it.
- **D4 (BP only):** `cq_ap_core` takes `allow_osd`; the production caller passes the literal `0`; the OSD counter (`tls_cq_ap_osd`) is incremented only on the test hook; `OsdCounter_ReadsZero_OnTheProductionPath` and `OsdCounter_CanCount` (sensitivity).
- **D5:** no new acceptance path (CRC, `IsPlausibleMessage` and dedup unchanged). **D6:** `apKind` through `FT8Result` kept at 48 bytes (a wire struct plus the index-aligned getter `ft8_get_last_ap_kinds`; the managed side throws if the count contract breaks, and every positive return path sets it), `DecodeResult.ApKind`, one `cq-ap: attempts=N decodes=M` line only while the flag is ON. **D7:** `ap=` on both PSK accounting lines and the status counters; checked first in the loop. **D9:** shim 20260072, `libft8.version.txt`, `ExpectedShimVersion`. FR-103 and changelog 1.66 are the next free numbers; VERSION and anchors 0.70.
- **D10:** (a) at −20 dB over 60 seeded cycles OFF 13, ON 30 (17 tagged `cq`), (b) `NonCq_IsNeverTaggedCq` (80 cycles, with a non-vacuity assertion), (c) `NoiseOnly_GivesNoCqDecodes` (240 cycles, and the attempt provably ran). The SNR sweep with the 10 pp bar (A1.3) is QA's acceptance run.

## QA's own runs (clean checkout of the exact commit: `_qa-scratch\cq-ap-review\tree`, detached at `7ca00264`)
- **Filter `FullyQualifiedName~CqAp` on `tests/OpenWSFZ.Ft8.Tests`: 23 passed, 0 failed**, with the committed DLL (SHA-256 `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`) **and** with a DLL rebuilt by `rebuild_shim.bat` from the same sources in this tree (SHA-256 starts `aca4a39e`, as the Developer said: Windows builds are not byte-reproducible).
- **Mutations (each applied, the DLL rebuilt where native, the same filter run, then reverted; the tree was `git checkout`-clean afterwards):**

| mutation | failing tests | result |
|---|---|---|
| N1 inject BEFORE `ftx_normalize_logl` (the QSO-AP form) | 1 (the after-normalisation test) | killed |
| N2 magnitude factor 1.01 → 0.5 | 1 | killed |
| N3 override sign flipped | 5 | killed |
| N4 OSD enabled in the production call | 5 | killed |
| N5 attempt runs even where the normal attempt decoded (instead, not extra) | 3 | killed |
| N6 i3 bits not forced (positions 0-28 only) | 1 | killed |
| N7 `apKind` never set in the native result | 3 | killed |
| N8 CQ-AP always on (flag ignored) | 4 | killed |
| M1 PSK `ap=` exclusion removed (`Daemon.Tests`, filter `~PskReporterCqAp`) | 4 of 5 | killed |
| M2 `ApKind` not copied into `DecodeResult` | 3 | killed |
| M3 flag not set in the per-decode bracket | 4 | killed |

All eleven are killed; none survives.

## Notes (none blocks the replay)
- **N-1 (a measurement caveat, no code change asked):** the forced LLRs are strong but BP may still flip a forced bit; a CRC-valid result would then be tagged `cq` although its text does not start with `CQ`. The unit test (80 synthetic cycles) cannot see it on real audio. QA's analysis will report, as a descriptive line, the count of `cq`-tagged ON decodes whose text does not begin with `CQ`.
- **N-2:** the PSK accounting line now ends `..., dedup=N, ap=0` even with the flag OFF (the spec's D7 asked for the reason on both lines). V-SELF's reading of "`PSK Reporter: N decodes seen, M reported`" is unaffected; the OFF log is otherwise unchanged.
- **N-3 (pin):** the arms pin the committed DLL `bbde6eb6…` (the Developer's build). A rebuild from the same sources behaves the same (23/23) but has another hash.
- **N-4:** `managed` always calls `ft8_get_last_ap_kinds` after a decode (also with the flag OFF): one extra P/Invoke per decode, no outcome change (the OFF identity hashes cover it).
- **N-5:** the Linux and macOS binaries are stale until the follow-up chore after the native merge (as in PR #254); the C compiled clean under GCC 14.2 `-Wall` in WSL (Developer's note).
- **Owed by QA:** `openspec/changes/cq-ap/tasks.md` before G9b; Replay81 `--cq-ap on|off` and the `apKind` column (the names are `Ft8Decoder.SetCqApEnabled`, `Ft8LibInterop.SetCqApEnabled`, `ft8_set_cq_ap`, `DecodeResult.ApKind`, `ft8_get_last_ap_kinds`, `ft8_get_last_cq_ap_stats`), with a dry run before the freeze.

## Verdict
**APPROVED.** The build satisfies D1-D10 and the amendment, and the tests can fail. The acceptance steps (Replay81 flag, the A1.3 sweep, then the freeze) may start.
