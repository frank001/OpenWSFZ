**User-facing:** yes

## Why

GitHub issue **#193**. `POST /api/v1/config` **replaces** the whole config (HK-035). Any key the body
leaves out comes back through System.Text.Json as its C# default, and the handler patches up *some*
omitted fields one at a time. That patch-up has missed a field at least three times (`ptt`;
`externalReporting.instanceId`/`role`/`leaderUrl`/`followerUrls`; now `cycleAudioArchive`). Each miss was
found live, after it had cost something. #193 cost about 44 minutes of archive during the R&R run.

Source spec: `qa/2026-09-29-2112-architect-to-eng-spec-config-save-preserves-unsent-settings.md`
(Architect, on `arch/config-save-preserves-settings` @ `6fb71458`, re-addressed to the Engineer by the
Captain, 2026-09-29). Base `main` @ `c3f42362`. Its §0.1 audit of what an ordinary Settings save resets:
`cycleAudioArchive` (whole section), `decodingEnabled` (a save restarts the pipeline),
`tx.holdTxFreq`/`txAudioOffsetHz`/`rxAudioOffsetHz`, `tx.autoAnswer`, `tx.retainedTxPower`/
`retainedComment`/`retainedPropMode`. Any field added in future is exposed by default.

## What Changes

- **Part A: omitted means unchanged, at every depth.** `POST /api/v1/config` applies the body as an
  overlay on the stored config (rules in `design.md` D1). The per-field guards are removed.
- **Part B: the one-line #193 fix** is subsumed by Part A. It ships alone only if the Captain wants #193
  closed first (design D8).
- **Part C: an "Audio archive" group on the Settings page** (mode, directory, size cap, age cap,
  manifest). Carries out the Captain's 2026-07-29 directive, which was never built.
- **Part D: one `Information` log line per successful save** naming the changed dotted paths, with values
  only for an allowlist of enum/boolean fields.
- **Part E: a standalone `qa/` config-drift module** for run tools, on this branch, with its own tests.
  See design D7: the spec assumed the run tools already poll the config API. They do not.

## Impact

- Behaviour a caller can see: a partial body no longer resets unsent fields; a body with no `decoder`
  no longer clears a stored decoder section whose marker is `false`.
- Code: `src/OpenWSFZ.Web/WebApp.cs`, `web/js/settings.js`, `web/settings.html`, `web/css/app.css`,
  `tests/OpenWSFZ.Web.Tests/`, `qa/` (Part E only). No `native/`, no `JsonConfigStore`, no
  `POST /api/v1/frequencies`.
- Not protected until synced: R&R and endurance build from `decoding_improvement`. Until the standard
  sync merge, **no Settings-page saves during a measurement run.**
- Docs: `REQUIREMENTS.md` amended, `VERSION` bumped (G9b). Memory `hk035` is updated by the Architect
  after merge.
