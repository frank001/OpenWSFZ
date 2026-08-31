# Developer handoff: `SUP-B` — instrument the real 12-bit callsign-hash path (three read-only counters)

**Authored by:** QA (per HK-000/HK-015/HK-011). **Status:** ready for a Developer session.
**Source spec:** `qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md`
Sec.3 (the instrument) and Sec.9.2 (handoff chain).
**Branch:** `qa/sup-b-2026-08-30`, cut fresh off `main` at `d38ebad` (Sec.9.1 — do not build this on
a closed QA branch).

🛑 **QA proposes this diff and stops here (HK-011). QA does not edit `src/` or `native/`, does not
build, does not run `pre_merge_check.py` (HK-006 — Captain's initiative only).** A separate Developer
session applies this, builds, and runs the existing test suite. The Captain reviews the diff before
any push. QA returns afterward to pin the `INST` binary's SHA256 (spec Sec.4) and run the ROW 0 gates
(spec Sec.5) — that is QA's, not the Developer's.

**MEASURE-ONLY.** After this change, decode output is byte-for-byte identical to before — same names
displayed, same decodes, same everything — plus three new process-lifetime counters and one new log
line. Nothing in this diff implements, enables, or flags the unique-match suppression rule itself
(spec Sec.3.4). If any change here alters what a lookup returns, that is a defect in this diff, not
in the spec.

---

## 1. What this measures, in one sentence

Of the FT8 messages OpenWSFZ actually displays today via the 12-bit nonstandard-callsign hash path
(`Q1CALL <...>` style Type-4 decodes), what fraction resolved to an **ambiguous** hash-table slot
(≥2 candidate entries), and of those, how often does the **most recently announced** matching entry
differ from the **first** one (which is what's actually shown)? See the spec Sec.0/3.1 for the full
product question this answers.

## 2. Native change — `src/OpenWSFZ.Ft8/Native/ft8_shim.c`

**No change to `native/ft8_lib_vendor/ft8/message.c` is needed.** The entire 12-bit lookup mechanism
— the probe walk, the table itself, and the callback wired up as `hash_if->lookup_hash` — lives in
`ft8_shim.c`, which is this project's own file, not vendored upstream code. `message.c`'s
`lookup_callsign` (line 594) only calls the callback; it never touches `callsign_table_t` directly.
Confirm this still holds before starting — if it doesn't, the shipped code has diverged from this
proposal and the proposal is what's wrong (spec Sec.5 preamble).

### 2.1 Add a recency stamp to each table entry (TRAP 2)

Anchor: `callsign_entry_t`, currently (search for it — it's right above `#define HASH_TABLE_SIZE`,
around line 630):

```c
typedef struct { char callsign[12]; uint32_t hash; } callsign_entry_t;
```

Change to:

```c
typedef struct { char callsign[12]; uint32_t hash; uint32_t announce_stamp; } callsign_entry_t;
```

`hash_table_init`'s `memset(tbl, 0, sizeof(*tbl))` (unchanged) zeroes the new field along with
everything else — no further change needed there. This grows `sizeof(callsign_table_t)` from 64 KB
to 80 KB (4096 × 20 bytes). Not ABI-visible — this struct is never marshalled to C#.

### 2.2 Stamp recency in `hash_table_add`, never in `hash_table_lookup` (TRAP 2)

Anchor: `hash_table_add` (search for `static void hash_table_add`, around line 667). Add a
process-global monotonic clock just above it:

```c
/* SUP-B (shim 20260047): monotonic recency stamp for the 12-bit-path divergence
 * ceiling D. Incremented in hash_table_add ONLY -- on a genuinely new insert and
 * on a repeat announcement of an already-known callsign (both are "announcements"
 * that should refresh recency). hash_table_lookup must NEVER write this -- doing
 * so would contaminate announcement recency with lookup recency (the exact defect
 * named in SUP-A Amendment 1's SimTable.lookup() last_used refresh). Same
 * best-effort, not-thread-local convention as g_hash_table_reject_count above:
 * an occasional missed/racy increment under concurrent decode is an acceptable
 * trade-off against synchronising the hot path (see that counter's own comment). */
static uint32_t g_h12_announce_clock = 0;
```

Inside `hash_table_add`, the "already known — no-op" branch currently reads:

```c
        if (((tbl->entries[idx].hash & 0x3FFFFFu) == hash) &&
            !strcmp(tbl->entries[idx].callsign, callsign)) {
            tbl->entries[idx].hash &= 0x3FFFFFu; return; /* already known — no-op, NOT a reject */
        }
```

Add the stamp write before the `return`:

```c
        if (((tbl->entries[idx].hash & 0x3FFFFFu) == hash) &&
            !strcmp(tbl->entries[idx].callsign, callsign)) {
            tbl->entries[idx].hash &= 0x3FFFFFu;
            tbl->entries[idx].announce_stamp = ++g_h12_announce_clock; /* SUP-B TRAP 2: re-announcement refreshes recency */
            return; /* already known — no-op, NOT a reject */
        }
```

And the genuinely-new-insert path at the bottom of the same function currently reads:

```c
    tbl->count++;
    strncpy(tbl->entries[idx].callsign, callsign, 11);
    tbl->entries[idx].callsign[11] = '\0';
    tbl->entries[idx].hash = hash;
}
```

Add the stamp write before the closing brace:

```c
    tbl->count++;
    strncpy(tbl->entries[idx].callsign, callsign, 11);
    tbl->entries[idx].callsign[11] = '\0';
    tbl->entries[idx].hash = hash;
    tbl->entries[idx].announce_stamp = ++g_h12_announce_clock; /* SUP-B TRAP 2: new insert */
}
```

### 2.3 A separate, read-only multiplicity/divergence walk (TRAP 1)

**Do not modify `hash_table_lookup` itself in any way that could change its return value or the
`callsign` it writes.** Add a new function immediately after it (search for `static bool
hash_table_lookup`, around line 637; insert after its closing brace, around line 655):

```c
/* SUP-B (shim 20260047): 12-bit-path unique-match sizing instrumentation (TRAP 1).
 * MEASURE-ONLY -- never called from anywhere that could change what a lookup
 * returns. Replays the SAME probe sequence hash_table_lookup uses (identical
 * h10/idx derivation, identical EMPTY-slot termination, identical
 * HASH_TABLE_SIZE bound) but continues past the first match purely to count
 * every matching entry and to compare the FIRST match against the
 * MOST-RECENTLY-ANNOUNCED one (by announce_stamp, TRAP 2). Read-only: never
 * writes to tbl, never allocates. sh is fixed at 10 because this is only ever
 * called for FTX_CALLSIGN_HASH_12_BITS (see cb_lookup_hash below) -- if a
 * future caller needs this for another hash width, thread sh through as a
 * parameter rather than hardcoding a different constant here. */
static void hash_table_count_h12_multiplicity(const callsign_table_t* tbl, uint32_t hash,
                                               int* out_count, bool* out_divergent)
{
    const uint8_t  sh  = 10; /* FTX_CALLSIGN_HASH_12_BITS, matches hash_table_lookup's own ternary */
    uint16_t       h10 = (hash >> (12 - sh)) & 0x3FFu;
    int            idx = (h10 * 23) % HASH_TABLE_SIZE;
    int            count = 0;
    int            first_match_idx = -1;
    int            most_recent_idx = -1;
    uint32_t       most_recent_stamp = 0;

    for (int probe = 0; probe < HASH_TABLE_SIZE; probe++) {
        if (tbl->entries[idx].callsign[0] == '\0') break;
        if (((tbl->entries[idx].hash & 0x3FFFFFu) >> sh) == hash) {
            count++;
            if (first_match_idx < 0) first_match_idx = idx;
            if (tbl->entries[idx].announce_stamp >= most_recent_stamp) {
                most_recent_stamp = tbl->entries[idx].announce_stamp;
                most_recent_idx   = idx;
            }
        }
        idx = (idx + 1) % HASH_TABLE_SIZE;
    }
    *out_count     = count;
    *out_divergent = (count >= 2) && (most_recent_idx != first_match_idx);
}
```

**Why this can't regress `hash_table_lookup`:** it is a wholly separate function with its own local
`idx`/probe loop over the same (`const`, read-only) `tbl`. `hash_table_lookup` is not called from
inside it, and it is not called from inside `hash_table_lookup`. Verify this stays true in review —
it is the entire mechanical content of spec ROW 0b.

### 2.4 Wire the walk in behind the 12-bit lookup, into thread-local scratch (TRAP 3)

Anchor: `cb_lookup_hash`, immediately below the multiplicity walk (search for `static bool
cb_lookup_hash`, currently):

```c
static _Thread_local callsign_table_t* tls_hash_table = NULL;
static bool cb_lookup_hash(ftx_callsign_hash_type_t t, uint32_t h, char* cs) {
    if (!tls_hash_table) { cs[0] = '\0'; return false; }
    return hash_table_lookup(tls_hash_table, t, h, cs);
}
```

Add scratch declarations above it and change its body to:

```c
/* SUP-B (shim 20260047): per-message 12-bit-lookup scratch (TRAP 3). Reset to
 * lookup_performed=false in ft8_decode_all immediately before each message's
 * ftx_message_decode call (see Sec.2.5 below) and read immediately after, iff
 * that decode succeeds AND is about to be emitted. message.c:431 is the ONLY
 * 12-bit lookup call site and fires at most once per message, so this simple
 * reset-then-read bracket is sufficient -- no accumulation, no stack. */
static _Thread_local bool tls_h12_lookup_performed = false;
static _Thread_local bool tls_h12_resolved         = false;
static _Thread_local int  tls_h12_multiplicity     = 0;
static _Thread_local bool tls_h12_divergent        = false;

static _Thread_local callsign_table_t* tls_hash_table = NULL;
static bool cb_lookup_hash(ftx_callsign_hash_type_t t, uint32_t h, char* cs) {
    if (!tls_hash_table) { cs[0] = '\0'; return false; }
    bool found = hash_table_lookup(tls_hash_table, t, h, cs); /* UNCHANGED return path -- TRAP 1 */
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
    return found;
}
```

⚠️ **Order matters:** `hash_table_count_h12_multiplicity` must be defined before `cb_lookup_hash` in
the file (it's called from there). Section 2.3's function goes directly after `hash_table_lookup`;
this section's changes go at `cb_lookup_hash`, further down — confirm the compiler doesn't need a
forward declaration (it won't, if the order above is followed).

### 2.5 Reset scratch before the decode call, accumulate at emission (TRAP 3, ROW 0d)

Anchor: inside `ft8_decode_all`'s per-candidate loop (search for `Attempt text decode BEFORE
occupying the dedup slot`, around line 1463):

```c
            /* Attempt text decode BEFORE occupying the dedup slot.
             * If ftx_message_decode fails (e.g. Type-4 hash not yet known),
             * bail here so the slot stays free for a later retry.          */
            char text[FTX_MAX_MESSAGE_LENGTH + 1];
            if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
                continue;

            /* Text decode succeeded — commit to the dedup table */
            memcpy(&decoded_msgs[walk], &msg, sizeof(msg));
            decoded_ht[walk] = &decoded_msgs[walk];
```

Change to:

```c
            /* Attempt text decode BEFORE occupying the dedup slot.
             * If ftx_message_decode fails (e.g. Type-4 hash not yet known),
             * bail here so the slot stays free for a later retry.          */
            char text[FTX_MAX_MESSAGE_LENGTH + 1];
            tls_h12_lookup_performed = false; /* SUP-B TRAP 3: fresh scratch for THIS message */
            if (ftx_message_decode(&msg, &s_hash_if, text) != FTX_MESSAGE_RC_OK)
                continue;

            /* Text decode succeeded — commit to the dedup table */
            memcpy(&decoded_msgs[walk], &msg, sizeof(msg));
            decoded_ht[walk] = &decoded_msgs[walk];

            /* SUP-B (shim 20260047): from here on this message is unconditionally
             * headed for results[] below (nothing between here and there can still
             * discard it) -- this IS the emission point ROW 0d checks against, not
             * the ftx_message_decode call above. Count DISPLAYS, not decode
             * attempts (TRAP 3, HK-022). */
            if (tls_h12_lookup_performed && tls_h12_resolved) {
                g_h12_displaying++;
                if (tls_h12_multiplicity >= 2) g_h12_ambiguous++;
                if (tls_h12_divergent)         g_h12_divergent++;
            }
```

🔴 **Verify the "unconditionally headed for `results[]`" claim yourself before relying on it** —
read from this insertion point down to `FT8Result* r = &results[num_decoded++];` (a few dozen lines:
frequency/dt/SNR computation) and confirm there is no `continue` or early exit in between on the
current `main`. If one has been added since this spec was written, move the counting block down to
sit immediately before the `results[num_decoded++]` line instead — the invariant that matters is
"exactly here is where a display is guaranteed," not the exact line number.

### 2.6 The three process-global counters and their getters

Add near `g_hash_table_reject_count` (around line 665), or immediately after the
`g_h12_announce_clock` declaration from §2.2 — either location is fine, keep them together:

```c
/* SUP-B (shim 20260047): the three counters spec Sec.3.1 defines. Same
 * best-effort, not-thread-local convention as g_hash_table_reject_count. */
static int g_h12_displaying = 0;
static int g_h12_ambiguous  = 0;
static int g_h12_divergent  = 0;
```

Add getters near `ft8_get_hash_table_reject_count` (around line 1084):

```c
/* ── 12-bit-path unique-match sizing (SUP-B, shim 20260047) ───────────────── */
/*
 * ft8_get_h12_displaying_count / ft8_get_h12_ambiguous_count /
 * ft8_get_h12_divergent_count — process-lifetime counts backing spec Sec.3.1's
 * S = h12Ambiguous / h12Displaying and D = h12Divergent / h12Displaying.
 * MEASURE-ONLY: these three getters and the counters behind them have zero
 * effect on decode output (spec Sec.3.4). Read-only, never reset, same
 * lifecycle as ft8_get_hash_table_reject_count (0 on daemon restart, may be
 * read from any thread).
 */
int ft8_get_h12_displaying_count(void) { return g_h12_displaying; }
int ft8_get_h12_ambiguous_count(void)  { return g_h12_ambiguous; }
int ft8_get_h12_divergent_count(void)  { return g_h12_divergent; }
```

## 3. Header — `src/OpenWSFZ.Ft8/Native/ft8_shim.h`

### 3.1 Declarations

Add next to `ft8_get_hash_table_reject_count(void);` (around line 720):

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

### 3.2 Version bump and changelog entry

Add a new entry to the running history block immediately before the existing `20260046` entry (find
it — it starts `r0-reproducible-native-build (FT8_SHIM_VERSION 20260039)` and the block runs forward
in version order, most recent last, ending just above `#define FT8_SHIM_VERSION 20260046`):

```c
 *   20260047 — f001-sup-b-instrumented-suppression-sizing: adds three new
 *              exported read-only getters -- ft8_get_h12_displaying_count(),
 *              ft8_get_h12_ambiguous_count(), ft8_get_h12_divergent_count() --
 *              counting how many EMITTED decodes resolved via the 12-bit
 *              nonstandard-callsign hash path, how many of those hit an
 *              ambiguous (>=2-entry) probe chain, and how many of THOSE had
 *              their most-recently-announced match differ from the first
 *              (displayed) one. Adds a uint32_t announce_stamp field to
 *              callsign_entry_t (64 KB -> 80 KB table, not ABI-visible --
 *              never marshalled to C#), stamped in hash_table_add only, never
 *              in hash_table_lookup. MEASURE-ONLY: hash_table_lookup's return
 *              value and the callsign it writes are byte-for-byte unchanged;
 *              the new counting walk is a separate, read-only function.
 *              hash_table_add's existing reject-on-full and already-known
 *              no-op behaviour is unchanged. No change to the 4096-slot
 *              capacity or eviction policy.
```

Then bump the define:

```c
#define FT8_SHIM_VERSION 20260047
```

## 4. C# interop surface — four files, mirroring `GetHashTableRejectCount` exactly

Three new members in each, same naming convention (`GetH12DisplayingCount`,
`GetH12AmbiguousCount`, `GetH12DivergentCount`):

### 4.1 `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs`

Add next to `int GetHashTableRejectCount();` (around line 64):

```csharp
    /// <summary>
    /// Process-lifetime count of EMITTED decodes whose display resolved via the 12-bit
    /// nonstandard-callsign hash path (f001-sup-b-instrumented-suppression-sizing, shim
    /// 20260047). Denominator for spec Sec.3.1's S and D. Process-global, read-only.
    /// </summary>
    int GetH12DisplayingCount();

    /// <summary>
    /// Of <see cref="GetH12DisplayingCount"/>, how many resolved against a probe chain
    /// holding ≥2 matching entries (shim 20260047). Process-global, read-only.
    /// </summary>
    int GetH12AmbiguousCount();

    /// <summary>
    /// Of <see cref="GetH12DisplayingCount"/>, how many had their most-recently-announced
    /// matching entry differ from the first (displayed) match (shim 20260047). A ceiling
    /// on change, not a benefit — see spec Sec.6.5's three prohibitions before citing this
    /// anywhere. Process-global, read-only.
    /// </summary>
    int GetH12DivergentCount();
```

### 4.2 `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs`

`DllImport`s next to `NativeGetHashTableRejectCount` (around line 570):

```csharp
    [DllImport("libft8.dll", EntryPoint = "ft8_get_h12_displaying_count", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetH12DisplayingCount();

    [DllImport("libft8.dll", EntryPoint = "ft8_get_h12_ambiguous_count", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetH12AmbiguousCount();

    [DllImport("libft8.dll", EntryPoint = "ft8_get_h12_divergent_count", CallingConvention = CallingConvention.Cdecl)]
    private static extern int NativeGetH12DivergentCount();
```

Public wrappers next to `GetHashTableRejectCount()` (around line 865), same
`EnsureInitialized()` pattern:

```csharp
    public static int GetH12DisplayingCount()
    {
        EnsureInitialized();
        return NativeGetH12DisplayingCount();
    }

    public static int GetH12AmbiguousCount()
    {
        EnsureInitialized();
        return NativeGetH12AmbiguousCount();
    }

    public static int GetH12DivergentCount()
    {
        EnsureInitialized();
        return NativeGetH12DivergentCount();
    }
```

### 4.3 `src/OpenWSFZ.Ft8/Interop/Ft8NativeInteropAdapter.cs`

Next to `GetHashTableRejectCount()` (around line 33):

```csharp
    public int GetH12DisplayingCount() => Ft8LibInterop.GetH12DisplayingCount();
    public int GetH12AmbiguousCount()  => Ft8LibInterop.GetH12AmbiguousCount();
    public int GetH12DivergentCount()  => Ft8LibInterop.GetH12DivergentCount();
```

### 4.4 `src/OpenWSFZ.Ft8/Ft8Decoder.cs`

Wrapper methods next to `GetHashTableRejectCount()` (around line 119):

```csharp
    public int GetH12DisplayingCount() => _interop.GetH12DisplayingCount();
    public int GetH12AmbiguousCount()  => _interop.GetH12AmbiguousCount();
    public int GetH12DivergentCount()  => _interop.GetH12DivergentCount();
```

The per-cycle cumulative log line, immediately after the existing `hashTableRejectCount` line
(around line 448 — search for `"Cycle {Time}: hashTableRejectCount="`), same Information level and
cadence, per spec Sec.3.3's exact required format:

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

## 5. Every other implementer of `IFt8NativeInterop` needs the three new stub methods

Adding three members to the interface is a breaking change for every test double implementing it —
the compiler will refuse to build until each is updated. Rather than leave that to be discovered one
error at a time, here is the full list, found via `grep -rn ": IFt8NativeInterop\b"`:

- `tests/OpenWSFZ.Ft8.Tests/WorkedBeforeLookupTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/SetDecodeParamsTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/RegionLookupTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/RefineCandidateTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/HashTableRejectCountLoggingTests.cs` (its `FixedRejectCountInterop`)
- `tests/OpenWSFZ.Ft8.Tests/GetLastSnrTermsTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/D009FpFilterTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/D011NonstandardCallsignFpGuardTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/D005MessageTrimTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/AvContainmentTests.cs`
- `tests/OpenWSFZ.Ft8.Tests/CoherentLlrAtTests.cs`

For every one of these except the two named in §6 below, none of them care about the new counters —
add the same trivial fixed-zero stub each place (mirroring how `HashTableRejectCountLoggingTests.cs`
already stubs unrelated members like `GetLastLlrStats`):

```csharp
        public int GetH12DisplayingCount() => 0;
        public int GetH12AmbiguousCount()  => 0;
        public int GetH12DivergentCount()  => 0;
```

Re-run `grep -rn ": IFt8NativeInterop\b"` yourself after your own edits, in case another file has
been added to this list since this document was written — do not treat the list above as
authoritative if the repo has moved (HK-022).

## 6. New test — mirrors `HashTableRejectCountLoggingTests.cs` exactly

Add `tests/OpenWSFZ.Ft8.Tests/H12InstrumentationLoggingTests.cs`, same structure as
`HashTableRejectCountLoggingTests.cs` (§5's list already includes it as a file needing the stub
update — this is that update, done properly instead of stubbed):

- A `FixedH12CountsInterop(int displaying, int ambiguous, int divergent)` test double (or extend
  `HashTableRejectCountLoggingTests.cs`'s existing `FixedRejectCountInterop` with three more
  caller-controlled fields — either is fine, prefer whichever keeps that file's existing two tests
  passing unmodified).
- One test asserting the new log line appears at `LogLevel.Information` once per `DecodeAsync` call,
  containing all three values (mirroring `DecodeAsync_EveryCycle_LogsHashTableRejectCountAtInformation`).
- One test asserting all-zero counts are still logged explicitly, not suppressed (mirroring
  `DecodeAsync_ZeroRejectCount_LogsZeroExplicitly`).

## 7. Native build — add the three exports everywhere the existing ones appear

🔴 **Do not treat this list as exhaustive — it is a starting point, not a substitute for actually
checking.** `ft8_get_hash_table_reject_count` appears as an `/EXPORT:` entry in at least:

- `native/ft8_lib_build/rebuild_shim.bat` (the script actually used for a local Windows rebuild —
  confirmed current, has every export through `ft8_get_last_snr_terms`)
- `src/OpenWSFZ.Ft8/Native/BUILD.md` (documentation — confirmed **already missing**
  `ft8_get_last_snr_terms`, i.e. it has drifted out of sync with `rebuild_shim.bat` at least once
  before; do not assume it's complete, cross-check both against each other)

Add `/EXPORT:ft8_get_h12_displaying_count`, `/EXPORT:ft8_get_h12_ambiguous_count`, and
`/EXPORT:ft8_get_h12_divergent_count` to every place you find the existing exports listed, including
any macOS/Linux build step in `.github/workflows/ci.yml` that lists exported symbols explicitly
(the Linux leg rebuilds `libft8.so` from source per `BUILD.md`'s own note — check whether that build
step needs anything beyond adding the new `int ft8_get_...(void)` functions, which C's default
external linkage already exports on ELF without a separate list).

✅ **The mechanical safety net, so a missed export list doesn't ship silently:** `tools/pre_merge_check.py`'s
native-binary-freshness step and `tools/check_native_version.py` compare the built binary's actual
exports/behaviour against what the managed side expects. Run the full `pre_merge_check.py` is
**not** yours to invoke (HK-006 — Captain's initiative only), but a plain local build + the existing
`dotnet test` suite will fail loudly with an unresolved P/Invoke entry point if any export list was
missed — that failure is expected and correct, not a sign this handoff is wrong.

⚠️ Also check `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — it carries a running changelog
similar to `ft8_shim.h`'s, but its own "Exported symbols" line was already found stale (missing
several exports added well before this change, e.g. `ft8_get_last_snr_terms`). Append this version's
entry in the same style if you're touching this file anyway; do not spend time backfilling its
pre-existing staleness — that's a separate, smaller cleanup someone can pick up later, not part of
this task's scope.

## 8. Definition of done

- [ ] §2's `ft8_shim.c` changes made exactly as specified; `hash_table_lookup` itself is
      byte-for-byte unchanged (diff it against `main` and confirm the diff touches nothing inside
      that function's body).
- [ ] §3's `ft8_shim.h` declarations and version-history entry added; `FT8_SHIM_VERSION` bumped to
      `20260047`.
- [ ] §4's four C# files updated.
- [ ] §5: every file in that list (re-verified against a fresh grep) compiles — either genuinely
      wired up (§6) or stubbed (§5).
- [ ] §6's new test file added and passing.
- [ ] §7: local build succeeds (Windows at minimum; Linux/WSL and macOS if you have the toolchain —
      same tiered expectation `pre_merge_check.py` itself uses) with no unresolved P/Invoke entry
      points.
- [ ] `dotnet test` — full suite green, not just the new file (a struct layout change touching a
      process-global table is exactly the kind of change that could have an unexpected interaction
      elsewhere; do not assume isolation).
- [ ] `git diff --stat` against `main` touches only the files named in §2/§3/§4/§5/§6 — nothing else.
- [ ] Present the diff to the Captain for explicit review (HK-011) before any push. Per HK-010,
      `gh pr merge` always needs the Captain's explicit sign-off regardless of green CI.
- [ ] **Do not run `pre_merge_check.py`** (HK-006) and **do not enable, flag, or otherwise implement
      the unique-match suppression rule** (spec Sec.3.4) — both are explicitly out of scope here.

Once merged, control returns to QA (spec Sec.9.2 step 4): pin the `INST` build's SHA256 into the
spec Sec.4 manifest, verify `git diff --stat` is empty, then replay the four corpora already
confirmed present on disk (§9 below) and run the ROW 0 gates.

## 9. Precondition already checked by QA — do not re-derive

Per spec Sec.2.1, QA ran `python qa/artefact_inventory.py --check` (2026-08-30, this session) — clean,
no regeneration needed — and confirmed via `qa/rr-study/f001-sup-a/common_supa.py`'s existing
`CORPORA` dict (already used by the now-superseded `SUP-A`, whose ROW 0b ran against these same four)
that all four candidate corpora have real, on-disk, replayable WAVs:

| id | path | WAVs on disk |
|---|---|---:|
| `S-17M` | `artefacts/20260808_live_run_1154-8080-17m/owsfz/` | 1,856 |
| `S-80M` | `artefacts/20260809_live_run_0155-8080-80m/owsfz/` | 1,988 |
| `S-20M` | `artefacts/20260808_live_run_0016-8080/owsfz/` | 2,747 |
| `L-20M` | `artefacts/20260731_live_run_2004-8080/owsfz/` | 10,489 |

All four bands survive (well above Sec.2.1's two-band minimum). No corpus is dropped. This does not
need re-checking before the Developer session starts; it only needs re-checking if QA's replay later
(§8 above) reports something not matching these counts.

## 10. Cross-references

- `qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md` —
  the spec this handoff implements Sec.3/Sec.9.2 of.
- `dev-tasks/2026-07-26-salvage-hashtablerejectcount-logging.md` — the precedent this handoff's
  structure and the C# surface's naming convention both follow.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` lines 634-720, 1449-1567, 1071-1084 (as of `main`
  `d38ebad`) — the exact regions this diff touches; line numbers will drift, search anchors are
  given throughout instead of trusting them.
- `native/ft8_lib_vendor/ft8/message.c` lines 400-431, 594-613 — read-only reference confirming the
  single 12-bit call site and the render path; **not modified by this change**.
