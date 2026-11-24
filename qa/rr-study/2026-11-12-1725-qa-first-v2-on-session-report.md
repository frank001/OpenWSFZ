# First live session with v2 ON (era "v2 ON"): QA report, descriptive only

**To:** Architect, Captain · **From:** QA · **Written:** 2026-11-12, `date -u` 17:24:27Z at the last check. **Reported, not gated.** Aggregates only: no callsigns and no message text (NFR-021, HK-037). Source: the daemon's own stdout log (`_qa-scratch\v2-on\daemon.out`, 3,862 lines, scratch only; its clock is local time, UTC + 1). Nothing decoded was read.

## Window and build
- **Daemon start 16:32:26Z (stamp); the flag `decoder.coherentFallbackResidualCandidates` was set at 16:32:36Z** (log line "Config saved via API: changed decoder.coherentFallbackResidualCandidates"); first decode carrying it: cycle 16:32:30 (log 16:32:48Z). **Last log line 17:21:03Z, mid-cycle, with no shutdown line: the daemon was force-stopped** (not by QA). About 48.6 minutes, **193 decode cycles** (cycle stamps 16:32:15 to 17:20:30, from the `cq-ap:` lines), **192 with the v2 fields**.
- Build: `_run-main` at `260190e8` (v0.71), shim 20260072, `libft8.dll` SHA-256 = the pin `bbde6eb6…6528`. 20 m, dial 14.074 MHz, CAT connected. **WSJT-X was not running.**
- **Both CQ-AP (`cqApEnabled` true, on since 13:29Z) and v2 were ON**, with R-F4 and L1′ (default ON), Deep, 5 / 0.05, `nhard` 24. This era is **"v2 ON"**, never pooled with "CQ-AP ON" alone or with earlier eras.
- Health: **0 WRN/ERR** lines in the log; the daemon's `/status` read 0 capture restarts, 0 overruns, 0 dropped chunks at 16:32:50Z (not re-read at the stop).

## What the third run did (192 cycles with the v2 fields)
| Quantity | Value |
|---|---|
| `resRun` | **`ran` 192 of 192**; `skipped-budget` **0**, `no-snapshot` 0, `no-residual` 0, `failed` 0 |
| `resCand` | `residual-R3` 135, `residual-R2` 57 |
| **`resAbandoned`** | **0 total, 0 cycles** |
| Third run's new-text rows (`resNew`, before the gate) | 50 |
| dropped by the 1097 Hz gate (`resNewGated`) | 41 (82 %) |
| kept and published (`resNewKept`) | **9**, in 8 cycles |
| Third run's wall time (`resWallMs`) | median **210 ms**, p95 334 ms, max **416 ms** |
| Fallback total wall time (`fbWallMs`, all runs) | median 569 ms, max 996 ms |

For scale only (not a bar): the Stage 2 replay on the CQ-AP night had `resWallMs` median 259 ms and max 594 ms, and the gate dropped 63 % of the third run's new-text rows; the live 20 m session shows a higher dropped share on 50 rows, which is far too few to compare.

## Deadlines and timing (192 or 193 cycles)
- Fallback deadline abandons (cycles with `abandoned > 0`): **0**. Residual-pass `deadlineAbandoned=True`: **0 of 193**. Third pass: `ran` 303, `skipped-no-new` 70 (the counts include runs within a cycle). Late round: `ran` 167, `no-new` 25, `skipped-nothing-decoded` 1, **`abandoned` 0**.
- **Latest batch arrival against the 13 s cycle** (the latest of the batch-4 and batch-5 publish times, over the 179 cycles that had one): **median 3,515 ms, p95 5,201 ms, max 5,503 ms.** For scale (era "RF4+L1′ ON", 20 m, 2026-11-10): median 4,305, p95 4,724, max 5,085 ms. Different hour, different band activity, and CQ-AP and v2 are now on; no comparison is claimed.
- **CQ-AP in the same window:** 193 per-cycle lines, 178,702 attempts, **95 `cq`-tagged decodes** (counts as logged; no corroboration is possible without a reference).

## Things not claimed
- No decode-rate, NET, SNR or false-decode figure: there is no WSJT-X reference in the window, so none exists for this era yet. **The false-decode check of v2 is cited only as "4 of 19 judged"** (the Stage 2 ruling); today's session adds nothing to it.
- 9 kept third-run rows in 192 cycles is a count of published rows, not of corroborated ones.
- The session is short (about 49 minutes) and ended by someone other than QA, so no end-of-session snapshot of `/status` or of the config exists beyond the start readbacks.

## Defects and housekeeping
- None found in the log. The pre-start config backup and the log are in `_qa-scratch\v2-on\`. The live WAV archive and `ALL.TXT` of the window were not gathered (the Captain did not ask; HK-016's gather script needs `--wsjtx-root` and is a separate step if he wants them in `artefacts\`).
