# NFR-021 redaction map -- S5-LEVEL ROW 0k decode CSVs

Same method as `results/REDACTION-MAP.md` (ROW 0's own redaction pass) and `REDACTION-MAP-M1-M4.md` -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is decoder output on a signal-free (S5) offline replay, never injected truth -- verified against both renders' own `truth.csv` `message_text` columns before rewriting (see `redact_row0k_decodes.py`'s guard step; S5 is signal-free so that guard set is empty).

Placeholders use a `K` infix (`<RDCTKnn>`) distinct from ROW 0's own `<RDCTnn>` and M1-M4's `<RDCTMnn>` placeholders so the three passes' tokens are never confused if the CSVs are read together. Deliberately NOT Q-prefix, for the same reason as the other two maps: a Q-prefix placeholder would be indistinguishable from a legitimately injected synthetic call and would corrupt a future `truth.csv` join.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCTK01>` | `CS-0620ab` |
| `<RDCTK02>` | `CS-33ca6b` |
| `<RDCTK03>` | `CS-c2ce7e` |
| `<RDCTK04>` | `CS-caa9c5` |
| `<RDCTK05>` | `CS-f329a8` |
| `<RDCTK06>` | `CS-fda80a` |
