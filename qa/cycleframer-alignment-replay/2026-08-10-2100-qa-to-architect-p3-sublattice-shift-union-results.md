# QA → Architect — P3 results: does sub-lattice placement cost decodes?

**2026-08-10 21:00Z** (filename and byline both from `date -u`, HK-017).
**Author:** QA. **Audience:** Architect.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-09-0129-architect-to-qa-spec-p2-pcm-scale-and-p3-sublattice-shift-union.md`
§3, as amended by its own Amendment 1 (2026-08-09 10:40Z — A1.2 restricts REF to replayed cycles,
A1.3 discloses pre-echoes, both applied below; A1.1 concerns P2 only and does not touch this arm).
**Harness:** `p3_shift_union.py`, shared machinery `p23_common.py`. Raw output: `p3_result.json`.
Run log: `p23_run_20260809T105321Z.log` (P3 section, lines ~126–244). Run: 2026-08-09, unattended
(`run_p23_unattended.sh`), immediately after P2 in the same process family.

**Status: ROW 3.** `S_all` = **4.27 pp** [4.11, 4.42] — the largest single-arm effect in the D-001
programme at the time it ran — but **ROW 1 is blocked by the guard**: `X_guard` = 0.897, meaning the
shift-union manufactures nearly as many non-`REF` decodes as it recovers real ones. Sub-lattice
placement is real; a union bolted outside the decoder is not the production fix.

---

## 0. 🔴 DLL provenance — read before citing anything below

Identical disclosure to P2 §0 (same run, same process family, same binary): DLL SHA256
`39aa1031ad63fd7c882ae9093a3d6c4d681f1c45e2a4f3b4336ff6c3f45e0aba`, `ft8_lib_version_check()` =
`20260035`, both asserted at startup and matching the spec's pin.

**Traced this session** (`2026-08-10-2042-qa-to-architect-shim-version-provenance-resolved.md`):
this is `d001-rc4-decode-depth`'s unmerged **three-pass** diagnostic build (`K_MAX_PASSES` 2→3), not
`main`'s two-pass production decoder (`FT8_SHIM_VERSION 20260033` on `main` today). RC4's own
measurement bounds the pass-count effect at **+0.70 pp** on its own population — smaller than this
arm's `SE_S_all` (0.080 pp) but not negligible next to it, and P3 was never itself tested at two vs
three passes. **All five legs (`base`, `F+`, `F−`, `T+`, `T−`) ran through the identical three-pass
binary**, so the three-pass configuration is common-mode across the shift-union contrast and cannot,
by itself, manufacture `S_all`. It **could** inflate the absolute decode counts each leg contributes
to the union (more passes → more candidates → more opportunities for the union to add a `REF`
decode), which is a reason for mild caution around the precise magnitude of `S_all`/`S_freq`/
`S_time`, not around their sign or ROW 3 disposition. `X_guard`, being a ratio internal to the gained
set, is less exposed to this than the absolute pp figures.

## 1. §1.1 hash-table disclosure

Same as P2: 8 worker processes × 64 partitions, process-private 256-slot hash tables, all five shift
legs for a given file run consecutively within one process (spec §1.1, mandatory for common-mode
`<...>` handling across `base`/`F+`/`F−`/`T+`/`T−`). `native_av_count` = **0**.

## 2. Ordered gate trace

**Corpus / population.** Identical to P2: 20m clean window, 2 529 in-window WSJT-X FT991A WAVs,
`REF` = 69 222. Lattice: `K_FREQ_OSR = K_TIME_OSR = 2` ⇒ 3.125 Hz / 0.08 s grid. Shift magnitudes:
±1.0417 Hz (= 3.125/3), ±320 samples (= 0.08 s/3 @ 12 kHz).

```python
def p3_row0(...):
    if n_cycles < 800:                return "ROW 0a"
    if ref_n != 69222:                return "ROW 0b"
    if not (45.0 <= r_base <= 70.0):  return "ROW 0c"
    if synth_freq_err_hz > 0.25:      return "ROW 0d"   # shift control, MANDATORY, runs first
    if u_equals_base:                 return "ROW 0e"
    if se_s_all > 1.0:                return "ROW 0f"
    return None
```

| row | bar | measured | verdict |
|---|---|---:|---|
| **0d (runs first, per spec)** | synthetic shift control error ≤ 0.25 Hz | applied +1.0417 Hz, mean reported +1.0084 Hz, **error 0.0332 Hz**, 356 matched messages | **PASS**, and inside prediction 5's tighter <0.05 Hz bound |
| 0a | ≥ 800 cycles | 2 529 replayed | **PASS** |
| 0b | `REF` == 69 222 | 69 222 | **PASS** |
| 0c | `45.0 ≤ R_base ≤ 70.0` | `R_base` = 56.322% | **PASS** |
| 0e | `U ≠ base` | `n_union` = 75 967 ≠ `n_base` = 47 319 | **PASS** |
| 0f | `SE(S_all) ≤ 1.0` | 0.0800 pp | **PASS**, comfortably (12.5× headroom) |

No row voided (`row0` = `null` in the raw result). **The shift control, run first as the spec
requires, confirms the Hilbert-mixer frequency shift and the integer-sample time shift both reach
the decoder correctly** — this is the check P1's own ROW 0d should have been (spec §3.3), and it
passed cleanly.

```python
def p3_gate(s_all, x_guard):
    if s_all >= 3.0 and x_guard <= 0.50:  return "ROW 1"
    if s_all <= 1.0:                      return "ROW 2"
    return "ROW 3"
```

`S_all` = 4.266 ≥ 3.0, **but** `X_guard` = 0.897 > 0.50 ⇒ the ROW 1 conjunction fails on the guard
alone ⇒ **ROW 3.**

## 3. Headline metrics

```
U       = base ∪ F+ ∪ F− ∪ T+ ∪ T−
S_all   = 100 * |REF ∩ (U \ base)| / |REF|
S_freq  = 100 * |REF ∩ ((F+ ∪ F−) \ base)| / |REF|
S_time  = 100 * |REF ∩ ((T+ ∪ T−) \ base)| / |REF|
X_guard = |U \ base \ REF| / |U \ base|
```

| metric | value | clustered 95% CI | SE |
|---|---:|---|---:|
| `R_base` | 56.322% | [55.751, 56.899] | 0.291 |
| **`S_all`** | **4.266 pp** | **[4.107, 4.424]** | 0.080 |
| `S_freq` | 2.405 pp | [2.284, 2.518] | 0.061 |
| `S_time` | 3.011 pp | [2.878, 3.129] | 0.066 |
| `X_guard` | 0.897 | — (ratio, point estimate per spec) | — |

🔴 **`S_time` (3.011 pp) > `S_freq` (2.405 pp).** T1 already bounded the frequency axis (`G` =
3.16 pp, a floor); the reference's own DT resolution (0.1 s) is coarser than the 0.08 s decode step,
so **the time axis has never been directly measurable from `ALL.TXT` before this arm** — this
result is the first direct measurement of it, and it is the *larger* of the two axes.

```
n_base = 47 319       n_union = 75 967       n_gained = 28 648
n_gained → REF-matched: 2 955 of 28 648 (10.3%)
```

The union's raw decode count rises by 60.5% (47 319 → 75 967) but only **2 955** of the 28 648
additional decodes land inside `REF` — the rest (25 693, or 89.7% of what was gained) are decodes
the union produced that neither WSJT-X instance corroborated. That is `X_guard` = 0.897 restated as
raw counts rather than a ratio: **the union manufactures roughly nine spurious/unverifiable decodes
for every one it recovers that WSJT-X also heard.**

## 4. Predictions scored

| # | prediction | tested by | measured | verdict |
|---|---|---|---|---|
| 1 | `S_all` = 1.5–5.0 pp | the gate | 4.266 pp | **HIT** |
| 2 | ROW 3 | the gate | ROW 3 | **HIT** |
| 3 | `S_freq` > `S_time` | §3.2 | `S_freq` 2.405 < `S_time` 3.011 | **MISS** (reversed) |
| 4 | `X_guard` = 0.35–0.65 | the guard | 0.897 | **MISS**, and this is the one that decided the row |
| 5 | shift control error < 0.05 Hz | ROW 0d | 0.0332 Hz | **HIT** |

**3/5.** Both misses were flagged in advance by the Architect's own Amendment 1 A1.3 (2026-08-09
10:40Z): the 24-file smoke test already showed `X_guard` = 0.817 (a "genuine early miss on a
recorded prediction, called now, in advance"), which correctly anticipated ROW 1 being blocked by
the guard at full scale. The `S_freq`/`S_time` ordering miss is new information, not previously
flagged, and is arguably the more consequential of the two misses (§3 above) — it means the axis
`ALL.TXT` could never measure directly is the larger contributor, not the smaller one.

## 5. Disposition

🔴 **Sub-lattice placement is real** — `S_all` = 4.27 pp clears the arm's own 3.0 pp ROW 1 threshold
by a wide, well-bounded margin (SE 0.080, CI excludes both 3.0 and any value near it from below).
**But the production recommendation the ROW 1 consequence text would have licensed does not follow**,
because the guard fired: `X_guard` = 0.897 means **this specific instrument — five separately-run
decodes unioned outside the decoder — cannot distinguish "recovering a real decode" from
"manufacturing an unverifiable one" well enough to read as a clean recall gain.**

Per the spec's own ROW 3 consequence text: *"If the `X` guard is what blocked ROW 1, say so
explicitly — that is 'the union buys decodes but also manufactures them,' a different finding from
'shifting does nothing,' and it argues for refinement **inside** the decoder rather than a union
bolted outside it."* That is the reading here. 🛑 **This does NOT license `K_FREQ_OSR`/
`K_TIME_OSR` 2→4 at `ft8_shim.c:469-470`** — a finer OSR keeps a single scoring/CRC pass per
candidate; this union ran the decoder five times independently and OR'd the results, so its false-
positive inflation is evidence about *unioning*, not about *oversampling* the lattice, in either
direction. Sizing an OSR change earns its own pre-registration, per the standing bar — this arm does
not shortcut it.

## 6. Citation limits (spec §6, restated)

**May be cited:** `S_all`, `S_freq`, `S_time`, `X_guard` — each with its clustered CI (`X_guard` as a
point estimate per spec) and the ROW 3 gate result; the shift-control result (0.0332 Hz error);
`X_guard` must travel with `S_all` in **every** citation — 🛑 quoting `S_all` = 4.27 pp alone, without
`X_guard`, misrepresents this arm as a clean recall gain.

🛑 **May not be cited:** as a statement about **live** OpenWSFZ recovery (WSJT-X's own audio, not the
capture path); `S_all` as a promise of production gain (the production form would be an OSR change,
not a union, and has not been measured); as license for `K_FREQ_OSR`/`K_TIME_OSR` 2→4 in any
direction; any binomial interval; any restatement of `G`, `D_int`, `U`, `M`, `A`, or the recovery
headline.

## 7. NFR-021

This report and `p3_result.json` carry counts, rates, frequency/time shift magnitudes and cycle
counts only. No callsign or message text appears in either artefact.
