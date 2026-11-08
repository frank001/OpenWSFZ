# COH-MULTISET (levers L1 + L2) — if G and today's fallback both fail on a WSJT-X-decoded signal, how many more become correct decodes from four further coherent bit-metric sets, and what do they cost in wrong payloads?

**QA report to the Architect.** Main extraction 2026-10-24 13:00:48Z → 13:05:44Z; V4′ replay 13:44:06Z → 14:32:36Z; V1(b) diagnostics and the noise leg afterwards (`date -u`). Spec `2026-10-24-1240-architect-to-qa-spec-coh-multiset.md` (branch `arch/coh-multiset`) with Amendment 1 (A1.1–A1.10). `BAR_L` = 0.5 pp, ratified by the Captain 2026-10-24 12:50:57Z before any real-audio decode, FROZEN. The Captain's go for the run: "go, run it on the PC".

**Scope (verbatim):** *Offline, Python, at WSJT-X's own positions on one 40 m night. Extraction and decode only; candidate search, subtraction, the managed layer and the live path are not exercised. WSJT-X's AP is off on this station. A gain here is an upper-side estimate for a build: the fallback in production starts from our own candidate positions, not WSJT-X's.*

## Verdict: **L1-GO**, W-FAIL does not fire (the ruling is the Architect's: `2026-10-24-1436-architect-coh-multiset-ruling.md`)

**NET_X = +2.115 pp of WSJT-X's decodes, 95 % CI [+1.937, +2.302]** (N = 26,190 rows in 975 sampled cycles, 974 of them with rows; cycle-block bootstrap, block = 8 sampled cycles, 122 blocks, B = 10 000, seed 20261024). `CI_lo` 1.94 ≥ `BAR_L` 0.5, so **L1-GO**.

**X** (the first of C1 > J2 > J3 > N1, fixed in advance, with a CRC-valid BP-only output) was consulted on **7,498 rows** (G and C3 both returned no CRC-valid payload, A1.1) and returned **554 right and 15 wrong**: **f_X = 2.64 %, Wilson 95 % [1.60 %, 4.30 %]**. The same night's **f_C3 = 3.02 %** (C3 on rows where G gave no output: 1,478 right, 46 wrong; the COH-GAIN figure 0.284 is shown beside it and is not the bar, A1.2). `CI_lo(f_X)` 1.60 % < 3.02 %: **W-FAIL does not fire.**

**Denominator.** N counts all 26,190 WSJT-X rows; the 1,842 rows the vendored encoder cannot pack (1,593 hashed-call token, 249 other) are credited zero. 24,348 rows were evaluated.

## All validity rows PASS

| row | result |
|---|---|
| **V1** pins | PASS: `libft8.dll` SHA-256 `aaf6b03e…26aef` (shim 20260069, the deployed v0.62 build; native unchanged to `main` `5a9667ee`) equal at the start and end of the main run; the ms_*.py scripts and the git HEAD (`96aa80d4`, tree clean) equal at start and end. OSD sign fix set 1 and **read back 1**. **nhard 24 cannot be read back** from this build (no decode-params getter). Substitute (a): the harness sets `ft8_set_decode_params(10, 0.10, 24)` and the V4′ replay log reads back `nhard=24` at both ends. Substitute (b) **PASS**: see below. |
| **V1(b)** every OSD accept has nhard ≤ 24 | PASS: `ft8_get_last_osd_diag` over `ft8_decode_all` on the 975 sampled cycles, same DLL and settings: 16,543 decodes, **48 OSD accepts (store not truncated), max nhard 16, 0 above 24; 7,153 reason-0 nhard-cap rejects** (the cap bites), 0 reason-1 rejects. **Limit:** that diagnostic does not record `ft8_ldpc_decode_llrs` (ft8_shim.h:1139-1140), so it cannot read QA's G arm; the Architect checked that the G gate (decode.c:1034) and the candidate gate (:727) read the same process-global `s_osd_nhard_max` (decode.c:77), so this shows the cap in force for the run. Output committed `d1f7d906` before it was evaluated. |
| **V2a** synthetic decode | PASS: the same 200 Q-prefix isolated signals as COH-GAIN V2 (−14 dB, off-lattice): C1, J2, J3, N1 each 200/200 (bar ≥ 0.99); C3 200/200. |
| **V2b** mutation | PASS: with the identity Gray map J2 and J3 each decode **0/200** (bar ≤ 0.50). Coverage: C1 and N1 are not mutated; their bit map is tied to the build through V3 (C3 contains the order-1 map). |
| **V3** C3 matches the build | PASS: first 300 rows, Python C3 vs `ft8_coherent_fallback_at`: BP outcome agrees 300/300 (206 outputs each, rightness equal on all 206), (df, dt) estimate equal 300/300, max \|dLLR\| 0.00195 (descriptive). Bar per A1.5: ≥ 299 and ≥ 297. |
| **V4′** control reproduces (A1.10 = COH-GAIN Amendment 3) | **PASS: G success on P1 = 0.9547** (P1 = the 15,240 rows the batch-labelled replay matched in batch 1; bar 0.90, unchanged). The replay's per-cycle WSJT-X line count equals the row list's `ws_load` in every cycle (0 mismatches). |
| **V5** determinism | PASS: a second fresh process over the first 300 rows, 0 differing fields (timing excluded). |

**V4 as first built FAILED and was replaced by the spec's own V4′.** QA built `live_hit` from the live OpenWSFZ ALL.TXT instead of a V4′-style replay: G success on those 18,907 rows was 0.770 against 0.90 (QA ledger Q15; a harness error against the spec text). The Architect ruled V4′ (A1.10) and asked that nothing be scored or cited until it passed; it did. V4′'s descriptives confirm the cause, as in COH-GAIN: G reads **0.46 %** of the 3,658 rows the replay matched only in batch 2+ (residual-pass decodes) and **0.52 %** of the 5,434 rows the replay did not match; the replay's batch-1 share of its matches is **80.6 %**.

**Run conditions of the V4′ replay.** Clean checkout of `main` `5a9667ee` in `_qa-scratch`, Replay81 built with every `Has*` property of that build except `HasDxped` (absent on `main`); mode `three1` (Deep, subtraction ON), 8 threads, nhard 24, sign fix 1, **coherent fallback flag ON (as shipped since f684277f)**, Test B rule, 0 deadline-abandoned cycles, no competing process (the Captain closed WSJT-X for it). Readbacks at both ends: Deep, nhard 24, `osdSignFixRead` 1, shim 20260069, `cohfb` True.

## What the arms show

| arm | rows | notes |
|---|---:|---|
| **G** (shipped, best of 9 cells, BP then OSD) | right 14,594 of 24,348 evaluated; CRC-valid output 15,326 | **732 rows with a CRC-valid output that is not the row's text** (not consulted) |
| **C3** (V3 coherent, BP only; run where G is not RIGHT) | 9,754 run; output 2,054; right 1,484 | on G-no-output rows: 1,478 right / 46 wrong |
| **X** (consulted rows) | 7,498 | 554 right, 15 wrong; **earlier-wrong-blocks-later-right: 0** |

- **Which set supplies X's first successes (fixed order C1 > J2 > J3 > N1):** C1 11, J2 262, J3 210, N1 71 (J2 + J3 = 472 of 554 = 85 %). First-wrong by set: C1 3, J2 5, J3 3, N1 4.
- **Order-free ("right at all" on consulted rows):** C1 11, J2 269, J3 401, N1 177; **any set right on 554 rows**. Overlap of the four sets (C1 J2 J3 N1, 1 = right): `0001` 71, `0010` 196, `0011` 14, `0100` 64, `0101` 11, `0110` 115, `0111` 72, `1000` 1, `1001` 2, `1010` 1, `1101` 4, `1111` 3. J3 alone is the biggest single contributor; N1 adds 71 rows nothing else reads.
- **Strata** (cuts from all sampled rows). SNR terciles (cuts −12, −3 dB): NET_X 2.71 / 2.39 / 1.29 pp (f_X 3.0 / 1.9 / 3.3 %). Load quintiles (cuts 23, 27, 29, 33 WSJT-X decodes per cycle): NET_X 2.53 / 2.30 / 2.02 / 1.87 / 1.95 pp (f_X 1.8 / 2.2 / 4.8 / 2.4 / 2.8 %). The gain is largest on the weakest and lightest-loaded rows, unlike COH-GAIN's C3, which gained in crowding.
- **Wall time** (median CPU per row): G 0.078 s, C3 0.047 s, the four sets together 0.031 s on consulted rows.
- **Sanity line, never a result:** G ∪ C3 over G on this night +5.67 pp [5.29, 6.05] (COH-GAIN post-hoc +5.25).

## L2 (OSD on coherent bits; descriptive, closed by the Architect at this reading)

C3 + OSD (shipped gate) over C3 BP-only on the consulted rows: **+19 right, +1 wrong** (+0.07 pp of N). X with OSD: 561 right / 15 wrong vs 554 / 15 BP-only. Per set, OSD adds C1 16 right / 0 wrong, J2 7 / 1, J3 5 / 0, N1 1 / 0. For scale: COH-GAIN's C3O at `nhard` 40 was +0.26 pp (25 true, 34 wrong).

## Noise leg (descriptive; HK-026: it has read 0 at every setting tried, so it bounds gross failure only and cannot rank sets)

200 pinned NHARD-REP noise WAVs (per-file SHA-256 verified; label NHARD-REP-PC, indices 1–200), 10 seeded positions each (seed 20261024; carrier uniform 500–2500 Hz, ws_dt uniform −0.3…0.8 s, anchor t = ws_dt + 0.7), 2,000 positions. **CRC-valid outputs: 0 for every arm** (G, C3, C1, J2, J3, N1; BP-only and BP + OSD). It shows no gross false-decode channel; it says nothing about the per-set wrong rate on real audio (the wrong share above is the measure, and it includes genuine co-channel stations).

## Faults and the row count (Architect's requests)

- **16 fault rows** (of 24,348 evaluated; at most 0.06 pp): **one kind only.** `ft8_extract_llrs_at` returned **−3 (frequency outside the export's band)** on the lattice cells of rows at **113–134 Hz (13 rows) and 3,106–3,107 Hz (3 rows)**. Fifteen rows had all 9 cells fail, one (134 Hz) 6 of 9. **There were no codeword/row mismatches.** The run continued for each (C3 ran); **11 are in the consulted population, 5 are not.** G cannot read these rows at all, so they are G-no-output rows by construction; counted, not dropped.
- **975 selected cycles, 974 with rows:** the sampled cycle at index 1, stamp `261022_194915` (the second WAV of the night), has **no WSJT-X Rx line** (the start of the run; WSJT-X had not decoded yet). No sampled cycle that has WSJT-X lines lacks an encodable row.

## Method notes and findings along the way

- J2/J3/N1 were written from the Architect's prose method only; no WSJT-X code was opened (licence policy; Captain 2026-10-24: method only). Tests: grouping (J2 14 pairs + 1 single per half, J3 9 triples + 1 pair per half, no Costas symbol, no straddle), clean-signal decode of all four sets, identity-Gray mutation, magnitude-of-sum, N1 bounds, the shared-estimate path reproduces the extractor's own V1 (9 tests), the gates (7 tests) and V4′ (5 tests).
- `live_hit` in `main_rows.csv` (Test B against the live ALL.TXT) is kept as a column and is **not** the control; V4′ is.
- One QA error in this arm (ledger Q15, above) and one self-caught test expectation (Q14).
- Selection: night `20261022_1949`, `owsfz/wav`, sample = index mod 3 == 1 (975 cycles, even/odd slots 488 / 487, Q-GATE-2 PASS), pilot = first 100 of mod 3 == 2 (not pooled; used for the anchor-offset check only: median(OWS_DT − WS_DT) = 0.700 s on 1,869 exact matches, PASS; the timing pilot was not run).

## Pins, build and instrument (HK-022)

Exact filter: none (Python scripts, no test filter); tests run with `python -I`. Pins: DLL `aaf6b03edb8eea1933bf7ab71d4c0bc4e67af214d9834c9030de769cc1826aef` actual = pinned, at the start and end of every process; `selection.json` SHA-256 (LF) `f521a1de8bc76531b13748caaeebaea91a8c1474ed9fbd18005ad46a2fa1ee7f`; `rows_sample.json` SHA-256 (LF) `ee825bdd807c740127d9009c1e7598490a55a29b735ae2256890e34d8d838036`. Commits (all local on `qa/refset`, not pushed): `31821058` selection, `c9054883` metrics, `a5a28071` delta and structure, `96aa80d4` harness freeze (+ V2, V3), `fe3dfed2` main outputs, `167ddd07` V4′ matched output and manifest, `1d172b18` V4′ evaluation, `d1f7d906` V1(b) output.

## Not done / limits (travel with every figure)

- **Positions:** the rows are WSJT-X's, not our candidates; in production the fallback works from our candidate positions and its F1b gate, so a build's gain will be smaller (the fallback went from +5.25 at positions to +3.82 in replay).
- **Scope:** one 40 m night, one band; no subtraction interaction (a new decode in production is also subtracted, which this arm does not see).
- **Wrong payloads** include genuine co-channel stations; f_X is an upper bound on false decodes. The false-decode gate for a build is the replay with the U′ instrument, not this arm.
- **732 G-wrong rows** (G returned a CRC-valid payload that is not the row's text) are counted and not consulted (A1.1); C3's and X's costs are measured only on rows where G returned nothing.
- **The joint metrics are QA's implementation of a prose method:** V2a/V2b show they decode clean signals and break when mis-mapped; they do not show the result is identical to WSJT-X's, and that is not the aim.
- **nhard 24 cannot be read back** from this build; V1(a) and V1(b) are the substitutes, and V1(b) cannot instrument the G arm itself (see V1(b) above).
- Not run: the timing pilot (not needed for the ruling); the 16 fault rows' frequencies lie outside the export's band (113–134 Hz, 3,106–3,107 Hz).

## Architect predictions, facts for the ledger (scoring is the Architect's)

X1 NET_X point ≥ 0.5 pp: +2.115 (yes). X2 L1-GO at BAR_L 0.5: yes. X3 J2 + J3 more than half of X's first successes: 472 of 554 = 85 % (yes). X4 W-FAIL fires: no. X5 C3 + OSD ≤ 0.3 pp over C3 BP-only: +0.07 pp (yes). X6 V2a passes first time for all four sets: yes (200/200 each).

## Files

`qa/rr-study/results/2026-10-24-coh-multiset/`: `selection.json`, `rows_sample.json`, `rows_pilot.json`, `delta_and_structure.json`, `v2.json`, `v3.json`, `main_rows.csv`, `main_pins.jsonl`, `main_run_info.json`, `v5_rows.csv`, `result.json`, `v4p_manifest.json`, `v4p_matchedbatch.csv`, `v4p.json`, `osd_diag.csv`, `osd_diag_info.json`, `osd_diag_eval.json`, `noise.json`, this report. Code in `qa/rr-study/coh-multiset/` (`ms_select.py`, `ms_metrics.py`, `ms_run.py`, `ms_gates.py`, `ms_v4p.py`, `ms_osd_diag.py`, `ms_noise.py`, `v4p_run.sh`, `ms_delta_structure.py` and the tests). Message text and per-row working files stayed in `D:\Projects\claude\_qa-scratch\coh-multiset\` (HK-037); every committed file holds numbers, stamps and indices only.
