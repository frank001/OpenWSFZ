# Developer handoff: shim version correction + `ft8_get_shim_capabilities` (D-001, Q1)

**Authored by:** QA (per HK-011/HK-015), following the Architect's consolidated handoff
`qa/cycleframer-alignment-replay/2026-07-27-1752-architect-to-qa-consolidated-handoff.md` §4 Q1,
itself sharpening the correction in `2026-07-27-1738-architect-version-correction.md`.
**Branch:** continue on `d001-c4-min-score-sweep` — same stacking convention as every other D-001
native dev-task on this branch. Do not branch off.
**Status:** pre-merge requirement. Small and mechanical (one `#define`, one small export, one
managed constant, one guard) but touches `ft8_shim.h` — read §1 before starting, since it lands on
top of a commit (`7c90638`) that just resolved 679 lines of previously-uncommitted state.
**Sequencing:** `ft8_shim.h`, `Ft8LibInterop.cs`, and both shipped binaries are now clean/committed
(`7c90638`). This dev-task is the next change on top, not a rebase.

---

## 1. Context — why this is a pre-merge requirement, not a nice-to-have

The `tls_diag_llr174` compile-time gate (`dev-tasks/2026-07-27-d001-gate-tls-diag-llr174-compile-time.md`,
reviewed and accepted in commits `72b090d`/`c97ce90`) changed a shipped binary's **observable
behaviour** under an **unchanged version number**:

- Shim 20260035, gate **off** (what actually shipped, `FT8_ENABLE_RAW_LLR_CAPTURE` defaults to 0):
  `ft8_get_last_candidate_llr` always returns `0`, `out_llr174_flat` untouched.
- Shim 20260035, gate **on** (a one-off diagnostic rebuild with `-DFT8_ENABLE_RAW_LLR_CAPTURE=1`):
  the same function returns real per-candidate LLR rows.

Same version, same default configuration, different behaviour depending on how the binary
happened to be compiled. The Architect's own review (`c97ce90`) sharpened why this cannot be left
as-is: CI auto-rebuilds `linux-x64/libft8.so` and `osx-arm64/libft8.dylib` from `ft8_shim.c` on
every push and never sets the capture flag, while `win-x64/libft8.dll` is built by hand and could
be either. **Three platform binaries can differ in capability while all reporting the same
version** — a version number cannot express a build-time variant, so a workflow that needs the
diagnostic has no reliable way to ask "can this binary actually do it?" before finding out the hard
way (a cycle of silent zeros, `c97ce90`'s bundled defect).

The fix has two independent halves: (1) make the *existing* mismatch visible by bumping the
version, so nobody mistakes a 20260035 built one way for a 20260035 built the other way ever
again, and (2) give callers a **runtime-discoverable capability bit** instead of relying on the
version number for something a version number cannot express. The Architect's ruling in `c97ce90`
was explicit that a build-flag variant is not itself a shim revision — the capability should be
runtime-discoverable, which is what this dev-task delivers.

## 2. Design — four small parts

### 2.1 Bump the version

- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:333` — `#define FT8_SHIM_VERSION 20260035` (as committed in
  `7c90638`) to **`20260036`**. Add a new dated
  paragraph to the version-history comment block immediately above (same style as the existing
  `20260034`/`20260035` paragraphs at `ft8_shim.h:279-332`) explaining the bump is **not** an ABI or
  struct-layout change — it exists purely so the startup ABI check can no longer conflate a
  gate-on and a gate-off binary built from the same nominal version, and to gate the new
  `ft8_get_shim_capabilities` export in.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:246` — `ExpectedShimVersion` from `20260035` to
  `20260036`. Add the matching XML-doc paragraph to the version-history block immediately above
  (`Ft8LibInterop.cs:200-245`, same one-paragraph-per-version style already there for 20260031
  through 20260035).
- **Rebuild both shipped binaries** (`win-x64/libft8.dll` via `rebuild_shim.bat`, `linux-x64/libft8.so`
  via `build_linux.sh` under WSL — same pattern as the sibling native dev-tasks on this branch) with
  the gate left at its default (`FT8_ENABLE_RAW_LLR_CAPTURE` undefined/0). Update
  `libft8.version.txt` on both platform sections.

### 2.2 Add `ft8_get_shim_capabilities()` — a runtime capability bitmask

A version number is a single scalar; it cannot express "this binary was built with the diagnostic
compiled in." Add one new export that can:

- **Declaration** (`ft8_shim.h`, alongside `ft8_lib_version_check` at `ft8_shim.h:350`, same
  comment style):

  ```c
  /*
   * ft8_get_shim_capabilities — bitmask of build-time-optional capabilities compiled into
   * this binary. Bit 0 (0x1) = raw-LLR candidate capture (tls_diag_llr174,
   * FT8_ENABLE_RAW_LLR_CAPTURE) is compiled in. Remaining bits reserved (0 in every build
   * today). A version number alone cannot express this: shim 20260035/20260036 binaries
   * built with vs. without FT8_ENABLE_RAW_LLR_CAPTURE report the SAME FT8_SHIM_VERSION but
   * have different capability bitmasks (see the compile-time gate dev-task,
   * dev-tasks/2026-07-27-d001-gate-tls-diag-llr174-compile-time.md, and the version-
   * correction dev-task this comment belongs to).
   */
  int ft8_get_shim_capabilities(void);
  ```

- **Definition** (`ft8_shim.c`, immediately after `ft8_get_max_passes` at `ft8_shim.c:1080`):

  ```c
  #define FT8_CAP_RAW_LLR_CAPTURE 0x1  /* bit 0: tls_diag_llr174 compiled in */

  int ft8_get_shim_capabilities(void)
  {
      int caps = 0;
  #if FT8_ENABLE_RAW_LLR_CAPTURE
      caps |= FT8_CAP_RAW_LLR_CAPTURE;
  #endif
      return caps;
  }
  ```

  Placing `FT8_CAP_RAW_LLR_CAPTURE`'s `#define` here (rather than reusing a bare `0x1` in both the
  native and managed layers) keeps the bit's meaning named at the point it is actually set; the
  managed side gets its own equivalent constant (§2.3) rather than sharing this one across the P/Invoke
  boundary — there is no existing mechanism in this codebase for sharing C `#define`s with C#.

- **`rebuild_shim.bat`**: add `/EXPORT:ft8_get_shim_capabilities` to the `/EXPORT:` list
  (`native/ft8_lib_build/rebuild_shim.bat:41-44`, same block the `20260035` exports were added to).
  No change needed for the Linux/macOS builds — both auto-export every non-static symbol already
  (confirmed: `build_linux.sh` sets no `-fvisibility=hidden` and needed no export-list edit for the
  shim 20260035 exports either).

### 2.3 Managed: read capabilities at load time, log at startup, expose a public property

Mirror the existing `LoadedShimVersion` pattern (`Ft8LibInterop.cs:258-272`) exactly:

1. Add the P/Invoke declaration next to `NativeGetMaxPasses` (`Ft8LibInterop.cs:493-494`):
   ```csharp
   [DllImport("libft8.dll", EntryPoint = "ft8_get_shim_capabilities", CallingConvention = CallingConvention.Cdecl)]
   private static extern int NativeGetShimCapabilities();
   ```
2. Add a named constant for the bit, near `ExpectedShimVersion` (`Ft8LibInterop.cs:246`):
   ```csharp
   /// <summary>Bit 0 of <see cref="LoadedShimCapabilities"/>: raw-LLR candidate capture
   /// (<c>tls_diag_llr174</c>) is compiled into the loaded binary. See
   /// <c>ft8_get_shim_capabilities</c> in <c>ft8_shim.h</c>.</summary>
   internal const int RawLlrCaptureCapabilityBit = 0x1;
   ```
3. Add the backing field + public-surface property immediately after `LoadedShimVersion`
   (`Ft8LibInterop.cs:258-272`), same shape:
   ```csharp
   private static int _loadedShimCapabilities;

   /// <summary>
   /// Bitmask of build-time-optional capabilities compiled into the loaded native binary
   /// (see <see cref="RawLlrCaptureCapabilityBit"/>). Triggers lazy initialisation as a
   /// side effect if it has not already run, same as <see cref="LoadedShimVersion"/>.
   /// Unlike the version, this is NOT guaranteed equal across binaries reporting the same
   /// <see cref="ExpectedShimVersion"/> — that is precisely the gap this property closes.
   /// </summary>
   internal static int LoadedShimCapabilities
   {
       get
       {
           EnsureInitialized();
           return _loadedShimCapabilities;
       }
   }
   ```
4. In `LoadAndVerify()`, read it once, right after `_loadedShimVersion = actual;`
   (`Ft8LibInterop.cs:981`) and before the `K_MAX_PASSES` drift check — capabilities are as
   fundamental to "what is this binary" as the version is, so they belong next to it, not buried
   after the other checks:
   ```csharp
   _loadedShimCapabilities = NativeGetShimCapabilities();
   ```
5. **Forward on `Ft8Decoder`**, mirroring `LoadedShimVersion` exactly (`Ft8Decoder.cs:70`):
   ```csharp
   public static int LoadedShimCapabilities => Ft8LibInterop.LoadedShimCapabilities;
   ```
6. **Log at startup beside the version** (`src/OpenWSFZ.Daemon/Program.cs:292-293`):
   ```csharp
   var shimVersion      = Ft8Decoder.LoadedShimVersion;
   var shimCapabilities = Ft8Decoder.LoadedShimCapabilities;
   startupLogger.LogInformation(
       "Native FT8 decoder shim ABI version: {ShimVersion}, capabilities: 0x{Capabilities:X}.",
       shimVersion, shimCapabilities);
   ```

7. **Make `SetCandidateDiagLlrCapture(true)` throw when the loaded binary lacks the capability** —
   at the moment the workflow asks, not after it has collected a cycle of zeros. Edit
   `Ft8LibInterop.SetCandidateDiagLlrCapture` (`Ft8LibInterop.cs:735-739`):
   ```csharp
   public static void SetCandidateDiagLlrCapture(bool enable)
   {
       EnsureInitialized();
       if (enable && (_loadedShimCapabilities & RawLlrCaptureCapabilityBit) == 0)
           throw new InvalidOperationException(
               "Cannot enable raw-LLR candidate capture: the loaded native binary was built " +
               "without FT8_ENABLE_RAW_LLR_CAPTURE (LoadedShimCapabilities bit 0 is clear). " +
               "Rebuild libft8 with -DFT8_ENABLE_RAW_LLR_CAPTURE=1 for a diagnostic build — " +
               "see dev-tasks/2026-07-27-d001-gate-tls-diag-llr174-compile-time.md. " +
               "Never enable this against a shipped/production binary.");
       NativeSetCandidateDiagLlrCapture(enable ? 1 : 0);
   }
   ```
   **Only guard the `enable == true` case.** `Ft8Decoder.cs` re-asserts this call
   **unconditionally every decode cycle** regardless of whether the diagnostic is on
   (`Ft8Decoder.cs:402`, `_interop.SetCandidateDiagLlrCapture(_candidateDiagLlrCaptureEnabled)`) —
   production's default `_candidateDiagLlrCaptureEnabled == false` must keep working as a silent
   no-op against every binary, gated or not. The throw only fires the cycle after a workflow
   explicitly calls `Ft8Decoder.SetCandidateDiagLlrCapture(true)` — it surfaces on the decode
   thread inside `Task.Run`, and `DecodeAsync`'s existing `try`/`catch` only catches
   `NativeAccessViolationException` (`Ft8Decoder.cs:375-408`), so this exception propagates to the
   caller uncaught, exactly the loud failure this task exists to produce.

### 2.4 Defence in depth — distinguish "capability absent" from "genuinely zero candidates"

§2.3.7's throw is the primary fix, but it lives entirely on the managed side and only fires when a
caller goes through `Ft8LibInterop.SetCandidateDiagLlrCapture`. The native export itself should not
rely on that being the only path in — make the gated-off return value self-describing:

- **Native** (`ft8_shim.c:1294-1305`, the `#else` branch of `ft8_get_last_candidate_llr`): return
  `-1` instead of `0`.
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
      return -1;  /* capability absent — distinct from 0 ("no rows"), see ft8_shim.h */
  #endif
  }
  ```
  Update this function's doc comment (`ft8_shim.h`, the `ft8_get_last_candidate_llr` block) to
  document the new `-1` contract explicitly.
- **Managed** (`Ft8LibInterop.cs:754-771`, `GetLastCandidateLlr174`): stop collapsing `n <= 0` to
  `[]`. `n == -1` (capability absent) must not be silently swallowed into the same empty result a
  legitimately-quiet cycle (`n == 0`) would produce:
  ```csharp
  public static float[][] GetLastCandidateLlr174()
  {
      EnsureInitialized();

      var flat = new float[MaxPass0Candidates * LlrPerCandidate];
      int n = NativeGetLastCandidateLlr(flat, MaxPass0Candidates);

      if (n == -1)
          throw new InvalidOperationException(
              "ft8_get_last_candidate_llr reports the loaded native binary lacks raw-LLR " +
              "capture capability (returned -1). This should be unreachable via " +
              "SetCandidateDiagLlrCapture(true), which already throws — reaching this means " +
              "something called the native export directly, bypassing that guard.");
      if (n <= 0) return [];

      var result = new float[n][];
      for (int i = 0; i < n; i++)
      {
          var row = new float[LlrPerCandidate];
          Array.Copy(flat, i * LlrPerCandidate, row, 0, LlrPerCandidate);
          result[i] = row;
      }
      return result;
  }
  ```
  Note this changes `if (n <= 0) return [];` to two checks — `n == -1` is now handled first and
  throws, then the remaining `n <= 0` (which after removing -1 only ever means `n == 0`) still
  returns `[]` exactly as before. No other line in this method changes.

**Do not touch `Ft8Decoder.cs`'s existing call sites beyond §2.3.5/§2.3.7** — the
`_candidateDiagLlrCaptureEnabled ? _interop.GetLastCandidateLlr174() : []` ternary at
`Ft8Decoder.cs:419` is unaffected: it already only calls `GetLastCandidateLlr174()` when the flag
is true, and by the time that line runs, §2.3.7's throw would already have fired earlier in the
same cycle if the binary lacked the capability — so in practice this branch of §2.4 is genuinely a
backstop, not a path any correctly-behaving caller should ever hit.

## 3. Scope discipline

Exactly what the Architect's handoff specified: one `#define` (version bump), one small export
(`ft8_get_shim_capabilities`), one managed constant (`RawLlrCaptureCapabilityBit`), one guard (the
§2.3.7 throw), plus §2.4's native/managed sentinel pair as defence in depth. **Not** a redesign of
the diagnostic surface — do not touch `ft8_set_llr_shrinkage`, the shrinkage-blend logic in
`decode.c`, or any of the shim-20260034 scalar diagnostics.

## 4. Acceptance criteria

- [ ] `FT8_SHIM_VERSION` (`ft8_shim.h`) and `ExpectedShimVersion` (`Ft8LibInterop.cs`) both read
      `20260036`; version-history comment blocks updated in both files.
- [ ] **The ABI check must reject a 20260035 binary.** Loading either of the two just-committed
      (`7c90638`) `20260035` binaries against the new `20260036`-expecting managed code must throw
      `InvalidOperationException` from `LoadAndVerify`. (Trivially true once the bump lands and the
      binaries are rebuilt — verify by NOT rebuilding one platform's binary first and confirming
      the mismatch throws, then rebuild it.)
- [ ] `ft8_get_shim_capabilities()` exported on all three platforms (Windows via
      `rebuild_shim.bat`'s new `/EXPORT:` line; Linux/macOS automatically).
- [ ] A **gate-off** (shipped/default) build reports `LoadedShimCapabilities` with bit 0
      (`RawLlrCaptureCapabilityBit`) **clear**.
- [ ] A **gate-on** (`-DFT8_ENABLE_RAW_LLR_CAPTURE=1`, local/throwaway) build reports bit 0 **set**.
      Do not commit a gate-on binary.
- [ ] `Ft8LibInterop.SetCandidateDiagLlrCapture(true)` throws `InvalidOperationException` against a
      gate-off binary; `SetCandidateDiagLlrCapture(false)` never throws, against any binary.
- [ ] `Ft8LibInterop.GetLastCandidateLlr174()` throws `InvalidOperationException` when the native
      export returns `-1`; still returns `[]` for a genuine `0`.
- [ ] Startup log line includes both the version and the capability bitmask
      (`src/OpenWSFZ.Daemon/Program.cs`).
- [ ] `Ft8Decoder.LoadedShimCapabilities` forwards `Ft8LibInterop.LoadedShimCapabilities`.
- [ ] Both shipped binaries rebuilt at `20260036`, gate off, and `libft8.version.txt` updated on
      both platform sections.
- [ ] The existing 297-test suite stays green, both Windows and WSL, against the rebuilt binaries.
- [ ] **New tests added against the real (non-mock) interop**, not just the eight mock-based files
      — per the Architect's note: all eight existing test files touching `GetLastCandidateLlr174`
      do so through mocks of `IFt8NativeInterop`, so a green mocked suite alone proves nothing about
      the native surface. Add to `tests/OpenWSFZ.Ft8.Tests/Ft8LibInteropTests.cs` (the existing
      home of the real, non-mocked `LoadedShimVersion` tests):
      - `LoadedShimCapabilities` bit 0 is clear against the committed (gate-off) binary.
      - `SetCandidateDiagLlrCapture(true)` throws `InvalidOperationException` against the committed
        binary (and that the exception message names the missing capability, not a generic
        failure).
      - `SetCandidateDiagLlrCapture(false)` does not throw.
      Real coverage for the everyday (non-diagnostic) path continues to come from
      `Ft8Decoder.cs:402-403`'s unconditional every-cycle calls plus the real-interop decode tests,
      as already noted in the Architect's handoff.
- [ ] `git diff --stat` shows changes confined to: `ft8_shim.h`, `ft8_shim.c`, `rebuild_shim.bat`,
      both shipped binaries, `libft8.version.txt`, `Ft8LibInterop.cs`, `Ft8Decoder.cs`,
      `Program.cs`, and the new/edited test file(s). No change to `decode.c`, `IFt8NativeInterop.cs`,
      `Ft8NativeInteropAdapter.cs`, or `Ft8CandidateDiagnostic.cs` — none of those need to know
      about capabilities; the guard lives entirely in the static `Ft8LibInterop` class that already
      owns the ABI self-test.
- [ ] **Not on this checklist, deliberately:** `pre_merge_check.py` (QA's own step, HK-006/HK-011).

## 5. References

- `qa/cycleframer-alignment-replay/2026-07-27-1752-architect-to-qa-consolidated-handoff.md` §4 Q1 —
  the task this implements, including the four-part design content reproduced/expanded here.
- `2026-07-27-1738-architect-version-correction.md` — the original correction this sharpens.
- `dev-tasks/2026-07-27-d001-gate-tls-diag-llr174-compile-time.md` — the compile-time gate this
  dev-task is closing the version-observability gap for; do not re-touch its scope (the
  `tls_diag_llr174` array itself, `ft8_set_llr_shrinkage`, or the shim-20260034 scalar group).
- `c97ce90` — the Architect's acceptance of the gate, which found and named the silent-zero defect
  this dev-task's §2.3.7/§2.4 fixes.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs:375-408` — `DecodeAsync`'s try/catch, showing only
  `NativeAccessViolationException` is caught, so §2.3.7's throw propagates uncaught as intended.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:258-272` — the `LoadedShimVersion` pattern this
  dev-task's `LoadedShimCapabilities` mirrors exactly.
- `tests/OpenWSFZ.Ft8.Tests/Ft8LibInteropTests.cs:168-210` — the existing real (non-mock)
  `LoadedShimVersion` tests; add the new capability tests alongside them, same style.

---

*Per HK-011, this is `src/`-and-native work — stays in a Developer session, diff reviewed by QA,
Captain sign-off before push. Per HK-014/HK-015 convention applied to Developer sessions in this
thread, nothing is pushed or merged from here; hand the diff back to QA when done.*
