# `AWGN-FP` — the S5 false-accept rate, measured offline at usable N

**Architect → QA, pre-registered.** 2026-09-02 19:06Z.
Base: `main`@`3b52608`, shim `20260049`.
Opened on QA's Recommendation 1 from `results/2026-09-02-3b52608/report.md` (Finding 1), and on the
PO's ruling of the same date.

---

## 0. Headline — read this before the spec body

QA's report says, correctly, that it "does not diagnose a root cause — three data points at N=60 is
not enough to fit a rate model." **That bind is an artefact of the instrument, not of the problem.**
Three things already exist that dissolve it, and none of them needs a new capture, a new export, or
a Developer session:

1. **S5's AWGN is seeded and deterministic.** `siggen.py:353` → `np.random.default_rng(seed)`, and
   every S5 slot's seed is recorded in that run's own `truth.csv`. The slots are reproducible
   offline, exactly.
2. **A WAV → `ft8_lib` offline seam already ships** and is the instrument several prior arms already
   ran on (`tests/OpenWSFZ.Ft8.Tests/`, `WavReader.cs`, `Ft8LibInteropTests`,
   `F005RealCorpusSaturationCheck`, `D001H6ApDecodeTests`).
3. **The diagnostic export this arm needs already exists** — `ft8_get_last_snr_terms`
   (shim `20260045`), wired through `Ft8LibInterop.GetLastSnrTerms` →
   `Ft8NativeInteropAdapter` → `IFt8NativeInterop`, with its own test file
   `GetLastSnrTermsTests.cs`. **Unlike `F-001` L3, this arm needs no new shim version and no
   HK-011 cycle.**

⇒ N moves from 60 slots per 77-minute hardware sweep to N in the thousands per offline run.

### 0.1 The finding that motivates it, which the sweep report does not contain

Every S5 false positive in the ratified-gate era carries the same signature, and it is a signature
the decoder computes about **its own** decode:

| sweep | S5 FP events | of those, reported SNR ≤ −25 dB | lowest *genuine* OpenWSFZ decode, same run |
|---|---|---|---|
| 2026-06-22 `f11f438` | 0 | 0 | −16 |
| 2026-07-04 `793a298` | 0 | 0 | −17 |
| 2026-08-21 `7d36038` | 1 | 1 | −17 |
| 2026-08-22 `f5dec23` | 4 | 4 | −17 |
| 2026-08-27 `22b749c` | 0 | 0 | −17 |
| 2026-08-29 `872ba65` | 1 | 1 | −17 |
| 2026-08-30 `2e60949` | 2 | 2 | −17 |
| 2026-09-02 `3b52608` | 4 | 4 | −18 |

**12 of 12. No genuine decode in that era has ever been below −18 dB.** The two populations are
disjoint by ~8 dB. Derived by the Architect directly from the committed `*_matched.csv` files, with
an OR-rule dedupe across scenario files (the same decode event appears in several, per the report's
own Recommendation 3 — counting the raw rows inflates by ≈8× and is the HK-021(i) trap).

**This is mechanistic, not a curve-fit.** `ft8_shim.c:1719` is
`float snr = signal_db - local_noise_db - 26.5f`, with no floor and no clamp. A reported −26 dB is
therefore `signal_db ≈ local_noise_db` — the decoder asserting a CRC-valid codeword with **zero
excess power over its own local noise estimate**. That is what a 14-bit-CRC escape from noise looks
like, and it is what a real signal cannot be. This run's four events read −27/−26/−26/−26 dB, three
at |DT| ≥ 1.0 s, two at frequencies outside the injected 450–2550 Hz band, and their message texts
are structurally garbage (11-character callsign fields, stray `/P` suffixes) — consistent with a
random 77-bit payload that happened to clear CRC-14.

### 0.2 Two claims from the report that this arm does NOT inherit

- 🔴 **"Escalating" is not established, and this arm must not assume it.** The same spurious process
  measured in *signal-present* cycles runs at **6.7%** of cycles this sweep against **12.7–14.9%**
  in the 2026-06-22 / 2026-07-04 sweeps that **passed** the gate. Total propensity is *down* ~2×;
  what changed is where events land. The live hypothesis is a **distribution shift** into noise-only
  slots, not a rising rate.
- 🔴 **The Architect's own discriminant is partly circular and this arm exists to break that.**
  The candidate window for the shift (`7d36038`..`f5dec23`) contains `c3a9ea8`
  ("negative time_offset SNR collapse", shim `20260046`) — a change to the **very SNR scale** the
  ≤ −25 dB cut is expressed on. The signature and the suspected cause sit on the same axis. Reading
  `signal_db`/`local_noise_db` as separate terms (ROW 2) is what decouples them.

### 0.3 The prohibition check, run before drafting, because it bit

`memory/closed-arms-prohibitions.md` closes two families that this arm's "obvious" mitigation lands
squarely inside:

- 🛑 **"Candidate-budget family closed twice — no caps, no passes."** ⇒ `s_k_min_score_pass2`
  (D-009's calibrated K=10), `K_MAX_CANDIDATES`, `K_MAX_CANDIDATES_PASS2` and the pass-config table
  at `ft8_shim.c:1552` are **OUT** as levers. They may be **named as hypotheses and measured**, never
  proposed as a change on this arm's evidence.
- 🛑 **"Input scaling CLOSED — normalisation, AGC, softmax/temperature, equalisation."** ⇒ ROW 0c's
  level-sensitivity check below is a **measurement of the instrument's own validity**, not a
  treatment. It changes the *rendered test signal*, never the decoder's input handling. Stated here
  explicitly so it is not mistaken for a re-proposal of the closed arm.

**The one surviving lever is emission-side and is neither of those families:** refusing to *emit* a
decode whose own `signal_db − local_noise_db` shows no excess changes nothing about what the decoder
searches or how its input is scaled — only what it publishes, on a statistic it already computes.
Whether to pull that lever is **not this arm's question**; this arm sizes it.

---

## 1. Population, and what this arm may speak about

- **Primary population:** signal-free AWGN slots as defined by `scenarios/s5-noise.json` parts 0
  (`awgn`, `level_dbfs -20`) and 1 (`awgn`, `level_dbfs -10`), rendered offline from recorded seeds.
- **Scoped to AWGN deliberately**, per that scenario file's own sizing note: parts 2 (steady carrier)
  and 3 (multi-carrier birdies) produced **1** false positive between them across the entire history
  in `results/`, against **52+** from parts 0/1. That is the base rate this scoping rests on
  (HK-021(u)); it is quoted from the harness, not assumed.
- 🛑 **Out of scope, and no row may be read as speaking to it:** the false-accept rate in
  *signal-present* cycles. It is a different generating process (a real signal is present to
  false-alarm off), its "unmatched" population is contaminated by matcher-join misses, and this arm
  measures none of it.

---

## 2. What QA builds

A single offline harness, `qa/rr-study/awgn_fp_replay.py` (or the equivalent under
`tests/OpenWSFZ.Ft8.Tests/` if the C# seam proves the shorter path — QA's call, HK-015):

1. Render N signal-free AWGN slots via the study's own `siggen.py`/`channel.py` noise path at the
   part-0 and part-1 `level_dbfs`, from seeds. **Reuse the shipped generator; do not write a second
   noise source** — a divergent generator would make every number unfalsifiable.
2. Decode each slot through the shipped `libft8.dll` at the pinned SHA256 (§5 ROW 0a).
3. For every emitted decode, record: `message_text`, `reported_snr_db`, `dt`, `freq`, **and the
   `signal_db` / `local_noise_db` pair from `GetLastSnrTerms`**.
4. Emit one row per decode and one row per slot, so both the per-slot event rate and the per-decode
   terms are recoverable without a re-run.

🔴 **HK-021(p): pre-register the build.** The binary under test is pinned by SHA256 before the first
reading, and every row below is void if that pin does not hold for the whole run.

---

## 3. The measurement

| # | Quantity | How |
|---|---|---|
| M1 | Per-slot false-accept event rate, part 0 and part 1 **separately** | fraction of slots emitting ≥ 1 decode, N ≥ 2,000 per part |
| M2 | `signal_db − local_noise_db` for every false accept | `GetLastSnrTerms`, per decode |
| M3 | The same quantity for **genuine** decodes | replay S1/S4's own seeded signal-present slots through the identical harness |
| M4 | Reported-SNR distribution of false accepts | histogram, 1 dB bins |

M3 is not optional garnish: **without it there is no complement, and the separation claim is
unfalsifiable** (HK-021(t)).

---

## 4. Pre-registered gate

### ROW 0 — instrument validity. Any one fires ⇒ STOP, report the failure, take no reading.

- **0a — binary identity.** SHA256 of the `libft8.dll` under test equals the pinned manifest value.
  A `FT8_SHIM_VERSION` string is **not** an identity (standing rule).
- **0b — the anchor.** Replay **this sweep's own 60 S5 seeds** offline. The offline harness must
  emit **2 ≤ events ≤ 10** across those 60 slots. The in-chain reading was 4; the band is the exact
  Poisson 95% interval for k=4, `[1.09, 10.24]`, taken to whole events — computed, not hand-typed,
  and pre-registered here so it cannot be widened after the fact.
  **Outside that band, the offline instrument does not reproduce the in-chain phenomenon and no
  N=2,000 number may be quoted from it.**
- **0c — level dependence.** Repeat 0b's 60 slots at the rendered level ±10 dB. If the event count
  moves by more than the same Poisson band, the instrument is **level-dependent**, its absolute rate
  does not transfer to the in-chain gate, and ROW 1 is **downgraded to relative-only** (comparisons
  between builds stay valid; absolute rates do not). This is the arm's single biggest validity risk:
  the in-chain audio passes through Voicemeeter and capture gain, and the offline path does not.
- **0d — the complement exists.** M3 returns ≥ 200 genuine decodes. A separation claim with no
  measured complement is decoration (HK-022's drafting question).

### ROW 1 — the rate is chronic, not a recent regression
**Fires iff** M1 (parts 0/1 pooled, N ≥ 4,000) lands inside **[1.15%, 3.85%]** — the exact
Clopper–Pearson 95% interval for the pooled in-chain S5 rate over **every full sweep since
2026-08-21**, named so the set cannot be reselected after the reading:
`7d36038` 1/120 · `f5dec23` 4/120 · `22b749c` 0/60 · `872ba65` 1/60 · `2e60949` 2/120 ·
`3b52608` 4/60 ⇒ **12 / 540 = 2.22%**.
⇒ The gate's PASS/FAIL history is binomial noise on a stable underlying rate, **QA's "worst reading
yet" is a point estimate not a trend**, and the S5 gate at N=60 is underpowered for its own purpose.
**Consequence, asserted now:** recommend to the PO that the §10 gate's N be re-derived, or that the
gate be read against this offline estimator.

### ROW 2 — the separation is real and mechanistic
**Fires iff** the maximum `signal_db − local_noise_db` over all false accepts (M2) is **strictly
below** the 1st percentile of the same quantity over genuine decodes (M3).
⇒ An emission-side plausibility floor is **sizeable and cheap**, and — because it is expressed in
the raw terms, not in the derived `snr` — it is **immune to the `20260046` SNR-scale change** that
makes §0.2's discriminant circular.
🔴 **This fires a SIZING, never a ship decision.** Any actual filter is a `src/` change ⇒ HK-011 in
full: QA authors the `dev-tasks/*.md` and stops.

### ROW 3 — the separation does not hold
**Fires iff** the two distributions of M2 overlap at all.
⇒ **The emission-filter route is dead on this evidence and is not to be re-proposed without a new
pre-registration.** Say so plainly; do not soften it into "needs more data."

### ROW 4 — anything else
Report the numbers, fire no conclusion. **A row that does not fire is not a licence to narrate.**

🔴 **What no row lifts.** None of ROW 1–3 may be read as a verdict on `s_k_min_score_pass2`,
candidate budgets, passes, or LDPC iteration count. That family is closed twice (§0.3). If the data
implicate it, that is a finding to *report*, and it earns its own pre-registration — never a change
on this arm's rows.

---

## 5. What QA does, in order

1. Pin the binary (ROW 0a). Author the harness (§2). **Do not touch `src/` or `native/`.**
2. Run ROW 0b, then 0c, then 0d. **Stop on any failure and report it** — a failed ROW 0 is a
   complete, publishable result, not a wasted run.
3. Only then: N ≥ 2,000 per part, M1–M4.
4. Evaluate ROW 1–3 mechanically. Report per HK-001.
5. 🔴 **HK-025 stands: if any row here is not mechanically decidable from its own data, QA may
   refuse to run it and say so.** Classify (validity vs precision), evaluate both branches, and if
   the same row results either way, it is diagnostic and must be refused rather than run.

---

## 6. Standing bars this arm does not lift

- The S7 P2 3-stack limit, Station F / `F-NBR-A` / `NBR-A`, and the S7 gap band remain exactly as
  closed. This arm touches none of them.
- No claim about the **in-chain** rate may be made from offline numbers if ROW 0c downgrades the
  instrument.
- 🛑 Efficacy of any resulting filter against **real off-air** false accepts is not measurable here
  and must not be implied. This arm measures a synthetic AWGN population only.
