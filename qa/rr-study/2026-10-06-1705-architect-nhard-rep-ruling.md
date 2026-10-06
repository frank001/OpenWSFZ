# RULING — `NHARD-REP`: **N-CLOSED**. `nhard` 60 is not a lever. It is worse than 40 on today's build: NET −0.58 pp [−0.79, −0.41]

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-06 17:06Z (`date -u`, HK-017)
- **Branch:** `arch/nhard-replication`. Docs only: `git diff --stat -- src/ native/` empty.
- **Reviewed:** QA report `qa/rr-study/results/2026-10-06-nhard-rep/report.md` + `rows.json` @ `3ab15347` (`qa/nhard-rep`, local, not pushed); raw numeric files in `artefacts/rr_2026-10-06_nhard_rep/` (read, numeric only, HK-037).
- **Against:** spec `2026-10-06-1430-architect-to-qa-spec-nhard-replication.md` + Amendments 1 (`722ff543`) and 2 (`f96b46c7`). `BAR_N` = 0.5 pp, ratified before any datum.

> ⛔ **READING CORRECTED 2026-10-06 17:1xZ (Architect, HK-022). The verdict and every figure stand. What they MEAN changes.** QA found, and the Architect verified from source, that **production OSD receives sign-inverted LLRs**: the extractor and BP use positive = bit 1, `osd_decode` uses positive = bit 0, and the call site does not negate. ⇒ Every production OSD accept is a chance-CRC false decode. **This arm therefore measured a cap on an OSD that cannot produce genuine decodes.** The cap acted only on false decodes, which is exactly what §2 observed. **§2's mechanism reading and §3's "cap below 40" lead are SUPERSEDED.** With OSD fixed, `nhard` must be measured again from scratch. Evidence and the next measurement: `2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md` §12 (Amendment 2, `15582597`, `arch/coherent-limb2`).

## 1. Verdict: N-CLOSED, accepted

**NET (60 − 40) = −0.581 pp of WSJT-X's decodes, 95 % CI [−0.79, −0.41]** (311 cycles, systematic 1-in-10, Σ`W` 9,466, block 8, 39 blocks, B 10,000). `CI_hi` −0.41 < `BAR_N` 0.5 ⇒ **N-CLOSED.** All validity rows pass.

**Checked myself (HK-018), not taken from the report:**

- **Arithmetic:** Σ`M60` − Σ`M40` = 6,704 − 6,759 = −55. −55 / 9,466 = −0.581 %. K − G = 2 − 57 = −55.
- **Interval, recomputed independently** from `per_cycle.csv` (my own block bootstrap, different RNG): **[−0.785, −0.410]**. It matches.
- **Not a clustering artefact:** 48 cycles have `d_i` < 0, and **1** has `d_i` > 0 (min −6). The largest |block sum| is 8 of 55. No first-paragraph flag.
- **V2′, read from `probe_*.csv`:** `P_lo` was accepted at every probe point in all three arms. `P_hi` was **rejected in N40 and AA and accepted in N60, at start and end.** The cap demonstrably reached the native gate in each arm. This is what makes N-CLOSED readable.
- **V6:** AA reproduced N40 exactly, 200/200 cycles, 0 multiset differences.
- **Fidelity:** the N40 replay gave 6,905 decodes vs 6,902 live, equal on 293/311 cycles.

**QA's disclosure (COH-GAIN prep ran, ≤ 2 workers, during the AA arm):** accepted with no effect on the verdict. AA matched N40 exactly, and V5 is 0 and 1 of 311 abandoned. The outcome depends on timing only through V5/V6, and both are clean.

## 2. What it says, beyond the row

The rows were registered to find a **gain** at 60. The data show a **loss**, and the descriptive split says where:

| | 40 | 60 |
|---|---|---|
| WSJT-X-confirmed decodes | 6,759 | 6,704 (−55: **−0.05 pp batch 1, −0.53 pp batch 2**) |
| not-confirmed decodes per cycle (an FP upper bound) | 0.47 | **1.14** |
| not-confirmed rate, band C / band D | 1.6 % / 5.3 % | 5.3 % / **16.9 %** |

- **The cost of 60 is real on real audio.** Not-confirmed output more than doubles. The 0.5 pp bar's noise-cost premise failed on white noise (Amendment 2), but it **holds on the air**: −0.27 confirmed per extra not-confirmed.
- **The loss is almost entirely in batch 2, the residual pass.** That fits the mechanism the spec named in §0, in the **opposite** direction to the one I priced: extra first-pass OSD accepts at 60 are mostly false, and **subtracting a false decode damages the residual**, costing genuine batch-2 decodes. 🛑 This arm does not test the mechanism (QA says so, correctly). It is the best-fitting reading, not a finding.
- **Settled for the programme:** item B closes. 40 stays. No intermediate caps (§7: they were only for N-LEVER).

**Citable as:** *"`nhard` 60 vs 40 on `main` `be3cc5ac` (shim 20260058), flag ON: NET −0.58 pp [−0.79, −0.41] of WSJT-X's decodes, one 40 m night (`20261004_1634`), 1-in-10 cycle sample, replay vs replay, Test B match rule. Not-confirmed decodes 0.47 → 1.14 per cycle."* Never cite it as *"`nhard` has no effect"*.

## 3. A lead, not a proposal: is 40 itself too high now?

If false first-pass OSD accepts poison the residual, **a cap below 40 might gain batch-2 decodes**. The product accepts 30–100.

The evidence on the other side: `NT`/`CC` found OSD rescued **no** genuine decode at any cap on synthetic audio, and `E3` found 2 WSJT-X-confirmed decodes in 57,594 that depended on 40 < `nhard` ≤ 60. So a lower cap may lose very little genuine output. It could gain from cleaner residuals, or it could also cut genuine OSD rescues in (30, 40].

**This is a new question, outside this arm's rows.** It would be a two-leg replication on the same harness (40 vs 30, ≈ 1.2 h, V2′ probes retuned to a vector with `nhard_true` in (30, 40]). **The Captain's call**, after `COH-GAIN`, which has the bigger upside. I am not speccing it unasked.

## 4. Report changes before commit: none required

The report states the scope sentence, the sample, the retired V2's 0-vs-0 as descriptive, V2′'s construction note, and that the batch-2 mechanism is untested. **It may be pushed as it stands, with the Captain's go (HK-033).**

## 5. Predictions, scored at ruling time (spec §10; ledger rule 1)

| # | prediction | P | class | outcome |
|---|---|---:|:---:|---|
| NR1 | Verdict N-CLOSED | 0.80 | H | ✅ HIT |
| NR2 | NET point in [−0.05, +0.15] pp | 0.65 | H | ❌ **MISS** (−0.58). I priced a null; the effect was a real loss, in the batch-2 direction NR6 had wrongly signed. |
| NR3 | V2 passes | 0.85 | C | ❌ MISS (already scored, Amendment 2) |
| NR4 | V6 passes | 0.80 | C | ✅ HIT (200/200 exact) |
| NR5 | not-confirmed per cycle higher at 60 | 0.90 | H | ✅ HIT (0.47 → 1.14) |
| NR6 | if K > G, more than half of K − G sits in batch 2 | 0.55 | H | ⏸️ **NOT SCORABLE**: its condition (K > G) did not hold. The batch-2 concentration did appear, with the opposite sign. |
