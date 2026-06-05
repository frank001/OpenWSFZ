## Context

`SerialCatConnection` is the serial CAT implementation used when `rigModel = "SerialCat"`. It communicates with the rig using ASCII commands in the Yaesu/Kenwood FA protocol: `FA;` to query VFO-A frequency and `FA<Hz>;` to set it.

The FA command's Hz field is zero-padded to a fixed width that varies by rig family:

| Rig family | Width | Example response |
|---|---|---|
| FT-991, FT-891, FT-857D | 9 | `FA014074000;` |
| TS-2000, FT-DX10, FT-DX5000 | 11 | `FA00014074000;` |
| Some older Kenwood | 10 | `FA014074000;` (varies) |

The current implementation hard-codes `D11` in `SetDialFrequencyMhzAsync`. A 9-digit rig receives `FA00014074000;` instead of the expected `FA014074000;` and silently ignores the command — the poll continues to work because `GetDialFrequencyMhzAsync` already accepts 8–11 digit responses, but the set command has no effect.

Hamlib solves this identically in its `newcat` backend: a `width_frequency` field is stored per-connection, lazily populated from the first FA; response via `priv->width_frequency`, then used as a dynamic width in `SNPRINTF("F%c%0*lld;", c, priv->width_frequency, freq)`.

## Goals / Non-Goals

**Goals:**

- SET commands use the same digit width the rig uses in GET responses — correct for all rig families without configuration.
- `LogDebug` entries record the exact command sent and raw response received, making future serial-layer issues diagnosable from Trace-level logs alone.
- The `cat-control` spec is corrected to match the implementation delivered in p19 and this change.
- Existing tests continue to pass; new tests cover both 9-digit and 11-digit rig profiles.

**Non-Goals:**

- Support for binary BCD protocol rigs (FT-817, FT-818) — those require an entirely different command codec and are out of scope.
- Dynamic re-calibration if the rig changes its response width mid-session — the width is written once from the first successful GET and treated as fixed for the connection lifetime.
- Changes to `RigctldConnection` — the rigctld path returns plain Hz integers and is not affected by this issue.
- Any user-visible configuration field.

## Decisions

### D1 — Self-discovery from GET response (not a lookup table, not a config field)

**Chosen**: Measure `digitCount = full.Length - 3` from the first successful `GetDialFrequencyMhzAsync` response and store it.

**Alternatives considered**:
- *Lookup table keyed on rig model*: Requires maintaining an ever-growing table, and `rigModel` in the config is `"SerialCat"` (generic) — there is no rig model identifier. Rejected.
- *User-configurable `catCommandDigits` field*: Adds operator burden for something the rig reveals automatically. Rejected in line with the principle that obvious things should not require configuration.
- *Always try 9 digits first, then 11 on failure*: Non-trivial retry logic, race conditions with the poll lock, and some rigs may not signal an error on a wrong-width command. Rejected.

The self-discovery approach mirrors Hamlib's production-proven behaviour and requires exactly one field and three lines of code.

### D2 — `volatile int` for `_freqWidth`, no lock

`_freqWidth` is written exactly once: from `GetDialFrequencyMhzAsync` when transitioning from 0 to the discovered value. After that it is read-only. A `volatile int` field guarantees visibility of the write across threads (the poll loop thread and the HTTP request thread) without the overhead of a lock. Writes of `int` are atomic on all .NET-supported architectures; the `volatile` keyword prevents the JIT from caching the zero in a register and missing the update.

### D3 — Default to 11 until first poll

The fallback value of 11 is chosen because:
1. It is the widest format and matches all known modern FT-DX/TS-2000 rigs, which are the most commonly connected over serial.
2. The window where the fallback is used is at most one poll interval (≤ 3 s in production). A tune request arriving before the first poll is unusual; if it does arrive, a 9-digit rig will silently ignore the command, but the next poll will correct the displayed frequency and the operator can retry.
3. The alternative (blocking the SET until the first GET completes) would require a `SemaphoreSlim` or `TaskCompletionSource`, complicating the implementation for an edge case that resolves itself within seconds.

### D4 — Calibrate on first successful GET, not in ConnectAsync

`ConnectAsync` currently opens the serial port only — it does not send any command. Adding a calibration FA; query to `ConnectAsync` would:
- Change the semantics of a method that currently performs no I/O beyond `Open()`
- Create a second code path for the FA; exchange separate from the poll loop
- Require timeout and retry handling in a method not currently expected to throw `TimeoutException`

The lazy-initialisation approach (`if (_freqWidth == 0) _freqWidth = digitCount`) inside `GetDialFrequencyMhzAsync` keeps calibration on the normal poll path with no additional code paths.

## Risks / Trade-offs

- **[Risk] First tune before first poll uses wrong width** → Mitigated by D3 (11 is correct for modern rigs; the poll-correction cycle handles the edge case for 9-digit rigs). Documented in comments.
- **[Risk] Rig returns variable-length responses** → No known rig in the FA protocol family does this. The spec constrains responses to 8–11 digits; anything outside that range raises `InvalidOperationException` and the poll fails, which is the existing behaviour. `_freqWidth` is only written when the response is valid.
- **[Risk] `_freqWidth` is written by poll thread and read by HTTP thread with no lock** → Mitigated by D2 (`volatile int`). The write is idempotent after the first valid GET — even in the vanishingly unlikely case of a double-write, both threads would write the same value.
