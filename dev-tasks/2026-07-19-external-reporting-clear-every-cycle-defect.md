# Developer Handoff — `ExternalReportingService` sends WSJT-X "Clear" every decode cycle, wiping GridTracker's map

**Date:** 2026-07-19
**Prepared by:** QA Engineer
**Status:** Confirmed defect, protocol-conformance issue — supersedes my earlier (wrong) theory
in `dev-tasks/2026-07-19-external-reply-decode-filter-bypass-option.md` as the explanation for the
"weird GridTracker behaviour" the Captain originally reported.
**Scope:** `ExternalReportingService.DecodeLoopAsync`, `openspec/specs/external-reporting/spec.md`,
`REQUIREMENTS.md` (FR-053), `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs`.

---

## 1. Evidence

The Captain provided a direct empirical comparison:

- **WSJT-X → GridTracker**, running a few minutes: spots accumulate across the whole map (dozens
  of stations spanning Europe, Asia, the Pacific — clearly a running history built up over the
  session).
- **OpenWSFZ → GridTracker**, running a few minutes: two consecutive screenshots ~16 seconds apart
  (one FT8 cycle) show the spot count *shrinking*, not growing — "previous contacts are wiped."

That is the signature of something actively purging GridTracker's accumulated state on a very
short, regular cadence — not a filtering problem (nothing on the decode-filter/engagement side
touches outbound traffic at all, confirmed in the prior handoff).

## 2. Root cause, confirmed against the real protocol

`ExternalReportingService.DecodeLoopAsync` (`src/OpenWSFZ.Daemon/ExternalReportingService.cs:387-431`)
sends a WSJT-X-protocol **Clear** datagram at the top of *every* decode-cycle iteration, before that
cycle's Decode datagrams:

```csharp
await foreach (var batch in _decodeChannel.ReadAllAsync(ct).ConfigureAwait(false))
{
    if (!IsOutboundActive) continue;
    await SendToAllEnabledAsync(WsjtxDatagram.EncodeClear(AppId)).ConfigureAwait(false);   // ← every ~15s
    foreach (var r in batch.Results) { /* ... Decode ... */ }
}
```

This is exactly what the current spec asks for — `openspec/specs/external-reporting/spec.md:154-164`,
"Requirement: Outbound Clear message" / "Scenario: Clear sent on new decode cycle boundary" ("WHEN
a new 15-second decode cycle begins, THEN a Clear datagram SHALL be sent... before that cycle's
Decode datagrams"), and `REQUIREMENTS.md` FR-053. **The spec itself encodes the misunderstanding**
— this was a reasonable-sounding guess at implementation time (`design.md`'s own provenance note
calls Clear "simple and well established" and did not flag it as needing verification, unlike the
richer message types), but it does not match what real WSJT-X actually does.

I checked the real WSJT-X protocol's own documentation (`NetworkMessage.hpp`, the canonical
source every third-party tool including GridTracker2 implements against). Its doc comment for the
Clear message reads:

> "This message is sent when all prior 'Decode' messages in the 'Band Activity' window have been
> discarded and therefore are no longer available for actioning with a 'Reply' message. It is sent
> when the user erases the 'Band Activity' window and when WSJT-X closes down normally."

So real WSJT-X sends Clear on exactly two occasions: an **explicit operator "erase" action**, and
**graceful shutdown**. It is emphatically *not* tied to the ordinary 15-second decode cadence —
WSJT-X decodes just as often as OpenWSFZ does and never sends Clear for that. GridTracker2 (and
every other consumer) is built against that assumption: receiving Clear means "the whole
Band-Activity decode history is gone, purge whatever you were keeping in sync with it." OpenWSFZ
currently tells GridTracker to do that every single cycle, so nothing it plots is ever allowed to
persist past the next 15-second window — hence the shrinking map, and the stark contrast with a
real WSJT-X session's accumulated spread.

(Sources consulted: WSJT-X's `NetworkMessage.hpp` protocol documentation, cross-referenced via
public mirrors of the WSJT-X source and third-party protocol implementations, since no live
WSJT-X/GridTracker2 capture is available in this environment — same caveat `design.md` already
carries for the other message types.)

## 3. Required fix

Stop sending Clear on the per-cycle path entirely. OpenWSFZ has no equivalent of WSJT-X's "erase
Band Activity window" operator action today (checked — no such control exists in `web/`), so the
only real analogue currently available is graceful shutdown, which `ExternalReportingService`
already handles for the **Close** message (`StopAsync` → `SendCloseToAllAsync`,
`ExternalReportingService.cs:222-246`). Recommended shape:

1. **Remove** the `SendToAllEnabledAsync(WsjtxDatagram.EncodeClear(AppId))` call from
   `DecodeLoopAsync` (`ExternalReportingService.cs:395`). Decode datagrams continue to be sent
   per-cycle exactly as before — only the preceding Clear goes away.
2. **Add** a Clear send alongside the existing shutdown-time Close, in `StopAsync` (or folded into
   `SendCloseToAllAsync` — your call), so GridTracker's decode-history bookkeeping is told to reset
   when OpenWSFZ actually stops, matching the "sent... when WSJT-X closes down normally" clause.
   This is a nice-to-have for protocol fidelity, not the fix for the reported symptom (which is
   entirely explained by removing step 1) — if you judge it out of scope for this pass, flag it
   back rather than silently dropping it, same convention as always.
3. If OpenWSFZ ever grows an operator-facing "clear decode history" action, that would be the
   correct place to emit Clear too (Window = 0) — not applicable today, just noting it for future
   reference so nobody re-introduces a per-cycle Clear "to be safe."

No change is needed to `WsjtxDatagram.EncodeClear` itself — the wire format (header-only, no
payload) matches the real message; only the *cadence* at which OpenWSFZ calls it is wrong.

## 4. Tests

- `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:447-490`
  (`Decode_AllResultsSuppressed_StillSendsClear`) currently asserts the opposite of the fix —
  "Clear must still fire every cycle." This test needs to be **replaced**, not just patched: the
  underlying scenario it was protecting (Clear firing even when every decode in a batch is
  suppressed) no longer applies once Clear isn't sent per-cycle at all. Repurpose it (or add a new
  test) to assert the new invariant: **no Clear datagram is ever sent from the decode loop**,
  regardless of how many decodes survive the exclusion filter.
- Any other test in this file asserting a Clear-then-Decode ordering per cycle (skim for
  `MessageType.Clear` — check around the `TwoEnabledTargets_BothReceiveDecode` test,
  `ExternalReportingServiceTests.cs:146-157`, which currently expects to "see past" a Clear+Decode
  pair) needs the same treatment.
- Add a new test for the shutdown-time Clear (§3 step 2, if implemented): `StopAsync` sends Clear
  to every enabled target before/alongside Close.

## 5. Documentation

- `openspec/specs/external-reporting/spec.md:154-164` — rewrite "Requirement: Outbound Clear
  message" to reflect the corrected semantics (sent on graceful shutdown, not per decode cycle).
  This should go through a proper OpenSpec change (this is a behavioural correction to a shipped,
  archived capability) — suggested name `fix-external-reporting-clear-cadence`, or fold it into
  whichever change vehicle you're already using if `external-reply-decode-filter-bypass-option`
  (the other open dev-task) is in flight at the same time; they touch the same capability but are
  otherwise unrelated, so either one change covering both or two small ones both work — your call.
- `REQUIREMENTS.md` FR-053 — amend the Clear-cadence clause; add a revision-history row noting this
  corrects a defect present since the capability's original 2026-07-12 implementation (row 1.31).
- **`**User-facing:** yes`** if declared as its own change — this materially changes what an
  operator sees in GridTracker/JTAlert, arguably more impactful than most UI-only changes that get
  this label.

## 6. Acceptance Criteria

- [ ] **AC-1:** No Clear datagram is sent from the per-cycle decode loop, under any config
  (suppression on/off, targets present/absent, batch empty/non-empty).
- [ ] **AC-2:** Decode datagrams continue to be sent per-cycle exactly as before (no regression).
- [ ] **AC-3 (if implemented):** A Clear datagram is sent to every enabled target on graceful
  daemon shutdown.
- [ ] **AC-4:** `openspec validate --strict --all` passes.
- [ ] **AC-5:** Full test suite green; `Decode_AllResultsSuppressed_StillSendsClear` and any other
  Clear-cadence-dependent test updated to match, not merely disabled.
- [ ] **AC-6 — live confirmation (strongly recommended given how this was found):** re-run the
  Captain's own comparison — point a real GridTracker2 instance at a patched build for several
  minutes and confirm spots now accumulate on the map instead of shrinking every cycle. This is
  the only way to be sure the fix actually resolves the reported symptom, since no automated test
  in this repo drives a real GridTracker2 process.
- [ ] **AC-7:** `python3 tools/pre_merge_check.py` clean before this is called ready for merge
  (HK-006).

## 7. References

- `src/OpenWSFZ.Daemon/ExternalReportingService.cs:387-431` (`DecodeLoopAsync`), `:222-246`
  (`StopAsync`/`SendCloseToAllAsync`).
- `openspec/specs/external-reporting/spec.md:154-165`.
- `REQUIREMENTS.md` FR-053 (row 1.31 in the revision history).
- `tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs:146-157,447-490`.
- WSJT-X `NetworkMessage.hpp` protocol documentation (Clear message semantics) — consulted via
  public source mirrors, no live capture available in this environment; treat as the same
  best-effort-until-confirmed caveat `design.md` already carries for the richer message types.
- `dev-tasks/2026-07-19-external-reply-decode-filter-bypass-option.md` — the prior (still valid,
  separately requested) handoff on the Reply/decode-filter interaction; unrelated to this defect,
  does not need to change because of this finding.
