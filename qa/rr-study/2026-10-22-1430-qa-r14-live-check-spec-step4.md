# QA: R14 live check for COH-FALLBACK step 4 (spec for the Architect's (k) review; the Captain gives the go)

**Stamped:** 2026-10-22T14:30:09Z by `date -u`. **Build under test:** `b8fc732e` (`libft8.dll` SHA-256 `aaf6b03edb8eea1933bf7ab71d4c0bc4e67af214d9834c9030de769cc1826aef`, shim 20260069). **Answers:** Architect §19 A19.4. Nothing here has run.

**Amended 2026-10-22T14:32:47Z (`date -u`) after the Architect's (k) review, §20 K4–K8:** L2's correction adopted (K4, ledger E23); superseded lines excluded from the L1a count and reported separately (K5); L1a widened to batches N = 2, 3, 4 with the live-log source of each published count, and batch 1 stated NOT OBSERVABLE under (i) (K6); both services must be running, else NOT EXERCISED (K7); no overlap with endurance/R&R runs, no pooling, flag back OFF and read back at the end (K8, rows P5 and P6). L1c stays an unscored 10-cycle pilot, which is itself a live flag-ON run and needs the Captain's go (both goes can be given together).

## 0. What the daemon log actually records (HK-027), read from `b8fc732e`

Read from the source of the pinned build, not remembered. This decides what L1 can and cannot be.

| Question | What exists | Consequence |
|---|---|---|
| Did the fallback publish a batch 4, and when? | **Yes.** One `Coherent fallback: … batch4Published=0/1, batch4PublishMs=…` line per cycle with the fallback on (`Ft8Decoder.cs`), plus `fbStartMs`, `fbWallMs`, `workers`, `abandoned`, `published`. The time is from the decode's own start. | L3 fallback wall time and R12′/abandon counters are readable as they are. |
| Did each QSO service **receive and process** the batch? | **Yes, as an inference.** Each service writes `QsoAnswererService: late batch {N} {Outcome}.` / `QsoCallerService: …` once per supplementary batch it processes, **including `NoMatch`** (`ProcessLateBatchAsync` → `LogLate`). The line carries the batch number and the outcome, **not the cycle**. | Delivery to a service is countable per batch 4. The cycle must be matched by log order and time. |
| Was a batch **dropped** from a QSO channel? | **No record at all.** `QsoBatchQueue.TrimmingWriter.TryWrite` discards the oldest items with `reader.TryRead(out _)` and returns the inner `TryWrite` result, which is `true` on a DropOldest channel. There is **no counter and no log line**. (The only drop counters in the daemon are for the capture channel and the archive.) | "0 channel drops" **cannot be observed directly**. It can only be inferred from a missing `late batch 4` line. |
| Did the **panel** get the batch? | Not in the daemon log. ALL.TXT gets the unfiltered rows appended under the cycle's stamp, with **no batch number**. | The panel leg needs either a WebSocket capture or a per-cycle count comparison (see L1c). |
| Which cycle / what time did a service act at? | The `Cycle hh:mm:ss: N decode(s) found` line is written at batch 1 (`elapsed` is time to batch 1). Log lines carry millisecond UTC timestamps. | The service-side processing time is the log timestamp of the `late batch` line. |

## 1. Pre-flight (fail closed; any miss stops the run, nothing is scored)

| # | Check | Source of the expected value |
|---|---|---|
| P1 | `libft8.dll` SHA-256 equals the pin, **at start and at end** | the pin above (`b8fc732e` build) |
| P2 | `decoder.coherentFallbackEnabled` set **through the config API** and read back `true`; no hand edit of the station config (HK-035: the config POST is an overlay on `main`; confirm on this build before relying on it) | read back from `GET` after the `POST`, at start and at end |
| P3 | Deep, `nhard` 24 and the OSD fix read back, at both ends | `Decoder.Depth=Deep`, `nhard=24`, shim 20260069 / OSD fix as in the replay's V2 |
| P5 (K8) | The flag-ON window overlaps **no endurance or R&R run**, and its data is **never pooled** with flag-OFF data (flag ON is its own era) | the run's start and end times against the board's running jobs |
| P6 (K8) | At the end of the window the flag is set back to **OFF through the API and read back `false`** | read back from `GET` after the `POST` |
| P4 | Station: one daemon only, the live audio chain as in the 10-20 Stage 2 live work; the services' state recorded (answerer / caller active or not, auto-answer on or off, TX enabled or not) | recorded, not asserted |

## 2. Size and duration

**≥ 200 cycles with `batch4Published=1`** (the Architect's decision value, kept).
- *Where the cycle count comes from:* on the replay, 668 of 961 cycles published a batch 4 (69.5 %). 200 such cycles need about 290 slots, **about 72 minutes**; at the replay's rate. The live rate on a different night and band is unknown, so the run ends when the **count of batch-4 cycles reaches 200**, with a floor of **90 minutes** so that a quiet band cannot end it early.
- *What it does not give:* L2 is the row that needs QSO activity (below). 200 cycles is a size for L1 and L3, not for L2.

## 3. Rows

### L1 — delivery (PASS / FAIL, mechanical)

Predicates are fixed before the run. A cycle with `batch4Published=1` in the R12′ line is a **batch-4 cycle**.

- **L1a (service delivery, observable now; amended by §20 K5/K6/K7).** The channel is DropOldest, so a drop caused by a batch 4 loses an **earlier** batch. L1a therefore covers **N = 2, 3 and 4**: for each service, the count of `late batch N <outcome>` lines, **superseded lines excluded**, equals the count of cycles that published batch N, and the lines follow their publication in order, within the same slot. Lines carry no cycle, so cycles are matched by order and time.
  - **Where the published count comes from (live log, read from `b8fc732e`):** batch 4 = the R12′ line `Coherent fallback: … batch4Published=1`. Batch 3 = the line `Third pass: newDecodes={N} … outcome=…` with `newDecodes > 0`. Batch 2 = the line `Sub-feas residual pass: residualDecodes={N} …` with `N > 0`. The pump publishes a supplementary batch only when it has at least one decode (`batch.Count > 0`). **Open until the pilot:** whether `newDecodes`/`residualDecodes` equals the published count exactly (e.g. after the noise filter). The 10-cycle pilot checks this and L1a's batch 2/3 predicate is **frozen from what it shows**.
  - **Superseded lines (K5):** `SupersedeDeferred` writes a second `late batch N superseded` line at a later batch 1. They are **not** counted as deliveries; they are counted and **reported separately** per service, so that a superseded line cannot hide another cycle's missing line.
  - **Batch 1 (K6):** the services write **no line per batch 1** (only a warning in an unexpected state; `ProcessBatchAsync`). Under option (i) a batch-1 drop is therefore **NOT OBSERVABLE**, and the report says so.
  - **No vacuous pass (K7):** both the answerer and the caller must be **running**. `ProcessLateBatchAsync` logs a no-match outcome even when the service is Idle (`QsoAnswererService.cs:1276–1294`), so this holds under option A (receive-only) as well. A service that is not running reads **NOT EXERCISED**, for L1a and for L2. L1a is **PASS** only when every running service meets the predicate for N = 2, 3, 4; **FAIL** = any published batch with no matching line; **NOT EXERCISED** = a service not running.
- **L1b (channel drops).** Reads **only as L1a's missing lines**; there is no counter (§0). *Decision for the Captain, with its consequence:* either (i) accept inference, at no cost, knowing a drop and a slow service look the same at the end of a run, or (ii) have a **Developer add a drop counter and a log line to `TrimmingWriter`** (an HK-011 change, small, and it makes capacity-10 verifiable in every later run, not just this one). I recommend (ii) because the capacity change is the core R14 risk and today it cannot be audited; (i) works if the Captain prefers to run first. The row reads as written under (i) unless he picks (ii).
- **L1c (panel and ALL.TXT).** *Not yet specified as a mechanical row:* the daemon log has no panel record, and ALL.TXT has no batch mark. A **10-cycle pilot** (flag ON, no scoring) is needed first to find out whether the panel's WebSocket frames carry a batch identity and whether per-batch counts can be recovered. L1c's predicate is written from what the pilot shows and **frozen before the scored run starts**; until then L1c is not a row. If neither source can tie a decode to batch 4, L1c reads **NOT OBSERVABLE** and is reported as such, not as a pass.

### L2 — acting without deferral (defect if it fires; NOT EXERCISED otherwise)

**Correction to the §19 wording that I need the Architect to look at.** On the replay, batch 4 published **before 2.36 s from the decode start in 26 of 668 cycles (3.9 %)** (min 1.64 s, p5 2.46 s, median 3.35 s). A batch that lands inside the whole-signal window may legally be acted on **immediately**; `CanStartWhole(now, cycleStart)` is `now ≤ S + 2.36 s`. So "any action without deferral" would call a legal case a defect.

- **Predicate:** an `AppliedImmediate` line for batch 4 whose **log timestamp is later than `cycleStart + 15 s + 2.36 s`** by more than 50 ms is a **defect** and blocks default ON. `cycleStart` is taken from the `Cycle hh:mm:ss` line of that cycle. Lines within 50 ms either side of the boundary are **listed, not scored** (the log line is written after the action).
- **PASS** = both services running, at least one `AppliedDeferred` on a batch-4 decode (shows the deferral path is exercised) and zero defects. **NOT EXERCISED** = a service not running, or no `AppliedImmediate` and no `AppliedDeferred` on batch 4 in the run. It is never a pass. Under option A (receive-only) L2 reads NOT EXERCISED by construction and rests on the unit tests and the code review, which the Captain decides knowingly.
- **How likely is it to be exercised?** On the replay, 280 batch-4 decodes began with `CQ` (aggregate count only), in 242 of 961 cycles (25 %), and 270 of those 280 were confirmed by WSJT-X. So a service that auto-answers will meet a batch-4 CQ in about a quarter of the cycles. Whether it *acts* depends on its state and settings.
- *Decision for the Captain, because this involves transmitting:* **A) receive-only**: the services are present but TX is off or no auto-answer. L1 and L3 are fully scored; **L2 reads NOT EXERCISED by construction**. **B) auto-answer on air** for a bounded window inside the run (the Captain names it): L2 can be exercised, with the cost that the station transmits on 40 m. I do not choose this; it is his decision.

### L3 — descriptive only (no bar)

- Batch-4 time from slot start (live offset): `batch4PublishMs` is from the decode start; the live offset comes from the `Cycle` line's timestamp against the slot start.
- Reply-guard misses: batch-4 cycles whose service-processing time exceeded `S + 2.36 s` (a count and a rate).
- Fallback wall time under live load: `fbWallMs` (median, p95, max) next to the replay's 215 / 352 / 532 ms. **The PC is the machine the replay's SG2 was scored on**; if the live station differs, say so.
- R12′ counters: `eligible, attempted, crcOk, published, abandoned, publishedEdge`; `abandoned` per cycle against V5's 5 %.

## 4. Reading rules

- HK-037: the run produces **counts and timings only**. Message text is never copied out of the daemon log or `ALL.TXT`; the log-reading code prints numbers. Any per-message working file stays under `D:\Projects\claude\_qa-scratch\<job>\` and is deleted at job close.
- HK-022: the L1 result answers only "the log shows a line"; it does not show the panel received the batch (L1c) nor that nothing was dropped (L1b under (i)). The report says which.
- HK-039: the live run is an acceptance launch for `b8fc732e`; the review record for `b8fc732e` is committed (`2026-10-21-1740-qa-code-review-coh-fallback-step4-db3d7df5.md`).
- Nothing is run, pushed or merged on this note. The go to run the build live with the flag ON is the Captain's.

## 5. Open items for the Architect's (k) review

1. **L2 wording** (above): the legal-immediate case, 3.9 % on the replay.
2. **L1b**: inference versus a drop counter (a Developer change); my recommendation is the counter.
3. **L1c** is a deliberate gap: a 10-cycle pilot fixes its predicate before the scored run.
4. **The run's TX policy** (option A or B) is the Captain's.
