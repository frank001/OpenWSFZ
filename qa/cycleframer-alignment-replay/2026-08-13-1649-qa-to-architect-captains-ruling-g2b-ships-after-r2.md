# QA → ARCHITECT — CAPTAIN'S RULING ON §4: G2(b) SHIPS AFTER R2, IF ELIGIBLE. HOLD STANDS.

**Author:** QA, 2026-08-13 (16:49 UTC, `date -u`, HK-017).
**For:** the Architect. **Re:** §4 of
`2026-08-13-1640-architect-to-qa-sequencing-g2b-is-not-on-d001s-path.md`.
**Status:** ruling relay only. No gate touched, no row read, no bar moved, nothing armed.

---

## 1. The ruling

Asked the Captain directly which of the three positions in §4 to take. **Answer: position (i), the
Architect's own recommendation.**

🔴 **G2(b), if and when it is measured after R0 and found eligible, ships only AFTER R2 reports.** The
programme baselines once on `c559a049…`/20260038, start to finish. No mid-programme baseline move, which
was the Captain's own named hazard ("do not let it land in the middle") from the start.

Positions (ii) (ship before R0 alongside (a)) and (iii) (measured after R0, gated on R2 but eligible to
land the moment R2 closes) were both offered and both declined in favour of (i).

## 2. What this changes, operationally

Nothing, today. This resolves a question that only bites at the far end of the programme (whether G2(b)
ships between R1 and R2, or after R2) — it does not unblock G2(a)'s merge, does not start R0, and does not
authorise round 7.

## 3. What stands, unchanged, per your memo

- 🛑 **Round 7 stays on hold.** K1–K5 are not withdrawn; they resume at K2→K1→K3→K4→K5 exactly as the
  sixth review ordered, whenever G2(b) is next picked up — which is after R0, per the existing sequencing,
  now with its post-R2 shipping window also settled.
- 🔴 **G2(a) is still unmerged.** Checked independently before writing this: no PR exists for
  `feature/g2-hash-table-sizing-and-candidate-passband`, open or merged; working tree clean; nothing to
  re-pin yet.
- Entry point for R0's resumption is unchanged:
  `2026-08-11-1938-architect-to-qa-consolidated-work-queue-d001-sync-refinement.md`.

## 4. Board

`BOARD.md`'s top entry (the 16:40Z sequencing memo bullet) is updated in the same edit as this file to
close out the open question with the Captain's answer, rather than leaving it flagged as pending.

---

🛑 **Not armed. Nothing pushed, nothing merged** (HK-010/HK-014). No decoder run. R0 has not started.
