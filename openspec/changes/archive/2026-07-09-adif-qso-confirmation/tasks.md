## 1. ADIF reader and worked-before index

- [x] 1.1 Extract the shared ADIF-path-resolution logic (`AdifLogWriter.ResolveAdifPath`'s
      directory-join behaviour) into a small shared helper usable by both `AdifLogWriter` and the
      new index, rather than duplicating it.
- [x] 1.2 Add a minimal ADIF reader that extracts every `<call:N>VALUE` token from an ADIF 3.x
      text file (case-insensitive tag matching), tolerating the leading header block (`ADIF
      Export`, `<adif_ver:...>`, `<eoh>`) and any other fields/tags present on each record line.
      A line that yields no parseable `CALL` token is skipped, not fatal to the rest of the parse.
- [x] 1.3 Add `IWorkedBeforeIndex` (naming illustrative) exposing at minimum: a load/build method
      reading the resolved `ADIF.log` path, a register-one-callsign method (used by task 3.1), and
      three query methods/booleans-producing lookup for a given callsign token: worked-callsign
      (with portable-suffix matching per task 1.5), worked-country, worked-region.
- [x] 1.4 Implement the index: on build, parse all distinct callsigns via the reader (task 1.2);
      for country/region, resolve each distinct callsign's entity/continent via
      `ICallsignRegionStore.TryGetRegion` once, inserting into the worked-entity/worked-continent
      sets ONLY when the resolution is non-null and `Synthetic == false` (design.md Decision 4).
      Missing `ADIF.log` at build time → empty index, not an error. Ensure the index's
      read/mutate surface is thread-safe (e.g. `lock` or concurrent collections) — decode reads
      and QSO-completion writes can happen concurrently.
- [x] 1.5 Port `web/js/main.js`'s `tokenMatchesCallsign` semantics (exact match, or a
      `callsign + "/"` prefix match either direction) to the backend for the worked-callsign
      query, so Partner matching is consistent with the frontend's existing CQ click-to-answer
      matching rule.
- [x] 1.6 Unit tests for the ADIF reader: well-formed multi-record file, header-only file (no
      records), a line with a truncated/malformed `<call:` tag (skipped, not fatal), missing file.
      Use only fictional Q-prefix/placeholder callsigns in any committed test fixture (NFR-021) —
      never copy real callsigns from the repo's live `ADIF.log` into a test fixture.
- [x] 1.7 Unit tests for `IWorkedBeforeIndex`: exact-callsign match, portable-suffix match both
      directions (task 1.5), country match with different callsign, region match with different
      country, two distinct unresolved ("Unknown") callsigns never co-match, a synthetic-resolved
      historical entry never causes a real decode to match, a synthetic-resolved decode itself
      always resolves `false` on country/region regardless of index content, empty index (no file)
      resolves all three `false`.

## 2. Decode payload

- [x] 2.1 Add a `WorkedBefore` field to `DecodeResult` (`src/OpenWSFZ.Abstractions/DecodeResult.cs`)
      carrying three independent booleans (`Call`/`Country`/`Region`) — nullable-advisory or
      non-nullable-with-false-defaults, per design.md's Decision 6 (either is acceptable; document
      the choice in the XML doc comment, mirroring `RegionInfo`'s existing doc-comment style).
- [x] 2.2 In `Ft8Decoder.cs`'s native-result mapping loop (alongside the existing `Region`
      resolution, ~lines 308-327), resolve `WorkedBefore` for the message's primary callsign token
      using `IWorkedBeforeIndex`, in the same try/catch-degrade-to-default-and-log-Warning pattern
      already used for `Region`. A `null`/unavailable index (e.g. no `IWorkedBeforeIndex` supplied)
      degrades to all-`false`, matching `_regionStore is not null` guard style.
- [x] 2.3 Register the new field's type for JSON serialization (`AppJsonContext.cs`, following the
      existing `RegionInfo` registration pattern) so it serializes correctly over the WebSocket
      decode channel.
- [x] 2.4 Register `IWorkedBeforeIndex` in DI (`Program.cs`), alongside the existing
      `ICallsignRegionStore` registration; call its startup build/load method during daemon
      startup, before the decode loop begins delivering results.
- [x] 2.5 Wire `AdifLogWriter.AppendQsoAsync`'s success path (after the ADIF record is written) to
      register the newly-logged callsign into the same live `IWorkedBeforeIndex` instance (inject
      it into `AdifLogWriter`). A failed write (existing `IOException`/
      `UnauthorizedAccessException`/generic-`Exception` catch blocks) SHALL NOT register the
      callsign.
- [x] 2.6 Unit tests: `Ft8Decoder` resolves `WorkedBefore` correctly for a matching decode, an
      index-throws case degrades to all-`false` without dropping the decode, no-index-supplied
      case degrades to all-`false`. `AdifLogWriter` tests: successful write registers the
      callsign into the index; failed write does not.

## 3. Frontend rendering

- [x] 3.1 `web/index.html`: add three `<th>` cells after the existing Region column header — text
      content `P`/`C`/`R`, `title` attributes `"Partner"`/`"Country"`/`"Region"`. Update the
      no-data placeholder row's `colspan` from `6` to `9`.
- [x] 3.2 `web/js/main.js`'s `handleDecodes()`: after the existing `formatRegion` cell, append
      three checkbox cells reflecting `r.workedBefore?.call`/`.country`/`.region` (default
      `false`/unchecked if the field or a sub-field is absent). Each `<input type="checkbox">`
      SHALL be `disabled` (readonly — `readonly` has no effect on checkboxes) and its `checked`
      state set directly from the payload value; do not attach a click/change handler that could
      mutate state.
- [x] 3.3 `web/css/app.css`: style the three new columns as narrow as practical (minimal cell
      padding, checkbox-sized column width) and confirm they render as the rightmost columns of
      the table with no unintended stretching from the table's layout algorithm.
- [x] 3.4 Note in a code comment or the PR description whether disabled-checkbox default browser
      styling is visually acceptable against the dark theme, or whether `accent-color`/a custom
      indicator is warranted (design.md's Open Question — non-blocking, cosmetic, resolve by
      inspection during manual verification).

## 4. Verification

- [x] 4.1 Run the full existing test suite; confirm zero regressions against pre-change baseline.
      `dotnet build OpenWSFZ.slnx` + `dotnet test OpenWSFZ.slnx --no-build`: 941/941 passed across
      all 9 test projects (0 failed, 0 skipped), including the 28 new qso-confirmation tests
      (25 Daemon.Tests: AdifReaderTests/WorkedBeforeIndexTests + 2 AdifLogWriterTests additions;
      3 Ft8.Tests: WorkedBeforeLookupTests).
- [x] 4.2 Manually verify end-to-end against the Captain's real `ADIF.log`. Verified in two parts
      (no RF signal source was available in this session to produce an actual live decode, so the
      backend matching logic and the frontend rendering were each verified directly against the
      real files, rather than via one continuous live-decode screenshot):
      - **Backend logic, real data**: a throwaway console harness (never committed — built,
        run, and deleted outside the repo) exercised the real `JsonConfigStore` →
        `CallsignRegionStore` (29,013 real region entries) → `WorkedBeforeIndex` pipeline
        directly against the repo-root `ADIF.log`. Confirmed: 757 distinct callsigns indexed
        (matches design.md's stated count exactly); a known-logged callsign resolves
        `Call=true`; a never-logged fictional Q-prefix callsign resolves all three `false`;
        a callsign whose DXCC entity was worked by a *different* station (itself excluded from
        the index) resolves `Call=false, Country=true, Region=true` — all three acceptance
        scenarios pass exactly as specified.
      - **Frontend rendering + live wiring, real daemon**: started
        `OpenWSFZ.Daemon.exe` from the repo root (so `ADIF.log`/`ALL.TXT` resolve to the real
        files). Startup log confirmed
        `qso-confirmation: worked-before index built with 757 distinct callsign(s) from
        'ADIF.log'.` — matching the backend check above exactly. Screenshot
        (`dev-tasks/screenshots/adif-qso-confirmation-01-decode-table-columns.png`) confirms
        the P/C/R columns render correctly as the three rightmost decode-table columns with
        correct header tooltips, and the no-data placeholder row spans the full 9-column width.
        Served `index.html`/`main.js` were diffed against source to confirm the running daemon
        was serving the actual changed files, not a stale build.
      - **Not exercised**: an actual live FT8 decode ticking a checkbox in the browser — no RF
        signal source was available. The decode-payload → checkbox-rendering path itself is
        covered by `Ft8Decoder`'s `WorkedBeforeLookupTests` (task 2.6) end-to-end at the
        payload level, and `makeWorkedBeforeCell`'s rendering logic is a direct, trivial
        `checked = !!value` mapping — low residual risk, but flagged here rather than silently
        assumed. Captain: let me know if you want a live-signal pass before merge.
- [x] 4.3 Confirm `openspec validate --strict` passes for this change before requesting review.
      `openspec validate --strict adif-qso-confirmation` → "Change 'adif-qso-confirmation' is valid".

## 5. Post-review UI correction (Captain feedback, design.md Decision 7)

- [x] 5.1 `web/js/main.js`'s `makeWorkedBeforeCell`: replace the `<input type="checkbox"
      disabled>` with a plain `<span>`. Set `textContent` to a checkmark glyph (e.g. `"✓"`) when
      the boolean is truthy, or an empty string when falsy/absent. No `disabled` attribute, no
      click/change handler (a `<span>` has no interactive semantics to suppress).
      Done — `span.className = 'worked-before-mark'`, JSDoc updated to describe the checkmark
      span and cite design.md Decision 7 instead of the disabled-checkbox rationale.
- [x] 5.2 `web/css/app.css`: remove the checkbox-specific rule
      (`#decodes-table td:nth-child(7/8/9) input[type="checkbox"]` — `accent-color`,
      `cursor: default`) and replace with a rule styling the checkmark span in
      `var(--color-success)` (the same token already used for the Call-CQ button's positive
      state). Keep the existing narrow-column width/padding/centring rule targeting
      `th`/`td:nth-child(7/8/9)` — that part is unaffected by this change.
      Done — checkbox rule and its explanatory comment replaced with
      `#decodes-table .worked-before-mark { color: var(--color-success); font-weight: 600; }`;
      the narrow-column width/padding/centring block above it untouched.
- [x] 5.3 Re-verify visually against the dark theme (screenshot or live daemon check per task
      4.2's precedent) that the checkmark is legible at a glance for all three columns, and that
      empty cells do not visually misalign the column width/centring.
      Done — started the real daemon from the repo root (confirmed
      `qso-confirmation: worked-before index built with 757 distinct callsign(s) from
      'ADIF.log'.`, same count as task 4.2), but no RF signal source was available to produce a
      live decode (same limitation noted in 4.2). Built a throwaway static HTML harness (never
      committed — created and deleted outside the diff) that loads the real `web/css/app.css`
      and calls the actual `makeWorkedBeforeCell` markup shape against four synthetic rows
      (all-true, all-false, and two mixed true/false combinations across P/C/R). Screenshot
      (`dev-tasks/screenshots/adif-qso-confirmation-02-checkmark-indicators.png`) confirms:
      green checkmarks are clearly legible against the dark background in all three columns,
      `false`/absent cells render empty with no stray text node or layout shift, and the mixed
      rows read unambiguously at a glance. Daemon stopped after verification.
- [x] 5.4 Update/add unit or manual-verification coverage for the new rendering shape if this
      repo's convention calls for it (no frontend test harness exists for `main.js` today — see
      design.md Decision 7 and the existing task 4.2 precedent of screenshot-based verification).
      No automated frontend test harness exists in this repo (consistent with task 4.2's
      precedent); the screenshot-based manual verification in 5.3 is the established convention
      and is treated as sufficient coverage for this rendering-only change.
- [x] 5.5 Re-run full `dotnet test` (0 regressions expected — this is a frontend-only rendering
      change, no backend payload shape changed) and `openspec validate --strict
      adif-qso-confirmation` before requesting re-review.
      `dotnet build OpenWSFZ.slnx`: 0 warnings, 0 errors. `dotnet test OpenWSFZ.slnx --no-build`:
      941/941 passed (identical to task 4.1's baseline — no regressions, no test touched this
      rendering path). `openspec validate --strict adif-qso-confirmation` → "Change
      'adif-qso-confirmation' is valid".
