## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel
function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile
time in the shim. The expected constant SHALL be **`20260009`** (H3b diagnostic: GFSK
quadrature PCM-domain SIC; version 20260008 was H3 CP-FSK scalar SIC; version 20260007 was
the reverted three-pass SIC; version 20260006 was D-002 SNR bias calibration). If the returned
value does not match the expected constant, `Ft8LibInterop` SHALL throw
`InvalidOperationException` with a message that names the library path and the mismatched
version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the
  committed shim source at `FT8_SHIM_VERSION = 20260009`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Previous library (20260008) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260008`
  (H3 diagnostic: CP-FSK scalar SIC)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call
  is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260006) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260006`
  (D-002 SNR bias calibration, pre-H3)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call
  is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260004) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260004`
  (fix-d001-revised Option B, pre-D003-diagnostics)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call
  is attempted, with a message identifying the library path and the version mismatch

---

### Requirement: Native library binaries are committed for all three reference platforms

Pre-compiled native library binaries, built from the committed `ft8_shim.c` + `kgoba/ft8_lib`
submodule at the pinned commit, SHALL be committed for all three reference platforms:

| Platform | Path | Declared in csproj |
|---|---|---|
| Windows x64 | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `<Content CopyToOutputDirectory="Always" Link="libft8.dll" />` |
| Linux x64 | `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` | `<Content CopyToOutputDirectory="Always" Link="libft8.so" />` |
| macOS ARM64 | `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib` | `<Content CopyToOutputDirectory="Always" Link="libft8.dylib" />` |

A companion `libft8.version.txt` SHALL record, for each platform binary: source commit SHA,
compiler toolchain and version, build date, SNR formula, and the pass count (**2**).
`BUILD.md` SHALL document the exact compiler commands required to reproduce each binary.
The binaries SHALL be built from the **`FT8_SHIM_VERSION = 20260009`** shim (H3b diagnostic:
GFSK quadrature PCM-domain SIC with analytic phase estimation).

#### Scenario: All three binaries are present in the test output directory after build

- **WHEN** `dotnet build -c Release` is run on any of the three reference platforms
- **THEN** the platform-appropriate native library file SHALL be present in
  `tests/OpenWSFZ.Ft8.Tests/bin/Release/net10.0/` alongside the test assembly

#### Scenario: The platform-appropriate binary is present in the daemon publish output

- **WHEN** `dotnet publish -c Release -r <rid>` is run for `OpenWSFZ.Daemon`
- **THEN** the platform-appropriate native library file SHALL be present in the publish output
  directory alongside the daemon executable
