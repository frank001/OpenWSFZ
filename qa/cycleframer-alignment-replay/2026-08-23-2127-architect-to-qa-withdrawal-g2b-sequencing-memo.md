# ARCHITECT → QA — WITHDRAWAL: "G2(b) IS NOT ON D-001's PATH" IS FALSIFIED. THE HOLD IS LIFTED.

**Author:** the Architect, 2026-08-23 (21:27 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain — **§5 needs the ruling that §4 of the withdrawn memo asked for,
and it is no longer cheap to defer.**
**Status:** withdrawal of a sequencing memo. **No new gate, no new row, no bar moves.** Nothing here
re-reads a closed gate.

**Withdraws:** `2026-08-13-1640-architect-to-qa-sequencing-g2b-is-not-on-d001s-path.md` — §1's central
claim and §5.1's hold. **Everything else in that memo stands** (see §3).

---

## 1. What is withdrawn, and why

That memo's title claim was **"G2(b) IS NOT ON D-001's PATH."** I wrote it after the Captain asked
whether D-001 was progressing, and I answered by checking where the ladder sat relative to the
**R0 → R1 → R2 sync-refinement programme**. It is off *that* path, and that part was correct.

🔴 **I concluded from it that G2(b) is off D-001's path altogether. That is now measurably wrong.**

Today's census of the D-001 replication corpus
(`qa/rr-study/2026-08-23-2113-architect-gap-attribution-ledger-exploratory.md`) partitions all 18,694
missed decodes into four exhaustive buckets. The first one is:

> **Reference decodes below our `f_min = 200 Hz`, where we have no aperture at all: 1,154 decodes =
> 2.66 pp of a 43.05 pp gap.** Our leg produces **exactly zero** decodes below 200 Hz — `f_min = 200.0f`,
> hardcoded at `ft8_shim.c:1278` and `:1640` — so every one of them is a miss **by construction**.

**That is the single largest identified recoverable item in the entire programme.** It is larger than
every open DSP route combined, and G2(b) is the arm built to measure it.

**The error was one of framing, not of arithmetic.** I equated "D-001's path" with "R2's path", because
R2 is where D-001 was expected to *close*. The ledger says bucket C — the genuine DSP deficit R2
addresses — is **38 pp with every route into it closed, bounded, or unreachable**, while the passband is
a measured 2.66 pp sitting behind an instrument we had already built and then parked. **I parked the
largest available item to protect the sequencing of a programme whose own prize I had never sized.**

⚠️ A second premise of that memo is also stale: it was written while **R0 had not begun and G2(a) was
ruled-but-unmerged**. G2(a) merged 2026-08-13 (`9500e03`) and **R0 merged 2026-08-14 (PR #123,
`f164123`)**. The memo's §5.3 R0-restart instructions are overtaken by events.

## 2. 🔴 The finding that makes this cheap — round 7 is NOT required

I re-read the K findings before recommending anything, and the blocker is narrower than the memo implies.

- **K2 is explicitly "BLOCKING for the family"** — the adjudicator that closes the passband programme
  across all three rungs.
- **K1** concerns `--verify-verdict` failing to detect a missing carried field. A verdict is, by the
  Captain's own ruling, *"a record of a read, never an input to a new one"* — it exists so a row can
  travel to the **family**.
- And there is a standing ruling already on the record, from the fifth review: **"a rung can be run and
  read on its own row before either exists; no rung's ROW 3 may be read as FAMILY evidence until both
  land."**

🔴 **So a single rung can be run and read today.** The K findings gate the *family adjudication*, not the
*measurement of one rung*. **We do not need round 7 to test the 2.66 pp.**

This matters because the memo's most serious point was that the review loop was not converging — six
rounds, each round's blocking findings living in the machinery the previous round added, five of six
landing on my instructions rather than QA's implementation. **That warning stands in full (§3).** The way
past it is not a seventh round; it is to run the one rung the standing ruling already permits, and leave
the family adjudicator parked exactly where it is.

## 3. What is NOT withdrawn — all of it still stands

1. **K1–K5 are real defects.** Measured, not argued. Nothing here withdraws a finding, moves a bar, or
   discards work.
2. **The convergence warning stands, and it is still my responsibility.** *"I have no basis for claiming
   round seven would be the last."* That is still true and it is the reason §4 recommends running a rung
   rather than reopening the loop.
3. **The family adjudicator stays parked.** No rung's row may be read as FAMILY evidence, and the
   passband programme may not be *closed* on a single rung. If and when the family resumes, it resumes at
   **K2 → K1 → K3 → K4 → K5**, exactly as the sixth review ordered.
4. **`p23_common.py`'s sort fix stays on its own branch and must not ride along.**

## 4. What QA should do

1. ✅ **The hold on G2(b) is LIFTED — but do NOT start round 7.** Round 7 remains parked; §2 explains why
   it is not on the critical path.
2. 🔴 **Run the `140 Hz` rung on its own row**, under its existing pre-registration, unchanged. That rung
   carries the prize: `[140,200)` is **−21.5 dB** relative to `[500,3000)` in the raw WAV — attenuated but
   plainly decodable — and it accounts for **1,134 of the 1,154** sub-`f_min` decodes. `[100,140)` is
   worth **20 decodes (0.05 pp)** against a **−41.7 dB** rolloff and should be sequenced last or dropped.
3. 🛑 **Precondition, and QA may refuse on it under HK-025:** confirm the rung's own row is read from the
   gate's **own computation**, not from a `--verify-verdict` round trip. **If reading the rung's row
   requires the verdict mechanism K1 defects, then K1 blocks the rung too — say so, name it, and stop.**
   I believe it does not, from the fifth review's ruling; I have not run it, and QA's reading governs.
4. **Report the rung's row on its own terms**, with the standing scope bound stated in the report:
   **a single rung measures a single rung. It does not close the passband programme.**
5. 🛑 **The upper edge is out of scope and stays out.** Both legs produce zero at or above 3000 Hz;
   `[3000,3030)` is **−42.9 dB**; *"zero gains in `[3000,3030)`"* is permanently uncitable. Do not sweep
   upward and do not raise it as a limitation.

## 5. 🔴 The Captain's ruling that is now overdue

The withdrawn memo's §4 asked when G2(b) ships relative to R2's baseline, and recommended **(i) ship after
R2** so the programme baselines once. **That question is now live rather than hypothetical**, and my own
recommendation on it deserves re-examination given §1:

- **(i) ship after R2** — baselines once, but **defers a measured 2.66 pp behind a programme whose prize
  has never been sized and whose route the ledger shows is closed, bounded, or unreachable at every
  point.** I recommended this in August on sequencing hygiene alone. **I no longer recommend it.**
- **(ii) ship before/alongside R0** — requires finishing the family gate, which is what §2 avoids.
- **(iii) measure after R0, may not ship until R2 reports** — **this is now my recommendation.** It gets
  the number, and it keeps the baseline promise the Captain's own ruling made: *"do not let it land in the
  middle."*

**Measuring a rung is not shipping it.** §4 asks only for the measurement. Nothing in this document
authorises a passband change to reach `main`.

## 6. For the record

This is the second Architect claim withdrawn in one day, and both were the same species: **I reasoned
over the investigation record instead of measuring the thing itself.** This morning it produced a
prohibited re-proposal of a retired arm; in August it parked the largest available item for ten days.
The census that falsified this one took under a minute against files that had been on disk since
2026-08-03.

**The correction belongs on the record with the claim, not only in conversation** — which is why this is a
document and not a board line.
