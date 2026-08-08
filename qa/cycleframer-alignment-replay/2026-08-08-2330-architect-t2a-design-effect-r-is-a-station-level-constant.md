# Architect note: T2's gate was underpowered by ~3.5× — `r` is a station-level constant

**Author:** Architect, 2026-08-08 (23:30 UTC, from `date -u`, per HK-017 — local had rolled to 08-09;
UTC governs).
**Repo `main` at `05fd19b`.** Diagnostic harness:
`qa/cycleframer-alignment-replay/t2a_design_effect_diagnostic.py`.
**Concerns:** `2026-08-08-2319-qa-to-architect-t2-offset-curve-shape-results.md` (T2, ROW 3) and, in
its §4, `2026-08-08-2046-…-t1-frequency-quantisation-results.md` (T1, ROW 3).
**Status:** post-hoc diagnostic on data already on disk. No `src/` change, no capture, no rebuild.
NFR-021: counts, rates and frequency statistics only.

🛑 **This does NOT re-read T2's gate or T1's. Both stay ROW 3, final.** What changes is the *reading*
of why T2 landed there, and one phrase in its §1 that would otherwise reach the board overstated.
**QA executed T2 exactly as specced. Every defect below is in my drafting.**

---

## 1. The finding

`r` is a deterministic function of frequency, and a station's audio frequency is near-fixed for a
session. **So decodes cluster hard by frequency, and the decode count is not the number of independent
units.** Measured on T2's own population by a frequency-clustered bootstrap (400 resamples, seed
`20260808`):

| group | decodes | distinct freqs | decodes/freq | binomial SE | clustered SE | design effect |
|---|---:|---:|---:|---:|---:|---:|
| CEN | 15 204 | 521 | 29.2 | 0.40 | 1.69 | **4.2×** |
| INT | 16 855 | 627 | 26.9 | 0.38 | 1.34 | **3.5×** |
| MID | 7 936 | 404 | 19.6 | 0.56 | 1.93 | **3.5×** |

```
SE(D_int):  binomial 0.55   clustered 2.16   =>  D_int = 4.03 pp is 1.9 sigma
SE(U):      binomial 0.68   clustered 2.35   =>  U     = 1.85 pp is 0.8 sigma
```

My spec §4 predicted `SE(U) = 0.62` pooled, `0.93` after *"a conservative ×1.5 for clustering (repeat
decodes of the same station)."* **The real factor is ×3.5.** I named the exact mechanism and then
mispriced it by a factor of ~2.5.

## 2. What this changes in T2's reading — and what it does not

**ROW 3 stands. The verdict is correct.** Three corrections to how it is read:

1. 🔴 **`U`'s split-half disagreement is NOT evidence of instability.** Each half's `SE(U)` is ≈3.3 pp,
   so `−0.01` vs `3.38` is precisely what noise looks like at that scale. T2 §5's framing — "a genuine
   disagreement, not a rounding margin," resting on the spec's own ≈0.87 pp noise floor — **used my
   understated floor.** The correct statement is that **the replication check never had the power to
   confirm anything**, so ROW 3 is an *instrument limitation*, not a null.
   ⚠️ This project has a standing rule against exactly that conflation: **"ROW 4 from an unpopulated
   stratum is an instrument failure, not a null result"** (HK-021, S.1r). Same error class, different
   cause — there the stratum was empty, here it was underpowered.

2. 🔴 **`D_int = 4.03 pp` at 1.9σ (p ≈ 0.06) must not be called "well supported."** T2 §1 says *"the
   interior region is genuinely the worst case; that part of the mechanism is well supported"* — that
   phrasing is heading for the board and **overstates a 1.9σ result.** Correct wording: **suggestive,
   consistent with the predicted mechanism, not established.** ⚠️ Note the split-half agreement
   (3.95 / 4.13) does **not** add independent confirmation — it is the same data partitioned, and the
   pooled estimate already carries all of it.

3. ✅ **Prediction 4's "miss" is very likely this same effect, not a finding.** The `mean_r`
   SNR-quintile spread of 0.0226 Hz against a 0.02 bar: under clustering the per-quintile SE on
   `mean_r` is several times the binomial value, which comfortably accounts for a 0.0226 spread —
   and QA already noted the five means are **not monotone in SNR**, which is not the shape a real
   physical SNR–offset relationship would produce. **Read as sampling noise, not as "`r` and SNR are
   correlated."** QA flagged it honestly rather than rounding it away and declined to classify it;
   this note supplies the classification.

## 3. 🔴 The structural ceiling — this closes the question, permanently

Each rung maps to a fixed set of residues mod 25 (`3.125 = 25/8`), so over the hardcoded 200–3000 Hz
passband the number of frequencies that *can* fall in a group is capped — and the corpus has already
nearly exhausted them:

| group | distinct freqs observed | structural ceiling | saturation |
|---|---:|---:|---:|
| CEN | 521 | ~560 | **93%** |
| INT | 627 | ~672 | **93%** |
| MID | 404 | ~448 | **90%** |

**More runtime adds decodes per frequency, not new frequencies.** Lifting `U` from 0.8σ to 2σ needs
roughly 6× the independent units, and **those units do not exist on one band.**

> **The midpoint (two-candidate) question is not answerable by more data from this instrument at all.**
> It needs multiple bands with genuinely different station populations, or a synthetic bench where
> frequency placement is controlled.

✅ T2's ROW 3 consequence already said *"do not spend further effort without a materially larger
corpus — and do not propose a capture run to get one."* **That was right, and it is now right for a
provable reason rather than a prudential one.**

### 3.1 The same ceiling binds T1's `G`

`G` is an `r`-stratified contrast on the same corpus, so it sits at the same precision ceiling: **no
additional 20m data will sharpen it.** Combined with the standing attenuation caveat, the honest
summary of `G` is **direction confident, magnitude poorly determined** — which is close to what ROW 3
concluded, reached independently.

🛑 **This is not a re-read of T1's gate and must never be cited as one.** T1 stays ROW 3, `G = 3.16 pp`.

## 4. The rule this earns

> **Your unit of observation is not necessarily your unit of independence.** Before setting any
> threshold on a stratified contrast, ask what the stratifier is a *function of*, and count the
> distinct values of **that** — not the row count.

**The tell was free and available before either gate was drafted:** 67 243 decodes over ~2 800
possible integer frequencies is **~24 decodes per frequency**, computable in one line from the field's
data type. Both T1 and T2 set their bars off row counts.

**Standing fix for any future `r`-stratified work:** report distinct-frequency counts per group
alongside n, and quote a **frequency-clustered bootstrap SE**, never a binomial one.

## 5. Calibration — third instance of the same personal failure

C.5a's tell 3 was *"the caveat was written and then under-weighted."* Since then:

| # | run | I wrote | I priced it at | it was |
|---|---|---|---|---|
| 1 | C.5a (07-26) | "injected flips are confidently wrong" | a mild conservative bias | the dominant parameter |
| 2 | H1 (08-08) | spec §3.4: the FP proxy "is already partly insulated" | a large `ΔF` (0.5–1.5 pp) | 0.02 pp |
| 3 | T2 (08-08) | spec §4: "repeat decodes of the same station" | ×1.5 | ×3.5 |

**Three times I identified the exact mechanism in writing and then assigned it a number I had not
computed.** The fix is mechanical and I am adopting it: **when a spec names a confound, either compute
its magnitude before the run or declare the gate underpowered — never estimate it in prose.** The
computation here took two minutes against data already on disk.

## 6. Citation limits

**May be cited:** the design-effect table (§1); `SE(D_int) = 2.16`, `SE(U) = 2.35`, and the 1.9σ / 0.8σ
readings; the structural-ceiling table and the 90–93% saturation (§3); the conclusion that the midpoint
question is unanswerable from single-band `ALL.TXT` data.

🛑 **May not be cited:** any claim that this changes T1's or T2's row — **both stay ROW 3**; `D_int` as
"well supported" (§2.2); the `U` split-half disagreement as evidence of instability (§2.1); any
restatement of `G`; the §2.3 reading of prediction 4 as a *measurement* that `r` and SNR are
uncorrelated — it is a reclassification of a noisy result, not a test.
