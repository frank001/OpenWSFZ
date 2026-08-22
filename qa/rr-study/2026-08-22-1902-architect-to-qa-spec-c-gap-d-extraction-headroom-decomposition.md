# Architect → QA — C-GAP-D: how much of D-001 is reachable by extraction quality at all?

**2026-08-22 19:02Z.** Pre-registration, HK-021. Population: existing ALL.TXT already on
disk. **No capture, no hardware, no `src`/`native` change, no live run.**

---

## 0. 🔴 MANDATORY DISCLOSURE — the Architect ran part of this analysis while drafting

This spec is **not** blind. Drafting it, I ran the 20m / `8080` leg through X1's own
population loader and computed the headline estimator. **The numbers I already saw are
printed in §6 in full, including the point estimate.** The bars in §5 were set knowing
them.

I am disclosing this rather than hiding it because the bars are set on **decision
relevance** — what value would change the project's course — and not on the observed
value, and you cannot judge whether I gamed them without seeing what I knew. If you judge
the bars post-hoc-contaminated, **say so before running** and I will re-derive them with
you. That challenge is legitimate and I will not treat it as obstruction.

What this changes about the arm's purpose: it is now **verification and generalisation**
(three bands, both legs, proper cluster inference, a null control) rather than discovery.
That is still worth running — a single-leg, single-band, unclustered point estimate is not
something this project acts on, and §6's numbers are exactly that.

---

## 1. The question, and why it comes before any further coherent-LLR work

D-001 is a ~42 pp recall deficit against WSJT-X. Route B2's remaining limb (coherent
multi-symbol LLR formation) is an **extraction-quality** treatment: at its theoretical
best, 3-symbol coherent combining buys `10·log₁₀(3) ≈ 4.8 dB`, realistically 2–3 dB.

**Nobody has ever measured what 2–3 dB is worth against this gap.** Every arm since
2026-08-15 has argued about mechanism without once asking what the mechanism could pay if
it worked perfectly. This arm asks that, and it is cheap.

It also asks a second question the first one exposes: **the misses that no amount of dB
can reach.** If our recall at a given reference SNR is well below 1.0 even at strong
signal, extraction quality is not what is dropping them, and D-001 has a term nobody has
named.

---

## 2. Population — reused verbatim, not re-derived (HK-018)

`qa/cycleframer-alignment-replay/x1_cross_band_decomposition.py`: `build_band(name)` for
`name` in `{20m, 17m, 80m}`, **imported and called unmodified**. It already provides, per
row: `ts`, `snr` (the **reference's**, never ours), `freq_hz`, `density`, `matched8080`,
`matched8081`.

- **REF population, exclusions, and the reference-SNR convention are X1's** — `A ∩ B` on
  `(ts, message)`, hash-message and out-of-band exclusions applied. Do not re-derive them.
- 🔴 **SNR is always the reference's.** Ours carries a known band-dependent gain error
  (`DEFECT-snr-reported-gain-error.md`) whose headline slope is currently stale. X1 already
  handles this correctly and says so in its own header.
- 🔴 **Report both legs (`8080`, `8081`) separately. Never pool them.** They are separate
  instances and this project has established that single-instance runs differ.

### 2.1 HK-026 — whose blind spot, measured by whose instrument

The blind spot being bounded is **OpenWSFZ's** miss population. The stratifying axis is the
**reference's** SNR. Different instruments ⇒ the prohibition is satisfied by construction,
not by care.

⚠️ **The one real limitation, stated rather than buried:** the population is `A ∩ B`, two
WSJT-X instances agreeing, so its low-SNR tail is truncated by *the reference's* own
sensitivity. `R(s)` is unmeasurable below roughly −24 dB. **This arm therefore says nothing
about signals WSJT-X itself misses — which is correct, because D-001 is *defined* against
WSJT-X, but it means no result here may be restated as a claim about all weak signals on
the band.**

### 2.2 Readout quantum (HK-021(o))

The reference reports SNR as an **integer dB**. The quantum is **1 dB**. Every SNR-axis
statement in this spec resolves against that quantum, never against a bootstrap SE. All
lifts are integers so that `s + Δ` is exactly representable with no interpolation.

### 2.3 Independence (HK-021(i))

Unit of observation is a decode; **unit of independence is a cycle (`ts`)** — decodes in a
cycle share a propagation instant. **Cluster bootstrap by `ts`, 2000 draws, fixed seed
`20260822`, resampling whole cycles within each band independently.** A binomial SE is
forbidden. **Report CLUSTER counts alongside row counts everywhere.**

⚠️ Do **not** construct any sample with a raw `set` intersection over string keys — the
hash-randomised-iteration trap is live on this project. Sort at construction.

---

## 3. Part A — the extraction-quality ceiling

### 3.1 Estimator

Let `R(s)` be measured recall at integer reference SNR `s`, computed per (band, leg) over
rows with `n(s) >= 30`. For a hypothetical uniform extraction improvement of `Δ` dB:

```
G(Δ)     = Σ over misses of  max( 0, ( R(s+Δ) − R(s) ) / ( 1 − R(s) ) )    [decodes]
G(Δ)_pp  = 100 · G(Δ) / N_ref                                              [pp of the gap]
```

Rows where `R(s+Δ)` is undefined (insufficient `n`) or `R(s) >= 1.0` contribute 0. Report
for **Δ in {1, 2, 3, 6, 10} dB**, each with a cluster-bootstrapped CI95.

### 3.2 🔴 The load-bearing assumption, and which way it errs

`G(Δ)` assumes **a Δ dB improvement in our extraction is equivalent to a Δ dB stronger
signal** — that a miss at `s` starts behaving like the population at `s+Δ`.

**This is generous, not conservative, and that is the point.** The population at `s+Δ`
carries *all* our other failure modes too, so `G` credits the extraction improvement with
recoveries that extraction cannot actually cause. **`G(Δ)` is therefore an upper bound.** A
*low* `G` is decisive; a high `G` would not be.

State this in the report. Do not present `G` as a prediction of what a build would deliver.

---

## 4. Part B — the misses that are not decode failures

§6 shows something Part A cannot express: at high reference SNR a large share of "misses"
have **an OpenWSFZ decode in the same cycle at essentially the same frequency**. Those are
not signals we failed to decode. They are signals we decoded and whose *message text* did
not match — which scores as a miss under a `(ts, message)` join.

This matters because the board's own standing note says hash-table saturation **does not
discard decodes — it costs message TEXT only**. That failure mode produces exactly this
signature, it is SNR-independent, and no DSP work addresses it.

### 4.1 Statistic

For each miss: `near` = there exists an OpenWSFZ decode with the same `ts` and
`|f_ours − f_ref| <= 5 Hz`.

🔴 **A raw `near` rate is meaningless — crowded cycles produce coincidences.** The statistic
is **excess over a null**:

- **Null control:** re-run the identical proximity test with the miss's frequency replaced
  by `f' = 200 + ((f_ref − 200 + shift) mod 2800)`. Same cycle, same density, same detector,
  association destroyed.
- **Run two shifts, `shift` in `{700, 1300}` Hz**, and report both. If the two nulls differ
  by more than 0.02 in any SNR bin, the control is shift-sensitive — **report it and treat
  Part B as descriptive only.**
- `f_txt(s) = near_rate(s) − null_rate(s)`, per 5 dB SNR bin **and** pooled, each with a
  cluster-bootstrapped CI95.

### 4.2 Classification of the excess (descriptive, no gate)

For misses flagged `near` at reference SNR >= 0 dB, report the **distribution of mismatch
types** between the reference text and our co-located decode's text:

| type | definition |
|---|---|
| T1 | our text contains `<...>` (unresolved hash) where the reference's does not |
| T2 | identical callsigns, different report/suffix field (e.g. `RR73` vs `73`) |
| T3 | one or more callsign characters differ |
| T4 | anything else |

⚠️ **NFR-021: no real callsign may appear in the report, in any example, in any commit.**
Report counts and types only. If an illustration is needed, synthesise a Q-prefix one.

---

## 5. The gate

`G(3)_pp`, **20m leg `8080`**, is the primary. 20m is the largest population and the band
D-001 was characterised on; the other bands and the `8081` leg are reported and must be
consistent, but do not drive the verdict. Rows are **strictly ordered and mutually
exclusive; a boundary value falls to ROW 4.**

| row | condition | verdict and consequence, as an assertion |
|---|---|---|
| **0** | validity — §5.1 | any 0-row firing ⇒ **arm VOID**, no ROW 1/2/3 may be read |
| **1** | `CI_hi( G(3)_pp ) < 10.0` | **EXTRACTION IS NOT THE ROUTE.** Even a perfect 3 dB extraction gain closes under a quarter of D-001. Route B2's remaining limb **may not be described as a D-001 treatment** in any subsequent proposal. Phase C is **not authorised on gap-closing grounds**. D-001's dominant term is elsewhere and naming it becomes the project's next question. |
| **2** | `CI_lo( G(3)_pp ) >= 10.0` and `CI_hi( G(3)_pp ) < 25.0` | **PARTIAL ROUTE.** Extraction work is worth a real but minority share. Phase C may be authorised **only** alongside a second, independently-specified route at the residual. |
| **3** | `CI_lo( G(3)_pp ) >= 25.0` | **EXTRACTION IS THE ROUTE.** Phase C is authorised as D-001's primary treatment and C-FREQ-A becomes load-bearing rather than diagnostic. |
| **4** | anything else, incl. a CI straddling either bar | **INCONCLUSIVE.** Report, propose a power increase, authorise nothing. |

**Part B has no gate.** `f_txt` is descriptive by design: it sizes a term, it does not
decide a route. It is reported alongside and the Captain reads both.

### 5.1 ROW 0 — validity, with HK-022's drafting question answered for each

| row | check | fires if | 🔴 what this row CANNOT detect |
|---|---|---|---|
| 0a | per-band `n_ref_clean` reproduces `x1_result.json`'s committed values | any band differs | an error **inside** `load()` shared by X1 and us — a match proves *stability*, not correctness |
| 0b | both legs' pooled recall agree within 5 pp | differ by > 5 pp ⇒ **report separately, do not pool, continue** | a fault present identically in both instances |
| 0c | `R(s)` monotone non-decreasing after isotonic smoothing, over bins with `n >= 30` | any violation > 0.05 ⇒ **flag and continue, do not stop** | a smooth but wrong curve |
| 0d | determinism — full re-run with the fixed seed is **mechanically diffed**, not asserted | any byte differs | a deterministic-but-wrong computation |
| 0e | cluster floor — >= 200 clusters and >= 5,000 rows per band-leg | below either ⇒ **STOP and escalate**, do not run that band | nothing about the *representativeness* of those clusters |

🔴 **0d is a diff, not a claim.** "Byte-identical" is mechanically verified on this project
or it is not stated.

### 5.2 Resolvable distance, stated while drafting (HK-021(m))

20m carries **2,529 cycles / 67,243 rows** (Architect-measured, §6). A cluster bootstrap
over ~2,500 clusters on a pp-scale proportion should deliver a half-width of order **0.5–1.0
pp**. The bars sit at 10.0 and 25.0 pp. **Report the achieved half-width; if it exceeds 2.0
pp, ROW 4 and escalate rather than reading ROW 1.**

### 5.3 Where the bars come from

Not from the data — from the decision. The gap is ~43.8 pp and the Product Owner's stated
stake is that D-001 closing is what makes this project more than an exercise.

- **25 pp** = closes a majority of the gap ⇒ worth building as the primary route.
- **10 pp** = closes under a quarter ⇒ does not change the viability question, and spending
  weeks of native work on it would be the same mistake R1 was designed to prevent.

---

## 6. 🔴 What the Architect already measured (the disclosure of §0, in full)

20m, leg `8080`, X1's `build_band` unmodified, **single leg, single band, no clustering, no
CI** — which is precisely why this arm exists:

```
N_ref = 67,243 rows / 2,529 cycles     miss = 29,464 (43.8%)     recall = 0.562
```

Recall vs reference SNR — **a shallow monotone ramp that never saturates**, not a threshold
curve:

| ref SNR | −21 | −16 | −11 | −6 | −1 | +4 | +9 | +14 | +19 |
|---|---|---|---|---|---|---|---|---|---|
| recall | 0.21 | 0.34 | 0.50 | 0.64 | 0.77 | 0.81 | 0.88 | 0.92 | 0.93 |

The shift estimator:

| Δ | 1 dB | 2 dB | **3 dB** | 6 dB | 10 dB |
|---|---|---|---|---|---|
| gap closed (pp) | 2.51 | 4.75 | **7.00** | 13.43 | 20.74 |
| % of the 43.8 pp gap | 5.7% | 10.9% | **16.0%** | 30.6% | 47.3% |

Part B's excess-over-null (`shift = 700`), by SNR bin:

| bin | −25..−21 | −15..−11 | −5..−1 | +5..+9 | +15..+19 | **pooled** |
|---|---|---|---|---|---|---|
| near | 0.051 | 0.098 | 0.205 | 0.321 | 0.557 | 0.118 |
| null | 0.086 | 0.075 | 0.066 | 0.056 | 0.016 | 0.071 |
| **excess** | −0.035 | +0.022 | +0.140 | +0.264 | **+0.541** | **+0.047** |

**Read plainly:** a 3 dB extraction gain — roughly the entire theoretical ceiling of
3-symbol coherent combining — appears to close about **16% of D-001**. And the recall curve
is still only ~0.93 at +19 dB, where SNR explains nothing, with over half of those residual
misses being decodes we apparently made and mislabelled.

**If this replicates under proper inference, extraction quality is not D-001's dominant
term, and Route B2 cannot close D-001 no matter how well limb 2 is built.**

I want that verified by QA — three bands, both legs, clustered, with a null — before the
Captain spends another session on the coherent path.

---

## 7. What this arm does NOT do

- Does **not** license any `src`/`native` change (HK-011).
- Does **not** re-open ROW 0g or `tasks.md` §4.3, and does **not** read ROW 1/2/3/4 of the
  Phase 1 gate. Those stay VOID.
- Does **not** call Route B2 dead. ROW 1 says extraction cannot *close* D-001; that is a
  statement about magnitude, not about whether the coherent path works.
- Does **not** re-open anything on the closed-arms list, and proposes no OSR change.
- Is **not** a re-read of a closed gate with a better metric — it is a new question with its
  own pre-registration, on a population no gate has been read against.

---

## 8. Handover

QA runs §3, §4, §5; reports; **stops.** No push, no merge, no `pre_merge_check.py`
(HK-014/HK-010/HK-006). Harness under `qa/cycleframer-alignment-replay/` alongside X1.

🔴 **N14 applies to this arm's own outputs**: derive every results filename from a UTC
timestamp, and refuse to overwrite a tracked file. Do not add another script to that list.
