# TASK for QA: file a GitHub issue for the 12-bit MISRESOLUTION defect

**Architect → QA.** 2026-08-26 19:13Z (`date -u`, HK-017). Repo `main` @ `f6674af`.

**Ordered by the PO**, 2026-08-26, after the ARM 1D ruling and the update posted to issue #60.

🔴 **This is QA's to file, not mine. The remote is QA's (HK-014).** I am supplying the body so you do
not have to re-derive it; the wording is yours to change, the **caveats below are not**.

---

## 1. Why a separate issue at all

**#60 is about hashes going UNRESOLVED** (`<...>` printed where F-001 had what it needed to resolve).
**This defect is the opposite failure: the hash RESOLVES, to the wrong station.** Same mechanism
underneath, opposite symptom, different remedy, different severity. Filing it under #60 would bury it.

Context already public on #60: https://github.com/frank001/OpenWSFZ/issues/60#issuecomment-5429877993
(that comment covers the mechanism, the options and the recommendation — **do not duplicate it**,
link it).

Source defect document, already in the repo: `DEFECT-twelve-bit-hash-misresolution.md` (ACCEPTED as
raised, severity **High**, per the 15:04Z ARM 1B ruling).

---

## 2. Suggested title

> `F-001: 12-bit hash collisions resolve to the WRONG callsign (first-match-wins) [HIGH]`

---

## 3. Body — suggested, with the non-negotiable parts marked

Everything under 🛑 must survive your edit. Everything else is yours.

**Summary.** Type-4 FT8 messages carry a 12-bit callsign hash — 4,096 codes, fixed by the protocol.
The session-scoped hash table resolves a query by taking the **first match on the probe chain**. Once
the table holds more than a few hundred names, multiple entries share a 12-bit code as arithmetic,
not as a bug, and the first match is frequently not the right one. The result is a **real but
incorrect callsign** rendered in the decode panel and carried into anything that logs or relays a
decode. A wrong name is loggable; `<...>` is honest.

**Scale of the collision space.** One session heard **16,320 distinct callsigns** against a
**4,096**-entry table. Of 1,868 resolved 12-bit queries, **50.9%** had ≥2 entries sharing the code.

**Measured rate.**

🛑 **This scoping sentence must travel with the 51.3% figure, every time, in the issue body itself —
not in a footnote and not on a later comment:**

> **51.3% is the callsign-level disagreement rate on the subset where BOTH decoders resolved the
> slot.** That subset is **243 of 1,899 resolved type-4 decodes (12.8%)**, and 243 of 3,232 type-4
> decodes overall (7.5%). The other **1,544** resolved type-4 decodes have **no reference row at all**
> and are not measurable from this corpus. **Nothing licenses extrapolating 51.3% onto them.**

- Decode-level rate, which must be carried alongside: **92 / 243 = 37.9%**.
- Gate: ARM 1B **ROW A1** fired; CP one-sided bounds from `x=59, n=115` are **0.43247 / 0.59310**,
  against a 5% threshold — **8.6x** the threshold.
- Corroboration, derived independently of the reference: a random-order null over the measured
  multiplicity distribution predicts a decode-level wrong-name rate of **~28%** vs **37.9%** measured.
  🛑 State it as *same order of magnitude, two independent derivations* — **not** as agreement, and
  **not** as evidence that the null's 10pp shortfall means anything. It is unexplained.

**Severity.** High. 🛑 **But sharpen it rather than leaning on the label**, and carry both halves:

- **Realised harm today:** wrong callsigns rendered and logged.
- **The severe form** — a station addressing us by hash, misresolved, so the QSO answerer never sees
  the call — has **exactly zero** exposure in this receive-only corpus. 🛑 **An exposure of zero is
  NOT evidence of absence.** It is a receive-only corpus; a transmitting station's exposure is a
  different and unmeasured thing.
- 🛑 **Say plainly that suppression does not fix the severe form.** Blanking an ambiguous resolution
  to `<...>` still leaves the answerer blind to the call. That harm needs the own-callsign direct
  hash match described on #60, which is orthogonal to the table entirely.

**Not established** — 🛑 reproduce this list, do not trim it:

- the split of the joint error between the two decoders;
- corpus-dependence of the rate (single device, single band, single session);
- the shape of any correction;
- whether the measured trade of a unique-match rule reaches a majority — **ARM 1D returned
  INDETERMINATE on both gates** (rescue 33–36 of 59 units, cost 20–27 of 56 units).

**Status of remedies.** 🛑 **This issue authorises no fix, no policy and no `src/` change.** Options
and the recommendation are on #60; link, do not restate. Each route earns its own pre-registered
measurement. 🛑 **No sentence may describe what a fixed build would do — no such build exists.**

🛑 **Every ambiguity/rescue/cost figure above comes from a REPLAYED table, i.e. a simulated
stratifier, and cannot be validated offline. Say so in the body.** The 51.3% / 37.9% / A1 figures are
**not** in that category — those are real decoder output against a reference — so do not blur the two.

---

## 4. Before you post

- **NFR-021:** repo is **public**. Scan the body for callsign-shaped tokens; there should be none.
  The severe-form example is stated generically ("a station addressing us"), and it needs no callsign
  to make sense — keep it that way.
- **Cross-link both directions:** the new issue links #60; add a one-line comment on #60 pointing at
  the new issue so the pair is navigable.
- Link `DEFECT-twelve-bit-hash-misresolution.md` and the ARM 1B / ARM 1D rulings under `qa/rr-study/`.
- 🛑 **Do not** re-open, re-read or re-quote ARM 1C — it is **VOID at ROW 0d** and its gates were
  never computed.

---

## 5. What QA does NOT owe on this

No re-run, no new measurement, no harness change. This is a filing task. If anything in Sec.3 looks
wrong to you, **push back rather than post it** — the numbers are load-bearing and a public issue is
hard to walk back.

## Cross-references

- `qa/rr-study/2026-08-26-1826-architect-to-qa-ruling-f001-d3-arm1d.md` — ARM 1D ruling (indeterminate gates, the sizing, the harm split).
- `qa/rr-study/2026-08-26-1504-architect-to-qa-ruling-f001-d3-arm1b.md` — ARM 1B ruling; Sec.3 is the source of the mandatory scoping caveat.
- `DEFECT-twelve-bit-hash-misresolution.md` — the defect as raised and accepted.
