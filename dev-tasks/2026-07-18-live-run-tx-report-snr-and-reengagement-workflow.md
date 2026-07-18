# Handoff: TX-D04 (fixed report placeholder must go live) + D-CALLER-022 (no safe way to confirm a partner received RR73)

**Date:** 2026-07-18
**Prepared by:** QA engineer (log/ADIF/ALL.TXT review of a live acceptance run, `logs/openswfz-20260718T185751Z.log`, Captain report)
**Status:** Awaiting developer action
**Defect IDs:** TX-D04 (existing, promoted from "deferred" to "must fix" — Captain's explicit instruction), D-CALLER-022 (new, medium — investigation + design, not a prescribed diff)

---

## 0. Captain's stated position (authoritative — design to this)

Two items were raised after QA reviewed a ~2.5 hour live acceptance run still in progress. Both were
put to the Captain for a call; both came back as real issues, not accepted behaviour:

> 1. I re-engaged the qso as the partner did not seem to have received the message, I cancelled the
> QSO dialog each time while trying to get the correct response from the partner. maybe worth to
> look into such an issue as it is a regular thing to pursue a correct QSO.
>
> 2. This is a real issue that needs to be raised, the application is able to measure the snr, it
> should report the correct value.

Item 2 (TX-D04) is the more clear-cut of the two: fix it as stated, real SNR, no design discussion
needed. Item 1 (D-CALLER-022) is a workflow gap the Captain wants *investigated* — "worth to look
into" — not a specific fix he's prescribed. Treat section 2 as an implementation task and section 3
as a design/investigation task.

---

## 1. Evidence (both items found in the same review pass)

Live daemon log `logs/openswfz-20260718T185751Z.log`, ADIF register `ADIF.log`, decode log `ALL.TXT`,
all from the same in-progress session.

### 1.1 TX-D04 — every report transmitted today was the fixed placeholder

Every `TX → "X PD2FZ +00"` / `TX → "X PD2FZ R+00"` line in the session — ten separate QSOs, zero
exceptions:

```
TX → "OO0O PD2FZ +00" at 494 Hz
TX → "PA7D PD2FZ +00" at 1281 Hz
TX → "G6LTT PD2FZ +00" at 1281 Hz
TX → "DK3KM PD2FZ +00" at 1281 Hz
TX → "IQ4JO PD2FZ +00" at 2603 Hz
TX → "R5AV PD2FZ +00" at 2603 Hz
TX → "F5HNQ PD2FZ +00" at 730 Hz
TX → "R5AV PD2FZ +00" at 730 Hz
TX → "DA2JM PD2FZ +00" at 1220 Hz  (×2)
```

Meanwhile the *received* SNR for these exact exchanges was measured correctly and is sitting right
there in the same cycle's decode batch, e.g. `ALL.TXT`:

```
260718_195745  7.074 Rx FT8   3  0.5  494 PD2FZ OO0O JO11
260718_195815  7.074 Rx FT8   3  0.5  494 PD2FZ OO0O R-08     ← OO0O's real report of us
260718_200845  7.074 Rx FT8   1  0.9 1281 PD2FZ G6LTT IO91
260718_200915  7.074 Rx FT8  -3  0.9 1281 PD2FZ G6LTT R-07    ← G6LTT's real report of us
```

The confusion the other direction — the report *we* send *them* — never appears in `ALL.TXT` because
that file is Rx-only (`grep -c " Tx FT8" ALL.TXT` → `0`); it only exists inside the daemon's own
decode batch (`DecodeResult.Snr`, `src/OpenWSFZ.Abstractions/DecodeResult.cs:39`, an `int`, dB
relative to the 2500 Hz noise floor) at the moment the responder's/partner's decode is matched. That
value is right there, in scope, at every site below — it is simply not being used.

This is not new behaviour — it is the exact, already-named `TX-D04` placeholder from the original
`qso-caller` design (`openspec/changes/archive/2026-06-26-qso-caller/design.md:328-330`, echoed in
`openspec/specs/qso-caller/spec.md:194`), accepted as a v1 trade-off:

> **[Risk] Caller sends `+00` as fixed report (TX-D04 deferred)** → This is a known placeholder. The
> partner will log `+00` in their ADIF regardless of actual signal quality. Acceptable for v1;
> TX-D04 closes this gap.

It never had a tracked backlog entry outside that one paragraph, which is why it survived unnoticed
this long — see §4.

### 1.2 D-CALLER-022 — re-engaging a working partner has no safe, dedicated path

Around 22:01–22:07, on 40 m, partner PA7D:

```
22:01:00  QsoCallerService: roger report R-09 from PA7D — sending RR73.
22:01:13  QsoCallerService: TX → "PA7D PD2FZ RR73" ... QSO with PA7D complete!
22:01:47  FR-051: ADIF QSO logged — partner: PA7D          ← operator confirmed the dialog, ~34 s later

22:02:36  POST /api/v1/tx/engage-decode
          QsoControllerRouter: switching to Answerer for mid-exchange jump-in (D-CALLER-012).
          QsoAnswererService: jump-in to "SendRr73" with partner PA7D at 1281 Hz.
          TX → "PA7D PD2FZ RR73" ... QSO with PA7D complete!      ← dialog opened, not confirmed
22:03:35  (repeat)
22:04:34  (repeat)
22:06:30  (repeat)
```

Four extra live RR73 transmissions to a partner already fully worked and logged, each one an explicit
`POST /api/v1/tx/engage-decode` — i.e. the operator manually double-clicking PA7D's row again because,
per the Captain's account, PA7D did not appear to have received the first RR73 and he was trying to
get a genuine acknowledgement through. Each of the four follow-up confirmation dialogs was cancelled
(not confirmed) — correctly, since they were not new information — but the transmissions themselves
already went out over the air before the dialog was ever shown, and there is presently no way to avoid
that.

This is corroborated by the two-role architecture itself: `engage-decode`'s only tool for "make sure
they got it" is the same **mid-exchange jump-in** mechanism (`D-CALLER-012`) meant for engaging a
*stranger's* in-progress exchange — it re-arms a full state machine cycle and re-transmits, with no
concept of "this is the same partner I already completed a QSO with in this session; the operator
wants confirmation, not a fresh contact." The system has no lighter-weight "resend my last message to
my last partner" action, and no automatic detection that our own RR73 may not have landed (e.g. no
retry/resend triggered by absence of a subsequent "PA7D <other-callsign>" that would indicate PA7D
moved on satisfied — versus continuing to decode PA7D still calling CQ or working others, which is
the actual FT8-native signal that a partner didn't hear you and is still available).

The Captain's framing — "it is a regular thing to pursue a correct QSO" — says this is not a one-off;
operators routinely need to confirm a marginal-copy partner actually got the final message. Right now
the only lever available reuses jump-in, which fires a real transmission *before* the confirmation
dialog is even shown, so "cancel the dialog" only prevents the duplicate log entry, not the duplicate
transmission.

---

## 2. Action — TX-D04: send the real measured report, not a placeholder (Medium/Real, per Captain)

**Files:** `src/OpenWSFZ.Daemon/QsoCallerService.cs`, `src/OpenWSFZ.Daemon/QsoAnswererService.cs`

Four TX-composition sites currently hardcode the report; all four have (or can trivially be given)
access to the `DecodeResult.Snr` (or a persisted copy of it) for the decode that triggered them:

1. **`QsoCallerService.cs:818`** — `ExecuteTxReportAsync`, `var reportMessage = $"{partner} {tx.Callsign} +00";`
   Two call sites feed this:
   - Line 735 (`First` auto-engage mode): `r` (the matched `DecodeResult`) is in scope in the
     enclosing `foreach (var r in batch.Results)` loop — `r.Snr` is directly available, just not
     threaded through the `ExecuteTxReportAsync(...)` call.
   - Line 694 (deferred "pending responder" path, `None` mode / opposite-phase defer): the SNR needs
     to survive the same way `_pendingResponderGrid` already does (declared line 114, set at
     333–337/423–427, read at 660–664, cleared at 675/691/1109–1113) — add a sibling
     `_pendingResponderSnr` field following that exact existing pattern.
   Also check `_recentResponderDecodes` (`Dictionary<string, DecodeResult>`, line 122) — it already
   stores the whole `DecodeResult`, so the `None`-mode operator-click path (`SelectResponderAsync`,
   ~line 313) may already have `.Snr` available with no new field needed; confirm before duplicating
   state.

2. **`QsoCallerService.cs:984`** — `RetryOrAbortAsync`'s `WaitRr73` retry branch, retransmitting the
   report after no response. This should resend the *same* value chosen at (1), not recompute a new
   SNR from a stale/absent decode — persist whatever value (1) picked into a field (e.g. `_rstSent`,
   mirroring the existing `_rstRcvd` field at line 99) and reuse it here.

3. **`QsoAnswererService.cs:965`** — `ExecuteJumpInAsync`'s `EngagePoint.SendReport` case,
   `var msg = $"{partner} {tx.Callsign} R+00";`. `ExecuteJumpInAsync`'s signature
   (`partner, freqHz, point, rawPayload, tx, stoppingToken`) does not currently carry an SNR — trace
   back to wherever `EngageAtAsync`/the jump-in entry point resolves `freqHz`/`rawPayload` from a
   `DecodeResult` and thread `.Snr` alongside them the same way.

4. **`QsoAnswererService.cs:1056`** — `HandleWaitReportAsync`'s normal (non-jump-in) report reply,
   `var reportMessage = $"{partner} {ours} R+00";`. Same pattern as (1)/site-735: `r` is in scope in
   the enclosing `foreach (var r in batch.Results)` (starts line 1022) — `r.Snr` is directly
   available, just not used.

**Also update, once a real `_rstSent`-equivalent exists on each service:**
- `QsoCallerService.cs:898` — `RstSent = "+00", // fixed report (TX-D04 deferred)` in the ADIF
  `QsoRecord` builder → use the real value.
- `QsoAnswererService.cs:1180` — `RstSent = "R+00"` in `BuildAndWriteQsoRecordAsync` → same. Note the
  doc comment immediately above (`1171`, "same fixed `RstSent = "R+00"` … the report this daemon
  always sends") will need rewording once this is no longer true.

**Formatting:** SNR reports in FT8 are always two digits, zero-padded, explicit sign (`+00`, `-09`,
`+18`, capped at `±30` in the standard — WSJT-X clamps to that range). Match the existing formatting
used elsewhere for `_rstRcvd`/decode payloads (e.g. `IsRogerReport`/`IsSignalReport` parsing already
handles this shape on the receive side — check whether a shared formatter already exists before
writing a new one).

**Do not** touch the `R`-prefix logic itself (`R+00` vs `+00` is a protocol-position distinction —
caller sends a bare report, answerer sends an `R`-prefixed roger-report — that part is already
correct and orthogonal to *which* number follows the sign).

**Regression test:** at minimum, one test per service asserting the composed TX message contains the
triggering decode's actual `Snr` value (not a literal `+00`/`R+00`), covering both the immediate
(`First`/normal) and deferred (`None`-mode pending, retry-retransmit) paths enumerated above.

---

## 3. Action — D-CALLER-022: investigate a safe "confirm they got it" path (design task, not prescribed)

The Captain wants this **looked into**, not a specific mechanism dictated. Bring back a proposal
rather than a diff. Things worth weighing, none of them mandated:

- Whether a genuinely lighter-weight "resend my last TX message to my last-worked partner" action
  (distinct from `engage-decode`'s full mid-exchange jump-in, which is designed for *strangers'*
  exchanges) would better fit this use case — one that doesn't run the full state machine and doesn't
  silently accept re-arming against an already-logged partner without at least a distinguishing log
  line or UI cue.
- Whether the decode-panel UI should visually distinguish "this row is the partner I already
  completed a QSO with this session" strongly enough that a double-click is a deliberate, informed
  choice rather than something that can happen by habit (the worked-before indicators already exist
  per `qso-confirmation-band-awareness` — check whether they're actually visible/prominent on a row
  that's mid-exchange with a *different* station, which is what PA7D's row looked like for the three
  minutes in question).
- Whether the protocol itself already gives a better signal than "operator guesses": if PA7D is
  subsequently decoded still calling CQ or working someone else, that already inherently confirms our
  RR73 was heard and PA7D moved on — the *symptom* the Captain describes (worrying whether RR73 landed)
  may be addressable by surfacing that existing confirmation more clearly in the UI, rather than
  needing a new TX action at all. Worth checking with the Captain whether that would have resolved his
  actual concern in this session before building new send-side machinery.
- Any solution must not regress `D-CALLER-018`'s abort-is-a-hard-stop guarantee
  (`dev-tasks/2026-07-12-answerer-abort-hard-stop-and-reengage-timing.md`) — a new lighter-weight
  resend path is still a TX action and must be equally abortable.

No code changes are requested for this section yet — bring a short design note back (design.md-style
or just a proposal in this same file's follow-up) before implementing.

---

## 4. Process note — TX-D04 had no discoverable backlog entry

TX-D04 was named and its risk accepted in `qso-caller`'s original `design.md`, but that's the *only*
place it was tracked — no `openspec/qa-backlog.md` entry, no GitHub issue, nothing that would surface
it on a routine backlog scan. It sat for three weeks and would have kept sitting had this live run not
been reviewed line-by-line against the raw decode log. Backlog entries N10/N11 have been added below
pointing back to this file; going forward, any `(deferred)` risk accepted in a design.md should also
get a one-line `qa-backlog.md` pointer at archive time, the same way `N9` already does for the AOT/COM
gap — a risk accepted in a design doc that nobody re-reads is not the same as a risk being tracked.
