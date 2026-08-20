# P-LIVE Stage 1 results — ROW 2 fires on the PRIMARY corpus. BOTH LIMBS CLOSE. The zero is STRUCTURAL (Amendment A4.3 confirmed empirically, not just as a risk).

**QA → Architect** · 2026-08-18 15:50 UTC · branch `qa/n1-ber-results`
**Spec:** `qa/rr-study/2026-08-17-1806-architect-to-qa-p-live-population-and-n-series-replication-spec.md`
**Amends applied:** `qa/rr-study/2026-08-18-1457-architect-to-qa-p-live-stage1-go-ahead-and-amendment-a4.md`
(A4.1 ROW 0f, A4.2 named PRIMARY, A4.3 mandatory decile table)
**Harness:** `qa/rr-study/p-live-population/plive_population.py` (population builder, new),
`qa/rr-study/p-live-population/run_stage1.py` (Stage 1 harness, new). Full console:
`qa/rr-study/p-live-population/results/full_run_console.log`. Report JSON:
`.../results/p_live_stage1_report.json`. Raw per-row measurements (numeric fields
only, NFR-021): `.../results/p_live_stage1_rows.json` (29.6 MB — flagged below,
§6).

---

## 0. Verdict

**ROW 2 FIRES on the PRIMARY population. `CI_hi(f_cross) = 0.0000% < 5%`. Both limbs
of D-001 limb 2 close, on outcome evidence, for the first time with a non-degenerate
denominator.**

- **PRIMARY (`20260803_live_run_1713`, Amendment A4.2): `f_cross = 0/15,389` rows
  (`n_clusters = 3,917`).** Bootstrap CI is `[0.0000%, 0.0000%]` — degenerate by
  construction (every one of 2,000 resamples returns exactly zero, exactly as
  Amendment A4/N5's retraction anticipated). **Rule-of-three bound: 0.0765%** — this
  is the number to cite, not the degenerate CI. Against N5's own honest bound of
  4.37% (67 clusters) and the 5% cut, this is a **~57× tighter bound on ~58× the
  clusters**, and it clears the cut with no marginal room at all (N5's bound cleared
  by 0.6pp; this one clears by 4.92pp).
- **All four extension corpora independently corroborate the same result** (own
  populations, own bootstraps, never pooled — §4): `f_cross = 0.0000%` on every one,
  rule-of-three bounds 0.109%–0.379%, medians and decile shapes visually identical
  to the primary's. This is not four more data points feeding one estimate; it is
  the same null replicating cleanly across five independently-captured corpora
  spanning three bands and two receiver instances.
- 🔴 **Amendment A4.3's warning is now an EMPIRICAL FINDING, not a risk flagged in
  advance: the zero is STRUCTURAL.** Every measured row in every corpus has
  `BER_V0 > B50` (i.e. `n_crossable = n_measured` exactly, `n_breakable = 0`
  exactly, everywhere) — the P-LIVE miss population never once produced a row within
  reach of the correction threshold. See §3.

**ROW 0c/0e/0f (Amendment A4.1) all cleared on the PRIMARY population before the
gate was evaluated** — see §2. No ROW 0 fired anywhere in this run.

**N5 is now ruled against this pair, per the spec's own §9 instruction**: its
ROW 2 (degenerate CI, honest bound 4.37%, HELD per the 2026-08-17 retraction) is
**confirmed** by Stage 1's non-degenerate result on a population ~58× the size, with
the added, materially different finding that the P-LIVE zero is structural in a way
N5's own THE-135/567 zero was not (§3.3).

---

## 1. Scope compliance and the sign tests (ROW 0d)

Both mandatory sign tests re-run **fresh**, not inherited from N4/N5:

- `n5_stats_sign_test.py` (f_break/f_net logic): **PASS**, all 4 cases, including
  case (3) (the load-bearing "half cross, half break" case Amendment A1.2 exists to
  catch).
- `n4_sign_unit_test.py` (V3_cum DSP correctness, 48 realisations × 4 injected
  offsets, both V1 and V3_cum): **PASS**, 187.0s.

DLL re-hashed from disk before arming (not inferred from a label):

```
sha256(src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll) = 6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672
```

Matches the pin exactly (shim 20260042, asserted by the harness on load). No `src/`
touched, no Developer session, no DLL rebuild, no capture run (HK-011 not engaged).
No per-row frequency search anywhere — `df_hz=0.0` fixed for every row, no sweep.
Rectangular window only.

**Population builder self-check (before any extraction ran):** `plive_population.py`
run standalone against all five corpora reproduced the spec's own §1 table
**exactly on row counts** (18,012 / 33,303 / 31,160 / 14,276 / 2,354) and within
0.5% on cluster counts (4,113 / 2,743 / 2,646 / 1,849 / 817 vs the spec's 4,108 /
2,732 / 2,638 / 1,849 / 817) — the small cluster deltas on three of five corpora
resolve themselves during measurement (a `ts` with zero WAV-eligible rows after
drops isn't a "measured" cluster; see the per-corpus `n_clusters_measured` figures
in §4, all slightly below the pre-drop count for exactly this reason).

---

## 2. ROW 0c/0e/0f — evaluated on PRIMARY only (Amendment A4.2), all CLEAR

| row | quantity | bound | measured (primary) | verdict |
|---|---|---|---|---|
| 0c | n_measured / n_clusters | ≥500 / ≥200 | 15,389 / 3,917 | clear |
| 0e | median hd_disagree_v0_v3 | ≥5/174 bits | 28.0/174 | clear |
| 0f (A4.1) | median `BER_V0` | ≥41.97% | 49.43% | clear |

HK-025 self-classification, re-derived independently before running: all three are
**VALIDITY** (0c: an underpowered primary makes every downstream CI meaningless; 0e:
if V0/V3 read near-identically the contrast cannot move and no null is
interpretable; 0f: a median below the band would mean the assembly is not selecting
the population Sec.2 defines). I agree with the Architect's classification on all
three; no HK-025 refusal exercised anywhere in this run.

Note the direction ROW 0f cleared **by a wide margin, not narrowly**: 49.43% sits
**7.46pp above** N1/N5's own published 43.97%, not merely inside the ±2pp band. This
is itself informative and foreshadows §3 — P-LIVE's miss population runs
*harder* than THE-135/567's, consistent with it containing rows where no candidate
was ever found at all (the superset property Sec.2.1 names), not merely
candidate-present-and-failed rows.

---

## 3. Amendment A4.3 — the mandatory decile table, and why the zero is structural

### 3.1 The table (PRIMARY, `n=15,389` — i.e. the WHOLE measured population, since
every row is crossable)

| percentile | `BER_V0` |
|---|---|
| p0 (min) | 33.91% |
| p10 | 44.25% |
| p20 | 45.98% |
| p30 | 47.13% |
| p40 | 48.28% |
| p50 (median) | 49.43% |
| p60 | 50.57% |
| p70 | 51.72% |
| p80 | 52.87% |
| p90 | 54.60% |
| p100 (max) | 64.37% |

`B50 = 11.3%`. **Even the single best row across 15,389 measured misses (`p0`) sits
39.3 bits above the correction threshold** (33.91% × 174 ≈ 59.0 bits vs `B50`'s 19.7
bits) — nowhere near the 5-bit gap N5 found on THE-135/567's own crossable
population. `p10 = 44.25%` is **32.9pp above** `B50`, dramatically clearing the
Architect's own pre-registered "P(p10 > 20%) ≈ 70%" bar (§8 A4 predictions).

### 3.2 What this means, stated plainly per Amendment A4.3's instruction

`P-LIVE`'s median `BER_V0` sits at **49.43% — statistically indistinguishable from
50%, i.e. chance level against a random 174-bit codeword.** This is not "a harder
version of the same kind of miss" N5 measured; it is a **different population in
kind**. `THE-135`/`THE-567` are candidate-present-and-failed: our own front-end
found *something* at that position and OSD/BP failed on it, leaving real residual
structure (N5's own crossable population had a minimum of 13.79%, only 5 bits from
`B50`). `P-LIVE`'s miss population instead requires only that WSJT-X decoded and we
detected **nothing at all** — and at 49.43% median, the raw single-symbol
non-coherent extraction at WSJT-X's exact reported position is producing
**essentially uncorrelated bits**, consistent with there being no candidate there
for our own energy-detection/sync stage to have found in the first place.

**A zero `f_cross` here is therefore an upper bound on the prize, not evidence
about V3's mechanism** — exactly the distinction Amendment A4.3 required not be
blurred, and now confirmed by measurement rather than merely flagged as a risk. V3
(order-3 coherent) was never handed anything within reach to convert at these
positions; this result says nothing about whether V3 helps on rows that DO carry
residual structure (that remains N1/N2's own already-ruled territory, R2 excluded
per standing prohibition).

### 3.3 Comparison table, N5 vs P-LIVE (context, not a new statistic)

| | N5 (THE-135/567) | P-LIVE (primary) |
|---|---|---|
| population | candidate-present-and-failed | WSJT-X decoded, we detected nothing |
| n crossable | 403/405 | 15,389/15,389 (100%) |
| median `BER_V0` | 43.97% | 49.43% |
| min `BER_V0` on crossable | 13.79% (5 bits from `B50`) | 33.91% (39.3 bits from `B50`) |
| `f_cross` | 0/403 | 0/15,389 |
| honest bound | 4.37% (rule-of-three, 67 clusters) | 0.0765% (rule-of-three, 3,917 clusters) |

Same qualitative verdict, but P-LIVE's is unambiguous where N5's was marginal
(cleared the 5% cut by only 0.6pp) — and P-LIVE independently explains *why* it is
so much more decisive: the population is further from `B50` by construction.

Deciles for all four extension corpora are in `p_live_stage1_report.json` — same
shape throughout (p0 in the low-to-mid 30s, median pinned at 49.43% on three of
five, 49.43%/48.85%/49.43% pattern on the fifth's neighbouring deciles), not
reproduced in full here to keep this report to the mandatory table plus the one
that gates.

---

## 4. Extension corpora — descriptive replication, never pooled (spec §5.2, A4.2)

| corpus | n_measured | n_clusters | median `BER_V0` | `f_cross` | rule-of-three |
|---|---|---|---|---|---|
| `20260803_live_run_1713` (**PRIMARY**) | 15,389 | 3,917 | 49.43% | 0.0000% | 0.0765% |
| `20260808_live_run_0016-8080` | 29,441 | 2,740 | 49.43% | 0.0000% | 0.1093% |
| `20260808_live_run_0016-8081` | 27,609 | 2,643 | 49.43% | 0.0000% | 0.1133% |
| `20260808_live_run_1154-8080-17m` | 13,006 | 1,846 | 49.43% | 0.0000% | 0.1622% |
| `20260809_live_run_0155-8080-80m` | 2,107 | 790 | 49.43% | 0.0000% | 0.3785% |

🛑 **Never summed.** `0016-8080`/`-8081` observe the same cycles (median per-cycle
Jaccard 1.000/0.909/1.000 per the spec) — their cluster counts stay separate exactly
as instructed. Row totals across all five sum to 87,552 measured / a
context-only, never-statistically-pooled 11,936 clusters — reported here purely to
show scale, not used anywhere in the gate.

`f_break` is `NaN`/descriptive-only in **every** corpus: `n_breakable = 0` exactly,
everywhere — not merely below the 30-row HK-021(j) floor, but structurally zero,
because (per §3) not one measured row anywhere had `BER_V0 ≤ B50` to begin with.
`f_net` therefore also reads exactly `0.0000%` everywhere with a degenerate
`[0,0]` CI — it is uninformative here, correctly reported as such, not a finding.

---

## 5. Drop reasons, disclosed per corpus (none change the verdict)

| corpus | `no_true_codeword` | `v0_extract_rc_-3` (freq outside our own 200–3000 Hz window) |
|---|---|---|
| PRIMARY | 1,605 (8.9%) | 1,018 (5.65%) |
| 0016-8080 | 3,058 (9.2%) | 804 (2.4%) |
| 0016-8081 | 2,798 (9.0%) | 753 (2.4%) |
| 1154-17m | 1,076 (7.5%) | 194 (1.4%) |
| 0155-80m | 194 (8.2%) | 53 (2.3%) |

`no_true_codeword` rates land within a point of N5's own ~8% — consistent, expected
(WSJT-X message formats our encoder occasionally can't round-trip). `v0_extract_rc_-3`
is **new to this round and self-explanatory**: `ft8_extract_llrs_at` rejects (rather
than clamps) any requested position whose frequency bin falls outside the shim's own
hardcoded `[200, 3000]` Hz waterfall range (`ft8_shim.c:1544-1548`) — these are rows
where WSJT-X's own passband (wider than ours) reported a station **outside our
production window entirely**, so they were categorically unreachable by any
LLR-stage treatment regardless of this measurement. No `no_wav` drops occurred
anywhere — every population row's `ts` had a WAV present in its own corpus's
`wsjt-x/wav/` directory (the anchor-supplying leg, spec §2 point 6); the small
cluster-count deltas noted in §1 are fully explained by these two drop reasons, not
by missing audio.

---

## 6. Scope, NFR-021, and one thing flagged rather than silently done

- No `src/`, no Developer session, no DLL rebuild, no capture run (HK-011 not
  engaged). No per-row frequency search; `df_hz=0.0` fixed. Rectangular window
  only. R2 stays excluded — nothing here touches it.
- **NFR-021 — grepped every emitted file individually, not merely asserted:**
  `p_live_stage1_report.json`, `p_live_stage1_rows.json`, `p_live_stage1_run.log`,
  `full_run_console.log` all **0 hits** on `message` (case-insensitive). Every row
  dict in `p_live_stage1_rows.json` carries only
  `{ts, corpus, ber_v0, ber_v3, d_ber, crosses, breaks, hd_disagree_v0_v3,
  anchor_freq_hz, anchor_dt}` — spot-checked, matches `measure_row`'s own
  contract, which never assigns a `message` key at any point.
- ⚠️ **Flagging, not silently committing: `p_live_stage1_rows.json` is 29.6 MB** —
  the raw per-row measurement dump across 87,552 rows (vs N5's 130 KB / 405 rows).
  It is NFR-021-clean and the fullest audit trail this round has, but it is an order
  of magnitude larger than anything else committed on this branch to date
  (`row0a_results.json`, the next-largest, is 2.98 MB). Committing unless told
  otherwise — flagging the size here per HK-016/HK-022 discipline rather than
  letting it pass silently.
- HK-009 ASCII console (`sys.stdout.reconfigure` where available) — followed. No
  Windows-console encoding failures during the ~30-minute run.
- This was an unattended run of non-trivial length (sign tests ~190s + extraction
  ~28 minutes). Run via the harness's own background execution with a completion
  monitor watching the log for a terminal state (ROW-fires or the final
  "Wrote results" line) — not a `Monitor`-owned long-lived process, and it did
  complete and was read back from its own output file, not merely trusted on a
  "done" claim (HK-022/HK-023).

---

## 7. Predictions scored (Amendment A4 §2 — nothing gated on these)

| prediction | called | measured | verdict |
|---|---|---|---|
| `f_cross` on primary | 0.000–0.005 | 0.0000 | **HIT** |
| P(ROW 2 fires) ≈ 80% | — | ROW 2 fired | **HIT** |
| P(ROW 1) ≈ 3%, P(ROW 3) ≈ 17% | — | neither fired | consistent |
| P(p10 of crossable > 20% BER) ≈ 70% | DIRECTIONAL | p10 = 44.25% (primary) | **HIT, by a wide margin** |
| P(any ROW 0 fires) ≈ 7% | — | none fired | **HIT** |
| P(`f_break` > 0 with CI clearing zero) ≈ 70% | — | `f_break` undefined, `n_breakable = 0` everywhere | **MISS** — not merely "CI doesn't clear zero," the breakable stratum is structurally empty in every corpus, the opposite of "becomes non-trivial with a real denominator" |

Five of six score as hits or consistent; the `f_break` prediction is a clean miss
and, per standing calibration discipline, is reported for the record rather than
rounded away — the Architect's own tally is the Architect's to update.

---

## 8. What I did NOT do

Per the go-ahead's own "run Stage 1, then STOP AND REPORT — do not continue into
Stage 2 unattended," I have not started Stage 2 (N1 on P-LIVE, limb 1/refinement
harm replication) or any later stage. R2 exclusion is unaffected by anything in this
report. A2/A3 remain open per the spec's own instruction and have not become a
round.

**Recommend:** given how unambiguous and structurally-explained this result is
(§3), Stage 2 (N1 on P-LIVE) looks like the natural next step if the Architect wants
to keep testing limb 1's harm on this larger population — but that is the
Architect's call, not mine to make here. Awaiting ruling on N5's pairing with this
result and on whether/when to proceed to Stage 2.
