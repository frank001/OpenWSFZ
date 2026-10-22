# Third pass (#240): corpus inventory and QA's choice, stated BEFORE any Deep-ON decode is read (QA → Architect)

- **To:** Architect. cc Captain. **From:** QA. **Date:** 2026-10-18 12:34Z (`date -u`).
- Spec §3.1 and the Captain's rule of 2026-10-03: every `artefacts/` folder with WAVs is listed before the corpus is chosen. Source: `D:\Projects\claude\OpenWSFZ\artefacts` (the Captain pointed QA at the root checkout). **Nothing Deep-ON has been decoded or read.** Docs only; `src/` and `native/` diff empty. Aggregates only: no message text or callsign appears here.

## 1. Inventory (one `find` over the root artefacts, folders with ≥ 50 WAVs)

WAV counts below are what `find` saw; a `*-gathered` folder holds both appraisers' WAVs, so the OWS side is half of its total.

| group | folders | WAVs | live WSJT-X `ALL.TXT` of the same session? |
|---|---|---|---|
| Endurance, gathered (6 sessions, 40 m, dial 7.074 MHz) | `20260922_2056`, `20260923_1730`, `20260925_2010`, `20260930_1930`, `20261004_1634`, `20261009_1752` | OWS side 2,882 / 5,763 / 2,884 / 4,299 / 3,106 / 3,634 | **yes, all six** (WSJT-X Rx FT8 lines 92,048 / 159,265 / 76,999 / 129,608 / 98,156 / 93,611) |
| Live runs, other bands | `20260808_live_run_1154-8080-17m` (**17 m**, 18.100 MHz, 1,856 OWS WAVs, WSJT-X 39,713 lines, 2026-08-08 11:54 → 19:38); `20260809_live_run_0155-8080-80m` (**80 m**, 3.573 MHz, 1,988 OWS WAVs, WSJT-X 10,952 lines, 2026-08-09 01:54 → 07:28) and their `-8081` twins | as given | yes (each has `wsjt-x/ALL.TXT`) |
| Other live runs (2026-06 → 2026-09: `20260614`…`20260921_1624_live_run-live-gap-map`, `20260908_…fp-floor-live-2`) | 22 folders, 126 → 20,981 WAVs each | not individually checked for an `ALL.TXT` | not examined (older builds, bands not read) |
| R&R and replay material | `rr-s6-refset-corpus` (15,680; the sol refset), `_rr_*_daemon_output`, `rr_2026-09-29_subfeas_off_on` (1,571), `rr_2026-10-06_nhard_rep` (201), `2026-08-30…2026-09-07-rr-s1s8-*`, `20260912_1151_rr-study-s1s8`, `20260914_1822_rr-study-s1s8` | synthetic or injected audio | no live reference |
| Small / D-001 | `d001_*` (51–80), `20260925_l1l4_capture_self_healing` (167), `20261002_2115_lateness_edge_run` (239), `p12-ft8lib-port_UAT-01_items` (280) | | not examined |

## 2. QA's choice and the reasons

- **Y-40 (primary): `20261009_1752_endurance_run-gathered`.** 40 m, 2026-10-09 17:52 → 10-10 09:00 UTC, **3,634 OWS WAVs, every cycle kept**, WSJT-X live `ALL.TXT` of the same session (93,611 Rx FT8 lines, about 26 per cycle). It is the first full session after the OSD-fix deploy (2026-10-09 14:01Z), the Architect's stated preference. The replay sets `nhard`, the OSD sign switch and the thread count itself, so the era of the recording is not a filter (Captain's rule). **Deterministic subsample:** every 8th WAV in sorted order starting at the first, **455 cycles** (every 16th would be 228). Rule fixed here, before any Deep data: `ls | awk 'NR%8==1'`.
- **Y-2 (descriptive): `20260808_live_run_1154-8080-17m`.** 17 m, 1,856 WAVs, 39,713 WSJT-X lines (about 21 per cycle, as crowded as the 40 m session), against 80 m's 5.5 per cycle where the residual pass has little to find. Same rule: every 8th, **232 cycles**. **Caveat, not examined:** the WSJT-X settings of that 2026-08 session (Decode depth, version) are not on record; M6 is descriptive only, and its reference may not be the 2.7.0 Deep one of §0.
- **T-REF (timing, sol, exclusive, 13 s):** the sol refset's 60 WAVs (`qa/rr-study/s6/s6-wavlist.json`, the audio of #240's 1.1 s / 3.1 s figures).
- **Not chosen, and why:** `20260930_1930` (the 10-01 OFF/ON replay night) is pre-OSD-fix and already used by the DI-sync identity runs; the other four endurance sessions add no band. The 80 m run is sparse. The older live runs were not individually inspected.

## 3. Cost, so the Captain can size it (measured, not guessed)

From the DI-sync logs: flag-ON cycles ran at about 6.7 s per cycle on the PC with 8 threads (108 cycles in 12 min), flag-OFF cycles about 0.6 s. Deep adds a third round on top.
- **Y-40, 455 cycles:** roughly 50 min per flag-ON arm. Arms: MAIN (`two1`, V1 reference), NORMAL (`three0`), DEEP (`three1`), DEEP repeat (V3), plus the OSD-sign-OFF control (`two0`-sized, a few minutes) = **about 3.5 h of PC CPU**.
- **Y-2, 232 cycles:** about 25 min per arm, **about 1.8 h**.
- **T-REF on sol:** 60 cycles × Normal and Deep, minutes, sol exclusive.
- The PC must not be busy with the live daemon or heavy browsing, or the abandon count (V4: fail above 5 %) rises. Record the CPU, thread count and whether the daemon was running (Amendment 1, A2).

## 4. Next (nothing started)

1. Freeze the Y-40 selection file (sorted stamps, the rule above, sha256 recorded) and the Y-2 one.
2. V1 and the control first on Y-40 (`MAIN` vs `NORMAL`), then V2/V3/V4, only then the Deep measurement rows.
3. Build under test: `feat/third-pass-deep` `a329cea9` (parent `535661a2`), Windows DLL identical to `f52f8c4b`'s; Replay81 at `c971885a` (local), self-test 12/12.
Needs: the Captain's go on the CPU time (about 5 h on the PC), and whether he wants the full 455 cycles or the 228 subsample.
