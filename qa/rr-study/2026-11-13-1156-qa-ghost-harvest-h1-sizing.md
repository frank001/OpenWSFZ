# GHOST-HARVEST H1 (sizing smoke on the R&R truth corpus): 0 ghosts in 105 dense cycles, and no decode at all in batches 2, 3 and 5. The pre-registered projection (≥ 60 late-batch ghosts in ≤ 3 h) is not met.

**Written:** 2026-11-13, `date -u` read 11:55:38Z. **To:** Architect, then the Captain. **Authority:** the Captain, "go" (H1, with the Architect's stop rule as relayed: *if the smoke does not project ≥ 60 late-batch (4/5) ghosts within ≤ 3 h of machine time, angle A ends*). **Basis:** `qa/rr-study/2026-11-13-1143-qa-ghost-harvest-h0.md`. Station quiet; no timing compared; nothing frozen; no spec.

## 1. The smoke

- **Corpus:** the R&R battery run `2026-09-29-0d6b193-OFF` (truth: `qa/rr-study/results/2026-09-29-0d6b193-OFF/truth.csv`; audio: `artefacts\rr_2026-09-29_subfeas_off_on\2026-09-29-62e8e74-OFF-captured-audio\owsfz\wav`, the daemon's own recording of the played synthetic cycles). **All 105 S7 cycles** (the dense scenario: 2 or 3 injected signals per cycle, 215 truth messages, Q-prefix synthetic calls only), with the cycle before the first as warm-up.
- **Pipeline:** `bin_v2` (v2 tree `59eb5a8f`, `libft8.dll` pin `bbde6eb6…`), arm B's exact flags (Deep, nhard 24, osd-sign-fix 1, cohfb, cohms, cohaudio Both, ungated, late round, CQ-AP off, cohrescand 1, 8 threads). Rc 0.
- **Classification:** a published decode is **true** if its text equals one of that cycle's truth messages, else a **ghost** (the audio holds only the synthetic signals and the audio chain's noise: no third-party signal can be decoded). The match ran inside a script; no text is printed or stored beyond `_qa-scratch\ghost-h1\` (synthetic Q-calls; the nc-dump stays there).

| batch | decodes | true | ghosts |
|---|---:|---:|---:|
| 1 | 173 | 173 | **0** |
| 2 | 0 | 0 | 0 |
| 3 | 0 | 0 | 0 |
| 4 (fallback) | 8 | 8 | **0** |
| 5 (late round) | **0** | 0 | 0 |
| **all** | **181** | **181** | **0** |

- **Cost:** 105 cycles in 178 s (11:51:57Z to 11:54:55Z), **1.66 s median per cycle**; no abandoned cycle.
- **Reading:** the pipeline found 181 of the 215 injected messages and **published nothing else, in any batch**. The residual pass, the third pass and the late round **produced no decode at all** on these clean synthetic cycles (b2 = b3 = b5 = 0): when the signals are well-modelled models, subtraction leaves no residue to decode.

## 2. The projection against the pre-registered rule

- **Point estimate: 0 ghosts in 105 cycles, so 0 projected for any horizon.** Batches 4 and 5 specifically: 8 decodes (all true) and none.
- **What is on disk (counted, not assumed):** S7 truth cycles with audio, union over every R&R run: **2,415 distinct stamps** (of 4,855 truth cycles; the others have no recording on disk). All of them would take **≈ 67 min** (2,415 × 1.66 s), so **machine time is not the limit; the corpus is.** The 2,415 are about 23 recordings of the same 105 scenes (the battery's seeds repeat across runs), so ghosts from them are strongly correlated, not independent draws.
- **Upper bound, for completeness:** 0 events in 105 cycles gives a 95 % upper bound of 3 / 105 = **0.029 ghosts per cycle (all batches)**; over the 2,415 cycles that is at most ≈ 69, and only if every ghost were a late-batch one, which this smoke contradicts (batch 5 produced nothing; batch 4's 8 decodes were all true). Within 3 h (≈ 6,500 cycles of this kind, more than the corpus holds) the bound is not the relevant number.
- **Verdict on the registered rule: it is not met.** The projection is 0; even the generous upper bound needs every ghost to land in batches 4 and 5 and the same 105 scenes to be independent draws, and neither holds. By the rule as relayed, **angle A's harvest route ends here.**

## 3. Why the corpus gives nothing, and what that says (for the Architect)

- The ghosts that matter for the late rounds are made **after subtracting real signals** whose models do not fit (fading, drift, transmitter shape: the SUB-FEAS and CS-CEIL findings). Synthetic signals are the model, so subtraction is clean and the late passes are empty (b2 = b3 = b5 = 0 here, against 1,215 / 103 / 190 confirmed decodes in those batches on the real night).
- **R&R S5** (signal-free) has recorded 0 false positives in earlier batteries (`2026-10-08-5989f5e` report: FP 0 of the S4 + S5 pool), consistent with this.
- The injection route of H0 §3 (synthetic signals over reversed real clutter) shares the same limit: the injected signals are clean models. It would add the real clutter but not the real signals' model mismatch, which is where the late-batch decodes and their residue come from. I did not run it; I would not expect it to change the count, and I have no data that says it would.
- **What would produce the right ghosts is real signals**: the real nights (arm B: 3 of 500 cycles had a tested-absent new decode under v2; 16 of 53 not-corroborated testable late decodes read absent on O). Their truth is unknown (not-corroborated is not false), which is the problem the harvest was meant to remove.

## 4. State

H1 done; nothing frozen, no spec, no PC window used beyond 3 minutes of replay. Files in `_qa-scratch\ghost-h1\` (selection, truth, run outputs; the nc-dump holds synthetic Q-call texts only) and `ghost-h0\`; `ta-res\`, `ta-check\`, `ta-mask\` kept. **The Architect rules on the stop rule; the Captain decides.**
