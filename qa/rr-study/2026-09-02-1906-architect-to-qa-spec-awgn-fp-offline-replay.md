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
🛑 **SUPERSEDED BY AMENDMENT 1 (see end of file). Retained as pre-registration provenance — do not execute this version.**
**Fires iff** the maximum `signal_db − local_noise_db` over all false accepts (M2) is **strictly
below** the 1st percentile of the same quantity over genuine decodes (M3).
⇒ An emission-side plausibility floor is **sizeable and cheap**, and — because it is expressed in
the raw terms, not in the derived `snr` — it is **immune to the `20260046` SNR-scale change** that
makes §0.2's discriminant circular.
🔴 **This fires a SIZING, never a ship decision.** Any actual filter is a `src/` change ⇒ HK-011 in
full: QA authors the `dev-tasks/*.md` and stops.

### ROW 3 — the separation does not hold
🛑 **SUPERSEDED BY AMENDMENT 1 (see end of file). Retained as pre-registration provenance — do not execute this version.**
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

---

## Amendment 1 — 2026-09-02 20:05Z, BEFORE M1–M4 RUNS

**Made by the Architect after ROW 0 passed and before any M-row was measured.** §0–§6 above are the
original pre-registration and are **not edited** — this amendment supersedes ROW 2 and ROW 3 only,
and the superseded text stays above as provenance.

Two things changed: I found a drafting fault in my own ROW 2/ROW 3 pair, and I de-blinded myself
against a related population while auditing the ROW 0 result directory. Both are disclosed here.

### A1.0 🔴 DISCLOSURE — I have seen data adjacent to this arm's headline, and it anchors the new thresholds

While running the NFR-021 redaction pass over the ROW 0 output I audited
`row0d_s1_complement_decodes.csv` and computed, on **signal-present S1** slots, the excess
distribution for truth-matching vs non-matching decodes and a sweep of emission-cut thresholds.
The numbers are in the ROW 0 report §7.3, labelled exploratory, no row.

**Consequences, stated rather than buried:**

- 🛑 **Architect prediction-scoring is SUSPENDED for ROW 2/ROW 3 of this arm.** I have seen a
  closely-related separation and cannot make a blind directional call.
- 🔴 The two thresholds introduced below (**6 dB margin**, **10% removal**) are **anchored on that
  exploratory reading** — a ~15 dB observed margin and a 23–30% observed removal. They are set to
  be clearly clearable by what I saw, but not trivially so. That is a judgement calibrated on
  peeked data, and it is a real cost of my having looked. A reader who wants an unanchored gate
  should reject these numbers and set their own before QA runs.
- ✅ What I have **not** seen: any S5 noise-only M1/M2/M4 result. The population this arm's headline
  ranges over is untouched. §7.3 is signal-present S1.

### A1.1 The fault in the superseded ROW 2 / ROW 3

ROW 2 fired only on **disjointness** (max false-accept excess strictly below the 1st percentile of
genuine excess), and ROW 3 fired on "the two distributions overlap at all" with the consequence
*"the emission-filter route is dead on this evidence and is not to be re-proposed."*

Disjointness is the wrong property. **An emission filter does not need the distributions to be
disjoint — it needs a threshold at which the cost is acceptable.** A spurious decode with a large
excess and a genuine decode with a small one can coexist while a low cut still removes a useful
share of the former at zero cost to the latter. As drafted:

- ROW 3 would fire on any overlap, however far above the useful threshold it sits, and would
  **permanently close a route the same data shows to be live and quantified.**
- ROW 3's consequence also over-ranges its population (HK-021(x)): it says "dead", unqualified,
  from a measurement made entirely on noise-only slots.

### A1.2 ROW 2 (revised) — a threshold with a margin exists

**Fires iff there exists a threshold `T ≥ 0 dB` on `excess = signal_db − local_noise_db` such that
all three hold:**

| | condition | why this and not something else |
|---|---|---|
| (a) | **zero** M3 genuine decodes have `excess ≤ T` | the cut must be free on the measured complement, not merely cheap |
| (b) | `percentile_1(M3 excess) − T ≥ 6.0 dB` | a bare zero-count is a readout artefact at finite n; the margin is what makes it robust. 6 dB = 2× in amplitude, and **less than half** the exploratory margin — see A1.0 |
| (c) | **≥ 10%** of M2 false accepts have `excess ≤ T` | below this the filter cannot justify a `src/` change and an ABI bump |

⇒ **An emission-side plausibility floor is sizeable and cheap. Report `T`, the removal fraction at
`T`, and the margin.** 🔴 Still a **SIZING, never a ship decision** — any actual filter is a `src/`
change ⇒ HK-011 in full: QA authors the `dev-tasks/*.md` and stops.

**Power, at my own stated expectation (HK-021(v)):** with M3 at n ≥ 2,000 genuine decodes the
readout quantum on condition (a) is 1/2,000 = 0.05%, so a clean zero bounds the true loss rate at
**95% UB ≈ 0.15%** (rule of three). That is the strongest statement (a) can support and it must be
quoted that way — **never as "costs nothing"**. Condition (b) carries the robustness that (a)
cannot at this n; this is why the margin term exists rather than a tighter count threshold I could
not resolve.

### A1.3 ROW 3 (revised) — no such threshold exists

**Fires iff no `T ≥ 0 dB` satisfies (a), (b) and (c) simultaneously.**

⇒ **The emission-filter route is unfavourable *for S5-class noise-only false accepts at the levels
this harness delivers*, and is not to be re-proposed for that population without a new
pre-registration.** Say it plainly — do not soften it to "needs more data."

🔴 **Scope it exactly that way and no wider (HK-021(x)).** This arm measures noise-only slots. It
may not close the route for signal-present spurious decodes, for real off-air conditions, or for
any threshold family other than a floor on `excess`.

### A1.4 Rows remain mutually exclusive and exhaustive

Revised ROW 2 and revised ROW 3 are exact complements by construction ("a valid `T` exists" /
"none does"), so exactly one fires. ROW 4 ("anything else") is now **unreachable for the M2/M3
separation question** and is retained only for M1/M4 outcomes that fire no rate row. Note this in
the report rather than silently leaving a dead row.

### A1.5 One addition to M3

M3 must record, alongside each genuine decode's excess, **whether its message text matches the
injected truth for its own `(part, trial)` slot**. ROW 0d's original "336 genuine decodes" conflated
250 truth-matching decodes with 86 spurious ones riding alongside real signal (ROW 0 report §7.2);
without the match flag, M3's "genuine" population would inherit exactly that contamination — and
since the spurious rows sit at the **low** end of the excess distribution, they would poison
condition (a) directly and force a false ROW 3. **This is the single most load-bearing line in the
amendment.**

---

# AMENDMENT 2 — 2026-09-03 16:16Z: post-result corrections to THIS SPEC's own defects

**Written after reading QA's M1–M4 report (2026-09-03 15:35Z). It corrects three things in the
spec above, none of them QA's.** ROW 2's verdict is **not** disturbed: it fired on its own
pre-registered text, evaluated correctly, and the arm is complete. What is corrected is (A2.1) the
ROW 1 comparator's arithmetic, (A2.2) a claim in ROW 0c about *where* the offline/in-chain risk
lives, and (A2.3) the reading that ROW 2's `T` is a shippable number. A2.4 orders one record
correction in QA's report.

## A2.1 🔴 ROW 1's pre-registered band mixes two different denominators — the Architect's error

§4 ROW 1 names its six-sweep set as `7d36038` 1/**120** · `f5dec23` 4/**120** · `22b749c` 0/**60** ·
`872ba65` 1/**60** · `2e60949` 2/**120** · `3b52608` 4/**60** ⇒ 12/540 = 2.22%.

**Three of those denominators are not the AWGN population.** `s5-noise.json` has four parts × 30
trials = 120 slots, of which **only parts 0/1 are AWGN**; parts 2/3 are carrier and multi-carrier —
confirmed by the `S5-LEVEL` report's own exhaustive ROW 0f enumeration, not by inference. The
offline arm measured **parts 0/1 only**. ⇒ The band was built on a denominator that is 2× too large
for half its members, and it is therefore **not the like-for-like comparator this spec claimed**.

✅ **Corrected comparator, stated so it cannot be reselected later:** on a consistent 60-slot AWGN
denominator the pooled in-chain figure is **12/360 = 3.33%**, not 2.22%. 🔴 **Do not treat 3.33% as
ratified either** — it is a *re-arithmetic of the same rows*, and A2.1 does not establish that each
numerator counted only parts 0/1. **The numerator provenance is now itself a measurement**, and it
is ROW 0m of the follow-up arm (`2026-09-03-1616-architect-to-qa-spec-fp-parity-and-inchain-floor.md`).

**Consequence for the reading, asserted (HK-021(t)):** QA's ROW 1 non-fire **stands** — 10.875% is
outside `[1.15%, 3.85%]` and outside any plausible re-derivation of it. But **the "≈5×" magnitude
does not stand.** Against the corrected denominator it is **≈3.3×**, and the citable form until the
follow-up lands is: *"the offline instrument's own chronic rate is 10.875% [9.93%, 11.88%]; the
in-chain pooled comparator is between 2.22% and 3.33% depending on a denominator defect not yet
resolved; the ratio is therefore between ~3× and ~5× and is not yet quotable as a single number."*

## A2.2 🔴 ROW 0c's stated "biggest validity risk" is wrong about the mechanism — capture *gain* cannot matter

§4 ROW 0c and §0 both name the risk as *"the in-chain audio passes through Voicemeeter and capture
gain, and the offline path does not."* **The gain half of that is impossible**, from source:

- `Ft8Decoder.cs:271` — `float[] normalisedPcm = NormalisePcm(pcm, PcmNormalisationTargetRms)`,
  target RMS **0.20** (`:52`, the D-002 SNR-bias fix), applied to **every** in-chain buffer before
  `DecodeAll` (`:303`).
- ⇒ The in-chain decoder's absolute operating level is **fixed by construction**. Voicemeeter gain,
  capture gain and playback volume are all divided out downstream of themselves. They cannot move
  the in-chain rate at all.
- ⇒ What survives from the real capture path is **spectral colouring, ADC quantisation/dither, and
  downsampling filter response** — never gain. Narrower, and testable.

🔴 **And it exposes a genuine parity defect in this arm's own instrument, in the opposite
direction:** `AwgnFpReplayTests.cs:425` calls `Ft8LibInterop.DecodeAll(pcm)` on **raw WAV samples**,
skipping `NormalisePcm` entirely. At the measured render RMS (−20.87 dBFS ≈ 0.090, `S5-LEVEL` ROW
0g) the offline instrument decodes **≈6.9 dB quieter than any in-chain decode of the same audio**,
with per-slot level variance the in-chain path does not have.
⚠️ **Honest weight:** ROW 0c's own ±10 dB flatness (6/7/7) is evidence *against* this explaining
the rate gap, and the daemon's operating point sits inside the range ROW 0c swept. So this is
ranked as **instrument hygiene that must be fixed before any further absolute-rate reading**, not
as the leading hypothesis. It is ROW 0n of the follow-up arm.

## A2.3 🛑 `T = 9.146 dB` IS NOT A SHIPPABLE THRESHOLD — it cuts into real decodes

ROW 2's `T` was chosen as the tightest value condition (b) allows, which is correct per the
amendment. But translate it onto the axis the decoder reports: `ft8_shim.c:1719` is
`snr = signal_db − local_noise_db − 26.5`, so `excess = snr + 26.5`, and

> **`T = 9.146 dB` is a cut at reported SNR = −17.35 dB.**

The ratified-era **lowest genuine OpenWSFZ decode** recorded in this project is **−17/−18 dB**
(spec §0.1) ⇒ excess **9.5 / 8.5 dB**. ⇒ **A genuine decode at −18 dB is removed by this `T`, and
one at −17 dB survives it by 0.35 dB.**

The reason ROW 2 read that as zero-cost is that M3's weakest genuine decode is excess **14.99 dB =
−11.5 dB reported SNR** — the S1 ladder's floor sits **≈6 dB above** the in-chain genuine floor.
⇒ The "13.4 dB gap at zero cost, 95% UB 0.130%" is a property of a **truncated population**, not of
the decoder (HK-021(x): the falsification population does not range over the claim's population).
🔴 **This is my drafting fault again, not QA's**: condition (b) anchors the margin to `p1(M3)`, a
percentile of whatever ladder M3 happens to contain, with no requirement that the ladder reach the
weakest decode the decoder actually emits.

✅ **The route is not damaged — only the number is.** Every one of the 454 false accepts has excess
≤ **+1.62 dB**, so a cut anywhere from ~2 dB upward removes **100%** of them. The design point must
be anchored to the **mechanism** (a CRC-valid codeword with no excess over the decoder's own noise
estimate cannot be a real signal), not to a margin fitted on a synthetic ladder. Indicative, **not
pre-registered and not a ruling**: `T ≈ 2 dB` removes 454/454 while sitting ≈6.5 dB below the
weakest genuine decode on record.

🛑 **Therefore: no emission-filter dev-task is authored on `T = 9.146`.** PO ruling, 2026-09-03:
**hold the filter dev-task** until the **in-chain genuine excess floor** is measured on the
separate terms — not converted from a reported SNR, since `c3a9ea8` rescaled that axis inside the
very era the −17/−18 dB figure spans. That measurement is ROW 1 of the follow-up arm.

## A2.4 Record correction QA owes on the M1–M4 report (units, not arithmetic)

Report §4 states *"454 false accepts across 4,000 slots (matches M1 exactly …)"*. It does not match:
M1's **435** is a count of **slots with ≥1 decode**
(`AwgnFpReplayTests.cs`: `slots.Count(s => s.Decodes.Count > 0)`); **454** is a count of **decode
rows**. 454 rows over 435 slots. **The rate 10.875% is a per-slot rate and must stay one** — this is
the rows-vs-clusters trap the board already bans (HK-021(i)); an in-chain comparator built by
cycle-dedupe is a *cluster* count and must be compared to 435/4,000, never to 454/4,000.
✅ **ROW 2 is unaffected** — condition (c) is a fraction of the M2 population, 454/454 = 100% either
way. Correct the sentence, add the slot-vs-row distinction to §2's table, and do not restate any
other figure.

## A2.5 Standing disclosure, unchanged

🛑 The Architect remains **de-blinded** on the excess distributions (A1.0). Prediction scoring stays
**suspended** for ROW 2/ROW 3 and is suspended for every threshold number in A2.3 as well.

---

# AMENDMENT 3 — 2026-09-04: the shim bump voided ROW 0a. Two PO rulings, and a new ROW 0r.

## A3.0 What happened, mechanically

`ac6150d` (Developer session, 2026-09-03 17:27Z) added `ft8_get_h12_unresolved_by_code` and rebuilt
the win-x64 and linux-x64 binaries, taking `main` from shim `20260049` to `20260050`. ROW 0a's pin
(`tests/OpenWSFZ.Ft8.Tests/AwgnFpReplayTests.cs:58`, `PinnedShaWinX64`) is therefore **void by
construction**, and `AssertBinaryPin()` gates every other row in the class ⇒ **8 failing tests on
`main`**. The Developer flagged it and left task 5.2 unchecked rather than patching it. Correct call.

🔴 **The defect is structural, not this bump's fault.** An **in-flight measurement arm's run-time
instrument precondition was sited in the always-run xunit suite.** Any legitimate shim bump reds
`main`. It will fire again on the already-queued `20260051`/`20260052` renumber.

## A3.1 RULING 1 (PO, 2026-09-04) — the pin moves behind its trait. It does NOT get re-pinned.

🛑 **Do NOT change `PinnedShaWinX64`'s value.** `ce02c7ba…153e` is the `20260049` identity and it
remains the identity of every already-landed row (M1–M4, ROW 0q, ROW 0m). Re-pinning it would
silently reattribute those results to a binary they were never measured on — the exact failure the
standing rule (*"`FT8_SHIM_VERSION` identifies NOTHING — pin the SHA256"*) exists to prevent.

Mechanical instruction:

1. The class **already carries `[Trait("Category", "AwgnFpReplay")]`** (`AwgnFpReplayTests.cs:46`).
   No new plumbing. Exclude it from the repo's default test invocation **and CI's** with
   `--filter "Category!=AwgnFpReplay"`.
2. The arm's own runs invoke `--filter "Category=AwgnFpReplay"` explicitly. **ROW 0a's semantics are
   unchanged for a measurement run** — it still fires on any binary mismatch, and every row in the
   class is still void if it does not hold for the whole run (HK-021(p)).
3. **Scope bar: `tests/` and test-invocation config only.** Verify `git diff --stat -- src/ native/`
   is empty and **say so in the report**. ⇒ zero `src/`/`native/` diff ⇒ **no HK-011 Developer
   session; QA does this.**

🔴 **HK-022 drafting question — what error can this change NOT detect?** A filtered-out suite is
**silent, not green-with-meaning**: after this change, `main` being green no longer says anything
about whether the arm ever ran. ⇒ **Mitigation, required, not optional:** every future `AWGN-FP` /
`FP-PARITY` result report must quote (a) the exact `--filter` command line used and (b) ROW 0a's own
printed `actual`/`pinned` SHA pair from **that run's** stdout. **A report carrying neither is not a
result** and may not be cited.

## A3.2 RULING 2 (PO, 2026-09-04) — ROW 0r, the carry-forward gate. NEW, pre-registered here.

The already-landed rows were measured on `20260049`. Whether they survive the bump is a
**measurement on the two binaries**, not an argument about the source diff.

🛑 **The "additive export, never called in the decode path" argument may NOT be substituted for this
row.** It is an assertion about source. ROW 0r is evidence about binaries. This deliberately reuses
the **`S5-LEVEL` ROW 0j/0k pattern**, which is already proven on this project (byte-identity failed,
decode-invisibility passed, the change landed **disclosed**).

**Obtaining the `20260049` binary — it must be the real artefact, never a rebuild:**

```
git show 3b52608:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll > <work>/libft8-20260049.dll
```

Then **assert its SHA256 equals `PinnedShaWinX64` before using it.** 🛑 **If that assertion fails,
STOP** — you do not hold the pinned binary and no carry-forward claim of any kind can be made.

**Population:** the arm's own pinned corpus — **every** M1 S5 slot under
`qa/rr-study/awgn-fp-replay/_work/m1m4_s5/`, no sampling, no truncation. ⚠️ Standing trap: do not
reach for any population helper taking a `limit=` (`compute_matched_hit_control` truncates in **file
order**, it does not sample — it was off ≈3.8× in past use).

**Method:** decode every slot twice — once through each binary — in the same process configuration
with the same decode params, and diff the **decode set per slot** (message text, frequency, SNR, DT),
**not** the per-slot count and **not** the aggregate event total.

**FIRES iff any slot's decode set differs between the two binaries.**

- ⇒ **Does not fire:** M1–M4, ROW 0q and ROW 0m **carry forward to `20260050` as DISCLOSED
  carry-forwards.** The report states both SHAs, the slot count, and "decode-identical", and every
  future citation of those rows carries that disclosure. **Landed, not silently — same as
  `S5-LEVEL` Option 2.**
- ⇒ **Fires:** those rows are **void on `20260050`**. Report which slots differ and how many. **They
  are re-run on `20260050` before any of ROW 0n/0o/0p/1/2/3 proceeds.** Do **not** investigate *why*
  they differ — that is a new pre-registration, not a patch to this one.

The two branches are **exact complements**; exactly one fires.

🔴 **HK-022 — what can ROW 0r NOT detect?** The M1 S5 corpus is **noise-only**. ROW 0r therefore
cannot detect a binary difference that appears only on **genuine** signals. ⇒ **The carry-forward
claim is scoped to the false-accept rows only.** **ROW 0d / M3's genuine-decode population is NOT
carried forward by this row.** If ROW 0n/0o or `FP-PARITY` ROW 1 needs M3, **M3's own corpus is
added to ROW 0r's population and that addition is stated** — otherwise the genuine side is an
undisclosed gap.

## A3.3 This will refire — stated once, so it is not rediscovered

The queued `20260051`/`20260052` shim renumber will void the pin again. A3.1 makes that a non-event
for `main`'s greenness; it does **not** make it a non-event for the arm. **ROW 0r is re-run for every
shim bump the arm spans**, against that bump's own predecessor binary, or the arm's rows stop being
attributable. `20260050` is **not** a renumber target (it is L3's, reserved).
