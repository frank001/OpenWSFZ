# D-006 Investigation Report — 2026-06-14

## Summary

During the 2026-06-14 endurance run (reported in `2026-06-14-582bd69/report.md`), OpenWSFZ suffered a process-terminating access violation (0xC0000005) at 01:18:45 UTC. The SEH wrapper added in shim 20260013 contained subsequent occurrences. This report documents the root-cause investigation and resolution.

**Result:** D-006 fully resolved. Shim 20260016 shipped at commit `2a21dd3`.

---

## 1. Crash evidence

**First production crash:** cycle `260614_011845`, 2026-06-14 01:18:45 UTC. 34 signals in the cycle; maximum audio frequency 2704 Hz. Process terminated with exit code 0xC0000005.

**Crash dump capture:** Shim 20260014 introduced `ft8_av_exception_filter()` — a filter-expression MiniDumpWriteDump call that captures `EXCEPTION_POINTERS` before stack unwind. This produced a valid MiniDump at `C:\Dumps\ft8_av_20260614_133145_28356.dmp` (~183 MB, FullMemory) on the first cycle that triggered the fault under the new shim.

**ExceptionStream contents:**

| Field | Value |
|---|---|
| ExceptionCode | 0xC0000005 (access violation) |
| Access type | WRITE (Param[0] = 1) |
| ExceptionAddress | `0x7FFA1A613D06` (libft8.dll RVA 0x3D06) |
| Bad write address | `0x0000000037E3B0BA` |
| Crashing thread TID | 0x6018 |

**CONTEXT registers at fault site:**

| Register | Value | Interpretation |
|---|---|---|
| RCX | `0x0000001737E3B0B6` | Correct 64-bit return from `stpcpy` |
| RBX | `0x0000000037E3B0B6` | Truncated — upper 32 bits (`0x17`) stripped |
| RSP | `0x0000001737E3AFF0` | Thread stack above 4 GB VA |
| RIP | `0x00007FFA1A613D06` | Write instruction inside `ftx_message_decode` |

The bad write address `0x37E3B0BA` is RBX + 4 — a pointer-relative write using the truncated value.

---

## 2. Root cause

**Location:** `ftx_message_decode()` in `ft8/message.c`, compiled into `message.obj`.

**Mechanism:** MSVC generated `MOVSXD RBX, EAX` (opcode `48 63 D8`, sign-extend 32-bit EAX to 64-bit RBX) to capture the `char*` return value from an internal `stpcpy()` call. Because `stpcpy` returns a pointer (64-bit on x64), the correct instruction is `MOV RBX, RAX` (`48 8B D8`).

`MOVSXD` discards the upper 32 bits of the returned pointer. When the .NET runtime allocates the thread stack above the 4 GB VA boundary — common in 64-bit managed processes — all stack-allocated buffers carry upper-address bits. The truncated pointer then refers to an invalid address, and the subsequent write faults.

**Trigger condition:** FT8 messages with the reply-prefix format ("R " prefix, i3/n3 type field bit 0x20 set). This code path calls `stpcpy` internally in `ftx_message_decode`. Standard messages do not follow this path and do not trigger the bug.

**Why it was intermittent:** Whether the thread stack is allocated above or below 4 GB is a runtime decision. In practice the managed heap grows upward during a live run; once the address space is sufficiently populated, new thread stacks land above 4 GB and every "R " reply-prefix decode faults.

---

## 3. Fix

**Binary patch to `message.obj`** (pre-built COFF object file):

| Field | Value |
|---|---|
| File | `native/ft8_lib_build/obj/message.obj` |
| Offset | 0x01B27 |
| Before | `0x63` (MOVSXD opcode — sign-extend) |
| After | `0x8B` (MOV opcode — full 64-bit move) |
| Sequence before | `48 63 D8` → `movsxd rbx, eax` |
| Sequence after | `48 8B D8` → `mov rbx, rax` |

Context verified: the patched instruction immediately follows the `CALL stpcpy` (E8 with relocation), preceding `MOVZX r8d, di` and `MOV eax, 0xCCCCCCCD` — the correct disassembly for the call-site capture in `ftx_message_decode`.

The DLL was rebuilt from the patched `message.obj`. Patch confirmed in the rebuilt binary: `48 8B D8` at RVA 0x3CF2 in the new DLL (export table shift due to removal of diagnostic filter function).

**`message.obj` is now tracked in version control** (`.gitignore` updated from directory-level `obj/` to wildcard `obj/*` with a negation exception) so that DLL rebuilds deterministically use the corrected object.

---

## 4. Additional changes (shim 20260016)

### Diagnostic dump infrastructure removed

The `ft8_av_exception_filter()` function, `MiniDumpWriteDump`, `dbghelp.h`, and the hardcoded `C:\Dumps\` path were removed from `ft8_shim.c`. Rationale: the infrastructure was a diagnostic one-shot; it served its purpose. A hardcoded Windows-only path in production code is unacceptable. The Windows-only limitation of `MiniDumpWriteDump` is also incompatible with the Linux/macOS build targets.

The `__except` clause reverts to `EXCEPTION_EXECUTE_HANDLER` — simple, portable (within MSVC), sufficient for permanent containment.

### RQ-2 latent OOB guard

A latent out-of-bounds read was identified in the `signal_db` computation loop. For signals at high audio frequencies (≥ 2956 Hz, `freq_offset ≥ 473`), `tones[b-b0] ∈ [0,7]` can push the waterfall column index `freq_offset + tone_col` past `num_bins`, reading past the end of the waterfall row.

Fix: skip the sample if `(int)cand->freq_offset + tone_col >= nb`. This silently omits out-of-range samples from the SNR average rather than reading uninitialised memory.

---

## 5. Verification

| Check | Result |
|---|---|
| `ft8_lib_version_check()` returns 20260016 | PASS |
| Patched opcode `48 8B D8` at DLL RVA 0x3CF2 | PASS |
| No `dbghelp`, `MiniDump`, `Dumps`, or `ft8_av_` strings in binary | PASS |
| `dotnet build OpenWSFZ.slnx -c Release` | 0 errors, 0 warnings |
| `dotnet test OpenWSFZ.slnx -c Release` | 341 passed, 0 failures |
| Live session continued decoding after fix deployed | Confirmed — no AV |
| GitHub Issue #17 (D-006) | CLOSED |

---

## 6. Outstanding items

D-006 is fully resolved. The SEH containment wrapper (`__try/__except`) is retained permanently as a production safety net; it does not depend on the pointer-truncation bug being absent.

The `message.obj` binary patch is the correct fix for the upstream MSVC codegen defect. Source access to `ft8_lib` is not available; a source-level fix is not feasible. The patch is minimal, targeted, and reproducible.

No further action required for D-006.
