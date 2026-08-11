# Defect: Decode Panel Updates in One Lump; Operator-Perceived Latency Unexplained

**Raised by:** Architect, 2026-08-11 (18:17 UTC, `date -u`, per HK-017), on the Product Owner's
direction.
**Severity:** Moderate, **product-facing usability**. The Product Owner reports the decode panel's
update behaviour is affecting operating.
**Status:** 🔴 **REAL AND OPERATIONALLY BINDING.** Not a perception problem — the Product Owner
confirmed 2026-08-11 that it is **the wait itself**, because the decode must be actionable in time
to engage a QSO. §3a re-scores the measured latency against that deadline and **partially reverses
the §3 verdict below.** Read §3a before acting on §3.
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
| n (cycles) | **84 432** |
| min | 8 ms |
| p50 | **518 ms** |
| p90 | 615 ms |
| p95 | 637 ms |
| p99 | **685 ms** |
| p99.9 | 736 ms |
| max | **1 367 ms** |
| cycles > 1 s | 8 (**0.01%**) |
| cycles > 2 s | **0** |

⚠️ **A 6.5 s outlier scare was chased down and dismissed** — `grep` over all of `artefacts/`
initially surfaced decodes of 6 202–6 515 ms. Every one traces to
`c4_min_score/k*_cap2000/.../decode.log`: the **candidate-budget sweep at cap 2000**, an offline
replay diagnostic that never shipped (production is 140/200, and that family is closed twice).
Live daemon logs only — the 61 `openswfz-*.log` files — give the table above. The distinction
matters: pooling replay harnesses with live operation would have inflated the headline ~10×.

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

⚠️ Caveats on the numbers, stated so they are not over-read: the 84 432 cycles pool many live runs
across months and bands and are not a controlled sample; `elapsed` is the managed-side stopwatch,
covering PCM normalisation plus the native call, **not** WebSocket delivery or render.

## 3a. Re-scored against the operating deadline — this PARTIALLY REVERSES §3

**Product Owner, 2026-08-11: it is the wait, not the absence of feedback.** The operator needs the
decode in hand early enough to engage a QSO. That supplies the deadline §3 was missing, and §3's
dismissal of a ~250 ms saving was made against an implicit "seconds matter" scale that is **wrong
for this application**. Corrected here.

**The deadline is physics, and it is already in our own code.** An FT8 transmission occupies
**12.64 s of the 15 s slot**, leaving a **~2.36 s guard interval** (`CycleFramer.cs:304`,
`main.js:1018-1023`). To answer a station heard in cycle N, the operator's own transmission must
begin within that guard, i.e. by **t = 17.36 s** where cycle N started at t = 0.

| event | time | source |
|---|---:|---|
| cycle N audio window closes | 15.000 s | 180 000 samples @ 12 kHz |
| decode begins | ~15.042 s | measured framing overhead, 42 ms |
| **decodes in hand (p50)** | **~15.560 s** | p50 518 ms |
| decodes in hand (p99) | ~15.727 s | p99 685 ms |
| decodes in hand (worst observed) | ~16.409 s | max 1 367 ms |
| 🔴 **TX must have started** | **17.360 s** | 15 + 2.36 guard |

**The operator's entire window to read, decide, and act is ~1.80 s at p50** — and 0.95 s in the
worst observed cycle. Into that must fit: visual scan of a panel that just repainted wholesale, the
decision itself, targeting and clicking the row, and the daemon's own PTT/keying startup.

🔴 **Re-scored, the machine is consuming ~24% of the actionable window at p50 and up to ~60% at the
observed worst case.** That is not the "negligible quarter-second" §3 called it. The decoder is
still not *slow* in absolute terms — 518 ms to demodulate a 15 s buffer is respectable — but it is
spending a quarter of a hard budget, and **against a 2.36 s deadline a 250 ms saving is ~14% of the
operator's remaining time, which is material.**

**What §3 still establishes, and it stands:** the latency is not a bug, a stall, a queue, or a
timer anyone forgot. Every component measured is behaving as designed. This is a **budget** problem
— the sum of honest costs against a deadline nobody wrote down — and it will not be fixed by
finding a culprit, because there isn't one.

**Three terms make up the budget. Only one is measured.**

| term | value | status |
|---|---|---|
| decode + framing | ~0.56 s (p50) | ✅ measured, n = 84 432 |
| delivery + render | unknown | ❌ never measured; bounded-small by inspection (§2), not by data |
| human scan → decision → click → PTT up | unknown | ❌ never measured; **plausibly the largest term** |

🔴 **The largest term is probably the human one, and it is the only one nobody has proposed
touching.** Shrinking it — a keyboard-driven engage, CQ and workable stations sorted or highlighted
to the top, a pre-targeted default — costs no native work, carries **no recall risk**, and is the
one lever on this list that cannot make D-001 worse. That is an architectural recommendation, not a
measurement, and it is offered as such.

## 4. What is therefore still open

The server hands off finished decodes ~0.66 s after the cycle closes, and nothing between the
decoder and the browser's render call is measurably slow. **The operator-perceived latency is
consequently unexplained, and no measurement of it exists.** Candidate loci, none of them measured
and listed in no particular order:

1. **WebSocket delivery and client render time** — never instrumented end-to-end. Row insertion
   cost at 20–27 decodes/cycle against a growing table is plausible but unquantified.
2. ~~**Lump versus trickle is a perceptual difference.**~~ 🛑 **ANSWERED AND CLOSED 2026-08-11 —
   the Product Owner confirms it is the wait, not the feedback.** A progress affordance alone does
   **not** address this defect. Do not propose one as the fix.
3. **The comparison baseline may not be like-for-like.** WSJT-X's own decode is slower than ours in
   absolute terms; what it has is progressive paint. Still worth confirming, but §3a means the
   deadline — not the comparison — is what governs.
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

## 6. The candidate levers, and what each one costs

🔴 **None of these is authorised by this document.** Listed so the Product Owner can choose, with
the honest price of each. Ordered by risk, cheapest and safest first.

**C — shrink the human term.** Keyboard-driven engage, CQ/workable stations sorted or highlighted
to the top, a pre-targeted default row. Web UI only: no native work, no rebuilt DLL, **no recall
risk, no D-001 interaction**. Attacks what is plausibly the largest term in the §3a budget.
✅ **My recommendation for first move**, on value-per-risk.

**D — measure the delivery + render leg.** Client-side `performance.now()` at WebSocket
`onmessage` and after render, carrying the cycle timestamp already in the payload. Cheap, no
capture run, and it closes the one unmeasured machine term. Do this alongside C.

**B — emit pass-0 decodes as soon as pass 0 finishes.** Buys an unknown share of the ~518 ms.
🔴 **Measure the per-pass split before costing this** — pass 1 searches a wider candidate net
(200 vs 140) so it may well be the larger half, and if so B is worth materially more than the
~250 ms §3 assumed. The measurement is cheap (a per-pass stopwatch in the shim); the *change* is a
native API addition ⇒ rebuilt `libft8.dll`, new `FT8_SHIM_VERSION` (first free integer is 20260038,
and G2 has claimed it — check before assigning), Developer session under HK-011.

**A — decode before the cycle closes.** The largest lever by far: the signal occupies 12.64 s of
the 15 s window, so in principle the buffer could be handed to the decoder ~1–2 s early and
decodes could land **before** the cycle boundary, handing the operator the full guard interval plus
margin. 🛑 **But the guard is exactly what absorbs DT spread and capture-clock drift, and this
project has no zero-drift capture chain on any corpus.** Cutting into it trades directly against
recall for late-DT stations — i.e. **against D-001, the programme's central open problem.**
🔴 **This earns its own pre-registration with recall as a primary metric, not a side observation.**
Do not prototype it first and measure after.

## 6a. Explicitly still not proposed

- **A progress affordance as *the* fix** — §4.2, closed by the Product Owner.
- **Any change to `suppress_candidate_tiles` or the pass count** for latency reasons. Three passes
  was swept and reverted (−4.30 pp); it is not a latency lever.
- **Any `src/` edit from this session.** Architect writes for QA (HK-015); QA characterises and
  authors the dev-task; the Captain signs off (HK-011).

## 7. Adjacent observation, recorded but NOT part of this defect

`suppress_candidate_tiles` is fed **our own reported SNR** (`ft8_shim.c:1413`, passed at `:1430`)
against **absolute** dB thresholds (−5 / +15). Our reported SNR carries a measured *gain* error —
`ours ≈ 0.6865 × reference − 4.742 dB`, n = 41 668 matched decodes
(`DEFECT-snr-reported-gain-error.md`). Mechanically, a signal the reference calls +15 dB we call
≈ +5.6 dB, landing it mid-ramp where the design intended full suppression.

🔴 **This is an inference from two separately verified facts, not a measurement**, it concerns
recall rather than latency, and it must not be actioned off this document. If pursued it earns its
own pre-registration.
