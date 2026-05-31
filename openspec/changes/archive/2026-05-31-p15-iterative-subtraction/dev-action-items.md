# Developer Action Items — p15-iterative-subtraction QA Review

**Date:** 2026-05-31
**Branch:** `feat/p15-iterative-subtraction`
**Source:** QA Review (second pass)

---

## 🔴 Required Before Merge

### 1 — Fix suppression description in `specs/iterative-subtraction/spec.md`

**File:** `openspec/changes/p15-iterative-subtraction/specs/iterative-subtraction/spec.md`
**Lines:** 3–4 (the "Second-pass spectrogram-domain residual decode" requirement)

The current text says:

> *"…setting all waterfall tiles covering the signal's 79-symbol window and **all 8 FT8 tone bins**… to the noise-floor median raw byte"*

This is wrong. The implementation uses **narrow suppression**: the exact decoded tone bin (from `ft8_encode`) plus its ±1 nearest neighbours — at most 3 bins per symbol, not 8. The rationale for this choice is already in `design.md §Decision 2`.

**What to write instead** (adapt as needed):

> *"…setting the exact decoded tone bin and its ±1 nearest neighbours (to cancel Hann-window first sidelobes), as determined from `ft8_encode()`, to the noise-floor median raw byte for each of the 79 FT8 symbols across all time and frequency over-sampling sub-bins."*

---

## 🟡 Recommended (Strong — Apply Before Merge)

### 2 — Add a unit test for `GetLastPassCounts` with a silent buffer

The spec contains this scenario (in `specs/ft8lib-interop/spec.md`):

> *"WHEN `DecodeAll` is called with a silent buffer AND THEN `GetLastPassCounts(2)` is called, THEN it SHALL return `[0, 0]`."*

There is currently no automated test for this. Add one alongside the existing interop or decoder tests. It should:

1. Call `Ft8LibInterop.DecodeAll` with 180 000 zeroed samples.
2. Call `Ft8LibInterop.GetLastPassCounts(2)` on the **same thread** immediately after.
3. Assert the returned array is `[0, 0]`.

This is cheap to write and protects the TLS mechanic from future regression.

### 3 — Remove the unnecessary `(uint16_t)` cast in dedup slot calculation

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`
**Line:** dedup block inside the pass loop

```c
// Current — confusing cast
int  slot = (int)(msg.hash % (uint16_t)K_MAX_DECODED);

// Replace with
int  slot = (int)(msg.hash % K_MAX_DECODED);
```

The cast is harmless (340 fits in `uint16_t`) but a future reader will wonder what it is protecting against. Remove it.

---

## ⚪ Noted — No Action Required This PR

These are on record; no work needed now.

| # | Item |
|---|---|
| N-1 | macOS `libft8.dylib` rebuild — CI will handle on push (tasks.md 4.5). |
| N-2 | Style compression in `hash_table_lookup` / `hash_table_add` — not a defect; future cleanup if desired. |
| N-3 | `MaxResults = 140` is below the two-pass ceiling of 340 — practical risk nil; tracked as prior Finding 4 for future housekeeping. |

---

## Checklist

- [x] R-1 — spec.md suppression text corrected
- [x] R-2 — `GetLastPassCounts` silent-buffer test added
- [x] R-3 — spurious `(uint16_t)` cast removed (win-x64 DLL rebuilt; linux/macOS via CI)
- [x] Re-submitted to QA

---

---

# Round 2 — QA Review (Final Pass, 2026-05-31)

**Source:** QA Review — code review findings

---

## 🔴 Required Before Merge

### R2-1 — Fix `findings.md` status text — factually wrong post-p15

**File:** `openspec/changes/p10-decoder-ground-truth/findings.md`
**Line:** 68

Despite being marked `[x]` in `qa-review.md`, this fix was **not applied**. A `git diff HEAD` on the file confirms only the timestamp changed — the status sentence was never rewritten.

**Current text (wrong):**

> *"The ~33% miss rate relative to WSJT-X is a known, accepted limitation of ft8_lib **not implementing iterative subtraction (second-pass decoder)**. This is a product-level decision **deferred to a future change**. No action required."*

After p15, iterative subtraction *has been implemented*. This sentence is factually false.

**Replace with:**

> *"Iterative signal subtraction was implemented in p15 (`p15-iterative-subtraction`) using spectrogram-domain ±1-bin narrow suppression. The remaining ~31% gap to WSJT-X is the ceiling of the spectrogram-domain approach: FFT-waterfall ±3.125 Hz frequency resolution prevents coherent PCM-domain waveform cancellation. Closing the remaining gap requires sub-Hz carrier-frequency estimation and PCM-domain waveform subtraction, scheduled as a future change."*

---

## Checklist

- [x] R2-1 — `findings.md` status text corrected to reflect p15 implementation
- [x] Re-submit to QA for final approval

Once R2-1 is done, QA will sign off and the PR may be marked ready-for-review.

---

---

# Round 3 — QA Review (2026-05-31)

**Source:** QA Review — high-effort code review, multi-angle finder + verify pass

---

## ⚠️ Administrative — Unauthorised working-tree changes (resolve first)

During the review process, a cleanup-angle analysis agent applied changes to three files without
authorisation. These changes are present in the working tree but **not committed**. They are
technically sound and QA would have recommended them regardless; however, they have not been
built or tested, and the `ft8_shim.c` change requires a **native binary rebuild** before
committing.

Resolve this item before tackling the required fixes below.

### ADM-1 — Decide: accept or revert the three pending working-tree edits

Run `git diff HEAD` to inspect the changes. A summary:

| File | Change |
|---|---|
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c` | Three ternary pass-config selectors replaced with `static const k_pass_cfg[]` table; magic literal `79` replaced with `FT8_NN` in SNR loop |
| `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` | `MaxDecodePasses = 2` added as `internal const` (ownership moved from `Ft8Decoder`) |
| `src/OpenWSFZ.Ft8/Ft8Decoder.cs` | `private const MaxDecodePasses` removed; references `Ft8LibInterop.MaxDecodePasses`; `IsEnabled` guard replaced with `_logger?.LogDebug(...)` |

**If accepting:** run `dotnet build -c Release` to verify the C# changes compile; rebuild
`libft8.dll` (Windows MSVC) and `libft8.so` (Linux GCC) before committing, as the shim
source has changed.

**If reverting:** `git restore src/OpenWSFZ.Ft8/` to discard the three modified files and
return to the last committed state. Proceed with only the required fixes below.

---

## 🔴 Required Before Merge

### R3-1 — Fix dedup slot written before `ftx_message_decode` succeeds

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`
**Lines:** 293–298 (inside the candidate loop, cross-pass dedup block)

**The bug:**

```c
// ← slot written unconditionally, BEFORE text decode is attempted
memcpy(&decoded_msgs[walk], &msg, sizeof(msg));
decoded_ht[walk] = &decoded_msgs[walk];

char text[FTX_MAX_MESSAGE_LENGTH + 1];
if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
    continue;   // slot is now permanently occupied; message never output
```

`ftx_message_decode` can fail for Type-4 (non-standard callsign) FT8 messages when
the 22-bit callsign hash is not yet in the per-call hash table — specifically when the
companion message containing the full callsign has a lower sync score and appears later
in the candidate list. When this happens:

1. **Pass 1:** LDPC/CRC passes → dedup slot at `walk` is written → text decode fails →
   `continue`. Message is never written to `results`.
2. **Pass 1 (later):** companion message decoded → callsign added to hash table.
3. **Pass 2:** same LDPC-valid payload re-detected → dedup probe finds `dup = true` →
   silently skipped. The hash table now has the callsign, but pass 2 never reaches
   `ftx_message_decode`.

The message is permanently lost.

**Fix — swap the write and the decode:**

```c
char text[FTX_MAX_MESSAGE_LENGTH + 1];
if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
    continue;   // ← text decode first; bail before touching dedup table

// Only occupy the dedup slot once we know the message is fully decodable.
memcpy(&decoded_msgs[walk], &msg, sizeof(msg));
decoded_ht[walk] = &decoded_msgs[walk];
```

This also resolves the secondary inefficiency (N-3 below): failed-text-decode messages
will no longer occupy dedup slots, so pass 2 will correctly re-attempt them rather than
skipping them as duplicates.

**Rebuild required:** after modifying `ft8_shim.c`, rebuild `libft8.dll` and `libft8.so`
before running the test suite. The macOS `libft8.dylib` will be rebuilt by CI on push.

**Regression test:** the existing `Ft8LibInteropTests` silent-buffer test exercises the
TLS mechanic but does not exercise the hashed-callsign path. A targeted test would require
a synthetic WAV or mock payload; given the low fixture coverage of Type-4 messages, QA
will accept a code-review-only verification of this fix. Ensure `dotnet test` remains
fully green after the change.

---

### R3-2 — Add overflow guard to `hash_table_add`

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`
**Lines:** 112–126

**The bug:**

```c
static void hash_table_add(callsign_table_t* tbl, const char* callsign, uint32_t hash)
{
    uint16_t h10 = (hash >> 12) & 0x3FFu;
    int      idx = (h10 * 23) % HASH_TABLE_SIZE;
    while (tbl->entries[idx].callsign[0] != '\0') {
        if (...match...) { ...; return; }
        idx = (idx + 1) % HASH_TABLE_SIZE;
        // ← no iteration limit; cycles forever if all 256 slots are full
    }
    ...
}
```

`HASH_TABLE_SIZE = 256`. If all 256 slots are filled with distinct callsigns and a 257th
unique callsign is added (via `cb_save_hash`), the `while` termination condition never
fires. The decode thread hangs indefinitely; `DecodeAsync` never returns.

With pass 2 using `K_MIN_SCORE_PASS2 = 1` (accepting essentially any candidate), more
callsigns are added per cycle than in the single-pass baseline. The practical ceiling on
busy contest bands is ~160–200 unique callsigns per 15-second slot — below 256, but with
less headroom than before p15.

**Fix — add one guard line before the loop:**

```c
static void hash_table_add(callsign_table_t* tbl, const char* callsign, uint32_t hash)
{
    if (tbl->count >= HASH_TABLE_SIZE) return;  // ← table full; discard silently

    uint16_t h10 = (hash >> 12) & 0x3FFu;
    int      idx = (h10 * 23) % HASH_TABLE_SIZE;
    while (tbl->entries[idx].callsign[0] != '\0') {
        ...
    }
    ...
}
```

Discarding new callsigns when the table is full is the correct degradation: unknown
callsigns display as `<HASH>` in decoded messages, which is identical to WSJT-X behaviour
on first-seen calls. No crash, no hang, no data corruption.

**Note:** this is a pre-existing defect (present before p15). It is included here because
p15 worsens the exposure and the fix is a single line.

---

## ⚪ Noted — No Action Required This PR

| # | Item |
|---|---|
| N-3 | Failed-text-decode candidates not tracked for suppression — pass 2 re-attempts LDPC on them (wasted compute). Resolves automatically once R3-1 is applied: failed candidates no longer occupy dedup slots, pass 2 can retry them, and successful retries suppress the tiles. |
| N-4 | `MaxResults = 140` below two-pass theoretical ceiling (340) — previously noted as Finding 4 in `qa-review.md`; practical risk nil at observed corpus volumes. |

---

## Checklist

- [x] ADM-1 — Working-tree edits accepted (build + DLL rebuild) or reverted
- [x] R3-1 — `ftx_message_decode` called before dedup slot is written; `libft8.dll` + `libft8.so` rebuilt; test suite green (213 passed, 4 skipped)
- [x] R3-2 — `hash_table_add` overflow guard added; `libft8.dll` + `libft8.so` rebuilt
- [x] Re-submit to QA for sign-off

---

---

# Round 4 — QA Review (2026-05-31)

**Source:** QA Review — high-effort multi-angle code review (7 finder angles + verifier pass)

---

## 🔴 Required Before Merge

### R4-1 — Increase `MaxResults` to match two-pass output capacity

**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`
**Line:** 33

**The bug:**

`MaxResults = 140` was set equal to `K_MAX_CANDIDATES` (the single-pass candidate limit) and
was never updated when the two-pass loop was added. The managed result buffer is passed to
the native shim as `max_results = 140`. In `ft8_shim.c` the inner loop guards:

```c
for (int ci = 0; ci < ncands && num_decoded < max_results; ++ci)
```

If pass 1 decodes all 140 messages (`num_decoded == 140 == max_results`), the pass-2 inner
loop condition is `false` at `ci = 0`. Every pass-2 candidate is skipped. `tls_pass_counts[1]`
is `0`. The iterative subtraction feature produces no extra decodes regardless of how many
signals are masked on the band.

**Fix — one line, no native rebuild required:**

```csharp
// Before
private const int MaxResults = 140;

// After
private const int MaxResults = 340;   // K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2 (two-pass capacity)
```

The `results[..count]` slice at the call site already returns only the populated portion;
enlarging the buffer is safe and requires no other change.

> **Rebuild required:** none — this is a managed-only change.

---

### R4-2 — Fix `MaxDecodePasses` / `K_MAX_PASSES` drift exposure

**File:** `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`
**Line:** 40

**The problem:**

`internal const int MaxDecodePasses = 2` (C#) and `#define K_MAX_PASSES 2` (C) are two
independent literals. `GetLastPassCounts(MaxDecodePasses)` passes `capacity = 2` to the
native shim, which clamps its return value to `min(tls_num_passes, capacity)`. If the native
shim is ever rebuilt with `K_MAX_PASSES = 3` while the managed constant stays at 2, pass 3's
count data is silently dropped — no exception, no diagnostic.

The existing ABI version check (`ExpectedShimVersion`) verifies struct layout but has no
channel for communicating `K_MAX_PASSES`.

**Fix — expose `K_MAX_PASSES` from the native shim and verify it at initialisation time.**

**Step 1 — add to `ft8_shim.h`:**

```c
/* Return the number of decode passes executed per ft8_decode_all call.
 * Managed layer verifies this matches its own MaxDecodePasses constant. */
int ft8_get_max_passes(void);
```

**Step 2 — add to `ft8_shim.c`:**

```c
int ft8_get_max_passes(void) { return K_MAX_PASSES; }
```

**Step 3 — add export to all three platform link commands in `BUILD.md`:**

```
/EXPORT:ft8_get_max_passes          (Windows)
ft8_get_max_passes.o                (Linux / macOS — no separate export syntax needed for shared libs)
```

**Step 4 — add P/Invoke and init check to `Ft8LibInterop.cs`:**

```csharp
[DllImport("libft8.dll", EntryPoint = "ft8_get_max_passes", CallingConvention = CallingConvention.Cdecl)]
private static extern int NativeGetMaxPasses();
```

In `LoadAndVerify()`, after the existing version check:

```csharp
int nativeMaxPasses = NativeGetMaxPasses();
if (nativeMaxPasses != MaxDecodePasses)
    throw new InvalidOperationException(
        $"Native K_MAX_PASSES ({nativeMaxPasses}) does not match managed MaxDecodePasses ({MaxDecodePasses}). " +
        "Rebuild the native library or update the managed constant.");
```

This follows exactly the same pattern as the existing `ExpectedShimVersion` / `NativeVersionCheck()`
check and requires no further changes to the decode path.

> **Rebuild required:** yes — `ft8_shim.c` and `ft8_shim.h` are modified.
> Rebuild `libft8.dll` (Windows) and `libft8.so` (Linux). macOS dylib via CI on push.
> Bump `FT8_SHIM_VERSION` only if the struct layout or an existing function signature changes;
> adding a new export alone does not require a version bump.

---

## 🟡 Recommended (Strong — Apply Before Merge)

### R4-3 — Add early-exit guard to outer pass loop when result buffer is full

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`
**Line:** 262 (outer pass loop)

When `num_decoded >= max_results` at the start of a pass, the outer loop still calls
`ftx_find_candidates` (a full waterfall scan, ~1–2 ms) and allocates the candidate array on
the stack before the inner loop immediately exits on its first iteration. This is pure waste.

**Fix — add one guard at the top of the outer loop body:**

```c
for (int pass = 0; pass < K_MAX_PASSES; pass++)
{
    /* Skip candidate search if the output buffer is already full.
     * Record zero new decodes for this pass so TLS stats remain consistent. */
    if (num_decoded >= max_results) {
        tls_pass_counts[pass] = 0;
        tls_num_passes        = pass + 1;
        continue;
    }

    int pass_max_cands = k_pass_cfg[pass].max_cands;
    ...
```

> **Rebuild required:** yes — `ft8_shim.c` is modified.

---

### R4-4 — Fix misleading `{Max}` denominator in per-pass log

**File:** `src/OpenWSFZ.Ft8/Ft8Decoder.cs`
**Line:** 140

The log message hard-codes `Ft8LibInterop.MaxDecodePasses` as the `{Max}` field rather than
the number of passes actually executed. If the native library runs fewer passes than
`MaxDecodePasses` (e.g. after R4-2 is applied and a mismatch causes early return), the log
reads `"pass 1 of 2"` with no `"pass 2 of 2"` entry — an operator cannot tell whether pass 2
ran or not.

**Fix — replace the constant with `passCounts.Length`:**

```csharp
// Before
passIdx + 1, Ft8LibInterop.MaxDecodePasses, passCounts[passIdx]

// After
passIdx + 1, passCounts.Length, passCounts[passIdx]
```

`passCounts.Length` is always authoritative: it reflects what `GetLastPassCounts` actually
returned from this run, not a compile-time assumption.

> **Rebuild required:** none — managed-only change.

---

### R4-5 — Add a real-signal regression test for pass-2 recovery

**File:** `tests/OpenWSFZ.Ft8.Tests/Ft8LibInteropTests.cs`

The only new test (`GetLastPassCounts_AfterDecodeAllOnSilentBuffer_ReturnsTwoZeroCounts`)
validates TLS plumbing on a silent buffer. It would pass even if `suppress_candidate_tiles`
were a no-op, or if `K_MIN_SCORE_PASS2` were set to `INT_MAX`. There is no living regression
test for the core p15 feature — that pass 2 actually decodes additional signals that pass 1
missed.

**Required test:**

Using any one of the three committed real-signal fixture WAVs, add a test that:

1. Calls `Ft8LibInterop.DecodeAll` on the fixture PCM.
2. Calls `Ft8LibInterop.GetLastPassCounts(2)` on the same thread.
3. Asserts `passCounts[0] > 0` (pass 1 found something on a real-signal fixture).
4. Asserts `passCounts[0] + passCounts[1]` equals the total decode count returned by
   `DecodeAll` (spec requirement: sum of pass counts equals total returned).

The fourth assertion is an explicit spec requirement from `specs/ft8lib-interop/spec.md` and
is not currently exercised by any test. It is also the most likely invariant to break silently
if R4-1 or R4-3 introduce a regression.

> **Rebuild required:** none.

---

## 🟠 Cleanup — Apply This PR (Low Effort)

### R4-6 — Suppress `supp_cands` / `supp_msgs` tracking in the final pass

**File:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`
**Lines:** 353–358 (suppression tracking block inside the inner loop)

With `K_MAX_PASSES = 2`, `pass = 1` is always the final pass.  The suppression guard
`if (pass < K_MAX_PASSES - 1)` is `if (1 < 1)` — always false.  Despite this, `supp_cands`
and `supp_msgs` are still allocated and populated on every successful decode in pass 2 (up to
200 struct copies), then silently discarded when the loop body exits.

**Fix — gate the tracking on whether suppression will actually run:**

```c
/* Track for suppression — only needed when a subsequent pass will use the data. */
if (pass < K_MAX_PASSES - 1 && nsupp < K_MAX_CANDIDATES_PASS2) {
    supp_cands[nsupp] = *cand;
    supp_msgs[nsupp]  = msg;
    nsupp++;
}
```

> **Rebuild required:** yes — `ft8_shim.c` is modified. Bundle with R4-3 to avoid a
> separate rebuild cycle.

---

### R4-7 — Correct stale macOS build date in `libft8.version.txt`

**File:** `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`
**Line:** 17

The macOS ARM64 entry reads:

```
Build date:       TBD — will be rebuilt by CI on push (probe-limit fix applied to ft8_shim.c)
```

The dylib was rebuilt by CI in commit `aa54b9e` (`chore(ci): rebuild libft8.dylib on macOS
ARM64 — R3-2b probe-limit fix`). Update this entry to reflect the actual build, consistent
with the Windows and Linux entries:

```
Build date:       2026-05-31 (p15 rebuild via CI macos-latest — iterative subtraction;
                  R3-2b probe-limit fix; ft8_shim.c FT8_SHIM_VERSION=20260001)
```

> **Rebuild required:** none — documentation only.

---

## ⚪ Noted — No Action Required This PR

| # | Item |
|---|---|
| N-5 | `GetLastPassCounts` returns `[]` when called on a thread that has never run `DecodeAll`. Silent but correct: `tls_num_passes = 0` is the correct default TLS state. Add a `Debug.Assert` or note in a future hardening pass if desired. |

---

## Rebuild and test sequence for this round

R4-2, R4-3, and R4-6 all touch `ft8_shim.c`. Bundle them into a single rebuild:

```
1. Apply R4-1 (Ft8LibInterop.cs — MaxResults)
2. Apply R4-2 steps 1–2 (ft8_shim.h + ft8_shim.c — ft8_get_max_passes)
3. Apply R4-3 (ft8_shim.c — early-exit guard)
4. Apply R4-6 (ft8_shim.c — supp tracking gate)
5. Rebuild libft8.dll (Windows MSVC) and libft8.so (Linux GCC)
6. Apply R4-2 steps 3–4 (BUILD.md export + Ft8LibInterop.cs P/Invoke + init check)
7. Apply R4-4 (Ft8Decoder.cs — log denominator)
8. Apply R4-5 (Ft8LibInteropTests.cs — real-signal test)
9. Apply R4-7 (version.txt — macOS date)
10. dotnet build -c Release → 0 errors, 0 warnings
11. dotnet test -c Release → all green
12. Push branch; confirm CI green on all three legs; re-submit to QA
```

---

## Checklist

- [x] R4-1 — `MaxResults` increased to 340; test suite green
- [x] R4-2 — `ft8_get_max_passes()` export added; `LoadAndVerify` checks it; `libft8.dll` + `libft8.so` rebuilt
- [x] R4-3 — Early-exit guard added to outer pass loop; bundled into R4-2 rebuild
- [x] R4-4 — Log `{Max}` uses `passCounts.Length`
- [x] R4-5 — Real-signal test added; sum-of-pass-counts assertion present
- [x] R4-6 — `supp_cands`/`supp_msgs` tracking gated on `pass < K_MAX_PASSES - 1`; bundled into R4-2 rebuild
- [x] R4-7 — `libft8.version.txt` macOS entry updated
- [ ] Re-submit to QA for sign-off
