# Developer handoff: decode-quality collapse after long continuous uptime

**Authored by:** QA (per HK-011/HK-015/HK-000), from a live incident during the 2026-07-31→08-01
multi-day 20m live run (`qa/cycleframer-alignment-replay/2026-07-31-1907-...-preflight-brief-
multiday-20m-live-run.md`).
**Branch:** fresh off `main`, current tip `2dacd1a`. This is investigation, not a known fix — scope
the branch once a root cause is found.
**Status:** ✅ **CLOSED 2026-08-03 — fixed and merged as `be5960a`.** See §0. This was the
reopened `CycleFramer` clock drift, tracked in
`dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-after-pr118.md`. **These are ONE
defect, not two;** that fix closes this one. See §0 below. A clean process restart is a workaround
because it resets accumulated drift to zero, not because it clears any runtime state.

**Superseded status line (retained for provenance):** *"live defect, reproduced once, root cause
not yet known… No regression test exists for this path."* Both italicised claims are now corrected:
the cause is known, and it **reproduced three times**, once per restart segment of the 07-31 corpus,
at consistent uptime. It is not an incident; it is a deterministic function of uptime.
**Severity:** high for this project's current priorities — 8080 is the "decisive corpus" instance
for an active multi-day corpus-gathering run; if this recurs unnoticed, it silently degrades the
one dataset the whole run exists to produce, while every existing health signal (heartbeat,
`[ERR]`/`[FTL]`, archiving) stays green throughout.

---

## 0. ✅ CLOSED — fix merged 2026-08-03 as `be5960a`

**This dev-task is closed. No Developer session is needed and none should be opened.** The root
cause below was fixed by the `CycleFramer` grid-realignment work merged to `main` as **`be5960a`**
(CI run `30831377759`, green on ubuntu/windows/macos). The capture window now re-anchors to the UTC
15-second grid at sample level every cycle; measured worst-case offset over a simulated 24 h at
48.4 ppm is **9 samples (0.75 ms)**, against the ~4.1 s that produced this collapse.

The §7 question this document left open — *"Tests required, once a root cause is found"* — is
answered by that work's oracle: five cases in `CycleFramerClockDriftOracleTests.cs`, including a
restart-punctuated multi-epoch case built specifically because **this** document's failure shape
(collapse after long uptime, cleared by restart) is what a single-epoch oracle cannot distinguish
from "bounded forever".

See `DEFECT-capture-clock-drift-silent-decode-loss.md`'s CLOSED banner for the full closure.

*Retained below for provenance: the incident record and the ruled-out candidates, which remain
accurate and are the reason the eventual diagnosis held together.*

---

## 0b. Resolution — how the root cause was identified, QA 2026-08-03 (14:35 UTC)

The collapse is the `CycleFramer` capture window walking off the UTC 15-second grid at 48.0 ppm and
crossing FT8's ~2.36 s guard interval. 8080/8081 decode ratio pooled over the corpus's three restart
segments, against accumulated drift:

| uptime | drift | 8080/8081 | |
|---:|---:|---:|---|
| 0–5 h | 0–0.86 s | 0.93–0.97 | flat, healthy |
| 6–11 h | 1.04–1.90 s | 0.95 → 0.81 | gradual decline |
| **12 h** | **2.07 s** | **0.713** | **cliff begins** |
| 13 h | 2.25 s | 0.426 | |
| 14 h | 2.42 s | **0.254** | past the guard interval |

**Every candidate ruled out in §2 below is *consistent* with drift rather than contradicting it:**

- *Power-cycling the radio didn't fix it* — correct; the defect is software framing, not RF.
- *A daemon restart fixed it completely* — correct; a restart re-anchors `cycleStart` to the grid
  at start-up (`CycleFramer.cs:86`) and resets accumulated drift to zero.
- *8081 was unaffected throughout* — correct; that chain drifts at 4.7 ppm, reaching 2 s at ~118 h.
  The run was 43.5 h, so 8081 never approached the cliff.

§2's checks were sound and remain valid; they simply could not see the mechanism, because the
window's alignment was not among the things measured. The ~14 h onset in §1 is the cliff.

⚠️ **Do not open a Developer session against this file.** The work is in the drift dev-task. This
one should be archived against that fix once it lands, and its §7 ("Tests required, once a root
cause is found") is answered by that task's §4 oracle work.

---

## 1. Incident summary

At approximately `2026-08-01T10:08Z`, after ~14 hours of continuous uptime, the 8080 instance's
decode rate collapsed from its session baseline (~20-24 decodes/cycle) to a 20-cycle mean of
1.45-3.05/cycle, including a run of three consecutive zero-decode cycles. The paired 8081 instance
— identical software, same band, same minutes, different physical hardware — was **completely
unaffected** throughout (steady 16-25 decodes/cycle). The collapse did not self-resolve; it was
still ongoing 49 minutes later when a manual daemon restart (same `config.json`, same `--port`,
nothing else changed) fully cleared it. Post-restart: 17-26 decodes/cycle and candidate counts of
131-140 within the first six cycles.

## 2. What was ruled out, and how

All checks below were run directly against the live WAV/log data, not assumed:

| Candidate cause | Check | Result |
|---|---|---|
| Clipping | Sample-level clip detection on recent WAVs | `clipped_frac = 0` throughout the collapse window |
| Silence / low input level | WAV peak/RMS | Normal (~0.13-0.15 peak, ~0.03-0.04 RMS), matching the session baseline exactly |
| Elevated noise floor | App's own `noise_floor` log metric | `-67` to `-68 dB` during the collapse — at or below the session average, not elevated |
| Hash-table saturation (`f-005-hash-table-saturation-diagnostic`) | Compared `hashTableRejectCount` between instances | 8081's reject count was **higher** than 8080's throughout (114,819 vs. 95,789 at the time) and 8081 showed zero decode impact — this rules the hash table out cleanly |
| Hardware/RF (radio, antenna, cable, receiver AGC) | Power-cycled the physical radio | **Did not fix it** — decode rate was, if anything, slightly worse in the 20 cycles immediately after (mean 1.45 vs. 2.3 before) |
| Software/process runtime state | Restarted the daemon process, config unchanged | **Fixed it completely**, within 6 cycles |

The elimination of hardware (power-cycle didn't help) combined with the software restart curing it
completely, with literally nothing else in the signal chain touched, is the strongest evidence:
**this is a software or runtime-state defect that surfaces after long continuous uptime**, not a
hardware, RF, or configuration issue.

## 3. What changed, mechanically

Not just "fewer decodes" — the shape of the failure is specific and worth preserving:

- **Raw LDPC candidate count dropped.** 8080 found 140-200 candidates/cycle earlier in the *same*
  session (e.g. `22:05Z`: `140 candidates found, 22 decoded`; `200 candidates found` on pass 2).
  During the collapse: `54-96 candidates found`, consistently lower. 8081 held steady at 140
  throughout the entire session, collapse window included.
- **LDPC fail rate on found candidates rose sharply.** Example from mid-collapse:
  ```
  Iterative subtraction: pass 1 of 2, 80 candidates found, 3 decoded.
  Iterative subtraction: pass 1 LDPC fail stats — failCands=74 meanAbsLLR=4.034 prenormVar=76.0432
  ```
  `meanAbsLLR` (~4.0) is in the same range as healthy cycles — i.e. this does not look like "the
  same candidates, just weaker signal driving more marginal LLRs failing checksum by a hair." It
  looks like a difference in candidate *quality/selection* itself, not simply reduced SNR. Whoever
  picks this up should not assume it's an SNR story without checking — the `meanAbsLLR` data argues
  against that being the whole picture.
- **Hashtable reject count kept climbing normally** (95,789 → 97,665 across the window) — i.e.
  decode processing was still running, just producing far fewer successful decodes per cycle.

## 4. Candidate hypotheses, unranked — this is genuinely open

None of these are confirmed; listed so the investigation doesn't retread ruled-out ground and has
a starting menu:

- **A different process-global native state degrading over time**, analogous in kind (not cause)
  to the callsign hash table's 256-slot saturation (`f-001-hashed-callsign-resolution`,
  `Ft8LibInterop.cs` ABI history) — but *not* the hash table itself, which is ruled out above by
  the cross-instance comparison. Worth auditing `ft8_shim.c`/`decode.c` for any other
  process-lifetime accumulator, cache, or fixed-capacity table that a 256-slot-style ceiling could
  apply to and that isn't yet observable via a getter the way `GetHashTableRejectCount()` is.
- **Managed-side state**: anything in `Ft8Decoder`, `CycleFramer`, or the decode-pump path
  (`OpenWSFZ.Daemon`) that accumulates per-cycle without bound over many hours — a growing
  collection, a cache without eviction, GC pressure changing timing enough to affect the decode
  window in a way that degrades candidate-finding specifically.
- **Floating-point/numeric drift** in whatever produces the LLR inputs to LDPC, if any running
  statistic (e.g. a noise-floor or calibration estimate) is computed incrementally rather than
  freshly per cycle and could drift over ~14h of continuous operation.
- **Not (yet) suspected, but not fully excluded**: a slow memory leak elsewhere in the process
  causing some unrelated resource pressure that manifests as degraded candidate-finding — differs
  from the above in that it wouldn't point at decode-specific code at all. Worth a quick working-set
  check on a future long-uptime instance before ruling this out.

## 5. Reproduction — the hard part

This did not reproduce quickly; it took ~14 hours of continuous decoding on real off-air audio to
manifest, and has only been observed once. Suggested approach, in order of cost:

1. **Cheapest first**: instrument a long-uptime run (the current live run, or a fresh one) with
   periodic dumps of whatever internal state the hypotheses in §4 point at, so if/when this recurs
   there's more to look at than "candidate count dropped."
2. **If a fast repro is needed**: consider whether replaying the archived WAV corpus from this
   incident (`OpenWSFZ-8080-capture/cycle-audio/`, cycles around `10:08Z`-`10:57Z` on 2026-08-01,
   see the manifest cross-reference in `qa/endurance/2026-08-02-multiday-20m-anova/CONTAMINATION-NOTE.md`)
   through a *freshly started* decoder reproduces the low-candidate behavior on that same audio —
   if a fresh process decodes the same WAVs fine, that confirms the defect is in accumulated
   process state, not the audio content itself (which is already strongly implied but not yet
   directly proven on the exact same input).
3. **Longest but most direct**: run two identical instances side by side (mirroring tonight's
   8080/8081 setup) for 24h+ and watch for either one to reproduce the pattern, with the
   instrumentation from step 1 already in place.

## 6. A short-term mitigation was attempted — tested end-to-end, found to carry a real risk, and disarmed

Both supervisor scripts (`qa/endurance/2026-07-31-supervisor-{8080,8081}.sh`) still carry a
cross-instance decode-collapse detector (`check_decode_collapse`/`recent_decode_mean`): each
instance would periodically compare its own recent decode-rate mean against its sibling's (same
band, same time — a shared/correlated dip, like the real over-the-air noise burst and the
noise-floor rise also observed the same night, must NOT trigger a restart; only a one-sided
collapse should). This was armed once (`ENABLE_CROSS_INSTANCE_DECODE_CHECK=1`) on the Captain's
direction that a recurrence must self-heal with no shell interaction required, after the verdict
formula and the function bodies were validated against real historical numbers (own_mean=3.25 vs.
sibling_mean=21.10 → correctly `bad`; the healthy post-recovery state → correctly `ok`).

**That unit-level validation was real but insufficient — it never exercised the actual
detect→kill→relaunch integration.** The Captain correctly pushed back on this and asked for a true
end-to-end test: a throwaway third daemon instance (port `9998`, same real Voicemeeter B1 device,
shared-mode, never touching production), fed synthetic low decode-count lines, watched by a
byte-for-byte copy of the real supervisor logic (only three timing constants shortened for a fast
test; verdict thresholds unchanged), launched with exactly one shell command and left to run
autonomously.

**Result: a real, fully autonomous kill-and-relaunch did occur, with zero further shell/tool calls
— but not via the decode-collapse trigger.** It fired on heartbeat-stall instead, and the timing is
the tell: the supervisor declared "no Heartbeat line in >90s" at `18:03:42Z`, one second *before*
the log shows a real heartbeat was written at `18:03:43Z` — and across the whole 91-second window
before that, **not one `"decode-collapse check: ..."` line appears**, despite synthetic low-decode
data being present in the log from the first few seconds. The check's periodic evaluation
essentially never ran.

**Working theory:** `recent_decode_mean` does `tail -n 4000 "$own_log"` on the *same file* the
outer loop already holds open via a persistent `tail -f -n 0`. On Windows/git-bash, a second `tail`
process opening that same actively-written file plausibly contends with the first one's handle,
stalling `read -t 10` on the `-f` pipe for far longer than 10s at a stretch. This would explain
both symptoms at once: the missing check-log lines, and the heartbeat-stall firing based on a
`last_heartbeat_epoch` that had fallen behind real time. **Not proven — a hypothesis with strong
circumstantial support, worth confirming (or ruling out) before this mitigation is ever re-armed.**

**Why this matters more than a failed test:** if the theory is right, the exact same pattern was
live on production 8080 and 8081 for roughly 35 minutes before this test ran. Zero
`"decode-collapse check"` lines appeared in either production `restart-supervisor.log` in that
window either — consistent with the check being silently inert there too, which means it was
providing no actual protection while carrying the same latent risk of eventually firing a false,
disruptive restart on the decisive corpus for a reason completely unrelated to decode quality.

**Disposition: disarmed on the Captain's instruction (`ENABLE_CROSS_INSTANCE_DECODE_CHECK` back to
default `0` on both production supervisors), effective 2026-08-01 ~18:10Z.** Do not re-arm without
first either (a) confirming/refuting the tail-contention theory and fixing the log-reading approach
so it doesn't share a file handle with the `tail -f`, or (b) redesigning the check to read decode
counts a different way entirely (e.g. tracking a running count from lines already consumed by the
main read loop, rather than re-reading the file with a second process). The scratch test artefacts
(`D:/Projects/claude/OpenWSFZ-test-decode-collapse/`) are left in place for whoever picks this up —
`restart-supervisor.log` and `HARNESS-RESULT.log` there have the full timeline.

If a redesigned version of this fires in the future, the trigger reason is written to
`restart-supervisor.log` (`"decode collapse: ..."`) and the corpus should get a new dated entry in
a `CONTAMINATION-NOTE.md`-style note, same as Window 4 below, recording the affected
`cycle_start_utc` span for exclusion from any decode-yield analysis — an auto-restart fixes the
daemon, it does not retroactively make the degraded window's
data representative.

## 7. Tests required, once a root cause is found

Depends entirely on what the root cause turns out to be — cannot be specified yet. At minimum,
whatever regression test is added should exercise the same shape of evidence used to root-cause it
here (a long-running or state-accumulating scenario that reproduces reduced candidate-finding
without any change to input audio), so a future fix regression is caught the same way this one was
caught: by comparing decode yield against a control, not by log errors, which this defect produces
none of.

## 8. Update — two further occurrences during the same live run; run now ended (2026-08-02)

The multi-day 20m live run this incident was first found on continued after this handoff was
written, and the same defect recurred twice more before the run was deliberately ended by the
Captain. Both were caught and handled by QA's judgment-based autonomous restart policy (a separate,
lighter mechanism than §6's disarmed cross-instance check — direct human/QA reading of the
`Decodes/30min` status-check column, not a scripted heuristic). Full blow-by-blow for both is in
`qa/endurance/2026-08-02-multiday-20m-anova/CONTAMINATION-NOTE.md`, Windows 6 and 7 — summary here for anyone
who doesn't want to read the whole contamination note first:

- **Window 6** (`2026-08-02T00:39Z`): same signature — one-sided `Decodes/30min` decline against a
  flat 8081, `0-dec/20` never reached zero. Restart fixed it, single-cycle recovery confirmed.
  Uptime since Window 4's restart: **~13h42m**.
- **Window 7** (`2026-08-02T13:43Z`): same signature again. Restart fixed it, but the *relaunched*
  instance itself died again ~76 seconds after the restart script's own heartbeat check confirmed it
  healthy — caught only because the supervisor's independent heartbeat-stall watchdog fired
  separately and relaunched a second time. **This means a single-point heartbeat check immediately
  after relaunch is not sufficient evidence of a durable recovery** — worth folding into whatever
  fix or improved restart tooling comes out of this investigation; the pattern suggests the
  defect's aftermath (whatever it is) can destabilize a fresh process for the first minute or so
  after restart, not just the long-uptime process before it. Uptime since Window 6's restart:
  **~13h03m**.

**The recurrence-interval pattern is now the single strongest lead for root-causing this**, and
wasn't visible after just one occurrence: measured uptime-since-prior-restart at each trigger was
**~14h (Window 4's original cold onset) → ~13h42m (Window 6) → ~13h03m (Window 7)** — three
independent measurements, all in a tight 13-14h band. This is much more consistent with an
uptime/state-accumulation trigger (a counter, cache, or buffer saturating on a roughly fixed
cadence — see the §4 hypothesis menu, especially the "process-lifetime accumulator" and
"unbounded managed-side collection" candidates) than with time-of-day or band-conditions
explanations, both of which would predict a much less regular interval. Whoever picks this up next:
start by looking for anything with a ~13-14h natural period at typical decode cadence (cycle count,
elapsed samples, a timer with a fixed rollover, etc.) rather than re-deriving the hypothesis list
from scratch.

**Autonomous-restart tally for the whole run: 2/5** (both used on this defect, both confirmed
recovered, cap never approached). **Run ended `2026-08-02T~15:52Z`** — decoding stopped in-app by
the Captain, daemons/supervisors/monitoring processes torn down by QA per the standing teardown
checklist, final corpus gathered to `artefacts/20260731_live_run_2004-8080/` and
`artefacts/20260731_live_run_2004-8081/` (`tools/gather_live_run_artefacts.py`, HK-016). Root cause
is **still unidentified** — this remains the top open item from this run.

## 9. References

- `qa/endurance/2026-08-02-multiday-20m-anova/CONTAMINATION-NOTE.md`, "Window 4" — full incident timeline,
  measurements, and manifest cross-reference for the affected corpus span.
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs:430-447` — `hashTableRejectCount` logging, the metric that was
  investigated and ruled out as a cause here.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:195-224` — native shim ABI version history, useful
  background on the callsign hash table's known 256-slot capacity ceiling (a different, already-
  understood saturation mechanism — useful as a model for "what a process-lifetime ceiling looks
  like in this codebase," not as the cause of this incident).
- `qa/endurance/2026-07-31-supervisor-8080.sh` and `-8081.sh` — the draft mitigation from §6.
