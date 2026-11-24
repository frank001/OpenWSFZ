# CQ-AP A1.3 sweep (positive control): result PASS

**QA · 2026-11-10T18:03Z (`date -u` read 18:01:53Z when the result was read).** Freeze: code `d100e9af`, record `abd54787`; run once at 17:29:40Z, nothing changed after it. Build `7ca00264`, `libft8.dll` SHA-256 `bbde6eb66af4…` (asserted in the code), shim 20260072. Synthetic Q-prefix messages only; aggregates only. Raw result: `_qa-scratch\cq-ap-review\sweep_result.json`.

## Phase A (OFF only, 100 cycles per step): S50 = −19 dB
OFF decoded of 100, from −24 to −12 dB: 0, 0, 0, 1, 9, **48** (−19), 86, 100, 100, 100, 100, 100, 100. The 0.5 crossing lies between −19 (0.48) and −18 (0.86): S50 = −19 dB.

## Phase B (grid −23 … −18 dB, 200 cycles per step, OFF and ON on the SAME audio)
| SNR | OFF | ON | ON − OFF | OFF Wilson-95 | ON Wilson-95 | step passes the bar | ON-only / OFF-only |
|---|---|---|---|---|---|---|---|
| −23 | 0 | 0 | 0.0 pp | [0, 0.019] | [0, 0.019] | no | 0 / 0 |
| −22 | 0 | 0 | 0.0 pp | [0, 0.019] | [0, 0.019] | no | 0 / 0 |
| −21 | 0 | 8 | +4.0 pp | [0, 0.019] | [0.020, 0.077] | no (< 10 pp) | 8 / 0 |
| **−20** | 15 | 50 | **+17.5 pp** | [0.046, 0.120] | [0.195, 0.314] | **yes** | 35 / 0 |
| **−19** | 93 | 136 | **+21.5 pp** | [0.397, 0.534] | [0.612, 0.741] | **yes** | 43 / 0 |
| −18 | 168 | 186 | +9.0 pp | [0.783, 0.884] | [0.886, 0.958] | no (< 10 pp) | 18 / 0 |

**Bar (A1.3): at one or more steps ON − OFF ≥ 10 pp with ON's Wilson lower bound above OFF's upper bound: met at two steps (−20 and −19 dB). VERDICT: PASS.** The build is not sent back; the replay arms may proceed once the live session exists.

## Descriptive
- **Never worse:** OFF-only successes 0 at every step (ON decodes everything OFF decodes on this audio).
- **No wrong messages:** 0 decodes of any other message in OFF and in ON, at every step (so no false decode in 1,200 signal cycles per arm).
- **Tagging:** `cq`-tagged decodes equal the ON-only successes at −21 and −20 (8 and 35); at −19 and −18, 46 and 22 tagged against 43 and 18 ON-only (the tag also lands on decodes the OFF run found in another pass; counted, not a defect).
- **OSD entries from the CQ-AP path: 0** at every step; **attempts per cycle: 213** (single signal, native passes only; the staged pipeline in the replay made about 1,000 per cycle).

## What this shows and does not show
- It shows the mechanism works as designed: on a clean single CQ in white noise, forcing the CQ bits after normalisation lowers the decode threshold by about one dB (the ON curve at −20 equals the OFF curve at about −19), and nothing is lost.
- It does **not** show a live gain or a false-decode rate on real audio: one signal per cycle, no interference, no hash-table state, no QSO traffic, white noise. The false-decode question belongs to K_N in the real arms.
- The 10 pp bar is the Architect's design choice with no data on file (A1.3); here two steps pass it by 7.5 and 11.5 pp.
