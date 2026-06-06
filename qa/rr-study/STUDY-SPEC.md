# OpenWSFZ ↔ WSJT-X Decoder Measurement System Analysis (Gage R&R)

**Document type:** Study specification & harness blueprint (Architect deliverable)
**Owner of execution & reporting:** QA
**Status:** **Ratified** by the Captain 2026-06-05 — §7 tolerances, §10 thresholds, Python analysis, and synthesiser-first build all approved. Harness build underway.
**Applies to:** OpenWSFZ FT8 receive/decode pipeline, measured against WSJT-X as a co-appraiser
**Last updated:** 2026-06-05

---

## 0. Decisions ratified by the Product Owner

| # | Decision | Choice |
|---|---|---|
| D1 | Primary reference | **Synthesized ground truth** (not WSJT-X, not app-vs-app only) |
| D2 | Signal synthesis | **Independent clean-room FT8 synthesizer** inside the harness |
| D3 | %GR&R basis | **Defined tolerance bands** (see §7), reported as %Tolerance |
| D4 | Next artefact | This full spec + harness blueprint |
| D5 | Tolerance bands (§7) & acceptance thresholds (§10) | **Ratified as proposed** (2026-06-05) |
| D6 | Analysis tooling (§9, §11) | **Python (pandas/matplotlib)**; Minitab optional manual cross-check |
| D7 | First-study platform (§4) | **Windows + VB-CABLE** (installed; see `RUNBOOK.md`) |
| D8 | Harness build order (§12) | **Synthesiser first**, gated by §5 self-validation, with encode unit tests |

---

## 1. Purpose

Replace the single scalar "recovery rate vs WSJT-X" parity number with a repeatable,
regression-trackable Measurement System Analysis (MSA) that:

1. Quantifies how **consistently** OpenWSFZ and WSJT-X measure the same received signals
   (Gage R&R on SNR, DT, audio frequency).
2. Quantifies how **accurately** each application measures against known truth
   (Bias & Linearity).
3. Quantifies decode **classification agreement** — recovery and false positives —
   against known truth and between applications (Attribute Agreement Analysis / Kappa).
4. Produces Minitab-style tables and plots committed to the repository, so that
   improvement or regression after any OpenWSFZ code change is visible at a glance.

The routine is **black-box and fully decoupled** from OpenWSFZ source: it shares no
assemblies, no P/Invoke, and is not referenced by `OpenWSFZ.slnx`. It interacts only with
(a) a shared audio device and (b) the two applications' `ALL.TXT` log files.

---

## 2. Why this design (the two corrections that make R&R valid)

### 2.1 Repeatability must be non-zero — inject noise, not files
A deterministic decoder fed a bit-identical WAV returns a bit-identical answer; repeatability
variance would be 0 and %GR&R meaningless. Therefore:

> **Each trial is an independent additive-noise realization at the part's nominal signal
> condition.** The generator renders the same message at the same true SNR/DT/frequency but
> draws a fresh, seeded noise instance per trial, plays it into the shared device, and **both
> applications capture that identical realization concurrently.** The next trial draws new noise.

Repeatability then measures each decoder's sensitivity to the random band noise it will face in
service — a physically meaningful quantity — and the shared-device requirement becomes
load-bearing (both apps must hear the *same* realization each trial for a properly crossed design).

### 2.2 Anchor to synthesized truth, not to WSJT-X
Because the harness synthesizes the signals it knows true SNR, DT, audio frequency, and message
text exactly. WSJT-X is a *co-appraiser*, not the gold standard (it has its own measurement error
and a quantized, clamped SNR scale). All accuracy metrics reference injected truth.

---

## 3. MSA vocabulary → FT8 domain

| MSA term | This study |
|---|---|
| Part | A synthesized signal **condition** with known truth (specific SNR / DT / freq / message). |
| Appraiser | The **application**: WSJT-X and OpenWSFZ. (The human only selects the device.) |
| Trial | An independent seeded noise realization of the part, captured by both apps concurrently. |
| Measurement (continuous) | Reported SNR (dB), DT (s), audio frequency (Hz) of matched decodes. |
| Measurement (attribute) | Decoded / not-decoded per candidate message; false positive on noise slots. |
| Gold standard | Injected truth from the generator. |

---

## 4. Test rig

### 4.1 Topology
```
 ┌──────────────────────────┐
 │  Signal generator (harness) │  synthesizes FT8 + seeded noise, aligned to 15 s UTC cycle
 └────────────┬─────────────┘
              │ plays PCM (mono, 48 kHz, shared mode)
              ▼
   ┌─────────────────────────┐
   │  Shared audio device     │  VB-CABLE (virtual) — render side = "CABLE Input"
   │  (operator-selected)     │  capture side = "CABLE Output"
   └───────┬─────────┬───────┘
           │         │  both apps open the capture endpoint in WASAPI shared mode
   ┌───────▼───┐ ┌───▼────────┐
   │  WSJT-X    │ │ OpenWSFZ   │   FT8 mode, Monitor ON, same nominal dial freq
   │  ALL.TXT   │ │ ALL.TXT    │
   └───────┬───┘ └───┬────────┘
           └────┬────┘
                ▼
   ┌─────────────────────────┐
   │  Matcher + analyser       │  joins truth ↔ WSJT-X ↔ OpenWSFZ; emits CSV + report
   └─────────────────────────┘
```

### 4.2 Setup requirements (operator runbook, abridged)
- Install a virtual audio cable (Windows: **VB-CABLE**; Linux: PulseAudio `module-null-sink` +
  `loopback`; macOS: **BlackHole**). Both apps select its **capture** endpoint as their input.
- WSJT-X: mode **FT8**, **Monitor ON**, audio input = shared device, `ALL.TXT` location noted.
- OpenWSFZ: audio device = shared device, decode started, `decodeLog.enabled = true`.
- Nominal dial frequency identical in both (e.g. 7.074) so log lines align; the value is cosmetic
  for the study since matching keys on audio freq + message + cycle.
- A real **analog loopback** (line-out → line-in) is an optional external-validity variant; the
  default is the virtual cable because the intended variation is injected in software (§2.1).

> **Concurrency note:** WASAPI shared mode permits multiple capture clients on one endpoint, so
> both apps capture the same stream simultaneously. Verify once during bring-up.

---

## 5. Independent FT8 signal synthesizer (D2)

A standalone module in the harness, **clean-room from the public FT8 protocol description**
(Franke/Somerville/Taylor, *"The FT4 and FT8 Communication Protocols"*). It MUST NOT reuse
OpenWSFZ or ft8_lib code — a shared bug must not be able to mask a decode defect.

Pipeline: standard-message text → 77-bit payload (callsign/grid packing) → 14-bit CRC →
LDPC(174,91) parity → Gray-coded 8-FSK symbols (58 data + three 7×7 Costas arrays at symbol
indices 0/36/72 = 79 symbols) → GFSK modulation, tone spacing 6.25 Hz, symbol period 0.16 s,
total 12.64 s placed within the 15 s slot at the part's DT offset and audio frequency.

Then: scale to target SNR relative to a generated noise floor referenced to a 2500 Hz bandwidth
(WSJT-X convention), add the seeded noise realization, render PCM.

**Self-validation gate:** before any study run, confirm WSJT-X decodes a clean (+10 dB) rendering
of every message used. If WSJT-X cannot decode the synthesizer's own output, the vectors are
invalid and the run aborts. This also independently proves the synthesizer's correctness.

---

## 6. Scenarios (parts design)

Continuous studies use one response variable each (clean separation). All use
**10 parts × 2 appraisers × 3 trials** unless noted; attribute studies use ≥ 50 instances.

| ID | Drives | Parts (10 unless noted) | Trials | Output |
|---|---|---|---|---|
| **S1 SNR ladder** | SNR R&R + Bias/Linearity | true SNR ∈ {−24,−21,−18,−15,−12,−9,−6,−3,0,+3} dB; fixed freq=1500 Hz, DT=0.2 s, one message | 3 | SNR Gage R&R; SNR bias & linearity |
| **S2 Frequency sweep** | Frequency R&R | audio freq ∈ {300,567,834,…,2700} Hz; fixed SNR=0 dB | 3 | Frequency Gage R&R |
| **S3 DT offset** | DT R&R | DT ∈ {0.0,+0.3,…,+2.7} s (10 steps, positive only — redesigned 2026-06-06 per R&R-003); fixed SNR=0 dB; WSJT-X DT corrected +0.55 s (convention offset) | 3 | DT Gage R&R |
| **S3b Negative-DT boundary** | Decode rate vs DT < 0 | DT ∈ {0.0,−0.3,…,−2.7} s (10 steps, negative sweep); fixed SNR=0 dB (companion to S3; attribute, not GR&R) | 3 | Per-DT decode rate per appraiser; informational |
| **S4 Density / QRM** | Attribute agreement | cycles with N∈{1,5,10,20,30} simultaneous signals at mixed SNRs; ≥ 50 message instances total | 3 | Recovery Kappa (vs truth & between apps) |
| **S5 Noise / birdies** | False positives | signal-free cycles: white noise, pink noise, steady carriers/birdies | 3 | False-positive rate & agreement |
| **S6 Off-air corpus** *(optional, not yet built)* | External validity | replay the committed 40 m fixture recordings through the device | 1 | Cross-check vs live p15 recovery metric |
| **S7 Compounding / co-channel** | Per-message recovery under overlap | 4 overlap families × 3 trials: co-channel stacks; near-collision Δf∈{3,6,12,25,50} Hz; time+freq stagger Δt∈{0.5,1.0,2.0} s; capture-ratio pairs | 3 | Per-message recovery, capture split, between-app agreement |

Replays/trials are seeded: `seed = hash(scenario, part_index, trial_index)` → byte-reproducible.

### 6.1 S7 rationale — compounding / co-channel overlap

S4 stresses *band loading*: N signals spread evenly across 300–2700 Hz, so even at N=30 the
50 Hz-wide signals never share a bin (~83 Hz spacing). It therefore never tests the everyday FT8
pileup where multiple stations transmit on the **same** audio frequency and their waveforms
physically **compound** into one overlapping signal. S7 fills that gap: each part lists explicit
per-signal `(msg_id, freq_hz, dt_s, snr_db)`. The harness models a **single receiver**: each station
is rendered clean, scaled by its relative SNR (`amp = 10^(snr_db/20)`, so `snr_db` sets station
**strength** against the floor), the stations are summed, and **one shared band-noise floor** is added
once for the whole slot (`channel.mix_to_shared_floor`). This matters for fidelity: an N-stack must
not carry N independent noise floors, and a capture pair (e.g. `0 / -10 dB`) must actually differ in
level or the capture-split deliverable measures nothing. **One truth row is logged per signal** (its
`true_snr_db` is that station's strength vs the shared floor) so the existing matcher scores each
compounded message independently. This yields genuine per-message recovery (matched / injected) — the
metric the S4/S5 attribute-Kappa path cannot produce, because its truth label has only the single
class "injected" and Cohen's κ is undefined on one class.

> **Note (shared-floor convention).** S4 density uses the same single-floor mixer: its `N` stations are
> spread across 300–2700 Hz, scaled by their per-station SNR, and summed over one floor. Earlier runs
> used a per-signal-noise convention (each station carried its own floor and all stations were rendered
> at equal amplitude regardless of `snr_db`); that inflated the floor ∝ N and erased capture ratios, and
> is superseded by this section. Runs predating the shared-floor mixer are not comparable to later ones.

Co-channel separation has no AIAG tolerance, so S7 is reported as an **informational** recovery
table (per overlap family, per part, capture strong-vs-weak split, and between-app agreement); it
does not contribute a PASS/FAIL verdict to the regression gate.

---

## 7. Tolerance bands (D3)

%Tolerance uses ±halfband as the spec half-width.

| Response | Tolerance (± half-width) | Rationale |
|---|---|---|
| SNR | **± 5 dB** | Revised 2026-06-06 after Run 1 (see note below). |
| Audio frequency | **± 4 Hz** | ≈ ⅔ of the 6.25 Hz FT8 tone bin; both apps report integer Hz. |
| DT | **± 0.2 s** | One `dt` display tick; within FT8's sync tolerance. |

> **SNR tolerance revision note (2026-06-06, ratified by Captain).**
> The original ±2 dB band was set on the assumption that WSJT-X integer quantization was the
> dominant SNR uncertainty.  Run 1 (SHA `46d7f6a`) showed that it is not: the dominant source
> is **finite-sample noise-floor estimation variance** — each trial draws a fresh noise
> realization, giving a different noise floor estimate and therefore a different measured SNR.
> The ANOVA Reproducibility was 0% (both apps agree exactly for the same realization) while
> Repeatability was 44.8% (trial-to-trial jitter σ ≈ 8.4 dB).  This is a property of the FT8
> protocol, not of either application.  The revised ±5 dB band reflects empirical FT8 community
> consensus (SNR reports vary ±3–4 dB in practice) and is consistent with what both apps can
> achieve.  The SNR bias gate (§10) is tightened to ≤ ±2 dB to retain a meaningful accuracy
> specification independent of the GR&R band.

Attribute target (a message is "decoded" if it appears with correct text and audio freq within ±4 Hz
in the matched cycle).

---

## 8. Decode matcher

The technical core. Joins three sources per cycle — **truth**, **WSJT-X ALL.TXT**, **OpenWSFZ ALL.TXT** —
and tolerates the differences between the two writers.

- **Cycle key:** UTC 15 s slot. Normalize both timestamps to the slot start (tolerate ±1 s skew).
- **Message key:** exact decoded text after whitespace normalization.
- **Frequency key:** audio offset within ± 4 Hz.
- A row matches truth when message text matches and audio freq within band; SNR/DT/freq are then
  paired for continuous analysis.
- Unmatched truth rows = misses (attribute). Decodes matching no truth row = false positives.
- Output: a tidy long-format CSV — one row per (scenario, part, trial, appraiser, truth-message)
  with columns for matched? / reported SNR / DT / freq / true values.

---

## 9. Analysis & outputs (Minitab-style)

Implemented in **Python** (pandas; ANOVA-method Gage R&R; matplotlib) so the report regenerates in
CI and is replayable. Minitab remains available as an optional manual cross-check.

### 9.1 Continuous Gage R&R (S1–S3)
- Variance-components table: Repeatability, Reproducibility (+ App×Part interaction), Part-to-Part, Total.
- `%Contribution`, `%Study Var`, **`%Tolerance`** (§7), and **ndc**.
- Six-panel report: Components of Variation · R-chart by app · Xbar-chart by app ·
  Measurement-by-Part · Measurement-by-App · App×Part interaction.

### 9.2 Bias & Linearity (S1)
- Per-app (measured − true) across the SNR ladder; bias, %linearity, constant-vs-drifting bias.
- Headline: any systematic OpenWSFZ-vs-WSJT-X SNR offset.

### 9.3 Attribute Agreement (S4–S5)
- Within-app agreement (decode-decision repeatability across realizations).
- Between-app agreement; each-app-vs-truth agreement with **Kappa** + CIs.
- False-positive rate from S5.

> **κ pooling correction (2026-06-06).** κ vs truth is undefined on a single-class
> truth vector, so the original per-scenario implementation returned NaN for every
> attribute cell (S4 is all-positive; S5 was mislabelled positive). It is replaced
> by a **pooled** confusion matrix: **S4 injected messages = positives**, **S5
> signal-free slots = negatives**, scored one decision per realization. This makes
> κ vs truth, between-app κ, and within-app repeatability well-defined and folds
> sensitivity (recovery) and specificity (FP rejection) into one measure. **The
> pooled attribute κ is currently reported as *advisory* and does not drive the
> overall verdict** (see §10) pending Captain ratification of the pooled method and
> of restricting the positive population to decodable SNRs (cf. the §16 S1 redesign
> note) so κ measures agreement rather than decode probability. **Tracked: R&R-002
> (GitHub #34).**

---

## 10. Acceptance thresholds (regression gate)

AIAG conventions, for ratification:

| Metric | Acceptable | Marginal | Unacceptable |
|---|---|---|---|
| %GR&R (per response) | < 10% | 10–30% | > 30% |
| ndc | ≥ 5 | — | < 2 |
| Attribute Kappa (vs truth, between apps) | ≥ 0.90 | 0.70–0.90 | < 0.70 |
| False-positive rate | ≤ 6% | — | > 6% |
| SNR bias (OpenWSFZ vs truth) | ≤ ±2 dB mean AND slope ≤ 0.1 | — | mean > ±2 dB OR slope > 0.1 |

Evaluated every run; a regression past these bands raises a defect for the Developer.

> **Attribute Kappa gate status (2026-06-06): advisory.** Following the §9.3 κ
> pooling correction, the attribute-Kappa row is computed and reported but **does
> not contribute to the overall PASS/FAIL verdict** until the pooled method (and a
> decodable-SNR positive population) is ratified. %GR&R, ndc, FP rate, and SNR bias
> remain hard gates. **Tracked: R&R-002 (GitHub #34).**

---

## 11. Repeatability of the routine itself

- Deterministic seeds → byte-reproducible test vectors and noise realizations.
- Pin and record the **WSJT-X version** and the **OpenWSFZ git SHA** in every report header.
- Document audio routing and app settings in the runbook; scripted launch where possible.
- One command regenerates the full report from raw logs.

---

## 12. Deliverable layout (committed to GitHub)

```
qa/rr-study/
  STUDY-SPEC.md          ← this document
  RUNBOOK.md             ← step-by-step operator setup & run procedure
  synth/                 ← independent FT8 synthesizer (clean-room)
  harness/               ← generator driver, log matcher, analysis (Python)
  scenarios/             ← scenario parameter files (versioned)
  results/
    <YYYY-MM-DD>-<sha>/
      report.md          ← Minitab-style tables + embedded plots
      *.csv              ← raw matched data + variance components
      *.png              ← six-panel + bias/linearity + attribute plots
  trend.csv              ← one row per run: sha, %GR&R_SNR, ndc, bias_SNR,
                           recovery_Kappa, FP_rate  → improvement/regression chart
```

`qa/` is **excluded from `OpenWSFZ.slnx`**; the harness has its own toolchain.

---

## 13. Roles & workflow

| Role | Responsibility |
|---|---|
| **Architect** | Owns this design and the thresholds (§7, §10). Signs off; does not run the study. |
| **QA** | **Owns execution, analysis, and the published report.** Runs each cycle, files regressions. |
| **Developer** | Downstream: receives regressions as defects and remediates; does not own the instrument. |

Run cadence: on demand before/after any change touching the decoder, audio pipeline, or SNR
calibration; and as a release gate.

---

## 14. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Virtual cable is sample-exact → low repeatability | Variation is injected as seeded noise per trial (§2.1), not relied on from the cable. |
| WSJT-X SNR quantization/clamping shows as discretization | Expected and reported as-is; not a harness bug. Bias study interprets it. |
| Concurrent capture unsupported on a platform | Verified at bring-up; fall back to two synchronized sequential runs of the identical seeded vector. |
| Independent synthesizer has an encoding bug | §5 self-validation gate: WSJT-X must decode every clean vector or the run aborts. |
| "No natural tolerance" for SNR | Defined bands (§7), ratified by Product Owner; %Study Var reported alongside. |
| Cycle/timestamp skew between the two writers | Matcher normalizes to slot start with ±1 s tolerance (§8). |

---

## 15. Open items — RESOLVED

All design questions have been ruled on by the Captain.

1. ~~Ratify tolerance bands (§7) and acceptance thresholds (§10).~~ → **Ratified as proposed 2026-06-05.**
2. ~~Confirm Python for analysis.~~ → **Python (pandas/matplotlib);** Minitab optional.
3. ~~Confirm target platform(s).~~ → **Windows + VB-CABLE** (installed; `RUNBOOK.md`).
4. ~~Approve build of the harness.~~ → **Approved; synthesiser first.**
5. ~~SNR tolerance ±2 dB vs physical limits of FT8 SNR estimation.~~ → **±5 dB ratified 2026-06-06 (see §7 note).**

---

## 16. Study run history

| Date | SHA | Overall | %GR&R SNR | ndc SNR | OWSFZ Bias | FP rate | Notes |
|---|---|---|---|---|---|---|---|
| 2026-06-06 | `46d7f6a` | ❌ FAIL | 44.8% | 1 | −1.96 dB / slope 0.512 | 0.0% | First live run. S1 fails old ±2 dB tolerance (see §7 revision). R&R-001 raised for SNR slope. S2 freq measurement excellent. S3 DT marginal. |

### S1 redesign recommendation (next run)
Restrict the S1 SNR ladder to levels ≥ −12 dB (where both apps decode reliably) to eliminate
selection bias from threshold misses.  Add a companion decode-rate study (attribute) covering
−24 to −15 dB, cleanly separating measurement variance from decode probability.

### S3 redesign — R&R-003 (GitHub #1) — **IMPLEMENTED 2026-06-06**

The S3 GR&R failure (%GR&R = 51.7%, ndc = 1) had two distinct root causes, neither of which
was fundamental measurement noise:

1. **OpenWSFZ cannot measure negative DT offsets.**  For signals with true DT < 0 s, OpenWSFZ
   still decodes the message but reports DT ≈ 0 regardless of the true value (at true DT = −2.0 s
   the bias is +1.97 s).  Including these parts inflated the App × Part interaction with a decoder
   capability boundary, not measurement noise.

2. **WSJT-X has a ~−0.55 s systematic DT convention offset.**  WSJT-X defines DT relative to
   the FT8 nominal TX start (≈ 0.5–1.0 s into the slot) while the harness uses the UTC slot
   boundary (DT = 0).  This produced a ~−0.55 s offset in all WSJT-X DT reports and dominated
   the SS_appraiser term in the ANOVA, attributing a calibration artefact to Reproducibility error.

**Changes implemented** (branch `fix/rr-003-s3-dt-redesign`, closes GitHub #1):

- **`scenarios/s3-dt-offset.json`** — Parts replaced: DT ∈ {0.0, +0.3, …, +2.7} s (10 positive
  steps, 0.3 s resolution, covering the reliable decode window of both apps). Added
  `wsjt_dt_correction_s: 0.55` field; the analyser reads this and adds +0.55 s to WSJT-X
  `reported_dt_s` before ANOVA so SS_appraiser captures genuine measurement disagreement, not a
  convention mismatch. Raw matched-CSV values are unaltered.

- **`scenarios/s3b-dt-boundary.json`** (new) — Companion attribute scenario: DT ∈ {0.0, −0.3,
  …, −2.7} s (10 negative steps). Measures *decode rate* (did it decode?) not DT precision. Cleanly
  separates "does it decode early-starting signals?" from "does it report DT accurately?".
  `analysis: "attribute_decode_rate"` — the analyser renders a per-DT decode-rate table and chart.

- **`harness/analyse.py`** — `_apply_wsjt_dt_correction()` helper added; S3 path in `main()`
  applies the correction when `wsjt_dt_correction_s` is present in the scenario JSON.
  `_analyse_decode_rate()` and `_decode_rate_report_lines()` added for S3b. S7 path updated to use
  scenario meta loaded at start of `main()`.

The DT GR&R is expected to improve substantially on the next run; the within-cell repeatability
(σ ≈ 0.10–0.14 s per appraiser from run aa053a9) is physically meaningful and is the residual
noise once the two artificial inflation sources are removed.
