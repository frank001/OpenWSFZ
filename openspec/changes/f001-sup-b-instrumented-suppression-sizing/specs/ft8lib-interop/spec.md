## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel
function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time
in the shim. **Phase 1 of this change (the three 12-bit hash-path sizing getters, shipped
2026-08-30) advanced the expected constant from `20260046`
(`fix-negative-time-offset-snr-collapse`) to `20260047`.** **Phase 2 of this change (Amendment 2's
per-code cluster table, spec'd, not yet built) SHALL advance the expected constant again,
`20260047` → `20260048`.** No existing production entry point's ABI, struct layout, or decode
behaviour SHALL change at either bump; `DecodeAll`, `GetLastPassCounts`, `SetDecodeParams`, and
every other existing exported symbol all remain byte-for-byte unchanged. If the returned value does
not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a
message that names the library path and the mismatched version values. This requirement applies on
all three reference platforms.

#### Scenario: Correct library passes the ABI self-test (Phase 1, shipped)

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the
  committed shim source at Phase 1's own `FT8_SHIM_VERSION = 20260047`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Pre-Phase-1 library (20260046) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260046`
  (`fix-negative-time-offset-snr-collapse`) after Phase 1's managed code expects its own newer
  constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is
  attempted, with a message identifying the library path and the version mismatch

#### Scenario: Correct library passes the ABI self-test (Phase 2, once shipped)

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the
  committed shim source at Phase 2's own `FT8_SHIM_VERSION = 20260048`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Pre-Phase-2 library (20260047) fails fast with a clear error, once Phase 2 ships

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260047` (Phase 1, the pin
  the 2026-08-30 15:39Z ROW 0 result ran against) after Phase 2's managed code expects its own
  newer constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is
  attempted, with a message identifying the library path and the version mismatch

## ADDED Requirements

### Requirement: Diagnostic 12-bit hash-path sizing getters and P/Invoke entry points (Phase 1 — shipped 2026-08-30, shim `20260047`)

The shim SHALL export three native functions — `ft8_get_h12_displaying_count()`,
`ft8_get_h12_ambiguous_count()`, `ft8_get_h12_divergent_count()` — each returning the corresponding
process-lifetime cumulative count defined by the `hashed-callsign-resolution` capability's
"Observable 12-bit hash-path unique-match sizing" Requirement. `Ft8LibInterop` SHALL expose
corresponding managed methods (`GetH12DisplayingCount`, `GetH12AmbiguousCount`,
`GetH12DivergentCount`) via P/Invoke, matching the existing `GetHashTableRejectCount` diagnostic-
getter pattern. `IFt8NativeInterop` SHALL add corresponding methods so that test doubles can supply
deterministic fixed values without loading the native DLL.

#### Scenario: All three getters are exported by all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbols `ft8_get_h12_displaying_count`, `ft8_get_h12_ambiguous_count`, and
  `ft8_get_h12_divergent_count` SHALL each be resolvable via the platform's native-library loading
  mechanism on Windows, Linux, and macOS without error

#### Scenario: Reading the counts has no side effects

- **WHEN** any of the three managed getters is called, at any point during or after a session
- **THEN** the call SHALL return the current cumulative value
- **AND** SHALL NOT reset any count, alter the hash table's contents, or affect subsequent decode
  behaviour in any way

#### Scenario: A per-cycle log line records all three counts together

- **WHEN** a decode cycle completes
- **THEN** the daemon's per-cycle log line SHALL record all three counts' current cumulative
  values, labelled `h12Displaying`, `h12Ambiguous`, and `h12Divergent`, explicitly as
  process-lifetime cumulative (not per-cycle deltas), even when all three are zero

#### Scenario: IFt8NativeInterop's three methods are callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that returns fixed values for the
  three new methods
- **THEN** calling each SHALL return its configured fixed value without loading the native DLL

---

### Requirement: Diagnostic 12-bit hash-path per-code cluster table native export (Phase 2 — Amendment 2, spec'd, not yet built, shim `20260048`)

The shim SHALL export one native function, `ft8_get_h12_by_code(displaying, ambiguous, divergent,
capacity, out_of_range)`, copying the complete 4,096-row per-code table defined by the
`hashed-callsign-resolution` capability's "Observable 12-bit hash-path per-code cluster identity"
Requirement into caller-supplied buffers, and writing the code-width-violation count into
`out_of_range`. It SHALL return the code-space size (4,096) on success, and `-1` if `capacity` is
less than the code-space size or if any pointer argument, `out_of_range` included, is `NULL` — a
caller MUST check for `-1` rather than assume success. **This export SHALL NOT be added to
`IFt8NativeInterop`, and SHALL get no `Ft8LibInterop` P/Invoke binding, no `Ft8NativeInteropAdapter`
method, no `Ft8Decoder` wrapper, and no test-double stub in any existing `IFt8NativeInterop`
implementer** — its only intended consumer is a measurement harness driving the native library
directly (e.g. via Python `ctypes`), following the precedent this capability already established
for `ft8_ldpc_decode_llrs` (a diagnostic-only export with no managed binding, `r2-coherent-llr-
instrument` Decision D10).

#### Scenario: The export is present in all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_get_h12_by_code` SHALL be resolvable via the platform's native-library
  loading mechanism on Windows, Linux, and macOS without error

#### Scenario: A capacity smaller than the code space is rejected, not partially filled

- **WHEN** `ft8_get_h12_by_code` is called with `capacity` less than 4,096
- **THEN** the function SHALL return `-1` and SHALL NOT write to any output buffer

#### Scenario: A NULL pointer argument, including out_of_range, is rejected

- **WHEN** `ft8_get_h12_by_code` is called with any of its five pointer arguments `NULL`
- **THEN** the function SHALL return `-1` and SHALL NOT write to any output buffer

#### Scenario: A successful call copies the full table and the violation count

- **WHEN** `ft8_get_h12_by_code` is called with `capacity >= 4096` and all five pointers non-`NULL`
- **THEN** the function SHALL return `4096`, SHALL write exactly 4,096 entries to each of the three
  count buffers, and SHALL write the current code-width-violation count to `out_of_range`

#### Scenario: No production call site invokes the export

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable
  from `DecodeAll`) is inspected after Phase 2 lands
- **THEN** it SHALL contain no call to `ft8_get_h12_by_code` outside of QA measurement harnesses

#### Scenario: No managed binding exists for the export

- **WHEN** `IFt8NativeInterop.cs`, `Ft8LibInterop.cs`, `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`,
  and every existing `IFt8NativeInterop` implementer are inspected after Phase 2 lands
- **THEN** none of them SHALL reference `ft8_get_h12_by_code`, `GetH12ByCode`, or any equivalent
  managed name — this is a deliberate scope boundary (design.md Decision D5), not an omission to be
  filled in later

#### Scenario: Existing exports and decode paths are unaffected

- **WHEN** the new binary's exported symbol table is compared against the prior `20260047` build,
  and `ft8_shim.c`'s existing decode-path logic (beyond the additive table-write inside the
  existing, unchanged emission-site guard) is diffed against its pre-Phase-2 source
- **THEN** every previously-exported symbol (all nineteen) SHALL be present with an unchanged
  signature, `ft8_get_h12_by_code` SHALL be the only new export this Requirement adds, and the diff
  on every existing decode-path computation SHALL be zero
