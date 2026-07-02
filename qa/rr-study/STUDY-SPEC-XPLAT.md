# OpenWSFZ Cross-Platform Decoder Gauge R&R Study
## Windows daemon vs Linux/WSL2 daemon vs WSJT-X (three-appraiser design)

**Document type:** Study specification — Measurement System Analysis (MSA)  
**Owner of execution & reporting:** QA  
**Status:** **Active** — pilot two-appraiser run completed 2026-07-01 (see §13); three-appraiser harness implemented 2026-07-02; audio normalization required before production run (D10)  
**Applies to:** OpenWSFZ FT8 receive/decode pipeline, native binary cross-platform parity  
**Companion to:** [`STUDY-SPEC.md`](./STUDY-SPEC.md) (existing Windows-only study)  
**Created:** 2026-06-30  
**Amended:** 2026-07-01 — added WSJT-X as third appraiser; added audio path normalization requirements  
**Amended:** 2026-07-02 — three-appraiser harness implemented (`run_study_xplat.py`, `matcher_xplat.py`, `analyse_xplat.py`, `smoke_test_null_sink.py`); CI uploads Linux daemon binary artifact  

---

## 0. Decisions ratified

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Study type | **Crossed Gauge R&R — three appraisers (target)** | All three appraisers measure every part in every trial; no nesting. Two-appraiser pilot completed 2026-07-01. |
| D2 | Appraisers | **Windows daemon** (WASAPI + win-x64 `libft8.dll`), **Linux daemon** (ALSA/PulseAudio + linux-x64 `libft8.so`), **WSJT-X** (WASAPI shared mode from same Voicemeeter Out B2 device as Windows daemon) | Three-appraiser design separates *decoder* effect (libft8 vs Fortran) from *audio-chain* effect (ft8loopback vs Voicemeeter). WSJT-X vs Windows = pure decoder comparison. |
| D3 | Signal injection | **Amended 2026-07-01:** Windows synthesizer plays to Voicemeeter AUX Input (VAIO2) → Voicemeeter Out B2 → (a) Windows daemon, (b) WSJT-X (both WASAPI shared mode). Linux synthesizer (same Python harness, same seeds) plays to PulseAudio null-sink (`ft8loopback`) → Linux daemon. All three run simultaneously, aligned to UTC 15 s cycle boundaries. | Same-seed guarantee preserves crossed simultaneous design. The ft8combined combine-sink approach trialled in the pilot was replaced: combine-sink caused resampling artefacts (§5.5). VAIO2 in-strip gain is calibrated so all three appraisers receive the same effective SNR (see §11 and RUNBOOK.md §5.6). |
| D4 | Response variables | Primary: **binary decode outcome** (Attribute R&R). Secondary: **reported SNR, DT, audio freq** (Continuous R&R) where both appraisers decode | Decode-or-not is the most operationally meaningful metric |
| D5 | Scenarios | **S1, S2, S3, S4, S5, S7** — identical scenario set to the existing Windows study (STUDY-SPEC.md §6) | Enables direct result comparison; any platform divergence is immediately visible |
| D6 | Acceptance thresholds | Same as STUDY-SPEC.md §10 for continuous metrics; attribute Kappa ≥ 0.90 for platform agreement | Consistent with established study |
| D7 | Native binary shim | **Both OpenWSFZ daemons must run the same shim version** (currently shim 20260030). Confirm via `GET /api/v1/status` before each run. WSJT-X version noted in §2 but not required to match. | Cross-shim daemon comparison is invalid |
| D8 | Ground truth | **Synthesized truth** — same harness as existing study. WSJT-X is an appraiser in this study, not the ground truth reference. | WSJT-X's ALL.TXT is matched against synthesized truth exactly as the Windows/Linux ALL.TXT files are. |
| D9 | Statistical analysis | **Python** (same `analyse.py` pipeline, extended for three-appraiser cross-platform output in `analyse_xplat.py`) + Minitab-style tables | Consistent with D6 of STUDY-SPEC.md |
| D10 | Audio normalization | **Required before production run:** PulseAudio set to 48000 Hz; Voicemeeter VAIO2 gain calibrated so all three appraisers report SNR within ±2 dB for a 0 dB reference injection. See RUNBOOK.md §5.6. | Pilot showed ~18 dB gain deficit on Windows/WSJT-X path and ~16 Hz Linux freq offset. Both are measurement-system defects that must be corrected before the study delivers valid parity conclusions. |

---

## 1. Purpose

This study answers two operational questions:

> **Q1 — Decoder parity:** Does the `libft8.so` Linux binary produce the same decode
> decisions as the `libft8.dll` Windows binary for the same injected FT8 signals?

> **Q2 — Audio chain characterization:** Does the ALSA–PulseAudio audio chain (WSL2)
> introduce systematic bias in SNR, frequency, or DT measurements relative to the
> Voicemeeter WASAPI path shared by the Windows daemon and WSJT-X?

The three-appraiser design separates these questions:
- **Windows daemon vs WSJT-X** — same Voicemeeter Out B2 audio path, different decoder
  (`libft8.dll` vs Fortran). Any difference here is a pure decoder effect.
- **Windows daemon vs Linux daemon** — same decoder source, different audio chain. Any
  difference here is primarily an audio-chain effect, modulo build-flag differences.
- **WSJT-X vs Linux daemon** — different decoder AND different audio chain. Differences
  here are a combination; the first two pairs disambiguate.

"Equivalently" is defined precisely in §10 (acceptance thresholds). The study is not looking
for exact numerical identity — the two audio paths introduce different timing jitter, different
sample-rate conversion paths, and different buffering characteristics. It is looking for
**absence of systematic bias and absence of material decode-rate divergence** that would
indicate a platform-specific defect.

### 1.1 What this study can demonstrate

- Whether the Linux binary's LDPC solver, AP decode, and candidate search produce the same
  decode decisions as the Windows binary for the same injected signals.
- Whether the ALSA–PulseAudio audio chain introduces material additional jitter or
  sample-rate artefacts that degrade decode performance relative to WASAPI.
- Whether `libft8.dll` and the WSJT-X Fortran decoder agree at each SNR/frequency/DT
  operating point (pure decoder parity, same audio path).
- Whether any audio-frequency, DT, or SNR *measurement* biases differ between platforms
  (indicating a platform-specific calibration issue).

### 1.2 What this study cannot demonstrate

- Decode performance under real off-air propagation (use S6 corpus replay for that, once
  the Linux audio path is validated).
- Performance of the Linux binary under native Linux hardware (non-WSL2). The audio path
  tested here includes PulseAudio running under WSLg, which is not present on bare-metal Linux.
- Any behaviour unique to the UI layer (WPF, JavaScript front-end). This study tests the
  daemon and WSJT-X decoder only.

---

## 2. Null and alternative hypotheses

Six families of hypotheses are tested, one per scenario. All statistical tests use
**α = 0.05** (two-sided where applicable).

### H₀_DEC — Decode-rate parity (primary; applies to all scenarios)

> **H₀:** The per-part decode rate of the Linux daemon equals that of the Windows daemon,
> across all SNR / frequency / DT / density conditions tested.  
> **H₁:** At least one part condition exists where the Linux decode rate is materially lower
> or higher than Windows.

"Materially" is operationalised as a **Cohen's κ < 0.90** on the binary decode decisions
across all (part × trial) cells, or a **McNemar χ² p-value < 0.05** on matched pairs.

**Directional sub-hypothesis (H₁_DIR):**  
> The Linux audio chain (ALSA–PulseAudio–WSLg) introduces systematic additional audio
> latency or jitter that degrades decode rate relative to WASAPI.

This is the most physically plausible failure mode and will be examined first in
post-hoc analysis if H₀_DEC is rejected.

---

### H₀_SNR — SNR measurement parity (S1)

> **H₀:** The mean (SNR_Linux − SNR_Windows) = 0 dB across all matched decodes.  
> **H₁:** A systematic SNR bias exists between platforms.

This uses a paired t-test on (SNR_Linux − SNR_Windows) for all (part × trial) cells where
both appraisers decoded. The existing Windows study's S1 Bias result (§9.2 of STUDY-SPEC.md)
provides the Windows baseline; this study measures whether Linux diverges from it.

**Sub-hypothesis H₀_SNR_LIN:**  
> **H₀:** The SNR bias (Linux − Windows) is constant across the SNR ladder (no differential
> linearity error between platforms).  
> **H₁:** The bias changes with true SNR (one platform's SNR scale is non-linear relative
> to the other's).

Tested by regressing (SNR_Linux − SNR_Windows) against true SNR; H₀_SNR_LIN is rejected
if the regression slope is significantly non-zero (p < 0.05).

---

### H₀_FREQ — Audio-frequency measurement parity (S2)

> **H₀:** The mean |freq_Linux − freq_Windows| = 0 Hz across all matched decodes.  
> **H₁:** A systematic frequency offset exists between platforms.

Paired t-test on (freq_Linux − freq_Windows). Tolerance ±4 Hz (STUDY-SPEC.md §7).

---

### H₀_DT — DT measurement parity (S3)

> **H₀:** The mean (DT_Linux − DT_Windows) = 0 s across all matched decodes.  
> **H₁:** A systematic DT offset exists between platforms.

Paired t-test on (DT_Linux − DT_Windows). Tolerance ±0.2 s (STUDY-SPEC.md §7).

**Physical interpretation:** A non-zero DT bias between platforms indicates that the two
audio chains have different and non-cancelling latencies in the cycle-boundary alignment
step. A constant offset is detectable and potentially correctable; a varying offset
(DT_bias correlated with DT_true) indicates a jitter problem in one audio path.

---

### H₀_ATT — Attribute agreement parity (S4, S5)

> **H₀:** The within-platform Kappa (repeat decode consistency) is identical between
> Linux and Windows, and both equal the existing Windows-only study baseline.  
> **H₁:** The Linux platform shows lower within-platform consistency (lower Kappa) than
> Windows.

**Sub-hypothesis H₀_FP — False-positive rate parity (S5):**  
> **H₀:** The false-positive rate (spurious decodes on signal-free cycles) is identical
> between Linux and Windows.  
> **H₁:** The Linux platform exhibits a higher false-positive rate than Windows.

Tested by Fisher's exact test on (FP_count_Linux, trials_Linux) vs (FP_count_Windows,
trials_Windows).

---

### H₀_COMP — Co-channel/compounding recovery parity (S7)

> **H₀:** The per-family recovery rate (co_channel, near_collision, time_freq, capture)
> is identical between Linux and Windows.  
> **H₁:** At least one overlap family shows a material recovery-rate difference between
> platforms.

This is **informational only** — no PASS/FAIL gate (consistent with S7 treatment in
STUDY-SPEC.md §6.2). However, any divergence here would be a significant finding because
the AP decode (H6) and OSD paths are the most numerically sensitive parts of the pipeline
and the most likely location for platform-specific floating-point divergence.

---

## 3. Test rig

### 3.1 Topology

```
 ┌──────────────────────────────────────────────────────────────────┐
 │  WINDOWS SIDE                                                     │
 │                                                                   │
 │  R&R synthesizer (Python, harness) — seed S, trial T             │
 │  synthesizes FT8 + seeded noise, aligned to 15 s UTC cycle        │
 │            │                                                      │
 │            │ plays PCM (mono, 48 kHz)                             │
 │            ▼                                                      │
 │  Voicemeeter AUX Input (VAIO2) — gain calibrated per §5.6.2      │
 │            │                                                      │
 │            ▼                                                      │
 │  Voicemeeter Out B2 (capture endpoint, WASAPI shared mode)        │
 │            │                          │                           │
 │            ▼                          ▼                           │
 │  Windows daemon (OpenWSFZ.Daemon)    WSJT-X (FT8 mode)           │
 │  WasapiAudioSource                   Input = Voicemeeter Out B2   │
 │  → libft8.dll (win-x64 shim ≥20260030)  (Fortran decoder)        │
 │  ALL.TXT → results/windows/          ALL.TXT → AppData\WSJT-X\   │
 └──────────────────────────────────────────────────────────────────┘

 ┌──────────────────────────────────────────────────────────────────┐
 │  WSL2 SIDE (same physical machine) — runs simultaneously          │
 │                                                                   │
 │  R&R synthesizer (Python, harness) — SAME seed S, trial T        │
 │  synthesizes identical FT8 + noise, aligned to same UTC cycle     │
 │            │                                                      │
 │            │ plays PCM (mono, 48 kHz) via sounddevice             │
 │            ▼                                                      │
 │  PulseAudio null-sink (ft8loopback) — server @ 48000 Hz          │
 │            │                                                      │
 │            │ arecord -D pulse -f FLOAT_LE -r 12000                │
 │            ▼  (captures ft8loopback.monitor)                      │
 │  Linux daemon (OpenWSFZ.Daemon)                                   │
 │  ArecordAudioSource → libft8.so (linux-x64 shim ≥20260030)       │
 │  ALL.TXT → results/linux/                                         │
 └──────────────────────────────────────────────────────────────────┘
         │                 │                     │
         ▼                 ▼                     ▼
 ┌───────────────────────────────────────────────────────┐
 │  Matcher + analyser (Python)                           │
 │  joins truth ↔ Windows daemon ↔ Linux daemon ↔ WSJT-X │
 │  emits CSV + Minitab-style report (all pairwise)       │
 └───────────────────────────────────────────────────────┘
```

**Audio path comparison — key differences between appraisers:**

| Appraiser | Audio path | Decoder | Gain-matched? |
|---|---|---|---|
| Windows daemon | Voicemeeter Out B2 (WASAPI shared) | libft8.dll (C, shim 20260030) | Reference |
| WSJT-X | Voicemeeter Out B2 (WASAPI shared, same device) | Fortran (WSJT-X binary) | ✅ Same path as Windows |
| Linux daemon | PulseAudio ft8loopback.monitor (arecord) | libft8.so (GCC, shim 20260030) | Requires §5.6.2 calibration |

### 3.2 Critical design requirement — crossed simultaneous capture (amended 2026-07-01)

Both daemons **must receive the same noise realization**. Under the original design this
was guaranteed by sharing a single physical audio signal via the WSLg bridge. Under the
amended D3, it is guaranteed by **using identical PRNG seeds** in two independent synthesis
runs that execute simultaneously, each feeding its own platform's audio chain.

- The Windows daemon captures VB-CABLE Output via WASAPI shared mode (unchanged).
- The Linux daemon captures `ft8loopback.monitor` via PulseAudio / arecord (amended).
- Both synthesizers use the same scenario JSON and the same per-trial seed derivation
  (`harness/common.py:compute_seed`), producing mathematically identical noise realizations.
- Both runs are launched simultaneously and align to the same UTC 15 s cycle boundaries,
  maintaining the crossed simultaneous design.

**Amended INVALID condition:** Sequential runs with *different* seeds remain invalid (noise
realizations differ; reproducibility variance is inflated). Sequential runs with *identical*
seeds are a design deviation but may be acceptable as a fallback (document in Section 1 of
the report). Simultaneous runs with same seeds (the standard procedure) are fully valid.

**What the amended design cannot test:** The WSLg bridge latency contribution to DT bias
(H₁_DIR sub-hypothesis) is no longer testable, because the bridge is no longer in the path.
This is acceptable — the sub-hypothesis concerned the bridge itself, which has been
eliminated as an unreliable dependency.

**Verification step (required before first production run):** Play one trial simultaneously,
collect both ALL.TXT outputs, confirm both decode the same message text at the same cycle
timestamp.

### 3.3 Timing and cycle synchronisation

The synthesizer aligns signal injection to the UTC 15-second FT8 cycle boundary (same as
existing study). Both daemons operate in continuous decode mode and align to the same wall
clock. Verify that the Linux daemon's cycle-boundary alignment does not diverge from the
Windows daemon's by more than ±500 ms (one measurable DT tick) on the first bring-up run.

---

## 4. Parts design

Identical to the existing Windows study (STUDY-SPEC.md §6). The same scenario JSON files
are used; no new scenario files are needed for the cross-platform study.

| Scenario | Parts | Trials | Response | Gate |
|---|---|---|---|---|
| S1 — SNR ladder | 10 × {−12 … +15} dB | 3 | Continuous SNR + binary decode | PASS/FAIL |
| S1b — Low-SNR threshold | 4 × {−24 … −15} dB | 3 | Decode rate | Informational |
| S2 — Frequency sweep | 10 × {300 … 2700} Hz | 3 | Continuous freq + binary decode | PASS/FAIL |
| S3 — DT offset | 10 × {0.0 … +2.7} s | 3 | Continuous DT + binary decode | PASS/FAIL |
| S3b — Negative-DT | 10 × {0.0 … −2.7} s | 3 | Decode rate | Informational |
| S4 — Density / QRM | 5 density levels | 3 | Attribute Kappa | PASS/FAIL |
| S5 — False positives | Signal-free cycles | 3 | FP rate | PASS/FAIL |
| S7 — Co-channel | 4 overlap families | 3 | Recovery rate | Informational |

Total injected observations (both platforms combined): 2 × (30 + 12 + 30 + 30 + 30 + 150+
+ FP trials + co-channel trials) ≈ **2 × 400 = ~800 observations minimum**.

---

## 5. Sources of variation — MSA decomposition

In this study the classical Gauge R&R variance components map as follows:

| MSA component | This study |
|---|---|
| **Repeatability (within-appraiser)** | Trial-to-trial variation on the same platform, same scenario, same part. Driven by the seeded noise realization changing each trial — i.e., the decoder's sensitivity to band noise. Expected to be identical between platforms if the decoders are equivalent. |
| **Reproducibility (between-appraiser)** | Platform-to-platform variation for the same noise realization. This is the primary study metric: any significant reproducibility component means the two platforms give systematically different answers to the same input. |
| **Appraiser × Part interaction** | Platform effect varies with part condition. A significant interaction (e.g. Linux loses more decodes only at low SNR) localises the defect. |
| **Part-to-part** | Variation between scenario parts (different SNR levels, different freqs, etc.). Expected to be large — this is genuine signal variation, not measurement system error. |
| **Total Gauge R&R** | Repeatability + Reproducibility. The study goal is %GR&R < 10% of study variation. |

### 5.1 Expected variance structure (prior)

Based on the existing Windows-only study results:

- **Repeatability** will dominate GR&R: trial-to-trial noise realization variation drives
  most within-cell SNR jitter (σ ≈ 8.4 dB from Run 1). This is a property of the FT8
  protocol, not the platform.
- **Reproducibility** is expected to be **near zero** if both binaries perform equivalently.
  Any measurable Reproducibility component is a finding.
- The **ALSA–PulseAudio–WSLg latency chain** may introduce additional DT jitter not present
  in the WASAPI path. This will appear as elevated Reproducibility in S3 and potentially
  elevated Repeatability on the Linux side specifically.

---

## 6. Tolerance bands

Identical to STUDY-SPEC.md §7:

| Response | Tolerance (± half-width) | Gate |
|---|---|---|
| SNR reported | ±5 dB | %Tolerance |
| Audio frequency | ±4 Hz | %Tolerance |
| DT | ±0.2 s | %Tolerance |
| Decode decision | — | Kappa ≥ 0.90 |

**Additional cross-platform tolerance — platform SNR bias:**  
The acceptable platform-to-platform SNR bias (Linux − Windows) is **±2 dB**. This is the
same as the individual-platform bias gate in STUDY-SPEC.md §10 and means neither platform
is allowed to be systematically shifted relative to the other beyond what could be explained
by measurement noise.

---

## 7. Analysis plan — Minitab-style outputs

All analyses are implemented in Python extending the existing `harness/analyse.py`. A new
entry point `harness/analyse_xplat.py` will be created that accepts two result directories
(Windows and Linux) and produces the cross-platform report.

### 7.1 Continuous Gauge R&R (S1, S2, S3) — ANOVA method

Standard two-appraiser crossed Gauge R&R per AIAG MSA 4th edition, Chapter 3.

**Variance components ANOVA table (one per response):**

| Source | SS | df | MS | F | σ² | %Contribution |
|---|---|---|---|---|---|---|
| Appraiser (platform) | | 1 | | | σ²_repro | |
| Part | | p−1 | | | σ²_part | |
| Appraiser × Part | | p−1 | | | σ²_interact | |
| Repeatability (residual) | | p·a·(r−1) | | | σ²_repeat | |
| **Total** | | p·a·r−1 | | | σ²_total | |

where p = number of parts, a = 2 (appraisers), r = number of trials.

**Derived metrics:**

| Metric | Formula | Target |
|---|---|---|
| %Repeatability contribution | σ²_repeat / σ²_total × 100 | Informational |
| %Reproducibility contribution | σ²_repro / σ²_total × 100 | < 10% (acceptable), < 30% (marginal) |
| %GR&R contribution | (σ²_repeat + σ²_repro) / σ²_total × 100 | < 10% (PASS), < 30% (MARGINAL) |
| %Study Var (%SV) | √(σ²_GRR) / √(σ²_total) × 100 | < 10% PASS, 10–30% MARGINAL |
| **%Tolerance (%P/T)** | 5.15·√(σ²_GRR) / tolerance × 100 | **< 10% PASS, 10–30% MARGINAL** |
| **ndc** | 1.41·√(σ²_part) / √(σ²_GRR) | **≥ 5 PASS, ≥ 2 MARGINAL** |

**Six-panel Minitab-style plot (one per scenario S1/S2/S3):**

1. Components of Variation bar chart (platform, part, interaction, repeatability)
2. R-chart by platform (within-platform range; control limits for each)
3. X̄-chart by platform (part means per platform; UCL/LCL; UCL/LCL shown separately)
4. Measurement by Part (both platforms; all trials; means connected)
5. Measurement by Platform (box plot per platform)
6. Platform × Part interaction plot (line per platform, x = part number)

### 7.2 Bias and Linearity (S1)

For each platform individually (mirroring STUDY-SPEC.md §9.2), plot (measured − true SNR)
vs true SNR with regression line. Then plot the **cross-platform bias difference**:
(SNR_Linux − SNR_Windows) vs true SNR with 95% CI band.

Headline metric: **platform SNR bias** = mean(SNR_Linux − SNR_Windows) across all matched
decodes. Gate: |bias| ≤ 2 dB.

### 7.3 Attribute Agreement Analysis (S4, S5)

**Within-platform Kappa (decode repeatability):**  
For each platform: across r=3 trials of the same part, do all trials agree (all decode or
all miss)? Report % agreement and Kappa per platform separately.

**Between-platform Kappa (platform parity):**  
For each (part × trial) cell, compute the binary decode decision of each platform.
Construct a 2×2 contingency table (Windows decode × Linux decode). Report:

- Cohen's κ with 95% CI (Fleiss formula)
- McNemar's χ² test statistic and p-value (tests whether discordant pairs are symmetric)

**False-positive parity (S5):**  
Fisher's exact test on (FP_Linux, N_trials_Linux) vs (FP_Windows, N_trials_Windows).

### 7.4 Cross-platform DT jitter analysis (S3)

In addition to the standard Gauge R&R, plot a **time-series of DT_Linux − DT_Windows**
across all trials in run order, to check for drift (cycle-lock slippage in the Linux audio
path over time).

If the WSLg bridge introduces a fixed latency offset, it will appear as a constant
(DT_Linux − DT_Windows) ≠ 0. This is correctable by configuration. If the offset is
non-stationary (drifting), it indicates clock-domain mismatch between WSLg audio and the
FT8 cycle timer — a more serious finding.

### 7.5 Power analysis

For the attribute McNemar's test (H₀_DEC):

Detecting a 5% absolute decode-rate difference (e.g. 90% Windows vs 85% Linux) at α=0.05,
β=0.20 requires approximately **n ≈ 200 discordant-pair observations**. The study design
yields ~400 total (part × trial) observations per platform — sufficient for detecting a
meaningful platform difference at the target power.

For the continuous paired t-test (H₀_SNR): assuming σ_diff ≈ 2 dB (conservative), detecting
a 1 dB platform bias at α=0.05, β=0.20 requires n ≈ 33 matched-decode pairs. S1 alone
provides 10 parts × 3 trials = 30 matched pairs per platform (if both decode every trial) —
marginally sufficient. The full study (S1+S2+S3) provides >90 paired observations for
continuous metrics.

---

## 8. Acceptance thresholds (PASS/FAIL/MARGINAL)

### 8.1 Per-metric gate (continuous Gauge R&R)

| Metric | PASS | MARGINAL | FAIL |
|---|---|---|---|
| %GR&R (platform reproducibility) | < 10% | 10–30% | > 30% |
| %Tolerance (%P/T) | < 10% | 10–30% | > 30% |
| ndc | ≥ 5 | 2–4 | < 2 |
| SNR bias \|Linux − Windows\| | ≤ 1 dB | 1–2 dB | > 2 dB |
| SNR bias \|WSJT-X − Windows\| | ≤ 1 dB | 1–2 dB | > 2 dB |
| SNR bias \|Linux − WSJT-X\| | ≤ 1 dB | 1–2 dB | > 2 dB |
| DT bias \|Linux − Windows\| | ≤ 0.1 s | 0.1–0.2 s | > 0.2 s |
| DT bias \|WSJT-X − Windows\| | ≤ 0.1 s | 0.1–0.2 s | > 0.2 s |
| Freq bias \|Linux − Windows\| | ≤ 2 Hz | 2–4 Hz | > 4 Hz |
| Freq bias \|WSJT-X − Windows\| | ≤ 2 Hz | 2–4 Hz | > 4 Hz |

> The `WSJT-X − Windows` pair shares the same Voicemeeter Out B2 audio path; any
> bias here is a pure decoder effect. A PASS on this pair with a FAIL on `Linux − Windows`
> isolates the defect to the Linux audio chain.

### 8.2 Per-metric gate (attribute)

| Metric | PASS | MARGINAL | FAIL |
|---|---|---|---|
| Between-platform Cohen's κ — Windows vs Linux | ≥ 0.90 | 0.75–0.89 | < 0.75 |
| Between-platform Cohen's κ — Windows vs WSJT-X | ≥ 0.90 | 0.75–0.89 | < 0.75 |
| Between-platform Cohen's κ — Linux vs WSJT-X | ≥ 0.90 | 0.75–0.89 | < 0.75 |
| McNemar χ² p-value (all pairs) | ≥ 0.05 (H₀ not rejected) | — | < 0.05 (H₀ rejected) |
| Within-platform Kappa (Linux) | ≥ 0.90 | 0.75–0.89 | < 0.75 |
| False-positive rate (Fisher, all pairs) | p ≥ 0.05 | — | p < 0.05 |

### 8.3 Overall study verdict

| Verdict | Condition |
|---|---|
| **PASS** | All per-metric gates PASS; no H₀ rejected at α=0.05 |
| **MARGINAL** | At least one metric MARGINAL, none FAIL; no H₀ rejected |
| **FAIL — Platform defect** | At least one metric FAIL, or H₀_DEC / H₀_SNR rejected at α=0.05 |
| **FAIL — Audio chain** | H₀_DEC not rejected but DT jitter analysis shows non-stationary WSLg offset |
| **INVALID** | Crossed design violated (sequential rather than simultaneous capture); run must be discarded |

---

## 9. Required report structure (NFR-023)

Every run produces a `report.md` following the five-section structure mandated by
NFR-023 and STUDY-SPEC.md §9.0:

### Section 1 — Study hypothesis *(QA-authored, not generated)*

State: which shim version is under test; whether this is a parity confirmation or a
regression investigation; which hypotheses (H₀_DEC through H₀_COMP) are live; what
outcome would constitute a significant finding.

### Section 2 — Data summary *(generated + QA-verified)*

- OpenWSFZ git SHA (both daemons must match)
- Shim version (must be identical for both platforms)
- Windows daemon: OS version, WASAPI device name
- Linux daemon: WSL2 distro + kernel version, `arecord --version`, PulseAudio source name
- Number of scenarios run, parts, trials, total observations per platform
- Any deviations from the standard protocol

### Section 3 — Results with graphs *(generated)*

One sub-section per scenario containing: ANOVA table, %GR&R metrics, six-panel plot,
bias/linearity chart (S1), attribute Kappa tables (S4/S5), DT jitter time-series (S3).

### Section 4 — Summary verdict table *(generated)*

| Metric | Windows | Linux | Delta | Gate | Verdict |
|---|---|---|---|---|---|
| S1 %GR&R | x% | x% | Δ | < 10% | PASS/FAIL |
| S1 Platform SNR bias | — | x dB | — | ≤ 2 dB | PASS/FAIL |
| S2 %GR&R | ... | ... | ... | ... | ... |
| ... | | | | | |
| **Overall** | | | | | **PASS / MARGINAL / FAIL** |

### Section 5 — Recommendations *(QA-authored, not generated)*

For each FAIL or MARGINAL: state the hypothesis rejected, the most probable physical
cause (audio latency, floating-point divergence, sample-rate mismatch), and the
recommended next diagnostic step (e.g. compare raw `arecord` capture against the
synthesized WAV byte-for-byte; check `libft8.so` build flags for FP precision).

---

## 10. Harness changes required

The existing `harness/analyse.py` operates on a single result directory containing
combined Windows+WSJT-X data. The cross-platform study requires a two-directory input.

A **new analysis script** `harness/analyse_xplat.py` is required with the following
responsibilities:

1. Accept `--windows-dir` and `--linux-dir` arguments pointing to the two ALL.TXT
   collection directories.
2. Re-use the existing `matcher.py` to join each platform's decodes to truth separately.
3. Merge the two matched CSVs on (scenario, part, trial, message) to form the
   cross-platform comparison dataset.
4. Implement the ANOVA decomposition, Kappa calculations, bias/linearity analysis,
   and DT jitter time-series described in §7.
5. Produce `report.md` and all PNG charts in the output directory.

**Existing `analyse.py` is not modified.** The cross-platform script is a new entrypoint
that reuses internal functions but does not alter the existing Windows+WSJT-X workflow.

---

## 11. Pre-run checklist (operator)

Before starting a production run, complete all items. For the audio-normalization
procedure details see RUNBOOK.md §5.6.

### One-time setup (first run only)

- [ ] PulseAudio sample rate set to 48000 Hz in WSL2 — see RUNBOOK.md §5.6.1.
  Verify: `pactl info | grep "Default Sample"` shows `48000 Hz`.
- [ ] WSJT-X configured: Input = Voicemeeter Out B2; Mode = FT8; TX disabled.
  See RUNBOOK.md §5.6.3 for full configuration steps.
- [ ] Voicemeeter VAIO2 gain calibrated — see RUNBOOK.md §5.6.2. All three appraisers
  report SNR within ±2 dB of each other for a 0 dB reference injection.

### Per-session checklist

- [ ] Windows daemon running on host; Linux daemon running in WSL2.
- [ ] Both OpenWSFZ daemons report the **same shim version** (`GET /api/v1/status` → `shimVersion`).
- [ ] Both daemons configured to write `ALL.TXT` to distinct, known paths.
- [ ] WSJT-X running and showing "Receiving" status; Input = Voicemeeter Out B2.
- [ ] Voicemeeter open; VAIO2 strip gain at calibrated position.
- [ ] R&R synthesizer plays to **Voicemeeter AUX Input (VAIO2)** — confirm Voicemeeter
  meters respond when a test tone is played.
- [ ] **WSL2 — ft8loopback null-sink active** (must be created once per WSL2 session):
  ```
  pactl list sinks short | grep ft8loopback   # should return one line
  # If absent:
  pactl load-module module-null-sink sink_name=ft8loopback \
        sink_properties=device.description=FT8Loopback
  pactl set-default-sink ft8loopback
  pactl set-default-source ft8loopback.monitor
  ```
- [ ] WSL2 Linux daemon configured with `audioDeviceId = "pulse"`.
  **Do NOT save settings via the browser UI** — the empty device dropdown will overwrite
  this value to `null` (D-LINUX-001, pending fix). Configure via `POST /api/v1/config`
  with the full correct body if a reset is needed (see RUNBOOK.md §1.5).
- [ ] **Audio chain verified end-to-end:** run `python smoke_test_null_sink.py` from
  inside `.venv-linux` in WSL2 — must print `✅ PASSED` for all three appraisers (Windows,
  Linux, WSJT-X). The updated script checks WSJT-X ALL.TXT for a recent decode.
  See §5.6.4 for the six-point verification gate.
- [ ] System clock accurate (NTP synced on both Windows and WSL2).
- [ ] No other audio playback or capture applications running.
- [ ] Python harness virtual environment activated: `.venv` (Windows) for
  `run_study_xplat.py`; `.venv-linux` (WSL2) activated by the orchestrator automatically.
- [ ] WSJT-X ALL.TXT location confirmed: `C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT`
  (or note actual path in Section 2 of the report if different).

---

## 12. Defect classification for cross-platform findings

| Finding | Classification | Example |
|---|---|---|
| H₀_DEC rejected + DT bias non-zero | Audio chain latency — likely WSLg buffer | Linux DT mean = +0.4 s vs Windows |
| H₀_DEC rejected + DT bias ≈ zero | Binary decoder difference — investigate libft8.so build | Same signals, Linux misses at −6 dB |
| H₀_SNR rejected | SNR calibration path differs between platforms | Linux SNR bias +3 dB across ladder |
| H₀_FP rejected | False-positive generator in Linux build path | Linux FP rate 2% vs Windows 0% |
| H₀_COMP divergence in co_channel family | OSD / AP floating-point — likely build-flag FP precision | Linux co-channel 5% vs Windows 0% |
| DT jitter non-stationary | WSLg clock domain drift | DT_Linux − DT_Windows trends over run |

---

## 13. Run history

| Date | SHA | Shim | Windows %GR&R | Linux %GR&R | Platform κ (Win/Lin) | Overall | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-01 | b03998f | 20260030 | — (S2 only) | — (S2 only) | 0.852 | **FAIL** | Pilot two-appraiser run. S2/S3/S4/S5/S7 only (S1/S1b/S3b not measured). Platform κ MARGINAL. SNR FAIL (18 dB gain asymmetry). Freq FAIL (−10.5 Hz offset). McNemar FAIL (n12=125, n21=0, p=0.0000) — directional, caused by gain asymmetry not decoder defect. FP parity PASS. Report: `results/2026-07-01-b03998f/report.md`. |
| *(v2 run pending normalization)* | | | | | | | Audio normalization (§5.6) required before next run. |

---

## 14. Relationship to existing study

This study **extends** rather than replaces STUDY-SPEC.md. The two studies share:
- The same scenario JSON files and synthesizer.
- The same acceptance thresholds (§10 of STUDY-SPEC.md; replicated in §8 above).
- The same NFR-023 five-section report structure.

The key differences:

| Dimension | STUDY-SPEC.md (existing) | This study |
|---|---|---|
| Appraisers | Windows daemon + WSJT-X | Windows daemon + Linux daemon + WSJT-X |
| WSJT-X role | **Appraiser** (primary reference) | **Appraiser** (decoder comparison) |
| Ground truth | Synthesized | Synthesized |
| Audio path | WASAPI shared mode (both appraisers) | WASAPI (Windows/WSJT-X) + PulseAudio (Linux) |
| Run logistics | Single machine, two appraisers | Single machine, three appraisers; Linux in WSL2 |
| Primary question | OpenWSFZ decode rate vs WSJT-X reference | Cross-platform binary parity; audio chain characterization |

WSJT-X appears in both studies: in STUDY-SPEC.md it is the *primary reference decoder*
against which OpenWSFZ is validated. In this study it is a *third appraiser* that allows
isolation of the decoder effect from the audio-chain effect. This dual role is intentional
and the results are complementary rather than contradictory.

Results from this study and from STUDY-SPEC.md runs are **not directly comparable** (different
operating points and normalization states) but the scenario definitions are identical, enabling
qualitative comparison of each platform's absolute decode-rate and measurement accuracy.

---

*Authored by QA, 2026-06-30.*  
*Amended 2026-07-01: three-appraiser design; audio normalization requirements added.*  
*Companion handoffs: `dev-tasks/2026-06-30-wsl-linux-rr-environment.md`; `dev-tasks/2026-07-01-xplat-three-appraiser-harness.md`.*
