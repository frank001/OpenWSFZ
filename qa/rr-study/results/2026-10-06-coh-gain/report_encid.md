# COH-GAIN ENC-ID (Amendment 9, spec §18 / §18.1): is the truth mis-packed on non-standard-call messages?

QA, 2026-10-07. Offline, one night (`20261004_1634`), one band (40 m), DLL SHA-256 `2fa6d993…f365` (shim 20260058). Harness run, no test `--filter`. Row list `encid_rows.json` SHA-256(LF) `4e0ac7f0…598e` (795 X + 19 OSD control), reach list `encid_reach_rows.json` `2c50c879…484d` (76,886 rows), both committed in `6f2aa866` before the extraction.

## Verdict: NO READING, because the shuffled-truth control Y4 FAILED

The pre-registered rule withholds the reading when a validity row fails. It is withheld, and the 2 % tolerance is not retuned.

| Row | Result |
|---|---|
| Y1 reproduction | **PASS** 814 / 814 rows (and 76,886 / 76,886 in the reach pass) |
| Y2 OSD control (0 allowed) | **PASS** 0 of 19 |
| Y3 synthetic round trip | **PASS** 6 tests, amended (below) |
| Y4 shuffled truth (≤ 2 % of 795) | **FAIL: 167 of 795 = 21.0 %** |

Raw `P` for the record, not a reading: `enc_match` 788 / 795 = 99.1 % [98.4, 99.7] (`call_eq` 788, and `hash_eq` on all 788; placeholder rows 0, so P without them is the same).

## Why Y4 fired, and what it means

793 of the 795 rows are CQ messages (`icq` = 1). For a CQ, `hash_eq` is vacuous (T is a CQ), so the whole match rests on X's decoded call equalling a call token of T. The shuffled control pairs each X with another row's T, at least 30 min apart, and 21 % still match: a station that calls CQ repeatedly for more than half an hour recurs, and recurrence is exactly what call equality cannot tell from a mis-packed truth. §18.1 anticipated recurrence and allowed 2 %; the data show far more of it. So **call equality alone does not discriminate a mis-packed truth from a recurring CQ station**, and the instrument cannot support a CONFIRMED/REJECTED reading at the bars as written.

Descriptive contrast, not a reading: same-row 99.1 % against shuffled-row 21.0 %. The same-row figure is high because the call is the row's own station; the control shows how much of that is explained by recurrence alone.

## Y3, amended (reported to the Architect on the day)

The pinned DLL never emits type 4: its std path packs any compound or non-standard call as a standard message with a 22-bit hash (`n28 = NTOKENS + n22`, `message.c:715-726`; `ftx_message_encode` tries std first, `message.c:138-148`), so "DLL-packed type-4 texts" cannot exist. Y3 was therefore pinned two other ways, committed before Y1: `hash12` equals the DLL's own `n22 >> 10` on 100 % of the synthetic compound-call texts the DLL packed (≥ 100, Q-prefixed calls), and the type-4 layout round-trips against an independent transcription of `message.c`'s byte-shift packer over 200 random field sets. The same code-reading fact is the mechanism behind the FIELD-ID pointer: for a compound-call CQ, the vendored encoder returns a hashed standard message (i3 = 1) where WSJT-X sends type 4.

## Mutants

Both mutants (keep `RR73` as a token; drop `/P` suffixes) move rows in the unit tests but **moved 0 rows in the data** (788 each): the CQ rows contain neither. Shown, as §18.1 asks, but they cannot be said to bear on this population.

## How far a type-4 truth defect reaches (descriptive, §18.1 item 4)

Over all CRC-valid outputs (C3 39,357; G 37,529):

| Set | X i3 = 4 vs T i3 = 1 | scored right | scored wrong in total |
|---|---|---|---|
| C3 | 815 | 0 | 1,567 (52 %) |
| G | 283 | 0 | 645 (44 %) |

No type-4 output is ever scored right: the truth for such a message is a hashed standard message, so whenever a decoder recovers what was on the air, the scorer calls it wrong. The defect, if real, therefore hits the wrong tallies in both directions equally, and touches roughly half of every wrong-payload count. Pair counts: `analysis_encid_reach.json`.

## Limits

One night, one band, offline; the verdict is about the control, not about the hypothesis. 793 of 795 rows are CQs, so the hash half of the rule was effectively not exercised.

## What it means

The honest state: the mechanism is a code-level fact (the encoder cannot produce type 4 for these texts), the data agree (99.1 % call equality, no type-4 output ever scored right), and the pre-registered control says that call equality alone is too weak to turn that into a reading. A stronger discriminator for CQ messages is needed (for example the grid: a type-4 CQ carries no grid, so T's own text should show whether WSJT-X printed one), or a control that excludes recurring stations. Either is a new amendment; I have not run anything beyond §18.

Files: `encid_rows.json`, `encid_reach_rows.json`, `analysis_encid.json`, `analysis_encid_reach.json`; numbers only in `artefacts/rr_2026-10-07_coh_gain_encid/` (HK-037).
