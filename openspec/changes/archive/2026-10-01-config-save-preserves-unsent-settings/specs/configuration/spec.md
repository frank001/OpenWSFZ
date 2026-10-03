## MODIFIED Requirements

### Requirement: Configuration REST API

The web server SHALL expose `GET /api/v1/config` and `POST /api/v1/config` endpoints to allow the UI to read and write the operator's configuration.

`POST /api/v1/config` SHALL apply the request body as an **overlay** on the stored configuration, not as a replacement:

| In the body | Effect |
|---|---|
| key absent, at any depth | the stored value SHALL be kept |
| key present, JSON object, stored value non-null | merged recursively by this same rule |
| key present, JSON object, stored value `null` | the body object is used as-is |
| key present, scalar or array | replaces the stored value wholesale; arrays SHALL NOT be element-merged |
| key present, explicit `null`, non-nullable section (`logging`, `decodeLog`, `ptt`, `remoteAccess`, `decodeNoiseSuppression`, `externalReporting`, `cycleAudioArchive`) | treated as absent; the stored value SHALL be kept |
| key present, explicit `null`, nullable field | `null` SHALL be stored |
| server-owned field (`decoder.nhard40MigrationApplied`) | the body SHALL be ignored; the stored value SHALL be kept |
| unknown key | ignored |

Validation and clamping SHALL run on the **merged** configuration.

#### Scenario: GET returns current config

- **WHEN** a client sends `GET /api/v1/config`
- **THEN** the server SHALL respond with HTTP 200, `Content-Type: application/json`, and the current in-memory configuration serialised as JSON, including `audioDeviceId`, `audioDeviceFriendlyName`, `audioOutputDeviceId`, and `audioOutputFriendlyName` fields

#### Scenario: POST writes and persists config

- **WHEN** a client sends `POST /api/v1/config` with a valid JSON body containing `audioDeviceId`, `audioDeviceFriendlyName`, `audioOutputDeviceId`, and `audioOutputFriendlyName`
- **THEN** the server SHALL update the in-memory configuration, call `IConfigStore.SaveAsync()`, and respond with HTTP 200 and the updated configuration as JSON

#### Scenario: POST clearing output device selection persists null values

- **WHEN** a client sends `POST /api/v1/config` with `audioOutputDeviceId: null` and `audioOutputFriendlyName: null`
- **THEN** the server SHALL persist both fields as `null` and respond with HTTP 200

#### Scenario: Config file without audioOutputDeviceId deserialises without error

- **WHEN** the daemon starts and the config file contains no `audioOutputDeviceId` or `audioOutputFriendlyName` keys (i.e. an existing pre-FR-048 config file)
- **THEN** the daemon SHALL deserialise successfully, treating both fields as `null`, and SHALL start normally

#### Scenario: POST with malformed JSON returns 400

- **WHEN** a client sends `POST /api/v1/config` with a body that is not valid JSON
- **THEN** the server SHALL respond with HTTP 400 and SHALL NOT modify or persist the configuration

#### Scenario: An empty body object changes nothing

- **WHEN** the stored configuration has every leaf set to a non-default value and a client sends `POST /api/v1/config` with `{}`
- **THEN** `GET /api/v1/config` afterwards SHALL return JSON string-equal to the JSON returned before

#### Scenario: A save that omits cycleAudioArchive keeps the stored archive settings

- **WHEN** the stored `cycleAudioArchive` is `{mode: "all", directory: "X", maxSizeMb: 999, maxAgeHours: 9, writeManifest: false}` and a client posts a body without a `cycleAudioArchive` key
- **THEN** `cycleAudioArchive` SHALL be unchanged

#### Scenario: A save that omits unsent runtime fields keeps them

- **WHEN** the stored configuration has `decodingEnabled: false`, `tx.holdTxFreq: true`, `tx.txAudioOffsetHz: 1234`, `tx.rxAudioOffsetHz: 1777`, `tx.autoAnswer: true` and non-empty `tx.retainedTxPower`/`retainedComment`/`retainedPropMode`, and a client posts the Settings-page body
- **THEN** every one of those fields SHALL be unchanged, and the decode pipeline SHALL NOT be started

#### Scenario: Explicit null on a non-nullable section keeps the stored value

- **WHEN** a client posts an explicit `null` for `logging`, `decodeLog`, `ptt`, `remoteAccess`, `decodeNoiseSuppression`, `externalReporting` or `cycleAudioArchive`
- **THEN** the stored section SHALL be kept and SHALL NOT be `null` in `GET /api/v1/config`

#### Scenario: Explicit null on a nullable field is stored

- **WHEN** a client posts `remoteAccess.passphrase: null` with `remoteAccess.enabled: false`, or `decodeNoiseSuppression.suppressUnknownRegion: null`
- **THEN** the field SHALL be persisted as `null`

#### Scenario: The migration marker is server-owned

- **WHEN** a client posts `decoder.nhard40MigrationApplied` with the opposite of the stored value
- **THEN** the stored value SHALL be kept

#### Scenario: Arrays replace

- **WHEN** the stored `externalReporting.targets` has two entries and a client posts `targets: []`
- **THEN** the stored `targets` SHALL become `[]`

#### Scenario: Validation runs on the merged configuration

- **WHEN** the stored `externalReporting.role` is `"follower"` with a `leaderUrl`, and a client posts `externalReporting.leaderUrl: ""`
- **THEN** the server SHALL respond with HTTP 400 and SHALL NOT modify the stored configuration

## ADDED Requirements

### Requirement: Every config save logs what it changed

On every successful `POST /api/v1/config` the server SHALL write exactly one `Information` log line naming the dotted paths whose value changed, for example `Config saved via API: changed cycleAudioArchive.mode (All→Off), tx.holdTxFreq`. When nothing changed it SHALL write `Config saved via API: no changes`. Values SHALL be printed only for `cycleAudioArchive.mode`, `decodingEnabled`, `tx.autoAnswer`, `tx.holdTxFreq`, `cat.enabled` and `remoteAccess.enabled`. Every other field SHALL be printed as a path only.

#### Scenario: A save that changes a measurement-critical setting is grep-able

- **WHEN** a save changes `cycleAudioArchive.mode` from All to Off and changes `tx.callsign`
- **THEN** exactly one line SHALL be logged, containing `cycleAudioArchive.mode (All→Off)` and the path `tx.callsign`

#### Scenario: Personal values never reach the log

- **WHEN** a save changes `tx.callsign`, `remoteAccess.passphrase`, a host, or a directory path
- **THEN** the log line SHALL NOT contain any of those values
