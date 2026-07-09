## ADDED Requirements

### Requirement: Operator-triggered refresh fetches and installs real country-file data

The system SHALL provide a backend operation, triggered only by explicit operator request (an API
call; not automatic on startup and not on a timer), that fetches the current country-file release
from country-files.com, converts its prefix-block entries into `CallsignRegionEntry` records, and
installs the result as the daemon's active `callsign-regions.json` data without requiring a daemon
restart.

#### Scenario: Successful refresh replaces the active region table

- **WHEN** an operator triggers the refresh operation and the fetch and conversion both succeed
- **THEN** the daemon's in-memory region table SHALL be replaced with the converted data, the new
  data SHALL be persisted to `callsign-regions.json`, and subsequent decode-result region lookups
  SHALL use the new data without a restart

#### Scenario: Refresh is never triggered automatically

- **WHEN** the daemon starts, or at any time absent an explicit operator-triggered refresh request
- **THEN** no network fetch to country-files.com SHALL occur, and the existing
  `callsign-regions.json`/compiled-in seed behaviour (per the `region-lookup` capability) SHALL be
  unaffected

---

### Requirement: Refresh failure leaves existing region data untouched

A failure to fetch or to convert the country-file release SHALL NOT modify the daemon's active
region table or the on-disk `callsign-regions.json` file. The failure SHALL be logged and reported
to the caller.

#### Scenario: Fetch failure preserves existing data

- **WHEN** an operator triggers the refresh operation and the fetch to country-files.com fails
  (network error, non-success HTTP status, or timeout)
- **THEN** the daemon's active region table and `callsign-regions.json` SHALL remain unchanged, the
  daemon SHALL log the failure, and the operation SHALL report failure to the caller

#### Scenario: Conversion failure preserves existing data

- **WHEN** an operator triggers the refresh operation, the fetch succeeds, but the fetched data
  cannot be parsed/converted (unexpected or malformed XML shape)
- **THEN** the daemon's active region table and `callsign-regions.json` SHALL remain unchanged, the
  daemon SHALL log the failure, and the operation SHALL report failure to the caller

---

### Requirement: Refreshed data may include individual-callsign entries unfiltered

The refresh operation SHALL pass individual-callsign exception entries from the source data
through to `callsign-regions.json` unfiltered when the conversion step produces them, and SHALL
NOT reject or strip them, because `callsign-regions.json` is never committed to version control
(the same status as `ALL.TXT`/`ADIF.log`) — so NFR-021 (no real third-party callsigns in version
control) is satisfied structurally by this file's location, not by filtering logic in this
capability.

#### Scenario: Individual-callsign entries are not rejected by the refresh operation

- **WHEN** the converted data includes an entry derived from the source's individual-callsign
  exception list
- **THEN** the refresh operation SHALL install it into `callsign-regions.json` the same as any
  other converted entry, without special-casing or rejecting it

---

### Requirement: An operator can view the current region-data status from the running daemon's GUI

The system SHALL provide a way for an operator to view, without inspecting log files or making a
raw API call, the current size of the active region table and the outcome of the most recent
refresh attempt made during the current daemon session (if any): whether one has occurred,
whether it succeeded or failed, when it happened, which release version was installed (if
available), and the error detail on failure.

#### Scenario: Status view before any refresh this session

- **WHEN** an operator opens the region-data status view and no refresh has been triggered since
  the daemon started
- **THEN** the view SHALL show the current entry count (reflecting seed data or a previously-saved
  `callsign-regions.json`, whichever is active) and SHALL clearly indicate that no refresh has
  occurred this session, without implying a failure occurred

#### Scenario: Status view after a successful refresh

- **WHEN** an operator opens the region-data status view after a refresh has succeeded during the
  current session
- **THEN** the view SHALL show the resulting entry count, the release version if one was
  identified, and the timestamp of the successful refresh

#### Scenario: Status view after a failed refresh

- **WHEN** an operator opens the region-data status view after a refresh has failed during the
  current session
- **THEN** the view SHALL clearly indicate the refresh failed, SHALL show the error detail, and
  SHALL NOT claim the entry count reflects a successful refresh that did not happen

---

### Requirement: An operator can look up how a specific callsign currently resolves, for diagnostic purposes

The system SHALL provide a way for an operator to type a callsign and see, without decoding a live
signal, how that callsign currently resolves against the active region table: the matched entity,
continent, CQ zone, and ITU zone when present, or a clear "no match" indication — using the same
longest-prefix-match logic the decode pipeline uses for region-lookup advisory display.

#### Scenario: Lookup resolves a recognised prefix

- **WHEN** an operator looks up a callsign whose prefix matches an entry in the active region table
- **THEN** the result SHALL show the matched entity and continent, and the CQ/ITU zone values when
  the matched entry carries them

#### Scenario: Lookup resolves the synthetic Q-series entry

- **WHEN** an operator looks up a callsign in the synthetic `Q`-prefix series (NFR-021)
- **THEN** the result SHALL indicate a synthetic-region match with no CQ/ITU zone values, distinct
  from both a real-entity match and a no-match result

#### Scenario: Lookup reports no match for an unrecognised prefix

- **WHEN** an operator looks up a callsign whose prefix matches no entry in the active region table
- **THEN** the result SHALL clearly indicate no match was found (the diagnostic equivalent of the
  decode pipeline's "Unknown"), not an error
