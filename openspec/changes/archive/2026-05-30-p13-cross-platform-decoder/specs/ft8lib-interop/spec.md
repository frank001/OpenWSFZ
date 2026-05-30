## MODIFIED Requirements

### Requirement: Single decode entry point via P/Invoke on all three platforms

The `Ft8LibInterop` class in `OpenWSFZ.Ft8` SHALL expose a single managed method `DecodeAll(float[] pcm)` that calls the native `ft8_decode_all` function via P/Invoke and returns a managed array of decoded results. The native library SHALL be loaded once per process lifetime via `NativeLibrary.Load`, selecting the platform-appropriate file name:

| Platform | File name |
|---|---|
| Windows x64 | `libft8.dll` |
| Linux x64 | `libft8.so` |
| macOS ARM64 | `libft8.dylib` |

The load path SHALL be `AppContext.BaseDirectory`. A `NativeLibrary.SetDllImportResolver` SHALL be registered on the assembly before the first P/Invoke call to map the `"libft8.dll"` import token to the platform-appropriate file name. A platform-guard that returns empty on non-Windows without loading the library is a violation of this requirement.

#### Scenario: DecodeAll returns results for a real-signal buffer (Windows)

- **WHEN** `Ft8LibInterop.DecodeAll` is called on Windows with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns results for a real-signal buffer (Linux)

- **WHEN** `Ft8LibInterop.DecodeAll` is called on Linux x64 with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns results for a real-signal buffer (macOS)

- **WHEN** `Ft8LibInterop.DecodeAll` is called on macOS ARM64 with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns empty array for a silent buffer

- **WHEN** `Ft8LibInterop.DecodeAll` is called with 180 000 samples of silence
- **THEN** the method SHALL return an empty array without throwing

#### Scenario: DecodeAll raises on wrong sample count

- **WHEN** `Ft8LibInterop.DecodeAll` is called with a buffer that is not exactly 180 000 samples
- **THEN** the method SHALL throw `ArgumentException` before calling the native function

---

### Requirement: Native library binaries are committed for all three reference platforms

Pre-compiled native library binaries, built from the committed `ft8_shim.c` + `kgoba/ft8_lib` submodule at the pinned commit, SHALL be committed for all three reference platforms:

| Platform | Path | Declared in csproj |
|---|---|---|
| Windows x64  | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`     | `<Content CopyToOutputDirectory="Always" Link="libft8.dll" />`    |
| Linux x64    | `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`    | `<Content CopyToOutputDirectory="Always" Link="libft8.so" />`     |
| macOS ARM64  | `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib` | `<Content CopyToOutputDirectory="Always" Link="libft8.dylib" />`  |

A companion `libft8.version.txt` SHALL record, for each platform binary: source commit SHA, compiler toolchain and version, build date, and SNR formula. `BUILD.md` SHALL document the exact compiler commands required to reproduce each binary, including Linux (GCC ≥10) and macOS (Clang / Xcode Command Line Tools) sections.

#### Scenario: All three binaries are present in the test output directory after build

- **WHEN** `dotnet build -c Release` is run on any of the three reference platforms
- **THEN** the platform-appropriate native library file SHALL be present in `tests/OpenWSFZ.Ft8.Tests/bin/Release/net10.0/` alongside the test assembly

#### Scenario: The platform-appropriate binary is present in the daemon publish output

- **WHEN** `dotnet publish -c Release -r <rid>` is run for `OpenWSFZ.Daemon`
- **THEN** the platform-appropriate native library file SHALL be present in the publish output directory alongside the daemon executable
