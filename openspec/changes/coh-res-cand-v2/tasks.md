## 1. Tests first (Developer, `a943512e` and `59eb5a8f`)

- [x] 1.1 R1: `decoder.coherentFallbackResidualCandidates` defaults to `false` (absent key, missing `decoder` section, a new `DecoderConfig`); the setter and getter round-trip; the config POST is an overlay (a body without the key leaves it as it was).
- [x] 1.2 OFF is a no-op: exactly one snapshot (pass 0's), exactly two runs both on it, and a coherent-fallback log line with no `res` field (also none in `Original` and `Residual` mode with the setting ON).
- [x] 1.3 R2 and R3: the third run reads the third pass's buffer with the third pass's own snapshot (R3), or the residual pass's buffer with the residual pass's snapshot (R2); the first two runs keep pass 0's snapshot and their budgets.
- [x] 1.4 R3 budget (QA review RC2): on the manual clock the third run's budget is `budgetMs` minus the fallback time already spent, smaller than the second run's.
- [x] 1.5 Add, do not replace: everything the first two runs publish is still published, in the same order, with the third run's rows after them.
- [x] 1.6 R3 edge cases: a missing snapshot (null or the call throws) gives `resRun=no-snapshot`; the budget spent after the first or the second run gives `skipped-budget`; no residual buffer gives `no-residual`; a failed first or third run publishes what it can and nothing throws.
- [x] 1.7 R4 gate: a new-text row at 1097 Hz is kept and at 1098 Hz is dropped, through the whole decode; the gate takes the published integer Hz, not the unrounded value; it leaves the first two runs' rows alone.
- [x] 1.8 R-F4: with R-F4 ON the first residual run's above-T1 row is ungated and the third run's never is; `ThirdRunCandidates` takes F1b-passed rows only, whatever the `Admitted` flag says.
- [x] 1.9 New text (QA review RC1): a third-run row whose text is already published in the cycle, by the first two runs or under a different payload by batch 1, 2 or 3, is not new, not counted, not gated and not published twice.
- [x] 1.10 R6 (QA review RC3): `resRun`, `resCand`, `resEligible`, `resNew`, `resNewGated`, `resNewKept`, `resAbandoned` (the third run's own abandoned count) and `resWallMs` on the line only while the setting is effective.

## 2. Implementation (Developer)

- [x] 2.1 `DecoderConfig.CoherentFallbackResidualCandidates`, `Ft8Decoder.SetCoherentFallbackResidualCandidates`, the daemon's two setter calls.
- [x] 2.2 The residual-snapshot plumbing ported from `b0d01f4f`: `SubtractionPass` (`captureCohSnapshot`, `ResidualPassReport.CohSnapshot`, `ThirdPassResult.CohSnapshot`) and `CohFallbackAudioSelector.Choice.CohSnapshot`.
- [x] 2.3 The third run, the gate (`ResidualRunMaxFreqHz = 1097`, `PublishedFreqHz`, `PassesResidualRunGate`, `ThirdRunCandidates`) and the log fields.
- [x] 2.4 `VERSION` 0.71, README and REQUIREMENTS anchors, FR-104 and changelog row 1.67; this change's proposal, design and delta spec. No `native/` change.

## 3. Verification

- [ ] 3.1 Full unfiltered `dotnet test OpenWSFZ.slnx`; `openspec validate --all --strict`; `python tools/check_version_bump.py origin/main` (G9a, G9b).
- [x] 3.2 QA: HK-039 review record before any replay: round 1 `qa/rr-study/2026-11-12-1430-qa-code-review-coh-res-cand-v2-a943512e-RETURNED.md` (three required changes); the delta review of `59eb5a8f` follows it.
- [ ] 3.3 QA: the freeze (build, DLL pin, cycle-list hash, arm A's folder hashes, the gate, analysis code with a passing synthetic self-test, seed 20261112, B = 2000, the U' classes frozen from arm A), then B-OFF (40 cycles, identical to arm A's rows).
- [ ] 3.4 QA: arm B, 500 cycles of the CQ-AP cycle list on `20261110_1817`, PC exclusive; the report with rows B-NAT, B-OFF, B-WIRE, B-KEEP, B-DUP, N-GO, U-OK, B-AB (restated by Amendment 3), B-LATE.
- [ ] 3.5 QA: `python tools/pre_merge_check.py` from a clean checkout of the exact commit before any push (HK-006).
