## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. The expected constant SHALL be `20260003` (updated from `20260002` to reflect the ABI change introduced by the three-pass PCM-domain SIC decode structure). If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at `FT8_SHIM_VERSION = 20260003`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Pre-SIC library fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260002` (pre PCM-SIC)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

---

### Requirement: Per-pass decode counts are accessible from managed code

`Ft8LibInterop` SHALL expose a method `GetLastPassCounts(int maxPasses)` that calls the native `ft8_get_last_pass_counts` function via P/Invoke and returns a managed `int[]` of length equal to the number of passes actually executed (now 3). The managed constant `MaxDecodePasses` SHALL be 3.

#### Scenario: GetLastPassCounts returns correct three-pass breakdown

- **WHEN** `Ft8LibInterop.DecodeAll` is called and then `GetLastPassCounts(3)` is called on the same thread
- **THEN** `GetLastPassCounts` SHALL return an array of length 3 whose sum equals the total number of decoded messages returned by `DecodeAll`

#### Scenario: GetLastPassCounts returns zeros for a silent buffer

- **WHEN** `Ft8LibInterop.DecodeAll` is called with a silent buffer (0 decodes) and then `GetLastPassCounts(3)` is called
- **THEN** `GetLastPassCounts` SHALL return `[0, 0, 0]`

---

### Requirement: Result buffer is sized for three-pass output capacity

The `MaxResults` constant in `Ft8LibInterop` SHALL be set to 480, sized to the three-pass output capacity: `K_MAX_CANDIDATES` (pass 0, 140) + `K_MAX_CANDIDATES_PASS2` (pass 1, 200) + `K_MAX_CANDIDATES` (pass 2, 140). The native `ft8_decode_all` call SHALL pass this value as `max_results`.

#### Scenario: Result buffer accommodates signals from all three passes

- **WHEN** `Ft8LibInterop.DecodeAll` is called on a buffer where each of the three passes produces decodes
- **THEN** all decoded messages SHALL be returned without truncation up to the 480-message capacity

---

### Requirement: Native library binaries are committed for all three reference platforms

Pre-compiled native library binaries, built from the committed `ft8_shim.c` + `kgoba/ft8_lib` submodule at the pinned commit, SHALL be committed for all three reference platforms. The binaries SHALL be built from the `FT8_SHIM_VERSION = 20260003` shim that implements three-pass PCM-domain SIC. `libft8.version.txt` SHALL record, for each platform binary: source commit SHA, compiler toolchain and version, build date, SNR formula, and the new pass count (3).

#### Scenario: All three binaries are present in the test output directory after build

- **WHEN** `dotnet build -c Release` is run on any of the three reference platforms
- **THEN** the platform-appropriate native library file at `FT8_SHIM_VERSION = 20260003` SHALL be present in the test output directory

#### Scenario: The platform-appropriate binary is present in the daemon publish output

- **WHEN** `dotnet publish -c Release -r <rid>` is run for `OpenWSFZ.Daemon`
- **THEN** the platform-appropriate native library file at `FT8_SHIM_VERSION = 20260003` SHALL be present in the publish output directory
