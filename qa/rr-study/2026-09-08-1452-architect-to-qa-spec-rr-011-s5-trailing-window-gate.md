# QA SPEC — `R&R-011`: S5 Gate A moves to a trailing 480-slot window, plus a per-sweep change test

**Architect, 2026-09-08 14:52 UTC** (`date -u`, HK-017). Implements the PO's ruling of 2026-09-08 on
§6 of `qa/rr-study/2026-09-08-1429-architect-to-qa-ruling-s5-gate-a-first-point-and-gate-form.md`
(**Option A**). Supersedes R&R-010's per-sweep scoring of Gate A; **Check B is untouched** (§7).

**Pre-registration. Commit this file before the next sweep runs** (HK-021's founding instruction).
No `src/`/`native/` change: this is `harness/analyse.py` and report scaffolding only, exactly as
R&R-010 was. `git diff --stat -- src/ native/` empty at authoring.

🛑 **DISCLOSURE, up front, because the reader is entitled to discount it.** I computed this design's
verdict on the existing data **before** proposing it. It **PASSes** (§5). The design was chosen on
the criterion in §4 — which is a property of Clopper–Pearson, not of that verdict — and §4.3 shows
the alternative anchors so the choice is auditable rather than fitted.

---

## 1. What changes

| | R&R-010 (current) | **R&R-011 (this spec)** |
|---|---|---|
| Per-sweep Gate A, N=120 | PASS/FAIL, gates the sweep | **`INFO`** — reported, never gates |
| Compliance gate | — | **Gate A-W**: trailing **480 AWGN slots**, ratified 6% UB **unchanged** |
| Change detection | — | **Gate A-Δ**: newest sweep vs the rest of the window, one-sided |
| Check B (narrowband) | FAIL iff ≥2 of 60 | **unchanged, untouched** |

**The window's unit is the SLOT, not the sweep.** Sweeps contribute unequal slot counts (60 before
R&R-010, 120 after); a "last 4 sweeps" rule would make the denominator depend on which era the
window straddles. Defining it in slots also means **the window is full today** — no blind period
while it fills.

---

## 2. Population — stated once, and it is the same one throughout

**Signal-free S5 AWGN slots, parts 0 and 1.** Unchanged from R&R-004's ratification, R&R-009 and
R&R-010. Parts 2/3 (narrowband) are **never** admitted to this window (§7).

Counts come from each run's own Section 10 gate line. 🛑 **Never back-computed from Section 6's
`S5 FP` column** — it mixes plain rates with 95% upper bounds.

🔴 **The window's seed, fixed at ratification and not to be re-derived:** the seven most recent runs
contributing AWGN slots, newest first — `4cc1984` 3/120, `4c7d5ad` 3/60, `35378b9` 2/60, `3b52608`
4/60, `2e60949` 2/60, `872ba65` 1/60, `22b749c` 0/60 = **15/480**. All seven reproduce against their
committed reports via `fp_composition_per_part.py` (ROW C1, 18/18).

---

## 3. The gates, as code (sibling (r) — the prose below is a gloss on this, not the reverse)

```python
CEILING = 0.06          # R&R-004, unchanged, NOT re-ratified
WINDOW_SLOTS = 480      # R&R-011, fixed at ratification -- see the prohibition in section 4.4
ALPHA_CHANGE = 0.05

def gate_a_w(window):                      # window: [(sha, events, slots)], NEWEST FIRST
    """Compliance. PASS iff the ratified 6% ceiling is demonstrated on the trailing window."""
    used, k, n = [], 0, 0
    for sha, ev, sl in window:             # accumulate newest-first until the window is filled
        if n >= WINDOW_SLOTS:
            break
        used.append((sha, ev, sl)); k += ev; n += sl
    if n < WINDOW_SLOTS:
        return "INFO", k, n, used          # window not yet full -> NO verdict, not a PASS
    ub = clopper_pearson_upper(k, n, alpha=0.05)
    return ("PASS" if ub <= CEILING else "FAIL"), k, n, used

def gate_a_delta(newest, window):          # newest: (sha, events, slots)
    """Change. FAIL iff this sweep is significantly WORSE than the rest of the window."""
    _, k1, n1 = newest
    k0 = sum(ev for _, ev, _ in window[1:]); n0 = sum(sl for _, _, sl in window[1:])
    p = fisher_exact([[k1, n1 - k1], [k0, n0 - k0]], alternative="greater")[1]
    return ("FAIL" if p <= ALPHA_CHANGE else "PASS"), p, (k1, n1), (k0, n0)
```

**Rows, mutually exclusive, evaluated in strict order.** ROW 0 first; if any ROW 0 fires, **no gate
row is evaluated and no S5 verdict of any kind is reported.**

| # | Row | Fires when | Consequence — stated as an assertion |
|---|---|---|---|
| **0a** | Positive control | S4 OpenWSFZ recall **== 0** in the same session | ⇒ **VOID.** Do not evaluate Gate A-W or A-Δ; do not report PASS. The S5 reading is not an estimate of anything. |
| **0b** | Scoping | any counted event's `cycle_utc` is **not** in parts 0/1's own truth rows | ⇒ **VOID.** Report the unscoped and scoped counts and stop. |
| **0c** | Window fill | accumulated slots **< 480** | ⇒ **`INFO`.** Report `k/n` and stop. **`INFO` is not a PASS.** |
| **1** | Compliance | Gate A-W returns `FAIL` | ⇒ the sweep FAILs on S5. |
| **2** | Change | Gate A-Δ returns `FAIL` | ⇒ the sweep FAILs on S5, **reported separately from ROW 1** — never pooled into one S5 line. |
| **3** | Clean | both return `PASS` | ⇒ S5 PASS. |

⚠️ **ROW 1 and ROW 2 can both fire.** That is intended and they are reported as two lines; the
sweep's overall S5 verdict is FAIL if either fires. They are not mutually exclusive *outcomes*, they
are two different questions — which is the whole point of the split. The **ROW 0 rows** are the ones
that must pre-empt, and they do.

🔴 **ROW 0a exists because of sibling (n), and it is not optional.** S5 slots are signal-free, so S5
has **no true positives of its own**: if the audio chain dies, OpenWSFZ hears nothing, the FP count
goes to **0**, and Gate A-W returns **UB 0.622% ⇒ PASS**. *A dead instrument passes the compliance
gate.* The positive control must therefore come from **outside** S5. `recall == 0` on injected S4
messages is unambiguous and needs no invented threshold; **partial** degradation is covered by S4's
and S8's own ratified gates, which is why this row is a floor at zero and not a band.

---

## 4. Why 480, and why this is not a loosening

### 4.1 The false-pass rate at the ceiling is unchanged at every N — that is Clopper–Pearson, not my choice

| true rate | P(Gate A-W PASSes) at N=480 |
|---|---|
| **6.00% — at the ceiling** | **0.050** |
| 6.36% — doubled from observed | 0.025 |
| 5.00% | 0.236 |
| 3.18% — the observed rate | **0.909** |

`P(UB₉₅ ≤ C | p = C) ≤ 0.05` holds **at every N by construction**. Widening the window does not make
a non-compliant decoder more likely to pass. **What N buys is the power to DEMONSTRATE compliance
when it actually holds** — and at N=120 a genuinely compliant 3.18% demonstrates it only **26%** of
the time, which is the defect being fixed.

### 4.2 The comparison that settles it

| | N=120 (R&R-010) | **N=480 (R&R-011)** |
|---|---|---|
| Compliant 3.18% ⇒ PASS | 0.262 | **0.909** |
| Doubled 6.36% ⇒ PASS | 0.016 | 0.025 |

N=120 fails **both** — it is indiscriminate, not strict. N=480 separates them.

### 4.3 The sizing anchors, shown so the choice is auditable (sibling (d))

Smallest window with `P(PASS) ≥ 0.90`: at the observed **3.182% ⇒ N = 480**; at **3.0%** (half the
ceiling, a value not taken from our data) **⇒ N = 480**; at 4.0% ⇒ N = 1,140. ⚠️ **480 is powered
against a pilot estimate drawn from the same instrument.** That is standard sample-size
determination and it is disclosed, not hidden — and the second anchor reaches 480 without using our
measured value at all.

### 4.4 🛑 Prohibitions, binding at ratification

- **`WINDOW_SLOTS = 480` is fixed. It may not be changed in response to a verdict, ever.** Re-tuning
  a window after a FAIL is the prohibited re-read (sibling (f)'s trap, sibling (y)).
- **`CEILING = 0.06` is not re-ratified and is not touched.** The PO argued against moving it and so
  do I.
- A future change to either earns a **new pre-registration**, never an amendment applied backwards.

### 4.5 Resolution, and the readout quantum (siblings (m), (o))

The gated statistic is an **integer count of slot-events**; the bar is an integer. At N=480,
`k=20 ⇒ UB 5.997% PASS` and `k=21 ⇒ UB 6.239% FAIL`. One event is **0.208%** of the window. 🛑 **No
bootstrap SE appears anywhere in this gate** — (o)'s failure mode is structurally absent.

### 4.6 Clustering, measured rather than asserted (sibling (i))

Between-sweep overdispersion was **computed, not estimated in prose**: χ² = 8.878, df = 9,
**p = 0.449** across the ten readings — no excess dispersion, so the binomial denominator is the
right one and no design effect is applied. ⚠️ **If a future window shows χ² p < 0.05, the binomial
interval understates the uncertainty and this gate must be re-drafted, not re-read.** Report the
statistic every sweep so that condition is visible.

### 4.7 The cross-build confound, with the maximum stated (sibling (p))

The window spans up to seven builds. The bound is mechanical and reported **every sweep**:
**leave-one-sweep-out on the window verdict.** If any single sweep's removal flips the verdict, the
verdict is reported as **`FRAGILE`** alongside its value and does not stand alone as evidence about
any build. On today's window all seven deletions PASS — the current verdict is not fragile.

⚠️ **Honest costs, stated in the gate's own definition rather than carried as prose:** the window
**lags** — a regression introduced in one sweep is diluted 1:4 and takes up to four sweeps to reach
full weight. Gate A-Δ is what covers that gap, and **it is blind below ~2×** (power 0.40 at 2×, 0.82
at 3×, false-alarm 0.03). **Neither gate detects a change smaller than 2× in a single sweep. Say so
in every report; do not let a PASS read as "nothing moved".**

### 4.8 My prediction, on the record (sibling (v))

**I expect the next sweep to PASS both rows** — Gate A-W at ~0.91, Gate A-Δ firing at ~0.03. Power
at my own stated expectation is therefore high for A-W and *irrelevant* for A-Δ, which is a null
expectation by design. ⚠️ Per HK-021's calibration section, my running tally is **ranges 2 of 3, row
calls 1 of 3** — discount the row call accordingly.

---

## 5. Worked example — the implementation must reproduce this exactly

Run against the §2 seed window, as of 2026-09-07:

```
Gate A-W : 15/480 = 3.125%   95% UB 4.771%   PASS iff k<=20   -> PASS
           CP95 [1.936%, 4.771%]
Gate A-Δ : 3/120 vs 12/360   Fisher(greater) p = 0.7682       -> PASS
LOO      : all 7 deletions PASS -> not FRAGILE
ROW 0a   : S4 recall > 0 -> does not fire
ROW 0c   : 480 slots accumulated -> does not fire
```

**If your implementation returns anything else, the implementation is wrong — escalate, do not
adjust the spec.**

---

## 6. HK-025 / sibling (k) pre-clearance — both branches evaluated, as QA is entitled to demand

| Row | Class | Both branches | Verdict |
|---|---|---|---|
| **0a** positive control | **VALIDITY** — if recall is 0 the FP count estimates nothing | n/a | ✅ legitimate |
| **0b** scoping | **VALIDITY** — a contaminated numerator is not this metric | n/a | ✅ legitimate |
| **0c** window fill | **PRECISION** | full ⇒ PASS/FAIL possible; short ⇒ `INFO`. **Rows differ** | ✅ legitimate |

🔴 **QA retains its HK-025 right to refuse this spec** without my agreement. I have run the check and
believe it clears; **if you disagree on any row, refuse it — the check is yours, not mine.**

**HK-022 applied to each row — "what error could this NOT detect?"**: ROW 0a cannot detect *partial*
chain degradation (covered by S4/S8's own gates, stated in §3). ROW 0c cannot detect a window that is
full but composed of stale builds (covered by the §4.7 LOO). **Gate A-W cannot detect a change
confined to the newest sweep** — that is exactly what Gate A-Δ is for, and **Gate A-Δ cannot detect a
change below ~2×**. That last blind spot is real, is not closed by this design, and must be stated in
every report.

---

## 7. Explicitly out of scope

- 🛑 **Check B is not touched.** Its `FAIL iff ≥2 of 60` threshold and its ROW 0 exposure
  precondition were adjudicated on 2026-09-06 and stand.
- 🛑 **The 6% ceiling is not re-ratified.**
- 🛑 **Nothing here revisits the closed `FP-REGRESSION` arc, and no baseline is created.**
- 🛑 **The OpenWSFZ-vs-WSJT-X gap is not addressed by this spec and is not made less open by it.**
  `21/660 = 3.182%` against `0/660`, p = 8.1×10⁻⁷ — that remains the standing open question and no
  PASS from Gate A-W may be read as bearing on it.

---

## 8. QA's tasks

1. **Implement §3 in `harness/analyse.py`** — `_verdict_s5_window` and `_verdict_s5_change`
   alongside the existing `_verdict_s5_narrowband`. Per-sweep Gate A becomes `INFO`. **Three separate
   verdict lines; no code path may combine them into one S5 row** (R&R-010's prohibition, carried
   forward and extended).
2. **Persist the window** — `trend.csv` already tracks the AWGN quantity; seed it from §2 and let the
   window be derived from it rather than hand-maintained.
3. **Reproduce §5 exactly** before the next sweep, as an implementation test.
4. **Section 6 stays in its standing format** (HK-034): the `S5 FP` column continues to carry the
   per-sweep Gate A figure, now labelled `INFO`, with the window verdict added as a **footnote in the
   established style** — same table, same columns. **Do not redesign the section.** The window verdict
   gets its own line in the Section 4 gate table.
5. **Correct `STUDY-SPEC.md` §16's mislabel** — *"Gate A alone detects it 77% of the time"* computes
   P(FAIL) at 3.33%, which is the **null**; 0.77 is the **false-alarm rate under no change**, not
   power. This ruling is the authority for the edit.
6. **Record R&R-011 in `STUDY-SPEC.md` §16** in the same form as R&R-009/R&R-010, marking R&R-010's
   per-sweep scoring **SUPERSEDED** and keeping its entry unedited as the historical record.

🔴 **Hard stop after task 6: commit and hand back** (HK-030 — an unblocked later step still sits
behind this stop). Do not run a sweep to exercise the new gate; the next routine sweep does that.
🔴 **HK-033: this is my spec, not QA's own new work, but nothing here authorises a push or a PR** —
the Captain's go-ahead is separate.

---

**Architect, 2026-09-08 14:52 UTC.** Committed locally, **not pushed** (HK-014).
`git diff --stat -- src/ native/` empty.
