# COH-RES-CAND v2 spec: QA (k) review, 2026-11-12T13:4xZ (`date -u` 13:44:44Z at the last check)

> **Correction 2026-11-12 (the Architect's E165; QA ledger Q59):** this record labelled several replay nights "20 m". The dial frequency in each night's WSJT-X log (second column, `ALL.TXT`) is **7.074 MHz (40 m) for every replay night on file** (`20260922_2056`, `20260925_2010`, `20260930_1930`, the `20261004` to `20261028` runs and `20261110_1817`); only the live station session of 2026-11-10 was on 20 m. The band-shift caveat in this record is therefore withdrawn; what remains is a night-to-night and configuration difference. Edited where it lives; the original wording is in the git history.

**To:** Architect · **From:** QA · **Spec:** `qa/rr-study/2026-11-12-1340-architect-to-qa-spec-coh-res-cand-v2.md` on `arch/coh-res-cand-v2` `0d1e0948` (read with `git show`, branch not checked out here).
**Verdict: ACCEPT WITH THREE AMENDMENTS.** The design (add, do not replace; one gate fitted before the build; test on a night it was not fitted on) is sound and the row set is nearly mechanical. Three things need your rows before Stage 0 runs: **K1** (the FEASIBLE row fires about 54 % of the time with no information), **K2** (a failed validity row reads OPEN, not VOID), **K3** (the 40 m U′ question, answered below, and the trigger as written misses a component that is above 2×). Nothing was built or run beyond desk checks on files on disk.

## Your four requests

### 1. The frozen Stage 0 feature list (frozen HERE, before any feature has been computed against a class)

The per-row fields on disk are the columns of `nc_dump.tsv`, written by `qa/rr-study/sub-feas/replay81/Program.cs:585`: `stamp, kind, matched, freq, dt, snr, same_any, min_df, wcount, path, text`. Read for columns 0 to 9 only; text stays in memory (HK-037).

| # | feature (fixed order) | source column | form | the build can compute it at publish time? |
|---|---|---|---|---|
| F1 | `snr` | col 5 | integer dB | **yes**, the row's own published SNR |
| F2 | `dt` | col 4 | seconds, written with 2 decimals (`F2`) | **yes**; the gate compares the value rounded to 2 decimals, as the harness writes it |
| F3 | `freq` | col 3 | integer Hz | **yes**, the row's own published frequency |

**Not admitted, with the reason:**
- `kind`: constant 4 in P0 by construction.
- `path`: **constant 2 for every kind-4 row** (A: 1,370 of 1,370; B: 1,441 of 1,441, checked). It carries no information.
- `matched`, `same_any`, `min_df`, `wcount`: derived from the WSJT-X lines. Your spec excludes them, and the build cannot compute them.
- `text`: not a numeric feature.
- Per-cycle fields in `coh.csv` (`eligible`, `attempted`, `crc_ok`, `sets`, `walk_entered`, `crc_c1`…): per cycle, not per row, so they cannot separate rows inside one cycle. A cycle-level gate is a different design. **No multi-set id per row exists in the dump**, so that branch of your CV-1 reasoning cannot be tested at Stage 0; it would need a harness change and a re-run, which breaks "no new runs".

**Why only three.** Every feature added multiplies the candidate gates and raises the chance-FEASIBLE rate in K1 below. Three features × two directions × the observed thresholds is the family K1 is calibrated on.

### 2. #272's folders are intact; counts re-derived

- `_qa-scratch\coh-res-cand\crc_result.json` SHA-256 prefix **`2b53b412366ce250`**, equal to the report's.
- `raw\{A,B}` and `scratch\{A,B}\nc_dump.tsv` all present. Rows: A **10,330**, B **10,401**, so B − A = **71** = 150 B-only − 79 A-only texts, equal to the report's descriptive line.
- **P0 re-count (new text in B's kind-4 rows against A's rows of the same cycle): 149 rows; 119 with `matched` = 1 (class C); 30 with `matched` = 0.** The script asserts 149 and 119 (`qa/rr-study/coh-res-cand-v2/p0_null.py`).
- 🟡 **Not re-derived today: the 19 / 9 / 2 split of the 30.** It needs `crc_analyse.py`'s `instrument()` (re-encode and tone test against the WAVs), and re-running that writes to the reference result's folder. It is step 1 of Stage 0: re-derive it into a NEW output path, and stop if it differs from 19 / 9 / 2 (your rule).

### 3. Arm A's U′ on this 40 m night, beside the values on file (all of them 40 m too)

Instrument: `cf_uprime.py off` (T = 0.276 frozen, blob asserted), on `_qa-scratch\cq-ap\arms\OFF\{nc.tsv, testb.csv}` (the CQ-AP OFF arm, 500 cycles with WSJT-X lines), pinned DLL `bbde6eb6…6528`, WAVs through a junction (artefact folder untouched). Output `_qa-scratch\cq-ap-u0\uprime_off_40m.json` (SHA-256 prefix `9dc1dcdb1716b47b`).

| night | band | cycles | **U′0 total** per cycle | tested_absent | hashed/unencodable | untestable class |
|---|---|---:|---:|---:|---:|---:|
| `20260922_2056` (step-4 OFF, committed) | 40 m | 960 | **0.186** | 0.0375 | 0.141 | 0.008 |
| `r-f4-second-night` OFF (committed) | 40 m | 799 | **0.288** | 0.0663 | 0.219 | 0.003 |
| **`20261110_1817` (arm A, today)** | **40 m** | **500** | **0.558** | **0.136** | **0.422** | 0.000 |

- **By your rule as written** ("more than 2× the highest value on file"): 0.558 / 0.288 = **1.94×, which does NOT trigger** (the trigger would be 0.576). It misses by 0.018.
- **The component the bar is about is above 2×.** U-OK / U-FAIL are on tested_absent. Today's tested_absent is **0.136, which is 2.05× the highest value on file (0.0663) and 3.6× the lowest (0.0375)**. Hashed calls are 0.42 per cycle, about 2× the values on file.
- **Null check:** this night's own null p99 is 0.293 against T = 0.276, a difference of 0.017 (limit 0.03). No exit-4 flag; the instrument is usable here.
- 🟡 **Limit:** I read the two committed OFF figures. Other nights on file (for example the COH-GATE-G train/test nights) were not re-read; the "highest value on file" may be higher than 0.288. **I read the number as a reason for you to rule on the bar before arm B, not as proof either way (K3).**

### 4. Timing, corrected from QA's own stamps (`cq-ap/arms/chain_status.txt`)

| arm | cycles | start | end | wall |
|---|---:|---|---|---:|
| OFF2 | 500 | 17:23:43Z | 18:05:34Z | 41.9 min |
| OFF | 500 | 18:05:35Z | 18:45:35Z | 40.0 min |
| ON | 500 | 18:45:36Z | 19:27:32Z | 41.9 min |
| REF | 50 | 19:27:33Z | 19:31:35Z | 4.0 min |

The whole CQ-AP chain took **2 h 08 min**, not the 3.5 h planned. **Arm B should take about 42 to 46 min** (500 cycles at about 5 s, plus a third fallback run of perhaps 0.3 to 0.5 s per cycle, which is 3 to 4 min). **B-OFF (40 cycles) is about 3.5 min.** Replace "about 1 h" and "about 1 h 15 min PC" with about 50 min and about 1 h. Stage 0's compute is seconds (P0 and the null above ran in under a second); the desk time is the record writing.

## (k) findings (HK-021 / HK-025: validity vs precision, both branches)

### K1. FEASIBLE fires about 54 % of the time when the features carry no information. AMENDMENT REQUESTED.

**Method.** P0's 149 rows with their real `snr`, `dt`, `freq` values. Labels permuted at random, 119 C / 19 TA / 11 other (a permutation breaks any real link between feature and class, so no real class was related to a feature). For each permutation, the spec's selection rule over F1-F3, both directions, every observed threshold: admissible iff `kept_TA ≤ 4`, take the largest `kept_C`. 5,000 draws, seed 20261112 (`p0_null.py`).

| null result | value |
|---|---:|
| **P(kept_C ≥ 40 with kept_TA ≤ 4)** | **0.544** |
| null `kept_C` median / 90th / 95th / 99th percentile | 41 / 53 / 56 / 66 |

**Reading.** Taking the best of 326 gates (13 distinct `snr`, 20 `dt` and 130 `freq` values in P0, two directions each) on 19 TA rows will find one that keeps 40 C rows at ≤ 4 TA more often than not, even if no feature carries any signal. FEASIBLE as written is therefore weak evidence: it says "a Developer session and a build are justified" about as often when the features are noise as when they are not. It is **not** decorative (a real separator also fires it), so I do not refuse the row. I do ask that it not be the only condition.

**Amendment proposed (your choice; a mechanical form of each):**
- **(a) permutation-calibrated bar (recommended).** FEASIBLE iff `kept_C ≥ 40` **and** the permutation p-value of the chosen triple's `kept_C` is ≤ 0.05 (5,000 draws, seed 20261112, the same family, computed in the Stage 0 script). On today's null that is `kept_C ≥ 56` (47 % of the C rows at ≤ 4 of 19 TA).
- **(b) keep 40, state it.** Accept that FEASIBLE justifies the build 54 % of the time on noise, and let Stage 2 do the filtering. Cost of a false FEASIBLE: one Developer session, one HK-039 review, about 1 h of PC.
- **(c) a smaller family.** Freeze one feature only (for example `snr`, the one with a physical reason to separate wrong payloads) and keep 40. That is a different, smaller test and I have not computed its null.

**Power caveat on (a):** I have not looked at how well any feature separates the real classes (that waits for your ruling and the frozen list). If the real best gate keeps, say, 45 C at 4 TA, (a) reads NOT-FEASIBLE and (b) reads FEASIBLE. Under (a), "NOT-FEASIBLE" means "not distinguishable from chance at n = 19 TA", which is a statement about the 19 rows, not about the lever.

### K2. A failed validity row reads OPEN. AMENDMENT REQUESTED.

Your verdict: ACCEPT iff all rows pass; FAIL iff N-STOP or U-FAIL; OPEN otherwise. **If a validity row fails (B-NAT, B-OFF, B-WIRE, B-KEEP, B-DUP) while N-GO and U-OK pass, the verdict is OPEN and goes to the Captain with the numbers.** A broken arm (for example B-KEEP failing means "add, don't replace" did not hold) is not an open question; it is an invalid arm. Proposed: **VOID** iff any validity row fails (the arm is repeated after a fix, no precision row is read), then FAIL / ACCEPT / OPEN over the precision rows only (N-GO, N-STOP, U-OK, U-FAIL, B-AB, B-LATE). Both branches of each row evaluated: B-NAT, B-OFF, B-WIRE, B-DUP, B-KEEP are validity (no outcome of NET or U′ changes whether they must hold); N-GO, N-STOP, U-OK, U-FAIL, B-AB, B-LATE are precision.

### K3. The U trigger. AMENDMENT REQUESTED (and, I think, your ruling before arm B).

See request 3. By the letter the trigger (total U′0 > 2× the highest value on file) misses by 0.018, but the tested_absent component, which is what U-OK / U-FAIL test, is 2.05× the highest and 3.6× the lowest value on file. I propose the trigger read on **tested_absent**, the bar's own quantity, in the same amendment. The bar 0.021 is a per-cycle ΔU′ (B's new outputs), not a level, so a higher baseline does not mechanically move it, but the hashed share (0.42 per cycle) is about twice that of the two nights read. [Corrected: every night on file is 40 m, so "never checked on a 40 m night" does not hold and the difference is night to night, not a property of the band.]

### Smaller points (no amendment unless you want one)

- **B-KEEP's hash exception** is a predicate and must be code at the freeze: "same freq and dt" is exact-equality on the harness's rounded values (freq integer Hz, dt 2 decimals); I will write it so and list every excepted row.
- **The U′ classes "frozen from arm A".** I have run the same instrument on arm A as a descriptive check today (testable classes: `report`, `report CQ`; `untestable_class` = 0). The frozen classes JSON in the Stage 2 freeze is a separate, committed run; today's output is not it.
- **Night and configuration shift is confounded with fitting (there is no band shift).** The gate is fitted on #272's night (`20260930_1930`, R-F4 and L1′ OFF) and tested on another 40 m night (both ON). `snr` and `freq` distributions differ from night to night, so a Stage 2 FAIL cannot separate "overfit to 19 rows" from "does not transfer". You say this in the fitting-risk paragraph; I only note that no descriptive line in §3 would separate the two, and I suggest adding the gated-in rows' SNR distribution beside P0's.
- **CV-1's multi-set branch** is untestable at Stage 0 (no per-row set id in the dump); see request 1.

## What QA holds and will do

- **Kept for v2 (your request):** `_qa-scratch\cq-ap\arms\OFF` (including `nc.tsv`, 12,036 rows = D_OFF) and `_qa-scratch\coh-res-cand\raw` and `scratch`. Deleted at v2's job close. New scratch from today: `_qa-scratch\cq-ap-u0\` (U′0 output and a junction to the artefact WAV folder; no message text written).
- `spots_raw.jsonl` and its secured copy: not needed by v2. I have **not** deleted them (the Captain secured them on 2026-11-10); deletion stays at CQ-AP's job close.
- **Next, on your amendments:** Stage 0 (step 1: re-derive 19 / 9 / 2 into a new path, stop if different; step 2: the frozen features above; step 3: the selection rule once), then the Stage 0 record before any Stage 1 work, and the Captain's go for the Developer session. Nothing of QA's is running.
