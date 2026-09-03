## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel
function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time
in the shim. **This change SHALL advance the expected constant from `20260049`
(`f001-h12-unique-match-suppression`) to `20260050`.**

This bump is MEASURE-ONLY, like `20260047`/`20260048` (`f001-sup-b-instrumented-suppression-sizing`)
before it — unlike `20260049`, it changes no decode output. No existing production entry point's
ABI or struct layout SHALL change: `DecodeAll`, `GetLastPassCounts`, `SetDecodeParams`, and every
other existing exported symbol remain byte-for-byte unchanged in signature, and the `FT8Result`
struct layout is untouched.

If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw
`InvalidOperationException` with a message that names the library path and the mismatched version
values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the
  committed shim source at `FT8_SHIM_VERSION = 20260050`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Previous library (20260049) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260049`
  (`f001-h12-unique-match-suppression` — the unique-match suppression pin, which does not yet
  export the unresolved-by-code table) after this change's managed code expects its own newer
  constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is
  attempted, with a message identifying the library path and the version mismatch

## ADDED Requirements

### Requirement: Diagnostic 12-bit hash-path unresolved-by-code native export

The shim SHALL export one native function, `ft8_get_h12_unresolved_by_code(counts, capacity,
out_of_range)`, copying a complete 4,096-row per-code table into the caller-supplied `counts`
buffer — one count per 12-bit code, incremented whenever a 12-bit hash-path lookup found **no**
matching table entry (the complement of `ft8_get_h12_by_code`'s resolved-and-displayed
population) — and writing the shared code-width-violation count (`g_h12_code_out_of_range`,
already defined by the `f001-sup-b-instrumented-suppression-sizing` Phase 2 export) into
`out_of_range`. It SHALL return the code-space size (4,096) on success, and `-1` if `capacity` is
less than the code-space size or if any pointer argument, `out_of_range` included, is `NULL` — a
caller MUST check for `-1` rather than assume success. **This export SHALL NOT be added to
`IFt8NativeInterop`, and SHALL get no `Ft8LibInterop` P/Invoke binding, no `Ft8NativeInteropAdapter`
method, no `Ft8Decoder` wrapper, and no test-double stub in any existing `IFt8NativeInterop`
implementer** — its only intended consumer is a measurement harness driving the native library
directly (e.g. via Python `ctypes`), following the identical precedent `ft8_get_h12_by_code` already
established for this exact shape of table (design.md Decision D2).

The counting condition SHALL be `tls_h12_lookup_performed && !tls_h12_resolved`, evaluated in an
`else if` on the same guard family as the existing resolved-branch emission-site counters — never
in a second, independent `if` block, and never inside `cb_lookup_hash` itself (design.md Decision
D4).

#### Scenario: The export is present in all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_get_h12_unresolved_by_code` SHALL be resolvable via the platform's
  native-library loading mechanism on Windows, Linux, and macOS without error

#### Scenario: A capacity smaller than the code space is rejected, not partially filled

- **WHEN** `ft8_get_h12_unresolved_by_code` is called with `capacity` less than 4,096
- **THEN** the function SHALL return `-1` and SHALL NOT write to any output buffer

#### Scenario: A NULL pointer argument, including out_of_range, is rejected

- **WHEN** `ft8_get_h12_unresolved_by_code` is called with any of its two pointer arguments `NULL`
- **THEN** the function SHALL return `-1` and SHALL NOT write to any output buffer

#### Scenario: A successful call copies the full table and the shared violation count

- **WHEN** `ft8_get_h12_unresolved_by_code` is called with `capacity >= 4096` and both `counts`/
  `out_of_range` non-`NULL`
- **THEN** the function SHALL return `4096`, SHALL write exactly 4,096 entries to `counts`, and
  SHALL write the current, shared code-width-violation count to `out_of_range`

#### Scenario: A lookup that resolved is never counted here

- **WHEN** a 12-bit hash-path lookup finds a matching table entry (`tls_h12_resolved == true`),
  whether or not that match is later suppressed as ambiguous
- **THEN** it SHALL NOT increment any entry in this export's table — that population is
  `ft8_get_h12_by_code`'s, not this Requirement's, and the two tables' code-indexed counts are
  never double-counted for the same lookup

#### Scenario: No production call site invokes the export

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable
  from `DecodeAll`) is inspected after this change lands
- **THEN** it SHALL contain no call to `ft8_get_h12_unresolved_by_code` outside of QA measurement
  harnesses

#### Scenario: No managed binding exists for the export

- **WHEN** `IFt8NativeInterop.cs`, `Ft8LibInterop.cs`, `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`,
  and every existing `IFt8NativeInterop` implementer are inspected after this change lands
- **THEN** none of them SHALL reference `ft8_get_h12_unresolved_by_code`, `GetH12UnresolvedByCode`,
  or any equivalent managed name — this is a deliberate scope boundary (design.md Decision D2), not
  an omission to be filled in later

#### Scenario: Existing exports and decode paths are unaffected

- **WHEN** the new binary's exported symbol table is compared against the prior `20260049` build,
  and `ft8_shim.c`'s existing decode-path logic (beyond the additive table-write inside the new,
  purely additive emission-site branch) is diffed against its pre-change source
- **THEN** every previously-exported symbol SHALL be present with an unchanged signature,
  `ft8_get_h12_unresolved_by_code` SHALL be the only new export this Requirement adds, and the diff
  on every existing decode-path computation SHALL be zero — confirmed by a byte-identical decode
  comparison of an existing corpus on the `20260049` and `20260050` binaries (spec §5 ROW 0e), not
  merely asserted from the diff being additive
