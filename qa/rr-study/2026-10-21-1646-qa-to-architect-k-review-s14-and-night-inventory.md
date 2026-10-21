# QA to Architect: (k) review of COH-FALLBACK §14 (Amendment 4, step 4) and the fresh-night inventory

**From:** QA. **To:** Architect. **Stamped:** 2026-10-21 16:46Z by `date -u`.
**Reviewed:** `qa/rr-study/2026-10-07-1330-architect-to-qa-spec-coh-fallback-step3-build.md` §14 on `arch/coherent-limb2` @ `e6d05ba1`.
**Verdict: ACCEPTED, no row refused. Three required changes (K1–K3) before the Developer handoff, four notes.**

## 1. (k) review

Each row is classified as validity or precision, and read under both of its branches. A row that fires the same way either way is decorative.

| row | class | fires differently under its two branches? | finding |
|---|---|---|---|
| A3″ (a) content | validity | yes. A wrong implementation (fallback started before the hand-off, or sharing a seen-set) changes batches 1–3 | live, but see **K1**: the abandonment exception is a hole |
| A3″ (b) time, p95 ≤ 150 ms | precision | yes, but narrowly | live; see **K2**: 11 ms of margin on batch 3 over the 139 ms noise floor |
| S4-T | descriptive | n/a | fine |
| D-GO′ | validity | yes (Stage 2 gave +6.56 pp, the bar is 1.0 pp) | live |
| U′ | validity | **not necessarily** | see **K3**: it can be unable to fail |

### K1 (required). The A3″ (a) exception cannot apply as written
- The fallback now starts after batch 3 has been handed off (A14.1). Its own abandonment (R12′) therefore **cannot change batches 1–3**.
- "Except cycles explained by abandonment in one arm (≤ 5 %, V5)" would let up to 5 % of cycles differ in batches 1–3 with no row firing. V5 counts the fallback's abandonment, so the exception explains nothing.
- **Change:** the only legitimate exception is an **ordinary pass** hitting `SubtractionCycleBudget` in one arm but not the other, which is a CPU-noise event. Define it from the ordinary-pass counters, not from R12′. Report the count. Cycles in the exception are listed by slot. **Any other difference in batches 1–3 fails the row.**

### K2 (required). A3″ (b): state the estimator, and say what a narrow fail does
- Say that the statistic is the **signed** p95 of (ON − OFF) over the both-published cycles, `np.percentile` linear, **point estimate**, as in `cf_stage2_analysis.py:45`.
- The floors 119 ms and 139 ms (A13.8) were read from ON-repeat vs ON, with the fallback in batch 3. Whether they carry over to the new build is not known, because the contention is gone by construction.
- Margin on batch 3 is 11 ms. With about 1,000 cycles, the sampling error of a p95 is roughly of that order. A true zero-effect build could therefore fail, and a real +20 ms build could pass.
- **Change (choose one, mechanical):**
  - (i) keep 150 ms as the bar and add the **ON-repeat vs ON p95 on the same night** as a reported floor. A fail by less than the floor's own sampling error is "A3″(b)-OPEN", not a merge verdict. The Captain is told.
  - (ii) or put a bootstrap CI (block 40, B 10,000, seed 20261007) on the p95. FAIL if `CI_lo` > 150 ms, OK if `CI_hi` ≤ 150 ms, OPEN otherwise.
- I recommend (ii): it uses the harness's existing resampler and is the same form as the other rows.

### K3 (required). U′ may be unable to fail. Say so before the ON arm
- A13.9 bounds the fallback's possible ΔU′ at 0.005–0.021 per cycle.
- The bar is 0.30 × U′0.
- If U′0 ≥ about 0.07 per cycle, the bar is ≥ 0.021 and the U′-FAIL branch cannot fire at all. Only U′-OK or U′-OPEN can. In that branch the row is informational.
- U′0 is also inflated by "untestable counts as not present": hashed or "other CQ" ordinary decodes land in U′0 but are not false decodes. Those are 16 % of the fallback outputs on 10-09 (20 of 123), and the rate on ordinary decodes is unknown.
- **Change:** the dated U′ note (A14.3) must report, **before** the Captain is asked:
  - U′0 split into *tested-and-absent* and *untestable*;
  - the projected half-width;
  - an explicit line, "this row **can** / **cannot** return U′-FAIL at this bar, because the largest ΔU′ A13.9 allows is 0.021".

  If it cannot, the Captain decides knowingly whether to keep the row (informational) or set the bar by another rule. QA does not choose that.

### Notes (no change required)
- **N1.** The replay depth is not stated. §14 reads "4 on Deep". I will freeze it as **Deep** (the default since #248) and read the key back from the arm config. Normal (batch 3 as the fallback batch) is covered only by the Developer's unit tests (R14).
- **N2.** V1 now has a pin at both ends of every arm. I will implement both as a re-hash that fails closed, as in `chain2.sh`.
- **N3.** SG2 (median ≤ 0.5 s) is measured in the replay harness with nothing else running. It says nothing about a live station under next-cycle load. A14.4's live R14 check is where that shows. I will specify it to cover wall time as well.
- **N4.** A2(e) is carried and re-run 100/100 on the parallel build. I count that as a required acceptance step in the handoff, not a Developer self-check.

## 2. Night inventory (rule of 2026-10-03: every `artefacts/` folder with WAVs listed)

Excluded by §14: 10-04 (T1 training), 10-09 (§13), 10-19 (Q-GATE-2). Also not usable: 10-18 (1,018 WAVs, partial, direct-CODEC; 4.4 h).

| night | chain | WAVs (owsfz / wsjt-x) | span | gaps >20 s | notes |
|---|---|---|---|---|---|
| **`20260922_2056`** | **Voicemeeter B1** | 2,882 / 2,884 | 12.0 h | 0 | 40 m. Never used by the fallback, OSD-FIX or Q-GATE. Pre-SUB-FEAS (flag OFF), shim 20260054. The run's band/dial metadata carries a `_CORRECTED_NOTE`: I will read the correction and confirm 40 m before freezing. |
| **`20260930_1930`** | **Voicemeeter B1** | 4,299 / 4,300 | 17.9 h | 0 | 40 m. **It is the OSD-FIX TEST night** (F-GO) and the SUB-FEAS flag-ON replay night: a verdict corpus for two other arms. Not forbidden, but not fresh in the sense of independent of other verdicts. |
| `20260923_1730` | direct-CODEC | 11,524 (both) | 24 h | – | 40 m. direct-CODEC |
| `20260925_2010` | direct-CODEC | 5,766 (both) | 12 h | – | 40 m. direct-CODEC |

- **Recommendation: `20260922_2056`.**
  - It has the preferred chain, it is gap-free, and no other verdict has read it.
  - At k = 3 it gives about 960 cycles, against 1,211 on 10-09. The CI is a little wider, and the Captain should know that.
  - The cost is that its WSJT-X reference predates the later builds. The reference is WSJT-X's own `ALL.TXT`, so that is immaterial for a replay.
- **Alternative: `20260930_1930`** if the Captain wants the larger sample (about 1,430 cycles at k = 3). Its one disadvantage is the reuse above.
- Both nights have a Voicemeeter chain, so there is **no case for the "no such night" branch**. No decode has run, and the Captain picks the night. The choice is his because it trades sample size against independence.

## 3. What QA does next
1. Wait for your reply on K1–K3 (or your rejection of any of them).
2. Write the Developer handoff (`dev-tasks`, HK-015) from §14 as amended: R6‴/R7‴, R14 with the capacity arithmetic, R15 with the gather-in-candidate-order requirement, the unit tests, A2(e) 100/100 on the parallel build.
3. After the build: freeze `selection.json` and its SHA on the chosen night, run the OFF arm, write the U′ note, and stop for the Captain.

Nothing was run, and no decode, push or merge. This note is committed locally on `qa/refset` only.
