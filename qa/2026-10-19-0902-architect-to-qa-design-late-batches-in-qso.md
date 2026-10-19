# Design: batch 2 and batch 3 decodes in the QSO answerer and caller (Architect → QA)

- **To:** QA. cc Captain. **From:** Architect. **Date:** 2026-10-19 09:02Z (`date -u`).
- **Requirement (the Captain's, via QA, 2026-10-19):** batch 2 and batch 3 decodes are valid decodes and are used in a
  QSO, by the answerer and the caller.
- **Code read:** `origin/main` `0c7124db`: `DecodePump.cs` (l.59–71, 142–163, 186–238), `QsoAnswererService.cs`
  (l.104, 576–613, 650–800, 1064–1182, 1270–1370), `QsoCallerService.cs` (same structure, l.660–1110),
  `DecodeBatch.cs`, `Program.cs` l.345–362.
- **For QA:** turn this into a Developer spec (HK-015). It is a `src/` change (HK-011). QA may refuse rows on (k) grounds.
- **Docs only.** `src/` and `native/` diff empty.

## 0. Facts the design rests on

| # | fact | source |
|---|---|---|
| F1 | Each service handles batches **serially**, and `TransmitAsync` **awaits the whole transmission** (about 12.64 s) | `QsoAnswererService.TransmitAsync`, the caller likewise |
| F2 | In a Wait state, batch 1 with no match calls `RetryOrAbortAsync` at once. It retransmits in the next slot and sets `_skipNextRetry = true` | answerer l.1143–1144, 1270–1305 |
| F3 | So batch 2/3 of cycle N would arrive **during** our retry transmission in N+1. They would be read only when it ends (~28.7 s after N's start), and today's code would treat them as **the next cycle**. They would consume the `_skipNextRetry` guard, and N+1's batch 1 would then count as a missed response. That is QA's point (b), made concrete | F1 + F2 |
| F4 | A transmission started late is **truncated**, not rejected (D-CALLER-021). After the cycle's 2.36 s guard it no longer fits whole | `Ft8TimeHelper.ClampSampleCountToWindowBoundary` |
| F5 | **2.36 s = 15 s − 12.64 s** (79 symbols × 0.16 s). A start later than this into the slot cannot send a whole FT8 signal | `CycleFramer.cs:367`, dossier #122 |
| F6 | The answerer and caller channels have capacity **2, DropOldest**. With 3 batches per cycle and one 12.64 s transmission, 2 are already queued: one slow cycle drops a batch 1 | `Program.cs:345, 351` |
| F7 | `_lastIdleDecodeBatch` is **replaced** by every idle batch (QA's point (a)) | answerer l.657 |
| F8 | Timing (QA): batch 2 is a median of 3.0 s (p90 4.7) after batch 1 on sol, and batch 3 about 1.5 s later. **So a late decode usually misses the slot that follows it.** On faster machines it sometimes won't | QA, 2026-10-19 |

## 1. The rule in one sentence

**A late decode counts as heard. It may cause any transition a decode causes. It never counts as a cycle. Its reply
goes in the next own-parity slot that can still start within 2.36 s.**

## 2. Design decisions (QA's questions 1–4)

### D1. A batch carries its number (Q2: neither merged nor counted as a new cycle: *supplementary*)

- `DecodeBatch` gets `int BatchNumber`, defaulting to 1. Every existing constructor call stays valid.
- `DecodePump.PublishSecondAsync` also writes batches 2 and 3 to the answerer and caller channels, as it already does
  to external reporting.
- **Only a batch 1 is a cycle.** Merging is rejected: it would mean holding batch 1 until the cycle's last batch, which
  gives up the 17.36 s answer deadline that two-stage publishing exists to protect.
- **Channel capacity rises from 2 to 8** for the answerer and caller (DropOldest kept). That allows two cycles of three
  batches with room to spare. Where 8 comes from: 3 batches × 2 cycles + 2 spare, the Architect's
  judgement (HK-038). AC8 tests it.

### D2. What a supplementary batch may do (Q1)

**Message-driven events apply. Absence-driven events do not.**

| event | batch 1 | batch 2/3 |
|---|---|---|
| A forward transition on a matching message (report, R-report, RR73/RRR, an answer to our CQ, auto-answer of a CQ) | yes | **yes**, with the timing of D3 |
| Abort because the partner is working another station | yes | **yes** (it is evidence, not absence) |
| Retry / no-response count, `RetryOrAbortAsync` | yes | **never** |
| Consuming the `_skipNextRetry` guard | yes | **never** |
| CQ-repeat counting (caller) | yes | **never** |
| Pending-target and jump-in firing (operator-armed, phase-driven) | yes | **never** |
| Watchdog reset | on the transmission, as today (D-007) | on the deferred transmission, when it is sent |

**Two guards, so a late batch never acts on an outdated state:**

- **Stale batch:** a batch 2/3 of cycle N is ignored if a batch 1 of a later cycle has already been processed.
- **Already answered:** a batch 2/3 of cycle N is ignored if batch 1 of N already caused a message-driven transition.
  The partner sends one message per cycle, so batch 1 found it.
- Either way, the decision is logged with the batch number and the reason.

### D3. When the reply goes out (Q1, the timing)

A batch-2/3 match is processed at time *t*. Let *S* = N's start + 15 s, the slot after the cycle it was heard in.

1. **Immediate:** if no transmission is running, the reply's parity is S's, and *t* ≤ *S* + 2.36 s (F5), transmit
   now, exactly as batch 1 would.
2. **Otherwise, deferred.**
   - The service makes the state transition now: partner, reports, the next message in `_lastTxMessage`, retry count
     reset to 0.
   - It holds the reply as a **deferred transmission**.
   - The deferred transmission is sent on the first later batch 1 whose next cycle has the reply's parity. In practice
     that is batch 1 of N+2, which sends it in N+3.
   - Before sending, that batch 1 runs through the handler of the **new** state:
     - a message-driven transition supersedes the deferred transmission, which is dropped;
     - otherwise the deferred transmission is sent. **It is not a retry:** no retry increment, then
       `_skipNextRetry = true` as after any transmission.
   - A batch 1 of the wrong parity, our own slot N+1, is not a missed response while a transmission is deferred.
3. **Auto-answer of a late CQ (Idle):** the same rule.
   - A deferred answer is **dropped** if an intervening batch shows the CQ station sending to someone else (destination
     neither CQ nor us). It is the same test as the Wait-state abort, applied before we transmit.

**What this does on air, worked through (answerer):**
- N: the partner sends us a report. Batch 1 misses it.
- N+1: we retry our answer. Batch 2 of N arrives during that transmission, and is read after it.
- Transition to WaitRr73, with the R-report deferred.
- N+2: the partner repeats the report, having heard our retry.
- N+3: we send the R-report.

Without the change, the same QSO stalls one more round or dies at the retry limit. This is ordinary FT8 practice: a
reply one round late.

### D4. The answerer snapshot is merged per cycle (Q3)

- **Merged, not replaced.** `_lastIdleDecodeBatch` holds one cycle.
  - A batch 2/3 with the **same** `CycleStart` **appends** its results.
  - A batch 1 of a **newer** cycle **replaces** the snapshot.
  - A batch 2/3 of an **older** cycle is dropped.
- So an external reply (`TryEngageExternal`) is accepted for a station from pass 0 and for one found only by the
  residual or third pass.
- The caller has no snapshot, so this applies to the answerer only.

### D5. The cycle-audio archive: out of scope (Q4)

- The Captain's wording covers QSO use. The archive stays as it is: one enqueue per window, at batch 1, with the pass-0
  count.
- **Known effect, for the Captain as housekeeping:** a cycle whose only decodes came from batch 2/3 is archived in
  NoDecodes mode. It matters only if someone selects archived audio by "had decodes". A separate small change can fix
  it, if he wants.

## 3. Acceptance criteria (mechanical; unit/integration tests with the fake time provider and fake PTT)

| AC | predicate |
|---|---|
| AC1 | **No supplementary batches ⇒ today's behaviour.** Every existing answerer, caller and pump test passes unchanged. With subtraction OFF, or with no batch-2/3 results, the transmitted message sequence and slots are identical to `0c7124db` in an integration replay |
| AC2 | For **each service × each Wait state**: a batch 2/3 with **no** match leaves the retry count, `_skipNextRetry`, the CQ-repeat count and the watchdog unchanged, and transmits nothing |
| AC3 | **Deferred reply:** batch 1 of N with no match → retry in N+1. Then batch 2 of N with the partner's message → state advances; no transmission in N+1 (the remainder) or N+2; the reply is transmitted starting at N+3's slot (with the batch-1 lateness of today's path); the retry count is 0 after it, and it does not increment the count |
| AC4 | **Immediate reply:** batch 2 of N matching, with no transmission running and *t* ≤ *S* + 2.36 s on the right parity ⇒ transmitted in slot *S*, untruncated. At *t* = *S* + 2.37 s ⇒ deferred per AC3 |
| AC5 | **Supersede:** while a reply is deferred, a batch 1 of N+2 carrying a message that causes a transition ⇒ that transition wins and the deferred message is never transmitted |
| AC6 | **Late CQ:** with auto-answer on, a CQ only in batch 2 is answered by the AC3/AC4 timing. If an intervening batch shows the CQ station sending to another station, the answer is dropped and the service stays Idle |
| AC7 | **Abort from a late batch:** the partner sending to another station in a batch 2/3 aborts exactly as from batch 1 |
| AC8 | **Stale and already-answered guards:** a batch 2 of N read after batch 1 of N+1 is ignored (logged); a batch 2 of N after batch 1 of N caused a transition is ignored (logged). Channel test: 3 batches per cycle for 4 cycles with a 12.64 s blocking transmission each own slot ⇒ no batch 1 is dropped |
| AC9 | **Snapshot:** batch 1 then batch 2 of the same cycle ⇒ `TryEngageExternal` accepts a reply to a batch-1 station and to a batch-2 station; a batch 2 of an older cycle does not change the snapshot |
| AC10 | **Logging:** every batch-2/3 decision in both services logs the batch number and the outcome (applied-immediate / applied-deferred / superseded / ignored-stale / ignored-answered / no-match), in the existing log style |

**Live verification is QA's to design.** The station has no on-air test partner, so AC1–AC10 are the evidence. A
live check, if QA wants one, counts the AC10 outcomes over an endurance run. It is never a pass/fail gate on QSOs the
station cannot arrange.

## 4. Not in this design

- Holding a batch-1 retry to wait for batch 2. That would start the retry late, with no evidence it helps.
- Answering in the slot after the reply's natural one, other than through D3.
- Any decoder change.
- The decode-panel display, which already shows batches 2 and 3.
