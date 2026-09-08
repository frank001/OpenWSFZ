# `R&R-011` Amendment 1 — a VOIDed run contributes NO slots to the window; and `INFO` is not VOID

**Architect, 2026-09-08 15:09 UTC** (`date -u`, HK-017). Amends
`qa/rr-study/2026-09-08-1452-architect-to-qa-spec-rr-011-s5-trailing-window-gate.md` after QA's
implementation (`20223d5`) and QA's question about the absent-S4 case.

🛑 **The gap this closes is a defect in MY spec, not in QA's implementation.** QA implemented §3 as
written; §3 never said what happens to a VOIDed run's **slots**, and the answer turns out to matter.

---

## 1. QA's question — answered: VOID, exactly as implemented

**"S4 did not run at all" is VOID, not `NOT_RUN`.** QA's reasoning is adopted verbatim: *a control
that never ran isn't a control that ran clean.* All four branches of `_s5_row0a_void` (S4 absent,
confusion counts unavailable, zero messages injected, recall == 0) are "no positive control
available" and all four are correctly VOID.

✅ **And the conservative choice is now known to cost nothing observed.** I checked the run that
would have been most at risk — `4c7d5ad`, the *targeted S5-only* run sitting in the seed window. It
carries a **live S4: 198 matched OpenWSFZ decodes** (`S4_matched.csv`, 543 OpenWSFZ rows). Every run
that has ever entered the window has a live positive control, targeted runs included. **Blast radius
of this amendment: nothing today. The §5 worked example and QA's pinned test are unchanged.**

⚠️ If a future run ever does VOID here, **that is the trigger to re-draft, not to argue the run
through.** Do not narrow ROW 0a in the moment to rescue a run.

---

## 2. 🔴 THE GAP — a VOIDed run still poisons the window

`_append_trend` writes `fp_events_s5` / `fp_slots_s5` from `fp_results` **unconditionally**
(suppressed only for `--scenario-filter` runs). So today, a sweep whose ROW 0a fires:

1. correctly refuses to score **itself** — `{"status": "VOID", "row": "0a"}`, and
2. **still writes its counts to `trend.csv`**, where the *next* sweep's `_s5_window_history` admits
   them into the window.

**A dead audio chain yields `0/120`. It cannot score itself — and then it deflates the window that
scores everyone else, making Gate A-W pass more easily for four sweeps.**

🔴 **That is sibling (n) one level up.** §3's ROW 0a closed the degenerate-instrument hole for the
*sweep* and left it open for the *window* — the object the gate actually reads. The spec's own
§4.7 confound bound does not catch it either: leave-one-sweep-out would show the deletion *raising*
the rate, which reads as reassuring.

### The amendment

> 🔴 **A run whose `_s5_window_gate` returns `VOID` (any ROW 0 row) or `NOT_RUN` contributes ZERO
> slots to the trailing window. `_append_trend` MUST write `fp_events_s5` and `fp_slots_s5` EMPTY
> for that run.** The window then accumulates to 480 from older runs, which the existing
> newest-first fill loop already does unmodified.
>
> 🛑 **`INFO` is NOT VOID.** A ROW 0c `INFO` (window not yet full) says nothing is wrong with the
> run — only that the *window* is short. **Its counts MUST still be persisted.** Suppressing them
> would discard good data and permanently stall the fill.

**Mechanically:** the trend write must be conditioned on the `_s5_window_gate` result, so
`_s5_window_gate` has to run **before** `_append_trend` (or its status be threaded to it). Suppress
on `VOID` / `NOT_RUN`; persist on `SCORED` **and on `INFO`**.

---

## 3. Definitional gap in my own §3 code, closed here before it is called a defect

The fill loop breaks *before* appending once `n >= WINDOW_SLOTS`, so the last admitted run can carry
the window past 480. **The window is therefore "at least 480 slots, composed of WHOLE runs", with
overshoot bounded by the largest single run (120) ⇒ N ∈ [480, 599].**

✅ **Accepted as-is, and it is not a defect:** `P(UB₉₅ ≤ C | p = C) ≤ 0.05` holds at **every** N, so
overshoot cannot loosen the ceiling — it can only add power. 🛑 **The alternative is worse:**
trimming a run to land exactly on 480 means choosing *which* of its slots to drop, which is a
parameter the data does not supply (sibling (d)).

**Report the window's actual N every sweep**, never the nominal 480.

---

## 4. What QA should change

1. Thread the `_s5_window_gate` status into `_append_trend`; write the two S5 columns **empty** on
   `VOID`/`NOT_RUN`, populated on `SCORED`/`INFO`.
2. One test per branch: a VOID run's counts do **not** appear in the next window; an `INFO` run's
   **do**.
3. Report the window's **actual N**, not "480".
4. Re-run the §5 worked example — **it must be unchanged** (`15/480`, UB 4.771%, PASS; A-Δ p=0.7682;
   LOO not FRAGILE). If it moved, the change was wrong.

🔴 **Hard stop after task 4** (HK-030). No sweep. No push (HK-033).

---

## 5. On QA's other three findings — all accepted, one of them beyond the task

✅ **The §16 mislabel was in three more places than I knew**, and QA found them: the §10 master
threshold table's note, the **generated report footnote**, and the source comment above
`S5_AWGN_PARTS`. 🔴 **The report-footnote instance is the one that matters** — it was reproducing
*"detects it 77% of the time"* into **every future report**, so the wrong framing would have kept
propagating long after the spec was fixed. Correcting it was outside the six tasks and was the right
call.

✅ **HK-025 concurrence on ROW 0a/0b (VALIDITY) and 0c (PRECISION) accepted.** ✅ **Sibling (n)
verification accepted**, including the check that Check B is not a usable S5-internal substitute —
it has the identical no-true-positive problem, which is the correct reason.

✅ **Updating the six `test_analyse_xplat.py` tests that pinned the old `_verdict_fp` PASS/FAIL was
in scope** — the contract changed by ratification; keeping the `_cp_upper_95` pins was right.

---

**Architect, 2026-09-08 15:09 UTC.** Committed locally, **not pushed** (HK-014).
`git diff --stat -- src/ native/` empty.
