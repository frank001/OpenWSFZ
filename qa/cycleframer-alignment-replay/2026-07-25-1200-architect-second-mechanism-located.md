# The second mechanism is located: the loss is at LDPC, not at the window boundary

**Author:** Architect, 2026-07-25 (12:00). **Status:** answers 11.10 §4 item 2 and item 4.
**Sources:** `artefacts/20260724_live_run_2227/` daemon logs + `ALL.TXT` — the same session
11.10 analysed. **No new live run, no new decodes, no `src/` change.** Probes:
`_work/capture_loss_probe.py`, `_work/rms_vs_decodes.py`, `_work/ldpc_stats.py` (git-ignored
`_work/`; ASCII-only per HK-009; aggregate counts only, no callsigns — NFR-021).

---

## 0. Verdict

**The live-path loss is not a timing defect of any kind.** The capture path delivers complete,
continuous, correctly-levelled audio to the decoder on every cycle including the ones that decode
nothing. The decoder's sync stage finds the signals — its candidate list is *saturated at its
compile-time maximum* on 99.8 % of zero-decode cycles. Every one of those candidates then fails
LDPC.

`fix-cycle-boundary-clock-drift` cannot recover this loss, and the study's premise — that a
misaligned window is what costs D-001 its live-path half — is falsified a second time, now by a
mechanism-level route rather than a magnitude-level one.

## 1. What the daemon's own logs already contained

The 8.1 instrumentation was added to measure *timing* and was read for flatness. Three quantities
it (and the decoder) also logged were never differenced.

### 1.1 The capture path loses nothing (`capture_loss_probe.py`)

`CycleFramer` closes a window on accumulating 180 000 samples. The device delivers 12 000
samples/s of real time. So `lost = (real_elapsed − 15.000) × 12000 − discarded`, with `discarded`
known exactly from the 136 `Cycle boundary resync` lines.

| decile | med real elapsed | med chunks | med lost | p90 lost | max lost | windows losing >1 chunk |
|---|---|---|---|---|---|---|
| 1 | 14.994 s | 241 | −72 | 564 | 720 | 0 |
| 3 | 14.995 s | 242 | −60 | 564 | 720 | 0 |
| 4 | 14.996 s | 242 | −60 | 516 | 708 | 0 |
| 9 | 14.995 s | 242 | −60 | 564 | 720 | 0 |
| 10 | 14.996 s | 241 | −48 | 528 | 744 | 0 |

**0 of 2 836 windows lost even one 750-sample chunk.** Total residual 2.2 s over 11 h 51 m, at the
±one-chunk quantisation floor. Chunk counts flat at 241–242 all night, in the collapsed deciles
exactly as in the clean one. The `DropOldest` channels never dropped anything.

### 1.2 No window was dropped between framer and decoder

Log-line census over the session:

```
2682  [DBG] Window emitted (N samples, cycle ...)
2682  [DBG] Starting decode for cycle ...; pcm = N samples, RMS = ...
2682  [INF] Cycle ...: N decode(s) found, elapsed=N ms
```

Exactly equal. `framerOutput` (capacity 2, `DropOldest`) never overflowed; the decode pump kept up
(median decode 373–653 ms against a 15 000 ms budget). Zero `Decode error`, zero dial-frequency
discards. **Every framed window was decoded.** The 1 050 zero-decode cycles are cycles where the
decoder ran to completion and returned nothing.

### 1.3 The audio on those cycles is indistinguishable from the audio on good cycles

| | n | median PCM RMS | p10 | p90 |
|---|---|---|---|---|
| zero-decode cycles | 1 050 | 1.290e−02 | 1.141e−02 | 1.507e−02 |
| decoding cycles | 1 789 | 1.308e−02 | 1.144e−02 | 1.530e−02 |

**Ratio of medians 1.01.** Noise floor −64 … −69 dB in every decile, no trend. PCM length exactly
180 000 on every cycle. Not one cycle in either population fell below a quarter of the decoding
median. The window handed to the decoder is fine.

## 2. Where the loss actually is

`ldpc_stats.py`, from the decoder's own per-pass logging:

| decile | med candidates | med decodes | decoded/candidate | zero-dec | med failCands | med meanAbsLLR | med prenormVar |
|---|---|---|---|---|---|---|---|
| 1 | **140** | 22.0 | 0.15 | 1.1 % | 82 | 4.075 | 116.0 |
| 2 | **140** | 15.0 | 0.09 | 8.8 % | 93 | 4.015 | 104.3 |
| 3 | **140** | 0.0 | 0.00 | 55.1 % | 136 | 3.835 | 94.5 |
| 4 | **140** | 0.0 | 0.00 | 61.1 % | 136 | 3.839 | 91.6 |
| 5 | **140** | 5.0 | 0.07 | 24.7 % | 100 | 3.920 | 97.0 |
| 6 | **140** | 1.0 | 0.05 | 32.9 % | 122 | 3.910 | 95.9 |
| 7 | **140** | 1.0 | 0.05 | 38.5 % | 132 | 3.900 | 90.3 |
| 8 | **140** | 2.0 | 0.05 | 35.7 % | 106 | 3.944 | 99.6 |
| 9 | 136 | 0.0 | 0.03 | 51.2 % | 112 | 3.839 | 94.0 |
| 10 | 90 | 0.0 | 0.03 | 59.9 % | 81 | 3.822 | 87.3 |

140 is `K_MAX_CANDIDATES` (`src/OpenWSFZ.Ft8/Native/ft8_shim.c:467`) — pass 1's hard cap. The
candidate list is **saturated in eight of ten deciles**, including both collapsed ones.

- Candidates on zero-decode cycles: median **140**, p90 **140** (n=1 050).
- Candidates on decoding cycles: median **140**, p90 **140** (n=1 789).
- **99.8 % of zero-decode cycles found ≥10 candidates.**

The candidate yield is *identical* between cycles that decode 22 messages and cycles that decode
none. What changes is survival: `failCands` climbs 82 → 136 as decodes collapse, with `meanAbsLLR`
4.075 → 3.83 and `prenormVar` 116 → 91.

## 3. Why this rules out alignment, independently of 11.10

11.10 falsified alignment by *magnitude* — measured `δ_live` was too small to explain the loss.
This falsifies it by *signature*, which is the stronger argument because it does not depend on the
recall(δ) model at all:

> **Misalignment destroys candidates. It cannot destroy LDPC survival at constant candidate count.**

`decode.c:279` searches `time_offset` over `DT_obs ∈ [−1.60, +3.12] s`. A signal inside that range
is found by sync *at its shifted offset*, and the LLR extraction then uses that same offset — so it
decodes normally (this is exactly why the measured recall plateau is flat at 0.92–0.99 out to
±2 s). A signal outside the range is not found at all: the candidate is **absent**, not failed.

So alignment error can only ever show up as **fewer candidates**. The observed signature is
**candidate list pegged at its ceiling, and the LDPC survival rate collapsing** — an orthogonal
failure mode. Whatever is happening in deciles 3, 4, 6 and 9, the window boundary is not it.

This also explains *why* 11.10 measured small `δ_live` in the collapsed deciles and found it
inconsistent with the recall it saw: the alignment genuinely was fine. The model was right; the
hypothesis it was being applied to was wrong.

## 4. The correction loop cannot recover the loss — and it is destroying audio

Attributing each of the 136 corrections to the window that consumes its discard:

| | cycles | zero-decode | rate |
|---|---|---|---|
| following a correction | 136 | 45 | **33.1 %** |
| not following a correction | 2 703 | 1 005 | **37.2 %** |

**95.7 % of zero-decode cycles have no correction anywhere near them**, and the cycles a correction
*does* damage are not measurably worse than the ones it doesn't. The upper bound on what a perfectly
converging `CycleFramer` could recover from this session's zero-decode population is **4.3 %**, and
the true figure is lower still — the two rates are statistically indistinguishable.

Separately, and worth recording because it is a real defect regardless of the above:

- 132 of 136 corrections were **discards**; 4 were replays. The loop threw away **67.1 s of real
  received audio** over the session.
- Meanwhile the measured capture rate is **~12 004 samples/s (+333 ppm, device running *fast*)** —
  windows fill 180 000 samples in 14.995 s, consistently, all night. A fast device warrants
  *replays*. The loop applied discards essentially every time.
- The constants in `CycleFramer` are derived from a measured **−42.41 ppm** — wrong magnitude
  (8×) and wrong sign against this session's own capture. At −42.41 ppm the session's genuine
  drift is ~1.8 s; the loop applied 66.8 s net.

None of this is why D-001 loses decodes. It is why the correction loop has never converged across
five rounds: it is not tracking a quantity that behaves the way its model assumes.

## 5. What is still open

**What degrades LLR quality in the live path but not in offline replay of the same RF** is not
settled here, and I am not going to guess it — §15.1's standing lesson in `SPEC.md` is that this
study's assumed physics has been wrong more often than its measurements have.

What is now bounded: it is downstream of window framing, upstream of LDPC, and it is *not* audio
level, continuity, length, or noise floor. The live and offline paths differ in exactly one place —
the capture chain (`WasapiAudioSource`: 48 kHz/32-bit/stereo → left channel →
`WdlResamplingSampleProvider` → 12 kHz) versus reading WSJT-X's already-decimated 12 kHz WAVs.

The decisive experiment is small and mostly offline:

1. Have the daemon write its own framed 180 000-sample windows to WAV for ~20 minutes of live
   capture, alongside WSJT-X recording the same audio (as it already does).
2. Decode both sets with the same `Ft8Decoder` at the same settings.
3. If OpenWSFZ's own capture yields materially fewer decodes than WSJT-X's capture of the same
   cycles, the defect is in the capture chain and the spectra will show which stage.
   If the two match, the defect is in the *live decoder invocation* (process-lifetime native state
   — `g_session_hash_table`, `hashTableRejectCount` reached 25 465) and the next probe is a
   restart-cadence test.

This costs ~20 minutes of radio time and one short offline decode run — versus the multi-night
endurance rounds the current thread has been spending.

## 6. Consequences for `tasks.md`

1. **10.8's live acceptance run should not be scheduled.** It would certify convergence of a loop
   that, per §4, is worth ≤4.3 % of the zero-decode population. 11.10 already qualified this; §4
   puts a number on it from the outcome side.
2. **10.1–10.4 are not wrong, they are small.** Decision 9's fix is sound as far as it goes and the
   uncommitted `src/` diff should not be discarded — but it should be re-scoped as correctness
   hygiene, not as a D-001 recovery.
3. **The `−42.41 ppm` constant derivation in `CycleFramer` is contradicted by this session's own
   capture (+333 ppm).** Whatever shape the loop finally takes, it should not be re-tuned against
   that figure again.
4. **Deliverable #2's recall(δ) curve remains valid and valuable** — it is a correct measurement of
   a real effect. It simply turns out to measure an effect that is not the dominant one. Phases
   0/0b/1a/1b were not wasted: they are what made it possible to *falsify* the alignment hypothesis
   rather than keep assuming it.
