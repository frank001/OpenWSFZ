# QA Backlog

Observations that are not merge-blocking but must be addressed in a future change.
Each item is classified with a severity and the change in which it was first noted.

---

## N1 — `Ft8LibInterop`: retry-after-failure produces a confusing exception

**Severity:** Low
**Source:** p13-cross-platform-decoder QA review
**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `LoadAndVerify()`

`LoadAndVerify()` registers `NativeLibrary.SetDllImportResolver` as its first step, then performs
the native binary existence check. If the existence check throws (file not present in output dir),
`_initialized` remains `false` and the double-checked lock permits a subsequent retry. On that
second call, `SetDllImportResolver` throws `InvalidOperationException: "A DllImportResolver is
already set for this assembly"`, which buries the original `DllNotFoundException` about the
missing binary.

This path is unreachable in normal operation (a built project always has the binaries in the
output directory), but it would confuse a developer investigating a broken local build.

**Suggested fix:** Guard the `SetDllImportResolver` call with a separate `_resolverRegistered`
volatile flag, or wrap it in `try { … } catch (InvalidOperationException) { /* already
registered */ }` to make it idempotent.

---

## N2 — `Ft8LibInterop`: platform filename computed twice in `LoadAndVerify()`

**Severity:** Cosmetic
**Source:** p13-cross-platform-decoder QA review
**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `LoadAndVerify()`

The platform-appropriate filename (`libft8.dll` / `libft8.so` / `libft8.dylib`) is computed once
inside the resolver lambda and a second time outside it for the `File.Exists` check. Both
computations produce the same result via identical `RuntimeInformation.IsOSPlatform` chains.

**Suggested fix:** Extract a `static string GetPlatformLibFileName()` private method and call it
from both sites.

---

## N3 — `Ft8LibInterop`: 6 720-byte heap allocation on every decode cycle

**Severity:** Low
**Source:** p12-ft8lib-port QA review (carry-through); confirmed in p13
**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` — `DecodeAll()`

```csharp
var results = new Ft8NativeResult[MaxResults];   // 140 × 48 bytes = 6 720 bytes, every cycle
```

A fresh 140-element array is heap-allocated on every 15-second decode cycle. The allocation
is negligible at current cycle rates but will appear prominently in any allocation profiler
trace.

**Suggested fix:** `ArrayPool<Ft8NativeResult>.Shared.Rent(MaxResults)` with a corresponding
`Return()` after the slice is extracted, eliminating the per-cycle heap pressure.
