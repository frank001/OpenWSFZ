# QA → Architect: C-GAP-D results — ROW 1 FIRES, replicated across all 3 bands and both legs

**2026-08-22 19:55Z.** Spec: `qa/rr-study/2026-08-22-1902-architect-to-qa-spec-c-gap-d-
extraction-headroom-decomposition.md`. No `src`/`native` change, no capture, no hardware
(HK-011 not implicated) — pure re-analysis of ALL.TXT already on disk via X1's own
`build_band()`/`load_band_raw()`, imported and called unmodified (HK-018).

Harness: `qa/cycleframer-alignment-replay/c_gap_d_extraction_headroom.py` (new). Raw
output: `qa/cycleframer-alignment-replay/results/20260822_195448Z-c_gap_d_report.json`
(N14-compliant filename, timestamp-derived, nothing to overwrite).

## 0. Summary

**ROW 1 FIRES on the primary (20m, leg `8080`): `CI_hi(G(3)_pp) = 7.172 < 10.0`.**
**Extraction quality is not the route.** Even a perfect 3 dB coherent-combining gain —
Route B2's whole remaining theoretical ceiling — closes at most ~7.2 pp of the 43.8 pp
gap, under a quarter of it. Per the pre-registered consequence, Route B2's remaining
limb may not be described as a D-001 treatment in any subsequent proposal, and Phase C
is **not authorised on gap-closing grounds.**

**This replicates cleanly.** All three bands, both legs — six independent point
estimates — land inside `[4.66, 7.17]` pp for `G(3)_pp`, every single CI upper bound
well clear of the 10 pp bar and nowhere near the 25 pp bar. The point estimate on the
disclosed leg/band (20m/`8080`, `G(3)_pp = 6.995`) matches the Architect's own
exploratory number (7.00) to three decimals — the drafting-time finding was not an
artefact of the single-leg/single-band population; the recall curve reproduces the
disclosed table exactly (spot-checked at all nine points, e.g. `R(-21)=0.210`,
`R(19)=0.930`).

**Part B corroborates the second finding: a majority of the "near" excess is
hash-unresolved text, not a decode failure.** Pooled over all six band-legs, of 2,052
misses classified (near, reference SNR ≥ 0 dB): **T1 (our text carries an unresolved
`<...>` hash the reference's doesn't) = 1,544 (75.2%)**, T3 (a callsign character
differs) = 474 (23.1%), T4 (other) = 34 (1.7%), **T2 (identical callsigns, differing
report/suffix) = 0**. This is descriptive by design (no gate) but it is a strong,
consistent signal: the dominant near-miss failure mode is hash-table text loss, exactly
the mechanism the board's standing note already named.

## 1. ROW 0 — validity

| row | check | 20m | 17m | 80m |
|---|---|---|---|---|
| 0a | `n_ref_clean` reproduces X1's committed value | **PASS** (67,243 = 67,243) | **PASS** (38,047 = 38,047) | not gated — no committed baseline exists in `x1_cross_band_decomposition.py` for 80m; reported only: 10,839 |
| 0b | legs agree within 5 pp | **PASS** (Δ=0.134 pp) | **PASS** (Δ=0.071 pp) | **PASS** (Δ=0.074 pp) |
| 0c | `R(s)` monotone after isotonic smoothing | **FLAG** (max violation 0.058/0.059, both legs — `>0.05`, per spec "flag and continue, do not stop") | pass (max 0.028) | pass (max 0.045) |
| 0d | determinism, mechanically diffed | **PASS — two independent full runs are byte-identical** (`json.dumps(..., sort_keys=True)` string equality, not asserted) | | |
| 0e | cluster floor (≥200 clusters, ≥5,000 rows) | **PASS** (2,529 cyc / 67,243 rows) | **PASS** (1,835 / 38,047) | **PASS** (1,196 / 10,839) |

No ROW 0 row fired in the STOP sense (0c is a flag-and-continue, not a stop, per its own
row definition). **The arm is valid; ROW 1-4 may be read.**

**0c's flag, read honestly:** the isotonic violation on 20m (~0.058) sits just over the
0.05 flag threshold, both legs, identically in each — consistent with real sampling
noise on a genuinely near-monotone but not perfectly smooth curve (a handful of adjacent
SNR bins swap order by a few points of `n`) rather than a structural problem; 17m and
80m are comfortably under. Flagged per spec, not treated as invalidating.

## 2. Resolvable distance (Sec.5.2)

Spec predicted a half-width of order 0.5–1.0 pp for ~2,500 clusters on a pp-scale
proportion, with an escalate bar at 2.0 pp. **Achieved half-width on the primary gate:
0.137 pp** — better than predicted, and nowhere near the escalate bar. ROW 4 is not
triggered by underpowering; the CI is decisive.

## 3. Part A — `G(Δ)_pp`, every band/leg

| band | leg | N_ref | Δ=1 | Δ=2 | **Δ=3** | Δ=6 | Δ=10 |
|---|---|---|---|---|---|---|---|
| 20m | 8080 | 67,243 | 2.51 [2.47, 2.73] | 4.75 [4.70, 4.95] | **6.995 [6.897, 7.172]** | 13.43 [13.21, 13.67] | 20.74 [20.36, 21.08] |
| 20m | 8081 | 67,243 | 2.49 [2.45, 2.71] | 4.73 [4.67, 4.92] | 6.96 [6.86, 7.14] | 13.36 [13.14, 13.61] | 20.65 [20.28, 21.01] |
| 17m | 8080 | 38,047 | 2.10 [2.14, 2.59] | 3.90 [3.86, 4.20] | 5.57 [5.46, 5.80] | 10.53 [10.29, 10.83] | 15.85 [15.46, 16.26] |
| 17m | 8081 | 38,047 | 2.09 [2.14, 2.57] | 3.90 [3.84, 4.19] | 5.56 [5.44, 5.79] | 10.52 [10.27, 10.80] | 15.83 [15.42, 16.22] |
| 80m | 8080 | 10,839 | 2.40 [2.37, 3.28] | 3.49 [3.49, 4.15] | 4.71 [4.69, 5.38] | 8.45 [8.16, 9.02] | 12.32 [11.77, 12.98] |
| 80m | 8081 | 10,839 | 2.37 [2.36, 3.24] | 3.49 [3.50, 4.14] | 4.68 [4.66, 5.36] | 8.36 [8.07, 8.93] | 12.20 [11.67, 12.85] |

(point [CI95lo, CI95hi], pp of that band's own reference population; cluster bootstrap
by `ts`, 2,000 draws, seed `20260822`.) **Every single `G(3)_pp` CI upper bound is under
7.2 — nowhere near the 10 pp ROW 1 bar, let alone the 25 pp ROW 3 bar.** The gap does
not close linearly with band size either (80m's point estimate is lower than 20m's,
despite 80m having a smaller, potentially less-representative population) — there is no
band where a plausible extraction gain reaches materially higher than the primary.

**Reading the assumption (Sec.3.2) straight: `G` is an upper bound, by construction —
it credits Δ dB of extraction with recoveries the population at `s+Δ` owes to every
other failure mode too.** A low `G` is therefore decisive in exactly the direction this
result points: extraction cannot be doing more than this, and it is doing far less than
a quarter of the gap.

## 4. Part B — the excess-over-null (descriptive, no gate)

**Pooled excess (near_rate − null_rate, shift=700 Hz), all six band-legs:**

| band | leg | n_miss | near_pooled | excess (700Hz) | CI95 | excess (1300Hz) |
|---|---|---|---|---|---|---|
| 20m | 8080 | 29,464 | 0.118 | 0.047 | [0.042, 0.051] | 0.058 |
| 20m | 8081 | 29,374 | 0.115 | 0.045 | [0.040, 0.050] | 0.055 |
| 17m | 8080 | 13,667 | 0.087 | 0.034 | [0.027, 0.040] | 0.034 |
| 17m | 8081 | 13,694 | 0.089 | 0.036 | [0.030, 0.042] | 0.037 |
| 80m | 8080 | 2,483 | 0.166 | 0.128 | [0.113, 0.145] | 0.131 |
| 80m | 8081 | 2,475 | 0.164 | 0.127 | [0.111, 0.145] | 0.129 |

Every band-leg's excess CI excludes zero — a real, positive, SNR-independent
"we-decoded-this" signature survives the null control everywhere, largest on 80m (a
smaller, higher-density-per-cycle population where the same absolute miss count is a
bigger fraction).

**Shift-sensitivity (spec's own honesty check): fires on every band-leg** — the 700 Hz
and 1300 Hz nulls differ by >0.02 in at least one 5 dB bin. Per spec, Part B is
therefore **treated as descriptive only** (it already carried no gate). Read plainly,
this sensitivity concentrates almost entirely in the sparsest high-SNR bins (20m/8080:
the +20 and +25 dB bins swing 0.17 and 0.33 between shifts on a handful of remaining
misses each; every bin from −25 through +15 dB — where the bulk of the 29,464 misses
actually sit — differs by ≤0.066 between the two shifts, most well under 0.02). The
pooled figure and the low/mid-SNR bins are stable; the instability is a small-`n` tail
effect, not a sign the whole excess is a null-control artefact. Recommend, if this
descriptive figure is ever load-bearing for a future decision, either a wider null-shift
sweep (more than 2 shifts) or restricting the reported bins to those with adequate `n`
before citing.

**Classification of the excess (misses flagged `near` at reference SNR ≥ 0 dB), pooled
across all six band-legs, counts only — no message text retained or logged, NFR-021:**

| type | count | share |
|---|---|---|
| T1 — our text carries an unresolved hash where the reference's doesn't | 1,544 | 75.2% |
| T2 — identical callsigns, differing report/suffix | 0 | 0.0% |
| T3 — a callsign character differs | 474 | 23.1% |
| T4 — anything else | 34 | 1.7% |

Classification method (stated per spec's own descriptive framing, not a gate): the
message's final whitespace token is treated as the variable exchange field (report,
`RR73`/`73`, or grid) in both CQ and directed forms; every token before it is the
"callsign part." T1 checks for an unresolved `<...>` token; T2 requires an identical
callsign part with a differing final token; T3 requires an equal-length, non-identical
callsign part. This is a heuristic, not a parser — it is adequate for a three-quarters-
versus-one-quarter split, not for a claim finer than that.

**T1's dominance (three in four) is a strong, independent corroboration of the board's
standing note** that hash-table saturation costs message TEXT only, not the decode
itself — this is exactly that failure mode's signature, appearing at the volume the
note predicted, on a population three bands wide.

## 5. Gate verdict

| | |
|---|---|
| Band / leg | 20m / `8080` (primary, per spec Sec.5) |
| `G(3)_pp` | 6.995, CI95 `[6.897, 7.172]` |
| Bar | ROW 1: `CI_hi < 10.0` |
| **Row** | **ROW 1 FIRES** |

**Consequence, as pre-registered:** extraction is not the route. Even a perfect 3 dB
extraction gain closes under a quarter of D-001. Route B2's remaining limb (the
coherent-LLR work `r2-coherent-llr-instrument` was built to validate) **may not be
described as a D-001 treatment** in any subsequent proposal. Phase C is **not
authorised on gap-closing grounds.** D-001's dominant term is elsewhere and naming it is
the project's next question — Part B's T1 result (§4) is a candidate for a piece of
that term (message-text loss under hash-table saturation), but it is descriptive, not
gated, and does not itself authorise anything.

**This does NOT call Route B2 dead** (per spec §7) — ROW 1 is a statement about
magnitude, not about whether the coherent path works. It also does not reopen ROW 0g or
`tasks.md` §4.3 (still VOID, `r2-coherent-llr-instrument` now archived on that basis,
this session, separately).

## 6. What this changes for C-FREQ-A

C-FREQ-A (`qa/rr-study/2026-08-22-1903-...md`) was explicitly **GATED behind C-GAP-D**
and, per the Architect's own §0 disclosure in that spec, **demoted in advance** to
"Route-B2 closure only" the moment C-GAP-D's ROW 1 fired — which it has. Whether to fund
C-FREQ-A on that reduced basis (a Route-B2-closure question, not a D-001-closure
question) is the Captain's call, not decided by this result.

## 7. Handover

Per spec §8: QA has run §3, §4, §5; reported; **stops here.** No push, no merge, no
`pre_merge_check.py` (HK-014/HK-010/HK-006). New harness commit is docs/qa-tooling only,
staged locally, not yet committed pending Captain review of this report.
