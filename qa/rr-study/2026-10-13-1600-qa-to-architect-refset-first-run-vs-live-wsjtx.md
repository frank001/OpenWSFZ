# First reference-set run, scored against live WSJT-X on identical audio, with the burst check (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-13 16:00Z (`date -u` 15:55Z at the last data read). **Go:** the Captain, in the QA window: "can you finish the report first?" Analysis only, no new decoding.
- **Descriptive, not a ruling.** Supplements `2026-10-12-1925-qa-to-architect-refset-first-run-result.md` (which held only leg A against live OWS and leg D against A). A NEW SERIES (Linux, FX-8350, replay-only budget override). Never pool with Windows or any other series, and never difference it against the live endurance matched share. Nothing filed, nothing pushed.
- **Label (amendment 9):** "first run, OpenWSFZ legs only (A, D, B); leg E pending". Not an S6 run and not a build-to-build baseline until leg E has run (the Captain stopped the leg E run on 2026-10-12; its design is open).

## What was scored (HK-022 pins)

| item | value |
|---|---|
| Source pass | `first-run-76aa48cd-standard`, 33 of 33 blocks, 1,056 scored cycles, 4 bands (17, 20, 40, 80 m), warm-up cycles never scored |
| Build | `main` `76aa48cd` (v0.57) + replay-only budget override (unlimited); native SHA-256 `dc517dc9ba88b78618535fcf9da4ad8bcf3db18cfd4a68e186459520bd618e6c` = the pin of the first run |
| Scripts | `qa/rr-study/refset/harness/score_vs_wsjtx.py` (`1c090411`), `burst_check.py` (`95fc4b5d`); both read the stored working files on sol, aggregates out |
| Outputs | `results/2026-10-12-refset-first-run-76aa48cd-LINUX-sol/vs-live-wsjtx.json`, `burst-check.json` (scanned for callsign shapes, none) |
| Match rule | sm_01 key, paired in order within a cycle; hashed rows reported separately (rendering depends on history, out of scope per amendment 4) |
| Orientation | matched share = share of WSJT-X's live rows that OWS reproduced; OWS-only = OWS rows left unmatched. Cycle-clustered CIs |

WSJT-X's live rows are the station's own `ALL.TXT` for the recorded cycles: 19,934 rows, 18,854 non-hashed. They include WSJT-X's own false decodes, so a share of them is **not** a share of truth.

## Headline

| leg | what it is | non-hashed matched share | OWS-only |
|---|---|---|---|
| **B** | OWS decoding the WSJT-X-side recording (identical audio to WSJT-X) | **74.0 % [73.1, 74.9]** (13,945 / 18,854) | 972 (5.2 % of WSJT-X's rows) |
| **A** | OWS decoding its own recording (the product view) | **73.7 % [72.8, 74.6]** (13,888 / 18,854) | 973 |

All rows by key (hashed included): B 73.5 % [72.7, 74.4], A 73.2 % [72.4, 74.1]. **A and B agree to 0.3 pp, so the capture route is not what separates the two decoders here; the gap is in the decoder.** This is the answer to the Captain's "decoding difference on identical input", obtained from data already decoded.

## Where the gap sits (leg B, non-hashed)

| split | result |
|---|---|
| By WSJT-X SNR (≤ −20 / −19..−15 / −14..−10 / −9..−5 / ≥ −4 dB) | 31.6 / 48.5 / 67.8 / 78.2 / 90.3 % |
| By band | 80 m 84.9 %, 17 m 76.8 %, 40 m 72.2 %, 20 m 67.3 % |
| By crowding, live row count (≤ 10 / 11–20 / 21–30 / > 30) | 82.7 / 80.5 / 73.4 / 66.7 % |
| By crowding, **union** row count (≤ 10 / 11–20 / 21–30 / > 30) | 83.5 [81.3, 85.8] / 80.6 [79.3, 81.9] / 73.9 [72.5, 75.1] / 66.9 [65.5, 68.4] % |

The gap grows with weaker signals and with a busier band. The **crowding trend survives re-binning by the union count**, which removes the dependence on WSJT-X's own count: the four shares change by 0.2 to 0.9 pp, so it is not an artefact of binning. The 4-cell SNR × crowding table is in `vs-live-wsjtx.json` (`snr_x_crowding`): at every SNR band the share falls as crowding rises, for example −9..−5 dB: 92.9 / 83.8 / 81.1 / 69.1 %.

## The OWS-only rows are bursty (the burst check)

A burst cycle is a leg B cycle with at least 3 OWS-only non-hashed rows (definition fixed before reading the result).

- **104 of 1,056 cycles are burst cycles and carry 883 of the 972 OWS-only rows (91 %).** 5 of 33 blocks hold any burst; 4 of them are 20 m.
- **103 of the 104 are one source night, `20260803_live_run_1713` (20 m)**; 1 is from `20260930_1930_endurance_run-gathered` (40 m). By UTC hour: 19 h 32, 06 h 32, 04 h 27, 00 h 12, 05 h 1. 16 runs of consecutive burst cycles, the longest 32 (two blocks are burst in every cycle).
- **In burst cycles live WSJT-X has a median of 9 rows against OWS's 18** (non-burst cycles: 18 against 14). In 35.6 % of burst cycles live has fewer than half of OWS's rows, against 0.3 % elsewhere. Several burst cycles have live WSJT-X at 0 to 3 rows while OWS finds 4 to 10.
- Sensitivity (**post hoc**, not a headline): without the burst cycles the leg B matched share is 73.8 % [72.9, 74.7] (from 74.0), and **OWS-only falls from 972 to 89 (0.49 % of WSJT-X's rows)**.

**Reading.** The matched share and the crowding trend stand. The OWS-only figure (5.2 %) is almost entirely one night in which live WSJT-X decoded thinly. Whether those rows are real decodes that WSJT-X missed, or WSJT-X's live decode was starved (depth, load, settings: its `.ini` for that night is not recorded; the build was `1ff4293` with uncommitted changes and OWS nhard 60), is **not shown**. Per your ruling the OWS-only count is always reported in two forms: all nights, and excluding `20260803_live_run_1713` ("WSJT-X live decode thin, cause unknown").

## What this does not show

1. Not truth: WSJT-X's live rows contain WSJT-X's own false decodes, and OWS-only rows are unclassified (real or false unknown).
2. One build, one platform (FX-8350, 8 threads, deadline removed), the standard-tier prefix of one frozen corpus: 33 blocks of 32 scored cycles; 17 m and 80 m are single-run, 17 m is hum-heavy, 10 m is absent.
3. The live WSJT-X rows come from the live run, not from a replay, so WSJT-X's own repeatability (leg E) is unknown. A matched share of 74 % is one WSJT-X realisation against one OWS realisation.
4. Leg A used the live path's recording, leg B the WSJT-X-side recording, both on the same decode settings; neither is the live early/final decode path.
5. Rendered hashed text is out of scope; hashed rows are counted by key only.

## Open, for your review

1. The keep-up question (the residual pass is slower than the cycle on this CPU, median 18.8 s) is unchanged from the 19:25 note and still replay-only.
2. The ~70 min single-replicate WSJT-X run on the 4 burst blocks plus the 3 busiest blocks would test whether live WSJT-X was thin on 0803 by load or by settings. It needs the Captain's go; nothing is armed.
3. Citation guard for the board: cite 74.0 % [73.1, 74.9] as "OWS reproduces this share of live WSJT-X's non-hashed rows on identical audio, one build, sol, standard-tier prefix", with the OWS-only figure always in both forms.

## Files

- On this PC: `qa/rr-study/results/2026-10-12-refset-first-run-76aa48cd-LINUX-sol/` (`aggregate.json`, `status.json`, `pins.jsonl`, `LABEL.md`, `vs-live-wsjtx.json`, `burst-check.json`). Per-message working files stay on sol in `~/qa-scratch/refset-first` until job close, then are deleted (HK-037).
- Commits on local `qa/refset`: `1c090411` (score_vs_wsjtx), `5106b7bc` (leg E tooling), `95fc4b5d` (burst_check). Not pushed (HK-033).
