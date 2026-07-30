# D-001: QA → Architect — cross-band corpus replication + a capture-chain measurement
# New evidence since the 2026-07-27 closing handoff. Not a reopening of the diagnostic
# programme under §0 of that handoff — this is analysis of corpus data gathered for
# other reasons (HK-020 cross-band gathering), plus one Captain-directed live measurement.

**Author:** QA, 2026-07-30 (22:21 UTC, `date -u`, per HK-017).
**For:** Architect (to fold into the row 4 decomposition owed per the closing handoff §8),
and the Captain.
**Supersedes nothing** — this is additive to `2026-07-27-2012-architect-to-qa-d001-closing-
handoff.md`, which remains the standing reference for programme state, stop rules, and the
menu decision. Read that document first if you haven't already.
**Authorisation:** the closing handoff's §0 stop rule forbids QA from opening new diagnostic
arms unilaterally. Nothing below is a new arm QA initiated. §1–§2 is analysis of endurance
corpus data gathered for HK-020 cross-band-replication purposes (unattended overnight runs,
2026-07-28→30), read after the fact per HK-018. §3–§4 is a specific live measurement the
Captain directed today, in this session, in response to §1–§2's findings — an explicit,
in-the-moment reopening of exactly the kind §0 anticipates, not a QA-initiated escalation.

---

## 0. Summary — the one thing to read if you read nothing else

Four to five days of unattended cross-band endurance corpus gathering (10m/20m/40m/80m,
hours-to-24h each) — originally run for HK-020 reasons, not for D-001 — turn out to bear
directly on this study. Two findings:

1. **The 64.1% parity figure that anchors the whole B.3 menu came from one band, one 21-
   minute corpus.** Across five new corpora spanning four bands, parity (OpenWSFZ decodes ÷
   reference-decoder decodes) ranges from **49.9% to 91.6%** — a >40-point spread, tracking
   decode density (busier bands parity worse) far more than anything the original corpus
   could have shown.
2. **A real, but secondary, capture-chain effect exists independent of decoder algorithm.**
   On a matched 30-cycle sample where both OpenWSFZ and WSJT-X independently recorded the
   same physical radio feed, WSJT-X's own recording of a given instant is measurably easier
   to decode than OpenWSFZ's recording of the identical instant — for **either** decoder, by
   ~10–13%. The decoder-algorithm gap (~48–51%) remains 4–5× larger and is the dominant
   factor; the capture-chain effect does not explain it away, but it is real, consistent in
   direction, and previously unquantified. One candidate mechanism (differential L/R audio
   requiring left-channel extraction) was tested directly and **ruled out** — it doesn't
   apply to this hardware. The resample-algorithm step (48 kHz→12 kHz) remains the one
   standing, unresolved candidate; QA has not pursued it further (§5).

Neither finding invalidates any corpus gathered. Both are additive information for the row 4
decomposition.

## 1. Cross-band parity — the menu's anchor number was one point on a wide distribution

`2026-06-07`→`2026-07-26` work priced row 4 against a single corpus: **live WSJT-X GUI =
2028; our decoder offline = 1300 (64.1% parity; NFR-018 target ≥80%); miss population =
789.** The B.1b second-corpus replication (a different 20m session) supported the *shape* of
the menu but was one additional data point, not a systematic band survey.

Since then, `qa/endurance/` has accumulated genuinely systematic cross-band data — unattended
overnight sessions run for HK-020 reasons (checking whether band choice affects anything at
all), each with a full matched-decode ANOVA report already committed:

| Corpus | Band | Span | Reference decoder | Parity (OpenWSFZ ÷ reference) |
|---|---|---:|---|---:|
| Original B.1/B.2 study | unstated, single | ~21 min | live WSJT-X | 64.1% |
| `qa/endurance/2026-07-29-489135a/anova_report_40m.md` | 40m | 3,575 cycles | jt9 (re-decode) | 62.5% |
| `qa/endurance/2026-07-29-5016363/anova_report_40m.md` | 40m | ~24h continuous | live WSJT-X | **49.9%** |
| `qa/endurance/2026-07-29-5016363/anova_report_20m.md` | 20m | 1,362 cycles | jt9 (re-decode) | **53.2%** |
| `qa/endurance/2026-07-29-5016363/anova_report_10m.md` | 10m | 1,490 cycles | jt9 (re-decode) | 77.7% |
| `qa/endurance/2026-07-29-5016363/anova_report_80m.md` | 80m | 2,917 cycles, partly contaminated (see `CONTAMINATION-NOTE.md` same dir) | jt9 (re-decode) | **91.6%** |

Parity tracks decode **density** (reference-decoder decodes per cycle) closely: 80m (~3.4/
cycle, sparse) parities best; 20m/40m (~19–36/cycle, dense) parity worst, around half. This is
the same axis as the co-channel/candidate-competition mechanism the closing handoff recorded
as **"not supported; bet withdrawn"** (§2.2 of that document) — but that verdict rested on an
in-corpus density *proxy* with a narrow spread (p90/p10 ≈ 1.6–1.8) that failed to replicate on
a second corpus. This is an out-of-band test with roughly a 10× density range, pointing the
same direction with a much larger effect. **QA is not re-opening that mechanism as an arm** —
flagging that the withdrawal rested on a low-power test, and this higher-power replication
disagrees with it, is Architect territory to weigh.

**Caveats, stated plainly:** the two 40m corpora aren't apples-to-apples with each other (one
is a jt9 re-decode, the other is against live WSJT-X's own clock-synced ALL.TXT, which carries
its own PC-clock-drift exposure a jt9 re-decode doesn't). The 80m corpus carries confirmed
intermittent audio-leak contamination (~60% of one window; see the contamination note) — it
does not appear to have moved the parity number off-trend, but it isn't a fully clean sample.

## 2. A second, independent signature — DT-offset sign tracks capture hardware, not band

Every ANOVA report tabulates the DT (time-offset) appraiser means. Split by which physical
instance produced the corpus:

- **SDR Uno / Voicemeeter B1 instance** (one instance, retuned 20m→80m→10m→20m): OpenWSFZ
  trails the reference decoder by **+0.650 s (10m), +0.654 s (20m), +0.668 s (80m)** — same
  sign, tight magnitude, across three unrelated bands and propagation conditions.
- **Physical-radio / USB Audio CODEC instance** (40m, both corpora): OpenWSFZ *leads* the
  reference decoder by **−0.273 s (vs jt9)** and **−0.641 s (vs live WSJT-X)** — opposite
  sign both times, though the two 40m magnitudes disagree with each other (plausibly the
  live-WSJT-X-clock-drift confound noted above).

The **sign** of the discrepancy tracks capture hardware, not band. This was the observation
that prompted the Captain to direct §3–§4 below — a legitimate, testable signature of the
closing handoff's still-open candidate mechanism: *"something in our own capture/processing
chain ahead of the decoder"* (§2.3 of that document, one of three named-but-never-measured
candidates).

## 3. The capture-chain measurement — a matched 2×2, on real audio

**Design:** 30 matched-timestamp cycles from the 24h 40m endurance session (`artefacts/
20260729_live_run_1831-8080`), where OpenWSFZ's `cycleAudioArchive` and WSJT-X's own `save/`
directory independently recorded the **same physical radio feed** (`Microphone (2- USB Audio
CODEC)`) throughout. Sample: `260730_064015` → `260730_064730` (30 consecutive matched
stems), copied to `artefacts/d001_wav_source_cross_decode_2026-07-30/` (git-ignored, NFR-021 —
contains real off-air message text).

Each WAV set was decoded by **both** decoders:
- **jt9** (`D:\WSJT\wsjtx\bin\jt9.exe -8 -d 3`, the same depth the endurance ANOVA scripts use).
- **OpenWSFZ's own decoder**, offline, via `qa/rr-study/d001-param-sweep-2026-07-22/`
  (drives the real production `Ft8Decoder` in-process, baseline grid point `k10_c0.10_n60`).
  Built off current `main` HEAD (`2e36c2e`); confirmed **no `src/` changes** between the live
  run's build (`5016363`) and HEAD, so this is decoder-identical to what produced the live
  corpus, not an approximation.

**Determinism sanity check first:** the offline harness reproduced 327 of the live session's
328 `ALL.TXT` lines for these exact 30 cycles — the harness is a faithful stand-in for the
live decode path.

**Result (unique (cycle, normalised-message) pairs, matching the ANOVA scripts' own
methodology):**

| | OpenWSFZ's own WAV | WSJT-X's own WAV |
|---|---:|---:|
| **OpenWSFZ decoder** | 327 (a) | 368 (b) |
| **jt9 decoder** | 495 (c) | 544 (d) |

**Decomposition:**
- **Decoder-algorithm effect** (same WAV source): jt9 beats OpenWSFZ by **+51.4%** on
  OpenWSFZ's own recording (495 vs 327), **+47.8%** on WSJT-X's recording (544 vs 368).
  Large, and essentially constant regardless of whose audio it's fed.
- **Capture-chain/WAV-source effect** (same decoder): WSJT-X's recording yields **+12.5%**
  more decodes than OpenWSFZ's recording of the identical instant, fed to OpenWSFZ's decoder
  (368 vs 327); **+9.9%** more fed to jt9 (544 vs 495). Real, consistent in direction both
  times, a minority effect.
- The two effects combine close to multiplicatively, not confounding one another: 1.125 ×
  1.478 ≈ 1.663, against the observed combined ratio 544/327 = 1.663 exactly.

**Caveat:** n=30 cycles, one contiguous ~7-minute slice near the end of a 24h session. Enough
to see the pattern and its direction clearly; not enough to pin the percentages down
precisely. A wider/multi-window sample would tighten this if it's worth the cost.

## 4. Chasing the mechanism one step, then stopping per the Captain's direction

Two candidate mechanisms for the capture-chain effect were live: differential/channel
handling, and the resample step. Only the first was tested.

**WSJT-X's own Audio settings, captured live (screenshot, unchanged since the session ran):**
`Input: Microphone (2- USB Audio CODEC)`, explicitly set to **Mono** — the identical Windows
device OpenWSFZ opened (confirmed via `WasapiAudioSource.cs`'s own log line:
`WASAPI device opened: ... 'Microphone (2- USB Audio CODEC )' — 48000 Hz, 32-bit, 2 ch`). Same
hardware, no splitter, no separate interface — but two different format negotiations against
it: WSJT-X requests mono directly; OpenWSFZ takes the device's default shared-mode stereo mix
format and does its own left-channel extraction + `WdlResamplingSampleProvider` resample
(48 kHz→12 kHz) afterward, entirely in managed code.

`WasapiAudioSource.cs`'s "D6" comment justifies the left-channel-only extraction by asserting
this device delivers a **differential signal (L = −R)**, and that averaging would produce
silence. This was measured directly today, not merely re-read:

- Built a standalone, throwaway tool (`qa/audio-capture-lr-phase-check/` — not part of
  `OpenWSFZ.slnx`, no `src/` dependency, dumps raw WASAPI stereo PCM with **zero** processing:
  no channel extraction, no resample, no decode).
- Captured 8 s live off `Microphone (2- USB Audio CODEC)` with the radio connected and
  receiving (`artefacts/lr_phase_check/raw_stereo.wav`, git-ignored).
- **Result: L and R are sample-for-sample identical.** `corr(L,R) = 1.000000`,
  `RMS(L−R) = 0.000000000`. Not differential. Both channels carry the same mono feed,
  duplicated.

**Consequence:** the D6 comment's stated justification does not match measured hardware
behaviour, at least as currently wired. This is **harmless in practice** — when L=R exactly,
"take the left channel" and "average L+R" produce identical output, so there is no live bug
and no data-quality consequence from this specific step. But the comment is factually wrong
and should not be trusted as future documentation. **This also rules out channel-handling as
a candidate for §3's capture-chain effect** — whichever channel-combining method either app
uses, the input to it is provably the same signal on both sides.

**What remains, unresolved, and not pursued further by QA today:** the resample-algorithm
step. We know our own (`WdlResamplingSampleProvider`, NAudio's windowed-sinc decimator). We do
not know WSJT-X's — different resampler, different filter design, or Windows' own per-client
audio-engine format conversion happening before either app sees samples, are all live and
indistinguishable from data on disk. Resolving it would require either reading WSJT-X's own
source or constructing a synthetic-test-tone comparison through our own resampler in
isolation. **QA is explicitly not doing either without direction** — per the Captain's own
steer today, matching the closing handoff's cost-discipline: the remaining question refines
the size of an already-bounded, already-secondary effect (~10–13%), not the dominant one
(~48–51%), and this project has an expensive, recent lesson about exactly this kind of
marginal-yield chase.

## 5. Recommendations

1. **Fold the capture-chain effect into the row 4 decomposition** (owed per the closing
   handoff §8) as a small, real, measured, previously-unquantified contributor — distinct
   from, and much smaller than, the decoder-algorithm gap that remains row 4's primary
   target.
2. **Re-weigh the withdrawn co-channel/density mechanism** (§2.2 of the closing handoff)
   against §1's cross-band replication before treating that withdrawal as final — the
   original test was low-power; this one isn't, and it disagrees.
3. **The 64.1%/789-message figures should be presented as one sample from a wide
   distribution (49.9%–91.6% measured so far), not a stable target**, wherever they're next
   cited to the Captain.
4. **File a trivial, low-priority dev-task correcting or re-verifying the D6 comment** in
   `WasapiAudioSource.cs` (QA will author it, per HK-015/HK-011 — a `src/` comment edit still
   routes through a Developer session). Not urgent; currently harmless.
5. **Do not authorise further chasing of the resample-algorithm question** unless the
   Captain judges the ~10–13% effect worth the cost of resolving precisely — it does not
   change the row 4 vs row 1 vs row 5 decision on its own.

## 6. What this does NOT do

- Does not reopen the diagnostic programme under §0 of the closing handoff as a standing
  QA-initiated effort — everything above was either after-the-fact analysis of corpus data
  gathered for other reasons, or a single Captain-directed measurement, not a new arm QA
  chose to run.
- Does not invalidate any of the four to five endurance corpora gathered 2026-07-28→30. Every
  finding here is additive interpretation, not a defect in the data. Confirmed explicitly with
  the Captain this session.
- Does not change the menu decision (row 1 vs row 4 vs row 5) — that remains the Captain's,
  informed by whatever the Architect makes of §1–§4 above.

## 7. Cross-references

- `2026-07-27-2012-architect-to-qa-d001-closing-handoff.md` — standing reference this note is
  additive to.
- `2026-07-26-2359-architect-b3-costed-menu.md`, `2026-07-27-1730-architect-row4-scoping-
  design.md` — the menu and row 4 scoping this note's findings feed into.
- `qa/endurance/2026-07-29-5016363/` (10m/20m/40m/80m ANOVA reports + `CONTAMINATION-NOTE.md`),
  `qa/endurance/2026-07-29-489135a/` (40m + 20m-no-audio) — source data for §1–§2.
- `artefacts/20260729_live_run_1831-8080/contents.md` — the 40m dual-app session §3 sampled
  from.
- `artefacts/d001_wav_source_cross_decode_2026-07-30/` (git-ignored) — §3's raw WAVs/decode
  outputs.
- `qa/audio-capture-lr-phase-check/` — the standalone L/R measurement tool (§4); `artefacts/
  lr_phase_check/raw_stereo.wav` (git-ignored) — its raw capture.
- `src/OpenWSFZ.Audio/WasapiAudioSource.cs` — "D6" comment (§4), current capture pipeline.

---

*Per HK-015 this is QA → Architect material. Per HK-014/HK-010 this note is committed locally
and goes no further; no push, no merge implied. Per HK-011 nothing here touches `src/` — the
D6 comment fix is a recommendation for a future dev-task, not applied. Per HK-006 no
`pre_merge_check.py` run is implied. The row 4 vs row 1 vs row 5 decision remains the
Captain's.*
