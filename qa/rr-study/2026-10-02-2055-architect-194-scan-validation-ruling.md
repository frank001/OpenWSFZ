# RULING — #194 captured-audio scan: VALIDATION ACCEPTED (09-23 + ON); OFF provisional; A11 split; wiring approved with conditions

- **To:** Engineer — cc QA, Captain  **From:** Architect  **Date:** 2026-10-02 ~20:55Z (HK-017)
- **Branch:** `arch/194-rr-improvements` (fresh off `origin/main`). Docs only: `git diff --stat -- src/ native/` empty.
- **On:** `eng/194-scan` `b371a0c4`, `qa/rr-study/captured-audio-scan/VALIDATION-REPORT-2026-10-02.md`; freeze 3 `d4316452` (`thresholds.json` `e1789e2e…`, `scan_core.py` `6ca48d41…`). The order was kept: three freezes, PC1 passed, and only then 09-29 was opened, once.

## 1. Verdict

**The scan is VALIDATED as a read-only instrument, on 09-23 (calibration) and the 09-29 ON run, with its holes stated.** The R0a/R0b/R0c-per-slot rows, V1 and V2 all PASS, and PC1 passes after A7–A10 (18 PASS, 4 BLIND). The 09-29 **OFF run is accepted as provisional descriptive data only, not as validation** (§3).

## 2. A11: split. YES for timing, NO for level

| Metric | Centre | Why |
|---|---|---|
| `tau_ms`, `dtau_ms` | **each run's own median** per (side, group), with the frozen `T` | Each app opens its own stream when a run starts, so the absolute lag (and the lag between the apps) is a property of that run's start, not a fault. The fault signature is a slot that departs from **its own run**. The numbers bear this out: OFF CROSS dτ 54 → 1, ON noise dτ 118 → 0 |
| `g_db`, `dg_db` | **unchanged: the calibration median** | A level change **between** runs is exactly the "volume or mixer change" the Captain listed in #194. Re-centring would hide it. The level family is stable today (medians agree to ≤ 0.05 dB across the three runs), so keeping it costs nothing |

Add two **run-level** lines to every scan report: (a) the run median `g_db` per (side, group) minus the calibration median, flagged `RUN-LEVEL` if \|Δ\| > 0.5 dB (the existing floor); (b) the run median `tau_ms`/`dtau_ms` offset, descriptive only.

🔴 **For 09-29 the registered result stays the freeze-3 result.** The A11 reclassification is given beside it in a labelled table ("A11, applied after reading; forward rule"). Note that many of the 09-29 BOTH `tau_ms` findings (OFF 19) are probably the same run-level offset, seen on both sides. The A11 table shows how many BOTH findings remain. **Only those, plus the level, drift and `lag_lost` families, are cited as shared-path events.**

A11 changes the rule's application, so it is **freeze 4** (new SHAs), and it applies to every run after 09-29.

## 3. The OFF run

66 % `REF-UNVERIFIABLE` > 50 % ⇒ by A1 "stop and report". It was reported. Its numbers stand as **provisional descriptive data, never as validation**. The scan's validity rests on 09-23 and ON. The cause the Engineer suggests (OpenWSFZ's archive holding only 259 of 407 slots, no S5 noise slot, consistent with #193's archive-mode reset) is a reading, not a finding. QA checks it in one line from that run's daemon config or log, and only if it is cheap. #193 is fixed on main, so it would be history, not a live defect.

## 4. Wiring into the post-run step: APPROVED, after these, in order

1. **Freeze 4** with A11 (and the two run-level lines).
2. **pytest for the pure functions** in `scan_core`/`scan_apply`: the A1 discrimination, A2 end-zero runs, A3′ (reference-only ambiguity), A10 `lag_lost`, A7 above-range classification, the A11 centring split, and BOTH/ONE/CROSS classification. Synthetic arrays only, no WAVs from runs.
3. **Wiring rules:** it runs after the gather, on that run only. 🛑 It **never deletes** anything. A scan failure **never** fails or blocks the run or the next one: it writes `scan_report.md` with the error. 🔴 CPU rule: it starts only when no timing run or live/overnight run is running (it takes about 5 min of one core). The report headline carries the holes **verbatim** from this validation.
4. When the audio-setup sampler exists (spec `…-1940-…-audio-setup-snapshot.md`), add its ±30 s join. Not before.

QA pushes, on the Captain's go (HK-033).

## 5. For the Captain: the notification-sound hole (his decision)

The scan cannot see a short added sound in busy and tonal scenes (12 above-range cells). **Recommendation: do not redesign those two measurements now.** The audio-setup probe showed that Windows' own sounds go to a Voicemeeter input that is **not routed** to the decoders' bus. Once the sampler runs, every run will record whether that is still true. A notification can only reach the decoders through a route the sampler would show. **Revisit the redesign only if a snapshot ever shows system audio routed to B1**, or if a scan anomaly turns up that the other metrics cannot explain.

## 6. Findings worth carrying (descriptive; none is a decoder finding)

- Shared playback-path events occur in **every** run. On 09-23, 12 ≈ 10 ms lag steps inside the continuous stream, and `lag_lost` in 5 slots (all BOTH). Count them under A11 before citing totals.
- OFF: the first 90 s (15:37:45–15:39:15Z) holds 7 BOTH slots together with a burst of Windows events (Kernel-General 16, SPP, AppModel) seen at no other time. A run's first minute and a half deserves a look in future runs once the sampler exists. **No cause is claimed.**
- 🛑 §9 guard: no S1 gain is cited for the dropped +1.45 dB follow-up.
- The §11 gatherer fix is done (`799eac56`, 15 tests green). It goes with the scan's push.
