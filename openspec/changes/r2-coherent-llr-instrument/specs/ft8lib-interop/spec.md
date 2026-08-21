## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. **Phase 1 of this change shipped `ft8_coherent_llr_at` at `FT8_SHIM_VERSION = 20260043`** (r0-reproducible-native-build lineage through `n1-extract-llrs-at-position`'s `ft8_extract_llrs_at` diagnostic export at `20260042`). **Phase B of this change (the B1 origin-correction fix, the B2 fusion-normalisation fix, and Amendment 1's B4 `ft8_ldpc_decode_llrs` diagnostic export) SHALL advance the expected constant to `20260044`**, asserted mechanically unused across all other branches before adoption (the board records two prior collisions across five unmerged `d001-*` branches) rather than inferred from being the next integer. No existing production entry point's ABI, struct layout, or decode behaviour SHALL change at either bump; `DecodeAll`, `GetLastPassCounts`, `SetDecodeParams`, and every other existing exported symbol all remain byte-for-byte unchanged. If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test (Phase B, once shipped)

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at Phase B's own `FT8_SHIM_VERSION = 20260044`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Pre-Phase-B library (20260043) fails fast with a clear error, once Phase B ships

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260043` (Phase 1, the pin every ROW 0g/B-pos-A/B-orig-A harness ran against before Phase B) after Phase B's managed code expects its own newer constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

## ADDED Requirements

### Requirement: Diagnostic coherent-LLR P/Invoke entry point (Phase 1 — shipped 2026-08-21, shim `20260043`; underlying native behaviour corrected under Phase B, shim `20260044`, no signature change)

`Ft8LibInterop` SHALL expose a managed method (e.g. `CoherentLlrAt`) that calls the native `ft8_coherent_llr_at` function via P/Invoke, taking the cycle's PCM buffer and a candidate's *existing, unrefined* grid `(freq_idx, time_idx)` and returning 174 coherent LLRs. `IFt8NativeInterop` SHALL add a corresponding method so that unit tests can supply a `FakeInterop` implementation that records the call without loading the native DLL, matching the existing pattern used for `RefineCandidate` and `ExtractLlrsAt`. This method SHALL be reachable only from test code and the Phase 1 gate harness (the extension of this change's own `r2_ber_grid.py`) — no production call site in `OpenWSFZ.Daemon` or `OpenWSFZ.Ft8`'s decode path SHALL invoke it, and it SHALL NOT itself call `RefineCandidate`/`ft8_refine_candidate` (design.md D1). **Phase B changes the values this method's underlying native call returns (design.md D8/D9's origin and fusion corrections) but not this method's signature, its `IFt8NativeInterop` surface, or any of the scenarios below.**

#### Scenario: CoherentLlrAt is exported by all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_coherent_llr_at` SHALL be resolvable via the `DllImport` / `NativeLibrary` mechanism on Windows, Linux, and macOS without error

#### Scenario: CoherentLlrAt returns 174 LLRs for a known-truth signal at its existing grid position

- **WHEN** `Ft8LibInterop.CoherentLlrAt` is called with a PCM buffer and the existing grid `(freq_idx, time_idx)` for a known candidate — no refinement step involved
- **THEN** the method SHALL return 174 coherent LLRs without throwing, and without any internal call to `RefineCandidate`

#### Scenario: IFt8NativeInterop.CoherentLlrAt is callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that records `CoherentLlrAt` calls
- **THEN** calling it with a representative PCM buffer and grid position SHALL record the arguments without loading the native DLL

#### Scenario: No production call site invokes CoherentLlrAt

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable from `DecodeAll`) is inspected after Phase 1 lands
- **THEN** it SHALL contain no call to `CoherentLlrAt` or `ft8_coherent_llr_at` outside of test code and the Phase 1 gate harness

---

### Requirement: Diagnostic LDPC-decode-from-LLRs native export (Phase B, Amendment 1 — not yet implemented)

The shim SHALL export a native function, `ft8_ldpc_decode_llrs(llr174, max_iters, osd_depth, out_a91, out_ldpc_errors, out_path, out_crc_ok)`, that decodes a caller-supplied 174-element raw (pre-normalisation) LLR vector through production's own decode sequence and reports whether it yields a CRC-valid message, so that a diagnostic LLR vector (from `ft8_extract_llrs_at` or `ft8_coherent_llr_at`) can be converted into a CRC-verified decode count rather than a modelled BER-threshold crossing. It SHALL, in order: (1) copy the caller's vector into a local buffer, and SHALL NOT modify the caller's own buffer, since `bp_decode` writes through its argument; (2) apply the same zero-variance degenerate guard `ftx_normalize_logl` itself requires, returning a negative code without normalising if the guard trips; (3) apply `ftx_normalize_logl` to the copy — mandatory, since without this step the export would measure LLR scale rather than LLR quality and any comparison between two differently-scaled extractions would be void; (4) save the normalised vector for the OSD fallback, exactly as the production sequence does; (5) run `bp_decode`; (6) pack to a 91-bit payload+CRC and compare the extracted and computed CRC-14; (7) if and only if the CRC fails and `osd_depth >= 0`, run the OSD fallback exactly as production does (including its existing two-feature accept/reject gate) and re-check the CRC, reporting via `out_path` which of BP or OSD produced the accepted result, or that neither did. The function SHALL NOT un-`static` `ftx_normalize_logl` or `osd_decode`, SHALL NOT move `osd_decode`, and SHALL NOT duplicate the CRC or normalisation arithmetic anywhere outside `decode.c` — it SHALL call the existing `static` functions from within `decode.c`, with only a thin wrapper in `ft8_shim.c`, the same two-file pattern `ftx_extract_likelihood_at`/`ft8_extract_llrs_at` already established. It SHALL be reachable only from test code and QA harnesses invoking it directly via the platform's native-library loading mechanism (e.g. Python `ctypes`) — no production call site in `OpenWSFZ.Daemon` or `OpenWSFZ.Ft8`'s decode path SHALL invoke it, and no managed `Ft8LibInterop`/`IFt8NativeInterop` surface is required for it (design.md D10, following `n1-extract-llrs-at-position`'s own precedent for a diagnostic-only, test/harness-only export).

#### Scenario: Export is present in all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_ldpc_decode_llrs` SHALL be resolvable via the platform's native-library loading mechanism on Windows, Linux, and macOS without error

#### Scenario: A known-good codeword decodes cleanly (B4-a, positive control)

- **WHEN** `ft8_ldpc_decode_llrs` is called with the exact codeword LLRs (`+1`/`-1` scaled, no noise) for a known encoded message
- **THEN** `out_crc_ok` SHALL be `1` and the recovered `out_a91` payload SHALL match the encoded message bit-for-bit

#### Scenario: Pure Gaussian noise never decodes (B4-b, negative control)

- **WHEN** `ft8_ldpc_decode_llrs` is called with pure Gaussian-noise LLRs, fixed seed, across 20 independent trials
- **THEN** `out_crc_ok` SHALL be `0` on all 20 trials — a probe that reports success on noise reports success on anything, so this bar is load-bearing, not advisory

#### Scenario: The caller's LLR buffer is never modified (B4-c)

- **WHEN** `ft8_ldpc_decode_llrs` is called and returns
- **THEN** the caller's `llr174` buffer SHALL be byte-identical to its value immediately before the call, since `bp_decode` writes through its argument and this export copies before calling it

#### Scenario: A zero-variance input is rejected, not crashed on (B4-d)

- **WHEN** `ft8_ldpc_decode_llrs` is called with an `llr174` vector of zero variance
- **THEN** it SHALL return a negative code, SHALL NOT call `ftx_normalize_logl` (which would divide by zero), and SHALL NOT crash or produce NaN output

#### Scenario: Agreement with the production decoder on real audio meets the floor (B4-e, the only scenario with known ground truth)

- **WHEN** `ft8_ldpc_decode_llrs` is fed the `ft8_extract_llrs_at` output, at the grid candidate's own position, for rows that `ft8_decode_all` itself decoded live on real audio
- **THEN** `out_crc_ok == 1` SHALL hold for at least 90% of those rows, and the recovered message text SHALL match production's own decode for every row where it does — this bar is a floor (production searches candidates; this export is handed one position, so 100% agreement is not expected), and a result below the floor SHALL be reported as a stop condition, not averaged away

#### Scenario: No production call site invokes the export

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable from `DecodeAll`) is inspected after this change lands
- **THEN** it SHALL contain no call to `ft8_ldpc_decode_llrs` outside of test code and QA harnesses

#### Scenario: Existing exports and decode paths are unaffected

- **WHEN** the new binary's exported symbol table is compared against the prior `20260043` build, and `decode.c`'s existing functions are diffed against their pre-change source
- **THEN** every previously-exported symbol SHALL be present with an unchanged signature, `ft8_ldpc_decode_llrs` SHALL be the only new export this Requirement adds, and the diff on every existing `decode.c` function SHALL be zero
