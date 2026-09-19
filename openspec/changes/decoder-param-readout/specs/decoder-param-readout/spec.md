## ADDED Requirements

### Requirement: Read-only decoder-parameter endpoint

The daemon SHALL expose `GET /api/v1/decoder/params`, returning a JSON object `{ "shimVersion": <int>, "entries": [ { "name": <string>, "kind": "runtime" | "compile-time", "value": <number>, "default": <number> }, ... ] }`. The values SHALL be read from the native decoder **on every request** and SHALL NOT be cached and SHALL NOT be derived from `AppConfig` or `app.json`. `shimVersion` SHALL be the value reported by the native library's own sentinel.

The route SHALL be read-only: `POST`, `PUT`, `PATCH` and `DELETE` SHALL return `405`. If the native library cannot be loaded, the endpoint SHALL return `503` with a message and SHALL NOT return an empty table. Authentication SHALL be the same as the other `/api/v1` routes.

#### Scenario: The endpoint shows what the native decoder reports

- **WHEN** the native decoder reports `osd_nhard_max = 40` (default `60`) while `app.json` holds a different value
- **THEN** the response SHALL contain an entry `{ "name": "osd_nhard_max", "kind": "runtime", "value": 40, "default": 60 }`

#### Scenario: The route rejects every mutating verb

- **WHEN** a `POST`, `PUT`, `PATCH` or `DELETE` request is sent to `/api/v1/decoder/params`
- **THEN** the response status SHALL be `405`

#### Scenario: An unavailable native library is an error, not an empty table

- **WHEN** the native interop cannot be loaded
- **THEN** the response status SHALL be `503` and the body SHALL NOT be an empty `entries` array

---

### Requirement: Read-only decoder-parameter page

The web UI SHALL provide a page `decoder-params.html` that lists **every** entry returned by `GET /api/v1/decoder/params`, grouped into *Runtime-settable* and *Compile-time*, showing each entry's name, value and default, and showing the shim version. The page SHALL contain **no `<input>`, `<select>` or `<textarea>` element and no control that mutates state**. The page SHALL be reachable by a link from the settings page.

#### Scenario: Every API entry is displayed with the API's value

- **WHEN** the page is loaded against a running daemon
- **THEN** each entry in the API response SHALL appear on the page with the same value and default, and the shim version SHALL be shown

#### Scenario: The page has no editable control

- **WHEN** the page's DOM is inspected
- **THEN** it SHALL contain no `<input>`, `<select>` or `<textarea>` element

#### Scenario: The page shows a change made through the existing settings

- **WHEN** an operator saves a changed decoder value through the existing Advanced Decoder Settings section and reloads the read-only page
- **THEN** the page SHALL show the value the native decoder now reports

---

### Requirement: The existing Advanced Decoder Settings section is unchanged

Adding the read-only page SHALL NOT change the `#advanced-decoder-settings` section of `settings.html` or its behaviour, other than a single link to the new page elsewhere on the settings page. The read-only page is a readout **beside** the editable section, not a replacement for it.

#### Scenario: The editable section is byte-for-byte unchanged

- **WHEN** the `#advanced-decoder-settings` element of `settings.html` before and after this change is compared
- **THEN** its markup SHALL be identical

---

### Requirement: The readout does not change decoding

Nothing in this capability SHALL alter decode output. At default parameters the native decoder SHALL produce byte-identical results to the previous shim version.

#### Scenario: Decode output is unchanged at defaults

- **WHEN** a fixed set of audio buffers is decoded by the previous shim and by this shim at default parameters
- **THEN** the decode results SHALL be byte-identical
