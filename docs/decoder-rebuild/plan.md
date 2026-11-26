# Decoder rebuild: plan (DRAFT for the Product Owner)

**Status:** APPROVED by the Product Owner, 2026-11-24 ("1-5 ok, write the specs for qa"). All five §9 proposals were accepted as written. Specs: [`spec-dr0-dr1-measure-and-relief.md`](spec-dr0-dr1-measure-and-relief.md) and [`spec-dr2-lean-decoder.md`](spec-dr2-lean-decoder.md).
**Author:** Architect (AI-assisted), 2026-11-24T17:00Z
**Requested by the Product Owner, 2026-11-24:** *"I want to rebuild the decoder and decoding phases from scratch using all the knowledge that we have gathered up to now. It needs to be leaner, decoding phases combined where possible. It has now become a CPU-heavy application and it should not be."*

---

## 1. Goal, in one paragraph

Replace today's stack of six separately bolted-on decode passes with **one decoder built on purpose**:
- one spectrogram per cycle
- one candidate list
- one demodulator that tries harder only on the candidates that deserve it
- one subtract-and-retry loop

It should keep **roughly today's decode count** while using **a fraction of today's CPU**, with far less code and far fewer settings. Decode gains are not the goal of this work. If it comes out a little ahead, good; if it comes out a little behind, the Product Owner decides whether the CPU saving is worth it (§9, question 2).

## 2. What the decoder does today (`main`, v1.0)

On **Deep** depth, each 15-second cycle runs these steps in sequence:

| Batch | Step | What it does | Setting / FR |
|---|---|---|---|
| (early) | Early decode | The primary decode run a second time on the first 13 s of audio, so rows show ≈ 2 s sooner | `earlyDecodeEnabled`, FR-083 |
| 1 | Primary | ft8_lib: candidate search on a coarse 3.125 Hz / 0.08 s grid, magnitude-only bit metrics, LDPC + OSD, CQ a-priori on failures | FR-001, FR-103 |
| 2 | Residual pass | Fit and subtract every batch-1 signal, then decode the residual audio again from scratch | FR-082, FR-077 |
| 3 | Third pass | Subtract again, decode again (Deep only) | Deep |
| 4 | Coherent fallback | Fine sync plus coherent bit metrics on failed candidates; runs on the original **and** the residual audio, three runs in total | FR-099–101, FR-104 |
| 5 | Late round | Subtract the batch 3 and 4 decodes, decode once more | FR-102 |
| 6 | Cross-cycle prior (XC) | Test the messages heard 30, 60 and 90 s ago as known templates | FR-105 |

On top of that sit `LR-BUILD` (two further late-round variants, not merged) and the code behind it: about **13,000 lines** across `Ft8Decoder.cs` (2,300), the interop layer (2,200), the native shim (4,700), the subtraction and fallback C (2,800) and the XC stage (800). There are about **15 decoder settings**, each with its own log line and its own tests.

### What each step costs and returns

The numbers below come from **one live night only** (`20261114_2312`, 40 m, build `66b3ddf1`, 2,834 cycles, station Ryzen 7 7800X3D), as recorded in the 2026-11-16 compute evaluation:

| Step | Wall time per cycle (median) | Decodes it added that night | Decodes per second of work |
|---|---:|---:|---:|
| Primary | 632 ms | 52,310 | 29.3 |
| XC | 50 ms | 3,850 | 27.4 |
| Coherent fallback | 623 ms | 11,656 | 6.4 |
| Residual pass | 1,528 ms | 9,972 | 2.4 |
| **Third pass** | **≈ 1,900 ms** | **2,323** | **0.42** |
| **Late round** | **996 ms** | **1,368** | **0.49** |

- **Wall time understates the load.** The residual pass and the fallback run on many threads at once, so CPU time is several times higher than these figures. This is why the PC feels busy.
- **"Decodes added" is not the same as what each step is worth.** If an earlier step were switched off, a later step would pick up part of its work. The real value of each step has never been measured on one night with one build. §5 Phase 0 does that.
- **The pattern is still clear.** The primary and XC are cheap and productive. The third pass and the late round spend ≈ 3 s of the ≈ 4.8 s for under 5 % of the decodes. The early decode runs the primary a second time just to show rows sooner.

## 3. What we know (the knowledge this plan is built on)

| # | Finding | Consequence for the rebuild |
|---|---|---|
| K1 | **The primary decoder is coarse.** It uses a 3.125 Hz / 0.08 s grid, has no fine sync, and uses magnitude-only, single-symbol bit metrics (ft8_lib's design). Shifting the audio by a third of a grid step recovered decodes in P3, which shows that placement costs real decodes. | The demodulator must refine sync per candidate before it decodes. Today only the fallback does that (±2 Hz in 0.1 Hz steps, ±0.12 s in 5 ms steps), as a separate pass. |
| K2 | **Simply adding more search points creates false decodes.** P3's union of shifted runs gained decodes, but 90 % of the gained rows were not in WSJT-X. | Refine inside the decoder, per candidate. Never take the union of several runs. |
| K3 | **Most of the remaining gap is overlapping signals.** Of the 11.8 pp gap to WSJT-X on `20261114_2312`, ≈ 8.4 pp is co-channel and ≈ 2.0 pp is isolated signals at about −18 dB and weaker. | Subtraction is the lever that matters, and its wins sit near the signals already subtracted. A full re-decode of the whole band after every subtraction wastes most of its work. |
| K4 | **The data-aided subtraction fit works.** SUB-FEAS: NET +8.89 pp. | Keep the fit (`subfeas_fit.c`, our own code). Reuse it, don't rewrite it. |
| K5 | **OSD adds nothing at today's settings.** OSD at `nhard` 24 vs OSD off gave identical text on `20261110` (NET 0.0). In the fallback it added 7 rows on a whole night. | Drop OSD from the hot path. Confirm on the Phase 0 replay. |
| K6 | **Some settings are proven non-levers.** Input scaling, window shape (Hann stays), a finer grid (OSR) without a false-decode check, candidate caps or counts, and more OSD all gained nothing. | None of them come back as settings. |
| K7 | **XC (repeat priors) is cheap and pays.** 50 ms per cycle; +2.8 pp on 40 m and +3.4 pp on 20 m (one night each). | Keep it, as the last step of the loop. |
| K8 | **The late-pass yield is limited by the accept gate, not the demodulator.** LATE-SUB's full round found ≈ +2.9 pp, but its false-decode cost was too high. No instrument yet judges buried decodes well. | One loop with one accept rule. Do not chase late-pass yield in this work. |
| K9 | **The hash table works as it is.** Fill-and-freeze; eviction loses decodes (EVICT, F-001 D3). | Carry it over unchanged. |
| K10 | **Native subtraction crashed before** (two `0xC0000005` in 2026-09). | Write the new native loop with bounds checks, sanitiser builds and a fuzz test (§7). |
| K11 | **A ground-up rewrite of the primary demodulator alone does not close the gap.** The coherent extractor, forced to WSJT-X's exact position, still missed 13.1 pp in NR. | The rebuild is about **cost and structure**, not about out-decoding WSJT-X. Do not sell it as a rate gain. |
| K12 | **Licences.** Permissive only. WSJT-X may be read for method; not one line of it may be copied or ported. | ft8_lib (MIT), KISS FFT (BSD-3) and our own C remain the building blocks. |

## 4. The proposed design

### 4.1 One pipeline, four stages

```
 15 s of audio
   │
   ▼
 S1  Spectrogram, computed ONCE              (shared by every stage below)
   │
   ▼
 S2  Candidates → fine sync → demodulate      ── one pass over the band
       tier A: magnitude metrics  (cheap; most signals decode here)
       tier B: coherent metrics   (only candidates whose sync score says "close")
       + CQ a-priori on tier-B failures
   │      ── publish batch 1 ──
   ▼
 S3  Subtract-and-retry LOOP                  (replaces residual, third, fallback-residual, late round)
       subtract everything decoded so far (data-aided fit, K4)
       re-run S2 ONLY in the time–frequency patches where something was subtracted
       repeat while the last round found something new AND budget remains (max 3 rounds)
   │      ── publish batch 2 ──
   ▼
 S4  Cross-cycle priors (XC), as today        ── publish batch 3
```

### 4.2 What each change buys

| Change | Replaces | Why it saves CPU |
|---|---|---|
| One spectrogram per round, and one decode path | 5–6 separate passes, each re-running the whole decode from raw audio | Recomputing the spectrogram is cheap (a few ms). The cost was always the repeated full-band candidate decoding, which the patch search removes. *(Corrected while writing the specs: the draft said "updated locally".)* |
| Tiered demodulation inside one pass | The primary pass **and** the separate coherent-fallback pass, with its three runs over two audios | The expensive coherent metrics run only on candidates that are close. There is no second sweep of the band. |
| Local re-search after subtraction | The residual pass, the third pass, the fallback's residual runs and the late round (four full-band passes) | K3: the new decodes are near what was subtracted. The rest of the band was already searched. |
| No OSD in the hot path (subject to Phase 0) | OSD on every failed candidate | K5. |
| A fixed worker count (default 2 threads) | Pools sized to the machine (up to 16 threads) | The application stops taking the whole PC. Speed comes from doing less work, not from more cores. |
| One native entry point per cycle (`ftz_decode_cycle`) | Dozens of P/Invoke calls, state snapshots and restores, and per-pass hash-state images | Less copying, a much smaller interop layer, and one owner of the hash table. |
| Early decode removed **or** made nearly free (§9, question 4) | A full second primary run every cycle | If batch 1 comes out ≈ 0.5 s after the cycle ends, the early decode no longer has a purpose. |

### 4.3 What stays the same

- What the operator sees and what goes out:
  - decode rows
  - `ALL.TXT`
  - the UDP feed to GridTracker and WSJT-X
  - PSK Reporter uploads
  - the plausibility filter (`IsPlausibleMessage`)
  - auto-answer and auto-call
- Batch publishing to the panel, with 3 batches instead of 6.
- The hash table and its 12- and 22-bit rules (K9).
- XC and CQ-AP behaviour.
- The 13 s cycle budget. The new decoder is expected to use only a small part of it.

### 4.4 Settings after the rebuild

**Kept:** `decodingEnabled`, AP constraints, `cqApEnabled`, `crossCyclePrior` (and its threshold), and a single `decoder.effort` with the values `fast` and `normal`. `fast` skips tier B and runs one loop round; it exists for a slow machine.

**Retired** (accepted and ignored when present, with a one-time log line):
- depth Normal/Deep
- `subtractionEnabled`, `subtractionMaxThreads`
- the five coherent-fallback keys
- `lateSubtractionRound`
- `osdNhardMax`, `osdCorrThreshold`
- `crossCyclePriorShadow`

**Correction (Architect, 2026-11-26):** `kMinScorePass2` is **not** retired. The lean decoder uses it as the minimum candidate score of the search on the residual audio (`native/ftz_decoder/ftz_decoder.c:679` at `9027616e`; station value 5, code default 10). It stays a setting until a measurement shows it can go.
- `earlyDecode*`, if question 4 says so

### 4.5 Where the code lives

- **Native C** (`native/ftz_decoder/`, new): S1–S3 in a single library call. It builds on ft8_lib's LDPC, CRC, message and constants code (MIT) and on our own `coherent_llr.c`, `sync_refiner.c` and `subfeas_fit.c`. It is new orchestration over pieces that are already proven.
- **C#** (`OpenWSFZ.Ft8`): calls the library once per cycle, maps the results to rows, runs S4 (XC is C# today and stays there), and handles publishing.
- **The old decoder stays in place** behind `decoder.engine = classic | lean` until the Product Owner switches the default (Phase 3). It is deleted in Phase 4.

## 5. Phases

Each phase ends with a short result note to the Product Owner and his go for the next one. No phase needs a pre-registered statistical arm. The checks are listed in §6.

### Phase 0: measure what we have (QA, ≈ 1 day, no code change)
**Goal:** one honest table of what each step costs in CPU and what it is really worth.

- **Instrument:** add process CPU-seconds per step to the per-cycle log line. This is the only code touch: a few lines, Developer, reviewed.
- **One replay of a recorded night, 1 hour (240 cycles), settings only, cumulative:**

  | Arm | Steps on |
  |---|---|
  | 1 | primary |
  | 2 | + residual pass |
  | 3 | + fallback |
  | 4 | + third pass |
  | 5 | + late round |
  | 6 | + XC |
  | 7 | 6, OSD off |
  | 8 | 6, early decode off |

  Each arm is scored against the WSJT-X decodes for the same audio.
- **Output:** for each step, CPU-seconds per cycle and NET decodes, from one night and one build. It sets the baseline the lean decoder is measured against.
- **Success:** the table exists, all arms together take under 2 hours of PC time, and the Product Owner has set the targets in §9.

### Phase 1: quick relief on today's code — ❌ SKIPPED 2026-11-24

DR-0 measured ≈ 0 CPU relief from settings. The Product Owner: no shipping for a long time; continue with the lean decoder. The text below is kept as the record.
**Goal:** cut CPU now, while the rebuild is under way.

- Switch off by default whichever steps Phase 0 shows to be poor value. The likely candidates are the third pass, the late round and OSD; Phase 0 confirms or rejects each.
- Cap the worker threads at 2.
- **Success:** CPU-seconds per cycle fall by the Phase 0 measured amount, and the decode loss is within the §9 budget. The Product Owner merges it when he chooses.
- **This is a defaults change, not code. It can ship as a minor version (v1.1).**

### Phase 2: build the lean decoder (Developer; the main work)
In steps, each one reviewed by QA before the next starts:

| Step | Deliverable | Check |
|---|---|---|
| 2a | `ftz_decode_cycle` with S1 + S2 tier A only, behind `engine = lean` | Unit tests, fuzz test |
| 2b | Tier B (coherent) on near-miss candidates, plus CQ-AP | Unit tests |
| 2c | S3 loop with local re-search | Unit tests |
| 2d | S4 (XC) wired to the new results; 3-batch publishing | Unit tests + one 1-hour replay: CPU and decodes vs today |

### Phase 3: switch over
- The Product Owner flips the default when he is happy with it. There is no test step and no waiting period *(revised 2026-11-24 at his direction)*. The version goes up one minor.

### Phase 4: delete the old decoder (≈ 1–2 days)
- Remove the classic passes, their settings, log lines, tests, interop and native code; `LR-BUILD` is not merged.
- Update `REQUIREMENTS.md`: retire FR-082, FR-099–102 and FR-104, and rewrite FR-083 and FR-105 in terms of the new stages.
- Archive the related OpenSpec changes.
- **Success:** the decoder plus interop is under **half today's line count**, with ≈ 5 decoder settings instead of ≈ 15.

## 6. How changes are checked: the light process this plan assumes

These follow the viability review (2026-11-23), option A, which this request effectively chooses.

1. **Every `src/`/`native/` commit:** unit tests pass, plus QA's code review before merge (HK-039 stays).
2. **A decoder behaviour change:** **one** replay of a fixed 1-hour slice against the current baseline, reporting decodes matched to WSJT-X, extra decodes, and CPU-seconds per cycle. No confidence intervals, no pre-registration, no amendments.
3. **The Product Owner decides a default change**, when he chooses. No required on-air period.
4. **A fixed test set:** one recorded 40 m hour, named once in Phase 0 and used for every comparison.
5. **Statistical arms happen only if the Product Owner asks for one.**

## 7. Risks

| Risk | Likelihood | Effect | Mitigation |
|---|---|---|---|
| Lean decodes noticeably fewer than today | Medium | Medium | The classic decoder stays switchable until Phase 3 passes. The §9 decode budget is agreed up front. |
| Local re-search misses decodes a full-band residual pass found | Medium | Low–medium | Step 2c measures it directly. If needed, widen the patches or add one full-band re-search on the last round. |
| A native memory bug (the 2026-09 crash history) | Medium | High (daemon crash on air) | Bounds checks, AddressSanitizer build in CI, fuzz test on random and clipped audio, and a C# guard that catches the error and drops the cycle instead of crashing. |
| Scope creep back into rate-chasing | High (history) | High | §1: rate is not the goal. New decode ideas wait until Phase 4 is done. |
| Licence contamination | Low | High | K12: WSJT-X read for method only; the review checks provenance comments. |
| Phase 0's one night is unrepresentative | Low | Low | The Product Owner's own use shows it. |

## 8. What this plan does not do

- It does not try to close the co-channel gap further, or reopen any closed arm (K6, K8).
- It does not change TX, CAT, the UI, the UDP feed or PSK Reporter.
- It does not port anything from WSJT-X.

## 9. Questions for the Product Owner

1. **CPU target.** The proposal is that the lean decoder uses **≤ 25 % of today's CPU-seconds per cycle** (measured in Phase 0) on the station PC, and finishes every cycle inside the budget with 0 abandoned on `sol` (the 2012 FX-8350) at `effort = normal`. Do you want a different number, or a different "slow machine" bar?
2. **Decode budget.** The proposal is that the lean decoder may be **up to 1 pp below today's WSJT-X match rate** on the same replay slice and still be acceptable. Is that the right trade, or must it match today's rate?
3. **LR-BUILD.** QA's validation run is still in flight. The rebuild replaces the late round, so the result would not change anything. **Recommended: stop the run now and do not merge LR-BUILD.** The alternative is to let it finish as you said on 2026-11-23.
4. **Early decode.** It costs a full extra primary run every cycle. Options:
   - **(a) remove it (recommended):** batch 1 should arrive ≈ 0.5 s after the cycle ends anyway
   - **(b) keep it for the lean decoder** at its cheapest
5. **Process.** Is the light process in §6 what you want, so that this plan answers the viability review's questions 1–3? If yes, the Architect writes the short rule-retirement list next.

---

*Sources: `evaluation-decoder-compute-cost-2026-11-16`, `project-viability-review-2026-11-23`, `architecture-ft8-lib` (K1, K2), the decode-improvement programme tracker (K3, K5, K8), `closed-arms-prohibitions` (K6, K9, K10), the standing licence policy (K12), and `Ft8Decoder.cs` on `main` `66b3ddf1` (§2). Every figure is from a single night as named; none are pooled.*
