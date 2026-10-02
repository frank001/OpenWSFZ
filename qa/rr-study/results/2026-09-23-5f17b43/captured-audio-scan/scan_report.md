# Captured-audio scan report: 2026-09-23-5f17b43 (CALIBRATION RUN)

- Frozen `thresholds.json` SHA-256 (LF): `e1789e2ec8a02caf66898dd15b2e208df6ebec3508460f2f29433a81b1146d11`; `scan_core.py` `6ca48d41fe3e957f2bea7bbdaf03b94150079ba80f341c2d6a36ff6d50b18eb4`; calibration run `2026-09-23-5f17b43`.
- Tool: `qa/rr-study/captured-audio-scan/` (`scan_run.py measure`, `scan_apply.py`). Measure wall time: **276.4 s** (V3, one core).
- Audio only. No decoder, `ALL.TXT` or message text was read; counts, slot keys and hashes only (NFR-021).

## What a finding can and cannot mean

> A WAV is recorded **before** either decoder runs, so **no WAV anomaly is ever a decoder defect.** Comparing the two apps' WAVs for the same slot locates a fault in one of two places only. If it shows **in both**, it is in the **shared playback path** (render → PortAudio → Voicemeeter → both recorders). If it shows **in one**, it is in **that app's recording path**. A slot with no anomaly says nothing about how either decoder handled it.

## Headline (plain words)

- **42** slot-family findings are **BOTH** (shared playback path), **9** OpenWSFZ-only, **17** WSJT-X-only, **1** cross-side, over 25 flagged slots of 407 owsfz / 407 wsjt-x scanned.
- 🔴 **Holes.** 30 (side, group, metric) cells are DESCRIPTIVE and never flag (12 of them DESCRIPTIVE-ABOVE-RANGE). **With these thresholds the scan cannot detect a short added sound (a Windows notification, a beep) or a click in the groups where `tile_excess_db` / `click_max` are above range** (owsfz: single, multi, tone2, tone3 tiles; wsjt-x: single, multi, tone3 tiles and multi, noise, tone3 clicks).
- **Blind spots stated:** WSJT-X's last 600 ms (it writes 14.4 s then zeros) cannot show a dropout; slots whose **reference** is lag-ambiguous (steady carriers) have no timing check: owsfz: {'single': 3, 'tone2': 30, 'tone3': 30}, wsjtx: {'single': 3, 'tone2': 30, 'tone3': 30}.
- **REF-UNVERIFIABLE** (mapping rests on the file name ↔ `cycle_utc` identity alone): owsfz: 175/407 (43 %), wsjtx: 175/407 (43 %) (limit 50 %).

## Validation rows

| Row | Result |
|---|---|
| R0c literal (rule as written, run-wide neighbour max) | owsfz fails 12/407 (2.9 %), wsjt-x 42/407 (10.3 %): **FAIL as written** (kept per ruling A1) |
| R0c per slot (A1), discriminating slots | owsfz 0.0 % fail of 232; wsjt-x 0.0 % of 232: PASS |
| V1 coverage, owsfz | 437 WAV files = 437 classified {'UNPLANNED': 30, 'SCANNED': 407}: PASS |
| V1 coverage, wsjt-x | 438 WAV files = 438 classified {'UNPLANNED': 31, 'SCANNED': 407}: PASS |
| V1 truth slots with no WAV on either side (MISSING) | 0 |
| V2 sidecar integrity, owsfz | 437 files re-hashed fresh, 0 mismatch: PASS |
| V2 sidecar integrity, wsjt-x | 438 files re-hashed fresh, 0 mismatch: PASS |
| V3 runtime | 276.4 s to measure 407 paired slots (reference renders ≈ 30 s per run extra) |

## Flagged slots by class and family

| class | family | slots |
|---|---|---:|
| BOTH | dropout | 1 |
| BOTH | level | 13 |
| BOTH | spectral | 11 |
| BOTH | timing | 17 |
| CROSS | dtau_ms | 1 |
| OWSFZ-ONLY | spectral | 7 |
| OWSFZ-ONLY | timing | 2 |
| WSJTX-ONLY | dropout | 9 |
| WSJTX-ONLY | level | 6 |
| WSJTX-ONLY | spectral | 2 |

Per-metric flag counts (non-DESCRIPTIVE only), side × metric: owsfz:click_max=18, owsfz:drift_ppm=15, owsfz:g_db=12, owsfz:lag_lost=5, owsfz:resid_db=5, owsfz:step_db_max=13, owsfz:tau_ms=1, owsfz:tile_excess_db=1, owsfz:zero_run_ms=1, wsjtx:click_max=1, wsjtx:drift_ppm=14, wsjtx:g_db=18, wsjtx:lag_lost=5, wsjtx:resid_db=11, wsjtx:step_db_max=19, wsjtx:tile_excess_db=6, wsjtx:zero_run_ms=10. `lag_lost` slots: owsfz=5, wsjtx=5.

The full list (slot key, cycle, class, family, metrics) is `flagged_slots.csv`; message text never appears.

## Descriptive: S1 chain gain

🛑 S1 `g_db` / `resid_db` below are descriptive chain gains. The +1.45 dB SNR-bias follow-up was dropped by the Captain on 2026-09-29; these numbers do not reopen it and are never cited as a build or chain effect.
- owsfz: median `g_db` -1.63, median `resid_db` -10.35 (n = 30).
- wsjtx: median `g_db` -0.67, median `resid_db` -12.70 (n = 30).
