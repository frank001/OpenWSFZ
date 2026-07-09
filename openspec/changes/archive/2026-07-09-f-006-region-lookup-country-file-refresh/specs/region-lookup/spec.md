## ADDED Requirements

### Requirement: Region table can be replaced at runtime without a restart

`ICallsignRegionStore` SHALL support replacing its entire in-memory region table and persisting the
replacement to `callsign-regions.json` atomically, without requiring the daemon to restart, and
without affecting any in-flight or subsequent region lookup's correctness (a lookup during the
replacement SHALL observe either the complete old table or the complete new table, never a partial
one).

#### Scenario: Runtime replacement updates both memory and disk

- **WHEN** a caller replaces the region table via the store's runtime-replacement operation with a
  new, valid list of entries
- **THEN** `callsign-regions.json` SHALL be overwritten atomically (write-to-temp-then-rename) with
  the new list, and subsequent calls to resolve a region SHALL use the new list

#### Scenario: A failed write during replacement leaves the previous table active

- **WHEN** a caller replaces the region table via the store's runtime-replacement operation and the
  underlying file write fails
- **THEN** the in-memory region table SHALL remain the previous list, and `callsign-regions.json`
  on disk SHALL remain unchanged
