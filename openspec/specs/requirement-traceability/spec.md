## Requirements

### Requirement: Tool exists and runs from CI

A first-party .NET console application SHALL exist at `tools/TraceabilityCheck/` and SHALL be invocable from CI via `dotnet run --project tools/TraceabilityCheck/ -- <args>`. The tool SHALL accept the path to `REQUIREMENTS.md` and one or more paths to test assemblies as arguments.

#### Scenario: Tool builds and runs with `--help`

- **WHEN** a developer runs `dotnet run --project tools/TraceabilityCheck/ -- --help`
- **THEN** the tool SHALL exit with code 0 and print usage information including the required arguments

### Requirement: Parsing of requirement IDs

The tool SHALL parse `REQUIREMENTS.md` and extract every requirement identifier matching the patterns `FR-###` and `NFR-###` (three digits, leading zero permitted). The set of extracted IDs SHALL match the set defined in `REQUIREMENTS.md` &sect;4 and &sect;5 verbatim.

#### Scenario: All declared requirement IDs are extracted

- **WHEN** the tool parses `REQUIREMENTS.md` v1.1
- **THEN** the extracted set SHALL include every `FR-001` through `FR-016` and every `NFR-001` through `NFR-015`

#### Scenario: Malformed requirement ID surfaces a parse error

- **WHEN** the tool parses a `REQUIREMENTS.md` containing a malformed identifier such as `FR-1` or `nfr-001`
- **THEN** the tool SHALL exit non-zero with a message naming the malformed identifier

### Requirement: Reflection over test assemblies

The tool SHALL reflect over each supplied test assembly and enumerate every test method's display name. A display name SHALL be considered to map a requirement if it begins with one or more requirement IDs (comma-separated where multiple), followed by a colon, followed by the human-readable description.

#### Scenario: Test mapping a single requirement is recognised

- **WHEN** a test method has the display name `"FR-007: When the daemon starts it should emit the welcome banner on stdout"`
- **THEN** the tool SHALL record `FR-007` as mapped by that test

#### Scenario: Test mapping multiple requirements is recognised

- **WHEN** a test method has the display name `"FR-002, NFR-004: When asked to bind elsewhere it binds to 127.0.0.1"`
- **THEN** the tool SHALL record both `FR-002` and `NFR-004` as mapped by that test

#### Scenario: Test without a leading requirement ID is not counted

- **WHEN** a test method has a display name that does not begin with a requirement ID
- **THEN** the tool SHALL NOT record that test as mapping any requirement

### Requirement: Missing-mapping detection (rubric criterion C1)

The tool SHALL exit non-zero if any requirement ID extracted from `REQUIREMENTS.md` is not mapped by at least one test display name across the supplied assemblies.

#### Scenario: Unmapped requirement fails the run

- **WHEN** `REQUIREMENTS.md` declares `FR-001` and no test display name begins with `FR-001`
- **THEN** the tool SHALL exit non-zero and the failure message SHALL name `FR-001` as unmapped

#### Scenario: All requirements mapped passes the run

- **WHEN** every requirement ID in `REQUIREMENTS.md` is mapped by at least one test
- **THEN** the tool SHALL exit with code 0

### Requirement: Stale-reference detection

The tool SHALL exit non-zero if any test display name references a requirement ID that does not exist in `REQUIREMENTS.md`.

#### Scenario: Test references a deleted requirement

- **WHEN** a test display name begins with `FR-999` and `FR-999` is not in `REQUIREMENTS.md`
- **THEN** the tool SHALL exit non-zero and the failure message SHALL name `FR-999` and the test that references it

### Requirement: Report artefact

On every run, the tool SHALL emit a `traceability.md` report file listing every requirement ID and the test display names that map to it (or `(unmapped)` when none). The report file path SHALL be configurable via a CLI option and SHALL default to `traceability.md` in the current working directory.

#### Scenario: Report file is produced even when the run fails

- **WHEN** the tool exits non-zero due to an unmapped or stale requirement
- **THEN** the `traceability.md` report SHALL still be written to disk for inspection

### Requirement: Skipped or excluded tests do not count (rubric criterion C4)

The tool SHALL treat a test marked with `[Fact(Skip = "...")]`, `[Theory(Skip = "...")]`, or excluded from the CI run by trait filter as if it were not present. A skipped test SHALL NOT satisfy a requirement-ID mapping.

#### Scenario: Skipped test does not satisfy mapping

- **WHEN** a test display name begins with `FR-001` but the test is marked `[Fact(Skip = "wip")]`
- **THEN** the tool SHALL treat `FR-001` as unmapped and exit non-zero
