# RULING: SUB-FEAS Stage B, item B2 (pruned freq_search). ACCEPTED; batch 2's median moves from 6.7 s to 2.4 s (replay)

- **From:** Architect. **To:** QA (owner). cc Captain, Developer. **Date:** 2026-10-04 02:20Z by `date -u` (HK-017).
- **Spec:** `qa/rr-study/2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md` §5h (Amendment 5 and its additions: abandoned cycles count as T2 = +∞; a PASS is read against 2.95 s − k_PC).
- **Build under test:** Developer `feat/sub-feas-stage-b` `aab18b75` (pushed as a branch; not merged), shim **20260059**, `libft8.dll` `2535dec1…`. First build `a8014b3c`: its native fit differs (a refactor and a length guard), but QA measured it **bit-identical** to `aab18b75` on all 3 716 E1 signals.
- **Evidence:** QA's messages of 2026-10-03 22:46Z (E2/E3/R3) and 2026-10-04 02:19Z (T2′/R1′/R4′). Artefacts `artefacts/20261004_b2_e2_e3_aab18b75/`, `artefacts/rr_2026-10-03_t2prime_stageA-main/`, `…_B2/`. I checked `median_t2_s`, `abandoned_inf`, `population` and `verdict` in both `t2prime_rows.json` files myself (HK-018/HK-022): they match QA's report.
- `git diff --stat -- src/ native/` of this ruling: empty. Aggregates only (HK-037).

## 1. Verdict

**B2 ACCEPTED. Stage B stops at B2** (the §5h stop rule: the first item after which E2, E3, R1′, R3, R4′ and T2′ all pass). **B3 and B1 are not built.**

| Row | Result |
|---|---|
| E2 equivalence | PASS: dt and df 3 629/3 629 identical, ḟ 3 628/3 629 (one adjacent step), residual energy 161/161 cycles (max 0.000 dB); 3 628/3 629 fitted signals **bit-identical** |
| E3 no loss | PASS: residual decodes 795 = 795 (ratio 1.0000; every cycle equal) |
| R3 stability | PASS: 0 AV, 0 contained, 0 exceptions |
| R1′ max whole call | PASS: **3 546 ms** (Stage A in the same session: 11 510 ms; bar 13 000) |
| R4′ abandon at 8 workers | PASS: **0.0 %** (Stage A: 1 of 1 075) |
| **T2′ median `T2_replay`** | **PASS: 2.424 s** (bar 2.50; Stage A same session **6.737 s**). p5 1.440, p95 2.843, max 3.578 s. Share of cycles ≤ 2.95 s: **98.8 %** (Stage A: 2.4 %) |
| T′ (4 workers, report-only) | **not run.** Run it once before the merge, report-only, for the other-hardware record |

## 2. What it means, and what it does not

- **Batch 2 now lands in time on the replay.** 98.8 % of cycles have T2 ≤ 2.95 s. The residual pass got about 2.8× faster at the median, with output that is bit-identical in practice.
- 🔴 **"Same-slot answerable" is NOT established.** The condition is median T2 ≤ 2.95 s − k_PC. The median leaves **0.526 s** for keying latency. k_PC is **unmeasured**: K1 found no CAT events; K2 run 1 was blind (no onset detected); and the Captain has **parked** keying latency for a real-radio design (2026-10-03 ~23:3xZ). The T2′ pass is therefore "fast enough if keying takes under about 0.5 s", nothing more.
- **Replay, not live:** the 09-30 night's audio, 8 workers, this PC, one session. QA could not certify that VLC was closed (it is not on the guard list). Both builds ran under the same conditions, so the comparison holds. The absolute figures carry that caveat. On air, the 09-30 night's T2 median was 5.71 s against this replay's Stage A 6.74 s: the replay is, if anything, slower than live.
- **The margin is narrow on the bar (0.076 s) and wide on the condition** (98.8 % of cycles ≤ 2.95 s). The bar was set deliberately below the condition, to leave room for k.

## 3. Predictions scored (ledger updated in the same edit)

| # | Prediction | P | Class | Outcome |
|---|---|---:|:---:|---|
| SB1 | B2 passes E2 and E3 on its first build | 0.60 | H | ✅ **HIT**. `a8014b3c` is bit-identical to `aab18b75` on all 3 716 E1 fits, so E2/E3 describe it too. E2/E3 were not run on `a8014b3c` directly, which is a limit, stated |
| SB2 | median `T2_replay` ≤ 2.50 s after B2 alone | 0.40 | H | ✅ **HIT** (2.424; narrowly) |
| SB3 | per-fit median at 8 workers ≤ 700 ms after B2 | 0.50 | H | **UNSCORED.** There is no acceptance-grade per-fit figure (the Developer's 649 ms was on a loaded PC). QA runs `fitprofile` on an idle PC (≈ 5 min) when one is free, and it is scored then |
| SB4 | T2′ passes after at most two items | 0.50 | H | ✅ **HIT** (one item) |

**Note on calibration:** SB2 at 0.40 was priced off my own rough arithmetic (≈ 2.4 s if step 1 fell to a tenth). That arithmetic landed almost exactly: 2.424 s. That's one data point, not a trend.

## 4. Next

1. **Merge:** QA's call under the Captain's session delegation (2026-10-03 23:38Z). **Step 4 merges first** (shim 20260058); B2 then rebases or merges onto it, takes the next free shim, and rebuilds its binaries. **Before B2's merge:** the T′ report-only run and SB3's `fitprofile` (both ≈ minutes, practical load acceptable), plus the usual pre-merge gates.
2. **Re-evaluation the Captain asked for at this ruling** (`todo-early-residual-pass-after-stage-b.md`): an early residual pass on #122 step 4's 13.0 s window. **My re-evaluation:** with B2, the median already sits under the 2.95 s condition. An early residual pass would add about 2 s of margin for keying, but it carries the decode-rate unknown (do the residual extras survive a shortened window?) and the question of one residual pass per cycle or two. **Recommendation: do NOT pursue it now.** The gating unknown is keying latency, not residual speed. Once a real-radio keying measurement exists, k decides it: k ≲ 0.4 s means no early residual is needed; a larger k makes it the lever. It goes back to the to-do list with that trigger, and the Captain decides.
3. **The batch-2 → auto-QSO choice** stays parked (Captain). B2 makes the option real **only if** k turns out small. The automation stays fenced from batch 2 (P-5).
