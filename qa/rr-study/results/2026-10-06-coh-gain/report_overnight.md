# COH-GAIN Amendment 5 — six further fresh samples, pooled; plus the OSD-OFF confirmation (overnight run)

**QA report.** Run 2026-10-06 20:41:38Z → 2026-10-07 02:00:26Z (`date -u`), five hours before the Captain's 05:00Z end. **UNRULED:** Amendment 5 is QA's own, written under the Captain's overnight authorisation (*"do an overnight run as you see fit … expand the samples as you see fit"*) because the Architect's session was unreachable; it changed **no threshold, row or arm**. `BAR_G` = 1.0 pp is the Captain's ratified decision value (HK-038) and was not touched.

**Scope (verbatim):** *Offline, Python, at WSJT-X's own positions on one 40 m night. Extraction and decode only; candidate search, the managed layer and the live path are not exercised. WSJT-X's AP is off on this station.*

## Verdict (primary, as pre-registered): pooled **COH-GO** — a marginal one

**NET_C3 pooled over all eight samples = +1.37 pp of WSJT-X's decodes, 95 % CI [+1.06, +1.67]** (73,977 rows, 2,479 cycles; the first sample, the Amendment-4 extension and six fresh samples; blocks of 8 within each sample then pooled, 312 blocks, B = 10 000, seed 20261006). `CI_lo` 1.06 ≥ `BAR_G` 1.0 ⇒ **COH-GO**. On the fresh samples alone (the six new ones plus the extension, 64,455 rows): **+1.37 pp [+1.04, +1.70]**. Blocks of 4 and 16 (not used): [1.09, 1.64] and [1.02, 1.71]. Earlier, with two samples, the same statistic read COH-OPEN (+1.41 [0.87, 1.94]); the point estimate did not move, the interval narrowed.

🟠 **How much weight the margin bears (post-hoc, descriptive, not a row).** `CI_lo` clears the bar by only **0.06 pp**. Dropping any ONE sample except r9 leaves `CI_lo` ≥ 1.0 (leave-one-out `CI_lo` 1.02 to 1.15); **dropping r9, the strongest sample (+1.82 pp), gives [0.97, 1.63]**. The point estimate is stable (1.30 to 1.46 pp across every leave-one-out). The eight sample estimates run **0.72 to 1.82 pp** (r2 is the low one, its own interval [−0.38, 1.72] straddles zero). The bootstrap's own noise is about ±0.01 pp on `CI_lo` (the order in which samples enter the resampler moved it from 1.063 to 1.058 in a re-run). Read it as: *the gain is real and about 1.4 pp; whether it is "≥ 1.0 pp with confidence" depends on which samples you include.* No clustering flag: the top-5 blocks carry 11 % of the positive gain; 1,872 of 2,479 cycles carry a non-zero net.

## Per sample (each judged by its OWN validity rows; none failed, none excluded)

| sample (i mod 10) | rows | NET_C3 [95 % CI] | NET_U [95 % CI] | V4′ G on P1 | V3 edge |
|---|---:|---|---|---:|---:|
| 3 (first) | 9,522 | +1.33 [+0.57, +2.03] | | 0.969 | 2.2 % |
| 5 (extension) | 9,576 | +1.49 [+0.69, +2.25] | +5.33 [+4.81, +5.81] | 0.965 | 2.1 % |
| 1 | 9,588 | +1.18 [+0.43, +1.95] | +4.99 [+4.50, +5.49] | 0.964 | 2.1 % |
| 2 | 8,882 | +0.72 [−0.38, +1.72] | +4.62 [+3.99, +5.25] | 0.945 | 2.0 % |
| 4 | 8,916 | +1.30 [+0.30, +2.22] | +5.19 [+4.62, +5.77] | 0.944 | 1.9 % |
| 6 | 8,893 | +1.57 [+0.75, +2.43] | +5.31 [+4.75, +5.91] | 0.946 | 2.0 % |
| 8 | 8,913 | +1.48 [+0.47, +2.43] | +5.60 [+5.04, +6.14] | 0.943 | 2.1 % |
| 9 | 9,690 | +1.82 [+1.03, +2.57] | +5.68 [+5.17, +6.19] | 0.967 | 2.2 % |

Every sample: V1 (pin), V3 (≤ 5 % edge), **V4′ (G ≥ 0.90 on its own batch-1 replay rows, 0.943 to 0.969)** and V5 (0 differing fields over its first 300 rows) PASS; V2 carried. The first sample's validity was recomputed, not copied.

## Secondary (U row, FRESH samples only): **U-GO** — the fallback's false decodes are the decision

**NET_U = +5.25 pp [+5.05, +5.46]** (64,455 rows) ⇒ U-GO (a replication check: the union cannot lose a row). **The mandatory cost: on the 27,571 G-fail rows C3 recovered the sent payload on 3,382 and returned a CRC-valid payload that is not the sent one on 1,567** (5.68 % of G-fail rows, 2.43 % of all rows): **0.46 wrong payloads per correct recovery**, reproducible across samples (sample 5: 0.42; sample 1: 0.40). Part of the 1,567 may be genuine other messages at the position; not separated. A fallback that buys 5.2 pp at that rate must be gated in the step-3 spec.

## Descriptives (fresh samples pooled; not verdicts)

- **C1 −7.64 pp**, **C3\* +1.92 pp**, C3 +1.37; C3 gains 3,382 (5.25 %) / losses 2,498 (3.88 %); C3\* 3,580 / 2,340. The coherent orders matter (C1 alone is far worse than G) and the estimator leaves about 0.5 pp (C3\* − C3) on the table. Complementarity as before: C3 gains where the live path missed and loses where G reads well.
- **Sign-corrected OSD** (Amendment 2 arms): GO vs G **+0.051 pp [+0.033, +0.073]**: **33** true recoveries on 27,571 BP-fail rows against **1,846** CRC-valid wrong payloads; C3O vs C3 **+0.258 pp [+0.216, +0.301]** (166 true, 212 wrong); no negated call returned path 0. A corrected OSD at WSJT-X's positions is a very small lever and an expensive one in wrong payloads.

## The OSD-OFF confirmation (NHARD-REP Amendment 3, fresh cycles `i mod 10 == 5`, arms N40B and N0B on the same binary)

**Fresh sample alone: NET_0 = +0.079 pp [+0.029, +0.141] ⇒ O-GAIN**; **pooled with the first OSD-OFF sample: +0.076 pp [+0.036, +0.123] (621 cycles) ⇒ O-GAIN.** It replicates: K = 9 confirmed decodes gained at `nhard` 0, G = 1 lost; unconfirmed decodes 173 → 147 (0.558 → 0.474 per cycle; band D 4.5 % → 3.0 %); all of the gain is batch 2. Validity PASS (V1′, V2″ both vectors rejected at 0 and P_lo accepted at 40, V3, V4, V5 0 of 310 abandoned; V7 carried from the first sample's pairing control, and here both arms ran on the same binary). The effect is real and tiny (about 0.08 pp, about 10 decodes per 310 cycles); OSD off is not harmful.

## Method, pins, instrument

- **Build and pin:** `origin/main` `be3cc5ac`, shim 20260058, `libft8.dll` `2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365`, equal at the start and end of every extraction and replay. Six new row lists frozen and pinned by LF SHA-256 in `cg_common.SAMPLE_PINS` (`rows_r1/2/4/6/8/9.json`), cycles disjoint from the first sample, the pilot and every other list (asserted in code and tests). Each sample's V4′ manifest was committed by the orchestrator BEFORE its extraction: `07a100ad` (r1), `123be005` (r2), `2598a0c6` (r4), `d02f3330` (r6), `21f1c3ba` (r8), `8cbeaf12` (r9). Amendment 5 itself `04e79355`, committed before any extraction.
- **Supervision:** detached orchestrator with a deadline guard (04:45Z), watchdog, 60 s heartbeat, idempotent steps; no restarts, no crashes, orphan check empty. 85 tests for the extractor work plus the NHARD-REP family, mutants caught (equivalent survivors only); no test `--filter` applies.
- **Order of analysis:** the pooled bootstrap's resampling order is by sample residue (1, 2, 4, 5, 6, 8, 9 after the first sample); a different order shifts `CI_lo` by about 0.005 pp.
- **Limits:** one night and one band; WSJT-X's own positions only (every gain presupposes the candidate search finds the signal); the original audio only; Python cost is not native cost; the 17 % batch-2 live hits are invisible to every arm here; genuine decodes WSJT-X also missed cannot be seen (HK-026). More samples tighten the interval but add no second night.

## For the Architect (nothing is licensed by this report)
Per §6 COH-GO ⇒ step 2 (ROW 0g-2 on today's DLL), then a step-3 build spec (Developer, HK-011; flag OFF by default; offline OFF/ON replay) that must **gate the fallback's wrong payloads** (0.46 per correct recovery). Because the margin is 0.06 pp and the verdict was reached under a QA-authored, unruled Amendment 5, the Architect should rule on Amendment 5 first and decide whether a marginal COH-GO is enough for a build spec.

## Files
Run folders `artefacts/rr_2026-10-06_coh_gain_{r1,r2,r4,r6,r8,r9,overnight}`, `rr_2026-10-06_nhard_rep_osdoff_b`; copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\` (files only, DLL copy excluded). Tracked here: this report, `analysis_multi.json`, `amendment5_overnight_qa.md`, the six row lists, the six manifests, and for the confirmation `osdoff_b_analysis.json`.
