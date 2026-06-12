## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel
function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile
time in the shim. The expected constant SHALL be **`20260007`** (diag-d001-three-pass-sic:
K_MAX_PASSES increased from 2 to 3 for D-001 diagnostic; builds on 20260006, which was the
D-002 SNR bandwidth constant calibration −26.0 → −26.5 dB). If the returned value does not
match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a
message that names the library path and the mismatched version values. This requirement applies
on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the
  committed shim source at `FT8_SHIM_VERSION = 20260007`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Previous library (20260006) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260006`
  (D-002 SNR bandwidth calibration, K_MAX_PASSES = 2)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is
  attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260005) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260005`
  (D-003 diagnostics, pre-D002-calibration)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is
  attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260004) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260004`
  (fix-d001-revised Option B, pre-D003-diagnostics)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is
  attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260002) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260002`
  (two-pass hard-zero suppression, pre-Option-B)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is
  attempted, with a message identifying the library path and the version mismatch

---

### Requirement: Per-pass decode counts are accessible from managed code

`Ft8LibInterop` SHALL expose a method `GetLastPassCounts(int maxPasses)` that calls the native
`ft8_get_last_pass_counts` function via P/Invoke and returns a managed `int[]` of length equal
to the number of passes actually executed (**now 3**). The managed constant `MaxDecodePasses`
SHALL be **3**.

#### Scenario: GetLastPassCounts returns correct three-pass breakdown

- **WHEN** `Ft8LibInterop.DecodeAll` is called and then `GetLastPassCounts(3)` is called on
  the same thread
- **THEN** `GetLastPassCounts` SHALL return an array of length **3** whose sum equals the total
  number of decoded messages returned by `DecodeAll`

#### Scenario: GetLastPassCounts returns zeros for a silent buffer

- **WHEN** `Ft8LibInterop.DecodeAll` is called with a silent buffer (0 decodes) and then
  `GetLastPassCounts(3)` is called
- **THEN** `GetLastPassCounts` SHALL return `[0, 0, 0]`

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
compiler toolchain and version, build date, SNR formula, and the pass count (**3**). `BUILD.md`
SHALL document the exact compiler commands required to reproduce each binary. The binaries SHALL
be built from the **`FT8_SHIM_VERSION = 20260007`** shim.

#### Scenario: All three binaries are present in the test output directory after build

- **WHEN** `dotnet build -c Release` is run on any of the three reference platforms
- **THEN** the platform-appropriate native library file SHALL be present in
  `tests/OpenWSFZ.Ft8.Tests/bin/Release/net10.0/` alongside the test assembly

#### Scenario: The platform-appropriate binary is present in the daemon publish output

- **WHEN** `dotnet publish -c Release -r <rid>` is run for `OpenWSFZ.Daemon`
- **THEN** the platform-appropriate native library file SHALL be present in the publish output
  directory alongside the daemon executable
