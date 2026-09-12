# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-12 (`fbf8c0b5`)

Same method as `results/REDACTION-MAP.md` (ROW 0's own redaction pass), `REDACTION-MAP-M1-M4.md`, `REDACTION-MAP-ROW0K.md`, and the 2026-09-03/09-06/09-07 sweeps' own maps -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is decoder output at S5 noise-floor SNR (RUNBOOK.md Sec.7.5's documented phenomenon: the FT8 CRC occasionally passes for a random bit pattern that happens to be callsign-shaped), never injected truth -- verified against this run's own `truth.csv` `message_text` column before rewriting (see `redact_s1s8_20260912_decodes.py`'s guard step). This run is the routine post-merge sweep against `fbf8c0b5` (`NHARD40-DEFAULT` 60->40 default, PRs #161/#162/#163); the flagged tokens are the two S5 Gate A noise-floor events (both AWGN, -19/-22 dB) that Gate A's own per-sweep reading counts as 0/120 FP events on the ratified scoring (they fall outside Gate A's own event definition) but which still appear verbatim in the raw decoder logs and matched CSVs and must not reach git unredacted.

Placeholders use a `912` infix (`<RDCT912nn>`) distinct from ROW 0's own `<RDCTnn>`, M1-M4's `<RDCTMnn>`, ROW 0k's `<RDCTKnn>`, the 2026-09-03 sweep's `<RDCTSnn>`, the 2026-09-06 sweep's `<RDCT906nn>`, and the 2026-09-07 sweep's `<RDCT7nn>` placeholders so tokens from different redaction passes are never confused if files are read together. Deliberately NOT Q-prefix, for the same reason as the other maps: a Q-prefix placeholder would be indistinguishable from a legitimately injected synthetic call and would corrupt a future `truth.csv` join.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCT91201>` | `CS-6996c7` |
| `<RDCT91202>` | `CS-e047ad` |
