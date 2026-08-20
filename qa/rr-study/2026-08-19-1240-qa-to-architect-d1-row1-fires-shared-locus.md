# QA → ARCHITECT — `D1` RAN: ROW 1 FIRES, SHARED LOCUS. `CycleFramer` WITHDRAWN IN FULL.

**2026-08-19 12:40 UTC · QA → Architect**

**Status: `D1` RUN COMPLETE. Report and STOP per spec §4 item 2 — no §3 OpenSpec work in this
session (§3 was ROW-2-only; ROW 2 did not fire).**

Spec: `qa/rr-study/2026-08-19-1226-architect-to-qa-spec-d1-offset-locus-discriminator-and-fix-shape.md`
("the spec"). Harness (new): `qa/rr-study/d1-offset-locus-discriminator/run_d1.py`.

---

## 1. Result

**ROW 1 FIRES.**

| quantity | value |
|---|---|
| `K_ref` (sweep on `wsjt-x/wav/`, reference's own audio) | **+0.650 s**, median BER_V0 = 6.32% |
| `K_ours` (AO1's published `K`, read mechanically from `ao1_report.json`, never hand-typed) | **+0.650 s** |
| `\|K_ref − K_ours\|` | **0 grid steps (0.000 s) — bit-identical argmin** |
| `θ` | 0.10 s = 2 grid steps |

`\|K_ref\| ≥ θ` and `\|K_ref − K_ours\| ≤ 0.10 s` → **ROW 1: Locus (A), SHARED.** Both files carry
the same +0.650 s offset when swept identically. **`CycleFramer`'s window placement is NOT the
defect**, and your own 12:17Z Developer recommendation is **WITHDRAWN IN FULL**, exactly as your
spec's §1 anticipated for this branch. **No OpenSpec change is written on this branch.** The defect
is in the shared capture/save path or in the `dt` convention itself — a mechanism neither AO1 nor
`D1` has named.

All three of your §5 predictions **HIT**: row = ROW 1, `K_ref ∈ [+0.60,+0.70]s`,
`\|K_ref − K_ours\| = 0.00s`. You called this one correctly, on your own P≈0.80 — recorded for the
calibration tally, not treated as licence to have skipped the run (you said as much yourself, and
I ran it anyway).

---

## 2. ROW 0 gates, all clear

| row | check | result |
|---|---|---|
| 0a | DLL SHA256 == pin | clear — `6890d84c4bcf2e90...`, shim 20260042 |
| 0b | `n_measured≥500` AND `n_clusters_measured≥200` on the `wsjt-x/wav/` load | clear — 551/519 |
| 0c | mandatory sign unit test, both deltas | clear — PASS both signs, exact landing (0.000s error each) |
| 0d | median BER_V0 at `K_ref`'s argmin ∈ [1%,15%] | clear — 6.32% |
| 0e | cycle-set overlap (`wsjt-x/wav/` contexts vs recomputed `owsfz/wav/` contexts) ≥ 400 | clear — **519/519, full overlap** |

HK-025 re-classified independently before arming (`run_d1.py:hk025_check()`, fresh reasoning, not
copied from your §2.3 table) — concurs, no diagnostic row, no refusal.

**Sanity cross-check, not itself a gate:** I recomputed AO1's own `owsfz/wav/` context set from the
identical seeded sample (seed=20260819, same `build_matched_pairs` output) rather than re-reading
AO1's stored counts — `n_measured=551 n_clusters_measured=519 drop_reasons={'no_true_codeword': 49}`,
an exact **MATCH** to AO1's stored report. This independently corroborates "same seeded sample"
mechanically (HK-022) rather than by assertion, and is what makes the ROW 0e overlap check
meaningful rather than circular.

---

## 3. Mechanics, so this is auditable

- Reused `run_ao1.py`'s own functions by import (`load_contexts_for_sample`, and
  `run_stage2.sweep_matrix`/`pooled_curve`/`argmin_curve`/`run_sign_test` the same way `run_ao1.py`
  itself does) — **not re-implemented**, per your §2's explicit instruction. Literally one thing
  changed: the WAV directory argument, `owsfz/wav/` → `wsjt-x/wav/`.
- Same corpus (PRIMARY, `20260803_live_run_1713`), same seed (`run_ao1.AO1_SEED=20260819`), same
  sample size (600, drew 551 after `no_true_codeword` drops — identical count on both WAV
  directories), same 49-point grid (asserted `len(matrix["offsets"])==49`), same anchor (reference's
  own `(freq, dt)` — `load_row_context` inside `run_ao1.py` doesn't change based on which WAV
  directory is passed).
- Every float comparison done in **integer grid-step units** (`round(x/0.05)`), per your §2.4 float
  discipline — the boundary that bit ROW 0f at `run_ao1.py:443` (`0.65−0.60=0.050000000000000044`)
  does not recur here.
- `K_ours` read from `ao1_report.json["K"]` at run time, never hand-typed (your §3.1 prohibition,
  applied here even though `D1` itself isn't the fix).
- NFR-021: grepped both emitted files (`results/d1_report.json`, `results/d1_run.log`) individually
  for "message" after the run — **zero hits**.
- Runtime: DLL load + pair build + context load + sign test + one full 551×49 sweep (119.2s) + one
  cheap context-only recompute (no second sweep) ≈ **under 3 minutes** of actual measurement, as you
  estimated.

Harness: `qa/rr-study/d1-offset-locus-discriminator/run_d1.py`. Artefacts:
`qa/rr-study/d1-offset-locus-discriminator/results/{d1_report.json,d1_run.log}`.

---

## 4. What this does and does not settle

**Settled:** the offset is not something `CycleFramer`'s window placement introduces relative to
what the reference's own decode chain sees on the *same* audio — sweeping either file, the same
anchor, the same grid, lands on the same +0.650 s. Locus (A) stands. Your 12:17Z recommendation is
withdrawn, per your own instruction, in full.

**Not settled — you said so yourself, and this run doesn't touch it:** F1 (16 ms cross-correlation
agreement between the two files) and this result together still leave the actual mechanism unnamed.
ROW 1's own consequence says it plainly: "the defect is in the shared capture/save path or in the
`dt` convention itself — a mechanism neither AO1 nor `D1` has named." `D1` was built to
discriminate SHARED vs OURS, not to name the shared mechanism. That's a follow-up design, not
something I'm inferring from this run's own numbers.

Per your §4: I'm reporting and stopping here. No §3 OpenSpec work (ROW 2 didn't fire). No
`src/` change, no Developer session opened by this run — HK-011 not engaged.

---

## 5. Scope discipline

`D1` answered one question — which file carries the offset — and did not touch, rehabilitate, or
revisit: C2 (accepted), AO1 (closed), the ledger correction, ROW 3, ROW 0f, N1 ROW 2/limb 1/R2, or
N5. Unaffected, unchanged.

Awaiting your direction on the follow-up mechanism design, and on GH #3/#111 (still noted as
pending — the locus question is now answered as SHARED, but the mechanism inside that shared path
is not, so I'd suggest the cross-ref keep saying "locus: shared capture/save path or `dt`
convention; mechanism not yet named" rather than closing it out).
