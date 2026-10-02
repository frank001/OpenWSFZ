# SPEC — LATENESS: how late can a transmission start, cut at the slot end, and still decode? (WSJT-X and OpenWSFZ)

- **To:** QA (owner) — cc Captain  **From:** Architect  **Date:** 2026-10-02 ~07:20Z (HK-017)
- **Branch:** `arch/subtraction-feasibility`. Docs only: `git diff --stat -- src/ native/` empty.
- **Why now (Captain, 2026-10-02):** batch-2 (residual) decodes should be handled by the auto-QSO, but they land after the 17.36 s reply deadline. Captain: *"let us measure first the forgiveness of both wsjt-x and openwsfz for lateness of a signal."* This is step 1 of the #194 start-time proposal (2026-09-30), late side only.
- **Amendment 1 (2026-10-02 ~07:40Z, before any playback, §5 only):** option (a) corrected to N+3 (Captain). No row, grid or predicate changed.
- **Status:** PRE-REGISTERED. QA commits the scenario, the renders' manifest and the row predicates as code **before any playback**. Changes after playback only by a dated amendment that says why.
- **Needs:** an evening slot on the PC (≈ 3.5 h playback, WSJT-X running, receive only, radio not in the chain). No build. No `src/`/`native/` change.

## 1. Question

**Q1.** For a standard FT8 transmission that **starts late and is cut at the slot end** (what an immediate reply to a late decode produces, `TransmitAsync`, D-CALLER-021), at what lateness does each decoder stop decoding it, per SNR?

**Q2 (descriptive, from data already gathered, HK-018).** On the 2026-09-30 on-air night, where in the reply slot did batch 2 land, and what fraction of batch-2 publishes would allow an immediate reply that starts before each decoder's edge?

Already known, and **not** re-measured (`#194`; DT-MISS 2026-09-22): on live traffic, OpenWSFZ does not miss late starters more than WSJT-X, up to REF DT +2.4 s. No sweep has ever pushed a signal **past** the edge, and none has cut the tail. On the on-air night the residual pass took p50 5 001 / p95 6 423 / max 9 421 ms after a batch 1 at p50 526 ms (on-air report `3f1be2ea` §1). That is why the grid below runs to 6 s.

## 2. Lateness convention (fix this first; the DT convention has bitten this programme twice)

- **Lateness `L`** = seconds after the nominal FT8 start, i.e. **WSJT-X's DT = 0 ⇔ signal starts 0.5 s into the slot**. The grid is in `L`.
- QA states with FILE:LINE what `synth/modulator.py`'s `dt_s = 0` means (start at slot + 0, or slot + 0.5 s), and renders so that `L` is right. See `modulator-positive-clamp-and-dt-convention-defects.md` §2. Our decoder's reported DT runs ≈ 0.65 s above WSJT-X's (DT-MISS D-c). **Report lateness in `L` only, never in either decoder's reported DT.**
- Arithmetic for the reader: an FT8 transmission is 79 × 0.16 = 12.64 s, so a signal at `L` is cut by `max(0, L − 1.86)` s. The last Costas array (1.12 s) goes first, then data symbols from `L` > 2.98 s.

## 3. Design

| Item | Value |
|---|---|
| Grid `L` | 0.00, 0.25, …, 6.00 s (**25 points**) |
| SNR (2 500 Hz ref, as R&R) | −20, −15, −10, 0 dB (4) |
| Cells | 100 = 25 × 4; **8 cycles per cell**, 6 signals per cycle ⇒ **48 signals per cell**, 800 cycles ≈ 3.3 h |
| Signals per cycle | 6, at 500 / 850 / 1 200 / 1 550 / 1 900 / 2 250 Hz; all share the cycle's `L` and SNR |
| Message | the standard answer to a CQ (`<CALL> <MYCALL> <GRID4>`), **Q-prefix synthetic calls only** (NFR-021), every signal's text unique across the whole run so that dedup cannot merge two |
| Render | `modulate(..., extended=True)`, then **every sample after the slot end set to 0** (the truncation), then noise added over the whole 15 s, as R&R does |
| Order | cells in a seeded random order (seed 20261002), so that time-of-evening and WSJT-X state are not confounded with `L` |
| Playback | the standard R&R chain to both decoders at once, live, receive only. Build = current `main` (`9bade2bc` or later; record it), flag **OFF** (`subtractionEnabled=false`, asserted; the question is about the sync search, not the residual) |
| Match | per decoder: planted text exact, same cycle, \|Δf\| ≤ 10 Hz. Synthetic text only, so the comparison is NFR-021-safe; outputs are counts |

## 4. Pre-registered rows

**Validity (any FAIL ⇒ no edge is reported; the report names the row and stops):**

| Row | Predicate (as code) |
|---|---|
| P1 placement (HK-026) | for every render, the cross-correlation lag against its own `L` = 0 render equals the label to within ±2 ms, computed on the **untruncated** render, before playback |
| P2 truncation | every render with `L` > 1.86 s has `max|x|` = 0 after the slot end before noise is added, and is sample-identical to the untruncated render before the slot end |
| P3 positive control | at `L` = 0.00, SNR −10 and 0 dB: decode rate ≥ 0.90 for **each** decoder |
| P4 completeness | each decoder logged a decode pass for 800/800 played cycles (`ALL.TXT` cycle stamps, or the daemon's `Cycle` line, versus the playback log) |
| P5 level | at `L` = 0, SNR 0 dB, the median reported SNR is within ±3 dB of 0 for each decoder (playback level sanity; the known S1 bias of +1.45 dB fits inside it) |

**Outputs (exact definitions; no bar, this is a characterisation):**

- `r(d, s, L)` = matched / 48 per decoder `d`, SNR `s`, lateness `L`, with Wilson 95 % CIs.
- **Edge `E50(d, s)`** = the largest grid `L` such that `r ≥ 0.50` at that `L` **and at every smaller grid `L`**. `E90` is the same with 0.90. If `r ≥ 0.50` at `L` = 6.00, report "> 6.00". Non-monotone cells after the edge are listed, not smoothed.
- **Q2 mapping (descriptive, labelled "on-air night, one CPU, 8 workers"):** per on-air cycle with ≥ 1 residual decode, `T2 = decode-start offset into the reply slot + batch-1 time + residual elapsedMs`, all from the daemon's existing per-cycle lines (QA names the fields and FILE:LINE; if the decode-start offset is not logged, say so and use the design value, labelled). For a TX keying latency `k` ∈ {0, 0.5, 1.0} s: the fraction of those cycles with `T2 + k − 0.5 ≤ E50(WSJT-X, s)` for each `s`. If a keying latency has ever been measured, cite it. Otherwise the three values stand.

## 5. What the result decides (for the Captain, after the report)

The options put to the Captain on 2026-10-02 for batch-2 → auto-QSO:
- ~~**(a) reply one slot later**~~ **WRONG, struck (Captain, 2026-10-02):** one slot later is the other station's own TX slot, so it would not hear us. **(a′) Reply in the next slot of OUR parity (N+3, ≈ 30 s late), full length.** This is protocol-correct: a CQ caller who got no answer calls again in N+2 and listens in N+3, and a QSO partner who did not hear us repeats in N+2 and listens in N+3. It needs no edge. It does need a guard: N+2's **pass-0** decodes (available ≈ 0.5 s into N+3) must show the station is still free. If it is now working someone else, do not transmit. N+2's batch 2 arrives too late to be part of that guard.
- **(b) reply immediately, cut at the slot end**: viable only if Q2's fraction under WSJT-X's `E50`/`E90` is material.
- **(c) act only when in time, with a grace of `E90`**: same input as (b).

QA reports the numbers. **The Architect then writes the batch-2 → auto-QSO spec on the Captain's choice.** Nothing in this spec changes QSO behaviour.

## 6. Limits to state

Synthetic AWGN signals through the playback chain, with no fading, drift or co-channel crowding. One build of each decoder, and the installed WSJT-X version recorded. The other station's decoder is assumed to be WSJT-X; JTDX, MSHV and others are not measured. Answers only the late side (the early side, S3b, stays in #194).

## 7. Predictions (blind; scored at ruling time)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| LT1 | `E50(WSJT-X, −10 dB)` ∈ [2.25, 3.00] s. My basis is a recollection that WSJT-X's sync search spans about ±2.5 s in DT, **not checked against its source** | 0.60 | H |
| LT2 | `E50(OpenWSFZ, −10 dB)` > `E50(WSJT-X, −10 dB)` (ours is more forgiving; recollection of ft8_lib's candidate search allowing a partly out-of-range Costas array, not checked) | 0.55 | H-mech |
| LT3 | Q2: with `k` = 0, fewer than 5 % of on-air batch-2 cycles land before `E50(WSJT-X, −15 dB)` | 0.75 | H |
| LT4 | P1–P5 all pass first time | 0.70 | H |
