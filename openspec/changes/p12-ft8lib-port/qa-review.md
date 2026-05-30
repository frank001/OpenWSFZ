# p12 QA Review — Required Changes

**Reviewer:** QA Gate  
**Branch:** `feat/p12-ft8lib-port`  
**Date:** 2026-05-30  
**Status:** ✅ All required fixes resolved — approved for merge  
**Resolution commit:** `f234f8e`

FT8 decoding is confirmed working. Eight findings were raised; four required fixes are now resolved (commit `f234f8e`). Four lower-priority findings remain deferred to a follow-on change as noted below.

---

## Required fixes ~~(merge blocked)~~ → ✅ RESOLVED

### R1 — SNR formula is wrong by ~26 dB ✅ FIXED

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, line 249  
**Severity:** High — user-visible, directly causes the reported "dB all over the place" symptom

`cand->score * 0.5f` is not an SNR. It is the average dB margin of each Costas sync bin over its immediate waterfall neighbours — a sync-quality proxy. The WSJT-X SNR convention references the signal power against the noise floor integrated over a **2500 Hz bandwidth**. FT8 tone spacing is 6.25 Hz, so the missing correction is:

```
10 * log10(2500 / 6.25) ≈ 26.0 dB
```

The ft8_lib demo source itself carries the comment `// TODO: compute better approximation of SNR` at this calculation, confirming it was never intended as a finished answer.

**Resolution:** Applied the minimum fix with a full explanatory comment:
```c
float snr_f = (float)cand->score * 0.5f - 26.0f;
```
`libft8.dll` rebuilt (MSVC 19.51.36244, 2026-05-30). `BUILD.md` updated with corrected SNR row. `libft8.version.txt` updated. The per-call noise-floor estimation remains a TODO as noted in the comment.

**Acceptance criterion:** ✅ Three `RealSignalFixtureTests` pass. G6 gate green.

---

### R2 — `DecodeAsync` throws synchronously, violating the `Task`-returning method contract ✅ FIXED

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`  
**Severity:** Medium — contract violation; callers using `try/catch` around `await` will not catch the exception

`DecodeAsync` is declared as returning `Task<IReadOnlyList<DecodeResult>>` but was **not** marked `async`. `Ft8LibInterop.DecodeAll` throws `ArgumentException` synchronously when `pcm.Length != 180_000`. That exception propagated **before** any `Task` was returned.

**Resolution:** The new canonical overload `DecodeAsync(float[], DateTime, CancellationToken)` is marked `async`. The length guard using `ExpectedSampleCount` appears at the top of the method body; the async state machine captures it as a faulted `Task`. The native call is wrapped in `await Task.Run(...)`.

**Acceptance criterion:** ✅ Wrong-length buffer surfaces as a faulted `Task`. `ExpectedSampleCount` used at the validation site.

---

### R3 — Cycle-start timestamp snaps to the wrong 15-second window under load ✅ FIXED

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, `src/OpenWSFZ.Ft8/CycleFramer.cs`  
**Severity:** Medium — produces incorrect timestamps in ALL.TXT and WebSocket events when the decode queue is backed up

`_clock.UtcNow` was captured after the 15-second audio buffer was recorded. Under scheduler pressure, `AlignToCycleStart` could snap to the start of the **new** cycle — 15 seconds ahead of the actual transmission window.

**Resolution:**
- `CycleFramer.RunAsync` signature changed to `ChannelWriter<(float[] Pcm, DateTime CycleStart)>`. The cycle-start is computed once at startup (`AlignToCycleStart(_clock.UtcNow)`) and advanced by 15 s after each emission.
- `IModeDecoder` gained a `DecodeAsync(float[], DateTime, CancellationToken)` overload; the old `DecodeAsync(float[], CancellationToken)` is kept for backward compatibility and delegates to the new one via `AlignToCycleStart`.
- `Program.cs` decode pump destructures the tuple and passes `cycleStart` to the new overload.
- `CycleFramerTests` updated for the new channel type. Two new cycle-start correctness tests added.

**Acceptance criterion:** ✅ `DecodeResult.Time` matches the cycle-start time recorded by `CycleFramer`. Two new CycleFramer tests verify correct timestamp alignment.

---

### R4 — `IsValidExtra15` false-positive filter was deleted with no equivalent in the native layer ✅ FIXED

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`  
**Severity:** Medium — marginal false-positive messages with impossible field values can reach ALL.TXT

The old `MessageUnpacker.TryUnpack` validated the 15-bit report/grid field of every Standard QSO message. `ftx_message_decode` applies no equivalent validation.

**Resolution:** Option 2 implemented. `Ft8Decoder.IsPlausibleMessage` (internal static) filters 3-token Standard QSO messages whose last field does not match any known-valid FT8 pattern:
- Maidenhead grid: `[A-R][A-R][0-9][0-9]` (rejects letters > 'R', i.e., index > 17)
- dB report: `[+-][0-9][0-9]` or `R[+-][0-9][0-9]`
- Terminal tokens: `RRR`, `73`, `RR73`
- Hash notation, CQ messages, non-3-token forms: accepted unconditionally

32 unit tests in `Ft8DecoderPlausibilityTests.cs` covering valid and invalid cases.

**Acceptance criterion:** ✅ Option 2 implemented and tested (32 tests).

---

## Recommended fixes (deferred to follow-on change)

The following findings are **not merge-blocking**. They are deferred to a follow-on change. Captain sign-off recorded here.

### N1 — Dedup hash table saturation silently drops a valid decoded message

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, line 233  
**Severity:** Low — extremely unlikely in practice, but produces silent data loss with no diagnostic  
**Status:** Deferred. A comment noting the behaviour is already present in the code.

### N2 — Per-call callsign hash table causes `<HASH>` leakage across cycles

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, line 196  
**Severity:** Low — uncommon (Type 4 messages are rare on most bands); functional quirk, not a crash  
**Status:** Deferred. `callsign_table_t` promotion to static TLS is a future improvement.

### N3 — C# text dedup can silently drop a distinct payload when two different messages render to the same string

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`  
**Severity:** Low — only affects Type 4 `<HASH>` messages  
**Status:** Deferred pending N2 (persistent hash table reduces collision frequency).

### N4 — `monitor_init` does not check `malloc` return values

**File:** `native/ft8_lib_build/patched/common/monitor.c`, line 86  
**Severity:** Low — allocation failure is extremely unlikely for <500 KB on modern Windows  
**Status:** Deferred. NULL-guard addition and error propagation are future improvements.

---

## Minor notes (no action required, fix at discretion)

- **`Marshal.SizeOf<Ft8NativeResult>()` on every call** (`Ft8LibInterop.cs` line 95): The comment says "only the first call evaluates it" — this is inaccurate. The reflection cost is cached by the runtime after the first call so there is no real performance concern, but the comment should be corrected or the check moved inside `LoadAndVerify()` where it genuinely runs once.

- **`new HashSet<string>` per cycle** (`Ft8Decoder.cs` line 75): Minor allocation; could be a reused instance field cleared at the top of each call. Not worth addressing unless profiling identifies it as a bottleneck.

- **`ComputeRms` scalar loop** (`Ft8Decoder.cs` lines 102–108): Could use `System.Numerics.TensorPrimitives.SumOfSquares` for SIMD acceleration. At 180 000 samples this costs ~0.3 ms on a scalar path — negligible but easy to improve if desired.

---

## Checklist for the developer

- [x] **R1** Fix SNR formula — apply `- 26.0f` offset; verify decoded SNRs are in −30..+10 dB range against answer keys
- [x] **R1** Add a comment explaining the formula and its known limitations
- [x] **R2** Add `pcm.Length != ExpectedSampleCount` guard at the top of `Ft8Decoder.DecodeAsync`; use the existing constant
- [x] **R3** Pass `cycleStart` from `CycleFramer` into `DecodeAsync`; remove `AlignToCycleStart`
- [x] **R4** Decide: implement a post-decode field-range filter, or obtain Captain sign-off to accept the CRC-14-only gate
- [x] Run `dotnet test -c Release` — 208 tests pass, 4 skipped (up from 176; 32 new tests added)
- [x] Run `dotnet run --project tools/TraceabilityCheck` — G3 green (181 tests, 45 IDs, 23 in debt)
- [x] Run `dotnet run --project tools/LicenseInventoryCheck` — G5 green
- [x] Rebuild `libft8.dll` and update `libft8.version.txt` — done (MSVC 19.51.36244, 2026-05-30)
- [x] Update `src/OpenWSFZ.Ft8/Native/BUILD.md` to document the SNR formula and the 26 dB offset rationale
