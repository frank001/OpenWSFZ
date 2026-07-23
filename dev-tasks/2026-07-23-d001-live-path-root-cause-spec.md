# D-001 — Live-Path Root-Cause Investigation: Cycle-Boundary Drift Hypothesis

**Date:** 2026-07-23
**Author:** QA (self-directed)
**Audience:** Architect, Captain
**Decision context:** `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/report.md`
(PR #103) found ≈23.4% of Isolated-class low-SNR misses decode successfully on isolated replay
but failed live; `qa/rr-study/results/2026-07-23-d001-tight-class-replay/report.md` (PR #105)
established the effect does **not** transfer to the Tight (co-channel) class at a comparable
magnitude. Both passes explicitly left the *mechanism* undiagnosed — this spec is that
follow-up, per PR #103 §5.3 item 1 and the go/no-go brief's own framing of it as the natural
next step now that the H7-ceiling risk (§3.1) is closed.
**Defect ID:** D-001 — weak-signal / co-channel decode recall gap vs WSJT-X (open, issue #3)
**Status:** Proposed, not yet approved to execute.

---

## 0. Executive summary

Neither prior pass asked *why* isolated replay recovers ~23% of Isolated-class misses. This
spec proposes a bounded, mostly-offline investigation built around one concrete, evidence-based
hypothesis, rather than an open-ended "compare AGC/timing state" mandate (the phrasing PR #103's
report used, before this codebase survey narrowed it).

**Working hypothesis: silent FT8 cycle-boundary drift, accumulating over a long-running live
session, pushes marginal-SNR signals outside the decoder's DT (time-offset) search window by
the time hour 10+ of a session is reached — a failure mode invisible to the existing per-pass
candidate-count diagnostic (which is why PR #103's CG-vs-LDPC split saturated to 100%
Ambiguous) and orthogonal to co-channel interference (consistent with PR #105's Tight-class
null result).**

The evidence for this specific hypothesis, and against several competing ones, was gathered by
reading the actual capture/framing code and the two retained live-session Debug-level daemon
logs (07-07, 06-22) **before** writing this spec, not assumed:

- `src/OpenWSFZ.Ft8/CycleFramer.cs`: the 15 s cycle boundary is computed **once** at startup
  (`AlignToCycleStart`) and then advanced purely by sample count (`ComputeLeadingSamples`) —
  **never re-synced to wall clock** for the life of the session.
- `src/OpenWSFZ.Audio/WasapiAudioSource.cs`: capture is piped through a
  `WdlResamplingSampleProvider` at a **fixed ratio**, with no correction for the real capture
  device's clock-rate error against its nominal declared sample rate — the classic mechanism by
  which "samples consumed" silently drifts away from "true elapsed seconds" over many hours,
  even though the sample-counting itself is perfectly deterministic.
- **No AGC, soft-limiter, or level-normalisation exists anywhere in the audio path** (confirmed
  by exhaustive grep of `OpenWSFZ.Audio`) — ruling that mechanism out entirely, contrary to
  this investigation's original "gain-staging" framing.
- **No cross-cycle decoder state that could plausibly help a short replay over a long session**
  — the waterfall/candidate/LDPC pipeline is freshly allocated every single decode cycle
  (`ft8_shim.c`, `monitor_init` on every call); the one real piece of cross-cycle state (the
  hashed-callsign table) would, if anything, make a *longer* session more capable, not less —
  wrong direction for this symptom.
- **Two retained live-session Debug-level daemon logs exist** (`artefacts/20260706_live_run_2308/logs/openswfz-20260706T210818Z.log`,
  49,908 lines; `artefacts/20260622_live run/openswfz-20260621T225646Z.log`, 26,783 lines) —
  both **zero `[WRN]` entries** (buffer-near-full / audio-chunk-dropped events, which do get
  logged elsewhere on this system when they occur — confirmed by finding `[WRN]` lines in four
  other retained session logs, so this is not a broken sink) and **exactly one pipeline restart
  each, in both cases within the first ~9 minutes of startup, none thereafter** — this
  provisionally rules out mid-session buffer drops and watchdog restarts as drivers of the
  effect for these two sessions specifically, and points the remaining suspicion squarely at
  the *silent* drift mechanism above, which produces no log line by construction.

**Effort: Phase 1 is a few hours, purely offline, reusing only already-retained logs — no new
capture.** Phase 2 is a small, targeted live replay (not a new on-air session) sized in hours,
not days. A possible Phase 3 (decisive live verification) is flagged as a Captain/Architect
decision point, not committed here — same pattern PR #103's spec used for its own §4.5.

---

## 1. The precise questions this answers

1. **Does OpenWSFZ's own reported FT8 DT (time-offset-from-slot-start) drift over the course of
   a long live session, in a way WSJT-X's does not?** This is the direct, cheap, offline proxy
   for "has the daemon's internal cycle-boundary silently desynchronised from true UTC by hour
   N" — if OpenWSFZ is drifting and WSJT-X (a mature, NTP-disciplined reference decoder) is not,
   the *difference* between the two apps' DT for the same signal, plotted against session-
   elapsed time, should show a real trend.
2. **Do the Isolated-class misses that decode on isolated replay (PR #103's ≈23.4% population)
   concentrate in the session hours where Phase 1 finds the largest apparent drift**, or are
   they spread uniformly across the session? A concentration in high-drift hours would be
   strong corroborating evidence; a uniform spread would argue against this specific mechanism
   even if some drift is measured.
3. (Only if 1–2 together implicate drift with reasonable confidence) **Is the drift large enough
   to plausibly explain candidate non-generation** — i.e., does the measured/extrapolated drift
   by late-session hours approach or exceed the decoder's DT search window, such that a
   marginal-SNR signal's true arrival time could fall outside where candidates are searched for
   at all?

---

## 2. Inputs (Gate 0 — already confirmed present during this spec's own preparation)

| Input | Status |
|---|---|
| ALL.TXT pairs, all three sessions (07-07, 07-06, 06-22) | **Confirmed present**, already used by Option B/`classify_cochannel.py`. DT is already a parsed field (`LINE_RE` group `dt`) — no new parsing logic needed for Phase 1's core signal. |
| Retained Debug-level live daemon logs | **Confirmed present for 2 of 3 sessions** (07-07: 49,908 lines; 06-22: 26,783 lines). **Not present for 07-06** (`artefacts/20260706_live_run/` has no `.log` file) — Phase 1's log-mining component (restarts/WRN events) is therefore a 2-session check, not 3; the DT-drift component (§3.1) can still use all three, since it only needs ALL.TXT. |
| Per-slot WAV audio (for Phase 2 replay) | **Confirmed present, 07-07 only** (same constraint as PR #103/#105 — the only session with retained audio). |
| Replay harness | **Confirmed present and reusable**, with one small, disclosed modification needed (§3.2 — retain ts/freq for *decoded-on-replay* hits, which the existing harness deliberately discards). |
| Source code confirming the drift/no-AGC/no-cross-cycle-state findings above | **Read directly** — `src/OpenWSFZ.Ft8/CycleFramer.cs`, `src/OpenWSFZ.Audio/WasapiAudioSource.cs`, `src/OpenWSFZ.Audio/CaptureManager.cs`, `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, `Native/ft8_shim.c`, `src/OpenWSFZ.Daemon/Program.cs` — this is read-only code inspection informing the spec, not a code change. |

**Gate 0 verdict: PASS.** Everything Phase 1 needs is already on disk.

---

## 3. Method

### 3.1 Phase 1a — Retained-log mining (offline, ~30 minutes)

For the two sessions with a retained Debug-level daemon log (07-07, 06-22):

1. Parse `CycleFramer started` / `CycleFramer cancelled` lines to enumerate every pipeline
   restart with its timestamp. Report count and timing (already known informally from this
   spec's own preparation: exactly 1 restart each, both within ~9 minutes of session start,
   none in the following 8–17 hours of steady-state operation — confirm this formally with a
   small script rather than relying on the manual grep used to write this spec, and check
   whether the two logs are actually complete — i.e. verify line counts and start/end
   timestamps against the corresponding ALL.TXT session span, so a truncated or rotated log
   file doesn't silently hide a restart).
2. Count `[WRN]` lines by message template (buffer-near-full, chunk-dropped, others). Report
   per-session counts, not just the pooled zero already observed.

**Expected outcome, stated up front so it isn't over-read if confirmed:** this is expected to
reproduce the zero-restart-after-startup / zero-WRN finding already observed informally. If it
does, that is confirmatory, not new — it does not by itself prove the drift hypothesis, it only
continues to rule out the two *loud* competing mechanisms (buffer drops, watchdog restarts) this
spec's own preparation already found no evidence for. If it does **not** reproduce (e.g. a
previously-unnoticed WRN cluster, or a restart the manual check missed), that is a materially
different and more important finding than anything else in this spec, and should redirect the
investigation toward whatever it finds rather than proceeding to 3.2 on the original hypothesis.

### 3.2 Phase 1b — Cross-app DT-drift analysis (offline, ~1–2 hours, all three sessions)

1. Extend (copy, don't modify) `classify_cochannel.py`'s `parse()`/`sig_key()` to additionally
   retain `dt` (already parsed, currently discarded) for every row, both apps, all three
   sessions.
2. For **matched decodes only** (same `sig_key` — i.e., the same real signal, decoded by both
   apps in the same slot) — the cleanest comparison, since it holds the true signal's actual
   arrival time constant and only lets timing-relative-to-window vary — compute
   `delta_dt = openwsfz_dt - wsjt_dt` for every matched pair, bucketed into hourly bins by
   session-elapsed time (`ts` minus session start).
3. Per session, per band (reuse Option B's two low-SNR bands **and** an unrestricted/all-SNR
   pass, since this specific mechanism is not expected to be SNR-selective — SNR affects
   whether drift-induced window misalignment costs a *decode*, not whether drift itself is
   occurring), fit a linear trend (`delta_dt` vs. elapsed hours) and report:
   - the slope (seconds of apparent OpenWSFZ-vs-WSJT-X DT drift per hour),
   - a significance test for slope ≠ 0 (a simple OLS with a t-test on the slope coefficient is
     sufficient at this sample size — no need for anything more elaborate),
   - the total `delta_dt` spread from first-hour to last-hour of the session, in seconds,
   - matched-pair count per hourly bin (report where bins get thin — late-session bins in the
     shorter sessions may have too few matched pairs to trust individually).
4. **Also report each app's own DT distribution independently** (not just the paired
   difference) as a sanity check — if WSJT-X's own DT trend is itself non-flat over the
   session, the "WSJT-X as a stable reference" assumption this whole phase leans on needs
   flagging, not silently accepted.

### 3.3 Phase 2 — Targeted small replay, correlating against Phase 1 (live, 07-07 only, ~1 hour)

This directly answers Question 2 (§1), which Phase 1 alone cannot — Phase 1 characterises
*whether and when* drift appears to occur; Phase 2 checks whether the actual failures line up
with it.

1. Modify (copy, don't overwrite) `run_isolated_replay.py` / this investigation's own small
   driver so that it **retains `ts`/`freq_hz`/`band` for Decoded-on-replay hits too** — the
   one deliberate gap PR #103's own report flagged (§5.3 item 1: "excluded from that committed
   file by design — re-derive via a fresh, small, explicitly-scoped follow-up"). This is
   exactly that follow-up. NFR-021 handling identical to prior passes (ts/freq/band only, no
   message text, ever committed).
2. Run a **small, explicitly non-exhaustive** replay — target 10 Decoded-on-replay hits (not
   PR #103's full 20-reproduced-per-stratum design; this pass needs decoded-on-replay *cases
   themselves*, not a reproduction-rate estimate, which PR #103 already delivered). Draw from
   the same stratified Isolated-class population PR #103 used (different seed, e.g.
   `D001-LIVEPATH`), over-drawing generously since decoded-on-replay was the *minority* outcome
   in PR #103 (19/59 tried).
3. For each of the ≥10 collected Decoded-on-replay hits, record its `ts` (hence session-elapsed
   time). Plot/table these against Phase 1's per-hour `delta_dt` trend for the same session
   (07-07). Report qualitatively and, if the sample supports it, with a simple test (e.g. do
   Decoded-on-replay hits skew toward later/higher-drift hours vs. a uniform-over-session null,
   via a Kolmogorov-Smirnov or simple rank comparison against the full Isolated-miss
   population's own `ts` distribution) whether they concentrate where drift is largest.

### 3.4 Phase 3 — decision point, not committed here

If 3.1–3.3 together implicate cycle-boundary drift with reasonable confidence (a real,
significant `delta_dt` trend in Phase 1b, corroborated by a temporal concentration in Phase 2),
the decisive follow-up would be a **direct, instrumentation-only measurement** of the daemon's
actual cycle-boundary alignment against true wall-clock/UTC over a multi-hour live session —
e.g. logging `CycleFramer`'s computed slot-start time alongside a wall-clock timestamp at a
fixed cadence (hourly), so drift can be read directly rather than inferred from DT statistics.
This is bounded and would not change decode behaviour (same guardrail PR #103's spec applied to
its own §4.5 shim idea) — but it needs a genuine multi-hour live capture, which is a bigger ask
than anything in Phases 1–2, and is explicitly **not** assumed or scoped by this document. Flag
it for the Captain/Architect once Phases 1–2 land; do not pre-commit to it now.

---

## 4. Rigour controls

1. **Hypothesis stated and evidenced before data collection**, not fitted after — the drift
   hypothesis and the two ruled-out competitors (AGC — doesn't exist in the codebase at all;
   cross-cycle decoder state — exists but wrong-direction for this symptom) come from reading
   the actual source, cited by file/function, not from re-guessing "AGC/timing/adjacent-cycle
   state" the way PR #103's report phrased the open question.
2. **WSJT-X-as-reference is checked, not assumed** (§3.2 point 4) — if WSJT-X's own DT isn't
   stable either, the whole paired-difference approach needs rethinking, and that must be
   reported plainly rather than silently worked around.
3. **Matched-decode-only DT comparison** (§3.2 point 2) isolates timing effects from population-
   composition effects — using each app's *full* independent DT distribution instead would
   conflate "OpenWSFZ's window drifted" with "OpenWSFZ decodes a different mix of signals than
   WSJT-X," which is not what this phase is trying to measure.
4. **Phase 2's sample is explicitly a correlation check, not a new precision estimate of the
   Decoded-on-replay rate** — PR #103 already delivered that estimate (≈23.4%); re-deriving it
   here would be redundant. n≥10 is sized for "does a temporal pattern exist," not for a tight
   confidence interval.
5. **Two of three sessions only for the log-mining component** (§3.1) — 07-06 has no retained
   daemon log; state this limitation plainly rather than silently generalising from two
   sessions to all three.
6. **A null result is a real, reportable finding, not a failed pilot.** If Phase 1b finds no
   significant `delta_dt` trend in any session, that rules out this specific hypothesis with
   real confidence (it was the leading, evidence-based candidate after a full code survey) and
   should be reported as such — it would leave the live-path effect's mechanism genuinely open,
   pointing toward the Phase 3-style direct-instrumentation approach as the only remaining route
   to an answer, or toward reconsidering whether "live-path" is the right frame at all.

---

## 5. Scope guardrails — what this is NOT

- **Not** a new on-air capture — Phase 1 is offline-only; Phase 2 reuses the existing retained
  07-07 WAV audio through the existing replay harness.
- **Not** a product or decoder code change of any kind. No fix is scoped, proposed, or assumed
  by this document — if drift is confirmed, *what to do about it* (re-sync CycleFramer to wall
  clock periodically, correct for resampler clock-rate error, etc.) is explicitly a separate,
  future conversation, not something this spec authorises.
- **Not** a re-opening of Option B, the histogram addendum, the runtime-parameter sweep, or
  either replay pilot (PR #103/#105) — additive throughout.
- **Not** Phase 3 — flagged as a decision point only (§3.4), not committed or scoped in detail
  here.
- **Not** a precision measurement of anything Phase 1b/Phase 2 touches — both are pilot-sized,
  stated as such.

---

## 6. Deliverables

1. `qa/rr-study/results/<date>-<sha>-d001-live-path-root-cause/report.md` (QA authors Sections
   1/5 per HK-001) — Phase 1a's restart/WRN counts per session, Phase 1b's per-session/per-band
   `delta_dt` trend table (slope, significance, spread, matched-pair counts per bin) plus each
   app's independent DT-stability sanity check, Phase 2's temporal-concentration check against
   Phase 1b, and a recommendation on whether Phase 3 is warranted.
2. The DT-drift analysis script and the modified small-replay driver, committed (NFR-021: no
   message text ever committed, same discipline as PR #103/#105).
3. If the finding is materially informative either way (confirms or rules out drift with
   confidence), a short addendum to `dev-tasks/2026-07-23-d001-h7-go-no-go-summary.md` noting
   it — though per that brief's own §3.1 ADDENDUM, this investigation no longer gates the H7
   A-vs-C decision, so this is a record-keeping courtesy, not a blocking update.

---

## 7. References

| Reference | Content |
|---|---|
| `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/report.md` (PR #103) | Source of the ≈23.4% Decoded-on-replay finding and its own §5.3 item 1, which this spec directly executes |
| `qa/rr-study/results/2026-07-23-d001-tight-class-replay/report.md` (PR #105) | Established the effect is not class-independent, closing the H7-ceiling risk and freeing this investigation to proceed on its own merits/priority rather than as a blocker |
| `dev-tasks/2026-07-23-d001-h7-go-no-go-summary.md` §3.1 ADDENDUM | Records that this investigation is no longer a precondition for the H7 A-vs-C decision |
| `src/OpenWSFZ.Ft8/CycleFramer.cs` | `AlignToCycleStart`, `ComputeLeadingSamples`, `RunAsync` — the sample-count-only framing this spec's hypothesis centres on |
| `src/OpenWSFZ.Audio/WasapiAudioSource.cs` | Capture path; confirms no AGC/limiter exists; `WdlResamplingSampleProvider` fixed-ratio resampling with no clock-drift correction; buffer-drop `LogWarning` call sites used by §3.1's log-mining |
| `src/OpenWSFZ.Audio/CaptureManager.cs` | Bounded channel (`DropOldest`, capacity 16) — the other buffer-drop mechanism §3.1 checks for |
| `src/OpenWSFZ.Ft8/Ft8Decoder.cs` | Per-cycle decode entry point; confirms candidate/LDPC state is not carried cross-cycle |
| `Native/ft8_shim.c` | `g_session_hash_table`, `monitor_init` per call — confirms the one real cross-cycle state (hash table) is wrong-direction for this symptom, and waterfall/candidate state is fresh every cycle |
| `artefacts/20260706_live_run_2308/logs/openswfz-20260706T210818Z.log` | Retained Debug-level live daemon log, 07-07 session — Phase 1a input |
| `artefacts/20260622_live run/openswfz-20260621T225646Z.log` | Retained Debug-level live daemon log, 06-22 session — Phase 1a input |
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/classify_cochannel.py` | `parse()`/`sig_key()` — reused, extended (copy) for Phase 1b's DT extraction |
| `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/run_isolated_replay.py` | Replay harness reused, modified (copy) for Phase 2 to retain Decoded-on-replay identity |
