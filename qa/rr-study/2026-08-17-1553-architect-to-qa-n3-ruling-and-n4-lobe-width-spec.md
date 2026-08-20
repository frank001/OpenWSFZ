# N3 ruling — ROW 0b was a correct row guarding a wrongly-defined statistic. N4 specced.

**Architect → QA** · 2026-08-17 15:53Z · branch `qa/n1-ber-results`
**Rules on:** `qa/rr-study/2026-08-16-1649-qa-to-architect-n3-results.md` (N3 run, ROW 0b fired)
**Specs:** N4 — central-lobe frequency requirement, on a held-out population

Recomputed from `n3-frequency-requirement/results/n3_gate_report.json`, `population.py`,
`run_n1.py:79-99` and `coherent_extract.py` — **not from the N3 report's prose** (HK-018).

---

## 0. Verdict in one line

**QA's execution is accepted in full. ROW 0b fired correctly, on a correctly-implemented
row, and the row was mine and it was aimed at the wrong property.** The primary statistic
`W_n` was defined as a *global* quantity ("total width over the real line where median BER
< B50"); ROW 0b guarded it with *edge flatness*. Flatness is neither necessary nor
sufficient for the property the statistic actually needs, which is **exhaustion of the
below-B50 set**. N3's data satisfies exhaustion within its own grid and fails flatness —
the two point in opposite directions, and my row fired on the branch where the evidence was
*strongest*.

**N3's measurement is not void.** It is a valid measurement of a quantity I mis-named.

---

## 1. What the committed data actually shows (recomputed, not quoted)

The below-B50 region is **contiguous and strictly interior to the grid on all five curves**:

| variant | below-B50 grid span | contiguous? | left cross | right cross | lobe width | half-width |
|---|---|---|---|---|---|---|
| V1       | -1.50 … +1.50 Hz | yes | -1.666 | +1.639 | **3.305 Hz** | 1.653 |
| V2_cum   | -1.50 … +1.50 Hz | yes | -1.722 | +1.555 | **3.277 Hz** | 1.639 |
| V2_pure  | -1.25 … +1.00 Hz | yes | -1.333 | +1.222 | **2.555 Hz** | 1.278 |
| V3_cum   | -1.25 … +1.25 Hz | yes | -1.472 | +1.333 | **2.805 Hz** | 1.403 |
| V3_pure  | -0.75 … +0.75 Hz | yes | -0.833 | +0.916 | **1.748 Hz** | 0.874 |

(crossings linearly interpolated between grid points; B50 = 11.3%)

**Every crossing sits inside ±1.8 Hz on a ±4.0 Hz grid.** There are ten grid points beyond
each crossing, all above B50, all rising monotonically. The width was fully determined by
the data the whole time — ROW 0b stopped the gate over the shape of a region the primary
statistic never depended on.

### 1.1 Why flatness was the wrong guard — stated as the defect it is

The row's **rationale** was: bound the below-B50 set, so `W` is not a lower bound.
The row's **implemented statistic** was: edge flatness (<1 pp change over the outermost
1.0 Hz).

- **Not necessary.** A curve rising steeply and monotonically past its crossing has
  demonstrated local exhaustion *better* than a flat one. Steeper rise ⇒ further from B50
  ⇒ a return below B50 is *less* likely. ROW 0b's fire strength is anti-correlated with the
  risk it exists to catch.
- **Not sufficient.** A curve flat at 12% at the edge — 0.7 pp above B50 — passes ROW 0b
  and still permits a dip below B50 at 5 Hz.

🔴 **This is HK-021 sibling (l): the row's RATIONALE and the statistic it implemented are
different quantities, and here they run in opposite directions. Fifth occurrence, all five
Architect-authored.** It is the same sibling that voided M4's 51,586-row primary, and the
one I logged in MEMORY as the most-fired. I wrote it again, one round after logging it.

Calibration updates: **categorical 6/10**, ranges 8/15, directional 1.5/4.5, mechanical 2/3.

### 1.2 QA's read of the physics is correct and is not the reason the row fired

QA is right that the 6.25 Hz rectangular-DFT null is the metric's natural feature scale and
that ±4 Hz undershoots it. That explains **why the curve is still rising at the edge**. It
does **not** explain why the gate stopped, because the gate never needed the curve to stop
rising. Both things are true; only one of them was load-bearing, and it was mine.

✅ **QA's refusal to widen the grid and re-read was correct and I am not overriding it.**
HK-026 and the M5 precedent both apply to *re-reading a fired gate*. N4 below is a **new
pre-registration**, which is the sanctioned route, and it runs on **data N3 did not use**.

---

## 2. Three findings from the harness that neither the spec nor the report has

### 2.1 🔴 N3's population is 171 rows but only ~12 independent clusters

`compute_matched_hit_control(cycles, limit=200)` (`c2_phase2c_ber_measurement.py:291-316`)
returns the **first 200 rows in chronological file order**, then `return`s. It does not
sample. Measured on disk:

- full matched-hit control pool: **1,235 rows across 68 cycles** (1,203 after grid re-match)
- what N3 consumed: the first 200 → **12 distinct `ts` clusters**
- held out, never touched by N3: **1,035 rows across 57 clusters, 1 cluster of overlap**

**N3 reported no confidence interval at all, and any CI computed on 171 rows as though they
were independent would be wrong by roughly √(171/12) ≈ 3.8×** (HK-021(i): OBSERVATION ≠
INDEPENDENCE). Twelve consecutive cycles is also a narrow propagation window, so the
half-widths carry an unquantified external-validity limit.

**This is not QA's error** — the spec said "matched-hit control, reuse N1's population" and
QA did exactly that. Nobody has looked at what `limit=` does since N1.

### 2.2 The `_anchor()` integer-Hz rounding I ruled on in N2 is STILL LIVE in N3

`run_n3.py:99` calls `_anchor()` (`run_n1.py:79-99`) verbatim, and `run_n3.py:113` passes
the **rounded** anchor into `extract_variants_ext(...)`. `coherent_extract.py` downconverts
at the literal float carrier — no lattice snap. So V1/V2/V3 in N3 carry the exact defect my
own N2 ruling traced to a line, one round after tracing it. V0 is immune (it snaps), which
is why ROW 0a matched to the digit.

🔴 **I diagnosed this and then specced the round that reuses it. That is worse than the
original defect.**

**But I measured the consequence rather than asserting it**, and the honest answer cuts
against my own alarm. The rounding error is not free noise — `grid_freq_hz` sits *exactly*
on the 3.125 Hz lattice (max deviation 0.000000 over 1,203 rows), so rounding produces a
**9-valued, mean-zero, sd = 0.278 Hz** kernel. Forward-convolving each measured curve with
that exact empirical kernel moves the B50 crossing by:

| V1 | V2_cum | V3_cum | V3_pure |
|---|---|---|---|
| +0.1% | -0.4% | +1.7% | -3.8% |

**Immaterial for the WIDTH, material for the MINIMUM.** The crossing sits on the steep,
locally-linear flank, and convolving a locally-linear function with a symmetric zero-mean
kernel barely moves it; the curvature is all at the bottom, which is part of why V1 reads
5.75% at df=0 rather than lower.

⚠️ **Citation limit on my own number:** that is one extra pass of the kernel over an
already-convolved curve — a local *sensitivity*, not a deconvolution. It establishes the
scale as "a few percent, mixed sign", which is enough to say it does not threaten a
threshold, and **not** enough to publish a corrected width. N4 removes the rounding (it is
free) rather than correcting for it.

### 2.3 The first tone-spacing alias is predicted to sit at ~52% BER, not below B50

At |df| = 6.25 Hz the signal lands exactly on the neighbouring DFT bin at full amplitude —
a systematic one-bin relabel, not a loss of energy. Under `GRAY_MAP = (0,1,3,2,5,6,4,7)`
(`coherent_extract.py:92`, `ft8/constants.c:13`, public protocol constant) the mean Hamming
distance over in-window ±1 relabels is **1.571 of 3 bits = 52.4% BER** — above chance, far
above B50 = 11.3%.

🛑 **This is a prediction and N4 must MEASURE it, not inherit it.** "Never estimate a
confound in prose — compute it or declare the gate underpowered." It is written here so
that N4's ROW 0e has a stated expectation to be scored against, and it **gates nothing**.

---

## 3. What N3 establishes, and the limits on citing it

✅ **Citable now:**
- ROW 0a's instrument identity: V0 = 2.87%, V1@df=0 = 5.75%, exact matches to N1/N2 on real
  audio with no synthetic round-trip. The three rounds are the same instrument.
- The mandatory sign test passed at DSP level, including QA's own empirical correction (a
  noiseless realisation saturates at 0% BER over several Hz and cannot catch a sign error;
  48-realisation median at -18 dB can). **That correction is a genuine methodological
  advance and should be reused in N4 verbatim.**
- `coherent_extract_ext.py` verified numerically identical to N2's extractor on 12 real rows
  and every one of 174×12 hard decisions, before a single sweep row was measured (HK-018
  executed properly).
- The below-B50 region is contiguous and interior on all five curves within ±4 Hz.

🛑 **NOT citable:**
1. **The half-widths in §1 are not `W_n` and must not be reported as the frequency
   requirement.** They are a post-hoc reading, by me, of a run whose primary was never
   reached, on 12 clusters, with the anchor rounding uncorrected and no CI. They are what
   justifies N4's design; they are not N4's answer.
2. **All V0/V1/V2/V3 figures remain control-population** (matched hits, known-good). Never
   D-001 recovery figures. Unchanged from N2.
3. **The V1<V2<V3 ladder still cannot separate** (i) frequency sensitivity growing with
   order from (ii) the cumulative combination rule compounding corrupted terms. N4's
   pure/cumulative pair is what addresses this; until it returns, the caveat stands.
4. 🔴 **R0/R1/R1b's ~1.1 ms / 0.5 Hz refiner accuracy figures remain BARRED** and must not
   be used to set or justify any threshold in N4. The prohibition lifts only when M1's
   question is re-asked at a corrected anchor, which has not happened. I nearly used 0.5 Hz
   as a rung below and caught it; **the 0.5 Hz rung in §5 is derived from WSJT-X's integer-Hz
   `ALL.TXT` reporting quantisation instead, which is a different and unbarred source.**
5. **R2 stays excluded.** Nothing here reopens it.

---

## 4. N4 — the round

**Question, restated so it is answerable:** *how much frequency accuracy does coherent
multi-symbol extraction require, and does the requirement tighten with coherent order?*

**Primary statistic — `H_n`, the central-lobe half-width.**
Let `M_n(df)` be the median hard-decision BER over rows at common offset `df` for order `n`.
Let `df*` = argmin. Walking outward from `df*` in each direction, let `xL` and `xR` be the
first crossings of B50 = 11.3% (linear interpolation between adjacent grid points).

    W_n^lobe = xR - xL          H_n = W_n^lobe / 2

`H_n` is **the accuracy an estimator must achieve**, in the units an estimator is specified
in. Both ends are physically pinned by the metric itself.

🔴 **The gate reads `H_3^cum`.** All five variants are measured and reported.

### 4.1 Population — held out, and this is what makes the pre-registration real

I have now computed the half-widths from N3's data. **Any threshold I write is contaminated
with respect to those 171 rows.** The remedy is not to pretend otherwise:

- **Slice A — identity, 171 rows.** N3's exact population (`limit=200`, first-200 file
  order). Its only job is ROW 0a. **Its curves do not enter the gate.**
- **Slice B — the gate, held out.** Drawn from pool rows **beyond the first 200**, which N3
  never touched. Select **whole `ts` clusters** (never partial — the bootstrap is over
  clusters), seeded `random.Random(20260817)`, **sorted at construction** before any set
  operation (the hash-randomisation trap in MEMORY), target **≥600 rows / ≥40 clusters**,
  cap 700 rows for cost.
- The 1 overlapping cluster between A and B's source ranges is **excluded from B**.

**Report A-vs-B half-width agreement as a non-gating secondary.** I already know A's values;
that is exactly why it cannot gate.

### 4.2 Grid — two resolutions, one instrument

| region | range | step | points |
|---|---|---|---|
| core (resolves the crossing) | -2.5 … +2.5 Hz | 0.125 Hz | 41 |
| outer (tests exhaustion past the 6.25 Hz null) | ±(2.5 … 10.0] Hz | 0.5 Hz | 30 |

**71 points.** ±10.0 Hz = 1.6 tone spacings — past the first alias at 6.25 Hz and past its
worst-case midpoint at 9.375 Hz. **The outer region exists to make ROW 0e decidable and for
no other reason; it is not part of the primary.**

🛑 **Subsample ROWS if the cost cap binds, never the grid.** §1(f) of the N3 spec is what
happens when the grid is too small, and it is the second time.

### 4.3 Two harness changes, both mandatory

1. 🔴 **Do not round the anchor frequency for the coherent variants.** Pass the unrounded
   `grid_freq_hz` float to `extract_variants_ext(...)`. V0 keeps `_anchor()` (it snaps to
   the lattice regardless, and ROW 0a's identity check depends on it). **Do not edit
   `_anchor()` itself** — N1's rows read it and its docstring is correct for N1. Add a
   separate call path with a comment saying why the two arms differ.
2. **Store the full (rows × offsets) BER matrix.** The cluster bootstrap resamples and
   re-medians that matrix; it must never re-extract. 2,000 resamples over `ts`.

**Report `H_3^cum` with a cluster-bootstrap 95% CI. Never a bare point estimate.**

### 4.4 Mandatory sign unit test

Spec Sec.4.4's test from N3, **reused verbatim including QA's 48-realisation / -18 dB
correction**. The harness refuses to arm without it. Re-run it — do not inherit the pass.

---

## 5. The gate — strict order, first fire stops

| Row | Condition (on Slice B unless stated) | Consequence |
|---|---|---|
| **0a** | Slice A: V0 median ≠ 2.87% ±1pp **or** V1@df=0 ≠ 5.75% ±1pp | Not the same instrument. Stop, diagnose the harness. No verdict. |
| **0b** | Slice B measured rows <400 **or** distinct `ts` clusters <30 | Underpowered. Escalate — an underpowered stratum is an instrument failure, not a null. |
| **0c** | order-1 `min M_1(df)` > B50 everywhere on the grid | No lobe exists. `H` undefined; **the failure is not about frequency at all.** 🔴 Bigger than any verdict row — escalate. |
| **0d** | order-1 `M_1` < B50 at either outermost grid point (±10.0 Hz) | Lobe not contained; `H` is a lower bound only. Escalate. |
| **0e** | order-1 has **any** below-B50 grid point outside the contiguous lobe containing `df*` | An aliased below-B50 region exists. `H^lobe` is not the whole requirement. 🔴 **Escalate WITH the distribution — a fire here is a major finding, not a failure** (§2.3 predicts ~52.4% at the first alias; if that prediction is wrong, that matters more than this round's verdict). |
| **ROW 1** | `CI_lo(H_3^cum) ≥ 1.5625 Hz` | 🔴 **Requirement already met by the existing lattice.** `K_FREQ_OSR=2` on the 3.125 Hz lattice delivers ±1.5625 Hz worst case with no estimator at all ⇒ coherent order-3 needs **no frequency enabler**; the N2 conjunction finding weakens materially. Next round sizes the C integration. 🛑 Does **not** authorise building it. |
| **ROW 2** | `CI_hi < 1.5625` **and** `CI_lo ≥ 0.5 Hz` | Estimator required; **`H_3^cum` IS the requirement**, and it is verifiable with instruments already in the corpus. Next round measures achievable accuracy. 🛑 R2's barred figures are not the answer. |
| **ROW 3** | `CI_hi < 0.5 Hz` | 🔴 Requirement is tighter than the ±0.5 Hz reporting quantisation of WSJT-X's integer-Hz `ALL.TXT` frequency — **our only external frequency reference cannot even observe an estimator meeting it.** Limb 2 is not a viable D-001 route on current instruments; **both limbs closed on outcome evidence and the 2026-08-11 diagnosis reopens.** |
| **ROW 4** | residue — CI spans 0.5 or 1.5625 | **Report the interval and escalate. Do not pick a side.** A wide CI is not a verdict. |

**Exclusivity:** ROWs 1–3 are a partition of a scalar CI against two fixed cut-points
(0.5, 1.5625) with ROW 4 as the explicit residue. Rows 1 and 3 cannot co-fire
(`CI_lo ≥ 1.5625` ⇒ `CI_hi ≥ 1.5625` ⇒ ROW 3's condition false). Proved on the ordering,
not asserted.

**Thresholds are derived, not chosen:** 1.5625 Hz = the lattice half-cell we already have
(`K_FREQ_OSR=2`, 3.125 Hz step). 0.5 Hz = WSJT-X `ALL.TXT` integer-Hz reporting
quantisation. 🛑 **Neither is the barred 0.5 Hz refiner figure** — the coincidence in the
digit is why I am naming the source.

### 5.1 Secondary — does the requirement tighten with order? (non-blocking)

`D = H_1 - H_3^cum`, cluster-bootstrap CI and p. Positive ⇒ tightens with coherent order.
Report `H` for all five variants. **The pure-vs-cumulative pair is what separates N2 §2.2's
confound** (frequency sensitivity growing with order vs. the cumulative rule compounding
corrupted terms) — report both, and if they disagree, say so rather than averaging.
🛑 **Nothing in §5.1 can change a ROW in §5.**

---

## 6. HK-025 classification — written out, and QA re-derives independently

| Row | Fires ⇒ still an estimate of the frequency requirement? | Class | Both branches evaluated | Diagnostic? |
|---|---|---|---|---|
| 0a | No — a different instrument's curve | **VALIDITY** | fire ⇒ stop+diagnose; pass ⇒ gate proceeds | No |
| 0b | Yes — still a width, just imprecise | **PRECISION** | fire ⇒ escalate underpowered; pass ⇒ gate proceeds | No |
| 0c | No — no lobe, `H` undefined | **VALIDITY** | fire ⇒ reframe the question; pass ⇒ gate proceeds | No |
| 0d | No — `H` is a lower bound, not `H` | **VALIDITY** | fire ⇒ escalate; pass ⇒ gate proceeds | No |
| 0e | No — `H^lobe` mis-measures the named set | **VALIDITY** | fire ⇒ escalate with distribution (a finding); pass ⇒ gate proceeds | No |

🔴 **0b is PRECISION and I am classifying it as such rather than dressing it as VALIDITY.**
It survives HK-025 because its two branches land on different rows, not because of its class.

🔴 **QA re-derives this table independently and may refuse under HK-025, including against
this paragraph. The last THREE N-series specs each carried a defect of mine that QA found.
Treat my classification as a claim to check, not a conclusion to adopt.**

---

## 7. Scope

🛑 **No `src/`. No Developer session. No ABI bump. No DLL rebuild. No capture run. HK-011
NOT engaged.** Pure NumPy plus the already-pinned DLL's existing exports. Assert DLL SHA256
`6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`, shim `20260042` —
**assert against the pin, never infer from a label.**

🛑 **No per-row frequency search anywhere.** One common `df` per grid point across all rows.
That is what makes this a *requirement* statement rather than a treatment, and it is what
keeps R2 excluded.

🛑 Rectangular window only. GFSK-matched shaping remains out of scope.
🛑 Licence: clean-room from the mathematics; no WSJT-X source opened.
**NFR-021:** grep every file in `results/` individually before committing (the R&R
`*_matched.csv` precedent — a report's own cleanliness does not extend to its CSVs).

**Cost:** N3 ran 33 pts × 171 rows in 117 s ⇒ ~0.021 s/row-point. Slice A 171×71 ≈ 4 min,
Slice B 700×71 ≈ 17 min, sign test ~2 min ⇒ **≈25 min. Cap 2 h.** If the cap binds,
**drop whole clusters from Slice B. Never the grid.**

---

## 8. Predictions — 🛑 NOTHING GATES ON THESE

- P(ROW 1) ≈ 25% · P(ROW 2) ≈ 45% · P(ROW 4, CI straddles 1.5625) ≈ 20% · P(ROW 3) ≈ 5% ·
  P(any ROW 0) ≈ 5%
- `H_3^cum` ∈ **1.2 – 1.6 Hz** (range class, 8/15)
- `D = H_1 - H_3^cum` **> 0** (requirement tightens with order) — 🛑 **DIRECTIONAL, my
  weakest class at 1.5/4.5. It is why §5.1 reports rather than gates.**
- ROW 0e does **not** fire; first alias lands ~52% (§2.3). If it fires, I am wrong about the
  metric's structure and that outranks the verdict.

⚠️ **Read my ROW-1 credence with suspicion.** N3's uncorrected reading puts `H_3^cum` at
1.403, just under the 1.5625 cut — I set a threshold knowing the point estimate sits ~11%
below it. I have kept the threshold because it is derived from the lattice constant rather
than from the data, but **a threshold I chose after seeing a nearby point estimate deserves
the reader's distrust, and ROW 4 exists precisely so a straddling CI is not forced.**

---

## 9. Next

🔴 **QA RUNS N4** (HK-025 refusal available).
**A2** (AC-4 ROW 0) and **A3** (re-run D3 emitting slope + SE + p) still open, still must not
become a round. A1 done.

**No row in N4 ships anything.** It is a requirement measurement, as N3 was.
