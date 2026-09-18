# `DENSITY-LIVE` — result: **ROW 1 CONCENTRATES**, `D(EXPOSED,PL) = 0.7293` (CI `[0.701, 0.754]`), well clear of the `0.170` bar — `C ≈ 4.30 pp`

QA, 2026-09-18 13:48Z (`date -u`, HK-017). Per spec
`2026-09-18-1339-architect-to-qa-spec-density-live-concentration.md`, `arch/density` `517db622`,
dispatched on Captain authority (density; spectral-locality gate cleared for **this one confirmatory
test only** — spec §0). No `src/`/`native/` change, no station time, no new capture.

**Headline: ROW 0 is silent (0a/0b/0c all PASS) and the primary contrast fires ROW 1.** Live misses
concentrate in the bench-proven near-neighbour geometry, by a wide margin: `D(EXPOSED,PL) = 0.7293`,
95% CI `[0.7010, 0.7540]` — the CI's *lower* limit alone (`0.701`) is more than 4× the `0.170` bar.
Attributable cost `C = D × n_EXPOSED / 91,046 ≈ 4.30 pp` of decode rate (spec's own worked example:
`D=0.170 ⇔ C=1.0pp`). **Density becomes the programme's main line** per spec §7's pre-registered
sequence; the M1/M2 mechanism arm is next, gated on its own shim-feasibility ROW 0.

---

## 1. HK-020 — critical config (checked against spec §1/§2, not inherited from a header)

| config | value |
|---|---|
| Corpus | **C2**, `artefacts/20260908_live_run_1827-fp-floor-live-2/`. `live-gap-now/corpus.c2_cycles()` verbatim: `cycle_start_utc >= 2026-09-08T19:36:45Z`, dial `14.074`, `*_2.wav` excluded |
| REF | `live-gap-now/analyse.load_ref_c2()` verbatim — WSJT-X FT991A `ALL.TXT`, A-only, restricted to replayed cycles. **91,046 rows** |
| TEST | `live-gap-now/analyse.load_live_c2_openwsfz()` verbatim — OpenWSFZ **live** `ALL.TXT`, same restriction. **57,969 rows.** Live logs only, no replay (spec §1: "a raw-C-ABI replay is not the live path") |
| Population | REF rows with SNR ≥ −10 dB: **60,239** (matches spec §1 exactly) |
| Matcher | `live-gap-now/matcher.recovery()` verbatim (H1's `R_wild` code path) |
| Bootstrap | own script, spec §3's method: resample **distinct REF integer frequencies** with replacement, `N=2000`, seed **`20260918`** (distinct from `live-gap-now`'s own `20260912`), paired — one resample per draw serves every contrast computed on it |
| Qualifiers carried on every number below | binary `6b2e16a6…` (shim `20260050`), `nhard=60`, pre-`PASSBAND-140`, 20 m, 2026-09-08/09, REF = WSJT-X FT991A alone. Not pooled with post-2026-09-12 (`nhard=40`) data |

New code: `qa/rr-study/density-live/density_live.py`. Reused verbatim (spec §6 item 1, HK-018):
`live-gap-now/{corpus.py,matcher.py,analyse.py}` (`load_ref_c2`, `load_live_c2_openwsfz`,
`recovery`). Wall time: **44 s** (classification + TEST load + 4× 2000-draw bootstrap, single
process, no station involvement).

## 2. Deliverable 1 — REF-only class table, before any TEST load

Spec §6 item 1's hard gate, run **before** `load_live_c2_openwsfz()` is called anywhere in the
process (checked by reading the script top to bottom, not merely by variable-naming discipline):

| class | got | spec §2.1 |
|---|---:|---:|
| EXPOSED | 5,363 | 5,363 |
| PL | 7,476 | 7,476 |
| PF | 10,781 | 10,781 |
| TRANSITION | 7,429 | 7,429 |
| CLEAR | 28,310 | 28,310 |
| GAP (excl.) | 598 | 598 |
| PL_TRANS_STRONG (excl.) | 282 | 282 |
| **total** | **60,239** | **60,239** |

**Exact match, every class, on the first run.** The classifier is correct before TEST touches it.

## 3. ROW 0 (strict order, either fires ⇒ STOP)

| row | predicate | result |
|---|---|---|
| **0a — placebo null** | 95% CI of `D(PL,PF)` inside `[−0.05,+0.05]` | **PASS.** `D=0.0272`, CI95 `[0.0095, 0.0451]` — comfortably inside, and the CI itself doesn't even reach the bar |
| **0b — coverage** | standardisation drops ≤5% of EXPOSED rows, and of `PL` rows in 0a | **PASS.** `0/5,363` EXPOSED dropped, `0/7,476` `PL` dropped — no 1 dB cell fell below `n=20` on either side of either contrast |
| **0c — reproduction** | pooled `R_wild` over all 91,046 REF rows = `61.09%` (2 dp) | **PASS, exactly.** `61.0856% → 61.09` |

**ROW 0 is silent.** The primary contrast can be read.

## 4. Primary — `D(EXPOSED, PL)`

```
D(EXPOSED, PL) = 0.7293
95% CI = [0.7010, 0.7540]   (n_freq resampled = 1,835)
bar    = 0.170  (= 1.0 pp attributable cost, spec's anchor)
C      = D x n_EXPOSED / 91,046 x 100 = 4.296 pp
```

**CI_lo (0.7010) ≥ 0.170 ⇒ ROW 1 CONCENTRATES.** Not a marginal read: the entire CI sits above
**4×** the bar. Per spec §4.2's own reachability check, `D` at complete live exclusion would land
near `PL`'s own recovery (~0.75–0.83); the measured `0.7293` is close to that ceiling, i.e. **the
bench's 0/100 exclusion is close to fully realised live**, not merely "detectable."

Raw recovery, for scale: **EXPOSED 5.18%** (n=5,363) vs **PL 83.23%** (n=7,476), vs **PF 80.83%**
(n=10,781, the other clean class ROW 0a validates as comparable to PL).

## 5. §4.3 — reporting only (gates nothing, changes no row)

**Per-class recovery, pooled:**

| class | n | recovery |
|---|---:|---:|
| EXPOSED | 5,363 | 5.18% |
| GAP (excl.) | 598 | 36.96% |
| PL | 7,476 | 83.23% |
| PL_TRANS_STRONG (excl.) | 282 | 17.02% |
| TRANSITION | 7,429 | 57.24% |
| PF | 10,781 | 80.83% |
| CLEAR | 28,310 | 85.30% |

**`D(EXPOSED,PL)` per 5 dB band** (🛑 not read against `0.170` — the bar belongs to the pooled,
standardised figure, HK-021(y)): `−10…−6: 0.674` · `−5…−1: 0.731` · `0…4: 0.760` · `5…9: 0.786` ·
`≥10: 0.844`. **Monotonically increasing with SNR** — the exclusion, where it holds, holds more
completely on stronger signals, not less; there is no band where the effect collapses.

**`D(TRANSITION,PF)` = 0.2668**, CI95 `[0.2377, 0.2950]` — graded-zone check, not a gate. Consistent
with the bench's partial-effect prediction (27/100→98/100 across the transition zone): a real but
much smaller penalty than the full-exclusion `EXPOSED` class.

**`D(EXPOSED,PF)` = 0.7590**, CI95 `[0.7377, 0.7785]` — for completeness, close to `D(EXPOSED,PL)`
as expected since ROW 0a already establishes `PL` and `PF` read alike.

**EXPOSED recovery split by `rel`:** `rel==0` (n=241): **32.37%**. `rel≥+1` (n=5,122): **3.90%**.
The C3 knife-edge (bench: exactly-equal level) is visible live too — an equal-level neighbour still
lets roughly a third through, while any stronger neighbour crushes recovery to under 4%.

**Counts:** GAP (excluded) = 598. PL_TRANS_STRONG (excluded) = 282. Ambiguous wildcard matches:
8/1,540 wildcard gains pooled (`ambiguous_frac` = 0.52%) — small, reported per spec, not chased.

**None of the above is cited as a mechanism finding or as evidence about diffuse crowding** (spec
§4.3's own instruction; §0's clearance covers this one geometry-fixed test only).

## 6. What this can't see (spec §5, not re-litigated, just checked it still applies as written)

Undecoded-neighbour blind spot (§5.1) dilutes `D` **toward zero**, i.e. the unsafe direction is
against ROW 1 — the measured effect clearing the bar by 4× makes that dilution risk moot for this
verdict's direction, though it means the true effect could be even larger than `0.7293`, not
smaller. WSJT-X SNR-under-overlap estimation error (§5.2) is exactly what the 2 dB GAP guard band
and ROW 0a's clean read bound. C2-only, one band, superseded binary (§5.4) still apply — this is a
live-concentration read on that one corpus, not a current-binary recovery figure (that's `A1`,
unchanged at 61.09%, elsewhere).

## 7. Predictions (spec §8) — reported, not self-scored (Architect/Captain score at ruling time)

| # | prediction | called | actual |
|---|---|---|---|
| 1 | ROW 0a passes | 0.65 | **passed** (`D=0.027`, well inside ±0.05) |
| 2 | Verdict is ROW 1 | 0.60 | **ROW 1** |
| 3 | Point `D` in 0.25–0.55 | 0.45 | **0.7293 — outside the called range, on the high side** |
| 4 | §2.1 table reproduces exactly | 0.95 | **exact, first run** (§2 above) |

Flagging #3 plainly rather than letting it pass quietly: the verdict called (ROW 1) landed, but the
point estimate landed well above the predicted band, not inside it. Worth weighing alongside the
ledger's standing note that HYPOTHESISED calls run biased toward over-predicting effect size in the
findable-defect direction — here the direction was right and the magnitude was still underestimated,
which doesn't fit that bias cleanly and may be worth a line in the ledger at ruling time.

## 8. NFR-021

Classifier reads numeric fields only (`snr`, `freq_hz`); message text is touched only inside
`matcher.load_all()`/`recovery()` (already-audited verbatim reuse) and never re-emitted. `scan()`/
`classify()` (`qa/rr-study/nfr021_pre_merge_scan.py`) run clean against
`results/density_live_result.json` and this report — zero flagged tokens.

## 9. Where this leaves the arm (spec §7)

**ROW 1 → density is the programme's main line.** Per the pre-registered sequence: the M1 (tone
contention) vs M2 (tile artefact) mechanism arm is next, on a continuous metric (LLR BER vs truth),
with shim feasibility as its own ROW 0 — that spec needs the Captain's go before I start it.
🛑 **This result establishes concentration, not mechanism, and licenses no fix** (spec §5.5) — same
discipline as the bench assessment it confirms.

## 10. Artefacts

Committed by path (HK-014/HK-033 — **not pushed**, Captain's go needed): `qa/rr-study/density-live/`
(`density_live.py`, `results/density_live_result.json`), this report. Branch: `qa/e4-bench` (current
worktree branch; will move to its own branch name if the Captain wants it split out before push).
No `artefacts/` gitignored output beyond what's already on disk for C2 (no new capture, no new
run).
