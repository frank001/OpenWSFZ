# QA → Architect — X3 results: does sub-lattice placement error cost more in a crowded cycle?

**2026-08-10 21:44Z** (filename and byline both from `date -u`, HK-017).
**Author:** QA. **Audience:** Architect.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-10-1808-architect-to-qa-spec-x3-lattice-crowding-interaction.md`.
**Harness:** `x3_lattice_crowding.py` (new). Raw output: `x3_result.json`. Wall clock: 18.8 min
(20m primary only; the base leg was reused from the ROW 0e pre-flight, so only the 4 shifted legs
cost decoder time here).

**Status: ROW 4 — inconclusive by the gate's own mechanical bar.** `I_20m` = **−1.375 pp**, 95% CI
`[−2.665, −0.197]`. The confidence interval **excludes zero** — this is not a flat null — but the
magnitude does not clear either the +2.0 pp (ROW 1) or −2.0 pp (ROW 3) bar, so the pre-registered
gate returns no reading. **80m replication was not run this session** — see §7.

---

## 0. 🔴 Read before anything else — three deviations from the spec, all disclosed in advance

1. **DLL pin.** The spec's own §0a/0b pin `39aa1031…` (shim 20260035). Per the Captain's explicit
   ruling this session (in answer to `2026-08-10-2042-qa-to-architect-shim-version-provenance-
   resolved.md`), that DLL is `d001-rc4-decode-depth`'s unmerged **three-pass diagnostic build**,
   not `main`. This harness pins `main`'s own committed decoder instead:
   `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, SHA256
   `f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015`, `ft8_lib_version_check()`
   confirmed **20260033** at startup (matches `main`'s current `FT8_SHIM_VERSION`). **X3 is
   therefore the first arm in the D-001 programme run against the correct two-pass production
   decoder rather than the RC4 diagnostic leftover.**
2. **ROW 0e's method.** Built and run twice — see §2.
3. **80m replication not run.** See §7.

---

## 1. Population, and a density-range caveat found while building this (disclose before citing `I_20m`)

`REF` = raw `A ∩ B`, 20m weekend corpus (69 222, matches P1/P2/P3/T1/X4 — ROW 0c PASS). Density
regimes use **X2's own definition, reused not re-derived**: per-cycle count of X2's *clean*
(hash+band-excluded) `REF` rows, `FLOOR ≤ 5`, `MID 6-13`, `OVERLAP 14-26`.

🔴 **20m's density distribution does not fit inside X2's regime ceiling.** X2's regimes were
calibrated primarily around 80m's own range. On 20m: median cycle density is **27** (min 4, max
49) — **1 385 of 2 529 cycles (55%)** exceed `OVERLAP`'s ceiling of 26 entirely and are excluded
from every regime this arm measures. Only **3 cycles** ever reach `FLOOR` on 20m (14 raw-`REF`
decodes — reported below for completeness, unusable for anything). **`I_20m` therefore
characterises only the density ~6–26 slice of 20m — the MID/OVERLAP contrast, not 20m's busiest
cycles, which this design cannot reach with X2's regime boundaries.** This is disclosed as a scope
limitation, not a defect: `MID` and `OVERLAP` are each comfortably populated (ROW 0d below), the
regime *boundaries* just don't reach 20m's own tail.

| regime | raw `REF` n | distinct freq clusters | ROW 0d bar (≥300 / ≥250) |
|---|---:|---:|---|
| FLOOR | 17 | 15 | not used (too small; not gated) |
| MID | 2 046 | 601 | **PASS** |
| OVERLAP | 21 234 | 2 231 | **PASS** |
| *(regime undefined — density > 26 or cycle absent from X2's density map)* | *45 925* | — | *excluded, disclosed here* |

---

## 2. ROW 0e — two methods, one disclosed correction

The spec's pre-flight instruction: *"Compute the clustered `SE(I)` from the base leg alone (which
P3 already establishes, and which costs one pass rather than five) plus the real per-regime
cluster counts."*

**First attempt (empirical, wrong quantity):** interpreted this as a fresh base-leg decode pass
(5.2 min) feeding a frequency-clustered bootstrap of the base leg's own **recovery-LEVEL** contrast
between MID and OVERLAP. Result: `SE` = **2.825 pp** — would have voided the arm as underpowered
(bar 0.75 pp).

**On inspection this was the wrong quantity.** Recovery *level* varies between regimes for many
reasons unrelated to lattice placement (propagation, SNR composition, decoder load); `S_all`
measures a much narrower thing — the *gain* a shift adds, paired within the same file, which is
exactly why P3 measured `SE(S_all)` = 0.080 pp pooled rather than something of this size. The spec's
own §1.1 worked example computed its ~0.18 pp/~0.92 pp scoping figures by rescaling P3's *own*
pooled `SE(S_all)` by assumed cluster fractions — that is the analytical method actually intended,
and it costs **zero decoder time** (P3 already is "the one pass").

**Second attempt (analytical, per the spec's own §1.1 method, using this session's REAL cluster
counts rather than assumed ones):**

```
SE_MID     = SE_pooled x sqrt(n_pooled / n_MID_clusters)     = 0.0800 x sqrt(30513/601)  = 0.570 pp
SE_OVERLAP = SE_pooled x sqrt(n_pooled / n_OVERLAP_clusters) = 0.0800 x sqrt(30513/2231) = 0.296 pp
SE(I)      = sqrt(SE_MID^2 + SE_OVERLAP^2)                                              = 0.642 pp
```

`0.642 pp ≤ 0.75 pp` ⇒ **ROW 0e PASS.** This is the gating result; the empirical proxy is retained
in `x3_result.json` (`row0e_secondary_empirical_proxy`) and reported here as disclosed context,
not as a contradicting result — it measures a materially different quantity (regime-level recovery
variance, not `S_all`'s own shift-gain variance) and its size mainly says that raw recovery level
is noisier across regimes than the shift-gain effect P3 characterised, which is itself unsurprising
rather than alarming.

---

## 3. Ordered gate trace

| row | check | bar | measured | verdict |
|---|---|---|---:|---|
| 0a | DLL identity pinned (corrected, §0) | SHA matches | `f2f30c89…` | **PASS** |
| 0b | shim version recorded | any, recorded | 20260033 | **PASS** |
| 0c | 20m `REF` reproduces | == 69 222 | 69 222 | **PASS** |
| 0d | regime populations (MID, OVERLAP) | ≥300 decodes, ≥250 clusters each | 2 046/601, 21 234/2 231 | **PASS** |
| 0e | pre-flight power (base leg only) | scoped `SE(I)` ≤ 0.75 pp | 0.642 pp (analytical) | **PASS** — see §2 |
| 0f | shift control (P3's, real audio) | Δf within 0.25 Hz of 1.0417 Hz, ≥200 matched | *not independently re-run — see note* | **inherited, not re-verified** |
| 0g | `native_av_count` == 0 | no access violations | 0 (both legs) | **PASS** |

⚠️ **ROW 0f note:** P3's own shift control (0.0332 Hz error, 356 matched messages, spec's own
mechanism) validates the *transform* — `freq_shift`/`time_shift` in `p23_common.py`, reused
unmodified here, byte-for-byte the same functions P3 exercised. It was **not re-run against the
corrected DLL** in this session (would cost one additional small decode pass). Disclosed as an
inherited-not-reverified check rather than silently assumed identical — the transform code did not
change between P3 and X3, only the DLL underneath it did, and the transform operates on PCM before
the DLL ever sees it, so this is a low-risk gap, not a load-bearing one, but it is a gap.

No row voided. `I_20m` proceeds to the gate.

---

## 4. Primary metric and gate

```
I_20m = S_all(OVERLAP, 20m) - S_all(MID, 20m)
```

| regime | `S_all` | `n_ref` |
|---|---:|---:|
| MID | 5.670 pp | 2 046 |
| OVERLAP | 4.295 pp | 21 234 |

```
I_20m       = -1.375 pp
SE(I_20m)   = 0.649 pp
95% CI      = [-2.665, -0.197] pp     (frequency-clustered, PAIRED per regime's own gained set)
```

```python
if se_I > 0.75:                      return "ROW 0e"   # 0.649 <= 0.75 -- not fired
if I >= 2.0 and lo > 0:               return "ROW 1"    # I is negative -- not fired
if abs(I) < 1.0 and se_I <= 0.40:     return "ROW 2"    # |I|=1.375 >= 1.0 -- not fired
if I <= -2.0 and hi < 0:              return "ROW 3"    # I=-1.375 > -2.0 -- not fired
return "ROW 4"
```

**>>> ROW 4 <<<**

### 4.1 🔴 What ROW 4 does and does not mean here — read this before citing "no effect"

**The 95% CI excludes zero on both bounds** (`[-2.665, -0.197]`) — this is a *statistically
non-trivial negative result*, not a flat, uninformative null. It falls into ROW 4 purely because
the pre-registered magnitude bar for a directional reading (`±2.0 pp`) is stricter than what the
data happens to show (`-1.375 pp`), and the gate was deliberately built that way (a bound, not a
significance test) — per HK-021 practice, a gate turning on a bare "CI excludes zero" would read
noise as a result far too often at this programme's typical effect sizes. **The honest statement is
"a small, real-looking, negative `I_20m` that does not clear the bar set for a directional verdict"
— not "no interaction was found."** Per the spec's own instruction ("Do not editorialise on the
point estimate" for ROW 4), no further interpretation is offered.

**Direction, noted without interpretation:** the point estimate is negative — `S_all` (the shift-
union's recall gain) is *smaller* in OVERLAP than in MID, the opposite of what the Architect's
own LOCAL-limb prediction (`I_20m` ∈ [0.5, 4.0] pp, i.e. lattice cost concentrating in crowded
cycles) anticipated. Stated as a fact about this measurement, not as evidence of anything the gate
itself did not certify.

---

## 5. Secondary quantities (spec §4, reported, never gating)

| regime | `S_freq` | `S_time` | `X_guard` |
|---|---:|---:|---:|
| FLOOR | 0.0 | 0.0 | 1.000 *(n=17, unusable — see §1)* |
| MID | 3.226 | 4.106 | 0.842 |
| OVERLAP | 2.496 | 2.976 | 0.885 |

`S_time > S_freq` in both usable regimes, consistent with P3's own pooled finding (3.01 vs 2.41) —
**not gated on, per spec §4.2's explicit bar** ("do not gate on which is larger — that is exactly
the directional call I got wrong").

`X_guard` sits at **0.84–0.89** in both regimes — slightly *higher* than P3's pooled 0.897 in
OVERLAP, close to it in MID. **No regime meaningfully improves on P3's guard problem**; the union
manufactures roughly as much junk everywhere as it did pooled. Per the Architect's own prediction 5
(§6 of the spec, explicitly ungated): `X_guard` was predicted higher in OVERLAP than MID/FLOOR —
**OVERLAP (0.885) is indeed higher than MID (0.842)**, consistent with the prediction, reported
for scoring only per the spec's own instruction that nothing turns on it.

---

## 6. Predictions scored

| # | prediction | type | measured | verdict |
|---|---|---|---|---|
| 1 | ROW 1 or ROW 2; not ROW 3 | categorical | ROW 4 | **N/A** — none of the three named rows fired; cannot score a categorical call against an unfired gate |
| 2 | `I_20m` ∈ [0.5, 4.0] pp | magnitude | −1.375 pp | **MISS** — wrong sign entirely, outside the range on the opposite side from where it was expected |
| 3 | measured `SE(I_20m)` ∈ [0.10, 0.35] pp (ROW 0e passes) | magnitude | 0.649 pp (analytical) | **ROW 0e passed as predicted, but the SE itself is well outside the predicted range** — partial credit, scored as a **MISS on the range**, hit on the categorical (passes) |
| 4 | 80m replication is UNDERPOWERED at ROW 0d, or fails to reach the 2.8 pp bar | categorical | not run this session | **NOT SCORABLE** — see §7 |
| 5 | `X_guard` higher in OVERLAP than MID/FLOOR (ungated, scoring only) | directional | OVERLAP 0.885 > MID 0.842 (FLOOR's 1.0 is on n=17, unusable) | **HIT**, for what an explicitly-ungated directional call is worth |

**Scorable predictions: 1 clear hit (5, ungated), 2 clear misses (2, 3's range), 1 mixed (3's
categorical half), 1 not scorable (4).** The one prediction that mattered most for reading the
result — #2, the magnitude and sign of `I_20m` — missed in direction as well as magnitude. Per the
Architect's own quoted calibration for this spec ("categorical ROW calls 5/7, ranges 7/10,
DIRECTIONAL/SHAPE calls 0/2"), a magnitude-bound miss of this kind is within the historical range
of misses on this class of call, not an outlier.

---

## 7. 🔴 80m replication — not run this session, flagged rather than skipped silently

The spec's replication metric, `I_80m = S_all(OVERLAP, 80m) - S_all(FLOOR, 80m)`, was **not run**.
Reasons, stated plainly rather than left implicit:

- The 20m primary already returned ROW 4 (no directional reading), so 80m's role as
  *confirmation of a directional result* has nothing to confirm this time.
- This session had already committed substantial decoder-replay time to the corrected-DLL
  primary leg (18.8 min) on top of the DLL-provenance investigation, three written reports, and
  the X4 arm. Running 80m's own five-leg shift-union (a smaller corpus by cluster count, ~907
  clusters, but not zero-cost) was not started without checking whether it remains worth doing
  given ROW 4 on the primary.

**This is a scope decision, not a technical blocker** — the harness (`x3_lattice_crowding.py`)
already supports it structurally (only the 20m-specific file listing and window are hardcoded in
`main()`; extending to 80m would follow the same `replay()`/`s_all_for_regime()`/
`cluster_bootstrap_paired_diff()` machinery already exercised and working). Left for the Architect/
Captain to decide whether it is still worth the decoder time given the primary's own inconclusive
reading, rather than QA deciding unilaterally to spend or withhold that time.

---

## 8. Citation limits (spec §5, restated)

**May be cited:** that `I_20m` was measured at −1.375 pp [−2.665, −0.197] pp and read **ROW 4**,
with the CI-excludes-zero nuance from §4.1 attached whenever the number is quoted at all. The
20m density-range caveat (§1) whenever `I_20m` is described as characterising "20m."

🛑 **May not be cited:** `I_20m` as evidence the lattice/crowding interaction is absent (ROW 4 is
"no reading," not "no effect" — §4.1); as a comparison across bands (`I` is within-band,
within-corpus only, per spec); as license for `K_FREQ_OSR`/`K_TIME_OSR` 2→4 in either direction
(P3's guard stands verbatim — finer OSR is a different mechanism than a five-run union, and neither
P3's nor X3's false-positive behaviour bears on it); as a re-read of P3 (P3 stays ROW 3, `X_guard`
= 0.897 pooled — X3 partitions that effect, it does not revise it). No `src/` recommendation, no
parameter sizing, no capture run follows from any part of this report, in any row.

## 9. NFR-021

This report and `x3_result.json` carry counts, rates, cluster counts and cycle timestamps only. No
callsign or message text appears in either artefact.
