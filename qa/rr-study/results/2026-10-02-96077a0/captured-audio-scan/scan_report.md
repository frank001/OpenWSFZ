# Captured-audio scan report: 2026-10-02-96077a0

- Frozen `thresholds.json` SHA-256 (LF): `c1d793ec773520267dcc0545f0d114bec635d63436b9c1960b3e7891b4a26d8d`; `scan_core.py` `582f422e27e7d9f2d949de7ac10f6fb0cee07c2c48d53c7dbcb6dbc4c7722a21`; calibration run `2026-09-23-5f17b43`.
- Tool: `qa/rr-study/captured-audio-scan/` (`scan_run.py measure`, `scan_apply.py`). Measure wall time: **278.7 s** (V3, one core).
- Audio only. No decoder, `ALL.TXT` or message text was read; counts, slot keys and hashes only (NFR-021).

## What a finding can and cannot mean

> A WAV is recorded **before** either decoder runs, so **no WAV anomaly is ever a decoder defect.** Comparing the two apps' WAVs for the same slot locates a fault in one of two places only. If it shows **in both**, it is in the **shared playback path** (render → PortAudio → Voicemeeter → both recorders). If it shows **in one**, it is in **that app's recording path**. A slot with no anomaly says nothing about how either decoder handled it.

## Headline (plain words)

- **48** slot-family findings are **BOTH** (shared playback path), **10** OpenWSFZ-only, **37** WSJT-X-only, **4** cross-side, over 38 flagged slots of 407 owsfz / 407 wsjt-x scanned.
- 🔴 **Holes.** 30 (side, group, metric) cells are DESCRIPTIVE and never flag (12 of them DESCRIPTIVE-ABOVE-RANGE). **With these thresholds the scan cannot detect a short added sound (a Windows notification, a beep) or a click in the groups where `tile_excess_db` / `click_max` are above range** (owsfz: single, multi, tone2, tone3 tiles; wsjt-x: single, multi, tone3 tiles and multi, noise, tone3 clicks).
- **Blind spots stated:** WSJT-X's last 600 ms (it writes 14.4 s then zeros) cannot show a dropout; slots whose **reference** is lag-ambiguous (steady carriers) have no timing check: owsfz: {'single': 3, 'tone2': 30, 'tone3': 30}, wsjtx: {'single': 3, 'tone2': 30, 'tone3': 30}.
- **REF-UNVERIFIABLE** (mapping rests on the file name ↔ `cycle_utc` identity alone): owsfz: 175/407 (43 %), wsjtx: 175/407 (43 %) (limit 50 %).

## Validation rows

| Row | Result |
|---|---|
| R0c literal (rule as written, run-wide neighbour max) | owsfz fails 14/407 (3.4 %), wsjt-x 36/407 (8.8 %): **FAIL as written** (kept per ruling A1) |
| R0c per slot (A1), discriminating slots | owsfz 0.0 % fail of 232; wsjt-x 0.0 % of 232: PASS |
| V1 coverage, owsfz | 454 WAV files = 454 classified {'UNPLANNED': 47, 'SCANNED': 407}: PASS |
| V1 coverage, wsjt-x | 455 WAV files = 455 classified {'UNPLANNED': 48, 'SCANNED': 407}: PASS |
| V1 truth slots with no WAV on either side (MISSING) | 0 |
| V2 sidecar integrity, owsfz | 454 files re-hashed fresh, 0 mismatch: PASS |
| V2 sidecar integrity, wsjt-x | 455 files re-hashed fresh, 0 mismatch: PASS |
| V3 runtime | 278.7 s to measure 407 paired slots (reference renders ≈ 30 s per run extra) |

## Flagged slots by class and family

| class | family | slots |
|---|---|---:|
| BOTH | level | 15 |
| BOTH | spectral | 15 |
| BOTH | timing | 18 |
| CROSS | dg_db | 3 |
| CROSS | dtau_ms | 1 |
| OWSFZ-ONLY | dropout | 1 |
| OWSFZ-ONLY | spectral | 8 |
| OWSFZ-ONLY | timing | 1 |
| WSJTX-ONLY | dropout | 15 |
| WSJTX-ONLY | level | 11 |
| WSJTX-ONLY | spectral | 4 |
| WSJTX-ONLY | timing | 7 |

Per-metric flag counts (non-DESCRIPTIVE only), side × metric: owsfz:click_max=23, owsfz:drift_ppm=14, owsfz:g_db=14, owsfz:lag_lost=3, owsfz:resid_db=5, owsfz:step_db_max=15, owsfz:tau_ms=2, owsfz:tile_excess_db=5, owsfz:zero_run_ms=1, wsjtx:drift_ppm=14, wsjtx:g_db=17, wsjtx:lag_lost=3, wsjtx:resid_db=17, wsjtx:step_db_max=26, wsjtx:tau_ms=9, wsjtx:tile_excess_db=8, wsjtx:zero_run_ms=15. `lag_lost` slots: owsfz=3, wsjtx=3.

The full list (slot key, cycle, class, family, metrics) is `flagged_slots.csv`; message text never appears.

## Descriptive: S1 chain gain

🛑 S1 `g_db` / `resid_db` below are descriptive chain gains. The +1.45 dB SNR-bias follow-up was dropped by the Captain on 2026-09-29; these numbers do not reopen it and are never cited as a build or chain effect.
- owsfz: median `g_db` -1.86, median `resid_db` -9.75 (n = 30).
- wsjtx: median `g_db` -0.85, median `resid_db` -11.18 (n = 30).

## Registered result: `a11` centring (A11 forward rule)

| class | family | slots (`a11`, registered) | slots (`freeze3`, freeze 3 rule) |
|---|---|---:|---:|
| BOTH | level | 15 | 15 |
| BOTH | spectral | 15 | 15 |
| BOTH | timing | 18 | 17 |
| CROSS | dg_db | 3 | 3 |
| CROSS | dtau_ms | 1 | 32 |
| OWSFZ-ONLY | dropout | 1 | 1 |
| OWSFZ-ONLY | spectral | 8 | 8 |
| OWSFZ-ONLY | timing | 1 | 1 |
| WSJTX-ONLY | dropout | 15 | 15 |
| WSJTX-ONLY | level | 11 | 11 |
| WSJTX-ONLY | spectral | 4 | 4 |
| WSJTX-ONLY | timing | 7 | 110 |

**Cite as shared-path events only** the BOTH findings that survive A11 plus the level, drift and `lag_lost` families.

### Run-level lines (A11)

(a) run median `g_db` minus the calibration median, per (side, group); `RUN-LEVEL` if |Δ| > 0.5 dB:
- owsfz single: -0.05 dB
- owsfz multi: +0.00 dB
- owsfz noise: -0.01 dB
- owsfz tone2: -0.00 dB
- owsfz tone3: -0.00 dB
- wsjtx single: -0.02 dB
- wsjtx multi: +0.00 dB
- wsjtx noise: -0.01 dB
- wsjtx tone2: -0.00 dB
- wsjtx tone3: -0.00 dB
(b) the run's own median `tau_ms` offset per (side, group) and `dtau_ms` offset: descriptive only, in the table below.

## Descriptive: run-level timing offset (the A11 evidence; the frozen two-sided rule for g_db stays on the calibration median)

The frozen `tau_ms` / `dtau_ms` / `g_db` / `dg_db` rule is two-sided around the **calibration run's** median. Medians per run (ms for tau, dB for g):

| side | group | cal median tau | this run median tau | cal median g | this run median g | slots beyond frozen T (tau) | beyond T if re-centred on this run |
|---|---|---:|---:|---:|---:|---:|---:|
| owsfz | single | -318.6 | -326.8 | -1.92 | -1.97 | 1 | 1 |
| owsfz | multi | -322.0 | -321.0 | -0.86 | -0.86 | 0 | 0 |
| owsfz | noise | -331.3 | -313.8 | -2.91 | -2.92 | 0 | 1 |
| wsjtx | single | -314.7 | -316.9 | -0.77 | -0.78 | 0 | 0 |
| wsjtx | multi | -323.1 | -294.7 | -0.07 | -0.06 | 3 | 0 |
| wsjtx | noise | -327.6 | -299.1 | -1.10 | -1.11 | 111 | 9 |
- dtau_ms, single: calibration median -8.7 ms, this run -8.9 ms; beyond frozen T (21.5): 1 of 99; if re-centred: 1.
- dtau_ms, multi: calibration median -0.2 ms, this run -22.6 ms; beyond frozen T (25.9): 30 of 125; if re-centred: 0.
- dtau_ms, noise: calibration median -3.9 ms, this run -14.2 ms; beyond frozen T (25.2): 1 of 120; if re-centred: 0.
