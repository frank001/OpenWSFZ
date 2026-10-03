# RULING: #122 gate 4a report (released catch figures). An early decode catches about 98 % up to 2 s early

- **From:** Architect. **To:** Engineer (owner). cc QA, Captain. **Date:** 2026-10-03 ~14:35Z (HK-017, `date -u`).
- **Report:** `qa/rr-study/results/2026-10-03-122-gate4a-truncation-replay/report.md`, `eng/122-gate4a` `df4ec892` (local, not pushed). Outputs: `artefacts/20261003_1139_122_gate4a_truncation_replay/`.
- **Spec:** `2026-10-03-1015-…-gate4a-truncation-replay.md` + Amendment 1. **Earlier rulings:** `2026-10-03-1420-…-v2-fail-ruling.md` (V2 FAIL on P; §4a: the Captain released the figures at 14:22Z).
- `git diff --stat -- src/ native/`: empty. Aggregates only (HK-037).
- 🔴 **Every figure here carries the report's label:** *Descriptive. From gate 4a, whose V2 failed on P (1 074/1 075; R, X17, X80 N/N); released by the Captain's decision, not a gate PASS.*

## 1. Verdict on the report

**ACCEPTED as written.** No changes requested.
- **Checked myself (HK-018/HK-022):** V2, V4′, `C(1.0)`/`C(2.0)` and `S_unc(1.0)` for P, R and X17, and the TR lines, all against `analysis_released.txt`. They match the report.
- The timing overlap is handled as I scoped it: X17's `t(x)`/`G(x)` are labelled. Nothing else depends on timing.
- Registered verdicts stand: **V2 FAIL on P**; V0, V1, V3, V5 PASS; **V4′ PASS on all four** (old V4 FAIL on all four, reported, not used).

## 2. What the figures say (descriptive)

| Corpus | C(1.0) | C(2.0) | C(2.5) | S_unc(1.0) /100 | S_corr(1.0) /100 | G(x) |
|---|---:|---:|---:|---:|---:|---|
| P (40 m, 09-30) | 0.991 | 0.984 | 0.963 | 0.27 | 0.87 | ≈ x up to 2.0 s |
| R (40 m, 09-22) | 0.992 | 0.983 | 0.957 | 0.25 | 0.64 | ≈ x |
| X17 (17 m) | 0.993 | 0.988 | 0.960 | 0.29 | 0.53 | ≈ x (labelled) |
| X80 (80 m, thin) | 0.994 | 0.987 | 0.960 | 0.47 | 0.26 | ≈ x |

1. **An early decode at 13.0 s (x = 2.0) already has ≈ 98 % of what the full window gives, on every corpus and every band tested.** That holds at 14.0 s (x = 1.0) too, at ≈ 99 %. The early decode costs about as much time as the full one (`t(x)` ≈ `t(0)` up to x = 2.0), so **those decodes would appear about x seconds earlier**: ≈ 2 s at x = 2.0, against the 2.36 s guard. This is the largest latency lever in #122 by a factor of about six (step 3 saves ≈ 0.32 s).
2. **Who is missed** is what the mechanism predicts. The weakest band (D, ≤ −16 dB) is at 0.94–0.95 at x = 2.0. Late starters (DT > 2.5 s, our convention) are at 0.80. Those are few (95 of 20 175 on P). The final decode at 15 s still gets them.
3. **`x*` is none on P, R and X17, as registered**, and 2.5 s on X80 (a thin corpus, not a firm point). `C` passes at every x. What fails is my `S_unc` ≤ 0.10 per 100: the early decodes add 0.17–0.47 uncorroborated decodes per 100. The verdict is not rewritten. For scale (descriptive, not a re-grade): the final decode's own uncorroborated rate is 1.45–3.28 per 100.
4. **`S_corr`: early decodes that the full window does NOT give, and that the live WSJT-X also decoded,** are 0.26–1.29 per 100. A shorter window finds some real signals the full window misses. My guess is that the cut removes interference that arrives late in the slot; **that is not checked**. 🛑 **No decode-rate claim:** replay, the same caveats as every replay, and corroboration by the live WSJT-X on these nights only.
5. **The V2 failure, in proportion:** one decode in 20 175 (P) was lost from the final decode when early decodes ran first. Whatever its cause, a step-4 build must not lose final decodes, so its spec carries a requirement for it (§4).

## 3. Predictions scored (ledger updated in the same edit)

| # | Prediction | P | Class | Outcome |
|---|---|---:|:---:|---|
| TR1 | `C(1.0)` on P ≥ 0.85 | 0.70 | H | ✅ HIT (0.991) |
| TR2 | `C(2.0)` on P ∈ [0.55, 0.85] | 0.55 | H | ❌ **MISS** (0.984, far above) |
| TR3 | `S_unc(1.0)` on P ≤ 0.50 per 100 | 0.70 | H | ✅ HIT (0.27) |
| TR4 | \|C_P(1.0) − C_R(1.0)\| ≤ 0.05 | 0.70 | H | ✅ HIT (0.001) |
| TR5 | V0–V4 pass the first time | 0.65 | H | ❌ MISS (scored 14:20Z) |
| TR6 | X17, X80: \|C_X(1.0) − C_P(1.0)\| ≤ 0.08 | 0.60 | H | ✅ HIT (0.002, 0.003) |

**Lesson (TR2, and the original V4 margin):** both rested on one premise, that the synthetic edge run's tail tolerance (≈ 0.89 s at −8/−16 dB) carries over to real signals. It does not: real decodes are mostly far above threshold, and FT8's LDPC recovers them from a much shorter window. **I carried a synthetic threshold result over to a population whose SNR distribution I had not looked at.** Check the population before transferring a threshold.

## 4. What this decides (spec §6), and what goes to the Captain

Spec §6's branches, applied as written:
- `x*` does not exist under the registered rule, and the reason is `S_unc` ⇒ *"Step 4 then needs a confirmation rule (show only what the final decode keeps, or mark early rows), and that is a design question for the Captain."*
- V2 failed on one decode ⇒ *"'loses nothing by construction' is false"* until D1–D3 say otherwise.

**My recommendation: step 4 is worth a build spec.** I would write it when the Captain asks, with three choices for him:
1. **Confirmation rule for early-only decodes**, which are 0.2–0.5 per 100 uncorroborated:
   - **(a) keep** them, as WSJT-X's progressive display presumably does (step 1's EL1 would show whether WSJT-X publishes early at all);
   - **(b) show them, then drop any the final decode does not confirm**;
   - **(c) mark them** until confirmed.

   I recommend **(b)** for the automation and **(a) or (c)** for the panel.
2. **Cut point x:** 1.0 s (≈ 99 % caught, ≈ 1 s earlier) or 2.0 s (≈ 98 %, ≈ 2 s earlier). I recommend **2.0 s**. It is what turns #122's "app latency uses about a quarter of the window" into "decodes are mostly on screen before the slot ends".
3. **Panel-only first, or with the automation:** the automation needs step 2 (progressive batches). Panel-only can go first.

**Requirements any step-4 spec carries, whatever he chooses:**
- **The final decode must be protected from the early decode's shared state,** for example run with the hash table as it stood before the early decode. That requirement holds whatever D1–D3 find. The D1–D3 outcome only decides whether it is the cause of the V2 miss.
- **The CPU interaction with the previous cycle's residual pass (flag ON) is measured on the station.** This replay had no residual pass running.
- `src/` work, HK-011, a separate Developer session.

**D1 (≈ 10 min): still recommended, for its own reason.** Whether the flag-OFF decode reproduces itself bears on every replay acceptance, Stage B's T2′ included, not only on step 4. Order and timing are the Captain's (the global hold stands until he lifts it).

**Interaction with Stage B / batch 2:** an early decode also starts the residual pass earlier only if the residual pass is allowed to run on the partial window. That is a decode-rate question, not part of this. The batch-2 arithmetic in the roadmap §1 is unchanged.
