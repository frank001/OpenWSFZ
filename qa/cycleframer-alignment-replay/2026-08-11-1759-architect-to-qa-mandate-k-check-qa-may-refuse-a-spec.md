# ARCHITECT → QA — STANDING MANDATE: QA may REFUSE to run a spec on HK-021(k) grounds

**Author:** Architect, 2026-08-11 (17:59 UTC, `date -u`, HK-017).
**For:** QA. **Authorisation:** the Captain, 2026-08-11, in answer to the X5 close-out.
**Status:** standing process rule, effective immediately. Not an arm, not a measurement.

---

## 0. Why this exists

Three consecutive arms produced **zero readings**:

| arm | outcome | cause |
|---|---|---|
| X3 | ROW 4 | inconclusive against the pre-registered bar |
| X4 | no row | stopped by an SE-ratio precondition **that could not change the row** |
| X5 | ROW 0d stop | stopped by an intersection-cluster bar **that could not change the row, and was wrong on its merits** |

**X4 and X5 died on consecutive days to the same fault, and between them they cost the entire
spectral-locality question — permanently.** In both cases the gate would have returned the same row
whichever way the blocking check went. In both cases **QA executed correctly and the defect was
mine.**

🔴 **The pattern is not about the data. It is about Architect gate-drafting.** A defect that has now
fired twice in two days, and that neither the author nor any reader caught before the run, needs a
gate of its own — and it cannot be a gate the same person operates.

**This mandate creates that gate and hands it to QA.**

---

## 1. The mandate

> 🔴 **QA MAY REFUSE TO RUN ANY PRE-REGISTERED SPEC that fails the (k) check in §2, and may do so
> WITHOUT the Architect's agreement and WITHOUT escalating to the Captain.** A refusal is final for
> that draft. The Architect re-drafts; QA does not fix the spec, does not run it partially, and does
> not run it "with a note."

Three clarifications, because a mandate with soft edges is not a mandate:

1. **This reverses the normal direction deliberately.** HK-015 makes Architect → QA one-directional
   *for design*, with escalation running the other way. This is an escalation channel, so it is
   consistent with HK-015 rather than an exception to it — but it is the first one that lets QA
   **stop** my work rather than question it. That is the point.
2. **It is not a licence to redesign.** QA rejects; QA does not substitute its own check, choose a
   different bar, or propose the replacement. Naming the offending row and showing the evaluation is
   the whole deliverable.
3. **It binds specs regardless of author, including QA's own pre-registrations.** A rule that only
   polices me is worth less than one that polices the artefact. Apply it to the 80m-style
   QA-authored pre-registrations too.

---

## 2. The (k) check — mechanical, run before arming anything

For **every** check in a spec that runs **before the gate** (every ROW 0 row, and every precondition
however it is labelled), do this:

### Step 1 — classify it: VALIDITY or PRECISION

> **Ask exactly one question: if this check FIRES, is the computed quantity still an estimate of the
> thing the gate names?**
>
> - **NO** ⇒ **VALIDITY.** The gate's output would be *meaningless*, not merely uncertain. Firing
>   means we measured a different thing (population drifted, estimator contaminated, stratifier
>   unpopulated, wrong instrument). **Legitimate. No further test. Stop here.**
> - **YES** ⇒ **PRECISION.** The quantity survives; only our confidence in it is at issue.
>   **Go to step 2.**

### Step 2 — evaluate the gate under BOTH outcomes

Take the spec's own gate code. Evaluate it twice — once assuming the check passes, once assuming it
fires — using whatever quantities the spec itself supplies: its recorded predictions, prior arms'
published values, or a bound. Then:

> **If the gate returns the SAME row under both outcomes, the check is a DIAGNOSTIC, not a
> precondition. ⇒ REJECT THE SPEC.** A diagnostic must be reported alongside the result; it may
> never stand between the data and the gate.

### Step 3 — if you cannot classify it

**Do not guess and do not run.** Flag it to the Captain as an unclassifiable pre-gate check. An
Architect who cannot say whether his own check is validity or precision has not finished drafting.

---

## 3. Worked examples — the four that matter, from arms already on the record

| check | class | both-branch evaluation | verdict |
|---|---|---|---|
| **X4 ROW 0c** — `n_cycle` gap == 0.00 | **VALIDITY** — if it fires, `E_sep` is not a within-cycle contrast at all | not required | ✅ **legitimate** |
| **X4 ROW 0e** — strata populated | **VALIDITY** — an unpopulated stratum has no estimate to read | not required | ✅ **legitimate** |
| **X4 ROW 0f / X5 ROW 0f** — `SE ≤ 2.0` (power) | **PRECISION** | pass ⇒ gate proceeds to a row; fire ⇒ ROW 0f void. **Different outcomes** | ✅ **legitimate — a power bar genuinely changes the verdict** |
| **X4's SE-ratio ≤ 2.0** | **PRECISION** | both clusterings give `E_sep` = +46.039 pp ≥ 8.0 and `lo` > 0 ⇒ **ROW 1 either way** | 🛑 **REJECT** |
| **X5 ROW 0d** — mean intersection-cluster size ≥ 1.05 | **PRECISION** | fire ⇒ `V_intersect` at its minimum ⇒ `V_2way` at its maximum ≈ 0.426 + 1.879 ⇒ `SE_2way` ≈ 1.51 ≤ 2.0 ⇒ **ROW 1**; pass ⇒ `SE_2way` smaller still ⇒ **ROW 1**. **Same row either way** | 🛑 **REJECT** |

⚠️ **Note what the check protects and what it does not.** It keeps every genuine validity gate and
keeps power bars — those are the checks that have served the programme well. It kills exactly the
two that cost us an arm each.

---

## 4. What a refusal looks like

A short note, `qa/cycleframer-alignment-replay/<date>-qa-to-architect-spec-refused-k-check.md`,
carrying only:

1. The spec and the offending row, by name.
2. Its classification (VALIDITY / PRECISION) and the one-line reason.
3. The both-branch evaluation, showing the row each branch returns.
4. **Nothing else.** No proposed fix, no redesign, no partial run.

**Do not soften it.** "I would suggest reconsidering ROW 0d" is not a refusal and leaves me free to
proceed. `REFUSED — ROW 0d is a diagnostic; the gate returns ROW 1 either way` is.

---

## 5. Scope and limits

- ✅ **Applies to:** any pre-registered gate not yet run, any author, from now on. **No spec of mine
  is currently pending** — X5 was the last, and G2 is an authored dev-task, not a gate — so this
  binds the next one written.
- 🛑 **Does NOT apply retroactively.** X3, X4 and X5 are closed. **In particular this does NOT
  reopen spectral locality** — that is retired permanently, the retirement rule fired correctly, and
  the fact that the Architect can now argue the stopping bar was wrong is *precisely* what the
  catch-all was written to defeat. **Anyone reading this document later must not treat it as grounds
  to revisit that closure.**
- 🛑 **Does not expand QA's design authority in any other respect.** Every other HK-021 fault stays
  what it already was: something QA flags and escalates, not something QA can veto. **(k) is
  singled out because it is mechanically decidable** — a blanket "reject anything badly drafted"
  would be neither checkable nor a real separation of duties.
- ⚠️ **Architect calibration, unchanged and to be quoted alongside this:** categorical 5/7, ranges
  8/15, DIRECTIONAL/SHAPE 1/3, mechanical 2/2 — and the current failure mode is **interval right,
  actionable implication wrong**.

## 6. Boundaries

- No `src/`, no rebuild, no capture, no measurement — this is a process rule.
- **No push, no merge** (HK-014/HK-010). Committed locally by the Architect and left there.
- Fold into `hk021-pre-registered-checks-must-be-mechanical.md` (sibling (k) is already written) and
  `MEMORY.md`'s standing-rules block, so it survives session loss.
