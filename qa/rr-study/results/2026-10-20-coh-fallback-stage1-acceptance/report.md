# COH-FALLBACK step 3, Stage 1 acceptance (QA, 2026-10-20, runs 18:22Z to 18:51Z by `date -u`)

Spec: `qa/rr-study/2026-10-07-1330-architect-to-qa-spec-coh-fallback-step3-build.md` section 5.1 with sections 8 to 11 (`arch/coherent-limb2`). Developer builds: `44f0df4e` (shim 20260066, `libft8.dll` `7af6f893...a4d3`) and the reworked `d926bdc6` (shim 20260067, `libft8.dll` `60963686...c3db`), both SHA-256 verified before use. Both on `origin/main` `9d5ba635`; local, not pushed.

## Result in one table

| row | build | result | value | bar |
|---|---|---|---|---|
| **A2(a)** BP outcome | 44f0df4e | **PASS** | 27,571 / 27,571 agree (native 4,734 outputs = Python 4,734, both on all) | >= 99.5 % |
| **A2(b)** (df, dt) estimate | 44f0df4e | **PASS** | 27,571 / 27,571 equal; edge flag also 27,571 / 27,571 | >= 99 % |
| **A2(c)** F1b | 44f0df4e | **PASS** | 4,949 / 4,949 within 0.25 dB (max difference 0.0 dB), gate decision equal on all 4,949 | >= 99 % and >= 99.5 % |
| **A2(e)** order equivalence | d926bdc6 | **PASS** | gate-first vs output-first publish the same payload multiset on 100 / 100 cycles | N / N |
| **A0** cost gate | d926bdc6 | **PASS** | 0 of 100 cycles with `f_i` > `s_i` (bar <= 5); `f_i` median 0.94 s, p95 1.25 s, max 1.37 s; slack min 8.71 s, median 9.72 s | <= 5 of 100 |
| **A2(d)** anchor convention | d926bdc6 | **FAIL as written** | dt offset median 0.000 s (PASS, bar +-0.02 s); window-edge rate **6.85 %** (373 / 5,446) (bar <= 2 %) | median within +-0.02 s AND edge <= 2 % |

A2(a) to (c) carry over to `d926bdc6`: my diff of `native/` between the two builds is 0 lines and the shim diff has two hunks, both inside `ft8_coherent_fallback_cycle`. (A2(a)-(c) were run on `44f0df4e`; they were not re-run on `d926bdc6`.)

## A2(d): the diagnostic, and the ruling it needs

The failure is entirely in one sub-population. The 5,446 "decoded candidates" of the 100 cycles split by whether the candidate matches a result that `ft8_decode_all` reported (|freq| <= 1 Hz, |dt| < 0.02 s):

| population | n | edge rate | dt offset median / abs median |
|---|---:|---:|---|
| primary decodes (the candidate behind a reported result) | 1,975 | **0.41 %** (8) | 0.000 s / 0.015 s |
| other decoded candidates (CRC-valid duplicates at adjacent lattice positions of the same signal) | 3,471 | 10.5 % (365) | 0.000 s / 0.040 s |
| all (the literal population) | 5,446 | 6.85 % (373) | 0.000 s / 0.025 s |

372 of the 373 edge cases are at the frequency edge (|df| = 2.0 Hz), not the time edge. The reading: an adjacent lattice position that also decodes the same payload sits up to about 3 Hz from the signal, so its own +-2 Hz window cannot centre on it. That is a property of duplicate neighbours, not of the anchor convention for the decode's own position. The spec text says "candidates the ordinary decode DID decode ... the decode's own refined position", which can be read as the primary decodes only, but QA does not re-define a bar after seeing the data: **A2(d) is reported FAIL as written, and the population is the Architect's ruling.** On the primary-only reading it passes (edge 0.41 %, dt median 0.000 s).
Relevance to the fallback itself: the eligible population is the candidates the ordinary decode did NOT decode; the same neighbour effect could occur there for a signal that is simply not decoded, and the payload dedup then drops the duplicates (R2'), so it would cost time, not publish duplicates.

## Detail

- A0 per cycle (median): eligible 161.5, attempted 161.5, CRC-valid 44, F1b computed 4, gated 3, published 3; stage times (ms, median): estimate 449, F1b 264, C3 + BP 242. Gate-first (the old order, harness only) takes a median of 11.2 s per cycle on the same cycles, i.e. the reorder is a factor of about 12.
- A0 conditions: station PC, the cycle export called serially after `ft8_decode_all`, one native thread, no deadline, nothing else heavy running (the OFF arm and the A2 run had finished). The committed OFF slack (`s_i`, committed before any Stage 1 timing) was used unchanged; the slack was not re-measured in this session (the Architect's "one session" condition: the OFF slack was measured at 17:14Z and the Stage 1 timing at 18:29Z, the same machine and day, but not back to back).
- Smoke history, descriptive only: on the first build `44f0df4e`, 2 cycles with the CPU shared, `f_i` was about 18 s against about 9 s of slack (F1b about 94 % of the time); A0 was NOT run on that build (Architect, Amendment 3).

## Limits

Replay on one night and chain; single native thread (a parallel design competes with the passes for cores; the serial worst case is what A0 assumes); A2's Python reference values are the persisted COH-GAIN results (DLL `2fa6d993`, `nhard` 40, inverted OSD for the Python's own decode), not a fresh Python re-run, apart from the equivalence of the BP stage that the persisted flags encode; macOS is left to CI; the Developer's smoke harness for A2 was not reused.

Files: `a2_abc_44f0df4e.json`, `a0_a2d_a2e_d926bdc6.json`, `a0_per_cycle.csv`, `a2d_split_diagnostic.json` (numbers only).
