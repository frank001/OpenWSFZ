# Defect: Decode Panel Updates in One Lump; Operator-Perceived Latency Unexplained

**Raised by:** Architect, 2026-08-11 (18:17 UTC, `date -u`, per HK-017), on the Product Owner's
direction.
**Severity:** Moderate, **product-facing usability**. The Product Owner reports the decode panel's
update behaviour is affecting operating.
**Status:** 🔴 **LOCUS NOT ESTABLISHED.** The obvious suspect has been measured and **ruled out**.
This document exists to stop a fix being built against the wrong cause.
**No fix proposed here.** Per HK-011/HK-015 the correction routes through QA characterisation and
then a Developer session; the `dev-tasks/*.md` is QA's to author, not this document.

---

## 1. The operator report

WSJT-X paints decodes to its GUI as soon as its first decoding pass completes, then repaints when
subsequent passes finish — the operator sees the band populate progressively, within the cycle.
OpenWSFZ does not do this at all: the decode panel stays empty and then fills in a single lump.
The Product Owner reports this as a usability problem, not a cosmetic one — during a QSO the
operator is waiting on the panel to decide the next action, and a panel that is empty until it
isn't gives no signal that anything is happening.

## 2. What the code actually does — verified 2026-08-11 against `main`

**The two passes are invisible from outside the decoder.** Both live inside a single native call,
`ft8_decode_all()`. The pass loop is `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1293`; the managed layer
(`Ft8Decoder.cs:280`) hands over PCM, blocks on `Task.Run`, and receives one finished array once
**both** passes have completed. There is no per-pass callback and no partial-results path. The
per-pass decode counts exist in the shim (`tls_pass_counts[]`, exposed via
`ft8_get_last_pass_counts`) but are diagnostic only — they never reach the UI in time to matter.

**Pass 1 does not see the same data as pass 0.** For every message decoded in pass 0, the shim
re-encodes it to its 79 tones and attenuates the waterfall tiles it occupied — the transmitted bin
plus ±1 neighbour — toward the noise floor (`suppress_candidate_tiles`, `ft8_shim.c:675-723`,
invoked at `:1302-1304`). Attenuation is soft and scaled by the decoded SNR: untouched at
≤ −5 dB, fully flattened at ≥ +15 dB, linear between. Pass 1 also widens the candidate net
(140 → 200) at an unchanged sync-score floor and LDPC iteration count.

**Publication is immediate and non-blocking.** `Program.cs:796` publishes to the decode event bus
fire-and-forget (`_ = decodeEventBus.Publish(...)`); the daemon does not wait on WebSocket
delivery. `DecodeEventBus` holds no timer, batch, or throttle. The one step between decode and
publish — `DecodeNoiseSuppressionFilter.Apply` with the region store — is an in-memory
longest-prefix match over a collection loaded once at startup (`CallsignRegionStore.cs:66`); it
performs no per-decode I/O. The browser client renders synchronously on message arrival
(`web/js/main.js:1820-1822`); no `setInterval`, debounce, or animation gate sits on that path.

## 3. What is measured — and it rules the obvious cause out

Decode wall-clock, from the existing per-cycle log line
(`Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms`, `Ft8Decoder.cs:426-428`),
across every daemon log in `logs/openswfz-*.log`:

| metric | value |
|---|---:|
| n (cycles) | **3 972** |
| min | 9 ms |
| p50 | **463 ms** |
| p90 | 581 ms |
| p99 | 642 ms |
| max | **934 ms** |

End-to-end on the server, worked from adjacent log timestamps (2026-08-07 run, representative):

```
cycle 19:27:00 window closes ....... 21:27:15.000 (+02:00 local)
"Starting decode for cycle" ........ 21:27:15.042    →  42 ms framing overhead
"22 decode(s) found, elapsed=582ms"  21:27:15.664    → 664 ms to results in hand
```

🔴 **The decoder is not the bottleneck. Results exist ~0.66 s after the cycle boundary.**

**Consequence, and it is the reason this document is worth reading:** the two-pass structure can
account for **at most ~250 ms** of the operator's wait. A per-pass GUI update — the fix the
symptom most obviously suggests, and the one I was on the point of speccing — would buy roughly a
quarter of a second and would cost a native API change, a rebuilt `libft8.dll`, and a Developer
session under HK-011. **It is the wrong lever and it should not be built.**

⚠️ Caveats on the numbers, stated so they are not over-read: the 3 972 cycles pool several runs
across 2026-08-03 → 2026-08-07 on mixed bands and are not a controlled sample; `elapsed` is the
managed-side stopwatch, covering PCM normalisation plus the native call, not WebSocket delivery or
render; and all of it was captured with debug logging enabled.

## 4. What is therefore still open

The server hands off finished decodes ~0.66 s after the cycle closes, and nothing between the
decoder and the browser's render call is measurably slow. **The operator-perceived latency is
consequently unexplained, and no measurement of it exists.** Candidate loci, none of them measured
and listed in no particular order:

1. **WebSocket delivery and client render time** — never instrumented end-to-end. Row insertion
   cost at 20–27 decodes/cycle against a growing table is plausible but unquantified.
2. **Lump versus trickle is a perceptual difference, not only a latency one.** A panel that fills
   in one frame at 0.7 s may *feel* slower than one that starts filling at 1.5 s and finishes at
   4 s, because the second gives continuous feedback. If this is the real complaint then the fix is
   a progress affordance, not speed — and that is a cheap change, not a native one.
3. **The comparison baseline may not be like-for-like.** WSJT-X's own decode is slower than ours in
   absolute terms; what it has is progressive paint. Worth confirming against the operator's
   actual side-by-side before anything is built.
4. **Something after the render call** — browser paint, layout thrash, or filter re-evaluation
   (`reapplyDecodeFilterToRenderedRows`) — unexamined.

## 5. The measurement that would close this

No new capture run is required and none should be proposed (`qa/ARTEFACT_INVENTORY.md` first,
per the standing rule). The instrumentation is client-side and small: stamp `performance.now()` at
WebSocket `onmessage` and again after the decode-panel render completes, carry the cycle-start
timestamp already present in the payload, and log the three deltas for a few hundred cycles. That
yields cycle-close → delivery → painted, which is the number nobody has.

🔴 **Pre-commit the threshold before looking** (HK-021). "What latency, painted-to-screen, counts
as acceptable to the operator?" is a Product Owner question and should be answered as a number
*before* the measurement is taken, or the result will be read to fit whatever it turns out to be.
Note also that my own directional predictions are the weakest class in my calibration record — do
not let a gate here turn on one.

## 6. Explicitly not proposed

- **A native per-pass callback / early-results flush.** Ruled out by §3 on measured evidence.
- **Any change to the two-pass structure or to `suppress_candidate_tiles`.** Unrelated to this
  defect; the pass count in particular has been swept and reverted before (three passes: −4.30 pp).
- **Any `src/` edit at all from this session.** Architect writes for QA (HK-015); QA characterises
  and authors the dev-task; the Captain signs off (HK-011).

## 7. Adjacent observation, recorded but NOT part of this defect

`suppress_candidate_tiles` is fed **our own reported SNR** (`ft8_shim.c:1413`, passed at `:1430`)
against **absolute** dB thresholds (−5 / +15). Our reported SNR carries a measured *gain* error —
`ours ≈ 0.6865 × reference − 4.742 dB`, n = 41 668 matched decodes
(`DEFECT-snr-reported-gain-error.md`). Mechanically, a signal the reference calls +15 dB we call
≈ +5.6 dB, landing it mid-ramp where the design intended full suppression.

🔴 **This is an inference from two separately verified facts, not a measurement**, it concerns
recall rather than latency, and it must not be actioned off this document. If pursued it earns its
own pre-registration.
