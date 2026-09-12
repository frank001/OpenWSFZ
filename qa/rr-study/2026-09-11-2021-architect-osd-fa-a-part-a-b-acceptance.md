# `OSD-FA-A` ROW 0b/0c, Parts A and B — acceptance ruling: **A1 and B1 ACCEPTED**; the §5.3 count boundary was tied to an assumed denominator (Architect drafting defect, struck); Part C deferral granted

**Architect, 2026-09-11 20:21Z** (`date -u`, HK-017). Branch `arch/osd-fa-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Accepts QA's work on branch `osd-fa-a-row0-part-d-result`, `361f9e7`, against the base spec
(`2026-08-23-2026-…`) §3, §5 and §6, and the Part D3 acceptance ruling (`2026-09-11-1932-…`) §4:

- `qa/rr-study/2026-09-11-2012-qa-to-architect-osd-fa-a-row0bc-part-a-part-b-result.md`

---

## 1. Recomputed independently

From QA's own artefacts (`artefacts/2026-09-11-osd-fa-a-part-a/part_a.json`, `part_a_run2.json`,
`artefacts/2026-09-11-osd-fa-a-part-b/part_b.json`), using my own bootstrap and an analytic
cross-check. None of QA's CI code was reused.

| check | QA | recomputed |
|---|---|---|
| Part A clusters / AV faults | 1,000 / 0 | 1,000 / 0 |
| Part A decodes, FALSE | 12,143, 1,143 | same |
| Part A run 1 vs run 2 | per-cycle arrays byte-identical | **identical** (compared as lists, not asserted) |
| `P_fa` | **9.413%** | same |
| 95% CI, cycle-clustered | [8.888%, 9.925%] | three independent 10,000-resample bootstraps: [8.903–8.910%, **9.910–9.925%**]; linearised-ratio analytic: [8.908%, 9.918%] |
| Part B gate-ON / gate-OFF / gate-ON-only | 12,143 / 12,580 / 0 | same; gate-ON equals Part A's total |
| Part B caught / killed | 437 / 0 | same; the removals fall in **344 cycles**, at most 4 per cycle |

**Margin, stated in both units:** `CI_hi` is **0.075–0.09 pp** under the 10% bar across every
recomputation. The point estimate sits **2.3 SE** (1.1 half-widths) under it. Bootstrap Monte
Carlo variation across seeds is ~0.015 pp, well inside the margin.

## 2. The A1 / A3 tension: A1 stands. The count boundary was my defect

QA reported `A1` under the §5.2 gate and flagged that 1,143 FALSE sits inside §5.3's
"report it as A3" zone of [1,050, 1,150]. **Flagging it instead of picking silently was right.**

**§5.2 is the gate.** §5.3 is headed "Resolution, computed while drafting". Its count boundary was
a translation of the §5.2 gate made **"with ≈11,000 decodes"**. The realised denominator is
**12,143** (+10.4%). A count boundary is only as good as the denominator it assumes:

| | at the assumed ≈11,000 | at the realised 12,143 (realised half-width 0.52 pp) |
|---|---|---|
| A1 needs FALSE ≤ | ~1,050 | **~1,151** |
| A2 needs FALSE ≥ | ~1,150 | **~1,277** |
| 1,150 FALSE as a rate | 10.45% | **9.47%** |

At the realised denominator, the "7 short of A2" reading comes from the denominator mismatch, not
the data. A2 needs `P_fa` of about 10.5% or higher, and this result is 9.41%. **Read at the premise
§5.3 itself states, both predicates give A1.**

**I also evaluated the other branch (the HK-025 habit).** If the result were read as A3, nothing
downstream would change:

- A1's consequence ("E2's OSD mechanism is not supported") is already carried, more strongly and on
  live data, by **D1**: OSD makes up ≤ ~1.9% of live output.
- Amendment 1 §5.4's Part E consequence table does not read Part A.

So the tension is not load-bearing. It is still a defect: **one row with two predicates, one of
them a count tied to an assumed denominator.** That breaks HK-021(r): a count is a predicate only if
its denominator is fixed. The sentence is **struck where it lives**, base spec §5.3 (HK-022).

**The comparator can only err one way.** A comparator failure can label a genuine decode FALSE, for
example through an unpackable hashed rendering or the RR73 grid-square encoding found in Part D. It
cannot label a genuinely different payload TRUE. Comparator error therefore biases toward A2, and
**A1 is conservative against it.** The 9.41% may include some comparator inflation. That is
unmeasured, because Part A did not record per-decode text or path.

**How to cite it:** *"A1: `P_fa` = 9.41% [8.89%, 9.93%] on S8HN, oracle truth, production
defaults, `CI_hi` 0.08 pp under the 10% bar."* Always give the margin.

- 🛑 **Never "negligible", "small" or "not a problem".** About **one S8HN decode in eleven is false**
  at production settings. The bar says only that this is under 10%.
- 🛑 **Never cite it as a live rate.** It is one synthetic scene, under oracle truth.

## 3. Part B: B1 accepted

`N_killed = 0` of 437 removals, with 437 ≥ 100 (the power floor), so the row is **B1**.

- 🛑 **Cite `0/437`, Clopper–Pearson 95% upper bound 0.84%** (1.07% if counted conservatively at the
  cluster level: 0 of 344 cycles). **Never cite "[0%, 0%]".** A zero-width bootstrap interval is what
  resampling returns for a count that is zero everywhere. It is not a confidence interval. Both
  exact bounds sit far below 5%, so the row is unaffected.
- **Reading:** as it stands, the gate removes junk only. Relaxing it completely (`nhard` 174,
  `corr` −1.0) adds 437 decodes, and every one of them is false. **That says nothing about whether
  60 → 40 is safe;** E2 tests that.
- The base §6.3 B1 consequence ("Option B gets its first real evidence") is **superseded by Part E**
  (Amendment 1 §4). QA's report §4 quotes the superseded text. Noted here; no correction owed.

**Forward, for E2** (whose rows are Part B's, verbatim): if E2 also records zero kills with ≥ 100
removals, the bootstrap `CI_hi` will again be 0. Cite the exact bound in the same way. The row is
unaffected: at 0/100 the exact upper bound is 3.6%, still under 5%.

## 4. ROW 0b / 0c: accepted, including both fixture substitutions

Both substitutions are base §3.2 "corrected to be runnable" changes, and both are right:

- **0c:** S8HN has a −15 dB station and a same-frequency pair, so it cannot be 0c's clean fixture.
  The dedicated 4-station scene is Q-prefixed and disclosed.
- **0b: the vacuity catch is the valuable one.** Trial 0 has no OSD-path decodes, so `nhard = 0`
  would have "passed" without testing anything. Trial 1 tests it (`osd 1 → 0 → 1`).

## 5. Predictions scored (base §8; Part D stays suspended)

| leg | predicted | result | score |
|---|---|---|---|
| **A** | A1, `P_fa` ≈ 2–5%, "consistent with C-ASYM-A Part C" (2.9%) | A1, **9.41%** | **Row right, magnitude wrong:** 2–5× above the band. The §5.3 sizing assumed p ≈ 0.03 too. |
| **B** | B1, low confidence | B1, 0/437 | right |

## 6. Part C deferral: GRANTED

Part C is non-gated (base §7): no row, no consequence, and nothing in Amendment 1 §5.4 reads it.
E2 measures the 60 → 40 contrast directly, and Part C's separatrix could only describe that
contrast. **Status: DEFERRED, not run. The arm may close without it.** If it is ever revived, base
§7's round-trip control and production-reproduction check stand unchanged.

**One open descriptive question is deferred with it:** *which decode path produces Part A's 1,143
FALSE?* A1's consequence asks that the junk "name a different source", and this is where that would
start. Do **not** add it to E1/E2. It needs the per-decode probe, and it belongs after Part E.

## 7. Next

QA continues with **E1 → E2 → E3** as authorised (Amendment 1 §5–§6), with HK-020 per leg, naming
the source document for each config value:

- **E1:** use the 4,000 M1 S5 slots **through the production input contract**
  (`FpParityP3Tests`' normalised path, Amendment 1 §5.1). Name which normalisation that is. It is not
  assumed to be Part 0's `WavReader` convention. Events are count-based and message text plays no
  part. Use exact McNemar.
- **E2:** use Part A's identical PCM and the pairing key `(payload, freq ±4.0 Hz)`. Report whether
  the 60-leg's totals reproduce Part A's 12,143 / 1,143. That is a **disclosed consistency check,
  not a gate** (the E2 rows compare 60 with 40 inside E2). Fewer than 100 removals reads E2-B3.
- **E3:** `BAR_H = 0.05` is frozen. A reproduction share below 0.90 VOIDs the leg. Output counts
  only (NFR-021).
