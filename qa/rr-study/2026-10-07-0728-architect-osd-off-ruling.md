# RULING — `OSD-OFF` (NHARD-REP Amendment 3): **O-GAIN accepted.** OSD off gains a little and loses nothing: NET +0.074 pp [+0.020, +0.146], replicated at +0.079 pp on fresh cycles

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-07 07:28Z (`date -u`, HK-017)
- **Branch:** `arch/nhard-replication`. Docs only: `git diff --stat -- src/ native/` empty.
- **Reviewed:** QA report `qa/rr-study/results/2026-10-06-nhard-rep/report_n0.md` + `n0_analysis.json` @ `b0fc95c5` (`qa/osd-off`, local, not pushed); the overnight confirmation section of `qa/rr-study/results/2026-10-06-coh-gain/report_overnight.md` @ `722bd640` (`qa/coh-gain`, local); raw numeric files in `artefacts/rr_2026-10-06_nhard_rep/` and `artefacts/rr_2026-10-06_nhard_rep_n0/` (read, numeric only, HK-037).
- **Against:** spec `2026-10-06-1430-architect-to-qa-spec-nhard-replication.md` §14 (Amendment 3, `59484596`), O-SAFE margin ratified by the Captain (`ad06779f`), V7 (`12caa402`).

## 1. Verdict: O-GAIN, accepted

**NET_0 (nhard 0 − nhard 40) = +0.074 pp of WSJT-X's decodes, 95 % CI [+0.020, +0.146]** (311 cycles, Σ`W` 9,466, block 8, 39 blocks, B 10,000). `CI_lo` > 0 ⇒ **O-GAIN**. All validity rows pass.

**Checked myself (HK-018), not taken from the report:**

- **Recomputed from the raw match files** (`matched_N40.csv`, `matched_N0.csv`, `per_cycle.csv`) with my own script: Σ`M40` 6,759, Σ`M0` 6,766, **K = 7, G = 0**, 6 cycles carry the gain. NET 0.0739 pp. My block bootstrap gives **[+0.020, +0.146]**. It matches the report.
- **Unconfirmed decodes recomputed** from `outcomes_*.csv`: 6,905 − 6,759 = **146** at 40, 6,889 − 6,766 = **123** at 0. It matches.
- **V2″, read from `probe_*.csv`:** at 0 both `P_lo` and `P_hi` are rejected (path −1); at 40 `P_lo` is accepted (path 1, CRC ok, payload match). The setting reached the native gate. This is what keeps a blind arm from reading as O-GAIN or O-SAFE.
- **V7** (0 of 100 cycles differ across harness binaries) is what makes the pairing with the N40 on file sound. Accepted.

**Replication (overnight run, Amendment 5, fresh cycles `i mod 10 == 5`, both arms on one binary):** NET_0 **+0.079 pp [+0.029, +0.141]**, K = 9, G = 1; pooled over 621 cycles **+0.076 pp [+0.036, +0.123]**. Unconfirmed 173 → 147. All of the gain is in batch 2 again. O-GAIN on both samples. I read the figures from QA's report; I have not re-run that sample's arithmetic.

## 2. What it says

- **OSD off is safe.** Across 621 cycles it lost **1** WSJT-X-confirmed decode and gained 16. This is what #215's analysis predicts: an OSD fed inverted LLRs cannot make genuine decodes, so turning it off removes only false ones.
- **The gain is real and very small.** About 0.08 pp, roughly 10 extra confirmed decodes per 310 cycles (about 2.6 hours of one band). It sits in batch 2, which fits the reading that a false first-pass decode, once subtracted, damages the residual. That mechanism is still the best-fitting reading, not a tested one.
- **The useful effect is on false output, not on decode rate.** Unconfirmed decodes fall by about 16 % (146 → 123; 173 → 147), and in band D (the weakest signals) from 5.3 % to 3.6 % and 4.5 % to 3.0 %. Unconfirmed is an upper bound on false decodes, not a count of them.

**Citable as:** *"`nhard` 0 (OSD effectively off) vs 40 on `main` `be3cc5ac` (shim 20260058), flag ON: NET +0.074 pp [+0.020, +0.146] of WSJT-X's decodes, replicated at +0.079 pp [+0.029, +0.141] on a second 1-in-10 sample; pooled +0.076 pp [+0.036, +0.123] over 621 cycles of one 40 m night (`20261004_1634`), replay vs replay, Test B match rule. Unconfirmed decodes fall about 16 %."* 🛑 Never cite it as a decode-rate improvement of note. It is a correctness fix that happens not to cost anything.

## 3. Consequence: a decision for the Captain (not licensed here)

The spec's stated consequence holds: O-GAIN is evidence for **OSD off as the interim default** until a working OSD exists (#215).

**The data the decision rests on:**

| | keep OSD on (`nhard` 40) | OSD off (interim default) |
|---|---|---|
| WSJT-X-confirmed decodes | baseline | +0.08 pp (16 gained, 1 lost in 621 cycles) |
| unconfirmed decodes per cycle | 0.47 / 0.56 | 0.40 / 0.47 (about −16 %) |
| what OSD contributes | only chance-CRC false decodes (#215, verified from source) | nothing lost |
| cost to make the change | none | a config default + a one-time migration, a dev-task, a Developer session (HK-011), a merge sign-off (HK-010). Small. |

**What each option leads to:**

- **Make the change:** the product stops putting known-false OSD decodes on the panel and into ALL.TXT, at no measured cost. Every run after it is a new population (OSD off), and must not be pooled with earlier runs, as with the flag-ON change in October.
- **Park it:** nothing gets worse than today. Production keeps adding about 0.07 unconfirmed decodes per cycle that the sign analysis says are false. #215 stays open with this ruling as its evidence.

**Does it matter?** For the decode rate, hardly: +0.08 pp is far below anything the programme is chasing. For **correctness** it matters a little: we ship a decoder path that can only produce wrong decodes. My recommendation is to make the change, because it is cheap and removes a known defect rather than adding a feature. It is not urgent, and parking it costs only the false decodes we already ship today.

🛑 Fixing OSD's sign properly is **not** recommended: COH-GAIN measured a sign-corrected OSD as no lever on today's LLRs (+0.011 pp, 1 true vs 271 wrong; overnight +0.051 pp, 33 true vs 1,846 wrong).

## 4. Report changes before commit: none required

The report states the scope sentence, the clustering flag (7 decodes in 6 cycles), that the mechanism is untested, and that the change is not licensed. **It may be pushed as it stands, with the Captain's go (HK-033).**

## 5. Predictions, scored at ruling time (spec §14; ledger rule 1)

| # | prediction | P | class | outcome |
|---|---|---:|:---:|---|
| OO1 | O-GAIN | 0.40 | H | ✅ HIT |
| OO2 | O-SAFE and not O-GAIN | 0.50 | H | ❌ MISS (the outcome was O-GAIN) |
| OO3 | O-HARM | 0.03 | H | ✅ HIT (it did not happen) |
| OO4 | not-confirmed per cycle falls by ≥ 0.10 | 0.55 | H | ❌ MISS (−0.074; the replication −0.084) |

Mutually exclusive OO1/OO2 put 0.40 on the outcome that occurred. I had the direction right and the size slightly high on OO4.
