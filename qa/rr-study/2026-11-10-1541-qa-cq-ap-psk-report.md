# CQ-AP-PSK: report. Verdict **USABLE (P_R)**, with the limit that goes with it

**QA · 2026-11-10T15:41Z (`date -u`; analysis run once at 15:39:16Z, 37 s).** Aggregates only: no callsign, message text or per-decode row (NFR-021, HK-037).
Freeze `22b854c5` (code `39f40ea4`); spec with Amendments 1-2; capture 11:56:28Z to 15:30:48Z (6,922,227 messages, SHA-256 `43cdf5af…091f49`); window [12:26:28Z, 15:00:48Z]. Command and output: `result.json` in scratch (SHA-256 starts `c48dc7e7`). Nothing in the code or the rules was changed after the freeze.

## Rows (gating population: **P_R**, because V-REF failed: no WSJT-X `ALL.TXT`)
| row | value | bar | result |
|---|---|---|---|
| V-REF | WSJT-X `ALL.TXT` absent | needs a live reference | **FAIL** (P_R gates, A1.4) |
| V-FEED | 0 gaps > 120 s, 0 spots without `t_tx`, 0 non-FT8 | none gate | pass |
| V-SELF | 1,294 feed spots with our `rc` ÷ 1,259 reported records (42 windows) = **1.028** | ≥ 0.90 | **pass** |
| N-INSUFF | weak bin n = **609** | < 30 fires | does not fire |
| G-COVER | C_weak = 607/609 = **0.9967**, Wilson 95 % lower **0.9881** | ≥ 0.40 | **pass** |
| G-SLOPE | C(−16…−18) − C_weak = 0.9985 − 0.9967 = **+0.0018** | ≤ 0.20 | **pass** (defined) |
| G-GHOST | 0 of 10,000 corroborated; Wilson 95 % upper **0.00038**; point 0.0 | upper ≤ 0.02 | **pass** (a guard, A2.3) |
| NOT-USABLE test | C_weak upper 0.9991 ≥ 0.40; ghost point 0.0 ≤ 0.05 | | does not fire |
| **Verdict** | **USABLE (P_R)** | | |

## Descriptive lines
- **P_R:** 8,750 decodes over the whole daemon-up period, **5,593 inside the window**. Of 29,659 decodes in the period, 9,349 were CQ decodes with a standard sender (one per cycle and sender).
- **C (P_R) per bin of our SNR:** ≥ −10: 3,305/3,305 = 1.000; −11…−15: 1,024/1,024 = 1.000; −16…−18: 654/655 = 0.998; ≤ −19: 607/609 = 0.997. **Call + band only** (no frequency limit): identical in every bin.
- **P_S (shuffle, ≥ 2 h and ≥ 200 Hz away):** 737 of 2,658 pairs corroborated = **0.277**; 2,935 of the 5,593 had no eligible partner (the window is only 2.6 h long) and were dropped.
- **D-T (matched spot time minus cycle start, every matched spot):** n = 5,767,666 spots (about 1,030 per decode), median −60 s, 5-95 % range −1,590 to +1,590 s: spread evenly over the ±1800 s window, as the once-per-hour reporting predicts.
- **Ghosts (A2.0-A2.1):** 400,000 candidates drawn, 371,298 unpack to a space-free call and all were run through the product's `IsPlausibleMessage` with the live grammar; the first 10,966 in draw order were consumed, 966 of them rejected by it, 10,000 kept (rejected share of all candidates 0.975). Round-trip proof against ft8_lib: 18,619 of 18,619 (freeze §4).
- Not computed (no WSJT-X): P_T, P_T-ours, P_T-missed, P_X.

## What this verdict does and does not say (QA's reading; the ruling is the Architect's)
- **The rows pass because of what P_R is, not because coverage was measured where AP would sit.** P_R holds only senders we decoded as a CQ at least three times within 20 minutes at the same frequency (A1.5). Such stations are steady, and steady stations on 20 m are heard by many receivers: C is about 1.00 in every bin, **flat from −10 dB down to ≤ −19 dB**. HK-026: an instrument whose response is flat where the boundary sits cannot bound its own blind spot. The slope row passes because the curve does not fall inside P_R, not because the feed vouches for weak one-off CQs. **No one-off weak CQ, the kind an AP decode adds, is in P_R by construction.**
- **The ghost null is clean:** 0 of 10,000 random publishable callsigns find a spot at the same time and frequency, against 27.7 % for real callsigns placed at the wrong time and frequency (P_S). The rule separates a random callsign from a real one; it does not separate a real callsign decoded once, weakly, from a real one heard in many places.
- **So "USABLE (P_R)" supports one claim:** a CQ-AP extra whose sender is a repeat caller could be corroborated by the feed at about 100 %, and a random false callsign at about 0 %. For one-off weak CQs the check says nothing; the weak-bin coverage of a station-independent reference (WSJT-X, P_T) is still unmeasured (A1.5, CA-3/CA-4 are scored on P_R, not P_T).
- V-SELF = 1.028 (above 1): the feed holds slightly more of our own spots than the log's reported-record sum; the reason was not investigated. It passes the ≥ 0.90 bar; it does not show feed loss.

## Housekeeping
- Spot file, `result.json`, `callsign-grammar.copy.json` and the gate binaries stay in `D:\Projects\claude\_qa-scratch\cq-ap-psk\`. The raw spot file is **kept until the Architect's ruling and then deleted at job close** (HK-037); say if it should go now.
- Committed here: the code, the freeze record, this report. No data file.
