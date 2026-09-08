# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-07 (`4cc1984`)

Same method as `results/REDACTION-MAP.md` (ROW 0's own redaction pass), `REDACTION-MAP-M1-M4.md`, `REDACTION-MAP-ROW0K.md`, and the 2026-09-03 sweep's own map -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is decoder output at S5 noise-floor SNR (RUNBOOK.md Sec.7.5's documented phenomenon: the FT8 CRC occasionally passes for a random bit pattern that happens to be callsign-shaped), never injected truth -- verified against this run's own `truth.csv` `message_text` column before rewriting (see `redact_s1s8_20260907_decodes.py`'s guard step). This run is the first live exercise of the S5-GATE-SIZING Amendment 1 Gate A / Check B population; all three flagged tokens fall inside Gate A's AWGN window (S5 parts 0/1) and were the cause of Gate A's FAIL verdict.

Placeholders use a `7` infix (`<RDCT7nn>`) distinct from ROW 0's own `<RDCTnn>`, M1-M4's `<RDCTMnn>`, ROW 0k's `<RDCTKnn>`, and the 2026-09-03 sweep's `<RDCTSnn>` placeholders so tokens from different redaction passes are never confused if files are read together. Deliberately NOT Q-prefix, for the same reason as the other maps: a Q-prefix placeholder would be indistinguishable from a legitimately injected synthetic call and would corrupt a future `truth.csv` join.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCT701>` | `CS-16550a` |
| `<RDCT702>` | `CS-2cdd97` |
| `<RDCT703>` | `CS-3e3d73` |
| `<RDCT704>` | `CS-4125bf` |
| `<RDCT705>` | `CS-46765c` |
| `<RDCT706>` | `CS-47dcf9` |
| `<RDCT707>` | `CS-4dc8d4` |
| `<RDCT708>` | `CS-4dd997` |
| `<RDCT709>` | `CS-55b579` |
| `<RDCT710>` | `CS-5a6dd0` |
| `<RDCT711>` | `CS-62e147` |
| `<RDCT712>` | `CS-662e65` |
| `<RDCT713>` | `CS-79f56e` |
| `<RDCT714>` | `CS-93825e` |
| `<RDCT715>` | `CS-9b3dcc` |
| `<RDCT716>` | `CS-a561a9` |
| `<RDCT717>` | `CS-acbb9c` |
| `<RDCT718>` | `CS-b41540` |
| `<RDCT719>` | `CS-c1f54a` |
| `<RDCT720>` | `CS-cfef2f` |
| `<RDCT721>` | `CS-d12153` |
| `<RDCT722>` | `CS-dd5af0` |
| `<RDCT723>` | `CS-e67dce` |
| `<RDCT724>` | `CS-f1273d` |
| `<RDCT725>` | `CS-f9648d` |
| `<RDCT726>` | `CS-faf23b` |
