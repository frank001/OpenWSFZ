# Architect → QA — C-FREQ-A: was the coherent path ever given a fair test?

**2026-08-22 19:03Z.** Pre-registration, HK-021. Offline synthetic sweep. **No capture, no
hardware, no live run, no `src`/`native` change.**

🔴 **GATED. Do not run this arm until C-GAP-D
(`2026-08-22-1902-architect-to-qa-spec-c-gap-d-extraction-headroom-decomposition.md`) has
reported and the Captain has ruled on it.** If C-GAP-D fires ROW 1, this arm still has value
— see §1.2 — but its value is *scientific closure on Route B2*, not gap-closing, and the
Captain should decide whether that is worth the session.

---

## 1. The question

### 1.1 What Phase B left on the table

Phase B closed ROW 0g-2's residual from **−67 to −3** median bit-errors, but 0g-2 still
fires. 0g-1 (the *sharp* limb, clean synthetic) **passes**. So the residual is exclusively a
real-audio phenomenon, and 11.4's pre-registered attribution rule already places it in
**fusion or frequency**, not position.

This arm tests the frequency half, and it does so because of an arithmetic property of the
code that was verified in source, not assumed:

- `coherent_llr.c:458` mixes at `freq_hz_grid` — snapped to the production lattice.
  `COH_FREQ_OSR 2`, `COH_SYMBOL_PERIOD_S 0.160` ⇒ quantum **3.125 Hz**, worst-case snap
  error **±1.5625 Hz**. Line 462 states the constraint explicitly: *"OWN grid frequency
  (unrefined) — design.md D1: no refined position."*
- The header (line 82) states magnitude is taken **last**, so accumulation is coherent
  across the whole window: `T = n_syms × 0.16 s`, up to `COH_MAX_NSYMS 3` ⇒ 0.48 s.

A residual carrier offset `δ` over a coherent accumulation of length `T` costs amplitude
`|sinc(δT)|`. At the half-quantum, a 2-symbol window suffers a **180° rotation** — the
second symbol arrives in anti-phase — and a 3-symbol window **270°**.

**And 0g-1's synthetic sits at 1500 Hz: `1500 × 0.160 = 240.0`, dead on a lattice bin, zero
snap error.** 0g-1's PASS therefore certifies the implementation *at zero frequency offset
only*. Real carriers land anywhere in the bin. That is HK-022 in its plainest form — a green
result answers whatever it was pointed at.

### 1.2 The architectural claim this tests

`design.md` D1 pinned the coherent extractor to the unrefined grid position. That constraint
was adopted because *time-position* refinement is dead three times over (M4, N1, P-LIVE
Stage 2). **It was then applied to both axes, and the axes are not symmetric:**

- **time** error costs a fraction of a symbol's energy — first-order tolerable, and the
  lattice is 0.08 s against a 0.16 s symbol;
- **frequency** error costs *phase*, growing as `T·δf` — first-order destructive, and
  **worst on exactly the multi-symbol windows that are the entire value proposition**.

If this arm fires ROW 1, then **Route B2's limb 2 has never been fairly evaluated** — we
built and measured a deliberately handicapped version of it. That is worth knowing whether
or not we go on to build anything, because it changes what a future ROW 3 (kill) on the
Phase 1 gate would have meant.

⚠️ **Honest demotion, stated by the Architect who proposed it:** C-GAP-D's exploratory
numbers indicate extraction quality can close only a minority of D-001. **This arm is
therefore no longer a candidate D-001 treatment.** I proposed it as one; the data demoted
it. It is now a closure question about Route B2, and it should be funded on that basis or
not at all.

---

## 2. Construction

### 2.1 Signal

`qa/rr-study/synth/encoder.encode_message` (verified `base_freq_hz: float`, continuous phase
integration via `inst_freq`/`cumsum` in `modulator.modulate` — fractional offsets are
honoured exactly). Q-prefix synthetic callsigns only (NFR-021). Seeded.

`base_freq_hz = 1500.0 + δ`, with:

**δ ∈ {0.000, 0.375, 0.750, 1.125, 1.500} Hz**

🔴 **Why the sweep stops at 1.5 and not 1.5625:** for `δ < 1.5625` the lattice snap output is
**invariant** — it resolves to 1500.0 at every sweep point — so the *code path is identical
across the whole sweep and only the audio changes*. At exactly 1.5625 the `lroundf` tie
makes the snap ambiguous. Stopping at 1.5 keeps the control clean.

### 2.2 Trials, noise, and the floor-degeneracy remedy

- **M = 40 trials per δ**, distinct messages, seeded.
- 🔴 Noise-free would sit both paths on the floor. Calibrate `snr_db` at `δ = 0` so
  `median(n_err_grid_min)` lands in **[5, 25]** — this is **0g-1's own floor-degeneracy
  remedy, reused verbatim** (HK-021(n)), not a new construction. Fix that `snr_db` once and
  hold it across every δ.
- Time convention: **do not attempt to resolve it** (the D3 landmine). Sweep
  `time_offset_s` over `m3_common.TIME_ANCHOR_OFFSETS_S` and take the **minimum `n_err` over
  the sweep, independently for each path** — exactly as 0g-1 does. Each path gets its best
  shot; the construction cannot manufacture a coherent failure.

### 2.3 Statistics

- **Primary:** `d(δ) = median over trials of ( n_err_grid_min − n_err_coh_min )` — **signed**
  (HK-021(l); the direction is the entire content). Same statistic as 0g-1b, so it is
  directly comparable to a committed number.
- **Secondary (this authorises 0g-3, specified in the ROW 0g spec §3 and never run):** the
  **`n_syms` selection share** — the fraction of the 174 bits sourced from each window size
  (1, 2, 3), per δ.
- Bootstrap over trials, 2000 draws, fixed seed `20260822`. Trials are independent by
  construction (distinct seeded messages, no shared cycle) — **this is the one arm on this
  project where a per-trial bootstrap is legitimate, and it is legitimate because the
  clustering structure that forces HK-021(i) elsewhere does not exist here.** Say so in the
  report rather than leaving it to be queried.

---

## 3. 🔴 Pre-registered predictions — printed in advance, before the run

Coherent gain factor `|sinc(δT)|`, `T = n_syms × 0.160 s`:

| δ (Hz) | n_syms=1 | n_syms=2 | n_syms=3 |
|---|---|---|---|
| 0.000 | 1.000 (0 dB) | 1.000 (0 dB) | 1.000 (0 dB) |
| 0.375 | 0.994 (−0.05 dB) | 0.976 (−0.21 dB) | 0.947 (−0.47 dB) |
| 0.750 | 0.976 (−0.21 dB) | 0.908 (−0.84 dB) | 0.800 (−1.94 dB) |
| 1.125 | 0.947 (−0.47 dB) | 0.800 (−1.94 dB) | 0.585 (−4.66 dB) |
| 1.500 | 0.908 (−0.84 dB) | 0.662 (−3.58 dB) | **0.341 (−9.34 dB)** |

Therefore, predicted:

1. `d(δ)` **monotone non-increasing** across the five sweep points.
2. `d(1.500) − d(0.000)` **strongly negative** — the 3-symbol window loses ~9.3 dB.
3. The **`n_syms=3` selection share falls monotonically** with δ; the `n_syms=1` share rises.

Prediction 3 is the mechanism-specific one. **No rival explanation reshapes the selection
share.**

### 3.1 Rivals, pre-registered and quantified

| rival | prediction it makes | how it dies |
|---|---|---|
| **R1** — "any frequency error hurts both paths equally" | grid degrades as much as coherent; share unchanged | the paired statistic `d(δ)` is differential; and R1 makes no prediction about the `n_syms` share |
| **R2** — "it is the mixer's low-pass edge" | degradation from filter rolloff | the LP is 90 Hz cutoff at 200 Hz rate, sized for a 43.75 Hz tone span. `δ <= 1.5 Hz` is **under 2% of that margin** ⇒ predicted effect ≈ **0**. Quantitative, not hand-waved. |
| **R3** — "it is the snap arithmetic, not the phase" | snapped frequency varies across the sweep | **ROW 0b** asserts the snap output is identical at every δ. If it is, R3 is dead by construction. |

---

## 4. Rows — strictly ordered, mutually exclusive, boundary falls to ROW 4

### 4.1 ROW 0 — validity

| row | check | fires if | 🔴 what this row CANNOT detect |
|---|---|---|---|
| 0a | binary identity — SHA256 of the DLL on disk asserted against the pre-registered pin, plus `FT8_SHIM_VERSION`, both recorded in the report | mismatch | nothing about whether that pinned binary is *correct* |
| 0b | **snap invariance** — the resolved grid frequency is identical at every δ | any variation ⇒ **arm VOID** | an error in the *true* signal's synthesis (independent path: our Python encoder vs the C extractor — not shared, so this is a genuine cross-check) |
| 0c | `δ = 0` reproduces 0g-1's committed `n_err` within 1 bit (the readout quantum) | differs by > 1 bit | drift shared by both the committed run and this one |
| 0d | noise calibration — `median(n_err_grid_min)` at `δ=0` in `[5, 25]` | outside ⇒ recalibrate and restate, do not proceed | nothing about the noise *realisation* being typical |
| 0e | determinism — full re-run at the fixed seed, **mechanically diffed** | any byte differs | a deterministic-but-wrong computation |

### 4.2 ROW 1–4

| row | condition | verdict and consequence, as an assertion |
|---|---|---|
| **1** | `d(1.500) − d(0.000) <= −5` bits **and** `d(δ)` monotone non-increasing **and** the `n_syms=3` share falls by `>= 0.10` from δ=0 to δ=1.500 | **MECHANISM CONFIRMED.** The coherent path's advantage is destroyed by sub-bin frequency offset. **Route B2 limb 2 has not been fairly evaluated**, and any fair evaluation requires per-candidate fine frequency estimation feeding the coherent mixer. Record this against `design.md` D1. Authorises **no build** — a proposal for that estimation is a separate OpenSpec change and a separate Captain decision, subject to C-GAP-D's ruling on whether it is worth doing at all. |
| **2** | `d(1.500) − d(0.000) <= −5` bits, but monotonicity **or** the share prediction fails | **PARTIAL.** Sub-bin frequency sensitivity is real but the specified mechanism is not what produces it. Report the shape. Authorises nothing. The Architect owes a revised mechanism before any further frequency arm. |
| **3** | `d(1.500) − d(0.000) > −5` bits | **REFUTED.** Sub-bin frequency offset does **not** explain the ROW 0g residual. Per 11.4's attribution, the residual is then **B2's fusion arithmetic**. 🔴 **The Architect's mechanism hypothesis is dead and must be recorded as dead on the board** — not softened, not held open. |
| **4** | anything else, incl. boundary values or a straddling CI | **INCONCLUSIVE.** Report, propose a power increase, authorise nothing. |

### 4.3 Resolvable distance, stated while drafting (HK-021(m))

`n_err` is an integer bit count; the quantum is **1 bit**. At M=40 the bootstrap half-width
on a median bit count is expected to be order **1–2 bits**. The ROW 1/3 bar sits at **5
bits**, i.e. roughly **3× the half-width and 5 quanta** from no-effect. The predicted effect
at δ=1.5 (a −9.34 dB loss on the dominant window) should be far larger than 5 bits.

**If the achieved half-width exceeds 2.5 bits, ROW 4 and escalate — do not read ROW 1 or ROW
3 through a blunt instrument.** For calibration of what "large" means here: the real-audio
residual this arm is trying to explain is **3 bits**.

---

## 5. What this arm does NOT do

- Does **not** license any `src`/`native` change (HK-011). **Naming a fix is not applying
  one.**
- Does **not** re-open ROW 0g, `tasks.md` §4.3, or the Phase 1 gate. They stay VOID. This is
  a **new question with its own pre-registration**, not a re-read of a closed gate with a
  better metric.
- Does **not** propose or imply a `K_FREQ_OSR`/`K_TIME_OSR` 2→4 change. That is on the
  closed-arms list and would earn its own pre-registration with a false-positive primary.
  **Per-candidate fine frequency *estimation* is a different mechanism** — a scalar offset
  feeding the diagnostic coherent mixer, not a change to production candidate generation —
  and must not be conflated with it in any downstream report.
- Does **not** revive time-position refinement, which is dead three times over. The
  distinction between the two axes is the whole point of §1.2 and must survive into the
  report.
- Does **not** call Route B2 alive or dead.

---

## 6. Handover

QA runs, reports, **stops.** No push, no merge, no `pre_merge_check.py`
(HK-014/HK-010/HK-006). Harness under
`qa/rr-study/r2-coherent-llr-instrument/`, importing `coherent_llr_ctypes.py`'s existing
pins.

🔴 **N14 applies, and this directory is where all three prior occurrences happened.** Derive
every results filename from a UTC timestamp and refuse to overwrite a tracked file. **Do not
add a fourth script to that list.**
