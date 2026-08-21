## 1. Build the coherent LLR export (native, diagnostic-only) — Phase 1

**BLOCKED on a Captain-opened Developer session (HK-011). Nothing in this change
authorises starting this section.**

- [x] 1.1 Read `sync_refiner.c`'s existing downconversion for reuse (not
      reimplementation). Per the Captain's binding licence ruling, WSJT-X source may be
      read for method only — no line copied, transliterated, or ported; this task reuses
      OpenWSFZ's OWN already-clean-room `sync_refiner.c`, so the licence question does
      not reattach here, but the discipline for anything newly written (the coherent
      correlation/LLR-formation logic itself) still applies. Done: `design_lowpass_hann`/
      `downconvert_decimate` reused verbatim (only their `static` qualifier removed,
      shared via new `refine_common.h`); no algorithm/constant duplicated or reimplemented.
- [x] 1.2 Add `ft8_coherent_llr_at` under `native/ft8_lib_vendor/refine/` (design.md Open
      Question 1's likely placement, alongside `sync_refiner.c`) or record the placement
      actually chosen and why if different. Done: new sibling file
      `native/ft8_lib_vendor/refine/coherent_llr.c` (not appended to sync_refiner.c
      itself, so that already-3x-gated file stays untouched apart from the two
      `static`-removal edits) — placement rationale recorded in that file's own header.
- [x] 1.3 Implement: reuse `sync_refiner.c`'s downconversion to complex baseband at the
      candidate's *existing grid frequency* (design.md D1 — no call to
      `ft8_refine_candidate`, no refined position anywhere in this path); for each of the
      58 data symbols, correlate coherently against each of the 8 tone hypotheses
      (complex accumulation across the symbol, magnitude last); form 1-, 2- and 3-symbol
      coherent metrics; combine into per-bit LLRs (max-log over tone hypotheses
      consistent with each bit); normalise to the scale `ftx_normalize_logl` expects.
      Done — see `coherent_llr.c`'s own ALGORITHM header comment for the full derivation,
      including the bit-index convention and window-fusion rule (both explicit
      implementation decisions, documented in place).
- [x] 1.4 Add `ft8_coherent_llr_at` as a new shim export (`ft8_shim.h`/`ft8_shim.c`,
      `rebuild_shim.bat`'s `/EXPORT` list, `build_linux.sh`'s object list). Confirm via
      `dumpbin /exports` (or platform equivalent) that no existing exported symbol
      changed and the new symbol is present. Prototype + changelog added to `ft8_shim.h`
      (`FT8_SHIM_VERSION` 20260042→20260043, no collision with any `d001-*` branch's own
      claimed integer — checked against all five unmerged branches directly). Export/
      compile step added to `rebuild_shim.bat`, `build_linux.sh`, and `BUILD.md` (all
      three platform procedures). `dumpbin /exports` verification deferred to task 5.2's
      rebuild (this task only wires the build scripts; no binary has been rebuilt yet).
- [x] 1.5 Confirm `ftx_decode_candidate()` is byte-for-byte unchanged by diffing against
      the pre-change vendored/patched source, and that no production call site anywhere
      in `decode.c`/`ft8_shim.c` calls `ft8_coherent_llr_at`. Confirmed: `decode.c` has
      ZERO edits from this change (verified — `ft8_coherent_llr_at` duplicates
      `ftx_normalize_logl`'s formula locally in `coherent_llr.c` rather than exposing it
      non-static, specifically to avoid any edit to decode.c that could risk codegen
      differences on the production path). `ft8_shim.c` also has zero edits — the new
      export lives entirely in `coherent_llr.c` and is never called from `ft8_shim.c` or
      `decode.c` (grep-confirmed: no reference to `ft8_coherent_llr_at` outside
      `ft8_shim.h`'s prototype and `coherent_llr.c`'s own definition).

## 2. Managed binding — Phase 1

**BLOCKED on the same Developer session as §1.**

- [x] 2.1 Add `Ft8LibInterop.CoherentLlrAt` (P/Invoke to `ft8_coherent_llr_at`) and the
      corresponding `IFt8NativeInterop.CoherentLlrAt` method, matching the existing
      `RefineCandidate`/`ExtractLlrsAt` diagnostic-export pattern so a `FakeInterop` can
      record calls without loading the native DLL. Update all existing
      `IFt8NativeInterop` test-double implementations with a stub; add
      `CoherentLlrAtTests.cs` (fake delegation + a real-binary smoke test). Done: all ten
      `IFt8NativeInterop` implementers updated (`Ft8NativeInteropAdapter` + nine test
      fakes across `AvContainmentTests`/`D005MessageTrimTests`/`D009FpFilterTests`/
      `D011NonstandardCallsignFpGuardTests`/`HashTableRejectCountLoggingTests`/
      `RefineCandidateTests`/`RegionLookupTests`/`SetDecodeParamsTests`/
      `WorkedBeforeLookupTests`); new `CoherentLlrAtTests.cs` (2.1a fake delegation, 2.1b
      real-binary smoke test, 2.1c wrong-length-PCM throw, 2.1d out-of-band-frequency
      throw — mirrors `RefineCandidateTests`' 2.1a/b/c pattern plus one extra scenario
      this export's own `-3` return code needs).
- [x] 2.2 Grep the production decode path (everything reachable from `DecodeAll`) to
      confirm zero call sites reference `CoherentLlrAt`/`ft8_coherent_llr_at` outside
      test code and the gate harness. Confirmed by grep (`CoherentLlrAt|ft8_coherent_llr_at`
      across `src/`, excluding the three interop-seam files themselves): zero matches.
      `Ft8Decoder.cs` (the production decode path) does not reference it anywhere.

## 3. Validation harness and population re-derivation — Phase 0 (THIS SESSION, QA)

- [x] 3.1 Re-derive the population Phase 1's gate will run on: reused
      `plive_population.build_p_live_population(PRIMARY_CORPUS)` verbatim (HK-018 — not
      reimplemented). Dry count reproduced Stage 2's own published number exactly:
      n_rows=18,012, **n_clusters=4,113** (cluster count reported per the 2026-08-20
      1613Z ordering doc's explicit instruction, not row count).
      `qa/rr-study/r2-coherent-llr-instrument/r2_population.py`.
- [x] 3.2 Confirm no population helper in this change's dependency chain truncates via a
      `limit=` argument (HK-021(i) — `compute_matched_hit_control(cycles, limit=N)`
      truncates in file order, is NOT used anywhere in this thread's population
      construction). `build_p_live_population`/`build_p_hit_population` take no `limit`
      parameter at all; confirmed by reading `plive_population.py` in full.
- [x] 3.3 Build the `ber_grid` harness (`r2_ber_grid.py`): per-row grid-position
      extraction via the *existing* `ft8_extract_llrs_at`, at Stage 2's own corrected
      anchor (`anchor_dt + 0.65s`, REUSED not re-swept). Deliberately drops the
      refiner call Stage 2's own `measure_stage2_row` made (design.md D1) — this
      harness never calls `ft8_refine_candidate`. Reports `n_err_grid` (int, 0-174) as
      well as `ber_grid` (float), since Phase 1's `f_net` gate thresholds on the
      integer bit count (`n_err ≤ 19`), not the float BER directly (design.md D5).
- [x] 3.4 ROW 0a: DLL SHA256 + shim version re-verified from disk immediately before
      arming (`6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`, shim
      `20260042` — the same pin already in production use; no rebuild). Confirmed
      `ft8_coherent_llr_at` does not exist in this binary (`ft8_shim.h` grepped, no
      such symbol) — this change's Phase 0 genuinely calls only pre-existing exports.

## 4. ROW 0c / ROW 0d — the two validity checks run against the CURRENT build — Phase 0

- [x] 4.1 **ROW 0c, mandatory sign unit test, two-sided (HK-021(n)).** SIGNAL sub-check:
      20 real P-HIT rows (seeded, sort-stabilised sample — `run_stage1r.
      deterministic_sample`, reused verbatim) at Stage 2's own corrected anchor;
      **median(n_err) = 12.50** (18/20 rows measured, 2 dropped: `no_true_codeword`/
      `grid_extract_rc`), bar `≤ 15` (8.6% of 174, headroom above Stage 2's own
      already-measured 5.75% median on the identical population/offset) → **PASS**.
      NOISE sub-check: 20 pure-Gaussian-noise trials against a fixed arbitrary truth;
      mean(n_err) = 84.00, bar `[80, 94]` (derived from the binomial(174, 0.5) null,
      mean ± ~4×SE(mean)); every per-trial value inside `[60, 114]` → **PASS**.
      **Construction note, recorded not hidden (HK-022):** the SIGNAL sub-check's first
      construction (a synthetic signal at its own encoder-specified position) FAILED
      (mean n_err ≈ 70/174) and was traced to an unrelated synth encoder/extractor
      position-convention gap (design.md D3) — rebuilt on real P-HIT data instead. The
      gate statistic was also corrected from mean to median mid-drafting after the mean
      (22.78) failed on the same sample whose median (12.50) passed (design.md D4) —
      both statistics are reported in the harness output, gate is on the median only.
      **ROW 0c: PASS.**
- [x] 4.2 **ROW 0d, `ber_grid` reproduces Stage 2's own median.** Full P-LIVE population
      measured (not sampled — the full population takes ~112s, well inside budget):
      **fresh median_ber_grid = 31.0345%** (n_rows=15,389, **n_clusters=3,917**) vs
      Stage 2's own **31.0345%** (n_rows=15,383, n_clusters=3,916 — a 6-row/1-cluster
      difference, noted honestly, immaterial to the mechanical bar). `|delta| =
      0.0000pp` (bar `≤ 1.0pp`) → **PASS.**
      `qa/rr-study/r2-coherent-llr-instrument/run_phase0.py`,
      `results/phase0_report.json`, `results/phase0_run.log`.
- [ ] 4.3 **`f_net`/`C_ber` gate itself — Phase 1, blocked on §1-2.** Cannot run before
      `ft8_coherent_llr_at` exists; this task is the eventual extension of §3.3's
      harness with a second (`ber_coh`) extraction call at the *same* `(freq_idx,
      time_idx)` as the grid extraction (candidate-identity requirement, Phase 1 spec
      §3 ROW 0e), then the pre-registered ROW 1/2/3/4 evaluation (design.md D6).

## 5. Shim version and cross-platform build — Phase 1

**BLOCKED on the same Developer session as §1-2.**

- [x] 5.1 Bump `FT8_SHIM_VERSION`/`ExpectedShimVersion` past `20260042`. Done: `20260043`
      (checked against all five unmerged `d001-*` branches' own claimed integers directly
      — no collision).
- [x] 5.2 Rebuild all three platform binaries; record each new DLL/so/dylib's SHA256.
      Windows (`rebuild_shim.bat`, MSVC 19.44.35223): SHA256
      `1889408787a2c7ea545dbe8477691b090417a74fc81116cbf1ea52413bfbdb3a`. Linux
      (`build_linux.sh` via WSL2 Debian, GCC 14.2.0): SHA256
      `8c79cf40f46bd0a5c7589d70f7379d7b5dd0a90230d74a26f450649449fd8a55`. macOS: NOT
      rebuilt — no Mac available locally (same limitation R0/R1/R1b recorded); this
      repo's own CI `commit-native-binaries` job rebuilds macOS from source and
      auto-commits on push, and this branch has not been pushed (HK-014). Recorded
      honestly in `libft8.version.txt`, not skipped silently. `dumpbin /exports`/`nm -D`
      both confirm all fourteen symbols present (thirteen pre-existing + the one new
      `ft8_coherent_llr_at`), no existing symbol lost. A real, recurring build-tooling
      defect was found and fixed in passing: `build_linux.sh` failed under WSL with CRLF
      line endings (the SAME symptom R1's own changelog already recorded fixing — that
      fix only normalised the committed blob, and with no `.gitattributes` in the repo,
      `core.autocrlf=true` silently reintroduces CRLF on every fresh Windows checkout);
      fixed properly this time via a new repo-root `.gitattributes` (`*.sh text eol=lf`).
- [x] 5.3 Re-run a production-decode-equality replay (R0/R1's own AC-1/AC-2-style
      pattern) between the pre-change and new binaries to confirm zero decode-output
      differences. Done: 250 contiguous cycles (`260808_004000`..`260808_014215`), reusing
      `qa/cycleframer-alignment-replay/r0_ac1_ac2_replay.py` +`r0_ac1_ac2_diff.py`
      verbatim (HK-018) — **PASS, zero differences**, on BOTH platforms built this
      session (Windows: `6890d84c...`→`1889408787...`; Linux:
      `b18f8ff1ec477afd...`→`8c79cf40f4...`).
- [x] 5.4 `dotnet build`: 0 warnings. `dotnet test`: full suite green plus new
      `CoherentLlrAtTests`. Done: `dotnet build -c Release` (whole repo, no `.sln`, dotnet
      10 SDK's implicit multi-project discovery) — 0 warnings, 0 errors. `dotnet test -c
      Release` (whole repo) — all green after clearing one pre-existing environmental
      artefact (a stray locked `OpenWSFZ.Daemon.exe` process from an earlier session
      blocked `tools/publish_selfcontained.py`'s copy step, transiently failing 2
      `OpenWSFZ.E2E.Tests`; killed the stray process, re-published, re-ran — 7/7 E2E green,
      unrelated to this change's own code). `OpenWSFZ.Ft8.Tests`: 314/314 green including
      the four new `CoherentLlrAtTests` (2.1a fake delegation, 2.1b real-binary smoke test
      against the freshly rebuilt shim-20260043 DLL, 2.1c wrong-length-PCM throw, 2.1d
      out-of-band-frequency throw).

## 6. Reporting and wrap-up

- [x] 6.1 Write the Phase 0 QA→Architect report: ROW 0c (both sub-checks, both
      statistics), ROW 0d (fresh vs. Stage 2 numbers, the small row/cluster
      discrepancy noted), the two construction-changed-mid-drafting notes (D3/D4), the
      synth encoder/extractor position-convention gap flagged as an aside, and an
      explicit statement that Phase 0 is done and Phase 1 needs a Captain-opened
      Developer session.
- [x] 6.2 Stop. No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006) — the
      Captain reviews and decides on merge; this task does not declare readiness
      unprompted. **Stopping here. No `src/` touched, no DLL rebuilt, no Developer
      session opened.**
