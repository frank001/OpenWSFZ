# N2 — does a COHERENT MULTI-SYMBOL LLR extractor fix the reading? BER against the same measured bar

**Architect → QA** · 2026-08-16 14:08Z · branch `qa/n1-ber-results` (off
`feat/r1b-sync-refiner-instrument-correction`)

Supersedes nothing. Follows N1
(`qa/rr-study/2026-08-16-1353-qa-to-architect-n1-results.md`), which fired ROW 2 and
closed limb 1.

---

## 1. Why this arm, and why it is shaped exactly like N1

D-001's root cause has been identified since 2026-08-11 and has two limbs:

1. **no fine position refinement** (grid 3.125 Hz / 0.08 s vs WSJT-X 0.5 Hz / 5 ms)
2. **no coherent multi-symbol bit metrics** (we take a single-symbol max-log over 8
   *magnitude* bins)

**N1 killed limb 1 on outcome evidence.** It held the metric constant and varied the
position: `d_ber` = −0.57 pp, CI95 [−1.15, +0.00], `f_cross` = 0.0%, and the strong
stratum (THE 135) was *significantly harmful* at −4.02 pp. R2 is excluded, not unscoped.

**N2 is the exact mirror: hold the position constant and vary the metric.** Same
population, same audio, same anchor, same bar, same statistic, same bootstrap, same
pairing. Every row is measured twice on the same buffer at the same position, so
population selection, SNR composition, corpus vintage and candidate-mismatch inflation
all cancel — the same reason N1's design survived where M1/M2/M4 did not.

This is deliberate. Five rounds died on proxy statistics. N1 was the first arm in this
thread to return a real finding, and it did so because it measured a **decode outcome
against a bar that was measured, not invented**. N2 changes one variable and nothing
else.

---

## 2. What I found in source while writing this — read this section before costing the arm

All three items were derived from the files, not from the board's prose. Two of them
**contradict things the board currently says in my own hand**.

### 2.1 🔴 The production pipeline destroys phase *before* extraction — the waterfall cannot be the front end

`native/ft8_lib_vendor/ft8/decode.h:21-31`:

```c
// #define WATERFALL_USE_PHASE
#ifdef WATERFALL_USE_PHASE
#define WF_ELEM_T          waterfall_cpx_t      /* {float mag; float phase;} */
#else
#define WF_ELEM_T          uint8_t
#define WF_ELEM_MAG(x)     ((float)(x)*0.5f - 120.0f)
#endif
```

`WATERFALL_USE_PHASE` is **commented out**. Production's waterfall is `uint8_t`:
magnitude only, **quantised to 0.5 dB steps**, floor −120 dB. The struct that would
carry phase exists and is disabled.

And `decode.c:1062-1075`, the metric itself:

```c
for (int j = 0; j < 8; ++j) s2[j] = WF_ELEM_MAG(wf[kFT8_Gray_map[j]]);
logl[0] = max4(s2[4],s2[5],s2[6],s2[7]) - max4(s2[0],s2[1],s2[2],s2[3]);
```

So the current LLR is a difference of **max-of-log-amplitude**, single symbol,
phase-free, 0.5 dB quantised, read off a 3.125 Hz / 0.08 s lattice
(`K_FREQ_OSR=2`, `K_TIME_OSR=2`, `ft8_shim.c:499-500`). That is wrong in three
independent ways at once — non-coherent, wrong domain (log-amplitude rather than
power normalised by noise), and quantised — before you even reach "single-symbol".

**Consequence for scoping: limb 2 cannot be built by consuming the existing waterfall.**
It needs its own complex front end. There is no cheap "just read the phase out" path.

### 2.2 🔴 The unknown-phase problem is real, is already documented in our own code, and already forced a retreat

The board's framing — *"the keystone is already built; what is missing is a consumer"* —
is **mine, and it is too optimistic.** `sync_refiner.c:161-212` records that the R1
implementation attempted complex combining across the three Costas blocks and **had to
retreat to non-coherent cross-block combining**, for a reason that applies with full
force to limb 2:

> FT8 is continuous-phase FSK (CPFSK): the transmitter's phase at the start of sync
> block 1 (symbol 36) and block 2 (symbol 72) carries the accumulated phase
> contribution of the ~29 DATA symbols between each pair of sync blocks — symbols whose
> tones are message-dependent and UNKNOWN to this diagnostic stage.

Coherent integration across **data** symbols has exactly this problem, and the standard
resolution is not "retain phase" — it is **enumerate the tone hypotheses**, because the
inter-symbol phase is a known, computable function of the tones *within* the group. That
means 8² = 64 hypotheses for a 2-symbol group and 8³ = 512 for a 3-symbol group,
max-log-marginalised down to per-bit LLRs.

**So limb 2 is not "write a consumer".** It is a hypothesis-enumerating coherent
demodulator. It is still cheap in compute (§6.3), but it is materially more design than
the board currently claims, and I am correcting my own entry rather than letting the
cheap framing stand.

✅ What *does* carry over: `costas_coherent_sum` (`sync_refiner.c:214-270`) already
proves out the two hard details — a **true continuous-phase integrated reference**
(design correction (2), found empirically after a naive per-symbol reference peaked
several samples off truth) and the correct working rate. Reuse the *method*, not the
buffer.

### 2.3 ✅ The arm needs NO `src/` change, no Developer session, no DLL — it is Python off the WAV

This is the finding that makes the round cheap, and it points the opposite way from
§2.2.

The measurement does **not** need a C implementation. `downconvert_decimate` is 30 lines
of standard DSP; the whole coherent extractor is a NumPy prototype off the same PCM N1
already loads. And the arithmetic falls out exactly:

- decimate 12000 Hz by 6 → **2000 Hz** working rate (`REFINE_DECIM_FINE`, already the
  refiner's own Stage C rate)
- 0.16 s symbol × 2000 Hz = **320 samples/symbol**
- 2000 / 320 = **6.25 Hz bin spacing = the FT8 tone spacing, exactly**

The 8 tones land on **exactly orthogonal** bins of a 320-point transform over one
symbol. The per-symbol matched filter *is* an 8-bin DFT. There is no approximation to
argue about, and the existing 2000 Hz choice is already the right one.

⇒ **HK-011 is NOT engaged. No `src/` edit, no `opsx:apply`, no ABI bump, no new DLL, no
capture run.** The C implementation is the *integration* round that this measurement
would gate — it is not needed to answer the question. Assert the merged DLL
(`6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`, shim **20260042**)
for the baseline arm and change nothing.

---

## 3. 🛑 Three things that must NOT be concluded from N1's data

### 3.1 🛑 The 44–50% median BER MUST NOT be used to predict N2's outcome — that is the HK-026 error exactly

N1 reports median BER ~44–50% in both arms. It is tempting to reason "those rows are
near-random, so no metric can rescue them."

**That reasoning is forbidden here, and it is forbidden on HK-026 grounds.** The 44–50%
figure was produced *by the very extractor whose blind spot N2 exists to measure*. It is
a property of the non-coherent magnitude-only metric, not a property of the audio. Using
it to bound what a different metric could recover is precisely "an instrument's output
used to derive the bounds of that instrument's own blind spot".

The valid bypass is available and is what N2 is: **a wider-aperture instrument.**

🛑 Symmetrically — the 44–50% figure must not be used to argue N2 *will* succeed either.
It is silent in both directions. Do not cite it in the N2 report as evidence for
anything except "this is what the old metric reads."

### 3.2 🛑 N1 did not test fine frequency estimation as an ENABLER, and §7.2 is not R2's rehabilitation

N1 killed limb 1 as a **standalone treatment**. It did not, and could not, test whether
fine frequency accuracy is a **precondition** for limb 2's coherent gain. The physics is
not optional: over a 3-symbol coherent group (0.48 s), a 0.5 Hz carrier error is 0.24
cycles ≈ 86° of phase rotation across the group. Single-symbol integration barely cares;
3-symbol coherent integration cares a great deal. And our anchor frequency comes from
`ALL.TXT` at **integer Hz** — so it is known to ±0.5 Hz at best.

§7.2 pre-registers a frequency-sensitivity sweep for this reason. 🛑 **It is a property
of the extractor's own matched filter — a demodulator estimating its own carrier is
standard — and it is NOT a re-proposal of `ft8_refine_candidate` under a new name.** If
the report frames it as R2 returning, that framing is wrong and must be struck. R2 stays
excluded. What §7.2 can legitimately produce is a *requirement statement* for a future
limb-2 integration ("coherent gain needs carrier to ±X Hz"), and nothing more.

### 3.3 🛑 `f_cross` is not recall, and B50 is a 50% point

`B50 = 11.3%` is the BER at which **half** of rows get corrected. A row crossing below it
has roughly even odds, not certainty. 🛑 Do not convert `f_cross` to a recall figure 1:1,
and do not conflate it with the retracted `k_50` = 13 / 7.47% (different quantity,
already retracted on the board). ROW 1's consequence is *"order a proper sizing"*, never
*"the sizing is f_cross"*.

---

## 4. The treatment — four metric variants, one pre-registered primary

All four read the **same** PCM at the **same** GRID anchor as N1's control arm
(`run_n1.py:_anchor()`), with the identical `P.read_wav` → `P.normalise_rms(pcm,
P.PROD_TARGET_RMS)` path. 🔴 **A different input scaling silently changes everything —
reuse N1's loader verbatim, do not reimplement it.**

| variant | what it is | what it isolates |
|---|---|---|
| **V0** | **baseline / control.** `ft8_extract_llrs_at` (shim 20260042), unmodified C, exactly as N1's GRID arm | production truth |
| **V1** | complex baseband → per-symbol 8-tone matched filter → max-log on **\|X\|²** | domain + quantisation + exact-frequency, **not** coherence |
| **V2** | V1 + **2-symbol** coherent groups, 64 tone hypotheses, max-log marginalised | first coherent step |
| **V3** | V2 + **3-symbol** coherent groups, 512 hypotheses | the full treatment |

**The primary is V3 vs V0.** V1 and V2 are pre-registered secondary decomposition —
computed always, reported always, used **only to attribute** a ROW 1/ROW 2 result.

🛑 **V1 or V2 outperforming V3 does not rescue a ROW 3.** If V3 lands ROW 3 and V1 looks
good, that is a NEW question and it earns a NEW pre-registration. Never re-read a closed
gate with a better metric.

### 4.1 Method, and the licence constraint on how it is written

The method is standard coherent matched-filter demodulation with max-log APP
marginalisation over tone hypotheses:

1. Downconvert PCM to complex baseband at the anchor carrier, lowpass, decimate by 6 →
   2000 Hz (method per `downconvert_decimate`, `sync_refiner.c:128-159`).
2. Per symbol `p ∈ [0,79)`, per tone `j ∈ [0,8)`: coherent correlation over that
   symbol's 320 samples against a **continuous-phase-integrated** reference
   (`costas_coherent_sum`'s design correction (2) — a naive per-symbol reference is a
   known, measured defect, do not repeat it). Yields complex `X[p][j]`.
3. V1: per-symbol max-log over `|X[p][j]|²`, Gray-mapped (`kFT8_Gray_map`), skipping
   sync symbols on the same `k + (k<29 ? 7 : 14)` schedule `ft8_extract_likelihood`
   uses.
4. V2/V3: for each group, the inter-symbol phase is **computable given the tone
   hypothesis**; sum complex across the group per hypothesis, take `|·|²`, max-log
   marginalise to per-bit LLRs; combine group orders by summation.
5. **Raw LLRs, no `ftx_normalize_logl`** — same convention as `ft8_extract_llrs_at`,
   so V0 and V3 are compared on the same footing. BER is hard-decision, so
   normalisation is irrelevant to the primary; keeping it off keeps the two arms
   symmetric.

🛑 **Rectangular per-symbol matched filter only.** GFSK-matched pulse shaping is
explicitly OUT of scope for N2 and is recorded here as a candidate refinement *if* ROW 2
fires. Do not add it mid-run.

🛑 **LICENCE — Captain's binding ruling, 2026-08-11.** Write this from the mathematics in
this section. **No WSJT-X source (`ft8b`, `sync8d`, `ft8_downsample`) is to be opened,
read, transliterated or ported during implementation.** `sync_refiner.c:11-22` is the
precedent: clean-room by construction, stated in the file header. Do the same in the N2
harness header. Our repo is **AGPL-3.0**; intake policy is **permissive only**.

---

## 5. Population, pairing, statistic

**Identical to N1 — reuse the modules, do not re-derive:**

- `population.build_paired_population()` — THE 135 + THE 567, candidate-present-and-failed,
  n=441 grid-matched / 405 measured, 67 `ts` clusters
- `population.build_matched_hit_control()` — the known-good control
- `n1_stats.B50_THRESHOLD` = 0.113, `cluster_bootstrap_median_diff`, `d_ber_row`,
  `f_cross_row`
- corpus `d001_c2_phase2c` (`qa/ARTEFACT_INVENTORY.md:47`, 260725_180615→260725_182645),
  WAVs already on disk — **no capture run**

**Sign convention, and it is load-bearing:**

```
d_ber = BER_V0 − BER_V3        POSITIVE = the coherent metric HELPS
```

Same direction as N1's `BER_grid − BER_refined`. **Mandatory sign unit test asserting
both ends on synthetic extremes before arming; the harness must refuse to run without
it** (N1's `sign_unit_test.py` is the pattern and it passed first time).

**Primary:** paired median `d_ber`, CI95 + p from a **cluster bootstrap over `ts`**
(HK-021(i) — rows within a cycle are not independent), 2000 draws, seed fixed and
recorded.

**Secondary, always computed and always reported:** `f_cross`; V1 and V2 against V0;
the per-population table (THE 135 / THE 567 — 🛑 **do not average to a verdict**, N1's
strata disagreed and that disagreement was the finding).

🛑 **HK-021(l): no statistic on an absolute value where a signed one exists.** The
one-sided "does it help" claim gates on signed `CI_lo`. `|d_ber|` appears only in ROW 3's
symmetric equivalence band, which is what an equivalence bound legitimately is.

⚠️ **Structural ceiling, stated in advance:** hard-decision BER saturates near 50%
(random). The baseline arm sits at 44–50%, i.e. **against that ceiling**, so the paired
difference is asymmetric-tailed — bootstrap the paired **median**, never the mean.

---

## 6. Gate — strict order, stop at the first row that fires

### 6.0 Preconditions

| Row | Fires when | Consequence |
|---|---|---|
| **0a** | synthetic noiseless round-trip: modulate a known message at a known (f, dt) with `qa/rr-study/synth/modulator.py`, extract with V3 → hard-decision BER **≠ 0.0% exactly** | the extractor cannot read a signal it was handed perfectly. Fix the harness, re-run. 🛑 Not a result. |
| **0b** | on `build_matched_hit_control()`: **V1 median BER > 5%** OR V0 median BER ≠ 2.87% ± 1 pp | origin/convention mismatch between the Python front end and the C baseline. 🔴 **A one-symbol time-origin error reads as ~50% BER, not "slightly worse" — this row is sharp by construction.** Escalate. |
| **0c** | fewer than **200** paired rows measured | underpowered ⇒ **instrument failure, not a null**. Escalate. |
| **0d** | median per-row hard-decision disagreement between V0 and V3 over the 174 bits **< 5 bits** | the two metrics are the same reading; no contrast is possible and `d_ber ≈ 0` is guaranteed and meaningless. **This row exists because M4 taught us to check the contrast CAN move before reading that it didn't.** Escalate. |

### 6.1 Verdict rows — mutually exclusive, in strict order

| Row | Fires when | Consequence (pre-written; the gate is mechanical) |
|---|---|---|
| **ROW 1** | `d_ber` CI_lo **> 5 pp** **AND** `f_cross` **≥ 0.20** | 🔴 **Coherent multi-symbol extraction is a first-order D-001 term.** The C integration round becomes **scopeable**, and a proper recall sizing is **ordered** (§3.3 — `f_cross` is not itself the sizing). |
| **ROW 2** | `d_ber` CI_lo **> 5 pp** **AND** `f_cross` **< 0.20** | 🔴 **Real, but it does not convert.** The metric genuinely extracts more information and it is not enough to cross the threshold on this population. **Limb 2 is necessary-but-not-sufficient.** Next work sizes *what else* is needed — **not** integration. ✅ A real finding, not a void. |
| **ROW 3** | `\|d_ber\|` **≤ 5 pp** **AND** CI_hi **< 15 pp** **AND** `f_cross` **< 0.02** | 🔴 **Limb 2 is dead too.** Both limbs of the 2026-08-11 root cause would then be closed **on outcome evidence**, and the diagnosis itself must be reopened from scratch. 🛑 This is a large claim and it is why ROW 0d exists. |
| **ROW 4** | anything else, including `d_ber` CI_hi < −5 pp (coherent significantly **worse**) | escalate with the full distribution. 🛑 **Do not average your way to a verdict.** |

**Exclusivity check (HK-021, done explicitly):** ROW 1/ROW 2 require `CI_lo > 5 pp`,
which implies `d_ber > 5 pp`, which excludes ROW 3's `|d_ber| ≤ 5 pp`. ROW 1 and ROW 2
are separated by `f_cross`. ROW 4 is the residue. No two rows can fire on the same data.

### 6.2 HK-025 classification — QA re-derives independently and MAY REFUSE

Each ROW 0, classified by the two-step test, both branches evaluated:

- **0a** — fires ⇒ is the result still an estimate of what the gate names? **No** (an
  extractor that cannot read a noiseless synthetic is not measuring coherent
  extraction). ⇒ **VALIDITY.** Legitimate.
- **0b** — fires ⇒ the Python front end is reading a different position or scaling than
  the C baseline; the paired contrast is then not a metric contrast at all.
  ⇒ **VALIDITY.** Legitimate.
- **0c** — fires ⇒ underpowered; the estimate exists but cannot distinguish ROW 2 from
  ROW 3, which are *different rows*. ⇒ **VALIDITY.** Legitimate.
- **0d** — fires ⇒ ROW 3 becomes guaranteed regardless of the fact being asked about.
  Not-fires ⇒ the contrast can move and rows 1–4 stay reachable. **Different rows in the
  two branches** ⇒ **VALIDITY**, not diagnostic. Legitimate.

None is DIAGNOSTIC. 🔴 **QA must run this classification independently, including against
this paragraph, and refuse under HK-025 if it disagrees. A refusal names the row and the
evaluation and STOPS — no fix, no partial run, no softening.**

### 6.3 Cost

Per row: downconvert 180 000 samples (FFT-based, or 61-tap FIR); then the per-symbol
correlation is a single `(79,320) × (320,8)` matrix product. V2/V3's hypothesis
enumeration operates on the 79×8 complex array — 78 pairs × 64 and 77 triples × 512,
trivially vectorised. **Minutes for the full 405 rows, not hours.** Estimate **≤ 45 min**
including §7.2's sweep; **cap 3 h**. 🛑 If it overruns, subsample **rows** — never trim
the variant ladder or the sweep grid.

---

## 7. Pre-registered secondaries

### 7.1 Variant decomposition
V1 and V2 vs V0, same statistic, same bootstrap. Attribution only (§4).

### 7.2 Frequency-sensitivity sweep — read §3.2 before writing this up
Run V3 at assumed carrier offsets `df ∈ {−1.0, −0.5, −0.25, 0, +0.25, +0.5, +1.0}` Hz
around the anchor; report median BER vs `df`. Answers "how much carrier accuracy does
coherent gain require", which is a **requirement statement for a future integration**.
🛑 Not a verdict row. 🛑 Not R2's rehabilitation.

### 7.3 Tight-match stratification — defined mechanically, in advance
Stratify on `|f_candidate − f_WSJTX|`: **tight** ≤ 2 Hz, **loose** > 2 Hz. Rationale: a
row whose matched candidate is a *different signal* than the one WSJT-X decoded reads
near-random for reasons **no metric can fix**, and such rows structurally suppress
`f_cross`. This is defined here, before the run, precisely so it cannot become a
post-hoc rescue. Report both strata; 🛑 the gate reads the **combined** population.

---

## 8. Predictions — 🛑 NOTHING GATES ON THESE

- P(ROW 1) ≈ **20%** · P(ROW 2) ≈ **35%** · P(ROW 3) ≈ **35%** · P(ROW 4 or any ROW 0) ≈ **10%**
- V1 alone captures ≥ half of whatever total gain appears: ≈ **50%** (directional)
- §7.2 shows median BER degrading measurably by `|df|` = 1.0 Hz: ≈ **60%** (directional)

⚠️ **Architect calibration, quoted because it is the honest weight to give the above:
categorical 6/9 · ranges 8/15 · DIRECTIONAL 1.5/3.5 · mechanical 2/3. Score the
CONSEQUENCE, not the interval.** 🔴 I argued the sync-refinement route for four days and
was wrong; I then predicted N1's ROW 2 correctly. Both facts are in the record. **No row
turns on any number in this section**, and the two directional predictions above are in
my weakest class by a wide margin.

---

## 9. Scope discipline

- 🛑 **No `src/` change. No Developer session. No `opsx:apply`. No ABI bump. No new DLL.
  No capture run.** HK-011 is not engaged. Assert DLL SHA256
  `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672` / shim **20260042**
  and never infer it from a label.
- 🛑 **R2 stays EXCLUDED.** N2 cannot unscope it. §7.2 is not a route back.
- 🛑 **The standing prohibition on citing R0/R1/R1b's ~1.1 ms / 0.5 Hz figures for real
  signals is UNCHANGED and N2 does not touch it.**
- 🛑 **A C implementation of the coherent extractor is NOT authorised by this spec.** It
  is the round that a ROW 1 would make scopeable — and ROW 1 makes it scopeable, it does
  not scope it.
- **NFR-021:** message text in-process only, for `ft8_encode_message`; never written to a
  result file or printed. Per-row output carries `ts` + numeric fields only. ⚠️ Grep
  **every** file in the run directory individually before committing — a report's own
  cleanliness does not extend to its CSVs.
- **A2 and A3 remain open and must not become a round. A1 is done.**

---

## 10. Deliverables

1. `qa/rr-study/n2-coherent-llr-extractor/` — harness: `coherent_extract.py`,
   `sign_unit_test.py`, `n2_stats.py` (importing N1's where possible), `run_n2.py`.
   Clean-room provenance note in the header (§4.1).
2. Sign unit test run **first**, result stated, harness refusing to arm without it.
3. Gate evaluated in **strict order**, stopping at the first row that fires, with the
   HK-025 re-derivation written out.
4. Report `qa/rr-study/<UTC>-qa-to-architect-n2-results.md`, HK-001 sections, per-stratum
   table, §7.1–7.3 secondaries.
5. Committed **locally**, per this branch's established pattern (`5c8e3bd`, `cf39947`,
   `0927a6e`). 🛑 **Not pushed** — HK-014.
6. **BOARD.md updated in the same edit as the result** (HK-024).

🔴 **NEXT: QA runs N2. HK-025 refusal is available and I have written out my own
classification specifically so it can be challenged.** QA does not author the follow-on
spec (HK-015).
