# p12 QA Review — Required Changes

**Reviewer:** QA Gate  
**Branch:** `feat/p12-ft8lib-port`  
**Date:** 2026-05-30  
**Status:** ❌ Changes required before merge

FT8 decoding is confirmed working. Eight findings were raised; four are required fixes before approval. Four are lower-priority and may be addressed in a follow-on change with Captain sign-off.

---

## Required fixes (merge blocked)

### R1 — SNR formula is wrong by ~26 dB

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, line 249  
**Severity:** High — user-visible, directly causes the reported "dB all over the place" symptom

`cand->score * 0.5f` is not an SNR. It is the average dB margin of each Costas sync bin over its immediate waterfall neighbours — a sync-quality proxy. The WSJT-X SNR convention references the signal power against the noise floor integrated over a **2500 Hz bandwidth**. FT8 tone spacing is 6.25 Hz, so the missing correction is:

```
10 * log10(2500 / 6.25) ≈ 26.0 dB
```

The ft8_lib demo source itself carries the comment `// TODO: compute better approximation of SNR` at this calculation, confirming it was never intended as a finished answer.

**Current code:**
```c
float snr_f = (float)cand->score * 0.5f;
```

**Minimum fix:**
```c
float snr_f = (float)cand->score * 0.5f - 26.0f;
```

**Better fix** (preferred): estimate the noise floor from the waterfall rather than using a fixed offset. `monitor_t` already tracks `mon.max_mag` (peak magnitude in dB across all blocks). A proper noise floor estimate uses the median bin magnitude across all waterfall blocks at the end of `monitor_process`. If that is out of scope for this change, apply the fixed −26.0 offset and document the limitation in a comment.

**Acceptance criterion:** Decoded SNR values for real off-air 40 m FT8 signals fall in the range −30 to +10 dB and are within ±6 dB of WSJT-X output for the same transmission. The three `RealSignalFixtureTests` must still pass.

---

### R2 — `DecodeAsync` throws synchronously, violating the `Task`-returning method contract

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, line 40  
**Also:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, line 80  
**Severity:** Medium — contract violation; callers using `try/catch` around `await` will not catch the exception

`DecodeAsync` is declared as returning `Task<IReadOnlyList<DecodeResult>>` but is **not** marked `async`. It uses `Task.FromResult(...)` at the end. `Ft8LibInterop.DecodeAll` throws `ArgumentException` synchronously when `pcm.Length != 180_000`. That exception propagates **before** any `Task` is returned, not as a faulted task.

```csharp
// caller expecting async exception semantics:
try
{
    var results = await decoder.DecodeAsync(wrongLengthBuffer, ct);
}
catch (ArgumentException ex)
{
    // This catch is NEVER reached — the throw escapes synchronously
    // before the await even executes.
}
```

**Fix:** Add the length guard in `Ft8Decoder.DecodeAsync` itself, before the call to `DecodeAll`, so the exception is thrown in a place the caller can predict:

```csharp
if (pcm.Length != ExpectedSampleCount)
    throw new ArgumentException(
        $"PCM buffer must be exactly {ExpectedSampleCount} samples. Got {pcm.Length}.",
        nameof(pcm));
```

The dead constant `private const int ExpectedSampleCount = 180_000` (line 27) is already there — use it. This does not fix the non-async exception propagation entirely (the method is still not truly `async`), but it moves the throw to a documented, documented pre-condition check that callers can reason about, and removes the surprise from inside `DecodeAll`.

Alternatively, mark the method `async` and use `await Task.Run(...)` for the native call. That is the cleaner long-term fix and also lets `CancellationToken` be honoured during the native decode (see R3 below).

**Acceptance criterion:** Passing a buffer of the wrong length to `DecodeAsync` results in a faulted `Task` (if async) or a clearly documented synchronous pre-condition throw. The `ExpectedSampleCount` constant is used at the validation site.

---

### R3 — Cycle-start timestamp snaps to the wrong 15-second window under load

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, line 59  
**Severity:** Medium — produces incorrect timestamps in ALL.TXT and WebSocket events when the decode queue is backed up

`_clock.UtcNow` is captured **after** the 15-second audio buffer has been recorded and `ComputeRms` has run. If the calling thread is delayed (scheduler pressure, GC pause, prior cycle's decode still running) such that `UtcNow` is read just after a 15-second boundary, `AlignToCycleStart` snaps to the start of the **new** cycle — 15 seconds ahead of the actual transmission window. Every `DecodeResult.Time` in that call is wrong by one cycle.

**Fix:** The `CycleFramer` knows when each 15-second window started. Pass the cycle-start timestamp into `DecodeAsync` as a parameter rather than inferring it inside the decoder from the current wall clock.

Proposed signature change:

```csharp
// IModeDecoder — add overload or replace parameter
Task<IReadOnlyList<DecodeResult>> DecodeAsync(
    float[]           pcm,
    DateTime          cycleStart,      // ← new: supplied by CycleFramer
    CancellationToken ct = default);
```

`Ft8Decoder` then uses `cycleStart.ToString("HH:mm:ss")` directly and removes `AlignToCycleStart` entirely.

If changing the interface is out of scope for this PR, add an overload and route `CycleFramer` through it; deprecate the single-parameter form.

**Acceptance criterion:** The `Time` field in `DecodeResult` matches the cycle-start time recorded by `CycleFramer`, not the wall-clock time at which `DecodeAsync` was invoked.

---

### R4 — `IsValidExtra15` false-positive filter was deleted with no equivalent in the native layer

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, line 241 (call to `ftx_message_decode`)  
**Severity:** Medium — marginal false-positive messages with impossible field values can reach ALL.TXT

The old `MessageUnpacker.TryUnpack` validated the 15-bit report/grid field of every Standard QSO message before returning it:

- Report field: value must be in **[1, 127]** — values 128–16383 have no FT8 meaning
- Grid field: Maidenhead letter indices must be in **[0, 17]**

Values outside these ranges indicate false LDPC convergences that happen to satisfy CRC-14 by chance (probability ≈ 1 in 16 384 per candidate). On a busy band with 140 candidates decoded per cycle, over a 24-hour session the expected false-positive count without this filter is non-trivial.

`ftx_message_decode` applies no equivalent validation. The message unpack in ft8_lib trusts the CRC entirely.

**Fix options (choose one):**

1. **Post-decode filter in the shim (preferred):** After `ftx_message_decode` returns `FTX_MESSAGE_RC_OK`, check the unpacked text for obviously impossible values. For Standard QSO messages (i3=0/1), re-parse the rendered string to verify the report/grid field is in range before writing to `results`. This is lightweight and keeps the validation close to the protocol.

2. **Post-decode filter in `Ft8Decoder.cs`:** Add a `IsPlausibleMessage(string text)` helper in the managed layer that applies a regex or field-range check on the decoded string.

3. **Accept the risk and document it** with a comment in `ft8_shim.c` explaining that CRC-14 is the sole false-positive gate, acknowledging the ~1-in-16384 residual rate.

**Acceptance criterion:** Option 1 or 2 implemented and tested. Or option 3 accepted by the Captain explicitly.

---

## Recommended fixes (not merge-blocking; address in follow-on or this PR)

### N1 — Dedup hash table saturation silently drops a valid decoded message

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, line 233  
**Severity:** Low — extremely unlikely in practice, but produces silent data loss with no diagnostic

When all 140 slots of `decoded_ht` are occupied by prior entries and a new valid decoded message's entire probe chain is full, `slot_found` is false and the message is silently skipped with no log entry.

**Fix:** Log a warning (or count a drop counter) when `!slot_found`:

```c
if (is_dup || !slot_found)
{
    // In production builds this path indicates hash-table saturation —
    // a successfully-decoded unique message was dropped.
    // The outer loop bound (num_decoded < max_results) prevents this in
    // the common case, but log it if it ever fires.
    continue;
}
```

At minimum, add a comment. The structural fix is to replace the fixed-size open-addressed table with a check against `num_decoded` before inserting — if `num_decoded >= max_results`, stop the outer loop early rather than probing a potentially-full table.

---

### N2 — Per-call callsign hash table causes `<HASH>` leakage across cycles

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, line 196  
**Severity:** Low — uncommon (Type 4 messages are rare on most bands); functional quirk, not a crash

The `callsign_table_t` is initialised fresh on every `ft8_decode_all()` call. Callsigns learned from Type 1 messages in cycle N are not available to Type 4 messages in cycle N+1. WSJT-X maintains a persistent cross-cycle hash table.

**Fix:** Promote `callsign_table_t` to a `static` variable in `ft8_shim.c` (or a `_Thread_local static` if multi-thread support is ever needed). Reset it only when a configurable TTL expires (e.g., after 10 minutes of inactivity), mirroring WSJT-X behaviour. This is a behavioural improvement, not a crash fix.

---

### N3 — C# text dedup can silently drop a distinct payload when two different messages render to the same string

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, line 81  
**Severity:** Low — only affects Type 4 `<HASH>` messages; the C shim already deduplicates standard messages

Two different 77-bit payloads can render to the same text (most likely two Type 4 messages from two different stations, both appearing as `"CQ <HASH> FN31"` because neither callsign is in the per-call hash table). The C# `HashSet<string>` drops the second as a duplicate even though it is a distinct signal.

**Fix:** If N2 is fixed (persistent hash table), `<HASH>` collisions become much rarer. For now, either remove the C# dedup layer (trusting the C-level payload dedup entirely) or document the known limitation.

---

### N4 — `monitor_init` does not check `malloc` return values

**File:** `native/ft8_lib_build/patched/common/monitor.c`, line 86  
**Severity:** Low — allocation failure is extremely unlikely for <500 KB on modern Windows; crash with no diagnostic if it occurs

`waterfall_init`, `monitor_init` call `malloc`/`calloc` without checking the return value. A NULL pointer is passed silently into `monitor_process`, which dereferences it immediately.

**Fix:** Since these are patched copies of ft8_lib source, add NULL guards in `monitor.c`:

```c
me->mag = (WF_ELEM_T*)malloc(mag_size);
if (me->mag == NULL) { /* log / abort */ return; }
```

Similarly for `me->window`, `me->last_frame`, `me->fft_work`. Return an error code from `monitor_init` and propagate it up to `ft8_decode_all`, which should return −2 (out of memory) so the managed caller receives an `InvalidOperationException` with a useful message rather than a process crash.

---

## Minor notes (no action required, fix at discretion)

- **`Marshal.SizeOf<Ft8NativeResult>()` on every call** (`Ft8LibInterop.cs` line 95): The comment says "only the first call evaluates it" — this is inaccurate. The reflection cost is cached by the runtime after the first call so there is no real performance concern, but the comment should be corrected or the check moved inside `LoadAndVerify()` where it genuinely runs once.

- **`new HashSet<string>` per cycle** (`Ft8Decoder.cs` line 75): Minor allocation; could be a reused instance field cleared at the top of each call. Not worth addressing unless profiling identifies it as a bottleneck.

- **`ComputeRms` scalar loop** (`Ft8Decoder.cs` lines 102–108): Could use `System.Numerics.TensorPrimitives.SumOfSquares` for SIMD acceleration. At 180 000 samples this costs ~0.3 ms on a scalar path — negligible but easy to improve if desired.

---

## Checklist for the developer

- [ ] **R1** Fix SNR formula — apply `- 26.0f` offset; verify decoded SNRs are in −30..+10 dB range against answer keys
- [ ] **R1** Add a comment explaining the formula and its known limitations
- [ ] **R2** Add `pcm.Length != ExpectedSampleCount` guard at the top of `Ft8Decoder.DecodeAsync`; use the existing constant
- [ ] **R3** Pass `cycleStart` from `CycleFramer` into `DecodeAsync`; remove `AlignToCycleStart`
- [ ] **R4** Decide: implement a post-decode field-range filter, or obtain Captain sign-off to accept the CRC-14-only gate
- [ ] Run `dotnet test -c Release` — all 176 tests pass, 4 skipped
- [ ] Run `dotnet run --project tools/TraceabilityCheck` — G3 green
- [ ] Run `dotnet run --project tools/LicenseInventoryCheck` — G5 green
- [ ] Rebuild `libft8.dll` and update `libft8.version.txt` if `ft8_shim.c` is changed (R1)
- [ ] Update `src/OpenWSFZ.Ft8/Native/BUILD.md` to document the SNR formula and the 26 dB offset rationale

*This review document to be removed or marked resolved when the PR is updated and re-reviewed.*
