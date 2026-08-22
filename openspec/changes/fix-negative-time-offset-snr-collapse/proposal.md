**User-facing:** yes

## Why

The FT8 decoder reports a catastrophically wrong SNR — typically 15–20 dB too low — for
any candidate whose sync position lands **before** the start of the 15 s decode window
(`cand->time_offset < 0`, i.e. the signal arrives early relative to the nominal slot
boundary). This is not a rare edge case: `decode.c:290` searches `time_offset` over
`-10 .. +19` as a matter of routine, and any signal whose true start precedes the slot
by more than a few tens of milliseconds — normal capture/propagation jitter, not a
malformed signal — lands in the corrupted branch.

Root cause, confirmed mechanically (`qa/rr-study/2026-08-22-1454-qa-to-architect-b-dt-c3-results.md`,
arm B-dt-C3, ROW 2 fired): `ft8_shim.c:1491-1498`'s `signal_db` loop clamps the waterfall
block index `b0` to `0` when `cand->time_offset` is negative, and then re-derives the
79-symbol index from that **clamped** value (`tones[b - b0]`) instead of from the true,
unclamped `time_offset`. Every symbol read is therefore taken from the wrong tone bin,
offset by `|time_offset|` blocks — `ft8_lib`'s own convention
(`patched/ft8/decode.c:160,226`) is to **skip** out-of-range blocks and never re-anchor
the symbol index, which this shim does not do. The measured signature (a step of 17.4 dB,
more than 200× the largest a truncation-only explanation could produce, landing exactly
at the block where `time_offset` turns negative) matches this mechanism and rules out the
alternative (signal falling partly outside the window) as the cause.

This directly costs decode recall: any early-arriving signal that would otherwise decode
at a normal SNR is scored 15–20 dB low, which — depending on where the noise-suppression
and OSD gates sit — can cause it to be discarded, mis-triaged, or simply misreported to
the operator. It is also a likely contributor to the still-open D-001 weak-signal
recovery gap (GitHub #3/#111), though this change does not claim to close D-001 on its
own; it removes one confirmed, mechanical source of SNR corruption.

## What Changes

- **`ft8_shim.c`** — the `signal_db` loop inside `ft8_decode_all`'s per-candidate block
  (currently lines 1485–1507) is corrected so the symbol index used to read
  `tones[]` is derived from `cand->time_offset` **unclamped**, matching `ft8_lib`'s own
  skip-out-of-range convention. The block-index clamp (`b0 = max(0, time_offset)`) is
  retained (it is still required to avoid reading the waterfall at a negative block
  index) but the **upper** bound (`b1`) is corrected to match, so no symbol index can run
  past `FT8_NN` — closing a latent out-of-bounds read that the clamp-mismatch made
  possible once the symbol-index side is fixed. `cnt` (the sample count the mean is
  divided by) will now legitimately be smaller than 79 for early-arriving signals — the
  average is *thinned* by the missing leading blocks, which is correct, rather than
  *corrupted* by wrong ones, which is the current behaviour.
- **`ft8_shim.h`** — `FT8_SHIM_VERSION` bumped to document the fix; version-history
  comment block extended.
- **Native binaries rebuilt** — win-x64 `libft8.dll`, linux-x64 `libft8.so`, osx-arm64
  `libft8.dylib` (CI-built) replaced with the corrected build.
- **`Ft8LibInterop.cs`** — `ExpectedShimVersion` constant updated to match.
- **`ft8lib-interop/spec.md`** — ABI sentinel version updated.
- **Regression + acceptance validation** — the eight committed `results/replay_*.json`
  files from AC-N1 (all `dt >= 0`) SHALL replay bit-identical, decode for decode, proving
  the fix is a no-op on every existing corpus that never exercised the clamped branch.
  The QA harness that discovered and localised the defect,
  `qa/rr-study/r2-coherent-llr-instrument/b_dt_c3_offline_negative_dt.py`, SHALL be
  re-run unchanged against the fixed binary as the fix's own acceptance test: it is
  pre-registered (in the spec that produced the pre-fix report) to require `E(p)` flat
  and `Δ(p) < 8.0 dB` across the whole sweep once the defect is corrected.

No change to `FT8Result` struct layout, no ABI break, no new native export. This is a
correctness fix to an existing, always-active code path — every production decode call
already runs this loop; there is no opt-in.

## Capabilities

### New Capabilities

_(None — this is a bug fix to existing SNR computation, not a new capability.)_

### Modified Capabilities

- `ft8-decoder`: SNR accuracy behaviour changes for the specific, previously-unhandled
  case of a candidate whose sync position precedes the decode window
  (`time_offset < 0`). A new requirement is added describing correct behaviour in this
  case; the existing SNR-accuracy requirement (S1 R&R gate, `true_dt >= 0` only) is
  unaffected in its own terms but is cross-referenced.
- `ft8lib-interop`: ABI sentinel version advances; `ExpectedShimVersion` and
  `ft8lib-interop/spec.md` version references must be updated to match the new
  `FT8_SHIM_VERSION`.

## Impact

| Area | Detail |
|---|---|
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c` | `signal_db` loop's symbol-index derivation and block-range upper bound corrected (lines ~1485–1507) |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.h` | `FT8_SHIM_VERSION` bumped, version-history comment extended |
| `src/OpenWSFZ.Ft8/Native/{win-x64,linux-x64,osx-arm64}/libft8.{dll,so,dylib}` | Rebuilt binaries |
| `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` | `ExpectedShimVersion` constant |
| `openspec/specs/ft8lib-interop/spec.md` | ABI sentinel version |
| `openspec/specs/ft8-decoder/spec.md` | New requirement for `time_offset < 0` SNR correctness |
| `qa/rr-study/r2-coherent-llr-instrument/` | AC-N1 replay regression check; B-dt-C3 harness re-run as post-fix acceptance |
| D-001 (GitHub #3/#111) | Contributing mechanism removed; does not close D-001 on its own |
