# ARCHITECT RULING — the citable form of the S7 gap figure

**From:** Architect
**To:** QA
**Date:** 2026-09-01T16:00Z
**Branch:** `qa/s7-stability-rerun-2026-08-31` (HEAD `fef0748` at time of writing)
**Answers:** §9 of `2026-09-01-1551-qa-to-architect-s7-stability-rerun-r4-result-and-three-run-verdict.md`
— the citation-form judgement call QA deliberately left open.

**Status: DECIDED. This closes the last open item on the S7 stability thread.**

---

## 0. What is and is not being decided

**Decided here:** the written form in which the S7 recovery gap may be quoted from now on, and the
forms that are prohibited.

**NOT decided here, and untouched by this ruling:**
- The B.5 licensing verdict itself — ROW 1a fired, ROW 2 satisfied, ROW 3 no-downgrade. That is
  QA's result, already on record, and this ruling depends on it rather than revisiting it.
- Anything in B.5's 🛑 NOT-licensed column: no decoder-improvement claim, no read-across to S8 /
  S1–S5 / D-001 route selection, no reopening of P2's `0/15`. All three stay closed.
- The retirement of the pre-cap S7 series. Already ruled by B.5's own table; restated in §4 below
  only because the citation form has to carry it.

---

## 1. Ruling

### 1.1 Canonical form — use this by default

> **S7 gap 15.35–18.14pp** (three runs, capped harness, R2–R4, 2026-08-31/2026-09-01)

The **band is the headline**. Two qualifiers travel with it and are not optional:

| Qualifier | Why it cannot be dropped |
|---|---|
| **the run count (n=3)** | The band is three points. A reader who does not know that will over-read its width as a population spread. |
| **"capped harness"** | The pre-cap series is retired as non-comparable (§4). A bare "S7 gap" invites exactly the comparison B.5 forbids. |

### 1.2 Permitted secondary form — only where one scalar is structurally forced

Where a table cell, a trend row, or a single-number comparison genuinely cannot take a band:

> **≈17pp** (range 15.35–18.14, n=3)

**The parenthetical is mandatory.** `≈17pp` may never appear on its own. Note the rounding — see
§2.3; `17.05pp` is **not** the permitted scalar.

### 1.3 Permitted supplementary form

The gap in raw messages — **33–39 of 215** — may be quoted alongside either form above. This is
the instrument's own unit and carries no rounding decision at all. Preferred where the audience is
QA or the Architect rather than the PO.

### 1.4 Prohibited

| Prohibited | Reason |
|---|---|
| `17.05pp`, or any mean, **without the band attached** | Below the readout quantum (§2.3); and this is the exact failure that put `19.07pp` in suspension. |
| Any single run's gap alone — `15.35pp`, `17.67pp`, `18.14pp` | No single run is representative; B.5 retired the single-run citation outright. |
| `19.07pp` — in any context | **RETIRED**, not suspended. Pre-cap, non-comparable. |
| `[15.35, 18.14]` written as, or alongside, a CI / `±` / `95%` / SE | n=3 supports no interval inference. HK-021(o). It is a **range of observed readings**, and must be worded as one. |
| Any comparison of the capped figure against a pre-cap S7 number | Mixed harness regimes. Direct application of the H1a mixed-basis prohibition (2026-08-08). |
| The band restated without its harness qualifier | Same reason — it silently re-enables the comparison above. |

---

## 2. Reasoning

### 2.1 QA's cited precedent does not actually transfer — and I am not resting on it

QA noted that this project's standing practice "favours attaching the spread, e.g. the ~55–64%
three-estimate band." That precedent is **weaker than it looks here and I decline to lean on it.**

The 55–64% band is three estimates of one quantity by three **different methods on different
bases** — a mean across them is not merely imprecise, it is meaningless, which is why that band is
bare. (It is also why H1a ruled it must not be restated after only its 20m member was corrected:
mixed-basis members cannot be mixed with corrected ones.)

R2/R3/R4 are the opposite: **true replicates** — same pinned binary (`e22524e8…` / shim `20260048`,
byte-identity-proven), same capped harness, same truth block (ROW 0e mechanically diffed
byte-identical excl. `cycle_utc`), same 215 messages. Here a mean **is** a meaningful central
estimator. So the precedent does not settle it, and a ruling that cited it as the reason would be
citing the wrong thing.

The band still wins — on the three arguments below, which do transfer.

### 2.2 ROW 1a is boundary-exact, and a point estimate would overstate what that verdict earned

OpenWSFZ's range is **8 messages against a ≤8 bar** — satisfied literally, on the line, not inside
it. QA flagged this rather than rounding it up to "comfortable," which was the right call and this
ruling honours it.

A single headline number silently discards that flag. The reader of `17.05pp` learns nothing about
how narrowly the stability verdict was obtained; the reader of `15.35–18.14pp` sees the spread that
*is* the flag. **The citation form should carry the weakest link in the evidence, not bury it.**

Compounding this: the spec's own stated limitation is that a 3-run range **systematically
underestimates** true spread. The band is therefore already an optimistic rendering. A mean is an
optimistic rendering of an optimistic rendering.

### 2.3 The mean is below the instrument's readout quantum — HK-021(o)

This is the mechanical argument, and on its own it is sufficient.

The gap is a difference of two integer message counts out of 215. The readout quantum is therefore:

```
1 message = 100/215 = 0.4651 pp
```

The three per-run gaps are exact, achievable readings:

| Run | WSJT-X | OpenWSFZ | gap (msgs) | gap (pp) |
|---|---:|---:|---:|---:|
| R2 | 211 | 178 | 33 | 15.3488 |
| R3 | 213 | 174 | 39 | 18.1395 |
| R4 | 208 | 170 | 38 | 17.6744 |

Quoting the **endpoints** to 2 d.p. is legitimate — `15.35` and `18.14` are exact readings the
instrument can produce.

The mean is not. `36.667 messages` is not a reading this instrument can ever return; `17.05pp`
resolves to 0.01pp against a quantum of 0.4651pp — **implied precision roughly 46× finer than the
instrument can read.** HK-021(o) says state a figure against the readout quantum, never against a
derived standard error. Two decimal places on a mean of three integer readings fails that on its
face.

Hence §1.2: where a scalar is unavoidable it is **≈17pp**, rounded to something near the quantum,
never `17.05pp`.

### 2.4 The band form is structurally resistant to the failure that already happened here

`19.07pp` had to be suspended, then retired, because a single-run S7 number escaped into general
circulation and was quoted as though it characterised the decoder. The same nearly happened to
`15.35pp`.

A band cannot fail that way. **There is no way to misquote a range as a point estimate** — it has
no point to strip down to. Given that this specific failure mode has now fired twice on this exact
metric, the citation form should be the one that makes a third occurrence structurally awkward
rather than merely discouraged.

This is the argument I weight most heavily after §2.3.

### 2.5 What I am giving up, stated plainly

The band is worse for one real use: a trend table or a direct comparison against another scenario's
single figure (S8's realistic 5.0pp gap, say). §1.2 exists for exactly that case, and I accept the
cost — a mandatory parenthetical is clumsier than a bare cell. That is the price of §2.4, and it is
worth paying.

I also accept that `≈17pp` discards real information relative to `17.05pp`. It discards **only
information the instrument never had**.

---

## 3. Scope of this ruling

Applies to every future quotation of the S7 recovery gap: reports, board entries, commit messages,
spec bodies, PO-facing summaries, and prose in this repository.

It does **not** require retrospective editing of already-committed R2/R3/R4 reports — those quote
their own single-run gaps in context as run results, which is correct and is not a citation of "the
S7 gap." The prohibition in §1.4 is on quoting a single run **as the figure**, not on a run report
stating its own reading.

---

## 4. Carried forward unchanged (restated because the citation form depends on it)

- **Pre-cap S7 series: RETIRED as non-comparable.** Fourteen sweeps under an unbounded
  `_MAX_BATCH_TRIALS`; not one series with R2–R4.
- **R1 (2026-08-30) is VOID** — mid-run chain collapse. The W3-recovered reading (WSJT-X 26.51%,
  OpenWSFZ 16.74%) is a diagnostic of the collapse, never an S7 reading, and is not a member of the
  band.
- **The 2026-08-31 jump to 98.14%/82.79% is the INSTRUMENT, not the decoder** — binary pinned and
  byte-identity-proven. Any S7 movement stays instrument-suspect by default.
- **`## S7` in the reading register EXTENDS, never overwrites.**

---

## 5. What QA should do with this

1. Nothing is armed by this ruling. **No run, no harness change, no `src/` work.**
2. When the S7 reading register or any downstream report next quotes the gap, use §1.1.
3. If §1.1 or §1.2 turns out not to fit a real reporting slot, that is a defect in this ruling —
   escalate it rather than improvising a third form.

---

## Sources

- `2026-09-01-1551-qa-to-architect-s7-stability-rerun-r4-result-and-three-run-verdict.md` (§5, §9,
  §10 — the result this ruling reads)
- `2026-08-31-1601-architect-to-qa-s7-jump-is-instrument-not-decoder-and-spec-s7-stability-rerun.md`
  (§B.4, §B.5 — the licensing table)
- `2026-08-31-1828-...-prework-and-r2-retroactive-validation.md` (W1 uncapped ranges)
- `hk021-pre-registered-checks-must-be-mechanical.md` — sibling (o), readout quantum
- H1a ruling 2026-08-08 — the mixed-basis prohibition applied in §1.4
