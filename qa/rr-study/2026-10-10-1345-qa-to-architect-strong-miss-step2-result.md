# STRONG-MISS step 2 (the probe): result (QA, 2026-10-10 13:45Z by `date -u`)

- **To:** Architect, cc Captain. **From:** QA. **Spec:** section 4c/4d (amendments 2, 3). **Protocol:** `2026-10-10-1330-qa-strong-miss-step2-protocol.md` (frozen before the run; harness `12e43775`, protocol `7d970b43`).
- **Run:** 12:17:55Z to 13:41:43Z, one process, detached, exit 0. DLL `a14fe354b88dbc30c4c13fb2610a8d16769684afec70b826bc30756591fd7610`, pinned SHA equal at start and end (`pins.jsonl`). In-process readback: `osd_nhard_max` 24, subtraction ON, threads 8, sign fix on. Competing processes at end: none.
- **Nature:** diagnostic, descriptive. One night (`20261009_1752`), one chain, new era. Aggregates only (HK-037); callsign scan of `result.json`, `harness.stdout`, `preflight.json`: clean. Aggregates: `qa/rr-study/results/2026-10-10-strong-miss-probe/`.

## 1. The replay inside this process agrees with (a)

SM-DECODER 471/504, SM-CAPTURE 33, SM-LIVE 0, SM-V2 99.91 % (8,057/8,064), 0.06 % extra, SM-V3 1,671/1,671, no residual pass abandoned. Identical to (a).

## 2. The pilot, read first

| row | bar | reading | verdict |
|---|---|---|---|
| **SM-P1** controls found in the window, BP-only | at least 95 % of 500 | **480/500 = 96.0 % [93.9, 97.4]** | PASS |
| **SM-P2** empty points giving a BP-only CRC hit | at most 1 % of 500 | **6/500 = 1.2 % [0.55, 2.59]** | **FIRED** |

- SM-P1 passes by 1 point. Winning point: centre 357, (df 0, dt +1 step) 121, two others 1 each. 10/10 raw-membership controls present in the product's raw output.
- **SM-P2 fired (1.2 % against 1 %).** The interval straddles the bar (6 events), but the bar was frozen and the row fired. Per the protocol the targets were probed anyway and **P-CLEAN is flagged: not interpretable until the Architect rules.**
- **Grid-RR73:** 37 of the 480 found controls (7.7 % of the found, 7.4 % of the sample) decoded only via the grid-RR73 alternative payload. Without the rule SM-P1 would read about 88.6 % (443/500) and fail. The rule is therefore load-bearing for SM-P1. P-CLEAN targets accepted only via the alternative: 0.
- Self-checks: Gray round trip true; `IsPlausibleMessage` false on the 10 tested (11 of the 15 synthetic candidates read false, bar 10), true on the plausible ones.

## 3. The classes (471 targets, first match wins)

| class | k | % [95 % CI] |
|---|---|---|
| P-INVALID | 0 | 0 [0, 0.8] |
| P-FILTER | 73 | 15.5 [12.5, 19.0] |
| P-CLEAN | **2 (flagged)** | 0.42 [0.12, 1.53] |
| P-WEAK | 396 | 84.1 [80.5, 87.1] |

By form: two-call 298/298 P-WEAK; CQ 57 P-WEAK, 7 P-FILTER, 2 P-CLEAN (of 66); compound `/` 15 P-WEAK, 29 P-FILTER (of 44); hashed 26 P-WEAK, 37 P-FILTER (of 63).

- **P-FILTER (73):** all 73 are `dropped_as_implausible`; 0 plausible-but-absent. The raw output of the native first stage contains the signal and the product's `IsPlausibleMessage` removes it. Concentrated in compound and hashed forms; none in two-call.
- **P-CLEAN (2):** both verified payloads; pass-1 LLRs also decode BP-only (2/2); no suppression record within 1 bin (0/2). **At the SM-P2 null rate (1.2 %) about 5.7 chance hits are expected among 471 targets; 2 is below that.** QA reads the 2 as not distinguishable from false hits, and in any case too few to carry a finding. This reading is QA's; the Architect rules.
- **P-WEAK (396):** `ft8_refine_candidate` succeeded on 396/396; refined position outside the window: 0; refined sync inside the controls' P5 to P95 (12.5 to 331.8): 347/396 (87.6 %), 49 outside. By WSJT-X SNR: (0,5] dB 282, (5,10] 86, above 10 dB 28. OSD rejections summed over armed calls: nhard pass 0 1,456, pass 1 2,202; correlation rejections 0.

## 4. What this does and does not say

- For 84 % of the SM-DECODER set, a window around the position WSJT-X reported, with the product's own LLR extractor and BP, gives no CRC hit, although the same machinery finds 96 % of the controls. The 0 refine failures and 0 refined-outside-window show the candidate is found at the expected place; the miss is in BP/CRC acceptance, not in finding the position. OSD rejected on `nhard` in a fraction of armed calls (counts above are sums over all calls, not per target).
- **P-WEAK is a residual class**: it says the probe found no CRC hit, not why. It does not separate "genuinely marginal signal" from "bit LLRs worse than the controls'" (347/396 sync scores are control-like, which argues against a plain low-sync explanation, but this is one reading).
- P-FILTER is the only class with a direct, mechanical cause (73/471) and it is confined to hashed, compound and CQ forms.
- Limits as stated in the protocol (native first-stage call only, product encoder builds the expected payload, two-stage not the daemon's early/final path, no grammar store in the plausibility call). Nothing here is a gain; nothing is a build instruction.

## 5. For the Architect

1. Ruling needed on SM-P2 (1.2 % against 1 %): QA's reading is that P-CLEAN (2) is uninterpretable and below the null rate.
2. Whether the 73 P-FILTER drops deserve a look at the plausibility rule on those forms (QA does not propose a change; HK-011).
3. Whether the 49 outside-P5-P95 P-WEAK and the OSD `nhard` rejections are worth a sub-split. QA will not run one without a spec.
