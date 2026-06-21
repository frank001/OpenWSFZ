# D-009 Gate-Isolation Ablation — Results

**Date:** 2026-06-21  
**Branch:** fix/d009-fp-callsign-filter  
**Architect decision:** dev-tasks/2026-06-21-d009-ablation-decision-arch.md  
**Developer handoff:** dev-tasks/2026-06-21-d009-ablation-dev.md  

## Ablation table

| Config | K | corr/nhard | co_channel % | co_channel_sweep % | P15 (Δ5 Hz) | P16 (Δ7 Hz) | S5 FP/slot |
|---|---|---|---|---|---|---|---|
| cfg1 | 1 | off | 45.7% (16/35) | 80.0% (48/60) | 0%  (0/10) | 80%  (8/10) | 0.692 (83/120) |
| cfg2 ⚠️ | 10 | off | 12.2% (5/41) | 44.2% (53/120) | 15%  (3/20) | 25%  (5/20) | 0.042 (5/120) |
| cfg3 (ref) | 10 | on | 34.3% (12/35) | 86.7% (52/60) | 50%  (5/10) | 70%  (7/10) | 0.042 (5/120) |
| cfg4 | 5 | off | 48.6% (17/35) | 75.0% (45/60) | 0%  (0/10) | 60%  (6/10) | 0.700 (84/120) |

**⚠️ cfg2 data-quality note:** truth.csv for cfg2-s7 was appended from two harness runs in different sessions — the prior session ran with scenario `trials=10` (then in effect); the current session uses `trials=5`. As a result cfg2 has P0/P1 at K_scenario=5 (5 unique cycles each), P2 at K_scenario=7 (7 unique cycles, 21 rows), and P3–P20 at K_scenario=10 (10 unique cycles each, 20 rows), versus K_scenario=5 throughout for cfg1, cfg3, cfg4 (35 and 60 unique injections respectively).  
**Impact on co_channel (P0–P2):** injected count is 41 vs the expected 35 at K=5; the 6 extra injections are from P2 extra cycles. The 5 matched decodes are from P0/P1 (5 unique cycles each) so the K=5-equivalent rate is ≈ 5/35 = **14.3%** — directionally identical to the reported 12.2%.  
**Impact on sweep (P15–P20):** 120 injections (K_scenario=10 × 2 msg × 6 parts) vs 60 at K=5; the 53 matches represent a genuine K=10 measurement (44.2%) — more statistically stable than the K=5 configs but not directly cross-comparable. A K=5 sub-sample would yield ≈ 44% (same rate, half the injections). **The direction is unaffected**: cfg2 sweep (44%) is far below cfg3 sweep (87%) under any K_scenario normalisation.

## Decision-rule evaluation

**SHIP criteria (pre-committed, from §3 of ablation-decision-arch.md):**
- co_channel_sweep ≥ 89%
- co_channel (P0–P2) ≥ 45%
- S5 FP ≤ 0.10/slot

Ship the **simplest** qualifying config (fewest active gates, then lowest K).

| Config | sweep ≥ 89%? | co_ch ≥ 45%? | FP ≤ 0.10? | Verdict |
|---|---|---|---|---|
| cfg1 (K=1, off) | ❌ | ✅ | ❌ | ❌ no |
| cfg2 (K=10, off) | ❌ | ❌ | ✅ | ❌ no |
| cfg3 (K=10, on) | ❌ | ❌ | ✅ | ❌ no |
| cfg4 (K=5, off) | ❌ | ✅ | ❌ | ❌ no |

## Reading

**Outcome: no config ships. Trade is irreducible. Escalate to Captain per ablation-decision-arch.md §5.**

### (a) K floor is the FP suppressor — corr/nhard gates are not

K_MIN_SCORE_PASS2 = 10 drops FP to 0.042/slot regardless of whether corr/nhard gates are on (cfg3) or off (cfg2). K floor = 1 (cfg1) or 5 (cfg4) leaves FP at 0.692–0.700/slot even with the C# text rules (A/B/C) active. The architect's hypothesis stated in §3 of ablation-decision-arch.md is **confirmed**: the pass-1 score floor, not the corr/nhard gates, carries the FP suppression work.

### (b) The architect's strong prior (Config 2 wins) is refuted

Config 2 (K=10, gates OFF) does not recover co_channel_sweep. Sweep drops to 44% at K=10 without gates — far below the 89% threshold and below every other config. The corr/nhard gates contribute ~43 pp of sweep recovery at fixed K=10 floor (cfg2 44% → cfg3 87%). Removing the gates to simplify the decoder would surrender most of the co_channel_sweep recovery.

Co_channel (P0–P2 equal-stack) follows a similar pattern: gates OFF at K=10 yields 14% (cfg2); gates ON recovers to 34% (cfg3). Both remain below the 45% threshold, but the gates provide a meaningful ~2.4× lift on the hardest equal-SNR recovery family.

### (c) All configs fail — irreducible trade, escalate to Captain

No config in the 2×2 factorial satisfies all three criteria simultaneously:

- **Sensitivity end (cfg4, K=5 gates OFF):** best co_channel (48.6% ✅), moderate sweep (75% ❌), catastrophic FP (0.700 ❌). The K floor is too low to suppress noise FPs.
- **Trust end (cfg3, K=10 gates ON):** moderate co_channel (34.3% ❌), near-threshold sweep (86.7% ❌ by 2.3%), acceptable FP (0.042 ✅). The closest config to passing.
- **cfg1 (K=1 gates OFF):** co_channel passes (45.7% ✅), but sweep (80% ❌) and FP (0.692 ❌) both fail.
- **cfg2 (K=10 gates OFF):** FP passes (0.042 ✅), but sweep (44% ❌) and co_channel (14% ❌) fail.

Per the pre-committed rule in ablation-decision-arch.md §5: the trade is irreducible. Clean per-config numbers for Captain escalation:

- **Sensitivity end:** cfg4 (K=5, gates off) — 48.6% co_channel, 75% sweep, 0.700 FP/slot
- **Trust end:** cfg3 (K=10, gates on) — 34.3% co_channel, 86.7% sweep, 0.042 FP/slot

The sweep shortfall in cfg3 (86.7% vs 89% threshold; 1 additional trial in 60 would close the gap) is borderline and may be within run-to-run variability at K=5. However, the co_channel shortfall (34.3% vs 45%; 3–4 additional matches in 35 needed) is structural — it reflects the gating stack's ~20 pp cost on the equal-SNR co-channel family documented at shim 20260028/K=1 in ablation-decision-arch.md §2.

No further K probing required per §5.

---

**NFR-021 compliance:** No real callsigns appear in this document.  
S5 FP counts are numeric only; S7 uses Q-prefix synthetic callsigns (MSG-01/02/03).  
