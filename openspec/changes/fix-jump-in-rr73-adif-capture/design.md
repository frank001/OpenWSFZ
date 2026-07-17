## Context

`QsoAnswererService.ExecuteJumpInAsync` (`QsoAnswererService.cs:892-979`) drives the three
mid-exchange jump-in cases introduced by `D-CALLER-012`. Two of the three already reach the
normal ADIF-writing machinery: `EngagePoint.SendReport` advances into `WaitRr73` (which, on the
partner's next `RR73`/`RRR`, calls the shared `ExecuteTx73Async`), and `EngagePoint.Send73` calls
`ExecuteTx73Async` directly. Only `EngagePoint.SendRr73` (`:961-970`) short-circuits: it
transmits RR73 and calls `SafeAbortToIdleAsync` without ever building or writing a `QsoRecord`.

`ExecuteTx73Async` (`:1098-1156`) is the canonical pattern: build a `QsoRecord`, branch on
`tx.QsoConfirmation` (publish via `_txEventBus.PublishQsoReview` if the browser will confirm and
call `POST /api/v1/tx/log-qso`, or call `_adifLog.AppendQsoAsync` directly otherwise — never
both, per `qso-log-dialog` D3), set `QsoComplete` and log ahead of the idle-abort, then abort.

The `_rstRcvd` field is also hardcoded to `"+00"` at jump-in entry (`:910`), regardless of what
the partner's decoded message actually contained. `QsoCallerService.IsRogerReport`
(`QsoCallerService.cs:1327-1334`) and its call site (`:847-851`) already implement the correct
normalization — strip a leading `R` from an `R±NN` roger report, otherwise keep the payload
as-is (covers a bare `RRR`) — for the equivalent non-jump-in case. The jump-in path needs the
same logic but currently has no access to the decoded payload text at all: `EngageAtAsync`
(`IQsoController.cs`, `QsoControllerRouter`, `QsoAnswererService`, `QsoCallerService` stub) has
no parameter for it, even though the exact text is sitting in `WebApp.cs`'s `engage-decode`
endpoint handler (`info`, used at `:1485-1517` to decide which `EngagePoint` to dispatch) and is
simply not forwarded.

## Goals / Non-Goals

**Goals:**
- `EngagePoint.SendRr73` jump-ins write a `QsoRecord` on completion, using the same
  confirmation-gated publish-or-direct-write branch as `ExecuteTx73Async`.
- `RstRcvd` on this path reflects the actual decoded payload (roger report or bare `RRR`),
  not a fixed placeholder.
- No behavior change to the other two jump-in cases, to `ExecuteTx73Async` itself, or to
  `PartnerGrid` (remains `null` on this path — correct, out of scope).

**Non-Goals:**
- Reopening the caller-side watchdog/retry timing (`D-008` — already correct, already tested;
  see the dev-task's "Finding B").
- Recovering `PartnerGrid` for jump-ins (see `dev-tasks/2026-07-12-adif-partner-grid-not-captured.md`
  Part 2 — genuinely unrecoverable, not this change).
- Any wire-format change to `POST /api/v1/tx/engage-decode`'s request or response shape. The
  payload text already exists server-side at the call site; only an in-process parameter is
  added between there and `ExecuteJumpInAsync`.

## Decisions

**Extract a shared record-build-and-write helper, called from both `ExecuteTx73Async` and the
new `SendRr73` case, rather than duplicating the `QsoRecord`/confirmation-branch block.**
Alternative considered: copy the block verbatim into the `SendRr73` case (as tasks in the source
dev-task sketch it). Rejected in favor of extraction — the two call sites differ only in
`RstSent` (`ExecuteTx73Async` always sends `"R+00"` as the *original* report it sent earlier in
the QSO, replayed into the record; the `SendRr73` jump-in never sent a report of its own, so
`RstSent` there is likewise `"R+00"`, i.e. actually identical) and in which state
(`QsoState.Tx73` vs the jump-in's existing `QsoState.Tx73`, also identical) is set beforehand.
Given the two call sites turn out to need identical parameters, a small private
`BuildAndWriteQsoRecordAsync(TxConfig tx, string partner, CancellationToken ct)` helper removes
the duplication cleanly with no parameter mismatch to reconcile.

**Thread the raw payload through `EngageAtAsync` as a new trailing `string rawPayload`
parameter, rather than re-deriving `RstRcvd` from state already held in
`QsoAnswererService`.** The service has no memory of the payload that triggered a jump-in — it
only ever saw the previous, now-expired QSO's own transcript (if any at all; tonight's incident
crossed a Caller→Answerer role switch, so `QsoAnswererService` never ran the original exchange).
The only place the text exists is the `engage-decode` HTTP handler. `QsoCallerService.EngageAtAsync`
is already a documented no-op stub (`QsoCallerService.cs:397-401`, "Not implemented... always
delegates to QsoAnswererService") — it gains the parameter for signature parity only, consistent
with its existing pattern for the other three parameters.

**Reuse `QsoCallerService.IsRogerReport`'s normalization logic rather than introducing a second
copy.** `IsRogerReport` is `internal static`, in the same assembly (`OpenWSFZ.Daemon`), so
`QsoAnswererService` can call it directly — no need to relocate it to a shared utility class for
a one-call reuse. If a third consumer appears later, promoting it to a shared helper becomes
worth reconsidering; not now.

## Risks / Trade-offs

- **[Risk]** Extracting the shared helper touches `ExecuteTx73Async`, a well-tested existing
  method, increasing the diff's blast radius slightly beyond the minimal "add an ADIF write to
  one case" framing. → **Mitigation**: the extraction is a pure refactor (move the existing block
  into a helper, call it from the existing call site) with zero behavior change; the full
  existing `ExecuteTx73Async` test suite re-runs unmodified as the regression guard.
- **[Risk]** Forwarding `rawPayload` through four layers (`WebApp.cs` → `IQsoController` →
  `QsoControllerRouter` → `QsoAnswererService`/`QsoCallerService`) is mechanical but touches a
  public interface signature. → **Mitigation**: `IQsoController.EngageAtAsync` is internal to this
  daemon (no external consumers across a process boundary — it's an in-process interface used by
  `WebApp.cs` and the two QSO services), so this is a compile-time-checked, safe signature change,
  not a breaking wire-format change.
- **[Risk]** A malformed or unexpected `rawPayload` (e.g. empty string, from a future caller that
  doesn't have real payload text) could make `RstRcvd` empty rather than a sensible placeholder.
  → **Mitigation**: apply the same `IsRogerReport`/fallback-to-as-is logic uniformly; an empty or
  unrecognized payload simply becomes `RstRcvd = rawPayload` (empty string), which is a strictly
  more honest representation of "we don't actually know" than fabricating `"+00"` — matches the
  proposal's stated goal of not fabricating data.

## Migration Plan

Not applicable — no data migration, no schema change, no external API change. The fix ships in a
single PR; rollback is a plain revert if needed. Existing `ADIF.log` entries are untouched.

## Open Questions

None outstanding — the dev-task this change formalizes already resolved the scope questions
(Finding A in scope, Finding B explicitly not) with the Captain.
