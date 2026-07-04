## Why

FT8's protocol lets a station announce a nonstandard/compound callsign (e.g. `PJ4/K1ABC`,
special-event calls, anything that doesn't fit the 6-character standard basecall) once in full
(a Type 4 message), then have later exchanges reference it cheaply via a 22-bit hash embedded in
a standard Type 1/2/3 message. Resolving that hash back to the real callsign requires the
decoder to remember hash→callsign mappings across transmission slots — that's the whole point of
the mechanism; the full text and the hash reference are, by design, decoded in *different*
15-second cycles.

`ft8_shim.c`'s native decode entry point (`ft8_decode_all`) currently allocates a fresh, empty
callsign hash table on every single call and destroys it before returning. The result: a
Type 4 message's callsign is immediately forgotten, so no later hash reference can ever resolve
it. Operators only ever see the WSJT-X-style `<...>` placeholder, never the real callsign — the
resolution mechanism is present in code but non-functional in practice. This blocks any
meaningful QSO with a station using a compound or special-event callsign (logging, AP decode
assist, and UI display all degrade to an anonymous placeholder).

## What Changes

- Give the native shim's callsign hash table a lifetime that spans multiple decode cycles
  (session-scoped) instead of being rebuilt empty on every `ft8_decode_all` call, so a callsign
  announced via a Type 4 message resolves correctly when referenced by hash in a later cycle.
- Apply a bounded eviction/replacement policy (FIFO, matching WSJT-X's own ~40-entries-per-width
  behaviour) so the table cannot grow unbounded over a long operating session.
- Preserve the existing AV/SEH containment behaviour: the table pointer is still safely detached
  on the exception path, but the underlying storage now survives a caught access violation rather
  than being torn down, so the session's accumulated hash knowledge isn't lost to a single faulted
  cycle.
- No change to the existing `<...>` placeholder convention for callsigns that are genuinely
  unresolvable (never seen, or evicted) — that remains correct WSJT-X-compatible behaviour.
- **Optional / stretch, not required for this change to ship**: extend `Ft8CallsignPacker` (C#)
  to pack tokens (`CQ`/`DE`/`QRZ`) and nonstandard/hashed callsigns for the AP (a-priori) LDPC
  decode-assist path, currently silently disabled whenever either party's callsign is
  nonstandard. Only worth doing once the persistent table above exists — hinting a hash the
  decoder can never look up buys nothing. Tracked as a separate, clearly-marked task; may be
  deferred to a follow-up change without blocking this one.

## Capabilities

### New Capabilities
- `hashed-callsign-resolution`: session-scoped callsign hash table in the native decode pipeline,
  enabling Type 1/2/3 messages to resolve a 22-bit callsign hash against a Type 4 message decoded
  in an earlier cycle, with bounded FIFO eviction and AV-safe lifecycle.

### Modified Capabilities
- (none — no existing spec in `openspec/specs/` documents hash-table lifetime or resolution
  behaviour; `ft8-decoder` and `ft8lib-interop` describe decode invocation and result-marshalling
  but are silent on cross-cycle callsign-hash state, so this is additive rather than a change to
  a documented requirement)

## Impact

- **Native**: `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — `ft8_decode_all`'s per-call
  `callsign_table_t htbl` allocation/teardown (lines ~1076–1078, ~1316, ~1331) becomes a
  session-scoped table; `FT8_SHIM_VERSION` bump per existing shim-versioning convention.
- **Managed**: no required change to `Ft8Decoder.cs` — its existing `<...>` pass-through handling
  (`IsPlausibleMessage`, D-005 trim fix) is already correct for both the resolved and unresolved
  cases and needs no modification.
- **Optional/stretch only**: `src/OpenWSFZ.Ft8/Ft8CallsignPacker.cs`,
  `src/OpenWSFZ.Daemon/QsoAnswererService.cs`, `src/OpenWSFZ.Daemon/QsoCallerService.cs` (AP
  constraint construction) — only if Gap B is taken on.
- **Testing**: native shim unit/integration coverage for table persistence across two synthetic
  `ft8_decode_all` calls (Type 4 in cycle 1, hash reference in cycle 2), FIFO eviction behaviour,
  and AV-path safety; no change expected to existing R&R study corpus results since this affects
  a message class (nonstandard calls) not currently exercised by the synthetic corpus.
