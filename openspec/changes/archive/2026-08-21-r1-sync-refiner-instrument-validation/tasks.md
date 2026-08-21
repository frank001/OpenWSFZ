## 1. Build the refiner (native, diagnostic-only)

- [x] 1.1 Read WSJT-X's `ft8_downsample` → `sync8d` → refined `ft8b` extraction path for
      understanding only. Per the Captain's binding licence ruling, no line may be copied,
      transliterated, or ported — write the C source independently from the method description in
      the spec, not by editing a pasted-in copy.
      **NOTE:** WSJT-X source was not present in or accessible from this session/repo at all
      (`ft4_ft8_public/` is never vendored, per standing policy). Implementation is written
      directly from spec.md/design.md's method description — clean-room by construction, which
      satisfies the licence ruling more strongly than "read for method, never copied" requires.
      See sync_refiner.c's header comment.
- [x] 1.2 Add the new refiner source under `native/ft8_lib_vendor/` in a clearly separated location
      from the byte-identical upstream vendor tree R0 established (design.md Open Question 1) —
      record which placement was chosen and why.
      **Placement:** `native/ft8_lib_vendor/refine/sync_refiner.c` — a new sibling directory to
      `common/`, `fft/`, `ft8/` (the byte-identical-to-upstream subtrees), per design.md Open
      Question 1's own suggested answer. Keeps R0's provenance guarantee for those three
      subdirectories untouched (D7).
- [x] 1.3 Implement stage 1 (downconvert to complex baseband, phase retained, ~200 Hz working rate)
      and stage 2 (coherent correlation against the three Costas 7×7 arrays: sum complex values
      first, magnitude last — explicitly not the `ft8_decode_multi_symbols()` shape, which sums dB
      magnitudes and is dead/wrong code already in the tree).
      Implemented as `downconvert_decimate()` (fused mix/filter/decimate, Hann-windowed-sinc FIR)
      and `costas_coherent_sum()` (per-symbol correlation using the ABSOLUTE baseband sample index
      for phase continuity across all 21 sync symbols — this is what makes the sum genuinely
      coherent, not 21 independent per-symbol estimates).
- [x] 1.4 Implement stage 3 (two-dimensional search: coarse time → frequency → fine time,
      re-deriving the baseband at the refined frequency before the fine time pass), using WSJT-X's
      published working ranges (±2.5 Hz / 0.5 Hz steps; ±4 baseband samples / ~5 ms) only as a
      starting point, tunable to hit AC-1 (design.md D3).
      Coarse time search widened to ±60 ms (D3 — tuned to cover this change's own pre-registered
      ±39 ms time-offset grid with margin, since ±4 samples/~5ms would not). Frequency search kept
      at WSJT-X's published ±2.5 Hz / 0.5 Hz-step starting point. Fine time search re-derives
      baseband at 2000 Hz (decimate-by-6) at the refined carrier, ±10 ms / 0.5 ms steps.
- [x] 1.5 Add `ft8_refine_candidate` as a new shim export. Confirm via `dumpbin /exports` (or
      platform equivalent) that no existing exported symbol changed and the new symbol is present.
      Declared in `ft8_shim.h`, defined in `sync_refiner.c`, added to `rebuild_shim.bat`'s
      `/EXPORT` list and `build_linux.sh`'s object list (ELF exports non-static symbols by
      default — no explicit export list needed on that platform). `dumpbin /exports` verification
      deferred to task 5.2 (actual rebuild).
- [x] 1.6 Confirm `ftx_decode_candidate()` is byte-for-byte unchanged by diffing it against R0's
      vendored/patched source. No production call site anywhere in `decode.c`/`ft8_shim.c` may call
      `ft8_refine_candidate`.
      Confirmed: zero bytes touched in `native/ft8_lib_build/patched/ft8/decode.c` or
      `src/OpenWSFZ.Ft8/Native/ft8_shim.c`'s `ft8_decode_all` (only `ft8_shim.h`'s declarations/
      version comment changed, which is not part of R0's byte-identical vendor guarantee). Grep
      confirms `ft8_refine_candidate`/`RefineCandidate` appears only in the interop seam
      (`Ft8LibInterop.cs`, `IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`), its own
      implementation file, docs, and the build scripts' export/object lists — no call site in
      `decode.c`, `ft8_shim.c`, `Ft8Decoder.cs`, or `OpenWSFZ.Daemon`.

## 2. Managed binding

- [x] 2.1 Add `Ft8LibInterop.RefineCandidate` (P/Invoke to `ft8_refine_candidate`) and the
      corresponding `IFt8NativeInterop.RefineCandidate` method, matching the existing
      `SetDecodeParams` pattern so a `FakeInterop` can record calls without loading the native DLL.
      Added to `Ft8LibInterop.cs`, `IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`; all 8
      existing `IFt8NativeInterop` test-double implementations updated with a stub; new
      `RefineCandidateTests.cs` covers fake delegation + a real-binary smoke test (2.1a/b/c).
- [x] 2.2 Grep the production decode path (everything reachable from `DecodeAll` in
      `OpenWSFZ.Daemon`/`OpenWSFZ.Ft8`) to confirm zero call sites reference `RefineCandidate` or
      `ft8_refine_candidate` outside test code and the new validation harness.
      Confirmed via grep (see 1.6 note) — zero production call sites.

## 3. Validation oracle and population

- [x] 3.1 Fix strata globally before generating anything (HK-021(g)): frequency offsets
      `{0, ±0.4, ±0.8, ±1.2, ±1.5} Hz` plus uniform-random draws; time offsets
      `{0, ±0.01, ±0.02, ±0.03, ±0.039} s` plus uniform-random draws; SNR strata
      `{+5, 0, −5, −10, −15, −20} dB`; distinct messages per generated buffer (standing synth
      requirement, `qa/rr-study/synth/`); `n ≥ 200` per SNR×offset-class cell.
      Implemented in `qa/rr-study/r1-sync-refiner/population.py`. **Judgment call (HK-004,
      recorded for the report):** "offset-class" is operationalised as two classes — "grid"
      (cycles deterministically through the 9×9=81 fixed grid combinations) and "random"
      (uniform-random draws within the same ±1.5 Hz / ±0.039 s ranges) — giving 6 SNR × 2
      classes = 12 cells × 200 = 2,400 signal trials. All strata are module-level tuples
      (never dict/set) walked in fixed order; the "random"-class draws come from a single
      seeded `np.random.default_rng`, avoiding R0 D3's hash-randomised-iteration pitfall.
- [x] 3.2 Generate the population via the existing encoder-only synth chain (`encoder.py` →
      `symbols.py` → `modulator.py` → `channel.py` → `wavio.py`). Do not touch the decoder side —
      truth is known by construction.
      No per-trial WAV files are persisted (2,400 signal + 1,200 noise trials × 720 KB would be
      ~2.6 GB); `population.py` instead returns a deterministic manifest, and
      `render_signal_pcm`/`render_noise_pcm` regenerate each trial's PCM bit-identically from the
      manifest + a per-trial seed on demand — deterministic by construction, which is what makes
      AC-5 meaningful. `encoder.encode_message` is called directly at `sample_rate_hz=12000`
      (matching `gen_decoder_fixtures.py`'s pattern), so no separate downsample step is needed.
- [x] 3.3 Report per-cell `n` for every SNR×offset-class cell. Any cell short of 200 is named as an
      underpowered instrument failure, not silently averaged in (HK-021(i)).
      `population.per_cell_counts()`; `run_harness.py` writes `per_cell_n` into the results file;
      `evaluate_acs.py` computes `underpowered_cells` (any cell with n < 200) and reports it
      explicitly rather than folding it into an aggregate.
- [x] 3.4 Add a pure-noise-only generation path (no injected signal) for AC-3, at the same trial
      count discipline as the signal-bearing cells.
      `population.build_noise_population()` / `render_noise_pcm()` — n=1,200 (6× the 200 floor,
      for a well-powered KS uniformity test), coarse positions drawn across a broad band
      (300–2700 Hz, 0.1–1.0 s) rather than one fixed corner of the search space.

## 4. Validation harness and the six acceptance criteria

- [x] 4.1 Build the harness (placement per design.md Open Question 3, e.g. under
      `qa/rr-study/` alongside the synth it drives) that calls `RefineCandidate` for every generated
      signal, records truth vs. measured `(Δf, Δt)`, and serialises raw per-signal results before
      any aggregation — so AC-5's byte-diff has something meaningful to compare.
      **Placement:** `qa/rr-study/r1-sync-refiner/` (Open Question 3's own suggested answer),
      containing `population.py` (§3), `refiner_ctypes.py` (thin ctypes binding, mirrors
      `p23_common.Decoder`), `run_harness.py` (drives the population through
      `ft8_refine_candidate`), and `evaluate_acs.py` (§4.2-4.7). **Important correctness point
      caught during implementation:** `run_harness.py` writes wall-clock timing to a SEPARATE
      `.timing.json` sidecar file, deliberately excluded from the results file AC-5 byte-diffs —
      mixing non-deterministic timing into the diffed file would have made AC-5 fail on every run
      regardless of the refiner's actual determinism.
- [x] 4.2 **AC-1 (RMS accuracy).** Compute `RMS(Δf)`/`RMS(Δt)` at SNR ≥ −10 dB. Evaluate against
      `RMS(Δf) ≤ 0.30 Hz`, `RMS(Δt) ≤ 7.7 ms`. FAIL ⇒ implementation defect, fix and re-run; says
      nothing about D-001 (HK-021(k), both branches).
      **PASS**: RMS(Δf)=0.1430 Hz (≤0.30), RMS(Δt)=1.135 ms (≤7.7), n=1,600. First measured
      independently, this FAILED badly (RMS(Δf)≈1.45 Hz, RMS(Δt)≈26.5 ms) — traced to two real
      implementation defects (§1.3/§1.4's design corrections), fixed, and re-measured to PASS. See
      the QA report (`qa/rr-study/2026-08-14-2003-...md`) §3–4 for the full diagnostic trail.
- [x] 4.3 **AC-2 (systematic bias).** Compute `mean(Δf error)`/`mean(Δt error)` at SNR ≥ −10 dB.
      Evaluate against `≤ 0.10 Hz` / `≤ 2 ms` absolute. If this fails with mean error large relative
      to RMS in a consistent direction, check the downconversion mixer's sign convention first — the
      specific defect named in advance (spec §5) as the highest-probability failure mode. Assert the
      sign/index convention with a test, never by re-reading the code twice.
      **PASS**: mean(Δf error)=−0.0019 Hz (≤0.10), mean(Δt error)=+0.429 ms (≤2.0). No sign-error
      signature (mean small relative to RMS in both dimensions) — the mixer sign/index convention
      was independently re-derived and verified correct by hand three separate times during the §1
      diagnosis, and confirmed empirically via a constant-DC control test.
- [x] 4.4 **AC-3 (noise-only null).** Run the refiner against the pure-noise population from 3.4.
      Report the statistical test, its statistic, and its p-value. FAIL ⇒ STOP. Do not proceed to
      draft an R2 proposal; escalate to the Captain immediately — this is the one criterion where a
      local fix-and-retry is not the correct response (design.md D5).
      **FAIL (frequency sub-check PASSES, time sub-check FAILS).** Test corrected mid-evaluation from
      a KS-test-against-continuous-uniform (wrong instrument for a discrete/bounded search output,
      HK-021(k)) to chi-squared goodness-of-fit against the correct discrete/convolution null.
      Frequency: χ² p=0.9420, PASS. Time: χ² p=0.0000, FAIL — a real, reproducible, but not fully
      root-caused selection-bias interaction between Stage A+B's noise-optimised selection and Stage
      C's re-derivation (see QA report §5 for the full empirical trail: constant-DC control,
      independent Python replica, fixed-vs-selected comparison). **STOPPED and escalated per D5 —
      did not iterate further locally.**
- [x] 4.5 **AC-4 (SNR monotonicity).** Compute RMS error per SNR stratum across all six strata;
      confirm non-increasing as SNR increases. FAIL ⇒ name the specific stratum pair where it broke;
      implementation defect, not a D-001 finding.
      **FAIL (marginal).** Three broken pairs, all tiny (freq +0.0016 Hz and +0.0045 Hz; time +0.024
      ms) — plausibly sampling noise at n=400/stratum, but AC-4 is a strict mechanical gate and is
      reported as FAIL per its literal definition, not softened. See QA report §6 for the full
      per-stratum table.
- [x] 4.6 **AC-5 (determinism).** Run the full harness three independent times against the same
      population. Mechanically byte-diff all three results files pairwise — never assert
      determinism from a single run or from reading the code. Confirm this depends on R0's
      `p23_common.py` sort-at-construction fix already being in place (it is, as of R0's merge).
      **PASS.** Three full runs (`run_a.json`/`run_b.json`/`run_c.json`,
      `qa/rr-study/r1-sync-refiner/results/2026-08-14/`), each 1,209,182 bytes, byte-identical.
      Wall-clock timing deliberately excluded from the diffed files (separate `.timing.json`
      sidecar) so scheduler jitter could never cause a spurious FAIL here.
- [x] 4.7 **AC-6 (cost).** Measure per-candidate wall-clock cost; project full-corpus runtime from
      the existing corpus's measured candidate volume. Report the number; do not gate on it. If the
      projection exceeds ~8 hours, escalate rather than optimise ad hoc or narrow the corpus
      unilaterally (design.md D6).
      **Measured, not gated.** Mean 21.5 ms/candidate; projected full-corpus (2,529 cycles) runtime
      1.51 h at 100 candidates/cycle, 5.14 h at the worst-case 340 candidates/cycle bound — both
      comfortably under the ~8 h escalation threshold. No escalation triggered.

## 5. Shim version and cross-platform build

- [x] 5.1 Bump `FT8_SHIM_VERSION` (`src/OpenWSFZ.Ft8/Native/ft8_shim.h`) and `ExpectedShimVersion`
      (`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`) to `20260040`.
- [x] 5.2 Rebuild all three platform binaries (Windows x64, Linux x64, macOS ARM64 — or record which
      platforms this session's toolchain access actually permitted, same honesty standard R0 applied
      to the macOS gap) from the extended vendor tree. Record each new DLL/so/dylib's SHA256.
      **Windows x64**: rebuilt via `rebuild_shim.bat` (MSVC 19.44.35223), 0 errors, `sync_refiner.c`
      itself compiled with 0 warnings. **Final SHA256** `fe0b7d534e06fd4d1f79575739af650f78a524861cb195178a1c1c9036139cdc`
      (several earlier SHA256s were produced mid-session while diagnosing and fixing the two
      algorithmic defects in §1/§4 — none are referenced by any committed artefact; only this one
      is final). `dumpbin /exports` confirms all 12 symbols including `ft8_refine_candidate`.
      **Linux x64**: rebuilt via `build_linux.sh` (GCC 14.2.0, WSL2 Debian — available and used
      this session). **Final SHA256** `61eef0945bd6b7bc85a9579411677e425b4008db5de24d5e790e64b14292fa07`.
      `nm -D` confirms all 12 symbols. (Note: `build_linux.sh` had CRLF line endings that broke
      direct WSL execution — worked around with `tr -d '\r'`; not fixed in the committed script,
      flagged for follow-up since this is a pre-existing condition, not introduced by this change.)
      **macOS ARM64**: NOT rebuilt — no Mac available locally, the identical limitation R0 recorded;
      requires the one-shot `workflow_dispatch` GitHub Actions path (tasks.md 2.1-2.7 pattern from
      R0). Recorded honestly in `win-x64/libft8.version.txt` and this report, same standard R0 applied.
- [x] 5.3 Re-run R0's AC-1/AC-2-style production-decode-equality replay (≥200 contiguous cycles,
      pinned 20m corpus) between the pre-change `20260039` binary and the new `20260040` binary to
      confirm zero decode-output differences — the new export must not have altered production
      behaviour by so much as one byte. Mechanically diff, never eyeball.
      Ran `qa/cycleframer-alignment-replay/r0_ac1_ac2_replay.py` against both binaries (pre-change
      `20260039` extracted from git `HEAD` — confirmed SHA256 `897f81dd…` matches R0's own shipped
      pin exactly — vs. the freshly built `20260040`), 250 contiguous cycles,
      `artefacts/20260808_live_run_0016-8080/wsjt-x/wav`, `260808_004000`..`260808_014215`
      (identical range to R0's own AC-1). `r0_ac1_ac2_diff.py` mechanical result:
      **`RESULT: PASS -- zero differences across 250 cycles`**.
- [x] 5.4 `dotnet build`: 0 warnings. `dotnet test`: full suite green, matching the R0 baseline
      (306/306 `OpenWSFZ.Ft8.Tests`) plus whatever new tests this change adds for `RefineCandidate`
      and the `FakeInterop` path.
      `dotnet build src/OpenWSFZ.Ft8`: **0 Warning(s), 0 Error(s)**.
      `dotnet test tests/OpenWSFZ.Ft8.Tests`: **309/309 passed** (306 R0 baseline + 3 new
      `RefineCandidateTests` — 2.1a fake delegation, 2.1b real-binary smoke test against the
      `synth-qso-01` fixture confirming a finite, positive sync score without throwing, 2.1c
      wrong-length-PCM `ArgumentException`), 0 failed, 0 skipped, against the freshly rebuilt
      `20260040` Windows binary.

## 6. Reporting and wrap-up

- [x] 6.1 Write the QA→Architect report per spec §7: all six AC results with measured values; the
      error-vs-SNR curve as a table (no parameter fit or quoted slope); per-cell `n` with any
      underpowered cell named; the AC-3 null test and its statistic/p-value; the AC-5 byte-diff
      evidence; measured AC-6 cost; the new DLL SHA256s and shim `20260040`; and an explicit
      statement of which of the four §4 outcome branches (R1 FAIL / R1 PASS + …) this run landed in,
      without speculating about R2's eventual result.
      Written to `qa/rr-study/2026-08-14-2003-qa-r1-sync-refiner-instrument-validation-report.md`.
- [x] 6.2 If all six ACs PASS: state plainly that R2 is now unblocked and may be proposed next. If
      AC-3 FAILs: state plainly that R2 must not be proposed until this is resolved, and escalate.
      If AC-1/AC-2/AC-4 FAIL: state the implementation defect found and whether it was fixed within
      this session or needs a further round.
      **AC-3 FAILED (time sub-check) → R2 must NOT be proposed until resolved; escalated to the
      Captain per D5** (report §12). AC-1/AC-2: two real defects found, fixed, and PASS within this
      session (report §3). AC-4: marginal FAIL, plausibly sampling noise, not fixed (a strict
      mechanical gate — no "just relax the bar" option available within this session; report §6).
- [x] 6.3 Stop. No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006) — the Captain
      reviews the diff and decides on merge; this task does not declare readiness unprompted.
      Stopping here. No push, no merge, no `pre_merge_check.py` run.
