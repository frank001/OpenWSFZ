# Developer handoff: `f001-h12-unique-match-suppression` — Option A, the unconditional unique-match rule

**Authored by:** QA (per HK-000/HK-015/HK-011). **Status:** ready for a Developer session.
**Source brief:** `qa/rr-study/2026-09-01-1949-architect-to-qa-brief-f001-option-a-unique-match-suppression.md`
(Architect, commit `265aba5`).
**Decision authority:** `qa/rr-study/2026-09-01-1510-po-decision-f001-sup-b-step7-option-a.md`
(PO, "NO NAME BEATS A WRONG NAME").
**OpenSpec change:** `openspec/changes/f001-h12-unique-match-suppression/` (opened, commit `d83dcc9`,
`openspec validate --strict --all` 63/0). This handoff implements that change's `tasks.md` §1–§6.
**Branch:** `feat/f001-h12-unique-match-suppression`, already checked out, already carries the brief
and the openspec entry. **Continue on this branch — do not cut a new one.**

🛑 **QA proposes this diff and stops here (HK-011). QA does not edit `src/` or `native/`, does not
build, does not run `pre_merge_check.py` (HK-006 — Captain's initiative only).** A separate Developer
session applies this, builds, and runs the existing test suite. The Captain reviews the diff before
any push. QA returns afterward to run the replay-based AC-1–AC-4 (tasks.md §7–§8) — that is QA's, not
the Developer's.

Every line reference below was re-read on this branch's current tree immediately before writing this
document (HK-018/HK-022) — not taken on the brief's word. Where a line number in the brief was
approximate, the exact current number is given here instead.

---

## 1. What this changes, in one sentence

`cb_lookup_hash` (`src/OpenWSFZ.Ft8/Native/ft8_shim.c`) already computes, one statement above its own
`return`, how many entries in the session hash table match a 12-bit callsign-hash reference. Today it
returns `found` regardless of that count. After this change it returns `found` **only when that count
is exactly 1** — an ambiguous match (≥2 candidates) renders the existing `<...>` placeholder instead of
a (possibly wrong) name, and the decode itself is kept. **`native/ft8_lib_vendor/` is not touched** —
`message.c`'s own `lookup_callsign`/`decode_nonstd` already do the right thing with a "not found" 12-bit
lookup (brief §2, re-verified below in §0).

## 0. Re-verification of the brief's §2 correction (do not re-derive — trust this, or re-check yourself)

`native/ft8_lib_vendor/ft8/message.c:594-614` — `lookup_callsign`:

```c
static bool lookup_callsign(const ftx_callsign_hash_interface_t* hash_if, ftx_callsign_hash_type_t hash_type, uint32_t hash, char* callsign)
{
    char c11[12];
    bool found;
    if (hash_if != NULL)
        found = hash_if->lookup_hash(hash_type, hash, c11);
    else
        found = false;
    if (!found)
    {
        strcpy(callsign, "<...>");
    }
    else
    {
        add_brackets(callsign, c11, strlen(c11));
    }
    ...
    return found;
}
```

`message.c:431`, inside `decode_nonstd` (the Type 4 handler), is the **only** 12-bit call site, and it
**discards the return value**:

```c
    lookup_callsign(hash_if, FTX_CALLSIGN_HASH_12_BITS, n12, call_3);
```

⇒ a `false` return from `cb_lookup_hash` on the 12-bit branch is not an error path: `call_3` becomes
`"<...>"`, `decode_nonstd` still returns `FTX_MESSAGE_RC_OK`. Confirmed independently, matches brief §2
exactly. **No vendor change in this task.**

## 2. Native change — `src/OpenWSFZ.Ft8/Native/ft8_shim.c`

### 2.1 The suppression flag, added to the existing 12-bit scratch block

Anchor — the existing `_Thread_local` scratch block, currently at lines 789–793:

```c
static _Thread_local bool     tls_h12_lookup_performed = false;
static _Thread_local bool     tls_h12_resolved         = false;
static _Thread_local int      tls_h12_multiplicity     = 0;
static _Thread_local bool     tls_h12_divergent        = false;
static _Thread_local uint32_t tls_h12_code             = 0; /* SUP-B Amendment 2: the 12-bit code itself */
```

Add one more line immediately after `tls_h12_code`:

```c
static _Thread_local bool     tls_h12_suppressed       = false; /* f001-h12-unique-match-suppression D3 */
```

### 2.2 `cb_lookup_hash` — the predicate and the return

Anchor — currently lines 796–811, unchanged apart from what's marked:

```c
static bool cb_lookup_hash(ftx_callsign_hash_type_t t, uint32_t h, char* cs) {
    if (!tls_hash_table) { cs[0] = '\0'; return false; }
    bool found = hash_table_lookup(tls_hash_table, t, h, cs); /* UNCHANGED return path -- TRAP 1 */
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
    return found;
}
```

Change to:

```c
static bool cb_lookup_hash(ftx_callsign_hash_type_t t, uint32_t h, char* cs) {
    if (!tls_hash_table) { cs[0] = '\0'; return false; }
    bool found = hash_table_lookup(tls_hash_table, t, h, cs); /* UNCHANGED return path -- TRAP 1 */
    if (t == FTX_CALLSIGN_HASH_12_BITS) {
        tls_h12_lookup_performed = true;
        tls_h12_resolved         = found; /* f001-h12-unique-match-suppression D3: "the table
                                            * resolved it" -- unchanged meaning, NOT gated on
                                            * suppression. SUP-B's counters depend on this. */
        tls_h12_code             = h; /* SUP-B Amendment 2: set unconditionally in this branch */
        if (found) {
            hash_table_count_h12_multiplicity(tls_hash_table, h, &tls_h12_multiplicity, &tls_h12_divergent);
            /* f001-h12-unique-match-suppression D1/D2: "NO NAME BEATS A WRONG NAME" -- suppress
             * (return not-found) when the probe chain holds >=2 candidates. Multiplicity, NOT
             * divergence (divergent is a strictly narrower signal SUP-B kept separate). Do not
             * touch cs: it already holds hash_table_lookup's resolved callsign, and
             * lookup_callsign (message.c:594) overwrites it with "<...>" on a false return and
             * never reads it again -- clearing it here would be redundant, not "helpful". */
            tls_h12_suppressed = (tls_h12_multiplicity >= 2);
        } else {
            tls_h12_multiplicity = 0;
            tls_h12_divergent    = false;
            tls_h12_suppressed   = false;
        }
    }
    return found && !tls_h12_suppressed; /* f001-h12-unique-match-suppression D1: the ONLY line
                                           * that changes decode output in this whole diff. */
}
```

🔴 **Confirm before editing:** `hash_table_lookup`, `hash_table_add`, `announce_stamp` and
`hash_table_count_h12_multiplicity` are all **untouched** by this section — this is the entire
mechanical content of design D2's must-not-change list and tasks.md 1.3/1.6.

### 2.3 Reset the new flag alongside the rest of the scratch (TRAP 3)

Anchor — currently line 1603, inside `ft8_decode_all`'s per-candidate loop, immediately before the
text-decode attempt:

```c
            char text[FTX_MAX_MESSAGE_LENGTH + 1];
            tls_h12_lookup_performed = false; /* SUP-B TRAP 3: fresh scratch for THIS message */
            if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
                continue;
```

Change to:

```c
            char text[FTX_MAX_MESSAGE_LENGTH + 1];
            tls_h12_lookup_performed = false; /* SUP-B TRAP 3: fresh scratch for THIS message */
            tls_h12_suppressed       = false; /* f001-h12-unique-match-suppression: same bracket,
                                                * so it can never leak between messages */
            if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
                continue;
```

(`cb_lookup_hash` always sets `tls_h12_suppressed` explicitly on every 12-bit invocation, so this
reset is defence-in-depth per tasks.md 1.1 rather than strictly load-bearing — do it anyway, matching
the existing scratch's own convention.)

### 2.4 The process-lifetime counter and its getter

Anchor — the three existing `g_h12_*` counters, currently lines 716–720:

```c
/* SUP-B (shim 20260047): the three counters spec Sec.3.1 defines. Same
 * best-effort, not-thread-local convention as g_hash_table_reject_count. */
static int g_h12_displaying = 0;
static int g_h12_ambiguous  = 0;
static int g_h12_divergent  = 0;
```

Add a fourth counter immediately after:

```c
/* f001-h12-unique-match-suppression (shim 20260049): how many of g_h12_ambiguous's displays
 * were actually suppressed (== all of them, by design -- see the getter's own comment below
 * for why this is a wiring invariant, not new information). */
static int g_h12_suppressed = 0;
```

Getter — anchor is the three existing getters, currently lines 1191–1193:

```c
int ft8_get_h12_displaying_count(void) { return g_h12_displaying; }
int ft8_get_h12_ambiguous_count(void)  { return g_h12_ambiguous; }
int ft8_get_h12_divergent_count(void)  { return g_h12_divergent; }
```

Add immediately after:

```c
/*
 * ft8_get_h12_suppressed_count -- f001-h12-unique-match-suppression (shim 20260049).
 * Process-lifetime count of EMITTED decodes whose 12-bit callsign was suppressed (probe chain
 * multiplicity >= 2). Incremented at the EMISSION point, never in cb_lookup_hash (design D4 /
 * SUP-B TRAP 3 again -- the callback also fires for messages whose ftx_message_decode later
 * fails and is discarded; counting there would measure decode ATTEMPTS, not displays). By
 * construction this is arithmetically identical to ft8_get_h12_ambiguous_count() on every run --
 * it is a WIRING INVARIANT between the decision site (cb_lookup_hash) and the counting site
 * (the emission block), not new information: a divergence between the two proves a wiring
 * fault; it cannot detect an error in the multiplicity computation itself, since both counters
 * descend from the same tls_h12_multiplicity (AC-5's behavioural scenarios cover that instead).
 * Read-only, process-global, zero on daemon restart, same lifecycle as its three siblings.
 */
int ft8_get_h12_suppressed_count(void) { return g_h12_suppressed; }
```

### 2.5 Increment the counter at the emission point — never in the callback

Anchor — currently lines 1611–1632, the emission block (unchanged apart from the one marked line):

```c
            /* SUP-B (shim 20260047): from here on this message is unconditionally
             * headed for results[] below (nothing between here and there can still
             * discard it) -- this IS the emission point ROW 0d checks against, not
             * the ftx_message_decode call above. Count DISPLAYS, not decode
             * attempts (TRAP 3, HK-022). */
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

Add one line beside `g_h12_ambiguous++` (do not touch anything else in this block — the guard
condition `tls_h12_lookup_performed && tls_h12_resolved` stays exactly as it is, per design D3:
`tls_h12_resolved` means "the table resolved it", not "and it was displayed unsuppressed"):

```c
                g_h12_displaying++;
                if (tls_h12_multiplicity >= 2) g_h12_ambiguous++;
                if (tls_h12_divergent)         g_h12_divergent++;
                if (tls_h12_suppressed)        g_h12_suppressed++; /* f001-h12-unique-match-suppression */
```

🔴 **Verify by inspection after editing:** `g_h12_displaying`, `g_h12_ambiguous`,
`g_h12_divergent`, and the three per-code arrays are **byte-for-byte unchanged** in this diff — only
one new line was added to this block (design D3, tasks.md 1.6).

---

## 3. Header — `src/OpenWSFZ.Ft8/Native/ft8_shim.h`

### 3.1 Declaration

Anchor — the three existing declarations, currently lines 757–765:

```c
/*
 * ft8_get_h12_displaying_count / ft8_get_h12_ambiguous_count /
 * ft8_get_h12_divergent_count — SUP-B (shim 20260047). See ft8_shim.c for the
 * full doc comment. Process-global, read-only, process-lifetime cumulative,
 * zero on daemon restart. MEASURE-ONLY: no effect on decode output.
 */
int ft8_get_h12_displaying_count(void);
int ft8_get_h12_ambiguous_count(void);
int ft8_get_h12_divergent_count(void);
```

Add immediately after (and before the existing `ft8_get_h12_by_code` block):

```c
/*
 * ft8_get_h12_suppressed_count — f001-h12-unique-match-suppression (shim 20260049). See
 * ft8_shim.c for the full doc comment. Process-global, read-only, process-lifetime cumulative,
 * zero on daemon restart. UNLIKE its three siblings above, this getter's underlying counter
 * corresponds to a change in decode OUTPUT (a suppressed callsign renders "<...>").
 */
int ft8_get_h12_suppressed_count(void);
```

### 3.2 Version bump and changelog entry

Anchor — the running changelog block, currently ending at line 660, with `#define FT8_SHIM_VERSION
20260048` at line 661:

```c
 *   20260048 — f001-sup-b-amendment-2-cluster-instrumentation: ...
 *              ...
 *              not need cluster identity.
 */
#define FT8_SHIM_VERSION 20260048
```

Insert a new entry before the `*/` that closes the changelog block, then bump the define:

```c
 *   20260048 — f001-sup-b-amendment-2-cluster-instrumentation: ...
 *              ...
 *              not need cluster identity.
 *
 *   20260049 — f001-h12-unique-match-suppression: implements the Option A decision
 *              ("NO NAME BEATS A WRONG NAME", qa/rr-study 2026-09-01) that SUP-B's
 *              instrumentation was built to size. UNLIKE 20260047 and 20260048, THIS
 *              BUMP CHANGES DECODE OUTPUT: cb_lookup_hash now returns "not found" for a
 *              12-bit callsign-hash lookup whose probe chain holds >=2 matching entries
 *              (tls_h12_multiplicity >= 2), so an ambiguous match renders the existing
 *              "<...>" placeholder instead of a (possibly wrong) name. The decode itself
 *              is never affected -- native/ft8_lib_vendor/ is not modified, and its
 *              lookup_callsign already handles a "not found" 12-bit result as a normal,
 *              non-error render path (message.c:594-614,431). hash_table_lookup,
 *              hash_table_add and announce_stamp are byte-for-byte unchanged; the 22-bit
 *              and 10-bit hash paths are untouched. Adds one new exported read-only
 *              getter, ft8_get_h12_suppressed_count(), incremented at the SAME emission
 *              site as the three SUP-B scalars (never inside cb_lookup_hash -- that would
 *              count decode attempts, not displays). The three SUP-B scalars
 *              (displaying/ambiguous/divergent) are UNCHANGED in meaning and continue to
 *              report what *would* have been displayed, so every reading already taken
 *              under 20260047/20260048 stays comparable to a run at this version.
 */
#define FT8_SHIM_VERSION 20260049
```

---

## 4. Binary rebuild

### 4.1 Windows export list — add the new symbol

Anchor — `native/ft8_lib_build/rebuild_shim.bat`, currently lines 155–158:

```
  /EXPORT:ft8_get_h12_displaying_count ^
  /EXPORT:ft8_get_h12_ambiguous_count ^
  /EXPORT:ft8_get_h12_divergent_count ^
  /EXPORT:ft8_get_h12_by_code ^
```

Add one line:

```
  /EXPORT:ft8_get_h12_displaying_count ^
  /EXPORT:ft8_get_h12_ambiguous_count ^
  /EXPORT:ft8_get_h12_divergent_count ^
  /EXPORT:ft8_get_h12_by_code ^
  /EXPORT:ft8_get_h12_suppressed_count ^
```

🔴 **This is the Windows-only trap (design D5).** The Linux build script has no export list
(default visibility) — a symbol present in the header and the `.c` but missing here **builds and
links clean on Linux, and fails only on Windows, only at runtime, on `P/Invoke` resolution.** Confirmed
by reading `.github/workflows/ci.yml`: no explicit export/symbol list for the Linux native-rebuild
step, so nothing there needs a matching edit.

### 4.2–4.4 Rebuild and record

- Rebuild Windows x64; record the compiler version and the binary's SHA256.
- Rebuild Linux x64; record the toolchain and the binary's SHA256.
- macOS ARM64 — not rebuilt locally (no Mac available); CI's `macos-latest` leg owns it, as on every
  prior native change. `pre_merge_check.py`'s local warning about this is expected, **not** a finding
  — do not report it as one.

(Optional housekeeping, not blocking: `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` carries its
own running changelog, already known stale from before this change — SUP-B's own dev-task flagged it.
Append a 20260049 entry in the same style if convenient while this file is open; do not spend time
backfilling its pre-existing staleness, that is separate, smaller cleanup for later.)

---

## 5. Managed interop — four C# files

### 5.1 `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs`

Anchor — currently lines 79–85 (the last of the three existing 12-bit getters):

```csharp
    /// <summary>
    /// Of <see cref="GetH12DisplayingCount"/>, how many had their most-recently-announced
    /// matching entry differ from the first (displayed) match (shim 20260047). A ceiling
    /// on change, not a benefit — see spec Sec.6.5's three prohibitions before citing this
    /// anywhere. Process-global, read-only.
    /// </summary>
    int GetH12DivergentCount();
```

Add immediately after:

```csharp
    /// <summary>
    /// Process-lifetime count of EMITTED decodes whose 12-bit callsign was suppressed because
    /// its probe chain held ≥2 matching entries (f001-h12-unique-match-suppression, shim
    /// 20260049). By design, arithmetically identical to <see cref="GetH12AmbiguousCount"/> on
    /// every run — a wiring invariant between the decision site and the counting site, not new
    /// information; see the native getter's own doc comment. Process-global, read-only.
    /// </summary>
    int GetH12SuppressedCount();
```

### 5.2 `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`

**Version bump.** Anchor — currently line 398, preceded by the `<remarks>` block for `20260048`
(currently ending at line 397):

```csharp
    private const int ExpectedShimVersion = 20260048;
```

Add a new `<remarks>` block immediately before it (after the existing `20260048` one, same pattern),
then bump the constant:

```csharp
    /// <remarks>
    /// f001-h12-unique-match-suppression, shim 20260049: implements the Option A decision — a
    /// 12-bit callsign-hash lookup whose probe chain holds ≥2 matching entries now renders the
    /// existing "&lt;...&gt;" placeholder instead of a (possibly wrong) name. UNLIKE every prior
    /// entry in this changelog, this bump changes decode OUTPUT, not just diagnostics. Adds one
    /// new exported read-only getter, <see cref="GetH12SuppressedCount"/>, bound below.
    /// </remarks>
    private const int ExpectedShimVersion = 20260049;
```

**DllImport.** Anchor — currently lines 616–622 (the last of the three existing 12-bit `DllImport`s):

```csharp
    /// <summary>
    /// SUP-B (shim 20260047): of <see cref="NativeGetH12DisplayingCount"/>, how many had their
    /// most-recently-announced matching entry differ from the first (displayed) one. See
    /// <see cref="IFt8NativeInterop.GetH12DivergentCount"/> for the full contract.
    /// </summary>
    [DllImport("libft8.dll", EntryPoint = "ft8_get_h12_divergent_count", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetH12DivergentCount();
```

Add immediately after:

```csharp
    /// <summary>
    /// f001-h12-unique-match-suppression (shim 20260049). See
    /// <see cref="IFt8NativeInterop.GetH12SuppressedCount"/> for the full contract.
    /// </summary>
    [DllImport("libft8.dll", EntryPoint = "ft8_get_h12_suppressed_count", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetH12SuppressedCount();
```

**Public wrapper.** Anchor — currently lines 940–947 (the last of the three existing public wrappers):

```csharp
    /// <summary>
    /// SUP-B (shim 20260047). See <see cref="IFt8NativeInterop.GetH12DivergentCount"/>.
    /// </summary>
    public static int GetH12DivergentCount()
    {
        EnsureInitialized();
        return NativeGetH12DivergentCount();
    }
```

Add immediately after:

```csharp
    /// <summary>
    /// f001-h12-unique-match-suppression (shim 20260049). See
    /// <see cref="IFt8NativeInterop.GetH12SuppressedCount"/>.
    /// </summary>
    public static int GetH12SuppressedCount()
    {
        EnsureInitialized();
        return NativeGetH12SuppressedCount();
    }
```

### 5.3 `src/OpenWSFZ.Ft8/Interop/Ft8NativeInteropAdapter.cs`

Anchor — currently lines 36–38:

```csharp
    public int GetH12DisplayingCount() => Ft8LibInterop.GetH12DisplayingCount();
    public int GetH12AmbiguousCount()  => Ft8LibInterop.GetH12AmbiguousCount();
    public int GetH12DivergentCount()  => Ft8LibInterop.GetH12DivergentCount();
```

Add a fourth line:

```csharp
    public int GetH12DisplayingCount() => Ft8LibInterop.GetH12DisplayingCount();
    public int GetH12AmbiguousCount()  => Ft8LibInterop.GetH12AmbiguousCount();
    public int GetH12DivergentCount()  => Ft8LibInterop.GetH12DivergentCount();
    public int GetH12SuppressedCount() => Ft8LibInterop.GetH12SuppressedCount();
```

### 5.4 `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

**Wrapper.** Anchor — currently lines 122–129:

```csharp
    /// <summary>SUP-B (shim 20260047). See <see cref="IFt8NativeInterop.GetH12DisplayingCount"/>.</summary>
    public int GetH12DisplayingCount() => _interop.GetH12DisplayingCount();

    /// <summary>SUP-B (shim 20260047). See <see cref="IFt8NativeInterop.GetH12AmbiguousCount"/>.</summary>
    public int GetH12AmbiguousCount() => _interop.GetH12AmbiguousCount();

    /// <summary>SUP-B (shim 20260047). See <see cref="IFt8NativeInterop.GetH12DivergentCount"/>.</summary>
    public int GetH12DivergentCount() => _interop.GetH12DivergentCount();
```

Add immediately after:

```csharp
    /// <summary>f001-h12-unique-match-suppression (shim 20260049). See <see cref="IFt8NativeInterop.GetH12SuppressedCount"/>.</summary>
    public int GetH12SuppressedCount() => _interop.GetH12SuppressedCount();
```

**Per-cycle log line (PO's choice, 2026-09-01 — native counter + C# binding + log line, folded into
the existing h12 line, not a new one).** Anchor — currently lines 459–469:

```csharp
        // ── SUP-B (shim 20260047): 12-bit-path unique-match sizing ──────────────
        // Per-cycle CUMULATIVE (not a delta), matching hashTableRejectCount's own
        // convention immediately above and spec Sec.3.3's rationale: this gives S
        // as a function of elapsed session time, which is the product question
        // being answered, and lets a raw daemon log reconstruct the S-over-time
        // curve spec Sec.6.2 needs without ad hoc endpoint polling.
        _logger?.LogInformation(
            "Cycle {Time}: h12Displaying={H12Displaying} h12Ambiguous={H12Ambiguous} " +
            "h12Divergent={H12Divergent} (process-lifetime cumulative).",
            timeStr, _interop.GetH12DisplayingCount(), _interop.GetH12AmbiguousCount(),
            _interop.GetH12DivergentCount());
```

Change to:

```csharp
        // ── SUP-B (shim 20260047) + f001-h12-unique-match-suppression (shim 20260049):
        // 12-bit-path unique-match sizing AND the suppression it now sizes ─────────
        // Per-cycle CUMULATIVE (not a delta), matching hashTableRejectCount's own
        // convention immediately above and spec Sec.3.3's rationale: this gives S
        // as a function of elapsed session time, which is the product question
        // being answered, and lets a raw daemon log reconstruct the S-over-time
        // curve spec Sec.6.2 needs without ad hoc endpoint polling. h12Suppressed is
        // arithmetically identical to h12Ambiguous by design (see the native getter's
        // own doc comment) -- it is a live wiring-invariant check, not new information.
        _logger?.LogInformation(
            "Cycle {Time}: h12Displaying={H12Displaying} h12Ambiguous={H12Ambiguous} " +
            "h12Divergent={H12Divergent} h12Suppressed={H12Suppressed} (process-lifetime cumulative).",
            timeStr, _interop.GetH12DisplayingCount(), _interop.GetH12AmbiguousCount(),
            _interop.GetH12DivergentCount(), _interop.GetH12SuppressedCount());
```

---

## 6. Every other implementer of `IFt8NativeInterop` needs the new stub

Adding a member to the interface is a breaking change for every test double implementing it. Verified
by `grep -rn ": IFt8NativeInterop\b"` on this branch's current tree (**13 files**, matching the brief's
count, not the stale "11" from the `SUP-B` proposal): 12 in `tests/` plus the production adapter
(§5.3, already done above). For every file below, add the stub next to its existing
`GetH12DivergentCount() => 0;` line:

```csharp
        public int GetH12SuppressedCount() => 0;
```

- `tests/OpenWSFZ.Ft8.Tests/SetDecodeParamsTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/WorkedBeforeLookupTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/RegionLookupTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/RefineCandidateTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/GetLastSnrTermsTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/D009FpFilterTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/D011NonstandardCallsignFpGuardTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/D005MessageTrimTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/AvContainmentTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/CoherentLlrAtTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/HashTableRejectCountLoggingTests.cs` (its `FixedRejectCountInterop`)
- `tests/OpenWSFZ.Ft8.Tests/H12InstrumentationLoggingTests.cs` (its `FixedH12CountsInterop` — **do
  not** just stub this one; §7.3 below gives it a caller-controlled field instead, since this file's
  whole job is pinning the log line that now includes `h12Suppressed`)

Re-run `grep -rn ": IFt8NativeInterop\b"` yourself after your own edits, in case another file has been
added to this list since this document was written (HK-022).

---

## 7. New tests — AC-5 (both directions of the rule)

### 7.1 `tests/OpenWSFZ.Ft8.Tests/TestFt8Encoder.cs` — three new helpers

Add these as new `public static` members (do not modify `PackType4CqAnnounce` or any existing
member), placed near `PackType4CqAnnounce` (currently ending at line 383):

```csharp
    /// <summary>
    /// f001-h12-unique-match-suppression: mirrors kgoba/ft8_lib's message.c:576-577 hash formula
    /// EXACTLY (<c>n22 = (47055833459UL * n58) >> 42 &amp; 0x3FFFFF</c>, <c>n12 = n22 >> 10</c>)
    /// so tests can pre-compute, without any native call, which literal callsigns will collide
    /// on the 12-bit path. <paramref name="callsign"/> must use
    /// <see cref="EncodeNonstandardCall58"/>'s charset (space, 0-9, A-Z, /).
    /// </summary>
    public static int Compute12BitCode(string callsign)
    {
        ulong n58 = EncodeNonstandardCall58(callsign);
        ulong n22 = (47055833459UL * n58) >> 42 & 0x3FFFFFul;
        return (int)(n22 >> 10);
    }

    /// <summary>
    /// Packs a Type 4 (i3=4) message whose call_to slot is resolved via the 12-bit hash table
    /// (icq=0, iflip=0 — message.c:434/437: call_1 = call_3 = the hash-resolved call, and the
    /// icq=0 branch renders call_1 into call_to) and whose call_de slot carries
    /// <paramref name="otherCallsignText"/> as literal 58-bit text. This is the "X, you are Y"
    /// shape f001-h12-unique-match-suppression's Option A actually changes — unlike
    /// <see cref="PackType4CqAnnounce"/>'s icq=1 "CQ" shape, where the 12-bit slot is present in
    /// the payload but structurally discarded by message.c:437's else branch and never rendered.
    /// </summary>
    public static byte[] PackType4HashReference(int n12Code, string otherCallsignText, int nrpt = 0)
    {
        var bits = new byte[77];
        ulong n58 = EncodeNonstandardCall58(otherCallsignText);
        PackBitsInto(bits,  0, 12, (ulong)n12Code); // n12 -- 12-bit hash reference -> call_to
        PackBitsInto(bits, 12, 58, n58);            // n58 -- literal text -> call_de
        PackBitsInto(bits, 70,  1, 0);              // iflip = 0
        PackBitsInto(bits, 71,  2, (ulong)nrpt);
        PackBitsInto(bits, 73,  1, 0);              // icq = 0 -- call_to renders call_1, not "CQ"
        PackBitsInto(bits, 74,  3, 4);              // i3 = 4
        return bits;
    }

    /// <summary>
    /// Builds a 180 000-sample PCM buffer from an already-packed 77-bit Type 4 payload — the
    /// shared tail of <see cref="PackType4CqAnnounce"/>'s own pipeline (AppendCrc14 →
    /// LdpcEncode → BitsToSymbols → SymbolsToPcm), factored out so
    /// <see cref="PackType4HashReference"/>'s raw bits can go through the same path.
    /// </summary>
    public static float[] BuildPcmFromType4Bits(byte[] type4Bits, double baseFreqHz)
    {
        byte[] info = AppendCrc14(type4Bits);
        byte[] cw   = LdpcEncode(info);
        int[]  syms = BitsToSymbols(cw);
        return SymbolsToPcm(syms, baseFreqHz);
    }
```

### 7.2 `tests/OpenWSFZ.Ft8.Tests/HashedCallsignResolutionTests.cs` — the two AC-5 tests

⚠️ **Read this class's own doc comment before adding anything** (currently lines 34–45): the hash
table is a **shared, process-global, never-reset native static** across the whole assembly. A 12-bit
code chosen by arithmetic alone could already be occupied by an unrelated earlier test's entry, which
would make an "ambiguous" or "unique" scenario built on it flaky depending on run order. The helpers
below verify emptiness live before relying on it — do not skip that check to simplify.

Add a new section after §3.6 (`HashTableSaturation_AtG2Capacity_...`, currently ending at line 450),
before the `── Helpers ──` divider:

```csharp
    // ── 3.7: f001-h12-unique-match-suppression — Option A (design D1/D2), AC-5 ───

    [Fact(DisplayName = "f001-h12-unique-match-suppression: a unique 12-bit match still renders the resolved callsign")]
    public void UniqueH12Match_StillRendersResolvedCallsign()
    {
        var (first, _, code) = FindEmptyColliding12BitPair("Q1H12A");

        var announceResults = Ft8LibInterop.DecodeAll(BuildPcmFromType4(first, DefaultFreqHz));
        announceResults.Should().Contain(r => r.Message.Contains(first),
            "the announcement must decode before the hash-reference lookup below means anything");

        byte[] hashRefBits = TestFt8Encoder.PackType4HashReference(code, "Q1H12ADE1");
        float[] pcm = TestFt8Encoder.BuildPcmFromType4Bits(hashRefBits, DefaultFreqHz);
        var results = Ft8LibInterop.DecodeAll(pcm);

        results.Should().Contain(r => r.Message.Contains(first) && r.Message.Contains("Q1H12ADE1"),
            "a 12-bit code with exactly one occupant must still resolve to the literal callsign, " +
            "unchanged from pre-f001-h12-unique-match-suppression behaviour — AC-5's 'unique " +
            "match' direction");
    }

    [Fact(DisplayName = "f001-h12-unique-match-suppression: an ambiguous 12-bit chain suppresses the callsign, but the decode survives")]
    public void AmbiguousH12Chain_SuppressesCallsign_DecodeSurvives()
    {
        var (first, second, code) = FindEmptyColliding12BitPair("Q1H12B");

        Ft8LibInterop.DecodeAll(BuildPcmFromType4(first, DefaultFreqHz))
            .Should().Contain(r => r.Message.Contains(first));
        Ft8LibInterop.DecodeAll(BuildPcmFromType4(second, DefaultFreqHz))
            .Should().Contain(r => r.Message.Contains(second));

        int suppressedBefore = Ft8LibInterop.GetH12SuppressedCount();

        byte[] hashRefBits = TestFt8Encoder.PackType4HashReference(code, "Q1H12BDE1");
        float[] pcm = TestFt8Encoder.BuildPcmFromType4Bits(hashRefBits, DefaultFreqHz);
        var results = Ft8LibInterop.DecodeAll(pcm);

        results.Should().Contain(r => r.Message.Contains("<...>") && r.Message.Contains("Q1H12BDE1"),
            "AC-1/AC-3: the decode must survive with the unresolved placeholder standing in for " +
            "the ambiguous 12-bit slot; everything else about the message is unchanged");
        results.Should().NotContain(r => r.Message.Contains(first) || r.Message.Contains(second),
            "AC-3: neither ambiguous candidate's callsign may appear in the output");
        (Ft8LibInterop.GetH12SuppressedCount() - suppressedBefore).Should().Be(1,
            "AC-4: the suppressed counter must move by exactly one for this one suppressed display");
    }

    /// <summary>
    /// Finds two DISTINCT Q-prefix synthetic callsigns whose 12-bit hash code
    /// (<see cref="TestFt8Encoder.Compute12BitCode"/>) is IDENTICAL, and whose code is verified —
    /// via a live, read-only probe (<see cref="IsCodeCurrentlyEmpty"/>) — to have ZERO occupants
    /// right now. <paramref name="prefix"/> must be unique to the caller and ≤7 chars (prefix +
    /// a 4-digit suffix must stay ≤11 chars, pack58's limit).
    /// </summary>
    private static (string First, string Second, int Code) FindEmptyColliding12BitPair(string prefix)
    {
        const int poolSize = 12_000; // >> 4096: virtually every code has 2+ candidates by then
        var byCode = new Dictionary<int, List<string>>();
        for (int i = 0; i < poolSize; i++)
        {
            string candidate = $"{prefix}{i:D4}";
            int code = TestFt8Encoder.Compute12BitCode(candidate);
            if (!byCode.TryGetValue(code, out var list))
                byCode[code] = list = new List<string>();
            list.Add(candidate);
        }

        foreach (var (code, candidates) in byCode)
        {
            if (candidates.Count < 2) continue;
            if (IsCodeCurrentlyEmpty(code))
                return (candidates[0], candidates[1], code);
        }
        throw new InvalidOperationException(
            $"No 12-bit code near prefix '{prefix}' is both a same-code pair AND currently " +
            "empty -- either the shared table is far more occupied than any prior test in this " +
            "class left it (check whether the opt-in G2 saturation test ran first; it " +
            "permanently fills the table and is documented to run last for exactly this reason), " +
            "or Compute12BitCode has drifted from message.c:576-577.");
    }

    /// <summary>
    /// Live, read-only probe: true iff <paramref name="code"/> currently has zero occupants in
    /// the process-global hash table. Costs one throwaway table entry of its own (the probe
    /// message's literal "de" call is auto-registered by unpack58, message.c:890-892) — harmless,
    /// the table has thousands of slots to spare and is never reset (design D1/D3).
    /// </summary>
    private static bool IsCodeCurrentlyEmpty(int code)
    {
        byte[] bits = TestFt8Encoder.PackType4HashReference(code, "Q1H12PROBE");
        float[] pcm = TestFt8Encoder.BuildPcmFromType4Bits(bits, DefaultFreqHz);
        var results = Ft8LibInterop.DecodeAll(pcm);
        var probe = results.FirstOrDefault(r => r.Message.Contains("Q1H12PROBE"));
        return probe.Message?.Contains("<...>") == true;
    }
```

🔒 **NFR-021:** every literal above (`Q1H12A####`, `Q1H12B####`, `Q1H12ADE1`, `Q1H12BDE1`,
`Q1H12PROBE`) is a fictional Q-prefix synthetic callsign, none reused from elsewhere in the suite.

### 7.3 `tests/OpenWSFZ.Ft8.Tests/H12InstrumentationLoggingTests.cs` — pin the log line's new field

This is the AC-5-adjacent "wiring" pin (tasks.md 5.4), not AC-5 itself. Three changes to the existing
file (full current content already read; only what's below changes):

**a)** The test double's constructor and member (currently lines 30–42):

```csharp
    private sealed class FixedH12CountsInterop(int displaying, int ambiguous, int divergent) : IFt8NativeInterop
    {
        ...
        public int    GetH12DisplayingCount()                => displaying;
        public int    GetH12AmbiguousCount()                 => ambiguous;
        public int    GetH12DivergentCount()                 => divergent;
```

Change to:

```csharp
    private sealed class FixedH12CountsInterop(int displaying, int ambiguous, int divergent, int suppressed) : IFt8NativeInterop
    {
        ...
        public int    GetH12DisplayingCount()                => displaying;
        public int    GetH12AmbiguousCount()                 => ambiguous;
        public int    GetH12DivergentCount()                 => divergent;
        public int    GetH12SuppressedCount()                => suppressed;
```

**b)** `DecodeAsync_EveryCycle_LogsH12CountsAtInformation` (currently lines 104–131): add a 4th
constant and pass it through, mirroring `ambiguous` (AC-4's invariant, for illustration — this file's
fake interop does not enforce the invariant, it just needs a concrete value to pin):

```csharp
        const int displaying = 17;
        const int ambiguous  = 5;
        const int divergent  = 2;
        const int suppressed = 5; // == ambiguous, matching the real AC-4 invariant
        var logger  = new RecordingLogger<Ft8Decoder>();
        var interop = new FixedH12CountsInterop(displaying, ambiguous, divergent, suppressed);
```

...and extend the assertion to also require `h12Suppressed` and its value:

```csharp
        logger.Entries.Should().Contain(
            e => e.Level == LogLevel.Information
                 && e.Message.Contains("h12Displaying")
                 && e.Message.Contains("h12Ambiguous")
                 && e.Message.Contains("h12Divergent")
                 && e.Message.Contains("h12Suppressed")
                 && e.Message.Contains(displaying.ToString())
                 && e.Message.Contains(ambiguous.ToString())
                 && e.Message.Contains(divergent.ToString())
                 && e.Message.Contains(suppressed.ToString()),
            "h12Displaying/h12Ambiguous/h12Divergent/h12Suppressed must all be logged at " +
            "Information level every cycle, carrying the values the four getters actually " +
            "returned");
```

**c)** `DecodeAsync_ZeroH12Counts_LogsZeroExplicitly` (currently lines 133–153): add `suppressed: 0`
to the constructor call and `h12Suppressed=0` to the assertion, same pattern as the other three
fields.

### 7.4 Demonstrate AC-5's ambiguous test is capable of failing (do this, then revert — do not skip)

Mirrors the FR-064 precedent (`dev-tasks/2026-09-01-flaky-externalreportingservice-fr064-heartbeat-race.md`
§"Leak-guard demonstrated capable of failing"). Temporarily change §2.2's
`tls_h12_suppressed = (tls_h12_multiplicity >= 2);` to
`tls_h12_suppressed = (tls_h12_multiplicity >= 999999);` (predicate can never fire), confirm
`AmbiguousH12Chain_SuppressesCallsign_DecodeSurvives` goes **RED**, then revert the temporary change.
Confirm `git diff --stat -- src/` is empty again before considering the real fix done — a test that
has never been seen to fail is not evidence.

---

## 8. Definition of done

- [ ] §2's `ft8_shim.c` changes made exactly as specified. `hash_table_lookup`, `hash_table_add`,
      `announce_stamp` and `hash_table_count_h12_multiplicity` are byte-for-byte unchanged (diff
      each against `main` and confirm nothing touches their bodies). The three existing counters
      and per-code arrays are unchanged apart from the one new `g_h12_suppressed++` line.
- [ ] §3's `ft8_shim.h` declaration and changelog entry added; `FT8_SHIM_VERSION` bumped to
      `20260049`.
- [ ] §4.1's export line added; Windows and Linux binaries rebuilt; SHA256s recorded for both.
- [ ] §5's four C# files updated; `ExpectedShimVersion` bumped to `20260049`.
- [ ] §6: every file in that list (re-verified against a fresh grep) compiles.
- [ ] §7.1–7.3's new tests and log-line pin added and passing.
- [ ] §7.4 done: the ambiguous test demonstrated RED under a temporarily-broken predicate, then the
      temporary change reverted (`git diff --stat -- src/` empty again before the real fix ships).
- [ ] `dotnet test` — full suite green, not just the new/changed files. Note any pre-existing
      failures explicitly as pre-existing — re-run them on the unmodified base commit before
      claiming so, rather than asserting it (tasks.md 6.2).
- [ ] Gate G10 (`check_test_delay_sync.py`) OK; **no new `Task.Delay(...)`** anywhere in the diff.
- [ ] `openspec validate --strict --all` passes (tasks.md 6.4).
- [ ] NFR-021 scan **post-commit**, not pre-commit — the scan misses uncommitted files (tasks.md 6.5).
- [ ] `git diff --stat` against `main` touches only the files named in §2/§3/§4/§5/§6/§7 — nothing
      else. In particular: **zero diff under `native/ft8_lib_vendor/`.**
- [ ] Present the diff to the Captain for explicit review (HK-011) before any push. Per HK-010,
      the merge always needs the Captain's explicit sign-off regardless of green CI.
- [ ] 🛑 **Do not run `pre_merge_check.py`** (HK-006 — Captain's initiative only). **Do not push, do
      not merge.**

Once the Developer session's diff is ready, control returns to QA for the replay-based AC-1–AC-4
(openspec `tasks.md` §7–§8): pin the new binary's SHA256 into the replay manifest **after** the
rebuild, replay the `S-17M` corpus at `20260048` (baseline) and `20260049` (candidate), and check the
decode-count/differing-line/suppressed-count criteria before handing the Captain a merge decision.

---

## 9. What this handoff does NOT authorize

- 🛑 No push, no merge, no `pre_merge_check.py`.
- 🛑 No work on `F-001` L3, the site-6 mitigation, `ARM 2`, or any change to the 22-bit/10-bit hash
  paths.
- 🛑 No flag, no staged default-off rollout — the PO explicitly declined that path.
- 🛑 `S_max` = 40% stays **FROZEN** — this build is the PO's Sec.6.4 escalation exercised, not a bar
  move.
- 🛑 No re-opening the accepted risk (unmeasured correct-name loss at `S-17M`'s CI upper bound) as a
  new finding — it is on the record (openspec `proposal.md`'s "Accepted risk" section).
- 🛑 No spec-sync / archive work (openspec `tasks.md` §10) — that is separate, and blocked on
  `f001-sup-b-instrumented-suppression-sizing` being spec-synced and archived FIRST (design.md Open
  Questions; `tasks.md` 10.1). Not this session's problem to solve.

---

## 10. Cross-references

- `qa/rr-study/2026-09-01-1949-architect-to-qa-brief-f001-option-a-unique-match-suppression.md` —
  the brief this handoff implements.
- `openspec/changes/f001-h12-unique-match-suppression/{proposal,design,tasks}.md` — the change this
  handoff builds tasks §1–§6 of.
- `dev-tasks/2026-08-30-sup-b-h12-instrumentation.md` — the precedent this handoff's structure and
  the C# surface's naming/doc-comment conventions both follow.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` lines 632-655, 716-720, 789-811, 1191-1193, 1611-1632, and
  `ft8_shim.h` lines 626-661, 757-765 (as of this branch's tip, identical to `main`@`68a014d`) — the
  exact regions this diff touches; line numbers will drift, search anchors are given throughout
  instead of trusting them.
- `native/ft8_lib_vendor/ft8/message.c` lines 400-458, 594-614, 872-895 — read-only reference
  confirming the 12-bit call site, the render path, and unpack58's auto-registration side effect;
  **not modified by this change**.
- `tests/OpenWSFZ.Ft8.Tests/HashedCallsignResolutionTests.cs`,
  `tests/OpenWSFZ.Ft8.Tests/TestFt8Encoder.cs`,
  `tests/OpenWSFZ.Ft8.Tests/H12InstrumentationLoggingTests.cs` — the three files §7 extends.
