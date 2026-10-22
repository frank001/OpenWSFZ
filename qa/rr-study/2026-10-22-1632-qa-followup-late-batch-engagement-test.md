# QA: possible follow-up for decode improvement: does the QSO engage correctly on a decode found only in batch 3 or batch 4?

**Stamped:** 2026-10-22T16:32:27Z by `date -u`. **Status:** a possible follow-up, **not blocking the step-4 merge** (the Captain, in QA's window, 2026-10-22 ~16:30Z: "a useful test, but not blocking the merge atm"). Nothing here is scheduled or run. **Build the question concerns:** `b8fc732e`, and the late-batch logic already on `main` (batches 2 and 3).

## 1. The question

The answerer is built to act on a decode that appears **only in a late batch** (the residual pass, the third pass, and from step 4 the coherent fallback's batch 4). It does so in three states (`QsoAnswererService.cs`, `HandleLateIdleAsync`, `HandleLateWaitReportAsync`, `HandleLateWaitRr73Async`):

| State | A decode found only in a late batch… | If the reply can start whole in this slot (`now ≤ cycle end + 2.36 s`) | Otherwise |
|---|---|---|---|
| Idle | a CQ that batch 1 did not give (only if auto-answer is on and the cycle has not already caused a transition) | `applied-immediate` | `applied-deferred`: the reply is held and sent in the next own-parity slot |
| WaitReport | the partner's report, or an early RR73/RRR | as above | as above |
| WaitRr73 | the partner's RR73/RRR | as above | as above |

The batch number is stored only for the log line; the logic does not distinguish batch 2, 3 and 4.

## 2. What is already known (so the follow-up is not asked twice)

- **Unit tests** cover the late-batch paths (`LateBatchQsoTests`, `LateBatch4Tests`, `LateBatchReplayTests`).
- **R14 live run, 2026-10-22 (descriptive, from the daemon log, counts only):** 14 answer attempts, all started from a batch-1 CQ. Late-batch lines: 28 on batch 2, 13 on batch 3 and 15 on batch 4 were `ignored-answered` (the cycle had already caused a transition); one `applied-immediate` on batch 2; **no `applied-deferred` on any batch**, so the held-reply path has **not been seen live**, and **no action on a batch-4 decode**. Outcomes: 4 completed, 8 timed out in WaitReport, 1 in WaitRr73, 1 operator stop.
- **How rarely the Idle case arises naturally:** on the 2026-09-22 night (961 selected cycles), 242 cycles had a CQ in batch 4, but **no cycle had a CQ only in batch 4** and **one cycle** had a CQ only in batches 3–4 and none in batches 1–2. The mid-QSO case (a partner's weak reply found only by a late pass) is the likelier real engagement, and the log of a live run cannot say how often it happened without reading message text.

## 3. What a follow-up test would answer

1. A decode found only in batch 4 (and, separately, batch 3) is **acted on** in the three states above.
2. When the guard fails (batch 4 is the latest batch, so it fails more often than batch 2), the reply is **held and sent in the next own-parity slot**, not truncated and not lost.
3. A held reply is **superseded correctly** by a later batch-1 event.

It would not answer whether the fallback decodes are correct; that is the replay's job (D-GO′, U′).

## 4. Outline of the test (to be specified and (k)-reviewed before it runs)

- **Rig:** a second, separate daemon on its own port with a copy of the station config: CAT off, external reporting off, **no RF path** (transmit audio to a device that reaches nothing). **The no-RF property is proven first, from the source and from a dry run, or the test does not run.** It runs after the R14 run, so that it cannot spoil the live timings.
- **Input:** short FT8 test audio with synthetic `Q`-prefix callsigns only (NFR-021): one cycle type with a single CQ weak enough that only the fallback finds it (batch 4), one that only the third pass finds (batch 3), one with the partner's report weak enough to be found late (mid-QSO). Decoding a weak signal is probabilistic, so each type is repeated over many cycles and the result is a count per outcome (`applied-immediate`, `applied-deferred`, `no-match`), not a single pass.
- **Reading:** from the daemon file log (millisecond times) and the transmit-side event, counts and times only (HK-037).
- **Pass/fail bars:** written before the run, each with where its number comes from (HK-038). The deferral bar needs a measured rate of "batch 4 arrives after 2.36 s" from the live R14 log.

## 5. Cost and risk

A second daemon, the test audio (a modulator exists in `qa/rr-study`), a proof of no RF, and station CPU after the R14 run. The risk is on-air transmission by mistake, which is why the no-RF proof is the first step and a hard gate.

## 6. Decision

Not blocking the merge. The Architect may pick it up under decode improvement; if the Captain wants it, it goes to QA with a go for the second daemon and for the test audio.
