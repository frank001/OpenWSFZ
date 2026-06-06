## Context

The SNR value attached to each decode result originates in `ft8_shim.c`
(`ft8_decode_all`), specifically in the `signal_db` computation block (lines 331–356 of
the current source). The formula is:

```
snr = signal_db - noise_floor_db - 26.0
```

where:
- `noise_floor_db` = waterfall-wide median, expressed in dB — a well-established estimator.
- `26.0` = `10·log₁₀(2500 / 6.25)` — the WSJT-X bandwidth normalisation constant (correct).
- `signal_db` = average over 79 symbols of **max(row[0..7])** — the flaw under repair.

FT8 is 8-FSK: at each symbol the transmitter activates exactly one of 8 tone bins. Taking
`max` over all 8 bins per symbol always selects the highest-energy bin, which is a noise
peak from a non-signal bin whenever that peak exceeds the signal bin. This inflates
`signal_db` by approximately 1–2 dB and introduces per-trial scatter (R² = 0.267), as
confirmed by the R&R study run `2026-06-06-5b868ce`.

The decoded tone sequence is available at the point of SNR computation: `ftx_decode_candidate`
has already succeeded and `msg.payload` is in hand. `ft8_encode(msg.payload, tones)` — an
O(79) integer operation — yields the transmitted tone index (0–7) for each of the 79
symbols. The suppression path (`suppress_candidate_tiles`) already calls this function on
the same `msg`; the SNR computation can share the identical call.

## Goals / Non-Goals

**Goals:**

- Replace `max(row[0..7])` with `row[tones[b - b0]]` in the signal power estimation loop,
  eliminating noise from the 7 non-active bins.
- Rebuild the native binary for all three target platforms (win-x64, linux-x64, osx-arm64).
- Verify via the R&R study that bias moves toward 0 dB and R² improves.

**Non-Goals:**

- Changing the noise-floor estimator (median approach is sound).
- Changing the 26 dB bandwidth correction.
- Modifying the decode pipeline, candidate search, LDPC, or iterative subtraction.
- Matching WSJT-X's exact SNR computation (parity is aspirational; accuracy relative to
  injected truth is the measurable target).
- Updating any managed C# code (`Ft8Decoder.cs`, `DecodeResult`, `AllTxtWriter`).

## Decisions

### D1 — Use `ft8_encode` for tone retrieval, not the candidate score

**Alternatives considered:**

| Option | Verdict |
|---|---|
| Use `cand->score` (sync correlation) as a proxy for SNR | Score is a dimensionless Costas-correlation value with no agreed dB mapping; would require empirical calibration per noise floor, and re-introduces a scene-dependent parameter. Rejected. |
| Average all 8 bins (mean instead of max) | Reduces the upward bias somewhat (~0.5 dB) but still includes noise from 7 non-signal bins. Does not fully eliminate the variance source. Rejected. |
| Use `ft8_encode` to select the active tone per symbol | Deterministic, zero-noise-from-wrong-bins, cheap, uses code already compiled and linked. **Chosen.** |

### D2 — Call `ft8_encode` once per candidate, not shared with `suppress_candidate_tiles`

`suppress_candidate_tiles` is called later in the same loop iteration (after the dedup
and text-decode paths). To keep the SNR block self-contained and avoid forward-reference
coupling, `ft8_encode` is called a second time independently in the SNR block. The cost is
negligible (79-symbol lookup table walk, ≪ 1 µs).

### D3 — Symbol index uses `b - b0` not `sym` counter

The existing loop variable is `b` (absolute block index, range `[b0, b1)`). The symbol
index within the decoded message is `b - b0` (range `[0, FT8_NN)`). The `tones` array
is indexed by symbol index, so `tones[b - b0]` is correct. A separate `sym` counter is
not introduced to keep the diff minimal.

### D4 — No change to `fi` offset calculation

`fi = cand->time_sub * pt + cand->freq_sub * nb + cand->freq_offset` already positions
the row pointer at the candidate's frequency origin (tone 0). `row[tones[b - b0]]` then
offsets by the transmitted tone index (0–7), which is exactly the bin to read. The existing
index arithmetic is correct and unchanged.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `ft8_encode` depends on `msg.payload` being correctly populated | It is: `ftx_decode_candidate` fully populates `msg` before the SNR block is reached; the existing text-decode call (`ftx_message_decode`) also depends on this and runs earlier. |
| Tone-bin signal power is lower than max-of-8, potentially causing SNR to read slightly negative at very weak signals | Expected and correct — the previous inflated reading was the anomaly. WSJT-X itself reports −24 dB for the lowest R&R tier, confirming this range is physically meaningful. |
| Platform-specific rebuild introduces a regression on linux-x64 or osx-arm64 | The change is a pure C source edit; build reproducibility is protected by CI (G6 gate runs on all three matrix legs). |
| R&R re-run required to confirm improvement | The study takes ~40 minutes; this is a planned verification step, not a risk. |

## Migration Plan

1. Edit `ft8_shim.c` — replace the signal power loop (single logical change, ≈ 8 lines).
2. Rebuild native binaries for all three platforms and commit updated DLL/SO/DYLIB.
3. Run `dotnet test` — confirm G6 gate and all existing tests pass.
4. Commit and push; CI validates on all three matrix legs.
5. Re-run R&R study against the new build; append result to `trend.csv`.
6. If bias ≈ 0 dB and R² ≥ 0.6, close the change. If not, investigate residual offset.

**Rollback:** revert the `ft8_shim.c` edit and rebuild binaries — no data migration, no
schema change, no user-visible API change.
