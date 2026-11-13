**User-facing:** no (a new configuration key, default OFF; the shipped behaviour does not change)

## Why

On the night `20261110_1817`, 22.9 % of the WSJT-X rows OpenWSFZ missed (520 rows, 3.72 pp of the reference) are exact repeats of a message it had decoded 30 to 90 s earlier within 10 Hz (QA's XC-PRIOR). A test that knows the WHOLE message fixes all 79 tones and needs no LDPC: summing the known tone's energy over the 79 symbols, in a +-3 Hz x +-0.12 s window around the prior's position on the fallback's residual buffer, detected 51 % of those rows at a measured false rate of 4.3e-4 per test (XC-TEMPLATE, a desk study, G = 1.91 pp). XC-BUILD builds that stage as **batch 6**, default OFF, with a **shadow null** (the same test on the opposite-parity priors, counted and never published) so the acceptance arms measure the false rate instead of inheriting it.

Authority: Architect spec `qa/rr-study/2026-11-13-1258-architect-to-qa-spec-xc-template-build.md` (`arch/cross-cycle-prior`, §1 R1 to R12 and §8 Amendment 1: R13, A1.1, A1.4); QA's (k) review `qa/rr-study/2026-11-13-1303-qa-k-review-xc-build.md` (`qa/same-chain` `fba6b4a3`, K1 to K6); the Captain's "go", 2026-11-13; QA task `dev-tasks/2026-11-13-xc-template-build.md` and fixtures `dev-tasks/2026-11-13-xc-template-fixtures.json`. The build is authorised behind a setting, default OFF, with the detection threshold a PLACEHOLDER. It does not authorise a default change.

## What Changes

- `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: bools `decoder.crossCyclePrior` and `decoder.crossCyclePriorShadow` (properties `CrossCyclePrior`, `CrossCyclePriorShadow`), absent = false. Config file and API overlay, HK-035; no Settings-page control.
- `src/OpenWSFZ.Ft8/Dsp/CrossCycleTemplateDetector.cs` (new, managed C# only): the XC-TEMPLATE statistic. A port of `coherent_extract.downconvert_decimate` and `correlate_symbols` and of `xt_lib.s_e` / `shift_baseband` / `search`: mix at the carrier, 61-tap Hann-windowed-sinc low-pass at 900 Hz, decimate by 6; per symbol a 320-point DFT at bins 0 to 7; 13 frequencies (the baseband shifted) x 25 start times; the managed form of the native `cf_snr_db` for the published SNR.
- `src/OpenWSFZ.Ft8/CrossCyclePriorStore.cs` (new): the per-decoder store of the messages published in batches 1 to 5 (last 6 cycles, 15 s slots, cleared on a band change, exact ages 2/4/6 live and 1/3/5 shadow) and the numbers-only diagnostic sink interface.
- `src/OpenWSFZ.Ft8/CrossCycleTemplateStage.cs` (new): the exclusions (already decoded, hashed, refused), and the parallel, nearest-first, budget-aware run.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs`: the two setters (`SetCrossCyclePrior`, `SetCrossCyclePriorShadow`), the internal `SetCrossCyclePriorThreshold` (T_E; `CrossCyclePriorThresholdDefault` = `+infinity`) and the internal `CrossCyclePriorProbe`; read once per cycle. `MapNative` records what batches 1 to 5 publish (only while ON). After the late round (or the fallback's batch) `RunCrossCycleStageAsync` runs the live stage and publishes batch 6 (`TemplateBatch` = 6, `PathTemplate` = 3) through the fallback's hand-off, then the shadow stage, then writes one counts-only `Cross-cycle prior:` line.
- `src/OpenWSFZ.Daemon/Program.cs`: the two setter calls, at both places (initial, per config change).
- **No native change.** `git diff --stat ce5734b6 HEAD -- native src/OpenWSFZ.Ft8/Native` is empty; `FT8_SHIM_VERSION` stays 20260072; `libft8.dll` SHA-256 stays `bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`.
- Tests (QA's fixtures as an embedded resource), `VERSION` 0.71 to 0.72 (every place the gates check), `REQUIREMENTS.md` FR-105 and a changelog row.

## The threshold

T_E is a shipped constant, **`double.PositiveInfinity` in this change**: nothing is detected, so ON with the shipped build publishes nothing and only writes the store and the log line. QA's TRAIN arm measures the shadow null's per-test S_E* (through the diagnostic sink) and freezes the value on the same build; it goes in before any merge. The desk value 3.0113 is not portable to a reimplementation nor to the product's own prior positions (spec R6).

## Out of scope

Any change to batches 1 to 5, the fallback, the late round, F1b, R-F4, multi-set, L1', CQ-AP, v2, the 13 s budget or `native/`; a Settings-page control; turning the setting ON by default; hashed (`<...>`) messages (14.4 % of the E1 rows: out of reach until #60); a PSK Reporter policy for batch-6 rows (see design D8).

## Era

None while the setting is OFF. Turning it ON on the station starts a new live era; live figures are never pooled across it.

## Capabilities

### New Capabilities

- `ft8-cross-cycle-template-prior`: the two settings, the prior store, the managed template detector, batch 6, the shadow null, the budget, the log line and the diagnostic sink.
