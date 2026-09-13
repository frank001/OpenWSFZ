# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-13 (`4584900d`, sweep 6 of 6, final)

Same method as prior sweeps' own maps -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is verified against this run's own `truth.csv` `message_text` column before rewriting (see `redact_s1s8_20260913e_decodes.py`'s guard step) -- none appear inside any injected truth message, so all are decoder output, never injected truth.

Placeholders use the `RDCT913E` infix, distinct from every prior pass's own infix. Deliberately NOT Q-prefix, for the same reason as the other maps.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCT913E01>` | `CS-00e8df` |
| `<RDCT913E02>` | `CS-01304b` |
| `<RDCT913E03>` | `CS-3794e8` |
| `<RDCT913E04>` | `CS-48515e` |
| `<RDCT913E05>` | `CS-4cc356` |
| `<RDCT913E06>` | `CS-5065a6` |
| `<RDCT913E07>` | `CS-6996c7` |
| `<RDCT913E08>` | `CS-759071` |
| `<RDCT913E09>` | `CS-79f56e` |
| `<RDCT913E10>` | `CS-a7be87` |
| `<RDCT913E11>` | `CS-baf958` |
| `<RDCT913E12>` | `CS-c5840d` |
| `<RDCT913E13>` | `CS-d12153` |
| `<RDCT913E14>` | `CS-dc43e0` |
| `<RDCT913E15>` | `CS-ddd9b0` |
| `<RDCT913E16>` | `CS-e047ad` |
| `<RDCT913E17>` | `CS-e18ab9` |
| `<RDCT913E18>` | `CS-e6d3bc` |
| `<RDCT913E19>` | `CS-eab2db` |
| `<RDCT913E20>` | `CS-efa450` |
