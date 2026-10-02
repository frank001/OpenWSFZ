# SPEC — LATENESS: how late can a transmission start, cut at the slot end, and still decode? (WSJT-X and OpenWSFZ)

- **To:** QA (owner) — cc Captain  **From:** Architect  **Date:** 2026-10-02 ~07:20Z (HK-017)
- **Branch:** `arch/subtraction-feasibility`. Docs only: `git diff --stat -- src/ native/` empty.
- **Why now (Captain, 2026-10-02):** batch-2 (residual) decodes should be handled by the auto-QSO, but they land after the 17.36 s reply deadline. Captain: *"let us measure first the forgiveness of both wsjt-x and openwsfz for lateness of a signal."* This is step 1 of the #194 start-time proposal (2026-09-30). Since Amendment 2 it covers **both** the late and the early side.
- **Amendment 1 (2026-10-02 ~07:40Z, before any playback, §5 only):** option (a) corrected to N+3 (Captain). No row, grid or predicate changed.
- **Amendment 2 (2026-10-02 ~12:30Z, before any playback; QA had frozen nothing):** Captain: *"I find >3 hours testing to find the edge excessive."* **§3 redesigned to ≈ 51 min of playback (was ≈ 3.3 h), and the early side added in the same session.** The main saving: **each of 16 signals in a cycle carries its own (`L`, SNR) cell**, where the original design made all 6 signals in a cycle share one. SNR levels cut from 4 to 2. §4 rows adapted (P1/P2 per signal, P3b and P6 added). §7: the SNR each prediction refers to moved to the new levels (−10→−8, −15→−16 dB). **No range or probability changed**, and LT5 was added for the early side. §6: the early side is no longer excluded. The superseded design is in git (`dac9f4ec`).
- **Status:** PRE-REGISTERED. QA commits the scenario, the renders' manifest and the row predicates as code **before any playback**. Changes after playback only by a dated amendment that says why.
- **Needs:** ≈ 1 h on the PC (≈ 51 min playback + warm-up), WSJT-X running, receive only, radio not in the chain. No build. No `src/`/`native/` change.

## 1. Question

**Q1.** For a standard FT8 transmission that **starts late and is cut at the slot end** (what an immediate reply to a late decode produces, `TransmitAsync`, D-CALLER-021), at what lateness does each decoder stop decoding it, per SNR?

**Q1e (added in Amendment 2, #194).** For a transmission that **starts early** (a station whose clock runs fast) and is played in full, how early can it start and still decode, per decoder and SNR? S3b was built for this in August and never run as a measurement.

**Q2 (descriptive, from data already gathered, HK-018).** On the 2026-09-30 on-air night, where in the reply slot did batch 2 land, and what fraction of batch-2 publishes would allow an immediate reply that starts before each decoder's edge?

Already known, and **not** re-measured (`#194`; DT-MISS 2026-09-22): on live traffic, OpenWSFZ does not miss late starters more than WSJT-X, up to REF DT +2.4 s. No sweep has ever pushed a signal **past** the edge, and none has cut the tail. On the on-air night the residual pass took p50 5 001 / p95 6 423 / max 9 421 ms after a batch 1 at p50 526 ms (on-air report `3f1be2ea` §1). That is why the late grid runs to 6 s.

## 2. Lateness convention (fix this first; the DT convention has bitten this programme twice)

- **Lateness `L`** = seconds after the nominal FT8 start, i.e. **WSJT-X's DT = 0 ⇔ signal starts 0.5 s into the slot**. The grid is in `L`; negative `L` is early.
- QA states with FILE:LINE what `synth/modulator.py`'s `dt_s = 0` means (start at slot + 0, or slot + 0.5 s), and renders so that `L` is right. See `modulator-positive-clamp-and-dt-convention-defects.md` §2. Our decoder's reported DT runs ≈ 0.65 s above WSJT-X's (DT-MISS D-c). **Report lateness in `L` only, never in either decoder's reported DT.**
- Arithmetic for the reader: an FT8 transmission is 79 × 0.16 = 12.64 s, so a signal at `L` is cut by `max(0, L − 1.86)` s. The last Costas array (1.12 s) goes first, then data symbols from `L` > 2.98 s. An early signal at `L` < −0.5 starts before the slot boundary. Whether a decoder sees audio from before the boundary is **not assumed**: the early block plays the head genuinely before the boundary (§3), so the measurement is right either way.

## 3. Design (Amendment 2)

Two blocks in one session, in this order: **LATE**, then **EARLY**. Both decoders listen live to the same playback.

| Item | LATE block | EARLY block |
|---|---|---|
| Grid `L` | 0.00, 0.25, …, 6.00 s (**25 points**) | −3.00, −2.75, …, 0.00 s (**13 points**; `L` = 0 is the block's own positive control) |
| SNR (2 500 Hz ref, as R&R) | −16, −8 dB (2) | −16, −8 dB (2) |
| Cells | 50 | 26 |
| Signals per cell | **32** | **32** |
| Signals | 1 600 | 832 |
| Playback | ordinary on-boundary 15 s buffers | buffers **armed 3.0 s early** through the existing S3b extended path (`requires_extended_dt`, `early_by_s`), long enough to hold every signal to its end |
| Cycles | 100 planted | 52 planted, **each followed by one cycle with no playback start**, so that an early buffer never overlaps the next one ⇒ 104 |
| Truncation | each signal set to 0 after the slot end, **before mixing** | none (every signal is played in full) |

- **Total 204 cycles ≈ 51 min.**
- **Signals per cycle: 16**, on fixed frequency slots `300 + 150·i` Hz, `i` = 0…15 (300–2 550 Hz). 150 Hz is three FT8 signal widths, so the slots do not overlap.
- **Assignment (seeded, 20261002, committed as code before playback):** within a block, the cells' signals are dealt to (cycle, frequency slot) positions so that (i) each cell gets exactly 32 signals, (ii) no cell appears twice in one cycle, and (iii) each cell's 32 signals use ≥ 12 distinct frequency slots. Cycle order is then shuffled by the same seed, so that time of evening and WSJT-X state are not confounded with `L`.
- **Message:** the standard answer to a CQ (`<CALL> <MYCALL> <GRID4>`), **Q-prefix synthetic calls only** (NFR-021), every signal's text unique across the whole session so that dedup cannot merge two.
- **Render:** each signal by `modulate(..., extended=True)`, truncated per the block, scaled to its SNR, mixed. Then noise is added over the whole buffer, as R&R does, and the usual peak-normalise and fade are applied. QA names the harness functions reused (FILE:LINE). **No new mixing code where the S4/S8 multi-signal path already does it.**
- **Build:** current `main` (record the SHA), flag **OFF**, asserted by config read-back. 🔴 `main` ships `subtractionEnabled` **ON** since 2026-10-02 10:23:45Z, so this needs an explicit override. The question is about the sync search, not the residual.
- **Match:** per decoder, planted text exact, same cycle, |Δf| ≤ 10 Hz. Synthetic text only, so the comparison is NFR-021-safe; outputs are counts.

**Why 16 and not more (trade-off for the Captain, recommendation 16):** 24 signals a cycle would save about a third of the time again. But OpenWSFZ loses more decodes than WSJT-X as a scene gets denser (DENSITY live cost ≈ 4.30 pp). Packing harder would bias exactly the cross-decoder comparison this run exists to make. 16 signals in 2.5 kHz is an ordinary evening band. **A third SNR level (e.g. −20 or 0 dB) costs ≈ 25 min if the Captain wants it.**

**Precision, stated in advance:** 32 signals per cell give a Wilson 95 % half-width of about ±16 pp at r = 0.5. The edge is located to one grid step (0.25 s) where the fall is steep, and no better. Signals in one cycle share the same noise realisation and decoder state, so cells are not fully independent. The report says so, and draws no conclusion from a one-step difference between decoders.

## 4. Pre-registered rows

**Validity (any FAIL ⇒ no edge is reported; the report names the row and stops):**

| Row | Predicate (as code) |
|---|---|
| P1 placement (HK-026) | for every signal, the cross-correlation lag of its clean, **untruncated** render against its own `L` = 0 render equals the label to within ±2 ms, computed before playback |
| P2 truncation | every LATE signal with `L` > 1.86 s has `max|x|` = 0 after the slot end before mixing, and is sample-identical to its untruncated render before the slot end. Every EARLY buffer contains each of its signals from start to end (no sample of any signal lies outside the buffer) |
| P3 positive control (late) | LATE block, `L` = 0.00, −8 dB: decode rate ≥ 0.90 for **each** decoder |
| P3b positive control (early path) | EARLY block, `L` = 0.00, −8 dB: decode rate ≥ 0.90 for each decoder, **and** within 3 matched signals (of 32) of P3's count for the same decoder. Otherwise the early-armed path itself changes decoding, and the early edges are not reported |
| P4 completeness | each decoder logged a decode pass for every planted cycle (204 − 52 idle = 152), from `ALL.TXT` cycle stamps or the daemon's `Cycle` line versus the playback log |
| P5 level | LATE block, `L` = 0, −8 dB: the median reported SNR is within ±3 dB of −8 for each decoder (a playback-level check; the known S1 bias of +1.45 dB fits inside it) |
| P6 wrong-cycle decodes | count of planted texts decoded in a cycle other than their own, per decoder. **Must be 0 in planted cycles**; in idle cycles, listed (an early head can in principle decode there; it is reported, not scored) |

**Outputs (exact definitions; no bar, this is a characterisation):**

- `r(d, s, L)` = matched / 32 per decoder `d`, SNR `s`, lateness `L`, with Wilson 95 % CIs.
- **Late edge `E50(d, s)`** = the largest grid `L` ≥ 0 such that `r ≥ 0.50` at that `L` **and at every smaller grid `L` ≥ 0**. `E90` is the same with 0.90. If `r ≥ 0.50` at `L` = 6.00, report "> 6.00". Non-monotone cells after the edge are listed, not smoothed.
- **Early edge `E50e(d, s)`** = the most negative grid `L` such that `r ≥ 0.50` at that `L` **and at every grid `L` between it and 0**. `E90e` likewise. If `r ≥ 0.50` at −3.00, report "< −3.00".
- **Q2 mapping (descriptive, labelled "on-air night, one CPU, 8 workers"):** per on-air cycle with ≥ 1 residual decode, `T2 = decode-start offset into the reply slot + batch-1 time + residual elapsedMs`, all from the daemon's existing per-cycle lines (QA names the fields and FILE:LINE; if the decode-start offset is not logged, say so and use the design value, labelled). For a TX keying latency `k` ∈ {0, 0.5, 1.0} s: the fraction of those cycles with `T2 + k − 0.5 ≤ E50(WSJT-X, s)` for each `s`. If a keying latency has ever been measured, cite it. Otherwise the three values stand.

## 5. What the result decides (for the Captain, after the report)

The options put to the Captain on 2026-10-02 for batch-2 → auto-QSO:
- ~~**(a) reply one slot later**~~ **WRONG, struck (Captain, 2026-10-02):** one slot later is the other station's own TX slot, so it would not hear us. **(a′) Reply in the next slot of OUR parity (N+3, ≈ 30 s late), full length.** This is protocol-correct: a CQ caller who got no answer calls again in N+2 and listens in N+3, and a QSO partner who did not hear us repeats in N+2 and listens in N+3. It needs no edge. It does need a guard: N+2's **pass-0** decodes (available ≈ 0.5 s into N+3) must show the station is still free. If it is now working someone else, do not transmit. N+2's batch 2 arrives too late to be part of that guard.
- **(b) reply immediately, cut at the slot end**: viable only if Q2's fraction under WSJT-X's `E50`/`E90` is material.
- **(c) act only when in time, with a grace of `E90`**: same input as (b).

QA reports the numbers. **The Architect then writes the batch-2 → auto-QSO spec on the Captain's choice.** Nothing in this spec changes QSO behaviour. The edges also fix the points of the #194 battery segment S3c (separate spec, `arch/194-rr-improvements`).

## 6. Limits to state

Synthetic AWGN signals through the playback chain, with no fading or drift, and a moderate, controlled crowding (16 signals per cycle, 150 Hz apart). One build of each decoder, and the installed WSJT-X version recorded. The other station's decoder is assumed to be WSJT-X; JTDX, MSHV and others are not measured. Two SNR levels only: an edge at another SNR is not interpolated beyond them.

## 7. Predictions (blind; scored at ruling time)

Amendment 2 moved the SNR each prediction refers to onto the new levels. No range or probability changed. LT5 is new. All were made before any data.

| # | Prediction | P | Class |
|---|---|---:|:---:|
| LT1 | `E50(WSJT-X, −8 dB)` ∈ [2.25, 3.00] s. My basis is a recollection that WSJT-X's sync search spans about ±2.5 s in DT, **not checked against its source** | 0.60 | H |
| LT2 | `E50(OpenWSFZ, −8 dB)` > `E50(WSJT-X, −8 dB)` (ours is more forgiving; recollection of ft8_lib's candidate search allowing a partly out-of-range Costas array, not checked) | 0.55 | H-mech |
| LT3 | Q2: with `k` = 0, fewer than 5 % of on-air batch-2 cycles land before `E50(WSJT-X, −16 dB)` | 0.75 | H |
| LT4 | P1–P6 all pass first time | 0.70 | H |
| LT5 | `E50e(WSJT-X, −8 dB)` ∈ [−2.50, −1.50] s (same unchecked recollection as LT1) | 0.50 | H |
