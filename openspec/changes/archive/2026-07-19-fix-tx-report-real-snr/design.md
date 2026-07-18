## Context

`QsoCallerService` and `QsoAnswererService` each have their own copy of a fixed-placeholder
signal report:

- `QsoCallerService.ExecuteTxReportAsync` (`:818`): `var reportMessage = $"{partner} {tx.Callsign} +00";`
- `QsoCallerService.RetryOrAbortAsync`'s `WaitRr73` branch (`:984`): same literal, recomputed on
  every retry.
- `QsoCallerService.ExecuteTxRr73Async`'s ADIF write (`:898`): `RstSent = "+00"`.
- `QsoAnswererService.HandleWaitReportAsync` (`:1056`): `var reportMessage = $"{partner} {ours} R+00";`
- `QsoAnswererService.ExecuteJumpInAsync`'s `EngagePoint.SendReport` case (`:965`): `var msg = $"{partner} {tx.Callsign} R+00";`
- `QsoAnswererService.BuildAndWriteQsoRecordAsync`'s ADIF write (`:1180`): `RstSent = "R+00"`.

`DecodeResult.Snr` (`src/OpenWSFZ.Abstractions/DecodeResult.cs:39`, `int`, dB relative to the
2500 Hz noise floor) is the real, already-measured value for the decode that triggers each of the
first, second, fourth, and fifth sites above — it is in scope (or one field-persistence hop away)
at every one of them except the jump-in `SendReport` case, which has no `DecodeResult` in scope at
all: `EngageAtAsync`'s only inputs are what the `engage-decode` HTTP handler forwards
(`partner`, `frequencyHz`, `theirCycleStart`, `point`, `rawPayload`), none of which currently
carry an SNR.

This exact shape of problem — a value that exists in the browser's decode-row data and in the
`engage-decode` handler's local scope, but not in `IQsoController.EngageAtAsync`'s signature — was
just solved for `rawPayload` by `fix-jump-in-rr73-adif-capture` (archived 2026-07-18,
`openspec/changes/archive/2026-07-18-fix-jump-in-rr73-adif-capture/design.md`). That change's
"Thread the raw payload through `EngageAtAsync` as a new trailing parameter" decision is reused
here verbatim for `Snr`, with one addition: `rawPayload` already existed server-side (parsed out
of `req.Message` by the handler itself); `Snr` does not — the `engage-decode` HTTP request body
today is `{message, frequencyHz, cycleStartUtc, confirm}` and has no SNR field. The browser
already has it, though: the decode-row object rendered into the table (`web/js/main.js:735`
JSDoc typedef) carries `snr:number` for every row, including the one the operator double-clicks
to trigger a jump-in — it is simply never forwarded in the POST body.

## Goals / Non-Goals

**Goals:**
- Every transmitted signal report (caller's bare report, answerer's `R`-prefixed roger-report)
  reflects the real measured `Snr` of the decode that triggered it, formatted as a standard FT8
  two-digit signed report.
- The ADIF `RstSent` field on both services reflects the same real value.
- A retry retransmits the exact value originally chosen, not a freshly (and potentially
  differently) computed one — matches existing `_rstRcvd`/`_lastTxMessage` persistence patterns.
- Jump-in cases that never compose a report this session (`SendRr73`, `Send73`) are left exactly
  as they are today — no new fabricated data, no regression.

**Non-Goals:**
- `D-CALLER-022` (re-engagement / "confirm they got it" workflow) — explicitly a design/
  investigation task per the Captain's own framing in the source dev-task, not a prescribed diff.
  Covered by a standalone note in this change directory, not by `tasks.md`.
- Any change to the `R`-prefix protocol-position logic itself (already correct, orthogonal).
- Any change to the wire format of anything other than `POST /api/v1/tx/engage-decode`'s request
  body (adds one field) and `IQsoController.EngageAtAsync`'s in-process signature.
- Recovering an SNR value for `EngagePoint.SendRr73`/`Send73` jump-ins — there is no decode to
  measure it from at that point in the exchange (same rationale as `PartnerGrid` staying `null` on
  jump-in).

## Decisions

**Add one shared `internal static string FormatSnrReport(int snr)` helper on `QsoCallerService`,
reused by `QsoAnswererService`.** Formats to FT8's standard two-digit signed report, clamped to
`±30` (`+00`, `-13`, `+30`). Both services already reuse `QsoCallerService.IsRogerReport` across
the assembly boundary-free `OpenWSFZ.Daemon` namespace for an analogous one-off reuse
(`fix-jump-in-rr73-adif-capture`'s design.md made the identical call for `IsRogerReport`) — same
justification applies here: a single formatter, not two copies. Answerer call sites prepend the
literal `"R"` themselves (unchanged protocol-position logic); the formatter itself is
prefix-agnostic.

**Persist the chosen value in a new `_rstSent` field on each service (mirroring the existing
`_rstRcvd` field), rather than recomputing it at each use site.** `QsoCallerService`'s retry branch
(`RetryOrAbortAsync`) and its ADIF writer (`ExecuteTxRr73Async`) both need the *same* value chosen
in `ExecuteTxReportAsync`, not a fresh decode lookup (there may be no fresh decode available on a
retry — that is the entire point of retrying). `QsoAnswererService`'s existing `_lastTxMessage`
field already carries the composed message text into its retry path unchanged, so no additional
threading is needed there for the *retry* case — but `BuildAndWriteQsoRecordAsync`'s ADIF write
still needs the plain numeric value separately, hence `_rstSent` on the answerer too.

**Thread `Snr` through `EngageAtAsync` as a new trailing `int snr` parameter**, exactly as
`fix-jump-in-rr73-adif-capture` threaded `rawPayload`: `IQsoController.EngageAtAsync` →
`QsoControllerRouter.EngageAtAsync` (pass-through) → `QsoAnswererService.EngageAtAsync` (stored in
a new `_jumpSnr` field, mirroring `_jumpRawPayload`) → `ExecuteJumpInAsync`'s new `int snr`
parameter, consumed only by the `EngagePoint.SendReport` case. `QsoCallerService.EngageAtAsync`
remains a no-op stub; it gains the parameter for signature parity only (`QsoCallerService.cs:397-401`,
already documented as "Not implemented... always delegates to QsoAnswererService"). The value
originates at the `engage-decode` HTTP handler (`WebApp.cs`), read from a new `Snr` field on
`EngageDecodeRequest`, itself populated by the browser from the same decode-row object it already
reads `message`/`frequencyHz` from (`r.snr`, already present in every row per the existing JSDoc
typedef — `web/js/main.js:735`) — no new server-side decode-matching logic is needed, unlike
`rawPayload` (which the handler parses out of `req.Message` itself); `Snr` simply rides along as
a fourth field on the same request the frontend already builds from row data it already has.

**At `ExecuteJumpInAsync` entry, explicitly (re)set `_rstSent = "R+00"` as a documented
placeholder** — mirroring the existing `_partnerGrid = null` treatment immediately above it in the
same method. This is correct only for the `SendRr73`/`Send73` jump-in cases (which never compose a
report this session); the `SendReport` case overwrites it with the real formatted value a few
lines later. Without this reset, `_rstSent` could otherwise leak a stale value from a *previous*
session's real report into an unrelated jump-in's `BuildAndWriteQsoRecordAsync` ADIF write.

**Do not thread `Snr` through `SelectResponderAsync`'s HTTP request body — read it back out of
`_recentResponderDecodes` instead.** `QsoCallerService` already maintains
`Dictionary<string, DecodeResult> _recentResponderDecodes` keyed by callsign for exactly this kind
of "operator selected this row, now go find its full decode data" lookup (used today to re-derive
`grid`). `SelectResponderAsync`'s existing `_recentResponderDecodes.TryGetValue(callsign, out var
recentDecode)` call already has the whole `DecodeResult` in hand — `recentDecode.Snr` is free.
Adding a new `_pendingResponderSnr` field (sibling to the existing `_pendingResponderGrid`)
follows the pattern already established for that field exactly. No wire-format change is needed on
`POST /api/v1/tx/select-responder` — unlike `engage-decode`, this path never left the server.

## Risks / Trade-offs

- **[Risk]** Forwarding `snr` through five layers (`web/js/main.js` → `EngageDecodeRequest` →
  `WebApp.cs` → `IQsoController` → `QsoControllerRouter` → `QsoAnswererService`/`QsoCallerService`)
  is mechanical but touches a public interface signature a second time in two weeks (after
  `rawPayload`). → **Mitigation**: same accepted rationale as before — `IQsoController` is
  in-process only, no external/wire-format consumer; compile-time-checked change, not breaking.
- **[Risk]** The browser-supplied `snr` in the `engage-decode` request body is trusted without
  server-side re-validation against a fresh decode batch (unlike `_recentResponderDecodes`'
  same-process lookup on the caller side). A stale or manipulated value would produce a
  misleading ADIF entry. → **Mitigation**: this is the same trust model the entire `engage-decode`
  endpoint already uses for `message`/`frequencyHz` (both browser-supplied, both already flow
  straight into a live transmission) — `snr` is strictly less consequential than those two
  (it affects only a logged report value, not what is transmitted to whom or on what frequency).
  Not a new trust boundary, just a new field crossing an existing one.
- **[Risk]** `DecodeResult.Snr`'s int range is not formally bounded by the type system; FT8's wire
  format caps at `±30` (WSJT-X clamps identically). An unclamped decoder Snr passed straight into
  `FormatSnrReport` could produce a 3-digit or malformed report. → **Mitigation**:
  `FormatSnrReport` clamps to `[-30, 30]` before formatting — matches WSJT-X's own behaviour and
  the FT8 spec.
- **[Risk]** `_rstSent`'s explicit reset at jump-in entry could be missed if a future
  `EngagePoint` case is added that also composes a real report. → **Mitigation**: the reset plus
  overwrite pattern exactly mirrors `_partnerGrid`'s existing, already-reviewed treatment one line
  above it — a future reviewer has a direct precedent to follow in the same method.

## Migration Plan

Not applicable — no data migration, no schema change. `POST /api/v1/tx/engage-decode`'s new `snr`
request field is additive and optional-in-spirit (a caller that omits it — e.g. an older cached
frontend bundle during a rolling deploy — gets `Snr` default `0`, which formats to `+00`, i.e.
today's existing placeholder behaviour; not a regression, a graceful default). Rollback is a plain
revert.

## Open Questions

None outstanding — `TX-D04`'s scope was fully resolved by the Captain in the source dev-task
("real SNR, no design discussion needed"). `D-CALLER-022` remains genuinely open by design; see the
standalone investigation note in this change directory.
