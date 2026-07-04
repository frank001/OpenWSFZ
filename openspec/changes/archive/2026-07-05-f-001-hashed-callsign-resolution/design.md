## Context

FT8's callsign-hash mechanism (WSJT-X's own design, faithfully ported into `kgoba/ft8_lib`,
which this project vendors as `libft8.dll` via `src/OpenWSFZ.Ft8/Native/ft8_shim.c`) exists to let
a station with a nonstandard/compound callsign (e.g. `PJ4/K1ABC`, an 11-character special-event
call) participate in an exchange without repeatedly burning the extra bits its callsign needs.

The callsign hash itself (`ihashcall` in WSJT-X's `packjt77.f90`, reproduced identically in
`ft8_lib`) is computed as:

```
n8 = 0
for each of up to 11 characters (charset: space, 0-9, A-Z, /):
    n8 = 38 * n8 + char_index
hash = (47055833459 * n8) >> (64 - m)     // keep the top m bits
```

`m` is 22, 12, or 10 depending on where the hash is embedded. Two message forms cooperate:

- **Type 4** (`i3=4`): transmits one party's callsign in full (58-bit plaintext, up to 11 chars)
  alongside a **12-bit hash** of the other party. This is how a nonstandard callsign is first
  "announced" — the receiver learns the full text once and should remember it.
- **Type 1/2/3** (`i3=1/2/3`, the standard-message family): each 28-bit callsign field (`c28`) is
  partitioned into three ranges — special tokens (`CQ`/`DE`/`QRZ`/"CQ nnn"/"CQ ABCD", `n28 <
  NTOKENS`), a **22-bit hash** of a nonstandard callsign (`NTOKENS ≤ n28 < NTOKENS + MAX22`), or a
  standard 6-char basecall (`n28 ≥ NTOKENS + MAX22`). This lets a *later* exchange reference the
  previously-announced nonstandard callsign by hash instead of retransmitting it.

Resolution therefore inherently spans multiple 15-second decode cycles: the Type 4 announcement
and the Type 1/2/3 hash reference are, by protocol design, sent in different slots. A decoder
that forgets what it heard between cycles can never close the loop — which is exactly the current
state of `ft8_shim.c`: `ft8_decode_all` builds a brand-new `callsign_table_t` on the stack at the
top of every call (`hash_table_init(&htbl); tls_hash_table = &htbl;`) and discards it before
returning. WSJT-X itself keeps this table alive for the life of the running session (and, per its
own hash-table persistence work referenced in `wsjt-devel`, even across restarts via a save/load
file) — this change brings the shim's behaviour in line with that baseline, without taking on the
save/load-to-disk piece, which is out of scope here.

## Goals / Non-Goals

**Goals:**
- A callsign announced via a Type 4 message in decode cycle *N* resolves correctly when
  referenced by its 22-bit hash in a Type 1/2/3 message in any later cycle *N+k* within the same
  running process/session.
- The table's memory footprint is bounded — it must not grow without limit over a multi-hour
  operating session.
- The existing AV/SEH containment behaviour (D-006, fix-seh-av-containment) is preserved:
  a caught access violation must not leave a dangling pointer or destabilise the next cycle.
- No behavioural change to the existing, already-correct `<...>` placeholder path for callsigns
  that are genuinely unresolvable (never announced, or evicted from the table).

**Non-Goals:**
- Persisting the hash table to disk across process restarts (WSJT-X's optional save/load file).
  Every fresh daemon run starts with an empty table, same as today; only in-process, cross-cycle
  persistence is in scope.
- Multi-mode / multi-band concurrent decode support. The current threading model runs one decode
  cycle at a time (`Ft8Decoder.DecodeAsync` awaits a single `Task.Run` per cycle); this change
  assumes that invariant continues to hold and does not add support for concurrent
  `ft8_decode_all` calls from independent decode pipelines.
- Extending `Ft8CallsignPacker` (C#) / AP-constraint construction to support nonstandard
  callsigns (Gap B in the proposal). Tracked as an optional stretch task; not required for this
  change's core guarantee.

## Decisions

### D1 — Storage: process-global static, not thread-local

The existing table is `_Thread_local`. `Ft8Decoder.cs` dispatches each decode cycle via a fresh
`Task.Run`, and .NET's thread pool gives no guarantee that consecutive cycles land on the same OS
thread. A thread-local table would therefore appear to reset unpredictably — sometimes
"persisting" across two cycles that happen to reuse a thread, sometimes not — which is worse than
todays fully-deterministic (always-empty) behaviour because failures would be intermittent and
hard to reproduce.

**Decision**: replace the per-call stack-allocated `callsign_table_t` with a single
process-global `static callsign_table_t g_session_hash_table`, initialised once (e.g. via a
`static bool g_initialised` guard, or an explicit `ft8_shim`-level init call if one already
exists) and reused by every subsequent `ft8_decode_all` call for the life of the process.
`tls_hash_table` (already thread-local) continues to exist purely as the pointer the
`cb_lookup_hash`/`cb_save_hash` callbacks dereference each call — it is set to point at
`&g_session_hash_table` at the top of `ft8_decode_all` instead of at a freshly-zeroed local, and
still cleared to `NULL` at the end of the call and on the SEH exception path (D2 covers whether
the *pointee* is also reset).

Alternative considered: a `CRITICAL_SECTION`-guarded global, to defend against any future
multi-threaded decode. Rejected for this change because it adds Windows-specific synchronisation
primitives to a code path that today has exactly one caller at a time (see Non-Goals); if
multi-mode concurrent decode is ever added, the locking should be introduced then, scoped to
whatever the new concurrency model actually requires, rather than speculatively now.

### D2 — Exception-path behaviour: preserve the table, don't reset it

On a caught access violation, the existing code nulls `tls_hash_table` and skips `monitor_free`
("a second AV inside the handler is worse than a leak"). With a process-global table, the
question is whether `g_session_hash_table`'s *contents* should also be discarded defensively.

**Decision**: leave `g_session_hash_table`'s contents untouched on the exception path; only
detach the thread-local pointer (`tls_hash_table = NULL`), exactly as today. Both documented root
causes of native AVs in this shim (D-006 pointer truncation in `message.c`'s `stpcpy` handling;
RQ-2 waterfall out-of-bounds read) are confined to the `ftx_message_decode` text buffer and the
waterfall (`monitor_t.wf`) respectively — neither has any code path that writes into the
callsign-hash table region, so there is no plausible corruption vector linking a caught AV to this
specific static buffer. Resetting it defensively on every AV would silently discard a session's
accumulated resolution knowledge on the very failure mode this shim already works hard to make
non-fatal, for no corresponding safety benefit.

Alternative considered: reset on every AV, symmetric with the current `monitor_t` conservatism.
Rejected — `monitor_t` is reset because the AV's known causes plausibly touch its memory; the hash
table is not in that blast radius, so applying the same caution here is safety theatre, not
safety.

### D3 — Eviction policy: keep "reject when full," don't build true FIFO (for now)

WSJT-X keeps roughly 40 entries per hash width with FIFO (oldest-evicted) replacement. This
shim's existing table is a single 256-slot open-addressed structure shared across all three hash
widths (10/12/22-bit lookups all key off the same underlying 22-bit hash via a right-shift — see
`hash_table_lookup`'s `sh` parameter), and `hash_table_add` already refuses new entries once
`count >= HASH_TABLE_SIZE` rather than evicting the oldest.

**Decision**: keep the existing "reject new entries once full" policy unchanged for this change.
256 slots is generous headroom for a realistic single-operator session's distinct nonstandard
callsigns; building true oldest-first FIFO eviction would require threading an insertion-order
sequence through the open-addressed structure (or a parallel circular index) for a benefit that's
speculative until real session logs show the table actually saturating.

Alternative considered: true FIFO eviction matching WSJT-X exactly. Deferred rather than rejected
— flagged in Risks/Trade-offs below as the first thing to revisit if operational logs ever show
`hash_table_add`'s guard triggering (new callsigns silently refused).

### D4 — Shim versioning

Per the existing `FT8_SHIM_VERSION` convention documented at the top of `ft8_shim.c`, this change
gets the next sequential version number in that history (the file's history header ends at
`20260030` as of this proposal; confirm the actual current value at implementation time, since
other changes may have landed the shim version forward in the interim). Record the new entry with
the same style of comment block used by every prior entry.

## Risks / Trade-offs

- **[Risk] Table saturation over a very long or very busy session** (many distinct nonstandard
  callsigns exceed 256 entries) → new callsigns are silently refused (existing `hash_table_add`
  guard); resolution then behaves exactly as it does today (permanent `<...>`) for the callsigns
  that didn't make it in. **Mitigation**: D3's deferred-FIFO note; add a debug/diagnostic log line
  when the guard triggers so this is observable in the field rather than silent, and revisit true
  FIFO eviction if it's ever seen in practice.
- **[Risk] Silent behavioural coupling to the single-decode-cycle-at-a-time assumption** (D1) → if
  a future change makes decode concurrent (e.g. multi-band), the unguarded global table becomes a
  genuine data race. **Mitigation**: the Non-Goals section calls this out explicitly; this design
  doc and the shim's version-history comment should be the first thing a future multi-mode change
  reads.
- **[Trade-off] No cross-restart persistence** (Non-Goal) → an operator restarting the daemon
  mid-session loses all accumulated hash knowledge, same as WSJT-X without its optional save/load
  file enabled. Acceptable: this matches the proposal's scoped ask (fix cross-*cycle* resolution
  within a run) and avoids taking on file-format and load-time-validation design questions that
  belong in a separate change if ever wanted.

## Migration Plan

- Single native shim change; no data migration, no persisted state to migrate, no public API
  surface change (no new exported entry points required — `ft8_decode_all`'s signature and
  `FT8Result` layout are unchanged).
- Rollback is a straight revert of the shim change and version bump; the managed layer requires no
  corresponding change and is unaffected either way.
- Roll out behind the existing shim-version discipline: build, run the existing R&R study corpus
  to confirm no regression on messages the corpus already exercises (none of which currently
  include nonstandard-callsign forms, per the proposal's Impact section), then add the new
  synthetic two-cycle test described in tasks.md before merge.

## Open Questions

- Should the diagnostic log line proposed in the saturation risk mitigation go through the
  existing `_logger` managed-layer path (would require a new TLS getter, mirroring
  `ft8_get_last_noise_floor_db`) or is a native-only counter (queryable on demand, not logged every
  cycle) sufficient for now? Recommend the latter to avoid adding a new P/Invoke surface for a
  diagnostic that's only needed if the saturation risk materialises.
- Confirm the actual next `FT8_SHIM_VERSION` value at implementation time (D4) rather than
  assuming `20260030` is still the most recent entry.
