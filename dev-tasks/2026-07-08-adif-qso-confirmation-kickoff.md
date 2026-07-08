# DEV TASK — adif-qso-confirmation: implementation kickoff

**Date:** 2026-07-08
**OpenSpec change:** `adif-qso-confirmation` — proposal/design/specs/tasks complete,
`openspec validate --strict --all` passes (49/49; 2 capability deltas: new `qso-confirmation`,
modified `web-frontend`)
**Branch:** none yet — create `feat/adif-qso-confirmation` from current `main`
(`a6fdd17`) before starting
**Status:** Ready for implementation — no application code has been written yet, only OpenSpec
artifacts (genuinely fresh start)

---

## 1. Context

The Captain asked for visual "worked before" confirmation on the main decode table: three
readonly checkbox columns (P/C/R) after the existing Region column, checked when the decode's
callsign / DXCC country / continent has already appeared in `ADIF.log`. Two scoping decisions
were confirmed directly with the Captain before this proposal was written (see design.md's
Context for full detail — do not re-litigate these):

- **Country vs Region are different granularities of the same lookup**, not duplicates: Country
  = DXCC entity only (e.g. "Germany"); Region = continent only (e.g. "EU"), which is
  deliberately coarser and will check more readily.
- **Match scope is unbounded**: any prior QSO anywhere in `ADIF.log`'s history counts — no
  band/mode/date filtering.

Read `design.md` in full before starting — it has six numbered decisions with rationale and
rejected alternatives, and answers most "why this way" questions in advance. The one item left
genuinely open is a cosmetic call (disabled-checkbox default styling vs. custom CSS) — resolve by
inspection during your own manual verification (§3 below / design.md's Open Questions), no need
to ask first.

**Important operational note:** the repository's `ADIF.log` currently contains the Captain's
real personal QSO log (826 lines, 757 distinct callsigns) — deliberately left in place for you to
test against live data end-to-end. Do not overwrite it with synthetic test data; if you need a
controlled fixture for automated tests, use a separate in-memory string or temp file, never real
callsigns in a committed test fixture (NFR-021 — see task 1.6/1.7 below).

## 2. Work breakdown & suggested sequencing

Follow `openspec/changes/adif-qso-confirmation/tasks.md` §1–§4 in order — dependency-ordered,
each task cites the governing spec/design section. Notes below are pitfalls and pointers found
during spec-writing, not a restatement of the tasks themselves.

### §1 — ADIF reader and worked-before index

This is the one genuinely new piece of infrastructure in this change — no ADIF *reader* exists
anywhere in the codebase today, only the writer (`AdifLogWriter.cs`). Keep it minimal per
design.md Decision 2: you only need to pull `<call:N>VALUE` tokens out of the file, tolerating the
`ADIF Export` / `<adif_ver:...>` / `<eoh>` header block that precedes the first record. Do not
reach for a third-party ADIF library or try to parse every field — nothing else in this feature
reads anything but `CALL`.

- Task 1.1 (shared path resolution): `AdifLogWriter.ResolveAdifPath()` (currently `internal`,
  `AdifLogWriter.cs` lines 99–106) already has the exact directory-join logic you need. Extract it
  to somewhere both `AdifLogWriter` and the new index can call — don't copy-paste the same
  five lines into a second file.
- Task 1.4's exclusion rule (Unknown/synthetic never enter the country/region sets) is the one
  correctness detail most likely to get silently skipped if you're moving fast — re-read
  design.md Decision 4 and spec.md's "Country and Region matching, with Unknown and synthetic
  entries excluded" requirement before writing the set-building loop. The failure mode if you get
  this wrong is subtle and hard to notice by eye: two completely unrelated stations that both fail
  to resolve a region would falsely show Country/Region as worked-before for each other.
- Task 1.5 (portable-suffix matching): the exact logic to port lives in `web/js/main.js`,
  function `tokenMatchesCallsign` (~lines 332-340):
  ```js
  function tokenMatchesCallsign(token, callsign) {
    return token === callsign || token.startsWith(callsign + '/');
  }
  ```
  Port this comparison both directions (decode token vs. historical log entry, and vice versa —
  spec.md has explicit scenarios for both directions, e.g. decode `Q1TST/P` matching logged
  `Q1TST`, and decode `Q1TST` matching logged `Q1TST/P`). Case sensitivity: match the existing
  codebase convention (callsigns are uppercased on ingestion elsewhere — confirm and be
  consistent rather than introducing a new casing rule).
- Thread-safety (task 1.4): the index is read on every decode cycle (~every 15s, but from the
  decode pipeline's thread) and written on every completed QSO (from wherever
  `AdifLogWriter.AppendQsoAsync` runs). Small data volumes (hundreds to low thousands of entries
  even for a very active, long-time operator) — a plain `lock` around mutation and lookup is
  suffficient, this is not a place to reach for anything elaborate.

### §2 — Decode payload

- Task 2.1/2.2: mirror `RegionInfo`'s existing pattern exactly.
  `src/OpenWSFZ.Abstractions/DecodeResult.cs` currently ends with `RegionInfo? Region = null);` —
  add the new field the same way. The resolution site in `Ft8Decoder.cs` is right next to the
  existing `Region` resolution (search for `"Region bycatch"` — the comment marking that block,
  ~lines 308-327); follow the identical try/catch/log-Warning/degrade-to-default shape, don't
  invent a different error-handling style for the new field sitting three lines below the old one.
- Task 2.3: `AppJsonContext.cs` line 22 has `[JsonSerializable(typeof(RegionInfo))]` — add the
  equivalent attribute for whatever type you choose for the `WorkedBefore` field (a new record, or
  reuse an existing shape if it fits — your call, just register it or the WebSocket payload will
  silently fail to serialize the new field).
- Task 2.5: inject `IWorkedBeforeIndex` into `AdifLogWriter`'s constructor. Register the callsign
  **after** the write succeeds (i.e. after the `await writer.WriteLineAsync(adif)` line inside the
  `try` block, not before) — a QSO that fails to write must not be counted as logged, per spec.md's
  explicit "A failed ADIF write does not register the callsign" scenario.

### §3 — Frontend rendering

- Task 3.1: `web/index.html` lines 68-84 — the placeholder row currently reads
  `<td class="td-no-data" colspan="6">`. This MUST become `colspan="9"` once the three new
  columns land, or the placeholder row will visually misalign. Easy to forget since it's a
  one-line change far from the interesting logic.
- Task 3.2: `web/js/main.js`'s `handleDecodes()` (~lines 382-410) currently ends each row with
  `tr.appendChild(makeCell(formatRegion(r.region)));`. Append three more cells after that line.
  `makeCell()` (lines 354-358) builds a `<td>` with `textContent` — you'll need a small new helper
  (or inline `document.createElement`) for a checkbox cell instead, since `makeCell` is
  text-only. Remember: `disabled`, not `readonly` — `readonly` is a no-op on
  `<input type="checkbox">` per the HTML spec, this is called out explicitly in design.md's Open
  Questions so it doesn't get "fixed" the wrong way during review.
- Task 3.3/3.4: no existing precedent for a checkbox-column style in `app.css` — use your
  judgement on width/padding, but do check the rendered result against the dark theme before
  calling it done. If disabled checkboxes look washed-out/hard to distinguish checked-vs-unchecked
  against the dark background, an `accent-color` override or a custom check glyph is a reasonable
  fix — this is explicitly left to your judgement per design.md, not a blocking spec requirement.

### §4 — Verification

- Task 4.2 is the one that actually exercises this feature against real data and cannot be
  faked by unit tests alone: the repo's live `ADIF.log` (Captain's real log, left in place for
  exactly this purpose) gives you genuine test cases for all three independent-column
  combinations (worked-before on all three, worked-before on none, and the interesting middle
  case — country/continent worked but not that specific callsign). Actually run the daemon and
  watch real decodes render against this data; don't infer correctness from code review alone —
  same category of risk flagged in `dev-tasks/2026-07-05-f-003-ap-assist-flaky-decode-test.md`
  and `dev-tasks/2026-07-05-f-004-operator-visibility-improvements-kickoff.md`'s task 3.10 note:
  a claim about runtime behaviour needs an actual run, not just a diff read.
- Attach before/after screenshots per this repo's established convention (no frontend test
  harness exists for `main.js`/`index.html` — see
  `dev-tasks/2026-07-05-settings-logs-tab-panel-too-narrow.md`).

## 3. Before opening a PR

- `openspec validate --strict --all` must still pass — it does today (49/49); don't let anything
  here regress it.
- Full `dotnet test` — 0 new failures, including everything added under §1.6/1.7 and §2.6.
- Do not commit any change to the repository's `ADIF.log` itself — it's the Captain's real
  personal log, present only for manual verification, not a build artifact or fixture.
- Rebase onto current `main` before opening the PR if it's moved further since `a6fdd17`.

## 4. QA review

Standard process: QA reviews the diff against `openspec/changes/adif-qso-confirmation/`'s
artifacts, checks task-completion-on-archive and spec-sync state, confirms the Unknown/synthetic
exclusion rule (design.md Decision 4) actually holds in the implementation (not just claimed in a
task checkbox), and confirms the manual verification against the live `ADIF.log` was actually run
before signing off. Please hold the merge for that review rather than proceeding once CI is green.

## 5. References

- `openspec/changes/adif-qso-confirmation/{proposal,design,tasks}.md` — source of truth for
  everything above; read `design.md` first, it has the full rationale for every decision
  referenced in §2 above.
- `openspec/changes/adif-qso-confirmation/specs/{qso-confirmation,web-frontend}/spec.md` — the
  two capability deltas (one new capability, one modified).
- `src/OpenWSFZ.Daemon/AdifLogWriter.cs` — existing writer to extend (path resolution, success-path
  registration hook).
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs` lines ~308-327 — existing `Region` resolution to mirror for
  `WorkedBefore`.
- `src/OpenWSFZ.Abstractions/DecodeResult.cs`, `CallsignRegionEntry.cs` — payload shapes to extend
  / reuse.
- `web/index.html` lines 68-84, `web/js/main.js` lines 342-410 — decode table markup and
  rendering to extend.
- `web/js/main.js` lines 332-340 — `tokenMatchesCallsign`, the portable-suffix rule to port to
  the backend (§1 task 1.5).
- `dev-tasks/2026-07-05-f-004-operator-visibility-improvements-kickoff.md` — the closest prior-art
  kickoff handoff in this repo, mirrored for this file's structure.
- `openspec/specs/adif-log/spec.md`, `openspec/specs/region-lookup/spec.md` — the two existing
  capabilities this change depends on but does not modify.
