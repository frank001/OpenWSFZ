# NFR-021 redaction map -- S1-S8 full sweep, 2026-09-03 (`35378b9`)

Same method as `results/REDACTION-MAP.md` (ROW 0's own redaction pass), `REDACTION-MAP-M1-M4.md`, and `REDACTION-MAP-ROW0K.md` -- imported from the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`), not reimplemented. Every token below is decoder output at S5/S7 noise-floor SNR (RUNBOOK.md Sec.7.5's documented phenomenon: the FT8 CRC occasionally passes for a random bit pattern that happens to be callsign-shaped), never injected truth -- verified against this run's own `truth.csv` `message_text` column before rewriting (see `redact_s1s8_20260903_decodes.py`'s guard step).

Placeholders use an `S` infix (`<RDCTSnn>`) distinct from ROW 0's own `<RDCTnn>`, M1-M4's `<RDCTMnn>`, and ROW 0k's `<RDCTKnn>` placeholders so tokens from different redaction passes are never confused if files are read together. Deliberately NOT Q-prefix, for the same reason as the other maps: a Q-prefix placeholder would be indistinguishable from a legitimately injected synthetic call and would corrupt a future `truth.csv` join.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. One-way by construction.

| placeholder | token fingerprint |
|---|---|
| `<RDCTS01>` | `CS-04e523` |
| `<RDCTS02>` | `CS-05bca6` |
| `<RDCTS03>` | `CS-192feb` |
| `<RDCTS04>` | `CS-1bf466` |
| `<RDCTS05>` | `CS-1e15c6` |
| `<RDCTS06>` | `CS-22cd48` |
| `<RDCTS07>` | `CS-2392ff` |
| `<RDCTS08>` | `CS-410076` |
| `<RDCTS09>` | `CS-5219c4` |
| `<RDCTS10>` | `CS-56391e` |
| `<RDCTS11>` | `CS-759071` |
| `<RDCTS12>` | `CS-788f02` |
| `<RDCTS13>` | `CS-7a47ce` |
| `<RDCTS14>` | `CS-7aa1c0` |
| `<RDCTS15>` | `CS-7e22d9` |
| `<RDCTS16>` | `CS-7fc608` |
| `<RDCTS17>` | `CS-857bd8` |
| `<RDCTS18>` | `CS-91217c` |
| `<RDCTS19>` | `CS-934eaf` |
| `<RDCTS20>` | `CS-9fe4f2` |
| `<RDCTS21>` | `CS-a1bd87` |
| `<RDCTS22>` | `CS-a66abb` |
| `<RDCTS23>` | `CS-b22a7f` |
| `<RDCTS24>` | `CS-bbfc31` |
| `<RDCTS25>` | `CS-bcbbcf` |
| `<RDCTS26>` | `CS-c2ebb9` |
| `<RDCTS27>` | `CS-df2d82` |
| `<RDCTS28>` | `CS-e3f8f6` |
