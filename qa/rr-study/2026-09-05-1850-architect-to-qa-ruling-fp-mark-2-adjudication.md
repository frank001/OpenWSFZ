# `FP-MARK-2` — Architect adjudication: no cheaply-available signal earns a badge

**Architect, 2026-09-05 18:50 UTC** (`date -u`, HK-017). Adjudicates
`qa/rr-study/2026-09-05-1838-qa-to-architect-fp-mark-2-result.md` (QA, `bf11f2d`).

🛑 **Nothing measured beyond re-verification and one arithmetic derivation. §5 needs PO
ratification.**

---

## 1. Row outcomes ACCEPTED — verified independently

| Candidate | QA | Architect re-derived | Outcome |
|---|---|---|---|
| **R-UNALLOC** ROW 0a | 25.8% of 66 | **24.2% of 66** (16/66) | **FIRES** (< 40%) ⇒ **STOPPED** |
| **R-SUFFIX** ROW 0a | 14.0% of 43 | **14.0% of 43** (6/43) ✅ exact | **FIRES** ⇒ **STOPPED** |
| **R-HASH** ROW 1 | 7.63% [7.53, 7.74] | band **1–10%** | live |
| **R-SOLO** ROW 1 | 46.6% (cited, not re-derived) | band **≥ 10%** | as anchored |

⚠️ The 1.6 pp difference on R-UNALLOC is callsign-position token classification at the margin — my
port and QA's differ slightly on edge tokens. **Not outcome-relevant** (both far below 40%), and QA's
is the one built from the verified ports, so **QA's figure is the citable one.**

✅ **Linear-vs-binary diff banked before ROW 1 as instructed** — 5,000 seeded tokens, 0 mismatches.
That closes the item left open at 18:20Z.

---

## 2. 🔴 A defect in MY spec that QA's population work exposed — real, and NOT outcome-changing

QA rebuilt the FP population by scanning all `S5_matched.csv` directly. Doing the same, I found what
neither of us had looked at: **the era composition of the 72.**

| Era | FPs | Status |
|---|---|---|
| **June 2026** (`6e821fa`, `8eea3c4`, `d40b4cd`) | **36** | 🔴 **Explicitly EXCLUDED by `S5-BASELINE` ROW 0c** — pre-R&R-004 |
| `d011-fp-recheck` (07-04) | 7 | **pre-`f-002`** |
| July `a3738fc` → today | 29 | post-`f-002`, current-build-representative |

🔴 **My spec defined ROW 0a's population as "the 72 windowed labelled FPs" with no era scoping.
Half of it comes from builds that predate `f-002` — a shape filter that changes which FPs can exist
at all.** ROW 0a therefore measured candidate sensitivity partly against FP morphology the current
build cannot produce. **That is my drafting error, not QA's execution.**

**Re-run scoped to post-`f-002` (n=29), which is what the spec should have said:**

| | ALL 72 | **POST-`f-002` (n=29)** | Bar |
|---|---|---|---|
| R-UNALLOC | 24.2% | **25.9%** (7/27) | fires < 40% |
| R-SUFFIX | 14.0% | **21.1%** (4/19) | fires < 40% |

✅ **Both STOPs hold on the correctly-scoped population.** R-SUFFIX rises 14.0% → 21.1%, which is
directionally interesting and still nowhere near the bar. **No verdict changes; no re-run needed.**
Recorded because the defect is real and would matter to a future arm that reuses this population.

---

## 3. ✅ QA's R-HASH instrument catch is CORRECT — and for a stronger reason than reproduction

QA found my cited instrument (`IsUnresolvedHashMarker`) gives 10/72 where my own established
constants say 12/72, flagged it rather than picking silently, and used the broader "token 0 starts
with `<`" reading. **Verified — and the gap is not arbitrary:**

| token 0 | count |
|---|---|
| starts with `<` | **12/72** ✅ reproduces the spec's constant |
| — of which **unresolved** `<...>` | **10** ← what `IsUnresolvedHashMarker` matches |
| — of which **resolved** `<CALL>` | **2** |

🔴 **The 2-decode gap is exactly the resolved-addressee class — and that is the HIGH-RISK half, so my
citation was wrong in the worst possible direction:**

- An **unresolved** `<...>` addressee is **low risk**: `DestMatchesOwnCallsign` explicitly *rejects*
  the unresolved marker, so it can never match this station and can never reach automation. It is
  also visibly `<...>` to the operator.
- A **resolved** `<CALL>` addressee is **high risk**: it looks like a genuine addressee, it **can**
  match via `DestMatchesOwnCallsign`, and it is precisely the 12-bit misresolution exposure
  (`DEFECT-twelve-bit-hash-misresolution.md`, 51.3% wrong names).

⇒ **`IsUnresolvedHashMarker` would have excluded the only subclass that can actually reach QSO
automation.** QA's broader reading is right **on mechanism**, not merely because it matches my
numbers — that latter argument would have been circular. **Good catch, correctly escalated.**

---

## 4. 🔴 THE ADJUDICATION — R-HASH clears its band and still should not ship

ROW 1 puts R-HASH in the **1–10% band**, which my spec mapped to "mark, hide-toggle defaults off".
**But the band alone is not the decision — HK-021(u) exists because a rate without its base rate
misleads, and here it does.**

R-HASH marks **16.7%** of FPs and **7.63%** of real decodes:

| Metric | Value |
|---|---|
| **Likelihood ratio (enrichment)** | **2.19×** |
| R-SOLO, for comparison | **2.15×** |
| **Badge precision**, across FP rates 1–8% | **2.2% – 16.0%** |
| Badges shown per true FP caught | **6 – 46** |

🛑 **A badge that is wrong between 6 and 46 times for every true positive does not earn screen space
or operator attention.** The conclusion is deliberately quoted as a *range* over plausible FP rates
so that it does not rest on `21/840` — which remains **descriptive and NOT a baseline** (guard (e)).
**It is insensitive to that input: the badge is poor at every rate in the range.**

**The honest summary of the whole arm:** four candidates measured, two stopped on sensitivity, and
**the best surviving signal enriches by 2.2×.** ⇒ **No cheaply-available feature separates FP from
real traffic well enough to mark on.** That is a real answer to the PO's original question, and it
is a negative one.

---

## 5. Options for the PO

| | Option | My read |
|---|---|---|
| **1** | **Drop the decode-panel badge.** Keep `decode-implausibility-marking` open but unimplemented, or archive it | ✅ **Recommended** — nothing available earns the badge |
| **2** | **Re-open Option B** (import public-domain boundary data). ⚠️ **Honest re-assessment: my Option-A recommendation has now been tested and it failed, so the geographic route is the only one left that ever looked strong** — 5/5 of the inspected grid-bearing FPs contradicted their own region, against R-HASH's 16.7%. Even discounting hard for n=6, that is a different order of sensitivity. Its false-flag rate remains **unknown and unmeasurable without the import**, and the ADIF validation gap (76.9% in 5 grid fields) is unchanged | Viable, payoff genuinely uncertain — not a flip-flop but the cheap-test-first sequence working as intended |
| **3** | **Ship R-HASH anyway** as advisory-only | 🛑 **Advise against** — §4 |

**Independent of 1/2/3 — the one measurement I would still do:** 🔴 **price
`SuppressUnknownRegion`.** R-UNALLOC is the *same predicate*, already shipping as a **suppressor**,
and its false-suppression rate has never been measured. My spec's STOP consequence meant QA correctly
did **not** compute its ROW 1 — but that conflated two questions. R-UNALLOC is dead **as an FP
marker** (25.9% sensitivity); its **false-flag rate on real traffic still prices a control that is
removing decodes from the panel and from automation eligibility today, invisibly.** That is about
existing shipped behaviour, not this feature, and it is one cheap row on data already pinned.

---

## 6. Process finding worth generalising — QA's assertion caught a fabricated citation

QA's first population build used a sub-agent's citation of a document that **does not exist**,
yielding 36 FPs instead of 72. **The script's own `== 72` assertion caught it before a single
candidate number was computed.**

✅ **This is the standard working.** The lesson is not "distrust sub-agents" but the stronger,
mechanical one: **an established constant belongs in the code as an assertion, not in the prose as a
reminder.** The 72 was in my §1 as a fact to be honoured; QA turned it into a guard that could fail
loudly. **Recommend that pattern for every future arm that inherits a population constant** — and
note it caught, in the same session, a defect that pure review had already missed twice.

---

## 7. Status

- **R-UNALLOC, R-SUFFIX: STOPPED** (verdicts hold post-era-correction). **R-HASH: clears its band,
  recommended NOT to ship** (§4). **R-SOLO: ≥10% band, as anchored.**
- **`tasks.md` stays unwritten.** `design.md` **D2** remains blocking — and on Option 1 there may
  never be a predicate to fill it.
- 🛑 **No FP-rate claim touched.** `FP-REGRESSION` closed; `21/840` still not a baseline.

---

**Architect, 2026-09-05 18:50 UTC.** Committed locally, **not pushed** (HK-014). `git diff --stat --
src/ native/` empty.
