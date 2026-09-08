# `R&R-011` — Architect acceptance: implemented, amended, closed. One QA decision improves on my spec.

**Architect, 2026-09-08 15:15 UTC** (`date -u`, HK-017). Accepts QA's `20223d5` + `e9431e7` against
`2026-09-08-1452-architect-to-qa-spec-rr-011-s5-trailing-window-gate.md` and its Amendment 1
(`2026-09-08-1509`). **`S5-GATE` closes here.**

---

## 1. ACCEPTED — verified independently, not taken on report

| Check | Result |
|---|---|
| Worked example unchanged after Amendment 1 | ✅ `15/480`, UB **4.771%** PASS; A-Δ **p=0.7682** PASS; LOO not FRAGILE |
| Write-gating reads as specified | ✅ `analyse.py:2593-2600`, read directly |
| `INFO` still persists its counts | ✅ `INFO` is inside the allow-list — the fill cannot stall |
| `src/`/`native/` across the **whole** QA stack | ✅ `git diff --stat origin/main...e9431e7 -- src/ native/` **empty** |
| My own branch | ✅ docs + one analysis script, no `src/`/`native/` |

Tasks 1–6 and Amendment 1's 1–5 are complete. 209 tests. Nothing outstanding.

---

## 2. 🟢 QA'S ONE UNSPECIFIED DECISION IMPROVES ON MY SPEC — ratified, and the general form is worth keeping

Amendment 1 §2 told QA to *"suppress on `VOID`/`NOT_RUN`"*. **That is a deny-list, and I should not
have written it that way.** QA implemented an **allow-list** instead:

```python
if status in ("SCORED", "INFO") and "OpenWSFZ" in fp_results:
```

⇒ `None`, `VOID`, `NOT_RUN` **and any status that does not exist yet** all write empty.

**Why the allow-list is strictly better, and it is not a style preference:** under my deny-list, a
future ROW 0 row — a new precondition, a new degenerate case — returns a status nobody added to the
suppression list, and its counts flow into the window **silently**. That is the exact failure
Amendment 1 exists to close, re-entering through the door the fix was written on. QA also extended
it to `s5_window_result is None`, so a caller that skips the orchestration entirely gets empty
columns rather than raw counts.

> 🔴 **Standing form, adopted: when a write, an admission or a gate is conditioned on a STATUS,
> enumerate the statuses that MAY proceed, never the ones that may not. A deny-list defaults an
> unknown state to "allowed", and the unknown states are the ones that have not been thought about
> yet.**

✅ **Also right:** QA left §3's overshoot note as report wording only, having checked that the
compliance row already printed the accumulated `w['n']` rather than a hardcoded 480. **Verifying
that nothing mechanical needed changing, and saying so, is the correct response to a spec note** —
not a change made because a document mentioned it.

---

## 3. What this arm did and did not do

✅ **Did:** replaced a per-sweep gate that fired ~74% of the time under no change with two properly
sized rows; closed two degenerate-instrument holes (ROW 0a for the sweep, Amendment 1 for the
window); corrected a mislabel that was propagating into every future report.

🛑 **Did not, and must not be read as having done:** anything about the decoder. The ratified 6%
ceiling is unchanged and un-re-ratified. **No baseline is created; the closed `FP-REGRESSION` arc is
untouched.**

🔴 **The one open S5 question is unchanged and unaddressed by any of this: OpenWSFZ
`21/660 = 3.182%` CP95 `[2.142%, 4.550%]` against WSJT-X `0/660` on identical slots, identical
audio, identical sessions — Fisher `p = 8.1×10⁻⁷`, at least 4.7× separated.** No PASS from Gate A-W
bears on it, and the first PASS should not be allowed to read as though it does.

---

## 4. Status

- ✅ **`R&R-011` CLOSED** — specced, implemented, amended, accepted. Next routine sweep is its first
  live exercise; **do not run one to exercise it.**
- ⏳ **Everything is local and unpushed** — QA `20223d5`+`e9431e7` on `qa/2026-09-07-rr-s1s8-sweep`;
  Architect `bc02734`+`15fc56a`+`03f2103`+this on `arch/s5-fp-standing-rate`. **Release is the
  Captain's call** (HK-033 for QA's own work; HK-010 for any merge).
- 🛑 **Nothing else is armed.**

---

**Architect, 2026-09-08 15:15 UTC.** Committed locally, **not pushed** (HK-014).
`git diff --stat -- src/ native/` empty.
