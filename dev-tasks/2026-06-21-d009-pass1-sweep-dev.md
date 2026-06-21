# D-009 — Developer Handoff: Pass-1 `min_score` Trade-Curve Sweep

**Date:** 2026-06-21
**Raised by:** Architect (B2 escalation, `2026-06-21-d009-b2-escalation-captain.md` §4a)
**Defect ID:** D-009 — OSD false-positive manufacture in noise
**Type:** **Measurement only.** Produce a trade curve. **Do NOT pick a value, ship a
binary, or implement a fix.** The Captain selects the operating point from the curve.

---

## 1. Context (read first)

The R6 diagnostic (`qa/rr-study/results/diag-nhard-2026-06-20/`) proved that OSD
false positives and genuine co-channel decodes are statistically identical on every
cheap signal-level axis (nhard, sync, corr/norm). Both originate in **pass 1** — the
spectrogram-suppressed SIC residual pass, which admits very weak candidates
(`K_MIN_SCORE_PASS2 = 1`) so OSD can dig out co-channel signals. That same low floor
is what lets noise reach OSD and be hallucinated into valid callsigns.

`K_MIN_SCORE_PASS2` is therefore the single dial that trades **co-channel
sensitivity** (D-001 gain) against **noise false-positive rate** (D-009). This task
measures that trade at several settings so the Captain can choose an operating point
with numbers in hand.

**No threshold is chosen here.** You produce a table; the architect/Captain decide.

---

## 2. Branch

```
fix/d009-fp-callsign-filter
```

Continue on the existing branch. Each sweep point is a **local rebuild for
measurement** — do **not** commit any of the swept binaries. The committed win-x64
DLL stays at shim 20260028.

---

## 3. Actions

### Action 1 — Sweep points

The knob is in `src/OpenWSFZ.Ft8/Native/ft8_shim.c`:

```c
#define K_MIN_SCORE_PASS2       1     /* ← sweep this */
#define K_MAX_CANDIDATES_PASS2  200
#define K_LDPC_ITERATIONS_PASS2 50
```

Measure these `K_MIN_SCORE_PASS2` values (5 points):

| Point | `K_MIN_SCORE_PASS2` | Rationale |
|---|---|---|
| P0 (baseline) | **1** | current shipped behaviour — the FP factory |
| P1 | **3** | |
| P2 | **5** | |
| P3 | **7** | low end of the observed surviving-candidate sync band |
| P4 | **10** | equal to pass-0 floor (`K_MIN_SCORE`) — pass-1 admits only strong candidates |

For each point: edit the one `#define`, rebuild **win-x64 Release** (production
build flags — **no** `-DNHARD_DIAG`; shim 20260028 gate values unchanged:
`OSD_NHARD_MAX = 60`, `OSD_CORR_THRESHOLD = 0.10`).

> Leave `K_MAX_CANDIDATES_PASS2` and `K_LDPC_ITERATIONS_PASS2` unchanged. Only
> `K_MIN_SCORE_PASS2` varies, so the curve has one independent variable.

### Action 2 — Measure both axes at each point

For each of the 5 builds, capture **both** metrics:

1. **False-positive rate (S5 noise)** — run the widened S5 noise scenario
   (`qa/rr-study/scenarios/s5-noise-wide.json`, ≥100 slots). Record FP count and
   **FP-per-slot rate** (this is the D-009 cost axis). Baseline reference: ~5 FP/slot
   at P0.

2. **Co-channel decode (S7)** — run S7 P0–P2, K=5
   (`scenarios/s7-compounding.json --parts 0,1,2`). Record `co_channel_sweep` %.
   Reference: 92.1% at the shipped baseline (this is the D-001 benefit axis).

Direct each point's runs to its own result subdirectory to avoid cross-contamination
(MEMORY Lesson 14):

```
qa/rr-study/results/diag-pass1-sweep-2026-06-21/p0-minscore1/
                                                /p1-minscore3/
                                                /p2-minscore5/
                                                /p3-minscore7/
                                                /p4-minscore10/
```

### Action 3 — Produce the trade-curve table, then STOP

Write `qa/rr-study/results/diag-pass1-sweep-2026-06-21/pass1_sweep.md`:

| `K_MIN_SCORE_PASS2` | S5 FP/slot | S5 FP count / slots | S7 co_channel_sweep % |
|---|---|---|---|
| 1 (baseline) | … | … / … | … |
| 3 | | | |
| 5 | | | |
| 7 | | | |
| 10 | | | |

Plus a 3–4 sentence plain reading: where does FP rate fall off a cliff, and where
does co_channel_sweep start to collapse? Is there a "knee" where FPs drop sharply
before sensitivity does — or do both degrade together (confirming the trade is
inseparable even on this axis)?

**Then stop.** Hand `pass1_sweep.md` to the architect. Do **not** select a value,
commit a binary, or bump the shim. NFR-023 report sections remain QA's obligation;
this is a diagnostic table, not a full study report.

---

## 4. Acceptance Criteria

| # | Criterion |
|---|---|
| AC1 | 5 builds measured, `K_MIN_SCORE_PASS2` ∈ {1,3,5,7,10}, all other defines unchanged |
| AC2 | Each point has S5 (≥100 slots) FP-per-slot rate AND S7 P0–P2 `co_channel_sweep` % |
| AC3 | `pass1_sweep.md` table complete + plain-language reading of the curve/knee |
| AC4 | No swept binary committed; committed DLL remains shim 20260028 |
| AC5 | No threshold selected, no fix implemented — architect/Captain decide from the curve |
| AC6 | NFR-021: S5 ALL.TXT (AWGN CRC-coincidence callsigns) **not** committed; only numeric metrics / counts in `pass1_sweep.md` |

---

## 5. References

- `2026-06-21-d009-b2-escalation-captain.md` — why this sweep exists (§4a, the trade dial)
- `qa/rr-study/results/diag-nhard-2026-06-20/nhard_observations.md` — R6 B2 finding (pass-1 origin)
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — `K_MIN_SCORE_PASS2` (~385); multi-pass loop (~1100)
- `qa/rr-study/scenarios/s5-noise-wide.json`, `scenarios/s7-compounding.json`
- MEMORY Lesson 14 (separate result dirs per point); Lesson 1 ("CI passes" ≠ committed binary current — irrelevant here since nothing is committed)
