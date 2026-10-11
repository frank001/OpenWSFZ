# REFERENCE-SET W pilot: run protocol (QA, frozen before the first real decode)

- **To:** Architect, cc Captain. **From:** QA. **Frozen:** 2026-10-11 00:4xZ (`date -u` 00:44:20Z when the live-file pin was read; the commit stamp is the authority). **Spec:** REFERENCE-SET §2c item 3 (the pilot and its rule), §2f item 4 (non-hashed rows), on `arch/reference-set`.
- **Go:** the Captain, in the QA window: "start with the W pilot" (after "how long will the W pilot take?" and "only cpu, no wsjt-x needed?").
- **Nature:** a calibration run that sets one number, W (warm-up cycles per block). One night, one chain, one build, subtraction ON. No gain is claimable; nothing here is pooled with anything.

## 1. What is measured

For a block of consecutive cycles from the anchor night, a **fresh process** decodes W warm-up cycles in order (output discarded, so the callsign hash table fills) and then L = 32 scored cycles in order. The scored cycles' output is compared with the **live OpenWSFZ rows of the same cycles**, which the live process produced with hours of hash history. W ∈ {0, 4, 8, 16, 40}.

## 2. Frozen inputs (pins)

| item | value | source |
|---|---|---|
| Build | checkout `421e3ce2` (DI sync 5), `libft8.dll` SHA-256 `a14fe354b88dbc30c4c13fb2610a8d16769684afec70b826bc30756591fd7610`, shim 20260061 | the live night's `arm_config.json`; the driver byte-checks the harness output DLL against it at start AND end |
| Settings | `osdNhardMax` 24, OSD sign fix on, subtraction ON, `subtractionMaxThreads` 8, `kMinScorePass2` 10, `osdCorrThreshold` 0.10 | the STRONG-MISS protocol, from the live run's `arm_readback.json` |
| Decode call | `Ft8Decoder.DecodeTwoStageAsync`, one call per cycle (output already post-plausibility and per-cycle text-dedup) | the STRONG-MISS call; not the live early/final path (stated limit) |
| Audio | `20261009_1752_endurance_run-gathered/owsfz/wav` (OpenWSFZ's own recording = leg A) | the REFERENCE-SET leg A definition |
| Live reference | `20261009_1752_endurance_run-gathered/owsfz/ALL.TXT`, 62,617 lines, SHA-256 `382b23b204173cdb185e4ce6eaab65c23e1ed0c8bd0aa3c1a9166f92d91b3653` | the run's `contents.md` (G1) and recomputed today |
| WAV pins | every WAV of every block is SHA-256-checked against `wavs.jsonl` (the step 0 inventory) before the first decode | inventory |
| Harness | `qa/rr-study/refset/wpilot` (`WPilot.csproj`, `Program.cs`), `--selftest` passes (key collapse, hashed detection, reproduced/extra counts, duplicates, exact-vs-key rendering) | this commit |

## 3. The blocks (frozen)

- Anchor night cycles that pass **every** desk-work check (`valid.jsonl`: 3,628 of 3,630). Valid stretches of one band are cut greedily into non-overlapping tiles of **72 cycles** (40 warm-up positions + 32 scored), giving 50 tiles.
- **Eligibility (a judgement, stated):** a tile is eligible only if its first scored cycle is **at least 2 h after the live process started** (17:52Z), because the live hash table was empty at the start and "the live run had full history" is false for the first hours. 43 of 50 tiles are eligible. Basis: none on file (no figure for how fast the table fills); 2 h is a round number chosen so that every block has several hundred earlier cycles of live history. Sensitivity: the report also gives the result for blocks with first scored cycle ≥ 6 h.
- **Draw:** 12 tiles, `random.Random(20261011).sample` over the eligible tile indices, sorted. The list is `wpilot_blocks.json` (SHA-256 prefix `5e1ed604d4aa49cd`): night 6, twilight 2, day 4.
- For W < 40 the block is the last W warm-up cycles of the tile plus the same 32 scored cycles, so every W sees the **same scored cycles**.

## 4. Metrics (all counted in memory, aggregates only)

Per cell (block, W), over the scored cycles, with the standing key (cycle + text with every `<...>` collapsed to `<HASH>`, whitespace normalised), rows paired per key as a multiset:

| name | definition |
|---|---|
| live rows | rows of the live `ALL.TXT` in the scored cycles; **hashed** = text contains `<`; non-hashed = no `<` |
| `A_nonhashed` | live non-hashed rows reproduced (key match) ÷ live non-hashed rows |
| `A_hashed_exact` (**the rule's metric**) | live hashed rows reproduced **with identical rendered text** (`<CALL>` resolved vs `<...>`) ÷ live hashed rows |
| `A_hashed_key` | live hashed rows reproduced by key (rendering ignored) ÷ live hashed rows |
| `A_all` | live rows reproduced by key ÷ live rows (the RS-V2 reading) |
| extras | replay rows with no live row of the same key ÷ live rows, for all / non-hashed / hashed |
| rendering split | among key-matched hashed rows with different text: live resolved/own `<...>`, live `<...>`/own resolved, both resolved but different |

Pooling: **per W, summed over the 12 blocks** (ratio of sums). Intervals: **block bootstrap**, 10,000 resamples of the 12 blocks, seed 1, percentile 95 %, for each A and for each difference A(W) − A(40) (paired by block).

## 5. The rule (frozen by the Architect; QA only restates it as code)

1. **W\*** = the smallest W in {0, 4, 8, 16, 40} with `|A_hashed_exact(W) − A_hashed_exact(40)| ≤ 0.01` (1 percentage point, absolute, on the pooled point estimates). If none, **W\* = 40 and the Architect rules**.
2. **Non-hashed dependence flag (§2f item 4):** if for any W in the set `|A_nonhashed(W) − A_nonhashed(40)| > 0.01`, the report says "non-hashed rows depend on W" and the **Architect rules before the corpus is frozen**.
3. Both branches carry information, so the rule is not decorative: W\* = 0 says warm-up is unnecessary on this evidence; W\* = 40 says the table matters at the 1 pp level; a flag says RS-V2's non-hashed basis is not safe.
4. **Resolution note (QA's, not part of the Architect's rule):** the report states, for W\*, the 95 % interval of `A_hashed_exact(W\*) − A_hashed_exact(40)`. If that interval reaches beyond ±1 pp the report says "not resolved at 1 pp with 12 blocks" and the Architect decides whether more blocks are needed. The expected hashed-row count is ≈ 25 per block (4.5 % of ≈ 540 rows), ≈ 300 in total; this is a prediction from the inventory, not a bar.

## 6. Validity rows of the pilot itself (mechanical)

| row | predicate | if it fails |
|---|---|---|
| P-V0 pins | every WAV of every block matches its inventory SHA-256; the harness DLL equals `a14fe354…` at start and end of the run | the run is void |
| P-V1 same reference | for each block, the live row count is identical in all five W cells | the run is void |
| P-V2 no abandonment | residual-pass `deadlineAbandoned` count is 0 in every cell | cells with abandonment are reported with and without; the rule is read both ways |
| P-V3 self-test | `--selftest` passes before the run | the run does not start |

Reported, **not gating**: `A_all` and `A_nonhashed` at W = 40 against the §2f RS-V2 bar (≥ 99 % reproduced, ≤ 1 % extra). That bar's basis is SM-V2 (99.91 % / 0.06 %, one continuous process, all rows, 433 cycles); the pilot is the first reading of it on blocks with a fresh hash table.

## 7. Design limits (stated now, repeated in the report)

1. Two-stage call, not the live early/final path.
2. The live process's history grew from empty at 17:52Z; the 2 h eligibility is a judgement.
3. JIT warm-up uses the committed synthetic fixture `synth-qso-01.wav` (Q-prefix calls only), so no real history enters the table from outside the block.
4. Two cells run at once (8 subtraction threads each, 16 cores). Timings are not compared; the abandonment count is the check.
5. One night, one band (40 m), one build; the result sets W for the corpus, it is not a decoder measurement.

## 8. HK-037 / NFR-021

One process per cell reads the live `ALL.TXT` and the audio, decodes, scores in memory and writes **counters only** to `cell_*.json`. No per-message list, digest or temp file is written; the log sink allows only the aggregate residual-pass template and warning templates. All run files are in `D:\Projects\claude\_qa-scratch\wpilot\` (outside git). Nothing from the run contains a callsign.

## 9. Run

`python qa/rr-study/refset/wpilot/run_wpilot.py` (detached, two cells at a time, resumable: a finished cell is skipped). Cell order: block by block, W = 40, 16, 8, 4, 0 within a block, so any prefix is balanced across W. Report: `analyze_wpilot.py` → `wpilot_result.json` and a note to the Architect. QA reports after block 4 (about 0.9 h) and at the end. Estimate: 12 blocks × 228 cycles × ≈ 5.6 s ≈ 4.3 h sequential, ≈ 2.5 to 3 h with two cells at once (±30 %; the rate is from the DI build and will be re-timed on the first cells).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
