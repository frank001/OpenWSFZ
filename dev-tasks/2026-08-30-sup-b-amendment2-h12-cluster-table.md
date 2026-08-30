# Developer handoff: `SUP-B` Amendment 2 — the per-code (`n12`) cluster table Sec.6.2 needs

**Authored by:** QA (per HK-000/HK-015/HK-011). **Status:** ready for a Developer session.
**Source specs:**
`qa/rr-study/2026-08-30-1608-architect-to-qa-spec-f001-sup-b-amendment-2-cluster-instrumentation.md`
("Amendment 2") Sec.B2/B2.1/B2.2/B2.3/B3, and
`qa/rr-study/2026-08-30-1617-architect-to-qa-spec-f001-sup-b-amendment-2-execution-pack.md`
("the execution pack") Sec.C2 — **the execution pack's 8-file table is what this handoff
implements file-for-file.**
**Branch:** `qa/sup-b-2026-08-30`, currently at `5c01d60` (the execution pack's own commit).
Working tree confirmed clean (`git status`) before this handoff was written.

🛑 **QA proposes this diff and stops here (HK-011). QA does not edit `src/` or `native/`, does not
build, does not run `pre_merge_check.py` (HK-006 — Captain's initiative only).** A separate
Developer session applies this, builds both platforms, and runs the existing test suite. The
Captain reviews the diff before any push. QA returns afterward to pin the new `INST` SHA256 into
the spec's Sec.4 manifest and run the amended ROW 0 (execution pack Sec.C4) on `S-17M` — that is
QA's, not the Developer's.

**MEASURE-ONLY, and narrower than it looks.** This is a second pass over code this same branch
already instrumented once (shim `20260046` → `20260047`, the three scalar counters). This pass adds
**one thing**: a fixed 4,096-row per-code table recording the SAME three quantities **broken out by
the 12-bit code**, because Sec.6.2's cluster bootstrap needs cluster *identity*, and three cumulative
scalars carry none. After this change, decode output is still byte-for-byte identical to before —
same names displayed, same decodes, same everything. Nothing here implements, enables, or flags the
unique-match suppression rule itself.

---

## 0. Eight files, pre-registered — do not add a ninth

| # | file | change |
|---|---|---|
| 1 | `src/OpenWSFZ.Ft8/Native/ft8_shim.c` | Three edits: §1.1–1.3 below. |
| 2 | `src/OpenWSFZ.Ft8/Native/ft8_shim.h` | New export declaration + `FT8_SHIM_VERSION` → `20260048`. §2 below. |
| 3 | 🔴 `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` | **Line 385, `ExpectedShimVersion` → `20260048`, plus its changelog comment. NOTHING ELSE in this file.** §3 below. |
| 4 | `native/ft8_lib_build/rebuild_shim.bat` | One `/EXPORT:ft8_get_h12_by_code` line after the current line 157. §4 below. |
| 5 | `src/OpenWSFZ.Ft8/Native/BUILD.md` | Same entry in its own export list. §5 below. |
| 6 | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` | New top entry: `20260048`, both SHA256, date. **§6 corrects the execution pack's own path** — it names `src/OpenWSFZ.Ft8/Native/libft8.version.txt`, but the file that actually exists on disk is one level down, at `win-x64/`. Verified by listing the directory before writing this handoff (HK-018); there is no second copy elsewhere to reconcile. |
| 7 | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | Rebuilt (Windows). |
| 8 | `src/OpenWSFZ.Ft8/Native/linux-x64/libft8.so` | Rebuilt (WSL2 Debian, `build_linux.sh`). |

🛑 **`IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs` and all 11 implementers of
`IFt8NativeInterop` are NOT in this list and MUST NOT be touched.** If partway through this you find
yourself editing a test double or adding a member to that interface, **the design has been
misread — stop and escalate rather than "helpfully" wire it up.** The reason, stated so it isn't
rediscovered as a surprise: the Sec.6 reading is produced by
`qa/cycleframer-alignment-replay/g2_verification_replay.py`/`g3_h12_replay.py` driving the named DLL
**directly by ctypes**, the same route the three scalars already use — it does not go through
`IFt8NativeInterop` at all, so a 4,096-row table has no place there. QA extends the Python replay
harness separately (execution pack Sec.C3); that is qa-tooling and not part of this handoff.

⚠️ **A bare `ExpectedShimVersion` bump with no other managed edit is the CORRECT outcome this
time, not an oversight.** Last time (`20260046` → `20260047`) it was a genuine miss, caught only
after it cascaded into 131 `Daemon.Tests` + 76 `Web.Tests` failures. This time it is correct **by
design** — the new export has no C# caller — so do not add one out of habit.

---

## 1. Native change — `src/OpenWSFZ.Ft8/Native/ft8_shim.c`

All three edits are additive, inside blocks that are already there from the prior (`20260047`)
pass. Confirmed against the actual current file before writing this (HK-018) — the anchors below
are today's real line numbers on `qa/sup-b-2026-08-30`, not carried over from the spec unchecked.

### 1.1 The table, beside the three existing scalars (currently `:716–720`)

Current file, unchanged text shown for anchoring:

```c
/* SUP-B (shim 20260047): the three counters spec Sec.3.1 defines. Same
 * best-effort, not-thread-local convention as g_hash_table_reject_count. */
static int g_h12_displaying = 0;
static int g_h12_ambiguous  = 0;
static int g_h12_divergent  = 0;
```

Add immediately after the third counter (before the following blank line and
`hash_table_add`'s definition):

```c

/* SUP-B Amendment 2 (shim 20260048): per-code (n12) cluster table for Sec.6.2's
 * clustered bootstrap. The 12-bit code is already in scope at the counting site
 * (cb_lookup_hash) and the code space is exactly 4096 by construction, so this
 * is a fixed-size static array -- no allocation, no growth, no hashing, no
 * iteration order. A complete sufficient statistic for the bootstrap;
 * per-lookup rows are NOT produced. Same best-effort, not-thread-local
 * convention as g_hash_table_reject_count and the three scalars above. */
#define H12_CODE_SPACE 4096          /* 12-bit hash type: codes are 0..4095 by construction */
static int      g_h12_by_code_displaying[H12_CODE_SPACE];
static int      g_h12_by_code_ambiguous [H12_CODE_SPACE];
static int      g_h12_by_code_divergent [H12_CODE_SPACE];
static int      g_h12_code_out_of_range = 0;   /* MUST stay 0 -- see ROW 0c-ii */
```

`static` array initialisation to all-zero is a C guarantee (BSS), so no explicit `memset` is
needed — mirrors `g_session_hash_table` below it.

### 1.2 One new thread-local, beside the existing per-message scratch (currently `:776–779`)

Current file:

```c
static _Thread_local bool tls_h12_lookup_performed = false;
static _Thread_local bool tls_h12_resolved         = false;
static _Thread_local int  tls_h12_multiplicity     = 0;
static _Thread_local bool tls_h12_divergent        = false;
```

Add a fifth field to the same group:

```c
static _Thread_local bool     tls_h12_lookup_performed = false;
static _Thread_local bool     tls_h12_resolved         = false;
static _Thread_local int      tls_h12_multiplicity     = 0;
static _Thread_local bool     tls_h12_divergent        = false;
static _Thread_local uint32_t tls_h12_code             = 0; /* SUP-B Amendment 2: the 12-bit code itself */
```

Then, in `cb_lookup_hash` (currently `:782–796`), the `if (t == FTX_CALLSIGN_HASH_12_BITS)` block
reads:

```c
    if (t == FTX_CALLSIGN_HASH_12_BITS) {
        tls_h12_lookup_performed = true;
        tls_h12_resolved         = found;
        if (found) {
            hash_table_count_h12_multiplicity(tls_hash_table, h, &tls_h12_multiplicity, &tls_h12_divergent);
        } else {
            tls_h12_multiplicity = 0;
            tls_h12_divergent    = false;
        }
    }
```

Add the code capture as the very next statement after `tls_h12_lookup_performed = true;`, **set
unconditionally in this branch, not only on `found`** (the table needs the code on every lookup
attempt through this path, matching how `tls_h12_lookup_performed`/`tls_h12_resolved` are already
set unconditionally here):

```c
    if (t == FTX_CALLSIGN_HASH_12_BITS) {
        tls_h12_lookup_performed = true;
        tls_h12_resolved         = found;
        tls_h12_code             = h; /* SUP-B Amendment 2: set unconditionally in this branch */
        if (found) {
            hash_table_count_h12_multiplicity(tls_hash_table, h, &tls_h12_multiplicity, &tls_h12_divergent);
        } else {
            tls_h12_multiplicity = 0;
            tls_h12_divergent    = false;
        }
    }
```

🛑 **Do not touch anything else in `cb_lookup_hash` or `hash_table_lookup`.** `hash_table_lookup`'s
body must stay byte-for-byte unchanged — that non-perturbation argument is what ROW 0b re-verifies,
and it is unchanged in kind by this amendment.

### 1.3 The increment, inside the existing emission-site block (currently `:1574–1578`)

Current file:

```c
            if (tls_h12_lookup_performed && tls_h12_resolved) {
                g_h12_displaying++;
                if (tls_h12_multiplicity >= 2) g_h12_ambiguous++;
                if (tls_h12_divergent)         g_h12_divergent++;
            }
```

**The guard condition (`if (tls_h12_lookup_performed && tls_h12_resolved)`) is UNCHANGED — do not
touch it.** Add the table-side increments inside the same block, after the three existing
scalar increments:

```c
            if (tls_h12_lookup_performed && tls_h12_resolved) {
                g_h12_displaying++;
                if (tls_h12_multiplicity >= 2) g_h12_ambiguous++;
                if (tls_h12_divergent)         g_h12_divergent++;

                /* SUP-B Amendment 2: cluster identity for Sec.6.2. Mask defensively
                 * so an out-of-range code can never write out of bounds -- and COUNT
                 * the violation, because masking alone would hide it (ROW 0c-ii is
                 * why this counter exists: masking preserves the SUM, so a mismasked
                 * code would still reconcile with 0c-iii's totals while cluster
                 * identity was silently scrambled). */
                if (tls_h12_code >= H12_CODE_SPACE) g_h12_code_out_of_range++;
                uint32_t c = tls_h12_code & (H12_CODE_SPACE - 1u);
                g_h12_by_code_displaying[c]++;
                if (tls_h12_multiplicity >= 2) g_h12_by_code_ambiguous[c]++;
                if (tls_h12_divergent)         g_h12_by_code_divergent[c]++;
            }
```

### 1.4 The new export

Add near `ft8_get_h12_divergent_count` (currently `:1176–1178`):

```c
/*
 * ft8_get_h12_by_code — SUP-B Amendment 2 (shim 20260048). Copies the full
 * 4096-row per-code cluster table into caller-supplied buffers. Returns
 * H12_CODE_SPACE (4096) on success; -1 if capacity < H12_CODE_SPACE or any
 * pointer (including out_of_range) is NULL -- caller must check for -1, not
 * assume success. *out_of_range receives g_h12_code_out_of_range (ROW 0c-ii).
 * Read-only, process-lifetime cumulative, zero on daemon restart, same
 * lifecycle as the three scalar getters above. Intended caller is the Python
 * replay harness by ctypes (once per run, at the end -- NOT per cycle: this
 * copies 48 KB, and per-cycle would add ~90 MB of copying per leg for
 * nothing), not IFt8NativeInterop -- see Ft8LibInterop.cs's own changelog
 * entry for why no C# binding exists.
 */
int ft8_get_h12_by_code(int* displaying, int* ambiguous, int* divergent,
                         int capacity, int* out_of_range)
{
    if (!displaying || !ambiguous || !divergent || !out_of_range || capacity < H12_CODE_SPACE)
        return -1;
    for (int c = 0; c < H12_CODE_SPACE; c++) {
        displaying[c] = g_h12_by_code_displaying[c];
        ambiguous[c]  = g_h12_by_code_ambiguous[c];
        divergent[c]  = g_h12_by_code_divergent[c];
    }
    *out_of_range = g_h12_code_out_of_range;
    return H12_CODE_SPACE;
}
```

This matches Amendment 2 Sec.B2.2's contract exactly (folding the out-of-range count into this one
call keeps the export count at 19 → 20, not 21).

---

## 2. Header — `src/OpenWSFZ.Ft8/Native/ft8_shim.h`

### 2.1 Declaration

Add next to `ft8_get_h12_divergent_count(void);` (currently `:745–747`):

```c
/*
 * ft8_get_h12_by_code — SUP-B Amendment 2 (shim 20260048). See ft8_shim.c for
 * the full doc comment. Process-global, read-only, process-lifetime
 * cumulative, zero on daemon restart. MEASURE-ONLY: no effect on decode
 * output. Returns H12_CODE_SPACE (4096) on success, -1 on any bad argument.
 */
int ft8_get_h12_by_code(int* displaying, int* ambiguous, int* divergent,
                         int capacity, int* out_of_range);
```

### 2.2 Version bump and changelog entry

Add a new entry to the running history block **immediately before** the current
`#define FT8_SHIM_VERSION 20260047` line (currently `:643`), i.e. right after the existing
`20260047` entry's last line (`... capacity or eviction policy.`) and before the closing `*/`:

```c
 *
 *   20260048 — f001-sup-b-amendment-2-cluster-instrumentation: adds one new
 *              exported read-only getter, ft8_get_h12_by_code(), returning a
 *              complete 4096-row per-code (n12) breakdown of the three
 *              20260047 scalars -- displaying/ambiguous/divergent counts
 *              indexed by the 12-bit callsign-hash code itself, plus an
 *              out-of-range violation count. Backs spec Sec.6.2's clustered
 *              95% bootstrap, which needs cluster IDENTITY, not just
 *              cumulative totals. Mechanism: one new thread-local
 *              (tls_h12_code, set unconditionally in cb_lookup_hash's
 *              existing 12-bit branch) and one new fixed 4096 x 3 static
 *              table incremented alongside the existing scalars, inside the
 *              SAME unchanged guard condition, at the SAME emission site.
 *              hash_table_lookup and cb_lookup_hash's return/output values
 *              are unaffected. No struct layout change, no ABI break to any
 *              existing export. The three 20260047 scalars are unchanged and
 *              remain the sufficient-statistic source for anything that does
 *              not need cluster identity.
 */
#define FT8_SHIM_VERSION 20260048
```

(Replacing the old `#define FT8_SHIM_VERSION 20260047` line with this one — the entry above it
stays, this only adds a new entry after it and bumps the number.)

---

## 3. Interop — `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`, ONE constant, nothing else

Current (`:385`):

```csharp
    private const int ExpectedShimVersion = 20260047;
```

Change to:

```csharp
    private const int ExpectedShimVersion = 20260048;
```

And add a new `/// <remarks>` block immediately after the existing `20260047` remarks block
(currently ending `:384`, just above the `private const int ExpectedShimVersion` line):

```csharp
    /// <remarks>
    /// f001-sup-b-amendment-2-cluster-instrumentation, shim 20260048: adds one new exported
    /// read-only getter, <c>ft8_get_h12_by_code</c>, returning a 4096-row per-code breakdown of
    /// the three shim-20260047 scalars. This binding is DELIBERATE: <c>ft8_get_h12_by_code</c>
    /// is NOT added to <see cref="IFt8NativeInterop"/>, has no <c>DllImport</c> here, and no C#
    /// caller anywhere. The reading that needs it (spec Sec.6.2's clustered bootstrap) is
    /// produced by the Python/ctypes replay harness driving the native DLL directly, the same
    /// route the three 20260047 scalars already use for that purpose — a 4096-row table has no
    /// place in an FR-019 log line, which is the only thing the managed counters serve. This
    /// bump exists solely as the ABI self-test: <see cref="ExpectedShimVersion"/> must track
    /// <c>FT8_SHIM_VERSION</c> on every native change regardless of whether the new export gets
    /// a managed binding, per the pattern every prior entry in this file follows.
    /// </remarks>
    private const int ExpectedShimVersion = 20260048;
```

🛑 **Do not add a `DllImport`, an `IFt8NativeInterop` member, an adapter method, a `Ft8Decoder`
wrapper, or a test-double stub anywhere for `ft8_get_h12_by_code`.** That is the entire point of
Sec.B3 — the C# interop needs nothing but this one constant.

---

## 4. Native build — `native/ft8_lib_build/rebuild_shim.bat`

Current (`:139–157`, 19 exports):

```bat
  /EXPORT:ft8_lib_version_check ^
  /EXPORT:ft8_decode_all ^
  /EXPORT:ft8_get_last_pass_counts ^
  /EXPORT:ft8_get_max_passes ^
  /EXPORT:ft8_get_last_noise_floor_db ^
  /EXPORT:ft8_encode_message ^
  /EXPORT:ft8_get_last_candidate_counts ^
  /EXPORT:ft8_get_last_llr_stats ^
  /EXPORT:ft8_set_ap_bits ^
  /EXPORT:ft8_set_decode_params ^
  /EXPORT:ft8_get_hash_table_reject_count ^
  /EXPORT:ft8_refine_candidate ^
  /EXPORT:ft8_extract_llrs_at ^
  /EXPORT:ft8_coherent_llr_at ^
  /EXPORT:ft8_ldpc_decode_llrs ^
  /EXPORT:ft8_get_last_snr_terms ^
  /EXPORT:ft8_get_h12_displaying_count ^
  /EXPORT:ft8_get_h12_ambiguous_count ^
  /EXPORT:ft8_get_h12_divergent_count ^
```

Add one line after `ft8_get_h12_divergent_count` (i.e. after the current line 157), before the
`.obj` list:

```bat
  /EXPORT:ft8_get_h12_by_code ^
```

20 exports total after this change.

---

## 5. Documentation — `src/OpenWSFZ.Ft8/Native/BUILD.md`

Same list, its own copy (`:154–172`). Add the matching line after `ft8_get_h12_divergent_count`
(currently `:172`), before the `.obj` list on the next line:

```
   /EXPORT:ft8_get_h12_by_code ^
```

⚠️ **Pre-existing drift found while writing this handoff (HK-018), NOT part of this task's scope
and not to be fixed here:** `BUILD.md`'s export list is already missing `ft8_get_last_snr_terms`
(present in `rebuild_shim.bat` since shim `20260045`, never backfilled here) — so `BUILD.md`
currently lists 18 exports where `rebuild_shim.bat` lists 19, and will list 19 where
`rebuild_shim.bat` lists 20 after this change. **Add only the one line named above; do not
backfill the pre-existing `ft8_get_last_snr_terms` gap as part of this diff** — that would be an
unregistered ninth-file-shaped change to a task pre-registered at eight files (execution pack
Sec.C2/Amendment 2 Sec.B3). Flagging it here is itself the fix for now; a separate small task can
backfill it later if anyone decides that's worth doing.

---

## 6. Version log — `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`

New top entry, above the current `=== CURRENT: f001-sup-b-instrumented-suppression-sizing
(FT8_SHIM_VERSION 20260047) ===` block (which becomes the second entry, unedited except that it is
no longer marked `CURRENT`). Follow this file's own established format exactly (see the existing
`20260047` entry for the pattern this mirrors) — fill in the two SHA256 values, the exact MSVC/GCC
compiler versions actually used, and the actual `dotnet test` result once you have them; do not
invent numbers. Suggested body, adapt as needed once real values are in hand:

```
=== CURRENT: f001-sup-b-amendment-2-cluster-instrumentation (FT8_SHIM_VERSION 20260048) ===

Built <DATE> from branch qa/sup-b-2026-08-30, on top of the
f001-sup-b-instrumented-suppression-sizing pin at shim 20260047 (SHA256
37cbb4acb93c0006d65c40defb0da21366160d3a6b07e283660eed358bd6ac26), per QA's Developer handoff
(dev-tasks/2026-08-30-sup-b-amendment2-h12-cluster-table.md, implementing
qa/rr-study/2026-08-30-1608-architect-to-qa-spec-f001-sup-b-amendment-2-cluster-instrumentation.md
Sec.B2 and qa/rr-study/2026-08-30-1617-architect-to-qa-spec-f001-sup-b-amendment-2-execution-pack.md
Sec.C2).

MEASURE-ONLY. Adds one new exported read-only getter, ft8_get_h12_by_code(), returning a complete
4096-row per-code (n12) breakdown of the three shim-20260047 scalars -- displaying/ambiguous/
divergent counts indexed by the 12-bit callsign-hash code, plus an out-of-range violation count.
Backs spec Sec.6.2's clustered 95% bootstrap over distinct n12 codes, which the three cumulative
scalars alone could not identify.

Mechanism: one new thread-local (tls_h12_code), set unconditionally inside cb_lookup_hash's
existing FTX_CALLSIGN_HASH_12_BITS branch; one new fixed 4096 x 3 static table
(g_h12_by_code_displaying/ambiguous/divergent) plus a g_h12_code_out_of_range counter, incremented
inside the SAME unchanged guard condition, at the SAME emission site, as the three existing
scalars. hash_table_lookup's body, cb_lookup_hash's return value, and the existing three scalars
are all byte-for-byte unchanged. No struct layout change (this is a new file-scope static array,
not a change to any existing struct). No C# binding -- the reading is produced by the Python/
ctypes replay harness directly; see Ft8LibInterop.cs's own changelog entry for why.

  Windows x64 (rebuild_shim.bat, MSVC <VERSION>): SHA256
    <FILL IN>
  Linux x64   (build_linux.sh, GCC <VERSION> via WSL2 Debian): SHA256
    <FILL IN>
  macOS ARM64: NOT rebuilt this session -- no Mac available locally, same limitation every prior
    native change in this project's history has recorded. Non-blocking: CI's
    `commit-native-binaries` job rebuilds macOS from source and auto-commits the result on every
    push that changes native sources -- this branch has not been pushed yet (HK-014/HK-011:
    Developer sessions build and test only, they do not push). The osx-arm64/libft8.dylib
    currently committed remains at its pre-this-change shim version until that push happens; do
    not treat it as shim-20260048-compatible before then.

  `dumpbin /exports` (Windows) confirms all TWENTY exported symbols present -- the nineteen
  pre-existing symbols unchanged, plus the one new ft8_get_h12_by_code -- and it is the ONLY
  addition. `nm -D` (Linux) confirms the same twenty plus ft8_encode (ELF's
  default-export-all-non-static behaviour, pre-existing, not part of this change).

  Local `dotnet build` + full `dotnet test` (excluding pre_merge_check.py, per HK-006/HK-011):
  <FILL IN — expect OpenWSFZ.Ft8.Tests at the same 319/319 as the prior pass, since no test file
  changes; note whether the previously-observed CycleArchiveServiceTests / FR-064
  ExternalReportingServiceTests flakes recur, and if so confirm zero file overlap as the prior
  passes did before treating them as unrelated>.

  NOTE: `ExpectedShimVersion` in Ft8LibInterop.cs was bumped to 20260048 alongside the shim
  version, with NO other managed-side change (§3 above) -- this is the deliberately correct
  outcome for this pass, unlike the prior pass where the bump alone (with a genuinely-needed
  managed binding elsewhere) was initially missed.
```

---

## 7. Definition of done

- [ ] §1's three `ft8_shim.c` edits made exactly as specified; `hash_table_lookup` and
      `cb_lookup_hash`'s existing return-path logic are byte-for-byte unchanged apart from the one
      added `tls_h12_code = h;` line (diff against the branch's current HEAD `5c01d60` and confirm
      nothing else in either function's body moved).
- [ ] §2's `ft8_shim.h` declaration and version-history entry added; `FT8_SHIM_VERSION` bumped to
      `20260048`.
- [ ] §3's ONE constant + comment change in `Ft8LibInterop.cs` — confirm via `git diff --stat`
      that this file's diff touches only this region, and that `IFt8NativeInterop.cs`,
      `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`, and all 11 implementers do not appear in the
      diff at all.
- [ ] §4/§5's export-list line added to both `rebuild_shim.bat` and `BUILD.md` (the one new line
      only — do not backfill BUILD.md's pre-existing `ft8_get_last_snr_terms` gap, §5 above).
- [ ] §6's version-log entry added with real SHA256/compiler/test values, not placeholders.
- [ ] Windows build: `dumpbin /exports` shows exactly **20** exported symbols, the 19 prior ones
      plus `ft8_get_h12_by_code`, and no others.
- [ ] Linux build (WSL2 Debian, `build_linux.sh`): `nm -D` shows the same 20 plus `ft8_encode`
      (pre-existing ELF default-export behaviour, not new).
- [ ] `dotnet test` — full suite run, not just `OpenWSFZ.Ft8.Tests` (a native change is exactly the
      kind of change that could have an unexpected interaction elsewhere; do not assume
      isolation). Record the result even if a pre-existing unrelated flake (FR-064's
      `ExternalReportingServiceTests`, or the `CycleArchiveServiceTests` one) recurs — that is a
      known, separately-tracked issue and does not block this diff, but must be reported, not
      silently absorbed.
- [ ] `git diff --stat` against the branch's current HEAD (`5c01d60`) touches only the 8 files in
      §0's table — nothing else. In particular: no test file added or edited (no new managed
      binding exists to test), no `IFt8NativeInterop`-family file touched.
- [ ] Committed on `qa/sup-b-2026-08-30`. **Does not push, does not merge, does not run
      `pre_merge_check.py`** (HK-006/HK-011/HK-014).
- [ ] Present the diff to QA / the Captain for review before any push, per HK-011.

Once committed, control returns to QA (execution pack Sec.C7.1 steps 3–5): pin the new `INST`
SHA256 into the spec's Sec.4 manifest, confirm `git diff --stat` is empty, extend the replay
harness and evaluator (execution pack Sec.C3/C4 — qa-tooling, not part of this handoff), and run
the full amended ROW 0 on `S-17M`.

---

## 8. Cross-references

- `qa/rr-study/2026-08-30-1608-architect-to-qa-spec-f001-sup-b-amendment-2-cluster-instrumentation.md`
  — Sec.B2 (the edits), Sec.B2.2 (the export contract), Sec.B2.3 (the interop line, named
  explicitly there too), Sec.B3 (why the interop needs nothing else).
- `qa/rr-study/2026-08-30-1617-architect-to-qa-spec-f001-sup-b-amendment-2-execution-pack.md` —
  Sec.C2 (the 8-file table this handoff implements), Sec.C7.1 (the sequence this handoff is step 2
  of).
- `dev-tasks/2026-08-30-sup-b-h12-instrumentation.md` — the immediately prior handoff (shim
  `20260047`) this one builds on; its C# interop section (§4/§5/§6) is exactly what is **not**
  repeated here, per Sec.B3's finding that this pass needs none of it.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — anchors as of `5c01d60`: scalars/table `:716-720`,
  per-message scratch `:776-780`, `cb_lookup_hash` `:781-796`, emission-site increment block
  `:1569-1578`, existing getters `:1176-1178`. Search anchors are given throughout instead of
  trusting line numbers to survive the edit.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — declarations `:745-747`, version history block ending
  `:643`.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:385` — the ABI sentinel this handoff bumps.
