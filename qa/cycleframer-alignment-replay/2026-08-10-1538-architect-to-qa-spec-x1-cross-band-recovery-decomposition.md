# Architect → QA — spec X1: cross-band recovery decomposition (20m / 17m / 80m)

**2026-08-10 15:38Z** (filename and byline both from `date -u`, HK-017).
**Author:** Architect. **Audience:** QA (HK-015).
**Status:** pre-registration. **Commit this document before writing the harness.**

---

## 0. What this is, and the disclosure that must be read first

The weekend of 2026-08-08/09 produced three legs on three bands — 20m, 17m, 80m — all on one
split antenna, one capture device, one frozen build. This is the first time the programme has had
three bands whose per-cycle decode densities **overlap**. The standing question it can finally
attack is the one the 08-08 queue §7 named as the better-than-sparse next arm: **is "band" a real
term in OpenWSFZ's recovery deficit, or is it entirely composition — how many signals there are,
and how loud they are?**

### 0.1 🔴 ARCHITECT DE-BLINDING DISCLOSURE — read before scoring anything

**I ran a scoping analysis of all three legs on 2026-08-10 while drafting this spec** (HK-018:
prefer a five-minute measurement to a paragraph of reasoning). It went well beyond an instrument
control. **I have seen the primary metric, at three levels of adjustment, for all three band
pairs.** Per the P1a precedent, **prediction-scoring on the primary metric is SUSPENDED.** Nothing
below is blind except the items explicitly listed in §5.2.

Everything I saw, stated so QA can reproduce and challenge it rather than inherit it:

| quantity | 20m | 17m | 80m |
|---|---:|---:|---:|
| REF population (A∩B, clean) | 67 243 | 38 047 | 10 839 |
| raw recovery | 56.18% | 64.08% | 77.09% |
| median / min density per cycle | 28 / 4 | 21 / 3 | 8 / 1 |
| median reference SNR | −9 dB | −7 dB | −4 dB |
| REF cycles | 2 529 | 1 835 | 1 196 |
| distinct REF frequencies | 2 593 | 2 377 | 913 |

Standardised band contrasts I have already computed (exact density cell × SNR stratum, common
support, min cell n ≥ 10):

| pair | SNR quintile | SNR decile | SNR 20-tile | min coverage |
|---|---:|---:|---:|---:|
| 80m − 20m | +5.70 pp | +5.57 pp | +4.83 pp | 67% |
| 80m − 17m | +2.70 pp | +2.68 pp | +2.02 pp | 64% |
| 17m − 20m | +1.34 pp | +0.84 pp | +0.76 pp | 98% |

A crude earlier version of the same contrast — density held in a *window* (14–26) rather than
matched exactly — gave **80m−20m +6.79 pp [5.38, 8.18]**, **17m−20m +2.07 pp [1.15, 2.94]**,
**80m−17m +4.76 pp [3.34, 6.10]** (cycle-clustered). **The window version is inflated: matching
density exactly cuts every contrast, and cuts 17m−20m by more than half.** That is the single
most important methodological fact in this document, and it is why §3 mandates exact-cell
standardisation and forbids window matching.

### 0.2 🔴 A standing board claim is corrected by the above

The board and the 08-08 queue §7 both carry, as a non-blind disclosure, that **"17m runs ~2–3 pts
above 20m at matched density."** Under exact density matching that term is **0.76–1.34 pp**, not
2–3. The earlier figure was density-window matched, and the residual density difference inside
the window (20m mean 22.1 vs 17m 21.0 vs 80m 17.6) accounts for most of the gap. **Do not carry
the 2–3 pt figure forward.**

### 0.3 Two arms I considered and am NOT speccing, with the measurement that killed each

**HK-018/HK-021(i) — an unpowered gate is an instrument failure, so do not commission one.**

1. **"Is the frequency-lattice penalty `G` band-dependent?"** A crude split suggested a sign
   reversal on 80m (+1.85 / +2.45 / −5.14 pp raw). It does not survive: SNR-standardised and
   **frequency-clustered** (T2a: `r` is a station-level constant), `G` = **+3.19 ± 1.22** (20m),
   **+2.70 ± 2.26** (17m), **−0.86 ± 5.12** (80m). 80m has only **907 frequency clusters** and the
   band is dead, so no more data exists at any runtime. An 80m `G` could not detect anything short
   of a ~10 pp effect. 🛑 **`G` is not band-separable from this corpus. Do not propose it.**
   ✅ Incidental cross-validation worth recording: my independent reimplementation gives 20m
   `G` = **+3.19 pp** against T1's published **3.16 pp** — two harnesses, 0.03 pp apart.
2. **"Cross-band data breaks T2a's structural ceiling on the midpoint question."** It does not.
   The ceiling is on **distinct integer frequencies in the 200–3000 Hz passband** (~2 801
   possible). 20m alone already covers 2 593 (93%); the three-band union reaches 2 732 (97.5%);
   **80m contributes 9 frequencies not already present.** Different station populations do not buy
   new frequency support. 🛑 **T2's two-candidate/midpoint question stays unanswerable from
   `ALL.TXT`; this corpus does not rescue it.**

---

## 1. The question, and why it bears on D-001

D-001 is localised to **demodulation** — no sync refinement exists, extraction is non-coherent,
magnitude-only, single-symbol. Every recovery figure the programme quotes is a *level* measured on
one band. If band is a first-order term, then two things follow:

- every cross-band recovery number ever quoted (the "~55–64% three-estimate band") is
  heterogeneous by construction, and
- the surviving term is a **channel/signal-population** effect — multipath and Doppler spread
  differ enormously between a dying NVIS 80m path and a long-haul 20m path — which is precisely
  the class of impairment a non-coherent single-symbol demodulator with no sync refinement should
  be worst at. That would make channel characterisation a live D-001 sub-question.

If band is **not** a real term, the finding is equally valuable and cheaper to act on: recovery is
governed by density and SNR composition alone, and a recurring source of confusion in this
programme is closed permanently.

⚠️ Note the ordering is **not monotone in dial frequency**: 80m (3.573) 77.1% > 17m (18.100)
64.1% > 20m (14.074) 56.2%. A naive "lower band is easier" story does not fit and must not be
offered as the explanation.

---

## 2. Prerequisite X0 — the 80m reference must be repaired first

🔴 **The two `wsjt-x/ALL.TXT` files in the 80m gather are the same inode** (`links=2`, identical
md5, size 706 943). `tools/gather_live_run_artefacts.py` gathered FT991A into **both** 80m
folders. The 20m and 17m gathers are correct (distinct files, distinct sizes and hashes).

This matters because the programme's `REF` is `set(A) & set(B)` — the intersection of the two
WSJT-X instances (`t1_frequency_quantisation.py`). On 80m that intersection **silently degenerates
to a single instance**, so 80m's REF is on a different basis from 20m's and 17m's.

✅ **The original is intact and the repair is mechanical.** The Captain confirmed both instance
logs still exist; verified while drafting:
`C:\Users\Frank\AppData\Local\WSJT-X - FT991A-Copy\ALL.TXT` covers the 80m window with **10 942
Rx FT8 lines over 1 196 cycles**, distinct from FT991A's 10 952 / 1 197.

**X0 tasks:**

1. Gather FT991A-Copy's window slice into `artefacts/20260809_live_run_0155-8081-80m/wsjt-x/`,
   replacing the hardlink. Use the same tooling and window convention as the other legs; do not
   hand-edit. Preserve the existing file (rename, do not delete) until the replacement verifies.
2. Regenerate `qa/ARTEFACT_INVENTORY.md` (`python qa/artefact_inventory.py`), confirm `--check`
   clean, and confirm the **HARDLINKED** annotation on the 80m pair is gone.
3. Record in the leg's `contents.md` that the original gather duplicated one instance, and file
   the tool behaviour as an operational note — a gather that silently produces two identical
   "instances" defeats any arm that assumes two. **Do not fix the tool in this arm** (HK-011:
   `tools/` change is a Developer session with sign-off); report it.

**Verified expectation, so QA can check the repair rather than trust it:** repaired
80m `A∩B` = **10 913 raw / 10 839 clean**, i.e. 99.6% of A; recovery moves 76.84% → **77.09%**
(+0.25 pp).

🛑 **Do not "solve" this by falling back to an A-only reference on all three bands.** I measured
that basis change: it moves recovery by 0.10 pp (20m), 0.54 pp (17m), 0.25 pp (80m). Against a
17m−20m contrast of ~0.9 pp, a 0.54 pp basis inconsistency is fatal. **If X0 cannot be completed,
X1 is VOID** (ROW 0a) — it does not degrade to an A-only run.

---

## 3. Definitions — mechanical, no judgement

**Corpus and windows.** Reuse `t1_frequency_quantisation.load` unmodified so the population is
provably the one the programme uses. Fields are 0-based: `[0]` ts, `[4]` SNR, `[5]` DT, `[6]` freq
Hz, `[7:]` message. ⚠️ Confusing `[5]`/`[6]` inverts the result exactly.

| band | owsfz (system under test) | reference A | reference B | window |
|---|---|---|---|---|
| 20m | `20260808_live_run_0016-8080` | same folder | `…-8081` | `260808_004000`–`260808_111500` |
| 17m | `20260808_live_run_1154-8080-17m` | same folder | `…-8081-17m` | `260808_120000`–`260808_193900` |
| 80m | `20260809_live_run_0155-8080-80m` | same folder | `…-8081-80m` **after X0** | `260809_015445`–`260809_072815` |

The 80m window **ends at the reference's last decoded cycle** (`260809_072815`): WSJT-X stopped
decoding as the band died while OpenWSFZ kept archiving to 10:11Z. Cycles after that point have no
reference and cannot yield a recovery figure — they belong to X2, not here.
**Mechanical check:** the 80m REF population must be *identical* whether the window ends at
`072815` or `101100` (no reference decodes exist in between). Assert it.

**Population (`REF`).** `A ∩ B` on the `(ts, message)` key, then the two pre-registered exclusions
applied symmetrically and identically on every band: drop messages containing `<...>`, and drop
rows whose **reference** frequency falls outside 200–3000 Hz.

**Matched.** A REF row for which OpenWSFZ produced the same `(ts, message)`.

**Density.** Per cycle, the count of REF rows in that cycle. It is a **cycle-level** property.

**SNR.** 🔴 Always the **reference's** reported SNR, never ours. Our SNR carries a measured
**gain** error (`DEFECT-snr-reported-gain-error.md`: pooled slope 0.687, and per-corpus slopes
differ by band — 80m 0.563, 20m 0.723). Stratifying on our own SNR would inject a
**band-dependent** stratifier error, which is HK-021(h)'s worst case.

**Strata (HK-021(g) — fixed GLOBALLY, pooled across all three bands, computed once).** T1 §4.1's
defect was re-deriving quintile edges inside each stratum; do not repeat it. SNR edges come from
the pooled three-band REF SNR distribution. Density is **not** binned at all — it is matched
**exactly**, integer to integer (HK-021(f): it is discrete, so quantile-binning is wrong).

**The ladder.** Three levels of SNR adjustment, fixed here, all three reported:

- **L1** = exact density × SNR **quintile**
- **L2** = exact density × SNR **decile**
- **L3** = exact density × SNR **20-tile**

⚠️ Exact-integer-SNR matching was tested while drafting and is **excluded**: common support
collapses to 43–46% for the 80m pairs and the estimate becomes unstable (+4.91 pp at min-n 10,
+1.21 pp at min-n 25 on 3% coverage). A gate that cannot populate is an instrument failure
(S.1r's lesson). L1–L3 all populate at ≥64% coverage.

**Primary metric.**

```python
def B_std(A, B, level, min_cell=10):
    """Coverage-weighted standardised recovery difference, band A minus band B."""
    cells_A, cells_B = cells(A, level), cells(B, level)          # key: (density, snr_stratum)
    common = [c for c in cells_A
              if c in cells_B and cells_A[c].n >= min_cell and cells_B[c].n >= min_cell]
    w = sum(cells_A[c].n + cells_B[c].n for c in common)
    return sum((cells_A[c].n + cells_B[c].n) *
               (100*cells_A[c].matched/cells_A[c].n - 100*cells_B[c].matched/cells_B[c].n)
               for c in common) / w

def coverage(A, B, level, min_cell=10):
    """Share of the SMALLER band's REF that lies inside common support."""
    S = A if n_ref(A) <= n_ref(B) else B
    return sum(cells(S, level)[c].n for c in common_cells(A, B, level, min_cell)) / n_ref(S)
```

**Uncertainty — HK-021(i), non-negotiable.** The unit of observation is a decode; the unit of
independence is a **cycle** (density is a cycle property and decodes within a cycle share a
propagation instant). **Cycle-clustered bootstrap**, 1 000 draws, fixed seed, resampling whole
cycles within each band independently and recomputing the cells and `B_std` on every draw. A
binomial SE is forbidden and will be wrong by a large factor.

**Pairs.** Primary: **80m vs 20m** (widest contrast, best powered). Secondary, reported but not
gated: 17m vs 20m, 80m vs 17m.

**Replicate.** Repeat the entire computation with OpenWSFZ **8081** as the system under test
(the reference stays the same). This is a genuine unseen validity check.

---

## 4. The pre-registered gate

Rows are mutually exclusive, evaluated in strict order; boundary values fall to the inconclusive
row. Written as the code that evaluates it (HK-021).

### ROW 0 — void conditions, checked before any other row is read

- **ROW 0a — reference basis.** X0 complete: the two 80m `wsjt-x/ALL.TXT` files resolve to
  **different inodes**, and `|A∩B| / |A| ≥ 0.95` on all three bands. Otherwise **VOID**. Do not
  substitute an A-only reference (§2).
- **ROW 0b — pipeline determinism.** The clean REF population reproduces **exactly**: 20m
  `67 243`, 17m `38 047`. (These are T1/T2's own numbers; a mismatch means the loader or window
  drifted, not that the data changed.) Otherwise **VOID**.
- **ROW 0c — identifiability (HK-021(c)).** For the pair being read, `coverage ≥ 0.60` at **every**
  level L1/L2/L3. If not, that pair is **NOT IDENTIFIABLE — instrument failure, not a null**, and
  no row may be cited for it.
- **ROW 0d — power.** Cycle-clustered `SE(B_std)` at L1 **≤ 1.5 pp** for the pair being read.
  Otherwise **UNDERPOWERED**, read as instrument failure, not a null.
- **ROW 0e — window integrity.** The 80m REF population is identical for window ends `072815` and
  `101100`. Otherwise **VOID** (the window definition is wrong).

### ROW 1 / 2 / 3 — on the primary pair, 80m vs 20m

```python
b1, b3 = abs(B_std("80m","20m","L1")), abs(B_std("80m","20m","L3"))
ci_lo, ci_hi = clustered_ci(B_std, "80m", "20m", "L1")

if b1 >= 3.0 and b3 >= 0.5 * b1 and not (ci_lo <= 0 <= ci_hi):
    return "ROW 1"      # a band term SURVIVES full standardisation
if b1 <= 1.0 or b3 <= 0.3 * b1:
    return "ROW 2"      # composition, not band
return "ROW 3"          # real in magnitude, granularity-sensitive
```

**Consequences, stated as assertions before the data is read:**

- **ROW 1** ⇒ **band is a first-order term in the decode gap.** Every cross-band recovery figure
  must be quoted with its band, and the "~55–64% three-estimate band" is confirmed heterogeneous
  rather than a spread of estimates of one number. Promotes **channel characterisation**
  (multipath/Doppler spread vs. lattice placement) to a named D-001 sub-question. 🛑 It does **not**
  license any `src/` change, and 🛑 **it does not license proposing a capture run** — say what
  instrument would be needed and stop.
- **ROW 2** ⇒ 🛑 **cross-band recovery differences may never again be cited as band effects
  without exact-cell standardisation.** The apparent band ordering is density and SNR composition.
  This closes a recurring confusion and retires the "17m runs above 20m" folklore outright.
- **ROW 3** ⇒ inconclusive: the contrast is real in magnitude but depends on how finely SNR is
  controlled, i.e. residual SNR composition explains a material share. Report the ladder, do not
  pick a favourite level.

**Secondary pairs** are reported with the same ladder, coverage and clustered CI, and are
explicitly **not gated** — they inform, they do not decide.

**Replicate check (reported, not gated):** `|B_std(8080) − B_std(8081)|` at L1 for the primary
pair. Above **1.0 pp**, flag the instrument as unstable and say so in §1 of the report.
⚠️ **Do not** read 8080-vs-8081 self-consistency differences *across* bands as a band property:
the two 20m instances started 24 minutes apart while the 17m and 80m pairs started in the same
second, so capture start alignment is **confounded with band** in this corpus (the 08-08 13:00Z
finding, still unresolved).

---

## 5. Predictions

### 5.1 Suspended
Prediction-scoring on `B_std` at every level, and on all three band pairs, is **SUSPENDED** — I
have seen those numbers (§0.1).

### 5.2 Still blind — recorded for calibration
1. Cycle-clustered `SE(B_std)` at L1 for 80m−20m: **0.8–1.6 pp**.
2. Coverage at L3 for 80m−20m: **60–75%**.
3. Replicate agreement `|B_std(8080) − B_std(8081)|` at L1: **≤ 1.0 pp**.
4. ROW 0 fires on no pair.

⚠️ **My calibration, quoted because a gate turns partly on my bounds** (HK-021): categorical ROW
calls 5/7, ranges 7/10, **directional/shape calls 0/2**. Ranges are **symmetric and simply wide** —
the "asymmetric, too pessimistic" advice is falsified and deleted. **No gate in this spec turns on
a directional call of mine**; every bound above is a magnitude.

---

## 6. Citation limits

- 🔴 **Basis warning.** Recovery levels here use the **T1 basis**: `A∩B`, `<...>`-bearing messages
  **excluded**, 200–3000 Hz. They are **not** comparable with the H1a-corrected **≈57.8%** 20m
  figure, which used wildcard matching over a different population. 🛑 **Never compare a figure on
  one basis against a figure on the other** — that is the same error the H1a spec caught in the
  "~55–64% three-estimate band."
- 🔴 **`B_std` is an UPPER bound on the band term, not a floor.** Matching on a noisy, finite-
  resolution proxy for signal quality leaves residual confounding, which inflates the contrast.
  This is the **opposite** direction from T1's `G` (a floor, because stratifier error attenuates a
  contrast). Do not apply T1's "quote it as at least X" wording here; quote **"at most"**.
- Raw, unstandardised recovery differences between bands are **descriptive only** and must always
  appear beside the standardised figure, never alone.
- The 80m leg's own dying tail is **out of scope here** and is X2's subject.
- 🛑 No `src/` recommendation may be drawn from this arm in any row.

---

## 7. What this arm cannot answer

- **Why** a band term exists, if one does. Multipath/Doppler spread is a hypothesis; nothing in
  `ALL.TXT` measures it.
- Anything about `G`, the lattice, OSR, or the midpoint question (§0.3 — measured, not argued).
- Anything requiring new capture. 🛑 **Do not propose one.**

---

## 8. Deliverables

1. `x1_cross_band_decomposition.py` in `qa/cycleframer-alignment-replay/`, importing
   `t1_frequency_quantisation.load` unmodified.
2. A report, HK-017 timestamps, carrying: the X0 repair evidence (inodes, counts, inventory
   `--check`), the ordered ROW 0 trace, the full ladder table with coverage and **clustered** CIs,
   both secondary pairs, the 8081 replicate, §5.2 predictions scored, and §6's citation limits
   restated in full.
3. NFR-021: counts and rates only. Message text stays out of anything tracked.
4. 🔴 **Update `BOARD.md` in the same edit as the result** (HK-024), and correct the "17m runs 2–3
   pts above 20m" claim there and in the queue §7 whatever this arm returns — §0.2 already
   falsifies it.
