## Why

The `ft8-decoder` spec already mandates *iterative signal subtraction* as a named component of the SHALL decode cycle (line 10: "…including all time-domain analysis, sync candidate detection, LDPC decode, **iterative signal subtraction**, and message unpacking…"), yet the current implementation performs only a single decode pass. The result is a 33.4% recovery gap against WSJT-X on the 42-cycle corpus (591 / 887 matched). WSJT-X recovers those 296 extra signals by stripping decoded transmissions from the spectrogram and re-decoding the residual; we do not. The change closes a SHALL compliance violation and satisfies RECOVERY_PLAN.md §7 Phase 2A exit criteria.

## What Changes

- **`src/OpenWSFZ.Ft8/Native/ft8_shim.c`** — add a second decode pass: after the first pass decodes all candidates, suppress each decoded signal's waterfall tiles (all 8 tone bins × 79 symbols × all time/freq over-sampling sub-bins) to the noise-floor median value, then re-run `ftx_find_candidates` and `ftx_decode_candidate` on the residual waterfall. Deduplicate across passes using the existing message hash table. Controlled by named constant `K_MAX_PASSES 2`.
- **`src/OpenWSFZ.Ft8/Native/ft8_shim.h`** — bump `FT8_SHIM_VERSION` to `20260001`. Add declaration for `ft8_get_last_pass_counts()`.
- **`src/OpenWSFZ.Ft8/Native/ft8_shim.c`** — add `ft8_get_last_pass_counts(int* out_counts, int capacity)` exported function. Uses thread-local storage to return per-pass new-decode counts from the most recent call on this thread.
- **`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`** — update `ExpectedShimVersion`, add P/Invoke for `ft8_get_last_pass_counts`.
- **`src/OpenWSFZ.Ft8/Ft8Decoder.cs`** — after `DecodeAll`, call `ft8_get_last_pass_counts` and log per-pass stats at Debug level per AC-IS-4.
- **`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`** — rebuilt from modified shim; MSVC from `native/ft8_lib` on `msvc-compat` branch.
- **`src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so`** — rebuilt (via WSL2 GCC or CI).
- **`src/OpenWSFZ.Ft8/Native/osx-arm64/libft8.dylib`** — rebuilt (via GitHub Actions workflow_dispatch or CI matrix).
- **`tests/OpenWSFZ.Ft8.Tests/Fixtures/*.expected.txt`** — expand answer keys to include medium-SNR signals (≥ 0 dB) newly recovered by the second pass (QA-reviewed, per AC-IS-2).
- **`openspec/changes/p10-decoder-ground-truth/findings.md`** — regenerated with post-implementation replay-harness measurement.
- **`RECOVERY_PLAN.md`** — Phase 2A exit criteria recorded as satisfied.
- **`src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`** — updated with new build provenance.
- **`src/OpenWSFZ.Ft8/Native/BUILD.md`** — updated build commands to reference `msvc-compat` branch of the submodule.

## Capabilities

### New Capabilities
- `iterative-subtraction`: Second-pass spectrogram-domain residual decode in the ft8 native shim. Covers: the waterfall tile suppression algorithm, the iteration termination condition (`K_MAX_PASSES`), the per-pass stats reporting mechanism (`ft8_get_last_pass_counts`), and the C# logging contract (Debug-level per-pass count messages in `Ft8Decoder`).

### Modified Capabilities
- `ft8lib-interop`: ABI version bump (`FT8_SHIM_VERSION` → `20260001`); new exported function `ft8_get_last_pass_counts`; `ExpectedShimVersion` constant update in managed code; P/Invoke binding for the new function.
- `ft8-decoder`: Recovery rate requirement is now operationally enforced; the implicit "iterative subtraction" clause in the timing requirement is implemented. Answer-key subsets expanded to medium-SNR signals; G6 gate must remain green on all three platforms with expanded keys.

## Impact

- **Native shim** (`ft8_shim.c`) — algorithm change; second decode pass adds wall-clock time. Expected to remain within the 13 s / 30 s CI budget given first-pass baseline of ~2–3 s.
- **ABI boundary** — `FT8_SHIM_VERSION` bumped; both managed and native sides must be updated together. Any stale binary will fail the ABI self-test on startup.
- **CI matrix** — all three platform binaries must be rebuilt and committed; CI G6 gate must pass with expanded answer keys on all three legs.
- **No new runtime dependencies** — the second pass uses the same ft8_lib functions already called in the first pass; no new library, no new P/Invoke entry point for the decode function itself.
- **`RECOVERY_PLAN.md`** — Phase 2A formally closed by this change.
