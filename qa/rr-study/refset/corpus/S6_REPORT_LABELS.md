# Standing labels for every S6 (REFERENCE-SET) report and R&R Dossier

Source of the rules: REFERENCE-SET 2j, 2k (`arch/reference-set`) and the frozen corpus `rr-s6-refset-corpus` (the README of the corpus is frozen and cannot carry later disclosures; this file does). A report generator (`render_rr_dossier.py`, not built yet) must emit these lines; a report that lacks one is incomplete.

1. **Corpus line (header):** corpus name `rr-s6-refset-corpus`, `manifest.json` SHA-256 `13a7b9c91dfb1b85f08318acce53aef14d5269b523e61ac391bf5be4325217ce`, `verify_corpus.py` result at the start of the run, usable blocks 192 (7,680 cycles, 32.00 h), W 8 + L 32.
2. **10 m:** "ABSENT: no correctly framed 10 m recording on disk."
3. **17 m, on EVERY 17 m figure:** "**single run, hum-heavy (scan)**". Basis (Architect 2k, checked by QA against `scan_cycles.csv`): the only 17 m run (`20260808_live_run_1154-8080-17m`) has median hum2-over-floor 39.5 dB (OpenWSFZ) and 37.9 dB (WSJT-X); 187 of 1,080 OpenWSFZ and 160 of 1,080 WSJT-X cycles are above 50 dB, maximum 82.5 dB. The only other run with any cycle above 50 dB is `20260925_2010` (4 OpenWSFZ, 3 WSJT-X of 560).
4. **17 m night EMPTY; 17 m twilight 3 blocks; 80 m 27 blocks, single run.** Any 17 m or 80 m result is labelled single-run.
5. **Route:** every per-route figure shows the label of its runs: "logged (audio-setup log)" (`20261004_1634`, `20261009_1752`: 23 blocks) or "attested, mid-run unverified" (the other nine runs: 173 blocks). No pooled route figure without saying which routes it pools.
6. **Hum and spur:** descriptive only. The decoder-input tap (3c (b)) compares hum and spur PER CYCLE against that cycle's own corpus-scan row in `scan_cycles.csv`, never against the fixed 20 dB / 40 dB bars (the bars sit at the population median: run medians 17.6 to 39.5 dB of hum2 against a bar of 20; peak-to-median 36.8 to 50.8 dB against a bar of 40).
7. **Appraiser:** WSJT-X 2.7.0 (attested; the PRECHECK canary measures that the running install decodes Q-prefix calls), recording `wsjtx.exe_sha256`; the off-air corpus itself carries real calls, so reports hold aggregates only (HK-037).
8. **Excluded blocks (4, never deleted):** `f3b9904a7a04`, `038968ae4d02`, `24855c3896ab`, `76da3b4de513` (corpus scan: silent source dropouts); a run skips them and says so.
9. **Not comparable:** a different corpus folder is a different S6 series; Linux and Windows runs are separate series unless a ruling says otherwise.
