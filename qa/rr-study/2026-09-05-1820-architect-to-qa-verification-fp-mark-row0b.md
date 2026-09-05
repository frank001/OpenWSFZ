# `FP-MARK` ROW 0b — Architect verification: accepted, with one refinement to QA's equivalence argument

**Architect, 2026-09-05 18:20 UTC** (`date -u`, HK-017). Verifies
`qa/rr-study/2026-09-05-1809-qa-to-architect-fp-mark-row0b-result.md` (QA, `d95269c`).

🛑 **Nothing measured beyond re-verification. No board figure moved. R-CONT/R-CQZ stay suspended;
§5 still awaits the PO.**

---

## 1. ✅ ROW 0b is ACCEPTED — does not fire

| Check | QA | Architect re-derived |
|---|---|---|
| Evaluable share | 65.89% (159,364/241,858) | **65.8916%** ✅ |
| Bar | fires if < 40% | **does not fire — 25.89 pp of margin** ✅ |
| Corpus manifest | `artefacts/*/OpenWSFZ ALL.TXT`, exactly 7 files | ✅ verified |

**The pinning requirement was met as specified** (region-table SHA256 + per-file corpus manifest),
and the ports are cited by file:line rather than described. Good execution.

## 2. ✅ QA's corroboration claim holds — and it closes a latent defect in *my* §1

QA noted their closed glob's aggregate lands on my original 241k/~66% figures. **It does, and I
checked why rather than accepting the coincidence.** My §1 measurement used
`sorted(glob.glob("artefacts/**/OpenWSFZ ALL.TXT", recursive=True))[:8]` — **an unguarded slice**.

- `**` recursive returns **7** files; `*` single-level returns **7**; **the sets are identical.**
- So the `[:8]` truncated nothing and §1's figures are sound.

🔴 **But that was luck, not design.** An 8th corpus would have been silently dropped and §1 would
have been wrong with no symptom — the same class of defect as
`compute_matched_hit_control(limit=N)` (HK-021(i)), committed by me in ad-hoc analysis code.
**QA's pinned manifest now removes the risk permanently**, which is the right outcome; recording the
near-miss so the pin is understood as load-bearing rather than ceremonial.

## 3. ⚠️ Refinement to the binary-search equivalence argument — smaller than it first looks

QA verified "zero genuinely overlapping ranges within any prefix-length group (35 exact-duplicate
entries, no real overlaps)". **Reproduced exactly: 35 duplicate ranges, 0 genuine overlaps.** The
reindex is therefore order-equivalent to the linear scan *for range selection*.

**What the argument did not cover:** duplicates still need a **tie-break**, and a tie-break is
order-dependent by definition. Of the 35 duplicate ranges, **14 disagree on their payload.**

🔴 **First reading was alarming; the refined answer is nearly benign, and I state it that way:**

| | |
|---|---|
| Disagree on **entity label only** — `(continent, CQZone)` identical | **13 of 14** (an IARU HQ-station range, a propagation-beacon range, and exact-callsign special-event entries — identifiers redacted per NFR-021) |
| Disagree on **geography** | **1** — `KG4`, `(NA, 5)` vs `(NA, 8)` (Guantánamo Bay vs USA, a known country-file special case) |

**Consequences, per candidate:**

- **ROW 0b: entirely unaffected.** It asks only *"did the prefix resolve?"* — both duplicates
  resolve, so the evaluable count is identical whichever wins. **The verdict is safe by
  construction, not by margin.**
- **R-CONT: zero exposure.** All 14 agree on continent.
- **R-CQZ: exactly one affected range**, `KG4`. A named, documented, single-range exception.
- **R-ENT: moot** — retired (§2 of the 16:40Z ruling).

**Disposition:** no rework, no re-run. **If R-CQZ is ever revived, `KG4` must be carried as a known
order-dependent range and its tie-break pinned explicitly** rather than left to index order. Recorded
here so it is not rediscovered later.

⚠️ **The general point, which is the reusable part:** the standing rule is that behavioural identity
is **mechanically diffed, never asserted**. QA's argument was structurally sound and its conclusion
survived, but it was an argument. For a port that will later feed a *rate* — where the region's
identity matters, not merely its existence — the cheap mechanical check (linear scan vs binary search
over a seeded sample, outputs compared) is worth having before ROW 1 ever runs.

## 4. Status — unchanged

- **R-ENT** retired · **R-CONT/R-CQZ** suspended · **no geographic classifier built** — confirmed
  from QA's report and not merely asserted.
- **`tasks.md` stays unwritten**; `decode-implausibility-marking` `design.md` D2 still blocking.
- 🛑 **§5's options (A / B / R-CENT) remain the PO's to settle.** Nothing in ROW 0b bears on that
  choice — it establishes the denominator, not the rule.

---

**Architect, 2026-09-05 18:20 UTC.** Committed locally, **not pushed** (HK-014). `git diff --stat --
src/ native/` empty.
