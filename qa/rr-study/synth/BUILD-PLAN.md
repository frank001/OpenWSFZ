# Clean-room FT8 Synthesiser — Build Plan

**Owner:** QA · **Approved:** 2026-06-05 (STUDY-SPEC D8) · **Toolchain:** Python 3.14 + numpy (`../.venv`)

The synthesiser turns a known message + known channel condition into PCM that **both** WSJT-X
and OpenWSFZ will hear (STUDY-SPEC §5). It is **clean-room**: derived from the public FT8 protocol
description (Franke/Somerville/Taylor), sharing no code with OpenWSFZ or `ft8_lib`, so a shared bug
cannot mask a decode defect.

## Pipeline (STUDY-SPEC §5)

```
text ─► 77-bit payload ─► +14-bit CRC ─► LDPC(174,91) ─► 58 data symbols
        (packing.py)        (crc.py)       (ldpc.py)       + 3 Costas arrays
                                                          (symbols.py)
  ─► GFSK modulation ─► place in 15 s slot at DT/freq ─► scale to SNR + seeded noise ─► PCM WAV
     (modulator.py)                                       (channel.py)        (wavio.py)
```

## Layers & status

| # | Module | What | Testable in isolation? | Status |
|---|---|---|---|---|
| L1 | `constants.py` | Tone count, spacing (6.25 Hz), symbol period (0.16 s), Costas array, Gray map, slot length | — | ✅ done |
| L2 | `crc.py` | FT8 CRC-14 (poly `0x2757`) over the padded 77-bit message | ✅ self-consistent + known vectors | ✅ done |
| L3 | `symbols.py` | 174 codeword bits → 58 Gray-coded data tones, interleaved with Costas at 0/36/72 → 79 tones | ✅ structural (Costas positions, range, count) | ✅ done |
| L4 | `modulator.py` | 79 tones → continuous-phase GFSK audio at target freq/DT in a 15 s slot | ✅ tone-count, duration, instantaneous-freq checks | ✅ done |
| L5 | `channel.py` | Seeded additive noise scaled to a target SNR in the 2500 Hz WSJT-X reference bandwidth | ✅ measured in-band SNR ≈ target | ✅ done |
| L6 | `wavio.py` | 16-bit mono PCM WAV writer (48 kHz) | ✅ round-trip | ✅ done |
| L7 | `packing.py` | Standard-message text → 77-bit payload (callsign 28-bit + grid/report 15-bit, i3/n3 type bits) | ✅ vs published worked example once implemented | ⏳ **next** |
| L8 | `ldpc.py` | 91-bit message → 83 parity bits → 174-bit codeword (FT8 generator matrix) | ✅ parity-check `H·c = 0` | ⏳ **next** |
| L9 | `encoder.py` | Wire L7→L2→L8→L3 into `encode_message(text) -> 79 tones` | ✅ end-to-end tone vector | 🔶 wired; blocked on L7/L8 |
| G | **§5 gate** | WSJT-X decodes a clean (+10 dB) render of every study message, else abort | requires WSJT-X | ⛔ pending L7–L9 |

L1–L6 (the channel/DSP spine) and the structural scaffolding are **independently verifiable now**
and covered by `../tests`. L7 (message packing) and L8 (LDPC parity) are the two table-heavy,
protocol-exact pieces; until both land, `encode_message` cannot produce a WSJT-X-decodable codeword,
so the §5 gate stays closed. That is by design — we build the verifiable spine first, then the
protocol tables, then prove correctness against WSJT-X at the gate.

## Definition of done for the synthesiser

1. `H · c = 0` for every generated codeword (L8 self-check).
2. CRC-14 matches a published FT8 worked example (L2).
3. **§5 gate green:** WSJT-X decodes a clean +10 dB render of every message in `scenarios/`.
4. Measured in-band SNR within ±0.5 dB of target across the S1 ladder (L5).
