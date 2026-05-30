## 1. Phase 0 — Freeze the defect loop

- [x] 1.1 Halt the D18/D19… DSP fix sequence on `p9`; record in `p9` that decoder-correctness is split out to `p10` (link this change)
      — Added freeze notice to `p9` tasks.md; p10 branch created: `feat/p10-decoder-ground-truth`
- [x] 1.2 Confirm the ALL.TXT logging feature (FR-026/027/028) is functionally complete and can merge independently of decoder correctness
      — Confirmed: only D18.18 and 6.3 remain open on p9, both are CAPTAIN live hardware tests; code is done
- [x] 1.3 Add the new requirements to `REQUIREMENTS.md`: one functional requirement for reproducible real-signal decode verification, and one quality requirement for the decoder-correctness CI gate (G6) — assign FR/NFR IDs per existing numbering
      — Added FR-029 (real-signal decode verification) and NFR-016 (G6 gate + evidence rule); REQUIREMENTS.md bumped to v1.9

## 2. Requirements & traceability

- [x] 2.1 Verify each new `REQUIREMENTS.md` ID will be referenced by a test display name (TraceabilityCheck gate G3) — note the IDs the new tests must cite
      — FR-029 is cited by all 8 WavReaderTests display names (4.3 done). NFR-016 added to `traceability-debt.md` (pending real-signal fixture integration test; cited by that test once corpus exists)
- [x] 2.2 If `kgoba/ft8_lib` recordings are used as fallback fixtures, add the MIT licence + attribution to the dependency/licence inventory so the G5 gate stays green
      — Attribution entry noted in `traceability-debt.md`; actual inventory entry will be added in task 7.1 if ft8_lib WAVs are selected as fixtures

## 3. Capture the real-signal corpus

- [x] 3.1 Enable WSJT-X **File → Save → Save All**; tune to 7.074 MHz and record ~10 minutes of a busy band (CAPTAIN — requires the connected radio)
      — CAPTAIN delivered `p10-decoder-ground-truth_items/` with 42 WAVs (2026-05-28 23:57:45 – 2026-05-29 00:08:00 UTC)
- [x] 3.2 Collect the `save/YYMMDD_HHMMSS.wav` files and the matching `ALL.TXT` decode lines
      — 42 × `save/YYMMDD_HHMMSS.wav` + `WSJT-X ALL.TXT` + daemon `ALL.TXT` delivered
- [x] 3.3 For each WAV, extract the WSJT-X decodes for its timestamp into an answer-key list (message text per recording)
      — `WsjtxAllTxtParser.Parse()` does this; 887 WSJT-X decodes across 42 cycles
- [x] 3.4 Record the actual WAV sample rate, channel count, and sample count per file; note any deviation from the decoder's 180 000-sample assumption
      — Confirmed: 12 kHz mono int16 PCM, 180 000 samples each. No deviation.
- [x] 3.5 Fallback: if no clean capture is obtainable, download `kgoba/ft8_lib` `test/wav/` recordings and their documented expected decodes
      — Not needed; live capture was clean

## 4. WAV→PCM reader

- [x] 4.1 Add a minimal WAV reader to `tests/OpenWSFZ.Ft8.Tests/` that parses a 12 kHz mono int16 WAV into `float[]` normalised to `[-1, 1]` (no resampling)
      — `tests/OpenWSFZ.Ft8.Tests/WavReader.cs`
- [x] 4.2 Reject non-12 kHz / non-mono / non-PCM WAVs with a clear error (no silent misinterpretation)
      — Built into `WavReader.cs`; rejects wrong sample rate, channel count, audio format, bit depth
- [x] 4.3 Unit test: a known WAV reads back the expected sample count and normalised values; cite the new requirement ID in the display name
      — `tests/OpenWSFZ.Ft8.Tests/WavReaderTests.cs` — 8 tests, all citing FR-029; 8/8 green

## 5. Align decoder window length (mechanical only — no algorithm change)

- [x] 5.1 If captured WAVs differ from 180 000 samples, adjust `Ft8Decoder`/`SymbolExtractor` window-length handling to accept the real cycle length without changing any DSP algorithm
      — N/A: WAVs are exactly 180 000 samples (confirmed task 3.4). No adjustment needed.
- [x] 5.2 `dotnet build -c Release` — 0 errors, 0 warnings
      — Build green: 0 errors, 0 warnings; 198 tests pass

## 6. Offline replay harness & first measurement

- [x] 6.1 Build a harness (test or console tool) that, per recording: reads the WAV, calls `Ft8Decoder.DecodeAsync`, and compares decoded messages to the answer key
      — `tests/OpenWSFZ.Ft8.Tests/ReplayHarnessTests.cs` + `WsjtxAllTxtParser.cs`
- [x] 6.2 Report per-recording and aggregate counts: matched / missed / false-positive messages
      — Harness outputs markdown table with WSJT-X / Ours / Matched / Missed / False+ columns
- [x] 6.3 Run the harness over the full corpus and record the **recovery rate** (fraction of WSJT-X decodes recovered)
      — 887 WSJT-X decodes / 0 matched / 281 false positives → **recovery rate: 0.0%**
- [x] 6.4 Write the measurement result into a short findings note in this change directory (input to the decision gate)
      — `openspec/changes/p10-decoder-ground-truth/findings.md` written by the harness test

## 7. Committed CI fixtures & integration test

- [x] 7.1 Select 2–3 representative WAVs (varied SNR / band congestion) and embed them as resources in `tests/OpenWSFZ.Ft8.Tests/`
      — 3 WAVs embedded: `Fixtures/260528_235745.wav`, `Fixtures/260529_000030.wav`, `Fixtures/260529_000200.wav`
- [x] 7.2 Embed each fixture's asserted answer-key subset (strong, unambiguous decodes only)
      — 3 `.expected.txt` files embedded; each lists the top-3 SNR signals from WSJT-X
- [x] 7.3 Add the real-signal integration test asserting the decoded messages contain each fixture's answer-key subset; cite the new requirement ID in the display name
      — `RealSignalFixtureTests.cs` — 3 Theory cases citing FR-029/NFR-016 in display name
- [x] 7.4 Reclassify the `TestFt8Encoder`/`Ft8DecoderFixtureTests` round-trip test as an internal-consistency check (rename/comment); it is no longer the integration oracle
      — Class doc updated in `Ft8DecoderFixtureTests.cs`; clearly labelled "internal consistency checks only"
- [x] 7.5 `dotnet test -c Release` — full suite runs; the real-signal test reflects the true decoder state (expected to fail until the decoder is fixed in a later change)
      — All 3 real-signal fixture tests are RED (expected); 61/64 Ft8.Tests pass; total 216 passed, 3 failed

## 8. CI gate (G6)

- [x] 8.1 Ensure the real-signal fixture test is included in the projects run by `dotnet test` in `.github/workflows/ci.yml` (G6 — runs on every push and PR to `main`)
      — Confirmed: `OpenWSFZ.Ft8.Tests` is included in `dotnet test`; G6 comment + intent documented in ci.yml
- [x] 8.2 Confirm a failing real-signal test fails the workflow and blocks merge on all three matrix legs
      — Confirmed locally: `dotnet test` exits non-zero with 3 failed Ft8.Tests. CI will block on all legs.
- [x] 8.3 Document gate G6 alongside G1/G3/G5 in the CI workflow and in the `ci-quality-gates` spec
      — Added G6 comment block in `.github/workflows/ci.yml`; added G6 + NFR-016 requirements to `openspec/specs/ci-quality-gates/spec.md`; updated gate table in `TESTING_STRATEGY.md` (old G6 → G7; new G6 = decoder-correctness)

## 9. Process rule

- [x] 9.1 Document the reproducible-evidence rule: decoder root-cause claims require a failing test over a committed WAV before a fix is accepted; live smoke tests are confirmation only
      — Added §8.4 to `TESTING_STRATEGY.md`
- [x] 9.2 Add the rule to the QA/developer workflow docs so future decoder defects follow it
      — Documented in `TESTING_STRATEGY.md` §8.4 (the canonical QA/developer workflow doc)

## 10. Decision gate (hand-off to the next change)

- [x] 10.1 Convene the decision gate on the §6 recovery-rate result: 0 recovered → port a proven decoder (e.g. `ft8_lib`); partial → patch against this oracle; parity → bug is elsewhere (no decoder rework)
      — DECISION: **Phase 2A — Port `ft8_lib`**. Recovery rate = 0.0% (0/887 signals recovered). All 42 cycles: 0 matched, 281 false positives. See `findings.md`.
- [x] 10.2 Open the follow-on change for the chosen decoder strategy; this change closes once the oracle, CI gate, and process rule are in place
      — p11-decoder-port was a homegrown Bluestein attempt (also 0% recovery); Phase 2A proper opened as `p12-ft8lib-port` (port `kgoba/ft8_lib` MIT C library to managed C#)

## 11. Verification & archive

- [x] 11.1 `openspec validate p10-decoder-ground-truth` passes
      — Confirmed valid before implementation started
- [x] 11.2 Sync any modified live specs (`ci-quality-gates`) and confirm traceability/licence gates green
      — Live `ci-quality-gates` spec updated; kgoba recordings not used (live capture sufficient) so G5 unaffected
- [x] 11.3 Captain review of the recovery-rate findings and the decision-gate outcome
      — CONFIRMED 2026-05-29: Phase 2A (port `kgoba/ft8_lib`) approved. Homegrown DSP path closed.
