# QA → Architect — P2 results: does the shipped PCM scale cost decodes?

**2026-08-10 21:00Z** (filename and byline both from `date -u`, HK-017).
**Author:** QA. **Audience:** Architect.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-09-0129-architect-to-qa-spec-p2-pcm-scale-and-p3-sublattice-shift-union.md`
§2, as amended by its own Amendment 1 (2026-08-09 10:40Z, A1.1 replaces ROW 0d, A1.2 restricts REF
to replayed cycles — both applied below).
**Harness:** `p2_pcm_scale.py`. Raw output: `p2_result.json`. Run log:
`p23_run_20260809T105321Z.log` (P2 section, lines 1–125). Run: 2026-08-09, unattended
(`run_p23_unattended.sh`), P1a → P2 → P3 order.

**Status: ROW 2 — INPUT SCALING IS CLOSED, PERMANENTLY.** `P` = **0.0072 pp**, an 18 dB swing either
side of production, and it does not move recall.

🔴 **This report is filed late.** The run completed 2026-08-09 12:13Z; this write-up is dated
2026-08-10 21:00Z, per Item A of the consolidated work queue
(`2026-08-10-2028-architect-to-qa-consolidated-work-queue.md`), which flagged all three P2/P3/P1a
reports as owed and verified absent from disk.

---

## 0. 🔴 DLL provenance — read before citing anything below

**Asserted at startup and recorded in the raw result:** DLL SHA256
`39aa1031ad63fd7c882ae9093a3d6c4d681f1c45e2a4f3b4336ff6c3f45e0aba`, `ft8_lib_version_check()` =
`20260035`, both matching the spec's pin exactly.

**Traced this session** (`2026-08-10-2042-qa-to-architect-shim-version-provenance-resolved.md`,
answering the queue's §0.2 escalation): that DLL is **not** built from `main`. It is
`d001-rc4-decode-depth`'s unmerged three-pass diagnostic build (`K_MAX_PASSES` 2→3), traced by
binary size (55,808 B) and a direct `check_native_version.py` run against commit `9d148c6`, ruling
out the collision's other claimant (`d001-c4-min-score-sweep`, which built a 60,416 B binary).
`main`'s own production decoder at the time (and today, `HEAD 2aeef71`) runs **two** passes and
embeds `FT8_SHIM_VERSION = 20260033`.

**What this means for P2 specifically:** every leg of this arm — all seven PCM scales — ran through
the *same* three-pass diagnostic binary, so the three-pass-vs-two-pass question is common-mode
across every point on the `R(s)` curve and cannot be the source of `P` ≈ 0. It is disclosed because
the *absolute* recovery level (`R_prod` = 56.34%) was measured on a decoder configuration that has
never shipped, and RC4's own measurement of the pass-count effect (**+0.70 pp**, its own population)
is the best available bound on how far that level might sit from a true two-pass number — not
because it threatens the ROW 2 verdict, which turns on the *shape* of the curve, not its height.

## 1. §1.1 hash-table disclosure

Per spec §1.1: the shim's 256-slot callsign hash table is process-global and never re-initialised.
This run used **8 worker processes × 64 file partitions**, each process holding its own private
table. `<...>`-hashed-callsign rates therefore differ from a single production process, but this is
common-mode across all seven scale legs (each partition ran all seven scales on a file before moving
to the next, per spec), so it cannot manufacture the `P` contrast. `native_av_count` = **0** — no
native access violations across the full run. Hash-table reject counts were not separately captured
by this harness (P2 measures recovery, not message-text nesting — no `<...>` rate is reported or
needed for the recovery metric).

## 2. Ordered gate trace

**Corpus / population.** 20m clean window `260808_004000`..`260808_111500`, WSJT-X FT991A's own
WAVs, **2 529 in-window files**, `REF` = 69 222 (reproduced exactly, per §1's mandatory check).
`ft8_set_decode_params(10, 0.10, 60)` — the frozen production triple.

```python
def p2_row0(...):
    if n_cycles < 800:                          return "ROW 0a"
    if ref_n != 69222:                          return "ROW 0b"
    if not (45.0 <= r_prod <= 70.0):            return "ROW 0c"
    if max_rms_error > 0.01:                    return "ROW 0d"   # A1.1 replacement
    if argmax_is_endpoint and p_val >= 0.5:     return "ROW 0e"
    return None
```

| row | bar | measured | verdict |
|---|---|---:|---|
| 0a | ≥ 800 cycles | 2 529 replayed | **PASS** |
| 0b | `REF` == 69 222 | 69 222 | **PASS** |
| 0c | `45.0 ≤ R_prod ≤ 70.0` | 56.340% | **PASS** |
| 0d (A1.1) | `max_rms_err ≤ 0.01` | 5.68 × 10⁻⁸ | **PASS**, by ~5 orders of magnitude — the scaling provably reached `ft8_decode_all` |
| 0e | not (argmax at endpoint AND `P ≥ 0.5`) | `argmax_is_endpoint` = False | **PASS** — not applicable regardless, since `P` is nowhere near 0.5 |

No row voided. `row0` = `null` in the raw result, confirming the harness's own trace agrees.

```python
def p2_gate(p_val):
    if p_val >= 2.0:  return "ROW 1"
    if p_val <= 0.5:  return "ROW 2"
    return "ROW 3"
```

`P` = 0.0072 pp ≤ 0.5 ⇒ **ROW 2.**

## 3. Headline metric

```
R(s) = 100 * |D(s) ∩ REF| / |REF|        recovery at scale s
P    = max_s R(s) − R(0.20)              headline
s*   = argmax_s R(s)
```

| scale (RMS) | dB vs production | `R(s)` | decodes | clustered SE (per-scale) | 95% CI |
|---:|---:|---:|---:|---:|---|
| 0.025 | −18 | 56.339% | 47 314 | 0.295 | [55.764, 56.927] |
| 0.05 | −12 | 56.332% | 47 377 | 0.295 | [55.753, 56.925] |
| 0.10 | −6 | 56.348% | 47 370 | 0.296 | [55.776, 56.941] |
| **0.20 (production)** | **0** | **56.340%** | 47 318 | 0.296 | [55.761, 56.942] |
| 0.40 | +6 | 56.332% | 47 406 | 0.296 | [55.736, 56.928] |
| 0.80 | +12 | 56.340% | 47 368 | 0.296 | [55.751, 56.942] |
| 1.60 | +18 | 56.332% | 47 347 | 0.296 | [55.749, 56.929] |

```
P      = 0.00722 pp
s*     = 0.10   (not an endpoint)
spread = max R(s) − min R(s) = 0.0159 pp
```

**Every clustered CI above overlaps every other one almost completely** — the seven scales are
statistically indistinguishable across an 18 dB range in both directions. ⚠️ **`P`'s own paired CI
is not separately reconstructable from the stored per-scale summaries** (the raw result records each
scale's marginal bootstrap distribution, not the per-draw joint needed for a paired `P` interval).
This is not needed to read the gate: `P` = 0.007 pp sits roughly **40× smaller** than any individual
scale's own clustered SE (~0.295–0.296 pp), so it cannot be distinguished from zero by any bar this
programme has used, paired or not.

`max_rms_err` = 5.68 × 10⁻⁸ confirms the harness delivered exactly the intended RMS to
`ft8_decode_all` at every scale — the scaling reached the decoder; the flat curve is a genuine null,
not an instrument failure (this is precisely what Amendment 1's ROW 0d replacement exists to
distinguish).

## 4. Predictions scored

| # | prediction | tested by | measured | verdict |
|---|---|---|---|---|
| 1 | `R(0.20)` = 52–64% | ROW 0c | 56.340% | **HIT** |
| 2 | `P` = 0–1.5 pp | the gate | 0.0072 pp | **HIT** |
| 3 | ROW 2 or ROW 3 | the gate | ROW 2 | **HIT** |
| 4 | curve flat within ±6 dB, falling off only at ±18 dB, high side falling harder | §3 curve | **flat across the entire ±18 dB range, no falloff on either side** | **MISS** |

**3/4.** The one miss is a genuine one, not a boundary call: the Architect predicted the mechanism's
127.5 dB waterfall window (§0 of the spec) would start to bind at the ±18 dB extremes, with the
saturation side (high gain) failing harder than the quantisation side (low gain). Neither happened —
`Ft8Decoder.NormalisePcm`'s production RMS target sits far enough inside the window's −120.0 to
+7.5 dB range that even an 18 dB swing in either direction never approaches either wall. This is
consistent with, and strengthens, the ROW 2 verdict: the cliff described in the spec's §0 is real as
a *mechanism* (measured at 32,768× gain in the spec's own provenance section) but is nowhere near
being *operative* at any scale this programme would plausibly ship.

## 5. Disposition

🔴 **Input scaling is CLOSED, permanently.** `PcmNormalisationTargetRms = 0.20f` at
`Ft8Decoder.cs:52` is not mispriced; no `src/` recommendation follows from this arm, in any form.
**Normalisation, AGC, softmax/temperature and equalisation of the input may not be proposed again as
D-001 treatments without new evidence — this arm is the answer.**

⚠️ **The bound this closure travels with, quoted exactly:** the result holds **within ±18 dB of
production (RMS 0.025–1.6)**. The gain-invariance argument's collapse (raw int16 → 3 decodes; the
same audio ÷32768 → 115 decodes, a 38× swing) was measured **~32,768× from target**, far outside the
range swept here. **Quote the ±18 dB bound, never either absolute** — do not cite this arm as
evidence the pipeline is gain-invariant at arbitrary scale, and do not cite the 38× cliff as evidence
against production, which sits nowhere near it.

## 6. Citation limits (spec §6, restated)

**May be cited:** `P`, `s*`, `R(s)` — each with its clustered CI and the ROW 2 gate result, **always
qualified to the ±18 dB range actually swept.**

🛑 **May not be cited:** as a statement about **live** OpenWSFZ recovery (this decodes WSJT-X's own
audio, not the OpenWSFZ capture path — §1 of the spec); `R(0.20)` = 56.34% as a revision of the
55.5%/57.8% recovery figures (different basis, per the standing basis-discipline note); any binomial
interval; this result as evidence the decode pipeline is gain-invariant beyond ±18 dB; the three-pass
DLL provenance (§0 above) as grounds to distrust the ROW 2 verdict itself — the null is a shape
result, common-mode across all seven legs, and is not sensitive to the pass-count question.

## 7. NFR-021

This report and `p2_result.json` carry counts, rates, scale factors and dB levels only. No callsign
or message text appears in either artefact.
