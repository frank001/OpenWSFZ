## ADDED Requirements

### Requirement: ft8_set_decode_params native entry point (shim 20260030)

The native shim SHALL expose a new function `ft8_set_decode_params(int k_min_score_pass2, float osd_corr_threshold, int osd_nhard_max)` that writes three module-level `static` variables read by `ft8_decode_all` on every invocation. The function SHALL be callable from any thread (module-level statics, not TLS). The three variables SHALL be initialised at compilation time to the D-009 calibrated defaults (`K_MIN_SCORE_PASS2 = 10`, `OSD_CORR_THRESHOLD = 0.10f`, `OSD_NHARD_MAX = 60`), so that the shim behaves identically to v20260029 if `ft8_set_decode_params` is never called.

The shim version constant `FT8_SHIM_VERSION` SHALL be advanced to `20260030`. All three platform binaries (Windows x64, Linux x64, macOS ARM64) SHALL be rebuilt from this shim version and committed.

#### Scenario: ft8_set_decode_params is exported by all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_set_decode_params` SHALL be resolvable via the `DllImport` / `NativeLibrary` mechanism on Windows, Linux, and macOS without error

#### Scenario: Updated parameters are used on the next decode call

- **WHEN** `ft8_set_decode_params(5, 0.20f, 50)` is called and then `ft8_decode_all` is invoked
- **THEN** the native shim SHALL use `K_MIN_SCORE_PASS2 = 5`, `OSD_CORR_THRESHOLD = 0.20f`, and `OSD_NHARD_MAX = 50` for that decode cycle

#### Scenario: Default parameter values match shim 20260029 behaviour

- **WHEN** `ft8_set_decode_params` is never called
- **THEN** `ft8_decode_all` SHALL behave identically to shim v20260029: `K_MIN_SCORE_PASS2 = 10`, `OSD_CORR_THRESHOLD = 0.10f`, `OSD_NHARD_MAX = 60`

---

### Requirement: SetDecodeParams P/Invoke and IFt8NativeInterop method

`Ft8LibInterop` SHALL expose a `public static void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax)` method that calls `EnsureInitialized()` and then invokes the native `ft8_set_decode_params` function via P/Invoke. `IFt8NativeInterop` SHALL add a corresponding `void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax)` method so that unit tests can supply a `FakeInterop` implementation that records the call without loading the native DLL.

#### Scenario: SetDecodeParams calls EnsureInitialized before P/Invoke

- **WHEN** `Ft8LibInterop.SetDecodeParams` is called before any `DecodeAll` invocation (native library not yet loaded)
- **THEN** the native library SHALL be loaded and the ABI version check SHALL pass before the `ft8_set_decode_params` function is called

#### Scenario: IFt8NativeInterop.SetDecodeParams is callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that records `SetDecodeParams` calls
- **THEN** calling `SetDecodeParams(8, 0.12f, 55)` on the fake SHALL record the arguments without loading the native DLL

---

## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. The expected constant SHALL be **`20260030`** (decoder-settings-page: runtime-configurable OSD gate parameters via `ft8_set_decode_params`; no change to decode logic, struct layout, or existing entry points; version history: 20260029 = D-009 K_MIN_SCORE_PASS2 raised 1→10, 20260028 = D-009 OSD nhard gate, 20260025 = OSD fallback + 50-iter BP, 20260021 = H6 AP decode hiscall offset fix). If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at `FT8_SHIM_VERSION = 20260030`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Previous library (20260029) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260029` (D-009 K=10)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Previous library (20260016) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260016` (fix-d006-cleanup)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

---

### Requirement: Native library binaries are committed for all three reference platforms

Pre-compiled native library binaries, built from the committed `ft8_shim.c` + `kgoba/ft8_lib` submodule at the pinned commit, SHALL be committed for all three reference platforms:

| Platform | Path | Declared in csproj |
|---|---|---|
| Windows x64 | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `<Content CopyToOutputDirectory="Always" Link="libft8.dll" />` |
| Linux x64 | `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` | `<Content CopyToOutputDirectory="Always" Link="libft8.so" />` |
| macOS ARM64 | `src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib` | `<Content CopyToOutputDirectory="Always" Link="libft8.dylib" />` |

A companion `libft8.version.txt` SHALL record, for each platform binary: source commit SHA, compiler toolchain and version, build date, SNR formula, and the pass count (**2**). `BUILD.md` SHALL document the exact compiler commands required to reproduce each binary. The binaries SHALL be built from the **`FT8_SHIM_VERSION = 20260030`** shim (decoder-settings-page: `ft8_set_decode_params` entry point for runtime-configurable OSD gate parameters).

#### Scenario: All three binaries are present in the test output directory after build

- **WHEN** `dotnet build -c Release` is run on any of the three reference platforms
- **THEN** the platform-appropriate native library file SHALL be present in `tests/OpenWSFZ.Ft8.Tests/bin/Release/net10.0/` alongside the test assembly

#### Scenario: The platform-appropriate binary is present in the daemon publish output

- **WHEN** `dotnet publish -c Release -r <rid>` is run for `OpenWSFZ.Daemon`
- **THEN** the platform-appropriate native library file SHALL be present in the publish output directory alongside the daemon executable
