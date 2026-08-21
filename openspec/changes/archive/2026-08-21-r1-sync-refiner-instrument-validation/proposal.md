**User-facing:** no

## Why

The FT8 decoder currently extracts symbols at the quantised lattice point returned by candidate
search — resolution **3.125 Hz / 0.08 s**, non-coherent, magnitude-only, with phase discarded at
the `uint8_t` waterfall (`decode.h:21`; `WATERFALL_USE_PHASE` is commented out and has zero
`#ifdef` branches wired to it in `decode.c`). D-001 (weak-signal recovery deficit against WSJT-X)
has been re-localised architecturally to this gap: misses cluster at ~44% median BER — reading in
the wrong place, not a faint-signal problem — and no sync refinement exists anywhere in the
pipeline. P3's own crude ⅓-lattice-cell shift produced the largest single-arm effect measured in
the D-001 programme (`S_all` = 4.27 pp), with the explicit conclusion "refine inside the decoder,
not by a union bolted outside it."

Wiring a refiner straight into the decode path (R2) without first proving it works would make a
null result uninterpretable: an implementation bug that produces no gain is indistinguishable from
a falsified hypothesis. **This change builds the refiner and validates it as an instrument against
a synthetic oracle with known answers, before it is allowed to touch the decode path or the
corpus.** R0 (native build reproducibility) is the dependency this change was blocked behind; it
merged to `main` 2026-08-14 (`f164123`), unblocking this work.

## What Changes

- Add a new native, per-candidate refinement stage (`ft8_refine_candidate`), reimplemented **from
  the method** WSJT-X uses (never copied — see Impact/licence note below): downconvert the
  candidate's region of PCM to complex baseband at ~200 Hz, retaining phase; correlate coherently
  against the three Costas 7×7 sync arrays; search two-dimensionally (coarse time → frequency →
  fine time) to produce a refined `(Δf, Δt)` plus a sync quality score.
- Expose the stage via a **new diagnostic export only**. `ftx_decode_candidate()` and all
  production decode behaviour remain byte-for-byte unchanged in this change — **BREAKING: none**,
  because nothing production-facing is touched.
- Add a validation harness that drives the refiner against the existing QA synth
  (`qa/rr-study/synth/`, encoder-only oracle) across a pre-registered grid of frequency offsets,
  time offsets, and SNR strata, and evaluates six mechanical acceptance criteria (RMS error, bias,
  noise-only null behaviour, SNR monotonicity, determinism, cost).
- Advance `FT8_SHIM_VERSION` / `Ft8LibInterop.ExpectedShimVersion` to **20260040** and rebuild all
  three platform binaries from the R0-vendored source tree plus this change's new refiner source.

## Capabilities

### New Capabilities
- `ft8-sync-refiner`: the per-candidate coherent sync-refinement stage itself (downconversion,
  Costas correlation, 2-D search) and its diagnostic-only export, plus the acceptance criteria that
  must pass before any decode-path change (R2) may build on it.

### Modified Capabilities
- `ft8lib-interop`: the ABI self-test's expected shim constant advances from `20260039` to
  `20260040`; a new diagnostic P/Invoke entry point (`ft8_refine_candidate`) is added alongside the
  existing production surface, with no change to `DecodeAll`, `GetLastPassCounts`, or
  `SetDecodeParams`.

## Impact

- **Affected code**: `native/ft8_lib_vendor/` gains the refiner's C source (new files, not part of
  the byte-identical upstream vendor tree — this is OpenWSFZ-original code); `ft8_shim.c` gains the
  new export; `src/OpenWSFZ.Ft8/Interop/` gains the corresponding P/Invoke binding; all three
  platform native binaries are rebuilt.
- **Affected tooling**: `qa/rr-study/synth/` is exercised (not modified) by a new validation
  harness under `qa/` that generates the offset/SNR grid, calls the refiner, and evaluates the six
  acceptance criteria; depends on R0's `p23_common.py` determinism fix (hash-randomised set
  iteration) already landed.
- **Not affected**: `ftx_decode_candidate()`, the production decode path, `DecodeAll`'s managed
  contract, and every existing `ft8-decoder`/`ft8lib-interop` scenario continue to behave
  identically — this change is additive and diagnostic-only by design.
- **Licence**: WSJT-X source may be read for understanding of the method; **no line of WSJT-X code
  may be copied, transliterated, or ported** (Captain's ruling, 2026-08-11 — MIT/BSD-2/BSD-3/ISC
  only; WSJT-X is GPLv3 and out of bounds regardless of this project's own AGPL-3.0 licence). The
  refiner is written from the method description, independently.
- **Downstream**: this change unblocks R2 (refinement wired into the decode path) only if all six
  acceptance criteria pass. It does not itself change recovery, false-positive rate, or any other
  decode-path metric — those are R2's concern, gated on this change's PASS.
