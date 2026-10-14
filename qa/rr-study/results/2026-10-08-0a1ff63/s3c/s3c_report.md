# S3c start-time edge guard: result

- Flag state: `subtractionEnabled = true`  (reference rates from a flag-OFF edge run: labelled, never pooled)
- Build: `3276573bc25c0c4fb4028d751f0cd62d46e2e31d`  DLL SHA-256 prefix: `2029b0804a9abcc3`
- Scenario SHA-256: `dc3a3fe87de0f227bf51e952cd085888ef3c873cc2a912f345c909a0af9604aa`

| decoder | part | L (s) | X / 32 | cycles with >= 1 decode | r_ref | k* | row |
|---|---|---:|---:|---:|---:|---:|---|
| WSJT-X | S3c-L90 | +2.75 | 32 | 4 of 4 | 0.893 | 24 | PASS |
| WSJT-X | S3c-L50 | +3.00 | 0 | 0 of 4 | 0.000 | 0 | DESCRIPTIVE (k* = 0) |
| WSJT-X | S3c-E90 | -1.75 | 32 | 4 of 4 | 0.893 | 24 | PASS |
| WSJT-X | S3c-E50 | -2.00 | 32 | 4 of 4 | 0.843 | 22 | PASS |
| OpenWSFZ | S3c-L90 | +2.75 | 32 | 4 of 4 | 0.893 | 24 | PASS |
| OpenWSFZ | S3c-L50 | +3.00 | 0 | 0 of 4 | 0.000 | 0 | DESCRIPTIVE (k* = 0) |
| OpenWSFZ | S3c-E90 | -1.75 | 32 | 4 of 4 | 0.893 | 24 | PASS |
| OpenWSFZ | S3c-E50 | -2.00 | 23 | 3 of 4 | 0.282 | 4 | DESCRIPTIVE (cycle-clustered, effective n ~ cycles) |

## Rows

- **S3c-WSJT-X (validity):** PASS
- **S3c-OWSFZ (guard):** PASS

A FAIL of the OpenWSFZ guard is a flag, not a verdict (one battery's 32 signals per part cannot tell a regression from bad luck at the 1 % level). ~8 % chance of at least one false FAIL somewhere per battery (4 parts x 2 decoders at 1 %), accepted by the spec. Counts only (NFR-021).

OpenWSFZ S3c-E50 (E -2.00) is a DESCRIPTIVE row from the battery after 2026-10-05 (Architect ruling 4c): the cell passes or fails a whole cycle at a time, so read 'cycles with >= 1 decode, of 4' beside the count; the early-side guard is S3c-E90.
- WSJT-X: planted slots with any decode pass 8/8; planted texts in the wrong cycle: 0
- OpenWSFZ: planted slots with any decode pass 8/8; planted texts in the wrong cycle: 0
