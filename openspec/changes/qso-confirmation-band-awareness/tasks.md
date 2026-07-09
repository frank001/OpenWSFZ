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
