# RULING — SUB-FEAS speed redesign, Stage A acceptance

- **Date (UTC):** 2026-09-30 13:58Z (mechanically derived, `date -u`, HK-017)
- **Author:** Architect. **Reads:** QA's report `qa/rr-study/results/2026-09-30-sub-feas-speed-stage-a-acceptance/report.md`
  (`qa/sub-feas` `b4f8d22d`, local), against spec `2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md`
  incl. Amendment 1 and the clamp note (`63660730`).
- **Build under test:** `feat/sub-feas-speed-redesign` `ca0bcd9b`, shim `20260056`, `libft8.dll` `ee00d118…990e4c`
  (actual = pinned), base DLL `5a6a4dc0…e38c5`. WSJT-X closed (asserted). Harness `8d7eadb3`.

## 1. Verdict: the registered outcome stands — Stage A FAIL, on R2′ alone

I read each row in the report's Section 4 tables, not in the summary message.

| Row | Bar | Result | Ruling |
|---|---|---|---|
| E1 | 100 % bit-identical | 3 878 / 3 878 rows, at 14 and at 4 workers; 161 cycles per Amendment 1 | **PASS** |
| R0 | as §8.1 | 20/20 × 3 | **PASS** |
| R1′ | max ≤ 13 000 ms | max **8 650 ms**, 0/905 over (§8.1: 16 309, 765 over) | **PASS** |
| R2′ | max ≤ 10 000 AND p95(H) ≤ 6 000 | max 8 650 (pass); **p95(H) 6 410.8** | **FAIL** (by 410.8 ms, 6.8 %) |
| R3 | 0 / 0 / 0 | 0 AV, 0 contained, 0 bad exits in 25 invocations | **PASS** |
| R4′ | abandon ≤ 5 % over H | **0 / 605** (§8.1: 531) | **PASS** |
| R5′ | flag-OFF ≤ 1.05× same-session base | 1.003 / 0.998 / 1.002 (noise floor 1.5 %) | **PASS** |
| R6 | ≤ 13 000 ms, synthetic | 6 186 ms | **PASS** |
| R7 | descriptive | +4.53 per cycle (was +0.60): the pass now **completes**. Not a decode-rate result | — |
| T | report only | 4 workers: median 11.5 s, 337/605 abandoned, **hard bound held** (max 12 095 ms) | A5 verified on real audio |

No bar is moved. Per the spec's registered order, a Stage A that fails only R2′ goes to **Stage B, item by item**.

## 2. What the data says about the miss

- **The tail is the signal count, and it rises in steps.** At 14 workers, 15–28 signals is two waves and 29+ is three.
  The 21 heavy cycles with 29–31 signals (3.5 % of H) have per-count medians of 7.1–8.4 s. The 28-signal cycles
  (median 6 377 ms) are what put p95 just over 6 000.
- **One fit costs about 2× its single-thread time when 14 run at once** (QA: about 2.5 s against the Developer's
  1.26 s single-thread; the cause is **not measured**, and memory-bandwidth or cache contention is only a hypothesis).
  This is where **my arithmetic was wrong**: I assumed per-fit cost is flat in the worker count. Adding workers only
  shortens a wave by less than their count suggests.
- ⇒ **Levers that cut per-fit cost (or per-fit memory traffic) help every cycle.** A lever that only packs work into
  fewer waves helps the 3.5 % above 28 signals. I agree with QA's Recommendation 3.

## 3. Next step (registered path, plus QA's one-step refinement, accepted)

1. **Before choosing a Stage B item**, the Developer re-runs `Ft8.FitProbe time` on the **candidate** DLL: single worker
   **and** 14 concurrent workers. The per-phase map exists only for the base build (step 1 ≈ 890 ms, step 2 ≈ 870 ms,
   single-thread), and the concurrency penalty is unmeasured. That is cheap, and it ranks B1/B2/B3 by evidence.
2. Then Stage B goes item by item in the order the profile supports (default B1 → B2 → B3). Each item is accepted on E2
   (equivalence) and E3 (no residual-decode loss), then re-timed on the R-rows. Stop at the first item that passes R2′.
3. **The alternative is the Captain's, not mine to take:** in the §8.1 spec R2 was designated a *Captain-adjustable
   margin*. Accepting 6.4 s would end the speed work at Stage A. I recommend **against** it for now. Row T shows a
   4-worker machine already abandons 56 % of heavy cycles, so the per-fit cost, not the bar, is what decides whether
   this feature works on anything but this machine.

## 4. Predictions scored (spec §5, Amendment 1)

| # | Prediction | P | Class | Outcome |
|---|---|---:|:---:|---|
| P1 | E1 passes on the first Stage A build | 0.60 | H | ✅ **HIT**: E1 ran once on `ca0bcd9b` and passed (3 878/3 878). No failed earlier E1 is on record |
| P2 | Stage A alone meets R2′ | 0.55 | H | ❌ **MISS**: p95(H) 6 410.8 > 6 000. Cause: per-fit cost roughly doubles at 14 workers, which my arithmetic assumed away |
| P3 | Stage A alone meets R4′ | 0.60 | H | ✅ **HIT**: 0 / 605 |
| P4 | M2 + M3 move the flag-OFF median < 5 % either way (M1 deferred) | 0.80 | H | ✅ **HIT**: within ±0.3 % |

3/4 HIT. One arm is one arm.

## 5. Still open before any merge (unchanged by this ruling)

- The flag-OFF control re-run on the new native build (tasks 10.5; **needs the Captain's go**).
- The base change `feat/sub-feas-native-subtraction` is unmerged; base §7 (sustained stability) and §8.2/§8.3 are open.
  **§8.2 is the only thing that can say whether R7's extra decodes are real.**
- FR-077 merge order with the config-save change.
- The flag stays **OFF** by default and in every live run.
- `src/`/`native/` diff of this commit: none (HK-011).
