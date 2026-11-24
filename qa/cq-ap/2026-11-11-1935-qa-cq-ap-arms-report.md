# CQ-AP (candidate #2): ARMS REPORT, mechanical verdict BETWEEN (V-SELF failed)

**Author:** QA · **Written:** 2026-11-11T19:3xZ (`date -u` 19:32:40Z) · **Freeze:** Part 1 `342d320b`, Part 2 `5cc84ad9`, code `32a17b0e` (unchanged; no amendment was made).
No callsign, message text or per-decode row appears here (NFR-021, HK-037). Raw result: `_qa-scratch\cq-ap\cqap_result.json` (SHA-256 `62b8b92c10b0f9a5…`, aggregates only).

## 1. What ran
Four arms, detached, PC exclusive, WSJT-X idle, in the frozen order. All rc 0, preflight ok, orphan check clean after each (`arms\chain_status.txt`).

| arm | build / DLL | CQ-AP | cycles | start to end (Z) |
|---|---|---|---|---|
| OFF2 | 7ca00264 / `bbde6eb6` | 0 | 500 | 17:23:43 to 18:05:34 |
| OFF | 7ca00264 / `bbde6eb6` | 0 | 500 | 18:05:35 to 18:45:35 |
| ON | 7ca00264 / `bbde6eb6` | 1 | 500 | 18:45:36 to 19:27:32 |
| REF | 98332f2a / `1ba8dc3d` | n/a | first 50 | 19:27:33 to 19:31:35 |

Analysis run once, with the Part 2 §5 command (`--run`, seed 20261111, B = 2000). Window: 261110_184745 to 261110_205230.

## 2. Rows
| row | result |
|---|---|
| V-NAT | PASS (ON 7ca00264 / bbde6eb6; REF 98332f2a / 1ba8dc3d) |
| V-SET | PASS (all four arms, 8 threads each, no missing readback token) |
| V-OFF | PASS (50 cycles compared, 0 excluded, 0 differing) |
| V-FEED | PASS (4,061,373 feed rows, 0 gaps over 120 s) |
| **V-SELF** | **FAIL: 773 own spots / 954 {Reported} = 0.810, bar 0.90 (37 windows)** |
| G-GAIN | PASS (K_C per 100 cycles CI [16.60, 24.40], CI_lo > 0) |
| NO-GAIN | not triggered (CI_hi of (K_C + K_N) / D_OFF = 1.009 %, bar < 0.15 %) |
| U-UB | PASS (K_N = 0; CI_hi 0.0 per cycle, bar 0.021) |
| T-TIME | PASS (p95 ON 5.954 s, OFF 5.459 s, difference 0.495 s, bar 1.0 s; abandoned cycles 0 vs 0 per 100) |

**Verdict, by the frozen order: BETWEEN.** VOID does not fire (V-SELF is not a VOID row in the frozen verdict function); NO-GAIN does not fire; SHIP-CANDIDATE needs V-SELF and it failed; FP-UNRESOLVED needs U-UB to fail and it passed. V-SELF alone separates this run from SHIP-CANDIDATE.

## 3. The numbers
- D_OFF 12,036; D_ON 12,157; **AP-only extras 102, all corroborated (K_C = 102), uncorroborated K_N = 0.** Hashed-call texts excluded: 0 among the extras.
- K_C per 100 cycles 20.4 [16.60, 24.40]; as a share of D_OFF 0.847 % (interval 0.685 % to 1.009 %).
- Corroboration: 63 by both the feed and WSJT-X, 39 by the feed only.
- By our SNR: at or above -10 dB 11; -11 to -15 dB 13; -16 to -18 dB 19; at or below -19 dB 59.
- AP activity in ON: 500 `cq-ap:` lines, 508,519 attempts, 314 AP decodes; OFF has 0 lines, 0 attempts, 0 decodes.
- A1.7 balance: ON-only decodes without AP 5.0 per 100 cycles; OFF-only 1.6 per 100 (hashed texts excluded: 5 and 3).
- N-1 (CQ-tagged texts not starting with CQ): 0, no flag. Extras with an OFF decode within 5 Hz in the same cycle: 7.
- Abandoned cycles: 0 in every arm.
- **OFF vs OFF2 repeat: 500 of 500 cycles compared, 0 differ, D 12,036 vs 12,036.** The decoder is deterministic on this build and these inputs, so every ON-minus-OFF difference is the flag, not run noise.

## 4. Reading, and its limit
- Every AP-only extra was confirmed by the feed or by WSJT-X; none is an unconfirmed possible false decode. The false-decode upper bound is 0.
- That bound is only as good as the feed. V-SELF measures exactly that: how many of the station's own transmissions the feed returned. It returned 81 %, not 90 %, so some real extras may be missing from the feed, which makes K_N more likely to be overstated than understated. Within K_N = 0 that cannot raise the false-decode count, but the frozen rule still withholds SHIP-CANDIDATE, and QA does not soften a frozen bar after seeing the number.
- The extras are 0.85 % of the OFF decodes, concentrated at or below -19 dB, which is where the A1.3 sweep expected the gain.

## 5. For the Architect to rule
1. V-SELF 0.810 against 0.90: treat the result as BETWEEN (as computed), or amend the bar? QA recommends no amendment of a bar after the number is known; if the Architect wants a rerun the question is whether any feed backfill is possible, which QA does not expect.
2. The programme's next step on the CQ-AP lever.
Nothing here is an upload, a merge or a push.

## 6. Housekeeping
`_qa-scratch\cq-ap\spots_raw.jsonl` is kept until the Architect rules (HK-037). The WSJT-X `ALL.TXT` was read by code only; only counts left the reading function.
