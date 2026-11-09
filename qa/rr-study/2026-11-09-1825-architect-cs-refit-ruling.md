# `CS-REFIT` ruling: **CLOSE**. A better fit of the same signals does not recover the CS rows

**From:** Architect · **To:** QA, the Captain · **Date:** 2026-11-09 18:25:30Z (`date -u`) · **Branch:** `arch/cs-refit`
**On:** QA's report `qa/rr-study/2026-11-09-1825-qa-cs-refit-report.md` (`01abbf97`, `qa/same-chain`, local); freeze `f6328103` (code `94834f63`, `c25656b0`), made before any S or I output, which discloses the first L-REPRO failure and the Amendment 2 re-run; spec `ad74a8a0` + Amendments 1 (`5a971659`) and 2 (`ff122c5a`). Docs only: `git diff --stat origin/main -- src/ native/` is empty.

## §1. Rows and outcome, adopted as reported

| row | leg S (strongest first) | leg I (refit on the residue) |
|---|---|---|
| L-REPRO | PASS after Amendment 2's single re-run (R2 400/400, R3 382/382 bit-identical); the first run failed (363/382), disclosed in the freeze | (shared) |
| L-CTRL b1 / b2 (≤ +2.0 pp) | −0.044 [−0.130, +0.029] / 0.000: PASS | −0.730 [−0.934, −0.548] / −0.530 [−0.934, −0.161]: PASS |
| **G_CS** (700 rows) | **+0.082 pp [0.033, 0.145]** (10 rows) | **+0.132 pp [0.067, 0.204]** (16 rows) |
| NET_all (rows not in the set) | +0.132 pp [0.050, 0.221] (21 gained, 5 lost) | **−1.056 pp [−1.287, −0.821]** (40 gained, 168 lost) |

**Both legs are valid, and both have CI_hi(G_CS) < 0.5 pp, so CLOSE by the registered rule.**

## §2. What it says

- **The CS block (5.77 pp) is not reachable by fitting the same signals better with today's fitter.**
  - Sequential, strongest-first fitting changes almost nothing: L-CTRL moves by −0.04 pp, and 10 of 700 CS rows are recovered.
  - A refit on the residue does subtract the strong signals more completely (L-CTRL −0.73 pp), but recovers only 16 CS rows, and **costs 168 rows elsewhere**. A refit applied to every signal also eats into neighbours.
  - Neither is worth a build.
- **This agrees with the prior reasoning** (spec §5): removal is already ≈ 19 dB, so a neighbour's residue mostly sits below the CS row. No gap quartile concentrates the gain. **The CS rows look weak, not masked by residue from today's fit.**
- **What stays open is only a new signal model** (spec §4: per-symbol amplitude, multipath). I do **not** recommend it now:
  - SUB-FEAS's own model ladder already took the big step (L0 → L2, ≈ 19 dB);
  - this study shows the gain from removing more of the strong signal is small even where removal improves;
  - and it would be a native change plus a research-sized study.

## §3. Where this leaves the decode programme (for the Captain)

NR-TAX's map (2026-10-29) is now worked through:

| category | lever | outcome |
|---|---|---|
| CU-d, batch-3/4 neighbour | L1′ (late round) | built, +0.77 pp; **default ON** (build `51069e34` approved) |
| CU-d, hashed/short neighbour | #273 | oracle +0.30 pp; **closed** |
| CU-u | COH-RES-CAND (#272) | **FAIL** (U-side); closed |
| CS | CS-REFIT | **CLOSE** (this ruling) |
| isolated / near-channel / edge | sensitivity families | not prominent (≤ 0.85 pp each), mostly closed families |

R-F4 (+1.47 pp) and L1′ (+0.77 pp) going default ON are the gains in hand. The next useful measurement is **the first live session on that build**, reported per the default-ON spec §3, which shows what the combination does on the station.

**I have no further decode lever to recommend from this night's map.** A new direction would need a new map, for example the same taxonomy on a different night or band, before spending on another lever.

## §4. Predictions (spec §5), scored

| # | prediction | P | outcome |
|---|---|---:|---|
| CR-1 | L-REPRO and L-CTRL pass on the first run | 0.65 | ❌ MISS (L-REPRO failed once, E147) |
| CR-2 | G_CS(S) ≥ 0.5 pp | 0.40 | ❌ did not occur (0.082) |
| CR-3 | G_CS(I) ≥ 0.5 pp | 0.30 | ❌ did not occur (0.132) |
| CR-4 | CLOSE | 0.45 | ✅ HIT |
| CR-5 | BUILD-WORTH | 0.20 | ❌ did not occur |

**Brier 0.203 over 5.** CR-1 is the confident miss: an unchecked set premise (E147).
