# The D-001 gap attribution ledger — every improvement on record, added up

**Architect, 2026-08-23 21:13Z.** Captain-directed: *"I want an overview of all possible
improvements from all the tests we have done with the potential small percentage of improvement.
At the end of that table I want all the potential improvements added together."*

🔴 **EXPLORATORY. NOT A PRE-REGISTERED RESULT. NO ROW. DO NOT CITE ANY FIGURE BELOW AS A RESULT.**
The census figures were computed by the Architect while answering a question in conversation.
They are pre-registered for independent derivation by QA as `GAP-CENSUS-A`
(`2026-08-23-2113-architect-to-qa-spec-gap-census-a.md`), and **Architect prediction scoring on
that arm is suspended** because this document de-blinded it.

Corpus: `artefacts/20260803_live_run_1713/` (D-001 replication corpus). Raw distinct
`(timestamp, message)` keys, no exclusions: ours 64,417 · theirs 43,423 · both 24,729 ·
**theirs-only 18,694 ⇒ D-001 = 43.05 %**. (The 42.2 % on record is a different, filtered basis;
reconciliation is `GAP-CENSUS-A` ROW 0a.)

---

## Table 1 — ADDITIVE. An exhaustive partition of the gap.

Every missed decode falls in exactly one bucket. These sum to the whole gap by construction.
Buckets B1/B2 are **null-corrected** — see the note below, it halved them.

| # | bucket | observed | null | excess | **pp of D-001** | recoverable by |
|---|---|---|---|---|---|---|
| **A** | Reference decode **below `f_min = 200 Hz`** — we have no aperture | 1,154 | n/a | 1,154 | **2.66** | opening the passband |
| **B1** | We decoded it; **our text carries an unresolved `<...>` hash** | 754 | 61 | 693 | **1.60** | hash resolution |
| **B2** | We decoded it; text differs otherwise | 1,133 | 793 | 340 | **0.78** | text/callsign diagnosis |
| **C** | **No decode of ours within 4 Hz — genuine DSP miss** | — | — | 15,653 | **≈ 38.01** | actual decoder work |
| | **TOTAL** | | | **18,694** | **43.05** | |

🔴 **A + B1 + B2 = 5.04 pp of the gap is not a decoding problem at all.** It is aperture and
text rendering.

---

## Table 2 — ADDITIVE. The school of small fish: everything gainable without decoding better.

| item | value | status | source |
|---|---|---|---|
| **Open the passband to 140 Hz** | **+2.66 pp** ⚠️ ceiling | **G2(b) ladder specced, 5 Architect reviews, NEVER ARMED** — blocked behind R0 | census |
| **Hash-text resolution** | **+1.60 pp** | **G2(a) 256→4096 ALREADY MERGED (`9500e03`, 2026-08-13) and never re-measured** | census, null-corrected |
| **Other text mismatch** | **+0.78 pp** | Undiagnosed; C-GAP-D's T3 (callsign char differs) is the likely population | census, null-corrected |
| **Time-origin offset (`AO1`)** | **+0.71 pp** `[0.49, 0.93]` | Measured, closed as a D-001 route, **product fix not authorised**. Offset is shared with the reference (`D1`), so this is absolute recall, not gap-closing — may partly sit inside bucket C | `AO1` Part C |
| **D-009 45-point OSD sweep** | **+0.11 pp** | Measured, marginal | D-009 |
| | **SUM ≈ +5.9 pp** | **≈ 14 % of the entire gap, with zero DSP improvement** | |

---

## Table 3 — NOT ADDITIVE. Real numbers that may not be summed, and why.

| item | value | why it cannot be added |
|---|---|---|
| Extraction-quality ceiling (`C-GAP-D` `G(3)`) | **6.995 pp** `[6.897, 7.172]`; all six band-legs `[4.66, 7.17]` | A **ceiling inside bucket C**, not an increment beside it. ROW 1 fired ⇒ extraction is *not* D-001's route; no realisation path exists. |
| Frequency quantisation (`T1` `G`) | **≥ 3.16 pp** (a floor) | Inside C. Treatment = finer lattice = **OSR change = closed**. |
| Lattice placement cost (`P3` `S_all`) | 4.27 pp | Inside C, **and doubly compromised**: ran pre-hash-randomisation-fix (UNVERIFIED) on `d001-rc4-decode-depth`'s unmerged DLL (~+0.70 pp confound). |
| Crowding (`X2` `F_std`) | **+17.22 pp** `[14.99, 19.38]` | A **contrast** between density regimes of our own recovery, not a share of the gap. Mechanism now permanently unreachable (X4/X5). |
| Band (`X1` `B_std`) | **+5.70 pp** | A contrast between bands. |
| Interior-worst-case (`X3` `U`) | 1.85 pp | **ROW 4 — no reading. Not citable.** |
| Near-neighbour exclusion (`F-NBR-A`) | 3–5 tone bins, level-ratio knife-edge | Real, deterministic mechanism; **live magnitude permanently unmeasurable**. A2 authorises no treatment. |
| Limb 2 (order-3 coherent extraction) | 0/403 on 67 clusters | Thin bound; may not be described as a D-001 treatment (C-GAP-D ROW 1). |
| Spectral locality (`X4` `E_sep`) | +46.039 pp | **Permanently uncitable.** Retired, four attempts, zero readings. |

---

## Table 4 — Measured at or below zero. Closed.

| item | value |
|---|---|
| `K_MAX_PASSES` 2→3 (RC4) | recall **0.000** — CPU and memory cost for nothing |
| `osd_nhard_max` 60→40 (D-009 Option B) | recall **0.000**, and makes OSD shallower where RC1 localised |
| Pass-1 suppression ramp | closed — over-suppression confirmed; duty cycle now measured (`Z = 0.6567`) but authorises no change |
| Limb 1 (per-candidate complex-baseband refinement) | **−4.02 pp — active harm**, replicated at scale |
| Candidate budget (caps, passes) | closed twice — and now confirmed from a third direction: **max 30 decodes in any cycle against caps of 340/540. The cap has never bound.** |
| Upper passband ≥ 3000 Hz | **zero on both legs.** Raw WAV puts `[3000,3030)` at **−42.9 dB** — the radio's own filter. "Zero gains in `[3000,3030)`" is permanently uncitable. |
| Inward edge effect above `f_min` | **hypothesis killed this session.** Miss rate `[200,250)` = **19.9 %** against a `[700,3000)` baseline of **38.3 %** — *better* than average. The passband prize is the out-of-band census and no more. |

---

## The correction that halved Table 2, disclosed

My first pass counted co-located decodes directly and reported B1+B2 as **4.35 pp**. That was
wrong by roughly a factor of two.

Our decode density is ~14 per cycle over 2,800 Hz, so an 8 Hz matching window catches accidental
neighbours at a rate comparable to the effect. A circular-shift null returns a mean of **854**
accidental co-locations against 1,887 observed ⇒ true excess **1,033 = 2.38 pp, not 4.35 pp**.
The null splits very unevenly — **61 for B1, 793 for B2** — so **roughly 70 % of bucket B2 as I
first counted it was noise**, while B1 is nearly all real.

**A co-location count without a null is not a result.** `GAP-CENSUS-A` §5.2 makes the null
mandatory, requires ≥ 200 offsets rather than my five, and requires a second null of a different
construction as a cross-check.

---

## What the ledger says

**The school of small fish is ≈ 5.9 pp — about 14 % of the gap — and it is worth more than every
open DSP route combined.**

Two of the three largest items are already built. **G2(a) is merged and has never been
re-measured. G2(b) is fully specced, survived five Architect reviews, and has never been armed.**
Neither needs new code.

The big fish, bucket C, is **38 pp** and every route into it is closed, bounded, or unreachable:
extraction is capped at ~7 pp and ruled not to be the route; the candidate-budget family is
closed twice and now demonstrably never binds; spectral locality is retired; the near-neighbour
mechanism is real but its live magnitude cannot be measured; limb 1 is harmful and limb 2 is
held on a thin bound.

**The expected return is inverted from how the programme has been prioritised.** That is the
Captain's read, and the arithmetic supports it.

⚠️ Three caveats, so nobody banks 5.9 pp:

1. **Bucket A is a ceiling, not a delivery** — it assumes we recover every sub-200 Hz signal
   through a chain 21.5 dB down. Burned `[140,200)` yield was **2.71 % against a 1.00 % bar**:
   real, but partial.
2. **Bucket B may be smaller than it looks.** Our `<...>` rate on this corpus is **6.75 %**
   against the reference's **6.61 %** — near parity, unlike the 5.5 %-vs-1.7 % that motivated
   G2(a). Hash-table sizing may not be the whole of B1.
3. **`AO1`'s 0.71 pp may partly sit inside bucket C** rather than beside it, and the offset is
   shared with the reference, so correcting it gains absolute recall rather than closing the gap.

---

## Recommended sequencing, for the Captain's decision

1. **`GAP-CENSUS-A`** — make these numbers citable. Counting only; every input already on disk.
2. **Re-measure the gap on a post-G2(a) binary.** Every headline D-001 figure in play was
   captured before that merge. Cheapest item on the board.
3. **Arm the G2(b) passband ladder.** Largest single identified item; already designed.
4. **`OSD-FA-A`** — specced and unrun; answers a different question (are *our* exclusive decodes
   false), and remains the right next DSP-side arm.
