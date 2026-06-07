# DEFECT — Native Stack Overflow: `pcm_residual` in `ft8_decode_all`

**Severity:** P1 — Fatal crash, process termination  
**Component:** `src/OpenWSFZ.Ft8/Native/ft8_shim.c` + `Native/win-x64/libft8.dll`  
**Status:** ~~Superseded~~ — PCM-domain SIC reverted on `revert/fix-d001-pcm-sic`; `pcm_residual` no longer exists in `ft8_shim.c`. Defect is moot.  
**Raised by:** QA, 2026-06-07  
**Superseded:** 2026-06-07 (change `revert-fix-d001-pcm-sic`)  
**Crash signature:** `0xC0000005` in `Ft8LibInterop.NativeDecodeAll`

---

## Engineering Record

This defect was raised during the code review of `fix/native-stack-overflow-pcm-residual`
(PR #5). The root cause was a 720 KB stack-local array in `ft8_decode_all`:

```c
float pcm_residual[FT8_EXPECTED_SAMPLES];   /* 180 000 × 4 bytes = 720 KB */
```

This exceeded the .NET thread pool thread stack budget (~896 KB usable after CLR reserve),
producing an intermittent `0xC0000005` (STATUS_ACCESS_VIOLATION) crash under real-signal load.

A heap-allocation fix was authored on the fix branch (`48e35c1`) and a macOS dylib was
committed (`f7c9b3a`). However, a **second** `0xC0000005` crash was observed with the fixed
DLL deployed — a different memory access violation in the SIC code path, root cause
unidentified.

Given that the R&R study showed **zero net improvement** from PCM-domain SIC (−0.1 pp
delta; 54.7% vs 54.8% baseline), the decision was made to **revert the entire PCM-SIC
feature** rather than continue debugging it. PR #5 was closed without merging.

`pcm_residual` was removed entirely as part of the revert. This defect is therefore
**superseded** — the defective code path no longer exists.

---

## Summary

| Item | Detail |
|---|---|
| **Defect type** | Native stack overflow — `float[180000]` on C call stack |
| **Crash code** | `0xC0000005` (Windows STATUS_ACCESS_VIOLATION on stack guard page) |
| **Partial fix** | Heap allocation authored on `fix/native-stack-overflow-pcm-residual` (`48e35c1`) |
| **Second crash** | Different access violation in SIC path with heap fix deployed; root cause unknown |
| **Resolution** | PCM-SIC reverted entirely on `revert/fix-d001-pcm-sic`; `pcm_residual` removed |
| **Outcome** | Defect superseded — code no longer exists; FT8_SHIM_VERSION restored to 20260002 |

See also: `openspec/changes/revert-fix-d001-pcm-sic/` for the full revert rationale.
