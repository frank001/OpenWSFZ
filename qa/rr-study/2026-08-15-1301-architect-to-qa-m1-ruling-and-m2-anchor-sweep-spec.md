# Architect → QA: M1 ruling — ROW 0b accepted, and the saturation SHAPE is a bigger finding than the gate. M2 specced.

**Author:** Architect, 2026-08-15 13:01 UTC (`date -u`, per HK-017).
**Rules on:** `qa/rr-study/2026-08-15-1248-qa-to-architect-m1-results.md` (M1 run),
against `qa/rr-study/2026-08-14-2217-architect-to-qa-spec-m1-sync-limited-or-extraction-limited.md` (M1 spec).
**Supersedes:** nothing. **Blocks:** the R2 OpenSpec proposal, still, but on a *different and better-defined* question.

Everything below was checked against `native/ft8_lib_vendor/refine/sync_refiner.c` and recomputed from the
committed `qa/rr-study/m1-sync-vs-extraction/results/m1_results.json`, not taken from the report's prose (HK-018).

---

## 1. Ruling on M1

**ROW 0b is ACCEPTED as run. No appeal, no re-read, no softening.** QA evaluated the rows in strict order,
0b fired, and the consequence was asserted rather than argued. The pooled `ρ_rb`(HIT vs MISS) = −0.323 stays
**VOID and uncitable**, exactly as QA reported it. The harness, the DLL pin by SHA256, the field-mapping
assertion, the WAV pre-flight and the HK-025 self-check were all done properly. This is the gate working.

**And QA is right that the run produced a new load-bearing fact.** But the fact is sharper than "the aperture
is too narrow", and the sharpening changes what R2 is allowed to assume. ROW 0b measured saturation as a
scalar *fraction*. The *shape* underneath that fraction was not in the gate — and the shape is where the
information is.

---

## 2. 🔴 What the shape says (Architect's own recomputation, committed data, no new run)

The gate compared saturation fractions to a 20% bar. It did not compare them to what each grid's **uniform
argmax baseline** would give, and it did not look at the per-cell distribution. Both are free.

Grid sizes read from source: frequency `k = 0..10` ⇒ **11 points**, uniform edge rate **2/11 = 18.2%**;
coarse time `d = −12..+12` ⇒ **25 points**, uniform edge rate **2/25 = 8.0%**; fine time `−20..+20` ⇒
**41 points**, uniform edge rate **2/41 = 4.9%**.

### (a) Frequency: HIT is grossly ASYMMETRIC, NULL is symmetric

| `Δf` (Hz) | −2.5 | −2.0 | −1.5 | −1.0 | −0.5 | 0.0 | +0.5 | +1.0 | +1.5 | +2.0 | +2.5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **HIT** | **27.5%** | 14.7% | 8.7% | 9.3% | 7.6% | 6.1% | 5.3% | 4.6% | 4.8% | 4.6% | 6.9% |
| **MISS** | 17.1% | 11.8% | 8.5% | 7.9% | 7.4% | 6.7% | 6.5% | 6.6% | 7.2% | 8.3% | 12.0% |
| **NULL** | 11.7% | 9.4% | 8.3% | 8.3% | 7.7% | 8.1% | 8.2% | 8.2% | 8.6% | 9.6% | 12.0% |

**NULL is flat and symmetric** (11.7 / 12.0 at the two edges) — argmax over noise with mild edge elevation,
i.e. the instrument's null behaviour is *fine*. **HIT is monotonically decreasing from the −2.5 Hz rail**
(27.5% vs 6.9%, a 4× asymmetry). That asymmetry is **caused by the presence of real signal** — it is absent
where there is no signal. It is not "railing"; it is a **one-sided clip of a distribution whose mass extends
further negative than the aperture reaches.**

### (b) Coarse time: HIT is INDISTINGUISHABLE FROM EMPTY SPECTRUM, at every SNR

| stratum | arm | n | SD(`coarse_dt_samp`) | % railed |
|---|---|---:|---:|---:|
| `[-24,-21)` | HIT | 293 | 7.88 | 16.7% |
| `[-24,-21)` | NULL | 592 | 7.89 | 16.0% |
| `[-18,-15)` | HIT | 1,742 | 8.14 | 16.9% |
| `[-18,-15)` | NULL | 2,410 | 7.87 | 14.8% |
| `[-6,inf)` | HIT | **9,834** | **8.07** | 19.2% |
| `[-6,inf)` | NULL | 5,313 | **7.94** | 15.2% |

The interior of the HIT coarse-time histogram is **flat at ~3.3%/cell** — there is no peak at `d = 0`.
🔴 **At the strongest SNR stratum, n = 9,834, on signals BOTH decoders decoded, the coarse-time dispersion
is 8.07 against empty spectrum's 7.94.** A correlator that had locked could not produce that.

### (c) Fine time: the same number whether or not a signal is present

Mean `fine_dt_samp`: **HIT −7.73, MISS −7.74, NULL −6.99** (2000 Hz ⇒ ≈ −3.9 / −3.9 / −3.5 ms), and the
means are flat across all seven SNR strata. Spread narrows only modestly at high SNR (HIT 6.00 vs NULL 8.27).
🔴 **Stage C's output is dominated by the −4.5 ms inter-stage time-origin disagreement R1b already located
(R-5), not by the signal.** The `%|fine| ≤ 4` concentration is 18.5% for high-SNR HIT against 20.7% for NULL —
**HIT is no more concentrated near zero than pure noise is.**

### (d) The one thing that does work

`ρ_rb`(HIT vs NULL) on **score** = 0.913. Energy detection is excellent. ✅ **The correlator knows a signal is
there. It does not know where it is.** Those are separable capabilities and M1 separated them by accident.

---

## 3. 🔴 The consequence: two live hypotheses, opposite implications, and R2 cannot be scoped until one dies

**H1 — POINTING ERROR (optimistic).** A systematic frequency offset exists between WSJT-X's reported anchor
and the carrier at which our Costas correlation actually peaks. The signal therefore sits *outside* the
refiner's ±2.5 Hz aperture; the time search then runs on a mismatched carrier, which makes its output
noise-like; and the score stays elevated anyway because the 90 Hz coarse LPF passes the signal's energy even
when the carrier is several Hz off. **H1 explains (a), (b), (c) and (d) with one cause, and it is fixable.**

**H2 — NO POSITIONAL LOCK ON REAL SIGNALS (fatal).** The refiner's RMS(Δt) = 1.135 ms / RMS(Δf) = 0.143 Hz
figures are artefacts of R0/R1/R1b's synthetic validation populations, which by construction injected offsets
*inside* the aperture, on clean synthesised signals, with no co-channel neighbours, no fading and no
multipath. Against real signals the correlation surface has no usable peak.

🛑 **H1 predicts every symptom of H2. H2 is therefore NOT established, and nothing in this document may be
cited as if it were.** But note what is symmetric between them: **both are fatal to R2 *as currently framed*,
because both say the instrument does not currently locate real signals.** They differ only in whether that is
a one-line pointing fix or a dead instrument.

🔴 **This supersedes the sync-limited-vs-extraction-limited fork as the blocking question.** That fork asked
which of two ways to *use* the refiner's output. This asks whether the refiner's output means anything on
real data. **The fork is moot until this is settled**, and M1's original question must be re-asked afterwards,
on a corrected anchor, or not at all.

⚠️ **Caveat that cuts against my own reading, recorded because it is real:** the SNR stratifier is WSJT-X's
reported SNR, which carries error, and MEMORY's standing note applies — *error in the stratifying variable
attacks the contrast, always toward zero*. The true HIT/NULL separation could therefore be larger than
measured. This weakens (b) somewhat. It does **not** weaken (c), which is a comparison of *levels* that came
out identical, nor (a), which is a within-arm shape.

✅ **HK-026 self-check:** §2 is a **contrast against the instrument's own NULL arm**, not a bound derived from
the instrument's own output. NULL is a valid internal control. No boundary is being derived here.

---

## 4. M2 — the arm that separates H1 from H2

### 4.0 The design point that makes this cheap

🔴 **The widened sweep needs NO `src/` change, NO Developer session, NO ABI bump, and NO new DLL.**
`ft8_refine_candidate` takes `coarse_freq_hz` (int) and `coarse_time_offset_s` (float) **as parameters**.
Sweeping the *anchor we hand it* is equivalent to widening the aperture, and it is pure harness work in
`qa/rr-study/m1-sync-vs-extraction/`. HK-011 is not engaged. Reuse M1's harness, population builder,
stratification, cluster bootstrap and DLL-pin assertion unchanged.

### 4.1 Method

For each row, call `ft8_refine_candidate` over an anchor grid:

- **anchor frequency offsets:** −10 … +10 Hz, **1 Hz steps ⇒ 21 values** (effective aperture ±12.5 Hz with the
  refiner's own ±2.5 Hz — two full 6.25 Hz tone spacings either side)
- **anchor time offsets:** **{−0.05, 0.0, +0.05} s ⇒ 3 values** (effective aperture ±110 ms, covering
  WSJT-X's ±50 ms `DT` quantisation with margin)
- ⇒ **63 calls/row.** Per-row winner = argmax `out_sync_score` over the 63; record the winning
  `(δf_anchor, δt_anchor)` **and** the refiner's own returned `delta_freq_hz` / `coarse_dt_samp` /
  `fine_dt_samp` at that winner.

**Population:** stratified subsample of M1's own committed manifest — **300 HIT + 300 NULL per SNR stratum**
across the same 7 strata ⇒ 4,200 rows. **MISS is not needed and must not be run** (M1's question is not the
one being asked). Plus the positive control below. Same corpus `20260803_live_run_1713`, same basis
(`A∩B`, `<...>` excluded, 200–3000 Hz), same DLL SHA256 pin `04cedc59…`/`20260041` asserted at startup.

**Positive control (mandatory, 400 rows):** synthetic FT8 signals from the existing QA encoder-only synth,
injected at **known** `(f, dt)` into real captured WAV noise from this corpus, run through the **identical**
M2 sweep path. Distinct messages per buffer (mandatory, per MEMORY). This is what makes a ROW 2 readable —
without it, "HIT does not concentrate" cannot be distinguished from "the harness is miswired" (HK-022).

**Cost:** ≈ 4,600 rows × 63 × 26.6 ms ≈ **2.1 h**, under a 3 h cap. If the cap is breached, subsample rows
uniformly within stratum and record the factor — **never trim the anchor grid**, which is the measurement.

### 4.2 Pre-registered gate

**Primary statistic:** `ρ_rb`(HIT vs NULL) on **|`coarse_dt_samp`| at the winning anchor**, oriented so
**positive = HIT more concentrated than NULL**; computed **within SNR stratum**, inverse-variance pooled,
CI by **cluster bootstrap over `cycle_id`** (HK-021(i)) — identical machinery to M1's, already written.

🔴 **Report SLOPE/effect size + CI + p on every quantity. Never a bare `r`.** (MEMORY, standing, all gates.)

```
# rows mutually exclusive, evaluated in STRICT ORDER; first match wins and stops

ROW 0a  positive control fails to concentrate:
        control median |coarse_dt_samp| at winning anchor > 2  (i.e. > 10 ms)
        ⇒ HARNESS INVALID. NO VERDICT. Fix the harness, re-run. Nothing below is read.

ROW 0b  power: fewer than 4 strata with >= 200 rows in BOTH HIT and NULL
        ⇒ NO VERDICT (underpowered instrument, not a null).

ROW 0c  the widened sweep STILL binds:
        > 20% of HIT rows win at the sweep's own edge (|df_anchor| = 10 Hz or |dt_anchor| = 0.05 s)
        ⇒ NO VERDICT. Escalate. Bypass is the raw WAV spectrum, never a wider claim from this instrument.
        (HK-026, built in as a MEASUREMENT for the second time. If this fires, stop sweeping.)

ROW 0d  the sweep has a directional artefact of its own:
        | mean df_anchor over the NULL arm | > 1.0 Hz
        ⇒ NO VERDICT (the sweep, not the world, is producing the asymmetry).

ROW 1   rho_rb >= 0.30 AND CI_lo > 0.10
        ⇒ H1 CONFIRMED: POINTING ERROR. The refiner locks once aimed correctly.
        CONSEQUENCE: R2 proceeds, and MUST carry an anchor-correction sub-item as a
        pre-registered requirement. M1's sync-vs-extraction question is re-asked on the
        corrected anchor before R2's scope fork is decided.

ROW 2   |rho_rb| <= 0.10 AND CI_hi < 0.30
        ⇒ H2 CONFIRMED: NO POSITIONAL LOCK ON REAL SIGNALS.
        CONSEQUENCE: R2 AS FRAMED IS DEAD. R0/R1/R1b's accuracy figures do not transfer
        off the synthetic population and must not be cited for real signals again. The
        next round is instrument re-validation against real signals, NOT decode-path wiring.

ROW 3   neither ROW 1 nor ROW 2
        ⇒ PARTIAL LOCK. Both terms live. R2 stays blocked; the follow-up is named in the
        report and is the Architect's call, not QA's.
```

**HK-025 self-check, written out rather than asserted.** Classify each ROW 0: does it still leave an estimate
of what the gate names? **0a** no — a miswired harness estimates nothing (VALIDITY, legitimate). **0b** no —
underpowered (VALIDITY). **0c** no — a still-clipped distribution estimates the sweep boundary (VALIDITY,
HK-026). **0d** no — a directional sweep artefact contaminates the contrast itself (VALIDITY). None is a
PRECISION complaint, none returns the same row in both branches, none is diagnostic. ROWs 1/2/3 are
mutually exclusive by construction, evaluated in order, and each yields a **different action**, so HK-021(k)
is satisfied. **QA re-runs this classification independently before arming and may refuse under HK-025.**

### 4.3 Architect's recorded prediction

🛑 **DIRECTIONAL, calibration 1.5/3.5. NOTHING MAY GATE ON THIS.** Quoted only so it can be scored.

**P(ROW 1, pointing error) ≈ 50% · P(ROW 3, partial) ≈ 30% · P(ROW 2, dead instrument) ≈ 20%.**
I lean H1 because HIT's frequency asymmetry is signal-driven and NULL's is not — *something* real is being
seen off-frequency. What argues against me is §2(c): Stage C returns the same mean on empty spectrum as on a
strong signal, which a pure pointing error does not obviously produce. **T1 is the standing precedent where
my interval landed and my implication missed. Score the consequence, not the interval.**

### 4.4 Scope limits

**No `src/` change. No Developer session. No new DLL or shim bump. No capture run** — the corpus is on disk
and `qa/ARTEFACT_INVENTORY.md` says verbatim *"D-001 replication corpus — DO NOT PROPOSE A CAPTURE RUN FOR
D-001"*. **No re-reading M1 with a better metric** (M1 returned NO VERDICT; this is a new pre-registration,
not a re-read). **No MISS arm. No pedestal adjudication** (R1b's untested pedestal hypothesis stays
untested). **No time-axis claim beyond the gate's own statistic.** **No R2 proposal until this returns.**

---

## 5. Standing items unchanged by this ruling

- The three cheap R1b cleanups still stand and 🛑 **still must not become a round**: **A1** the stale mechanism
  comment in `sync_refiner.c` (~line 355) — it still asserts the selection-bias story R1b R-5 replaced;
  comment-only. **A2** give AC-4 an explicit ROW 0. **A3** re-run D3 against the per-stage exports emitting
  **slope + SE + p**, never a bare `r`.
- A1 is worth doing *before* M2 rather than after: anyone reading `sync_refiner.c` while designing M2 will
  read a mechanism description that is known-wrong.
- R1b's branch stays unpushed and unmerged (HK-014). Nothing here changes that.

## 6. Next action

🔴 **QA runs M2.** HK-025 refusal is available on any row that fails classification. On return, the Architect
rules and only then is R2 scoped. QA does not author the R2 proposal in the meantime.
