## ADDED Requirements

### Requirement: PropModeStore persists protocol-aware propagation mode list

A new class `PropModeStore` in `OpenWSFZ.Daemon` SHALL manage a JSON-backed list of propagation mode entries. Each entry is a `PropModeEntry` record with three fields: `Protocol` (string), `Value` (string — the ADIF `PROP_MODE` field value), and `Description` (string — human-readable label).

The backing file SHALL be `prop-modes.json`, located in the same directory as `appconfig.json` (resolved via `LaunchOptions.ConfigPath`). If the file does not exist on startup, `PropModeStore` SHALL create it with the default FT8 seed (see below) and save it before returning from the constructor / initialisation method.

`PropModeStore` SHALL be registered as a singleton in the DI container and injected into `WebApp.cs` for the API endpoints.

**Default FT8 seed (10 entries, in order):**

| Protocol | Value | Description |
|---|---|---|
| FT8 | *(empty string)* | Not specified |
| FT8 | TR | Tropospheric Ducting |
| FT8 | ES | Sporadic E |
| FT8 | F2 | F2 Reflection |
| FT8 | EME | Earth-Moon-Earth |
| FT8 | MS | Meteor Scatter |
| FT8 | TEP | Trans-Equatorial |
| FT8 | SAT | Satellite |
| FT8 | LOS | Line of Sight |
| FT8 | INTERNET | Internet-assisted |

#### Scenario: Default seed written on first run

- **WHEN** `prop-modes.json` does not exist and `PropModeStore` initialises
- **THEN** the file SHALL be created with the 10 default FT8 entries and no error SHALL be thrown

#### Scenario: Existing file loaded correctly

- **WHEN** `prop-modes.json` exists and contains a valid list of entries
- **THEN** `PropModeStore` SHALL load and expose those entries without overwriting the file

#### Scenario: Empty file is treated as missing and reseeded

- **WHEN** `prop-modes.json` exists but contains an empty array `[]`
- **THEN** `PropModeStore` SHALL overwrite it with the default FT8 seed

---

### Requirement: GET /api/v1/prop-modes returns current list

`GET /api/v1/prop-modes` SHALL return the full list of `PropModeEntry` objects as a JSON array. The response format SHALL be:

```json
[
  { "protocol": "FT8", "value": "", "description": "Not specified" },
  { "protocol": "FT8", "value": "TR", "description": "Tropospheric Ducting" }
]
```

#### Scenario: GET returns seeded FT8 entries

- **WHEN** `GET /api/v1/prop-modes` is called after first-run seed
- **THEN** the response SHALL be HTTP 200 with a JSON array containing the 10 default FT8 entries

#### Scenario: GET requires auth on non-loopback

- **WHEN** `GET /api/v1/prop-modes` is called from a non-loopback address without a valid API key
- **THEN** the response SHALL be HTTP 401

---

### Requirement: POST /api/v1/prop-modes replaces current list

`POST /api/v1/prop-modes` SHALL accept a JSON array of `PropModeEntry` objects and atomically replace the stored list. It SHALL save the new list to `prop-modes.json` and return the updated list as HTTP 200.

Validation: each entry SHALL have a non-null `Protocol` and `Description`. `Value` may be empty (represents the "Not specified" option). The list SHALL NOT be required to contain the default seed entries — operators may customise freely.

#### Scenario: POST replaces list and persists

- **WHEN** `POST /api/v1/prop-modes` is called with a valid array
- **THEN** the response SHALL be HTTP 200 with the updated list, and `prop-modes.json` SHALL reflect the new entries on the next application start

#### Scenario: Subsequent GET returns POSTed list

- **WHEN** `POST /api/v1/prop-modes` is called followed immediately by `GET /api/v1/prop-modes`
- **THEN** the GET response SHALL return the entries that were submitted in the POST

#### Scenario: POST requires auth on non-loopback

- **WHEN** `POST /api/v1/prop-modes` is called from a non-loopback address without a valid API key
- **THEN** the response SHALL be HTTP 401
