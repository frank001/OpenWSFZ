## ADDED Requirements

### Requirement: Native shim ABI version is exposed on the status endpoint

The daemon SHALL retain the native FT8 decoder shim's actual loaded ABI version (as read once by
`Ft8LibInterop`'s startup self-test) and include it as a `shimVersion` field in the response of
`GET /api/v1/status` and in the initial WebSocket `status` event payload.

#### Scenario: Status endpoint includes the loaded shim version

- **WHEN** a client sends `GET /api/v1/status`
- **THEN** the response body SHALL include a `shimVersion` integer field equal to the value the
  native library reported at startup

#### Scenario: Shim version is stable for the process lifetime

- **WHEN** `GET /api/v1/status` is called more than once during the same daemon process lifetime
- **THEN** `shimVersion` SHALL be identical across all responses (it is read once at startup, not
  re-queried per request)

---

### Requirement: Shim version is displayed read-only in the Advanced settings tab

The settings page's Advanced tab SHALL display the current `shimVersion` value from the status
endpoint, read-only, for operator diagnosis (e.g. comparing against a known-good value from a
release note or R&R study report).

#### Scenario: Advanced tab shows the loaded shim version

- **WHEN** the operator opens the settings page's Advanced tab
- **THEN** the shim version number SHALL be visible as a read-only value, sourced from
  `GET /api/v1/status`
