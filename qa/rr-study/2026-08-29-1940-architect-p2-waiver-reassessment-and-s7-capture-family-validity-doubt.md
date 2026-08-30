# ARCHITECT — P2 waiver reassessment: **not moved**, but the waiver is **mis-described**, and S7's capture family now has a validity problem

**Author:** Architect (Captain asked for a reassessment of the P2 waiver "after recent improvements")
**Date (UTC, `date -u`, HK-017):** 2026-08-29 19:40:08Z
**Type:** Measurement report. **No spec, no arm, no change proposed.** Direction requested.

---

## 1. Direct answer — P2 has not moved. The waiver's factual basis is intact

Measured across **every run holding P2's 15-row shape**, from before the waiver to the latest build:

| run | WSJT-X | OpenWSFZ | per-trial (OpenWSFZ) |
|---|---:|---:|---|
| 2026-06-20 `6e821fa` | 9/15 | **0/15** | [0,0,0,0,0] |
| 2026-06-22 `f11f438` ← waiver | 12/15 | **0/15** | [0,0,0,0,0] |
| 2026-07-04 `793a298` | 15/15 | **0/15** | [0,0,0,0,0] |
| 2026-08-05 `3bd4cd0` | 15/15 | **0/15** | [0,0,0,0,0] |
| 2026-08-15 `8d6e1b1` | 15/15 | **0/15** | [0,0,0,0,0] |
| 2026-08-21 `7d36038` | 15/15 | **0/15** | [0,0,0,0,0] |
| 2026-08-22 `f5dec23` | 15/15 | **0/15** | [0,0,0,0,0] |
| 2026-08-27 `22b749c` | 12/15 | **0/15** | [0,0,0,0,0] |
| 2026-08-29 `872ba65` | 12/15 | **0/15** | [0,0,0,0,0] |

🔴 **135 observations. Zero recoveries. No variance whatsoever, before or after the waiver.**

✅ **And nothing landed that could plausibly have moved it.** 45 commits touch `native/` or
`src/OpenWSFZ.Ft8/` on `main` since 2026-06-22, but they are diagnostic exports (`ft8_coherent_llr_at`,
`extract_llrs_at_position`, sync-refiner instrumentation), build/vendoring work (`r0-reproducible-native-build`),
hash-table and callsign features (F-003/F-004/F-005, `HASH_TABLE_SIZE` 256→4096, D-011), and
CycleFramer timing fixes. The one genuine demodulation change is `c3a9ea8` (negative `time_offset`
SNR collapse). **None of it targets multi-signal separation**, and the two most recent sweeps carry
all of it. ⇒ **The waiver stands on its facts. There is nothing to lift.**

---

## 2. 🔴 But the waiver is described wrongly, and the description is the part that matters

P2 is recorded as **"3-stack co-channel, equal 0 dB"**. Read from `S7_matched.csv`'s own truth rows:

```
freq=1492.0 Hz  snr=0.0 dB  dt=0.0 s   CQ Q1ABC FN42
freq=1500.0 Hz  snr=0.0 dB  dt=0.0 s   Q4XYZ Q1ABC -07
freq=1511.0 Hz  snr=0.0 dB  dt=0.0 s   Q3PQR Q1ABC RR73
separations: 8.0 Hz, 11.0 Hz   (total span 19 Hz)
```

**It is not co-channel.** The signals are 8 and 11 Hz apart.

🔴 **And OpenWSFZ solves both of those separations perfectly, with two signals:**

| part | signals | separation | levels | recovery |
|---|---:|---:|---|---:|
| **P8** | 2 | **8 Hz** | equal | **10/10** |
| **P19** | 2 | **8 Hz** | equal | **10/10** |
| **P9** | 2 | **11 Hz** | equal | **10/10** |
| P10 / P20 | 2 | 9 Hz | equal | 10/10 |
| **P2** | **3** | **8 + 11 Hz** | equal | **0/15** |

⇒ **Not a separation limit. Not a level limit. The third signal is the variable** — and the failure
is **total**: zero of three recovered, never one, never two, in 45 trial-signal opportunities.

⚠️ **Nor is it a signal-count limit.** S8 (the realistic band scene) carries **12 simultaneous
signals per cycle** and OpenWSFZ recovers **55/60 = 91.67%**. Twelve concurrent signals are fine when
spread across the band; three inside 19 Hz produce nothing.

**Correct description: three equal-power signals within a ~19 Hz span yield zero decodes, at pairwise
separations that are individually solved at 10/10.** That is a much sharper and more tractable
statement than "co-channel stacking is structurally hard", and it is worth correcting in the record
whatever is decided about the waiver.

---

## 3. 🔴 The finding I was not looking for — S7's capture family contradicts S8

While establishing P2's density context I found a direct contradiction between two scenarios in the
**same run, same build, same harness, same session** (so the 08-29 confound does not apply):

**S8 places two signals at exactly `1500.0 Hz`, both `dt = 0.0`, at `0 dB` and `−6 dB`. Both decode.**

| run | S8 co-channel pair (0 / −6 dB, **0 Hz apart**) | S7 P12 weak (0 / −6 dB, **9 Hz apart**) |
|---|---:|---:|
| 2026-08-21 `7d36038` | **5/10** | 0/5 |
| 2026-08-22 `f5dec23` | **10/10** | 0/5 |
| 2026-08-27 `22b749c` | **10/10** | 0/5 |
| 2026-08-29 `872ba65` | **5/5** | 0/5 |

🔴 **Same level difference. Zero separation instead of nine. Better result — reliably, across four
independent runs.** That is backwards for any masking or leakage theory, in which co-channel must be
the harder case.

**Consequence.** Spec `WIN-A` §1.2 called the −3 dB → −6 dB capture cliff *"the single sharpest fact
in the battery"* and built the whole arm on it. This says the cliff is **not a property of the
decoder** — the decoder demonstrably recovers a −6 dB signal underneath a 0 dB one at zero
separation. It is a property of **how S7's capture family is constructed.**

✅ **This is consistent with `WIN-A`'s ROW 0e result rather than contradicting it** — leakage was
never the mechanism, and two independent lines now say so.

⚠️ **What I am NOT claiming.** I have not identified what differs between the two constructions.
Candidates, none tested: message/callsign content, per-part seeds, the synth path used for S7's
two-signal parts vs S8's scene, or DT handling. **This is a flag, not a diagnosis**, and it must not
be written up as one.

---

## 4. What this puts at risk, stated plainly

If S7's capture family is measuring its own construction rather than the decoder, then part of the
headline **19.07 pp S7 gap** is scenario artefact, not product deficit:

| cluster | pp of the gap | status after this |
|---|---:|---|
| Capture (P12/P13/P14) | **6.98** | 🔴 **validity in doubt** — §3 |
| P2 3-stack (waived) | **5.58** | ⚠️ **real but mis-described** — §2 |
| Tight separation (P15/P4/P0) | 6.51 | untouched by this report |
| ΔF 13 Hz (P1) | 0.93 | untouched |
| OpenWSFZ ahead (P3) | −0.93 | untouched |

⚠️ **Up to ~12.6 pp of the 19.07 pp — roughly two thirds — now sits under a validity question or a
wrong label.** And the realistic scenario has OpenWSFZ at 55/60 against WSJT-X's 58/60, a
three-decode gap, stable across three runs.

🛑 **I am not concluding that the capture family is invalid.** I am reporting that a within-run,
four-run-reproducible contradiction exists, that it was found in data we already held, and that it
sits directly underneath the target the last several arms have been aimed at.

---

## 5. Direction requested — no work starts without it

1. **P2 waiver:** my recommendation is **keep the waiver, correct its wording** to §2's description.
   It is not co-channel and it is not a general multi-signal limit; it is a narrow-span three-signal
   failure. ⚠️ **Re-scoping a waiver is the Captain's call, not mine.**
2. **The §3 contradiction:** worth a bounded, offline investigation — existing artefacts plus the
   synth, no radio, no decoder change — into what differs between S8's co-channel pair and S7's P12.
   **This would be a scenario-validity question, not a D-001 arm**, and it should be settled before
   any further arm is aimed at the capture family.
3. **Sequencing:** if §3 holds up, the S7 battery needs revision before it is used to target work
   again — which would also change what "improving performance" means, per the open question from
   earlier this session.

🛑 Nothing here authorises a scenario edit, a `src/`/`native/` change, an arm, or a merge. Per HK-014
committed locally, not pushed.
