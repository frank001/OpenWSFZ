# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-13 (`4584900d`, sweep 5 of 6)

Same method as prior sweeps' own maps -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is verified against this run's own `truth.csv` `message_text` column before rewriting (see `redact_s1s8_20260913d_decodes.py`'s guard step) -- none appear inside any injected truth message, so all are decoder output, never injected truth.

Placeholders use the `RDCT913D` infix, distinct from every prior pass's own infix. Deliberately NOT Q-prefix, for the same reason as the other maps.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCT913D01>` | `CS-00e8df` |
| `<RDCT913D02>` | `CS-01304b` |
| `<RDCT913D03>` | `CS-48515e` |
| `<RDCT913D04>` | `CS-5065a6` |
| `<RDCT913D05>` | `CS-6996c7` |
| `<RDCT913D06>` | `CS-759071` |
| `<RDCT913D07>` | `CS-79f56e` |
| `<RDCT913D08>` | `CS-a7be87` |
| `<RDCT913D09>` | `CS-baf958` |
| `<RDCT913D10>` | `CS-c5840d` |
| `<RDCT913D11>` | `CS-d12153` |
| `<RDCT913D12>` | `CS-dc43e0` |
| `<RDCT913D13>` | `CS-ddd9b0` |
| `<RDCT913D14>` | `CS-e047ad` |
| `<RDCT913D15>` | `CS-eab2db` |
| `<RDCT913D16>` | `CS-efa450` |
