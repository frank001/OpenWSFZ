# XC-SUP result (QA, 2026-11-14T02:20:09Z `date -u`): SUP-FOUND

**To:** Architect (your lead 1, E194, HK-026). **From:** QA. Branch `qa/same-chain`, local, nothing pushed. **Counts only**; the text was read inside `qa/xc-build/xc_sup.py` and never left it (HK-037). Result file: `qa/xc-build/results/xc_sup_2026-11-14.json`.

## 1. Verdict by your reading rule

**SUP-FOUND.** n(SUP-W) = **641** against the limit of 4 (SHADOW's own rule, 25 + n <= 29). Not close.

| Class (first match wins) | n | share of 2,579 | SNR median | with a co-located different text that shares the sender token | veto flag_O |
|---|---|---|---|---|---|
| COR (Test B corroborated) | 904 | 35.1 % | -18 | 0 | 17 |
| **SUP-W** (a WSJT-X row of the cycle, different text, df <= 3.125 Hz, ddt <= 0.2 s) | **641** | **24.9 %** | -18 | **583 (90.9 %)** | 526 |
| SUP-O (ON's own batch 1 to 5, different text, same window) | 16 | 0.6 % | -18.5 | 4 | 16 |
| FREE | 1,018 | 39.5 % | -18 | 0 | 0 |

- Mean co-located different texts: COR 0.05, SUP-W 1.90, SUP-O 1.06, FREE 0.
- **The sender-token figure is the pattern you predicted:** in 583 of the 641 SUP-W rows the WSJT-X row sitting in the template's slot is a different message that contains the template's sender token. Chance co-location cannot do that.
- **Chance baseline** (same window, ordinary batch 1 to 5 matched decodes against a different-text WSJT-X row): 391 of 20,335 = 1.9 %, which would give about 50 of 2,579 by chance, none sharing a sender token. 641 is far above it.
- **A lower bound.** SUP-W needs WSJT-X to have decoded the real next message. Stale templates where WSJT-X decoded nothing there sit in FREE (1,018), invisible to this test. I do not estimate them.

## 2. R14 co-location veto, from the same files (not a ruling)

- A veto on "ON's own batch 1 to 5 decode with a different text in the window" would remove **526 of the 641 SUP-W rows (82.1 %)** and all 16 SUP-O rows.
- It would remove **17 COR rows: NET cost 17 / 25,493 = 0.067 pp** (NET 3.546 to about 3.479 pp).
- **115 SUP-W rows remain** that no own decode shadows (WSJT-X decoded the real message, we did not). A live veto cannot see them without WSJT-X; they need a detector that scores the symbols the two messages do NOT share. That is Developer territory (HK-011), after your ruling.

## 3. Instrument checks (HK-022, HK-026) and one QA error

- **My first run was wrong.** It compared DT raw in a 0.2 s window, although OpenWSFZ's `dt` and WSJT-X's DT carry a fixed 0.6 s convention offset. The first output read SUP-W 2, SUP-CLEAN, which was an instrument that could not see a co-located row. The COR rows' own dt difference (median 0.600 s, p05 to p95 [0.600, 0.700], all 904 rows) exposed it before anything was reported. Corrected: the window is centred on the offset, and the code asserts that the COR median is 0.6 s +/- 0.05. Ledger row **Q69** (69 rows now). **Do not cite the "SUP-W 2" figure; it was never a result.**
- **Validity checks that held:** 2,579 batch-6 rows and 904 COR rows reproduce the chain analysis exactly (asserted in code); all 904 COR rows find an equal-text WSJT-X row within 10 Hz.
- **Provenance:** ON arm of the PC chain, `_qa-scratch\xc-chain\full\ON\nc.tsv` (23,630 rows), TEST night `20260808_0016`, frozen build `f82b6432`, `libft8.dll` `bbde6eb6...6528`, T_E 3.076042. The window constants are yours (3.125 Hz, 0.2 s); the 0.6 s is the convention offset.

## 4. What this changes

- **NET is unaffected** (the 904 are COR). **The false-publish burden is not small:** at least 641 of 2,579 template publishes (24.9 %) show a different message from the same station in the same slot. That lands on the PSK Reporter upload and on what the Captain sees in the panel. Default-ON is blocked on XC-SUP, as you said.
- The shadow null calibrates false detections on an opposite-parity slot (25 events, as designed); it does not calibrate this class. That is your E194.

## 5. Next (QA, in your order)

(2) the descriptive delta U' with angle A's statement beside it; (3) done earlier (`5b` of `2026-11-14-0212-qa-xc-build-pc-arms-result.md`: 98.8 % of the 904 are weak bands B, C, D). Second night: **not started**; my earlier 17 m run on `20260808_1154` was stopped within 3 minutes, before any result, because you excluded 20260808. The Captain's standing plan for tonight is that QA starts the tests it needs; I will pick the 40 m night per his 2026-10-03 rule (list every `artefacts/` folder), freeze the selection, state the predicate before running, and include XC-SUP in its analysis. The working files stay in `_qa-scratch\xc-chain\full\` until you say they may go.
