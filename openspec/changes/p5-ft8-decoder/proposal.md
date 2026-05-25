## Why

Phase 4 delivered a proven, cross-platform PCM capture pipeline — `CaptureManager.Samples`
is a live `ChannelReader<float[]>` delivering 12 kHz mono float chunks to anyone who will
consume them. FR-001 (FT8 receive-only decode) and FR-009 (decoded messages list) are the
core value proposition of OpenWSFZ v1; without them the application is an audio-configured
web server with a placeholder waterfall. With the capture foundation solid, the time to
build the FT8 decoder is now.

## What Changes

- **`OpenWSFZ.Ft8` project** (new) — cleanroom C# FT8 DSP library:
  - `IClock` interface (fleshed out): `UtcNow` property; injected for testable cycle alignment
  - `IModeDecoder` interface (fleshed out): `DecodeAsync(float[] pcm, CancellationToken ct)`
    returning `IReadOnlyList<DecodeResult>`
  - `DecodeResult` record: `Time`, `Snr`, `Dt`, `FreqHz`, `Message`
  - `CycleFramer`: accumulates PCM chunks from `CaptureManager.Samples`, emits one
    exactly-15-second audio window per FT8 cycle, UTC-aligned to even second boundaries
  - `Ft8Decoder` implementing `IModeDecoder`: GFSK symbol extraction → costas-array sync →
    LDPC(174,87) soft-decision decode → CRC-14 check → 77-bit message unpack
- **`tests/OpenWSFZ.Ft8.Tests`** (new) — fixture-based unit tests using known-good WAV
  snippets and reference bit vectors; no real audio device required
- Both new projects added to `OpenWSFZ.slnx`
- **`CycleFramer` wired into daemon** (`Program.cs`) — started alongside `CaptureManager`,
  shut down on `ApplicationStopping`
- **WebSocket `decode` event** — after each cycle the `WebSocketHub` broadcasts a `decode`
  event to all connected clients carrying the list of `DecodeResult` payloads
- **`js/main.js` decode handler** — handles incoming `decode` WS events and populates the
  existing `#decodes-table` (columns already scaffolded: Time, dB, DT, Freq, Message);
  newest decode rows prepended; table capped at 200 rows

## Capabilities

### New Capabilities

- `ft8-decoder`: Cleanroom FT8 DSP pipeline — cycle framing, LDPC(174,87) soft-decision
  decode, CRC-14 verification, and 77-bit message unpacking producing `DecodeResult` records
- `decode-events`: WebSocket `decode` event broadcast from daemon to browser and corresponding
  UI handler that populates the decoded-messages table in real time

### Modified Capabilities

- `daemon-host`: Daemon now starts and stops the `CycleFramer`/`Ft8Decoder` pipeline as part
  of its application lifecycle (alongside the existing `CaptureManager` hooks)
- `web-server`: WebSocket endpoint now also pushes `decode` events (one per FT8 cycle) in
  addition to the existing `status` and `heartbeat` events

## Impact

- **New projects**: `src/OpenWSFZ.Ft8`, `tests/OpenWSFZ.Ft8.Tests` — both added to solution
- **`src/OpenWSFZ.Abstractions`**: `IModeDecoder` and `IClock` interfaces fleshed out;
  `DecodeResult` record added
- **`src/OpenWSFZ.Audio`**: `CaptureManager` unchanged; consumed by new `CycleFramer`
- **`src/OpenWSFZ.Daemon`**: `Program.cs` wires in `CycleFramer` and `Ft8Decoder`
- **`src/OpenWSFZ.Web`**: `WebSocketHub` gains `decode` broadcast; `AppJsonContext` updated
  for `DecodeResult` serialisation
- **`web/js/main.js`**: new `decode` event handler
- **Dependencies added**: none expected — DSP is pure C#; LDPC tables are generated at build
  time or hard-coded from the public FT8 specification
- **License**: all DSP derived from public protocol specifications (QEX Nov/Dec 2019 paper by
  Franke & Taylor); no GPL-3.0 code borrowed
