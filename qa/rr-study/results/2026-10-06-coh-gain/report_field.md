# COH-GAIN FIELD-ID (Amendment 8, spec §17 / §17.1 / §17.2): what are the unexplained outputs?

QA, 2026-10-07. Offline, one night (`20261004_1634`), one band (40 m), DLL SHA-256 `2fa6d993…f365` (shim 20260058). Harness run, no test `--filter`. Row list `field_rows.json` SHA-256(LF) `0f4f4038…5f9a` (917 X + 215 OSD control), committed in `75fbdfee` before the extraction.

**First paragraph, per §17.2: E-ENC is 0 by construction. This is a property of the instrument, not a finding, and hypothesis (i) (the truth was mis-encoded) is NOT TESTED by this amendment.** The pinned DLL exports one packing per text (`ft8_encode_message`), so the alternative-packing set is the RR73 variant that `payload_match` already absorbs. The type-pair table below is a descriptive pointer toward (i), not a test of it.

## Reading

**E-RESIDUAL** (mechanical): `E` = (E-ADJ + E-QSO) / 917 = 33 / 917 = **3.6 % [2.4 %, 5.0 %]**, CI_hi < 0.50. Per §17.1 this makes **no claim about false decodes**; a second real transmitter, a mis-encoded truth and a false decode are not separated by these classes.

| Class | X rows (917) | OSD control (215) |
|---|---|---|
| E-ENC (0 by construction) | 0 | 0 |
| E-ADJ | 0 | 0 |
| E-QSO | 33 | 0 |
| E-G2 (not in E) | 294 | 0 |
| E-HASH | 28 | 3 |
| E-RESIDUAL | 562 | 212 |

Validity: **X1** 1,132 / 1,132 rows reproduced (C3 and G), 0 not. **X2** 0 of 215 OSD rows in E-ADJ / E-QSO / E-ENC (0 expected, tolerance 5 %). **X3** identity packing round-trips on every row, 0 failures. All PASS.

## The pointer (descriptive, post-hoc, not in E)

Message-type pairs `i3x` (decoded X) vs `i3t` (truth T, the re-encoded WSJT-X text), all 917 rows:

| X i3 vs T i3 | rows | of which E-RESIDUAL |
|---|---|---|
| 4 vs 1 | **795 (86.7 %)** | 527 |
| 1 vs 1 | 96 | 33 |
| 2 vs 2 | 22 | 0 |
| 0 vs 1 | 4 | 2 |

The OSD control (chance codewords) gives i3 = 4 on 19 of 215 (8.8 %, about the 1/8 expected). Among the X rows 86.7 % are i3 = 4 (non-standard message type) while the re-encoded truth is standard: that is not what unrelated outputs would look like. It is consistent with the on-air message being a non-standard packing that the vendored encoder re-packs as a standard one for the same WSJT-X text, i.e. hypothesis (i), but this instrument cannot say so. §17.2 reserves it as a pointer that would justify an encoder-level test.

Other descriptives: `adj` = none on all 917 (no neighbouring-cycle repeat); c1 equal on 34, c2 equal on 33, report/grid equal on 0; E-G2 total (G returned the same payload) 324 of 917 (294 after E-QSO; the 321 on file was over the 912 M-NONE rows).

## Limits

One night, one band, offline; E-ENC structurally unable to fire; layout "other" (799 rows) means the field flags are 0 for them, so E-QSO under-counts wherever X and T differ in layout. Not an upper or lower bound on false decodes.

## What it means

The reading says what it was built to say and no more: the unexplained outputs are not another period's message and not mostly the same QSO. The type-pair table is the one real lead. If most of these are non-standard messages that the truth encoder mis-packs, they are correct decodes scored wrong, and the 0.178 (and the WRONG-ID wrong-payload rate) would shrink. That is for the Architect and the Captain to decide: an encoder-level test needs a separate decision (new instrument, non-standard hash table).

Files: `field_rows.json`, `analysis_field.json`; numbers only in `artefacts/rr_2026-10-07_coh_gain_fieldid/field_rows.csv` (HK-037).
