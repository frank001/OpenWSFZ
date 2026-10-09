# RULING — SUB-FEAS offline flag-OFF/ON replay of the 2026-09-30 night (the controlled decode-rate test)

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-02 ~06:20Z (HK-017)
- **Reviewed:** `qa/rr-study/results/2026-10-01-sub-feas-offline-onoff-replay/report.md` + `rows.json` @ `676086db` (`qa/onoff-replay`, worktree `D:\Projects\claude\_onoff-replay`, local, not pushed); raw numeric rows in the QA worktree's `artefacts/rr_2026-10-01_onoff_replay/` (read, numeric only, HK-037)
- **Against:** spec `qa/rr-study/2026-10-01-1935-architect-to-qa-spec-sub-feas-offline-onoff-replay.md` + Amendment 1 (`d292f913`)
- **`src/` / `native/` diff:** none (docs only; `git diff --stat -- src/ native/` empty)

## 1. Verdict — **D1 REPLICATED, accepted**

**NET +11.73 pp, 95 % CI [11.41, 12.03]** (block 40, 108 blocks, B 10 000, seed 20261001), 4 298 cycles. V1–V6 all PASS. Block 20 / 160 give [11.47, 11.98] / [11.25, 12.17], so the verdict does not depend on the block length. `CI_lo` is about 11× the registered 1.0 pp bar.

What I checked myself, not taken from the report:

- **Arithmetic:** (93 326 − 78 128) / 129 608 = 11.726 %. The band NETs (0.77 + 4.71 + 3.75 + 2.49) sum to 11.72. Batch-1 counts per band sum to 79 702 = OFF decodes, and minus 1 669 not-corroborated that leaves 78 033 = `M_on,b1`. Batch-2 counts sum to 15 713, and minus 420 that leaves 15 293 = `M_on,b2`. All internally consistent.
- **The batch-1 / OFF gap of −95** (−0.07 pp) is explained in the report (one pairing of the union, plus the hash-table history). V4 compares numeric fields 4 298/4 298, so batch 1 *is* the OFF decode set, and the −95 is a matching effect only. Accepted. It does not touch the NET, which uses `M_on` and `M_off` only.
- **The aborted first OFF attempt:** it was discarded and rerun from row 0, before any ON decode. No row, threshold or input changed. V3 is therefore read on the rerun. This is correct handling, and the report names it as required.

**Citable as:** *"NET +11.73 pp [11.41, 12.03], one 40m night, replay vs replay, Test B match rule"*, always with the scope sentence. 🛑 It is not to be differenced against Stage 2's +8.89 pp (spec §9). Quote the two side by side, labelled.

## 2. The band-D FP-watch flag — **the flag stands; small; not a §8.2 answer**

The flag is mechanical and fired: batch-2 not-corroborated **194/3 429 = 5.7 % [4.93, 6.48]** vs batch-1 **454/11 095 = 4.1 % [3.74, 4.48]**. I add one check of my own (HK-018) and one of size:

1. **It is not an SNR-mix artefact inside band D, at least not in the obvious direction.** Band D is open-ended (≤ −16 dB), so a batch that sat lower in the band would be corroborated less often by WSJT-X just from being weaker. From `outcomes_ON.csv` (numeric), batch 2's band-D decodes are **stronger**, not weaker, than batch 1's. The median is −18 dB in both, but the share at ≤ −20 dB is 21.6 % vs 34.4 % and the share at ≤ −22 dB is 7.1 % vs 16.6 %. Weaker-in-band would have *lowered* batch 2's rate. The flag survives this confounder, and if anything this understates it. ⚠️ **Caveat:** batch-2 SNR is estimated on the residual audio, so the two SNR scales may not be strictly comparable. That is unverified.
2. **Size:** the excess over the batch-1 rate is ≈ (5.66 − 4.09) % × 3 429 ≈ **54 decodes over the 4 298-cycle night**. The upper bound on *all* batch-2 band-D false positives is 194 (≈ 0.045 per cycle). Against that, band D added **+2.49 pp** of WSJT-X-corroborated decodes. Across all bands, batch 2's not-corroborated total is 420/15 713 = 2.7 %, vs 1 669/79 702 = 2.1 % for batch 1.
3. **Bands A and B go the other way:** batch 2 is corroborated *more* often than batch 1 (0.7 % vs 1.5 %, 1.4 % vs 1.8 % not-corroborated). Band C overlaps.

**Reading:** in the weakest band, residual-pass decodes are somewhat less often confirmed by WSJT-X than pass-0 decodes. "Not corroborated" is an upper bound on false positives, not a count of them. This is the same direction as Test B's band-D point gap (92.9 % vs 95.2 % at n = 169), which was then unresolved. At n = 3 429 it resolves. **It does not change D1, and it does not answer §8.2.** It is the one number the Captain should weigh if he considers flag-ON by default or batch 2 reaching the answerer. **No new run is requested on account of the flag.**

## 3. What this changes, and what it does not

- **Changes:** the decode-rate gain is now shown on two 40m nights by two instruments: the Stage 2 Python fit (payload match), and this native build through the managed two-stage path (text match). The live-path questions that remain are about runtime and FP, not about whether an effect exists.
- **Does not change:** flag default **OFF**; batch 2 **not** reaching the answerer. **Both are the Captain's decisions.** This run informs them; it does not make them.
- **Still open:** band replication (🔎 checked: the only other archived night with a gathered live WSJT-X `ALL.TXT`, `20260925_2010`, is also 40m, so a band replication needs a **new capture night on another band** and cannot be a replay of existing data); §8.2 beyond the upper bound; live-path runtime on another CPU; multi-pass. Stage B and the default-thread decision were both held for this result (board, 2026-10-01 19:55Z), and are now unblocked for the Captain to order.

## 4. Report changes before commit — **none required**

The report meets every "must say" in the spec: the scope sentence, the aborted attempt, matched-% and NET non-comparability, the (k) note, the open pre-flight item, the parity FILE:LINE, and 0 competing processes. It may be pushed as it stands, with the Captain's go (HK-033). The SNR-mix check in §2 here is my analysis, and it belongs in this ruling, not in QA's report.

## 5. Predictions, scored at ruling time (spec §10; ledger rule 1)

| # | Prediction | P | Class | Outcome |
|---|---|---:|:---:|---|
| OR1 | Verdict D1 | 0.85 | H | ✅ HIT. The easy direction: the spec itself called D1 expected after Test B. |
| OR2 | NET point in [4.0, 14.0] pp | 0.60 | H | ✅ HIT (11.73), in the upper part of a wide range |
| OR3 | V4 passes N/N | 0.95 | C | ✅ HIT (4 298/4 298) |
| OR4 | V6 passes 160/160 | 0.85 | H | ✅ HIT (160/160 identical). Written against the original V6; met under both the original and Amendment 1's wording. |
| OR5 | No band raises the FP-watch FLAG | 0.70 | H | ❌ **MISS**: band D flagged |

🔴 **OR5 was a computable miss priced as a hypothesis.** Test B had already shown a 2.3 pp band-D gap in the flagging direction at n = 169, and the board said "watch it". The power at this corpus's size was a one-line calculation: ≈ 3 400 batch-2 and ≈ 11 000 batch-1 band-D decodes give Wilson half-widths of ≈ 0.8 and ≈ 0.4 pp, so any gap above ≈ 1.2 pp flags. A gap anywhere near Test B's would flag. **I had the point estimate and the expected n, and did not combine them.** Same family as the ledger's "compute what the instrument reads before writing the bar". Tally not quoted: the ledger's cumulative count is unreconciled since 2026-09-22.
