# First live session on the default-ON build (era "RF4+L1′ ON"): QA report, spec §3

**To:** Architect · **From:** QA · **Written:** 2026-11-10T15:32Z (`date -u`)
**Reported, not gated** (spec §3). Aggregates only: no callsigns and no message text (NFR-021, HK-037).

## Window and build
- **Daemon start 11:35:28Z, stop 15:30:48Z** (`date -u` readings; force-stopped). 941 decode cycles (cycle stamps 11:35:30 to 15:30:45 UTC), 0 watchdog restarts, 0 capture restarts, 0 dropped cycles.
- Build: `_run-main` at `98332f2a` (v0.69), shim 20260071, `libft8.dll` SHA-256 starts `1ba8dc3d` = the pin. Port 8080, 20 m, dial 14.074 MHz, capture from the direct "Microphone (2- USB Audio CODEC)" (the Captain's choice; the device id was re-resolved at start, a WRN in the log, same friendly name).
- Voicemeeter strip 0 unmuted to B1, AUX muted (read-only status). **WSJT-X was not running** (no reference decoder in this window).
- Source: the daemon's stdout log (`_qa-scratch\live-rf4on\daemon_final.out`, 19,269 lines, scratch only). Nothing decoded text was read.

## 1. Both flags read back true
- `coherentFallbackResidualUngated` = **true** (R-F4), read from the live `/api/v1/config` during the session (about 11:36Z), and `lateSubtractionRound` = **true** (L1′), read from the saved config file after the stop (the key was absent at the 20:38Z read-back of 2026-11-09, which reads as ON; it is present as `true` in the saved file after the stop, and QA did not check whether the 12:07Z overlay POST, which touched only the WAV archive key, is what wrote it out).
- Behavioural confirmation in the log: 930 late rounds with `outcome=ran`, and the fallback's `ungated=` field non-zero (below).
- Decoder otherwise: Deep, fallback ON, multi-set ON, audio Both, `kMinScorePass2` 5, `osdCorrThreshold` 0.05, `nhard` 24.

## 2. Per 100 cycles (941 cycles)
| Quantity | Total | per 100 cycles |
|---|---|---|
| Batch-5 (L1′ late round) decodes published | 853 | **90.6** |
| Batch-4 (coherent fallback) rows published | 934 | 99.3 |
| Fallback rows published in all (`published=`) | 4,092 | 434.9 |
| Residual-run rows published by R-F4's ungating (`ungated=`) | 1,382 | **146.9** |
| Fallback deadline abandons (cycles with `abandoned>0`) | **0** | **0.0** |
| Residual-pass deadline abandons (`deadlineAbandoned=True`) | **0** | **0.0** |
| Third pass (`/status` counters at the stop): runs 931, skipped-no-new 10 | 941 cycles | 0 abandoned, 0 failed |
| Late round outcomes | `ran` 930, `no-new` 10, `abandoned` **0** | |

Definition notes: "published" is the field of the daemon's own per-cycle line; the `ungated` and `published` fields are counts of rows, one per decode, summed over cycles. `ungated` is the count R-F4's ungating admitted in the fallback line.

**For scale (replays, not a bar):** R-F4 second night: fallback abandoned 0 and residual pass abandoned 0 (pre-registered row V-2N-AB). L1′ third night, ON arm: fallback abandoned in 4 of 800 cycles (0.5 per 100), third pass 2, residual 0 (`2026-10-31-0000-qa-late-sub-l1p-third-night-report.md`, line 12). The late round itself abandoned in 228 of 800 replay cycles there; **live it abandoned 0 of 940**. **Live is not worse than either replay on any abandon count (0 against 0.5 and 0).** Architect's DO-3 reads: the bar was "≤ larger of the two replay rates + 1 per 100"; live 0.0 ≤ 1.5, a hit. (Scoring is the Architect's.)

## 3. Latest batch arrival against the 13 s cycle
Per cycle, the latest published batch time (batch-4 publish time or batch-5 publish time, `ms` after the window, the same fields as the KMIN-OSD-RECAL report): **median 4,305 ms, p95 4,724 ms, max 5,085 ms** over 940 cycles. For comparison the KMIN arm B (the same 5 / 0.05 floor, replay) had 4,627 / 5,916 / 7,236 ms. **No cycle is near the budget; the maximum is 8 s below the 13 s cycle, so L1′'s batch 5 never arrives too late for the TX decision in this window.**
## 4. Things not claimed
- No decode-rate, SNR or false-decode figure. There is no WSJT-X reference in the window, so no NET and no comparison with any earlier era (never pool across eras).
- No total of decodes was computed.
- WAV archive: written only from 12:07:45Z (814 files) because `cycleAudioArchive.mode` was `off` in the station config until the Captain noticed it; 11:35 to 12:07Z has no audio.

## 5. Defects and housekeeping found
- **QA's watcher stopped nothing at 14:30:00Z:** a non-forced `taskkill` does not close the console daemon. The daemon was force-stopped at 15:30:48Z; process check clean, no orphans (HK-019). Fix for the next watcher: `taskkill /F`.
- QA error: the `cycleAudioArchive` key was not read before the start (the Captain noticed the missing WAVs). Ledger row to follow.
- PSK Reporter upload was ON under the Captain's call for the whole window (a datagram about every 5 minutes, no errors, no "queue-dropped").
- MQTT feed recorded in parallel for CQ-AP-PSK; it reads nothing from the daemon and is not part of this report.
