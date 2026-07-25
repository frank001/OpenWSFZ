# Deliverable #5 — maximum acceptable alignment error

> **Superseded 2026-07-26.** Closed alignment-replay work, retained as history; no live D-001
> lead. See `2026-07-26-0015-d001-consolidation-and-clean-slate.md`.

**Author:** Architect, 2026-07-25. **Status:** FINAL (supersedes the provisional value in SPEC §10
item 5 and `tasks.md` 11.7 / 10.8(d)).
**Derived from:** Phase 1b (`2026-07-25-phase1b-findings.md`, 400 cycles x 11 offsets), Phase 1a's
finer negative grid (25 cycles x 7 offsets), and the session-wide arm-A DT baseline
(51,862 signals across all 2,827 cycles of `artefacts/20260724_live_run_2227/`).
**Consumer:** `tasks.md` 10.8(d), as a live acceptance bound; and as a cap on correction magnitude.

---

## 0. First, the sign convention — settled

Three documents (SPEC §10 item 5, SPEC §6.3, `tasks.md` 11.7) each assert the tolerance interval is
"wider on the negative side," and each then quotes an interval that is wider on the *positive* side.
Both statements are correct. They are stated in different frames, and no document names either
frame. That is the defect.

**The δ convention is not ambiguous** — `rewindow.py` settles it in code:

```python
base = round(delta_seconds * SAMPLE_RATE)          # window starts at base + k*W
```

Positive δ starts the cut window **later** in the audio, so a signal at true DT `d` is observed at
`DT_obs = d - δ`. The decoder accepts `DT_obs ∈ [-1.60, +3.12]` (`decode.c:279`). Therefore a signal
survives iff `δ ∈ [d - 3.12, d + 1.60]`. This is confirmed empirically, not just algebraically:
Phase 1b's measured 50% crossings are -2.345 and +2.434 against `DT_med ± ` the bound's two halves
(-2.320, +2.400).

The two frames, and which is which:

| frame | interval (0724) | wider side | what it describes |
|---|---|---|---|
| **DT-relative** (`δ - DT_med`) | `[-3.12, +1.60]` | **negative** | the decoder's search bound. A property of ft8_lib. |
| **absolute δ** (what the framer controls) | `[-2.32, +2.40]` | **positive** | the bound *after* the population's `DT_med = +0.80` shifts it right. |

Measured on the model curve, the DT-relative asymmetry is not subtle — at ±2.3 s from `DT_med`,
population recall is **0.966 on the negative side and 0.055 on the positive side.** The absolute
frame nearly cancels that asymmetry only because `DT_med` happens to be +0.80, roughly half the
difference between the bound's two halves.

**Ruling: every quoted interval, including this deliverable and 10.8(d)'s gate, is stated in the
absolute δ frame**, because that is the frame `δ_live(k) = DT_ref(k) - DT_live(k)` (§6.3 step 3)
produces and the frame the framer's error lives in. Where a document describes the *asymmetry
direction*, it must name the frame explicitly. Corrected text for the three affected passages is in
§5 below.

---

## 1. The bound

> **δ ∈ [ DT_p95 − 3.12 , DT_p05 + 1.60 ] seconds**
>
> — keep the alignment error inside the window where at most 5% of the signal population is pushed
> off each edge of the decoder's search bound.

**Instantiated on the 0724 session** (`DT_p05 / DT_p50 / DT_p95 = +0.40 / +0.80 / +1.50`):

> ### δ ∈ [ −1.62 , +2.00 ] s at `DT_med = +0.80`

This is the number 10.8(d) consumes. It is **not** a constant of the decoder — see §3.

## 2. What it costs at the edges

| quantity | at δ = −1.62 | at δ = +2.00 | inside (δ = 0) |
|---|---|---|---|
| population recall (model) | 0.957 | 0.956 | 1.000 |
| per-cycle **median** recall (measured) | 0.90 | 0.90 | 1.000 |
| per-cycle **p10** recall (measured) | 0.81 | 0.81 | 1.000 |
| cycles decoding **nothing** | 3 / 400 | 1 / 400 | 0 / 400 |

The percentile form is defined on population loss, and the median cycle empirically retains 0.90 at
both edges — the ~0.05 gap between population and median-cycle recall is a consistent bias visible
at every plateau point in Phase 1b (residuals −0.046 at δ=−1.0, −0.054 at δ=+2.0). Because both
edges carry the same bias, the interval stays balanced under either statistic.

**Percentile is stated, per SPEC §10's own constraint — but in the DT frame, not the recall frame.**
That is the improvement over the provisional value: putting the percentile inside the formula makes
the bound adapt to the DT distribution's *shape*, not merely its median.

Other operating points, if a different risk appetite is wanted:

| DT percentile pair | interval | population recall at edges |
|---|---|---|
| p2 / p98 | `[−1.32, +1.60]` | 0.980 / 0.981 |
| **p5 / p95 (recommended)** | **`[−1.62, +2.00]`** | **0.957 / 0.956** |
| p10 / p90 | `[−1.92, +2.20]` | 0.910 / 0.893 |

## 3. How the form was validated, and why it is the portable one

The percentile form was **not** fitted. It is a restatement of the same zero-parameter model Phase 1b
tested: the edge at which 5% of signals fall past `+3.12` is `DT_p95 − 3.12`, and the edge at which
5% fall past `−1.60` is `DT_p05 + 1.60`. Its agreement with the sweep is therefore a check, not a fit:

| edge | percentile form | measured (90% median-recall contour) | Δ |
|---|---|---|---|
| negative | **−1.620** | −1.611 (Phase 1b 400-cycle bracket, −1.0/−2.0) | 0.009 |
| positive | **+2.000** | +2.011 (Phase 1b, −0.0/+2.0/+2.25) | 0.011 |

Both within 0.011 s. Phase 1a's independent 25-cycle fine grid puts the negative edge at −1.514,
0.11 s tighter — consistent with its much smaller sample and with the known reproducible under-
prediction near δ ≈ −2.25 noted in Phase 1b §"Measured vs. predicted".

**Why percentiles and not `DT_med` ± fixed margins.** The median-only form
(`δ ∈ [DT_med − 2.30, DT_med + 1.20]`) reproduces 0724 exactly but silently assumes 0724's DT
*spread*. That spread is unusually tight — **IQR 0.10 s, p5–p95 span 1.1 s, σ 0.386** — so the
margins it implies are near their maximum. A session with a broader DT distribution would need
tighter margins, and the median-only form would not notice. The percentile form re-derives them.

## 4. Transfer conditions — read before applying to any other session

1. **Re-derive `DT_p05` and `DT_p95` from the target session's own reference decodes.** The interval
   tracks the signal population; it is not a decoder constant. On 0724 the two forms coincide, which
   is precisely the situation in which an untested assumption is invisible.
2. **`DT_med = +0.80` is measured in OpenWSFZ-0724's own cut frame, which itself carried alignment
   error.** A session run against a *fixed* framer will have a different `DT_med` — that is the
   point of fixing it. 10.8(d) must therefore measure that session's DT baseline and re-instantiate
   the bound, not import `[−1.62, +2.00]` as a literal.
3. **`decode.c:279` is load-bearing.** Any re-vendoring or re-patching of ft8_lib invalidates the
   `[-1.60, +3.12]` bound and every figure here (standing note, `tasks.md` 11.4).
4. **Single session, single band, single night.** The independent replication is 0723
   (`tasks.md` 11.10), not yet run. Until it does, treat the *form* as validated once and the
   *instance* as specific to 0724.
5. **The zero-recall floor does not vanish inside the interval.** 1–3 cycles in 400 decode nothing
   even at δ well within bounds. A gate phrased as "no cycle loses decodes" would fail on clean
   alignment; 10.8(d)'s "≥95% of cycles inside the interval" phrasing is the correct shape.

## 5. Corrections required to the three affected documents

**(a) SPEC §10 item 5** — replace the provisional value and name the frame:

> the decoder's search window is itself asymmetric (`DT_obs ∈ [−1.60, +3.12]`), so **in the
> DT-relative frame** the interval is `[DT_med − 3.12, DT_med + 1.60]` — wider on the negative side,
> the opposite of what item 9 claimed. **In the absolute δ frame the study measures and 10.8(d)
> consumes, `DT_med = +0.80` shifts this to `[−2.32, +2.40]`, which is wider on the *positive*
> side. Quote intervals in the absolute frame; name the frame whenever describing the asymmetry.**
>
> ~~Provisional value … **δ ∈ [−1.6, +2.0] for ≥92% median recall**~~ → **FINAL, Phase 1b:
> `δ ∈ [DT_p95 − 3.12, DT_p05 + 1.60]` = `[−1.62, +2.00]` at `DT_med` = +0.80, for 0.90 median /
> 0.81 p10 per-cycle recall. See `2026-07-25-deliverable-5-alignment-bound.md`.**

**(b) SPEC §6.3** — the parenthetical "in the opposite direction, with *more* headroom on the
negative side" is true only in the DT-relative frame; append "(DT-relative frame — in the absolute
δ frame this session's `DT_med = +0.80` makes the positive side wider)". The step-3 sign correction
itself is unaffected and still stands.

**(c) `tasks.md` 11.7 and 10.8(d)** — same substitution; 11.7's "with *more* headroom on the
negative side" must gain the same frame qualifier, and both provisional `[−1.6, +2.0]` values become
the final bound above. 10.8(d) additionally needs transfer condition #2 spelled out: it must
re-derive the interval from its own session's DT percentiles rather than hard-coding 0724's.

## 6. Provenance

`_work/phase1b/baseline_dt_population.json` (51,862 DT values), `phase1b_summary.csv` (11 measured
points, n=400 each), `phase1b_verdict.json`, `_work/phase1a_summary.csv` and
`_work/phase1a_refine_summary.csv` (negative-side fine grid, n=25). All git-ignored and local per
NFR-021 — derived from `ALL.TXT` files containing real third-party callsigns. This document contains
only aggregate timing statistics and no callsigns.
