# QA: R14 pilot result and the predicates frozen before the scored run

**Stamped:** 2026-10-22T15:16Z by `date -u` (checked 15:14:34Z when the pilot was read). **Spec:** `2026-10-22-1430-qa-r14-live-check-spec-step4.md` as amended (`1334bbec`, P4 `376f251b`). **Build:** `b8fc732e`, `libft8.dll` `aaf6b03e…` (the pin), shim 20260069, one daemon (pid 37328), station config untouched except the one value below.

## 1. Pre-flight read-backs

| | Read back |
|---|---|
| CAT | `catConnectionStatus: Connected`; dial set to 14.074 MHz at 14:50:21Z through `POST /api/v1/tune`, read back 14.074 three times in the next 12 s (the daemon polls the rig every second) |
| Flag | `decoder.coherentFallbackEnabled` set `true` at 15:07:28Z through the config API; the before/after config differs in that one value only |
| Decoder | `osdNhardMax` 24, subtraction on; shim 20260069 |
| WSJT-X | not running (P4, the Captain via the Architect) |
| TX power | set to 25 W **by the Captain, on the radio** (his word in QA's window, 2026-10-22 ~15:10Z). The daemon has no rig-power control and QA cannot read it back. |

## 2. Pilot (receive-only, auto-answer off; 15:07:30Z to 15:14:00Z)

26 cycles in the window, 24 scored (the two end cycles are dropped). 8 batch-4 cycles. Both services logged `late batch N no-match` lines.

**Finding (the reason for the pilot).** The R12′-style counts in the log **over-count** what is published: in the cycle 15:12:45 the third pass logged `newDecodes=1` but **no batch 3 was published** (ALL.TXT held batch 1 plus batch 2 only, 22 lines = 19 + 3), and neither service logged a batch-3 line. So "a count greater than 0 in the log" is not the same as "the pump published a batch", because the pump publishes only when a decode is left after the earlier batches' dedup. Read the way the amended spec wrote it, L1a would have called a correct run a FAIL (it did, on the first try, for this cycle).

## 3. Frozen predicates for the scored run (nothing here changes after the scored run starts)

- **Published set per cycle** = the unique subset of {2, 3, 4} whose nominal sizes (`residualDecodes`, `newDecodes`, `Coherent fallback … published=`) sum to **the cycle's ALL.TXT line count minus batch 1's count** (`Cycle … N decode(s) found`). ALL.TXT is the unfiltered record of what the pump published. A cycle where no subset, or more than one, fits is listed as **unreconciled / ambiguous** and is not scored. ALL.TXT is read for the stamp (first 13 characters) only; nothing else leaves the function (HK-037).
- **L1a** (script `cf_r14_log.py`): per running service, per scored cycle, the sorted batch numbers of its non-superseded `late batch N` lines equal the published set, in order; superseded lines reported separately. PASS needs every scored cycle to match for both services **and** a **coverage of ≥ 0.90** of the cycles with a determined published set. *Where 0.90 comes from:* the pilot reconciled 23 of 24 scored cycles (0.958); one in 24 unreconciled is tolerated, more than 10 % is not read (INCONCLUSIVE). FAIL = any scored cycle with a missing or extra line.
- **L1b** (channel drops): inference only, option (i) (the Captain, via the Architect): a missing `late batch N` line in L1a. **Batch 1 is NOT OBSERVABLE.**
- **L1c** (panel): the pilot did **not** capture the panel's WebSocket frames, so the panel leg is **NOT OBSERVABLE** in this run. The ALL.TXT leg is used as the reference of what was published, so it is not an independent delivery check. The report says so.
- **L2** (script): defect = batch-4 `applied-immediate` logged later than cycle start + 15 s + 2.36 s + 50 ms (file log, millisecond timestamps); within ±50 ms listed, not scored. PASS = both services running, ≥ 1 `applied-deferred` on batch 4 and no defect; NOT EXERCISED otherwise; never a pass without a deferred action.
- **L3**: descriptive, from the same script (batch-4 time from decode start and after the slot start, reply-guard misses, `fbWallMs`, workers, R12′ counters, abandoned cycles).

## 4. The scored run

- **Window:** starts when this note is committed; the daemon stays as read back above. Ends at **200 batch-4 cycles**, with a floor of **90 minutes** (spec §2). *Projected, not measured:* the pilot's batch-4 rate was 8 of 24 = 33 % (the replay's was 69.5 %), so 200 batch-4 cycles would take about 600 cycles = **about 150 minutes**; the 90-minute floor is not the limit.
- **Auto-answer (TX policy B, the Captain, 2026-10-22 ~15:10Z in QA's window: "an hour will be fine"; "if you are going to reply to CQ turn power to 25W minimum, don't change anything else"):** `tx.autoAnswer` set to `true` through the config API for **one hour, inside the run**, read back, and set back to `false` and read back at the end of the hour. Nothing else in the TX settings is changed.
- **End of run (K8):** flag set back to `false` through the API and read back; `autoAnswer` false; the daemon left on 20 m unless the Captain says otherwise.
- **No overlap:** no endurance or R&R run is active on the PC; the `sol` replay is a different machine.
- **HK-037:** counts and times only; the daemon log and ALL.TXT are never copied out.
