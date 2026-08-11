# SPEC R2 — Refinement in the decode path: the arm that resolves D-001

**Author:** Architect → QA
**Date:** 2026-08-11 19:10:21Z (mechanically derived, HK-017)
**Programme:** `2026-08-11-1910-architect-to-qa-programme-d001-sync-refinement.md`
**Shim version:** **20260041** · **Depends on:** R0 PASS **and** R1 all-AC PASS
**Type:** 🔴 **BUILD SPEC with acceptance criteria** — but unlike R0/R1 this one **also produces a
finding about D-001**, in either direction. See §6.

---

## 1. What this delivers

R1 built and validated a refiner that reports a corrected `(Δf, Δt)` for a candidate. **R2 makes
the decoder actually use it.**

🔴 **The design point that must not be got wrong.** Refining to ≈0.5 Hz / 5 ms and then extracting
symbols from the **3.125 Hz / 0.08 s magnitude waterfall** would throw the refinement away — the
best you could do is pick a marginally better lattice cell. **Extraction must be performed on the
complex baseband at the refined position**, computing per-symbol tone bins there directly. That is
what WSJT-X does (its `cs(0:7,·)` come from the refined baseband, never from a coarse grid), and it
is the only way the refinement reaches the LLRs.

**Scope for R2: non-coherent, single-symbol extraction at the refined position.** Magnitude of the
per-symbol tone bins computed from the baseband. 🛑 **Coherent multi-symbol metrics
(`bmetb`/`bmetc` analogue) are R3 and are OUT OF SCOPE here** — they are a separate, additive
change and folding them in would make an R2 null uninterpretable, which is the exact mistake R1
exists to prevent.

🛑 **Licence policy (programme §2.1): WSJT-X may be read for method, NOT ONE LINE copied.**
🛑 **subtract-and-resynthesise is DEAD** — three builds, three reverts, −17 pp at worst. Not in
scope, and adding it voids the arm.

---

## 2. Pins — assert every one at startup, fail loudly

| item | value |
|---|---|
| corpus | 20m, `artefacts/20260808_live_run_0016-808{0,1}/`, **2 529 cycles** |
| `REF` | **69 222** (two-instance intersection) |
| baseline recovery | **≈57.8%** (H1a; the `[55.5, 57.8]` bracket is retired, `V` = 0.9968) |
| baseline FP | **4.24–4.90%**, best estimate ~4.7% |
| baseline DLL | `f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015`, shim 20260033 |
| 🛑 never use | `39aa1031…` — unmerged RC4 three-pass diagnostic build |
| R2 DLL | shim **20260041**, SHA recorded at run time |
| `ALL.TXT` fields | `[4]` SNR · `[5]` **DT** · `[6]` **freq Hz** — ⚠️ confusing 5/6 inverts a result exactly |

🔴 **Both legs (baseline and refined) must run in the SAME session on the SAME corpus with the SAME
harness.** Do not compare against a historical number. 57.8% is the expected baseline, but the
baseline leg is **measured, not assumed** — if the re-measured baseline disagrees with 57.8% by
more than its own SE, **stop and escalate**; something else has changed.

---

## 3. Pre-flight (ROW 0) — run before the arm, all must pass

| check | bar | if it fails |
|---|---|---|
| **0a** `REF` reproduction | exactly **69 222** | VOID — loader defect |
| **0b** determinism | 3 process runs, results **mechanically byte-diffed** identical, on both legs | VOID. 🔴 Depends on R0's `p23_common.py:182` fix. *"Two runs, byte-identical" must be MECHANICALLY DIFFED, never asserted.* |
| **0c** DLL identity | SHA asserted at startup on both legs; shim 20260033 / 20260041 | VOID |
| **0d** 🔴 **the refiner is actually firing** | **≥ 50%** of decoded candidates carry a **non-zero** applied `(Δf, Δt)`, and the applied refinements are **not all identical** | VOID — the stage is wired in but inert, and the arm would measure a no-op while looking like a null |
| **0e** baseline sanity | re-measured baseline recovery within its own SE of 57.8% | escalate, do not proceed |

**0d is the one that would otherwise go unnoticed.** A refinement stage that computes correctly
(R1 passed) but is not actually consulted by extraction produces a *perfect null* that looks
exactly like a falsified hypothesis. **Assert it mechanically, on the production path, not by
reading the code.**

---

## 4. Metrics

**M1 — recovery (co-primary).** `R_refined` and `R_base`, both against `REF`, same corpus.
`ΔR = R_refined − R_base`. Clustered CI by **frequency-cluster bootstrap** (HK-021(i): unit of
observation ≠ unit of independence; residual `r` is a station-level constant, so cluster — **never
binomial**).

**M2 — false positives (co-primary, NOT deferred).** Unmatched-output fraction on both legs, plus
the callsign-plausibility FP proxy. ⚠️ **The Captain deferred FP on G2 ("we will look at FP
later"). R2 cannot defer it** — refinement changes what reaches the CRC, and a recovery gain bought
with an FP blow-out is a different product, not a better one. Both legs, same proxy, reported
together.

**M3 — 🔴 the independent end-to-end confirmation, and it is nearly free.** Compute `mean_r`, the
residual to the nearest 3.125 Hz lattice point, on **our own reported frequencies**, both legs.

This exploits an instrument already built and closed-form validated (T1, H1a):

| | `mean_r` | meaning |
|---|---|---|
| uniform null | **0.780** (exact, derived from the 13-rung ladder) | off-grid |
| OpenWSFZ baseline | **0.2397 / 0.2404** | on-grid — pure integer-Hz reporting rounding |
| WSJT-X | **0.7398** | indistinguishable from uniform ⇒ refined |
| **OpenWSFZ after R2** | **must move decisively off 0.24 toward the null** | ⇒ refinement reached the reported output |

✅ **This is the cheapest and strongest confirmation available that refinement is live end to end**,
it needs no new instrument, and it is independent of whether recovery improves. 🔴 **If `ΔR ≈ 0`
but `mean_r` has moved off-grid, the refinement genuinely happened and the null is a real finding
about D-001. If `mean_r` has NOT moved, the null is an integration bug** — and that distinction is
the single most valuable thing this spec produces.

**M4 — cost.** Wall-clock both legs; report the ratio.

---

## 5. Acceptance criteria

**Bars are derived from the corpus's own resolution and from measured baselines. 🛑 No bar in this
spec comes from an Architect magnitude expectation** — my last four magnitude calls all missed with
the interval right and the implication wrong.

| # | criterion | bar |
|---|---|---|
| **AC-1** | recovery improves | `ΔR > 3 × SE(ΔR)`, clustered, computed on this corpus |
| **AC-2** | FP not materially worse | unmatched-output fraction rises by **≤ 2.0 pp** absolute |
| **AC-3** | refinement reached the output | `mean_r` moves from ~0.24 to **> 0.45** (midpoint of on-grid and the 0.780 null) |
| **AC-4** | determinism | ROW 0b, both legs, byte-diffed |
| **AC-5** | cost | reported; **no fail bar** — escalate if the refined leg exceeds ~8 h |

⚠️ **AC-1's bar is statistical, not practical.** Whether a statistically-real `ΔR` is *worth
shipping* is the **Captain's** decision, not QA's. Report the number and the CI; do not editorialise
a ship/no-ship recommendation.

---

## 6. 🔴 How this resolves D-001 — evaluate all four branches BEFORE running (HK-021(k))

| outcome | reading | next |
|---|---|---|
| **AC-1 ✅ AC-2 ✅ AC-3 ✅** | **D-001's cause is confirmed and the fix works.** | Captain rules on shipping; R3 (coherent multi-symbol) becomes worth speccing |
| **AC-1 ✅ AC-2 ❌** | Real gain bought with real FP cost. **A genuine engineering trade.** | 🔴 **ESCALATE — the Captain's call, not QA's.** Do not tune to make AC-2 pass |
| **AC-1 ❌ AC-3 ✅** | 🔴 **The refinement provably happened and did not help. The architectural hypothesis organising the last month is FALSIFIED** — with a validated instrument (R1) and a live-path assertion (ROW 0d) behind the null. | **This is a RESULT, not a failure.** The lattice is not the binding constraint; the programme looks elsewhere with this definitively closed |
| **AC-1 ❌ AC-3 ❌** | Integration bug — refinement is not reaching the output. | **Says NOTHING about D-001.** Fix and re-run |

🔴 **Every branch changes what happens next, so these are gates and not diagnostics.** And note
that **three of the four branches resolve D-001** — the fourth is a bug to fix. That is the point
of the R0→R1→R2 ladder and it is why R1 was not allowed to be skipped.

---

## 7. Reporting

Standard QA→Architect report: the ROW 0 trace in order; M1–M4 with clustered CIs; the four-branch
reading actually applied; the byte-diff evidence; both DLL SHAs; and **citation limits** — what may
and may not be quoted from this arm.

🛑 **Do not restate any figure from the standing blacklist** — `A` = 15.55 in any form, `k_50`,
`c_bottom`, `E_sep` = +46.039 pp, `Δ_local`/`Δ_cycle`, `sensitivity_25_100`. The depth caveat
("every recovery figure is against `NDepth = 3`") stays **exactly as worded**.

## 8. Constraints

🔴 **HK-011 in full** — QA authors `dev-tasks/*.md` and STOPS; separate Developer session; Captain
reviews the diff. 🔴 **HK-014 / HK-010 / HK-006** unchanged.
🛑 **No parameter tuning inside this arm.** No `K_MAX_PASSES`, no candidate caps, no passband, no
OSD thresholds, no LLR scaling, **no OSR change** (barred separately, needs its own
pre-registration with FP primary). **Refinement is the only variable.** If it is tempting to tune
something to make a bar pass, that is the signal to stop and escalate.

## 9. Architect predictions (scored on report)

- **ROW 0d: PASS**, and **AC-3: PASS** — both categorical, magnitude-free, my least-bad category
  (5/7).
- 🛑 **NO prediction on `ΔR`, on FP movement, or on cost.** DIRECTIONAL is my weakest category
  (**1/3**) and **no gate in this spec turns on any prediction of mine** — every bar is derived from
  the corpus, a measured baseline, or a closed-form null.
- ⚠️ **Recorded so it can be scored against me:** I believe the largest risk to this arm is not
  that refinement fails to help, but that it helps **and** inflates FP (the AC-1 ✅ / AC-2 ❌
  branch). That is a DIRECTIONAL call, it is written as an escalation path in §6 and **not** as a
  gate, and it should be treated as low-confidence.
