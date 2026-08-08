# QA → Architect: T1 results — frequency-lattice quantisation costs ~3 pp, ROW 3

**Author:** QA, 2026-08-08 (20:46 UTC, `date -u`, per HK-017). Repo `main` at `31387bf`.
**Scope:** executes the spec at
`qa/cycleframer-alignment-replay/2026-08-08-2030-architect-to-qa-spec-t1-frequency-quantisation.md`
in full — same populations, same exclusions, same pre-registered gate, verbatim.
**Status:** pure re-analysis of `ALL.TXT` files already on disk and inventory-verified. No `src/`
change, no capture, no rebuild. Harness `qa/cycleframer-alignment-replay/t1_frequency_quantisation.py`,
currently untracked; committing is the Captain's call (HK-010). NFR-021: no message text and no
callsign appears anywhere below — every figure is a count, a rate, or a frequency statistic.

---

## 1. Bottom line

**20m (primary, citable): `G = 3.16 pp` → ROW 3 — real, but small, and it does not clear the 4.0 pp
bar for ROW 1.** The instrument checks all pass cleanly (§3), so this is a measured result, not an
instrument failure. Frequency-lattice quantisation is a genuine, small contributor to the
demodulation-stage deficit — concentrated in weak-to-moderate SNR (up to ~7 pp there) and negligible
at strong SNR (~1.3 pp) — but on its own it does not promote sub-bin sync refinement to the leading
D-001 treatment candidate. Per the gate's own ROW 3 consequence: report the full curve, fold into
the demodulation framing, do not spend a Developer session on this alone.

Your recorded prediction (§4.1 of the spec) was **ROW 1, `G` in 3–6 pp**. The point estimate landed
exactly on the bottom edge of that range (3.16 pp) but the categorical call misses — it sits just
under your own gate's ROW 1 threshold. Recording that plainly, as your own §4.1 asked: this is the
boundary case the gate was built to catch, not a clean confirmation.

## 2. Method, exactly as specced

- **Reference** = intersection of WSJT-X FT991A and FT991A-Copy on `(ts, message)`, 20m clean window
  `00:40–11:15` UTC (`260808_004000`..`260808_111500`), same window the 1942 report uses.
- **Matched** = reference decode for which OpenWSFZ 8080 produced the identical `(ts, message)` key.
  **Missed** = reference decode with no such row.
- **Trap avoided (spec §2):** every `r` and every SNR value below comes from the reference —
  specifically **WSJT-X FT991A's** own reported frequency/SNR, consistently, for both the matched
  and missed groups, never OpenWSFZ's. §3 below shows this choice is not load-bearing: repeating the
  whole computation using FT991A-Copy's frequency instead gives `G = 3.13 pp` — 0.03 pp apart, well
  inside noise. Either instance would have produced the same reading.
- **Pre-registered exclusions (§3.2 of the spec), applied before any statistic, both groups
  symmetrically:** decodes carrying an unresolved `<...>` token (1 113 of 69 222, 1.6%); decodes
  outside 200–3000 Hz (866, 1.3%); cycles outside the clean window (handled by construction). Kept
  population: **67 243** of 69 222 (97.1%).
- **Metric:** `residual(f) = min(f mod 3.125, 3.125 − f mod 3.125)`, quintiles of the reference
  population's `r`, `G = recovery(Q1) − recovery(Q5)` in percentage points.

## 3. Instrument checks (the gate's ROW 0 conditions) — all pass

| check | bar | 20m value | verdict |
|---|---|---:|---|
| smallest quintile | ≥ 500 | 9 317 | pass |
| `mean_r_ours` (OpenWSFZ, matched subset, this window) | < 0.45 | **0.2404** | pass — on-grid, consistent with §0.3's whole-corpus 0.2397 |
| `mean_r_ref` (WSJT-X, this population) | ≥ 0.50 | **0.7367** | pass — off-grid, consistent with §0.3's whole-corpus 0.7398 |
| `G` plausibility ceiling | ≤ ~15 pp (else instrument failure) | 3.16 | well inside |

Both instrument numbers reproduce the whole-corpus figures from the spec's §0.3 control to three
decimal places even though this run uses a different (windowed, exclusion-filtered) population. That
cross-check was not required by the spec but is a cheap sanity margin, and it held.

## 4. Primary result — 20m, citable

| quintile | `r` range (Hz) | n | matched | recovery |
|---|---:|---:|---:|---:|
| Q1 (bin-centre) | 0 – 0.250 | 9 317 | 5 473 | **58.7%** |
| Q2 | 0.250 – 0.625 | 17 085 | 9 733 | 57.0% |
| Q3 | 0.625 – 0.875 | 10 700 | 6 048 | 56.5% |
| Q4 | 0.875 – 1.125 | 10 934 | 5 850 | 53.5% |
| Q5 (bin-edge) | 1.125 – 1.5625 | 19 207 | 10 675 | **55.6%** |

`G = 58.7 − 55.6 = 3.16 pp`. The curve is not perfectly monotone (Q5 ticks back up 2.1 pp from Q4's
low), but the bin-centre quintile is the clear high point and the trend from Q1 to Q4 is monotone
downward. This is the same shape your own SNR-recovery curve has always had — real, sub-linear, not
a clean staircase.

### 4.1 Mandatory control — is `G` carried by one SNR band?

Recomputed within reference-SNR quintiles (SNR always from WSJT-X FT991A, never ours, per
`DEFECT-snr-reported-gain-error.md`):

| SNR quintile | approx. band (dB) | n | `G_sub` (pp) |
|---|---|---:|---:|
| 1 (weakest) | ≤ −16 | 11 532 | **6.00** |
| 2 | −16…−11 | 14 173 | **4.44** |
| 3 | −11…−6 | 14 424 | **6.91** |
| 4 | −6…0 | 12 920 | 1.24 |
| 5 (strongest) | ≥ 0 | 14 194 | 1.36 |

**`G` is not carried by a single SNR quintile — it is present across three of five bands (weak to
moderate SNR) at 4.4–6.9 pp, exceeding the 3.16 pp headline, and nearly vanishes at strong SNR
(1.2–1.4 pp).** That is a coherent, physically sensible pattern: quantisation costs more where the
decode margin is already thin and costs almost nothing where a signal has margin to spare. The
headline `G` is diluted by the two strong-SNR quintiles, where recovery is already 70–87% and there
is little room left to lose. **This is genuinely new information the top-line number hides:** among
weak-to-moderate signals specifically, sync quantisation is closer to your predicted 4–6 pp band than
the pooled figure suggests.

## 5. Secondary — 17m, replication signal only, NOT citable as a row

Per spec §3.1, the 17m leg voided under its own ROW 0b (board, 08-08 14:15Z) and **no row may be
cited from it.** Reporting the numbers for completeness only:

- Reference population 38 827 → 38 047 after exclusions (582 `<...>`, 198 out-of-band).
- Matched: 24 380/38 047 = 64.1%.
- Instrument checks pass (`mean_r_ours = 0.2538`, `mean_r_ref = 0.7485`, min quintile n = 6 188).
- Quintile recoveries: 64.1 / 65.8 / 67.3 / 60.8 / 63.9%. `G = 0.19 pp`.

**Flagging the tension plainly rather than explaining it away:** 17m's `G` is near zero while 20m's
is 3.16 pp. Because the leg is void, this is not evidence against the 20m finding — but it is not
independent corroboration either, and it should not be read as a second data point until a valid 17m
(or any second-band) leg exists. SNR-quintile `G_sub` on 17m ranges −0.23 to 5.53 pp, similarly mixed.

## 6. Reading against the gate

```
n_min_quintile = 9317   ≥ 500        → not ROW 0
mean_r_ours    = 0.2404 < 0.45       → not ROW 0
mean_r_ref     = 0.7367 ≥ 0.50       → not ROW 0
G              = 3.16   < 4.0        → not ROW 1
G              = 3.16   > 1.0        → not ROW 2
                                      → ROW 3
```

**ROW 3 consequence, per the spec's own table: "Real but small. Report the full quintile curve. Fold
into framing; do not spend a Developer session on it alone."** That is what this document does.

## 7. What this does and doesn't change

- **Does not overturn the demodulation-stage framing (spec §0.1).** A ROW 2 result would have killed
  the frequency half of that thesis outright; it did not happen. A small, SNR-concentrated, real
  effect is consistent with demodulation quality mattering, just not sufficient by itself to explain
  the bulk of the ~97% figure.
- **Does not promote sub-bin frequency refinement to the leading treatment candidate.** That was
  ROW 1's consequence specifically; ROW 3 explicitly withholds it.
- **Leaves the two remaining suspects from spec §7 exactly where they were** — non-coherent
  single-symbol extraction and the absent time refinement — neither answerable from `ALL.TXT`, per
  the spec's own §3.5 scope limit (reference DT resolution 0.1 s is coarser than our 0.08 s grid
  step; not re-litigated here).
- **Worth carrying forward for later:** if a Developer session ever touches sync refinement for a
  different reason (e.g. investigating the time axis with a different instrument), the SNR-stratified
  finding in §4.1 says the frequency component of that fix would concentrate its benefit on weak
  and moderate signals, not strong ones — useful for sizing that work if it's ever proposed, but this
  alone does not justify proposing it.

## 8. Artefacts

- Harness: `qa/cycleframer-alignment-replay/t1_frequency_quantisation.py` (untracked).
- Inputs: `artefacts/20260808_live_run_0016-808{0,1}/{owsfz,wsjt-x}/ALL.TXT` (20m),
  `artefacts/20260808_live_run_1154-808{0,1}-17m/{owsfz,wsjt-x}/ALL.TXT` (17m) — both already
  inventory-verified, `qa/ARTEFACT_INVENTORY.md --check` clean before this run.
- No files written outside `qa/`; no message text or callsign logged anywhere in script output.

## 9. Citation limits

**May be cited:** the 20m `G = 3.16 pp`, ROW 3; the instrument-check pass; the SNR-quintile
breakdown in §4.1, including the "not carried by one band, concentrated in weak/moderate SNR"
reading; the cross-instance robustness check (FT991A vs Copy, 3.16 vs 3.13 pp).

🛑 **May not be cited:** any row or `G` value from the 17m leg (§5 — void, replication signal only);
any claim that this result promotes sub-bin refinement to the leading D-001 treatment (that is ROW
1's consequence, not ROW 3's).
