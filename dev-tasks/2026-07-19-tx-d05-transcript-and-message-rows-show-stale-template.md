# Handoff: TX-D05 — TX message rows and QSO Transcript show a hardcoded `+00`/`R+00` template, not the real report `fix-tx-report-real-snr` (TX-D04) now sends

**Date:** 2026-07-19
**Prepared by:** QA engineer (Captain report + source review, on top of `656bd7e`)
**Status:** OpenSpec change proposed and complete — ready for implementation (`/opsx:apply`)
**Defect ID:** TX-D05 (new — direct consequence of TX-D04 shipping; same feature family, next number
in that sequence since the Captain already knows it by that name)
**Severity:** Medium (display-only — no protocol, ADIF, or over-the-air content is wrong; the
operator cannot trust what the screen shows during/after a live QSO, which matters for exactly the
kind of "did they get it" judgement call raised in D-CALLER-022)

**Implementation ready — start here:** `openspec/changes/fix-tx-transcript-real-message/`, branch
`fix/tx-d05-transcript-real-message` (base: `origin/main` at `092c42a`, TX-D04 already merged),
proposal commit `a16436d`. `proposal.md`/`design.md`/`specs/**`/`tasks.md` are all complete —
`openspec status --change fix-tx-transcript-real-message` reports `isComplete: true`;
`openspec validate --strict --all` is 56/56 with this change included. Section 2 below is the
*original* rough sketch of a fix, superseded by `design.md`'s actual decisions (concrete API shape,
frontend caching strategy) and `tasks.md`'s 38 numbered tasks — read this section for the "why"/
evidence, but implement from `design.md`/`tasks.md`, not from the sketch below.

---

## 0. Captain's report (authoritative)

After `fix-tx-report-real-snr` (TX-D04, `656bd7e`) shipped, the Captain made a real QSO and reported:

> on screen snr reporting is still 0 db [screenshot of QSO Transcript, showing `EB3JT PD2FZ +00`
> repeated across every "sent report" line] . adif log is
> `<RST_SENT:3>-03<RST_RCVD:3>-15...` . what is real?

---

## 1. Answer: the ADIF is real; the screen is not

Confirmed by reading `656bd7e` end to end (not assumed):

- `QsoCallerService.ExecuteTxReportAsync` composes `_rstSent = FormatSnrReport(snr)` from the real
  `DecodeResult.Snr` of the triggering decode, transmits *that* string via `TransmitAsync`, and the
  same `_rstSent` value is what lands in `QsoRecord.RstSent` → the ADIF line. Same pattern, same
  correctness, on `QsoAnswererService`'s `SendReport` jump-in case and its normal `WaitReport` reply.
- The Captain's `-03`/`-15` ADIF line is the real, correct, over-the-air content. TX-D04 works.

The on-screen TX message rows (`#tx-msg-1/2/3`) and the QSO Transcript panel built on top of them are
a **separate, client-side-only rendering path** that was never connected to any of this — before or
after TX-D04. `web/js/main.js`, `renderMessageRows()`:

```js
if (effectiveRole === 'caller') {
  texts = [
    `CQ ${txCallsign} ${txGrid}`,
    `${p} ${txCallsign} +00`,      // ← string literal — not data
    `${p} ${txCallsign} RR73`,
  ];
  ...
} else {
  texts = [
    `${p} ${txCallsign} ${txGrid}`,
    `${p} ${txCallsign} R+00`,     // ← string literal — not data
    `${p} ${txCallsign} 73`,
  ];
  ...
}
```
(`web/js/main.js:187–201`)

This function is called purely off `txState` WebSocket pushes (`state`, `partner`, `role`) — it has
no access to, and was never given, the actual composed message text or a real SNR. It fabricates
"Row 2" from a template that assumed the report was always `+00`, which was *true* right up until
`656bd7e` shipped — the template and reality happened to coincide by construction, not by design.

The QSO Transcript feature (`qso-transcript-panel`, FR-062, built the same day as this fix, `main.js:229–232`)
compounds this: rather than capturing what was actually sent, it just logs whichever synthetic
template string `renderMessageRows` was about to render for the row that just went active:

```js
if (hasEnteredNewActiveTxState(prevState, state, activeStates)) {
  const activeIndex = activeStates.indexOf(state);
  appendTranscriptEntry('sent', texts[activeIndex], currentTxPartner);
}
```

That feature's own `design.md` (`openspec/changes/archive/2026-07-18-qso-transcript-panel/design.md:5-9`)
says outright the message rows show "*the template for the current exchange step*" — so this was a
known, accepted characteristic of the *display*, just never connected to the fact that TX-D04 was
about to make the template and reality diverge. No code in `qso-transcript-panel` is wrong relative to
what it set out to do; it faithfully logs the template, and the template is now stale.

**Confirmed there is no existing channel the frontend could read the real value from even if it tried:**
- `TxStatusResponse` (`src/OpenWSFZ.Web/AppJsonContext.cs:151-157`): `State`, `Partner`,
  `AutoAnswerEnabled`, `Role`, `CallerPartnerSelect`, `Keying` — no message text, no SNR.
- `WsTxStateMessage` (the `txState` WebSocket push, same file `:132-140`): `Type`, `Role`, `State`,
  `Partner`, `AutoAnswerEnabled`, `Keying`, `AbortReason` — same gap.
- `QsoAnswererService` already tracks the real sent text internally as `_lastTxMessage` (set at every
  TX-composition site — lines 898, 994, 1017, 1089, 1167 — and reused verbatim for retries at 1273)
  but it is never surfaced through either of the above.
- `QsoCallerService` has **no equivalent field at all** — `reportMessage`/`rr73Message`/`cqMessage`
  are local variables inside their respective methods, never persisted.

So this isn't "the frontend has the data and formats it wrong" — the real value genuinely never
leaves the daemon process today for either role.

---

## 2. Original rough sketch (superseded — see `design.md`/`tasks.md` for the actual plan)

This section is kept for history/context only; do not implement from it directly.

**Backend:**
- Add a `_lastTxMessage` field to `QsoCallerService`, mirroring `QsoAnswererService`'s existing one —
  set it at the same three composition sites TX-D04 already touched (`ExecuteTxReportAsync`,
  `RetryOrAbortAsync`'s report-retransmit branch, and the CQ/RR73 composition sites for row 1/3
  completeness) rather than leaving those as bare local variables.
- Add a `LastTxMessage` (or similarly named) field to `TxStatusResponse` and `WsTxStateMessage`,
  threaded from whichever service (`QsoCallerService`/`QsoAnswererService`) is currently active via
  `QsoControllerRouter`, so both the polled status endpoint and the WebSocket push carry the real
  last-transmitted text.

**Frontend:**
- `renderMessageRows` should prefer the real `lastTxMessage` for whichever row is/was actually
  transmitted this session, falling back to the current template only for rows not yet reached (there
  is no real content for "Row 3: RR73" to show before Row 2 has actually fired — the template remains
  correct and honest for *future*, not-yet-transmitted rows).
- `appendTranscriptEntry('sent', ...)` (`main.js:231`) should log the real transmitted text once
  available, not `texts[activeIndex]` unconditionally.

**Scope check:** confirm whether `qso-transcript-panel`'s existing tests
(`web/js/qsoTranscript.test.js`) assert against the literal template strings anywhere — if so those
assertions will need updating alongside this fix, not because they're wrong today, but because the
behaviour they pin is exactly what's being changed.

**Regression test:** at minimum, an integration-level test asserting that after a real TX-D04-style
report transmission with a non-zero SNR, the polled `TxStatusResponse` (or WS push) reflects that same
non-`+00` value — this is the gap that let TX-D05 ship invisibly alongside TX-D04 in the first place;
a test at the seam between "backend composes real value" and "frontend can see it" would have caught
this before the Captain had to.

This sketch turned out to be right in direction but incomplete on one point: it doesn't say what
happens once the state moves *past* a row (e.g. from `TxReport` to `TxRr73`) — if the backend only
ever exposes "the single last transmitted message," a naive frontend read of that one field would
lose row 2's real text the moment row 3 is sent. `design.md`'s actual decision resolves this: the
frontend caches the real text per row locally, at the moment each transition fires, rather than
re-deriving history from the backend — see `design.md`'s "Decisions" section for the full reasoning
and the alternatives considered (a three-field backend, an event-sourced push) and why they were
rejected in favour of this one-field-plus-client-cache approach.

## 2a. Actual plan — see the OpenSpec change

Read, in order: `openspec/changes/fix-tx-transcript-real-message/proposal.md` (what/why),
`design.md` (the real design — API shape, frontend caching decision, risks/trade-offs, all with
alternatives considered), `specs/{qso-caller,qso-answerer,qso-controller,web-frontend}/spec.md`
(the testable contract each capability must satisfy), `tasks.md` (38 numbered, dependency-ordered
tasks, from the `IQsoController.LastTxMessage` property through to frontend row-caching and
regression tests). Run `/opsx:apply` against this change, or work through `tasks.md` directly.

---

## 3. Process note

TX-D04's own dev-task (`dev-tasks/2026-07-18-live-run-tx-report-snr-and-reengagement-workflow.md`) was
scoped to the backend/ADIF path only — reasonably, since that's where the evidence pointed at the
time. Neither that write-up nor the TX-D04 implementation PR touched, or was asked to touch, any
frontend file. The gap only became visible because the Captain immediately made a real QSO and looked
at the screen. Worth noting for future "fix the backend value" tasks in this codebase: TX panel state
is rendered from a separate, intentionally-decoupled template system (`renderMessageRows`), so a
backend value becoming "real" does not automatically propagate to the UI — that always needs its own
explicit wiring check.
