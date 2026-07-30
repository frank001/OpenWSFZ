# Audio contamination note — Voicemeeter B1 / SDR Uno feed, 2026-07-29

**Status:** Confirmed by direct measurement (WAV peak amplitude), not just observation. Flagged
per the Captain's direction — not considered a blocking defect, but the corpus below must not be
treated as clean for study purposes without accounting for this.

## Cause

A system audio device (VLC / web browser, confirmed by the Captain) was leaking into the
Voicemeeter B1 virtual bus that this instance's audio input is drawn from. This is independent of
SDR Uno's own signal chain — it's other Windows application audio bleeding into the same virtual
mixer bus, not an RF/SDR-side defect.

## Confirmed activity context (Captain's account, matches the measured data exactly)

- **20m period:** interacting with QA/Developer sessions or browsing Reddit, "maybe occasionally"
  playing audio.
- **80m period:** started watching a movie shortly after the retune — continuous background audio
  for the whole period, explaining the pervasive intermittent contamination measured below.

## Timeline and scope (all times UTC, 2026-07-29)

| Window | Band | Status | Evidence |
|---|---|---|---|
| `18:31:15` – `21:14:xx` | 20m (14.074 MHz) | **Clean** | Dense sampling (~every 3 min, 53 points) across the full ~2h43m span: **zero elevated readings** — every single sample below the 0.20 threshold, mostly under 0.10. Consistent with "occasional" light browsing audio either not leaking measurably or falling between samples too briefly to register — no evidence of contamination at this sampling density. |
| `21:18:00` – `23:07:30` | 80m (3.573 MHz) | **Contaminated, intermittent** | Dense sampling (~every 3 min, 38 points) across the full span: ~60% of sampled cycles show elevated peak amplitude (>0.20, up to 0.75), scattered from the very first 80m cycle to just before discovery. Matches a movie playing continuously in the background — on/off at the level of individual 15 s cycles (quiet dialogue vs. louder scenes/music), not a constant tone. |
| `23:07:30` – `23:08:00` (approx.) | 80m | Clean (first discovery + turn-off) | Peak amplitude back to 0.12–0.18 baseline. |
| `23:08:15` – `23:18:00` | 80m | **Contaminated (deliberate test)** | Captain deliberately re-enabled the leak to characterize it: played "Snowy White – Midnight Blues" then "Volbeat – Sad Man's Tongue". Peak amplitude 0.21–0.25 throughout this window, confirmed via waterfall screenshot (broadband wash vs. clean discrete tones) and WAV measurement. |
| `23:18:00` onward | 80m | **Clean, confirmed** | Peak amplitude back to 0.15–0.17, matching pre-contamination baseline; waterfall visually confirmed clean, matching the 40m instance's own waterfall side by side. |

## What this does NOT affect

- The **40m instance** (`OpenWSFZ-40m-capture`) — physical radio via USB Audio CODEC microphone
  input, an entirely separate audio device, never touched Voicemeeter.
- **WSJT-X's own 40m recordings** (`%LocalAppData%\WSJT-X\save\`) — same physical radio input,
  unaffected.

## Caveat

The 20m/80m split above is based on dense spot-sampling (53 points for 20m, 38 points for 80m), not
an exhaustive per-file scan of every archived cycle. Both windows were sampled at comparable density
(~every 3 minutes) and the results are internally consistent — 53/53 clean on 20m, ~60% elevated on
80m — giving reasonable confidence in the characterization either way, but not certainty for any
single specific cycle. If a specific cycle's cleanliness matters for the study, verify that file
directly (WAV peak amplitude
`>0.20` is the working threshold established tonight; the app's own logged `noise_floor` metric
does **not** reliably distinguish contaminated from clean cycles — see the deliberate-test evidence
above, where `noise_floor` stayed within normal variance throughout the confirmed-contaminated
window).

## Band history (this instance/directory), plain retunes, not contamination

For corpus completeness, in addition to the contamination timeline above: the Captain retuned
this instance again, 80m → 10m (dial 28.074 MHz), via `POST /api/v1/tune` (CAT disabled on this
instance, so this is the manual-dial-frequency config path, same mechanism as the earlier 20m→80m
retune). The API call/config update landed at **2026-07-30T09:27:24Z** (confirmed from the app's
own log line, `POST /api/v1/tune` request — not estimated), with the physical SDR Uno-side switch
confirmed done by the Captain shortly after. Cross-checking the manifest: the first `dial_mhz=28.074`
cycle rows also begin at the `2026-07-30T09:` hour, consistent with the app-side and physical-side
switches having happened together, not with a gap where the app was mislabeling still-80m audio as
10m. Persisted to `config.json` so an auto-recovery supervisor restart reloads 10m correctly. No
contamination concern noted for this retune at time of writing — the audio-leak issue above was
already resolved and stayed off. If 10m-band cycles later need excluding/including for study
purposes, cross-reference `cycle-archive.csv`'s `dial_mhz` column (28.074) and `cycle_start_utc` >=
2026-07-30T09:27:24Z, same method used to split the 20m/80m table earlier.

## Second 20m window (this instance retuned back from 10m)

The Captain stopped decoding and retuned SDR Uno back to 20m. Exact boundaries, from the app's own
log (`logs/openswfz-20260729T182813Z.log`), not estimated:

- **10m window closed:** `2026-07-30T15:40:53.980Z` (`Capture stopped ... (operator-stopped)`).
- Dial frequency set to 14.074 MHz via `POST /api/v1/tune` while capture was still stopped
  (`decodingEnabled=false` confirmed at the time of the call).
- **20m window (2nd) opened:** `2026-07-30T15:42:24.205Z` (`Capture started`), first cycle
  `15:42:15Z`. Manifest confirms `dial_mhz=14.074` from the first row onward, decode counts
  21-26/cycle — healthy, consistent with a real band, not a mislabeling gap.

So this instance/directory's corpus now spans three non-contiguous band windows: 20m (1st),
80m, 10m, 20m (2nd) — cross-reference `cycle-archive.csv`'s `dial_mhz` + `cycle_start_utc`
columns against the boundaries recorded in this file (this section and the "Band history" section
above) to reconstruct which rows belong to which window.

## Manifest cross-reference

`cycle-archive.csv` in this same directory has one row per archived cycle with `cycle_start_utc` and
`dial_mhz` — cross-reference against the timeline above to identify/exclude specific affected rows.
