## Context

The FT8 decode pipeline produces `IReadOnlyList<DecodeResult>` after each 15-second cycle. Each `DecodeResult` carries SNR, DT, audio frequency offset, and message text. The operator currently sees these results only through the WebSocket event bus; there is no persistent record on disk.

WSJT-X writes every decoded message to `ALL.TXT` in a well-known columnar format used by logging tools, contest software, and manual comparison workflows. An operator comparing OpenWSFZ output against WSJT-X must do so manually; `ALL.TXT` eliminates that friction.

Two pieces of information required by the format are missing from the current system:
- **Date component of the cycle timestamp** — `DecodeResult.Time` is `"HH:mm:ss"` (no date). The date must be inferred from the UTC wall-clock time captured at the start of the decode call.
- **Dial frequency** — the radio's VFO setting (e.g. 7.074 MHz) is not known to the daemon. The operator must supply it via configuration.

## Goals / Non-Goals

**Goals:**
- Write one line per decoded message to `ALL.TXT` (or a configured path) after each decode cycle, in the WSJT-X format.
- Provide `dialFrequencyMHz` and `allTxtPath` (plus `allTxtEnabled`) as operator-configurable fields.
- File write failures SHALL NOT affect decode results, WebSocket emission, or application uptime.
- Expose the new config fields on the Settings page.
- Add formal `FR-027` and `FR-028` to `REQUIREMENTS.md`.

**Non-Goals:**
- Log rotation for `ALL.TXT` (could be added later as a separate requirement).
- ADIF, CSV, or any other export format.
- Real-time SDR frequency readout (the dial frequency is a static config value, not VFO tracking).
- Retroactive population of `ALL.TXT` from prior sessions.

## Decisions

### D1 — AllTxtWriter as a plain DI service, not a BackgroundService

The decode pump in `Program.cs` already runs a sequential async loop. Calling `allTxtWriter.AppendAsync(cycleUtc, results)` immediately after `DecodeAsync` returns is sufficient; no background queue is needed. A plain scoped/singleton service keeps the design minimal and avoids the complexity of a channel or producer–consumer pattern for a ~15-second-interval operation.

_Alternative considered_: `IHostedService` with a `Channel<(DateTime, IReadOnlyList<DecodeResult>)>`. Rejected as disproportionate for the workload.

### D2 — Open–append–close per cycle for file I/O

Each `AppendAsync` call opens the file in append mode, writes all lines for the cycle, and closes it. This avoids holding a file handle open between cycles (no handle leak on crash, no flush-timing issues) and is safe for external tools that read `ALL.TXT` between cycles.

_Alternative considered_: Keep a `StreamWriter` open for the session lifetime. Rejected because a crash or process kill could leave unflushed lines; the 15-second inter-write interval makes open-close-per-cycle cost negligible.

### D3 — Timestamp construction from cycleUtc + result.Time

`Program.cs` captures `DateTime.UtcNow` immediately before calling `DecodeAsync`. This is passed to `AllTxtWriter.AppendAsync` as `cycleUtc`. The ALL.TXT timestamp is formed as:

```csharp
string date = cycleUtc.ToString("yyMMdd");
string time = result.Time.Replace(":", "");   // "17:29:30" → "172930"
string timestamp = $"{date}_{time}";           // "260528_172930"
```

The date from `cycleUtc` and the time from `result.Time` are independent sources; they could theoretically disagree for cycles that straddle midnight by more than the decode latency. In practice this is negligible (p8 decode latency is 4–7 s; the mismatch window is <10 s per day), and WSJT-X itself uses the same approach (wall-clock date + snapped cycle time).

_Alternative considered_: Add `DateTime CycleStartUtc` to `DecodeResult`. Rejected as a disproportionate change to a shared abstraction for what is an output-formatting concern.

### D4 — New config sub-object `decodeLog`

Group the three related fields under `AppConfig.DecodeLog`:

```json
"decodeLog": {
  "enabled": true,
  "path": "ALL.TXT",
  "dialFrequencyMHz": 7.074
}
```

This mirrors the existing `logging` sub-object pattern and keeps top-level `AppConfig` from accumulating scattered scalar fields. `dialFrequencyMHz` lives here because it is used exclusively for the ALL.TXT output line; it is not a general transceiver frequency setting.

### D5 — Line format

```
YYMMDD_HHMMSS     D.DDD Rx FT8 {snr,6} {dt,5:F1} {freq,4} {message}
```

Implemented in C# as:

```csharp
$"{timestamp}     {config.DialFrequencyMHz:F3} Rx FT8 {result.Snr,6} {result.Dt,5:F1} {result.FreqHz,4} {result.Message}"
```

This reproduces the exact column alignment observed in WSJT-X `ALL.TXT` files.

## Risks / Trade-offs

- **Invalid path configured** → `AllTxtWriter` SHALL log a Warning and skip writing for that cycle; it SHALL NOT throw. The decode result list and WebSocket emission are unaffected.
- **Directory does not exist** → `AllTxtWriter` attempts `Directory.CreateDirectory` on first write; failure is treated the same as an invalid path.
- **Very large ALL.TXT** → No rotation is provided in this change. Operators on busy bands could accumulate large files over days. Acceptable for v1; rotation can be added as FR-029 if needed.
- **Dial frequency = 0.0 (unconfigured)** → The line will show `0.000 Rx FT8 …` which is clearly wrong but not harmful. The UI SHALL show a warning or placeholder if `dialFrequencyMHz` is 0.

## Open Questions

None blocking implementation.
