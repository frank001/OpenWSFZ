## ADDED Requirements

### Requirement: Frequency list REST endpoints

The web server SHALL expose `GET /api/v1/frequencies` and `POST /api/v1/frequencies` endpoints to allow the UI to read and write the operator's frequency list.

#### Scenario: GET /api/v1/frequencies returns the full entry list

- **WHEN** a client sends `GET /api/v1/frequencies`
- **THEN** the server SHALL respond with HTTP 200, `Content-Type: application/json`, and the current in-memory frequency list as a JSON array of frequency entry objects, each with `protocol`, `frequencyMHz`, and `description` fields

#### Scenario: GET /api/v1/frequencies returns an empty array when list is empty

- **WHEN** a client sends `GET /api/v1/frequencies` and `IFrequencyStore.Entries` is empty
- **THEN** the server SHALL respond with HTTP 200 and a JSON body of `[]`

#### Scenario: POST /api/v1/frequencies accepts and persists a new list

- **WHEN** a client sends `POST /api/v1/frequencies` with a valid JSON array of frequency entry objects
- **THEN** the server SHALL call `IFrequencyStore.SaveAsync` with the provided list, respond with HTTP 200, and return the saved list as the response body

#### Scenario: POST /api/v1/frequencies with malformed JSON returns 400

- **WHEN** a client sends `POST /api/v1/frequencies` with a body that is not a valid JSON array of frequency entries
- **THEN** the server SHALL respond with HTTP 400 and SHALL NOT modify or persist the frequency list

#### Scenario: POST /api/v1/frequencies with an empty array clears the list

- **WHEN** a client sends `POST /api/v1/frequencies` with a body of `[]`
- **THEN** the server SHALL accept it, persist an empty list, and respond with HTTP 200

---

### Requirement: Tune action endpoint

The web server SHALL expose `POST /api/v1/tune` to allow the UI to change the active dial frequency. The endpoint abstracts the two possible outcomes based on current CAT state:

- **CAT active** (`ICatState.Status` is `Connected` or `Connecting`): the endpoint SHALL call `IRadioConnection.SetDialFrequencyMhzAsync` and update `ICatState.DialFrequencyMHz` optimistically with the requested value
- **CAT inactive** (`ICatState.Status` is `Disabled` or `Error`): the endpoint SHALL update `AppConfig.DecodeLog.DialFrequencyMHz` to the requested value and call `IConfigStore.SaveAsync()`

The response SHALL always return HTTP 200 with `{ "effectiveFrequencyMHz": <number> }` so the caller does not need to know which path was taken.

#### Scenario: POST /api/v1/tune with CAT active commands the rig

- **WHEN** `ICatState.Status` is `Connected` and a client sends `POST /api/v1/tune` with `{ "frequencyMHz": 14.074 }`
- **THEN** the server SHALL call `IRadioConnection.SetDialFrequencyMhzAsync(14.074)`
- **AND** `ICatState.DialFrequencyMHz` SHALL be updated to `14.074` optimistically
- **AND** the response SHALL be HTTP 200 with `{ "effectiveFrequencyMHz": 14.074 }`

#### Scenario: POST /api/v1/tune with CAT disabled updates config

- **WHEN** `ICatState.Status` is `Disabled` and a client sends `POST /api/v1/tune` with `{ "frequencyMHz": 7.074 }`
- **THEN** `AppConfig.DecodeLog.DialFrequencyMHz` SHALL be updated to `7.074` and persisted via `IConfigStore.SaveAsync()`
- **AND** the response SHALL be HTTP 200 with `{ "effectiveFrequencyMHz": 7.074 }`

#### Scenario: POST /api/v1/tune with missing or invalid frequencyMHz returns 400

- **WHEN** a client sends `POST /api/v1/tune` with a body lacking `frequencyMHz` or with a non-numeric value
- **THEN** the server SHALL respond with HTTP 400 and SHALL NOT modify any state

#### Scenario: POST /api/v1/tune with negative frequencyMHz returns 400

- **WHEN** a client sends `POST /api/v1/tune` with `{ "frequencyMHz": -1.0 }`
- **THEN** the server SHALL respond with HTTP 400

#### Scenario: POST /api/v1/tune CAT set failure returns 502

- **WHEN** `ICatState.Status` is `Connected` and `IRadioConnection.SetDialFrequencyMhzAsync` throws an exception
- **THEN** the server SHALL log a Warning with the exception detail and respond with HTTP 502 (Bad Gateway) without updating `ICatState.DialFrequencyMHz`
