## Context

Phase 4 established a proven, cross-platform PCM capture pipeline. `CaptureManager.Samples`
is a bounded `ChannelReader<float[]>` delivering 12 kHz mono float32 chunks; it is live and
tested on Windows (WASAPI). `IModeDecoder` and `IClock` are stub interfaces in
`OpenWSFZ.Abstractions`. The `OpenWSFZ.Ft8` project directory exists in the file system
(build artifacts only) but has no source files and is not wired into the solution.

The FT8 protocol is fully specified in the public domain: Franke & Taylor, "The FT4 and FT8
Communication Protocols", QEX Nov/Dec 2019. All DSP in this phase is derived from that
specification — no GPL-3.0 source is consulted.

## Goals / Non-Goals

**Goals:**
- Implement a cleanroom FT8 decoder in pure C# that produces `DecodeResult` records from
  raw PCM (FR-001)
- Frame 15-second UTC-aligned audio windows from `CaptureManager.Samples` and feed them
  to the decoder once per FT8 cycle
- Broadcast decoded results to all connected WebSocket clients as `decode` events (FR-009)
- Populate the existing `#decodes-table` in the browser UI with real decoded messages
- Achieve the hard real-time deadline: decode must complete before the next cycle begins
  (NFR-003)
- All components unit-testable without a real audio device (fixture WAVs and bit vectors)

**Non-Goals:**
- Waterfall / spectrogram rendering (p6)
- Transmit, PTT, rig control (v2+)
- Decode persistence / logging (v2+)
- Other modes (FT4, JT65, WSPR, etc.) — p5 is FT8 only
- ARM64 or non-x86_64 performance tuning
- Adaptive SNR threshold tuning (fixed threshold for v1)

## Decisions

### 1. Pure C# DSP — no native interop

FT8 decoding is primarily array arithmetic (FFT, matrix multiply for LDPC). Modern .NET 10
`System.Numerics` and `Span<T>` provide efficient vectorised primitives without P/Invoke.

**Alternatives considered:**
- *P/Invoke to a C shared library*: adds platform-specific packaging and limits AOT
  compatibility. Rejected unless C# proves too slow.
- *FFmpeg DSP via LibVLCSharp*: wrong abstraction level; overkill for tone detection.
  Rejected.
- *Fortran*: explicitly excluded by project constraints.

### 2. 8-FSK symbol demodulation via Goertzel per-tone DFT

FT8 uses 8-FSK with 79 symbols, 6.25 Hz tone spacing, ~0.16 s symbol duration at 12 kHz.
Each symbol window is 1920 samples. For each symbol interval, compute the energy at each of
the 8 candidate frequencies using the Goertzel algorithm (a single-bin DFT). The tone with
maximum energy is the decoded symbol.

**Alternatives considered:**
- *Full FFT per symbol*: higher overhead for only 8 bins needed; Goertzel is exact and
  efficient for a small number of target frequencies. Rejected.
- *Correlation with pre-computed sinusoids*: equivalent to Goertzel, higher memory. Rejected.

### 3. Costas-array synchronisation by 2-D cross-correlation

FT8 transmissions are framed by three Costas arrays (7 symbols each at positions 0, 36, 72).
Synchronisation is achieved by sliding a 7×7 template across the time–frequency grid and
locating the peak correlation. This gives the sample offset and frequency offset before LDPC.

**v1 known limitation — frequency sweep only:**  
The v1 implementation (`CostasSynchroniser`) slides the template over frequency (tone-bin
offset) but not time (symbol offset is fixed at 0). The FT8 protocol allows ±1 second of
clock skew between transmitter and receiver, meaning the first Costas array may arrive
anywhere from sample −12 000 to +12 000 of the captured buffer. Transmissions that start
more than ~0.1 s off the UTC cycle boundary will be missed until the time-domain sweep
is implemented (see task 4.2-bis). Operators using GPS-disciplined or NTP-synchronised
clocks (standard practice) will be minimally affected by this gap in v1.

**Alternatives considered:**
- *Matched filter in frequency domain*: equivalent but more complex to implement cleanly in
  a streaming context. Rejected for v1.

### 4. LDPC(174,87): min-sum belief propagation, 50 iterations

The generator matrix `H` (87×174) is published in the FT8 specification and embedded as a
constant array in `OpenWSFZ.Ft8`. The decoder uses log-likelihood ratios (LLRs) derived from
symbol energies and runs min-sum flooding for up to 50 iterations per candidate.

The 14-bit CRC is checked after each LDPC pass; if it passes the message is accepted.

**Alternatives considered:**
- *Sum-product (belief propagation)*: more accurate in theory; significantly more expensive
  per iteration. For v1 at desktop hardware headroom this distinction is not material.
  Deferred.
- *Hard-decision decoding*: cheaper but far less effective at low SNR. Rejected — FT8's
  weak-signal advantage comes from soft-decision LDPC.

### 5. CycleFramer: wall-clock aligned, IClock-injected

`CycleFramer` consumes `CaptureManager.Samples` on a background Task. It computes the
sample offset into the current 15-second cycle using `IClock.UtcNow`, pre-fills up to one
window of silence if the daemon starts mid-cycle, then accumulates 180 000 samples
(15 s × 12 000 Hz) before firing the decode callback. If the decode task from the previous
cycle is still running when the new window closes, the new window is queued (capacity 1);
overflow is dropped with a warning (should not happen on modern hardware).

`IClock` is injected so tests can control cycle alignment without real-time dependencies.

### 6. Decode result delivery: Channel → daemon pump → WebSocket broadcast

`CycleFramer` writes completed `DecodeResult[]` arrays to a `Channel<DecodeResult[]>`
(bounded, capacity 2, `DropOldest`). A background pump in `Program.cs` reads the channel
and calls `WebSocketHub.BroadcastDecodes(results)`. The hub sends a JSON `decode` event
to each connected socket, discarding stale connections silently.

**Alternatives considered:**
- *IObservable / Rx.NET*: additional NuGet dependency, no meaningful advantage at this scale.
  Rejected.
- *Direct callback from CycleFramer*: couples framer to hub, harder to test. Rejected.
- *ASP.NET Core SignalR*: significant additional surface area; WS is already wired. Rejected.

### 7. WebSocket event shape

All existing WS events follow `{ "type": "<name>", "payload": <object> }`. The new `decode`
event follows the same shape:

```json
{
  "type": "decode",
  "payload": [
    { "time": "15:30:00", "snr": -12, "dt": 0.3, "freqHz": 1234, "message": "W1AW K1TTT EN43" }
  ]
}
```

An empty array payload `[]` is valid and represents a cycle with no decodes.

### 8. Fixture-based testing strategy

Unit tests use:
- **Known LDPC codewords** from the specification appendix (round-trip encode/decode)
- **CRC-14 vectors** from the spec
- **77-bit message pack/unpack** against reference callsign / grid pairs
- **WAV fixture file** (embedded resource, ~170 kB) captured from a known FT8 signal;
  used to smoke-test the full decode pipeline end-to-end in CI without a real device

The WAV fixture is committed to `tests/OpenWSFZ.Ft8.Tests/Fixtures/`. Toolchain: xUnit,
matching the rest of the test suite. Test class prefix: `Ft8-Decoder:`.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| LDPC convergence rate below WSJT-X parity without access to reference tuning | Start with 50 iterations min-sum; benchmark against public WAV test vectors from the spec; tune iteration count if needed |
| Costas sync missing weak signals | Accept for v1; tune correlation threshold empirically with fixture WAVs; document known limitation |
| Decode latency overruns 15-second deadline on slow hardware | Profile on target HW early; the algorithm is O(n) in samples; LDPC iteration count is the lever |
| `CycleFramer` clock skew vs. transceiver-side clock | Operator's PC and radio clocks should be within ±1 s (standard HAM practice); `IClock` injection allows future NTP-discipline |
| WebSocket broadcast blocking the decode pump | Hub sends to each socket with a per-socket 1-second timeout; lagging sockets are closed |

## Open Questions

1. **SNR reporting precision** — the spec gives SNR in dB relative to noise in a 2500 Hz
   passband. Confirm the exact dB calculation formula matches what WSJT-X displays so the UI
   is directly comparable.
2. **FT8 message format** — standard messages (callsign/grid/report), non-standard (free
   text, compound callsigns) — scope for v1 is standard messages only; non-standard messages
   decoded but displayed as raw 72-bit hex.
3. **WAV fixture provenance** — capture a clean fixture from a real 20m FT8 session or use a
   synthetic test vector generated by a reference encoder. Either is acceptable; capture from
   real air is preferred for end-to-end confidence.
