# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-12/13 (`4584900d`)

Same method as `results/REDACTION-MAP.md` (ROW 0's own redaction pass) and the 2026-09-03/06/07/12 sweeps' own maps -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is verified against this run's own `truth.csv` `message_text` column before rewriting (see `redact_s1s8_20260912b_decodes.py`'s guard step) -- none appear inside any injected truth message, so all are decoder output, never injected truth.

Placeholders use a sha-based `45849` infix (`<RDCT45849nn>`), distinct from every prior pass's own infix (`RDCTnn`, `RDCTMnn`, `RDCTKnn`, `RDCTSnn`, `RDCT906nn`, `RDCT7nn`, `RDCT912nn`) so tokens from different redaction passes are never confused if files are read together. A date infix would have collided with the 2026-09-12 sweep's own `RDCT912` pass (same calendar start date, different run/sha) -- hence sha-based here. Deliberately NOT Q-prefix, for the same reason as the other maps: a Q-prefix placeholder would be indistinguishable from a legitimately injected synthetic call and would corrupt a future `truth.csv` join.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCT4584901>` | `CS-01304b` |
| `<RDCT4584902>` | `CS-6996c7` |
| `<RDCT4584903>` | `CS-759071` |
| `<RDCT4584904>` | `CS-a7be87` |
| `<RDCT4584905>` | `CS-dc43e0` |
| `<RDCT4584906>` | `CS-e047ad` |
| `<RDCT4584907>` | `CS-efa450` |
