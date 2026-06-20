# D-009 R6 — Pre-Committed Decision Fork

**Date:** 2026-06-20
**Author:** Architect
**Companion to:** `2026-06-20-d009-nhard-diag.md` (diagnostic handoff),
`2026-06-20-d009-fp-filter-arch-design.md` (nhard design),
`2026-06-20-d009-fp-filter-arch-review.md` (Categories A–E, Paths 1–3)
**Defect:** D-009 — OSD false-positive callsign manufacture in noise
**Status:** Pre-commitment. Binds the R6 strategy to the diagnostic outcome
*before* the data is collected, so the investigation cannot drift into R7/R8.

---

## 0. Why this document exists

D-009 is five rounds deep (R1–R5) in **filtering OSD output**. R5 shipped an
*uncalibrated* `OSD_NHARD_MAX = 60` with a fabricated calibration claim and failed
S5 on the first trials. The corrective is the nhard diagnostic
(`2026-06-20-d009-nhard-diag.md`) — collect the histograms R5 skipped.

The risk is that R6 becomes "pick a different number and try again," then R7, R8.
To prevent that, **the diagnostic's two possible outcomes are mapped to two fixed
strategies here, and the run is augmented to capture the data both strategies need
in a single pass.** After the diagnostic, the path is already chosen by the data —
no new design round.

---

## 1. Augmented diagnostic capture (amends nhard-diag Actions 2 & 3)

The `NHARD_DIAG` probes in `decode.c` now emit the **candidate sync score**
alongside `nhard`, at both OSD sites:

```c
fprintf(stderr, "OSD_NHARD_SITE1 %d corr %.3f norm %.3f sync %d\n",
        nhard, osd_corr, osd_norm, cand->score);
```

So the same run that answers *"does nhard separate FP from genuine?"* also answers
*"could a higher sync-score entry gate have killed these FPs without OSD output
filtering at all?"* — without a second diagnostic round.

**Additional capture (amends Action 4):** in `nhard_observations.md`, tabulate for
both populations **(nhard, sync)** pairs, not nhard alone. Add to the data files:

- `nhard_fp_s5.txt` — `nhard sync` per line (FP candidates, S5 AWGN)
- `nhard_genuine_s7.txt` — `nhard sync` per line (genuine S7 P0–P2 recoveries)

Everything else in the nhard-diag handoff stands. **Still stop at Action 3/5 and
report to the architect** — this document tells the architect (me) which branch to
take, it does not authorise the developer to implement a fix.

---

## 2. The decision variable

From the two histograms, compute the separation on **each** axis independently:

- **nhard separation:** is there a threshold `T` such that
  `P(FP nhard ≤ T)` is small (target ≤ 3% per the widened S5 gate) while
  `P(genuine nhard ≤ T)` is high (target ≥ 0.97, i.e. we keep ~all real decodes)?
- **sync separation:** is there a sync floor `S` with the same property on the
  `sync` column?

Report both as 2×2 confusion outcomes at the best threshold on each axis, plus the
2-D separation (best joint `nhard`×`sync` boundary).

---

## 3. The fork

### Branch A — nhard separates cleanly (clear gap exists)

**Trigger:** a single `NHARD_MAX = T` gives FP-nhard ≤ T fraction ≤ 3% AND
genuine-nhard ≤ T fraction ≥ 97%.

**Action (R6-A):**
1. Set `OSD_NHARD_MAX = T` (the measured gap value, **documented with the
   histogram it came from** — no repeat of the R5 fabrication).
2. Keep `OSD_CORR_THRESHOLD = 0.10` (nhard carries noise rejection).
3. Keep Tier-3 text Rules A/B/C (already landed).
4. Rebuild production win-x64, bump shim (next free version), commit.
5. **Gate to ship:** AD3 (S5 ≥ 100 slots, FP rate = 0, 95% upper bound ≤ 3%) and
   AD4 (S7 P0–P2 K=5, co_channel_sweep ≥ 89%).
6. **No Tier 2/4. No ABI break.** This was the right track; we ship.

This is the arch-design's intended terminus. It is the *cheapest* good outcome.

---

### Branch B — nhard overlaps (no usable gap)

**Trigger:** every `T` that suppresses FP-nhard to ≤ 3% also rejects > 3% of
genuine decodes. This confirms the nhard-diag §1 hypothesis: ft8_lib's depth-2
`osd_decode` Hamming-minimises by construction, so FP and genuine codewords are
*both* close to the channel and nhard cannot separate them.

**This refutes nhard as an output discriminant for our OSD.** Do **not** propose
R7 with a different output statistic (corr/norm is already refuted; nhard now
refuted — the output-filtering avenue is exhausted by measurement, not opinion).

**Pivot to attacking P1 at the source — gate OSD *entry*, not OSD *output*:**

The sync column tells us whether this works. Two sub-cases:

- **B1 — sync separates:** if genuine OSD recoveries sit at a clearly higher
  `cand->score` than the noise FPs, add a dedicated **OSD-entry sync floor**: only
  invoke `osd_decode` when `cand->score >= OSD_MIN_SYNC` (a threshold *above* the
  global `min_score` used for BP candidates). This is structurally what WSJT-X does
  — it does not run OSD on every BP failure. Calibrate `OSD_MIN_SYNC` from the same
  histogram. Keep BP's `min_score` unchanged so non-OSD sensitivity is untouched.
  Ship gate: same AD3/AD4 as Branch A.

- **B2 — neither nhard nor sync separates:** the FP population is genuinely
  indistinguishable from genuine weak decodes on every cheap axis. Escalate to the
  **scope decision** (§4) — this means OSD's noise-FP cost may be structural and the
  question becomes whether the −21→−27 dB gain justifies it. Do not implement
  anything further without Captain sign-off on scope.

---

## 4. Scope backstop (only reached via B2)

If B2, surface to the Captain explicitly:

> OSD added a real co-channel/weak-signal gain (D-001: S7 51.6% → 80.2%,
> co_channel_sweep ≈ WSJT-X). It also manufactures CRC-14 false positives from
> pure noise that no cheap output statistic (corr/norm, nhard) or entry statistic
> (sync) can fully separate. Options at that point, in order of preference:
>
> 1. **Tier 2/4 ABI flag** (arch-design Path 1): tag OSD-origin decodes and apply a
>    strict text profile *only* to them — accepts residual Category E but removes
>    Categories A–D with zero FN on BP traffic. The ABI bump (48→52 bytes) is paid
>    here, justified by measurement.
> 2. **OSD depth/iteration reduction** — trade some −27 dB reach for fewer noise
>    coincidences; re-measure the S7 vs S5 trade curve.
> 3. **Restrict OSD to AP-armed (QSO-context) decodes only** — OSD runs only when
>    `ap_overrides != NULL`, i.e. when we already expect a specific station. Blind
>    OSD (the FP source) is disabled; H6 directed gain retained. Largest behaviour
>    change; smallest FP surface.

These are *not* R6 actions. They are the menu if and only if both cheap axes fail.

---

## 5. What ships at the end of R6

| Outcome | Fix | ABI break | Ship gate |
|---|---|---|---|
| A (nhard gap) | `OSD_NHARD_MAX = T` + Rules A/B/C | No | AD3 + AD4 |
| B1 (sync gap) | `OSD_MIN_SYNC` entry gate + Rules A/B/C | No | AD3 + AD4 |
| B2 (no gap) | — escalate to §4 scope decision — | TBD | Captain sign-off |

In **A and B1 the loop terminates at R6.** Only B2 opens a further (scoped,
Captain-gated) decision. There is no R7 that is "another threshold guess."

---

## 6. Acceptance for this fork doc

| # | Criterion |
|---|---|
| F1 | Diagnostic probes emit `sync` alongside `nhard` at both OSD sites (done in this commit) |
| F2 | `nhard_observations.md` reports nhard AND sync separation for both populations (per §2) |
| F3 | Architect selects A / B1 / B2 strictly from the §2 decision variable — no eyeballing |
| F4 | Chosen threshold is documented with the histogram it was read from (no R5-style unbacked constant) |
| F5 | Whichever branch ships re-runs the widened S5 (≥100 slots) and S7 P0–P2 gates before merge |

---

## 7. References

- `2026-06-20-d009-nhard-diag.md` — diagnostic handoff (Actions 1–5)
- `2026-06-20-d009-fp-filter-arch-design.md` — nhard design, AD1–AD8, measurement gate
- `2026-06-20-d009-fp-filter-arch-review.md` — Categories A–E, Paths 1–3, calibration ceiling
- `native/ft8_lib_build/patched/ft8/decode.c` — OSD sites (~636, ~820); `min_score` sync gate (~276); `cand->score`
- WSJT-X `lib/ft8/osd174_91.f90` — `nharderrors`; and the sync-gated OSD entry pattern (decoder.f90)
- MEMORY Lesson 10 — corr/norm is a weak (magnitude-coupled) discriminant; why an orthogonal axis was sought
