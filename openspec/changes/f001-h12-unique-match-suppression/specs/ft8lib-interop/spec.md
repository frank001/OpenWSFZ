## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel
function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time
in the shim. **This change SHALL advance the expected constant from `20260048`
(`f001-sup-b-instrumented-suppression-sizing` Phase 2) to `20260049`.**

🔴 **Unlike the two bumps immediately preceding it, this bump is behaviour-bearing on the decode
output path.** `20260047` and `20260048` were both MEASURE-ONLY; `20260049` changes what the
decoder renders for an ambiguous 12-bit hash reference. No existing production entry point's ABI or
struct layout SHALL change: `DecodeAll`, `GetLastPassCounts`, `SetDecodeParams`, and every other
existing exported symbol remain byte-for-byte unchanged in signature, and the `FT8Result` struct
layout is untouched — this is a behaviour-bearing rebuild, not an ABI break.

If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw
`InvalidOperationException` with a message that names the library path and the mismatched version
values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the
  committed shim source at `FT8_SHIM_VERSION = 20260049`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Previous library (20260048) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260048`
  (`f001-sup-b-instrumented-suppression-sizing` Phase 2 — the measure-only pin, which still
  displays a callsign resolved from an ambiguous probe chain) after this change's managed code
  expects its own newer constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is
  attempted, with a message identifying the library path and the version mismatch

## ADDED Requirements

### Requirement: Diagnostic 12-bit suppression-count native export and P/Invoke entry point

The shim SHALL export a read-only getter, `ft8_get_h12_suppressed_count`, returning the
process-lifetime count of decodes whose 12-bit-hash-resolved callsign was withheld because its
probe chain held two or more matching entries. It SHALL be bound in managed code as
`IFt8NativeInterop.GetH12SuppressedCount()`, following the three existing 12-bit sizing getters'
own pattern.

Reading the count SHALL have no side effects on decode behaviour, on the hash table, or on any
other counter.

#### Scenario: The getter is exported by all three platform binaries

- **WHEN** the shim is built for Windows x64, Linux x64 and macOS ARM64
- **THEN** `ft8_get_h12_suppressed_count` SHALL be present and resolvable in each binary

⚠️ The Windows build carries an explicit export list; the Linux build relies on default symbol
visibility. A symbol omitted from that list builds and links clean on Linux and fails only on
Windows, only at runtime, on `P/Invoke` resolution. This scenario is not satisfied by a successful
Linux build.

#### Scenario: Reading the count has no side effects

- **WHEN** `GetH12SuppressedCount()` is called any number of times between decode cycles
- **THEN** subsequent decode results SHALL be identical to those produced without the calls
- **AND** the returned value SHALL be unchanged by the act of reading it

#### Scenario: The method is callable on a fake implementation

- **WHEN** a test double implements `IFt8NativeInterop`
- **THEN** it SHALL be able to satisfy `GetH12SuppressedCount()` with a fixed value, without
  loading the native library

#### Scenario: Existing exports and decode paths are unaffected

- **WHEN** the shim is rebuilt at `20260049`
- **THEN** every previously exported symbol SHALL remain present with an unchanged signature
- **AND** the only decode-output difference from `20260048` SHALL be the callsign token of messages
  whose 12-bit hash reference resolved against an ambiguous probe chain
