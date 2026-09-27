# `SUB-FEAS`: can we model a decoded real signal precisely enough to subtract it?

**Architect → QA, 2026-09-27 18:55Z** (`date -u`, HK-017). Branch `arch/subtraction-feasibility`.
Docs only: `git diff --stat origin/main -- src/ native/` is empty. **Offline, `qa/` Python only. No
build, no `src/`/`native/` change, no default change (HK-011).**

**Authority.** GAP-LOCATE's final ruling (`2026-09-27-1610`, `main` `4c21280d`) closed on **LB**: 17.06 pp of
the 19.27 pp strong-miss pool cannot be decoded by our extraction **even at the right position**. That loss
grows with cycle load, and in 1,150 cells another transmission dominates. The Captain was offered
(a) a scoped feasibility study of the one family sized to that answer, or (b) stopping decode-rate
work. **The Captain, 2026-09-27: *"go with option 1. It is a hobby project after all. lets see how far
we can get."*** This spec is that study.

🛑 **What this does and does not reopen.** *Subtract-and-resynthesise DEAD* (`closed-arms-prohibitions.md`)
stands for **builds**. This arm **measures** one precondition offline, which the standing record names
as missing: *"The precondition subtraction needs, an accurate per-signal frequency/time/phase estimate,
still does not exist on real signals"* (board archive, 2026-09-13). Nothing in this arm may be proposed
as a build. A build needs a separate Captain ruling on this arm's result.

---

## §1. Why this is a new question and not a fourth re-run

The three June builds (`20260007` three-pass, H3 `20260008`, H3b `20260009`, archived under
`openspec/changes/archive/2026-06-12-diag-d001-*`) and the August refiner differ from this arm on
**every** axis that the record blames for their failure:

| axis | June builds (H3b design.md) | Refiner (R1/R1b, M-series) | **SUB-FEAS** |
|---|---|---|---|
| Where the template sits | Decoder lattice, 3.125 Hz / 80 ms (archive: *"you cannot subtract a signal you cannot locate"*) | Estimated **blind**, from the 21 Costas symbols | **Data-aided**: fitted after decode, using **all 79 known symbols** |
| Frequency/time refinement | None: *"iterating or refining … out of scope"* (H3b design.md:49) | Yes, but blind and anchored ~0.65 s off (M3) | Fine fit around an **empirically calibrated** anchor (ROW 0g) |
| Amplitude/phase model | **One** complex scalar for the whole 12.64 s | n/a | **Time-varying** complex envelope, which tracks fading and drift |
| Where it was judged | Decode rate on synthetic S7 | Proxies (voided twice) | **Real on-air audio first**, with a synthetic sanity row only |

The method class, estimating a decoded signal's time-varying complex amplitude by low-pass filtering
`x · conj(reference)`, is published: Franke, Somerville & Taylor, *"The FT4 and FT8 Communication
Protocols"*, QEX, July/Aug 2020. 🛑 **Licence policy (`standing-licence-policy.md`):** read that paper, or
WSJT-X, **for method only. Not one line may be copied, transliterated or ported.** Implement from scratch
in numpy. The GFSK synthesis may mirror the vendored **ft8_lib** (MIT) generator. Cite the file and line.

---

## §2. Corpus and data handling

- **Corpus:** `20260925_2010` endurance run, gathered at `artefacts/20260925_2010_endurance_run-gathered/`
  in the QA worktree. Use `owsfz/wav/*.wav` (2,884 cycles, 12 kHz mono int16), `owsfz/ALL.TXT` (the known
  messages: freq `[6]`, DT `[5]`, SNR `[4]`) and `wsjt-x/ALL.TXT` (for the isolation filter and Stage 2
  corroboration). 12h 40m, **40m** (dial 7.074 MHz per `arm_config.json`), direct-CODEC, nhard 40, `decoding_improvement`
  `51e40b55`, shim `20260054`, DLL SHA-256 `38a21f84…589a1cba`.
- **PCM:** load with `gap-locate/wavio.py::load_cycle_pcm` (production RMS normalisation). Do not re-derive it.
- **DLL** (ROW 0a and Stage 2 only): the run's own DLL, SHA-256 pinned from its `arm_config.json`, loaded
  the `gl_dll_pin.py` way (`artefacts/20260925_2010_endurance_run/arm_config.json` → `dll_sha256`). Not a worktree `bin/` copy.
- 🔒 **NFR-021 / HK-037:** message text and tone sequences stay inside the function that reads `ALL.TXT`.
  Key every output row by `(cycle_ts, freq_hz, row_id)` with numeric fields only. **No callsign, grid or
  message text in any JSON, log or report.** Scan before committing, with `scan()`/`classify()` imported.

## §3. Population

**P** = OWS decodes in the run window that meet all of these:
1. SNR `[4]` ≥ 0 dB. These are the strong signals that mask others.
2. **Isolated**: no other decode from **either** program's `ALL.TXT` in the same cycle within 60 Hz of
   `freq`. Undecoded overlapping signals still leak in and inflate the residual. That bias is
   **conservative** (it makes PASS harder) and is disclosed, not corrected.
3. **Re-encodable standard message**: exclude hashed `<…>`, non-standard or free text, and 2-token messages.
   Report the excluded count by reason.

Split **A** = even cycle index, split **B** = odd. **A is used only to choose `W*` (§4). Every gated
number is read on B.** If the full run exceeds 3 h after a timing probe, keep every k-th cycle, with k the
smallest integer that brings it under 3 h. Apply k to both splits, and record k and the probe result.

## §4. Estimator and legs

For each row, with `x_a` the analytic signal of the cycle PCM and `r` the complex GFSK baseband of its
79-tone sequence (FT8: 1,920 samples per symbol, 6.25 Hz spacing, Gaussian BT = 2.0):

1. **Anchor** (ROW 0g gives `τ0`): search from `(freq, DT + τ0)`.
2. **Fine fit:** maximise `|Σ x_a(t) · conj(r(t − Δt)) · e^{−j2πΔf t}|` over Δt ∈ ±60 ms (1 ms steps) and
   Δf ∈ ±2.0 Hz (≤ 0.05 Hz resolution; a zero-padded FFT over Δf is fine).
3. **Envelope:** `c(t) = LP_W[x_a · conj(r_fit)] / LP_W[|r_fit|²]`, where `LP_W` is a Hann-weighted moving
   average of length `W`. Estimate: `ŝ = Re{c · r_fit}`.
4. **`W` family:** {12.64 s (= one scalar, June's model), 2.56, 1.28, 0.64, 0.32 s}. **`W*` = the
   member with the lowest median `X` (§5) on split A.** It is chosen once and frozen before B is read.

| leg | position | envelope | what it is |
|---|---|---|---|
| **L0** | lattice-snapped (`gap-locate/lattice.py`) | `W` = 12.64 s | June's model, rebuilt as a control |
| **L1** | fine fit | `W` = 12.64 s | isolates the effect of positioning |
| **L2** | fine fit | `W*` | the candidate |

`RR73` rows: fit both encodings, the on-air grid value 32373 and ours `MAXGRID4+3`, and keep the one with
the larger correlation (ROW 0f). The GAP-LOCATE side finding says ours is wrong on air. A template built
from our encoder would be the wrong waveform.

## §5. Metrics (per row)

- `B_i` = [`f_i` − 6.25, `f_i` + 50.0] Hz. The time span is the fitted 12.64 s.
- `E(y)` = energy of `y` inside `B_i` over the span.
- `N̂_i` = noise floor: the 20th percentile of per-6.25-Hz-bin energy across 200–2800 Hz, same span and
  same cycle, scaled to the width of `B_i`.
- **Primary: `X_i = 10·log10(E(x − ŝ_i) / N̂_i)`** is the residual above noise in dB. A perfect
  subtraction gives ≈ 0.
- Secondary: `D_i = 10·log10(E(x) / E(x − ŝ_i))` is the suppression in dB.

Report X and D by SNR band [0,5), [5,10), [10,∞) as a description only.

## §6. ROW 0 (any FAIL ⇒ STOP and report; a FAIL is not a result)

| row | check (mechanical) | bar |
|---|---|---|
| **0a** encoder fidelity | 300 rows sampled from P (seed 20260927). Synthesise a clean signal at nominal (f, DT) and decode it with the pinned DLL. The 77-bit payload must equal the one encoded (RR73 per §4) | ≥ 0.99 |
| **0b** synthetic recovery | 400 synthetic single-signal cycles; SNR ∈ {0, +5, +10} dB; random f, Δt ∈ ±0.5 s, phase; impairment ∈ {none, linear drift 0.5 Hz over the transmission, Rayleigh fade with 0.2 Hz Doppler}. Use the best `W` per impairment | median X ≤ 1.0 dB (none, drift), ≤ 2.0 dB (fade), at every SNR. "None" also needs median \|Δt err\| ≤ 2 ms and \|Δf err\| ≤ 0.05 Hz |
| **0c** noise floor | 200 noise-only synthetic cycles plus 200 cycles with 15 random signals | `N̂` within ±1.0 dB of truth in ≥ 95 % |
| **0d** size | `|P_A|` and `|P_B|` | each ≥ 1,000 |
| **0e** DLL pin | loaded DLL SHA-256 = the run's `arm_config.json` | equal |
| **0f** RR73 form | among RR73 rows in P, the share where the on-air form wins the correlation | ≥ 0.90 (else STOP: the encoding premise is wrong) |
| **0g** anchor | on the first 10 % of cycles by time (excluded from A and B), a wide search: Δt ∈ ±1.0 s at 5 ms, Δf ∈ ±3 Hz at 0.1 Hz. `τ0` = median Δt | IQR(Δt) ≤ 40 ms **and** median Δf ∈ [−1, +1] Hz |
| **0h** convergence | share of P rows whose fine-fit optimum sits on the search-box edge | ≤ 0.02 |

⚠️ 0g exists because the refiner's M1/M2 were voided by a ~0.65 s anchor error (M3), and our DT is known
to be ≈0.70 s off WSJT-X's convention. **Do not hard-code any offset. Measure it.**

## §7. Stage 1 gate, read on split B, leg L2 (rows are exclusive and exhaustive)

Statistic: median `X` over `P_B`, with a 95 % CI from a cycle-clustered bootstrap (2,000 draws, seed 20260927).

```python
if ci_hi_X <= 3.0 and median_D >= 10.0:   row = "PASS"     # leftover ≤ noise: a masked neighbour sees ≤ +3 dB
elif ci_hi_X <= 6.0:                      row = "PARTIAL"
else:                                     row = "FAIL"
```

**Required controls (descriptive, always reported):** the paired median ΔX for L0−L2 and L1−L2, with CIs.
🔴 **C-FLAG:** if L0's own median X has `ci_hi ≤ 3.0`, say so in the headline. It would mean June's failure
was **not** a modelling problem, and PASS would not license anything.

## §8. Stage 2: the payoff (pre-registered now, runs only on PASS/PARTIAL **and** the Captain's go)

For each split-B cycle: fit and subtract **all** of OWS's re-encodable decodes (L2, `W*`). Decode the
residual with the pinned DLL (nhard 40). A **new** decode is one not in that cycle's OWS list.
**Corroborated** = also in WSJT-X's `ALL.TXT` for the same cycle, compared on outcome fields inside the
function, with RR73 equivalence per GAP-LOCATE Amendment 4.

- **Primary:** `ΔR` = corroborated new decodes / WSJT-X decodes in split B, in pp, with a cycle-clustered
  bootstrap CI.
  `WIN` if `ci_lo ≥ 1.0`; `SMALL` if `0 < ci_lo < 1.0`; `NONE` otherwise.
- Report uncorroborated additions (count and share). 🛑 **Uncorroborated ≠ false positive** (DENSITY guard).
- Caveat, stated in the report: a DLL replay is not the live path. `ALL.TXT` is post-`IsPlausibleMessage`
  plus text-dedup (`Ft8Decoder.cs:338-354`). Apply the same text-dedup, and let corroboration stand in for
  the plausibility filter.

## §9. Architect predictions (scored at ruling time; `architect-prediction-ledger.md`)

| # | prediction | P | class |
|---|---|---:|:---:|
| 1 | ROW 0b passes | 0.80 | C |
| 2 | ROW 0f passes (on-air RR73 form wins) | 0.90 | C |
| 3 | Stage 1 reads **PASS** / PARTIAL / FAIL | 0.30 / 0.35 / 0.35 | H |
| 4 | L0 − L2 paired median ΔX ≥ 3 dB (modelling is what June got wrong) | 0.70 | H-mech |
| 5 | Given PASS, Stage 2 reads WIN | 0.35 | H |

🔴 **Bias named in advance:** my HYPOTHESISED record is 1/7, and it leans toward "a findable mechanism
exists". PASS is held at 0.30 for that reason. #4 is an H-mech call, the class that came out backwards
last time (FADE).

## §10. Deliverables

- Harness: `qa/rr-study/sub-feas/`. Reuse `gap-locate/` modules by import; do not copy them.
- `sub_feas_result.json`: every ROW 0, the `W*` selection table from split A, and per-leg X/D summaries.
  No text.
- Report to the Architect: `qa/rr-study/<UTC>-qa-to-architect-sub-feas-results.md`. Put the ROW 0 table
  first, then the Stage 1 row. **Stop after Stage 1.** Stage 2 needs the Captain's go.
- QA may REFUSE this spec on HK-025(k) grounds. Say so before running, not after.
