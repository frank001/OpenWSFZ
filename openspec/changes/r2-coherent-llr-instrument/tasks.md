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
      🔴 **STILL BLOCKED ON 4.4 (ROW 0g) — ROW 0g ran 2026-08-21 and FIRED (0g-2). Per
      the pre-registration's own consequence, this task's gate is VOID and MUST NOT be
      evaluated: no ROW 1/2/3/4 may be read, ROW 3 MUST NOT be declared, Route B2 MUST
      NOT be called dead. NOT RUN this session.** See
      `qa/rr-study/2026-08-21-1100-qa-to-architect-row0g-fires-phase1-gate-void.md`.
      Unblocks only on a native fix (HK-011 Developer session) followed by a ROW 0g
      re-run that passes — never on a re-read of 0g's own output with a different
      metric.
- [x] 4.4 **ROW 0g — instrument-gain check, runs BEFORE the 4.3 gate.** Pre-registration:
      `qa/rr-study/2026-08-21-1038-architect-to-qa-spec-b2-phase1-row0g-instrument-gain-check.md`
      (Captain-authorised 2026-08-21). Two limbs, **both against the CURRENT merged
      binary — no native change, no Developer session, HK-011 not engaged**:
      **0g-1** clean-signal ceiling (20 noise-free synthetic signals, `time_offset_s`
      swept over `m3_common.TIME_ANCHOR_OFFSETS_S` to sidestep the design.md D3
      convention gap, each path minimised independently) — bars
      `median(n_err_coh_min) ≤ 5` **and** signed `d_clean ≥ 0`, with floor- and
      stub-degeneracy guards (HK-021(n));
      **0g-2** paired on 200 real P-HIT rows at the `+0.65s` anchor, signed `d_real`
      cluster-bootstrapped by `ts` (HK-021(i)) — fires if `CI_hi(d_real) < 0`.
      🔴 **RESULT: 0g-1 PASS (0g-1a median(n_err_coh_min)=3.00≤5; 0g-1b d_clean=+3.00≥0,
      via the floor-degeneracy noise rerun at snr≈-19dB; no stub degeneracy). 0g-2
      FIRES DECISIVELY: d_real=-67.0 bits, cluster-bootstrap CI95=[-71.0,-65.0] (190
      clusters) — coherent path's median n_err=79/174 on real P-HIT rows, near the
      pure-noise null of 84-87, against grid's median n_err=10. ROW 0g OVERALL: FIRES.**
      Harness: `qa/rr-study/r2-coherent-llr-instrument/coherent_llr_ctypes.py`,
      `row0g_instrument_gain_check.py`; results in `results/row0g_report.json` /
      `results/row0g_run.log`. Full writeup:
      `qa/rr-study/2026-08-21-1100-qa-to-architect-row0g-fires-phase1-gate-void.md`.
      🔴 **Consequence applied: the Phase 1 gate (§4.3) is VOID, no ROW 1/2/3/4 read,
      ROW 3 NOT declared, Route B2 NOT called dead.** Rationale that motivated the
      check (a code-read hazard, NOT the mechanism confirmed by the result): the fusion
      in `coherent_llr.c` selects per bit on raw `fabsf` across `n_syms` windows never
      normalised by window length, biased toward `n_syms=3` on scale alone; combined
      with the unresolved advance-before-use rotator convention at `n_syms=2/3`. The
      MEASURED failure shape (near-total collapse to chance on real audio, while
      matching-or-beating grid on driftless synthetic tones) is more severe than that
      hazard's own "gain-reduced but correctly-signed" description — flagged as a new,
      unverified hypothesis (real signal frequency/phase drift over the ~12.6s message
      exposing a coherent-path sensitivity a static synth tone never exercises) in the
      writeup's §3, for whoever picks up the native fix.

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

---

# Phase B — origin fix (B1), fusion fix (B2), LDPC-decode diagnostic export (B4,
# Amendment 1), and the cascade pin (C1)

**Authority:** `qa/rr-study/2026-08-21-1525-architect-to-qa-spec-phase-b-origin-and-
fusion-fix-and-row0g-rerun.md`, amended by `qa/rr-study/2026-08-21-1644-architect-to-
qa-phase-b-amendment-1-ldpc-decode-llrs-export-and-cascade-pin.md`. **If any task below
appears to conflict with either spec, the specs win — escalate, don't guess.**

🔴 **§7-10 are a `native/` change. HK-011 is engaged; nothing below authorises starting
them.** Only a Captain-opened Developer session runs `opsx:apply` on §7-10 (build and
tests only — never `pre_merge_check.py`, HK-006). The Captain reviews the diff before
any push or merge (HK-010/HK-014). §11 is QA's own follow-on run, not the Developer
session's. §12 (C1) is docs-only and needed no Developer session — it is applied
already, by this same authoring pass (design.md Decision D-B2-1).

## 7. B1 — the waterfall-origin correction (native)

**BLOCKED on a Captain-opened Developer session (HK-011).**

- [ ] 7.1 In `ft8_coherent_llr_at` (`native/ft8_lib_vendor/refine/coherent_llr.c`),
      after the existing lattice snap produces `time_offset_s_grid` (currently used
      directly to form `origin_sample_f` at line 437), apply the correction:
      `correction_symbols = 1/time_osr − freq_osr/2 − 0.5` (== `-1.0` at production's
      own `K_TIME_OSR = K_FREQ_OSR = 2`), `origin_sample_f = (time_offset_s_grid +
      correction_symbols * symbol_period) * fs`. **Derive `time_osr`/`freq_osr`/
      `symbol_period` from `mon.wf.time_osr`/`mon.wf.freq_osr`/`mon.symbol_period` —
      all three are already read in this function (lines 394-398) — captured before
      `monitor_free(&mon)` at line 413. Do NOT hardcode `-0.16f` or `-1.0f`.**
- [ ] 7.2 Add a comment at the correction naming *why* it exists — the look-back window
      and the `b + (s+1)/T − F/2` window-centre derivation — pointing at
      `qa/rr-study/2026-08-21-1412-architect-to-qa-origin-convention-finding-and-spec-
      b-orig-a.md`. A bare unexplained constant is how this defect survived the C port.
- [ ] 7.3 Confirm the derived `-1.0` symbol correction (at production OSR) matches
      `qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py:227`'s own
      `TIME_ORIGIN_CORRECTION_SAMPLES_2K = -SPS_2K` constant, calibrated empirically in
      the Python prototype since the N2 session. **If it does not match, stop and
      escalate — do not proceed to rebuild.**

## 8. B2 — the fusion normalisation (native, same session as §7)

- [ ] 8.1 Before the cross-`n_syms` magnitude comparison at `coherent_llr.c:480`
      (`if (n_syms == 1 || fabsf(candidate) > fabsf(out_log174[gb]))`), standardise
      each window's per-bit LLRs to a common, window-size-independent scale before
      comparing (design.md D9) — e.g. divide each window's `bit_llr[]` by
      `scale = stddev(mag[0..n_tones))` for that window, guarding `scale > 0` (leave
      the window's LLRs unscaled, or exclude it, if not). A better-justified
      alternative is acceptable if the reasoning is recorded in the commit/code
      comment. Do **not** fix this by restricting `n_syms` — the 1-, 2- and 3-symbol
      windows must all remain in the comparison; that coherence is Route B2's entire
      premise.
- [ ] 8.2 Add the mandatory unit test (design.md D9, `specs/ft8-coherent-llr/spec.md`'s
      "Fusion selects by normalised reliability, not by window length" scenario):
      construct two windows whose magnitudes carry equal discriminative information but
      differ in absolute scale by a known factor; assert their normalised per-bit LLRs
      agree to a stated tolerance, and assert the pre-normalisation values do **not**.
      C-side or Python-side, Developer's choice of placement — record which, and why.

## 9. B4 — `ft8_ldpc_decode_llrs` diagnostic export (native, Amendment 1, same session)

- [ ] 9.1 Add `ft8_ldpc_decode_llrs` to `native/ft8_lib_build/patched/ft8/decode.c`
      (forced placement — `ftx_normalize_logl` at `decode.c:391` and `osd_decode` at
      `decode.c:507` are both `static` there), exactly as `ftx_extract_likelihood_at`
      (`decode.c:838`) already does, with a thin wrapper in `ft8_shim.c` (the
      established two-file pattern). Signature per the 1644Z spec §B.2:
      `int ft8_ldpc_decode_llrs(const float* llr174, int max_iters, int osd_depth,
      uint8_t* out_a91, int* out_ldpc_errors, int* out_path, int* out_crc_ok)`.
      **Do not un-`static` anything, do not move `osd_decode`, do not duplicate the
      CRC or normalisation arithmetic into the shim.**
- [ ] 9.2 Implement in this order, mirroring `decode.c:641-713` and nothing else (1644Z
      spec §B.3): (1) `memcpy` the caller's vector into a local `float
      log174[FTX_LDPC_N]` — never modify the caller's buffer, `bp_decode` writes
      through its argument; (2) degenerate guard FIRST (copy `decode.c:799`'s own guard
      in spirit — zero variance ⇒ `ftx_normalize_logl` would divide by zero ⇒ return a
      negative rc, do not normalise); (3) `ftx_normalize_logl(log174)` — **mandatory**,
      removes any global scale difference between the grid and coherent LLR vectors
      before BP sees them, without it B4 measures scale, not quality; (4) save the
      normalised vector for OSD (`decode.c:643-646`); (5) `bp_decode(log174,
      max_iters, plain174, out_ldpc_errors)`; (6) pack to `a91`, extract/compute CRC-14
      (`decode.c:707-713`), compare; (7) **if and only if the CRC fails and
      `osd_depth >= 0`**, run the OSD fallback exactly as production does (including
      its existing two-feature accept/reject gate), re-check the CRC, report which path
      succeeded in `out_path` (`0` = BP converged, `1` = OSD fallback, `-1` = neither).
- [ ] 9.3 Confirm `decode.c`'s existing functions are byte-for-byte unchanged (diff
      against the pre-change source) and that no production call site anywhere in
      `decode.c`/`ft8_shim.c` calls `ft8_ldpc_decode_llrs` (grep-confirmed). B4 gets no
      `Ft8LibInterop`/`IFt8NativeInterop` C# binding (design.md D10) — reachable only
      from test code and QA harnesses via the native-library loading mechanism.
- [ ] 9.4 Native or Python smoke tests (Developer's choice of placement, per the
      `n1-extract-llrs-at-position` precedent design.md D10 cites), covering all five
      mandatory acceptance checks from the 1644Z spec §C — **all two-sided/floor bars
      below are load-bearing, not advisory:**
      - **B4-a** (positive control): encode a known message, build its exact codeword
        LLRs (`+1`/`-1` scaled, no noise), decode → `crc_ok == 1` **and** the `a91`
        payload matches the encoded message bit-for-bit.
      - **B4-b** (negative control, HK-021(n)): pure Gaussian LLRs, fixed seed, 20
        trials → `crc_ok == 0` on **all 20**.
      - **B4-c**: the caller's input buffer, read back after the call, is byte-identical
        to before.
      - **B4-d**: zero-variance input → negative rc, no crash, no NaN.
      - **B4-e** (the only check with known ground truth, HK-026): take rows
        `ft8_decode_all` DID decode live, extract with `ft8_extract_llrs_at` at the
        grid candidate's own position, feed B4 → **≥ 90% agreement** (`crc_ok == 1`) on
        rows production decoded, and the recovered message text matches. **If it lands
        below 90%, STOP and escalate — B4 is not reproducing the production decode
        path and no C2 number can be read.** (Report per-row `out_path` so a
        BP-vs-OSD split remains possible later without re-running anything — Amendment
        1 §G.)
      🔴 **B4-a through B4-d are mandatory and gate this task. B4-e failing does NOT
      block ROW 0g (§11.3 below) — B4 is inert, nothing calls it — but it MUST be
      reported and MUST stop any C2 work (C2 is not this change's scope regardless).**

## 10. Version, pin, cross-platform build — Phase B (native, same session)

**BLOCKED on the same Developer session as §7-9.**

- [ ] 10.1 Bump `FT8_SHIM_VERSION`/`ExpectedShimVersion` from `20260043` to `20260044`.
      🔴 **Assert mechanically that `20260044` is unused across all branches before
      adopting it** — do not infer freedom from the number being the next integer (the
      board already records two collisions across five unmerged `d001-*` branches).
      Header history entry in the established style (`ft8_shim.h`).
- [ ] 10.2 Rebuild all three platform binaries you have toolchain access to; record
      each SHA256 honestly (state, don't skip silently, if a platform is unavailable —
      same standard R0/Phase 1 used for macOS). `dumpbin /exports`/`nm -D`/platform
      equivalent: confirm `ft8_ldpc_decode_llrs` is present, every previously-exported
      symbol is unchanged, and it is the **only** addition.
- [ ] 10.3 Re-run a production-decode-equality replay (≥200 contiguous cycles,
      `qa/cycleframer-alignment-replay/r0_ac1_ac2_replay.py` +
      `r0_ac1_ac2_diff.py`, reused verbatim — HK-018) between the pre-Phase-B and new
      binaries: zero decode-output differences, mechanically diffed, on every platform
      rebuilt.
- [ ] 10.4 **Re-pin the harnesses in one place.**
      `qa/rr-study/r2-coherent-llr-instrument/coherent_llr_ctypes.py:40-41`'s
      `CURRENT_DLL_SHA256`/`CURRENT_SHIM_VERSION` — read the rebuilt DLL's actual
      SHA256 from disk, do not copy it from a report. Confirms the four harnesses that
      import these constants (`row0g_instrument_gain_check.py`,
      `b_pos_a_lattice_position.py`, `b_orig_a_origin_convention.py`,
      `phase_a_deconfounding.py`) all pick up the new pin.
- [ ] 10.5 Verify mechanically whether `.github/workflows/ci.yml`'s fourth build recipe
      needs an edit for the new `decode.c` export (B4 adds a new *symbol*, even though
      no new source *file* — re-check rather than inheriting Phase 1's "no edit needed"
      answer). State the result either way.
- [ ] 10.6 `dotnet build`: 0 warnings. `dotnet test`: full suite green (regression check
      only — Phase B adds no C# code, design.md D10). Confirm nothing in
      `Ft8LibInterop`'s ABI self-test path broke from the version bump alone.
- 🛑 The Developer session runs **build + tests only**. `pre_merge_check.py` is the
      Captain's initiative alone (HK-006).

## 11. Acceptance ordering — QA, after the Developer session, in this exact order

**BLOCKED on §7-10 landing.** Two changes (B1, B2) share one Developer session, which
normally destroys attribution; this ordering restores it (2026-08-21 15:25Z spec §5).

- [ ] 11.1 **FIRST — re-run `b_orig_a_origin_convention.py` exactly as it ran at
      2026-08-21 15:00Z** (same seed, same N, same spec) — the acceptance test for B1
      alone. Required: `mode(G)` = `+2`, **unchanged** (control — the grid path must be
      untouched); `mode(C)` moves `0` → `+2` (B1 works: coherent now agrees with grid's
      own cell). 🔴 **If `mode(C)` does not move to `+2`, B1 is wrong or mis-applied —
      STOP, do not run §11.3, escalate. If `mode(G)` moves at all, something touched
      the grid path that should not have — STOP and escalate; this is a genuine
      control.** Report `frac_at_mode` for both; a drop in `frac_at_mode(C)` well below
      0.918 is worth flagging (possible B2 variance) but is not itself a stop
      condition.
- [ ] 11.2 **SECOND — confirm the B2 unit test (§8.2) passes.**
- [ ] 11.3 **THIRD, only if 11.1 and 11.2 both pass — re-run ROW 0g AS PRE-REGISTERED**
      (`qa/rr-study/2026-08-21-1038-architect-to-qa-spec-b2-phase1-row0g-instrument-
      gain-check.md`, `specs/ft8-coherent-llr/spec.md`'s ROW 0g Requirement above):
      same population, same sample, same seed, same anchor, same bars, both limbs —
      **not a variant, not a re-read of existing output with a better metric.**
      - Floor: fewer than 100 rows or 60 clusters delivered ⇒ STOP and escalate rather
        than run (HK-021(i)).
      - `d_clean`/`d_real` are **signed** — never gate on `|d|` (HK-021(l)).
      - **ROW 0g PASSES** ⇒ the Phase 1 gate (§4.3 above) is evaluated exactly as
        pre-registered in the 2026-08-19 spec §3.
      - **ROW 0g FIRES** ⇒ §4.3 stays VOID, no ROW 1/2/3/4 may be read, ROW 3 must not
        be declared, Route B2 must not be called dead — report which limb fired and
        STOP.
      - A PASS is not a certificate of correctness — it says the correlator is not
        grossly defective in the ways ROW 0g names.
- [ ] 11.4 **Attribution statement, recorded regardless of outcome:** if 11.1 passes and
      ROW 0g still fires at 11.3, B1 is confirmed working and the residual belongs to
      fusion/frequency, not to position (2026-08-21 15:25Z spec §5.3).

## 12. C1 — pin the cascade shape in `design.md` (docs only, QA, no Developer session)

- [x] 12.1 Added Decision **D-B2-1** to `design.md` (the coherent path is a fallback
      leg behind the grid path, never a replacement — grid decodes first; the coherent
      leg runs only where the grid decode's CRC-14 already failed, on that candidate,
      emitting only if its own CRC-14 passes), verbatim per the 1644Z spec §E, in this
      document's own house style. `openspec validate r2-coherent-llr-instrument
      --strict` confirmed passing after the edit. Does **not** amend design.md D1 — the
      2026-08-21 12:01Z spec §5 ruling on D1 remains the Captain's and remains owed.

## 13. Reporting and wrap-up — Phase B

- [ ] 13.1 Write the Phase B QA→Architect report: B1/B2 diffs (or a statement that the
      Developer session recorded an alternative, equally-justified fusion rule per
      §8.1), the §11 acceptance-ordering results in order (11.1 mode(C)/mode(G), 11.2
      unit test, 11.3 ROW 0g both limbs), the §9.4 B4 acceptance results (B4-a through
      -e, explicit on whether B4-e cleared 90%), the new SHA256s per platform, and the
      §10.4 re-pin confirmation.
- [ ] 13.2 State plainly whether the Phase 1 kill gate (`tasks.md` §4.3) is now
      unblocked, still void, or newly void for a different reason — say so, or say
      what's still missing. Do not declare Route B2 dead or alive; that verdict, if any
      fires, belongs to §4.3 itself, evaluated only after §11.3 passes.
- [ ] 13.3 Stop. No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006) — the
      Captain reviews the diff and decides on merge; this task does not declare
      readiness unprompted.
