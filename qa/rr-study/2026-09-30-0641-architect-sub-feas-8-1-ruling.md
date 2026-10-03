# RULING — SUB-FEAS §8.1 real-band runtime replay

- **Date (UTC):** 2026-09-30 06:41Z (mechanically derived, `date -u`, HK-017)
- **Author:** Architect. **Reads:** QA's report `qa/rr-study/results/2026-09-29-sub-feas-8-1-replay/report.md`
  (`qa/sub-feas` `8bf7abcd`, local), against my spec `2026-09-29-2010-…-spec.md` incl. Amendments 1–2.
- **Build under test:** `2b39cf18`, `libft8.dll` `5a6a4dc0…e38c5` (actual = pinned; self-referential, no independent pin).

## 1. Verdict: the registered outcome stands — FAIL

| Row | Registered bar | Result | Ruling |
|---|---|---|---|
| R0 | \|Δ\| ≤ 1 on ≥ 95 % of pilot, via each archive's producing DLL | 20/20 on all three runs | **PASS**; the timing rows are citable |
| R1 | max ≤ 13 000 ms over H ∪ M | max **16 309 ms**, 765/905 over | **FAIL** |
| R2 | max ≤ 10 000 ms AND p95(H) ≤ 6 000 ms | 16 309 / 14 809 | **FAIL** (not PARTIAL: R1 also fails) |
| R3 | 0 AV / 0 contained / 0 exits | 0 / 0 / 0 | **PASS** |
| R4 | report; > 5 % over H ⇒ "mostly inert on busy bands" | **531/605 = 87.8 %** | flag fired |
| R6 | ≤ 16 000 ms, synthetic | 14 089 ms | **PASS** |
| R7 | descriptive | +0.60/cycle all, per run +1.68/+0.20/+0.04 | no claim, not pooled |

I checked each row's number in the report's own tables (Section 4), not in the summary message. No bar is moved.

## 2. What I accept from QA's reading, and one correction

- ✅ **R1 read jointly with R4 (Amendment 1):** the maxima sit at 13–16 s **because** the cooperative guard fired
  and then overshot. This is two defects: (a) the pass is too slow for a busy cycle (it runs to the deadline in
  87.8 % of H cycles), and (b) the guard is not a wall-clock bound (worst overshoot +3 309 ms, mechanism
  unmeasured). Neither is fixed by moving the budget.
- ✅ **QA's Recommendation 4 is right:** my spec's phrase "mostly inert on busy bands" is too strong. The ON path
  changed the count in 138/905 cycles and was never lower. The pre-registered wording stays in the spec as
  written; this correction lives here (HK-034).
- ⚠️ **R6's allowance did not bound the real-band overshoot** (3 309 > 3 000 ms). R6 stands as registered. My
  lesson: I set an allowance constant for a quantity the build did not measure.
- ⚠️ **Machine not idle** (WSJT-X/jt9 resident). This does not rescue R1: the pass needs several times the budget,
  not a few percent.

## 3. Prediction ledger

My §8.1 spec registered **no** prediction for R1–R4 (the only forecast in it, the "~26 s at 24 signals", was the
design's FFT benchmark, quoted, not mine). **No ledger row to score.** Recorded here so its absence is not read
later as an unscored miss.

## 4. Consequence

- The flag stays **OFF** by default and in every live run. Nothing in §8.1 supports live use; §7 and §8.2 remain
  unsatisfied.
- **Captain, 2026-09-30:** *"go for option 2. more threads, code speedup, remove redundant monitoring from hot
  decode path"*. The speed redesign is specified in
  `2026-09-30-0641-architect-to-qa-spec-sub-feas-speed-redesign.md`. The §8.1 selection and harness are reused
  there as its acceptance instrument.
- `src/`/`native/` diff of this commit: none (HK-011).
