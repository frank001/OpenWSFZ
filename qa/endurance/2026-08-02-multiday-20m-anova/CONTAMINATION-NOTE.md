# Audio contamination / notable-event note, 2026-07-31 → 08-02 (multi-day 20m live run)

**RUN ENDED `2026-08-02T~15:52Z`.** Decoding stopped in-app by the Captain; both daemons,
both supervisors, and the standing status-check loop torn down by QA per the standard teardown
sequence (supervisors killed before daemons so neither auto-restart fought the stop; a full
orphan sweep afterward caught and killed two stray `tail.exe` processes — one a known HK-023
half-detached `TaskStop` artifact, one a genuine leftover from an earlier supervisor incarnation
predating this session). Final corpus gathered via `tools/gather_live_run_artefacts.py` (HK-016)
to `artefacts/20260731_live_run_2004-8080/` and `artefacts/20260731_live_run_2004-8081/` —
184,918 / 212,422 `ALL.TXT` lines, 10,489 / 10,512 WAVs, full daemon log history, both alongside a
matching WSJT-X-side copy for comparison. Everything below this line is the still-accurate history
of the run; nothing in it needs to change now that the run is over.

**Status:** Confirmed by direct measurement (WAV peak amplitude, RMS, sample-level clip detection,
decode-log counts), not just observation. Windows 1, 2, and 5 are self-inflicted, deliberate live
experimentation by the Captain (not a capture-chain or app defect). Window 3 is neither
self-inflicted nor a defect — a genuine over-the-air event, kept here for corpus completeness, not
as a warning. **Windows 4, 6, and 7 are the same genuine software defect recurring** — a real
decode-quality collapse on 8080, root cause not yet known, see
`dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` §8 for the full three-occurrence
pattern and the recurrence-interval finding. Flagged per the same standard as
`qa/endurance/2026-07-29-5016363/CONTAMINATION-NOTE.md` so the corpus below is not treated as
uniformly clean for study purposes without accounting for all seven windows.

**Build under test:** `main` @ `2dacd1a` (post PR #119). Not implicated in Windows 1-3 — those are
caused by external audio-chain adjustments (Windows input-volume slider, SDR Uno's own RX Control
VOLUME slider), not by the daemon or the archive pipeline. `CycleArchiveService` behaved correctly
throughout: it archived exactly what was on the wire, including the silence and the clipping,
faithfully.

## QA-judgment autonomous restart policy (2026-08-01, replaces the supervisor-level mitigation)

Per the Captain's direction: no supervisor-script changes (the cross-instance decode-collapse
check stays disarmed, see Window 4 §6 in the dev-task). Instead, on every 30-minute check, QA
(this session) looks for anomalies directly; if one has clearly persisted for more than 5 minutes
(the last-20-cycle / 5-minute window already sampled each check), the affected instance (8080 or
8081) is restarted directly — same procedure as the original Window 4 fix: stop, relaunch with
identical config, confirm recovery over the following cycles — and logged here every time, not
just once. Capped at 5 such restarts total for this run; each one increments the tally below.

**Autonomous-restart tally: 2 / 5 used.** (Window 6, `2026-08-02T00:39Z`, 8080. Window 7, `2026-08-02T13:43Z`, 8080.)

## Cause

The Captain was live-experimenting with input gain on both instances, chasing a visual difference
in waterfall brightness between the two web UI panels. In hindsight (see "Retrospective" below)
that visual difference was not evidence of a real decode problem — 8080 had been decoding cleanly
at ~20-26 decodes/cycle the entire session, before, during, and after every gain change described
here — but the live experimentation itself produced two real, measurable contamination windows.

## Window 1 — 8081 (SDR Uno / Voicemeeter Out B1): silence

**Cause:** SDR Uno's own RX Control panel VOLUME slider (a gain stage upstream of the Windows
audio endpoint, confirmed distinct from it — see "Two independent gain stages" below) was dragged
to zero.

| | |
|---|---|
| **Window (UTC, cycle-start timestamps from the archived WAV filenames)** | `2026-07-31T20:13:15Z` – `2026-07-31T20:13:30Z` |
| **Duration** | ~30 s (2 cycles) |
| **Evidence** | `260731_201315.wav` and `260731_201330.wav` in `OpenWSFZ-8081-capture/cycle-audio/`: peak amplitude **exactly 0.0** (pure digital silence), vs. 0.09–0.22 immediately before and after |
| **Bounded by** | `260731_201300.wav` (peak 0.10, clean) before; `260731_201345.wav` (peak 0.20, clean) after |

## Window 2 — 8080 (physical radio / USB Audio CODEC): hard clipping

**Cause:** Windows recording level for "Microphone (2- USB Audio CODEC)" raised from its
session-long baseline of 53.7% to 100%, via the device's Windows Sound Settings "Input volume"
slider.

| | |
|---|---|
| **Window (UTC, cycle-start timestamps from the archived WAV filenames)** | `2026-07-31T20:21:45Z` – `2026-07-31T20:23:30Z` |
| **Duration** | ~120 s (8 cycles) |
| **Evidence** | Sample-level clip detection (samples at/above 98% of full scale) on all 8 WAVs in the window: `260731_202145.wav` through `260731_202330.wav`, peak amplitude pinned at **1.0000** (full digital scale) with 0.36%–1.71% of samples clipped per file — genuine sustained distortion, not a brief transient |
| **Bounded by** | `260731_202130.wav` (peak 0.046, clean, `clipped_frac=0`) before; `260731_202345.wav` (peak 0.147, clean, `clipped_frac=0`) after |

### ⚠️ This window also affects WSJT-X, not just this app's archive — confirmed directly, not inferred

Initial concern raised (correctly) that this was only an inference from "same device," and that
WSJT-X has its own independent Rx gain slider that might have protected it. Checked directly rather
than argued: WSJT-X was saving its own WAVs to `%LocalAppData%\WSJT-X\save\` throughout this window,
with the same UTC-cycle filenames as this app's archive. Measured them the same way:

| WSJT-X's own saved WAV | Peak | Clipped fraction |
|---|---:|---:|
| `260731_202130.wav` | 0.046 | 0 (clean) |
| `260731_202145.wav` | 0.9999 | 0.24% <<< clipping |
| `260731_202200.wav` | 1.0000 | 0.32% <<< clipping |
| `260731_202215.wav` | 1.0000 | 0.32% <<< clipping |
| `260731_202230.wav` | 0.9999 | 0.34% <<< clipping |
| `260731_202245.wav` | 0.9997 | 0.11% <<< clipping |
| `260731_202300.wav` | 0.9999 | 0.32% <<< clipping |
| `260731_202315.wav` | 0.9998 | 0.08% <<< clipping |
| `260731_202330.wav` | 1.0000 | 0.13% <<< clipping |
| `260731_202345.wav` | 0.143 | 0 (clean) |

Same boundaries as this app's archive, independently confirmed. WSJT-X's Rx gain slider operates
*after* it receives audio from Windows — the clipping happens upstream of that, either in the USB
CODEC's own analog input stage or in the Windows endpoint's shared digital gain (the "Input volume"
control, applied once by WASAPI and delivered identically to every app capturing that device in
shared mode, which is the default). No downstream slider, in WSJT-X or anywhere else, can recover a
waveform once it's been pinned at the ceiling — turning gain down afterward only makes the already-
distorted signal quieter. Any WSJT-X decodes or ADIF log entries falling inside `20:21:45Z`–
`20:23:30Z` on 20m should be treated with the same caution as this app's archived cycles for that
span.

## Window 3 — both instances: correlated broadband noise burst (not a defect, not self-inflicted)

**Cause:** Not determined — no local audio-chain adjustment was in progress at the time (both
instances had been stable and untouched for over an hour by this point). Character of the event
points to a genuine over-the-air occurrence rather than a local artifact — see reasoning below.

| | |
|---|---|
| **Window (UTC)** | `2026-08-01T00:35:01Z` – `2026-08-01T00:36:16Z` |
| **Duration** | ~75 s (5 cycles), self-resolved — no intervention |
| **Evidence** | RMS elevation ~2–4× baseline on both instances at the *same* UTC cycles, correlated: 8080 `260801_003501/003531/003601.wav` RMS 0.066–0.077 vs. ~0.033–0.042 baseline; 8081 `260801_003501/003531/003601.wav` RMS 0.066–0.132 vs. ~0.005–0.013 baseline, including one large transient peak (0.698) at `003615.wav` with low RMS (a brief click, not sustained). Both back to baseline by `003631`/`003630` |
| **Clipping** | None on either instance throughout (`clipped_frac = 0` on every file) |
| **Decode impact** | None evident — 8080 continued decoding 8–14 messages/cycle through and after the window |

**Why this is filed differently from Windows 1 and 2:** those were reproduced by a known, single-
device local action and only ever showed up on the one instance being adjusted. This burst is
correlated across **two independent hardware paths** (USB CODEC microphone vs. SDR Uno/Voicemeeter)
at the same UTC cycle boundaries. A local Windows/application audio leak (the 07-29 precedent)
would only reach whichever single device it was routed to — it would not appear on both receivers'
completely separate signal chains simultaneously. Two independent antennas hearing the same thing
at the same moment is evidence of something genuinely on 14.074 MHz (a strong nearby transmission,
QRM, or atmospheric noise), not a defect in either capture chain. Recorded for corpus completeness
only — no action taken, none needed.

## Band-conditions observation — gradual noise-floor rise across the session (not a defect)

Raised by the Captain's own read of the waterfall ("noise seems persistent, maybe just degrading
of the band") after Window 3 above was already reported resolved. Checked the app's own
`noise_floor` log metric across the *entire* session rather than just the recent window, since a
short-term RMS check (which showed clean/normal in the minutes right after Window 3) cannot reveal
a slow multi-hour drift.

| | First 40 cycles (session start, ~20:04Z) | Last 40 cycles (~00:43Z) | Change |
|---|---:|---:|---:|
| 8080 `noise_floor` mean | −70.0 dB | −63.3 dB | +6.7 dB |
| 8081 `noise_floor` mean | −72.4 dB | −61.8 dB | +10.6 dB |

Real and correlated across both independent receivers — consistent with genuine evening-into-night
HF noise floor rise, not a capture-chain artifact (same reasoning as Window 3: a local defect would
not move both independent hardware paths together). Decode counts have **not** collapsed
proportionally — first-20 vs. last-20 cycle means are 20.9→19.3 (8080) and 22.3→19.3 (8081), a
~7–13% dip well inside normal hour-to-hour variance and nowhere near the 07-29 precedent's actual
escalation pattern (59%→18%→2% collapse). No action taken; recorded because a multi-hour noise-
floor drift is directly relevant to any density or SNR analysis run over this corpus later, even
though it isn't currently hurting decode yield.

## Window 4 — 8080: decode-quality collapse, root cause unknown (real defect, not self-inflicted)

Distinct from the noise-floor observation above, and found in the course of investigating what
first looked like it might be related. **This is the one entry in this note that is a genuine
software defect, not experimentation or a band-conditions artifact.**

| | |
|---|---|
| **Window (UTC)** | approx. `2026-08-01T10:08Z` – `10:57Z` (~49 min), ended by a manual daemon restart, not self-resolved |
| **Symptom** | Decode rate collapsed from the session baseline (~20-24/cycle) to a 20-cycle mean of 1.45-3.05/cycle, including a run of three consecutive zero-decode cycles. 8081 was unaffected throughout (steady 16-25/cycle, same band, same minutes) |
| **Ruled out** | Clipping (`clipped_frac=0`), silence, low audio level (WAV peak/RMS normal throughout), elevated noise floor (`-67` to `-68 dB`, at or below the session average), hash-table saturation (8081's `hashTableRejectCount` was *higher* than 8080's throughout and showed zero effect) |
| **What changed** | Raw LDPC candidate count itself dropped — from the 140-200 range 8080 also showed earlier in this same session, down to 39-96, while 8081 held steady at 140 throughout. LDPC fail rate on found candidates also rose sharply (most candidates failing checksum, `meanAbsLLR` unchanged — i.e. not simply "weaker signal," something about candidate quality itself) |
| **Diagnostic steps taken, in order** | 1) Power-cycled the physical radio — **did not fix it**, arguably slightly worse afterward. 2) Restarted the 8080 daemon process — **same config, same radio, same antenna, nothing else changed — fully fixed it**, decode rate back to 17-26/cycle and candidate counts back to 131-140 within the first six cycles after restart |
| **Conclusion** | Since a clean process restart alone cured it with literally nothing else changed, this rules out hardware/RF as the cause and points at a **software/runtime-state defect that surfaces after long continuous uptime** (~14h in this occurrence). ~~Root cause not yet identified~~ — **superseded 2026-08-04, see note below.** |

**Superseded 2026-08-04 (QA, Task 1 of the FP-surge spec).** This window's "root cause not yet
identified" line is stale, not this window's own observations, which stand as recorded above and
are not being rewritten. The cause was identified 2026-08-03: the `CycleFramer` capture window
drifting off the UTC 15 s grid at 48.0 ppm and crossing FT8's ~2.36 s guard interval — fixed and
merged as `be5960a`. Measured directly, not just attributed: on `artefacts/20260803_live_run_1713/`
(post-fix), the decisive 18.96 h uptime epoch shows no decode-ratio cliff past the 13.7 h point
(`median(ratio, after)` = 93.5% of `median(ratio, before)`, clear of the 0.80x NOT-CLOSED bar; see
`qa/endurance/2026-08-03-drift-screen/window4_closure_check.py`). See
`dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` Sec.0/Sec.0b for the full
resolution. The disarmed cross-instance decode-collapse detector (Sec.6 of that dev-task) is not
needed for this specific failure mode; whether it is wanted for a different one remains open.

**Operational note:** the supervisor did not and could not detect this — every signal it watches
(heartbeat, `[ERR]`/`[FTL]`, archiving liveness) stayed green throughout. A cross-instance detection
heuristic was drafted, unit-validated against this incident's real numbers, and briefly armed live
on both supervisors — then a proper end-to-end integration test (a throwaway third daemon instance,
synthetic decode data, the real supervisor logic, launched with one shell command and left
autonomous) found it likely does not work as intended on this platform: it never fired on its own
trigger during the test, a false heartbeat-stall fired instead, and the evidence points at a
Windows-specific file-handle contention between the check's own log-reading and the supervisor's
persistent `tail -f`. **Disarmed on both production instances as of ~18:10Z the same day**, since an
inert-but-risky check is worse than no check. See
`dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` §6 for the full test writeup and
the disposition. Until redesigned and re-tested, a recurrence of Window 4's pattern can only be
caught by direct judgment during a check-in — which is, in fact, exactly how this one was caught in
the first place.

## Two independent gain stages on the 8081 path (found while diagnosing this)

Queried directly via the app's own NAudio libraries against the live Windows audio endpoints
(`NAudio.CoreAudioApi.MMDeviceEnumerator`, not inferred): the Windows recording level for
**Voicemeeter Out B1 was already pinned at 100%** throughout tonight's experimentation and was
never touched. All of Window 1's silence and the subsequent elevated levels came entirely from SDR
Uno's own internal VOLUME slider, a separate gain stage feeding into that already-maxed Windows
input. Worth recording since it isn't obvious from the app's config or the Windows Sound panel
alone that there are two stacked, independently-adjustable gain controls in that specific chain.

## Settled state (as of this note, still running)

Both sides confirmed clean and stable across 6+ consecutive cycles before this note was written:

| Instance | Windows input level | WAV peak range (clean cycles) | Clipping |
|---|---|---:|---|
| 8080 (radio) | 80% (Input volume slider, Windows Sound Settings) | 0.150–0.182 | none |
| 8081 (SDR Uno) | 100% (unchanged all session; SDR Uno's own VOLUME slider set by ear to "somewhat" matching, no exposed numeric value) | 0.080–0.158 | none |

## Retrospective — was any of this necessary?

No functional decode problem motivated the experimentation. 8080 was decoding cleanly (~20-26
decodes/cycle, zero errors, zero clipping) at the original 53.7% mic level for the entire session
before this began. The two receivers are different hardware chains (physical radio + USB CODEC vs.
SDR Uno + virtual audio bus) with no inherent reason to read the same absolute level, and nothing
in this run's actual goal (the 8080-vs-paired-WSJT-X density-penalty comparison) depends on 8080
and 8081 matching each other — the 8080/8081 same-band overlap is a secondary bonus comparison,
not the decisive corpus. The only concrete effects of the chase were the two contamination windows
above. Recorded here as the direct, procedural lesson: a visual gain difference between two
independently-rendered waterfall panels is not evidence of anything by itself — check WAV peak
amplitude (or decode counts, which never moved) before treating it as a problem worth touching a
running capture for.

## Window 5 — 8081: deliberate SDR Uno gain test (self-inflicted, disclosed as a test after the fact)

**Cause:** Captain-initiated SDR Uno audio-setting changes, disclosed afterward as a deliberate test
of whether QA would react to a self-inflicted deviation by restarting the instance.

| | |
|---|---|
| **Window (UTC)** | `2026-08-01T18:45Z` – `19:30Z` (~45 min), ended by the Captain restoring the prior SDR Uno settings, not by any restart |
| **Effect** | 8081's `Decodes/30min` ratio against WSJT-X fell to **29.4%** at the `19:24:57Z` check (vs. its normal ~55-60% range) — invisible in the cumulative `vs WSJT-X` column, which barely moved, since a 45-minute dip is diluted across a session already carrying 100,000+ cumulative lines. Recovered on its own after restoration: 29.4% → 38.5% (`19:33Z`) → 46.3% (`19:37Z`) → 57.5% (`19:46Z`), back to baseline |
| **Audio/archive integrity** | No silence, no clipping — WAVs continued archiving normally throughout; only decode *yield* was reduced, not capture quality |
| **Response** | No restart performed. Correctly attributed to a stated, external, self-disclosed cause rather than treated as a software anomaly — a restart cannot fix a gain/tuning setting, same lesson as Windows 1/2 |

**Why this one is recorded rather than dismissed as "just a test":** it directly motivated adding
the `Decodes/30min` column to the standard status check (the cumulative ratio alone would not have
surfaced this in a timely way, which is itself the point the Captain was demonstrating). It also
sits inside 8081's corpus at exactly this span, so it belongs in the manifest cross-reference below
on the same footing as Windows 1 and 2, even though nothing here was actually broken.

## Window 6 — 8080: recurrence of the long-uptime decode collapse, judgment-restarted (autonomous, QA-actioned)

Same signature as Window 4, caught and acted on during unattended overnight monitoring per the
QA-judgment autonomous restart policy (see top of this note) — the first live use of that policy
this run.

| | |
|---|---|
| **Window (UTC)** | `2026-08-01T23:38Z` – `2026-08-02T00:40Z` (~62 min), ended by an autonomous QA restart, not self-resolved |
| **Symptom** | 8080's `Decodes/30min` ratio against WSJT-X fell one-sided across three consecutive 30-min checks: 41.5% (`23:38Z`) → 31.9% (`00:08Z`) → 18.9% (`00:38Z`), while 8081 held steady-to-improving in the same spans (53.8% → 51.1% → 54.1%), same band, same minutes. `0-dec/20` stayed `0/20` throughout — this was a yield collapse, not yet a full stop, consistent with Window 4's progression before its own restart |
| **Context** | 8080 daemon uptime at trigger was ~13h42m (started `2026-08-01T10:57:02Z`) — inside the same long-continuous-uptime window as Window 4's ~14h occurrence. No external cause was stated or observed (Captain AFK, no gain/config changes in progress) |
| **Judgment** | First two data points (`23:38Z`, `00:08Z`) were held as "watching, not acting" per the >5-min-persisted / one-sided bar, explicitly logged as such at the time. The third consecutive one-sided reading (`00:38Z`), continuing to worsen rather than recovering, was judged to cross the trigger threshold — matches the known defect signature, not distinguishable from genuine band variance by that point |
| **Action** | `qa/endurance/restart-8080-on-anomaly.sh "one-sided decode-rate collapse..."` run as the single pre-staged atomic call at `00:39:47Z` (enabled to run without an interactive permission prompt via a narrow `.claude/settings.json` allowlist added this session specifically for these two restart scripts, since the Captain stated he is not available for shell-permission interaction) |
| **Outcome** | **PASS.** Old PID `34596` killed and confirmed dead (`00:39:51Z`), relaunch issued (`00:39:57Z`), new instance confirmed healthy via real heartbeat within 21s (`00:40:08Z`), new log `openswfz-20260802T003959Z.log` |
| **Tally** | Autonomous-restart count now **1 / 5** for this run |

Root cause remains unidentified (see `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md`)
— this is a second confirmed occurrence of the same unresolved defect, not a new one. Worth noting
for that investigation: recurrence interval from the Window 4 restart (`~10:57Z`) to this trigger
(`~23:38Z` onset) is close to Window 4's own onset-from-restart interval (~14h), which may support
an uptime-based (vs. purely time-of-day) trigger hypothesis.

## Window 7 — 8080: second recurrence of the long-uptime decode collapse, judgment-restarted (autonomous, QA-actioned)

Same signature as Windows 4 and 6, caught and acted on during continued unattended overnight/
morning monitoring per the QA-judgment autonomous restart policy. Second live use of the policy
this run, and notably close in recurrence interval to the first.

| | |
|---|---|
| **Window (UTC)** | `2026-08-02T12:12Z` – `13:44Z` (~92 min from first detectable softening to restart), ended by an autonomous QA restart, not self-resolved |
| **Symptom** | 8080's `Decodes/30min` ratio against WSJT-X declined across four consecutive 30-min checks: 58.4% (`12:12Z`) → 52.8% (`12:42Z`) → 48.8% (`13:12Z`) → 32.8% (`13:43Z`), while 8081 held flat in the same spans (68.2% → 66.7% → 68.1% → 65.0%), same band, same minutes. `0-dec/20` stayed `0/20` throughout — again a yield decline rather than a full stop at the point of restart, consistent with both prior occurrences |
| **Context** | 8080 daemon uptime at trigger was ~13h03m since the Window 6 restart (`2026-08-02T00:39:59Z` relaunch → `13:43Z` trigger) — closely matching Window 6's own ~13h42m-since-prior-restart interval and Window 4's original ~14h onset. No external cause was stated or observed (Captain AFK throughout) |
| **Judgment** | First reading (`12:42Z`, 52.8%) and second (`13:12Z`, 48.8%) were held as "watching" per the established >5-min-persisted / one-sided bar, explicitly logged as such at the time, since the decline was gradual and shallower than Window 6's. The third consecutive one-sided reading (`13:43Z`, 32.8%) — a steep drop rather than a continued gentle slope — was judged to cross the trigger threshold |
| **Action** | `qa/endurance/restart-8080-on-anomaly.sh "..."` run as the single pre-staged atomic call at `13:43:34Z`, via the same `.claude/settings.json` allowlist set up after Window 6 (no interactive permission prompt needed, consistent with the Captain being unavailable for shell interaction) |
| **Outcome** | **PASS.** Old PID `36376` killed and confirmed dead (`13:43:39Z`), relaunch issued (`13:43:46Z`), new instance confirmed healthy via real heartbeat within 24s (`13:44:03Z`), new log `openswfz-20260802T134348Z.log` |
| **Tally** | Autonomous-restart count now **2 / 5** for this run |

**Addendum, discovered `13:52Z` while answering the Captain's question about what he'd just seen:**
the instance my restart brought up did *not* stay healthy. The supervisor's own independent
heartbeat-stall watchdog (a pre-existing, always-armed mechanism, separate from the QA-judgment
restart policy) fired **76 seconds later**: `13:45:20Z` SUPERVISOR(8080) detected no heartbeat line
for >90s on PID `13068` (the process my restart had just relaunched and confirmed healthy at
`13:44:03Z`), killed it, waited its standard 300s cooldown, and relaunched again at `13:50:24Z`,
confirmed healthy at `13:50:54Z` — new log `openswfz-20260802T135024Z.log`, currently running as PID
`2180`. This is the supervisor's own retry counter (2/5), entirely separate from the QA-restart
tally above, which stays at 2/5.

**This means my restart script's single-point heartbeat check is not sufficient evidence of a
durable recovery** — it confirmed healthy against a process that died again under a minute and a
half later. Whether that's an artifact of restarting into the same defect's aftermath, a race
between the restart script's relaunch and the supervisor's watch-phase re-arm, or a distinct
instability worth its own investigation is open. **Manifest exclusion range for Window 7 extended
to `[12:12Z, 13:50Z]`** (was `13:44Z`) to cover the unstable intermediate instance. The
currently-running instance (`13:50:24Z` onward, PID `2180`, log `openswfz-20260802T135024Z.log`) is
**confirmed clean as of `14:43:33Z`** — first full 30-min cycle entirely inside the post-restart
window read 58.8% vs 8081's 61.5%, back in line with baseline.

Root cause still unidentified (`dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md`) —
this is a third confirmed occurrence of the same unresolved defect (Window 4, Window 6, Window 7).
**The recurrence intervals now form a pattern worth flagging to that investigation directly: ~14h
(Window 4's original onset from a cold/unknown-age start), then ~13h42m (Window 6, measured from
the Window 4 restart), then ~13h03m (Window 7, measured from the Window 6 restart)** — consistently
in the 13-14h band across three independent measurements, which is stronger evidence for an
uptime/state-accumulation trigger (e.g. a counter, buffer, or cache that saturates on a roughly
fixed cadence) than for a time-of-day or band-conditions explanation. Whatever the mechanism, the
autonomous restart policy is now handling it correctly and repeatably — two clean single-cycle
recoveries in a row.

## Manifest cross-reference

`cycle-archive.csv` (`CycleArchiveService.ManifestFileName`, one per instance directory) has one
row per archived cycle with `cycle_start_utc` and `dial_mhz` — cross-reference against the five
windows above to identify/exclude affected rows if this corpus is later used for a density or SNR
analysis:

- Window 1 (8081 silence): `cycle_start_utc` in `[20:13:15Z, 20:13:30Z]`
- Window 2 (8080 clipping): `cycle_start_utc` in `[20:21:45Z, 20:23:30Z]`
- Window 3 (correlated noise burst, both instances, not a defect): `cycle_start_utc` in
  `[00:35:01Z, 00:36:01Z]` on 2026-08-01 — flag rather than exclude, since decode quality was
  unaffected; only relevant if an analysis is specifically sensitive to elevated broadband noise.
- **Window 4 (8080 decode collapse, real defect): `cycle_start_utc` in `[10:08Z, 10:57Z]` on
  2026-08-01 — exclude from any density/decode-yield analysis on 8080.** Audio itself is clean
  (archived WAVs are not corrupted, only under-decoded relative to what they contain), but decode
  counts for this window are not representative of the app's normal performance and would bias any
  density comparison against WSJT-X for that span specifically.
- **Window 5 (8081 SDR Uno gain test, self-inflicted): `cycle_start_utc` in `[18:45Z, 19:30Z]` on
  2026-08-01 — exclude from any density/decode-yield analysis on 8081** for the same reason as
  Window 4: audio/archiving is clean and uncorrupted, but decode yield for this span reflects a
  deliberately degraded gain setting, not the instance's normal performance.
- **Window 6 (8080 decode collapse recurrence, real defect, autonomously restarted): `cycle_start_utc`
  in `[23:38Z, 2026-08-01]`–`[00:40Z, 2026-08-02]` — exclude from any density/decode-yield analysis
  on 8080** for the same reason as Window 4: audio/archiving is clean, but decode yield for this
  span is not representative of normal performance. The new instance (PID relaunched `00:39:57Z`,
  log `openswfz-20260802T003959Z.log`) confirmed clean and stable for 26 consecutive cycles
  (`01:09Z`–`13:12Z`) before Window 7 began.
- **Window 7 (8080 decode collapse, second recurrence, autonomously restarted, plus a follow-on
  supervisor heartbeat-stall restart on the first relaunch): `cycle_start_utc` in `[12:12Z, 13:50Z]`
  on 2026-08-02 — exclude from any density/decode-yield analysis on 8080** for the same reason as
  Windows 4 and 6, extended to cover the short-lived intermediate instance
  (`openswfz-20260802T134348Z.log`, `13:44Z`–`13:45Z`, killed by the supervisor's own heartbeat-stall
  watchdog). The instance now running (PID relaunched `13:50:24Z`, log
  `openswfz-20260802T135024Z.log`) is pending confirmation over the next 1-2 cycles before being
  treated as clean.
