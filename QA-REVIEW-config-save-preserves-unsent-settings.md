# QA review: `config-save-preserves-unsent-settings` (#193, FR-074 to FR-077, v0.52 content shipped in v0.53)

**Reviewer:** QA. **Date:** 2026-10-01. **Ordered by:** the Captain (task 7.3, "do the review").
**When:** post-merge. The change reached `main` in PR #196 (`d3c53ed0`), after the Engineer's `/opsx:verify` PASS and a green CI on all three platforms.
**Method:** read-only review of the merged code on `origin/main`: `src/OpenWSFZ.Web/ConfigOverlay.cs`, the `POST /api/v1/config` handler in `WebApp.cs`, `ConfigChangeSummary.cs`, `AppConfig.cs`, `JsonConfigStore.cs`, `AppJsonContext.cs`, and the other callers of `IConfigStore.SaveAsync`. **QA ran no test suites for this review.** The evidence for behaviour is the Engineer's Web.Tests 359/359 and `config_drift` 18/18, and the CI runs cited in tasks 7.1.
**Not reviewed:** the behaviour of `web/js/settings.js` (the Settings page), Playwright T15, the node `web/js` tests.

## Verdict: APPROVED. No blocker. Five notes.

## What was checked and found sound

| Question | Finding |
|---|---|
| Is the hand-written list of non-nullable sections complete? | Yes. `AppConfig` has seven non-nullable sections (`Logging`, `DecodeLog`, `Ptt`, `RemoteAccess`, `DecodeNoiseSuppression`, `ExternalReporting`, `CycleAudioArchive`); all seven are in `ConfigOverlay.NonNullableSections`. `Cat`, `Tx`, `Decoder` are nullable and correctly absent. |
| Can a merge strand a stale key (a removed dictionary entry survives)? | No. No config type under `OpenWSFZ.Abstractions` or `OpenWSFZ.Config` is a dictionary. |
| Can a differently-cased key bypass the merge? | No. `AppJsonContext` sets only `PropertyNamingPolicy = CamelCase`; binding is case-sensitive, so a `"Decoder"` key is simply ignored. |
| Duplicate JSON keys? | Rejected: `JsonNode.Parse` throws `ArgumentException`, answered 400 "Malformed JSON.". |
| Server-owned marker `decoder.nhard40MigrationApplied`? | Forced from the store after the merge, whether or not the body sent it. |
| Can the change-log line leak message text or personal data (NFR-021, HK-037)? | No. Values are printed for six enum or boolean paths only (`cycleAudioArchive.mode`, `decodingEnabled`, `tx.autoAnswer`, `tx.holdTxFreq`, `cat.enabled`, `remoteAccess.enabled`); every other changed path is named without its value. |
| Does the schema-agnostic design protect fields added later? | Yes (design D1). The Engineer reports T4/T5 are reflection-enumerated, so they cover `decoder.subtraction*`. |

## Notes

**R1. Lost-update window (Low to Medium; a pre-existing class, not a regression).**
The handler merges the body onto `store.Current`, validates, then calls `store.SaveAsync`. `JsonConfigStore` serialises writes with `_saveLock`, but that protects the file write, not the read-modify-write. Nine daemon-side sites also do read-modify-write on the store: `QsoAnswererService` (4), `QsoCallerService` (2), `QsoControllerRouter`, `CatPollingService` (dial frequency, fire-and-forget), `CaptureAutoStartCoordinator`. A POST whose snapshot predates one of those saves can write the stale value back (for example `tx.autoAnswer` after a retry exhaustion, or the dial frequency), and the reverse also holds. The window is short (from the `store.Current` read until the save acquires the lock) and the old full-replace handler was strictly worse. No test covers it. *Remedy if wanted:* an atomic `UpdateAsync(Func<AppConfig, AppConfig>)` on the store, executed under `_saveLock` (an `src/` change, HK-011, Developer session). **Captain's decision 2026-10-01: accept and record; revisit if a lost update is ever observed.**

**R2. Clamps also correct stored values the body did not send (Low).**
The post-merge validation clamps `cat.pollIntervalSeconds`, `tx.watchdogMinutes`, `tx.retryCount`, the decoder values and `subtractionMaxThreads` whatever the body contained, so a hand-edited out-of-range stored value is silently corrected (with a warning) on an unrelated save. That departs from the letter of FR-074 ("a setting that was not sent is not changed"). The archive validation is deliberately different: it checks only values the body sent. *Remedy if wanted:* clamp only values the body sent. **Captain's decision: leave it, note the wording.**

**R3. `configBeforeSave` is read late (Low).** It is taken after validation, so under a concurrent write the single change-log line can name paths the caller did not change. Cosmetic.

**R4. Broad `catch (ArgumentException)` (Info).** It exists for the duplicate-key case but also converts any unrelated `ArgumentException` inside the overlay into a 400 "Malformed JSON.", which could hide a bug.

**R5. Delta-spec wording gap (Info; raised by the Engineer's verify).** The rule "an explicit null on a non-nullable scalar returns 400" is in FR-074 but not listed in the delta spec's table.

## Operational consequence (not a defect)

The fix is on `main`. Builds from `decoding_improvement` and older branches still **replace** the config on POST until that branch is synced (Captain's decision 2026-10-01: sync before the next endurance run, one dedicated merge by QA with a new arm label). Until then the standing guard stands: no Settings saves during a measurement run (HK-035 addendum).
