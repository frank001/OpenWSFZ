# n1-extract-llrs-at-position — Developer session report

**2026-08-16 11:53Z.** Branch `feat/r1b-sync-refiner-instrument-correction` (this precondition
change was applied directly on it, per the change's own proposal.md — no new branch cut for a
change scoped this narrowly). All `tasks.md` items complete (16/16, §1-§6). **Not pushed, not
merged, `pre_merge_check.py` not run** — per HK-011/HK-014/HK-010/HK-006, the Captain reviews the
diff and decides on merge.

## 1. What this change is

QA's HK-011 dev-task (`openspec/changes/n1-extract-llrs-at-position/`), authored 2026-08-16 and
stopped for a separate Developer session per that housekeeping rule. Adds one native export,
`ft8_extract_llrs_at(pcm, pcm_len, freq_hz, time_offset_s, out_llr174)`, that runs the existing,
unmodified `ft8_extract_likelihood()` extraction path at a caller-supplied lattice position instead
of one `ftx_find_candidates()` already located. N1's own harness (population/pairing/gate) needs
this to extract LLRs twice per row — grid position (control) and grid + `ft8_refine_candidate`'s
`(delta_f, delta_t)` (treatment) — which neither `ft8_decode_all`'s own output nor any existing
export can do.

## 2. Native changes (§1-§3)

- **`native/ft8_lib_build/patched/ft8/decode.c`**: new non-static probe `ftx_extract_likelihood_at()`,
  following the exact pattern `ftx_compute_candidate_llr_stats` already established — builds a
  throwaway `ftx_candidate_t` from the four lattice-index parameters and delegates immediately to
  the existing `static ft8_extract_likelihood()`. **Confirmed byte-for-byte unchanged**: `git diff`
  on this file shows pure additions only (45 lines added, 0 removed/modified) — `ft8_extract_likelihood()`'s
  own body is untouched.
- **`src/OpenWSFZ.Ft8/Native/ft8_shim.c`/`ft8_shim.h`**: new export `ft8_extract_llrs_at`, following
  design.md D2's sketch — builds the waterfall with the same `monitor_config_t` literal
  `ft8_decode_all` uses (copied, not shared, per minimality), inverts the forward freq_hz/dt mapping
  (`ft8_shim.c`'s own "Frequency, time offset, and SNR" block) to the nearest lattice quadruple,
  guards `freq_offset` against `mon.wf.num_bins` (D3 — `get_cand_mag` has no bounds check), calls the
  new probe, and returns raw pre-normalisation LLRs (`ftx_normalize_logl` deliberately not called).
  Same `_MSC_VER`/`__try`/`__except` SEH containment shape as `ft8_decode_all`. Return codes:
  `0`/`-1`/`-2`/`-3` per design.md D3.
- **`native/ft8_lib_build/rebuild_shim.bat`**: `/EXPORT:ft8_extract_llrs_at` added immediately after
  `/EXPORT:ft8_refine_candidate` — confirmed no other export-list line changed.
- **Version bump**: `FT8_SHIM_VERSION` (`ft8_shim.h`) and `ExpectedShimVersion`
  (`Ft8LibInterop.cs:281`) both `20260041` -> `20260042`, both with the full version-history comment
  block updated per the project's established convention.

## 3. Build (§3.3-§3.4)

Rebuilt Windows x64 via `rebuild_shim.bat` (clean `obj\` clear-and-rebuild, all 12 translation
units). **0 compile errors.** Warnings are exactly the same pre-existing set the tree already
carried (C4267/C4996/C4244 in vendored `text.c`/`message.c`/`kiss_fft.c`/`kiss_fftr.c` and the two
pre-existing `strcpy`/`strncpy` warnings in `ft8_shim.c`) — **zero new warnings** from either
`decode.c`'s or `ft8_shim.c`'s diff.

**New DLL SHA256: `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`** (both
`native/ft8_lib_build/libft8.dll` and the copy at `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` —
identical, confirmed via `sha256sum`).

`dumpbin /exports` on the new DLL: **13 exported symbols** — the prior 12 (`ft8_lib_version_check`,
`ft8_decode_all`, `ft8_get_last_pass_counts`, `ft8_get_max_passes`, `ft8_get_last_noise_floor_db`,
`ft8_encode_message`, `ft8_get_last_candidate_counts`, `ft8_get_last_llr_stats`, `ft8_set_ap_bits`,
`ft8_set_decode_params`, `ft8_get_hash_table_reject_count`, `ft8_refine_candidate`) plus
`ft8_extract_llrs_at`, exactly one addition, every existing symbol's RVA-adjacent position
consistent with an additive link.

**CI (Linux x64 / macOS ARM64, §3.4):** confirmed **no workflow-file change needed**.
`build_linux.sh` and `.github/workflows/ci.yml`'s macOS `clang`/Linux `gcc` steps compile
`ft8_shim.c` (now containing `ft8_extract_llrs_at`, a non-static function) directly into
`libft8.so`/`libft8.dylib` with default compiler visibility — no `/EXPORT:` list or
`-fvisibility=hidden` flag on either platform, so the new symbol is picked up automatically on the
next CI run. The workflow's `$EXPECTED` shim-version assertions are derived dynamically from
`Ft8LibInterop.cs`'s `ExpectedShimVersion` via a `python3 -c` regex extraction, not hardcoded, so
the version bump alone requires no CI YAML edit.

## 4. Verification (§2.3-§2.4, §5.1)

All three checks in `qa/rr-study/n1-extract-llrs-at-position/`, all **PASS**:

- **`check_inverse_mapping.py`** (task 2.3, pure Python, no DLL): 6 known
  `(time_offset, freq_offset, time_sub, freq_sub)` quadruples run through the forward formula then
  the inverse formula (transcribed line-for-line from the C), all 6 round-trip exactly — including a
  negative-`time_offset` case (`(-3, 10, 1, 0)` and `(-1, 0, 0, 0)`), which exercises the
  negative-modulo normalisation design.md D2 calls out specifically. float32 arithmetic throughout
  (numpy), matching the C `float` path rather than Python's native double precision.
- **`smoke_test.py`** (tasks 2.4 + 5.1, against the real built DLL, `--dll-sha256` pinned):
  - (a) a real candidate (`freq_hz=997, dt=0.480`, from `ft8_decode_all` on a real WAV from
    `artefacts/20260808_live_run_0016-8080/wsjt-x/wav`) -> `rc=0`, 174 finite floats. **PASS.**
  - (b) `pcm_len=179999` -> `rc=-1`. **PASS.**
  - (c) `freq_hz=9000` (far outside `[200,3000)`) -> `rc=-3`, output buffer confirmed untouched
    (pre-poisoned with `-999.0`, still `-999.0` after the call). **PASS.**
  - (d) round-trip against that same real candidate: re-encoded its decoded message's true 174-bit
    codeword (`ft8_encode_message`, same Gray/sync pattern `c2_phase2c_ber_measurement.py`
    established) and compared against `ft8_extract_llrs_at`'s hard-decision output at that
    candidate's own `(freq_hz, dt)`. **BER = 0.0%.** This is the mechanical proof (design.md Risks,
    last bullet) that the new inverse mapping lands on the exact same lattice point production used
    to decode this message — a wrong lattice point would extract a *different* candidate's
    likelihoods, which reads as ~50% BER (uncorrelated), not 0%.

## 5. Byte-identical production-replay check (§4.1)

Reused `qa/cycleframer-alignment-replay/r0_ac1_ac2_replay.py`/`r0_ac1_ac2_diff.py` (the same R0/R1b
harness), 250 contiguous cycles, `260808_004000`..`260808_014215`, pinned 20m corpus
(`artefacts/20260808_live_run_0016-8080/wsjt-x/wav`):

- **Pre-change (20260041):** `git show HEAD:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, SHA256
  `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf`.
- **Post-change (20260042):** this session's build, SHA256
  `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`.
- **Result: `RESULT: PASS -- zero differences across 250 cycles`.** Confirms this change is purely
  additive — `ft8_decode_all`'s production decode path, candidate selection, and every existing
  exported symbol's *behaviour* are unaffected, not merely asserted.

## 6. `dotnet build` / `dotnet test` (§5.2)

- **`dotnet build`: 0 warnings, 0 errors.** This change adds no C# code (design.md D5) — the only
  managed-layer edit is `Ft8LibInterop.cs`'s `ExpectedShimVersion` constant and its doc comment.
- **`dotnet test` (full suite): 1284/1287 passed, 3 failed.** All 3 failures are **pre-existing and
  environmental, independently confirmed unrelated to this change**:
  - `OpenWSFZ.Daemon.Tests`: `CycleArchiveServiceTests.Manifest_WritesOneRowPerArchivedCycle_InOrder`
    (a `TimeoutException` from a polling helper) — re-ran with this change's `src/`/`native/`
    edits **stashed back to HEAD** (i.e. against the pre-change tree, same DLL/shim the branch
    already had): **fails identically.** Not caused by this change.
  - `OpenWSFZ.Daemon.Tests`: `ExternalReportingServiceTests.Follower_AbsoluteExclusion_AppliesBeforeRelay`
    — flaked once under load (competing with two background Python replay processes at the time),
    **passed** on the isolated re-run against the stashed (pre-change) tree. Timing-sensitive, not
    this change.
  - `OpenWSFZ.E2E.Tests`: `DaemonE2ETests.WelcomeBanner_AppearsOnStdoutWithinTimeout` and
    `StatusEndpoint_ReachableAfterBanner` — both fail because `DaemonProcess.StartAsync` looks for a
    published binary at `src/OpenWSFZ.Daemon/bin/Debug/net10.0/publish/`, which **does not exist in
    this session** (confirmed: `ls` returns "No such file or directory") — `dotnet build`/`dotnet
    test` never run `dotnet publish`. A missing precondition for this specific E2E project, not a
    regression; this change's native/interop edits play no role in daemon startup or the publish
    step.
  - No test anywhere references `ExpectedShimVersion`, `FT8_SHIM_VERSION`, or `ft8_extract_llrs_at`
    directly, so the ABI self-test path's own regression coverage is exercised only implicitly (by
    every other passing `OpenWSFZ.Ft8.Tests` test that loads the DLL) — **`OpenWSFZ.Ft8.Tests`:
    310/310 passed**, confirming the version bump alone did not break the startup ABI check.

## 7. Is N1's harness now unblocked? (§6.2)

**Yes**, per the N1 spec's own precondition framing (§3.1 cleared 2026-08-16 11:21Z; §3.2 is this
change). Both blocking preconditions are now cleared:

- §3.1 (BER harness recovery + bar reproduction): done, ROW 0a does not fire.
- §3.2 (this change, `ft8_extract_llrs_at`): done, built, verified (§4-§5 above), zero regression to
  production decode behaviour (§5 above).

N1's own population/pairing/gate/sign-unit-test (spec §4-§5) is separate QA work, not part of this
change's scope (design.md Non-Goals) — that is the next deliverable.

## Summary of every SHA referenced

| Binary | SHA256 | Shim |
|---|---|---|
| Pre-change (this branch, HEAD) | `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf` | 20260041 |
| **Post-change (this session ships)** | **`6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`** | **20260042** |

## What's next

This change is complete pending the Captain's review. Per HK-011 this Developer session ran
`opsx:apply` (build/tests only, `pre_merge_check.py` explicitly not run per HK-006). Not pushed, not
merged. Once reviewed and merged, N1's own harness (population, pairing, gate) is QA's next
deliverable, unblocked as of this change.
