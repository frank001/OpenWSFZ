# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-06 (`4c7d5ad`)

Same method as `results/REDACTION-MAP.md` (ROW 0's own redaction pass), `REDACTION-MAP-M1-M4.md`, `REDACTION-MAP-ROW0K.md`, and `results/2026-09-03-35378b9/REDACTION-MAP.md` -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is decoder output at S5/S7 noise-floor SNR (RUNBOOK.md Sec.7.5's documented phenomenon: the FT8 CRC occasionally passes for a random bit pattern that happens to be callsign-shaped), never injected truth -- verified against this run's own `truth.csv` `message_text` column before rewriting (see `redact_s1s8_20260906_decodes.py`'s guard step).

Placeholders use a `906` infix (`<RDCT906nn>`), tied to this run's date and distinct from every prior redaction pass's own placeholder namespace, so tokens from different passes are never confused if files are read together. Deliberately NOT Q-prefix, for the same reason as the other maps: a Q-prefix placeholder would be indistinguishable from a legitimately injected synthetic call and would corrupt a future `truth.csv` join.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCT90601>` | `CS-08e05b` |
| `<RDCT90602>` | `CS-11069c` |
| `<RDCT90603>` | `CS-1e88b5` |
| `<RDCT90604>` | `CS-1fff51` |
| `<RDCT90605>` | `CS-297796` |
| `<RDCT90606>` | `CS-49f2a2` |
| `<RDCT90607>` | `CS-4b3faf` |
| `<RDCT90608>` | `CS-50f19b` |
| `<RDCT90609>` | `CS-52383a` |
| `<RDCT90610>` | `CS-59afba` |
| `<RDCT90611>` | `CS-6ae69c` |
| `<RDCT90612>` | `CS-6c6185` |
| `<RDCT90613>` | `CS-6dae3f` |
| `<RDCT90614>` | `CS-730bd5` |
| `<RDCT90615>` | `CS-7e0fa9` |
| `<RDCT90616>` | `CS-825504` |
| `<RDCT90617>` | `CS-89c2b7` |
| `<RDCT90618>` | `CS-9daf38` |
| `<RDCT90619>` | `CS-b7ff2f` |
| `<RDCT90620>` | `CS-b88a45` |
| `<RDCT90621>` | `CS-c57194` |
| `<RDCT90622>` | `CS-cb1e31` |
| `<RDCT90623>` | `CS-cb30d8` |
| `<RDCT90624>` | `CS-cf3dc3` |
| `<RDCT90625>` | `CS-d5c35a` |
| `<RDCT90626>` | `CS-d779f7` |
| `<RDCT90627>` | `CS-f18e9f` |
