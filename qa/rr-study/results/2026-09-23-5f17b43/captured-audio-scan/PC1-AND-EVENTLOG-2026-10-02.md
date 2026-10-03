# #194 scan: section 7 (event log) and PC1 results on the 2026-09-23 calibration run

- **From:** Engineer  **To:** Architect, cc QA  **Date:** 2026-10-02 (evening). Freeze: `3953ac35` (`thresholds.json` SHA-256 `a3b19753d66fa0d603dc2b6f5388a093d2b0d402da702320aadbbd5aac84cad9`, `scan_core.py` `07e8d11691c851917dcc6ec3768c558a458c940c47454c0684db6fc81d0c52f4`, both over LF-normalised bytes = the git blobs; the first freeze commit `766eb7a4` hashed CRLF working-copy bytes and is superseded, before any 09-29 audio was read).
- **Status: PC1 has FAILS, so per ruling step 3 the scan STOPS here. The 09-29 pair has NOT been read.**

## 1. Section 7: Windows event log, 2026-09-23 10:33 to 12:24 UTC (local = UTC+2)

- **Retention (the log reaches the run).** Oldest retained entries: System 2026-03-28, Application 2026-07-18, Microsoft-Windows-Audio/Operational 2026-09-15, Kernel-PnP/Configuration 2025-05-31, DeviceSetupManager/Admin 2026-05-23. All reach back past 09-23. **Absence of an audio event is therefore real for those logs** (Audio/Operational: 0 events in the window; Kernel-PnP/Configuration: 0; DeviceSetupManager: 0). It does not cover Voicemeeter's or WSJT-X's own logs, which are not Windows event logs.
- **Events in the window** (System 3, Application 8; none from an audio, USB or driver-reset provider): System 10:34:09 Service Control Manager 7040 (BITS start type), 11:05:17 GroupPolicy 1129 + 1500 (a periodic 100-minute pattern: also 09:25 and 12:45), Application: Software Protection Platform 16394/16384 pairs at 10:42:32, 11:27:51, 11:34:33, 11:45:55 (a recurring pattern, also present every 6 to 15 minutes before the run).
- **Finding 2 of the ruling (11:08:45Z, S5 p0 `t010` step, then the low-`rho` run `t011` to `t024` to ≈ 11:12:30Z): NO event within ±30 s, and none between 11:05:17 and 11:27:51.** The nearest is the 11:05:17 Group Policy refresh, 3.5 minutes earlier. So the log gives **no explanation** for it. It is not read as "nothing happened": the recorder of a Voicemeeter or sound-settings change would not necessarily be in these logs. The Captain's recollection (if he touched sound settings, Voicemeeter or the PC around 11:08Z) remains the open question.
- **The 12 shared lag-step slots, ±30 s:** three have an event within ±30 s: `S1b_p001_t000` 10:42:30 (SPP 10:42:32, 2 s), `S4_p003_t002` 11:05:00 (Group Policy 11:05:17, 17 s), `S5_p001_t022` 11:27:45 (SPP 11:27:51, 6 s). Base rate: the ±30 s windows around all 11 events cover about 9 % of slot starts, so 1.05 of 12 expected by chance, observed 3, binomial P(≥ 3) ≈ 0.075. **Descriptive only; both providers are routine, recurring services, nothing audio-related.** No claim of cause. (A first query used a UTC-marked time that the event-log filter read as local time and returned the wrong window; it was caught because the output ended at 10:16Z, and redone with local times.)
- **Search for S3 outliers** (ruling item): the 12 lag-step slots include two S3 slots, `S3_p001_t000` (10:53:45Z) and `S3_p009_t001` (11:01:15Z, an oversize +2.7 s part). I did not open `S3_matched.csv` (that is QA's; it carries decoder output). For QA's descriptive check: both are listed in `sidecar_*.csv` with `drift_dlag_samples` 120.8 and 113.6 on both apps.

## 2. PC1 (per side × group, 10 unflagged slots drawn with seed 20261002, injections at 0.5×/1×/2× of the frozen T)

`pc1.json` (same directory). Summary over (side, group, metric) cells: **71 PASS, 5 FAIL, 8 NOT-INJECTABLE, 14 DESCRIPTIVE (no PC1), 8 BLIND (A3), 10 UNTESTED (`resid_db`: no injection defined).** Unmodified copies flagged: 0 in every cell. The spec's six injections reach five metrics; I added five extensions (tau shift, click spike, clip, head zeros, tail zeros) so that every non-DESCRIPTIVE metric has a control; `resid_db` has none (UNTESTED, to be ruled).

**FAIL (2× not flagged in all drawn copies):**

| cell | 2× rate | note |
|---|---:|---|
| `owsfz:single:hiccup` | 9/10 | drift/step expected |
| `wsjtx:single:drift_ppm` | 9/10 | T = 20 ppm (floor) |
| `wsjtx:multi:drift_ppm` | 9/10 | T = 20 ppm (floor) |
| `wsjtx:multi:tile_excess_db` | 4/4 injectable | 6 of 10 copies needed a tone above full scale |
| `wsjtx:noise:click_max` | 4/4 injectable | 6 of 10 copies needed a spike above full scale |

The drift misses are one copy of ten each, in the groups that hold the `lag_ambiguous` slots (7 in `single`, 1 in `multi`): consistent with an ambiguous-lag copy whose `drift_ppm` is NaN, but **I have not verified which copy it is**.

**NOT-INJECTABLE (the injection that 2× T implies exceeds full scale):** `tile_excess_db` in owsfz single/multi/tone2/tone3 and wsjtx single/tone3 (T = 27 to 179 dB; the tone would need 1.1 to 10⁷ times full scale), and `click_max` in wsjtx multi/tone3 (T = 188 / 497 sigma). **By construction these metrics cannot flag anything a 16-bit WAV can hold**: their calibrated thresholds sit above the instrument's range (HK-026, the same class of defect as a bar below the real "nothing" level, here a bar above the real "anything"). They did not trip the 2 % DESCRIPTIVE test because the calibration run's content spread is wide and the flagged share stayed under 2 %.

**Flat response (HK-026):** `clip_n` (a single rule, any clipped sample flags, so 0.5× = 1 sample already flags) and `hiccup` in the noise group respond identically at 0.5× and 2×: the scan flags at the smallest injection, which says nothing about sensitivity near the bar. Reported, not a fail.

**BLIND (A3):** `tau_ms` and `drift_ppm` have no valid values in `tone2` and `tone3`, both sides.

## 3. What I need from the Architect

1. Is a PC1 FAIL on a metric whose threshold is above the injectable range a stop for the whole scan, or does that metric become DESCRIPTIVE ("cannot flag within a 16-bit file")? I propose the latter, mechanically: a cell whose 2× injection is not representable is DESCRIPTIVE.
2. The two real misses (`drift_ppm` 9/10 in `wsjtx:single`/`multi`): if the missing copy is an ambiguous-lag slot, the control must be drawn from non-ambiguous slots (a draw rule, not a threshold change). I will check which copy it is and report if you want that.
3. `resid_db`: define an injection, or classify as DESCRIPTIVE.
4. Whether 09-29 may be read once those are settled (the order says PC1 FAIL ⇒ stop).

The scan work is paused here. The Engineer has also been given the LATENESS edge test by QA (the Captain's priority), which now takes the session.
