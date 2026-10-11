# REFERENCE-SET W pilot: result (QA)

- **To:** Architect, cc Captain. **From:** QA. **Date:** 2026-10-11 03:22Z (`date -u`). **Run:** 2026-10-11 00:45:30Z to 03:21:38Z (9,367 s), 60 cells (12 blocks x W 0/4/8/16/40), two cells at a time.
- **Protocol:** `qa/rr-study/refset/wpilot/PROTOCOL.md`, frozen in `b69701bb` before the first real decode. **One disclosure:** `analyze_wpilot.py` was written after the run started but before any cell file was read; it implements §4 and §5 of the protocol as code and nothing else.
- **Pins:** harness DLL `a14fe354b88dbc30c4c13fb2610a8d16769684afec70b826bc30756591fd7610` at start and end (P-V0 pass), live `ALL.TXT` SHA-256 `382b23b2…3653` unchanged, 864 WAV hashes matched the inventory, self-test passed. Aggregates only (HK-037); `wpilot_result.json` is committed beside this note.

## Validity rows

| row | result |
|---|---|
| P-V0 pins | PASS |
| P-V1 same live reference in all five W cells | PASS (6,755 live rows, 418 hashed, in every W) |
| P-V2 no deadline abandonment | **FAIL in 7 cells, 2 blocks**: block 0 (W 16, 40) and block 9 (all five W); 12 abandoned residual passes in total, 0 contained exceptions. Two cells ran at once (8 threads each). Read both ways below. |
| P-V3 self-test | PASS |

## Result (pooled over the 12 blocks; ratio of sums; block bootstrap 10,000, seed 1)

| W | live hashed rows | **A_hashed_exact** | A_hashed_key | A_nonhashed | A_all | extra non-hashed | extra hashed |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 418 | 0.6770 | 1.0000 | 0.9983 | 0.9984 | 0.0013 | 0 |
| 4 | 418 | 0.7679 | 1.0000 | 0.9983 | 0.9984 | 0.0013 | 0 |
| 8 | 418 | 0.8014 | 1.0000 | 0.9986 | 0.9987 | 0.0013 | 0 |
| 16 | 418 | 0.8373 | 1.0000 | 0.9983 | 0.9984 | 0.0013 | 0 |
| 40 | 418 | **0.8971** | 1.0000 | 0.9986 | 0.9987 | 0.0013 | 0 |

Difference from W = 40 on `A_hashed_exact` (95 % block bootstrap): W 0 **-22.0 pp** [-32.5, -12.9]; W 4 -12.9 pp [-22.8, -6.1]; W 8 -9.6 pp [-19.5, -2.9]; W 16 -6.0 pp [-16.4, 0.0].

## The rule, as frozen

1. **W\* = 40** (no W below 40 is within 1 pp of W = 40's hashed-row agreement); "none within 1 pp ⇒ W = 40 and the Architect rules". The §5.4 resolution note does not apply (W\* = 40).
2. **Non-hashed dependence flag: not raised.** `A_nonhashed` moves by at most 0.03 pp across W (CI [-0.10, 0.00] pp). RS-V2's non-hashed basis is safe on this evidence.
3. **RS-V2 reading at W = 40 (not gating):** 99.86 % of live non-hashed rows reproduced, 0.13 % extra, against the frozen bar of at least 99 % / at most 1 %: **the bar is met with a wide margin on blocks with a fresh hash table.**

## Sensitivity (the same rule, same outcome)

| reading | blocks | W\* | within 1 pp of W 40 | non-hashed flag | `A_hashed_exact` W 0 .. 40 |
|---|---:|---:|---|---|---|
| all | 12 | 40 | {40} | no | 0.677, 0.768, 0.801, 0.837, 0.897 |
| first scored cycle ≥ 6 h after the live start | 9 | 40 | {40} | no | 0.666, 0.765, 0.788, 0.833, 0.897 |
| no abandonment in any cell of the block | 10 | 40 | {40} | no | 0.646, 0.762, 0.798, 0.818, 0.893 |

## What the data say, and what they do not (for your ruling)

1. **History changes how a hashed call is RENDERED, never whether the row is decoded.** `A_hashed_key` is 1.0000 for every W, including W = 0: every live hashed row is reproduced by key; only the text (`<CALL>` resolved or `<...>`) differs. The comparison key collapses `<...>`, so **every key-matched metric in the reference set (legs A to D) is independent of W** on this evidence. W only matters if the rendered text of hashed rows is itself scored.
2. **`A_hashed_exact` is still rising at W = 40** (+6.0 pp from 16 to 40, +3.6 pp from 8 to 16, +3.4 pp from 4 to 8, +9.1 pp from 0 to 4) and sits at 89.7 %, not near 100 %. The live process had hours of history. So W = 40 is **not converged**: a W of a few hundred cycles would be needed to approach the live rendering. The rule's reference point (W = 40) is therefore itself an unconverged one: the 1 pp comparison is "within 1 pp of an unconverged value", which only W = 40 can satisfy. I state this plainly because it makes the rule's outcome (W\* = 40) nearly forced, whatever the data.
3. **Limits (stated in the protocol, repeated):** 418 hashed rows, 12 blocks, one night, one band; two-stage call, not the live early/final path; the 2 h eligibility is a judgement; abandonment in 2 blocks (excluding them changes nothing).

## What the Architect needs to rule

- **(a)** W for the corpus: **W = 40 by the rule**. Given point 1, a smaller W would cost nothing for any key-matched metric and shrink the corpus cost (a block of 40 cycles instead of 72 at L = 32: the 11,520-cycle cap then holds 288 blocks instead of 160, and replay time per block drops by 44 %). Your call; I take the rule's W = 40 unless you rule otherwise.
- **(b)** Whether any REFERENCE-SET report scores rendered hashed text. If not, the h12/hash-history behaviour is outside what the set measures, and W can be small.
- **(c)** The abandonment: for the full runs, run with one cell at a time (or fewer threads) so P-V2 holds. I will do so unless told otherwise.

QA's own reading: none of this changes the quota numbers' form; they are recomputed for the W you rule (`n = W + L`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
