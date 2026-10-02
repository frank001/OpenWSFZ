# Captured-audio scan report: 2026-09-29-62e8e74-OFF

- Frozen `thresholds.json` SHA-256 (LF): `c1d793ec773520267dcc0545f0d114bec635d63436b9c1960b3e7891b4a26d8d`; `scan_core.py` `582f422e27e7d9f2d949de7ac10f6fb0cee07c2c48d53c7dbcb6dbc4c7722a21`; calibration run `2026-09-23-5f17b43`.
- Tool: `qa/rr-study/captured-audio-scan/` (`scan_run.py measure`, `scan_apply.py`). Measure wall time: **157.2 s** (V3, one core).
- Audio only. No decoder, `ALL.TXT` or message text was read; counts, slot keys and hashes only (NFR-021).

## What a finding can and cannot mean

> A WAV is recorded **before** either decoder runs, so **no WAV anomaly is ever a decoder defect.** Comparing the two apps' WAVs for the same slot locates a fault in one of two places only. If it shows **in both**, it is in the **shared playback path** (render → PortAudio → Voicemeeter → both recorders). If it shows **in one**, it is in **that app's recording path**. A slot with no anomaly says nothing about how either decoder handled it.

## Headline (plain words)

- **36** slot-family findings are **BOTH** (shared playback path), **7** OpenWSFZ-only, **5** WSJT-X-only, **54** cross-side, over 69 flagged slots of 244 owsfz / 244 wsjt-x scanned.
- 🔴 **Holes.** 30 (side, group, metric) cells are DESCRIPTIVE and never flag (12 of them DESCRIPTIVE-ABOVE-RANGE). **With these thresholds the scan cannot detect a short added sound (a Windows notification, a beep) or a click in the groups where `tile_excess_db` / `click_max` are above range** (owsfz: single, multi, tone2, tone3 tiles; wsjt-x: single, multi, tone3 tiles and multi, noise, tone3 clicks).
- **Blind spots stated:** WSJT-X's last 600 ms (it writes 14.4 s then zeros) cannot show a dropout; slots whose **reference** is lag-ambiguous (steady carriers) have no timing check: owsfz: {'single': 3, 'tone2': 27, 'tone3': 30}, wsjtx: {'single': 3, 'tone2': 27, 'tone3': 30}.
- **REF-UNVERIFIABLE** (mapping rests on the file name ↔ `cycle_utc` identity alone): owsfz: 160/244 (66 %), wsjtx: 160/244 (66 %) — 🛑 OVER 50 %: STOP.

## Validation rows

| Row | Result |
|---|---|
| R0c literal (rule as written, run-wide neighbour max) | owsfz fails 3/244 (1.2 %), wsjt-x 3/244 (1.2 %): **FAIL as written** (kept per ruling A1) |
| R0c per slot (A1), discriminating slots | owsfz 0.0 % fail of 84; wsjt-x 0.0 % of 84: PASS |
| V1 coverage, owsfz | 259 WAV files = 259 classified {'UNPLANNED': 15, 'SCANNED': 244}: PASS |
| V1 coverage, wsjt-x | 437 WAV files = 437 classified {'UNPLANNED': 30, 'UNPAIRED': 163, 'SCANNED': 244}: PASS |
| V1 truth slots with no WAV on either side (MISSING) | 0 |
| V2 sidecar integrity, owsfz | 259 files re-hashed fresh, 0 mismatch: PASS |
| V2 sidecar integrity, wsjt-x | 437 files re-hashed fresh, 0 mismatch: PASS |
| V3 runtime | 157.2 s to measure 244 paired slots (reference renders ≈ 30 s per run extra) |

## Flagged slots by class and family

| class | family | slots |
|---|---|---:|
| BOTH | level | 8 |
| BOTH | spectral | 1 |
| BOTH | timing | 27 |
| CROSS | dtau_ms | 54 |
| OWSFZ-ONLY | dropout | 1 |
| OWSFZ-ONLY | spectral | 6 |
| WSJTX-ONLY | dropout | 1 |
| WSJTX-ONLY | level | 1 |
| WSJTX-ONLY | spectral | 1 |
| WSJTX-ONLY | timing | 2 |

Per-metric flag counts (non-DESCRIPTIVE only), side × metric: owsfz:click_max=7, owsfz:drift_ppm=5, owsfz:g_db=7, owsfz:lag_lost=3, owsfz:step_db_max=8, owsfz:tau_ms=19, owsfz:zero_run_ms=1, wsjtx:click_max=1, wsjtx:drift_ppm=6, wsjtx:g_db=7, wsjtx:lag_lost=3, wsjtx:resid_db=1, wsjtx:step_db_max=9, wsjtx:tau_ms=20, wsjtx:zero_run_ms=1. `lag_lost` slots: owsfz=3, wsjtx=3.

The full list (slot key, cycle, class, family, metrics) is `flagged_slots.csv`; message text never appears.

## Descriptive: S1 chain gain

🛑 S1 `g_db` / `resid_db` below are descriptive chain gains. The +1.45 dB SNR-bias follow-up was dropped by the Captain on 2026-09-29; these numbers do not reopen it and are never cited as a build or chain effect.
- owsfz: median `g_db` -1.63, median `resid_db` -10.32 (n = 30).
- wsjtx: median `g_db` -0.65, median `resid_db` -13.25 (n = 30).

## Registered result: `freeze3` centring; the A11 reclassification below is 'applied after reading; forward rule'

| class | family | slots (`freeze3`, registered) | slots (`a11`, A11, applied after reading; forward rule) |
|---|---|---:|---:|
| BOTH | level | 8 | 8 |
| BOTH | spectral | 1 | 1 |
| BOTH | timing | 27 | 8 |
| CROSS | dtau_ms | 54 | 1 |
| OWSFZ-ONLY | dropout | 1 | 1 |
| OWSFZ-ONLY | spectral | 6 | 6 |
| WSJTX-ONLY | dropout | 1 | 1 |
| WSJTX-ONLY | level | 1 | 1 |
| WSJTX-ONLY | spectral | 1 | 1 |
| WSJTX-ONLY | timing | 2 | 1 |

**Cite as shared-path events only** the BOTH findings that survive A11 plus the level, drift and `lag_lost` families.

### Run-level lines (A11)

(a) run median `g_db` minus the calibration median, per (side, group); `RUN-LEVEL` if |Δ| > 0.5 dB:
- owsfz single: -0.02 dB
- owsfz multi: +0.00 dB
- owsfz tone2: -0.00 dB
- owsfz tone3: -0.00 dB
- wsjtx single: +0.02 dB
- wsjtx multi: +0.01 dB
- wsjtx tone2: -0.00 dB
- wsjtx tone3: -0.00 dB
(b) the run's own median `tau_ms` offset per (side, group) and `dtau_ms` offset: descriptive only, in the table below.

## Descriptive, NOT frozen: run-level offset of the dev metrics (question for the Architect)

The frozen `tau_ms` / `dtau_ms` / `g_db` / `dg_db` rule is two-sided around the **calibration run's** median. Medians per run (ms for tau, dB for g):

| side | group | cal median tau | this run median tau | cal median g | this run median g | slots beyond frozen T (tau) | beyond T if re-centred on this run |
|---|---|---:|---:|---:|---:|---:|---:|
| owsfz | single | -318.6 | -283.9 | -1.92 | -1.94 | 19 | 0 |
| owsfz | multi | -322.0 | -335.3 | -0.86 | -0.86 | 0 | 0 |
| wsjtx | single | -314.7 | -247.3 | -0.77 | -0.75 | 20 | 0 |
| wsjtx | multi | -323.1 | -318.0 | -0.07 | -0.06 | 0 | 0 |
- dtau_ms, single: calibration median -8.7 ms, this run -32.8 ms; beyond frozen T (21.5): 54 of 74; if re-centred: 1.
- dtau_ms, multi: calibration median -0.2 ms, this run -19.4 ms; beyond frozen T (25.9): 0 of 110; if re-centred: 0.
