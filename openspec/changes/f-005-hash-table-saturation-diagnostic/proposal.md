## Why

The 2026-07-06 endurance run (`qa/endurance/2026-07-06-7340e45/report.md` §3.5) observed the
OpenWSFZ-only hashed-callsign (`<...>`) rate increase ~72% over the pre-F-001 baseline — the
opposite of F-001's expected field effect. QA triage of the raw session logs traced the great
majority of this to expected, structural causes (a busier band producing more forward/
never-heard hash references; WSJT-X's 6+ day continuous hash-cache accumulation versus
OpenWSFZ's fresh session-scoped table). No evidence of a resolution-logic defect was found.

One real, unresolved question survived triage: F-001's native hash table is fixed at 256 slots
(`openspec/changes/archive/2026-07-05-f-001-hashed-callsign-resolution/design.md`, decision D3),
and that design doc explicitly flagged table saturation as a risk on a busy or long session. The
implementation already added a counter for exactly this scenario
(`g_hash_table_reject_count`, tasks.md §2.1) but deliberately left it native-only with no
P/Invoke surface, deferring exposure until "the saturation risk materialises." This endurance
session decoded on the order of 700–1,000+ distinct nonstandard-shaped callsign texts against
that 256-slot capacity — several times over. The trigger condition this counter was built for has
very plausibly now occurred, and there is currently no way to confirm or deny it from outside the
native process. Without that visibility, every future run repeats the same ambiguous, off-line,
text-heuristic triage instead of reading a number.

## What Changes

- Add a minimal read-only P/Invoke getter exposing the existing native
  `g_hash_table_reject_count` counter, following the same pattern as the existing
  `ft8_get_last_noise_floor_db` diagnostic getter.
- Surface the counter's value through the daemon's existing diagnostics/logging path so an
  operator or a future endurance-run analysis can directly read it (e.g. logged at session end
  or on demand), rather than inferring saturation from an off-line ALL.TXT text heuristic.
- No change to resolution behaviour, the 256-slot capacity, or the "reject when full" eviction
  policy (D3's decision stands unchanged) — this is an observability-only addition.

**Explicitly out of scope:**
- Increasing hash table capacity.
- Implementing FIFO eviction (the design doc's deferred alternative).
- Persisting the hash table across process restarts.
- Any change to hash resolution correctness or the `<...>` placeholder convention.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `hashed-callsign-resolution`: add a new requirement that the session-scoped hash table's
  reject-when-full saturation count SHALL be observable from the managed layer, so that table
  saturation can be confirmed or ruled out during live operation and QA analysis instead of only
  being inferable indirectly.

## Impact

- **Native shim** (`ft8_shim.c`): add one exported read-only getter function returning the
  existing `g_hash_table_reject_count` static; no change to any existing exported function's
  signature or behaviour. Requires a shim version bump per the existing `FT8_SHIM_VERSION`
  convention.
- **Managed interop** (`Ft8LibInterop.cs` or equivalent P/Invoke layer): add the corresponding
  P/Invoke declaration and `ExpectedShimVersion` bump, mirroring the existing
  `ft8_get_last_noise_floor_db` wrapper.
- **Diagnostics/logging path**: surface the counter value through whatever existing
  operator-facing diagnostic mechanism is most appropriate (daemon log line, diagnostics
  endpoint, or both) — exact placement decided in design.md.
- **Tests**: unit coverage confirming the getter returns zero before any rejection occurs and
  the correct count after the existing table-saturation test scenario (`HashTableSaturation_...`
  in `HashedCallsignResolutionTests`) forces a rejection.
- No impact to decode correctness, AP-assist, callsign structure validation, or any other
  currently shipped capability.
