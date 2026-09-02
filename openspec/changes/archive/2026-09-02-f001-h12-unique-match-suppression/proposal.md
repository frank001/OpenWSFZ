**User-facing:** yes

## Why

`F-001`'s 12-bit nonstandard-callsign hash path resolves a Type 1/2/3 message's hash reference
against a session-scoped table whose probe bucket is only 12 bits wide. That is a many-to-one space
over the amateur callsign population, so a probe chain can legitimately hold **more than one**
matching entry — and when it does, the decoder today displays the **first** match as though it were
certain. Some of those displayed names are wrong, and nothing on screen distinguishes them from the
right ones.

`SUP-B` was built to size that cost and did so on three bands. Two of the three returned `MARGINAL`
against the frozen `S_max` = 40% bar, which by design routes the decision to the Product Owner
rather than to the bar. **The PO decided on 2026-09-01: ship the unconditional unique-match rule on
all bands, resolving the straddle by the standing ruling "NO NAME BEATS A WRONG NAME"**
(`qa/rr-study/2026-09-01-1510-po-decision-f001-sup-b-step7-option-a.md`). This change is that
decision, built.

The measurement question is closed and is not reopened here. **`S_max` = 40% remains FROZEN** — the
PO exercised Sec.6.4's escalation exactly as specified, which is not a bar move, and a future band
still reads against 40%.

## What Changes

- **BREAKING (decode output):** when a 12-bit callsign-hash lookup resolves against a probe chain
  holding **two or more** matching entries, the callsign SHALL NOT be displayed. The message renders
  the existing unresolved-hash placeholder `<...>` in that position and **the decode itself is
  kept** — no decode is gained or lost by this change. This is the first `hashed-callsign-resolution`
  requirement that alters decode output; every prior one in this capability was read-only.
  🔴 Unlike `f001-sup-b-instrumented-suppression-sizing`, which states in terms that both its phases
  are MEASURE-ONLY, **this change deliberately changes what the operator sees.** That is why it is a
  separate change and not an extension of that one.
- Suppression is decided in the project's own hash-lookup callback (`cb_lookup_hash`,
  `src/OpenWSFZ.Ft8/Native/ft8_shim.c`), which already computes the probe-chain multiplicity one
  statement above its own return. **The vendored decoder (`native/ft8_lib_vendor/`) is NOT modified**:
  its `lookup_callsign` already renders `<...>` on a reported-not-found lookup, and its only 12-bit
  call site discards the return value, so a suppressed lookup is not an error path and the message
  still decodes successfully.
- The existing `SUP-B` instrumentation **keeps counting what *would* have been displayed** — the
  suppression is expressed through a separate signal, not by falsifying the "resolved" flag. Every
  ROW 0 reading already taken therefore stays comparable, and the instrument can predict, in advance
  and mechanically, exactly how many output lines this change alters.
- Adds one native diagnostic export, `ft8_get_h12_suppressed_count`, with a managed `P/Invoke`
  binding and a per-cycle log line (Product Owner's choice, 2026-09-01, over a native-only counter or
  no counter at all).
- `FT8_SHIM_VERSION` / `ExpectedShimVersion` advances `20260048` → `20260049`.
- Scope is the **12-bit** hash path only. The 22-bit and 10-bit paths are untouched, as are
  `hash_table_lookup`, `hash_table_add` and the `announce_stamp` mechanism.

### Accepted risk, recorded so it is not re-opened as a finding

At `S-17M`'s confidence-interval upper bound this withholds a substantial share of the 12-bit-resolved
names currently displayed on that band (`S-17M` = `53.54% [30.42%, 70.92%]`, citable only as point
estimate paired with its own interval), and **how many of those were correct is unmeasured**. Closing
that gap needs a truth source that `R6` rules against buying. The PO took this decision with the
Architect's concern on the record. Two things bound it honestly and neither removes it: `S` is an
**upper bound on UX cost and is never correct-name loss** (`R5`), and the suppressed set is
*enriched* for wrong names by construction — enriched is not "mostly wrong". 🛑 This is an
ACCEPTED RISK, not an oversight; do not re-raise it as new.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `hashed-callsign-resolution`: one new Requirement — a 12-bit hash reference resolving against an
  ambiguous probe chain SHALL render the unresolved placeholder rather than a candidate callsign,
  while the decode is retained. This narrows the existing "Cross-cycle callsign hash resolution"
  Requirement, whose scenarios remain correct for the unique-match and never-announced cases and are
  unchanged.
- `ft8lib-interop`: the ABI self-test's expected shim constant advances `20260048` → `20260049`; one
  new diagnostic native export with a managed binding. `DecodeAll` and every other exported symbol
  are unchanged.

## Impact

- **Affected code:**
  - `src/OpenWSFZ.Ft8/Native/ft8_shim.c` / `ft8_shim.h` — the suppression predicate and return in
    `cb_lookup_hash`, one thread-local flag, one process-lifetime counter and its getter, the
    emission-point increment, version bump and changelog entry.
  - `src/OpenWSFZ.Ft8/Interop/{IFt8NativeInterop.cs,Ft8LibInterop.cs,Ft8NativeInteropAdapter.cs}`,
    `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — one member each, plus the per-cycle log line.
  - **13 files declare an `IFt8NativeInterop` implementation** (12 in `tests/`, plus the production
    adapter); each needs a fixed-zero stub. ⚠️ Verified by search on `main`@`68a014d` — the
    `f001-sup-b-instrumented-suppression-sizing` proposal's "11 implementers" is stale.
  - `native/ft8_lib_build/rebuild_shim.bat` — one `/EXPORT:` line. 🔴 The Linux build script carries
    no export list (default visibility), so a symbol omitted here builds and links clean on Linux and
    fails **only on Windows, only at runtime**, on `P/Invoke` resolution.
  - New tests pinning both directions of the rule.
- **Not affected, and must stay that way:** `native/ft8_lib_vendor/**` (unmodified),
  `hash_table_lookup` / `hash_table_add` / `announce_stamp`, the `SUP-B` emission-point counters'
  existing semantics, and the 22-bit and 10-bit hash paths.
- **Rebuild targets:** Windows x64 (MSVC) and Linux x64 locally; macOS ARM64 on CI's `macos-latest`
  leg, as on every prior native change — its "could not rebuild here" warning on a Windows box is
  expected and permanent, not a finding.
- **Operator-visible:** stations whose 12-bit hash reference is ambiguous will show `<...>` where a
  (possibly wrong) callsign appeared before. Decode counts, frequency, DT and SNR are unaffected.
- **Design authority:**
  `qa/rr-study/2026-09-01-1949-architect-to-qa-brief-f001-option-a-unique-match-suppression.md`.
  **Decision authority:** `qa/rr-study/2026-09-01-1510-po-decision-f001-sup-b-step7-option-a.md`.
