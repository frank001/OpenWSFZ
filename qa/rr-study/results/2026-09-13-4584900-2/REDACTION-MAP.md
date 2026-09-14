# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-13 (`4584900d`, sweep 3 of 6)

Same method as prior sweeps' own maps -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is verified against this run's own `truth.csv` `message_text` column before rewriting (see `redact_s1s8_20260913b_decodes.py`'s guard step) -- none appear inside any injected truth message, so all are decoder output, never injected truth.

Placeholders use the `RDCT913B` infix, distinct from every prior pass's own infix. Deliberately NOT Q-prefix, for the same reason as the other maps: a Q-prefix placeholder would be indistinguishable from a legitimately injected synthetic call and would corrupt a future `truth.csv` join.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCT913B01>` | `CS-00e8df` |
| `<RDCT913B02>` | `CS-01304b` |
| `<RDCT913B03>` | `CS-5065a6` |
| `<RDCT913B04>` | `CS-6996c7` |
| `<RDCT913B05>` | `CS-759071` |
| `<RDCT913B06>` | `CS-79f56e` |
| `<RDCT913B07>` | `CS-a7be87` |
| `<RDCT913B08>` | `CS-d12153` |
| `<RDCT913B09>` | `CS-dc43e0` |
| `<RDCT913B10>` | `CS-e047ad` |
| `<RDCT913B11>` | `CS-eab2db` |
| `<RDCT913B12>` | `CS-efa450` |
