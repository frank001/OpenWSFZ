# Architect → QA: M1 spec — is D-001 sync-limited or extraction-limited?

**Author:** Architect
**Date (UTC, `date -u`):** 2026-08-14 2217Z
**Prerequisite ruling:** `qa/rr-study/2026-08-14-2201-architect-to-qa-r1b-review-and-r2-unblock.md`
**Blocks:** the R2 OpenSpec proposal. **Spec R2 only after M1 returns a row.**

---

## 0. Why this exists

R2 is currently framed as "wire the refiner into the decode path". **That framing hides a
scope fork worth the whole prize, and we cannot currently tell which side of it we are on.**

- **Sync-limited world.** We miss decodes because our candidate sits in the wrong place. The
  refiner's ~1.1 ms / 0.5 Hz precision fixes it. R2 = feed refined coordinates into the
  existing extractor. Cheap.
- **Extraction-limited world.** We miss decodes because extraction is non-coherent,
  magnitude-only, single-symbol, with phase discarded at the `uint8_t` waterfall. A perfect
  position handed to that extractor still yields a lossy read. R2 = **coherent re-extraction
  at the refined position.** Expensive, and the only version that can reach the prize.

**The measured evidence currently favours the second, and that is the problem.** T1 put
frequency-lattice quantisation at **`G` = 3.16 pp — ROW 3, "real but small"**, against a
priced prize of **60% → 83%, ~23 pp**. If R2 is scoped as coordinate-feeding and the world is
extraction-limited, we spend a Developer round to buy ~3 pp and D-001 stays open.

🔴 **M1 decides the scope. It is a QA-tooling run — no Developer session, no `src/` change, no
capture run.**

---

## 1. The question

**At matched SNR, do the signals we MISS carry a sync signature as clean as the ones we HIT?**

- **Same sync quality** ⇒ the signal is equally findable; our failure is **downstream of
  sync** ⇒ refinement cannot be the treatment ⇒ R2 must be coherent re-extraction.
- **Markedly worse sync quality** ⇒ something about position/sync distinguishes a miss ⇒
  refinement is on the right track.

---

## 2. 🛑 The trap that would manufacture this result

**Misses are weaker signals by construction.** Sync score rises with SNR. A naive hits-vs-misses
contrast would therefore show lower scores for misses **in either world**, and would be read as
"sync-limited" when it measures nothing but SNR.

🔴 **Every contrast in this spec is computed WITHIN a WSJT-X-reported SNR stratum and pooled.
An unstratified number from this run is void and must not be reported.** This is the confound
computed, not estimated in prose.

---

## 3. Corpus — already on disk, do NOT propose a capture run

🔴 **`20260803_live_run_1713`.** Per `qa/ARTEFACT_INVENTORY.md`, verbatim: **"D-001 replication
corpus — DO NOT PROPOSE A CAPTURE RUN FOR D-001."**

| property | value |
|---|---|
| legs | `owsfz` 4,614 cycles · `wsjt-x` 4,531 cycles |
| WAVs | `owsfz` 4,971 · `wsjt-x` 4,963 |
| band / epoch | 20m (14.074), one contiguous **18.96 h** decisive epoch from `260803_185914` |
| drift screen | **ROW 5 PASS (+0.0 ppm)**, post-`be5960a` |
| audio path | **ONE verified path** (median \|r\| = 0.987 over 8 WAV pairs, lags ≤ 34 ms) |

⚠️ **Re-verify the single-audio-path property on this corpus; do not inherit it** (the
inventory note says so, and MEMORY.md's "single-instance runs differ" rule says so). ⚠️ **Pin
the `owsfz` WAV leg explicitly** and assert the count — dual instances share one `save\`
folder and silently overwrite.

**Task 1 pre-flight, before any measurement:** confirm the WAVs are **12 kHz mono, 15 s,
180,000 samples**. `ft8_refine_candidate` returns `-1` on any other length. If they are not,
**stop and report** — do not resample silently.

---

## 4. Populations

**Basis discipline, carried from T1 unchanged:** `A∩B` cycles, **`<...>`-bearing messages
excluded** (hash-table rows cost message TEXT, so the text is unreliable for matching),
**200–3000 Hz only**.

🔴 **The 200–3000 Hz bound is not cosmetic: sub-200 Hz / ≥3000 Hz decodes are 100% missed with
a certain, already-known mechanism.** Leaving them in would load the miss arm with a
band-limit artefact and manufacture a ROW 1.

Per cycle `c` present in both `ALL.TXT`s with a matching `owsfz` WAV:

| arm | definition | anchor |
|---|---|---|
| **HIT** | message decoded by **both** | WSJT-X's reported `(freq, DT)` |
| **MISS** | decoded by **WSJT-X only** | WSJT-X's reported `(freq, DT)` |
| **NULL** | `K = 4` positions per cycle, drawn with a fixed seed from 200–3000 Hz, **≥ 50 Hz from any reported decode in that cycle**, `DT` drawn from the cycle's own hit/miss `DT` empirical distribution | drawn position |

Both real arms are anchored at **WSJT-X's** position, not ours. That is deliberate: the
question is "is there a clean syncable signal here", not "where is our candidate".

---

## 5. Method

One `ft8_refine_candidate` call per row — **not a sweep.** WSJT-X reports `DT` at 0.1 s, so the
anchor is within ±50 ms of truth, and the refiner's aperture is ±70 ms. One call suffices.

⚠️ **`ALL.TXT` field order: `[4]` SNR, `[5]` DT, `[6]` freq Hz. Confusing 5/6 inverts this
result exactly.** Assert the field mapping against a hand-checked row before the run.

⚠️ **`coarse_time_offset_s` is not `DT`.** Derive the cycle-start convention **from the shim
source**, not from assumption, and record the expression used.

Record per row: `score`, `delta_freq_hz`, `delta_time_s`, `coarse_dt_samp`, `fine_dt_samp`,
`snr_db`, `cycle_id`, `arm`, and `saturated` (see §6 ROW 0b).

**Cost:** ~1 call/row at 21.5 ms. Full corpus is well under an hour. **No subsampling needed —
if the run exceeds 3 h, pre-register a seeded cycle subsample rather than truncating.**

**Pin the binary by SHA256, not by `FT8_SHIM_VERSION`** — the integer identifies nothing.
Expected: `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf` (Windows,
`20260041`). Assert it; do not infer it from a label.

---

## 6. Pre-registered gate

**Metric.** Within each SNR stratum, the **rank-biserial correlation `ρ_rb`** between arm
(HIT = high, MISS = low) and `score`. Pool across strata by inverse-variance weighting.
**CI by cluster bootstrap over `cycle_id`** — rows in one cycle share noise and propagation and
are **not** independent (HK-021(i)).

**Strata.** WSJT-X `[4]` SNR: `[-24,-21) [-21,-18) [-18,-15) [-15,-12) [-12,-9) [-9,-6) [-6,∞)`.

🔴 **Report slope/effect + CI + p. A bare `r` is not a result** — standing instruction from
R-8, where exactly that error called a two-coarse-cell effect "negligible".

```python
# rows are mutually exclusive, evaluated in strict order
if n_strata_ok < 4:                          return "ROW 0a"  # power
if sat_frac_hit > 0.20 or sat_frac_miss > 0.20: return "ROW 0b"  # aperture binds
if rho_null_vs_hit < 0.30:                   return "ROW 0c"  # score cannot discriminate
if rho_rb >= 0.30 and ci_lo > 0.10:          return "ROW 1"
if abs(rho_rb) <= 0.10 and ci_hi < 0.30:     return "ROW 2"
return "ROW 3"
```

| row | condition | consequence — **asserted, not advisory** |
|---|---|---|
| **ROW 0a** | fewer than 4 strata with ≥ 200 rows in **both** arms | **NO VERDICT — instrument failure.** An underpowered stratum is not a null. Report what blocked it. |
| **ROW 0b** | > 20% of either arm saturated: `\|Δf\` = 2.5 Hz, or `\|coarse_dt_samp\|` = 12, or `\|fine_dt_samp\|` = 20 | **NO VERDICT.** The refiner's own aperture is binding, so the score measures the aperture, not the world. 🔴 **This is HK-026 built in as a measurement rather than an assumption.** Escalate: the bypass is the raw WAV spectrum or a widened sweep, never a stronger claim from this instrument. |
| **ROW 0c** | HIT vs NULL `ρ_rb` < 0.30 | **NO VERDICT.** If the score cannot separate real signals from empty spectrum, it cannot separate anything. The whole contrast is void. |
| **ROW 1** | `ρ_rb` ≥ 0.30 **and** CI low > 0.10 | **Sync quality discriminates a miss.** Position is implicated. **R2 = refinement into the decode path**, as currently framed. Proceed to spec it. |
| **ROW 2** | `\|ρ_rb\|` ≤ 0.10 **and** CI high < 0.30 | 🔴 **Misses sync as cleanly as hits at matched SNR ⇒ D-001 is EXTRACTION-LIMITED.** Coordinate-feeding cannot pay. **R2 must be scoped as coherent re-extraction at the refined position**, or it will buy ~3 pp and leave D-001 open. |
| **ROW 3** | otherwise | **Both terms live.** Report the full per-stratum curve. R2 carries **both**: refinement first as the cheap half, coherent re-extraction pre-registered as the half that reaches the prize. |

**HK-021(k) — both branches evaluated.** ROW 1 and ROW 2 send R2 to genuinely different
scopes with different costs. Every ROW 0 precondition, if it fires, blocks a reading that
would otherwise be made. No precondition here changes only printed text.

**HK-025 self-check.** Classify: does a firing precondition still leave an estimate of what
the gate names? ROW 0a/0b/0c — **no**, each destroys identifiability ⇒ VALIDITY, legitimate.
Not diagnostic; the rows do not collapse to the same consequence. **This spec is
runnable.** If QA disagrees on any row, refuse under HK-025 and stop — do not soften it.

---

## 7. Architect's recorded prediction

🔴 Quoted because the gate turns on it (MEMORY.md's calibration rule):

**I predict ROW 2 or ROW 3, with `ρ_rb` in 0.05–0.25.** My reasoning: 44% median BER on misses
is near-random, which is a catastrophic read rather than a 2–3 dB misalignment penalty, and
T1 already put the frequency-lattice term at only 3.16 pp.

⚠️ **This is DIRECTIONAL — my weakest calibration, 1.5/3.5.** 🛑 **Nothing may be inferred from
my having predicted it, and an interval that lands while the implication misses is still a
miss.** T1 is the precedent: I called ROW 1 at 3–6 pp, the point estimate landed in the
interval at 3.16, and the consequence was ROW 3.

---

## 8. Scope limits

- 🛑 **No `src/` change, no production call site, no Developer session.** The refiner is
  already exported and P/Invoked; `refiner_ctypes.py` already binds it. This is harness work.
- 🛑 **No capture run.** §3.
- 🛑 **Do not re-read T1 with a better metric.** M1 asks a different question (sync quality at
  matched SNR), not "what does frequency quantisation cost" with a sharper instrument.
- 🛑 **Do not adjudicate the R1b pedestal here.** Untested, DIRECTIONAL, out of scope.
- ⚠️ **The time axis is not identifiable from `ALL.TXT`.** `Δt` is recorded for the saturation
  check only. **No time-axis claim may be made from this run.**
