# `FP-FLOOR-LIVE-2` Amendment 3 — PO-directed: discard everything captured so far; the corpus restarts clean at `19:36:45Z`

**Architect, 2026-09-08 19:33Z** (`date -u`, HK-017). Branch `arch/fp-floor-operator-setting`.
**Committed before the new start time, and before any outcome has been read.**

**PO direction, verbatim:** *"This is a multi hour run overnight. just throw all the data up to now
away for my part. I don't want any possible contamination."*

---

## 1. Ruling — applied, and it is the CLEANER option, not a concession

🔴 **All decodes before `2026-09-08T19:36:45Z` are discarded.** The corpus is everything from that
boundary forward.

**Pinned mechanically and outcome-blind:** the timestamp is the first FT8 cycle boundary at least
three minutes after this ruling was written — derived from the clock, **not** from the data, and
fixed before the capture reaches it. 🛑 **It was not chosen by looking at counts, and no `K_removed`,
`k`, or corroboration figure has been computed at any point in this arm.**

**Why this is better than the two-span corpus it replaces:**

1. ✅ **The interior gap disappears.** Amendment 2 left `18:36:15–18:52:45` excised, making the
   corpus a union of two spans — a shape that had to be carried into Part B and explained. **The
   corpus is now a single contiguous span.**
2. ✅ **It is strictly more conservative.** It discards *more* than any prior boundary, including
   the pre-disturbance span nobody suspected, and every minute during which the operator was near
   the rig at all.
3. ✅ **It ends the contamination question outright** rather than adjudicating it. The PO's judgement
   — that a few tens of minutes are worth nothing against a 13-hour overnight run — is correct
   arithmetic, and the argument was costing more than the data.

**Cost:** ~69 minutes of a run whose stopping rule needs ~7–14 h. Immaterial.

## 2. Amendment 2's closure guard is SATISFIED, not bypassed — stated so it cannot be cited as precedent

Amendment 2 closed the disturbance-exclusion window and required any later request to be
**escalated and not applied.** That is exactly what happened: the request came to the Architect, no
outcome existed, and the decision is recorded in the open with its cost visible.

🛑 **This does not reopen the window. It closes it harder.** From `19:36:45Z` the corpus boundary is
**FIXED**:

- **No further exclusion, trimming or restart may be applied** — by QA, the Architect, the Captain
  or the PO — **once any outcome figure has been computed.** Such a request is escalated and
  reported with the arm read **both ways**, never applied silently.
- 🔴 **The distinguishing test, and the only one that matters: has anything been READ yet?** Every
  boundary change in this arm so far has been made with **zero** outcome visible, which is what kept
  each of them legitimate. **After the first `K_removed` is computed, that protection is gone
  permanently and no good faith substitutes for it.**

## 3. Mechanical consequences for QA

1. **`n` resets to zero at `19:36:45Z`.** Everything before it leaves the corpus entirely — it is
   not a second excluded span, it is simply not part of the run.
2. **The stopping rule runs from the new start:** `n ≥ 600` **or** 24 h **measured from
   `19:36:45Z`**, whichever first. ROW A2's `n < 200 ⇒ VOID` likewise.
3. **`REF = A` only** (Amendment 1) — unchanged, and now trivially constant across a single
   contiguous span.
4. **Do not delete the discarded audio or logs.** They stay in `artefacts/` as provenance; they are
   simply outside the analysed corpus. Record the boundary and this ruling's filename in
   `contents.md`, with the prior entries **struck, not deleted** (HK-034).
5. ⚠️ **Re-assert `captureActive=true` and `decodingEnabled=true` at or after the boundary** and
   record the check — the corpus now begins at a timestamp nobody has yet confirmed the rig was
   healthy at.

## 4. Everything else stands

ROW 0a–0e, ROW A1/A2, wildcard matching, Amendment 1's `REF = A`, the rounding bound, the power
disclosure, and the PO-ratified `hi ≤ 0.02` — all unchanged.
