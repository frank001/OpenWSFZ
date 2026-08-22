## MODIFIED Requirements

### Requirement: ABI self-test on first load

On the first call that triggers `NativeLibrary.Load`, `Ft8LibInterop` SHALL invoke a sentinel function (`ft8_lib_version_check`) that returns a known integer constant embedded at compile time in the shim. **Phase 1 of this change shipped `ft8_coherent_llr_at` at `FT8_SHIM_VERSION = 20260043`** (r0-reproducible-native-build lineage through `n1-extract-llrs-at-position`'s `ft8_extract_llrs_at` diagnostic export at `20260042`). **Phase B of this change (the B1 origin-correction fix, the B2 fusion-normalisation fix, and Amendment 1's B4 `ft8_ldpc_decode_llrs` diagnostic export) advanced the expected constant to `20260044`, shipped** (`feat/r2-coherent-llr-phase-b`, commit `7ed8b0c`). **Amendment 2, as corrected by Amendment 3 (the `ft8_get_last_snr_terms` diagnostic export, conditional on arm B-dt-A's ROW 2 firing — it fired) SHALL advance the expected constant again, `20260044` → `20260045`**, asserted mechanically unused across all other branches before adoption (the board records two prior collisions across five unmerged `d001-*` branches) rather than inferred from being the next integer. No existing production entry point's ABI, struct layout, or decode behaviour SHALL change at any bump; `DecodeAll`, `GetLastPassCounts`, `SetDecodeParams`, and every other existing exported symbol all remain byte-for-byte unchanged. If the returned value does not match the expected constant, `Ft8LibInterop` SHALL throw `InvalidOperationException` with a message that names the library path and the mismatched version values. This requirement applies on all three reference platforms.

#### Scenario: Correct library passes the ABI self-test (Phase B, shipped)

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at Phase B's own `FT8_SHIM_VERSION = 20260044`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Pre-Phase-B library (20260043) fails fast with a clear error

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260043` (Phase 1, the pin every ROW 0g/B-pos-A/B-orig-A harness ran against before Phase B) after Phase B's managed code expects its own newer constant
- **THEN** `Ft8LibInterop` SHALL throw `InvalidOperationException` before any decode call is attempted, with a message identifying the library path and the version mismatch

#### Scenario: Correct library passes the ABI self-test (Amendment 2/3, once shipped)

- **WHEN** `Ft8LibInterop` loads the platform-appropriate `libft8` binary compiled from the committed shim source at Amendment 2/3's own `FT8_SHIM_VERSION = 20260045`
- **THEN** the version check SHALL pass silently and decode calls SHALL proceed normally

#### Scenario: Pre-Amendment-2 library (20260044) fails fast with a clear error, once Amendment 2/3 ships

- **WHEN** `Ft8LibInterop` loads a `libft8` binary compiled at version `20260044` (Phase B, the pin arm B-dt-A ran against) after Amendment 2/3's managed code expects its own newer constant
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

---

### Requirement: Diagnostic SNR-terms native export and P/Invoke entry point (Amendment 2, corrected in full by Amendment 3 — not yet implemented, conditional on arm B-dt-A's ROW 2, which fired)

The shim SHALL export a native function, `ft8_get_last_snr_terms(out_signal_db, out_local_noise_db, capacity)`, that returns the two per-decode terms of the SNR formula `snr = signal_db - local_noise_db - 26.5f` (`ft8_shim.c:1473-1474`) for every decode returned by the most recent `ft8_decode_all` call on the calling thread, so that a measured collapse in reported SNR (mean reported-minus-true SNR of `-11.9..-14.6 dB` on affected decodes, stable `+0.5..+1.0 dB` on WSJT-X across the same audio) can be localised to one of its two otherwise-unobservable terms rather than remaining an assertion. `out_signal_db[i]`/`out_local_noise_db[i]` SHALL correspond to `results[i]` from that same `ft8_decode_all` call — index-aligned, same order, same count. Either output pointer MAY be `NULL` to request only the other array; if both are `NULL`, the function SHALL write nothing and SHALL return the count it would have written. The function SHALL return `-1` if `capacity < 0`. The export SHALL be read-only: it SHALL NOT alter control flow, ordering, or any value already computed for `FT8Result` — it exposes the `signal_db`/`local_noise_db` locals already computed at `ft8_shim.c:1450-1474`, it does not add a second, independent computation of them. `Ft8LibInterop` SHALL expose a corresponding managed method (e.g. `GetLastSnrTerms`) via P/Invoke, matching the existing `GetLastCandidateCounts`/`GetLastLlrStats` parallel-array diagnostic-getter pattern (unlike `ft8_ldpc_decode_llrs`, which per design.md D10 gets no C# binding — this export does, per the amendment's own §4). `IFt8NativeInterop` SHALL add a corresponding method so a `FakeInterop` implementation can record the call without loading the native DLL, matching the existing pattern for `GetLastCandidateCounts`/`GetLastLlrStats`/`CoherentLlrAt`.

#### Scenario: Export is present in all three platform binaries

- **WHEN** the platform-appropriate `libft8` binary is loaded
- **THEN** the symbol `ft8_get_last_snr_terms` SHALL be resolvable via the `DllImport`/`NativeLibrary` mechanism on Windows, Linux, and macOS without error

#### Scenario: Arrays are index-aligned with the decode results from the same call (AC-N3)

- **WHEN** `ft8_get_last_snr_terms` is called immediately after an `ft8_decode_all` call that returned `n` decodes, with `capacity >= n`
- **THEN** the function SHALL return exactly `n`, and `out_signal_db[i]`/`out_local_noise_db[i]` SHALL correspond to `results[i]` for every `i` in `[0, n)`

#### Scenario: The two terms reconstruct the reported SNR within the int-rounding quantum (AC-N2)

- **WHEN** `ft8_get_last_snr_terms` is called after a decode and its two arrays are compared against the corresponding `FT8Result.snr` value
- **THEN** `abs((signal_db[i] - local_noise_db[i] - 26.5) - snr[i])` SHALL be `<= 0.5 + 1e-3` for every decode `i` — the `+1e-3` is a float-representation allowance for the `(int)roundf` quantum, not a loosening of the criterion (resolved against the readout quantum, HK-021(o))

#### Scenario: Capacity is honoured exactly, including the both-NULL and negative-capacity cases (AC-N4)

- **WHEN** `ft8_get_last_snr_terms` is called with `capacity` values of `0`, `1`, and `count-1` (on a cycle with `count >= 3`, since `count-1` is degenerate below that), with both pointers non-`NULL`, with one pointer `NULL`, with both pointers `NULL`, and with a negative `capacity`
- **THEN** the function SHALL write exactly `capacity` entries and return `capacity` for each non-negative case with no overrun; SHALL write nothing and return the count it would have written when both output pointers are `NULL`; and SHALL return `-1` without writing anything when `capacity < 0`

#### Scenario: The export is read-only and changes no decode-path value (AC-N1)

- **WHEN** a binary built with this export is replayed against the same audio as the pre-Amendment-2 archived Phase B binary (`a3d32b78...` win / `13d9799d...` linux, or the equivalent committed working-tree binary, `7ed8b0c`), for at least 200 contiguous cycles on every platform rebuilt
- **THEN** every decode-output field SHALL be byte-for-byte identical between the two binaries — zero differences — since this export only reads values `ft8_decode_all` already computed and writes them to TLS storage, it does not participate in decode control flow

#### Scenario: No production call site invokes the export

- **WHEN** the `OpenWSFZ.Daemon` and `OpenWSFZ.Ft8` production decode path (everything reachable from `DecodeAll`) is inspected after this Amendment lands
- **THEN** it SHALL contain no call to `GetLastSnrTerms`/`ft8_get_last_snr_terms` outside of test code and QA harnesses

#### Scenario: `IFt8NativeInterop.GetLastSnrTerms` is callable on a fake implementation

- **WHEN** a test supplies an `IFt8NativeInterop` implementation that records `GetLastSnrTerms` calls
- **THEN** calling it with a representative `maxDecoded` value SHALL record the call and return a deterministic fake result without loading the native DLL

#### Scenario: Existing exports and decode paths are unaffected

- **WHEN** the new binary's exported symbol table is compared against the prior `20260044` build, and `ft8_shim.c`'s existing decode-path logic (beyond the two-line TLS write this export adds) is diffed against its pre-change source
- **THEN** every previously-exported symbol (all fifteen) SHALL be present with an unchanged signature, `ft8_get_last_snr_terms` SHALL be the only new export this Requirement adds, and the diff on every existing decode-path computation SHALL be zero
