# Architect → QA: SPEC — Stage 1RE, limb 2 at scale on the CORRECTED anchor

**Author:** Architect
**Date:** 2026-08-21 15:38 UTC (`date -u`, HK-017)
**Authorised by:** the Captain, 2026-08-21 — Stage 1 re-run sequenced **BEFORE** the Phase B
Developer session.
**Supersedes in execution (not in provenance):** P-LIVE Stage 1, withdrawn
`2026-08-18-1616-architect-to-qa-p-live-stage1-ruling-anchor-provenance-defect.md`.
**Predecessors:** `2026-08-17-1806-…-p-live-population-and-n-series-replication-spec.md` (Stage 1 as
originally pre-registered) · `2026-08-18-1824-…-stage1r-results.md` (+0.65 s) ·
`2026-08-18-2013-…-stage2-results.md` (the ROW 0 structure this spec reuses) ·
`2026-08-17-1744-…-retraction.md` §102-115 (N5's honest 4.37 % bound)
**Binary under test:** current merged `main` (`a420016`), shim **20260043**, DLL SHA256
`1889408787a2c7ea…`. **No native change. No Developer session. HK-011 NOT engaged.**

---

## 0. Why this runs, and why it runs FIRST

**Limb 2 has never been measured at scale.** The P-LIVE stage map, verified from the reports this
session rather than from the board's summary of them:

| Stage | Question | Limb | Fate |
|---|---|---|---|
| **1** | N5's outcome conversion at scale | **2** | ran, **WITHDRAWN**, never re-run |
| 2 | N1's refinement harm at scale | 1 | ran on **3,916 clusters**, ROW 3 HARM |
| 3 | N2 at scale | 2 | **never ran** |
| 4 | N4 at scale | — | never ran |

⇒ limb 2's only outcome number is still N5's `0/403` on **67 clusters**, whose honest bound is
**4.37 %** (rule-of-three on CLUSTERS, `1 − 0.05^(1/67)`), **not** the degenerate `[0.00, 0.00]`
bootstrap CI. 🛑 **N5 is UNRULED/HELD and has never been CONFIRMED. Do not cite `0.00 %` in any
form.**

At ~12,000 clusters a zero yields a bound of **~0.025 %** — a ~175× tightening. Per the 1806 spec's
own words: *"Limb 2 closes or opens properly, for the first time."* This is pure re-analysis and it
precedes committing a native session to Route B2.

🛑 **This does not re-open, amend or delay the Phase B spec (1525Z), which stands as authorised.**
It changes the ORDER only.

---

## 1. The three defects that killed Stage 1 — every one gets an explicit remedy

The 1616Z ruling named three. A re-run that fixes only the famous one repeats the failure.

| # | Defect (1616Z) | Remedy in this spec |
|---|---|---|
| **D-a** | **Anchor in the wrong convention.** Stage 1 passed WSJT-X's raw `ALL.TXT` DT to `ft8_extract_llrs_at`, which expects a **buffer-relative** offset. | §2 — the corrected offset, **derived on this run**, not inherited. |
| **D-b** | **ROW 0f was ONE-SIDED and blind to the falsifying direction.** A mis-anchored extraction pushes BER *toward 50 %*; ROW 0f could fire only on implausibly *low* BER, so the symptom scored as PASS. (Minted HK-021(n).) | §3 ROW 0c — **two-sided**, reusing Stage 2's own proven bracket. |
| **D-c** | **No positive control of any kind** (`grep control run_stage1.py` → zero hits). | §3 ROW 0b — a P-HIT control measured **on this run**, proving the instrument is pointed correctly before P-LIVE is touched. |

⚠️ A fourth, from the N5 spec's own Amendment A1.2 and repeated in the 1616Z ruling: **an outcome
statistic that counts only crossings is blind to breakages.** §4 gates on **`f_net`**, signed.

---

## 2. The anchor — derive it on this run, do not inherit it

🔴 **The two measured offsets are NOT in conflict and must not be averaged, swapped or
"reconciled":**

- **M3's +0.45 s** was measured **through the sync refiner** (`ft8_extract_llrs_at`'s companion
  coarse search).
- **Stage 1R's +0.65 s** was measured **directly at `ft8_extract_llrs_at`'s own entry point** — the
  call this arm makes. Independently re-derived by Stage 2 Part A to three significant figures
  (median `BER_V0` 5.75 %), with **perfect chronological quartile stability (max deviation
  0.000 s)** and replication on a **second corpus**.

⇒ **+0.65 s is the correct convention for this arm.** Nevertheless:

🔴 **Sweep for it on this run rather than hardcoding it** — reuse Stage 2 Part A's derivation
verbatim (`m3_common.TIME_ANCHOR_OFFSETS_S`, seeded P-HIT sample) and adopt the swept argmin.
Report it. **If the swept argmin differs from +0.65 s by more than one lattice cell (0.08 s), STOP
and escalate** — that is an instrument change, not a nuisance parameter.

🛑 **Stage 1R explicitly bars re-reading Stage 1's published numbers with a +0.65 s correction
applied.** This is a **re-run**, not a re-interpretation. The withdrawn numbers stay withdrawn and
are not compared against, quoted, or used to set expectations in the report.

---

## 3. Preconditions — strictly ordered, each changes the verdict (HK-021(k))

Reuse Stage 2's own ROW 0 structure (HK-018 — it was written *after* the ruling and has passed once).

- **ROW 0a — binary pin.** Re-hash the DLL and assert SHA256 + shim version against the pinned
  manifest **before arming**. Never infer from a label.
- **ROW 0b — POSITIVE CONTROL, on this run (remedies D-c).** On the seeded **P-HIT** sample at the
  swept offset, median `BER_V0` must land inside **[1.0 %, 15.0 %]**. This proves the extraction is
  pointed correctly *tonight, on this data, through this binary*. **Outside ⇒ VOID, escalate, do not
  proceed to P-LIVE.**
- **ROW 0c — TWO-SIDED anchor sanity (remedies D-b).** Median `BER_grid` on the P-LIVE population
  must lie inside **[8 %, 40 %]**. 🔴 **Both bounds are load-bearing.** The upper bound is the one
  that would have caught Stage 1: a mis-anchored extraction reads ~50 % and MUST fire. A one-sided
  floor here is decorative (HK-021(n)).
- **ROW 0d — offset stability.** Split the P-HIT sweep sample into four chronological `ts` quartiles;
  each quartile's own argmin must sit within **0.05 s** of the pooled argmin. **Any quartile outside
  ⇒ VOID, escalate.**
- **ROW 0e — population floor.** Fewer than **500 rows** or **200 clusters** delivered ⇒ **STOP and
  escalate** rather than run. Report rows AND clusters (HK-021(i)); **never pass `limit=` to any
  population helper** — it truncates in file order.

---

## 4. The measurement

Reuse Stage 1's own pre-registered arms and definitions **verbatim** (V0 grid vs V3_cum coherent, at
the anchor, **no search of any kind** — design.md D1 discipline). The only changes from the
withdrawn run are §2's anchor and §3's preconditions.

**Primary statistic — signed, two-sided (remedies A1.2):**

```
f_net = (n_cross - n_break) / n_crossable          per-row, then cluster-bootstrapped by ts
```

- `n_cross` — rows V0 fails and V3_cum decodes. `n_break` — rows V0 decodes and V3_cum fails.
- 🔴 **HK-021(l): report `f_net` SIGNED. Never gate on `|f_net|`, and never report `f_cross` alone.**
- 🔴 **HK-021(i): bootstrap by `ts` CLUSTER. Report cluster counts everywhere.**
- 🔴 **Report the rule-of-three bound explicitly ALONGSIDE the bootstrap CI, computed on CLUSTERS:
  `1 − 0.05^(1/n_clusters)`.** If `n_cross = 0` the bootstrap CI is **degenerate by construction** —
  every resample returns zero — and quoting it as a real interval is the exact defect that
  overstated N5. **The rule-of-three number is the headline; the bootstrap CI is secondary.**

### ROWs — strict, exclusive, exhaustive, two-sided

| ROW | Condition | Assertion / consequence |
|---|---|---|
| **1** | `CI_lo(f_net) > 0` | **LIMB 2 CONVERTS.** Coherent LLRs convert real misses at scale. Route B2 is strongly motivated; Phase B becomes high-value. Report the point estimate against the ~42 pp gap — a conversion rate is not yet a recovered message. |
| **2** | CI contains 0 **and** rule-of-three bound (or `CI_hi`) **< 0.5 %** | **LIMB 2 CLOSES.** At this cluster count the prize is bounded below 0.5 % of the crossable population. 🔴 **Escalate to the Captain before any Phase B Developer session — this materially changes what Route B2 is worth.** |
| **3** | CI contains 0, bound in **[0.5 %, 5 %]** | **STILL OPEN, TIGHTER.** N5's 4.37 % is improved but not decisive. Phase B proceeds as authorised. |
| **4** | `CI_hi(f_net) < 0` | **LIMB 2 HARMS.** Coherent LLRs break more than they convert — the limb-1 pattern (Stage 2 ROW 3) repeating on limb 2. Escalate hard; **do not proceed to Phase B without a Captain ruling.** |

**HK-021(m), resolvable distance stated while drafting:** at ~12,000 clusters the rule-of-three
quantum is `1 − 0.05^(1/12000)` ≈ **0.025 %**, so ROW 2's 0.5 % bar sits ~20× above the resolution
floor and ROW 3's boundaries are comfortably resolvable. At the ROW 0e floor (200 clusters) the
bound is ≈1.5 %, which still resolves ROW 2 vs ROW 3 but **not** finely — if delivery lands near the
floor, say so plainly in the report rather than quoting a bound the cluster count cannot support.

---

## 5. Cost and prohibitions

Stage 1 measured 15,389 rows in ~20 minutes of compute. Budget generously; **do not truncate the
population and do not sample it down** — cluster count is the entire point of this arm.

- 🛑 **No `src/`/`native/` edit, no rebuild, no push, no merge.** HK-011 not engaged.
- 🛑 **ROW 0g stands FIRED, task 4.3 stays VOID, ROW 3 (Phase 1's numbering) is not declared, and
  Route B2 is NOT dead** — nothing in this arm bears on any of that.
- 🛑 **The withdrawn Stage 1 numbers stay withdrawn.** Not cited, not compared against, not used to
  set expectations. `f_cross = 0/15,389` and the 0.0765 % bound may not appear in the report.
- 🛑 **N5 is not re-ruled by this arm.** If ROW 1 or ROW 4 fires, N5's own 4.37 % bound is
  contradicted at scale and that is an escalation to the Architect, not a QA ruling.
- 🛑 B3 stays HELD; the Phase B spec (1525Z) is unchanged and still authorised.
- ⚠️ HK-025 available on every row: classify, evaluate both branches, refuse rather than part-run.

---

## 6. Predictions (Architect, recorded before the run)

- **ROW 3 (still open, tighter): ~45 %.**
- **ROW 2 (limb 2 closes below 0.5 %): ~35 %.**
- **ROW 1 (converts): ~15 %.**
- **ROW 4 (harms): ~5 %.**

⚠️ My directional record is 2.5/5.5, I got 0g-2 wrong at ~70 % stated, and I overstated N5 to the
Captain earlier today by quoting a degenerate CI as a real bound. Weight these accordingly.

## 7. What I have NOT established

- **That the anchor is now right.** It is measured three ways and stable, but P-LIVE's population is
  *by definition* one where we detected nothing, so it can never anchor on our own candidate. §3's
  ROW 0b control exists precisely because that weakness is structural and permanent.
- **That a null here kills Route B2.** It would bound the ADDITIVE-fusion Python prototype's
  conversion rate. ⚠️ **The C path fuses differently — max-magnitude across `n_syms` (= C1) — so
  this arm does not test C1 and cannot speak to it.** A ROW 2 makes Route B2 much less attractive;
  it does not by itself close it.
- **That limb 2 and the ~42 pp gap are the same size question.** They are not, and a conversion
  fraction must never be quoted as a recovered-message count.
