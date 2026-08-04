# QA → Architect — Task 3 result: candidate budget PARTIALLY saturated, dense-regime only

**Author:** QA, 2026-08-04 (15:45 UTC, `date -u`, per HK-017).
**Executes:** `qa/rr-study/2026-08-04-1500-architect-to-qa-spec-false-positive-surge-and-window4-closure.md`
Sec.5.
**Verdict: ROW 3 — PARTIAL.**

---

## Step 1 — counts were already in the gathered log

`artefacts/20260803_live_run_1713/owsfz/openswfz-20260803T185914Z.log` (the decisive epoch's own
process log, 18.96 h, one process instance = one epoch by construction) carries LDPC candidate
counts at `[DBG]` level, one pair of lines per processed cycle:

```
Iterative subtraction: pass 1 of 2, 140 candidates found, 20 decoded.
Iterative subtraction: pass 2 of 2, 200 candidates found, 1 decoded.
```

"pass 1 of 2" = pass-0 (`K_MAX_CANDIDATES = 140`), "pass 2 of 2" = pass-1
(`K_MAX_CANDIDATES_PASS2 = 200`). No replay needed.

## Step 2 — counts

Reconstructed by sequential pairing (no timestamp label in these DBG lines): **4,552 cycles**, all
carrying both pass-0 and pass-1 counts — clear of the 500-cycle floor.

```
sat_0 (pass-0 candidates == 140): 2083/4552 = 0.4576
sat_1 (pass-1 candidates == 200): 1489/4552 = 0.3271
pass-0 candidate distribution: min=0 median=133 max=140 mean=102.5
```

## Pre-registered rule evaluation

`0.10 <= sat_0 (0.4576) < 0.50` -> **ROW 3 — PARTIAL.** Rivalrous in the dense regime only.

## sat_0 stratified by decodes/cycle (required by ROW 3)

| decoded/cycle | n | sat_0 |
|---:|---:|---:|
| 0–7 | 1,202 | 0.0000 |
| 8 | 100 | 0.0100 |
| 9 | 124 | 0.0323 |
| 10 | 141 | 0.0567 |
| 11 | 162 | 0.0988 |
| 12 | 176 | 0.0909 |
| 13 | 180 | 0.2167 |
| 14 | 227 | 0.4317 |
| 15 | 265 | 0.5698 |
| 16 | 291 | 0.6735 |
| 17 | 299 | 0.8194 |
| 18 | 284 | 0.8627 |
| 19 | 296 | 0.9257 |
| 20 | 232 | 0.9612 |
| 21 | 200 | 0.9700 |
| >=22 | 373 | 1.0000 |

**This is a clean, monotone transition, not noise.** Saturation is essentially zero below 8
decodes/cycle and essentially total above 22 — the budget only binds in the dense part of the
distribution, which is exactly where a rivalry mechanism (a false candidate displacing a real one)
would be expected to bite hardest, since that's where the top-140-by-score cut is closest to the
signal population.

Instrument: `qa/rr-study/candidate_saturation_check.py` (committed `85a71f3` before running, per
HK-021).

## What this does and does not establish

Per Sec.1 and the standing constraints: this measures **saturation**, not **false positives**. A
saturated slot means *some* candidate below the top-140 by sync score was discarded; it does not
distinguish whether the discarded candidate or the retained one was the false one, and there is no
oracle here (Sec.3's standing constraint applies). It is consistent with, and does not refute, the
hypothesis in Sec.1 (drift previously suppressed both populations' scores, acting as an accidental
FP filter; `be5960a` restored them). **Sec.1's hypothesis stands; Task 3 does not kill it (ROW 4 did
not fire).**

Per Sec.5's own scope limit, **no cap change or gate re-tuning is proposed here.** If the Captain
wants the candidate-cap sweep priced, that is `dev-tasks/2026-07-26-d001-candidate-cap-sweep.md`,
Developer work under HK-011.
