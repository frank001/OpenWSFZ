## 1. Tests first (Developer, `7ca00264`)

- [x] 1.1 D1: the pattern forces exactly 32 positions, `[0,29)` and `[74,77)`, each equal to the bit ft8_lib's own encoder produces for `CQ Q1ABC JO22`; the forced LLRs are written after normalisation at 1.01 times the largest |LLR| of the non-forced entries (`CqApNativeTests`).
- [x] 1.2 D1b: with the right-sign override the attempt decodes a clean encoded `CQ Q1ABC JO22`; with the opposite-sign override it does not.
- [x] 1.3 D2: the setting defaults to `false` (absent key, missing `decoder` section, `new DecoderConfig()`); an explicit value survives a load, an unrelated save and a reload; the config POST is an overlay (`CqApConfigTests`, `CqApApiTests`); the flag reaches native before every decode (`CqApDecoderWiringTests`); with the flag off nothing is counted and nothing is tagged.
- [x] 1.4 D3 and D4: never instead (a candidate the normal attempt decodes is not an attempt); a CQ-AP decode goes through dedup, clears the coherent-fallback eligibility and stores its payload; the OSD counter reads 0 on the production path and can count (`CqApNativeTests`, `CqApStagedTests`).
- [x] 1.5 D5 to D7: an implausible CQ-AP decode is dropped; the tag reaches `DecodeResult`; one `cq-ap:` line per cycle only while the flag is on; a `cq` decode is not uploaded and is counted under `ap=` on both PSK Reporter accounting lines and in the status counters (`PskReporterCqApTests`).
- [x] 1.6 D10: a weak `CQ Q1ABC JO22` is decoded more often with the flag on, and tagged; a non-CQ is never tagged `cq`; noise-only audio gives no `cq` decode over 240 cycles.

## 2. Implementation (Developer)

- [x] 2.1 Native: `ftx_decode_candidate_cq_ap`, `ftx_cq_ap_inject` and the probe in `decode.c`; the exports `ft8_set_cq_ap`, `ft8_get_last_ap_kinds`, `ft8_get_last_cq_ap_stats`, `ft8_cq_ap_pattern`, `ft8_cq_ap_probe_llrs`; the attempt inside the `decoded` determination in `ft8_decode_all`; `FT8_SHIM_VERSION` 20260072; `rebuild_shim.bat` export list.
- [x] 2.2 Managed: `DecoderConfig.CqApEnabled`, `Ft8Decoder.SetCqApEnabled`, the per-cycle counters and log line, `ApKind` on `DecodeResult`, the wire struct and the aligned getter, the `ap=` exclusion in `PskReporterEngine`, the daemon wiring.
- [x] 2.3 `VERSION` 0.70, README and REQUIREMENTS anchors, FR-103 and changelog row 1.66; this change's proposal, design and delta spec.

## 3. Verification

- [ ] 3.1 Full unfiltered `dotnet test OpenWSFZ.slnx`; `openspec validate --all --strict`; `python tools/check_version_bump.py origin/main` (G9a, G9b).
- [x] 3.2 QA: HK-039 review record before any replay: `qa/rr-study/2026-11-10-1655-qa-code-review-cq-ap-7ca00264-APPROVED.md`; 23 of 23 CqAp tests with the committed and a rebuilt DLL; eleven mutations killed.
- [ ] 3.3 QA: Replay81 `--cq-ap on|off` and the `apKind` column, with a dry run on the reviewed build before the freeze.
- [ ] 3.4 QA: the A1.3 positive control (synthetic `CQ Q...`, 1 dB steps from OFF's 50 % SNR minus 4 dB to plus 1 dB, at least 200 cycles per step; at some step ON exceeds OFF by at least 10 percentage points with separated Wilson-95 intervals). A fail sends the build back; no replay arm runs.
- [ ] 3.5 QA: the live session corpus (the Captain's; WSJT-X alongside with its PSK spotting off, `cycleAudioArchive` on and read back, the MQTT recorder from before the daemon start, at least 3 h), the freeze, the OFF and ON arms, the report. Turning the setting ON is a new era and is the Captain's decision after the Architect's ruling.
- [ ] 3.6 QA: `python tools/pre_merge_check.py` from a clean checkout of the exact commit before any push (HK-006); the Linux and macOS binaries are refreshed by the follow-up chore after the native merge.
