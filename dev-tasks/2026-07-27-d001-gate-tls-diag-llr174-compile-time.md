# Developer handoff: compile-time-gate `tls_diag_llr174` out of shipped native binaries (D-001)

**Authored by:** QA (per HK-011/HK-015), following the Architect's ruling
`qa/cycleframer-alignment-replay/2026-07-27-1622-architect-dll-size-ruling.md` §4.
**Branch:** continue on `d001-c4-min-score-sweep` — same stacking convention as every other D-001
native dev-task on this branch. Do not branch off.
**Status:** small, mechanical, single-array fix, but read §3's ABI gotcha before touching anything —
it is not as simple as wrapping the whole feature in one `#ifdef`.

---

## 1. Context — what's blocked and why

The Architect's ruling is unambiguous: **the native binaries (`win-x64/libft8.dll`,
`linux-x64/libft8.so`) do not merge to `main` in their current (uncommitted, working-tree) form.**
The cause is one array — `static _Thread_local float tls_diag_llr174[K_MAX_CANDIDATES][FTX_LDPC_N]`
(`src/OpenWSFZ.Ft8/Native/ft8_shim.c:589`, 140 × 174 floats = 97,440 bytes) — added this session
(shim 20260035, D-001 C.2 Phase 2c) for the raw-LLR BER measurement. It is study scaffolding: no
product code path reads it, and per the ruling §2 the real cost is not disk (+97 KB Windows-only,
`.tbss` absorbs it for free on Linux — see §5 below for QA's own confirmation of that mechanism) but
**committed memory, ~97 KB × every thread in the process, paid permanently by the shipped product**.

The Architect's recommendation (§4, option **(d)**): `#ifdef` the array out, off in the shipped
build. **Scope the fix to this one array.** The neighbouring `tls_diag_freq_hz` / `_dt` / `_score` /
`_decoded` / `_prenorm_var` / `_postnorm_mean_abs` arrays (~1.4 KB total, shim 20260034, already
studied and accepted) are not the problem and must not be disturbed.

## 2. Design: default-off via `#if`, not a build-script flag

Use a header-level default so **no build script needs editing** and every shipped platform
(win-x64 via `rebuild_shim.bat`, linux-x64 via `build_linux.sh` and CI's `gcc` step, osx-arm64 via
CI's `clang` step) gets the small binary automatically, with zero risk of someone forgetting to pass
a flag on one platform and shipping the array there by accident:

```c
/* Opt-in, OFF by default. Only the D-001 C.2 Phase 2c raw-LLR BER-measurement study needs this
 * array; no shipped build should carry it (qa/cycleframer-alignment-replay/
 * 2026-07-27-1622-architect-dll-size-ruling.md). To build a diagnostic binary that can capture
 * raw LLRs, compile with -DFT8_ENABLE_RAW_LLR_CAPTURE=1 (gcc/clang) or /DFT8_ENABLE_RAW_LLR_CAPTURE=1
 * (cl) added to that ONE build invocation — do not commit a binary built this way. */
#ifndef FT8_ENABLE_RAW_LLR_CAPTURE
#define FT8_ENABLE_RAW_LLR_CAPTURE 0
#endif
```

Place this near the top of `ft8_shim.c`, above the `tls_diag_llr174` declaration (or in
`ft8_shim.h` if you'd rather it be visible to both files — it currently only needs to be visible in
`ft8_shim.c`, since that's the only translation unit that touches the array).

## 3. The ABI gotcha — read this before writing any `#ifdef`

**`ft8_set_candidate_diag_llr_capture` and `ft8_set_llr_shrinkage` must stay unconditionally
exported and callable in every build, shipped or not.** This is not optional and is easy to miss if
you gate the whole feature as one block.

Why: `Ft8Decoder.cs` (managed side) calls both of these **every single decode cycle**, unconditionally,
regardless of whether the diagnostic is enabled:

```csharp
// src/OpenWSFZ.Ft8/Ft8Decoder.cs, ~line 397-400 (working-tree diff, not yet committed)
_interop.SetCandidateDiagLlrCapture(_candidateDiagLlrCaptureEnabled);
_interop.SetLlrShrinkage(_llrShrinkageWeight);
```

This is the same "re-assert every cycle, TLS is thread-affine" pattern already used for
`SetCandidateDiagCapture`, and it is **not itself gated** on `_candidateDiagLlrCaptureEnabled` being
true — the calls happen every cycle no matter what. If `ft8_set_candidate_diag_llr_capture` or
`ft8_set_llr_shrinkage` disappear from a shipped `libft8.dll`/`.so` (e.g. by wrapping the whole
`/* ── Thread-local raw-LLR-174 capture ── */` block in one `#if FT8_ENABLE_RAW_LLR_CAPTURE`), the
**daemon will throw `EntryPointNotFoundException` on the very first decode cycle** of any shipped
build. This is a production-breaking regression, not a diagnostic-only concern — do not let it
happen.

**What actually needs gating is narrower:**

| symbol | gate it? | why |
|---|---|---|
| `tls_diag_llr174` array (`ft8_shim.c:589`) | **Yes** | this is the 97,440-byte cost |
| the write into it inside the pass-0 loop (`ft8_shim.c:1554-1555`, `if (tls_diag_llr_capture_enabled) ftx_get_candidate_raw_llr(&mon.wf, cand, tls_diag_llr174[di]);`) | **Yes** | can't compile without the array |
| `ft8_get_last_candidate_llr` body (`ft8_shim.c:1269-1275`) | **Yes, but keep the function itself exported** — gate only its body, return `0` in the `#else` branch | the export symbol must survive; only its ability to actually copy 97 KB needs to go away |
| `tls_diag_llr_capture_enabled` flag (`ft8_shim.c:588`) | **No** | 4-byte int, not the cost, and `ft8_set_candidate_diag_llr_capture` needs somewhere to write |
| `ft8_set_candidate_diag_llr_capture(int)` (`ft8_shim.c:1245-1248`) | **No — never gate this function or its export** | called unconditionally every cycle by `Ft8Decoder.cs` |
| `ft8_set_llr_shrinkage(double)` (`ft8_shim.c` — search for the function, it sets `tls_llr_shrinkage_weight`) | **No — never gate this function or its export** | called unconditionally every cycle by `Ft8Decoder.cs`; also not part of the 97 KB cost (a `double`, not an array) |
| the small `tls_diag_*` scalar/array group at `ft8_shim.c:568-575` (freq_hz/dt/score/decoded/prenorm_var/postnorm_mean_abs) | **No** | out of scope per the ruling; ~1.4 KB, already studied and accepted |
| `/EXPORT:` lines in `rebuild_shim.bat` for all three shim-20260035 entry points | **No changes** | all three symbols (`ft8_set_candidate_diag_llr_capture`, `ft8_get_last_candidate_llr`, `ft8_set_llr_shrinkage`) must remain exported in every build; only what `ft8_get_last_candidate_llr` *does* changes |

So the concrete edit to `ft8_get_last_candidate_llr` looks like:

```c
int ft8_get_last_candidate_llr(float* out_llr174_flat, int capacity)
{
#if FT8_ENABLE_RAW_LLR_CAPTURE
    int n = (tls_diag_count < capacity) ? tls_diag_count : capacity;
    for (int i = 0; i < n; i++)
        memcpy(out_llr174_flat + (size_t)i * FTX_LDPC_N, tls_diag_llr174[i], sizeof(tls_diag_llr174[i]));
    return n;
#else
    (void)out_llr174_flat;
    (void)capacity;
    return 0;
#endif
}
```

and the capture-loop write and the array declaration both get wrapped in
`#if FT8_ENABLE_RAW_LLR_CAPTURE ... #endif` (no `#else` needed for either — the array simply doesn't
exist, and the write simply doesn't happen, in a shipped build).

**Do not touch `Ft8Decoder.cs`, `Ft8LibInterop.cs`, `Ft8NativeInteropAdapter.cs`, or
`IFt8NativeInterop.cs`.** All managed-side plumbing (already in the working tree, uncommitted) is
correct as-is and works unchanged against the gated binary: `SetCandidateDiagLlrCapture` and
`SetLlrShrinkage` keep working every cycle (harmless no-ops against the gated build — they set a
flag/weight nothing reads), and `GetLastCandidateLlr174()`/`ft8_get_last_candidate_llr` returns `0`
candidates in a shipped build (which is exactly what already happens today whenever the capture flag
is left at its default `false` — `Ft8Decoder.cs` only calls `GetLastCandidateLlr174()` when
`_candidateDiagLlrCaptureEnabled` is true, and production never sets that true).

## 4. Actions

1. Add the `FT8_ENABLE_RAW_LLR_CAPTURE` default-off guard (§2) near the top of `ft8_shim.c`.
2. Wrap the `tls_diag_llr174` array declaration (`ft8_shim.c:589`) in
   `#if FT8_ENABLE_RAW_LLR_CAPTURE ... #endif`.
3. Wrap the capture-loop write (`ft8_shim.c:1554-1555`, inside the existing
   `if (tls_diag_llr_capture_enabled)` block) the same way.
4. Rewrite `ft8_get_last_candidate_llr`'s body per §3's snippet — function stays, export stays,
   behaviour becomes "always returns 0" in a shipped (gate-off) build.
5. Leave `ft8_set_candidate_diag_llr_capture`, `ft8_set_llr_shrinkage`, and every other
   `tls_diag_*`/`tls_llr_*` symbol untouched.
6. **Rebuild both shipped binaries** with the gate left at its default (0) — i.e. no extra `-D`/`/D`
   flag on the normal build commands:
   - Windows: `native/ft8_lib_build/rebuild_shim.bat` (as-is, no edits needed — confirms the
     default-off design in §2 requires no build-script changes).
   - Linux: `wsl -d Debian -- bash -c "cd '<wslpath-to-repo>' && ./native/ft8_lib_build/build_linux.sh"`
     (same script used by the sibling dev-task
     `dev-tasks/2026-07-26-d001-c2-phase2c-linux-so-rebuild.md` — follow its WSL invocation pattern,
     including the absolute `dotnet` path gotcha if you also run local tests).
7. **Verify the size drop directly**, both platforms:
   - `dumpbin /headers` (or just `ls -la`) on `win-x64/libft8.dll` — expect it to land close to the
     pre-Phase-2c size (~60.8 KB) rather than the current 158,208 bytes. The remaining shim-20260035
     growth (small `tls_llr_*` shrinkage scalars, two new exported functions' code, one new
     `IMAGE_TLS_DIRECTORY` descriptor if any TLS survives at all) should be a few hundred bytes at
     most — nowhere near 97 KB.
   - `readelf -S linux-x64/libft8.so | grep -A1 tbss` — expect the `.tbss` section size to shrink
     back down close to its shim-20260034 size (QA measured 0x18770 = 100,208 bytes on the current
     working-tree build with the array present; it should drop to roughly 2,700-2,800 bytes once
     `tls_diag_llr174`'s ~97,440-byte contribution to `.tbss` is gone — see §5 for how QA measured
     this).
8. **Verify the version-check / ABI plumbing is unaffected.**
   `tools/check_native_version.py src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll 20260035` (and the `.so`
   equivalent) should still report `FT8_SHIM_VERSION=20260035` — this fix does not bump the shim
   version, since no export's signature or existing behaviour changes (only what one export's body
   *does* when the diagnostic flag is set changes, from "returns real data" to "returns 0", exactly
   matching that export's own documented "returns 0 otherwise" contract for the not-both-toggles-set
   case).
9. **Build and test locally — do not run `pre_merge_check.py` yourself** (HK-006/HK-011: that gate
   is QA's own review step). Confirm:
   - `dotnet build OpenWSFZ.slnx -c Release` succeeds (Windows).
   - `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release` passes, including the tests in this session's
     diff (`AvContainmentTests.cs`, `D005MessageTrimTests.cs`, `D009FpFilterTests.cs`,
     `D011NonstandardCallsignFpGuardTests.cs`, `HashTableRejectCountLoggingTests.cs`,
     `RegionLookupTests.cs`, `SetDecodeParamsTests.cs`, `WorkedBeforeLookupTests.cs` — these only
     added fake-interop stub methods for the new `IFt8NativeInterop` members, so they should be
     unaffected either way, but confirm rather than assume).
   - WSL-side `dotnet build` + `dotnet test tests/OpenWSFZ.Ft8.Tests -c Release --no-build` against
     the rebuilt `.so`, same pattern as the sibling Linux-rebuild dev-task.
   - Manually sanity-check the diagnostic path still *works* when actually enabled: a quick
     standalone call (e.g. a throwaway console snippet, or reuse
     `qa/rr-study/d001-param-sweep-2026-07-22/Program.cs` if it already exercises
     `SetCandidateDiagLlrCapture`) with `FT8_ENABLE_RAW_LLR_CAPTURE=1` defined at compile time,
     confirming a rebuilt *diagnostic* binary still returns real LLR rows — this is what protects the
     C.2 Phase 2c study's ability to rebuild this capability on demand, per the Architect's ruling §4
     ("no workflow that needs this buffer switchable in a *shipped* artifact"). Do not commit this
     diagnostic-build binary anywhere.
10. **Update `libft8.version.txt`** (both the Windows and Linux sections) recording this fix:
    build date, a one-line note that `tls_diag_llr174` is now compile-time-gated
    (`FT8_ENABLE_RAW_LLR_CAPTURE`, default off, shipped binaries do not include it), and a reference
    to this dev-task. Do not change the `FT8_SHIM_VERSION` number (§4.8).
11. **Confirm the diff is otherwise surgical.** Expect changes in: `ft8_shim.c` (the gate + three
    edits from §4.1-4.4), `win-x64/libft8.dll`, `linux-x64/libft8.so`, `libft8.version.txt`. Nothing
    in `ft8_shim.h`, `decode.c`, `rebuild_shim.bat`, `build_linux.sh`, or any `.cs` file should need
    to change. If you find yourself editing any of those, stop and check with QA before continuing —
    it likely means the ABI-stability requirement in §3 is not being met.

## 5. QA's own confirmation of the `.tbss` mechanism (context, not an action item)

The Architect's ruling §8 flagged its own Linux control as "a file-size comparison... if QA wants it
nailed rather than inferred, `readelf -S` closes it in a minute." QA ran it:

| binary | `.tbss` size (bytes) |
|---|---:|
| `main` (pre-C.2, pre-Phase-2c) | 72 (`0x48`) |
| working tree (shim 20260035, array present) | 100,208 (`0x18770`) |

Delta: **100,136 bytes**, against 140×174×4 = 97,440 bytes for `tls_diag_llr174` alone plus
140×(4+4+2+1+4+4) = 2,660 bytes for the six shim-20260034 scalar/array diagnostics plus a handful of
bytes for the shim-20260035 shrinkage scalars and the new enable flag — sums to ~100,130, matching
the observed delta to within rounding. This directly shows the array landing in `.tbss` (a `NOBITS`
section — occupies virtual TLS space but zero *file* bytes), confirming the mechanism the ruling
inferred from the file-size-delta argument alone. Nothing for the Developer to act on here; recorded
so the size expectation in §4.7 has a basis.

## 6. Acceptance criteria (what QA will check)

- [ ] `tls_diag_llr174` array and its capture-loop write compile only when
      `FT8_ENABLE_RAW_LLR_CAPTURE` is defined non-zero; default (no flag passed) is 0.
- [ ] `ft8_get_last_candidate_llr` remains exported in every build; returns 0 when the gate is off.
- [ ] `ft8_set_candidate_diag_llr_capture` and `ft8_set_llr_shrinkage` remain exported and functional
      (harmless no-ops) in every build — **verified by actually running the daemon/decoder tests
      against the rebuilt shipped binary, not just by inspecting the source**.
- [ ] `win-x64/libft8.dll` shrinks from 158,208 bytes to within a few hundred bytes of the
      pre-Phase-2c ~60.8 KB baseline.
- [ ] `linux-x64/libft8.so`'s `.tbss` section shrinks from 100,208 bytes to roughly 2,700-2,800
      bytes (verify via `readelf -S`).
- [ ] `FT8_SHIM_VERSION` stays at 20260035 (no ABI/behaviour change to any export's contract).
- [ ] `libft8.version.txt` updated on both platform sections.
- [ ] Local Windows build + `OpenWSFZ.Ft8.Tests` pass.
- [ ] Local WSL build + `OpenWSFZ.Ft8.Tests` pass against the rebuilt `.so`.
- [ ] A locally-built (uncommitted) diagnostic binary with `FT8_ENABLE_RAW_LLR_CAPTURE=1` still
      returns real per-candidate LLR rows — confirms the C.2 Phase 2c study workflow survives.
- [ ] `git diff --stat` shows only `ft8_shim.c`, the two shipped binaries, and `libft8.version.txt`
      changed. No `.cs` file, no `ft8_shim.h`, no build script.
- [ ] **Not on this checklist, deliberately:** `pre_merge_check.py` (QA's own step, HK-006/HK-011)
      and anything touching the osx-arm64 `.dylib` (CI rebuilds it from source on every push
      regardless — no local action needed, per the `commit-native-binaries` job).

## 7. References

- `qa/cycleframer-alignment-replay/2026-07-27-1622-architect-dll-size-ruling.md` — the ruling this
  implements, §2 (real cost is per-thread memory), §4 (recommended fix, option (d)), §7 (what this
  does not authorise).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:557-605` — the two `tls_diag_*` comment blocks (C.2 Phase 1
  scalars, out of scope; C.2 Phase 2c `tls_diag_llr174`, in scope) and the LLR-shrinkage globals
  (out of scope, not an array).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1236-1330` (approx.) — `ft8_set_candidate_diag_llr_capture`,
  `ft8_get_last_candidate_llr`, `ft8_set_llr_shrinkage` definitions.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (working-tree diff, ~line 397-400) — the unconditional
  every-cycle call site that makes §3's ABI constraint non-negotiable.
- `dev-tasks/2026-07-26-d001-c2-phase2c-linux-so-rebuild.md` — sibling dev-task, same WSL rebuild
  pattern, same branch-stacking convention.
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — shim 20260035 entry, to be updated per
  §4.10.

---

*Per HK-011, this is `src/`-and-native work — stays in a Developer session, diff reviewed by QA,
Captain sign-off before push. Per HK-014/HK-015 convention applied to Developer sessions in this
thread, nothing is pushed or merged from here; hand the diff back to QA when done.*
