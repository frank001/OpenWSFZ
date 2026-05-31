## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. The expected constant SHALL be `20260001` (updated from `20240001` in p15 to reflect the ABI change introduced by `ft8_get_last_pass_counts`). If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at `FT8_SHIM_VERSION = 20260001`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Wrong library fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary that returns an unexpected version constant (e.g. the pre-p15 value `20240001`)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

---

## ADDED Requirements

### Requirement: Per-pass decode counts are accessible from managed code

`Ft8LibInterop` SHALL expose a method `GetLastPassCounts(int maxPasses)` that calls the native `ft8_get_last_pass_counts` function via P/Invoke and returns a managed `int[]` of length equal to the number of passes actually executed. This method SHALL only be called after a `DecodeAll` call on the same thread.

#### Scenario: GetLastPassCounts returns correct per-pass breakdown

- **WHEN** `Ft8LibInterop.DecodeAll` is called and then `GetLastPassCounts(2)` is called on the same thread
- **THEN** `GetLastPassCounts` SHALL return an array of length 2 whose sum equals the total number of decoded messages returned by `DecodeAll`

#### Scenario: GetLastPassCounts returns zeros for a silent buffer

- **WHEN** `Ft8LibInterop.DecodeAll` is called with a silent buffer (0 decodes) and then `GetLastPassCounts(2)` is called
- **THEN** `GetLastPassCounts` SHALL return `[0, 0]`
