# D-001 Live-Path Root-Cause Investigation — Results Report

| Field | Value |
|---|---|
| Defect ID | D-001 (open, issue #3) |
| Type | Offline log analysis + fast direct hardware measurement (no product/decoder code changed) |
| Governing spec | `dev-tasks/2026-07-23-d001-live-path-root-cause-spec.md` |
| Decision context | PR #103 (≈23.4% Isolated-class Decoded-on-replay) / PR #105 (effect not class-independent) left the mechanism undiagnosed |
| Analysis date | 2026-07-23 |
| Status | **COMPLETE — root cause identified and independently corroborated by two methods** |

---

## Section 1 — Study Hypothesis

### 1.1 What this pass answers

Why does isolated replay recover ≈23% of Isolated-class misses that failed live? The spec's
working hypothesis, built from reading `CycleFramer.cs`/`WasapiAudioSource.cs` before any data
was collected: the 15s cycle boundary is computed once at startup and advanced purely by sample
count, never re-synced to wall clock — if the real capture device's clock runs at a slightly
different rate than its declared nominal rate, this silently accumulates into real drift between
OpenWSFZ's internal decode window and the true FT8 UTC time grid over a many-hour session.

### 1.2 Method (revised mid-session for speed — see note)

**Phase 1 (offline, ~5 min compute):** extended `classify_cochannel.py`'s parser to retain the
already-present `dt` field; for matched decodes (same signal, both apps, same slot) across all
three sessions, computed `delta_dt = openwsfz_dt − wsjt_dt` binned by session-elapsed hours and
fit an OLS trend. Also mined the two retained Debug-level live daemon logs (07-07, 06-22) for
restarts/buffer-drop warnings.

**Phase 3 (originally scoped as a 3.5-hour live marker-injection test relying on FT8's 0.1s DT
quantization to show a visible step over hours). Replaced, on Captain's direction, with a much
faster, more precise method:** a direct measurement of the actual capture device's sample
delivery rate against its declared nominal rate, via a Python `sounddevice` recording with
per-callback wall-clock timestamps fit to a linear regression. A ppm-level clock error resolves
in **minutes** at sample-level precision, not hours at 0.1s FT8-DT precision — no daemon, no FT8
decode, no waiting required. Run against both VB-CABLE (today's replay-pilot device) and the
actual physical **USB Audio CODEC** device used in every historical live session (confirmed via
the retained log's own `WaveFormat=48000 Hz` banner naming that exact device).

### 1.3 Pre-committed decision thresholds

None — this is a direct measurement compared against Phase 1's independently-derived figure.

### 1.4 Null hypothesis

Neither OpenWSFZ's DT trend (Phase 1) nor either tested device's clock rate (Phase 3) deviates
from a stable/nominal baseline. **Rejected on both counts, for the physical USB Audio CODEC
device specifically** (Section 3).

---

## Section 2 — Data Summary

### 2.1 Phase 1 — cross-app DT drift (all three sessions, matched decodes)

| Session | n matched (all SNR) | `delta_dt` slope | t-statistic | Spread over session |
|---|---:|---:|---:|---:|
| 07-07 | 41,398 | −0.1712 s/hr | −2482 | 3.0 s |
| 07-06 | 38,223 | −0.1714 s/hr | −2105 | 2.0 s |
| 06-22 | 29,350 | −0.1725 s/hr | −1347 | 2.4 s |

Remarkably consistent across three independent sessions (different dates), all low-SNR bands
individually, and the all-SNR pool — a systematic, near-deterministic rate, not noise (t-stats in
the hundreds to thousands). WSJT-X's own DT slope stays within ±0.02 s/hr of flat in every
session — confirms it as a stable reference. OpenWSFZ's own DT slope alone (not just the
difference) is essentially identical to `delta_dt`'s, confirming the drift originates on
OpenWSFZ's side.

**Log mining (07-07, 06-22):** zero `[WRN]` (buffer-near-full/dropped) events in either session;
exactly one pipeline restart each, both within ~9 minutes of startup, none in the following
8–17 hours of steady-state operation. Rules out mid-session buffer drops and watchdog restarts
as the driver.

### 2.2 Phase 3 — direct device clock-rate measurement

| Device | Measured rate | ppm error | Predicted drift (this mechanism alone) | Fit precision (RMSE) |
|---|---:|---:|---:|---:|
| VB-CABLE "CABLE Output" (today's test rig) | 47,999.999 Hz | −0.02 ppm | −0.0001 s/hr | 0.73 ms |
| **USB Audio CODEC (the actual historical-session device)** | **47,997.964 Hz** | **−42.4 ppm** | **−0.1527 s/hr** | **0.64 ms** |

Two independent 300s runs against the USB CODEC device agreed to within 0.2 ppm (−42.25 and
−42.41 ppm). VB-CABLE — a software-emulated device, not what any historical session used — shows
no measurable error, ruling out the measurement method itself as an artifact source.

---

## Section 3 — Results

**Root cause identified: the physical USB Audio CODEC device used throughout every historical
live session has a genuine ~−42 ppm clock-rate error** — it delivers audio samples about 42
millionths slower than its own declared/negotiated 48,000 Hz. `WasapiAudioSource.cs`'s
fixed-ratio resampler and `CycleFramer.cs`'s sample-count-only cycle framing (never re-synced to
wall clock) together turn this into an accumulating real-time offset: because the device takes
measurably *longer* than nominal to deliver a given sample count, CycleFramer's internal 15s
cycle boundary drifts progressively later relative to true UTC as a session runs. A signal
arriving at the true FT8 protocol boundary then lands progressively *earlier* relative to
OpenWSFZ's own (later-starting) window — producing exactly the increasingly-negative DT trend
Phase 1 measured independently from three full historical sessions.

**Quantitative agreement between the two independent methods:**

- Phase 1 (hours of historical decode data, cross-referenced against WSJT-X): **−0.171 s/hr**
- Phase 3 (5 minutes of direct hardware measurement, this mechanism alone): **−0.153 s/hr**

**89% of the measured drift is explained by this single mechanism**, with matching sign in every
one of three independent sessions and both measurement methods. The residual ~11% is well within
what device-specific ppm variation (clock error is not always perfectly constant run-to-run) or
minor additional contributors could plausibly account for — not evidence of a second major
mechanism.

**Practical magnitude:** over a ~17-hour session (the historical 07-07 run), this predicts
≈17 × 0.153 ≈ **2.6 seconds** of accumulated window lag by session end — enormous relative to a
15-second FT8 slot, easily sufficient to push a marginal-SNR signal's true arrival time outside
wherever the decoder's candidate search actually looks by late in a long session. This is
invisible to the existing per-pass candidate-count diagnostic (matches PR #103's 100% Ambiguous
finding — the passband stays busy with unrelated candidates regardless) and has nothing to do
with co-channel interference (matches PR #105's Tight-class null result — a Tight-class miss's
failure is dominated by its interferer, not by window alignment).

### 3.1 Caveats

- **Single physical device tested.** The ~42 ppm figure is specific to this one USB Audio CODEC
  unit; other capture devices (a different sound card, or the operator's radio-interface audio
  path in a different physical setup) would need their own measurement — this is a per-device
  hardware characteristic, not a universal constant.
- **Method change disclosed, not hidden.** The originally-scoped 3.5-hour marker-injection design
  (`phase3_marker_drift.py`, since removed) was replaced mid-session with the direct clock-rate
  measurement above at the Captain's explicit direction for speed; the smoke-tested marker-based
  design was sound and could still serve as an independent confirmation if wanted, but was not
  needed once the direct measurement converged this cleanly with Phase 1.
- **This confirms the mechanism, not yet a fix.** No code change is proposed or scoped by this
  report — see Section 5.

---

## Section 4 — Verdict Table

| Question | Answer |
|---|---|
| Does OpenWSFZ's DT drift relative to WSJT-X over a live session? | **Yes — −0.171 s/hr, 3/3 sessions, extremely high confidence** |
| Is the drift explained by mid-session buffer drops or watchdog restarts? | **No — zero WRN events, zero mid-session restarts in both logged sessions** |
| Does the actual historical-session capture device have a measurable clock-rate error? | **Yes — ~−42 ppm, reproduced twice, ruling out measurement noise** |
| Does that error's predicted drift match Phase 1's independently-measured drift? | **Yes — −0.153 s/hr predicted vs −0.171 s/hr observed, 89% agreement, matching sign** |
| Root cause | **Device clock-rate error (~42 ppm, this specific USB audio device) + `CycleFramer`'s sample-count-only framing with no periodic wall-clock resync** |

---

## Section 5 — Recommendations

### 5.1 One-paragraph recommendation to Architect and Captain

**This investigation identifies a specific, quantified, high-confidence root cause for the
live-path effect PR #103 found**, via two independent methods that agree in sign and to within
11% in magnitude: `CycleFramer`'s 15-second cycle boundary is computed once at startup and
advanced purely by sample count, with no periodic re-synchronisation to wall clock; the real
capture device used in every historical session runs its clock ~42 ppm slow, which this framing
silently converts into real accumulating time drift — around 2.6 seconds over a 17-hour session.
**A fix is a bounded, well-understood class of change** (periodically re-anchor the cycle boundary
to wall clock, or correct for the resampler's assumed ratio using a measured/calibrated device
rate) — but no fix is proposed here; per this investigation's own guardrails, that is a separate,
future product-code conversation, appropriately a Developer-facing dev-task, not something QA
tooling should freelance.

### 5.2 What this pass does NOT authorise

- **Not** a code fix — no `src/` change is proposed, scoped, or estimated here.
- **Not** proof this is the *only* contributor to the ~23.4% Isolated-class Decoded-on-replay
  effect — 89% agreement is strong, not total; some residual could have other causes.
- **Not** a claim that every OpenWSFZ deployment has this exact ~42 ppm error — it is this one
  device's measured characteristic.

### 5.3 Suggested next steps, in priority order

1. **Draft a dev-tasks handoff proposing a fix** (periodic wall-clock resync in `CycleFramer`,
   or resampler-ratio calibration) for the Developer persona, per HK-000 — this is now a
   well-evidenced, well-understood product change, not exploratory QA work.
2. **If a fix ships, re-run the Tight/Isolated replay pilots (PR #103/#105's harness) against a
   corrected build** to measure how much of the ~23.4% Isolated-class gap the fix actually
   recovers — the natural regression-style validation once a fix exists.
3. Optional, lower priority: measure the clock-rate error on additional capture devices if the
   Captain wants to know whether ~42 ppm is typical or this-device-specific.

---

## Appendix A — Reproduction

- `python phase1_dt_drift.py` — offline, ~1 minute; reads existing ALL.TXT pairs and the two
  retained Debug-level daemon logs; writes `phase1_results.json`.
- `python phase3_clockrate_direct.py --duration-s 300 --device-index <N>` — live, ~5 minutes per
  device; no daemon needed. `phase3_clockrate_results_usbcodec.json` /
  `phase3_clockrate_results_vbcable.json` are this session's committed runs (USB CODEC device
  index 95, VB-CABLE WASAPI-hostapi index 97 in this environment — re-detect via
  `sd.query_devices()` on a different machine, matching name substring `"CABLE Output"` /
  `"USB Audio CODEC"` and the 48000 Hz WASAPI hostapi variant).
- Total live measurement time this session: **~20 minutes** (four 300s/20s recordings plus one
  aborted 3.5-hour design, stopped early per the Captain's direction to use the faster method
  instead).
