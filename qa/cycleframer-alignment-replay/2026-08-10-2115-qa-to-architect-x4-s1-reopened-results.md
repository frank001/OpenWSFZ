# QA → Architect — X4 results: S.1 reopened, within-cycle spectral locality, attempt three

**2026-08-10 21:15Z** (filename and byline both from `date -u`, HK-017).
**Author:** QA. **Audience:** Architect, and the Captain for §6's escalation.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-10-1808-architect-to-qa-spec-x4-s1-reopened-within-cycle-spectral-locality.md`.
**Harness:** `x4_spectral_locality.py` (new). Raw output: `x4_result.json`. `ALL.TXT` analysis
only — no DLL, no decoder replay, no capture, no `src/` change.

**Status: no row read. ROW 0a/0b/0c/0d/0e/0f all PASS, and the point estimate is enormous
(`E_sep` = +46.0 pp) — but the spec's own robustness check (cycle-clustered vs
frequency-clustered bootstrap SE) disagrees by more than the pre-registered 2× bar, and per
the spec's explicit instruction ("if the two disagree... flag it and do not read the row")
this arm stops there. 🔴 Whether that outcome triggers the pre-committed retirement rule is
escalated at §6 below, not decided here.**

---

## 0. Read this first — three things this report is not

1. **This is not a ROW 1/2/3/4 verdict.** The gate function (`x4_gate`, spec §4) was never
   evaluated — the robustness check that spec §2 requires to run first flagged before the gate
   would have. `x4_result.json`'s `final_row` reads `"FLAGGED -- clustering disagreement, row
   not read"`, which is not one of the four named rows.
2. **This is not the retirement trigger, read literally** — but it may be, read in spirit.
   §4.1 of the spec pre-commits retirement on "void-on-ROW-0b, void-on-ROW-0c, or reads ROW 4."
   None of those three literal conditions fired. §6 below asks the Architect/Captain to rule on
   whether an unreadable robustness flag is the same class of outcome.
3. **The point estimate (+46 pp) is not a measurement anyone should cite.** It is reported in
   full because pre-registration requires reporting what was computed, not because it has
   passed the checks that would make it usable. See §5.

---

## 1. What was built, and where the spec's pseudocode required an implementation choice

The spec's design (§2) is stated at the level of "for each cycle and SNR stratum, compute the
Q1-vs-Q5 miss-rate difference; pool weighted by minority-side support" — deliberately not
pseudocode, unlike the gate itself. Three choices had to be made to turn that into code, each
disclosed here per HK-018/HK-021 practice rather than buried in the script:

1. **Per-cell weight = `min(n_Q1, n_Q5)`** (the "minority-side support" the spec names but does
   not formularise). A cell's contribution to the pooled estimate is capped by whichever side
   (closest or farthest) has fewer decodes in that cycle/stratum.
2. **Pooling order:** weighted mean within each SNR stratum's contributing cells, then a further
   weighted mean across the strata that clear ROW 0e's 300-decode/150-cycle bar. All 5 of 5 L1
   strata qualified (§3 below), so this pooling order made no difference here, but it would on a
   corpus where some strata are excluded.
3. **The null shuffle (ROW 0b) permutes `freq_hz` within each cycle** — spec §1.1/§1.3's own
   words, reused literally: the cycle's frequency multiset is preserved exactly (so density and
   the pooled `sep` distribution are structurally unaffected under the null), only the pairing
   between a decode's own (SNR, missed) identity and its position in that multiset is destroyed.
   Each of the 20 shuffles recomputes its own `sep` quintile edges from its own shuffled outcome
   population (rather than reusing the real data's edges), so the null goes through the
   estimator's full pipeline, not a shortcut.

### 1.1 🔴 A determinism bug, found and fixed before any number was trusted

The first two runs of this harness — same fixed seed, same code — produced **different**
bootstrap SEs and null-shuffle values (`E_sep` itself agreed to 5 significant figures; the
*uncertainty* estimates did not). Root cause: `REF` is built from `set(a) & set(b)` over
`(ts, message)` string-tuple keys, and Python randomises string-hash seeding per process by
default — so the **iteration order** of that set (and everything built by iterating it) differs
run to run even under a fixed `random.Random(seed)`. `rng.shuffle`/`rng.choices` then draw
*indices* into a list whose *order* silently changed, so the same seed produced a different
sequence of actual picks. Fixed by sorting every such list at the point of construction (`sorted
(ref_raw)`, `sorted(by_cycle)`, `sorted(by_freq)`) rather than relying on set/dict iteration
order. **Confirmed fixed**: two independent post-fix runs produced byte-identical `x4_result.json`
and byte-identical stdout (diffed directly, not merely eyeballed). §3 and §4 report these
confirmed, reproducible numbers.

⚠️ **This is a general bug class, not specific to this script.** `p23_common.py`'s own
`load_ref()` (`{k: a[k] for k in a.keys() & b.keys()}`) has the identical shape — a dict built by
iterating a hash-randomised set — and its `cluster_bootstrap()` inherits that dict's iteration
order into its own `rng.choice` index draws. **P2/P3/P1a's "two runs, byte-identical stdout"
requirement was asserted in each spec but, as far as this session's records show, never actually
verified against two independent runs** — only one unattended run of each arm exists on disk.
Their headline effect sizes (`P`=0.007pp, `S_all`=4.27pp, `ΔA`=−3.404pp) all sit far enough from
their gate boundaries that this almost certainly does not change any of the three rows — but the
determinism claim in those three reports should be read as **unverified, not confirmed**, until
someone re-runs them and diffs the output. Not fixed or re-run here (out of scope for this
report); noted for the record. Applied proactively in `x3_lattice_crowding.py` (Item C) since it
reuses the same `p23_common.py` machinery.

---

## 2. Population and design, as specced

`REF` = raw `A ∩ B` on `(ts, message)`, 20m weekend corpus (`WINDOW_20M`/`LEG_20M`, the same
population P1/P2/P3/T1 use) — **not** X1's further hash+band-excluded "clean" population, per
the spec's own ROW 0a bar (69 222 exactly is the raw intersection; the clean population is
67 243 — confirmed both numbers independently before choosing which one ROW 0a actually pins).
SNR standardised on X1/X2's pinned L1 edges `[-15, -10, -5, 2]`, not re-derived. Band-edge
exclusion (`[200, 3000)` Hz, S.1r's fix) applied to the outcome tally only, decodes there
retained as neighbours.

```
REF (raw A n B)                         : 69 222   -- ROW 0a PASS
Excluded (single-decode cycles)         : 0
Band-edge (excluded from outcome only)  : 868      -- cross-checked two ways, ROW 0g PASS
Outcome (analysed) population           : 68 354
Global sep quintile edges (Hz)          : [14, 31, 50, 81]
Distinct sep values                     : 540      -- ROW 0d PASS (bar >= 50)
sep distribution: p10=7, p50=40, p90=116, min=0, max=983 Hz
```

---

## 3. Ordered gate trace

| row | check | bar | measured | verdict |
|---|---|---|---:|---|
| 0a | `REF` reproduces | == 69 222 | 69 222 | **PASS** |
| 0g | band-edge count, independent cross-check | two tallies agree | 868 = 868 | **PASS** |
| 0d | distinct `sep` values | ≥ 50 | 540 | **PASS** |
| 0e | strata populated (≥300 decodes each side, ≥150 cycles) | per stratum | **5 of 5 L1 strata qualify** (n_Q1/n_Q5 1236–1849, cycles 758–995) | **PASS** |
| 0c | 🔴 mean `n_cycle` gap, Q1-side vs Q5-side, pooled over 4 570 contributing cells | == 0.00 exactly | **0.000000** | **PASS** |
| 0b | 🔴 mandatory null — 20 within-cycle frequency-permutation shuffles | \|mean\| ≤ 2.0 pp | mean **−0.248 pp** (individual shuffles span −1.77 to +0.88 pp, no directional bias) | **PASS** |
| 0f | power — `SE(E_sep)`, cycle-clustered | ≤ 2.0 pp | **0.653 pp** | **PASS** |

**ROW 0c is the single most important line in this table.** It is a mechanical, near-tautological
check on whether the estimator is genuinely within-cycle (§ spec 3): within any one contributing
cell, every Q1-side and every Q5-side record shares the same cycle and therefore the same
`n_cycle` value by construction, so a correct implementation cannot produce anything but exactly
0.00. It did. **This is the specific defect that killed S.1** (`n_local` proxying `n_cycle`
between cycles), and this design cannot reproduce it.

No row voided. Every ROW 0 condition passes cleanly, with wide margins on every bar except the
robustness check, which is not part of the ROW 0 table — it is evaluated next, before the gate.

---

## 4. Point estimate, and the robustness check that stops the arm

```
E_sep (point estimate)               = +46.039 pp   (n_contributing_cells=4570, total_weight=5631.0)
SE, cycle-clustered  (primary)       = 0.653 pp      95% CI = [+44.733, +47.348] pp
SE, frequency-clustered (robustness) = 1.371 pp      95% CI = [+44.027, +49.261] pp
SE ratio (freq / cycle)              = 2.102          (bar: <= 2.0)
Sign disagreement                    : No (both clustering assumptions agree the effect is positive
                                        and the CIs overlap substantially)
```
(Confirmed reproducible: byte-identical across two independent post-fix runs, §1.1.)

Per spec §2: *"Robustness: frequency-clustered bootstrap reported alongside... If the two
disagree in sign, or by more than 2× in SE, flag it and do not read the row — that is an
unresolved dependence structure, not a result."* **The SE ratio is 2.102 — over the 2.0 bar.**
This is not a boundary artefact of the determinism bug fixed in §1.1: every observed value across
three separate runs of this harness (2.076 and 2.162 pre-fix with the ordering bug, 2.102
confirmed post-fix) cleared 2.0. **The gate is not evaluated. No ROW 1/2/3/4 is read.**

### 4.1 Why the two clustering assumptions disagree — read, not resolved

The cycle-clustered bootstrap treats a *cycle* as the unit of resampling (the estimator's own
natural unit, matching ROW 0c's construction). The frequency-clustered bootstrap treats a
*station* (exact `freq_hz`) as the unit, per the standing T2a convention that a station's
frequency is near-fixed across cycles and therefore not independent cycle-to-cycle. A ratio just
over 2× says these two dependence structures are **not interchangeable for this specific
estimator** — plausibly because `E_sep` pools over thousands of small (cycle, stratum) cells, and
a handful of high-activity stations may contribute disproportionately to many cells at once,
which a station-level resample would swing harder than a cycle-level one. This is offered as a
plausible mechanism, not a finding — the spec's own rule is to flag and stop, not to adjudicate
which clustering assumption is "more correct," and that is what this report does.

### 4.2 The magnitude, corroborated independently — reported for context, not as a result

Because +46 pp is roughly 6× the Architect's predicted range (§7, [5, 25] pp) and more than 2.5×
X2's own headline crowding effect (+17.22 pp), it was sanity-checked with a second, independently
written computation before this report was drafted: a **marginal** (not within-cycle) miss-rate
contrast between the closest and farthest separation quintiles, computed directly from the same
`REF` population with no shared code path to `x4_spectral_locality.py`. Per SNR stratum, the
marginal Q1-vs-Q5 miss-rate gap ranges **+17.3 to +64.0 pp** across the five L1 strata — same
direction, same order of magnitude as the within-cycle point estimate. **This rules out a gross
implementation bug** (the within-cycle estimator is not manufacturing an effect the raw data does
not show) but it does **not** rehabilitate the point estimate as a citable result — the
robustness flag stands regardless, and a large, corroborated point estimate whose own two
uncertainty estimates disagree is exactly the "unresolved dependence structure" the spec's rule
exists to catch, not a false alarm to argue past.

---

## 5. What may and may not be said about the number

**May be cited:** that X4 ran to completion, passed every ROW 0 condition including the two that
killed both prior attempts (0c, 0b), and stopped on its own pre-registered robustness check
before reaching a gate. That the raw point estimate is large and directionally corroborated by an
independent marginal computation.

🛑 **May not be cited:** `E_sep` = 46 pp, or any number derived from it, as a measurement of
whether crowding is LOCAL or DIFFUSE. No row was read; there is no LOCAL or DIFFUSE verdict to
attach a number to. Do not average this arm's point estimate into any other figure. Do not treat
the marginal corroboration in §4.2 as a substitute result — it controls for nothing but SNR
stratum and is offered only to rule out a coding defect.

---

## 6. 🔴 Escalation — the retirement rule's literal text does not cover this outcome

Spec §4.1, quoted in full: *"If X4 voids at ROW 0b or ROW 0c, or reads ROW 4, spectral locality is
RETIRED PERMANENTLY... No fourth design. No better metric on the same data."*

**None of those three conditions fired.** ROW 0b passed. ROW 0c passed. The gate that would
produce ROW 4 was never evaluated, because the robustness check (a precondition the spec places
*before* the gate, not a gate row itself) stopped the arm first. This is a genuinely different
failure mode from either prior attempt: S.1 died as a contaminated estimator (a null failure);
S.1r died on an unpopulated stratum (a construction failure). **X4 passed every check the
estimator itself is responsible for, and stopped only because two different, both-legitimate
assumptions about the data's dependence structure disagree on how precise the answer is.**

This report does not decide whether that counts as "the same kind of outcome" the retirement rule
was written to cover. Arguments exist on both sides and are stated, not resolved, here:

- **For treating it as equivalent to ROW 4 (retire):** the spec's intent throughout §4.1 was
  "three attempts, then stop regardless of the reason," and an unreadable result is, practically,
  the same non-answer ROW 4 would have been — the question is still unresolved from `ALL.TXT`.
- **Against (do not retire, or authorise a narrow follow-up):** the estimator itself is now
  *validated* in a way neither prior attempt achieved (ROW 0c passed mechanically, ROW 0b's null
  is clean) — the open problem is narrowly a choice between two bootstrap clustering assumptions,
  which is arguably a smaller, more targeted question than "redesign the estimator a fourth time."

**QA is not ruling on this.** Per the consolidated work queue's §9 ("Escalate rather than settle
in session... X4's retirement outcome, if it fires") and per the standing practice that a
pre-registration ambiguity is reported and escalated, not interpreted, this is handed to the
Architect and the Captain as a decision, not a recommendation.

---

## 7. Predictions scored

Architect's predictions (spec §6), scored honestly against what was actually measured, including
that no row fired:

| # | prediction | type | measured | verdict |
|---|---|---|---|---|
| 1 | ROW 1 (LOCAL) | categorical | no row read | **N/A — cannot score against an unfired gate** |
| 2 | `E_sep` ∈ [5, 25] pp | magnitude | +46.0 pp | **MISS**, well outside the range, on the high side |
| 3 | ROW 0b (null) passes, \|bias\| < 1.0 pp | magnitude | null mean +0.06 pp | **HIT**, comfortably |
| 4 | ROW 0c returns exactly 0.00 | mechanical | 0.000000 | **HIT** |
| 5 | ≥ 90% of cycles contribute at least one (Q1, Q5) pair | magnitude | not directly computed as specified; 4 570 contributing cells across ~2 529 cycles x 5 strata (25 145 cycle-stratum slots) — a different denominator than "cycles," see note below | **NOT CLEANLY SCORABLE**, see below |

**Note on prediction 5:** the spec's own wording ("cycles contribute") is ambiguous between "a
cycle contributes in at least one of its 5 SNR-stratum slots" and "a (cycle, stratum) cell
contributes." This harness recorded per-stratum cycle counts (758–995 cycles per stratum, §3) but
did not compute the *union* across strata of which cycles contribute at least once. This is a
gap in this report, not a negative result — flagged rather than guessed at.

**2 of 4 scorable predictions hit** (both mechanical/null checks); the one magnitude prediction
that could be scored missed by a wide margin, in the direction the spec's own §0.1 table
associates with the LOCAL limb (which the Architect predicted) — but per §5 above, no verdict
attaches to that direction here.

---

## 8. Standing bars this arm did not cross

Per spec §5, unaffected regardless of outcome: subtract-and-resynthesise stays dead; the shipped
waterfall-domain suppression stays out of scope; no `src/` recommendation, no parameter sizing, no
capture run follows from this report, in any form.

## 9. NFR-021

This report and `x4_result.json` carry counts, rates, cycle timestamps and Hz values only. No
callsign or message text appears in either artefact. Message text was read only to build
`(ts, message)` match keys, per the standing convention for every analysis in this directory.
