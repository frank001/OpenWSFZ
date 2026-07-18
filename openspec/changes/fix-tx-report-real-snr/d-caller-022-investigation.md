# D-CALLER-022 — investigation note: safe "confirm they got it" re-engagement

**Status:** Investigation only, per the Captain's explicit framing in
`dev-tasks/2026-07-18-live-run-tx-report-snr-and-reengagement-workflow.md` §0/§3 — "worth to look
into," not a prescribed fix. **No code changes accompany this note.** Bring it back to the Captain
for a decision before any implementation work is scheduled.

## The observed problem

During a live run, the operator worked `PA7D` to completion (RR73 sent, ADIF logged), then
double-clicked `PA7D`'s row four more times over ~5 minutes because the partner did not appear to
have received the closing RR73. Each double-click fired a real, live RR73 retransmission over the
air via the mid-exchange jump-in mechanism (`D-CALLER-012`/`EngageAtAsync`) *before* the
confirmation dialog was ever shown — cancelling the dialog prevented a duplicate ADIF entry, but
not the duplicate transmission. The Captain: "it is a regular thing to pursue a correct QSO" —
this is routine operator behaviour on marginal-copy contacts, not a one-off.

## Root cause

`engage-decode`'s only tool for "make sure they got it" is the same mid-exchange jump-in mechanism
designed for engaging a *stranger's* in-progress exchange. It has no concept of "this is the same
partner I already completed a QSO with this session; the operator wants confirmation of receipt,
not a fresh contact" — it re-arms a full state-machine cycle and transmits unconditionally once the
phase check passes, with no lighter-weight path and no distinguishing UI/log signal that the target
row is already-worked.

## Options considered (none decided — Captain's call)

1. **A genuinely lighter-weight "resend my last TX message to my last-worked partner" action**,
   distinct from `engage-decode`'s full jump-in. Would need to still respect `D-CALLER-018`'s
   abort-is-a-hard-stop guarantee (any TX action must remain equally abortable) and would need its
   own confirmation-before-transmit ordering (unlike jump-in's current transmit-before-confirm
   ordering, which is exactly what made the observed incident possible — four live transmissions
   before four cancelled dialogs).
2. **UI prominence for "this row is already worked this session."** The `qso-confirmation-band-
   awareness` worked-before indicators already exist server-side and are rendered per-row, but it
   is not yet confirmed whether they are visually prominent enough on a row that is mid-exchange
   with a *different* station (which is what `PA7D`'s row looked like for the several minutes in
   question — worked, but not the currently-engaged partner). Worth a targeted check before
   building any new TX action: does surfacing "you already worked this station" more strongly
   change operator behaviour without any new machinery at all?
3. **Let the protocol's own signal do the confirming.** If `PA7D` is subsequently decoded still
   calling CQ or working someone else, that already inherently proves the RR73 was received and
   `PA7D` moved on — arguably the *actual* information the operator was seeking by re-engaging.
   Surfacing that existing decode fact more clearly (e.g. a passive "PA7D worked another station at
   HH:MM — your RR73 landed" note) might resolve the underlying worry with zero new TX capability.
4. **Ask the Captain directly** whether option 3 would have resolved his actual concern in this
   session, before investing in new send-side machinery at all — cheapest way to find out whether
   this is a UI/information gap or a genuine missing-feature gap.

## Constraint any eventual solution must respect

Must not regress `D-CALLER-018`'s abort-is-a-hard-stop guarantee
(`dev-tasks/2026-07-12-answerer-abort-hard-stop-and-reengage-timing.md`) — whatever mechanism is
chosen is still a TX action and must remain equally abortable, with no armed-but-uncancellable
window wider than what jump-in already has today.

## Recommendation for the Captain

Start with option 4 (ask) before option 2 (cheap UI check) before option 1 (new TX action) — in
that order of cost. This note intentionally does not pick one; it is the Captain's decision per
the source dev-task's own framing.
