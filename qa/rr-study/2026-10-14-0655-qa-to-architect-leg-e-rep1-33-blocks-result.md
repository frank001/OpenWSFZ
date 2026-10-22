# QA to Architect: leg E replicate 1 (33 blocks) complete, Section 8 added to the Linux consolidated report

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-14 06:55Z (`date -u` 06:52:16Z at analysis). **Go:** the Captain, "complete the r&r and the report ... consult the architect". The Architect's session was not running, so this is the note, not a consultation; nothing here asks for a ruling before the Captain reads it.
- **What ran:** `queue_leg_e.sh 1` on `sol`, 2026-10-13 19:15:17Z to 2026-10-14 01:19:43Z; WSJT-X 2.7.0 exe SHA `2f968b2f…17b4` = pin, canary decoded, driver SHA `66316f6c…`, NDepth 3, lead 0.0 s, 33 blocks, 0 excluded, orphan check 0. Descriptive, one replicate (spec §2o definitions).
- **Files:** `qa/rr-study/results/2026-10-13-leg-e-rep1-33-blocks-sol/` (`SUMMARY-rep1.json`, `compare-rep1-33.json`, `QUEUE-STATUS.txt`); report Section 8 in `results/2026-10-13-LINUX-series-consolidated/report.md`. Aggregates only; scanned, no callsigns. Comparison: `leg_e_subset_compare.py` unchanged, pointed at all 33 blocks (its own 'note' string still says 7 blocks; text only).

| Figure | Value |
|---|---|
| LIVE rows reproduced by E | 93.3 % [89.3, 96.0] (17,592 / 18,854); E-only 1,381 |
| LIVE rows reproduced by B | 74.0 % [71.1, 77.2] (13,945 / 18,854): the first run's figure, unchanged |
| E rows reproduced by B | 76.1 % [73.3, 79.1] (14,433 / 18,973); B-only 484 |
| `late` (> 17 s), 1056 cycles | 3.0 % [0.9, 5.8]; by live-row bin 0.0 / 0.3 / 0.9 / 16.3 % |
| `T_wsjtx_last` | median 14.86 s, P90 16.05, max 18.13 |
| `T_ows` > 15 s | 72.7 % [60.3, 84.8] (a different quantity) |

- **For the Architect's reading:** (1) Section 7's 11.2 % late share was a selected-busiest sample; the corpus figure is 3.0 %. If any document quotes 11.2 % as WSJT-X's keep-up on the corpus, it should say 'busiest 7 blocks' (the S6 amendment 3 standing row should take the 33-block figure). (2) One block, `cb2e73aa964f` (20260921, 20 m twilight), has E at 62.4 % of live (live 34.3 rows per cycle, E 21.8): the replay is the thin one there; cause not examined. (3) One replicate: no repeatability figure for leg E; K = 3 under §3c is still not met.
- **Not done:** the three Linux S1-S8 repeats with WSJT-X running stay deferred (the report's recommendations 1-3 are open); the generator `build_consolidated_report.py` does not yet produce Section 8 (hand-added; a regeneration would drop it); `~/qa-scratch/leg-e` working files (message text) remain on `sol` until job close; nothing committed beyond this note, nothing pushed.
