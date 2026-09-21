# `DENSITY-LIVE` — pre-registration: do our live misses concentrate in the near-neighbour geometry the bench proved causal?

**Architect, 2026-09-18T13:39Z** (`date -u`, HK-017). Branch `arch/density`, cut from `origin/main`
`de5b2c72`. Docs-only; `git diff --stat origin/main...HEAD -- src/ native/` is empty.

**Status: cleared to run.** Captain, 2026-09-18:
- *"go with option b, park fade and move to density"* — FADE parked as UNRESOLVED (`E4-STAGE2` §22).
- **Spectral-locality gate CLEARED:** the Captain was asked whether this check is a different question
  from the retired SPECTRAL LOCALITY work, and ruled **"Clear it"**.

⚠️ **What that clearance covers, and what it does not.** It covers **this one confirmatory test**: a
geometry fixed in advance from the bench (`F-NBR-A` C2/C3), with its signature checked on live rows. It
does **not** reopen spectral locality's exploratory question ("is the crowding penalty local or
diffuse?"). 🛑 **Nothing in this document may be cited as evidence about diffuse crowding, and no
stratum, cut or distance may be added after the data is seen.** A second live-stratification check
needs a second Captain ruling.

**It needs no station time, no new run, no `src/`/`native/` work and no Developer.** It runs on
existing live logs.

---

## §0. What this answers, in one line

The bench (`F-NBR-A`) proved that **a neighbour within 18.75 Hz at equal-or-greater level excludes the
victim completely** (0/100, and 100/100 with the neighbour removed). The assessment
(`2026-09-16-1730-architect-assessment-density-near-neighbour-exclusion.md` §2) sized how often that
geometry occurs live, at **≈ 5.9 pp** of decode rate: **a ceiling, assuming the bench's 0/100 generalises.**

> **Does it generalise? On live rows WSJT-X decoded, do we miss the "exposed" rows much more often than
> comparable rows that have a neighbour just as close but clearly weaker?**

The answer decides the programme's next move. **ROW 1** makes density the main line, with the mechanism
arm next. **ROW 2** retires the 5.9 pp as a planning figure and parks density.

---

## §1. Corpus, fixed

| | |
|---|---|
| **Corpus** | **C2**, `artefacts/20260908_live_run_1827-fp-floor-live-2/`. OpenWSFZ and WSJT-X #1 (FT-991A) on the **same** `Voicemeeter Out B1` audio, so every difference is a decoder difference. |
| **Window** | `live-gap-now/corpus.c2_cycles()` verbatim: `cycle_start_utc ≥ 2026-09-08T19:36:45Z`, dial 14.074, `*_2.wav` excluded. **4,113 cycles.** |
| **REF** | WSJT-X FT991A `ALL.TXT` via `live-gap-now/analyse.load_ref_c2()`, verbatim. **91,046 rows.** |
| **TEST** | OpenWSFZ **live** `ALL.TXT` via `analyse.load_live_c2_openwsfz()`, verbatim. 🛑 **Live logs only — no replay.** A raw-C-ABI replay is not the live path (MEMORY). |
| **Hit** | `live-gap-now/matcher.recovery(test, ref)["hit_set"]`, verbatim (exact + wildcard, `R_wild`). It reproduces A1 = 61.09%. |
| **Population** | REF rows with **SNR ≥ −10 dB** (60,239). This is where the bench says we do not lose on clean signals, and where the assessment's sizing lives. |

⚠️ **Qualifiers that travel with every number from this arm:** binary `6b2e16a6…` (shim `20260050`),
`nhard` = 60, **pre-`PASSBAND-140`**, 20 m, 2026-09-08/09, REF = WSJT-X FT991A alone. 🛑 **Never pool
with post-2026-09-12 data (nhard 40).** `NBR-RERUN` (G1) found the bench reproducer **unchanged** on the
shipped binary, so the geometry question is not expected to have moved. That is a reason to run on C2,
**not** a claim that C2's rates are current.

**Why C2 and nothing else:** it is the only corpus with both decoders live on identical audio after the
2026-08-19 dual-instance fix (checked; `artefacts/` has no later dual-decoder live run).

---

## §2. Classes, fixed from the bench before any outcome is seen

For every REF row `v` in the population, look at the **other REF rows in the same cycle**. For each
neighbour `n`: `Δf = |f_n − f_v|` (integer Hz, `ALL.TXT` field `[6]`) and `rel = snr_n − snr_v`
(field `[4]`).

| class | predicate (first match wins, in this order) | bench anchor |
|---|---|---|
| **EXPOSED** | some neighbour with `Δf ≤ 18` and `rel ≥ 0` | C2: 0/100 at ≤ 3 bins · C3: 0/100 when **equal** |
| **GAP** | some neighbour with `Δf ≤ 18`, and the max `rel` over those is −1 or −2 | **excluded**, counted. It is the 2 dB guard band against WSJT-X's integer SNR under overlap. |
| **PLACEBO-LEVEL** (`PL`) | neighbour(s) with `Δf ≤ 18`, all `rel ≤ −3`; **and** no neighbour with `19 ≤ Δf ≤ 31` and `rel ≥ 0` | C3: **100/100 when 3 dB stronger** |
| *(PL but a strong transition-zone neighbour)* | as `PL` but failing the second clause | **excluded**, counted |
| **TRANSITION** | no neighbour at `Δf ≤ 18`; some at `19 ≤ Δf ≤ 31` | C2: 27/100 at 4 bins, 98/100 at 5 — **reported only** |
| **PLACEBO-FAR** (`PF`) | nothing at `Δf ≤ 31`; some neighbour at `50 ≤ Δf ≤ 100` with `rel ≥ 0` | C2: **100/100 at 50 and 100 Hz** |
| **CLEAR** | none of the above | reported only |

```python
def classify(v_snr, v_f, neighbours):          # neighbours: [(snr, f), ...] same cycle, v excluded
    near  = [s - v_snr for s, f in neighbours if abs(f - v_f) <= 18]
    trans = [s - v_snr for s, f in neighbours if 18 < abs(f - v_f) <= 31]
    far   = [s - v_snr for s, f in neighbours if 50 <= abs(f - v_f) <= 100]
    if near:
        m = max(near)
        if m >= 0:   return "EXPOSED"
        if m >= -2:  return "GAP"
        return "PL" if not trans or max(trans) < 0 else "PL_TRANS_STRONG"
    if trans:        return "TRANSITION"
    if far and max(far) >= 0: return "PF"
    return "CLEAR"
```

🔒 **NFR-021:** the classifier reads **numeric fields only**. Message text stays in memory inside
`load()`/`recovery()` and is never written. Outputs are counts and rates.

**Duplicate decodes can't create fake pairs:** `load()` keys on `(ts, message)`, so two same-message
REF lines in one cycle collapse to one row before classification.

### 2.1 ✅ Class sizes — computed by the Architect from REF ONLY, before writing this

🛑 **Blind to the outcome.** The script (`scratchpad/density_ref_counts.py`, reproduced by §2's
classifier) read **only** the WSJT-X `ALL.TXT`. **No OpenWSFZ decode was loaded and no recovery was
computed on any class.**

| class | n | −10…−6 | −5…−1 | 0…4 | 5…9 | ≥ 10 |
|---|---:|---:|---:|---:|---:|---:|
| **EXPOSED** | **5,363** | 2,059 | 1,500 | 1,017 | 509 | 278 |
| **PL** | **7,476** | 1,188 | 1,614 | 1,617 | 1,289 | 1,768 |
| **PF** | **10,781** | 4,307 | 3,111 | 1,847 | 927 | 589 |
| TRANSITION | 7,429 | 1,923 | 1,789 | 1,481 | 1,005 | 1,231 |
| CLEAR | 28,310 | 5,383 | 5,516 | 5,210 | 4,268 | 7,933 |
| GAP (excl.) | 598 | | | | | |
| PL_TRANS_STRONG (excl.) | 282 | | | | | |
| **total** | **60,239** | | | | | |

✅ **EXPOSED = 5,363 reproduces the assessment's ≈ 5,361** (18 Hz on integer Hz vs 18.75). `PL` margins:
3 dB 407 · 4–11 dB ≈ 430–520 each · ≥ 12 dB 3,545.

🔴 **The classes are heavily SNR-confounded:** EXPOSED skews weak, `PL` skews strong, and so does our
own recovery (58.6% at −10…−6 → 87.2% at ≥ +10, E4 bench spec §0.2). **A raw miss-rate difference would
mostly measure SNR.** Hence §3's standardisation.

---

## §3. The statistic

**Strata:** REF SNR in **1 dB** cells from −10 to +9, and one cell for ≥ +10 (21 cells). Five-dB bands
would leave a within-band SNR gradient of several pp, which is enough to fake a contrast.

For classes `A`, `B`: **`D(A,B)` = Σ_s w_s · (miss_A,s − miss_B,s)**, where `miss = 1 − hit rate`,
**`w_s` = `A`'s share of rows in cell `s`** (direct standardisation to `A`'s SNR mix). A cell with
`n_A < 20` **or** `n_B < 20` is dropped. Report how many `A` rows that drops; 🛑 if it exceeds 5% of `A`,
**ROW 0b** fires.

**CI:** `live-gap-now/bootstrap.py`'s scheme, verbatim in method: resample **distinct REF integer
frequencies** with replacement (station-persistence clusters), **N = 2000, seed 20260918**, recompute
`D` per draw, 95% percentile interval. **Paired:** one resample per draw serves every contrast.

**Attributable live cost:** `C = D(EXPOSED, PL) × n_EXPOSED / 91,046`, in pp of decode rate. With
n_EXPOSED = 5,363, **`C` = 1.0 pp ⇔ `D` = 0.170.**

---

## §4. Gates

### 4.1 ROW 0 — validity (either fires ⇒ 🛑 STOP, no primary reading)

| row | predicate | fires ⇒ |
|---|---|---|
| **0a — the placebo null** | 95% CI of **`D(PL, PF)`** **not** inside **[−0.05, +0.05]** | STOP. The two classes the bench says are **both clean** (100/100 at 3 dB stronger; 100/100 at 50–100 Hz) differ live ⇒ something other than the bench geometry (proximity, busyness, SNR mis-estimation under overlap) is moving miss rates by more than the bar can tolerate. |
| **0b — coverage** | standardisation drops > 5% of EXPOSED rows, or of `PL` rows in 0a | STOP. |
| **0c — reproduction** | pooled `R_wild` over all 91,046 REF rows ≠ **61.09%** (to 2 dp) | STOP — wrong corpus, window or matcher. |

**Why 0a changes the verdict (HK-021(k)).** If `PL` is itself contaminated, e.g. a 3 dB-weaker neighbour
at 6 Hz still hurts (C3 measured level only at 12 Hz), then `PL` misses too much and **`D(EXPOSED, PL)`
is biased down**. A ROW 2 "deflate" would then be manufactured. If `PF` is contaminated, the reading is
the mirror image. **Either way the primary contrast can't be read.**

**Null in independent units (HK-021(z)).** "The bench geometry is the whole story" ⇒ `PL` and `PF` both
recover at their SNR-conditioned baseline ⇒ `D(PL, PF)` ≈ 0. **The 0.05 bar is ≈ 3.5× the expected CI
half-width:** with ~7,500 vs ~10,800 rows clustered on a few thousand frequencies, the binomial SE is
≈ 0.008, doubled for clustering ≈ 0.015, so the half-width is ≈ 0.03. It passes where the null holds and
fails on a confound of ≳ 0.05. **The 0.05 is about 30% of the primary bar (0.17),** so a confound that
large would already be material to ROW 1/2.

### 4.2 Primary — `D = D(EXPOSED, PL)` (only if ROW 0 is silent)

| row | predicate | reading |
|---|---|---|
| **ROW 1 — CONCENTRATES** | 95% CI lower limit of `D` **≥ 0.170** | **Live cost ≥ 1.0 pp, attributable to the bench geometry.** Density becomes the programme's main line; the M1/M2 mechanism arm (assessment §7.3) is next, with the shim-feasibility question as its ROW 0. |
| **ROW 2 — DEFLATES** | 95% CI upper limit of `D` **< 0.170** | **Live cost < 1.0 pp.** The bench exclusion does not generalise at planning scale. 🛑 **The ≈ 5.9 pp is RETIRED as a planning figure.** Density is parked. |
| **ROW 3 — UNRESOLVED** | otherwise (CI straddles 0.170) | Report `D`, `C` and the CI. Back to the Architect and the Captain. |

```python
lo, hi = ci95(D_draws)
if row0_fires:        verdict = "ROW 0 STOP"
elif lo >= 0.170:     verdict = "ROW 1 CONCENTRATES"
elif hi <  0.170:     verdict = "ROW 2 DEFLATES"
else:                 verdict = "ROW 3 UNRESOLVED"
```

**Why 1.0 pp.** It is the anchor this programme already uses: `E4` §10.3's bars derive from a 1 pp
effect, and FADE was parked today **because** its ceiling is ≤ 1.0 pp. A density effect below that is
no more worth a main-line arm than FADE was. Using the same number makes that comparison honest.

**Can every row be returned?** (The check `E4-STAGE2` failed three times.) `D` is a difference of miss
rates in [−1, +1]. The bench predicts `D` ≈ `PL`'s own recovery (~0.75) if exclusion is complete live;
no effect predicts `D` ≈ 0. **At a CI half-width of ≈ 0.04, ROW 1 is reached at any true `D` ≳ 0.21, ROW 2
at any `D` ≲ 0.13, and ROW 3 only in between.** All three are reachable. ✅

**Readout quantum.** n = 5,363 vs 7,476, and the smallest EXPOSED 1-dB cell holds tens of rows. A single
row moves `D` by ≈ 0.0002. **Nothing here is near its quantum.**

### 4.3 Reporting only — gates nothing, can change no row

1. **Raw recovery per class**, pooled and per 5-dB band, **with n.**
2. **`D(EXPOSED, PL)` per 5-dB band.** 🛑 No band may be read against 0.170 (HK-021(y)): the bar belongs
   to the pooled, standardised figure.
3. **`D(TRANSITION, PF)`**: the bench predicts a partial effect (27/100 → 98/100). Reported as the
   graded-zone check, **not** a gate.
4. **`D(EXPOSED, PF)`**, for completeness.
5. **EXPOSED recovery split by `rel` = 0 vs ≥ +1**: the C3 knife-edge sat exactly at equal level.
6. **Counts:** GAP, PL_TRANS_STRONG, dropped cells, ambiguous wildcard matches (`recovery()["n_ambiguous"]`).

🛑 **None of these may be cited as a mechanism finding or as evidence about diffuse crowding.**

---

## §5. What this can't see — named now, so it can't be discovered later

1. **Neighbours WSJT-X didn't decode are invisible** (HK-026). They misfile EXPOSED rows into `PL`/`PF`/`CLEAR`,
   which **dilutes `D` toward zero**, and that is the unsafe direction for ROW 2. **Bounded, not
   eliminated:** misfiling needs an **undecoded** neighbour **at ≥ the victim's SNR**, and the victim is
   ≥ −10 dB. WSJT-X missing a signal at ≥ −10 dB is rare (it takes the crowded station 5/5 on the bench).
   **Disclosed, not gated.**
2. **WSJT-X's SNR under overlap is estimated, not true.** The 2 dB GAP guard band absorbs ±1 dB of it;
   larger errors misfile across EXPOSED/`PL` in both directions.
3. **It measures REF-decoded rows only.** A victim WSJT-X also lost is not in the population. The
   question is our deficit **where WSJT-X succeeds**, which is the A1 convention.
4. **C2 is one corpus, one band, 4,113 cycles (≈ 17 h of air time), a superseded binary** (§1 qualifiers).
5. 🛑 **A ROW 1 establishes that live misses concentrate in the geometry. It does not establish M1 vs M2,
   and it licenses no fix.** §7's order stands.

---

## §6. Deliverables (QA)

1. A script under `qa/rr-study/density-live/` that imports `live-gap-now`'s `corpus`, `analyse`,
   `matcher` **verbatim** and implements §2's `classify()` and §3's statistic. Re-derive §2.1's class
   table **before** loading any TEST data and **stop if it does not match** (it proves the classifier
   matches the one used to set the bars).
2. `results/density_live_result.json`: ROW 0a/0b/0c values and verdicts, `D`, CI, `C`, the verdict, all
   §4.3 items. **Numeric only (NFR-021)**; run the NFR-021 scanner (import `scan()`/`classify()`) on
   the output **and** on the report prose.
3. A QA report in `qa/rr-study/` in the usual `qa-to-architect` form.
4. 🛑 **No `src/`/`native/` change, no station time, no new capture.** Commit by path; push waits on the
   Captain (HK-033).

---

## §7. Sequence after the verdict — pre-registered

| verdict | next |
|---|---|
| **ROW 1** | Mechanism arm (M1 tone contention vs M2 tile artefact) on a **continuous** metric (LLR BER vs truth), shim feasibility as its ROW 0. Spec needs the Captain's go. |
| **ROW 2** | Density parked; 5.9 pp retired as a planning figure. Architect brings the Captain the next-largest open item. |
| **ROW 3** | Architect and Captain. **No second live stratification without a new Captain ruling** (the clearance covers this test only). |
| **ROW 0** | Report and stop. No re-cut of classes, bars or strata. |

---

## §8. Predictions — written before any OpenWSFZ decode is loaded for this arm

🔴 **Per the ledger: my HYPOTHESISED calls are biased toward over-predicting a findable defect.** Here
the defect is already established on the bench; the live question is generalisation, which is exactly
where my calls have gone wrong. **Weight these accordingly.**

| # | prediction | P | class |
|---|---|---:|:---:|
| — | **Live-concentration check fires** — carried from the assessment §8 #1 (2026-09-16), **the scored one**, not re-forecast | **0.70** | H |
| 1 | ROW 0a passes (`PL` and `PF` agree within ±0.05) | 0.65 | H |
| 2 | Verdict is **ROW 1** (given ROW 0 silent) | 0.60 | H |
| 3 | Point `D` lands in **0.25–0.55** | 0.45 | H |
| 4 | §2.1's class table reproduces exactly (deliverable 1) | 0.95 | C |

⚠️ **#2 at 0.60 is lower than the carried 0.70.** That is deliberate: it now also has to clear ROW 0 and
a 1 pp bar, and neither existed when 0.70 was written. **The carried 0.70 is scored against "misses
concentrate"** (point `D` > 0 with CI excluding 0), **the new 0.60 against ROW 1.**

---

## §9. Status

- ➡️ **DISPATCHED to QA** on Captain authority (density; spectral-locality gate cleared for this test only).
- 🛑 **No OpenWSFZ decode has been classified by anyone for this arm.** §2.1 is REF-only.
- 🔴 **Bars fixed: ROW 0a ±0.05 · primary 0.170 (= 1.0 pp).** They do not move after the result.

---

## §10. ACCEPTANCE RULING — ROW 1, CONCENTRATES. `D` = 0.7293 [0.7010, 0.7540] · `C` ≈ 4.30 pp

**Architect, 2026-09-18T13:50Z.** QA report `2026-09-18-1348-qa-to-architect-density-live-result.md`,
script `qa/rr-study/density-live/density_live.py`, result JSON beside it. QA commit `db9b4d01` on
`qa/e4-bench`, not pushed.

### 10.1 Checked, not taken on report

- ✅ **Independent recompute** by the Architect, own code (§2 classifier, §3 standardisation, no
  bootstrap), against the same live logs: **`R_wild` 61.0856% · `D(EXPOSED,PL)` 0.7293 · `C` 4.296 pp ·
  `D(PL,PF)` 0.0272 · `D(TRANSITION,PF)` 0.2668.** Every point estimate matches QA's to 4 dp.
- ✅ **Deliverable 1:** QA reproduced §2.1's REF-only class table exactly, all seven classes, before
  loading TEST.
- ✅ **Artefact check: are EXPOSED pairs two real stations?** A result this strong needs one. REF-only,
  text compared in memory, counts written. **Only 2 of 5,363 pairs share a sender token** (0.04%). The
  victim-to-neighbour `Δf` is **roughly uniform over 0–18 Hz** (231–385 per 1 Hz bin, no pile-up at 0),
  which is not how duplicate decodes of one signal would look. 5.7% share *some* token, consistent with
  callers in a pile-up working the same station. **These are two transmitters.**

### 10.2 The gates

| row | value | bar | |
|---|---|---|---|
| 0a — placebo null `D(PL,PF)` | **0.027** [0.009, 0.045] | inside ±0.05 | ✅ silent |
| 0b — coverage | 0 rows dropped | ≤ 5% | ✅ silent |
| 0c — reproduction | **61.0856%** | 61.09% | ✅ silent |
| **Primary `D(EXPOSED,PL)`** | **0.7293 [0.7010, 0.7540]** | CI_lo ≥ 0.170 | 🟢 **ROW 1**: CI_lo clears by **4.1×** |

⇒ 🟢 **ROW 1 — CONCENTRATES.** **Live cost attributable to the bench geometry: `C` ≈ 4.30 pp** of decode
rate on C2.

**Raw, for scale:** WSJT-X decoded all 5,363 EXPOSED rows; **we decoded 278 (5.2%).** SNR-matched rows
with an equally close but ≥ 3 dB weaker neighbour: 83.2%. **The bench's 0/100 does generalise to live,
almost completely.**

⚠️ **0a passed but its CI excludes zero:** `PL` recovers ≈ 2.7 pp worse than `PF`. A weaker
near-neighbour costs a little. That is inside the tolerated confound and **could inflate `D` by at most
≈ 0.045**, against a 0.56 margin over the bar, **so the verdict is unaffected.** 🛑 **It may not be read as
mechanism evidence.**

### 10.3 What the number is and is not

- **4.30 pp is NOT the whole density cost.** It prices only the complete-exclusion geometry (≤ 18 Hz,
  neighbour ≥ own level). Reporting item 3, `D(TRANSITION,PF)` = **0.267** [0.238, 0.295] over 7,429 rows,
  is the graded zone the bench predicted (27/100 → 98/100). 🛑 **Reporting only, not gated, and not added
  to `C`.** It says there is more beyond the gated geometry, not how much.
- **§5's caveats stand:** neighbours WSJT-X didn't decode are invisible (biases `D` **down**, so the
  unsafe direction for ROW 2, the conservative one for ROW 1). It is one corpus on a superseded binary,
  `nhard` 60, pre-`PASSBAND-140`.
- **The 5.9 pp sizing is NOT validated as a number.** It assumed 100% loss on EXPOSED rows; live loss is
  ≈ 95%, but priced against the SNR-matched `PL` baseline it comes to 4.30 pp. **Cite 4.30 pp (C2), not 5.9.**
- 🛑 **ROW 1 says nothing about M1 vs M2 and licenses no fix** (§5.5).

### 10.4 Reporting items, as reported

- **`rel` split (item 5):** equal level (`rel` = 0, n=241) we recover **32.4%**; neighbour ≥ 1 dB
  stronger (n=5,122) **3.9%**. That is the C3 knife-edge, seen live.
- **Per-band `D` (item 2) rises with SNR:** 0.67 → 0.84 from the weakest band to the strongest. **Strong
  victims are excluded as completely as weak ones.** This is a level-ratio effect, not a weak-signal
  one, exactly as C3 said. 🛑 No band is read against a bar.
- ⚠️ **QA reporting defect, cosmetic:** `density_live.py:92` (`snr < -6`) puts −6 dB in the band labelled
  "−5…−1", so the reporting bands don't match §2.1's. **Primary is unaffected** (1 dB cells). QA should
  fix the label or edge in the report before push.

### 10.5 🔴 What ROW 1 does to the programme, and two closed doors the Captain must see

Per §7: **density is now the programme's main line**, and the **M1/M2 mechanism arm** is next, on a
continuous metric, with shim feasibility as ROW 0. **That arm is the Architect's to specify (HK-015), and it
needs the Captain's go first.**

🛑 **Two of the most obvious fix routes are CLOSED by standing prohibition, and nobody should reach for
them because this number is large:**

1. **Subtract-and-resynthesise is DEAD** (three builds, three reverts). This is how WSJT-X handles a
   stronger neighbour, and it would be the first thing anyone suggests.
2. **The candidate-budget family is closed twice.** An **M2** outcome (tile/pass-1 artefact) lands in it
   and **authorises nothing directly**. It would need a new pre-registration naming the specific
   parameter, FP primary.

**This is why the mechanism question comes first:** an **M1** outcome (tone-set contention in extraction)
routes to D-001 limb 2's extraction work, which is **not** closed. **The arm decides which door is open.**

### 10.6 Ledger — scored at ruling time

| prediction | P | class | outcome |
|---|---:|:---:|---|
| Live-concentration check fires (carried, assessment §8 #1) | 0.70 | H | ✅ **HIT** |
| ROW 0a passes | 0.65 | H | ✅ **HIT** |
| Verdict ROW 1 | 0.60 | H | ✅ **HIT** |
| Point `D` in 0.25–0.55 | 0.45 | H | 🔴 **MISS**: 0.7293, **above** the band |
| §2.1 class table reproduces | 0.95 | C | ✅ **HIT** |

⚠️ **The miss runs against the ledger's named bias.** I **under**-predicted the size of a defect, the
first time that direction has appeared. I discounted the bench's 0/100 for live generalisation, and it
generalised almost completely. **One arm is one arm; it doesn't show the bias is fixed.**

### 10.7 Status

- 🟢 **ROW 1 — CONCENTRATES. `D` = 0.7293 [0.7010, 0.7540], `C` ≈ 4.30 pp (C2).** Recomputed independently.
- ➡️ **With the Captain:** go / no-go on the M1/M2 mechanism arm (Architect specs it) · push of QA
  `db9b4d01` and Architect `517db622` + this ruling (HK-033 / HK-014).
- 🛑 **Subtract-resynthesise DEAD · candidate-budget CLOSED ×2** — neither reopens on this result.
