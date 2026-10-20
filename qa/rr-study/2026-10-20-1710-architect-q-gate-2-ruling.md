# RULING: `Q-GATE-2`: **G2-OK, accepted.** The frozen strength gate keeps **+3.03 pp [2.72, 3.35]** of WSJT-X's rows that today's product misses, at **0.014 [0.006, 0.023]** unexplained outputs per cycle, against `U_max` 0.05

- **Architect, 2026-10-20 17:10Z (by `date -u`, read at 17:02Z).** Branch `arch/coherent-limb2`.
- **Against:** spec `2026-10-20-1530-architect-to-qa-spec-q-gate-2.md` with Amendment 1 (§12, `19e35ac1`) and
  Amendment 2 (§13, `3ba9fa2c`). `U_max` = 0.05 was set by the Captain and `BAR_G` = 1.0 pp came from the spec, both
  before any label was joined.
- **On:** QA's report `qa/rr-study/results/2026-10-20-q-gate-2/report.md` (QA `qa/refset` `0d8d674d`, local; root
  results copy read), with `main_analysis.json` and `pilot_pool.json` beside it.
- Docs only: the `src/` and `native/` diffs are empty.

## 1. Verdict: G2-OK, accepted

| row | value | bar | result |
|---|---|---|---|
| KG (GA, F1b ≤ T1 = 17.552446 dB, frozen, no retune) | **3.031 pp [2.722, 3.346]** (754 kept RIGHT of 24,876 encodable rows) | CI_lo ≥ 1.0 | met |
| UPC (kept unexplained per sampled cycle) | **0.01396 [0.00644, 0.02256]** (13 of 931 cycles' worth) | CI_hi ≤ 0.05 | met |

- **Checked from the JSON, not the prose:** 754 / 24,876 = 3.031 %, and 13 / 931 = 0.01396. The `ROW` block of
  `main_analysis.json` reads `G2-OK`, with the same intervals. There were 117 blocks of 8 cycles, B = 10,000 and seed
  20261020, as frozen.
- **Wording (A1.4), required in every citation:** G2-OK is **necessary, not sufficient**, for the step-3 build. UPC counts false outputs at real-signal positions only. It does not establish the step-3 false-decode rate.
- **Over all 933 sampled cycles UPC is 0.01393.** Two cycles hold no encodable row. The row is read over 931, as the
  per-cycle unit was defined. The difference is immaterial.

## 2. Validity: all PASS. One process slip, ruled

All rows PASSED: S0, V-L, V-P, V-T1, V-G1, V-C1, V-K and V-T2. The V-T2 figures follow A2.2:

| control | n | matches | Wilson 95 % upper | bar |
|---|---|---|---|---|
| main | 124 | 0 | 3.0 % | main point rate ≤ 2 % |
| pooled (pilot + main) | 324 | 0 | 1.17 % | ≤ 2 % |

The pilot pool reached n = 200 with 0 matches: 108 outputs from `i mod 5 == 3` and 92 from the first 651 cycles of
`== 2`, 1 cycle excluded for < 2 rows.

🛑 **The slip QA disclosed: the A2.1 pool gate printed nothing, and the main run started without it.** The cause was a
Git-Bash path passed to Windows Python. QA then ran the check with correct paths: n = 200, 0 matches, PASS.

**Ruling: the result stands.** The reasons:
- **What the gate protects.** It exists so main-run labels aren't spent while the truth rule is in doubt.
- **Its input was fixed before the main run.** The control outputs of residues 3 and 2 are extracted from those cycles
  alone. The check is a mechanical count, and no main-run output can change it.
- **It passed with 0 matches.** So the run the spec would have permitted is the run that happened.
- **What is lost is the mechanical enforcement of the order, not the evidence.** This is recorded, not excused (HK-022).

**Required before the next arm that uses this chain:** QA's script fails closed on an empty or unparsable gate result. QA proposed exactly that.

## 3. What it means

**On today's product, the frozen gate does what it promised, on a night it has never seen.**
- **The setting:** the 20261019_1905 night, at WSJT-X's own positions, on signals the live product missed.
- **The gain:** it adds 3.03 pp of WSJT-X's rows.
- **The cost:** it emits 0.014 unexplained outputs per cycle. The live product's OWS-only rows on the same sampled
  cycles run at **0.170** per cycle, so the gated fallback would add **≈ 8 %** to that rate at these positions.
- **The gain is spread out.** It comes from 452 distinct cycles, and the top 5 blocks hold 11.3 % of it.
- **The weakest signals carry it.** Kept RIGHT by SNR band: 266 at ≤ −16 dB, 361 at −15..−6 dB, 112 at −5..+4 dB and
  15 at ≥ +5 dB.

**Descriptive only; no row and no retune.**
- **Ungated:** 3.88 pp at UPC 0.030. So the gate costs 0.85 pp of gain and halves the unexplained rate.
- **Where the gate cuts:** mostly at ≥ −5 dB. The kept RIGHT counts fall from 225 to 112 in −5..+4 dB and from 74 to
  15 at ≥ +5 dB.
- 🛑 **T1 is not re-tuned on this.** The standing prohibition applies: a closed gate is never re-read with a better metric.

**Q-GATE (10-07) is not re-read, and the bridge is not differenced against it.**
- **Q-GATE's verdict stands:** GATE-OPEN at 0.178 against 0.15 on its own night, build and truth.
- **The bridge, on Q-GATE's population definition (G-fail only, live hits ignored):** KG 3.98 and UPC 0.058.
- **What separates the two readings here is mostly the population.** Rows the live product already decodes would never
  reach the fallback in the step-3 design, and the P population excludes them. P is the population the product will see.

## 4. Predictions, scored at ruling time (spec §11)

| # | prediction | P | class | outcome |
|---|---|---:|:---:|---|
| QG1 | every validity row passes | 0.80 | C | ✅ **HIT** (with the disclosed process slip, §2; the rows themselves all passed) |
| QG2a | G2-OK if `U_max` 0.15 | 0.60 | H | **VOID** (the Captain chose 0.05; only the matching line is scored, per §11) |
| QG2b | G2-OK if `U_max` 0.05 | 0.35 | H | ✅ **HIT**. UPC came in an order of magnitude below 0.178. I under-priced it, because I anchored on the old night's rate |
| QG3 | point KG in [2.0, 4.5] pp | 0.55 | H | ✅ **HIT** (3.03) |
| QG4 | rule (ii) moves ≥ 70 % of old-rule unexplained out of M-NONE | 0.60 | H | ❌ **MISS** (9 of 37 = 24 %) |

🔴 **QG4 is the miss the §11 warning named.** It was the tidy "findable localised defect" story: 795 of 917 type-4
outputs on the 10-07 population carried forward as the explanation.
- On this night and population, the type-4 truth rule explains only a quarter of the old-rule unexplained outputs.
- **What that does and doesn't say:**
  - The mechanism ENC-ID verified from source is still real.
  - It is not the dominant source of unexplained outputs once the product's misses define the population.
- FIELD-ID and ENC-ID are closed and not re-read.

## 5. What this licenses, and what it does not

- **Licensed:** the gate obstacle to the step-3 build is cleared. Spec `2026-10-07-1330-…-coh-fallback-step3-build.md`
  can go to Stage 1 on the Captain's go. Stage 1 is the native core, the A0 cost gate and A2 port fidelity, and it needs
  a Developer session (HK-011).
- **Not established, and still the build's job:** the items spec §10 and the step-3 spec §1 list.
  - whether the product's candidate search finds these signals;
  - false outputs on **noise-only candidates**;
  - the native CPU cost;
  - any second band.
- 🔴 **HK-038: the step-3 spec's Stage 2 acceptance bars are from an older era and must be refreshed before Stage 2's
  replay is frozen.**
  - **The budget's basis is stale.** U-OK 0.15 rests on 0.47 not-confirmed decodes per cycle from build `be3cc5ac`,
    which ran N40 with OSD OFF. The spec's fixed config says `nhard` 40, while today's era is 24, with the OSD fix.
  - **The spec has a guard.** Its own [0.30, 0.65] check on the OFF arm would catch a shifted basis.
  - **But the bar should be set from today's build before the run, not rescued by the guard after it.**
  - **Stage 1 doesn't depend on those bars.** So the refresh is an amendment I draft alongside Stage 1. It is not a
    precondition for starting Stage 1.

## 6. Order from here

1. **The Captain decides** whether the step-3 build goes to Stage 1 now: a Developer session, on `decoding_improvement`
   or a branch off it.
2. The Architect drafts the Stage 2 era refresh (`nhard` 24, the U-OK basis from today's build, the D-GO population)
   as a step-3 spec amendment, for QA's (k) review.
3. QA fixes the chain script to fail closed (§2).
