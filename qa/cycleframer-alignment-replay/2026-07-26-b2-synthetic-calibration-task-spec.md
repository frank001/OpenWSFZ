# D-001 B.2 — synthetic-waveform BER calibration, QA task spec

**Author:** QA, 2026-07-26. **Operationalises:**
`2026-07-26-2230-architect-sec6-redesign-ruling.md` §5 (method) and §6 (the `E` estimator and
its fixed reading rule), unchanged and reused verbatim per
`2026-07-26-2330-architect-capability-pricing-plan.md` §4. QA-runnable directly: no native
change, `K_MIN_SCORE`/`K_MAX_CANDIDATES` stay at shipped defaults, no rebuild.

This is QA's own execution record (same posture as B.1's spec): no `dev-tasks/` entry, since
nothing crosses HK-011's boundary.

---

## 1. What is being measured

Plant known FT8 signals into synthetic 15 s / 12 kHz buffers, add AWGN, decode through the
**unmodified shipped production path** (`ft8_decode_all`, `ft8_set_decode_params(10, 0.10, 60)`,
`K_MAX_CANDIDATES`=140, no constant swaps), and for every planted signal whose candidate is
located, read out its 174 raw LLRs and its `decoded` flag via the existing opt-in exports
(shim 20260034/20260035 — no new export, per the 22:30 ruling's decline of the `ft8_decode_
llr174_diag` proposal). Compute hard-decision BER of the raw LLRs against the true codeword
(re-derived by re-encoding the planted message and stripping sync/Gray-decoding, verified
end-to-end by `c2_phase2c_gray_sync_roundtrip_verify.py`). Bin by BER, plot P(decode | BER).

**Two arms:**
- **Arm A** — isolated planted signal, well clear (≥150 Hz) of any other planted signal in the
  same buffer. The clean calibration curve.
- **Arm B** — co-channel pairs at Δf ∈ {0, 3, 7, 15} Hz, same dt, similar SNR — the actual D-001
  condition and the condition THE 135 lives in.

## 2. Pieces reused, not re-derived (22:30 ruling §5 table, confirmed present this session)

| piece | source |
|---|---|
| message → 79 tones | `ft8_encode_message` (ctypes into `libft8.dll`, shim ≥20260035) |
| tones → true 174-bit codeword | `INV_GRAY`/`SYNC_RANGES`/Gray-decode, verified in `c2_phase2c_gray_sync_roundtrip_verify.py` — reused verbatim, not re-derived |
| tones → 12 kHz PCM | direct-at-12kHz CPFSK synthesis (numpy), parameters taken from `Ft8AudioSynthesiser.cs`'s documented constants (1920 samples/symbol at 12 kHz, 6.25 Hz tone spacing, 79 symbols, continuous phase) rather than going through the 48 kHz→decimate path, per the ruling's own "trivial CPFSK in numpy" framing |
| per-candidate raw LLRs, decoded flag, score/freq/dt | `ft8_set_candidate_diag_capture(1)` + `ft8_set_candidate_diag_llr_capture(1)` + `ft8_get_last_candidate_diag` + `ft8_get_last_candidate_llr` (shim 20260034/35, ctypes) |
| hard-decision sign convention | `hd = 1 if llr > 0.0 else 0` — the empirically-verified convention from `c2_phase2c_ber_measurement.py`, **not** decode.c's own internal `hd` formula (that one is for a different internal purpose, see that script's docstring) |
| THE 135's own measured BERs, to compute E | `c2_phase2c_ber_measurement.py`'s `compute_135_population` + `measure_population`, imported and called, not re-derived |

## 3. Synthesis parameters

- Sample rate 12 kHz, 1920 samples/symbol, 79 symbols → 151,680 samples (12.64 s) per
  transmission, placed at a fixed `dt` offset inside the 180,000-sample (15 s) buffer.
- **NFR-021:** every planted message uses a Q-prefix synthetic callsign pair (ITU-unallocated),
  same convention as every other native-touching script in this thread.
- SNR defined as a simple time-domain broadband ratio (signal RMS vs. added-noise RMS over the
  whole buffer) — an internally consistent sweep knob, not a claim to reproduce WSJT-X's own
  reported-SNR dB formula. The dependent variable this calibration reads out is **BER**, not the
  nominal SNR used to reach it; the sweep only needs to traverse BER 0% → ≳55%, which a broadband
  ratio does regardless of its absolute calibration against any other SNR convention in this
  codebase.
- Per-buffer AWGN realisation is shared across every planted signal in that buffer (one physical
  channel per buffer), consistent with "the channel sets the LLR magnitudes," not the
  implementer.
- Arm A: 8 signals/buffer, frequencies spread across a slotted range with ≥150 Hz guaranteed
  separation, same `dt`, same per-buffer SNR (sweep SNR across buffers).
- Arm B: 4 co-channel pairs/buffer (one per Δf ∈ {0, 3, 7, 15} Hz), pairs mutually ≥150 Hz apart,
  same `dt` within a pair, same per-buffer SNR.
- Candidate match tolerance: ±10 Hz / ±0.5 s (this thread's standing convention, also the free
  check on the control-arm mismatch rate the 22:30 ruling's §5 point 5 calls for).

## 4. Reading — unchanged from the 22:30 ruling, reused verbatim

- **E = Σ over THE 135 of P(decode | BER_i)**, using Arm B's curve (or Arm A's, if the two arms
  agree) — the lower-bound estimator, artefact-robust by construction.
- Reading rule (22:30 §6.1): **E < 1** → front-end limited, correction noted and overruled by
  measurement, caveat about lower-bound stated explicitly. **1 ≤ E ≤ 15** → real but small
  decode-path residue, Captain's call whether to chase it. **E > 15** → material defect, item 4
  re-decomposes, outranks §6.3.
- Report alongside E: B10/B50/B90 from the curve, and N = |{THE 135 : BER ≤ B50}|.

## 5. What this does not authorise

Same guardrails as B.1 and the plan itself: no native/`src/` change, no push/merge, no
`pre_merge_check.py`, NFR-021 (aggregate stats only in the findings doc; raw candidate/LLR/message
data under git-ignored `artefacts/`).

## 6. Cross-references

- `2026-07-26-2230-architect-sec6-redesign-ruling.md` §5, §6 — the design this operationalises.
- `2026-07-26-2330-architect-capability-pricing-plan.md` §4 — the one-line pointer sequencing
  this as B.2.
- `c2_phase2c_ber_measurement.py`, `c2_phase2c_gray_sync_roundtrip_verify.py` — reused pieces.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — the exports this harness calls.
- `src/OpenWSFZ.Ft8/Ft8AudioSynthesiser.cs` — CPFSK parameter reference.
