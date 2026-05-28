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

- [ ] 3.1 Enable WSJT-X **File → Save → Save All**; tune to 7.074 MHz and record ~10 minutes of a busy band (CAPTAIN — requires the connected radio)
- [ ] 3.2 Collect the `save/YYMMDD_HHMMSS.wav` files and the matching `ALL.TXT` decode lines
- [ ] 3.3 For each WAV, extract the WSJT-X decodes for its timestamp into an answer-key list (message text per recording)
- [ ] 3.4 Record the actual WAV sample rate, channel count, and sample count per file; note any deviation from the decoder's 180 000-sample assumption
- [ ] 3.5 Fallback: if no clean capture is obtainable, download `kgoba/ft8_lib` `test/wav/` recordings and their documented expected decodes

## 4. WAV→PCM reader

- [x] 4.1 Add a minimal WAV reader to `tests/OpenWSFZ.Ft8.Tests/` that parses a 12 kHz mono int16 WAV into `float[]` normalised to `[-1, 1]` (no resampling)
      — `tests/OpenWSFZ.Ft8.Tests/WavReader.cs`
- [x] 4.2 Reject non-12 kHz / non-mono / non-PCM WAVs with a clear error (no silent misinterpretation)
      — Built into `WavReader.cs`; rejects wrong sample rate, channel count, audio format, bit depth
- [x] 4.3 Unit test: a known WAV reads back the expected sample count and normalised values; cite the new requirement ID in the display name
      — `tests/OpenWSFZ.Ft8.Tests/WavReaderTests.cs` — 8 tests, all citing FR-029; 8/8 green

## 5. Align decoder window length (mechanical only — no algorithm change)

- [ ] 5.1 If captured WAVs differ from 180 000 samples, adjust `Ft8Decoder`/`SymbolExtractor` window-length handling to accept the real cycle length without changing any DSP algorithm
      — Blocked on task 3.4 (must know real WAV sample count first)
- [x] 5.2 `dotnet build -c Release` — 0 errors, 0 warnings
      — Build green: 0 errors, 0 warnings; 198 tests pass

## 6. Offline replay harness & first measurement

- [ ] 6.1 Build a harness (test or console tool) that, per recording: reads the WAV, calls `Ft8Decoder.DecodeAsync`, and compares decoded messages to the answer key
      — Blocked on corpus capture (task 3.1)
- [ ] 6.2 Report per-recording and aggregate counts: matched / missed / false-positive messages
- [ ] 6.3 Run the harness over the full corpus and record the **recovery rate** (fraction of WSJT-X decodes recovered)
- [ ] 6.4 Write the measurement result into a short findings note in this change directory (input to the decision gate)

## 7. Committed CI fixtures & integration test

- [ ] 7.1 Select 2–3 representative WAVs (varied SNR / band congestion) and embed them as resources in `tests/OpenWSFZ.Ft8.Tests/`
      — Blocked on corpus capture (task 3.1)
- [ ] 7.2 Embed each fixture's asserted answer-key subset (strong, unambiguous decodes only)
- [ ] 7.3 Add the real-signal integration test asserting the decoded messages contain each fixture's answer-key subset; cite the new requirement ID in the display name
- [ ] 7.4 Reclassify the `TestFt8Encoder`/`Ft8DecoderFixtureTests` round-trip test as an internal-consistency check (rename/comment); it is no longer the integration oracle
- [ ] 7.5 `dotnet test -c Release` — full suite runs; the real-signal test reflects the true decoder state (expected to fail until the decoder is fixed in a later change)

## 8. CI gate (G6)

- [x] 8.1 Ensure the real-signal fixture test is included in the projects run by `dotnet test` in `.github/workflows/ci.yml` (G6 — runs on every push and PR to `main`)
      — Confirmed: `OpenWSFZ.Ft8.Tests` is included in `dotnet test`; G6 comment + intent documented in ci.yml
- [ ] 8.2 Confirm a failing real-signal test fails the workflow and blocks merge on all three matrix legs
      — Blocked on task 7.3 (fixture integration test must exist first)
- [x] 8.3 Document gate G6 alongside G1/G3/G5 in the CI workflow and in the `ci-quality-gates` spec
      — Added G6 comment block in `.github/workflows/ci.yml`; added G6 + NFR-016 requirements to `openspec/specs/ci-quality-gates/spec.md`; updated gate table in `TESTING_STRATEGY.md` (old G6 → G7; new G6 = decoder-correctness)

## 9. Process rule

- [x] 9.1 Document the reproducible-evidence rule: decoder root-cause claims require a failing test over a committed WAV before a fix is accepted; live smoke tests are confirmation only
      — Added §8.4 to `TESTING_STRATEGY.md`
- [x] 9.2 Add the rule to the QA/developer workflow docs so future decoder defects follow it
      — Documented in `TESTING_STRATEGY.md` §8.4 (the canonical QA/developer workflow doc)

## 10. Decision gate (hand-off to the next change)

- [ ] 10.1 Convene the decision gate on the §6 recovery-rate result: 0 recovered → port a proven decoder (e.g. `ft8_lib`); partial → patch against this oracle; parity → bug is elsewhere (no decoder rework)
      — Blocked on tasks 6.3/6.4 (recovery rate measurement)
- [ ] 10.2 Open the follow-on change for the chosen decoder strategy; this change closes once the oracle, CI gate, and process rule are in place

## 11. Verification & archive

- [x] 11.1 `openspec validate p10-decoder-ground-truth` passes
      — Confirmed valid before implementation started
- [ ] 11.2 Sync any modified live specs (`ci-quality-gates`) and confirm traceability/licence gates green
      — Partially done: live `ci-quality-gates` spec updated; full gate confirmation blocked on corpus work
- [ ] 11.3 Captain review of the recovery-rate findings and the decision-gate outcome
