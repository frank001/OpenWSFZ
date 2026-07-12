# DEV TASK — `QsoCallerService`/`QsoAnswererService` never call `KeyUpAsync` after a normal transmission; every real TX cycle relies on the 20 s watchdog to release PTT

**Date:** 2026-07-12
**OpenSpec change:** `cat-tx-ptt` (implementation review) — no spec text changes needed; this is a
code defect in the implementation (the *callers* of `IPttController`, not the controllers
themselves), found during hardware acceptance (Gate 16, the confirmed two-way QSO / release gate R3).
**Branch:** `feat/cat-tx-ptt`.
**Status:** New. Found during a real, live hardware-acceptance attempt: the Captain reported the rig
was heard and answered by a real station (HB9HYO) but the QSO could not be completed, and pointed QA
at `logs/openswfz-20260712T152156Z.log` and `ALL.TXT`.
**Found by:** QA, diagnosing the log against the `cat-tx-ptt` implementation.
**Severity:** **Critical — merge-blocking.** This is not a rare edge case; it fires on **every
single transmission** made with either new PTT method (`CatCommand` or `SerialRtsDtr`). It defeats
the entire purpose of this change: the transmitter is not reliably keyed *and unkeyed* under real
operation.

---

## Evidence

`logs/openswfz-20260712T152156Z.log`, the QSO with HB9HYO (times are local, +02:00):

```
17:28:45.377 [INF] SerialRtsDtrPttController: KeyDown — PTT asserted ("Rts").
17:28:45.371 [DBG] QsoAnswererService: state → "TxReport" (partner: HB9HYO).
17:28:58.129 [DBG] QsoAnswererService: state → "WaitRr73" (partner: HB9HYO).
17:29:05.392 [ERR] SerialRtsDtrPttController: watchdog fired after 20014 ms — forcing PTT release.
```

The state machine advances to `WaitRr73` at 17:28:58 — i.e. it believes the transmission is
complete and it is time to listen — but **no `KeyUp — PTT released` line exists anywhere between
the `KeyDown` and the watchdog firing.** The rig's PTT line stayed physically asserted for a further
**~7.3 seconds** after `QsoAnswererService` had already moved on to listening for a reply, until the
20-second failsafe watchdog forced it off. This pattern repeats identically for every transmission in
this session (5 separate watchdog-forced releases logged in a 4-minute window: 17:27:05, 17:27:35,
17:29:05, 17:29:35, 17:30:05, 17:30:35), for both `QsoCallerService` (CQ calls) and
`QsoAnswererService` (the HB9HYO exchange). Even the one cycle in this log that *wasn't* forced by
the watchdog (17:22:45–17:23:02) still released PTT ~17.6 s after key-down — roughly 5 s later than
the expected ~12.7 s (12 640 ms audio + `tailTimeMs`) — meaning normal release is *also* not prompt
even when it does eventually happen. `ALL.TXT` confirms HB9HYO answered PD2FZ/P's CQ at 15:28:00 UTC
and nothing further from HB9HYO was ever decoded — consistent with the daemon's own receiver still
being held in TX for several extra seconds into what should have been its next listen window.

## Root cause

`IPttController.KeyDownAsync` asserts PTT and blocks until the loaded audio buffer has finished
playing; `KeyUpAsync` is a **separate call** the caller must make afterward to actually release PTT
(wait `TailTimeMs`, then de-assert the line/send the unkey command). This is correct and
intentional for `CatPttController`/`SerialRtsDtrPttController` — see their own doc comments
("`KeyDownAsync` sequence: assert PTT → wait `LeadTimeMs` → play audio → await completion.
`KeyUpAsync` sequence: stop playback → wait `TailTimeMs` → release PTT.") — but it is a **behaviour
change** from the previous `AudioOnlyPttController`-only world, where forgetting to call `KeyUpAsync`
after a normal transmission was harmless: `AudioOnlyPttController.KeyUpAsync` just stops WASAPI
playback that has, by construction, already finished, so skipping it had no observable effect (VOX
drops out on its own the instant audio stops). Nobody updated the *callers* for the new contract.

Confirmed by inspection — `KeyUpAsync` is called at exactly four places in the whole daemon, **all
of them abort paths**, none of them the normal-completion path:

```
src/OpenWSFZ.Daemon/QsoAnswererService.cs:274   (SafeAbortToIdleAsync-equivalent, plain abort)
src/OpenWSFZ.Daemon/QsoAnswererService.cs:1288  (graceful-stop abort)
src/OpenWSFZ.Daemon/QsoCallerService.cs:234     (SafeAbortToIdleAsync, plain abort)
src/OpenWSFZ.Daemon/QsoCallerService.cs:1038    (SafeAbortToIdleAsync, graceful-stop)
```

The actual transmit helper in both services brackets only `KeyDownAsync`, never follows it with
`KeyUpAsync`:

```csharp
// QsoCallerService.cs:930-960 (TransmitAsync) — QsoAnswererService.cs:~1160-1199 is structurally identical
_keying = true;
PublishKeyingTransition();
try
{
    await _pttController.KeyDownAsync(linked.Token).ConfigureAwait(false);
}
finally
{
    _keying = false;
    PublishKeyingTransition();
}
linked.Token.ThrowIfCancellationRequested();
_logger.LogDebug("QsoCallerService: TX complete for \"{Message}\".", message);
// <-- caller returns here; KeyUpAsync is never called. Every subsequent state
//     transition (WaitAnswer/WaitRr73/etc.) proceeds with PTT still asserted.
```

The only reason this has *ever* worked at all is `PttWatchdog`'s 20-second failsafe — which exists
specifically to catch bugs, not to be the normal release mechanism for every transmission. This also
means `IPttController.cs`'s own interface doc comment is stale: it still describes the contract in
purely `AudioOnlyPttController` terms ("`KeyDownAsync` starts WASAPI audio playback; `KeyUpAsync`
stops it") and never states the now-critical rule that every `KeyDownAsync` **must** be followed by a
`KeyUpAsync` in the caller's normal-completion path, not only its abort path — worth fixing alongside
the code, since this is exactly the kind of contract gap that let the bug go unnoticed through code
review.

## Why this is worse than "the rig keys a bit long"

1. **It breaks FT8 timing outright.** FT8 depends on precise 15-second-aligned TX/RX slot boundaries.
   Holding PTT asserted ~7 extra seconds past the intended tail time keeps the rig transmitting (and
   the daemon's own receiver blind) well into what should already be the next receive window — this
   is almost certainly why HB9HYO's continuation of the exchange, if sent, was never decoded, and
   directly explains "someone did respond, but I was not able to finish the QSO."
2. **Every single transmission relies on the watchdog.** This is not an occasional/rare trigger — the
   watchdog fired on effectively every TX cycle in this session. A mechanism explicitly designed as a
   last-resort failsafe ("this should never fire during correct operation" — `PttWatchdog`'s own
   design rationale) is now the *primary* release path, which also means a genuine watchdog
   regression would be much harder to notice separately, since it fires constantly regardless.
3. **CAT-command PTT (`CatPttController`) has the identical gap** and is equally broken, even though
   this particular log happened to be running `SerialRtsDtr` — this is not a serial-specific bug.

## Recommended fix

In both `QsoCallerService.TransmitAsync` (`QsoCallerService.cs:930-960`) and
`QsoAnswererService`'s equivalent (`QsoAnswererService.cs:~1160-1199`), call
`_pttController.KeyUpAsync(...)` immediately after `KeyDownAsync` completes — in the **same**
`finally` block already wrapping the keying-state broadcast, so PTT is released exactly once
regardless of whether `KeyDownAsync` returned normally, threw, or was cancelled:

```csharp
_keying = true;
PublishKeyingTransition();
try
{
    await _pttController.KeyDownAsync(linked.Token).ConfigureAwait(false);
}
finally
{
    // KeyUpAsync must run here, not only from the abort path (SafeAbortToIdleAsync) —
    // that path is for operator/watchdog-initiated abort of an in-progress *session*, this
    // is the ordinary, successful end of a single transmission. Use CancellationToken.None so
    // release still happens even if `ct`/`linked.Token` is already cancelled — mirrors both
    // controllers' own KeyUpAsync bodies, which already tolerate being called when nothing is
    // asserted (a safe no-op) so this is safe to call unconditionally.
    try
    {
        await _pttController.KeyUpAsync(CancellationToken.None).ConfigureAwait(false);
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex, "QsoCallerService: KeyUpAsync threw after TransmitAsync — ignoring.");
    }
    _keying = false;
    PublishKeyingTransition();
}
linked.Token.ThrowIfCancellationRequested();
```

Order the two `finally`-block actions so `KeyUpAsync` runs **before** `_keying = false` /
`PublishKeyingTransition()` — the keying broadcast should reflect "still keyed" for the brief window
while `KeyUpAsync`'s own `TailTimeMs` wait is in progress, not flip to "not keying" prematurely while
PTT is still physically asserted.

**Do not** attempt to fix this by shortening the watchdog timeout instead — that would only reduce
the *duration* of the stuck-key window per cycle, not eliminate the underlying missing call, and
would leave every transmission still relying on a failsafe as its normal path.

**Also fix:** `src/OpenWSFZ.Abstractions/IPttController.cs`'s doc comment — update it to state
plainly that a caller **must** call `KeyUpAsync` after every `KeyDownAsync` in the normal-completion
path, not only on abort/cancellation; the current wording ("`KeyDownAsync` starts WASAPI audio
playback; `KeyUpAsync` stops it") predates `CatPttController`/`SerialRtsDtrPttController` and reads
as if `KeyUpAsync` is optional cleanup rather than a mandatory pairing.

## Tests required

- A `QsoCallerServiceTests.cs`/`QsoAnswererServiceTests.cs` case (both files already exist and use a
  test-double `IPttController` recording call order, per the existing `TestPttController`-style
  pattern already used elsewhere — e.g. `tests/OpenWSFZ.Web.Tests/PttTestEndpointTests.cs`) asserting
  that a normal, successful transmission cycle calls `KeyDownAsync` **immediately followed by**
  `KeyUpAsync`, with no intervening state transition — the exact regression this task fixes.
- A case confirming `KeyUpAsync` runs even when the transmission is cancelled mid-`KeyDownAsync`
  (linked-token cancellation), not only on full success.
- Re-run `PttWatchdogTests.cs`, `CatPttControllerTests.cs`, `SerialRtsDtrPttControllerTests.cs`
  unmodified — this fix is entirely on the caller side; no controller-level assertion should change.

## Verification

1. `dotnet build` / `dotnet test` — expect unchanged pass counts plus the new caller-side tests, all
   green.
2. Manual, hardware-required (this is exactly what Gate 16 needs to re-attempt): with
   `ptt.method = "SerialRtsDtr"` (or `"CatCommand"`) and a real QSO in progress, confirm
   `SerialRtsDtrPttController: KeyUp — PTT released` (or the CAT equivalent) now appears within
   roughly `tailTimeMs` of each transmission's audio ending — **not** the 20-second watchdog line.
   Confirm the watchdog does **not** fire during normal operation across a full multi-exchange QSO.
3. Repeat the actual failed scenario: attempt a real two-way QSO end-to-end and confirm it completes
   (RR73 both ways) now that the rig returns to receive promptly after each of the daemon's own
   transmissions.
4. `openspec validate --strict --all` — expect unchanged pass count (no spec text is changing).

## QA re-review

QA will re-run the manual reproduction in "Verification" step 2/3 directly (watching the rig and the
log together, not just trusting the new unit tests), confirm the new caller-side tests assert call
*order*, not just call *presence*, confirm `IPttController.cs`'s doc comment is corrected, and confirm
the full suite plus `openspec validate --strict --all` are green before sign-off. **Hardware
acceptance Gates 14–16 (`openspec/changes/cat-tx-ptt/tasks.md`) must be re-attempted from scratch
after this fix lands — none of the keying observed before this fix should be considered valid
evidence for those gates**, including any prior informal confirmation that "the radio responds" —
the rig keying at all (Gates 14/15) is necessary but not sufficient; it must also *unkey* promptly
enough to hold FT8 timing for Gate 16 to mean anything.

## References

- `logs/openswfz-20260712T152156Z.log` — the session this was found in; five separate
  watchdog-forced releases in the first ~4 minutes of real automated operation, all traceable to this
  gap.
- `ALL.TXT` — HB9HYO's answer to PD2FZ/P's CQ (line 294, `260712_152800`), with nothing further from
  HB9HYO decoded afterward — consistent with the daemon's own receiver being unavailable slightly
  too long after each of its own transmissions.
- `src/OpenWSFZ.Daemon/QsoCallerService.cs:930-960` (`TransmitAsync` — missing `KeyUpAsync` call) and
  `:234`, `:1038` (the only two `KeyUpAsync` call sites, both abort-only).
- `src/OpenWSFZ.Daemon/QsoAnswererService.cs:~1160-1199` (transmit helper — identical gap) and `:274`,
  `:1288` (the only two `KeyUpAsync` call sites, both abort-only).
- `src/OpenWSFZ.Daemon/SerialRtsDtrPttController.cs`, `src/OpenWSFZ.Daemon/CatPttController.cs` — both
  correctly implemented per their own documented `KeyDownAsync`/`KeyUpAsync` contract; **not** where
  the bug is. Do not modify either controller to "fix" this.
- `src/OpenWSFZ.Daemon/PttWatchdog.cs` — the failsafe that has been masking this defect by
  eventually releasing PTT every time, ~7+ seconds late.
- `src/OpenWSFZ.Abstractions/IPttController.cs` — stale doc comment to correct alongside the fix.
- `openspec/changes/cat-tx-ptt/hardware-acceptance.md` — Gates 14–16, to be re-attempted after this
  fix lands.
