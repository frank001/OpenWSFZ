# ARCHITECT → QA — SEQUENCING: G2(b) IS NOT ON D-001's PATH. HOLD ROUND 7; R0 IS THE WORK.

**Author:** the Architect, 2026-08-13 (16:40 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain — **§4 needs a ruling before R0 starts.**
**Status:** sequencing memo. **No new gate, no new row, no new pre-registered check.** Nothing here
re-reads a closed gate or revises a bar.

---

## 1. Why this exists

The Captain asked whether we are making progress on closing D-001. I checked the ladder rather than
answering from the board's summary line. **We are not — not on the path that closes it.** This memo says
where the work actually is, and what I got wrong.

## 2. The state, in four lines

| | |
|---|---|
| **D-001 closes at** | **R2** (three of its four outcome branches resolve it, including the falsification branch) |
| **R2 needs** | R1 all-AC PASS → which needs R0 PASS |
| **R0 needs** | **G2 item (a) merged**, then R0/R1/R2 re-pinned to `c559a049…`/20260038 |
| **G2(a) status** | **ruled MERGE by the Captain — not merged.** R0's remaining deliverables are blocked behind it |

**Three specs written 2026-08-11. None run. No decoder has been run in any of this.**

## 3. Where G2(b) sits — off that path, by our own ruling

G2(b)'s gate is sequenced **after R0**. That is not my re-reading; it is the accepted sequencing on the
board (*"item (a) first — it improves the instrument — this gate after R0"*), and every one of the six
review entries repeats **"R0 still precedes this gate."**

So six review rounds and six revisions over ~25 hours have hardened the instrument for a measurement that
comes **after** a phase that has not begun, which is itself waiting on a merge authorised a day ago.

🔴 **The loop is also not converging, and that is my responsibility.** Each round's blocking findings live
in machinery the previous round added. J1/J2/J3 were *"the conclusion travels, the evidence that licensed
it does not."* The ruling that fixed it produced K1/K2 — **the same defect, moved from the verdict's
contents to the verdict's consumer.** Five of six rounds landed on the **Architect's instructions**, not
QA's implementation; QA has implemented every instruction correctly, and in two cases better than
specified. K2's fix (F10) adds another mechanism, which is precisely the shape that has generated the next
round's findings four times running. **I have no basis for claiming round seven would be the last, and I
should have said so before opening round six rather than after.**

⚠️ **To be clear about what is NOT being said: K1–K5 are real.** A family adjudicator that closes the
passband programme on three evidence-free verdicts is a genuine defect, measured, not argued. *Real* and
*worth doing now* are different questions, and I conflated them.

## 4. 🔴 OPEN QUESTION FOR THE CAPTAIN — settle before R0 starts, not between R1 and R2

If G2(b) is measured after R0 and then **ships**, it moves R2's baseline — the exact hazard the Captain's
own ruling named: **"do not let it land in the middle."** The specs do not resolve this. The three
coherent positions:

- **(i)** G2(b) is measured and, if eligible, ships **after R2** — the programme baselines once, on
  `c559a049…`, start to finish. *(Architect's recommendation — it is the only option that cannot move a
  baseline mid-programme.)*
- **(ii)** G2(b) ships **before R0** alongside (a) — one combined re-pin, but it requires finishing the
  gate first, which is what this memo is arguing against doing now.
- **(iii)** G2(b) is measured after R0 but explicitly **may not ship** until R2 reports.

**Not QA's call and not mine.** Flagged here so it is ruled while it is cheap.

## 5. What QA should do

1. 🛑 **HOLD round 7. Do not start the K1–K5 fixes** pending the Captain's ruling on §4. The sixth review
   stands as written and loses nothing by waiting; everything is committed.
2. ✅ **G2(b) is parked, not abandoned.** No work is discarded, no finding is withdrawn, no bar moves. If
   and when it resumes, it resumes at K2 → K1 → K3 → K4 → K5 exactly as the sixth review ordered.
3. 🔴 **On the Captain's merge of G2(a):** the R0 restart path is already written on the board — verify
   the Developer session's diff, **re-pin the DLL SHA256 and shim version in every R0/R1/R2 spec** (they
   still carry `f2f30c89…`/20260033; the target is `c559a049…`/20260038), then resume R0's remaining
   deliverables (D1 vendor sources, D2 full rebuild, D4 `--assert-dll-sha`, D5 `THIRD-PARTY-NOTICES.md`,
   AC-1 replay). 🛑 **Do not resume R0 on the old pin.**
4. **Entry point unchanged:**
   `2026-08-11-1938-architect-to-qa-consolidated-work-queue-d001-sync-refinement.md`.

⚠️ **`p23_common.py`'s sort fix stays on its own branch and must not ride along** with any of this.

## 6. Two standing points this produced

🔴 **A mechanism invoked by a separate command is prose with a `main()`.** A check that is not on the path
that *consumes* the artefact is not a check — it is a tool someone may remember to use. (From K2; stated
in the sixth review, repeated here because it generalises well beyond G2(b) and will fire on R1/R2.)

🔴 **An instrument is finished when the measurement it serves is next, not when it is flawless.** Six
rounds of review found real defects in a gate that was never the next thing to run. The instrument's
quality was never the binding constraint; its **position in the queue** was, and I did not check the queue
once in six rounds.

---

🛑 **Not armed. Nothing pushed, nothing merged** (HK-010/HK-014). No decoder has been run. R0 has not
started.
