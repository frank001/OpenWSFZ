## ADDED Requirements

### Requirement: Frequency entry data model

The application SHALL use a `FrequencyEntry` record to represent a single working frequency. Each entry SHALL carry:
- `protocol` (string) — the digital mode this entry applies to (e.g., `"FT8"`)
- `frequencyMHz` (double) — the VFO-A dial frequency in megahertz
- `description` (string, may be empty) — a human-readable label (e.g., `"40m"`, `"20m"`)

The model SHALL support any protocol string so that future modes (FT4, JT65, etc.) can be added without schema changes.

#### Scenario: FrequencyEntry round-trips through JSON correctly

- **WHEN** a `FrequencyEntry` with `protocol = "FT8"`, `frequencyMHz = 14.074`, `description = "20m"` is serialised to JSON and deserialised again
- **THEN** all three fields SHALL have their original values

#### Scenario: Empty description is valid

- **WHEN** a `FrequencyEntry` is deserialised from JSON with `description` absent or equal to `""`
- **THEN** the entry SHALL be accepted without error and `description` SHALL be an empty string

---

### Requirement: IFrequencyStore service

`OpenWSFZ.Daemon` SHALL define a public interface `IFrequencyStore` and a concrete `FrequencyStore` implementation registered as a singleton in DI. `IFrequencyStore` SHALL expose:

```csharp
IReadOnlyList<FrequencyEntry> Entries { get; }
Task SaveAsync(IReadOnlyList<FrequencyEntry> entries, CancellationToken cancellationToken = default);
```

`SaveAsync` SHALL replace the in-memory list atomically (update `Entries` after successful write) and write to `frequencies.json` using the same write-to-temp-then-rename pattern as `IConfigStore`.

#### Scenario: Entries returns the loaded list after startup

- **WHEN** the daemon starts and `frequencies.json` contains a valid list
- **THEN** `IFrequencyStore.Entries` SHALL reflect the loaded entries before any REST request is handled

#### Scenario: SaveAsync updates in-memory list and persists

- **WHEN** `IFrequencyStore.SaveAsync` is called with a new list
- **THEN** `IFrequencyStore.Entries` SHALL return the new list immediately after the call
- **AND** the `frequencies.json` file SHALL contain the serialised new list

#### Scenario: SaveAsync is atomic — no partial write on interruption

- **WHEN** `SaveAsync` is called
- **THEN** the implementation SHALL write to a temporary file in the same directory as `frequencies.json` and rename it over the target, ensuring that an interrupted write does not leave a corrupt file

---

### Requirement: frequencies.json default file creation

`frequencies.json` SHALL be a project deliverable committed to the repository. If the file is absent at the resolved path on daemon startup, the daemon SHALL write the compiled-in default list before proceeding, just as it does for `app.json`. The default list SHALL reflect the standard FT8 working frequencies published by WSJT-X.

The default list SHALL contain the following entries (protocol `"FT8"`, descriptions are amateur band designations):

| frequencyMHz | description |
|---|---|
| 1.840  | 160m |
| 3.573  | 80m  |
| 5.357  | 60m  |
| 7.074  | 40m  |
| 10.136 | 30m  |
| 14.074 | 20m  |
| 18.100 | 17m  |
| 21.074 | 15m  |
| 24.915 | 12m  |
| 28.074 | 10m  |
| 50.313 | 6m   |
| 70.100 | 4m   |
| 144.174 | 2m  |
| 222.065 | 1.25m |
| 432.065 | 70cm |

#### Scenario: Default frequencies.json written when file is absent

- **WHEN** the daemon starts and no `frequencies.json` exists at the resolved path
- **THEN** the daemon SHALL create the parent directory if necessary, write the default 15-entry FT8 list, and continue without error

#### Scenario: Existing frequencies.json is loaded, not overwritten

- **WHEN** the daemon starts and `frequencies.json` exists at the resolved path
- **THEN** the daemon SHALL load that file and SHALL NOT overwrite it with the default list

#### Scenario: frequencies.json path resolves relative to the executable

- **WHEN** no override is configured
- **THEN** `frequencies.json` SHALL be resolved from the same directory as the daemon executable, consistent with `app.json` path resolution

---

### Requirement: frequencies.json contains only valid entries

The `frequencies.json` file SHALL be a JSON object with a single key `"entries"` whose value is a JSON array of `FrequencyEntry` objects.

```json
{
  "entries": [
    { "protocol": "FT8", "frequencyMHz": 7.074, "description": "40m" }
  ]
}
```

#### Scenario: Valid frequencies.json is deserialised without error

- **WHEN** `frequencies.json` contains a well-formed JSON object with an `"entries"` array
- **THEN** `IFrequencyStore.Entries` SHALL reflect all entries

#### Scenario: Malformed frequencies.json logs an error and uses the default list

- **WHEN** `frequencies.json` exists but is not valid JSON or does not match the expected schema
- **THEN** the daemon SHALL log an Error, use the compiled-in default list in memory, and SHALL NOT overwrite the malformed file (preserving it for operator inspection)

#### Scenario: Unknown fields in frequencies.json are preserved on round-trip

- **WHEN** `frequencies.json` contains extra fields not in the `FrequencyEntry` schema
- **THEN** `SaveAsync` SHALL preserve those fields in the written file (round-trip fidelity)
