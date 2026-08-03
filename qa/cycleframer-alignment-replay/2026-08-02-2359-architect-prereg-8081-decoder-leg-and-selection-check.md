# Architect — PRE-REGISTRATION: 8081 decoder leg, and does the +0s selection bias T4?
# Written before the measurement is run. Thresholds fixed here. NOT authorised until the Captain says so.
# ⚠️ Runs AFTER T4 reports. Does not amend T4. Does not compute F_dec.

**Author:** Architect, 2026-08-02 (23:59 UTC, `date -u`, per HK-017). Repo at `162a08d`.
**For:** QA to execute **only on the Captain's authorisation, and only after T4 has reported.**
**Origin:** the Captain's observation that 8081's drift is marginal, so its WAVs should be usable
for the jt9 comparison. They are — for one leg, and for one thing worth more than that leg.

---

## 1. Why this exists

T4's population is the **+0s stratum**: cycles where 8080's capture window sat on the UTC grid.
Because 8080 drifts at 48.0 ppm, that is **the first ~3 hours after each restart** — 3,618 of
10,475 cycles (34.5%). It is drift-free by construction, which is what makes it valid, but it is
**not a random sample of the run**.

I flagged that in the 2316 hand-off as a caveat I could name but not measure. **8081 can measure
it.** At 4.7 ppm it holds **99.4% grid alignment across all 43.5 hours** (10,409/10,467) with
**100% own-WAV coverage** — so on 8081 the same comparison can be run on the full run *and* on the
+0s subset, with nothing else changing.

| | 8080 | 8081 |
|---|---:|---:|
| grid-matched cycles | 3,618 / 10,475 = 34.5% | **10,409 / 10,467 = 99.4%** |
| own WAVs present | — | **10,467 = 100%** |
| usable (aligned **and** WAV) | 3,617 | **10,409** |

WAV format verified jt9-compatible on both: mono, 12000 Hz, 16-bit, 15.00 s.

## 2. What 8081 can and cannot do

**CAN — the decoder leg.** `B − A` is "identical audio bytes, different decoder." jt9 over 8081's
own WAVs against 8081's own live decodes is exactly that.

**CANNOT — `F_dec`.** Leg C is WSJT-X on **FT-991A → USB Audio CODEC**; 8081 is on **SDR Uno →
Voicemeeter B1**. The split antenna makes propagation and feedline common-mode
(`three-decoder-antenna-split-run-2026-07-31-todo.md`), but the receiver, its AGC, its ADC and the
virtual audio path all differ. `C − B` on 8081 would measure capture framing **plus a different
radio** — the exact confound Angle 1 was built to avoid. **8081 is an addition, not a substitution.**

## 3. Design

```
A81  = 8081 live decodes                    (8081 ALL.TXT)
B81  = jt9 offline over 8081's OWN WAVs     (same cycles, same audio bytes)

G    = (SUM(B81) - SUM(A81)) / SUM(A81)     <- decoder surplus, ratio-of-sums
```

**Estimator:** `ratio_of_sums()` from `qa/endurance/anova_common.py` (T3 item 4). Never
mean-of-ratios.
**Matching:** exact `(ts, normalize_hash_tokens(message))`, as T4.

**Two populations, differing ONLY by selection:**

```
P_full  = 8081 cycles that are grid-aligned AND have an own WAV        (~10,409)
P_0s    = the subset of P_full whose timestamps fall in 8080's
          +0s stratum, as QA defines it via apply_grid_snap            (~3,6xx)
```

**Primary statistic:** `dG = G(P_full) - G(P_0s)` — absolute difference in ratio units.

## 4. Pre-registered decision rows — mechanical, ordered, mutually exclusive

Evaluated in order; the first matching row is the verdict.

```
ROW 0 (guard):  |P_full| < 500  OR  |P_0s| < 500
                OR NOT isfinite(G(P_full))  OR NOT isfinite(G(P_0s))
                ⇒ INVALID. Do not interpret. Report and escalate.

ROW 1:  |dG| <= 0.05    ⇒ SELECTION UNBIASED.
                T4's decoder-attributable term is not an artefact of sampling
                the first ~3 h after each restart. T4's verdict generalises to
                the full run and may be reported without a selection caveat.

ROW 2:  |dG| >  0.05    ⇒ SELECTION BIASED.
                T4's headline figure is conditioned on the post-restart window.
                It remains valid for its own population but MUST be reported
                as such, and T5's design must account for it.

ROW 3 (catch-all): no row above fired
                ⇒ NO VERDICT. Report and escalate. Should be unreachable given
                ROW 0, and exists because rows 1-2 are exhaustive over the reals
                but not over float("nan") — the gap found in T4's own §4 on
                2026-08-02.
```

**Where 0.05 comes from — not taste.** It is the same ±5% bar the programme already uses for
instrument agreement in T4's null N3 (`|jt9(WSJTX wav) - C| / C > 0.05 ⇒ VOID`). Using a different
tolerance for "do two populations of the same instrument agree" than for "does the instrument agree
with itself" would need a reason, and there isn't one.

## 5. Mandatory nulls — any failure ⇒ VOID

```
M1  IDENTITY:   A81 matched against itself must give recall exactly 1.0000.
                Anything else ⇒ VOID (the matcher is broken).

M2  COVERAGE:   every cycle in each population must have its own WAV.
                coverage < 0.99 in either population        ⇒ VOID.

M3  DEDUP:      jt9 output must carry zero duplicate (ts, message) pairs.
                Else                                         ⇒ VOID.

M4  NESTING:    P_0s must be a strict subset of P_full.
                Any cycle in P_0s absent from P_full          ⇒ VOID
                (the two populations would not differ by selection alone,
                which is the entire premise).
```

Non-finite `G` is handled by ROW 0 rather than a null, so it cannot be reached twice.

## 6. Secondary — replication, descriptive only

Report `G(P_0s)` on 8081 alongside T4's decoder-attributable term on 8080. If the decoder surplus
is a genuine property of the decoder rather than of a capture chain, the two should be comparable.

**No threshold is set on this and no verdict attaches to it.** It is reported as a description, so
that a later hypothesis about chain-independence has an honest prior instead of a reverse-fitted
one. Stating that in advance is the point.

## 7. Stated in advance, so nothing can be reverse-fitted

- 8080 and 8081 run at **0.93–0.97 of each other** when both are drift-healthy (measured, 23:45
  today). Instance-to-instance variation on this hardware is a few percent, so a `dG` of 0.05 is
  above the noise I would expect from the instances differing at all.
- The +0s stratum is the **first ~3 h after each restart**. If anything varies with uptime other
  than drift, `dG` is where it would appear.
- Per T9, the >2 s decode cliff is a **48 ppm** phenomenon on 8080. 8081 reaches 2 s only at
  ~118 h, and the run was 43.5 h, so **P_full is not contaminated by the cliff.**
- **I hold no prior on ROW 1 vs ROW 2.** That is why it is worth running.

## 8. What this does NOT do

- **Does not amend T4.** T4 is authorised and runs exactly as pre-registered.
- **Does not compute `F_dec`**, and must not, as a by-product or otherwise.
- **Does not touch leg C.** No WSJT-X data is read by this measurement at all.
- **Does not settle the density penalty** (T5) or the S.1 VOID.

## 9. Ordering — this matters

**Run after T4 reports.** Not for a technical conflict — `G` is not `F_dec` — but because seeing a
large decoder surplus on 8081 before T4's rows are read would contaminate how they are read. The
pre-registration discipline is worth more than the day it saves.

## 10. Cross-references

- `2026-08-02-1813-architect-prereg-angle1-baseline-deficit-decomposition.md` — T4. Authorised.
  This note is subordinate to it and changes nothing in it.
- `2026-08-02-2316-architect-to-qa-handoff-…` — T4's selection caveat (§T4) that this measures,
  and T9's drift cliff that bounds it.
- `qa/endurance/anova_common.py:ratio_of_sums` — the estimator, T3 item 4.
- `qa/ARTEFACT_INVENTORY.md` — the corpus row.

---

*Per HK-015 Architect → QA: design mine, execution QA's, on the Captain's authorisation only. Per
HK-014/HK-010 committed locally, no push, no merge. Per HK-017 real `date -u` UTC. Per HK-021 §4
and §5 are mechanical — hard thresholds, the 0.05 anchored to an existing programme bar rather than
chosen, consequences as assertions, rows exclusive and ordered, and a catch-all because rows are
exhaustive over the reals but not over NaN. Per HK-018 §1 and §7's figures were measured from data
on disk before this design was written, not asserted. Per HK-022 each figure names its population.
NFR-021: aggregate counts only.*
