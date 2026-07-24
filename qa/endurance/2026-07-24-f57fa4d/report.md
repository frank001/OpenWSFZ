# Endurance Test Report — 2026-07-24 (short session, evening)

## 1. Study hypothesis

**What is this run testing?**

This is a further live-hardware run for `openspec/changes/fix-cycle-boundary-clock-drift/`,
building on `qa/endurance/2026-07-24-29041f7/report.md`. Like that run, the correction logic
itself is unchanged since `1cebf81` (Decision 5's size-to-confirmed-deviation mechanism) — this
is not a test of a new fix, since `tasks.md` 8.3 (fix shape) remains undecided. What's new in the
build under test is `tasks.md` 8.4 (systematic `hashTableRejectCount` logging) and 8.7 (two
isolated, confound-free unit tests confirming the discard-costs-real-time mechanism — already
run and passed as unit tests, not re-tested live here). This run exists to (a) confirm 8.4's new
logging behaves correctly under sustained real load rather than only the synthetic smoke check
already done earlier the same session, and (b) gather a fresh live data point — including a
direct DT comparison against WSJT-X, both `ALL.TXT` logs having been cleared beforehand.

**Build under test:** `f57fa4d` (feat(ft8): log `hashTableRejectCount` per cycle; confirm
discard-vs-replay real-time-cost asymmetry — tasks.md 8.4/8.7/8.8), branch
`docs/propose-fix-cycle-boundary-clock-drift`, open PR #108. Reviewed pre-push per HK-011 earlier
the same session (implementation + review both conducted under the Captain's explicit sign-off to
treat that portion of the session as Developer, per `tasks.md` 8.4/8.7's own notes) — approved,
merge hold unaffected.

**Session length:** ~38m47s (18:23:34Z–19:02:21Z), against `ce13e30`'s 7h54m, `1cebf81`'s 6h16m,
and `29041f7`'s 32m4s. Explicit short-first choice, confirmed with the Captain before starting;
stopped at the first checkpoint (~34 min in) on the Captain's explicit instruction ("stop it"),
rather than run to a predetermined length or extended by default.

**Null hypotheses:**

- **H₀-1 (stability):** OpenWSFZ completes the session without crash, audio dropout, or
  unrecoverable gap.
- **H₀-2 (drift bounded) — carried over, not re-tested by new logic:** the correction keeps
  accumulated deviation small and non-trending. Already rejected in `ce13e30`, `1cebf81`, and
  `29041f7`; not expected to pass here either, since nothing about the correction itself changed.
- **H₀-3 (pipeline-timing instrumentation stays flat) — carried over confirmation, not a new
  test:** `29041f7` refuted a correlation between the growing deviation and the three
  cadence-instrumented pipeline stages (WASAPI inter-arrival, chunk-dequeue gaps, channel-write
  latency); this run checks whether that negative result continues to hold on a fresh session.

**Not a formal hypothesis, but the most actionable observation this run produced:** a manual DT
comparison against WSJT-X (§3.3) — not something either prior run against this change attempted.

**Defects under observation:** `fix-cycle-boundary-clock-drift` (open, PR #108, not merged; merge
hold per HK-011 stands regardless of this run's outcome — 8.3/6.6/7.6/8.6 remain open even if
every hypothesis above resolves favourably).

---

## 2. Data summary

| Field | Value |
|---|---|
| Date | 2026-07-24 (local CEST, UTC+2) |
| OpenWSFZ SHA | `f57fa4d` on `docs/propose-fix-cycle-boundary-clock-drift` |
| ft8_lib shim | 20260033 (unchanged) |
| Session start | 2026-07-24 20:23:34 local (18:23:34 UTC) |
| Session end | 2026-07-24 21:02:21 local (19:02:21 UTC) |
| Duration | 38 minutes 47 seconds |
| Total 15-second cycles (windows emitted) | 154 |
| Total decodes (OpenWSFZ) | 3,607 (mean 23.4/cycle) |
| Band | 20 m (14.074 MHz FT8) |
| Audio device | `'Microphone (2- USB Audio CODEC )'` (`d451e08c-82b5-446e-a5f1-1bdd8fceeac2`), WASAPI, 48000 Hz → 12000 Hz — same device family as every prior round |
| WSJT-X | Running in parallel throughout; `ALL.TXT` cleared before this run; **WAV saving disabled this run** (no WAV artefacts preserved, unlike `29041f7`) |
| Daemon log file | `logs/openswfz-20260724T182334Z.log` (git-ignored, local only, NFR-021) |
| Shutdown | Graceful, operator-initiated (`POST /api/v1/decode/stop` at 19:02:16Z; `RecordingStopped (graceful)`; `Capture stopped ... (operator-stopped). Chunks received: 37048`), full application shutdown at 19:02:21Z |
| Cycle-boundary drift checks logged | 154 (one per window, Debug level, matching windows emitted; each of the 3 resyncs below additionally restates its own triggering check's deviation figure on its own Information-level line, so a naive text search for "deviation = ... samples" over-counts by 3 — accounted for in this report's figures) |
| Cycle-boundary resyncs fired | 3 (Information level) — see §3.2 |
| Hash table reject count (session end) | 2,394 (F-005 metric; first time this session's own per-cycle series is available end-to-end, per 8.4 — see §3.3) |

**Confirmed before monitoring began:** `hashTableRejectCount=` (8.4), `Cycle boundary drift
check`, and `Cycle boundary pipeline timing` (Decision 6) lines were all present and correctly
formatted in the live log from early in the session — not a stale pre-instrumentation build. Also
confirmed via a separate synthetic smoke test earlier the same session (real native decoder, real
console logger, no live device): see this session's transcript for that check, which predates and
is independent of this live run.

---

## 3. Results

### 3.1 Stability

OpenWSFZ ran cleanly for 38m47s (154 decoded cycles) with no crash or decode gap.

| Metric | Value |
|---|---|
| Log ERR entries | **0** |
| Log FTL entries | **0** |
| Heartbeat count | 464 |
| Heartbeat `=false` readings | 3 total — 2 at 20:23:46/20:23:51 local (before `CycleFramer started` at 20:23:53.707 local; benign startup transient, same pattern documented in prior reports) and 1 at 21:02:21 local (`captureActive=false`, `audioActive=true`, `dataFlowing=true` — the operator-initiated stop taking effect, not a fault) |
| Daemon process identity | Single PID (48664) throughout, no restart |
| Shutdown | Graceful (operator API call) |

**H₀-1: CONFIRMED** — zero failures; the only non-`true` heartbeat readings are fully accounted
for by startup and operator-initiated shutdown.

### 3.2 Cycle-boundary drift correction — non-convergence reproduces again, at a rate consistent with all three prior runs

**H₀-2: REJECTED again, as expected.** Three corrections fired this session:

| # | Fired at | Deviation at fire | Next reading | Delta | Direction |
|---|---|---|---|---|---|
| 1 | 18:34:45.163Z | 1956.9 samples (163.08 ms) | 1324.4 samples | -632.5 | decrease |
| 2 | 18:36:15.285Z | 1468.5 samples (122.37 ms) | 1877.3 samples | +408.8 | **increase** |
| 3 | 18:39:45.453Z | 2020.0 samples (168.34 ms) | 1755.5 samples | -264.5 | decrease |

Unlike `1cebf81`'s consistent "next reading same-or-higher" pattern, 2 of these 3 show an
immediate decrease — but this is not evidence of convergence. Looking at the whole session rather
than just the three correction events: the first 10 drift-check readings averaged **1,122.3
samples**; the last 10 averaged **2,469.0 samples** — the oscillation band itself climbed by
roughly 2.2x over the session, corrections notwithstanding. Net rate: (2,469.0 − 1,122.3) samples
over ≈38.2 minutes ≈ **35.3 samples/min** — closely consistent with `ce13e30`'s whole-session rate
(≈34.1 samples/min) and `29041f7`'s (≈31.6 samples/min), the third session in a row to show this
same rate band despite differing session length (32 min to 7h54m), band conditions, and now also
a different correction-firing cadence (3 corrections here vs. 8 in `29041f7`'s comparable ~32-38
min). **The consistency of this rate across four independent sessions (`ce13e30`, `1cebf81`,
`29041f7`, this run) is itself the strongest cross-run evidence yet that a single, comparable-rate
underlying mechanism is responsible, not session-specific noise.**

**H₀-3: continues to hold (flat).** `real inter-window elapsed` this session: min 14.950s, max
15.156s, avg 15.0038s (n=153) — flat around the 15.000s nominal, same as `29041f7` found, no
correlation with the 2.2x climb in deviation described above. This run did not separately
re-verify chunk-dequeue-gap/WASAPI-cadence flatness in as much depth as `29041f7`'s dedicated
pass, but spot checks during monitoring showed the same flat pattern (avg ~62ms, max ~63-64ms
throughout).

### 3.3 `hashTableRejectCount` — first live per-cycle series (tasks.md 8.4)

This is the first live run with 8.4's logging in place, closing the gap `29041f7`'s own
recommendations (§5) flagged: a per-cycle series is now available instead of a single end-of-run
value. The table saturated (moved off zero) at 18:39:15Z, then climbed steadily and linearly to a
session-end value of **2,394** — roughly 1-1.5 rejects/second sustained for the last ~23 minutes
of the session, consistent with this band's real decode load (mean 23.4 decodes/cycle, many more
unique stations heard than the table's 256 slots). No errors or decode-pipeline impact observed
from the saturation — purely observational, exactly as designed. **Not yet compared against the
deviation trend for correlation** (that comparison needs the per-cycle series lined up against the
drift-check series, which this report does not attempt — flagged as a next step, not done here).

### 3.4 DT comparison against WSJT-X (new this run, not attempted in `ce13e30`/`1cebf81`/`29041f7`)

A manual comparison of OpenWSFZ's own WSJT-X-format `ALL.TXT` (repo root, `AllTxtWriter`,
FR-027/028) against WSJT-X's own `ALL.TXT`, for one cycle (18:29:00Z, before any correction had
fired), matched by audio frequency bin (11 matched decodes out of OpenWSFZ's 25 vs. WSJT-X's 47
decoded that cycle — a recall gap consistent with the known baseline, not analysed further here).
Message content (real third-party callsigns) is deliberately omitted from this report per NFR-021;
frequency and DT only:

| Freq (Hz) | OWSFZ DT | WSJT-X DT | Delta |
|---|---|---|---|
| 1031 | 0.8 | 0.2 | +0.6 |
| 1497 | 0.7 | 0.2 | +0.5 |
| 1944 | 0.7 | 0.1 | +0.6 |
| 2009 | 0.2 | -0.4 | +0.6 |
| 2063 | 0.4 | -0.1 | +0.5 |
| 981 | 1.0 | 0.4 | +0.6 |

(11 rows matched in total; the other 5 followed the same pattern, omitted here for brevity — the
finding is the flatness of the offset, not the specific count.) **Every matched pair shows
OpenWSFZ's DT running ~+0.5 to +0.6 s higher than WSJT-X's, essentially flat across all 11
matches in this single cycle.** This is notably larger, and notably flatter, than the ~0.1-0.2s
`deviation` the `CycleFramer` drift-check instrumentation itself reported at this same point in
the session (§3.2) — which suggests, as a hypothesis rather than a finding, that this may be a
separate, largely time-invariant measurement/reference-point offset between the two decoders'
respective DT calculations, distinct from the session-scale growing drift this investigation
exists to fix. **This has not been checked against any prior characterization of an
OpenWSFZ-vs-WSJT-X baseline DT offset** (if one exists) and is based on a single cycle's worth of
matched decodes — not a session-wide statistical comparison. Recommended as a priority follow-up
(§5), not concluded here.

---

## 4. Summary verdict table

| Metric | Value | Threshold | Verdict |
|---|---|---|---|
| Stability — no crash | 0 crashes | 0 | **PASS** |
| Stability — no log ERR/FTL | 0/0 | 0 | **PASS** |
| Duration | 38m47s | — | **PASS (short session, by design; stopped on Captain's instruction at first checkpoint)** |
| Correction bounds cumulative drift (H₀-2) | Oscillation band climbed ~2.2x (1,122.3 → 2,469.0 samples avg) over the session at ≈35.3 samples/min, closely matching `ce13e30`/`29041f7`'s independently-measured rates, despite 3 corrections firing | should stay small/non-trending | **FAIL (expected — no fix landed since `1cebf81`)** |
| Pipeline-timing instrumentation stays flat (H₀-3) | `real inter-window elapsed` avg 15.0038s (n=153), no correlation with the deviation climb | correlation would indicate a specific root cause at these stages | **CONTINUES TO REFUTE that explanation — consistent with `29041f7`** |
| `hashTableRejectCount` per-cycle logging (8.4) | Live, correct, first full per-cycle series this run (0 → 2,394) | logging present and accurate | **PASS** |
| DT offset vs. WSJT-X | ~+0.5 to +0.6s, flat across 11 matched decodes in one cycle | (no threshold set — new observation) | **FLAGGED for follow-up, not yet interpreted** |

**Overall verdict:** as expected on H₀-1/H₀-2/H₀-3 (stable, still non-convergent at a rate now
confirmed across four independent sessions, pipeline-timing instrumentation still not implicated).
The two genuinely new contributions this run makes are (a) 8.4's logging confirmed working under
real sustained load, and (b) the DT-offset observation, which is new information no prior run in
this investigation gathered. `tasks.md` 6.6/7.6/8.6 remain unchecked; the HK-011 merge hold
stands. This run does not decide 8.3 — like `29041f7`, it adds evidence 8.3 will be decided from.

---

## 5. Recommendations

**Primary — investigate the DT-offset finding (§3.4) before the next live round.** A flat ~+0.5
to +0.6s offset across every matched decode in one cycle is either (a) an already-understood,
benign artefact of how the two decoders compute/report DT (in which case documenting that
explicitly would close this out), or (b) new information relevant to the D-001 thread this whole
investigation grew out of. Either way, a single cycle's worth of matched decodes is not enough to
characterize it properly — a session-wide, scripted DT comparison (matching by frequency bin and
approximate timing across the full session, not a manual spot check) would settle whether the
offset is genuinely constant, itself drifts, or correlates with the same corrections/deviation
this report already tracks.

**Second — line up the `hashTableRejectCount` per-cycle series against the deviation series.**
8.4's logging is now confirmed working; the next live run (or a re-analysis of this run's own
artefacts) should actually plot/compare the two series to check for correlation, rather than
noting both exist independently as this report does.

**Third — the cross-run rate consistency (§3.2) deserves its own note in `tasks.md` 8.3's
discussion.** Four sessions, four different lengths and band conditions, one consistent
~31-35 samples/min underlying rate — this is a strong argument that whatever 8.3 decides should
address a single stable mechanism, not something session-dependent or intermittent.

**Not yet addressed by this run:** `tasks.md` 8.3 (fix shape) remains blocked — this run adds
data but does not isolate a fix. `tasks.md` 6.6/7.6/8.6 remain unchecked.

**Cross-references:** `qa/endurance/2026-07-24-ce13e30/report.md`, `qa/endurance/2026-07-24-1cebf81/report.md`,
`qa/endurance/2026-07-24-29041f7/report.md` (the three prior runs against this change);
`qa/endurance/2026-07-24-f57fa4d/run-notes.md` (this run's raw working notes, including the
in-session correction to an initial undercount of corrections fired, and the NFR-021 scrub of a
callsign table before it could be committed).

---

## Appendix: reproduction

- Report: this file (+ rendered `report.html`).
- Daemon log: `logs/openswfz-20260724T182334Z.log` (git-ignored, local only, NFR-021) — not
  preserved to a committed `artefacts/` snapshot this run (unlike `29041f7`'s
  `artefacts/20260724_live_run_1607/`); reference figures in this report were extracted directly
  via `grep`/`awk` against that log file while it was still present locally.
- OpenWSFZ's own decode log (`ALL.TXT`, repo root) and WSJT-X's `ALL.TXT`
  (`C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT`): both git-ignored, local only, NFR-021 — no WAV
  files preserved this run (WAV saving was disabled in WSJT-X for this session, per the Captain's
  setup).
- Git state at time of this run: `HEAD = f57fa4d` (this report + `run-notes.md`/`monitor.sh`
  committed after the run completed) on `docs/propose-fix-cycle-boundary-clock-drift`.
- The live monitoring script used during the run is preserved at
  `qa/endurance/2026-07-24-f57fa4d/monitor.sh` (adapted from `29041f7`'s version; retuned
  mid-session to fold `hashTableRejectCount` into periodic status instead of per-cycle events once
  the table saturated — see `run-notes.md` for why).
