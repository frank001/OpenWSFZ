**User-facing:** no

## Why

D-001's N1 arm (`qa/rr-study/2026-08-15-1840-architect-to-qa-N1-ber-at-refined-position-spec.md`,
Captain-authorised route, replacing the abandoned M-series) measures whether extracting LLRs at
`ft8_refine_candidate`'s refined `(freq, dt)` instead of the candidate's own grid position moves
hard-decision BER across the LDPC/OSD correction threshold. Its precondition 3.1 (recovering the
July BER harness and reproducing its bar) is done and cleared — ROW 0a does not fire
(`qa/rr-study/2026-08-16-1121-qa-n1-precondition-ber-harness-recovery-and-bar-reproduction.md`).

Precondition 3.2 is not done. N1's design is a **paired** measurement: every row extracted twice,
once at the candidate's grid position (control) and once at grid + `ft8_refine_candidate`'s
`(Δf, Δt)` (treatment). Today's `measure_population()` only *looks up* LLRs a decode run already
emitted at its own grid position (`cand["llr174"]`, keyed by `nearest_candidate`) — there is no
native entry point that runs extraction at a **caller-supplied** position. `grep` for any such
export across `src/` and `native/` on this branch returns nothing (confirmed while drafting the N1
spec, and independently while drafting this proposal). N1 cannot run without it.

This change adds that one export, as narrowly scoped as the N1 spec requires: read-only
instrumentation of the existing, unmodified `ft8_extract_likelihood()` extraction path at a
position the caller supplies, returning the raw pre-normalisation LLRs. No decode path, candidate
selection, or production behaviour changes.

## What Changes

- **New native export** `ft8_extract_llrs_at(pcm, pcm_len, freq_hz, time_offset_s, out_llr174[174])`
  in `ft8_shim.c`/`ft8_shim.h`. Builds the waterfall from `pcm` exactly as `ft8_decode_all` does
  (same `monitor_config_t`), snaps the caller's `(freq_hz, time_offset_s)` to the nearest point on
  the *same* frequency/time lattice production candidates already live on (`K_FREQ_OSR` /
  `K_TIME_OSR`, unchanged), and calls the existing `ft8_extract_likelihood()` static function
  against a synthetic `ftx_candidate_t` at that snapped position. Returns the **raw,
  pre-normalisation** 174 log-likelihoods — `ftx_normalize_logl()` is a positive scale factor and
  is deliberately not applied, matching the sign-convention discipline `c2_phase2c_ber_measurement
  .py`'s `hard_decision_ber()` already documents and depends on.
- **New non-static decode.c probe**, `ftx_extract_likelihood_at()`, following the exact pattern
  `ftx_compute_candidate_llr_stats()` already established for exposing an otherwise-`static`
  extraction routine to `ft8_shim.c` without changing any decode-path function's visibility or
  signature.
- **Shim version bump** `FT8_SHIM_VERSION` 20260041 → **20260042** (39–41 reserved/in-use by
  R0/R1/R1b/M1–M4 per the board; 42 is the next free slot).
- **No change** to `ft8_decode_all`, candidate selection, the OSD/BP decode path, `K_FREQ_OSR`/
  `K_TIME_OSR`, or any existing exported symbol's signature.
- **No C# interop wiring** — see design.md Decision D5 for why this is a considered scope choice,
  not an omission, and what would need to change to add it later.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `ft8lib-interop`: the ABI self-test's expected shim constant advances from `20260041` to
  `20260042`; a new requirement is added for the diagnostic `ft8_extract_llrs_at` native export
  (native-only — no managed `Ft8LibInterop`/`IFt8NativeInterop` surface, see design.md D5).

## Impact

- **Affected code**: `native/ft8_lib_vendor/patched/ft8/decode.c` (new non-static probe function,
  no change to any existing function's body or signature); `src/OpenWSFZ.Ft8/Native/ft8_shim.h`
  (new export declaration, version bump); `src/OpenWSFZ.Ft8/Native/ft8_shim.c` (new wrapper
  implementing the waterfall-build + lattice-snap + extract sequence); `native/ft8_lib_build/
  rebuild_shim.bat` (add `/EXPORT:ft8_extract_llrs_at`); CI's Linux/macOS rebuild steps pick up the
  new export automatically (no CI config change expected — confirm in task 5).
- **Not affected**: `ftx_decode_candidate()`, `ft8_decode_all`'s production decode path, candidate
  selection, `K_FREQ_OSR`/`K_TIME_OSR`, every existing `ft8-decoder` scenario, and every existing
  exported symbol's ABI. This change is purely additive — the same boundary R0/R1/R1b already
  established for diagnostic-only native work.
- **Consumer**: `qa/rr-study/n1-ber-at-refined-position/` (not yet written — N1's own harness,
  QA's follow-on work once this export exists), invoked directly via `ctypes`, the same access
  pattern `c2_phase2c_ber_measurement.py` and `w1_sec5_calibration.py` already use for
  `ft8_encode_message`/`ft8_get_last_candidate_llr`-family exports. No `OpenWSFZ.Daemon` or
  `OpenWSFZ.Ft8` managed code calls it.
- **Licence**: no new algorithmic code — this is instrumentation of the existing, unmodified
  `ft8_extract_likelihood()`. Standing licence policy (Captain's ruling 2026-08-11) continues to
  apply unchanged; no WSJT-X source consulted or copied.
- **Downstream**: once this lands, tested, and its DLL SHA256 is pinned, N1's own harness
  (population/pairing/gate, spec §4–§5) can be written and run. That is separate QA work, not part
  of this change's scope.
