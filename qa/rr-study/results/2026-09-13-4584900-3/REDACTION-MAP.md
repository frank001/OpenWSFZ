# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-13 (`4584900d`, sweep 4 of 6)

Same method as prior sweeps' own maps -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is verified against this run's own `truth.csv` `message_text` column before rewriting (see `redact_s1s8_20260913c_decodes.py`'s guard step) -- none appear inside any injected truth message, so all are decoder output, never injected truth.

Placeholders use the `RDCT913C` infix, distinct from every prior pass's own infix. Deliberately NOT Q-prefix, for the same reason as the other maps.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCT913C01>` | `CS-00e8df` |
| `<RDCT913C02>` | `CS-01304b` |
| `<RDCT913C03>` | `CS-5065a6` |
| `<RDCT913C04>` | `CS-6996c7` |
| `<RDCT913C05>` | `CS-759071` |
| `<RDCT913C06>` | `CS-79f56e` |
| `<RDCT913C07>` | `CS-a7be87` |
| `<RDCT913C08>` | `CS-baf958` |
| `<RDCT913C09>` | `CS-d12153` |
| `<RDCT913C10>` | `CS-dc43e0` |
| `<RDCT913C11>` | `CS-ddd9b0` |
| `<RDCT913C12>` | `CS-e047ad` |
| `<RDCT913C13>` | `CS-eab2db` |
| `<RDCT913C14>` | `CS-efa450` |
