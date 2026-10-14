# COH-GAIN Amendment 4 — the extension on fresh cycles (`i mod 10 == 5`), the pooled primary and the U row

**QA report.** V4′ replay 19:46Z → 20:20Z, extraction 20:21Z → 20:30Z (`date -u`, 2026-10-06). Spec §14 of `2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md` (branch `arch/coherent-limb2`), as amended (U-GO is a replication check, `394c0645`). `BAR_G` = 1.0 pp, FROZEN. The Architect's session was not reachable when this was written, so it is **unruled**.

**Scope (verbatim):** *Offline, Python, at WSJT-X's own positions on one 40 m night. Extraction and decode only; candidate search, the managed layer and the live path are not exercised. WSJT-X's AP is off on this station.*

## Verdict (primary): pooled **COH-OPEN** again

**NET_C3 pooled over both samples = +1.41 pp, 95 % CI [+0.87, +1.94]** (19,097 rows, 619 cycles, blocks of 8 within each sample then pooled, 78 blocks, B = 10 000, seed 20261006). `CI_lo` 0.87 < `BAR_G` 1.0 ≤ `CI_hi`: **COH-OPEN**. There is no automatic third sample; the Captain decides. Blocks of 4 and 16 (not used): [0.93, 1.89] and [0.81, 1.99]. Extension alone: **+1.49 pp [+0.69, +2.25]** (9,575 rows); sample 1 was +1.33 [+0.57, +2.03]. The two samples agree.

🟢 **No first-paragraph clustering flag** this time: the top-5 blocks carry 29.3 % of the positive pooled gain; 466 of 619 cycles carry a non-zero net; the largest |Σ d| in a block is 18.

## Secondary (extension rows only): **U-GO**, with a false-decode cost that decides the design

**NET_U = +5.33 pp [+4.81, +5.81]** (U = G, and C3 only where G fails) ⇒ `CI_lo` ≥ 1.0: **U-GO**. Per the Architect's amendment this is a **replication check** (the union cannot lose a row; it equals C3's gain rate, 5.25 % on sample 1).

**The fallback's false decodes (mandatory):** of the **4,225 G-fail rows**, C3 recovered the sent payload on **510** and returned a **CRC-valid payload that is not the sent one on 215** (5.09 % of G-fail rows; 2.25 % of all rows). That is **0.42 wrong payloads per correct recovery** (sample 1: 198 per 500, 0.40). A fallback that buys 5.3 pp at that rate is **not shippable as it stands**; the step-3 spec must gate on it. Part of the 215 may be genuine other messages at the position; this was not separated.

## Extension validity (all PASS; V2 carried)

| row | result |
|---|---|
| V1 | PASS: `libft8.dll` `2fa6d993…f365` equal at start and end. |
| V3 | PASS: C3 estimate on the window edge in 204 of 9,575 rows (2.1 %). |
| **V4′** | **PASS: G = 0.965 on P1** (5,522 rows the extension's own batch-labelled replay matched in batch 1; bar 0.90); G reads 0.7 % of the 1,146 batch-2-only rows and 0.4 % of the 2,907 rows the replay did not match; replay batch-2 share 17.2 %; per-cycle WSJT-X counts equal `ws_load` in all 310 cycles. |
| V5 | PASS: a fresh process over the first 300 extension rows, 0 differing fields. |
| V2 | carried (synthetic, sample-independent, passed). Sample 1's validity still passes (recomputed, not copied). |

## Extension descriptives (not verdicts)

- C1 −7.97 pp; C3\* +1.96 pp; C3 gains 510 / losses 367 (sample 1: 500 / 373): the same complementarity (gains on live misses, losses on live hits).
- Sign-corrected OSD: GO vs G **+0.073 pp** (7 true recoveries on 4,225 BP-fail rows, **256** CRC-valid wrong payloads); C3O vs C3 **+0.209 pp** (20 recoveries, 34 wrong). Again not a lever, and again costly in wrong payloads.

## Pins, build, instrument

DLL `2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365` (shim 20260058, `be3cc5ac`). Frozen extension list `rows_ext.json` LF SHA `7267de64c3979fe7838a32cbcd2a46d63e10316cc2dea1cad67220c9c4ff8852` (310 cycles, 9,576 rows, 574 excluded before extraction). Commits (local `qa/coh-gain`, not pushed): plumbing `06d10e59`, V4′ manifest `9d75de2c` (**before** extraction). 77 tests, mutants caught. Analysis writes `analysis_ext.json` (never a `rows*.json` name). Not done / limits as in the first report: one night, WSJT-X's positions only, the original audio only, candidate search not exercised.

## Predictions, facts for the ledger
CE1 (pooled COH-GO, 0.35): no. CE2 (pooled COH-OPEN, 0.50): **hit**. CE3 (U-GO, 0.80): **hit**. CE4 (wrong payloads ≥ 0.25 per correct recovery, 0.65): **hit** (0.42).
