## MODIFIED Requirements

### Requirement: WebSocket endpoint

The daemon SHALL expose `GET /api/v1/ws` that accepts WebSocket upgrade requests. On
connect, the server SHALL immediately push one `status` JSON event. The server SHALL push
a `heartbeat` event every 5 seconds while the connection is open. After each FT8 decode
cycle the server SHALL push a `decode` event carrying the list of decoded results for that
cycle (see `decode-events` spec for payload shape). The broadcast SHALL be fire-and-forget
per connection; a connection that cannot accept a frame within 1 second SHALL be closed
silently.

#### Scenario: WebSocket upgrade is accepted

- **WHEN** a client sends an HTTP Upgrade request to `GET /api/v1/ws`
- **THEN** the server SHALL respond with HTTP 101 Switching Protocols and establish the
  WebSocket connection

#### Scenario: Status event pushed on connect

- **WHEN** a WebSocket connection is established
- **THEN** the server SHALL send a JSON text frame containing a `status` event within
  1 second of connect

#### Scenario: Heartbeat event pushed periodically

- **WHEN** a WebSocket connection has been open for 5 seconds
- **THEN** the server SHALL have sent at least one additional JSON frame (the heartbeat)
  to the client

#### Scenario: Decode event pushed after each FT8 cycle

- **WHEN** a WebSocket connection is active and a FT8 decode cycle completes
- **THEN** the server SHALL push a `decode` event to the connected client within 500 ms
  of the cycle completing

#### Scenario: Non-WebSocket request to WS endpoint returns 400

- **WHEN** a plain HTTP GET (no Upgrade header) is sent to `/api/v1/ws`
- **THEN** the server SHALL respond with HTTP 400
