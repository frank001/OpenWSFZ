# ARCHITECT → QA — **TODO**: three housekeeping items, unrelated to any arm

**Author:** Architect → QA (HK-015)
**Date (UTC, `date -u`, HK-017):** 2026-08-29 19:58:51Z
**Type:** Housekeeping. **No arm, no spec, no `src/` or `native/` change.** All three are QA-owned
(HK-011 tooling / repo hygiene) and none is blocked on anything.

These accumulated across the `WIN-A` session and are unrelated to each other. Item 2 is the one that
actually matters; items 1 and 3 are traps waiting for the next person.

---

## 1. 🔴 Pull the `trend.csv` row for the void run

**File:** `qa/rr-study/trend.csv` (currently modified, uncommitted)
**Row:** `2026-08-29,872ba653ce880791c9e3eea587167aaed7cb7af1,0.24664291586733672,28,1.083333333333333,0.5855263157894737,7.663999493450448`

**Why:** the 2026-08-29 run was ruled **VOID as an arm**, and even read purely as a status sweep its
numbers are not comparable to the rest of the series — it was the **first live use** of a 259-line
harness change, and WSJT-X (unchanged code) missed its own pinned S7 figure by 10 observations.
`trend.csv` exists to be a like-for-like series; this row is not like-for-like.

**Do:** remove the row. `trend.csv` has **no notes column**, so there is no way to mark a row as
confounded — the options are "remove" or "silently mislead the next reader".

⚠️ **Worth recording while you are in there (no fix requested):** `analyse.py`'s own comment at
~line 2307 documents this exact class of incident, and the guard added at `d565c57` catches
**filtered/partial** runs. This run was neither — a *complete* sweep on a *changed* instrument, which
that guard cannot see. Not asking you to extend it; recording so the guard is not mistaken for
broader cover than it has.

---

## 2. 🔴 Commit the harness change — it is now the standing instrument and it has NO IDENTITY

**File:** `qa/rr-study/harness/run_scenario.py` — **+182 / −77, uncommitted**

**Why this is the important one.** The Captain has **retained** this change, so it is the instrument
every future sweep will run on. While it is uncommitted it has **no SHA, cannot be pinned in a
pre-registration, and cannot be reproduced.** An instrument that cannot be named cannot be re-run,
and `FT8_SHIM_VERSION`-style labels are exactly what this project has learned not to trust.

**Do:** commit it on its own, with a message describing what it actually does (below), and record the
resulting SHA where the next arm's pins can find it.

⚠️ **Describe it accurately — it is materially larger than "skipping the 15 s silence between
parts", which is how it has been referred to.** From reading the diff, it:

- concatenates every ordinary trial's rendered buffer into **one `sd.play()`/`sd.wait()` call for the
  whole scenario** — whole scenarios play as a single uninterrupted stream (this is the mechanism
  behind S3's DT residual going from an exact −0.800 s constant to −1.200 s ± 0.330 s);
- adds `_SLOT_SAMPLES` to detect and **exclude S3's two oversized parts** (`dt_s` +2.4/+2.7 render to
  721920/736320 samples, not 720000);
- 🔴 **refactors truth-row writing** into a new `_write_truth_row()` parameterised over queued items,
  replacing the inline S8/S7/S4/else dispatch. **`truth.csv` is the ground truth for every metric in
  the battery** — that is a correctness-relevant change, not a timing one.

✅ Credit where due: the diff's own comments show a tolerance-based relaxation was considered and
**rejected specifically because it would inflate DT**. The sensitivity was understood.

⚠️ **It has never been validated live against the unbatched cadence** — verified in simulation only,
and its first live use is the run that was voided. **Not asking for that validation now**; flagging
that it is outstanding so it is not mistaken for done. The readout, when someone wants it, already
exists: WSJT-X's S3 DT residual SD (0.000 s unbatched; require ≤ 0.05 s to pass).

---

## 3. ⚠️ Restore `main`'s DLL into the working tree

**Current state:** both `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` and
`native/ft8_lib_build/libft8.dll` hold **`c82812976e8bd3290a9ac3ff36a8af583b9c3893e48818040263cbc59434c77a`**
— the **Hamming treatment** binary from the now-closed `WIN-A` arm.

**Should be:** `main`'s **`bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`**
(shim `20260046`).

**Why:** `WIN-A` is closed and Hamming is not shipping. Anything run against this tree right now —
a test, a sweep, a demo, a screenshot — silently exercises a **retired experimental decoder**. That
is precisely the "stale binary produces a plausible-looking result" failure you caught during the
08-29 run setup, left armed for whoever comes next.

**Do:** restore from `main` (or check the branch out cleanly) and **assert the SHA afterwards** — do
not infer it from the branch name or the shim version.

⚠️ The branch `experiment/win-a-hamming-rung1` itself is **not merged and not to be merged.**
Retaining or deleting it is your call under HK-003; I have no preference.

---

## Not on this list, deliberately

- 🛑 **`matcher.py` Pass 2 scoping** — real, documented, and provably not affecting any reported
  number (`analyse.py::_compute_fp_rates()` re-windows independently). It was held back to avoid
  stacking a second instrument change on an arm; **that arm is now closed, so it is unblocked** —
  but it is low priority and I am not asking for it here.
- 🛑 Nothing in this file authorises a `src/`/`native/` change, an arm, a merge, or a push.
