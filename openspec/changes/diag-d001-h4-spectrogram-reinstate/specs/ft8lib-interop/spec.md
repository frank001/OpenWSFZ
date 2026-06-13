## MODIFIED Requirements

### Requirement: ABI version sentinel matches committed shim

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. The expected constant SHALL be **`20260010`** (diag-d001-h4-spectrogram-reinstate: spectrogram-domain soft-SNR suppression reinstated; H3b PCM-domain GFSK quadrature SIC call site removed; GFSK helpers retained but not called; D-003 TLS diagnostic retained; builds on 20260009 H3b diagnostic, rejected). If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Version check passes with shim 20260010 binaries

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at `FT8_SHIM_VERSION = 20260010`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Stale H3b binary (20260009) is rejected

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260009` (H3b GFSK quadrature SIC, rejected)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Baseline binary (20260006) is rejected

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260006` (D-002 SNR calibration, spectrogram suppression)
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch
