# R1-R4 split: why the K2 neighbours were never subtracted

**Date:** 2026-11-27 · **Author:** QA · **Asked by:** the Architect (board, 2026-11-26: "split the never-subtracted K2 neighbours into R1-R4, data on disk only") · **Status:** a measurement, no bars; no build, no replay. **Aggregates only (NFR-021):** the text of a result is read inside ONE function (`load_results`) that returns a gate code (`OK`, `HASH`, `TOKENS`); nothing else touches text. Inputs: the three SUB-PROBE runs (`probe_{S40,H40,H20}_L_n*`, decoder `fc3d5b5c`, shim 20260080), script `qa/decoder-rebuild/r1r4_split.py`, output `r1r4_split.json` beside this file. Code read at `main` `326538fb`, `native/ftz_decoder/ftz_decoder.c`.

## Summary

1. **The text gate (R1) is the largest single cause, and almost all of it is the hash placeholder.** Of the K2 neighbours never subtracted, **71 % (112 of 157), 17 % (18 of 105) and 50 % (134 of 266)** were never fitted because the unpacked text failed `ftz_text_reencodable` (`:744`, used at `:1029`); **91 %, 89 % and 96 % of those had a `<...>` placeholder** (the rest had fewer than three tokens). The fit takes its tones from the PAYLOAD (`:1074`), so the gate looks like a leftover from the classic text-based re-encoding.
2. **The second cause is the cross-cycle batch (XC): 16 %, 50 % and 35 %** (25, 52, 94 neighbours). Those results are found after the round loop and have no round that could fit them; this was not on the Architect's list (R1-R4), it is the same count as the "batch 3" column of SUB-PROBE.
3. **R2 (the step-2e fit skip) is small: 12, 8 and 8 neighbours (8 %, 8 %, 3 %).** R3 (no valid fit) is 5, 25 and 30 (3 %, 24 %, 11 %). R4 (found in the last round, so the round that would fit it never ran) is 3, 1 and 0.
4. **Upper bound for the R1 fix, not a prediction:** the K2 cases whose neighbour was an R1 result are **25.7 %, 3.6 % and 19.5 % of all K2 cases** (112 of 436, 18 of 495, 134 of 686). Whether subtracting them would let the missed signal decode is NOT measured here: it needs the fit to succeed (R3 shows it does not always) and the decode to follow.
5. **R1 is a property of the traffic, not constant:** as a share of ALL published results it is 7.8 % (S40), 1.2 % (H40) and 8.1 % (H20). H40 is the odd one: it has few hashed-call messages and a high R3 share instead.

## 1. The causes, as code (all checked against the source above)

Round loop `for round = 0..3`. Round r >= 1 first selects for fitting the results found by round r-1 (`:1024-1032`), then searches and decodes. A result is in the first class it meets:

| Class | Definition | How it is decided here |
|---|---|---|
| SUB | the result has a SUB probe row | per result (position match) |
| XC | found by the cross-cycle batch (3), outside the round loop | per neighbour, from `matchedbatch.csv` |
| R4 | found in round 3 (nothing follows), or the cycle was abandoned / a fit cancelled | per result: the round from the published CAND row; cycle flags from the log (0 cycles flagged in all three runs) |
| R1 | text gate false (`HASH`: contains `<`; `TOKENS`: fewer than 3 tokens) | per result, from its own text |
| R2 | no CAND row of the SAME round that FAILED lies in [f - 50, f + 100] Hz (`ftz_fit_needed`, `:701-706`) | per result, **exactly**: the rule is a function of positions, and the probe has every failed CAND row of that round |
| R3 | fit tried and returned "no valid fit" (rc -3, `:1088`) | **by elimination** (reencodable, a fit needed, no SUB row); checked against the log's `fitNone` totals, see section 3 |

## 2. The K2 neighbours that were never subtracted

| Slice | K2 cases | never subtracted | R1 hash | R1 tokens | **R1 total** | XC | R2 | R3 | R4 | unread |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S40 | 436 | 157 | 102 | 10 | **112 (71.3 %)** | 25 (15.9 %) | 12 (7.6 %) | 5 (3.2 %) | 3 | 0 |
| H40 | 495 | 105 | 16 | 2 | **18 (17.1 %)** | 52 (49.5 %) | 8 (7.6 %) | 25 (23.8 %) | 1 | 1 (a) |
| H20 | 686 | 266 | 129 | 5 | **134 (50.4 %)** | 93 (35.0 %) | 8 (3.0 %) | 30 (11.3 %) | 0 | 1 (b) |

(a) H40: one neighbour the inherited rule counts as never subtracted does have a SUB row at its lean result's own position (the WSJT-X-position match of SUB-PROBE missed it by tolerance). (b) H20: one neighbour (batch 3) has no row in the result dump. Both are inside the inherited 157 / 105 / 266 and are not hidden.

**Inherited figures asserted in the script, not quoted:** classified 667 / 696 / 914, K2 436 / 495 / 686, never subtracted 157 / 105 / 266, and the batch split of those (110 / 22 / 25, 36 / 17 / 52, 143 / 29 / 94) all reproduce.

**Attribution, as the Architect asked.** Per neighbour: SUB, XC, R4, R1 (own text) and R2 (positions of the round's failed candidates). By elimination: R3. R2 is exact because ftz_fit_needed is a pure function of the failed CAND rows of the round that found the result; so the Architect's code fact (if T's candidate failed in the SAME round that found N, R2 cannot apply) holds, and the 12 / 8 / 8 R2 neighbours are exactly the ones whose T candidate only appeared in a LATER round (the rule's intended behaviour: nothing had failed yet).

## 3. Does the split add up? (cycle totals from the log, all published results)

| Slice | R2 derived | `skipped=` summed | R3 derived | `fitNone=` summed | SUB derived | SUB rows | published results with no readable round |
|---|---:|---:|---:|---:|---:|---:|---:|
| S40 | 700 | 700 | 26 | 25 | 4,564 | 4,569 | 245 |
| H40 | 743 | 743 | 145 | 138 | 6,780 | 6,774 | 577 |
| H20 | 616 | 618 | 123 | 122 | 6,092 | 6,094 | 738 |

R2 reproduces the log exactly on two slices and is 2 short on the third; R3 is within 1, 7 and 1 of the log (the same position-matching tolerance that moves SUB by 5, 6 and 2). The last column is mostly the cross-cycle decodes (the dump holds 224, 485 and 721 more results than `lean.csv`'s round count); the remaining 21, 92 and 17 are results whose published CAND row was not within 3.2 Hz and 0.16 s. **Reading caveat:** that residue is largest on H40 (92), where R3 is also the least certain (7 over the log).

## 4. All published results (the base rate)

| Slice | linked results | SUB | R2 | R1 | R3 | R4 |
|---|---:|---:|---:|---:|---:|---:|
| S40 | 5,764 | 79.2 % | 12.1 % | 7.8 % | 0.5 % | 22 |
| H40 | 7,785 | 87.1 % | 9.5 % | 1.2 % | 1.9 % | 22 |
| H20 | 7,450 | 81.8 % | 8.3 % | 8.1 % | 1.7 % | 13 |

R2 is the largest non-subtracted class overall (it is the rule working as designed: the fit is skipped when nothing failed nearby), but it almost never matters for a missed neighbour (section 2); R1 is the opposite: smaller overall, dominant for the K2 neighbours.

## 5. What this does and does not say

- It says WHY the neighbours were not subtracted. It does not say that subtracting them would recover the missed signal: no fit was run, no signal removed. The bound in the summary (25.7 %, 3.6 %, 19.5 % of K2 cases) is the most the R1 fix can address; SUB-PROBE found that strong neighbours stop about 5 dB short even when subtracted, which lowers it further.
- H40 behaves differently (R1 3.6 % of K2 cases, R3 and XC larger): any proposal built on S40 or H20 alone should say so.
- XC (cross-cycle results) is a separate lever from R1-R4: those results are found after the rounds; fitting them would need a round after the cross-cycle search, which is a larger change than the gate.

**Proposal for the Architect (not a spec):** "fit the payload regardless of the text gate" (`:1029` / `:744`). It is a one-line change in the decoder's selection, the tones already come from the payload, and the check is already in place (the probe would show the new SUB rows and the fit's `fitNone` count). Cost to watch: more fits per cycle (S40 would fit about 450 more results in 170 cycles, about 2.7 per cycle; H20 about 2.5; H40 about 0.4).
