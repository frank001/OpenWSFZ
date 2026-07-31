# 2026-07-28 session log — full narrative

**Why this document exists**: this session covered a lot of ground beyond the corpus itself — a
crash diagnosis, a multi-hour QRM investigation, a second receiver built live, a protocol bug
found and partly fixed, and a tool idea proposed, refined twice, and correctly scrapped. Most of
that lived only in conversation or scattered across `artefacts/` (git-ignored, not durable) and
brief mentions in `report.md`. This is the complete, chronological account, written so none of it
gets lost. Cross-references: `artefacts/20260728_live_run_1319/report.md` (the terser
after-action summary), `artefacts/20260728_live_run_1319/screenshots/NOTES.md` (the interference
investigation's own working notes), `anova_report_10m.md`/`anova_report_20m.md` (this directory).

**A note on redaction (added 2026-07-31, before first commit):** the original narrative named
real third-party amateur callsigns directly — decoded stations encountered during the QRM
investigation and the propagation narration. Per NFR-021 (only Q-prefix synthetic callsigns, plus
`PD2FZ` and public figures, may appear in version control), every real callsign below has been
replaced with a consistent Q-prefix synthetic call (one call per station, used at every occurrence
of that station). `PD2FZ` and the already-synthetic `Q1OFZ` were untouched. This document was
edited in place — no separately preserved unredacted copy of this narrative exists on disk — but
the raw decode logs it was written from (`artefacts/20260728_live_run_1319/owsfz/ALL.TXT` and
`.../wsjt-x/ALL.TXT`, both git-ignored, never committed) still carry every real callsign named
below, so the ground truth is not lost, only kept out of version control.

---

## 1. Opening: "why did OpenWSFZ close?" — a crash, a false lead, and its real cause

The day started with the Captain clearing all WAVs/`ALL.TXT` and starting both applications for a
fresh 10m run. Early checks found `decodingEnabled: false` on the daemon — the Captain armed it
manually. Shortly after, the daemon vanished without either of us issuing a kill command.

**First investigation** (log inspection) found the actual cause: an unhandled
`NullReferenceException` in `CycleArchiveService.TryEnqueue` —
`_configStore.Current.CycleAudioArchive.Mode` dereferenced on a null `CycleAudioArchive`. The
persisted `config.json` had the literal value `"cycleAudioArchive": null`.

**Root cause, traced through the actual code** (not guessed): `JsonConfigStore.SaveAsync` only
re-applies the System.Text.Json "omitted key deserialises to null instead of the property
initialiser" guard for `Ptt`, not for `CycleAudioArchive` — and `WebApp.cs`'s `POST
/api/v1/config` handler's guard block (which re-defaults `Logging`/`DecodeLog`/
`DecodeNoiseSuppression`/`ExternalReporting`) had never been extended to cover
`CycleAudioArchive` either, since that section was added after the guard block was written. Since
there's no Settings-page UI field for `cycleAudioArchive` at all, *every* ordinary settings save
hits this path. `CycleArchiveService.TryEnqueue` and `ProcessItemAsync` both dereferenced the
section unconditionally, unlike `AllTxtWriter`/`ExternalReportingService.Reconcile`, which already
carried the equivalent defence-in-depth for this exact class of bug (D-010, an earlier incident).
This also explained a second symptom: the crash-and-restart cycle silently reset the archive mode
back to `Off` on every restart, because `Load()`'s own null-guard substitutes a fresh default
(`Mode = Off`) rather than preserving what was actually configured.

**A second, unrelated complication surfaced mid-diagnosis**: the daemon restarted itself twice
with nobody — Captain or QA — having issued a restart, including once immediately undoing a
deliberate `taskkill` meant to abort the session. Investigated via `Get-CimInstance
Win32_Process` searching for stray `bash.exe`/supervisor processes (rather than assuming it was
either of us): found `qa/endurance/2026-07-26-supervisor-80m.sh` (PID 19768) still running,
uninterrupted, since 22:47 the night of 2026-07-26 — over 36 hours, through an entirely separate
prior session, auto-restarting the daemon on every failure it saw per its own correctly-implemented
HK-013 design. Killed. This produced a new standing rule, **HK-019** (supervisor teardown +
orphan-check discipline), written to QA memory the same day.

**The fix**: three-layer guard (`WebApp.cs`, `JsonConfigStore.SaveAsync`, and defence-in-depth in
`CycleArchiveService` itself, mirroring the `AllTxtWriter` pattern), plus the same one-line fix
for the analogous `RemoteAccess` gap (lower urgency, not an active crash). Handed off via
`dev-tasks/2026-07-28-fix-cycle-audio-archive-null-config-crash.md` (QA-authored, per HK-011),
implemented in a separate Developer session (commit `031fb37`), and code-reviewed directly: three
new regression tests reproducing the actual STJ quirk end-to-end, full test suites re-run clean
(91/91, 264/264, 588/588 across the three touched projects), single clean commit on top of
current `main`. Approved.

## 2. Fresh 10m run, on the fixed build

Published fresh from the fix branch (self-contained win-x64), launched with an isolated,
freshly-written `cycleAudioArchive` config (`mode: "all"`) confirmed via the running instance's
own `/api/v1/config`. Verified live: real decode within the first cycle, WAV files landing
correctly, no repeat crash. WSJT-X started in parallel by the Captain.

## 3. The QRM hunt

### 3.1 First sighting, first (wrong) guess

Mid-session, the Captain spotted an evenly-spaced comb pattern filling almost the entire 0–3000 Hz
waterfall passband on WSJT-X — visually nothing like normal FT8 traffic (which shows scattered,
irregular tone positions). Both the Captain and QA guessed **solar power converter PWM harmonics**
from the shape and midday timing alone, deliberately not retuning to check 11m directly so as not
to disturb the run.

### 3.2 A false-decode side-thread: `Q36IBD/P`

Comparing OpenWSFZ's and WSJT-X's `ALL.TXT`s for the same cycle (`112115`) found 4/5 messages
agreeing closely, with one differing catch each side. WSJT-X's unique catch (`Q2TND`) had a
plausible real-world callsign shape; OpenWSFZ's (`Q36IBD/P`) did not — no valid amateur prefix
scheme places two digits directly after a single leading letter, a classic signature of an
LDPC pass on noise rather than a genuine weak-signal recovery. Flagged as a likely false decode,
plausibly related to an interference-elevated near-threshold candidate population, not proof of a
decoder defect (later folded into `report.md` §4 and `NOTES.md`).

A related check (not fully resolved that evening, deferred): whether OpenWSFZ was genuinely
"outperforming" WSJT-X. Turned out most of the apparent lead was simply because WSJT-X's `ALL.TXT`
only started once the Captain restarted it (it hadn't been decoding earlier) — not a fair
same-window comparison for the earliest cycles.

### 3.3 Q3EAT: the "insane power" investigation

Extreme SNR readings (26–35 dB) for one specific station (`Q3EAT`, worked in turn by `Q4DNG`,
`Q5DGM`, `Q6DMA`) stood out against otherwise-normal-range DX in the same cycles. Cross-checked
against OpenWSFZ's own log: **both independent decoders** flagged the same one station as
anomalous (28/34/35 dB on our side vs. 26/32/32 on WSJT-X's) — strong evidence of a genuine
phenomenon, not a decoder-specific SNR-estimator quirk. A PSKReporter check for `Q3EAT` showed
236 transmitters heard across 90 countries in 24h, 2,846 reports — an exceptionally active,
widely-heard station. The Captain then found and read `Q3EAT`'s HamQTH bio directly (Spanish):
*"mi instalación de antenas está compuesta por directiva para 10-15-20m..."* — a directional beam
antenna on exactly the bands in question. Fully explained: strong signal + real beam gain, not a
bug or artefact.

**Terminology correction, twice**: QA initially attributed the Spain opening to "ducting" (a
tropospheric VHF/UHF phenomenon, not really applicable at 28 MHz); corrected to **Sporadic-E**,
the actual well-known 10m mechanism for exactly this signature (sudden, sustained, geographically
concentrated strong openings, in-season for Northern Hemisphere summer). Confirmed against the
live corpus: `Q7EBL`, `Q8ECA`, `Q9EGF`, `Q1EAZ` all running unusually strong and sustained for
30+ minutes.

### 3.4 "Should we wait it out or switch bands?" — and a corrected assumption

QA recommended continuing on 10m, initially reasoning from an assumed motivation ("a rare,
fleeting DX opening"). The Captain corrected this directly: the actual motivation was never about
catching a specific opening — this run (like the 2026-07-26/27 80m overnight run before it) is
part of a deliberate, systematic effort to gather cross-reference corpora from bands **other than
20m/40m**, to check whether band choice matters at all. QA had speculated about the Captain's
reasoning instead of asking. Under the corrected motivation, the interference itself became a
legitimate part of what the cross-band comparison was meant to surface, not a confound to avoid.

### 3.5 Characterising the interference properly

A longer waterfall capture (~6 minutes) let the comb's timing be characterised precisely: present
for ~45–60s, then clean for ~5 minutes, then back — a duty-cycle pattern, refining "on and off"
into an actual rough period.

### 3.6 Cross-antenna SDR investigation

The Captain brought up SDRuno on a separate SDR receiver — **sharing the same physical antenna**
via a pre-existing MFJ-1708B-SDR splitter (installed 2023, well before this project, so not a new
variable) — to look at a wider span without retuning the live run's own radio. A wide (2 MHz) span
(27.1–29.0 MHz) revealed several discrete, non-comb carriers, most notably a strong spike
initially marked at **27,535.729 kHz, -66.1 dB** — sitting ~130 kHz above the legal CB ceiling
(27.405 MHz), in "freeband"/"outband" territory known for illegal linear-amplifier operators,
particularly in parts of Europe.

A separate, unrelated tall spike was also found near **28,784.794 kHz** — inside 10m proper,
consistently present across every later check regardless of the freeband cluster's state.
Explicitly ruled *out* of the interference story (most likely ordinary band occupancy or a
receiver birdie, never confirmed either way).

### 3.7 Building the correlation, sample by sample

Over roughly 90 minutes, alternating SDRuno checks against WSJT-X's own comb-present/comb-absent
windows:

- **On, marked**: 27,535.729 kHz (-66.1 dB); 27,703.309 kHz (-91.1 dB); 27,634.003 kHz (-93.2 dB) —
  all landing within a ~170 kHz pocket, consistent with SSB voice energy shifting with modulation
  (or several nearby stations clustered together), not a fixed carrier.
- **On, weaker**: 27,464.000 kHz (-107.4 dBm, SNR 6.7 dB) — a much fainter reading, but consistent
  with catching a lull in real speech (SSB only carries energy during actual talking) rather than
  contradicting the pattern.
- **Off, baseline**: a clean SDRuno capture during a genuinely comb-absent WSJT-X window, showing
  no comparable elevated feature in the same region.

**Real audio confirmation**: the Captain got SDRuno's own audio working (after some Voicemeeter
audio-routing trouble) and demodulated actual **French voice** on ~27.51 MHz in AM mode,
confirmed intermittent ("comes and goes"). A later attempt during an active comb window, in USB
mode, produced only noise — plausibly a mode mismatch (AM demodulated as USB), or plausibly
genuine evidence of an overdriven, badly-modulated transmission strong enough to both splatter
into the front end *and* sound distorted rather than clean — left as an open, not fully resolved,
distinction.

**Local-source ruled out**: a standalone tinySA Ultra, on its own separate antenna (explicitly
*not* connected to the shared feed, to avoid any risk to the live run), showed nothing elevated
during an active comb-present window — evidence against a local/near-field noise source inside
the shack, pointing the source outward, over the air.

### 3.8 Final verdict

**Not solar power converters.** Five independent, converging lines of evidence — real audio
identification, consistent frequency clustering just above the legal CB ceiling, correlation with
the comb across multiple paired on/off checks, expected strength variance for real SSB voice, and
a local source explicitly ruled out — point to intermittent, strong French freeband/CB voice
traffic (illegal linear amplifier operation) overloading the receiver front end at ~540 kHz
remove, well outside the signal's own legitimate bandwidth. Not proven via one perfect
simultaneous capture, but well-supported. Full detail and the complete evidence trail:
`artefacts/20260728_live_run_1319/screenshots/NOTES.md`.

## 4. Two PSKReporter side-investigations

### 4.1 The gray "Unknown" band markers

The Captain noticed gray markers on PD2FZ's own PSKReporter map and, recalling the legend, was
concerned they might indicate genuine 11m (CB) activity from PD2FZ's own station. Investigated:
the Captain confirmed **zero transmissions** in the past 24 hours (pure receive), so any
emissions-safety concern was fully off the table immediately. The actual explanation, found by
reading `ExternalReportingService.cs`'s own code: the WSJT-X UDP protocol's `Decode` packets carry
only a *relative* frequency offset, never an absolute one — GridTracker must pair each `Decode`
with the most recently received `Status` packet (which does carry the real dial frequency) to
compute an absolute frequency for PSKReporter. An occasional pairing gap (a dropped UDP `Status`
packet, or a `Decode` arriving before the first `Status`) would explain a spot rendering as
"Unknown" band — a benign client-side timing artifact, not a defect in what OpenWSFZ sends.
Narrowing the PSKReporter view to the last 6 hours (i.e., just this session) showed **zero** gray
markers — confirming the gray ones were leftover history from *outside* this session (most likely
the prior night's 80m run), not a live defect.

### 4.2 The pink wedge/lens overlay

A separate, static, pie-slice-shaped translucent overlay appeared on PD2FZ's own PSKReporter map
across multiple screenshots spanning several hours. QA (twice) speculated it might be the
day/night grayline; the Captain twice corrected this ("duh, I know what the grey line is" — the
genuine grayline is the separate, real moving dark-shadow terminator visible in wider world-map
views). Worked out properly on request: the wedge's position was static across a 3+ hour span
(a real terminator would have visibly swept ~45° of longitude in that time) and had an apex
anchored exactly at PD2FZ's own station location, radiating outward in one compass sector — the
signature of a **point-source directional-antenna pattern**, not a globe-spanning terminator band.
Concluded: most likely PSKReporter rendering PD2FZ's own registered antenna heading/beamwidth,
echoing the same concept just confirmed for `Q3EAT`'s bio.

## 5. The dual-receiver build (10m + 20m simultaneously)

Building on the corrected cross-band-corpus motivation (§3.4), the Captain proposed routing
SDRuno's 20m-tuned output through Voicemeeter (`Voicemeeter Out B1`) into a **second, fully
isolated OpenWSFZ instance**. Set up carefully:

- Confirmed the exact Voicemeeter device via the running instance's own `/api/v1/audio/devices`
  endpoint rather than guessing a name.
- Built a dedicated config outside both the repo and `%APPDATA%` (deliberately, to avoid any
  collision with git-tracked files or the live 10m instance's real config): own port (8081), own
  `decodeLog.path`, own `cycleAudioArchive.directory`, `mode: "all"`.
- Launched from the same already-tested fixed-build exe. Verified immediately: real 20m decodes
  flowing, WAVs archiving correctly, main 10m instance and WSJT-X completely undisturbed
  throughout (confirmed via unchanged PIDs at every check).
- `tx.callsign` was left unconfigured initially, and the UI correctly showed the synthetic
  placeholder `Q1OFZ` rather than defaulting to the real callsign — confirmed as
  `TxConfig.Callsign`'s actual coded default (`"Q1OFZ"`), matching this project's NFR-021
  privacy policy working as designed on an unconfigured instance.

A screenshot of both instances' web UIs running side by side prompted a genuinely warm moment —
"there is something really satisfying about this" — worth recording as much as the technical
content: a splitter installed in 2023, an SDR mostly used for spectrum-watching, and existing
Voicemeeter routing, combined for a real second live corpus at negligible marginal cost.

## 6. External reporting and the `AppId` collision

The Captain initially approved of the 20m instance *not* reporting to GridTracker/PSKReporter
(`externalReporting.enabled: false`, deliberately set that way when the instance was built). On
reflection, the Captain pushed back correctly: there's nothing wrong with reporting *genuine*
reception — that's literally what PSKReporter is for, and a station running multiple bands
simultaneously under one callsign is completely normal. QA's original "avoid polluting the network
with test data" framing was wrong; the actual valid reason was narrower — the instance would have
reported under the synthetic `Q1OFZ` placeholder, not the real callsign, which genuinely would
have been misleading. Fixed properly: fetched the instance's full current config, set
`tx.callsign = "PD2FZ"` / `tx.grid = "JO33"`, enabled `externalReporting` targeting the same local
GridTracker as the main instance — done via a full GET-then-POST round-trip (not a partial body),
deliberately following the exact discipline learned the hard way in §1.

**Symptom**: shortly after, GridTracker's live view began clearing itself every ~15 seconds (one
FT8 cycle). **Root-caused directly in code**: `ExternalReportingService.cs`'s WSJT-X-protocol
`AppId` is a hardcoded `const string "OpenWSFZ"` — identical across every running instance, with
no config override. Both simultaneous instances broadcasting under the literal same identity meant
GridTracker couldn't distinguish them, most plausibly seeing what looked like one instance whose
dial frequency kept jumping between bands.

The Captain initially accepted this as a cosmetic nuisance not worth fixing tonight, and asked for
a dev-task capturing the proper fix (a configurable `InstanceId` field on `ExternalReportingConfig`,
following the exact same STJ-omitted-key-guard discipline as §1's fix — written into
`dev-tasks/2026-07-28-fix-external-reporting-appid-collision.md`). Later, the Captain checked
PSKReporter directly and found the 20m instance's spots **were not arriving there at all** — the
collision breaks actual downstream delivery, not just GridTracker's local display. External
reporting was disabled again on the 20m instance for the rest of the session, and the dev-task was
updated to reflect the confirmed (not merely cosmetic) impact — raising its priority.

## 7. The third-receiver idea: proposed, refined twice, correctly scrapped

While exploring adding a *third* simultaneous receiver, the Captain hit real friction — juggling
another application's audio settings alongside SDRuno's own routing got confusing enough to stop
rather than risk the live run. This prompted a genuinely useful design conversation with three
distinct iterations:

1. **QA's first idea (over-scoped, rejected)**: eliminate SDRuno/Voicemeeter entirely and build
   direct SDR-hardware access plus software channelization into OpenWSFZ itself. The Captain
   rejected this directly — keep Voicemeeter, don't fold SDR access into OpenWSFZ, "just a simple
   application" that routes audio.
2. **QA's second idea (under-scoped, also wrong)**: a small standalone audio *router* — one input,
   manually selected to one of several labeled outputs, no hardware access at all. Written up as
   `dev-tasks/2026-07-28-band-audio-router-tool-idea.md`. The Captain corrected this too: what was
   actually wanted was a lightweight replacement for SDRuno's own core function — tuning and
   demodulating an SDR directly — run as multiple simple instances, one per band.
3. **The real constraint, checked rather than assumed**: before writing a third spec, QA
   researched whether multiple processes can independently drive the same physical SDR hardware
   simultaneously. From the SDRuno screenshots' own UI (three switchable antenna ports — ANT A/B/C
   — rather than two independent receive chains), the Captain's unit appears to be a
   **single-tuner** device (RSPdx-shaped, not the dual-tuner RSPduo). A single-tuner SDR can only
   be centred on one frequency, with one instantaneous bandwidth window, at any moment — typically
   exclusively owned by one process. "Multiple simple instances independently tuning the same
   hardware" therefore cannot work as described; the real options are either a genuine
   channelizer (if the desired bands fit within one ~10 MHz tuning window) or **separate physical
   SDR hardware** per far-apart band (10m + 20m, tonight's actual case, is far too wide for any
   single tuner). Presented clearly, with a request to confirm the actual hardware before writing
   anything further.

The Captain's response: **"that's enough. scrap the whole idea."** The spec file was deleted
cleanly rather than left as stale, incorrect documentation. Recorded here so the reasoning (and
why it was rejected) isn't lost even though the artefact itself is gone — a genuine hardware
constraint, correctly identified before any implementation effort was wasted on it.

## 8. Band-condition narration, threaded through the evening

Several live cross-checks against the running corpus, not just PSKReporter's own map, confirmed
real propagation events as they happened:

- **10m fading, 20m opening** ("10m seems to be dying, 20m is on fire") — confirmed via decode
  density (3 decodes/cycle on 10m vs. 18 decodes in one 20m cycle alone, genuinely global:
  `Q2VRV` Hong Kong, `Q3BDA`/`Q4BIJ` China, `Q6NJF` Kenya, `Q7RAJ` Russia, `Q8JAJ` Japan) and
  raw line-count totals (20m's `ALL.TXT` overtook 10m's within about three hours of being added,
  despite starting more than an hour later).
- **A genuine South America opening** during the later grayline-approach window — `Q9PYM`,
  `Q1PYV`, `Q2PUY`, `Q3CXA`, `Q4LUT`, `Q5LUA` all worked into Europe at consistently deep
  negative SNR (-16 to -29 dB), matching expected long-path F2 propagation, cross-checked directly
  against both `ALL.TXT` and PSKReporter's map.
- **Grayline genuinely encroaching** toward the Captain's own longitude by the session's later
  stages, correctly distinguished (§4.2) from the unrelated static antenna-pattern overlay on the
  same maps.

## 9. Session close: stop, gather, and a process gap caught and fixed

At the Captain's instruction, all three processes (10m OpenWSFZ, WSJT-X, 20m OpenWSFZ) were
stopped cleanly — no crashes, no orphaned processes (checked explicitly this time, per §1's HK-019
lesson).

**First gather attempt was a genuine miss**: QA built an ad-hoc artefact directory structure
(`10m/`/`20m/` subfolders, `README.md`, `report.md`) from scratch instead of using the
established, already-committed `tools/gather_live_run_artefacts.py`, which encodes the actual
agreed convention (no band names in any path — bands are a run *parameter*, not identity;
`contents.md`/`.html`, not `README.md`; auto-rendered HTML companion). Caught only when the
Captain asked **"where is the ANOVA report?"**, which led to discovering that the established
`qa/endurance/endurance_anova.py` tool — built specifically for this purpose, per the Captain's
own 2026-07-27 standing instruction that every endurance session gets this treatment — lived on
`d001-c4-min-score-sweep`, a branch QA had not had checked out all evening (having worked from
`fix-cycle-audio-archive-null-config-crash`, forked off `main`, since §1).

**Corrected properly**: switched to the branch holding the tooling, read both scripts fully rather
than guessing at their interfaces, then re-ran the *real* gather tool twice — once for 10m
(reusing the existing folder identity, since its start time already matched) and once for 20m as
its own genuinely separate "live run" folder (correct per the tool's own convention, since 20m had
no WSJT-X pairing and started at a different time). Verified line/WAV counts matched exactly
before deleting the superseded ad-hoc structure. Two further inaccuracies were caught and
hand-corrected while filling in the mechanical `contents.md` files: the auto-captured "build under
test" reflected the tooling-access branch, not the branch that actually ran the session; and 20m's
device metadata leaked in from the 10m instance's config because an `OPENWSFZ_CONFIG` environment
variable set via `export` in one shell call didn't survive into a separate subsequent shell call.

**The ANOVA reports themselves** (`anova_report_10m.md`, `anova_report_20m.md`, this directory):
each band's own `cycleAudioArchive` WAV archive was independently re-decoded by `jt9` (WSJT-X's
own CLI decoder — no dependency on the live WSJT-X GUI instance, which is why this worked for 20m
too, despite no WSJT-X ever having run on that band) and matched against OpenWSFZ's `ALL.TXT` by
cycle and normalised message text. Headline numbers: jt9 out-decoded OpenWSFZ by ~30% on 10m
(8,390 vs. 6,480) and by roughly double on 20m (50,953 vs. 25,512) — consistent with this being
the plain `main` baseline decoder, not the D-001 tuning branch. SNR means differed by ~14.8 dB on
10m and ~6.25 dB on 20m between the two decoders — a real, measured, unexplained cross-band
difference, explicitly left as Architect/Captain territory to interpret, not concluded here.
Frequency-offset differences were statistically significant on both bands (large sample sizes)
but practically negligible (≤0.1 Hz) — flagged as a clean statistical-vs-practical-significance
example, not a real disagreement.

## 10. What's left open

- `dev-tasks/2026-07-28-fix-external-reporting-appid-collision.md` — confirmed real (not
  cosmetic) impact, scoped, not yet implemented.
- `dev-tasks/2026-07-28-fix-cycle-audio-archive-null-config-crash.md` — implemented, tested,
  reviewed, done.
- The third-receiver idea (§7) — deliberately scrapped, not pursued further; this document is now
  its only remaining record.
- `qa/endurance/2026-07-28-supervisor-10m.sh` — written early in the session as a precaution, never
  actually armed/used (the crash-and-orphan saga in §1 made it moot before it was needed); left in
  place, harmless.
- HK-019 (QA memory) — new standing rule from §1's orphaned-supervisor discovery, now permanent
  across sessions.
- The AM-vs-USB "just noise" question from §3.7 — left genuinely unresolved, not just deferred:
  could be mode mismatch or could be a real overdriven signal; worth resolving if the interference
  question is ever revisited.
