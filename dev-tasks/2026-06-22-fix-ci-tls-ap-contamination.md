# Developer Handoff — Fix CI TLS AP-bit contamination (Windows-only test failure)

**Date:** 2026-06-22  
**Raised by:** QA Engineer  
**Priority:** BLOCKER (CI red on every push since D-009 merge `ef16040`)

---

## 1. Context

CI has been failing on `windows-latest` since the D-009 merge (`ef16040`, 2026-06-22).
The failure is **Windows-only**; Linux and macOS pass. Root cause is now confirmed: a
**thread-local storage (TLS) AP-bit contamination** caused by thread pool thread reuse
on the 2-core Azure CI VM, which has far fewer thread pool threads than a local developer
machine and therefore reuses them more aggressively.

**Defect ID:** none (regression introduced by D-009; fix is a pure test-layer change).  
**CI failure:** `GetLastPassCounts_AfterDecodeAllOnRealSignal_SumEqualsTotal` in
`OpenWSFZ.Ft8.Tests`.

### Failure chain

1. `D001H6ApDecodeTests.ApDecode_WithCorrectBits_RecoversCoChannelMessage` is an **async**
   test that uses a real `Ft8Decoder(clock)` instance with AP constraints (Q1OFZ/Q9XYZ).
   Internally, `Ft8Decoder.DecodeAsync` fires a `Task.Run` lambda on a thread pool thread
   **T** and calls:
   ```csharp
   _interop.SetApBits(ap.MycallBits, ap.HiscallBits);   // sets TLS: 28 mycall bits, 28 hiscall bits
   var r = _interop.DecodeAll(normalisedPcm);
   ```
2. The `Task.Run` completes; thread **T** is returned to the thread pool.
   **`ft8_decode_all` does not reset `tls_ap_num_mycall_bits` / `tls_ap_num_hiscall_bits`.**
   Thread **T**'s TLS carries the Q1OFZ/Q9XYZ AP bits indefinitely.
3. On CI (2-core VM, far fewer thread pool threads), xUnit's scheduler assigns the
   synchronous test `GetLastPassCounts_AfterDecodeAllOnRealSignal_SumEqualsTotal` to
   thread **T** (reused from pool).
4. That test calls `Ft8LibInterop.DecodeAll(pcm)` **without first calling
   `SetApBits([], [])`** to clear state. Inside `ft8_decode_all`:
   - `ap_active = (tls_ap_num_mycall_bits > 0 || ...)` → **true** (dirty TLS)
   - Pass 0 uses `ftx_decode_candidate_ap` with the Q1OFZ/Q9XYZ bits
   - These bits are **wrong for the fixture** (which encodes Q1ABC/Q9XYZ messages)
   - Wrong-sign LLR injection → BP fails → OSD invoked → nhard gate rejects all OSD candidates
   - `new_decodes = 0` → `tls_pass_counts[0] = 0`
5. `counts[0].Should().BeGreaterThan(0)` → **FAIL**.

On local Windows 11 (8–16 cores) the thread pool has enough threads that **T** is
rarely reused by xUnit before the AP bits are overwritten, so the test passes locally.

---

## 2. Branch name

```
fix/ci-tls-ap-contamination
```

---

## 3. Actions (numbered, ordered)

### 3.1 — Add `SetApBits([], [])` before each direct `DecodeAll` call on the real fixture

File: `tests/OpenWSFZ.Ft8.Tests/Ft8LibInteropTests.cs`

**Two tests need the guard.** Both call `Ft8LibInterop.DecodeAll(pcm)` directly (bypassing
`Ft8Decoder`, which always resets AP state). Add a single line immediately before each
`Ft8LibInterop.DecodeAll(pcm)` call:

```csharp
Ft8LibInterop.SetApBits([], []);   // clear any stale TLS AP bits from concurrent tests
```

**Test 1** — `GetLastPassCounts_AfterDecodeAllOnRealSignal_SumEqualsTotal` (line 87 of
current file):

```csharp
// Act — both calls on the same thread (no Task.Run); TLS is thread-scoped.
Ft8LibInterop.SetApBits([], []);   // ← ADD THIS LINE
Ft8NativeResult[] results = Ft8LibInterop.DecodeAll(pcm);
int[] counts = Ft8LibInterop.GetLastPassCounts(Ft8LibInterop.MaxDecodePasses);
```

**Test 2** — `GetLastCandidateCounts_AfterDecodeAllOnRealSignal_CandidatesAtLeastDecodes`
(line 137 of current file):

```csharp
// Act — same thread
Ft8LibInterop.SetApBits([], []);   // ← ADD THIS LINE
Ft8NativeResult[] results = Ft8LibInterop.DecodeAll(pcm);
int[] decodeCounts    = Ft8LibInterop.GetLastPassCounts(Ft8LibInterop.MaxDecodePasses);
int[] candidateCounts = Ft8LibInterop.GetLastCandidateCounts(Ft8LibInterop.MaxDecodePasses);
```

> **Why test 2 also?**  Without the guard, test 2 happens to pass today because its
> assertions do not require `decodeCounts[0] > 0`. But with dirty AP bits it tests the
> wrong thing (0 actual decodes, masked by `candidateCounts >= decodeCounts`). The guard
> makes both tests correctly exercise the un-assisted decode path.

> **What about the silent-buffer tests?** They do not need the guard. A zero-amplitude
> PCM buffer yields no waterfall energy → no candidates → no decode attempts →
> `new_decodes = 0` regardless of AP state.

### 3.2 — Update inline documentation

In each modified test method, add or extend the comment block to document the guard:

```
// AP bits are cleared before DecodeAll to prevent TLS contamination from
// D001H6ApDecodeTests.ApDecode_WithCorrectBits_RecoversCoChannelMessage, which
// runs concurrently and leaves non-zero AP bits on a Task.Run thread pool thread
// that CI (2-core VM) may reuse for this synchronous test.
```

### 3.3 — Build and test locally

```
dotnet build OpenWSFZ.slnx -c Release
dotnet test OpenWSFZ.slnx -c Release
```

Expected: **388 passed, 0 failed**.

### 3.4 — No native code changes

This fix is **managed-code only** (C# test file). No changes to:
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` (no shim version bump)
- `native/ft8_lib_build/patched/ft8/decode.c`
- Any `.csproj`, `Directory.Packages.props`, or NuGet packages
- The obj/ cache key is unchanged

---

## 4. Acceptance criteria (QA review checklist)

QA will check the following before approving:

| # | Criterion |
|---|-----------|
| AC-1 | `dotnet test -c Release` → **388 passed, 0 failed, 0 skipped** |
| AC-2 | `GetLastPassCounts_AfterDecodeAllOnRealSignal_SumEqualsTotal` passes (**was failing**) |
| AC-3 | `GetLastCandidateCounts_AfterDecodeAllOnRealSignal_CandidatesAtLeastDecodes` passes (was already passing; must remain passing) |
| AC-4 | All other 386 tests remain green |
| AC-5 | `SetApBits([], [])` call is on the same thread as `DecodeAll` (no `Task.Run` wrapper) |
| AC-6 | Both modified tests contain the AP-contamination guard comment (Action 3.2) |
| AC-7 | No changes to native source files, `.csproj` files, or `Directory.Packages.props` |
| AC-8 | Branch is `fix/ci-tls-ap-contamination`, never `main` |

---

## 5. References

- Failing CI run: `27920096806` (`f11f438`, 2026-06-22)
  — `windows-latest` only, `Build & Test (windows-latest)` job
- Root cause investigation: this session (2026-06-22), QA engineer
- `D001H6ApDecodeTests.cs` — sets real AP bits via `Ft8Decoder` + `Task.Run`
- `Ft8LibInterop.cs` — `SetApBits([], [])` resets `tls_ap_num_mycall_bits = 0`
- `ft8_shim.c` lines 445–448, 972–985 — TLS AP bit storage and setter
- `ft8_shim.c` line 1083 — `ap_active` flag read in `ft8_decode_all`
- `ft8_shim.c` lines 1049–1053 — TLS reset at start of decode (does NOT include AP bits)
- `Ft8Decoder.cs` lines 178–182 — correct pattern: always call `SetApBits` before `DecodeAll`
