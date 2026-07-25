# Working notes — fix-cycle-boundary-clock-drift 9.5 live re-confirmation, 40m band, 2026-07-24 night

Live scratch notes kept during an unattended overnight run so nothing gets lost before the final
`report.md` is written in the morning. Not the report itself.

## Session structure

- Sub-session A: 22:27:53Z–23:06:55 local effective start/kill (`logs/openswfz-20260724T202531Z.log`).
  Ended by a **deliberate** kill as part of validating the overnight auto-recovery supervisor
  (see `hk013-unattended-run-supervisor-standard.md`), not a genuine failure. First kill attempt
  (23:04:55) used a bogus PID (`ps -W` MSYS-synthetic column bug) and silently no-op'd — sub-session
  A actually continued uninterrupted until the *second*, corrected kill at 23:06:55.
- Sub-session B: 23:07:12 onward (`logs/openswfz-20260724T210711Z.log`), auto-resumed same
  device/band with no manual intervention, confirming the supervisor's restart mechanism works.
  Supervisor armed and watching this and all subsequent sub-sessions; `retry_count=0` as of last
  check (no genuine failures tonight, only the manual validation kill).

## Correction-by-correction convergence tally (the actual 9.5 acceptance question)

"Good" = |next reading| < 60% of the correction's own magnitude (same bound `CycleFramerTests.cs`
9.3 uses). "Bad" = >= 60%, i.e. the correction's own real-time cost re-appeared as fresh deviation
roughly as badly as the pre-9.1 defect this fix targets.

| # | Sub-session | Fired (local) | Type | Correction | Next reading | Ratio | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | A | 22:32:00 | discard | +1555 | -242.0 | 15.6% | GOOD |
| 2 | A | 22:32:45 | replay | -507 | +1972.9 | 389% | BAD |
| 3 | A | 22:38:15 | discard | +2065 | -773.2 | 37.4% | GOOD |
| 4 | A | 22:39:45 | replay | -984 | +2619.1 | 266% | BAD |
| 5 | B | 23:07:45 | discard | +1007 | 97.5 | 9.7% | GOOD |
| 6 | B | 23:20:00 | discard | +880 | 711.5 | 80.9% | BAD |
| 7 | B | 23:23:15 | discard | +1218 | 517.5 | 42.5% | GOOD |
| 8 | B | 23:24:15 | discard | +782 | 1232.7 | 157.6% | BAD |
| 9 | B | 23:25:00 | discard | +1311 | 212.7 | 16.2% | GOOD |
| 10 | B | 23:26:15 | discard | +682 | 1286.3 | 188.6% | BAD |
| 11 | B | 23:27:30 | discard | +1347 | 731.6 | 54.3% | GOOD (close to the 60% line) |

**Sequence of verdicts: G,B,G,B,G,B,G,B,G,B — a perfect strict alternation across all 10
corrections so far**, spanning a process restart and a ~12-minute idle gap (23:08–23:20, no
corrections at all) between events 5 and 6. This *supersedes* the earlier "discard converges,
replay doesn't" working hypothesis from sub-session A alone (recorded in the transcript before
23:07) — events 6-10 are ALL discard-type and still alternate good/bad perfectly, so the type
split in A (1G,2B,3G,4B = discard,replay,discard,replay) looks now like it was **coincidental
overlap with the alternation, not evidence that type itself is the driver.**

**Working hypothesis, not yet confirmed:** something about a correction's own accounting leaves a
residual that flips sign or resets every *other* firing — e.g. each correction's actual real-time
cost doesn't exactly match `pendingNominalAdjustSeconds`'s idealized nominal-sample-rate estimate,
and whatever's left over from a "good" (small-residual) firing sets up conditions for the *next*
firing to be measured against a slightly-off baseline, and vice versa. A single strict alternation
across only 10 events (p ~ 1/512 under a naive fair-coin null, for what a back-of-envelope figure
is worth — not a real significance test) is more suggestive of a mechanical cause than of
independent noise, but 10 events across ~1 hour is still a thin sample; needs more data before
concluding anything, and definitely needs someone to actually trace the mechanism rather than
pattern-match on this table alone. Do not retune constants from this table alone.

**Do NOT lose the type-based framing entirely** — of the 5 GOOD firings, discard=5/5; of the 5 BAD
firings, discard=3/5 and replay=2/2. Replay is still 0/2 good, discard is 5/8 good. With only 2
replay events total, "replay is always bad" and "verdict just alternates regardless of type" are
both still consistent with the data — more replay events specifically would help separate these.

## Open items for the morning report

- Confirm the alternation holds/breaks as more corrections accumulate overnight.
- If it keeps alternating cleanly, that's a stronger, more specific clue than "replay is broken"
  and should be the lead finding, with the type-correlation reframed as likely coincidental.
- Note sub-session A/B split and the validation-kill gap explicitly so it isn't mistaken for an
  unexplained data gap.
- Pull `restart-supervisor.log` for the final tally of any genuine (non-manual) restarts.

## RESOLVED — final full-night results (see `../2026-07-25-40m-band-9.5-fail/report.md` for the
full writeup; this section just closes out the open items above)

The alternation pattern **did not hold** once the full night's 136 corrections were extracted
programmatically. It looked clean for the first ~11 events (all captured live, in the transcript,
before the Captain went AFK) purely because that was still early in the session, before
correction magnitudes grew large. Automated extraction across the whole night:

- **32/136 (23.5%) GOOD, 104/136 (76.5%) BAD** by the same <60%-of-correction-magnitude bound
  9.3's unit tests use.
- discard: 32/132 good (24.2%); replay: 0/4 good (0%) — the type split survived, the alternation
  claim did not. Replay's 0/4 is suggestive but too small a sample to lean on alone.
- **The real finding, invisible in the first ~11 events:** correction magnitude grew
  essentially monotonically, hour over hour, all night — roughly 8x from the 22:00 hour
  (avg 1,718.8 samples/correction) to the 09:00–10:00 hours (avg ~11,600–12,100). This is the
  clearest, most session-scale evidence yet that 9.1 does not achieve convergence, not just
  "hasn't been proven to yet."

Session ended cleanly: Captain's own graceful stop at 10:18:42 local (`POST /api/v1/decode/stop`,
649,750 chunks received that sub-session, 0 ERR/FTL all night). The overnight supervisor
(HK-013) never had to recover from a genuine failure, but did misfire once, harmlessly, when that
same graceful stop's ~90s of resulting silence looked like a stall to it — see the report's
Section 2 and the now-updated `hk013-unattended-run-supervisor-standard.md` for the two new bugs
this surfaced (a `tasklist` "no match" message being treated as a literal PID, and no way to
distinguish an intentional stop from a hang).

**Verdict: 9.5 FAILS.** Full detail, recommendations, and next steps in the report.
