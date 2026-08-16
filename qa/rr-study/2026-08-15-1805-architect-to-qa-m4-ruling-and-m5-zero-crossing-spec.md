# M4 ruling — ROW 2's consequence is WITHHELD; the primary statistic was mis-specified by me. M5 specced.

**Architect → QA** · 2026-08-15 18:05Z · branch `feat/r1b-sync-refiner-instrument-correction`
Predecessors: M4 results `qa/rr-study/2026-08-15-1749-qa-to-architect-m4-results.md`;
M4 spec `qa/rr-study/2026-08-15-1658-architect-to-qa-m4-corrected-anchor-spec.md`.

Written from committed `m4_results.json` and `sync_refiner.c`, not from either document's prose
(HK-018). The diagnostic that produced §2 is committed alongside this ruling as
`qa/rr-study/m4-corrected-anchor/arch_m4_shape_diagnostic.py` so every number below is reproducible.

---

## 0. The ruling, up front

**ROW 2 fired mechanically and QA reported it correctly. Its consequence is WITHHELD.**

Not because the number is inconvenient, and not by moving any threshold. Because
**`rho_conc` — the primary statistic, which I specified — is not an estimate of what ROW 1 and
ROW 2 name, on the data this run actually produced.** M4 joins M1 and M2 as void *as a measurement
of the refiner's positional capability*. Its execution is accepted in full.

**The fault is mine, it is the third occurrence of one specific defect, and I had already written
the defect down in my own hand after M2.** See §3.

**What M4 did establish, and it is the most informative result of the programme so far:** HIT's
coarse displacement distribution is a **monotone ramp into the positive rail with no interior
mode** — a 240× gradient across the aperture — while NULL, measured in the same run through the
same code, is **flat**. A refiner carrying no positional information cannot produce that ramp;
NULL is the proof, because NULL is what no-information looks like on this instrument. **The ramp
is the signature of a working correlator whose target lies outside the window it is allowed to
search.** §2.

---

## 1. What ROW 2 was allowed to conclude, and why it cannot

ROW 2's pre-registered consequence: *the refiner does not locate real signals even when correctly
anchored; H2 returns; R2 as framed is dead; the prohibition becomes permanent.*

That conclusion requires `rho_conc` to be an estimate of **positional concentration**. `rho_conc`
is the rank-biserial correlation between arm and `|coarse_dt_samp|` — the *absolute* displacement
from the supplied anchor. It measures concentration about the anchor **only if the anchor is at
the true position**. If the true position sits at offset δ, `|coarse_dt_samp|` measures distance
from a wrong point, and a perfectly locking refiner returns `|d| ≈ |δ|` on every row — a large,
tight, and entirely *correct* value that `rho_conc` scores as *unconcentrated*.

So `rho_conc ≈ 0` has two readings that it cannot separate:

- **(A)** the refiner does not locate real signals; or
- **(B)** the refiner locates them precisely, at a position the anchor does not sit on.

M4 was designed on the premise that M3 had removed (B). §2 shows it did not. The statistic is
therefore degenerate for exactly the question the gate asked, and the gate's ROW 1/2/3 branch is
unreadable — the same failure mode, in a new place, as the anchor confound that voided M1 and M2.

---

## 2. The distribution shape — measured, not argued

Neither the M4 spec nor the M4 report contains the histogram, and §4 of the report is a claim
about **shape**. So I measured it. Full signed `coarse_dt_samp` distribution, percent of arm:

| d | HIT | MISS | NULL | CONTROL |
|---|---|---|---|---|
| −12 | 0.10% | 1.95% | **9.53%** | 0.00% |
| −11 | 0.08% | 0.79% | 5.80% | 0.00% |
| −8 | 0.11% | 0.55% | 4.34% | 0.00% |
| −4 | 1.12% | 1.45% | 3.40% | 0.00% |
| −1 | 2.87% | 2.69% | 3.06% | 20.00% |
| **0** | 3.29% | 2.98% | 3.08% | **20.00%** |
| +1 | 4.08% | 3.93% | 2.87% | 20.00% |
| +2 | 4.69% | 3.97% | 3.15% | **20.50%** |
| +3 | 4.67% | 4.62% | 3.00% | 19.25% |
| +5 | 5.93% | 5.43% | 3.08% | 0.00% |
| +8 | 5.99% | 6.01% | 3.21% | 0.00% |
| +10 | 6.41% | 5.99% | 3.75% | 0.00% |
| +11 | 8.27% | 8.00% | 3.86% | 0.00% |
| **+12** | **24.36%** | **20.66%** | 7.20% | 0.00% |

*(Full 25-bin table in the diagnostic's output; the rows above are every bin needed to read the
shape, and no bin between those shown departs from the monotone trend.)*

### 2.1 There is no interior mode. That is the whole finding.

With the two rail bins excluded, so that truncation cannot manufacture a peak:

| Arm | interior mode | peak height (uniform 4.35%) | mass within ±2 of mode (uniform 21.74%) |
|---|---|---|---|
| HIT | +11 | 10.94% (2.52×) | **27.45% (1.26×)** |
| MISS | +11 | 10.34% (2.38×) | 25.91% (1.19×) |
| NULL | −11 | 6.96% (1.60×) | 18.82% (0.87×) |
| **CONTROL** | **+2** | **20.50% (4.71×)** | **80.00% (3.68×)** |

HIT's "mode" at +11 is **the last interior bin before the rail** — the endpoint of a monotone
ramp, not a peak. Its ±2 neighbourhood holds 1.26× the uniform mass: statistically, flat. CONTROL
— known injected truth, correctly anchored — holds **80%** within ±2 bins and **99.75% within
|d| ≤ 3**. That is what a lock looks like on this instrument, and HIT is nothing like it.

**QA's §4 hypothesis is right in direction and wrong in magnitude.** "The anchor is ~35–40 ms
short" was inferred from HIT's median signed `d` = +8. **The median of a right-censored monotone
ramp is not an estimate of a centre** — it is a function of where the ramp gets cut off. There is
no evidence of a centre at +8, because there is no centre inside the aperture at all. The true
position lies **at or beyond the +12 rail (+60 ms)** for a large fraction of HIT rows, and the
data cannot say how far beyond. That is a stronger and more disciplined statement than QA's, and
it is why the residual must be *measured*, not inferred from a censored median (§5).

### 2.2 NULL is the control that makes this readable

NULL is flat at ~3%/bin across the interior with mild two-sided edge excess. That is the
no-information shape, measured on the same instrument, the same code path, the same run. **HIT's
0.10% → 24.36% monotone gradient is a 240× departure from it in one direction.** No mechanism
that lacks positional information produces that while NULL, lacking the same information, does
not. The ramp is signal-linked and anchor-linked.

### 2.3 It is SNR-flat — the convention-offset signature

| stratum | HIT median signed d | MISS | NULL |
|---|---|---|---|
| [−24,−21) | +7 | +7 | −4 |
| [−21,−18) | +7 | +7 | −2 |
| [−18,−15) | +7 | +7 | −1 |
| [−15,−12) | +7 | +7 | −1 |
| [−12,−9) | +7 | +7 | −1 |
| [−9,−6) | +7 | +7 | −1 |
| [−6,inf) | +8 | +7 | −2 |

Flat to one step across a 18 dB span, and the interior mode is +11 in six of seven strata for both
HIT and MISS. **A fixed convention residual is SNR-flat; a signal-dependent effect scales.** This
is the identical signature M3 used to identify the first anchor confound, and it points the same
way. Combined with S2 ≈ 0 (HIT and MISS indistinguishable), the residual is a property of how the
anchor is constructed, not of whether the signal decoded.

---

## 3. My fault, named exactly — and it is the third occurrence

At the M2 ruling I wrote, of my own gate:

> *"THE FAULT QA DID NOT NAME AND THE WORSE ONE: `is_edge_winner` is an OR ACROSS TWO AXES AND
> BOTH SIGNS, collapsing pulled-early/late/up/down into one scalar — structurally incapable of
> seeing a 6.5:1 late-vs-early asymmetry, and I specced it sign-blind AFTER my own M1 ruling had
> already found a one-sided asymmetry."*

**I then specced M4's ROW 0c and M4's primary statistic sign-blind.**

| # | Round | Statistic | Sign-blind because | What it could not see |
|---|---|---|---|---|
| 1 | M2 | `is_edge_winner` | OR over both axes, both signs | a 6.5:1 late-vs-early asymmetry |
| 2 | M4 | ROW 0c railed fraction | `\|coarse_dt_samp\| == 12` | a **242:1** one-sided rail |
| 3 | M4 | ROW 1/2 primary `rho_conc` | rank-biserial on `\|coarse_dt_samp\|` | a monotone ramp vs. a flat distribution |

Occurrence 3 is the expensive one: it is the *primary*, not a ROW 0, and it is the reason a
51,586-row run at full population cannot answer its own question.

**On ROW 0c specifically, and I am not moving a threshold.** ROW 0c's own stated rationale in my
spec is a one-sided phenomenon — *"HIT railing censors the concentrated end and hides a working
refiner."* The statistic I implemented is two-sided. Sign-aware, against the correct **one-sided**
uniform floor of 4.0% (1/25, not 8.0%):

| Arm | at +12 | × one-sided floor | at −12 | ratio |
|---|---|---|---|---|
| HIT | 24.36% | **6.09×** | 0.10% | **242:1** |
| MISS | 20.66% | 5.16× | 1.95% | 10.6:1 |
| NULL | 7.20% | 1.80× | 9.53% | 0.8:1 |
| CONTROL | 0.00% | 0.00× | 0.00% | — |

The row's *threshold* did not fire. The condition the row exists to detect is present by a margin
no sign-aware bar would have missed. **But this ruling does not rest on ROW 0c** — §2's shape
evidence stands on its own, and I am flagging the ROW 0c defect as a lesson, not using it as the
mechanism of the ruling. That distinction matters: re-reading a ROW 0 against its observed value
is precisely what my own spec forbade.

### 3.1 The test that keeps this honest, and the way it cuts

I predicted ROW 1 at 55%. I am now withholding a ROW 2. That is the exact shape of motivated
reasoning and it must be answered, not asserted past.

The answer is that **the censoring made ROW 1 nearly unreachable regardless of the truth.** HIT
railing at +12 *inflates* HIT's `|d|`, which drives `rho_conc` **down**. With 24% of HIT rows on
the far rail, `rho_conc ≥ 0.30` was close to geometrically impossible whatever the refiner can
actually do. **A gate that can only land in one row independently of the fact it is asking about
is not a gate.** That is the ground of this ruling, and it would have voided a ROW 1 just as
surely — a ROW 1 obtained under 24% one-sided censoring would have been equally uninterpretable,
and I would have had to withhold my own preferred verdict on the same reasoning.

🔴 **This is not an HK-025 failure QA missed.** The classification QA re-derived was correct at
classification time: the degeneracy is a property of the *data's censoring*, which nobody could
see before the run. QA ran the gate in strict order, reported the fired row, refused to soften it,
computed and withheld S1/S2 exactly as required, escalated §5.5 rather than choosing a leg, and
surfaced §4 — the finding that unlocked this ruling — from data the spec never asked it to
examine. **M4's execution is accepted without reservation. The defect is entirely in my
specification of it.**

---

## 4. Two subsidiary rulings, and one correction to the report

### 4.1 The §5.5 replication escalation is DISCHARGED

`rho_conc = nan` on the replication leg has the mechanical cause QA identified: `pooled_contrast`'s
hardcoded `STRATUM_MIN_N = 200` excludes all seven strata when the leg carries 100/stratum/arm.
That is the spec's own power floor applied to a leg the spec itself declared underpowered and
non-gating. **Not a wiring defect, not a contradiction of the primary — discharged.** QA was right
to escalate rather than choose, and right to state both readings. It is moot in any case: the
primary it would replicate is void.

### 4.2 ROW 0d's NULL slope is NOT evidence for the buffer attractor — the sign is wrong

The report reads the measured slope as *"consistent with (not proof of) the buffer-origin
attractor mechanism."* **It is not consistent with it. It is the wrong sign.**

If NULL were pulled toward a fixed absolute buffer time `t_a`, the chosen displacement satisfies
`d ≈ t_a − A`, so `slope(d ~ base_dt_s)` is **negative** — for a full lock, −1 step per step, i.e.
**−200 steps/s** in M4's units. M4 measured **+1.0177 steps/s, p = 4×10⁻⁶**. Positive, and
~200× too small even to be an attenuated version of it. The magnitude is uninterpretable anyway
(NULL is 16.7% two-sided censored, which attenuates any slope toward zero), but censoring does not
flip a sign.

**M4's condition-2 measurement is the best-powered test of the §3 buffer-attractor hypothesis run
so far, and it does not support it.** Mark §3 of the M4 spec as **not supported at row level by
M4**; the profile-level evidence in M3 stands unchanged and is untouched by this. Do not carry the
attractor forward as the explanation of NULL's behaviour.

### 4.3 A better explanation of NULL's skew, from source — and it is in `src/`

`sync_refiner.c:345-353`:

```c
for (int d = -REFINE_COARSE_TIME_HALF_SAMPLES; d <= REFINE_COARSE_TIME_HALF_SAMPLES; d++)
    for (int k = 0; k <= n_freq_steps; k++) {
        float mag = costas_coherent_sum(..., base_origin1 + (float)d, df, sps1);
        if (mag > best_score_ab) { best_score_ab = mag; best_dt_samp = d; best_df = df; }
    }
```

`d` ascends from −12 and the comparison is strict `>`. **On an exact tie the most negative `d`
wins.** M2 already established that this score plateaus bit-identically across nearby anchors. The
refiner's *internal* coarse scan steps 5 ms — far finer than the 0.05 s anchor grid on which QA's
M3 tie-fix operated — so internal ties are correspondingly more likely, and **QA's M3 fix could
never have touched this, because it is in C.**

Predicted signature: on a flat score surface, mass accumulates at the low end and decays upward.
NULL measured: −12 **9.53%**, −11 5.80%, −10 5.18%, −9 4.69%, −8 4.34%, decaying to ~3.0% mid-grid.
**That is the signature.** And its strength orders with how flat the surface is — NULL 9.53% ≫
MISS 1.95% ≫ HIT 0.10%.

This is a **hypothesis consistent with source and shape, not a measurement** — the ordering is
confounded with "HIT is pulled positive", and counting ties needs instrumentation inside the C.
But it is a better-grounded account of NULL's persistent negative skew — including **both** exact
ROW 0d bar landings the programme has now flagged as suspicious — than a buffer attractor whose
sign is wrong. 🛑 **It is not a licence to change `sync_refiner.c`.** It is recorded here, it is
non-gating in M5, and M5 reads it out for free (§5.6).

---

## 5. M5 — locate the true origin by ZERO-CROSSING, not by score-argmax

**The question:** does the refiner's coarse time estimate *track* the true position of a real
signal — and if so, where is that position?

This replaces `rho_conc` with a statistic that is sign-aware, censoring-diagnosable, and **does
not use `score` at all**, which is what makes it immune to the sweep-selection artefact that void
M3's argmax (M4 spec §4).

### 5.1 The statistic, and why it settles both questions at once

For a swept anchor offset `u`, let `m(u)` = median **signed** `coarse_dt_samp` over an arm.

If the refiner locates a real signal at true buffer-relative position `T`, then
`d = clip(T − A(u), ±12)` where `A(u) = anchor_dt_s + 0.45 + u`. So in the unclipped region:

> **`m(u)` falls with slope exactly −1 step per 5 ms of `u`, and crosses zero at `u = u*`, where
> `u*` is the residual anchor error.**

If the refiner does **not** locate, `d` is independent of `u` and **the slope is 0.**

**`slope_track` — the OLS slope of `m(u)` on `u`, in steps per 5 ms step of `u`, fitted over the
unclipped window `|m(u)| ≤ 8` — is M5's primary statistic.** Its null is 0 (no tracking) and its
"instrument works" value is −1.0 (perfect tracking). Both ends are physically pinned, which is
what M4's `rho_conc` lacked.

**Sign convention, to be asserted as a unit test before arming, exactly as in M4 §5.3:**

> `slope_track == −1.0` on synthetic input where every row returns `d = T − A(u)` unclipped for a
> fixed `T`. `slope_track == 0.0` on synthetic input where `d` is drawn independently of `u`.
> **QA must assert both ends and must not arm until it passes.** A sign error inverts the verdict.

**The zero-crossing `u*` is the secondary**, reported with CI, and it is what the following round
would use as the anchor. 🛑 **`u*` is not readable unless ROW 1 fires** — a crossing estimated from
a distribution that does not track is meaningless (S1/S2's discipline in M4, same reasoning).

### 5.2 Grid — and why it brackets the disputed range symmetrically

`u ∈ [−0.10, +0.40] s`, step **0.01 s (2 coarse steps)** ⇒ **51 anchors per row.**

Absolute anchor swept = `anchor_dt_s + 0.35 … +0.85` s. This brackets **M3's measured +0.45** and
**my ALL.TXT-derived +0.60…+0.70 prediction** with margin on both sides. The step is 2 coarse
samples, well inside the ±12 aperture, so the crossing cannot be stepped over.

⚠️ **I am an interested party in that range and I am saying so.** At M3 my +0.60…+0.70 prediction
was scored a MISS against a measured +0.45, and §2 now suggests the residual runs in the direction
of my prediction. **That is not a vindication and must not be recorded as one** — M3's +0.45 is a
score-argmax, which my own M4 spec §4 showed to be selection-biased, and §2 shows only that the
residual is positive and beyond +60 ms, not what it is. The grid is set to *contain both* and let
a measurement decide. If `u*` lands nearer +0.45 than +0.65, that is the answer.

### 5.3 Population

Stratified subsample of the **same M1 manifest**, no reseeding: **300 HIT + 300 NULL per stratum ×
7 strata = 4,200 rows.** MISS is **not** run — S2 ≈ 0 already established HIT and MISS are
positionally indistinguishable, so MISS buys nothing here and costs a third of the runtime.

Plus **M2's 400-row positive control verbatim**, swept identically. 🔴 **The control's own anchor
stays at `dt_offset = 0` before the sweep is applied** — i.e. control anchor = `base_dt_s + u`, no
`+0.45`. It is correctly anchored by construction (M4 §5.2) and its crossing must land at
`u* ≈ 0`. **This is now a real validation, not plumbing-only:** the control has a *known* true
position, so its measured `slope_track` and its `u*` together test the statistic end-to-end. That
is more than the control could do in M2/M3/M4, and it is the HK-022 guard for M5.

**Cost:** 4,600 rows × 51 anchors = 234,600 calls × 20.4 ms = **~80 min.** Cap **3 h**. If
breached, subsample rows within stratum; 🛑 **never trim the anchor grid** — the grid is the
instrument.

### 5.4 The gate — pre-registered, mechanical, strict order

**ROW 0a — harness invalid.** Fires if any `rc != 0`, or the control's pre-sweep offset is not 0,
or the DLL SHA256 does not assert. ⇒ no verdict, QA fixes and re-runs.

**ROW 0b — underpowered.** Fires if fewer than 4 strata have ≥200 rows in both HIT and NULL. ⇒
instrument failure, not a null.

**ROW 0c — the crossing is not interior.** Fires if HIT's `m(u)` does **not** cross zero strictly
inside the grid — i.e. `m(u)` has the same sign at both `u = −0.10` and `u = +0.40`. ⇒ the residual
is outside the swept range. **No verdict, escalate.** 🛑 **Do not extend the grid and re-read** —
that is a new pre-registration. This row is the HK-026 guard: it is the mechanism by which the
sweep declares its own blind spot rather than bounding it.

**ROW 0d — the control fails.** Fires if the control's `u*` is outside ±0.02 s, **or** the
control's `slope_track` is outside [−1.3, −0.7]. ⇒ the statistic does not recover a *known* truth,
so it cannot adjudicate an unknown one. **No verdict, escalate.**
🔴 *Bars derived from grid geometry: ±0.02 s is two grid steps; ±0.3 on the slope is 30% of a
physically pinned value of exactly −1. I have not computed either quantity. If ROW 0d fires on a
bar I set blind that is a legitimate outcome and QA must not soften, re-centre, or re-derive it.*

**ROW 1 — the refiner tracks real signals.** Fires if HIT `slope_track ≤ −0.70` **AND** its 95% CI
excludes −0.30. ⇒ **the refiner carries genuine positional information on real signals.** M4's
ROW 2 consequence is formally set aside. `u*` becomes readable and is the corrected anchor. The
standing prohibition on R0/R1/R1b's ~1.1 ms / 0.5 Hz figures **does not lift here** — tracking is
necessary but not sufficient for an accuracy claim; the expiry condition becomes a concentration
measurement *at* `u*`, which is the round after this one. **R2 stays unscoped.**

**ROW 2 — the refiner does not track.** Fires if `|slope_track| ≤ 0.20` **AND** its 95% CI
excludes −0.50. ⇒ the refiner carries **no** positional information on real signals, at any anchor
in a ±0.25 s bracket around the disputed range. **H2 is then established, not merely leading; R2
as framed is dead; the prohibition becomes PERMANENT; the next round is instrument
re-validation.** This is the row that would have made M4's consequence correct, asked with a
statistic that can actually distinguish it.

**ROW 3 — partial.** Anything else ⇒ escalate with `m(u)` tabulated at all 51 anchors and both
arms' full histograms at the three anchors nearest the crossing. 🛑 **Do not average to a verdict.**

**NULL is not a gate row here** — it has no true position to track, so its `slope_track` is
expected ≈ 0 and is reported as a reference curve, not a bar. 🛑 **Do not construct a HIT-vs-NULL
contrast on `slope_track` and read it as a verdict** — that is a different statistic and it earns
its own pre-registration.

### 5.5 Censoring must be reported at every anchor, not just at the crossing

At each `u`, report per arm: median signed `d`, the **one-sided** rail fractions at +12 and −12
separately (never `|d| == 12`), and the fraction with `|d| ≤ 3`. **The slope is fitted only over
anchors where HIT's combined rail fraction is < 25%** — stated in advance, because a slope fitted
through censored points is attenuated toward zero, which biases toward ROW 2. If fewer than 5
anchors qualify, that is **ROW 0c**.

🔴 **No statistic in M5 may be computed on `|coarse_dt_samp|`.** Signed, always. That is the
lesson of §3 written into the method.

### 5.6 Free read-outs — non-gating, report only

- **`u*` for MISS**, if MISS rows are cheap to add at the crossing anchors only. Non-gating.
- **The §4.3 tie-break signature:** at each anchor report NULL's count at −12 versus +12. If the
  ascending-scan-plus-strict-`>` account is right, NULL's −12 excess is roughly invariant to `u`
  while +12 is not. Non-gating, and it cannot be resolved without instrumenting the C — do not
  try.
- **`fine_dt_samp`** recorded, 🛑 still prohibited as a positional metric (M4 spec §2.1, unchanged).

### 5.7 HK-025 classification — QA re-derives independently and may refuse

| Row | If it fires, still an estimate of what the gate names? | Class | Both branches |
|---|---|---|---|
| 0a | **No** — a miswired harness measures nothing | VALIDITY | fires ⇒ no verdict, fix + re-run; else ⇒ 0b. Different ✅ |
| 0b | **No** — an underpowered stratum is instrument failure, not a null | VALIDITY | fires ⇒ no verdict; else ⇒ 0c. Different ✅ |
| 0c | **No** — a slope fitted where no crossing exists estimates nothing | VALIDITY | fires ⇒ escalate, no verdict; else ⇒ 0d. Different ✅ |
| 0d | **No** — a statistic that cannot recover known truth cannot adjudicate unknown truth | VALIDITY | fires ⇒ escalate, no verdict; else ⇒ ROW 1/2/3. Different ✅ |

All four VALIDITY, none DIAGNOSTIC, none merely changes printed text (HK-021(k)).
🔴 **QA runs this independently, including against this paragraph, and may refuse under HK-025
without my agreement and without escalation.**

### 5.8 HK-026 self-check

**Is `slope_track` derived from the instrument's own blind spot?** No. It is a *slope against a
swept parameter*, with both ends physically pinned by geometry (−1 = tracking, 0 = not) rather
than by anything the instrument reports. The crossing `u*` **is** derived from the instrument's
output — which is why it is (a) gated behind ROW 1, (b) required to be strictly interior to the
grid by ROW 0c, and (c) validated against a control with known truth by ROW 0d. The instrument
declares its own blind spot via ROW 0c instead of being asked to bound it. ✅

**Is the +0.35…+0.85 bracket an HK-026 violation?** It is set from two *independent* sources — two
full decoders' `ALL.TXT` DT gap, and the 2026-07-25 2×2 decoder×audio measurement — plus M3's
correlator argmax, and it is 2.5× wider than the gap between them. The response is not flat where
the boundary sits, and ROW 0c fires if it is. ✅

### 5.9 Free replication — and I have not looked

M3 recorded all 49 calls per row including `coarse_dt_samp`, so **`m(u)` is already computable from
committed `m3_results.json` over `dt_offset ∈ [−1.20, +1.20]`** at 0.05 s resolution. That is a
coarse-grid version of M5's primary, free, on 1,400 rows.

QA computes it and reports it as a **non-gating** replication (its 0.05 s step is 10 coarse steps,
so it resolves the crossing poorly and will have few unclipped anchors — it is a sanity check on
sign and rough location, nothing more). **Different ROWs across the two legs ⇒ escalate, do not
choose** — and note M4's §5.5 precedent: a mechanical power-floor mismatch is a discharge, not a
contradiction; check for that class of cause before escalating.

🔴 **I have deliberately not computed `m(u)` on M3's data, on either arm.** The gate above was
written before anyone evaluated it and must stay that way until QA runs it. §2's diagnostic reads
only M4's *fixed-anchor* histogram, which contains no `u` axis and therefore no slope.

---

## 6. Predictions — 🛑 NOTHING GATES ON THESE

| Prediction | Credence | Class + running score |
|---|---|---|
| ROW 1 | **~80%** | categorical, 5/8 |
| ROW 3 | ~12% | categorical |
| ROW 2 | ~5% | categorical |
| ROW 0c (crossing not interior) | ~3% | categorical |
| `u*` lands in 0.55–0.70 s absolute | — | range, **8/16 — my weakest class** |
| HIT `slope_track` in [−1.05, −0.80] | — | range |
| Control `u*` within ±0.01 s | ~85% | directional, 2.5/4.5 |

**Why I am at 80% and not higher.** For: HIT's 240× monotone gradient against a flat NULL is very
hard to produce without positional information, and it is SNR-flat, which fits a convention
residual and not a capability failure. Against: I have never seen this refiner track a *real*
signal — every accuracy figure it has ever produced came from synthetic populations with offsets
injected *inside* its aperture, which is the whole substance of H2 — and a monotone ramp is also
what you would get from a broad, signal-linked score gradient that never resolves a peak at all.
**§2 shows the ramp is signal-linked; it does not show the refiner can resolve a peak.** ROW 1's
bar is deliberately set on the slope and not on the ramp for that reason.

**Calibration note, quoted where it belongs:** my directional calls run **1.5/3.5** and my ranges
**8/15** — and at M4 my most confident directional call (HIT railed < 12%) missed by 2×. **No row
in §5.4 turns on any prediction above.**

---

## 7. Scope — what is prohibited in this round

- 🛑 No `src/` change. No Developer session. No ABI bump. No new DLL, no `FT8_SHIM_VERSION` bump.
  No capture run. **HK-011 not engaged.** Pin and assert SHA256 `04cedc59…` / `20260041`, as M1–M4.
- 🛑 **No widening of the coarse aperture.** §4.3 identifies a tie-break in `sync_refiner.c` and §2
  shows the aperture is too narrow for the current anchor — **neither licenses a source edit.**
  Sweeping the anchor moves the aperture and is pure harness work; that is the whole design.
- 🛑 **No statistic on `|coarse_dt_samp|`** (§5.5). Signed, always.
- 🛑 `fine_dt_samp` prohibited as a positional metric.
- 🛑 No re-read of M1/M2/M3/M4's closed gates with a better metric. §2 is a **validity diagnostic on
  M4's precondition**, not a re-read of its ROW 1/2/3 branch, and no HIT-vs-NULL contrast on a
  re-centred statistic has been computed by anyone.
- 🛑 **R2 stays unscoped, unproposed and unestimated.** ROW 1 does **not** scope it (§5.4).
- 🛑 **The standing prohibition on R0/R1/R1b's ~1.1 ms / 0.5 Hz figures for real signals REMAINS,
  and M4 does not make it permanent** — ROW 2 was the trigger for permanence and its consequence
  is withheld. The expiry condition is now a concentration measurement at `u*`, one round beyond
  M5.
- **A2** (AC-4 needs an explicit ROW 0) and **A3** (re-run D3 against the per-stage exports,
  emitting slope + SE + p) remain open and **must not become a round**. A1 is done.
- HK-014: I commit this locally and stop. I do not push and do not ask.

## 8. What QA delivers

1. `qa/rr-study/m5-zero-crossing/` — harness, committed, with the §5.1 sign unit test and the
   §5.3 control-anchor assertion in code.
2. `results/m5_results.json`, `m5_gate_report.json`, `harness_run.log`, `m5_evaluate.log`.
3. A dated report `qa/rr-study/<UTC>-qa-to-architect-m5-results.md` (HK-017: filename and byline
   mechanically derived and agreeing), containing the gate in **strict order**, `m(u)` tabulated at
   all 51 anchors for HIT / NULL / CONTROL, the per-anchor one-sided rail fractions of §5.5, the
   fitted window and which anchors it excluded and why, `u*` with CI **or an explicit statement
   that it is withheld**, and the §5.9 replication leg.
4. The board updated in the **same edit** as the result (HK-024).

**QA does not author the next spec (HK-015). QA may refuse this one under HK-025 (§5.7).**
