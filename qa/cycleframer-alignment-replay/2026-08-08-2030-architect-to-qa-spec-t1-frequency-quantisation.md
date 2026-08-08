# Architect → QA: T1 spec — does candidate-grid frequency quantisation cost us decodes?

**Author:** Architect, 2026-08-08 (20:30 UTC, `date -u`, per HK-017). Repo `main` at `2dc8a5c`.
**For:** QA. §6 is for the Captain.
**Status:** **NOT AUTHORISED TO RUN.** This is a spec per HK-015; QA owns the decision to scope it
and the dev-task if one is needed. No `src/` change, no capture, no rebuild — every input is on disk.
**Supersedes nothing.** Adds an arm; retracts one hypothesis of my own (§0.2).

---

## 0. Why this exists, and what changed today

### 0.1 The reframing this arm tests

D-001 is localised to the decode stage (RC1: `f_nocand = 0.0924`; 90.8% of in-band misses had a
candidate). Within that stage, the sub-stage has now been narrowed by numbers already on the board
but never placed side by side:

| quantity | value | source |
|---|---:|---|
| BER of candidates we **did** decode (matched-hit control) | median **2.9%** | W1 §3 |
| BER our BP+OSD corrects at 50% success (`B50`) | **11.3%** | W1 §8 |
| BER of candidates present that **failed** (THE 135) | median **44.0%**, p10 17.2% | W1 §8 |

That distribution is **bimodal, not a gradient**. The misses do not sit just past the correction
threshold — they sit at ~4× it, out on the near-flat tail where P(decode) ≈ 2%, approaching the 50%
coin-flip floor. `E = 4.28` of 135 (~3%) is the *complement* of the finding: **~97% of the missed
population was not correctable by any error-correction change**, because the soft bits arriving at
LDPC carry almost no information.

W1 reported `E` correctly and stopped, because its reading rule explicitly forbade editorialising on
the 1–15 band. The inference was never drawn. **The failing sub-stage is demodulation — how symbols
become LLRs at a located candidate — not error correction.** This arm tests one concrete, code-level
mechanism for that.

### 0.2 🔴 A hypothesis of mine died today; recording it so it is not re-chased

I proposed that hash-table saturation discards decodes at `ft8_shim.c:1372`. **It does not.**
`message.c:594–614` (`lookup_callsign`) writes the literal `"<...>"` on an unknown hash, and **both
call sites (431, 782) discard the return value** — `ftx_message_decode` returns `RC_OK`. There is no
loss path. Do not re-scope it.

What is real, and is a **measurement** problem rather than a decode problem: `hashTableRejectCount`
ended at **35 379** on the 20m leg (against 595 on C.1's entire 68-cycle corpus), and **2 507 of our
45 258 decodes (5.5%) carry an unresolved `<...>` token, against 1 275 of 76 967 (1.7%) for the
reference** — ~3.3×, consistent with our 256-slot table saturating run-wide while the reference's
does not. Those are frames we demodulated and error-corrected *correctly* whose text cannot match the
reference. §3.2 excludes them here; §6.2 flags the separate question they raise.

### 0.3 The instrument check, already run — and it is itself evidence

Per HK-021 ("draft the gate by writing the code that evaluates it") I ran the positive control before
writing this. Residual `r` = distance from a reported audio frequency to the nearest multiple of
3.125 Hz, `r ∈ [0, 1.5625]`. Uniform-null is `mean_r = 0.781`, `frac(r < 0.5) = 0.320`.

| decoder | `mean_r` | `frac(r < 0.5)` | reading |
|---|---:|---:|---|
| **OpenWSFZ** | **0.2397 Hz** | **0.881** | on-grid; residual is integer-Hz **reporting rounding only** |
| **WSJT-X** | **0.7398 Hz** | **0.308** | indistinguishable from uniform ⇒ **off-grid, refined** |

20m leg, `artefacts/20260808_live_run_0016-8080/`, n = 45 258 / 76 967, whole-corpus.

This confirms the grid model from the code (`ft8_shim.c:1379-1381`: `freq_hz = (min_bin +
freq_offset + freq_sub/freq_osr) / symbol_period`, with `K_FREQ_OSR = 2` and `1/symbol_period =
6.25 Hz` ⇒ a **3.125 Hz lattice**) **empirically, from output alone.** It also demonstrates the
architectural difference directly: we report on a lattice; the reference does not, because it refines
sync below the lattice and we never do — `ftx_find_candidates()` goes straight into
`ftx_decode_candidate()` (`ft8_shim.c:1314-1335`) with no refinement step between.

⚠️ **My first run of this control used the wrong ALL.TXT column** (field 5 is DT, field 6 is
frequency) and produced exactly inverted numbers. The corrected figures are above. **Field indices
are 0-based on whitespace split: `[4]` SNR, `[5]` DT, `[6]` frequency Hz, `[7:]` message.**

---

## 1. The question

> Among decodes the reference makes, does our recovery depend on **where the signal sits inside our
> 3.125 Hz candidate lattice** — worse at a bin edge than at a bin centre?

A signal at a bin edge is demodulated up to **1.5625 Hz off, 25% of the 6.25 Hz FT8 tone spacing**,
with no refinement to correct it. If that is material, recovery falls with `r`.

---

## 2. 🛑 The trap that would manufacture this result

**Use the REFERENCE's reported frequency for BOTH the matched and the missed group.**

Our own reported frequency is on-grid *by construction* (`mean_r = 0.24`, §0.3). Computing `r` from
OpenWSFZ's frequency for the matched group and the reference's for the missed group would produce a
large spurious `G` that measures nothing but the lattice we already know about. Every `r` in this
measurement comes from the reference, for both groups, without exception.

---

## 3. Method

### 3.1 Populations

- **Reference** = the intersection of the two WSJT-X instances (a decode *both* made) — the same
  conservative definition the 08-08 report uses.
- **Matched** = reference decode for which OpenWSFZ 8080 produced the same `(cycle, normalised
  message)`. **Missed** = reference decode with no such OpenWSFZ row.
- Corpus: `artefacts/20260808_live_run_0016-808{0,1}/` (20m). Use the report's **clean window**
  (00:40–11:15 UTC), not the whole corpus.
- Replicate on the 17m corpus as a **secondary** report. 🛑 The 17m leg voided under its own ROW 0b,
  so it may be reported as replication only and **no row may be cited from it.**

### 3.2 Pre-registered exclusions

Applied before any statistic, to both groups symmetrically:

1. **Any decode whose text contains `<...>` on either side** — §0.2's contamination. Report the count
   excluded.
2. **Any reference decode outside 200–3000 Hz** — `ft8_shim.c:1183` makes those a *certain, different*
   mechanism (3.3% of misses). Leaving them in pollutes the missed group.
3. Cycles outside the clean window.

### 3.3 The metric

```python
STEP = 3.125  # Hz — from K_FREQ_OSR=2 and 6.25 Hz tone spacing; NOT a tunable
def residual(f_hz):
    m = f_hz % STEP
    return min(m, STEP - m)          # in [0, 1.5625]
```

Stratify the reference population into **quintiles of the observed `r`** (quantiles, per HK-021 —
never absolute `r` constants), and report recovery per quintile.

```
G = recovery(bottom r quintile) - recovery(top r quintile)   # percentage points
```

### 3.4 Mandatory control

Recompute `G` **within quintiles of reference-reported SNR** (quantiles, not dB constants; and always
the reference's SNR — never ours, per `DEFECT-snr-reported-gain-error.md`). Report `G` per SNR
quintile. If `G` is carried by a single SNR quintile, say so explicitly; the headline `G` alone would
then be misleading.

### 3.5 🛑 Scope limit — do NOT extend this to the time axis

Our time lattice is 0.08 s (`K_TIME_OSR = 2` on a 0.16 s symbol). The reference reports DT at **0.1 s
resolution — coarser than our own grid step.** The time residual is therefore **not identifiable from
`ALL.TXT`**, and an attempt would be an HK-021(c) failure by construction. If the time axis is wanted
it needs a different instrument, specced separately.

---

## 4. Pre-registered gate

Rows mutually exclusive, strict order, boundary values fall to the inconclusive row.

```python
def t1_row(G, n_min_quintile, mean_r_ours, mean_r_ref):
    """G = recovery(bottom r quintile) - recovery(top r quintile), in pp."""
    if n_min_quintile < 500:      return "ROW 0"   # instrument failure, NOT a null
    if mean_r_ours >= 0.45:       return "ROW 0"   # our grid model is wrong
    if mean_r_ref  <  0.50:       return "ROW 0"   # reference is on our grid too: no contrast
    if G >= 4.0:                  return "ROW 1"
    if G <= 1.0:                  return "ROW 2"
    return "ROW 3"
```

| row | condition | consequence |
|---|---|---|
| **ROW 0** | any quintile under 500 decodes; **or** `mean_r_ours ≥ 0.45`; **or** `mean_r_ref < 0.50` | **NO VERDICT — instrument failure.** Report what blocked it. Do **not** read as evidence either way. |
| **ROW 1** | `G ≥ 4.0` pp | **Sync quantisation is a material mechanism.** Sub-bin refinement becomes the leading D-001 treatment candidate and outranks further parameter work. Costs a Developer session; the Captain decides. |
| **ROW 2** | `G ≤ 1.0` pp | **Refuted at material scale.** Frequency quantisation is not the mechanism. The demodulation thesis (§0.1) survives but must be tested another way — the remaining suspects are non-coherent single-symbol extraction and the absent time refinement, neither answerable from `ALL.TXT`. |
| **ROW 3** | otherwise | **Real but small.** Report the full quintile curve. Fold into framing; do not spend a Developer session on it alone. |

### 4.1 My prediction, recorded in advance so it can be checked against the result

**I expect ROW 1, with `G` in the 3–6 pp range.** Reasoning, so the bound is checkable rather than a
feeling: a 25%-of-tone-spacing offset costs roughly 1–2 dB of effective SNR, and the measured SNR
recovery curve runs about **3 pp per dB** through its mid-range (43.4% at −15…−10 dB → 57.9% at
−10…−5 dB). Quintile means contrast `r ≈ 0.16` against `r ≈ 1.40`, most of the available range. So
3–6 pp.

**`G` cannot plausibly exceed ~15 pp.** SNR is the dominant axis and quantisation can only be a
component. **A result above 15 pp is an instrument failure, not a finding** — most likely the §2
trap. Check the frequency source before reporting it.

If `G ≤ 1.0` (ROW 2) my §0.1 mechanism is wrong in its frequency half, and I would rather that be
recorded plainly than reasoned around.

---

## 5. Cost

Pure re-analysis of `ALL.TXT` files already gathered and inventory-verified. **No capture, no
rebuild, no `src/` change, no authorisation beyond QA's own.** The comparison harness
(`qa/endurance/2026-08-08-four-decoder-interim-comparison.py`) already builds the matched/missed sets
and already stratifies by SNR; this adds a residual column and a regrouping. Estimate **1–2 hours**,
dominated by wiring the exclusions in §3.2 correctly rather than by compute.

**NFR-021:** message text is read only to build match keys and to apply the `<...>` exclusion. No
message text, and no real callsign, may appear in the report or in any committed file — every figure
is a count, a rate, or a frequency statistic.

---

## 6. For the Captain

**6.1 This does not touch the D-009 Option B ruling** and does not ask for one. It runs whichever way
that goes.

**6.2 A separate, cheaper item that came out of §0.2 and is not part of T1.** The 2 507 unresolved-`<...>`
decodes (5.5% of our output, ~3.3× the reference's rate) cannot match the reference by text. They are
therefore counted as **misses**, and plausibly land in the **novel/FP** bucket where the plausibility
proxy can never resolve `...`. That bears on two live numbers — the **55.5% recovery** figure and the
**~4% FP rate**. Magnitude **not measured**; the fix is ~30 minutes (re-run the 20m comparison with
`<...>`-bearing rows excluded from both sides and report how far each number moves). I recommend it
runs **before** either figure is quoted further, but it is not part of this arm.

**6.3 A reproducibility hazard, unrelated to D-001, found while verifying §0.2.** Only `decode.c` is
vendored under `native/ft8_lib_build/patched/`. Every other translation unit — including
`message.c` — is compiled from **`C:\Temp\ft8_lib_headers`**, an untracked directory outside the repo
(`rebuild_shim.bat:9,20`). `message.obj` links from a source that exists nowhere in version control.
A `C:\Temp` clear would make the native library unbuildable and no commit would record why.

---

## 7. What this arm does not do

- **It does not measure the time axis** (§3.5) — the reference's DT resolution forbids it.
- **It does not test non-coherent single-symbol extraction.** `ft8_decode_multi_symbols()` exists in
  `decode.c` with **no call site**; whether multi-symbol extraction would help is a separate question
  needing a rebuild, and is not scoped here.
- **It does not re-open** RC1–RC4, C.1, C.2, or the §5 calibration. All closed; none re-derived here.
- **It proposes no capture run.** Every input is on disk and inventory-verified.
- **It does not merge or push** (HK-014), and authorises nothing (HK-015).

---

*Per HK-015 Architect → QA; the dev-task, if any, is QA's to author. Per HK-014 committed locally,
never pushed. Per HK-011 nothing here changes `src/`. Per HK-006 `pre_merge_check.py` is the
Captain's. Per HK-021 the gate above is executable, carries an explicit ROW 0, stratifies by
quantiles, takes its one constant (3.125 Hz) from the physical system rather than inventing it, and
states a falsifiable prediction with an upper bound in §4.1.*
