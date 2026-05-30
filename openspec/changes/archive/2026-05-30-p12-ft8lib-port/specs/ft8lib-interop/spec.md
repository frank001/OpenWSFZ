## ADDED Requirements

### Requirement: Single decode entry point via P/Invoke

The `Ft8LibInterop` class in `OpenWSFZ.Ft8` SHALL expose a single managed method `DecodeAll(float[] pcm)` that calls the native `ft8_decode_all` function via P/Invoke and returns a managed array of decoded results. The native library SHALL be loaded once per process lifetime via `NativeLibrary.Load` at the path `libft8.dll` relative to `AppContext.BaseDirectory`.

#### Scenario: DecodeAll returns results for a real-signal buffer

- **WHEN** `Ft8LibInterop.DecodeAll` is called with a 180 000-sample PCM buffer containing real FT8 transmissions
- **THEN** the method SHALL return one or more `Ft8NativeResult` structs whose `Message` fields match known WSJT-X decodes for that buffer

#### Scenario: DecodeAll returns empty array for a silent buffer

- **WHEN** `Ft8LibInterop.DecodeAll` is called with 180 000 samples of silence
- **THEN** the method SHALL return an empty array without throwing

#### Scenario: DecodeAll raises on wrong sample count

- **WHEN** `Ft8LibInterop.DecodeAll` is called with a buffer that is not exactly 180 000 samples
- **THEN** the method SHALL throw `ArgumentException` before calling the native function

---

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the DLL path and the mismatched version values.

#### Scenario: Correct DLL passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads `libft8.dll` compiled from the committed shim source
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Wrong DLL fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8.dll` that returns an unexpected version constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the DLL path and the version mismatch

---

### Requirement: Native result struct is layout-compatible with the C shim

The `Ft8NativeResult` struct in managed code SHALL be decorated with `[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]` and SHALL declare fields matching the C `FT8Result` struct in the shim: `int FreqHz`, `float Dt`, `int Snr`, and a fixed-length `char[32]` message buffer. The managed struct size SHALL equal the C struct size (verifiable via `Marshal.SizeOf`).

#### Scenario: Struct size matches between managed and native

- **WHEN** `Marshal.SizeOf<Ft8NativeResult>()` is called
- **THEN** the returned size SHALL equal the value of `sizeof(FT8Result)` as compiled into the shim (documented in `Ft8LibInterop.cs` as a compile-time constant)

---

### Requirement: libft8.dll is committed as a content file

The pre-compiled `libft8.dll` (Windows x64, built from the `kgoba/ft8_lib` git submodule at a pinned commit) SHALL be committed at `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` and declared as `<Content CopyToOutputDirectory="Always"/>` in `OpenWSFZ.Ft8.csproj`. A companion `libft8.version.txt` SHALL record the source commit SHA and the compiler toolchain used.

#### Scenario: libft8.dll is present in the test output directory after build

- **WHEN** `dotnet build -c Release` is run
- **THEN** `libft8.dll` SHALL be present in `tests/OpenWSFZ.Ft8.Tests/bin/Release/net10.0/` alongside the test assembly

#### Scenario: libft8.dll is present in the daemon publish output

- **WHEN** `dotnet publish -c Release` is run for `OpenWSFZ.Daemon`
- **THEN** `libft8.dll` SHALL be present in the publish output directory alongside `OpenWSFZ.Daemon.exe`
