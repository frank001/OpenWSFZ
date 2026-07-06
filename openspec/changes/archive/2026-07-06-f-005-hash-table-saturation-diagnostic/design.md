## Context

F-001 (`openspec/changes/archive/2026-07-05-f-001-hashed-callsign-resolution/`) gave the native
decode pipeline a process-global, session-scoped callsign hash table (`g_session_hash_table`,
`ft8_shim.c`) so a nonstandard callsign announced via a Type 4 message could be resolved from a
hash reference in a later decode cycle. That design fixed the table at 256 slots (decision D3)
and accepted "reject new entries once full" as the saturation policy, on the stated assumption
that 256 slots would be "generous headroom for a realistic single-operator session." The
implementation (tasks.md §2.1) hedged against that assumption being wrong by adding
`static int g_hash_table_reject_count`, incremented inside `hash_table_add`'s existing
full-table guard — but deliberately did not expose it, per the design's own Open Questions,
"to avoid adding a new P/Invoke surface for a diagnostic that's only needed if the saturation
risk materialises."

The 2026-07-06 endurance run (10h52m, real 40 m FT8 traffic) is the first extended session run
against this table. QA triage of that run (`qa/endurance/2026-07-06-7340e45/report.md` §3.5, and
the follow-up analysis referenced in this change's proposal) found the session decoded on the
order of 700–1,000+ distinct nonstandard-shaped callsign texts — several times the table's
256-slot capacity — while also observing an unexplained rise in unresolved hash references that
a naive reading might attribute to a resolution bug. Triage ruled out a resolution-logic defect,
but could not rule saturation in or out, because the one counter built for exactly this question
is unreachable from the managed layer. The assumption behind D3 has plausibly already been
exceeded once; the mitigation promised at the time ("add a diagnostic... if it's ever seen in
practice") is now due.

## Goals / Non-Goals

**Goals:**
- Make `g_hash_table_reject_count` readable from the managed layer, so a running or completed
  session can be inspected to confirm or rule out table saturation directly, rather than by
  offline text-heuristic inference over ALL.TXT.
- Keep the change purely observational: zero effect on resolution behaviour, capacity, or
  eviction policy.
- Follow the existing diagnostic-getter precedent (`ft8_get_last_noise_floor_db`) rather than
  introduce a new pattern.

**Non-Goals:**
- Increasing the 256-slot capacity or implementing FIFO eviction. If this diagnostic later
  confirms saturation is happening routinely, that is a follow-up decision for the Captain, not
  something this change pre-empts.
- Persisting the hash table or this counter across process restarts. The counter resets to zero
  on every fresh daemon run, exactly as `g_session_hash_table` itself does.
- A full metrics/telemetry surface. This is a single counter, read on demand or logged
  periodically — not a new subsystem.

## Decisions

### D1 — Getter shape: mirror `ft8_get_last_noise_floor_db` exactly

**Decision**: add `int32_t ft8_get_hash_table_reject_count(void)` (or the equivalent signed
32-bit return type already used by the noise-floor getter) as a new exported native function,
returning `g_hash_table_reject_count` with no side effects and no locking (the existing counter
is a simple process-global `int`, incremented only from the single decode-cycle-at-a-time path
per F-001's own concurrency assumption — see that design's D1 and Non-Goals, which this change
does not alter). Add the matching P/Invoke declaration in the managed interop layer, and bump
`FT8_SHIM_VERSION` / `ExpectedShimVersion` together per the existing shim-versioning discipline
(F-001's tasks.md §1.1/discovered-item recorded exactly this two-file coupling as an easy thing
to miss).

Alternative considered: expose it as an out-parameter on an existing call (e.g. bundled into
`FT8Result`) to avoid adding a new exported symbol. Rejected — it would force every caller of the
hot decode path to carry a rarely-needed diagnostic field, and breaks the precedent set by
`ft8_get_last_noise_floor_db`, which already established "separate on-demand getter" as this
codebase's pattern for this exact category of diagnostic.

### D2 — Surfacing: log at session end, not every cycle

**Decision**: read the counter once at graceful daemon shutdown (alongside whatever
session-summary logging already exists) and write it to the daemon log as a single line, e.g.
`Hash table reject count (session): N`. Do not log it every decode cycle.

Rationale: the value is monotonically non-decreasing and only interesting in aggregate — a
per-cycle log line would add 15-second-cadence noise for a number that changes rarely (only once
the table is actually full) and provides no diagnostic value until then. Session-end is exactly
where an operator or a QA endurance-run analysis would look for it, and matches how this
project already writes other end-of-session facts (e.g., the existing shutdown-path logging
inspected during the D-011/F-001 sessions).

Alternative considered: expose via a diagnostics HTTP endpoint (the daemon already has an
`/api/v1` surface per the endurance report's `POST /api/v1/decode/stop`). Not rejected outright
— left as an option for whoever implements this if a live (non-post-hoc) read is wanted — but
the minimum viable version for this change is the session-end log line, since that alone closes
the observability gap the endurance triage identified. Tasks.md should treat the HTTP endpoint
as optional/stretch, matching F-001's own precedent of marking speculative extensions as
deferred stretch tasks rather than blocking the core fix.

### D3 — No reset-on-read

**Decision**: the getter is read-only; nothing resets `g_hash_table_reject_count` to zero when
it is read. The counter's lifecycle stays tied purely to the process (reset only on daemon
restart), consistent with `g_session_hash_table` itself.

Alternative considered: reset on read, to get a "since last check" delta. Rejected — adds
mutation to what should be a trivially safe, side-effect-free diagnostic read, and there is
exactly one consumer (session-end logging) for which a cumulative session-lifetime count is the
more useful number anyway.

## Risks / Trade-offs

- **[Risk] The getter is added but nothing ever calls it** (log line wiring is skipped or
  forgotten) → the observability gap this change exists to close would remain. **Mitigation**:
  tasks.md requires an end-to-end test (or, at minimum, a manual verification step recorded in
  the PR) confirming the session-end log line actually appears with a non-zero value when the
  existing `HashTableSaturation_...` test scenario's conditions are reproduced.
- **[Risk] Reading a plain (non-atomic) `int` written from the decode path while a shutdown-path
  read happens "concurrently"** → per F-001's own D1, decode calls are strictly one-at-a-time and
  never overlap with the shutdown sequence reading the daemon's own final log line (shutdown only
  proceeds after the last decode cycle completes), so no torn read is possible under the current
  threading model. **Mitigation**: none needed beyond noting this dependency explicitly, so a
  future concurrent-decode change (already flagged as a risk in F-001's own design) revisits this
  assumption too.
- **[Trade-off] Session-end-only visibility (D2)** means an operator cannot see saturation
  happening live, mid-session, without the optional HTTP-endpoint stretch. Acceptable: the
  triage this change responds to was itself a post-hoc endurance-run analysis, so closing that
  exact gap does not require live visibility — only that the number exists and can be read once
  the session's data is being reviewed.

## Migration Plan

- Single native shim change (new exported getter, no change to any existing function's signature
  or behaviour) plus a matching managed P/Invoke declaration and shim-version bump, following the
  same two-file coupling F-001 already documented as easy to miss.
- No data migration, no persisted state, no public API break.
- Rollback is a straight revert of the shim/version bump and the log-line wiring; no other code
  depends on this getter existing.
- Verify via: the existing `HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive`
  test's setup (264 distinct callsigns added, capacity 256) extended to also assert the new
  getter reports a reject count consistent with the known overflow (264 − 256 = 8, accounting for
  any table occupancy already present at test start per that test's own documented caveat about
  not assuming an empty table).

## Open Questions

- Should the optional HTTP diagnostics endpoint (D2's alternative) be scoped into this change's
  tasks.md as a stretch item, or deferred to a separate future change entirely? Recommend
  stretch/optional within this change's tasks.md, consistent with how F-001 itself handled its
  own optional Gap B extension — but this is the Captain's call at task-review time.
