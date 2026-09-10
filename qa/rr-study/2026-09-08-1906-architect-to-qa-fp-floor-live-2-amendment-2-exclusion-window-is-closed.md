# `FP-FLOOR-LIVE-2` Amendment 2 — the operator-disturbance exclusion window is CLOSED, and its endpoint must be confirmed against the Captain's account

**Architect, 2026-09-08 19:06Z** (`date -u`, HK-017). Branch `arch/fp-floor-operator-setting`.
**Committed while the capture is still running and before any outcome is readable.**

**Trigger:** QA reported that the Captain, after stopping SDR Uno, said they *might* have disturbed
audio to `WSJT-X #1` or OpenWSFZ while troubleshooting the shared Voicemeeter rig. QA checked
thoroughly — noise-floor and decode-count series on **both** decoders' independent `ALL.TXT`,
cycle-audio clip/gap/drop counters, supervisor health — **found nothing**, reported that, and at the
Captain's request applied a precautionary exclusion anyway. Effective corpus start moved
`18:33:11Z → 18:36:15Z`; cost 2 decodes (`n` 31→29).

---

## 1. ✅ QA is right that HK-021(y) does not fire — and the reasoning needs both halves stated

QA's argument: the boundary is fixed by **when the Captain says they touched hardware**, not by how
the data looks. **Correct.** (y)'s drafting question is *"if I had not already seen the counts, what
would have told me to put the boundary here?"* — and here the answer is a real external event, in
the same class as a merge, a build or a deployment.

🔴 **But it holds only because BOTH conditions are true, and they must both keep being true:**

1. the boundary derives from an **event external to the outcome** — the operator's own account of
   physically handling equipment; **and**
2. it was applied **before any outcome was readable.**

**If either fails, (y) fires.** Recording both, because in three weeks only the first will be
obvious from the file.

## 2. 🔴 The exclusion window CLOSES NOW — this is the amendment's substance

A precautionary exclusion granted on an operator's recollection is legitimate. **A standing
willingness to grant more of them is not**, because recollection can be revisited after results
exist, and a corpus that can be trimmed by later recollection is a corpus selected on its outcome —
(y) arriving through the back door, wearing an operator's good faith as cover.

⇒ **The disturbance-exclusion window is fixed at whatever §3 establishes and is CLOSED from this
commit.**

🛑 **Any further request to exclude a span for operator-disturbance reasons, made after this point,
is to be ESCALATED AND NOT APPLIED — by QA, without the Architect's agreement, and regardless of who
asks.** That includes the Captain, and it includes me. QA reports the request, the span, and what
the arm reads **both with and without it**; the decision is then taken in the open with the cost
visible, rather than by quietly shortening the corpus.

⚠️ **This is not a statement of distrust and must not be read as one.** It is the same discipline
`R&R-011`'s `WINDOW_SLOTS`/`CEILING` freeze applies to the Architect's own parameters: **the time to
fix a boundary is before you can see what it buys.**

## 3. 🔴 ACTION FOR QA — confirm the window's ENDPOINT, from the Captain, not from the data

**The exclusion as applied ends at `18:36:15Z`. The SDR Uno stop was `18:52:45Z`.** Those are ~16
minutes apart, and the troubleshooting that *concluded* in stopping SDR Uno plausibly **spanned**
that gap rather than ending before it began.

🔴 **If the Captain was handling the shared Voicemeeter rig from ~18:33 through to the 18:52:45 stop
— or after it — then the exclusion covers the beginning of the disturbance and leaves the rest of it
inside the corpus.** Excluding the wrong 3 minutes is worse than excluding nothing, because it
creates a *documented* reassurance that the contaminated span was removed.

**QA to ask the Captain directly:** *over what wall-clock span were you physically handling the
audio rig — start and end — including anything after the SDR Uno stop?* Then set the exclusion to
that span.

🛑 **Derive the endpoint from the Captain's answer alone. Do NOT look for where the data "goes back
to normal" and cut there** — that is exactly (y), and QA's own clean check already established there
is no visible anomaly to cut on, so any data-derived endpoint would be fitting a boundary to noise.

⚠️ **If the corrected span turns out to run past the SDR Uno stop, the cost stops being negligible.
Report the cost; do not absorb it, and do not trim the span to keep it cheap.**

✅ **Excluding at the START of a run is the safe place to do it** — it shortens the corpus rather
than putting a hole in the middle. If the corrected span is contiguous from the run start, that
property is preserved. **If it is not contiguous, say so explicitly**: an interior gap changes the
corpus's shape and must be visible in Part B, not buried in `contents.md`.

## 4. Sizing — anchor corrected, and deliberately not recomputed

The Architect's `~44/h` was anchored to the original `18:27Z` start; the effective clock now begins
~9 minutes later. **Negligible against the ~4.5 h / ~13.6 h projections and the 24 h cap, and it is
not being recomputed here** — the projection's only job is to confirm the cap is not binding, which
it still is not. 🛑 **`n` and its arrival rate remain stopping-rule quantities only.**

## 5. Everything else stands

Amendment 1 (`REF = A` only, for the whole corpus), ROW 0a–0d, ROW A1/A2, wildcard matching, the
rounding bound, the power disclosure, and the PO-ratified `hi ≤ 0.02` — all unchanged.
