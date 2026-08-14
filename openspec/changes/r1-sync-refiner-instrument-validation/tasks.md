## 1. Build the refiner (native, diagnostic-only)

- [ ] 1.1 Read WSJT-X's `ft8_downsample` → `sync8d` → refined `ft8b` extraction path for
      understanding only. Per the Captain's binding licence ruling, no line may be copied,
      transliterated, or ported — write the C source independently from the method description in
      the spec, not by editing a pasted-in copy.
- [ ] 1.2 Add the new refiner source under `native/ft8_lib_vendor/` in a clearly separated location
      from the byte-identical upstream vendor tree R0 established (design.md Open Question 1) —
      record which placement was chosen and why.
- [ ] 1.3 Implement stage 1 (downconvert to complex baseband, phase retained, ~200 Hz working rate)
      and stage 2 (coherent correlation against the three Costas 7×7 arrays: sum complex values
      first, magnitude last — explicitly not the `ft8_decode_multi_symbols()` shape, which sums dB
      magnitudes and is dead/wrong code already in the tree).
- [ ] 1.4 Implement stage 3 (two-dimensional search: coarse time → frequency → fine time,
      re-deriving the baseband at the refined frequency before the fine time pass), using WSJT-X's
      published working ranges (±2.5 Hz / 0.5 Hz steps; ±4 baseband samples / ~5 ms) only as a
      starting point, tunable to hit AC-1 (design.md D3).
- [ ] 1.5 Add `ft8_refine_candidate` as a new shim export. Confirm via `dumpbin /exports` (or
      platform equivalent) that no existing exported symbol changed and the new symbol is present.
- [ ] 1.6 Confirm `ftx_decode_candidate()` is byte-for-byte unchanged by diffing it against R0's
      vendored/patched source. No production call site anywhere in `decode.c`/`ft8_shim.c` may call
      `ft8_refine_candidate`.

## 2. Managed binding

- [ ] 2.1 Add `Ft8LibInterop.RefineCandidate` (P/Invoke to `ft8_refine_candidate`) and the
      corresponding `IFt8NativeInterop.RefineCandidate` method, matching the existing
      `SetDecodeParams` pattern so a `FakeInterop` can record calls without loading the native DLL.
- [ ] 2.2 Grep the production decode path (everything reachable from `DecodeAll` in
      `OpenWSFZ.Daemon`/`OpenWSFZ.Ft8`) to confirm zero call sites reference `RefineCandidate` or
      `ft8_refine_candidate` outside test code and the new validation harness.

## 3. Validation oracle and population

- [ ] 3.1 Fix strata globally before generating anything (HK-021(g)): frequency offsets
      `{0, ±0.4, ±0.8, ±1.2, ±1.5} Hz` plus uniform-random draws; time offsets
      `{0, ±0.01, ±0.02, ±0.03, ±0.039} s` plus uniform-random draws; SNR strata
      `{+5, 0, −5, −10, −15, −20} dB`; distinct messages per generated buffer (standing synth
      requirement, `qa/rr-study/synth/`); `n ≥ 200` per SNR×offset-class cell.
- [ ] 3.2 Generate the population via the existing encoder-only synth chain (`encoder.py` →
      `symbols.py` → `modulator.py` → `channel.py` → `wavio.py`). Do not touch the decoder side —
      truth is known by construction.
- [ ] 3.3 Report per-cell `n` for every SNR×offset-class cell. Any cell short of 200 is named as an
      underpowered instrument failure, not silently averaged in (HK-021(i)).
- [ ] 3.4 Add a pure-noise-only generation path (no injected signal) for AC-3, at the same trial
      count discipline as the signal-bearing cells.

## 4. Validation harness and the six acceptance criteria

- [ ] 4.1 Build the harness (placement per design.md Open Question 3, e.g. under
      `qa/rr-study/` alongside the synth it drives) that calls `RefineCandidate` for every generated
      signal, records truth vs. measured `(Δf, Δt)`, and serialises raw per-signal results before
      any aggregation — so AC-5's byte-diff has something meaningful to compare.
- [ ] 4.2 **AC-1 (RMS accuracy).** Compute `RMS(Δf)`/`RMS(Δt)` at SNR ≥ −10 dB. Evaluate against
      `RMS(Δf) ≤ 0.30 Hz`, `RMS(Δt) ≤ 7.7 ms`. FAIL ⇒ implementation defect, fix and re-run; says
      nothing about D-001 (HK-021(k), both branches).
- [ ] 4.3 **AC-2 (systematic bias).** Compute `mean(Δf error)`/`mean(Δt error)` at SNR ≥ −10 dB.
      Evaluate against `≤ 0.10 Hz` / `≤ 2 ms` absolute. If this fails with mean error large relative
      to RMS in a consistent direction, check the downconversion mixer's sign convention first — the
      specific defect named in advance (spec §5) as the highest-probability failure mode. Assert the
      sign/index convention with a test, never by re-reading the code twice.
- [ ] 4.4 **AC-3 (noise-only null).** Run the refiner against the pure-noise population from 3.4.
      Report the statistical test, its statistic, and its p-value. FAIL ⇒ STOP. Do not proceed to
      draft an R2 proposal; escalate to the Captain immediately — this is the one criterion where a
      local fix-and-retry is not the correct response (design.md D5).
- [ ] 4.5 **AC-4 (SNR monotonicity).** Compute RMS error per SNR stratum across all six strata;
      confirm non-increasing as SNR increases. FAIL ⇒ name the specific stratum pair where it broke;
      implementation defect, not a D-001 finding.
- [ ] 4.6 **AC-5 (determinism).** Run the full harness three independent times against the same
      population. Mechanically byte-diff all three results files pairwise — never assert
      determinism from a single run or from reading the code. Confirm this depends on R0's
      `p23_common.py` sort-at-construction fix already being in place (it is, as of R0's merge).
- [ ] 4.7 **AC-6 (cost).** Measure per-candidate wall-clock cost; project full-corpus runtime from
      the existing corpus's measured candidate volume. Report the number; do not gate on it. If the
      projection exceeds ~8 hours, escalate rather than optimise ad hoc or narrow the corpus
      unilaterally (design.md D6).

## 5. Shim version and cross-platform build

- [ ] 5.1 Bump `FT8_SHIM_VERSION` (`src/OpenWSFZ.Ft8/Native/ft8_shim.h`) and `ExpectedShimVersion`
      (`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`) to `20260040`.
- [ ] 5.2 Rebuild all three platform binaries (Windows x64, Linux x64, macOS ARM64 — or record which
      platforms this session's toolchain access actually permitted, same honesty standard R0 applied
      to the macOS gap) from the extended vendor tree. Record each new DLL/so/dylib's SHA256.
- [ ] 5.3 Re-run R0's AC-1/AC-2-style production-decode-equality replay (≥200 contiguous cycles,
      pinned 20m corpus) between the pre-change `20260039` binary and the new `20260040` binary to
      confirm zero decode-output differences — the new export must not have altered production
      behaviour by so much as one byte. Mechanically diff, never eyeball.
- [ ] 5.4 `dotnet build`: 0 warnings. `dotnet test`: full suite green, matching the R0 baseline
      (306/306 `OpenWSFZ.Ft8.Tests`) plus whatever new tests this change adds for `RefineCandidate`
      and the `FakeInterop` path.

## 6. Reporting and wrap-up

- [ ] 6.1 Write the QA→Architect report per spec §7: all six AC results with measured values; the
      error-vs-SNR curve as a table (no parameter fit or quoted slope); per-cell `n` with any
      underpowered cell named; the AC-3 null test and its statistic/p-value; the AC-5 byte-diff
      evidence; measured AC-6 cost; the new DLL SHA256s and shim `20260040`; and an explicit
      statement of which of the four §4 outcome branches (R1 FAIL / R1 PASS + …) this run landed in,
      without speculating about R2's eventual result.
- [ ] 6.2 If all six ACs PASS: state plainly that R2 is now unblocked and may be proposed next. If
      AC-3 FAILs: state plainly that R2 must not be proposed until this is resolved, and escalate.
      If AC-1/AC-2/AC-4 FAIL: state the implementation defect found and whether it was fixed within
      this session or needs a further round.
- [ ] 6.3 Stop. No push, no merge, no `pre_merge_check.py` (HK-014/HK-010/HK-006) — the Captain
      reviews the diff and decides on merge; this task does not declare readiness unprompted.
