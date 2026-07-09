## 1. Data model — `WorkedBeforeState` and `WorkedBeforeInfo`

- [x] 1.1 Add `WorkedBeforeState` enum (`Never`/`DifferentBand`/`ThisBand`) to
      `src/OpenWSFZ.Abstractions/`.
- [x] 1.2 Change `WorkedBeforeInfo` from three `bool` properties to five `WorkedBeforeState`
      properties: `Contact`, `Country`, `Continent`, `CqZone`, `ItuZone`. Update `.None` static
      to all-`Never`.
- [x] 1.3 Update `DecodeResult.WorkedBefore` doc comments to reflect the new shape (still
      nullable/degrades identically on failure).
- [x] 1.4 Confirm JSON serialization casing/shape for the five-field, enum-valued
      `workedBefore` payload follows this codebase's existing camelCase convention (check
      `AppJsonContext.cs` source-gen config); add/adjust source-gen context entries as needed
      for `WorkedBeforeState`.

## 2. `AdifReader` — widen to parse `BAND` alongside `CALL`

- [x] 2.1 Add `AdifLogEntry` readonly record struct (`Call`, `Band` nullable) to
      `src/OpenWSFZ.Daemon/AdifReader.cs`.
- [x] 2.2 Add `ReadEntries(path, logger) : IReadOnlyList<AdifLogEntry>`, reusing the existing
      `<tag:N>VALUE` extraction helper for both `CALL` and `BAND` tags per record. A record with
      a parseable `CALL` but no parseable `BAND` yields `Band: null` — not a skip.
- [x] 2.3 Retire `ReadCallsigns` once `WorkedBeforeIndex` (task 3) is the only caller and has
      migrated to `ReadEntries` — do not leave two divergent read paths over the same file.
- [x] 2.4 Unit tests: fixture ADIF text (synthetic Q-prefix callsigns, NFR-021) covering
      present/missing/malformed `BAND` tags per record, mixed with the existing malformed-`CALL`
      coverage.

## 3. `WorkedBeforeIndex` — per-value band-tracking, five dimensions

- [x] 3.1 Extract a shared `DeriveBand`-equivalent helper (frequency MHz → band name string) so
      both `AdifLogWriter` and the new "current band" resolution point (task 4) use one table,
      not two — mirrors the existing `AdifPathResolver` extraction precedent.
- [x] 3.2 Rework internal storage from flat `HashSet<T>` per dimension to
      `Dictionary<TValue, HashSet<string>>` (value → bands worked) for all five dimensions
      (callsign, entity, continent, CQ zone, ITU zone). Preserve the existing Unknown/synthetic
      exclusion (nothing changes about *whether* a value is indexed, only *what* is stored once
      it is).
- [x] 3.3 `LoadAsync`: switch to `AdifReader.ReadEntries`, populate all five dictionaries
      including band association; a record with `Band: null` still populates the "worked at all"
      fact for each axis but no band-set entry.
- [x] 3.4 `Register(string callsign, string? band)`: update signature and internal logic to
      match the dictionary shape; `AdifLogWriter.AppendQsoAsync`'s call site updated to pass its
      already-computed band (task 5).
- [x] 3.5 `Resolve(string callsignToken, string? currentBand) : WorkedBeforeInfo`: update
      signature; for each of the five axes, compute `Never` (not in dictionary) /
      `DifferentBand` (in dictionary, `currentBand` not in its band-set or `currentBand is null`)
      / `ThisBand` (in dictionary, `currentBand` in its band-set — this case wins over
      `DifferentBand` even if other bands are also present).
- [x] 3.6 Unit tests covering: never worked, worked-different-band, worked-this-band, worked on
      both this-band-and-another-band (ThisBand wins), `currentBand: null` degrade
      (never `ThisBand`), unknown-band historical record contributing to "ever" but not to any
      band, all five dimensions independently, and Unknown/synthetic exclusion still holding
      (regression coverage for the pre-existing behaviour, unchanged).

## 4. Current-band resolution — thread through the decode pump

- [x] 4.1 `Ft8Decoder.DecodeAsync`: add optional `string? currentBand = null` parameter.
- [x] 4.2 `Ft8Decoder`'s worked-before attachment point: pass `currentBand` through to
      `_workedBeforeIndex.Resolve(primaryToken, currentBand)`.
- [x] 4.3 `Program.cs`'s decode pump: resolve the current band alongside the existing `dialFreq`
      resolution (reuse `WebApp.ResolveEffectiveFrequency`, now trustworthy per D-013), convert
      via the task-3.1 shared `DeriveBand` helper, pass into `ft8Decoder.DecodeAsync(...)`.
- [x] 4.4 Confirm existing call sites/tests of `DecodeAsync` that don't pass `currentBand`
      continue to compile and behave identically (degrade to `DifferentBand`-at-best, never
      `ThisBand`) — no test changes required for pre-existing tests unless they specifically want
      to exercise the new parameter.

## 5. `AdifLogWriter` — pass band into live registration

- [x] 5.1 `AppendQsoAsync`'s existing `_workedBeforeIndex?.Register(...)` call: pass the
      already-computed `DeriveBand(record.DialFrequencyMHz)` value alongside the callsign.
- [x] 5.2 Unit test: a QSO logged with a known band registers into the index such that the very
      next decode of that callsign on the same band resolves `ThisBand` (mirrors the existing
      "confirmed on next decode" test, extended for band).

## 6. Frontend — column rename/expansion, tri-state glyph rendering

- [x] 6.1 `web/index.html`: rename `#decodes-table` header cells (P/C/R → Ctc/DXCC/Cnt), add two
      new header cells (CQz/ITz), update `title` attributes, update placeholder-row `colspan`.
- [x] 6.2 `web/js/main.js`: rework `makeWorkedBeforeCell` (or equivalent) from a two-state
      (checked/empty) to a three-state renderer (`never`/`differentBand`/`thisBand` → empty /
      distinct glyph / checkmark glyph); update `handleDecodes()`'s five-field mapping from the
      new `workedBefore` payload shape.
- [x] 6.3 `web/css/app.css`: add styling for the new `differentBand` glyph state, visually
      distinct from both empty and the existing `--color-success` checkmark state.
- [ ] 6.4 Manual/screenshot verification against the dark theme (per the lesson from the
      original capability's Decision 7 — disabled-checkbox legibility issue) — confirm all three
      states are readable at a glance while decodes scroll.

## 7. Verification

- [x] 7.1 `dotnet build OpenWSFZ.slnx -c Release` — 0 warnings, 0 errors.
- [x] 7.2 `dotnet test OpenWSFZ.slnx -c Release` — full suite green, no regressions in existing
      `qso-confirmation`/`region-lookup`/`adif-log` test coverage.
- [x] 7.3 `openspec validate --strict --all` — passing, including this change's delta specs.
- [ ] 7.4 End-to-end manual check against a real `ADIF.log` with multi-band history (e.g. the
      Captain's real personal log): confirm a station worked on a past band shows
      "different-band" and, after retuning to that same band, flips to "this-band" without a
      daemon restart.
- [x] 7.5 Post-implementation fix: the Captain's live screenshot after 7.1–7.3 showed every
      worked-before indicator rendering empty. Root cause: `JsonStringEnumConverter<WorkedBeforeState>`
      with no explicit naming policy serialises the exact PascalCase member name (`"ThisBand"`),
      not the lowerCamelCase the frontend compares against (`"thisBand"`) — `AppJsonContext`'s
      `CamelCase` `PropertyNamingPolicy` only renames JSON *properties*, not enum *values*. Fixed
      with explicit `[JsonStringEnumMemberName]` per enum member; added
      `WorkedBeforeJsonSerializationTests` (direct serialize + round-trip) as permanent regression
      coverage. `dotnet build` (0/0), `dotnet test` (969/969) after the fix.

## 8. Frontend — decode table Band column (folded in mid-implementation, Captain's request)

A small additional requirement, added after tasks 1–7 above were otherwise complete: `#decodes-table`
gains a **Band** column between Time and dB, showing the session's current active band for that
decode (e.g. `"40m"`) — the same band-name convention as the Settings → Frequencies tab's
Description column. Reuses the `currentBand` value this change's task 4 already threads through
`Ft8Decoder.DecodeAsync` for worked-before resolution, so the Band column and the worked-before
indicators on one row always agree — no new resolution logic.

- [x] 8.1 `DecodeResult`: add `string? Band = null`, appended as the last positional parameter
      (after `WorkedBefore`) so no existing positional call site breaks.
- [x] 8.2 `Ft8Decoder.DecodeAsync`: populate `Band: currentBand` on the constructed `DecodeResult`
      (the exact same value passed to `_workedBeforeIndex.Resolve`).
- [x] 8.3 `web/index.html`: insert a `<th>Band</th>` header between Time and dB; bump the
      placeholder row's `colspan` from 11 to 12.
- [x] 8.4 `web/js/main.js`: insert `makeCell(r.band ?? '')` between the Time and dB cells in
      `handleDecodes()`; update the JSDoc payload shape comment to include `band`.
- [x] 8.5 `web/css/app.css`: narrow/centre the new Band column (`nth-child(2)`); shift the
      worked-before column selectors from `nth-child(7..11)` to `nth-child(8..12)` to account for
      the inserted column.
- [x] 8.6 Unit tests: `DecodeResult.Band` is populated verbatim from `currentBand` when supplied,
      and stays `null` when `currentBand` is unresolvable/omitted (mirrors task 4.4's degrade
      posture).
- [x] 8.7 `dotnet build`/`dotnet test` — 0/0 warnings/errors, full suite green
      (971/971 after this addition).
- [ ] 8.8 Manual/screenshot verification: Band column renders the expected value and aligns
      visually with the existing columns — same manual-check caveat as task 6.4.
