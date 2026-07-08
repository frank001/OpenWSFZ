## 1. ADIF reader and worked-before index

- [ ] 1.1 Extract the shared ADIF-path-resolution logic (`AdifLogWriter.ResolveAdifPath`'s
      directory-join behaviour) into a small shared helper usable by both `AdifLogWriter` and the
      new index, rather than duplicating it.
- [ ] 1.2 Add a minimal ADIF reader that extracts every `<call:N>VALUE` token from an ADIF 3.x
      text file (case-insensitive tag matching), tolerating the leading header block (`ADIF
      Export`, `<adif_ver:...>`, `<eoh>`) and any other fields/tags present on each record line.
      A line that yields no parseable `CALL` token is skipped, not fatal to the rest of the parse.
- [ ] 1.3 Add `IWorkedBeforeIndex` (naming illustrative) exposing at minimum: a load/build method
      reading the resolved `ADIF.log` path, a register-one-callsign method (used by task 3.1), and
      three query methods/booleans-producing lookup for a given callsign token: worked-callsign
      (with portable-suffix matching per task 1.5), worked-country, worked-region.
- [ ] 1.4 Implement the index: on build, parse all distinct callsigns via the reader (task 1.2);
      for country/region, resolve each distinct callsign's entity/continent via
      `ICallsignRegionStore.TryGetRegion` once, inserting into the worked-entity/worked-continent
      sets ONLY when the resolution is non-null and `Synthetic == false` (design.md Decision 4).
      Missing `ADIF.log` at build time → empty index, not an error. Ensure the index's
      read/mutate surface is thread-safe (e.g. `lock` or concurrent collections) — decode reads
      and QSO-completion writes can happen concurrently.
- [ ] 1.5 Port `web/js/main.js`'s `tokenMatchesCallsign` semantics (exact match, or a
      `callsign + "/"` prefix match either direction) to the backend for the worked-callsign
      query, so Partner matching is consistent with the frontend's existing CQ click-to-answer
      matching rule.
- [ ] 1.6 Unit tests for the ADIF reader: well-formed multi-record file, header-only file (no
      records), a line with a truncated/malformed `<call:` tag (skipped, not fatal), missing file.
      Use only fictional Q-prefix/placeholder callsigns in any committed test fixture (NFR-021) —
      never copy real callsigns from the repo's live `ADIF.log` into a test fixture.
- [ ] 1.7 Unit tests for `IWorkedBeforeIndex`: exact-callsign match, portable-suffix match both
      directions (task 1.5), country match with different callsign, region match with different
      country, two distinct unresolved ("Unknown") callsigns never co-match, a synthetic-resolved
      historical entry never causes a real decode to match, a synthetic-resolved decode itself
      always resolves `false` on country/region regardless of index content, empty index (no file)
      resolves all three `false`.

## 2. Decode payload

- [ ] 2.1 Add a `WorkedBefore` field to `DecodeResult` (`src/OpenWSFZ.Abstractions/DecodeResult.cs`)
      carrying three independent booleans (`Call`/`Country`/`Region`) — nullable-advisory or
      non-nullable-with-false-defaults, per design.md's Decision 6 (either is acceptable; document
      the choice in the XML doc comment, mirroring `RegionInfo`'s existing doc-comment style).
- [ ] 2.2 In `Ft8Decoder.cs`'s native-result mapping loop (alongside the existing `Region`
      resolution, ~lines 308-327), resolve `WorkedBefore` for the message's primary callsign token
      using `IWorkedBeforeIndex`, in the same try/catch-degrade-to-default-and-log-Warning pattern
      already used for `Region`. A `null`/unavailable index (e.g. no `IWorkedBeforeIndex` supplied)
      degrades to all-`false`, matching `_regionStore is not null` guard style.
- [ ] 2.3 Register the new field's type for JSON serialization (`AppJsonContext.cs`, following the
      existing `RegionInfo` registration pattern) so it serializes correctly over the WebSocket
      decode channel.
- [ ] 2.4 Register `IWorkedBeforeIndex` in DI (`Program.cs`), alongside the existing
      `ICallsignRegionStore` registration; call its startup build/load method during daemon
      startup, before the decode loop begins delivering results.
- [ ] 2.5 Wire `AdifLogWriter.AppendQsoAsync`'s success path (after the ADIF record is written) to
      register the newly-logged callsign into the same live `IWorkedBeforeIndex` instance (inject
      it into `AdifLogWriter`). A failed write (existing `IOException`/
      `UnauthorizedAccessException`/generic-`Exception` catch blocks) SHALL NOT register the
      callsign.
- [ ] 2.6 Unit tests: `Ft8Decoder` resolves `WorkedBefore` correctly for a matching decode, an
      index-throws case degrades to all-`false` without dropping the decode, no-index-supplied
      case degrades to all-`false`. `AdifLogWriter` tests: successful write registers the
      callsign into the index; failed write does not.

## 3. Frontend rendering

- [ ] 3.1 `web/index.html`: add three `<th>` cells after the existing Region column header — text
      content `P`/`C`/`R`, `title` attributes `"Partner"`/`"Country"`/`"Region"`. Update the
      no-data placeholder row's `colspan` from `6` to `9`.
- [ ] 3.2 `web/js/main.js`'s `handleDecodes()`: after the existing `formatRegion` cell, append
      three checkbox cells reflecting `r.workedBefore?.call`/`.country`/`.region` (default
      `false`/unchecked if the field or a sub-field is absent). Each `<input type="checkbox">`
      SHALL be `disabled` (readonly — `readonly` has no effect on checkboxes) and its `checked`
      state set directly from the payload value; do not attach a click/change handler that could
      mutate state.
- [ ] 3.3 `web/css/app.css`: style the three new columns as narrow as practical (minimal cell
      padding, checkbox-sized column width) and confirm they render as the rightmost columns of
      the table with no unintended stretching from the table's layout algorithm.
- [ ] 3.4 Note in a code comment or the PR description whether disabled-checkbox default browser
      styling is visually acceptable against the dark theme, or whether `accent-color`/a custom
      indicator is warranted (design.md's Open Question — non-blocking, cosmetic, resolve by
      inspection during manual verification).

## 4. Verification

- [ ] 4.1 Run the full existing test suite; confirm zero regressions against pre-change baseline.
- [ ] 4.2 Manually verify end-to-end against the Captain's real `ADIF.log` (already present in the
      working tree for this purpose): start the daemon, confirm a station known to be in
      `ADIF.log` shows P checked (and C/R checked if its country/continent also appear
      elsewhere in the log), a station never logged shows all three unchecked, and a station
      whose country has been worked but who personally hasn't shows P unchecked / C checked.
      Attach before/after screenshots to the PR per this repo's established convention (no
      frontend test harness exists — see `dev-tasks/2026-07-05-settings-logs-tab-panel-too-narrow.md`).
- [ ] 4.3 Confirm `openspec validate --strict` passes for this change before requesting review.
