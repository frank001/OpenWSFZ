# ft8lib-interop Specification

## Purpose
Specifies the P/Invoke binding layer between managed C# code and the `kgoba/ft8_lib` native decode library. This layer is implemented in `OpenWSFZ.Ft8/Interop/` and was introduced in p12. The ft8-decoder spec depends on this capability for its decode implementation.

Per **NFR-001**, the library SHALL function on all three reference platforms: Windows x64, Linux x64, and macOS x64.

## Requirements

### Requirement: Single decode entry point via P/Invoke on all three platforms

The `Ft8LibInterop` class in `OpenWSFZ.Ft8` SHALL expose a single managed method `DecodeAll(float[] pcm)` that calls the native `ft8_decode_all` function via P/Invoke and returns a managed array of decoded results. The native library SHALL be loaded once per process lifetime via `NativeLibrary.Load`, selecting the platform-appropriate file name:

| Platform | File name |
|---|---|
| Windows x64 | `libft8.dll` |
| Linux x64 | `libft8.so` |
| macOS x64 | `libft8.dylib` |

The load path SHALL be `AppContext.BaseDirectory`. A platform-guard that returns empty on non-Windows without loading the library is a violation of this requirement.

#### Scenario: DecodeAll returns results for a real-signal buffer (Windows)

- **WHEN** `Ft8LibInterop.DecodeAll` is called on Windows with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns results for a real-signal buffer (Linux)

- **WHEN** `Ft8LibInterop.DecodeAll` is called on Linux x64 with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns results for a real-signal buffer (macOS)

- **WHEN** `Ft8LibInterop.DecodeAll` is called on macOS x64 with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns empty array for a silent buffer

- **WHEN** `Ft8LibInterop.DecodeAll` is called with 180 000 samples of silence
- **THEN** the method SHALL return an empty array without throwing

#### Scenario: DecodeAll raises on wrong sample count

- **WHEN** `Ft8LibInterop.DecodeAll` is called with a buffer that is not exactly 180 000 samples
- **THEN** the method SHALL throw `ArgumentException` before calling the native function

---

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Wrong library fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary that returns an unexpected version constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

---

### Requirement: Native result struct is layout-compatible with the C shim

The `Ft8NativeResult` struct in managed code SHALL be decorated with `[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]` and SHALL declare fields matching the C `FT8Result` struct in the shim: `int FreqHz`, `float Dt`, `int Snr`, and a fixed-length `char[36]` message buffer. The managed struct size SHALL equal the C struct size (48 bytes, verifiable via `Marshal.SizeOf`). This layout constraint applies identically on all three reference platforms — the C shim MUST be compiled with identical struct packing on each.

#### Scenario: Struct size matches between managed and native

- **WHEN** `Marshal.SizeOf<Ft8NativeResult>()` is called
- **THEN** the returned size SHALL equal the value of `sizeof(FT8Result)` as compiled into the shim (48 bytes, documented in `Ft8LibInterop.cs` as a compile-time constant)

---

### Requirement: Native library binaries are committed for all three reference platforms

Pre-compiled native library binaries, built from the committed `ft8_shim.c` + `kgoba/ft8_lib` submodule at the pinned commit, SHALL be committed for all three reference platforms:

| Platform | Path | Declared in csproj |
|---|---|---|
| Windows x64 | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `<Content CopyToOutputDirectory="Always" Link="libft8.dll" />` |
| Linux x64 | `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` | `<Content CopyToOutputDirectory="Always" Link="libft8.so" />` |
| macOS x64 | `src/OpenWSFZ.Ft8/Native/osx-x64/libft8.dylib` | `<Content CopyToOutputDirectory="Always" Link="libft8.dylib" />` |

A companion `libft8.version.txt` SHALL record, for each platform binary: source commit SHA, compiler toolchain and version, build date, and SNR formula. `BUILD.md` SHALL document the exact compiler commands required to reproduce each binary.

#### Scenario: All three binaries are present in the test output directory after build

- **WHEN** `dotnet build -c Release` is run on any of the three reference platforms
- **THEN** the platform-appropriate native library file SHALL be present in `tests/OpenWSFZ.Ft8.Tests/bin/Release/net10.0/` alongside the test assembly

#### Scenario: The platform-appropriate binary is present in the daemon publish output

- **WHEN** `dotnet publish -c Release -r <rid>` is run for `OpenWSFZ.Daemon`
- **THEN** the platform-appropriate native library file SHALL be present in the publish output directory alongside the daemon executable
