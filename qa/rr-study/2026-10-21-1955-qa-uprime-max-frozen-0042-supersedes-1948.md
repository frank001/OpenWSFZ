# QA: U′_max FROZEN at 0.042 for COH-FALLBACK step 4 (supersedes the 19:47:56Z freeze; before any ON decode)

**Stamped:** 2026-10-21T19:55:32Z by `date -u`.

## The record, in order (nothing is deleted)

| time (`date -u`) | where | who | what |
|---|---|---|---|
| 19:47:56Z | QA's window | the Captain, first-hand | *"keep the 30% rule."* → U′_max = 0.0559375, frozen in `2026-10-21-1948-qa-uprime-max-frozen-step4.md` (`e89b2445`) |
| 19:49:24Z | the Architect's window | the Captain, reported by the Architect | *"alright, go with your recommendations."* The Architect's one open recommendation was a fixed 0.042 (§18 A18.4). |
| 19:53:33Z | the Architect's window | the Captain, reported by the Architect | *"go with your recommendations"* again, after asking whether 0.042 is too tight. |
| ~19:55Z | QA's window | the Captain, first-hand | *"Confirmed. I'm sorry about the confusion as I was a bit confused also."* (reply to QA's question of which value stands, with 0.042 named as the alternative) |

QA froze the first value from the Captain's own words in its window, held it when a relayed message contradicted it, asked the Captain directly, and re-freezes on his direct confirmation.

## The frozen value

| | |
|---|---|
| **U′_max** | **0.042** per cycle (a fixed value, the Captain's choice; it is 2 × 0.021, twice 10-09's largest observed ΔU′) |
| rows | **U′-OK** `CI_hi(ΔU′)` ≤ 0.042; **U′-FAIL** `CI_lo(ΔU′)` > 0.042; **U′-OPEN** otherwise |
| expected, solved at 960 cycles with the A11.2 half-width | U′-OK if ΔU′ ≤ about 0.027; U′-FAIL if ΔU′ ≥ about 0.065; a fallback exactly as noisy as 10-09's largest (0.021) reads U′-OK |
| A2.4(a) | half-width at 0.042 is 0.0183; 2 × 0.0183 = 0.037 ≤ 0.042: the trigger does not fire |
| the 30 % rule, for the record | would have given 0.0559375; it is not used |
| class list, thresholds, T, sample | unchanged from the 19:47:56Z note: `uprime_off_classes.json` SHA-256 `da559b55b2dafd6f2c27061d11a1557866c3a7a0dd1b92309184f4edb7839a23`; n ≥ 10 and present rate ≥ 80 %; T = 0.276; up to 50 per class, seed 20261007; calibration offset −0.18 s |
| analysis script | `cf_step4_analysis.py` (`9448cb92`), run as `python cf_step4_analysis.py <raw> <out> 0.042` |

The bar is never moved after ΔU′ is seen. No ON decode has run. The ON go is a separate decision of the Captain's.
