# QA: R14 live check, COH-FALLBACK step 4: report (for the Architect's ruling)

**Stamped:** 2026-10-22T17:23Z by `date -u` (17:22:25Z when drafting began). **Build:** `b8fc732e`, `libft8.dll` SHA-256 `aaf6b03e…` (the pin, read at the start and again after the run: equal), shim 20260069, one daemon (pid 37328), 20 m, 14.074 MHz, flag ON from 15:07:28Z to 17:20:50Z. **Spec:** `2026-10-22-1430-qa-r14-live-check-spec-step4.md` (as amended) and the frozen predicates in `2026-10-22-1514-qa-r14-pilot-and-frozen-predicates.md`. **Window scored:** 15:14:56Z to 17:20:50Z. **Numbers:** `results/2026-10-22-coh-fallback-step4-r14-live/scored_run.json`; reader `cf_r14_log.py`. **Aggregates only (HK-037); no callsigns.**

## 1. Verdicts as the frozen predicates read

| Row | Result | One-line reading |
|---|---|---|
| Pre-flight P1–P6 | met (see §5) | |
| Run size | **205 batch-4 cycles among the 502 scored cycles** (206 including the two end cycles; the waiter counted 206 since 15:15Z): the bar of ≥ 200 is **met**. **196** of them fall in cycles whose published set could be reconciled and so are scored by L1a (§3 item 5) | met |
| **L1a** | **FAIL as written** | **0 missing lines** on either service; **6 cycles with an extra line**, identical on both services (§2) |
| L1b (drops) | inference only: **0 missing lines** in 483 reconciled cycles | batch 1 NOT OBSERVABLE |
| L1c (panel) | NOT OBSERVABLE | no WebSocket capture |
| **L2** | **FAIL as written on one event, which I read as a defect of the predicate, not of the product (§4)** | **first live action on a batch-4 decode** |
| L3 | descriptive (§6) | |

I do not choose between the "as written" and "as read" columns. The Architect rules.

## 2. L1a: what failed and what did not

- **Reconciliation of the published set against ALL.TXT:** 483 of 502 scored cycles determined (**0.962**, above the 0.90 bar), 16 unreconciled, 3 ambiguous. Unreconciled and ambiguous cycles are not scored.
- **Missing lines (the delivery question):** **0** for batches 2, 3 and 4, on **both** services, in all 483 determined cycles. Lines are in order. Superseded lines: **0**.
- **Extra lines:** **6 cycles** (the same 6 on both services) have a `late batch 3` or `late batch 4` line where the reconciled set says that batch was not published: cycles 15:23:45, 15:24:45, 16:14:00, 16:14:30, 17:14:45 and 17:16:45. In each, the batch sizes in the log leave **two** subsets whose sizes add up to the ALL.TXT line count (for example, nominal sizes {batch 2: 2, batch 4: 1} and an ALL.TXT excess of 2 fit "batch 2 only" and "batch 2 reduced to 1 by dedup, plus batch 4"). My rule picks the subset that uses the nominal sizes and is wrong when the pump's dedup reduces one batch's size. The services' lines show the batches that really arrived. This is an **instrument limit of the reconciliation I froze**, not a delivery fault, but I cannot prove it from the log; it is consistent with the arithmetic. Under the rule as frozen the row reads **FAIL**.
- The frozen predicate was written for "a missing or extra line" and I do not relax it. **For the Architect:** rule whether L1a reads FAIL as written, or PASS on "0 missing, and the 6 extras explained by an ALL.TXT size coincidence".

## 3. What else is in the data

1. **Batch 4 published in 196 of 483 cycles (40.6 %)** (the pilot's 33 %, the replay's 69.5 %).
2. **R12′:** eligible 69,751, attempted 69,751, CRC-OK 14,324, published 312, abandoned **0** (0 abandoned cycles), edge-published 4.
3. **Workers observed:** 0 (cycles with nothing to do), 1, 5, 8, 14.
4. **Config POSTs during the run, all by API:** flag ON (15:07:28Z), `tx.autoAnswer` (on at 15:15:14Z and by the re-arm job, 34 re-arms), `tx.retryCount` 200 → 3 (16:02:19Z), `externalReporting.targets[0].port` 2237 → 2238 (~15:58Z), an operator abort and `autoAnswer=false` (15:59:26–15:59:41Z), the end-of-window `autoAnswer=false` (16:51:17Z, read back 16:51:21Z), the flag OFF at 17:20:50Z (read back `false`). **No cycle gap and no service restart** around the port POST (39 consecutive 15-second cycles, 15:50:00Z to 15:59Z). The station config now keeps `retryCount` 3 and port 2238; both are the Captain's choices.
5. **Run size:** 205 of the 502 scored cycles had a batch 4 (counted from the `batch4Published=1` lines, independent of the reconciliation), so the bar of ≥ 200 is met on the cycles in the window. **L1a scores 196 of them**: 9 batch-4 cycles fall in the 19 cycles whose published set was unreconciled or ambiguous and are not scored. The reconciled set lists batch 4 in 193 cycles; the other 3 are the extra-line cycles of §2. If the Architect wants the bar read on the scored cycles (196), the run is 4 cycles short; I read it on the window's cycles.

## 4. L2: the first live action on a batch-4 decode

- **Counts.** QSO attempts in the whole window: **34** (the ordinary path, from a batch-1 CQ: 31; **started from a late batch: 3**: two from **batch 2** at 16:10:31Z and 16:40:46Z, and one from **batch 4** at 16:48:16Z). Outcomes of the 34: 8 complete, 1 operator abort, 9 retry-exhausted (7 ordinary, 2 late-batch), 16 ended because the partner was working another station (15 ordinary, 1 late-batch). `applied-immediate` lines: 4 (batches 2, 2, 2 and 4), `applied-deferred`: **0** (so the held-reply path was **not seen live on any batch**), `ignored-answered`: many.
- **The batch-4 action (cycle 16:48:00Z):** the answerer aborted a QSO to Idle at 16:48:15.363Z, the fallback published batch 4 (2 decodes) at **16:48:16.074Z = slot start + 1.074 s**, and the answerer began its transmission at **16:48:16.074Z** (the `TX →` line has the same millisecond as the batch-4 line), which is inside the whole-signal window (≤ 2.36 s). It then transmitted for 12.8 s and logged `late batch 4 applied-immediate` at 16:48:28.895Z.
- **Why the frozen predicate fires:** it takes the **log time of the `applied-immediate` line** as the processing time. That line is written **after the action completes**, and an immediate action includes the whole transmission (12.8 s). So the predicate read 13.9 s after the slot start and called it a defect. By the transmission-start time (16:48:16.074Z, S + 1.07 s) the action was **legal and correctly immediate**. I wrote in the spec that "the log line is written after the action" and sized the tolerance at 50 ms; for an immediate action that was wrong by the length of a transmission. **My error in the spec.** I could not have measured the start time any other way than the `TX →` line, which I did not name.
- **What this establishes (descriptive):** requirement 9 *does* occur live: a CQ found only in a late batch was answered immediately within the guard, once in this run for batch 4 and twice for batch 2. It does not establish the deferred path. It also corrects what I told the Captain and the Architect earlier in the day: "no action on a batch-4 decode" was true at 16:03Z and is not true of the whole run.
- **Rows:** as written **FAIL** (one `applied-immediate` over the guard by the line time); by transmission-start time **PASS-ish: one legal immediate, 0 deferred**, and the rule "PASS needs at least one `applied-deferred`" is **not met**, so the row reads **NOT EXERCISED for the deferral path** either way. The Architect rules.

## 5. Pre-flight read-backs and the deviations

- P1 pins: start (published build) and end both `aaf6b03e…`. P2: flag set by the config API, read back; the before/after config differs in that one value. P3: `osdNhardMax` 24, subtraction on, shim 20260069. P4: WSJT-X not running, one daemon; the answerer and the caller **both** running (L1a/L2 not vacuous). P5: no endurance or R&R run on the PC; the `sol` replay is a separate machine. P6: flag set back to `false` through the API and **read back `false`** at 17:20:50Z.
- **Teardown:** the re-armer ended at 16:51:14Z, **then** `autoAnswer=false` was set at 16:51:17Z and read back `False` at 16:51:21Z (the order the Architect asked for); orphan check at 16:51Z: only the counter script was left; the counter ended at 17:20:39Z.
- **Armed time:** **3,223 s (53.7 min)** from the arm events to the next disarm, from `rearm.log` and the answerer's disarm lines (the window was extended to 16:51:17Z to make up the unarmed gaps; it is under one hour because the answerer disarms on every return to Idle and the re-armer polls every 5 s). The unarmed gaps between a disarm and the next re-arm are under 5 s each; the aggregate is under the hour by the QSO-end-to-re-arm lag, 34 times.
- **Deviations (all Captain-directed, in QA's window, relayed to the Architect):** the auto-answer re-arm job and the extended window (§3); the abort at 15:59:26Z and the re-arm job's stop, resumed at 16:02:19Z; `tx.retryCount` 3; the external-reporting port change (and the loopback defect, issue #251); TX power changed by the Captain on the radio (25 W at 15:10Z, 50 W at ~16:10Z, 5 W at ~16:55Z; QA cannot read it back, so these are his words).

## 6. L3 (descriptive)

| | |
|---|---|
| Batch-4 publish time from decode start | median 2,556 ms, p95 3,001 ms, max 3,173 ms |
| Fallback line after slot start | median 2,607 ms, p95 3,046 ms, max 3,194 ms |
| Reply guard (service-line time > S + 2.36 s) | 259 of 392 batch-4 service lines (**66 %**); this counts the line time, which includes the service's own processing queue; it is **not** the rate at which a reply could not start whole |
| Fallback wall time | median 125 ms, p95 204 ms, max 315 ms |
| Workers | 0, 1, 5, 8, 14 (14 on the busy cycles) |
| Abandoned | 0 cycles |

The 66 % is why the deferred path matters for step 4: batch 4 is usually published after the 2.36 s guard on this machine, so most batch-4 actions would be deferred. **No deferred action occurred**, so that path remains unseen live (unit tests only).

## 7. For the report's reader

- The run is valid for L1a (zero missing lines on both services) and L3, subject to the Architect's reading of the 6 extra-line cycles and of the 7-cycle size question.
- **L2 is not "NOT EXERCISED" as I told the Captain earlier:** there was one legal immediate action on a batch-4 decode, and the frozen predicate mis-scores it. The deferred path was not exercised.
- The controlled test (`2026-10-22-1632-qa-followup-late-batch-engagement-test.md`) is still the way to see the deferred path.
