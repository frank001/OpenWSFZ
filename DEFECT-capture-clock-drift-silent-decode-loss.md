# Defect: Capture Clock Drift — Silent, Total Decode Loss After ~13 Hours

**Raised by:** Architect, 2026-07-30 (23:15 UTC, `date -u`, per HK-017)
**Severity:** **Critical** — on affected capture hardware the application silently stops
decoding after ~13 hours of continuous operation and never recovers, while reporting healthy
on every existing health signal. All unattended runs longer than ~12 hours on that hardware
produce partly or wholly invalid data.
**Affects:** the capture/framing path — `src/OpenWSFZ.Audio/WasapiAudioSource.cs`,
`src/OpenWSFZ.Ft8/CycleFramer.cs` (exact locus not yet established, see §7).
**Found:** incidentally, while validating whether two recorders' WAV files were comparable for
a D-001 cross-decode study. Not found by any test, gate, or supervisor.

---

## 1. What is wrong

OpenWSFZ's capture window drifts monotonically relative to UTC at approximately **45–49 ppm**
(~0.17 s per hour) on the physical-radio capture device. WSJT-X, listening to the **identical
audio feed on the same machine**, shows no drift at all.

The drift is harmless until it exceeds the decoder's DT search tolerance at roughly **2.4
seconds**, at which point decoding collapses almost completely. At the measured drift rate that
threshold is reached about **13 hours** into a session.

There is no error, no warning, and no health-flag change when it happens.

## 2. Evidence

Three independent measurements agree. Source session:
`artefacts/20260729_live_run_1831-8080` (40m, 25 h continuous, physical radio via
`Microphone (2- USB Audio CODEC)`, OpenWSFZ and the real WSJT-X application recording and
decoding the same feed simultaneously).

### 2.1 Raw audio — direct cross-correlation of the two recorders' WAVs

Both applications archive their own WAV per cycle, identical format (12 kHz, mono, 16-bit,
exactly 180 000 frames). Cross-correlating matched cycle stems (lag convention validated
against a synthetic control first; correlation at nominal alignment is ~0.005 throughout,
confirming the files are genuinely offset and not merely noisy):

| cycle stem (UTC) | peak correlation | measured lag |
|---|---:|---:|
| `260729_220000` | 0.94 | **−0.812 s** |
| `260730_000000` | 0.86 | **−1.182 s** |
| `260730_064015` | 0.84 | **−2.342 s** |
| `260730_120000` | 0.75 | **−3.282 s** |
| `260730_180000` | 0.67 | **−4.322 s** |

Negative lag = OpenWSFZ's capture window starts **later** in absolute time than WSJT-X's, so a
given real-world event appears earlier within our file. Rate: **−0.171 s/h ≈ 47.6 ppm.**

### 2.2 Decode metadata — the reported DT ramp

The drift is equally visible in live `ALL.TXT` output, which is decoder output rather than
archive content — so this is the **live decode path**, not merely the archive writer:

| | our mean DT | reference mean DT |
|---|---|---|
| session start (18:00 UTC) | **+0.588 s** | +0.194 s |
| 12 h later (06:00 UTC) | **−1.362 s** | +0.184 s |
| session end (18:00 UTC) | (post-collapse, unreliable) | +0.197 s |

Ours ramps by −1.95 s over 12 h (**−163 ms/h ≈ 45 ppm**). **WSJT-X's stays flat to within
15 ms across the full 25 hours.**

> The decode-derived rate (45 ppm) is slightly lower than the raw-audio rate (47.6 ppm) because
> reported DT suffers survivorship bias — the most badly-offset signals fail to decode and never
> enter the mean. The two agreeing in this direction, and by this margin, is a consistency check
> rather than a discrepancy.

### 2.3 The dose–response, and the cliff

Measured drift against hourly parity (our decodes ÷ WSJT-X's decodes, same feed, same hour):

| hour (UTC) | drift | ours | WSJT-X | parity |
|---|---:|---:|---:|---:|
| 18–06 *(13 h)* | −0.25 → −2.34 s | ~3 000–5 100/h | ~4 300–8 500/h | **58–75%, flat** |
| **07** | **−2.48 s** | 1 394 | 3 755 | **37.1%** |
| **08** | **−2.67 s** | 344 | 2 988 | **11.5%** |
| 09 | −2.84 s | 104 | 1 954 | 5.3% |
| 12 | −3.36 s | 10 | 890 | **1.1%** |
| 18 | −4.36 s | 75 | 5 407 | 1.4% |

**Parity is completely flat out to −2.34 s, then falls off a cliff between −2.34 s and −2.48 s.**
This is the signature of a bounded DT search window in the decoder: once the entire capture
window slips outside the candidate search range, nothing is found. WSJT-X continued decoding
1 000–6 000 messages/hour throughout.

### 2.4 It is device-dependent, and it reproduces

| session | instance / device | drift | outcome |
|---|---|---:|---|
| `20260729_live_run_1831-8080` (40m) | **USB Audio CODEC** (physical radio) | **−45 ppm** | collapse at ~13 h |
| `20260728_live_run_2354-8080` (40m) | **USB Audio CODEC** (physical radio) | **−44 ppm** | same ramp, +0.78 → −1.45 s over 14 h; counts 5 184/h → 536/h |
| `20260728_live_run_2354-8081` (20m) | **Voicemeeter B1** (SDR Uno) | **~0** | DT flat +1.18 → +1.03 over 13 h; no collapse |
| `20260729_live_run_1831-8081` (10m/20m/80m) | **Voicemeeter B1** (SDR Uno) | **~0** | stable parity throughout |

**Two independent sessions on the physical-radio device drift and degrade. The virtual-audio
device does not drift at all.**

The Voicemeeter virtual device is software-clocked off the system clock and therefore cannot
drift against it. The USB CODEC has its own crystal. This is consistent with the capture path
free-running on the audio device's sample clock without re-synchronising cycle boundaries to
UTC — **a hypothesis consistent with all four sessions, but not yet directly verified in code**
(§7).

## 3. Why nobody noticed — the failure is invisible

This is arguably as serious as the drift itself.

- **Zero `[WRN]`, `[ERR]` or `[FTL]` lines in the entire 25-hour session** — 207 498 log lines,
  all `[INF]` or `[DBG]`.
- **The heartbeat reported perfect health continuously**, including through all 12 broken hours:
  ```
  Heartbeat: captureActive=true, audioActive=true, dataFlowing=true
  ```
  720 such lines per hour, every hour, flipping to `false` only at deliberate shutdown. Audio
  genuinely *was* flowing — the drift means it is framed against the wrong window, not absent.
- **HK-013's unattended-run supervisor cannot catch this.** It triggers on `ERR`/`FTL`/hang.
  None occur. The process is alive, logging at ~9 000 lines/hour, and reporting healthy while
  decoding roughly 1% of what it should.

**An unattended overnight run therefore looks completely successful and produces garbage for
half its duration.** Every existing signal — process liveness, log level, heartbeat flags,
supervisor triggers — is blind to it.

## 4. Impact

1. **Product:** continuous operation on the physical radio is limited to ~12 hours before
   decoding silently ceases. A restart resets the accumulated drift, which is why shorter
   sessions have never shown it.
2. **Reporting:** during the degraded period the application continues to run, log, and report
   normally while contributing almost nothing — and whatever it does report carries DT values
   offset by seconds.
3. **Study data:** any corpus gathered on the affected device over more than ~12 hours is partly
   invalid. Specifically:
   - `qa/endurance/2026-07-29-5016363/anova_report_40m.md`'s **49.9% parity is not a decoder
     measurement.** It averages ~13 h at ~65% with ~12 h of a broken application at ~2%. It must
     not be cited (see the D-001 ruling's §9).
   - `qa/endurance/2026-07-29-489135a/anova_report_40m.md`'s **62.4% is depressed by the same
     mechanism** over its final hours and needs recomputing on its drift-free window.
   - The 10m/20m/80m corpora are on the **unaffected** device and appear sound.
4. **Study conclusions:** the "capture-chain effect" reported in
   `qa/cycleframer-alignment-replay/2026-07-30-2221-qa-to-architect-…-findings.md` §3 was
   measured on a 30-cycle sample at `260730_064015` — **2.34 s of drift**, at the very edge of
   the cliff. That result is confounded and cannot be read as an audio-quality comparison.

## 5. Relationship to prior work

- **`fix-cycle-boundary-clock-drift`** (PR #108, three fix rounds, all "defeated by live
  testing", ultimately paused and set aside 2026-07-25 when the LDPC-saturation mechanism was
  found). **The drift it was chasing is real and is still present.** What that work correctly
  concluded is that timing was not the explanation for D-001's *parity gap* — and that remains
  true: parity is ~65% from hour one, long before any meaningful drift accumulates. **Both
  statements hold.** This defect does not reopen D-001; it is a separate failure that was
  co-located with it.
- **D-003/D-004** (`fix-d004-local-noise-floor`) also arose from this same USB CODEC audio
  chain. That device has now produced three distinct defects; it may be worth treating it as a
  standing risk area rather than a coincidence.
- **HK-020** records an overnight run that produced zero usable corpus. Not confirmed to be this
  same cause, but the shape matches and it is worth re-checking against this finding.

## 6. Suggested next step — a decisive offline experiment

Three previous fix rounds were defeated by live testing, which is slow and non-reproducible.
**This can now be settled offline, deterministically, on data already on disk.**

Because the per-cycle drift is directly measurable by cross-correlating our WAV against
WSJT-X's, our archived WAVs can be **shifted back into alignment and re-decoded**:

- **If parity in the collapsed window recovers from ~2% toward ~65%**, the collapse is window
  misalignment and nothing else — proven, not inferred. The fix then targets cycle-boundary
  synchronisation, and the re-aligned corpus becomes usable again rather than being discarded.
- **If it does not recover**, the drift is a symptom of something else in the capture path and
  the diagnosis must widen.

Either outcome is decisive, and both use 5 782 matched WAV pairs already archived under
`artefacts/20260729_live_run_1831-8080`. This also yields the decoder's true DT tolerance
(~2.4 s from §2.3) as a measured constant, which the project needs regardless.

## 7. What is NOT established

Stated explicitly so none of it is cited as fact:

- **The mechanism in code.** "Capture free-runs on the device sample clock without UTC resync"
  fits all four sessions but has **not** been verified by reading `WasapiAudioSource.cs` or
  `CycleFramer.cs`. The locus could equally be the framing logic, the resampler's rate
  assumption, or the interaction between them.
- **The exact DT tolerance.** §2.3 brackets the cliff between 2.34 s and 2.48 s from decode
  counts. That is an observed threshold, not a value read from `ft8_lib`'s candidate search.
- **Whether the drift is linear indefinitely**, or whether it is corrected by anything at longer
  timescales.
- **Whether other capture devices are affected.** Only two are represented in the available
  data; `ArecordAudioSource`/`SoxAudioSource` paths are untested for this.
- **Whether the 49.9% figure is fully explained** by this. The healthy-window parity is ~65.6%,
  which is close to but not identical to the sibling corpus's 62.4%; some residual difference
  may remain once that corpus is itself recomputed on its clean window.

## 8. Process

Per HK-015 the dev-tasks arising from this are QA's to author, not the Architect's. Per HK-011
any `src/` change routes through a separate Developer session with the Captain's sign-off; this
document proposes **no fix** — §7 is why. Per HK-014 it is committed locally and goes no further.
Per HK-006 no `pre_merge_check.py` run is implied. Per NFR-021 all figures are aggregates; the
raw WAV and `ALL.TXT` material referenced stays under git-ignored `artefacts/`.

## 9. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md`
  — the D-001 ruling this finding forced a revision of (§3.2 withdrawn, Measurement B redesigned).
- `qa/cycleframer-alignment-replay/2026-07-30-2221-qa-to-architect-capture-chain-and-cross-band-findings.md`
  — the QA note whose §2 DT-sign observation was this drift seen in cross-section.
- `qa/endurance/2026-07-29-5016363/anova_report_40m.md`, `qa/endurance/2026-07-29-489135a/anova_report_40m.md`
  — the two affected corpora.
- `artefacts/20260729_live_run_1831-8080/` — 5 782 matched WAV pairs, both `ALL.TXT`s, daemon log
  (git-ignored).
- `openspec/changes/` — `fix-cycle-boundary-clock-drift` history (PR #108, paused).
