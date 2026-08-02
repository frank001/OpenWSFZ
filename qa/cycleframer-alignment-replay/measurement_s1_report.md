# Arm S.1 -- spectral locality, segment 1 result (D-001)

Spec: `2026-07-31-1649-architect-arm-s1-spec-rev3-segment-1-execution-ready.md`, quoted verbatim throughout. Corpus: `artefacts/20260729_live_run_1831-8081/owsfz/20m`, restricted to segment 1 (< 2026-07-30 00:00:00). Prerequisite (drift screen, segment 1) cleared: `2026-07-31-1719-qa-drift-screen-8081-20m-per-segment-result.md` (peak drift 0.136s vs the 0.5s bar).

**Cutoff reproduction check:** `stratify_cycles` on segment 1 gives q1=23.0, q3=41.0; spec pre-registers sparse<=23, dense>=41. **MATCH**

## Self-check 1 -- matching gate

Segment 1 total matched: **9751** (expected **9751**). **PASS**

## Self-check 2 -- density contrast

176 sparse cycles (mean 18.47/cyc), 159 dense cycles (mean 48.86/cyc). Contrast **2.65x** (bar >= 2.0x, expected 2.65x). **PASS**

## Self-check 2b -- locality contrast (W=50)

| stratum | mean n_local(lo) | mean n_local(hi) | contrast (hi-lo) | verdict |
|---|---:|---:|---:|---|
| sparse | 0.000 | 1.376 | 1.376 | PASS |
| dense | 0.650 | 2.420 | 1.770 | PASS |

**PASS** -- gap >= 1.0 required in BOTH strata.

## Self-check 6 -- cut reproduction (W=50)

| stratum | lo (computed) | hi (computed) | lo (expected) | hi (expected) | verdict |
|---|---:|---:|---:|---:|---|
| sparse | 1620 | 1631 | 1620 | 1631 | PASS |
| dense | 4359 | 3410 | 4359 | 3410 | PASS |

**PASS**

## Self-check 3 -- common support

Usable SNR bins (n>=20 in all four cells): **18** (bar >= 10, expected 18). **PASS**

## Self-check 4 -- duplicate-key confound

Interpretation used (the spec states the principle -- gap must be < 1/10 of the effect it could confound -- but this arm has two effects, not one, so the gap is checked against each of the two it could plausibly confound):

| cell pair | dup-key rate gap (pts) | vs |1/10 x relevant effect| | confounded? |
|---|---:|---:|---|
| local axis (hi vs lo, worst of sparse/dense) | 0.000 | 2.922 | no |
| cycle axis (dense vs sparse, worst of lo/hi) | 0.000 | 2.690 | no |

**PASS**

## Self-check 5 -- temporal composition

Satisfied by construction: segment 1 is a single contiguous session (2026-07-29 18:31:30 -> 21:14:30), stated explicitly per the spec rather than silently omitted. **PASS**

**All six self-checks pass.**

## Mandatory null (Sec5) -- 20 within-cycle freq_hz shuffles, seed 20260731

| run | Delta_local (pts) |
|---:|---:|
| 0 | +2.314 |
| 1 | +3.004 |
| 2 | +3.966 |
| 3 | +1.644 |
| 4 | +2.466 |
| 5 | +3.152 |
| 6 | +1.960 |
| 7 | +0.435 |
| 8 | +4.090 |
| 9 | +2.812 |
| 10 | +1.709 |
| 11 | +3.177 |
| 12 | +1.159 |
| 13 | +2.189 |
| 14 | +1.099 |
| 15 | +2.222 |
| 16 | +2.983 |
| 17 | +4.048 |
| 18 | +1.926 |
| 19 | +2.284 |

**Mean: +2.432 pts. Stdev: 0.992 pts (n=20/20).** Bar: mean within +-2.0 pts of zero. **FAIL -- ARM IS VOID**

The locality metric is measuring something structural about how frequencies are distributed. Reporting the null failure, not the arm's result, per Sec5.

