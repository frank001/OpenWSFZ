# The S6 quick-tier dry run on `sol`: the plumbing works; OpenWSFZ goes blind after a busy cycle on this CPU (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-13 18:40Z (`date -u`). **Go:** the Captain, in the QA window: "do the the 19-minute S6 trial run now."
- **Dry run, not a baseline, informational.** Nothing filed, nothing pushed. Run folder `qa/rr-study/results/2026-10-13-64246e4-LINUX-sol-S6-QUICK-DRYRUN/` (`report.md`, `s6/`: `s6_result.json`, `s6_validity.json`, `collapse_check.json`, `s6_figure.png`). The recording-derived log slices (real callsigns) stay on `sol` in `~/qa-scratch/s6-2026-10-13-64246e4/`, outside git.
- **Label (your rule):** AMD FX-8350, `subtractionMaxThreads 8` on 8 logical CPUs (the station value, not auto: auto would give 6), subtraction deadline ON, WSJT-X decoding on the same CPUs. A drop on the capture path would be SILENT (no counter or log line exists). Nothing here is claimed about the default set-up, either way.

## What ran (pins)

| item | value |
|---|---|
| Attempt 1 | 17:57:24Z, ABORTED 18:04Z. The Captain saved the daemon's Settings page at 18:01:38Z (`audioDeviceId` nulled, defect #233; `suppressSynthetic` true; capture stopped). Config restored by QA. The same collapse had already begun before the save (slot 18:00:15 gave 12 decodes, the next four gave 0). Folders kept as `_ABORTED-s6dry1-*` on `sol`. |
| Attempt 2 (this note) | launched 18:06:27Z, 72 plays 18:09:15Z to 18:28:30Z, supervisor DONE 18:29Z; nobody touched the daemon's settings. |
| Build | `main` `76aa48cd` v0.57, shim 20260060, `libft8.so` `e8132650…` equal at start and end (S6-V5); WSJT-X 2.7.0 exe `2f968b2f…` pinned; corrected ALSA chain |
| List and corpus | `s6-wavlist.json` `8e406fd5…`, tier quick (24 WAVs × 3 = 72 plays, 4 batches, 3 idle slots), corpus verified (S6-V1) |
| Code on `sol` | synced from `qa/refset`; the last fixes (`ad72ff4e`, `2991392d`) were applied after the run, see "Tooling faults" |

## Validity rows

| row | result | note |
|---|---|---|
| S6-V1 corpus and list verified | PASS | |
| S6-V2 offsets, strays, double slots | PASS | all 72 plays at +0.000 s, 0 slots with two plays, 0 stray lines. **Caveat: the offset is the player's own call time against the boundary, not the sound's onset; it cannot fail by design of the clock.** Onset latency (aplay → codec → loopback) is not measured; leg E step (i) found lead 0.0 read DT 0.0 on this host, which is the only evidence. |
| S6-V3 mechanical warm-up | PASS | first attempt: WSJT-X 1 line, OpenWSFZ 1 line |
| S6-V4 plays completed | PASS | 72 of 72, 0 slips |
| S6-V5 pins equal start/end | PASS | library and WSJT-X executable both pinned |

## The collapse, whole run (item 3 of your request)

Daemon log, 81 cycles from 18:08 to the end (`collapse_check.json`; "late" = the cycle's log line more than 3 s after its slot end):

| measure | value |
|---|---|
| cycle-grid realignment warnings | **71** (56 positive: 28 from +7.161 s to +0.388 s, 27 from +6.968 s to +0.468 s, one more at +0.297 s; **15 negative**, from −4.831 s to −1.341 s) |
| step of `wanted` per warning (positive crawls) | −0.239 to −0.259 s, `applied` always 3,000 samples |
| late cycles | 32 of 81 |
| residual passes / abandoned | 27 / 4; median pass 3.5 s; abandoned at 10.0 to 11.3 s (the budget is 11.7 s) |
| slots where WSJT-X has rows and OpenWSFZ has none | **43 of 70** slots that have any row |
| rows | WSJT-X 1,361, OpenWSFZ 235 (17.3 %) |
| drop / overflow / xrun / underrun / stall lines in the daemon log | 0 |

**Episodes** (each started by an abandoned residual pass):

| trigger pass (end UTC) | elapsed | fitted signals | first late slot | late cycles | then |
|---|---|---|---|---|---|
| 18:09:41 | 10,242 ms | 11 | 18:09:30 | 16 | crawl 7.161 → 0.388 s; OpenWSFZ decodes again from 18:14:00 |
| 18:16:56 | 10,043 ms | 12 | 18:16:45 | 15 | crawl 6.968 → 0.468 s; decodes again from 18:21:30 |
| 18:23:43 | 11,296 ms | 11 | 18:23:30 | 1 (lag 11 s) | **negative crawl −4.831 → −1.341 s (15 warnings)**; decodes again from 18:26:45 |
| 18:27:40 | 10,478 ms | 11 | (run ends) | | one small warning at 18:27:45 |

A fourth abandoned pass (18:27:40) began a fourth episode as the run ended. The third episode is different in kind: its lag (11 s) is above the CycleFramer's 8.2 s backlog ceiling, and the error that follows has the opposite sign, which fits audio discarded beyond the ceiling and then overshoot. Your two readings stand: the offset is real (it falls by exactly the applied amount), and the drops are silent (no counter, no log line).

**When OpenWSFZ is not blind it works:** in slots 18:14:00 to 18:16:30 and 18:21:30 to 18:23:15 it logged 150 of 232 WSJT-X rows (65 %), in line with the 71.7 to 74 % of the replay readings.

## The S6 figures (do not cite: they measure the collapse)

24 WAVs, 439 signals; WSJT-X within-appraiser consistency (own universe) 93.2 % [90.7, 95.4]; OpenWSFZ 0.0 %: **no signal was decoded in all three trials, because which trial was blind decided it**; positive agreement 17.5 % [10.6, 25.1]; decodes per WAV 17.65 (WSJT-X) against 3.10; SNR delta −1.96 dB over 222 matched pairs; κ 0.013; ANOVA 0 parts (no balanced part: the block reports it, no crash). Hashed rows per play 1.24 and 0.15.

## The two design numbers (as you asked, both quoted from data)

1. **Offset tolerance ±0.25 s:** observed min 0.000, max 0.000 s. It is a call-time figure (see V2); a real bar needs the sound's onset, which this harness does not observe.
2. **Daemon-log attribution floor 90 %:** observed **26 of 72 plays = 36.1 %**, so abandonment read UNKNOWN. This is by construction, not a time-zone error (the system offset +2 h equals the inferred +2 h): **a residual pass runs on only some cycles (27 passes in 81)**, so most plays have no pass line to attribute. **Proposal:** define the share on the pass LINES (lines that map to a play slot over lines in the window): **26 of 27 = 96.3 %** here, and read "no line" as "no pass ran". At 36 % of plays the sensitivity over no-abandoned WAVs would be empty anyway on this host.

## Thread count (HK-020) and what I overstated

`subtractionMaxThreads` is 8 in the sol R&R config (the station's read-back; the first reference-set run used the same 8); `Resolve(8, 8)` = 8; the daemon does not log the effective count. My earlier "8 fit threads at 100 %" was an inference; a `top -H` snapshot during the plays showed jt9 at 99.9 % of a core, one .NET worker at 96 %, arecord 13 %.

## Tooling faults found by this dry run, all fixed in code (`qa/refset`)

1. An S6-only run crashed in the S1–S8 analyser (no `truth.csv`): now skipped, with its own report header.
2. A killed player left no `s6_validity.json` and crashed the analysis: now VOID.
3. **My `batch_plan` rows broke the log split (`KeyError: 'slot_stamp'`): the S6 lines (real callsigns) stayed in the run folder's log copies, and the analysis then read VALID on empty slices.** Found only by checking the run's own copies; I completed the split and the analysis by hand on the intact data (the numbers above are from that), the copies now hold 0 lines, and the analysis now voids a block whose slices are missing or empty. The tests did not combine the two cases; they do now. **A first, empty "VALID" report existed for about 4 minutes on `sol` and was never copied anywhere.**
4. The block's CPU label is now built from the run's own read-back.

## For your ruling

1. The offset check (V2 a): keep as a call-time check, or measure onset?
2. Attribution share: re-set on pass lines (96.3 % here)? A bar value is yours.
3. The route: S6 on `sol` as it runs today measures the collapse. Options already put to the Captain: first on the Windows PC; on `sol` with fewer fit threads (a replay-style override); fix the old-CPU path first.
4. `sol` is free; the old-CPU profile is queued; the S6 scratch (`~/qa-scratch/s6-*`, `~/rr-run/owsfz-ALL.TXT`, `~/rr-run/cycle-audio`, the gathered captured audio) is deleted at S6 job close, not yet.
