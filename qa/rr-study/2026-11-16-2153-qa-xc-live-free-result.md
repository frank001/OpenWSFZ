# XC-LIVE-FREE result (QA, 2026-11-16T21:53:00Z `date -u`)

**To:** Architect (spec `qa/rr-study/2026-11-16-1302-architect-to-qa-spec-xc-live-free.md`, `arch/cross-cycle-prior` `50d2ae3c`). **From:** QA. Branch `qa/same-chain`, local, nothing pushed. **Counts only** (NFR-021, HK-037): message text was read inside `qa/xc-build/xc_sup.py` and `qa/xc-build/xc_next_tx.py` and never left them. Night: endurance `20261114_2312_endurance_run` (XC ON, 40 m, `66b3ddf1`), one night, never pooled.

## 0. Verdict in four lines

- **XC-SUP-L passes:** SUP-W **19** of 3,851 publishes = **6.71 per 1,000 cycles** against the bar of 29.
- **FREE is 48.9 %** of the XC publishes (1,884 of 3,851), beside 48.0 % and 54.5 % in the acceptance arms.
- **The instrument can see stale publishes** (V-POS passes on the regenerated first-build control, under both step tables); on the live night's own SUP-W it cannot (6 stepped, UNDERPOWERED).
- **FREE reading: the two frozen tables disagree on the label.** T-G (the spec's example, literal): FREE-OPEN. T-C (the sender's own chain): FREE-OK. **At the upper bounds, FREE stale plus SUP-W is at most 12.6 per 1,000 cycles under either table, against 29.**

## 1. Step 0: how the XC rows were identified (HK-027)

No live tag exists: `owsfz/ALL.TXT` has the plain 9 to 11 columns (message words only), `cycle-archive.csv` has per-cycle counts, the daemon log has `published=` per cycle. **V-ID could not be run.** Route taken: replay of the 2,834 archived WAVs through the shipped build with XC ON (`bin_defaults`, `libft8.dll` pin `bbde6eb6…`, source of `66b3ddf1`; `--xc-defaults 1`, shadow 0; selection hash `8644488047fde86c`, registered before any decode). Read-back (spec section 5) at the start and the end of the arm: `crossCyclePrior` true, shadow false, frozen `xcte=3.076041980658299`, `xctp=2.2220253019230114`, Deep, `nhard` 24, CQ-AP, multi-set, late round, residual candidates, 8 threads, `clock=system`.

**V-REP (descriptive):** replay ON published **3,851** batch-6 rows against the live **3,850** (0.03 % apart); cycles with at least one publish 1,956 against 1,955. The bar (10 %) is the Architect's judgement; far inside it. The replay is offline, so its timing is not the live timing. The ON arm was paused for 1 h 12 m 03 s (17:12:01Z to 18:24:04Z, at the Captain's request, `pause_log.txt`); the one cycle in flight at the pause is not identified and, if its late round saw the pause as elapsed time, it is one cycle in 2,833.

## 2. Step 1: XC-SUP on the live night (`xc_sup.py`, unchanged)

**dt offset, measured on this night (E195/E197):** the 1,946 COR rows' own dt difference has median **0.600 s**, p05 to p95 [0.600, 0.700]; the co-location window is centred on it.

| Class | n | share of 3,851 | SNR median |
|---|---|---|---|
| COR | 1,946 | 50.5 % | -18 |
| **SUP-W** | **19** | **0.49 %** | -18 |
| SUP-O | 2 | 0.05 % | -19.5 |
| **FREE** | **1,884** | **48.9 %** | -19 |

**Row XC-SUP-L:** 19 over 2,832 cycle rows = **6.71 per 1,000** <= 29: **PASS**. (The JSON's `limit: 4` is the first chain's SHADOW rule, not this spec's.) In SUP-W the sender-token pattern is 1 of 19; in the acceptance TEST it was 583 of 641.

## 3. Step 2: the next-transmission check (`xc_next_tx.py`, selftest ALL PASS)

Predicates and **both** step tables were frozen in code and committed (`09fdeaa3`) before the first run. Why two tables: the spec's own example reads "report, then RR73" as AHEAD, which a single global ranking gives (T-G: grid 1, report 2, R-report 3, RRR/RR73 4, 73 5); a caller's own next message after a report is RR73, which the sender's own chain gives as one step (T-C: grid 1, report 1, R-report 2, RRR/RR73 2, 73 3). Neither was chosen after the data.

**Units (live):** 3,851 publishes: 1,251 CQ excluded, 2 non-standard excluded, 1 with no look-up slot, 2 SUP-O (not a class of the spec); **COR 1,342, SUP-W 13, FREE 1,240**. Next transmission found in WSJT-X's ALL.TXT for 1,302 units and nowhere for 1,293 (OWS's matched rows were never needed for the look-up).

**Live night, class counts (stepped = NEXT-OK + AHEAD + BEHIND):**

| Table | Class | NEXT-OK | AHEAD | BEHIND | NONE | stepped | AHEAD share |
|---|---|---|---|---|---|---|---|
| T-G | COR | 657 | 72 | 1 | 612 | 730 | 9.86 % |
| T-G | SUP-W | 5 | 1 | 0 | 7 | 6 | 16.7 % |
| T-G | FREE | 512 | 54 | 0 | 674 | 566 | 9.54 % |
| T-C | COR | 728 | 1 | 1 | 612 | 730 | 0.14 % |
| T-C | SUP-W | 6 | 0 | 0 | 7 | 6 | 0.0 % |
| T-C | FREE | 565 | 1 | 0 | 674 | 566 | 0.18 % |

NONE share: COR 45.6 %, SUP-W 53.8 %, FREE 54.4 %. **NONE is not a false-decode signal and stays unread.**

**V-POS on the live night's own SUP-W: UNDERPOWERED** (6 stepped, bar 20; LV-2 as written fails). Per the spec the control is the first build's SUP-W on TEST. **The control rows were not on file** (`nc.tsv` of `xc-chain/full/ON` was deleted at the 2026-11-14 job close under HK-037; QA error Q78; ledger 78). QA regenerated the arm with the recorded command (`bin_new`, `sel_test_1000.json` sha `d12be505…`, `--xc-prior 1 --xc-shadow 1 --xc-te 3.076041980658299`) and the **regenerated arm reproduced the first chain's counts exactly: 2,579 publishes, SUP-W 641, FREE 1,018, COR 904, SUP-O 16.**

**Control (TEST, first build; 1,000 cycles):**

| Table | Class | NEXT-OK | AHEAD | BEHIND | NONE | stepped | AHEAD share |
|---|---|---|---|---|---|---|---|
| T-G | COR | 288 | 39 | 2 | 318 | 329 | 11.85 % |
| T-G | SUP-W | 35 | 68 | 4 | 465 | 107 | 63.55 % |
| T-G | FREE | 220 | 41 | 2 | 406 | 263 | 15.59 % |
| T-C | COR | 328 | 0 | 1 | 318 | 329 | 0.0 % |
| T-C | SUP-W | 75 | 30 | 2 | 465 | 107 | 28.04 % |
| T-C | FREE | 258 | 4 | 1 | 406 | 263 | 1.52 % |

**V-POS (control):** **PASS under both tables** (n 107 >= 20; T-G 63.55 % >= 3 x 11.85 %, ratio 5.4; T-C 28.04 % > 0 and >= 3 x 0). The bar is the Architect's own; the control is another night and the first build.

**FREE reading, live night (V-POS from the control; FREE and COR from the live night; 10,000 cycle-block resamples, seed 20261116, 95 % percentile interval):**

| Table | FREE minus COR | interval | bar (upper <= 2 pp) | label |
|---|---|---|---|---|
| T-G | -0.32 pp | [-3.53, +2.93] | not met | **FREE-OPEN** |
| T-C | +0.04 pp | [-0.40, +0.53] | met | **FREE-OK** |

**Budget line** (AHEAD excess x stepped FREE, per 1,000 cycles, at the point estimate and at the interval's upper bound; 566 stepped FREE over 2,833 cycles): point estimates 0.00 (T-G) and 0.08 (T-C); upper bounds **5.85 (T-G)** and **1.06 (T-C)**. Added to SUP-W 6.71: **at most 12.6 per 1,000 against 29**, under either table.

**For comparison (control FREE, first build, no parity gate):** T-C FREE minus COR +1.52 pp [+0.35, +3.19]: the instrument does read a stale excess in FREE where one is expected to be larger.

## 4. Read on the two tables (HK-026, HK-025; for the Architect)

- **Precision, not validity, is what T-G fails.** Its COR baseline AHEAD share is 9.9 %, so with 566 FREE and 730 COR stepped rows the interval half-width is about 3.3 pp: **"upper bound <= 2 pp" can be met only if FREE is already about 1.3 pp below COR**; a perfectly clean FREE reads FREE-OPEN almost surely. That row cannot say FREE-OK on this population, whatever FREE holds. (It can still say FREE-STALE, lower bound > 2 pp.)
- T-C has a 0.14 % COR baseline; its interval is narrow (±0.5 pp), so its row can fire either way. Its price: it misses a one-step-ahead stale (S sent M', XC published M, S repeats M'), the case the spec's section 7 already names.
- QA does not choose a table for the label after the data. What is solid under both: V-POS passes on the control; FREE minus COR on the live night has a point estimate at about zero (-0.32 and +0.04 pp); the upper bounds cost at most 5.85 and 1.06 per 1,000.

## 5. Predictions (Architect's table, scored by the Architect at ruling time; QA's reading of the rows)

| id | prediction | QA's reading |
|---|---|---|
| LV-1 | XC-SUP-L passes | **hit** (6.71 per 1,000) |
| LV-2 | V-POS passes with this night's own SUP-W (n >= 20) | **miss** (6 stepped); it passes on the control |
| LV-3 | FREE-OK | **mixed:** FREE-OK under T-C, FREE-OPEN under T-G (the spec's literal table); the Architect scores it |
| LV-4 | FREE share in [45 %, 60 %] | **hit** (48.9 %) |

## 6. Limits

One live night; its chain is not the acceptance nights' chain. The replay's XC rows are a proxy for the live ones (equal in count to 0.03 %, not matched row by row). 1,251 of 3,851 XC publishes are CQ and are outside the check. About half of every class has no next transmission in WSJT-X's log (NONE). The control is another night, the first build. T-G and T-C were both computed; the label depends on the table.

## 7. Pending (does not block this reading)

The XC-OFF arm of the live night (shipped build, same selection) is running as an identity cross-check only: ON minus OFF should differ in batch 6 alone. Its result will be added here when it ends. Working files are KEPT under `D:\Projects\claude\_qa-scratch\xc-live-free\` (`README.txt` there; Captain's rule 2026-11-16).

## 8. Instrument record

Scripts `qa/xc-build/xc_live_free_replay.sh`, `xc_live_free_chain.sh` (`307a4574`, `ad88e5f6`), `xc_next_tx.py` (`09fdeaa3`), `xc_sup.py` (unchanged). ON arm: `libft8.dll` pin `bbde6eb6…` in both harness builds, 8 threads, read-back ok at the start and at the end of both arms. Filter / selection lines: ON: `--selection sel_full.json` (sha `8644488047fde86c`, run `20261114_2312`, stratum FULL); CTRL: `sel_test_1000.json` (sha `d12be505…`, run `20260808_0016`, stratum FULL). QA errors this arm: Q78 (spec inputs not checked), Q79 (OFF arm's arguments not exercised); ledger 79.
