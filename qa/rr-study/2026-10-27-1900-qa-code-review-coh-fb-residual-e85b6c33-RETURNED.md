# QA code review: COH-FB-RESIDUAL switch, `e85b6c33` (branch `dev/coh-fb-residual`, base `main` `d20059c3`)

**Reviewed-commit:** `e85b6c33314acefd3344f44801e6f458a305ed76` · **Verdict:** RETURNED (one required change, labels only) · replay-only build, never merged.

## Read
`git diff main...dev/coh-fb-residual`: 5 files, 305 insertions, 11 deletions. Empty under `native/`. Spec `bc9abc8f` plus Amendment 1 (`90ed3a89`, §5a).

## Findings
- **Correct and as handed over:** switch read once at construction, exact ordinal `residual`; unset returns the same `normalisedPcm` reference with label `original` (R0 should be byte-identical); candidate snapshot untouched; the third pass works on a clone of the residual pass's buffer, so no array is shared with a writer and none is pooled; third-pass buffer carried out on `ThirdPassResult.Residual`; `FittedSignals` added to the report; Normal depth gives `residual-unavailable`; the new field is appended at the end of the log line; no magic numbers; tests present for parser, selector and wiring (Developer reports Windows suite green: Ft8 633, Daemon 810, Web 404, Config 175, Rig 41, Audio 40, E2E 9, TestSupport 12, LicenseInventory 24, Traceability 34; not re-run by QA, R0 is the check that matters).
- **R-1 (required): the log labels do not match Amendment 1.** The Developer built to QA's handoff (`audio=original|residual|residual-unavailable`). The spec now (§5a item 3) says the field logs the level actually used: `residual3` (third pass's buffer), `residual2` (residual pass's buffer), `residual-unavailable` (original audio read although the switch was set). `Select()` already steps down third pass, residual pass, original, so only the label strings and the tests change (`CohFallbackAudio.cs`, `CohFallbackAudioTests.cs`, `CoherentFallbackWiringTests.cs`). Keep `original` for switch unset. Fault: QA's handoff, not the Developer's.
- **Note, no change required:** when the third pass is `abandoned` or `failed` but the residual pass completed, `Select()` uses the residual pass's buffer (`residual2`). That is the spec's step-down rule.

## Why RETURNED rather than approved
R0 byte-identity must be run once, on the final commit. Approving `e85b6c33` and then changing the strings would force a second R0.

QA side, done in the same commit: Replay81's fallback-line regex (`qa/rr-study/sub-feas/replay81/Program.cs:737`) now accepts the trailing `, audio=<level>` field.
