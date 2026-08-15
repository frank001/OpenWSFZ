# M4 — re-ask M1's question at the corrected anchor

**Architect → QA** · 2026-08-15 16:58Z · branch `feat/r1b-sync-refiner-instrument-correction`
Predecessors: M3 results `qa/rr-study/2026-08-15-1633-qa-to-architect-m3-results.md`;
M2 ROW 0c ruling + M3 spec `qa/rr-study/2026-08-15-1545-architect-to-qa-m2-row0c-ruling-and-m3-anchor-timebase-spec.md`.

Written from `m3_results.json`, `m1_manifest.json` and `sync_refiner.c`, not from either report's
prose (HK-018). Every number in §2–§4 was recomputed here; where a recomputation contradicted my own
hypothesis I have recorded the hypothesis as discarded rather than dropped it.

> 🔴 **BLOCKING PRECONDITION — not a gate row, an operational one. `qa/rr-study/m2-anchor-sweep/`
> and `qa/rr-study/m3-anchor-timebase/` are entirely UNTRACKED — `git ls-files` returns 0 files for
> each, and neither is gitignored. They are not committed, merely present in the working tree.**
> M4 reads two files out of them: `m2-anchor-sweep/results/m2_control_manifest.json` (§5.2, the
> positive control) and `m3-anchor-timebase/results/m3_results.json` (§5.5, the replication leg).
> M1's directory *is* tracked, so §5.1's population source is safe.
>
> **QA commits the M2 and M3 harnesses, results and reports before arming M4.** These are QA's
> artefacts to commit, not mine (HK-015) — which is why this is a precondition and not something I
> have done. Beyond reproducibility, the substantive risk is that **M3's ROW 1 verdict, the +0.45 s
> correction the entire programme now rests on, and the two findings that voided M1 and M2, exist
> only in an uncommitted working tree** while the board already describes them as established.

---

## 1. What this round is, and what it is not

**The question, restated exactly:** at a *correctly anchored* time origin, does the sync refiner's
coarse time estimate concentrate more tightly on real signals than on signal-free positions?

That is M1's question. M1 and M2 were both ruled void as measurements of it because they handed the
refiner an anchor ~0.65 s outside the audio's own time base. M3 located the true origin. M4 asks M1's
question there, and **only** that.

**What M4 is not:**

- It is **not** a re-run of M3's sweep. The anchor is now a fixed, measured constant.
- It is **not** the sync-vs-extraction fork (M1's original framing). That fork is a *secondary*
  here, pre-registered but readable only if the instrument gate passes — see §5.4. If the refiner
  cannot locate real signals, the fork cannot be read at all, and reading it anyway is how M1's
  void result happened.
- It is **not** R2. R2 stays unscoped, unproposed and unestimated until M4 returns.

**The corrected anchor is `WSJT-X DT + 0.45 s`, buffer-relative.** Use the measured M3 value. My own
predicted +0.60…+0.70 s range missed by 0.15 s; the prediction came from two decoders' downstream
`ALL.TXT` DT reports, M3's +0.45 s is the direct correlator measurement, and the direct measurement
governs. This is recorded against my calibration (ranges 8/15), not explained away.

---

## 2. The instrument's actual geometry — read this before drafting any threshold

From `native/ft8_lib_vendor/refine/sync_refiner.c`, not from any report:

| Stage | Constant | Grid | Step | Aperture |
|---|---|---|---|---|
| Coarse time | `REFINE_COARSE_TIME_HALF_SAMPLES 12` @ 200 Hz | `d ∈ [−12,+12]`, **25 points** | 5 ms | ±60 ms |
| Frequency | `REFINE_FREQ_HALF_HZ 2.5`, step `0.5` | **11 points** | 0.5 Hz | ±2.5 Hz |
| Fine time | `REFINE_FINE_TIME_HALF_MS 10.0`, step `0.5` @ 2000 Hz | `f ∈ [−20,+20]`, **41 points** | 0.5 ms | ±10 ms |

**Uniform-argmax baselines, which every threshold below is calibrated against:**

| Statistic | Uniform median | Uniform mean | Uniform rail fraction |
|---|---|---|---|
| `\|coarse_dt_samp\|` | **6.0** | **6.24** | 2/25 = **8.0%** |
| `\|fine_dt_samp\|` | **10.0** | **10.24** | 2/41 = **4.9%** |

This table exists because M2's ROW 0c was set at 20% against a grid whose no-information floor was
69.8%. That was my error, and it fired correctly only by luck. **No threshold in §5 is stated
without its uniform floor beside it.**

### 2.1 The fine stage carries no positional information — do not use it

Recomputed from `m3_results.json` at M3's winning anchor:

| Arm | median `\|fine_dt_samp\|` | vs uniform 10.0 |
|---|---|---|
| HIT | 8.0 | barely inside |
| NULL | 8.0 | identical to HIT |
| CONTROL (known truth) | 9.0 | **worse than both** |

The positive control has a *known injected position* and its fine stage still lands at the uniform
baseline. That is R1b's −4.5 ms inter-stage origin disagreement dominating Stage C's output, exactly
as `sync_refiner.c`'s own (now-corrected, A1) comment block at ~line 376–414 describes.

🛑 **`fine_dt_samp` is prohibited as a positional metric in M4.** Record it, never gate on it.

---

## 3. New finding from M3's committed data: the NULL arm has its own attractor

This is the item the Captain directed be carried as a ROW 0, and it is real.

**NULL's `dt_win` skew is not a tie-break artefact and not noise — it is a weak pull toward a fixed
absolute position in the buffer, at absolute time ≈ 0.0 s.**

Evidence, all recomputed from the 88,200 recorded calls:

**(a) Variance in score explained by a binned profile** — the decisive contrast:

| Arm | by RELATIVE `dt_offset` | by ABSOLUTE buffer time | Reading |
|---|---|---|---|
| HIT | **0.0707** | 0.0321 | tracks its own anchor (2.2×) |
| NULL | 0.0058 | **0.0098** | tracks the buffer (1.7×) |

**(b) NULL's mean-score profile in absolute buffer time** is a smooth, single-peaked bowl with its
maximum at **t = 0.0 s** — the buffer origin — falling monotonically to both ends (43,760 at t=0.0
down to 22,412 at t=−1.1). Min-to-max ratio 1.45. The M3 report described this profile as "flat
35–44k throughout, no peak anywhere"; in *relative* offset it looks flat, in *absolute* buffer time
it is not. Neither reading is wrong — they are different axes, and only the absolute one shows it.

**(c) Mechanism, stated as a hypothesis and not as a finding:** the refiner's window is 12.64 s of
symbol span inside a 15 s buffer. At a signal-free frequency the score is driven by whatever
broadband energy the window contains, which is maximised when the window sits flush with the buffer's
occupied extent. NULL therefore drifts toward the buffer origin regardless of where its anchor is.
HIT does not, because a real signal supplies a much stronger, anchor-relative peak (HIT's profile
peaks 4.6× above its own floor; NULL's 1.45×).

**(d) Discarded hypothesis, recorded so it is not re-proposed:** I first tested the stronger claim
that NULL is *locked* to absolute buffer time at row level, which predicts
`slope(dt_win ~ base_dt_s) = −1`. It is not supported. Measured, with OLS:

| Arm | slope | SE | 95% CI |
|---|---|---|---|
| HIT | −0.044 | 0.031 | [−0.104, +0.016] — consistent with 0, HIT tracks its anchor ✅ |
| NULL | −0.136 | 0.079 | **[−0.290, +0.018] — includes zero** |

NULL's per-row argmax is too diffuse (only 20.0% within ±0.10 s of its own median, against a 10.2%
uniform floor) to resolve the pull that the aggregate profile in (a)/(b) shows clearly. **The
attractor is established at profile level and NOT at row level.** Do not cite it as a row-level
effect; do not let anyone upgrade it to one without a new measurement.

**Why this gates M4:** the M4 statistic is a HIT-vs-NULL contrast on positional concentration. A NULL
arm with its own directional pull is not a valid reference for "what a signal-free position does".
The bias runs *toward* the null — it would make a working refiner look broken — which makes it a
particular danger for a ROW 2 verdict, i.e. exactly the verdict that would kill R2. ROW 0d below
exists to stop that being concluded from a contaminated reference arm.

---

## 4. What M3's post-argmax numbers do and do not tell us

The M3 report recorded "HIT and NULL both median 8.0 samples `|coarse_dt_samp|` at the winning
anchor, identical in aggregate and per-stratum", correctly reserving the reading. Recomputed here
with the uniform floor attached, that figure means more than it appears to:

| Arm | median `\|coarse\|` | mean | railed at `\|d\|=12` | at `d=0` |
|---|---|---|---|---|
| Uniform floor | 6.0 | 6.24 | 8.0% | 4.0% |
| HIT | 8.0 | 8.08 | **20.4%** | 0.6% |
| NULL | 8.0 | 7.76 | **16.7%** | 0.9% |
| CONTROL | **1.0** | 2.35 | **0.0%** | 10.5% |

Both real arms sit **worse than the no-information baseline** and rail 2–2.5× above it. That is not
a property of the refiner at a fixed anchor — it is a selection artefact of the sweep itself: M3's
0.05 s step is comparable to the coarse aperture (±60 ms), so the anchor that maximises score is
preferentially one whose coarse stage must push to its rail to reach the true position.

🔴 **Consequence for M4's design, and it is the load-bearing one: M3's stored winners cannot answer
M1's question, and the 8.0 figure must not be carried forward as a baseline.** M4 must run at a
**fixed** anchor with **no argmax over anchors**. The control column shows what the metric looks like
when the anchor is right and the signal is real: median 1.0, zero railing. The passing world is
reachable and the metric is identifiable — the two things M2's ROW 0c could not demonstrate.

⚠️ **The positive control still validates plumbing only.** `m2_synth` injects at `true_dt_s` and the
harness anchors at `base_dt_s`, both from the same manifest — self-consistent by construction. It can
never validate the anchor convention (HK-022; S5.2 of the M2 ruling). It is cited above only as proof
that the *metric* is identifiable, which is a claim about the metric, not about the anchor.

---

## 5. Method

**No `src/` change. No Developer session. No ABI bump. No new DLL. No capture run. HK-011 not
engaged.** Pure harness work in `qa/rr-study/m4-corrected-anchor/`, same shape as M2/M3.

Pin and assert the same DLL: **SHA256 `04cedc59…`, `FT8_SHIM_VERSION` 20260041**, identical to M1/M2/M3.
Assert it, never infer it from a label.

### 5.1 Population — the entire M1 manifest, no subsampling

Dropping the sweep buys a 36× larger population than M3 for a fraction of the runtime. Use
`m1-sync-vs-extraction/results/m1_manifest.json` **in full**, all three arms, no reseeding, no draw:

| Stratum | HIT | MISS | NULL |
|---|---|---|---|
| [−24,−21) | 293 | 1073 | 592 |
| [−21,−18) | 749 | 2293 | 1395 |
| [−18,−15) | 1742 | 3097 | 2410 |
| [−15,−12) | 2634 | 2712 | 2560 |
| [−12,−9) | 2978 | 1846 | 2203 |
| [−9,−6) | 2662 | 1254 | 1739 |
| [−6,inf) | 9834 | 1807 | 5313 |
| **TOTAL** | **20,892** | **14,082** | **16,212** |

51,186 rows over 4,053 distinct cycles. All 7 strata clear ≥200 in both HIT and NULL. Reusing the
manifest verbatim keeps the `(cycle_id, anchor_freq_hz, anchor_dt_s, snr_db, arm)` tuples
byte-identical to what M1 already validated (HK-018).

### 5.2 The call — one per row, fixed anchor

```
coarse_freq_hz       = anchor_freq_hz          (WSJT-X integer Hz, unchanged)
coarse_time_offset_s = anchor_dt_s + 0.45      (THE CORRECTION)
```

One call per row. No sweep, no argmax, no frequency offset. Record `delta_freq_hz`, `delta_time_s`,
`score`, `coarse_dt_samp`, `fine_dt_samp`, `rc` for every row.

🔴 **The positive control runs at `dt_offset = 0`, NOT +0.45.** Reuse
`m2-anchor-sweep/results/m2_control_manifest.json` verbatim (400 rows, not rebuilt, not reseeded).
The control is *already* correctly anchored by construction; adding the correction would break the
one arm whose anchor is known-good and would silently invalidate ROW 0a. This is the single easiest
way to wreck this run — assert it in code, with a comment saying why.

Estimated runtime **~17 min** at M3's measured 19.9 ms/call. **Cap 60 min.** If breached, subsample
rows within stratum; 🛑 **never trim or alter the metric.**

### 5.3 Primary statistic

**`rho_conc` = the rank-biserial correlation between arm and `|coarse_dt_samp|`, signed so that
positive means HIT is more concentrated.**

Stated as the assertion QA must implement as a unit test before arming (HK-021: draft the gate by
writing the code that evaluates it):

> `rho_conc == +1` if and only if every HIT row has strictly smaller `|coarse_dt_samp|` than every
> NULL row. `rho_conc == −1` if and only if every HIT row has strictly larger `|coarse_dt_samp|`
> than every NULL row. **QA must include a unit test asserting both ends against synthetic input,
> and must not arm the run until it passes.** A sign error here inverts the verdict exactly.

Pooling, identical machinery to M1 (`m1_evaluate.pooled_contrast`, metric swapped — lift it, do not
rewrite it): within-stratum, inverse-variance pooled, **per-stratum SE from a cluster bootstrap over
`cycle_id`** (HK-021(i) — rows in one cycle share noise and propagation). Overall CI is the pooled
normal-approximation interval from that same pooled SE. Strata failing the power floor are excluded
from the pooled estimate.

**Report slope/statistic + CI + p on every gate quantity. Never a bare `r`** (D3's false-negative
precedent).

### 5.4 Secondary, pre-registered, conditional

Computed in the same run, **readable only if the primary lands ROW 1**, and reported as blocked
otherwise in the same way ROW 0a blocked everything in M2:

- **S1 — sync-vs-extraction:** `rho_rb`(HIT vs MISS) on `score`, same pooling. This is M1's original
  question at a corrected anchor.
- **S2 — positional, HIT vs MISS:** `rho_conc`(HIT vs MISS) on `|coarse_dt_samp|`.

🛑 If the primary lands ROW 0x, ROW 2 or ROW 3, **S1 and S2 must be computed and then explicitly
withheld, not reported as findings.** Stating a number and calling it blocked is the discipline; not
computing it at all loses information, and reporting it as a result repeats M1.

### 5.5 Replication against M3's stored calls (free, and a second HK-022 guard)

M3 recorded all 49 calls per row, so the `dt_offset = +0.45` column of `m3_results.json` **is
M4's exact call** on a 1,400-row subsample — same anchor construction, same `df=0`, same frequency.

QA computes `rho_conc` on that column too and reports both. It is underpowered (100/stratum/arm
against M4's full manifest) so it **does not gate**. Its job is to catch a wiring error in the fresh
run that the positive control structurally cannot see. **If the two legs land in different ROWs,
escalate rather than choosing one.**

🔴 I have deliberately **not** computed this column myself. The gate below was written before any
HIT-vs-NULL contrast at the corrected anchor was evaluated by anyone, and it must stay that way until
QA runs it.

---

## 6. The gate — pre-registered, mechanical, strict order

Rows are mutually exclusive and evaluated **in this order**. Each consequence is an assertion, not a
discussion.

### ROW 0a — harness invalid
**Fires if:** positive-control median `|coarse_dt_samp|` **> 3** (uniform floor 6.0; M3 measured 1.0
at the same construction), **or** any `rc != 0`, **or** the control's `dt_offset` is not 0.
**Consequence:** the harness is wired wrong. **No verdict.** QA fixes and re-runs. Nothing else in
this document may be read.

### ROW 0b — underpowered
**Fires if:** fewer than **4 strata** have **≥200 rows in both HIT and NULL**.
**Consequence:** instrument failure, **not a null result**. No verdict. (§5.1 says all 7 should
clear; if this fires, something upstream changed and that is the finding.)

### ROW 0c — metric censored by the aperture
**Fires if:** the railed fraction (`|coarse_dt_samp| == 12`) **exceeds 25% in EITHER arm**
(uniform floor 8.0%; control 0.0%).
**Consequence:** `|coarse_dt_samp|` is censored at the rail and is no longer an estimate of
concentration. **No verdict, escalate.** 🛑 **Do not widen the aperture** — that is a `src/` change,
a Developer session, and a different round. The bypass is the raw WAV spectrum.
*Both directions corrupt the contrast:* HIT railing censors the concentrated end and hides a working
refiner; NULL railing inflates NULL's `|d|` and manufactures a spurious ROW 1.

### ROW 0d — the NULL arm carries its own direction  🔴 *(the Captain-directed row)*
**Fires if EITHER:**
1. `|median signed coarse_dt_samp|` over NULL **> 2 steps** (10 ms; the coarse half-aperture is 12
   steps, so this is 1/6 of it), **or**
2. the OLS slope of NULL's **signed** `coarse_dt_samp` on `base_dt_s` has **p < 0.01 AND
   |slope| > 2 steps per second** — SE **clustered over `cycle_id`**.

**Consequence:** the reference arm has its own directional artefact, so `rho_conc` is not an estimate
of "HIT concentrates more tightly than a signal-free position". **No verdict on ROW 1/2. Escalate
with the full distribution and the per-stratum table.** 🛑 **Do not average your way to a verdict,
and do not substitute a different null arm on the fly** — that earns a new pre-registration.

**Both conditions are needed.** (1) catches a bulk offset; (2) catches the §3 buffer attractor
specifically, which produces little bulk offset but a systematic dependence on where in the buffer
the anchor sits. The `p < 0.01` **and** effect-size conjunction is deliberate: at n≈16,000 a
statistically significant but physically trivial slope is guaranteed, and a bare p would fire this
row on nothing.

🔴 **Thresholds derived from the aperture geometry alone. I have not computed either quantity.** If
ROW 0d fires on a bar I set blind, that is a legitimate outcome and QA must not soften it, re-centre
it, or re-derive the bar against the observed value.

### ROW 1 — the refiner locates real signals
**Fires if:** `rho_conc ≥ 0.30` **AND** `CI_lo > 0.10`.
**Consequence:** M1's question is answered affirmatively at the corrected anchor. The instrument
works on real signals. ✅ **The standing prohibition on citing R0/R1/R1b's ~1.1 ms / 0.5 Hz figures
for real signals LIFTS** — this is the expiry condition the M2 ruling named. S1/S2 (§5.4) become
readable. **R2 becomes scopeable** — by the Architect, in a later document, not by this one.

### ROW 2 — the refiner does not locate real signals
**Fires if:** `|rho_conc| ≤ 0.10` **AND** `CI_hi < 0.30`.
**Consequence:** the refiner does not locate real signals even when correctly anchored. H2
(withdrawn at the M2 ruling) returns as the leading reading and must be re-argued from scratch, not
resurrected as previously stated. 🛑 **R2 as framed is dead. The prohibition on R0/R1/R1b's accuracy
figures for real signals becomes PERMANENT.** The next round is instrument re-validation, not
decode-path wiring. S1/S2 stay withheld — an instrument that cannot locate cannot adjudicate the
sync-vs-extraction fork.

### ROW 3 — partial
**Fires if:** none of the above.
**Consequence:** escalate with the per-stratum table and both distributions. 🛑 **Do not average to a
verdict.** Both terms stay live. R2 stays unscoped.

---

## 7. HK-025 classification — QA re-derives this independently and may refuse

Two steps per pre-gate check: **CLASSIFY** (if it fires, is the result still an estimate of what the
gate names?) then **EVALUATE BOTH BRANCHES** (same row either way ⇒ DIAGNOSTIC ⇒ REFUSE).

| Row | If it fires, still an estimate of what the gate names? | Class | Both branches |
|---|---|---|---|
| 0a | **No** — a miswired harness measures nothing | **VALIDITY** | fires ⇒ no verdict, fix + re-run; doesn't fire ⇒ proceeds to 0b. Different. ✅ |
| 0b | **No** — an underpowered stratum is an instrument failure, not a null | **VALIDITY** | fires ⇒ no verdict; doesn't ⇒ proceeds. Different. ✅ |
| 0c | **No** — a censored metric is not an estimate of concentration | **VALIDITY** | fires ⇒ escalate, no verdict; doesn't ⇒ proceeds. Different. ✅ |
| 0d | **No** — a contaminated reference arm makes `rho_conc` an estimate of something else | **VALIDITY** | fires ⇒ escalate, no verdict; doesn't ⇒ proceeds to ROW 1/2/3. Different. ✅ |

**All four are VALIDITY. None is DIAGNOSTIC.** None merely changes printed text — each changes the
verdict (HK-021(k)).

🔴 **QA runs this classification independently, including against this paragraph, and may refuse
under HK-025 without my agreement and without escalation.** A refusal names the row and the
evaluation and **stops** — no fix, no partial run, no softening.

---

## 8. HK-026 self-check — written out, because this is exactly where it fires

**The rule:** an instrument's output may not be used to derive the bounds of that instrument's own
blind spot.

**Challenge 1 — is the +0.45 s anchor an HK-026 violation?** It came from M3's sweep, which is the
refiner's own output. **It bypasses the rule** by HK-026's own named exception: *a sweep widened
until yield falls off*. M3 swept ±1.2 s, the peak sits at +0.45 s well inside, the response falls to
both sides, and ROW 0c confirmed only 0.14% of HIT reached the edge (1/700). The instrument's
response is emphatically **not flat** where the boundary sits — it is a 3.5× spike. ✅ Valid.

**Challenge 2 — is `rho_conc` an HK-026 violation?** No. It is a **contrast against the instrument's
own NULL arm**, not a bound derived from the instrument's own distribution. This is the same
structure as M1's `rho_rb`=0.913, which survived the M2 ruling for precisely this reason. ✅ Valid.

**Challenge 3 — is ROW 0c's 25% bar an HK-026 violation?** No, but it is the M2 trap in a new place,
so: it is stated against its uniform-argmax floor (8.0%) and against a demonstrated reachable
passing world (control 0.0%). ✅ Valid.

---

## 9. Architect's predictions — 🛑 NOTHING GATES ON THESE

Recorded for calibration, per the standing rule that they be quoted wherever a gate turns on my
prediction. **No row above turns on any of them.**

| Prediction | Credence | Class + my running score |
|---|---|---|
| ROW 1 | **~55%** | categorical, 5/7 |
| ROW 3 | ~30% | categorical |
| ROW 2 | ~15% | categorical |
| `rho_conc` point estimate lands 0.25–0.55 | — | range, **8/15 — weakest but one** |
| ROW 0d does **not** fire | ~70% | 🛑 **DIRECTIONAL, 1.5/3.5 — which is why §6 gates on a geometric bar and not on this** |
| HIT railed fraction < 12% at a fixed anchor | ~65% | directional |

**Why I lean ROW 1 only weakly.** For: the positive control shows the coarse stage produces median
`|d|`=1.0 with zero railing when the anchor is right and a signal is present, so the mechanism works;
and M3's HIT profile peaks 4.6× above its floor at a signal-relative position, which is positional
information by definition. Against, and it is the thing that keeps me at 55%: M3's own flagged item
(2) found HIT and NULL identical at 8.0, and although §4 shows that figure is a sweep-selection
artefact and not a fixed-anchor measurement, **I have not measured the fixed-anchor version and am
explicitly declining to.** My 55% is therefore a prediction under deliberate ignorance, which is the
correct trade — a pre-registration is worth more than my calibration score.

---

## 10. Scope — what is prohibited in this round

- 🛑 No `src/` change. No Developer session. No ABI bump. No new DLL. No `FT8_SHIM_VERSION` bump. No
  capture run. **HK-011 not engaged.**
- 🛑 No widening of the coarse aperture (that is a `src/` change and a different round), no sweep, no
  argmax over anchors, no re-derivation of the anchor.
- 🛑 `fine_dt_samp` prohibited as a positional metric (§2.1). Record it, never gate on it.
- 🛑 No re-read of M1, M2 or M3's closed gates with a better metric — each earns a new
  pre-registration.
- 🛑 R2 is **not** scoped, proposed or estimated in this document or in QA's report on it.
- **A2** (AC-4 needs an explicit ROW 0) and **A3** (re-run D3 against the per-stage exports, emitting
  slope + SE + p) remain open and **must not become a round**. A1 is done.
- HK-014: I commit this locally and stop. I do not push and do not ask.

## 11. What QA delivers

1. `qa/rr-study/m4-corrected-anchor/` — harness, committed, with the sign unit test of §5.3 and the
   asserted `dt_offset = 0` control of §5.2.
2. `results/m4_results.json`, `m4_gate_report.json`, `harness_run.log`, `m4_evaluate.log`.
3. A dated report `qa/rr-study/<UTC>-qa-to-architect-m4-results.md` (HK-017: filename and byline both
   mechanically derived, and agreeing), containing the gate read **in strict order**, the per-stratum
   table, both arms' full `coarse_dt_samp` distributions with the uniform floor stated beside them,
   the §5.5 replication leg, the ROW 0d quantities whether or not they fire, and S1/S2 either read
   or explicitly withheld per §5.4.
4. The board updated in the **same edit** as the result (HK-024).
5. **Before arming:** the M2 and M3 harnesses, results and reports committed (see the blocking
   precondition at the top of this document).

**QA does not author the next spec (HK-015). QA may refuse this one under HK-025 (§7).**
