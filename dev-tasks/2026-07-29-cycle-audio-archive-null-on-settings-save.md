# Developer handoff: implement the cycle-audio-archive Settings-page control (currently absent — the gap that lets a save silently null the whole config section)

**Authored by:** QA (per HK-000/HK-015), found live 2026-07-29 during the 40m/20m(→80m) dual-instance
live-run session, immediately after the Captain retuned the 20m/SDR-Uno instance to 80m via the web
Settings page.
**Branch:** fresh off `main` (`a029574`); unrelated to `feat/external-reporting-single-connection`
or the LoggingConfig fix branch.
**Status:** root cause confirmed live and pinned down to the exact line responsible (§2). **Captain's
directive (2026-07-29): implement the actual Settings-page control for `cycleAudioArchive`** — not
merely a defensive workaround — since the capability has been fully implemented and testable
end-to-end since 2026-07-26 and this project's own convention is that a control ships once that's
true. §3 is written to that decision; the backend/observability items in §3(b)/(c) remain worth
doing regardless, as defense in depth, but are no longer the primary ask.
**Priority context:** this silently defeats the exact corpus-gathering goal (NFR-021-adjacent;
`cycle-audio-archive` capability) that motivated tonight's whole live-run — and it will recur on
*every* settings-page save an operator makes, not just a frequency retune, for as long as no
settings-page control exists for this field. A second, unrelated finding tonight
(`dev-tasks/2026-07-29-psk-reporter-direct-upload.md`) already flagged that this kind of gap is only
found by directly checking a downstream service; this one is worse because there is no downstream
service to check against — the daemon just quietly stops archiving and reports itself perfectly
healthy the whole time.

## 1. Symptom

Sequence, reconstructed from the running 20m/follower instance's own file timestamps and API state:

1. `cycleAudioArchive` explicitly set (`mode: "all"`, `directory: ".../OpenWSFZ-20m-capture/cycle-audio"`,
   `maxSizeMb: 2048`, `maxAgeHours: 168`, `writeManifest: true`) and confirmed archiving correctly —
   most recent successful cycle before the retune: `260729_211430.wav` (cycle start
   `2026-07-29T21:14:30.000Z`).
2. Captain used the web Settings page to change the dial frequency to 3.573 MHz (80m) and re-enable
   decoding.
3. `GET /api/v1/config` immediately afterward returned `"cycleAudioArchive": null` — not omitted, not
   a default object, a literal JSON `null` where `AppConfig.CycleAudioArchive` is documented
   (`src/OpenWSFZ.Abstractions/AppConfig.cs:100-105`) as "Always non-null on `AppConfig`."
4. Decoding, capture, ALL.TXT logging, and the `externalReporting` leader/follower relay all continued
   completely normally throughout — confirmed via `/api/v1/status` (`state: Running`,
   `captureActive`/`audioActive`/`decodingEnabled: true` throughout) and fresh ALL.TXT lines at the new
   3.573 MHz dial frequency arriving on schedule.
5. **No new file landed in `cycle-audio\` from `211430` until I manually re-POSTed a valid
   `cycleAudioArchive` object at `2026-07-29T21:17:xxZ`** — a gap of ~3.5 minutes, roughly 14 FT8
   cycles of genuine, never-to-be-recovered 80m off-air audio.
6. **`cycleArchiveDroppedCycles` in `/api/v1/status` never moved from `0`** across the entire outage —
   the one operator-visible counter that exists specifically to surface "a cycle didn't get archived"
   gave no signal at all. Nor did anything appear in the recent log tail matching
   `cycle-audio-archive` (the string every other logged path in `CycleArchiveService` — collisions,
   disk-floor trips — uses consistently). Whatever code path this explicit-`null` config hits, it is
   currently invisible on every instrument this project has for the purpose.
7. Confirmed the 40m/leader instance, untouched by any settings-page save tonight, still has its
   correct, non-null `cycleAudioArchive` — this is specific to a settings-page save happening on an
   instance, not something that spontaneously drifts on its own.

## 2. Root cause (per the Captain's own diagnosis, matching the evidence)

There is no settings-page UI control for `cycleAudioArchive` yet (consistent with this project's own
UI-visibility convention — a control only ships once its backend capability is fully implemented and
testable end-to-end; `cycle-audio-archive` shipped 2026-07-26 as a config-only capability with no
Settings-page surface). The web frontend's save action for *any* settings-page change — here, dial
frequency — round-trips a config object that has no notion `cycleAudioArchive` exists, and its
save path writes that field as an explicit `null` rather than preserving whatever value the
just-fetched config actually had.

**Pinned down precisely — `web/js/settings.js`'s save handler (~line 1352-1371) builds its
`POST /api/v1/config` body as an explicit object literal naming every `AppConfig` field it knows
about:**

```js
await Promise.all([
  postConfig({
    audioDeviceId, audioDeviceFriendlyName, audioOutputDeviceId, audioOutputFriendlyName,
    port, showCycleCountdown, logLevel, decodeLog, logging, cat, ptt, tx, remoteAccess,
    decoder, decodeNoiseSuppression, externalReporting,
  }),
  postFrequencies(freqEntries),
]);
```

Every single top-level `AppConfig` property is listed here **except `cycleAudioArchive`** — it is the
one field this literal never includes, because it is the one field with no settings-page control
backing it. `externalReporting` *is* in this list (it has a settings-page section — the "External
Programs" tab, per the `gridtracker-udp-reporting` comment at line 398) even though *its own*
`instanceId`/`role`/`leaderUrl`/`followerUrls` sub-fields have no UI either; that's why it survives a
save while `cycleAudioArchive` doesn't — the omission bites at the whole-section level, not the
individual-field level. (How `externalReporting`'s own UI-less sub-fields survive being rebuilt from
a narrower JS object at line ~1345-1350 that also only lists `enabled`/`targets`/
`honourInboundCommands`/`restrictExternalRepliesToDecodeFilter` is a secondary question — possibly
`POST /api/v1/config`'s handler merges nested objects against the currently-stored config rather than
replacing them outright, which would explain both observations at once. Not verified; a five-minute
read of `WebApp.cs`'s `POST /api/v1/config` handler would confirm or rule this out before relying on
it, but it isn't necessary to resolve before doing the work below — giving `cycleAudioArchive` its own
settings-page section removes the whole-section omission either way.)

## 3. Primary task: implement the cycle-audio-archive Settings-page control

Per the Captain's directive, this is scoped as a real feature addition, not a defensive patch. Give
`CycleAudioArchiveConfig` (`src/OpenWSFZ.Abstractions/CycleAudioArchiveConfig.cs`) its own
settings-page section, modelled on the existing `decodeNoiseSuppression` section
(`web/js/decodeNoiseSuppression.js` + its `.test.js` sibling — the closest existing precedent: a
similarly small, config-only capability that already went through exactly this "add a settings-page
section" step after shipping config-only). Concretely:

- **Mode** — a dropdown/select over the four `CycleAudioArchiveMode` values: `off` (default),
  `all`, `decoded`, `noDecodes` — surface each option's actual meaning in the UI copy (per the enum's
  own doc comments: "off" archives nothing; "all" archives every framed window regardless of decode
  outcome; "decoded" only windows with at least one decode; "noDecodes" only windows with none — the
  failure-population case D-001 investigations use).
- **Directory** — a text input, optional/blank-default. UI copy should make the NFR-021 implication
  explicit: recordings contain real off-air audio and real third-party callsigns, and a blank value
  resolves to the per-user application-data directory (`ConfigPathResolver
  .ResolveDefaultCycleAudioDirectory()`), never the repository or executable directory. Worth a
  one-line reminder in the UI that **two simultaneous instances on the same machine must each be given
  a distinct directory** — tonight's earlier live-run finding (both instances defaulting to `null`
  raced into the same shared folder for ~20 minutes before being caught and fixed; see the session's
  own live notes) is exactly the mistake this control should make hard to repeat by accident.
- **Max size (MB)** / **Max age (hours)** — numeric inputs, defaults 2048 / 168, matching the backend
  defaults exactly (mirror the existing numeric-input dirty-state/validation pattern already used for
  `decoder`'s `kMinScorePass2`/`osdCorrThreshold`/`osdNhardMax` controls).
- **Write manifest** — a checkbox, default checked (the `cycle-archive.csv` sidecar).
- Add `cycleAudioArchive` to the `postConfig({...})` object literal in `web/js/settings.js` (~line
  1354) and to the dirty-state snapshot function (~line 399) — both are currently missing this
  section entirely, which is the direct cause of tonight's bug (§2). Adding the real control also
  fixes the bug as a side effect: the frontend is no longer blind to the field, so it can no longer
  silently omit it.

## 5. Secondary, defense-in-depth items (do regardless of §3)

**(a) Backend invariant:** separately from the settings-page work, `POST /api/v1/config` accepting an
explicit `null` for a field the codebase treats everywhere else as "always non-null" is itself a gap
worth closing directly — this is the same defect *family* (D-WFC-001/"Lesson 6") this project has
fixed repeatedly for the *omitted-key* case (`CycleAudioArchiveConfig`, `DecodeNoiseSuppressionConfig`,
`ExternalReportingConfig`, `TxConfig`, `DecoderConfig`, `PttConfig`, and — hours before tonight's
session — `LoggingConfig`, see `dev-tasks/2026-07-29-fix-loggingconfig-null-rotationschedule-crash.md`),
but this is the *explicit-null* case, which none of those fixes actually guard against — a
`[JsonConstructor]` with defaulted parameters only rescues an *omitted* key; an explicit
`"cycleAudioArchive": null` in the POST body still deserialises straight through to a null property,
exactly as observed tonight. Recommend `POST /api/v1/config` reject (HTTP 400, no partial persistence
— matching the existing out-of-range-port / follower-without-leaderUrl rejection pattern already in
`WebApp.cs`) any request whose body sets a documented-always-non-null section to explicit `null`, for
every such section, not just this one.

**(b) Observability gap, worth fixing regardless of (a):** whatever code path silently no-ops when
`_configStore.Current.CycleAudioArchive` is null needs to at minimum log a `[WRN]` and increment
`cycleArchiveDroppedCycles` (or a distinct counter) every time it happens. An outage with zero signal
on the one metric built to catch exactly this class of problem is a second, independent defect from
the null itself — even after §3 and 5(a) ship, some future gap in this same family deserves to be
loud, not silent.

## 6. Tonight's live workaround (not a fix, do not treat as one)

Re-POSTed the full config with `cycleAudioArchive` restored to its correct explicit object via
`POST /api/v1/config`. Confirmed archiving resumed on the very next cycle
(`260729_211800.wav`, cycle start `2026-07-29T21:18:00.000Z`). For the remainder of tonight's session,
QA will re-verify `cycleAudioArchive` after every further settings-page interaction the Captain makes,
on either instance, until this is properly fixed — this is a stopgap, not a substitute for §3/5(a)/5(b)
above.

## 7. Tests required once designed

- Frontend: a settings-page save round-trips `cycleAudioArchive`'s four fields (`mode`, `directory`,
  `maxSizeMb`, `maxAgeHours`, `writeManifest`) correctly through the new control — mirror
  `decodeNoiseSuppression.test.js`'s existing coverage shape.
- Frontend regression: a settings-page save that changes one unrelated known field (e.g. dial
  frequency) must leave every field *still* without its own UI control — `externalReporting`'s
  relay-only sub-fields, at minimum — byte-for-byte unchanged in the resulting `POST /api/v1/config`
  body, so this exact defect shape doesn't recur for the next field that ships config-only.
- Backend: `POST /api/v1/config` with an explicit `"cycleAudioArchive": null` (and the same for every
  other always-non-null section) must be rejected with HTTP 400 and must not persist any part of the
  request — mirroring the existing `ConfigApiNullGuardTests`-style coverage already established for
  other fields (see `tests/OpenWSFZ.Web.Tests/ConfigApiNullGuardTests.cs` from the
  `external-reporting-single-connection` branch for the existing pattern to extend).
- `CycleArchiveService`: once whichever code path handles a null/invalid config is identified, add a
  regression test asserting it logs a `[WRN]` and increments a drop counter rather than silently
  no-op'ing.

## 8. Evidence

- `src/OpenWSFZ.Abstractions/AppConfig.cs:100-105` — the doc comment establishing the "always
  non-null" invariant this defect violates.
- `D:/Projects/claude/OpenWSFZ-20m-capture/cycle-audio/cycle-archive.csv` — the manifest itself shows
  the gap directly: last pre-outage row `260729_211430.wav` (14.074 MHz), next row
  `260729_211800.wav` (3.573 MHz) — nothing in between, ~3.5 minutes/14 cycles missing.
- `GET http://127.0.0.1:8081/api/v1/config` — captured raw mid-outage tonight, showing
  `"cycleAudioArchive":null` verbatim alongside a fully-intact `externalReporting` block from the same
  response.
