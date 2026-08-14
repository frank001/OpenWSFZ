# QA → Architect: H1 results — how much do `<...>` hash tokens distort the 55.5% and the ~4% FP rate?

**Author:** QA, 2026-08-08 (21:35 UTC, `date -u`, per HK-017). Repo `main` at `0c28a07`.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-08-2121-architect-to-qa-spec-h1-hash-token-contamination.md`.
**Harness:** `qa/cycleframer-alignment-replay/h1_hash_token_contamination.py`.
**Status:** pure re-analysis of `ALL.TXT` already on disk (20m leg, `artefacts/20260808_live_run_0016-808{0,1}/`).
No `src/` change, no capture, no rebuild, no Developer session. `qa/artefact_inventory.py --check`
ran clean before starting. NFR-021: no message text or callsign appears anywhere below or in the
harness's output — counts and rates only.

**Bottom line: both gates cleared ROW 0. Gate A fires A-ROW 1 (material) at `M = 2.26 pp`. Gate B
reads B-ROW 2 (immaterial) at `ΔF = 0.02 pp`.** The two gates land on opposite verdicts, which the
spec calls out in advance as legitimate, not a contradiction (§4, "recovery and FP are different
denominators"). Practically: the hash table's saturation is real and materially depresses the
recovery figure, but it is **not** what drives the ~4% false-positive estimate.

---

## 1. ROW 0 — instrument checks (ordered trace, from the harness)

```
0a: |R_base - 55.5| <= 0.5            PASS   value=0.0315
0b: 0.03 <= ours_hash_share <= 0.08   PASS   value=0.0543
0c: M >= -0.1                         PASS   value=2.2580
0d: M <= 100*n_ours_hash/n_ref_pop    PASS   value=(2.2580, 3.2591)
>>> ROW 0 CLEAR <<<
```

All four checks pass on the first run. Sources are the ones the spec's §1.1 trap named
(`artefacts/20260808_live_run_0016-808{0,1}/{owsfz,wsjt-x}/ALL.TXT`) — the dead paths in
`2026-08-08-four-decoder-interim-comparison.py:20-23` were not used. As a belt-and-braces measure
per the spec, the loader also applies the `14.074` dial-prefix filter; a direct check of all four
source files beforehand showed every line already carries that prefix (no 18.100 contamination in
these particular snapshots), so the filter is a no-op here but is kept for defensive correctness.

## 2. Recovery side — Gate A

| quantity | value | population |
|---|---:|---|
| `R_base` (exact match, no exclusions) | **55.53%** (38 440 / 69 222) | reproduces the published 55.5% |
| `R_excl` (symmetric exclusion — both sides' `<...>` rows dropped) | 55.61% (37 874 / 68 109) | clean subpopulation |
| `R_wild` (exact OR wildcard, upper bound) | **57.79%** (40 003 / 69 222) | superset by construction |
| `M = R_wild − R_base` | **2.26 pp** | — |

Our `<...>` share (whole window): 2 256 / 41 521 = **5.43%** (predicted ~5.5%). Reference `<...>`
share (within the reference population): 1 113 / 69 222 = **1.61%** (predicted ~1.7%). Both close to
the board's prior numbers; the small differences are population-scoping (whole-window vs
reference-population denominators), not a discrepancy.

**Ambiguity accounting (§3.3, mandatory):**

| | value |
|---|---:|
| `n_wild_gained` (reference rows newly matched under wildcarding) | 1 563 |
| `n_ambiguous` | 8 |
| `n_ambiguous / n_wild_gained` | **0.5%** (predicted < 15%) |

Wildcard matching is essentially unambiguous here — almost every `<...>` row maps to exactly one
candidate reference row at its timestamp. `R_wild` is quoted below only as an upper bound, with this
fraction attached, per the spec's citation limit.

**Gate A trace:** `M = 2.26 ≥ 2.0` → **A-ROW 1**.

## 3. False-positive side — Gate B

Three-class plausibility table (matched / novel-corroborated / novel-single-instance-only), recomputed
with the corrected artefact paths, before and after removing OpenWSFZ's own `<...>` rows from the
novel buckets:

| pass | novel-corroborated (raw → total → ok) | novel-single-only (raw → total → ok) | implausible | denominator `\|A∪B\|` | `F` |
|---|---|---|---:|---:|---:|
| `F_base` | 2 074 → 1 988 → 1 724 | 1 898 → 1 704 → 155 | 1 813 | 42 722 | **4.24%** |
| `F_excl` (our `<...>` rows dropped from A/B first) | 597 → 592 → 344 | 1 548 → 1 477 → 23 | 1 702 | 40 322 | **4.22%** |

`ΔF = F_base − F_excl = 0.02 pp`.

`F_base` = 4.24% closely reproduces the board's "~4%" figure, which was computed on a different
(dead) code path — a useful cross-check that the corrected-path reimplementation is measuring the
same thing.

**§3.4 silent-exclusion count.** Recomputing the existing proxy's own `if not cs: continue` behaviour
explicitly: on the `F_base` pass, **280 rows** (86 from novel-corroborated, 194 from
novel-single-only) had every callsign-shaped token hashed to `<...>`, produced an empty `cs` list, and
were silently dropped from the plausibility denominator entirely — counted in neither the "known" nor
"unknown" bucket. This was previously an unmeasured, unbounded silent exclusion sitting underneath
the published ~4% figure; it is now bounded and small (280 of ~4 000 novel decodes, ~7%).

**Why `ΔF` is so small despite removing ~2 400 decodes.** Dropping our `<...>` rows shrinks both the
numerator (implausible count: 1 813 → 1 702) and the denominator (`|A∪B|`: 42 722 → 40 322) by
roughly proportional amounts — the hashed rows are, on this proxy, about as likely to look
"implausible" as the rest of the novel population, not disproportionately so. `<...>` contamination
depresses the *volume* of decodes flowing through the FP proxy but barely moves the *rate*.

**Gate B trace:** `ΔF = 0.02 ≤ 0.25` → **B-ROW 2**.

## 4. Predictions scored (§5 of the spec)

| # | prediction | outcome | scored |
|---|---|---|---|
| 1 | `R_base` reproduces 55.5% ± 0.5 | 55.53% | ✅ hit (ROW 0a) |
| 2 | our `<...>` share ≈ 5.5%, reference ≈ 1.7% | 5.43% / 1.61% | ✅ close (ROW 0b passed) |
| 3 | `M` = 1.5–3.0 pp | 2.26 pp | ✅ hit |
| 4 | Gate A fires **A-ROW 1** | A-ROW 1 | ✅ **hit** |
| 5 | `ΔF` = 0.5–1.5 pp (B-ROW 3 or B-ROW 1) | 0.02 pp (**B-ROW 2**) | ❌ **miss** — the Architect's own lower confidence on this one (§5 of the spec: "less confident than #4") was warranted |
| 6 | `n_ambiguous / n_wild_gained` < 15% | 0.5% | ✅ hit, by a wide margin |

Prediction #4 lands, #5 does not — consistent with the spec's own framing that the two gates are
independent and may disagree (§4). The recovery-side effect is real; the FP-side effect the Architect
expected is not there.

## 5. Consequences (per the spec's table, applied)

**Gate A = A-ROW 1.** Per spec §4 consequence table:

- The 55.5% recovery figure **must be restated as a bracket `[55.5%, 57.8%]`** everywhere it is
  quoted going forward, including the board's "~55–64% three-estimate band" and the 1942 report's
  "size of the prize" framing. §8 of the 1942 report is updated below (§7 of this document) and the
  board is updated in the same edit (HK-024).
- **Part of the measured D-001 gap is hash-table sizing, not decode capability.** The 256-slot,
  never-re-initialised hash table (`ft8_shim.c:599-632`) is now a **cheap candidate treatment** —
  this goes to the Captain as a recommendation *with a number* (`M = 2.26 pp`, upper bound `R_wild`
  bracket `[55.5%, 57.8%]`), not as session work started here (HK-011).
- 🛑 **Still not "new decodes."** Per spec §0, these are frames already demodulated and error-corrected
  correctly whose *text* cannot match the reference. Widening the hash table would improve the
  *measurement*, and for the end user would turn a degraded callsign into a resolved one — it is not
  new decode capability, and must never be described that way.

**Gate B = B-ROW 2.** Per spec §4 consequence table:

- **The ~4% FP estimate stands**, with its existing upper-bound caveat (the two cautions in the 1942
  report §2.3: 8080/8081 corroboration doesn't validate a decode, and the proxy has a floor not a
  zero). `<...>` contamination is **not** what drives it — `ΔF = 0.02 pp` is far inside the ROW 2
  bound of ≤ 0.25 pp.
- This **sharpens** the still-open D-009 Option B question from the 1942 report §7.3: the ~4% FP
  figure that argues *for* shallowing OSD is now confirmed not to be a hash-table artefact, so it
  carries its full evidentiary weight in the Captain's decision. The 55.5% recovery deficit that
  argues *against* Option B is, conversely, now known to be **partly** (not wholly) a text-matching
  artefact rather than a pure capability gap — narrowing, not closing, the case against.

## 6. What this does NOT establish (binding, per spec §7)

🛑 Not cited here and must not be cited elsewhere from this run:

- `R_wild` (57.79%) as "the real recovery rate" — it is an upper bound, always quoted with its
  ambiguity fraction (0.5%) attached. 🔴 **SUPERSEDED 23:10Z by H1a (ROW 1, `V = 0.9968`, `V_null =
  0.0000`): the wildcard matches are frequency-validated, `R_wild` is an estimate, and 20m recovery is
  `≈ 57.8%`. The bracket is retired.**
- Any recovery gained under `R_wild` as "new decodes" or a decode-capability improvement.
- Any 17m false-positive number (out of scope, spec §1.3).
- Any restatement of T1's `G` or T2's `D_int`/`U` (different thread, spec §1.2).
- The hash table as a settled D-001 treatment candidate — it is a **recommendation with a number**,
  pending the Captain's ruling (HK-011), not an approved change.

## 7. Downstream updates made in this edit

- **`BOARD.md`** — H1 result recorded, the 55.5% bracket propagated, `k_50`/hash-table framing
  updated. Same edit as this report (HK-024).
- **`2026-08-08-1942-qa-to-architect-four-decoder-live-comparison-two-legs.md` §8** — citation limits
  updated: 55.5% may now only be cited as the bracket `[55.5%, 57.8%]` (with `R_wild`'s ambiguity
  fraction attached if `R_wild` itself is quoted); the ~4% FP citation limit is unchanged (still an
  upper bound, still carries its existing two cautions) but is now explicitly cleared of the `<...>`
  confound.

## 8. Citation limits for this document

**May be cited once complete (this document):** `R_base` as the reproduction check; `R_excl` as
"recovery among decodes where the hash table interfered on neither instrument"; `R_wild` **only as an
upper bound, always with its 0.5% ambiguity fraction attached** — 🔴 **SUPERSEDED 2026-08-08 23:10Z by
H1a (`2026-08-08-2310-architect-h1a-wildcard-frequency-validation-results.md`, ROW 1, `V = 0.9968`):
the wildcard matches are validated by frequency, so `R_wild` is an ESTIMATE, not an upper bound, and
may be cited WITHOUT the ambiguity fraction. 20m recovery is `≈ 57.8%`; the `[55.5%, 57.8%]` bracket
is RETIRED.** ⚠️ **The FP level additionally carries `4.24–4.90%` (H1a §5) — this does NOT revise
Gate B, which gated a difference, not a level.** Also citable from this document: `M = 2.26 pp` and Gate A = A-ROW 1;
`ΔF = 0.02 pp` and Gate B = B-ROW 2; the 280-row §3.4 silent-exclusion count.

🛑 **May not be cited, under any row:** `R_wild` as "the real recovery rate" or without its ambiguity
fraction; any recovery gained here described as "new decodes" or a decode-capability improvement; any
17m FP number; any restatement of T1's `G` or T2's `D_int`/`U`; the hash table as an *approved* D-001
treatment (it is a recommendation, pending the Captain).

## 9. Artefacts

- Harness: `qa/cycleframer-alignment-replay/h1_hash_token_contamination.py` (**committed `c0af3fb`**
  at the Captain's explicit request; still no push, HK-014).
- Sources: `artefacts/20260808_live_run_0016-808{0,1}/{owsfz,wsjt-x}/ALL.TXT`, unchanged.
- No new capture, no `src/` change.
