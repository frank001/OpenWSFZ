# QA → Architect: AO1 results — ROW 3 FIRES (production framing defect confirmed-in-part), Part C WITHHELD on a grid-step-exact quartile straddle

**Author:** QA
**Date:** 2026-08-19 11:35:47Z (mechanically derived via `date -u`, HK-017)
**Runs:** `qa/rr-study/2026-08-19-1058-architect-to-qa-prereg-ao1-production-time-origin-offset.md`
("the spec") in full, §11 order
**Harness (new):** `qa/rr-study/ao1-production-time-origin-offset/{ao1_common.py,run_ao1.py}`
**Status:** 🔴 **ROW 3 FIRES — the production decode buffer sits off the UTC
grid by a signed constant, and the archive is faithful to what the live
daemon decoded. Route A is promoted from open to confirmed-in-part.** 🛑
**Part C (the recall-cost sizing) did NOT run this round — ROW 0f fired**,
so whether this is a D-001 treatment (C1) or a product-only fix (C2/C3) is
still unanswered. QA STOPS here per §11 step 10.

---

## 0. Headline

**R (the reporting gap, live path vs archive-independent reference, full
25,411-row/4,371-cluster matched population, cluster-bootstrapped):
`+0.700s`, CI95 `[+0.700,+0.700]s`.** The degenerate-looking CI is not a bug —
`d_dt` is bimodal at exactly `{+0.6: 47.7%, +0.7: 52.1%}` (plus a 0.2% tail at
±0.1 more), the reporting-quantisation signature the spec's own §2 S3
disclosure predicted (reference ticks in 0.1s, ours in 0.08s, straddling one
true constant) — independently re-derived here, not merely re-quoted.

**K (the physical-position sweep, on OUR OWN archived audio, anchored at the
reference's own (freq, dt), M3's 49-point grid): `+0.650s`, median `BER_V0`
at that argmin = `6.90%`.** Sharp, single trough — 49.43% (chance) at the raw
reference anchor (`dt_offset=0.0`), flat chance-level (43–50%) across the
entire rest of the ±1.2s grid, three points at `{+0.60: 8.05%, +0.65: 6.90%,
+0.70: 12.64%}`, back to chance one step outside that. **Zero extraction
failures at any of the 49×551 = 26,999 calls.**

**`|R|=0.700s ≥ θ`, `|K|=0.650s ≥ θ`, `sign(K)=sign(R)` (both positive),
`|K−R|=0.050s ≤ 0.15s` ⇒ ROW 3 FIRES.** The signal is not merely mislabelled —
it physically sits ~0.65s later inside our own archived buffer than the
reference's grid says, and the archive agrees with the live path to within
one reference reporting-tick. This is the discriminator the 19:21Z ruling
said was missing: R alone (live path) could not tell labelling from
placement; K (independently located in our own WAV) says placement.

**Replicated, independently, on ALL THREE extension corpora AO1 uses** (both
`-8081` legs excluded per spec §4): `R=+0.700s` and `K=+0.650s` on
`20260808_live_run_0016-8080` (43,662/2,733), `20260808_live_run_1154-8080-
17m` (25,437/1,856), and `20260809_live_run_0155-8080-80m` (8,598/1,179,
`R` CI95 `[+0.600,+0.700]s` — the smallest corpus, mildly wider). **Every
corpus, every leg, lands on the identical `+0.65s` physical offset.** This is
the tightest cross-corpus agreement this whole investigation has produced.

🛑 **Part C did NOT run.** ROW 0f fired: the last of four chronological
quartiles (`260804_101545`…`260804_135445`, the final ~29% of PRIMARY) swept
its own argmin to `+0.60s` against the pooled `+0.65s` — a delta of exactly
**one grid step (0.05s)**, which cleared the bound only by floating-point
noise (`0.65−0.60 = 0.050000000000000044` in IEEE double, `>0.05` by
4.4×10⁻¹⁷). See §3.3 — this is a genuine HK-021(m) flag, not a hedge: the
row's own tolerance equals the sweep's own grid resolution, so it has **zero**
power to distinguish "true one-step drift" from "a single quartile's own
noisy argmin landing on the neighbouring grid point," and it will fire on
either. Per the spec's own §5 table this is not a STOP — Part B still reports
in full — but it withholds Part C regardless of the main-row outcome, so the
recall-cost question (C0–C4, whether this is a D-001 treatment candidate)
remains **open**.

---

## 1. Gate trace, strict order (§11)

| Row | Condition | Measured | Result |
|---|---|---|---|
| 0a | DLL SHA256 re-hashed, asserted before arming | `6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`, shim 20260042 | **clear** |
| 0e | Mandatory sign unit test (Stage 2's construction, reused verbatim — §2.1) | see §2.1 | **PASS** |
| 0b | matched-pair dry count, PRIMARY, rows<2000 OR clusters<500 | 25,411 rows / 4,371 clusters | **clear** |
| 0c | cluster-median `dt_ref` outside [−0.35,+0.35]s two-sided | **+0.200s** | **clear** |
| — | `R`, full population, cluster-bootstrapped, SIGNED | **+0.700s**, CI95 [+0.700,+0.700]s, p=0.0000 | reported |
| — | `K`, seeded 551-row sample sweep | **+0.650s**, median BER_V0=6.90% | reported |
| 0d | median `BER_V0` at K's argmin outside [1.0%,15.0%] two-sided | **6.90%** | **clear** |
| 0f | any of 4 chronological ts-quartiles' own argmin differs from pooled by >0.05s | max deviation = **0.050000000000000044s** (float-boundary case, §3.3) | 🔴 **FIRES** — Part C WITHHELD |
| 0g | reference SNR field unparseable on >5% of rows | **0.00%** | **clear** |
| **ROW 1** | \|R\|<θ AND \|K\|<θ | R=0.700, K=0.650 | does not fire |
| **ROW 2** | \|R\|≥θ AND \|K\|<θ | K≥θ | does not fire |
| **ROW 3** | \|R\|≥θ AND \|K\|≥θ AND sign match AND \|K−R\|≤0.15s | 0.700/0.650, same sign, \|K−R\|=0.050s | 🔴 **FIRES** |

HK-025: independently re-derived before arming (`run_ao1.py:hk025_check()`,
fresh reasoning, not copied from the spec's §6 table). Concurs on all seven
ROW 0 rows — each routes fired-vs-cleared to a genuinely different downstream
action (0f: Part C withheld vs eligible; 0g: Part C descriptive vs gated;
Part B is unaffected by either). No refusal.

---

## 2. `R` — the reporting gap, full population

### 2.1 Matched-pair construction (§4)

Symmetric uniqueness rule (spec's own one-directional rule and this
symmetric one coincide on PRIMARY — zero ambiguous pairings measured either
direction, reported explicitly rather than assumed):

```
n_ref_rows=43,423  n_our_rows=64,417
n_ambiguous_ref_side=0  n_ambiguous_our_side=0
n_matched=25,411  n_matched_clusters=4,371
```

### 2.2 The bimodal signature (independently re-derived, not re-quoted from §2's scouting)

`d_dt = our_dt − ref_dt` over all 25,411 matched pairs takes almost exactly
two values:

| `d_dt` | count | share |
|---|---|---|
| +0.7 | 13,244 | 52.1% |
| +0.6 | 12,123 | 47.7% |
| +0.5 / +0.8 | 44 | 0.2% |

Mean 0.652s, median 0.700s, population stdev 0.050s — i.e. **one true
constant straddled by two different reporting grids** (reference ticks at
0.1s, ours at 0.08s), exactly the mechanism the spec's own §2 disclosed as
the reading of S3, not merely asserted from it. This is *why* the
cluster-bootstrap SE on the median is ~10⁻¹⁶ (effectively 0): at n=25,411,
the 52.1/47.7 split resolves to the same median in every one of 2,000
resampled draws.

### 2.3 `R`

```
R [PRIMARY]: point=+0.700s mean=+0.700s se≈0s CI95=[+0.700,+0.700]s
             p=0.0000 (n_rows=25,411 n_clusters=4,371 n_draws=2,000)
```

---

## 3. `K` — the physical-position sweep, our own archived audio

### 3.1 Mandatory sign unit test (§11 step 2, Stage 2's construction reused verbatim)

`run_stage2.run_sign_test` / `_pooled_argmin`, unmodified — exercises the
identical extraction code path the K sweep itself uses, on 20 real matched-
pair contexts loaded from **our own** `owsfz/wav/` (not the reference's, per
AO1's own K definition):

| | argmin | vs. expectation |
|---|---|---|
| baseline (`delta=0`) | `O0 = +0.65s` | — |
| `delta = +0.30s` | `O_pos = +0.35s` | expect `O0−delta=+0.35s` — **exact** |
| `delta = −0.30s` | `O_neg = +0.95s` | expect `O0−delta=+0.95s` — **exact** |

Both land exactly on the predicted grid point, opposite-sign compensating
shifts as required. **PASS.**

### 3.2 Sample and sweep, PRIMARY

Deterministic sample (seed `20260819`, same seeded/sort-stabilised procedure
as Stage 1R/Stage 2): 600 of 25,411 rows → 565 clusters. 49 dropped at
`no_true_codeword` (8.2%, same drop class every prior arm has seen) →
**n_measured=551, n_clusters_measured=519**. 49-point sweep, 551×49=26,999
extractions, **151.6s, zero extraction failures at any offset**.

Shape: chance-level (43.7–50.0%) across the entire grid except a single
sharp three-point trough at `{+0.60: 8.05%, +0.65: 6.90%, +0.70: 12.64%}`.
Full 49-row table in `results/ao1_report.json["k_primary"]["sweep_table"]`.
**At the raw reference anchor (`dt_offset=0.0`) median BER_V0 = 49.43%** —
chance, on our own archive, positive control fashion: confirms the archived
buffer does not read correctly at the reference's literal reported position,
which is exactly what a real placement offset predicts.

### 3.3 ROW 0f — the grid-step straddle (HK-021(m), flagged, not smoothed over)

| quartile | ts range | n_rows | argmin | Δ vs pooled |
|---|---|---|---|---|
| 0 | `260803_171530`…`260803_211630` | 138 | +0.65s | 0.000s |
| 1 | `260803_211800`…`260804_062145` | 138 | +0.65s | 0.000s |
| 2 | `260804_062445`…`260804_101515` | 138 | +0.65s | 0.000s |
| 3 | `260804_101545`…`260804_135445` | 137 | +0.60s | **0.050000000000000044s** |

Three of four quartiles land bit-for-bit on the pooled `+0.65s`. The fourth
(the chronologically last ~29%, ~137 rows) lands exactly one grid step away.
The bound (`0.05s`) **equals the sweep's own grid step**, so this row has no
resolving power at all between "true drift of one step" and "one quartile's
own noisier argmin, at ~140 rows instead of 551, landing on the neighbouring
point" — and the measured delta cleared the bound only by IEEE float noise on
`0.65−0.60`. Per §5's own table this is not ambiguous about its
*consequence* (Part C withheld, Part B still reports), but it is ambiguous
about what it *means*, and I am not picking a reading — reporting the
straddle as-is, per HK-021(m)'s own instruction ("state the minimum distance
the gate can resolve … or a straddle is the modal outcome").

---

## 4. Extension-corpus replication (§11 step 9 — descriptive, per corpus, never pooled)

| corpus | matched (rows/clusters) | R | K sample (measured/clusters) | K |
|---|---|---|---|---|
| `20260808_live_run_0016-8080` | 43,662 / 2,733 | +0.700s, CI95[+0.700,+0.700] | 555/508 | **+0.650s**, median BER 6.32% |
| `20260808_live_run_1154-8080-17m` | 25,437 / 1,856 | +0.700s, CI95[+0.700,+0.700] | 563/482 | **+0.650s**, median BER 6.32% |
| `20260809_live_run_0155-8080-80m` | 8,598 / 1,179 | +0.700s, CI95[+0.600,+0.700] | 578/433 | **+0.650s**, median BER 4.02% |

Both `-8081` legs excluded per spec §4 (Jaccard ~1.000 with their `-8080`
twin; `0155-80m`'s `-8081` additionally carries the G1 hardlink defect). Four
independent corpora — three days, three bands (20m/17m/80m) — **agree on the
physical offset to the sweep's own grid resolution.** This is not a PRIMARY-
corpus artefact.

Gates nothing (HK-021(k)): ROW 3 was decided on PRIMARY alone, before any of
this table was computed.

---

## 5. Part C — withheld, not run

Per §5/§7/§11: Part C runs **only if ROW 3 fired AND ROW 0f cleared.** ROW 3
fired; ROW 0f fired. Part C was **not evaluated** this round —
`run_part_c()` exists and is ready (SNR/dt standardisation, X1's `b_std`
formula reproduced locally, cluster bootstrap by `ts`, `MIN_CELL=10` reused
from X1 verbatim) but was gated off by construction, per the spec's own
consequence table, not by a compute-budget or scope decision on QA's part.

**Consequence: whether this is a D-001 treatment (C1, ≥+2.0pp recall cost at
matched SNR) or a product-only fix (C2/C3, small or no measurable cost) is
still unanswered.** §9 of the spec is explicit that ROW 3 alone does not
decide this — Part C's row does.

---

## 6. Predictions scored (§8 — nothing gated on these)

| prediction | outcome | class | result |
|---|---|---|---|
| Part B row: ROW 3, P≈0.70 | ROW 3 fired | categorical | **HIT** |
| `K` ∈ [+0.55, +0.75]s | +0.650s | range | **HIT**, dead centre |
| `\|K−R\|` ≤ 0.05s | 0.050s | range | **HIT**, exactly on the boundary |
| ROW 0f clears (quartile deviation ≤0.05s) | **FIRED** (float-boundary straddle, §3.3) | categorical | **MISS** — but see §3.3: the miss is a grid-resolution artifact, not a contradicted claim; the underlying quartile agreement (3/4 exact, 1/4 one step) is arguably closer to "clears" than "fires" |
| Part C row: C2, `L`∈[+0.2,+1.0]pp | **not evaluated** | categorical+range | **unscoreable** — Part C did not run, this is not a null result to compare against |
| Part C power: ~50/50 C0 | **not evaluated** | directional | **unscoreable**, same reason |
| `R` = +0.65s | +0.700s | 🛑 not scoreable | Architect scouted this (§2, S3) — explicitly excluded from scoring per the spec's own §8 instruction |

Per standing practice, QA scores each prediction individually and leaves the
aggregate running-tally arithmetic to the Architect's own bookkeeping.

---

## 7. What this does and does not license (§9/§10, restated per instruction)

✅ **ROW 3 fired**: a production framing defect is confirmed, and
`CycleFramer`'s realignment (`:184`, "spans the wall-clock interval
`[G, G+15]`") does not achieve its own documented intent. Route A is
promoted from open to confirmed-in-part.

✅ The offset is real, signed, consistent in direction and magnitude across
the live-path statistic (`R`) and the archive-located statistic (`K`), and
replicates across four independent corpora spanning three bands and three
days.

🛑 **Does NOT claim D-001 is explained.** Even if Part C eventually fires C1,
the largest credible recall figure in play (per the spec's own §2 naive
arithmetic, itself inadmissible) is ~2pp against a ~42pp gap — a contributing
defect at most, never the cause.

🛑 **Does NOT rehabilitate any withdrawn number.** Stage 1's `f_cross`,
the 0.0765% bound, "N5 CONFIRMED" stay uncitable.

🛑 **Does NOT reopen limb 1, R2, or N1's ROW 2.** N1's anchor was convention-
clean; unaffected either way.

🛑 **Does NOT authorise any `src/` change.** A `CycleFramer` fix is HK-011:
Developer session + Captain's sign-off, out of scope regardless of what Part
C eventually finds.

🛑 **Does NOT extend to the sub-lattice time residual** (T1's prohibition
stands — this arm measures a bulk offset ~6.5× the reference's own reporting
resolution, a different quantity by construction).

⚠️ **The D-001 treatment-vs-product-fix question is now the single most
load-bearing open item this arm created** — Part C is fully specced and
ready to run the moment ROW 0f's straddle is resolved (either by a Captain/
Architect ruling on how to read §3.3, or by a re-run with a design that does
not share this row's own resolution floor — e.g. a coarser quartile split, a
tolerance stated in whole grid steps rather than a raw float compare, or
simply re-running ROW 0f on the full 25,411-row population instead of the
551-row sample, which would very likely resolve the ambiguity outright).

---

## 8. Scope and NFR-021

No `src/`, no Developer session, no DLL rebuild, no capture run — HK-011 not
engaged. DLL re-hashed from disk immediately before arming, matches the pin
exactly (`6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`,
shim 20260042 — same pin N1/Stage 1R/Stage 2 used).

`ao1_common.py` adds a NEW parser (`parse_all_txt_with_snr`) rather than
editing the shared `c2_phase2c_ber_measurement.parse_all_txt` — every already
-reported figure that depended on that function's exact behaviour (tok[5]=dt,
tok[6]=freq; SNR previously dropped) stays untouched.

No per-row dump: every deliverable is a summary statistic, a 49-point sweep
table (no row identity), or a quartile table (counts and ts ranges only).
`results/ao1_report.json` and `results/ao1_run.log` are the only committed
outputs, both far below the `*_rows.json` class the `.gitignore` pattern
exists for.

NFR-021: message TEXT is used in-process only (`ExtractLLRs.true_codeword`,
inside `load_row_context`) and is **never** written to any row dict, JSON
field, or log line. Verified mechanically, not asserted:

```
$ grep -in "message" results/ao1_report.json results/ao1_run.log
(no output, exit code 1)
```

Both emitted files grepped individually. Zero hits.

---

## 9. Next

Per §11 step 10: **QA stops here.** No follow-on arm, no `src/` change, no
Part C re-attempt, without a ruling. Awaiting the Architect's (and/or
Captain's) direction on:

1. **How to read ROW 0f's grid-step-exact straddle (§3.3)** — whether it
   licenses a targeted re-run (e.g. ROW 0f evaluated on the full population,
   or restated as a whole-grid-step tolerance) to unblock Part C, or whether
   it stands as reported and Part C waits for its own pre-registration.
2. Whether Route A's promotion to "confirmed-in-part" (ROW 3, this round)
   changes the D-001 route-probability ledger (`2026-08-18-1902-…-ledger-
   and-route-probabilities.md`, §10 item 1, now discharged by this arm) ahead
   of Part C's own answer to the treatment-vs-product-fix question.
3. GitHub issue #3 / #111 cross-reference update — not yet done this round,
   folding in on instruction or alongside the ruling.
