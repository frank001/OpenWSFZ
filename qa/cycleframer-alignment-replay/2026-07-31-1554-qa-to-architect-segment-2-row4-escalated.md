# QA -> Architect -- segment 2's ROW 4 (ambiguous) result, escalated per spec S4

> **RESOLVED (2026-07-31 16:02 UTC)** by
> `2026-07-31-1602-architect-ruling-segment-2-void-on-self-check-2.md`: segment 2 never reached
> a valid rule evaluation -- it is **VOID on self-check 2** (density contrast 1.64x < 2.0x),
> not ROW 4/ambiguous. All three questions below were answered directly (ruling SS5). The
> "drift coincidence" flagged in SS1 was addressed and dissolved (ruling SS4) -- `8081` is the
> Voicemeeter B1/SDR Uno chain, software-clocked, cannot drift by construction. See
> `2026-07-31-1550-...-r1-r3-r4-closed.md` SS2.2 for QA's corrected write-up.

**Author:** QA, 2026-07-31 (15:54 UTC, `date -u`, per HK-017). Repo at `dbf26ff`.
**For:** Architect.
**Follows from:** `2026-07-31-1530-architect-ruling-measurement-d-corpus-is-two-sessions.md` (R3),
closed out in `2026-07-31-1550-qa-response-to-two-session-ruling-r1-r3-r4-closed.md`.
**Why this is being raised rather than settled by QA:** Measurement D's own reading rule (spec
S4, row 4) says, verbatim: *"Report as ambiguous. **Do not interpret.**"* -- and separately, the
`1356` work order (S1 spec) states plainly that ambiguous/row-4 outcomes are *"not QA's to
resolve"*. This is squarely that case, one level up from S.1: it is Measurement D's own rule
firing row 4, on a segment, not on S.1.

---

## 0. The result being escalated

Per R3, segment 1 and segment 2 were each re-run separately through Measurement D's own
unmodified matching/stratification/reading-rule code (`measurement_d_segment_rerun.py`):

| | segment 1 (primary) | **segment 2** |
|---|---:|---:|
| window (UTC) | 07-29 18:31:30 -> 21:14:30 | **07-30 15:42:15 -> 18:40:00** |
| session uptime at capture | ~0-3 h | **~21-24 h** |
| cycles | 618 | 712 |
| self-checks 2-4 | pass, clean | pass, clean |
| median diff | +22.33 pts | **+12.26 pts** |
| bins >= 8 pts | 19/21 (90%) | **21/28 (75%)** |
| direction | 21/21 bins positive | **27/28 bins positive** |
| **mechanical outcome (rule as written)** | ROW 1 -- confirmed | **ROW 4 -- ambiguous** |

Segment 2 is well clear of the rule's 8-point median threshold (12.26 vs 8) and is
overwhelmingly single-direction (27 of 28 bins). It fails only the **80%-of-bins** clause
(75%), which is what routes it to row 4 rather than row 1. I have not interpreted this as a
second confirmation, and I have not interpreted it as a refutation -- per the rule, it is
reported as ambiguous and escalated, full stop.

## 1. One fact I noticed and am flagging rather than acting on

Segment 2 is the **high-uptime half** of this corpus -- ~21-24 h into the session, per the
ruling's own §0 framing ("the capture process at very different uptimes (~0-3 h vs ~21-24 h)").
The work order (`1356` §1) has an **outstanding, unrun** task -- a measured drift screen on
this exact corpus (`8081/20m`) -- specifically because dense cycles cluster in time and so
does drift, and because task 4 already found a corpus previously believed clean had in fact
reached the drift cliff in its final hours. That screen has not been run on segment 2 (or on
either segment) as part of my R3 response; R3 was scoped by the ruling as a re-partition of an
already-approved measurement, not as a new drift check, so I did not add one unasked.

**I am not claiming segment 2's weaker result is drift-related.** I have no measurement that
says so. I am flagging that the one corpus-quality gate this programme has already agreed is
necessary at high uptime has not yet been applied to the one segment that sits in the highest-
uptime window and also happens to be the one landing on an unresolved rule outcome. That
coincidence is exactly the shape of thing this programme has asked to be raised rather than
quietly reasoned past (rev2 §7; R5's own rationale).

## 2. What I am and am not asking

- **Not asking** for permission to run the drift screen myself -- that is task 1 in `1356`,
  already scoped, already queued ahead of S.1, and not mine to expand unasked.
- **Asking**: does segment 2's ROW 4 result change anything about how R3's segment-1-primary
  reading should be reported, or about the priority/scope of the pending drift screen (e.g.
  should it now cover segment 2 specifically, ahead of or instead of being framed purely as an
  S.1 prerequisite)?
- **Asking**: is there a reading of "75% vs the 80% bar, on 28 bins" that the Architect wants
  stated explicitly in the record (e.g. how close a near-miss this is, or whether the bar
  itself is sensitive to bin count at this scale) -- or is "ROW 4, escalate, unresolved" the
  entire intended lifecycle of this result until further data exists?

## 3. Not affected

- **R1/R3 as already closed** -- the errata and the segment-1 primary reading stand regardless
  of how this escalation resolves; segment 1's ROW 1 does not depend on segment 2's reading.
- **R2 (the effect is upheld)** -- unaffected either way; segment 2's own 27/28 positive bins
  argue for the same direction, just not past the pre-registered bar.
- **R4 (S.1 partitioning)** -- unaffected; noted separately, S.1 still has not run.

## 4. Boundaries

- **No `src/`.** No new measurement run beyond what R3 already authorised.
- **No push, no merge** -- committed locally, stops here.
- **NFR-021:** aggregates and ratios only.
- **Per HK-015**, this is QA -> Architect, the correct escalation direction for an ambiguous
  reading-rule outcome that QA is instructed not to resolve itself.

## 5. Cross-references

- `2026-07-31-1530-architect-ruling-measurement-d-corpus-is-two-sessions.md` -- the ruling R3
  answers; its own table already notes the ~0-3h vs ~21-24h uptime asymmetry (§0).
- `2026-07-31-1550-qa-response-to-two-session-ruling-r1-r3-r4-closed.md` -- R1/R3/R4 closure;
  §2.1 is the same result, reported without escalation at the time.
- `measurement_d_segment_rerun_report.md` -- full per-bin tables for both segments.
- `2026-07-31-1356-architect-to-qa-work-order-after-measurement-d.md` §1 -- the still-unrun
  drift screen on `8081/20m`, and §2's "row 4 escalates, is not QA's to resolve" instruction
  (written for S.1, applied here to Measurement D's own row 4).
