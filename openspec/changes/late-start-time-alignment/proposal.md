**User-facing:** yes

## Why

Issue #259. When a QSO answer starts late in its 15 s slot (a manual double-click, or a GridTracker Reply arriving mid-slot), OpenWSFZ keys at once and plays the 12.64 s clip from its first symbol, cutting the tail at the slot boundary (D-CALLER-021: `Ft8TimeHelper.ClampSampleCountToWindowBoundary`). The 12.64 s buffer has no lead-in silence, so symbol 0 goes out at the moment of the late start and the signal sits at DT about +(t - 0.5) s, where t is the start offset into the slot.

WSJT-X handles a late start differently (source: GitHub `saitohirga/WSJT-X` master, not the 2.7.0 tag): `widgets/mainwindow.cpp` allows a late start only while `fTR < 0.75` (11.25 s into an FT8 slot), and `Modulator/Modulator.cpp` ("adjust for late starts", `delay_ms` 500 for FT8) begins the waveform at the offset that has already elapsed, so it **skips the start of the clip** and every remaining symbol goes out at its proper time (DT about 0). WSJT-X's sync search is +-2.48 s (`lib/ft8/sync8.f90`, `JZ=62` steps of 0.04 s), so an OpenWSFZ start more than about 3 s into the slot is not decodable by a WSJT-X station.

The case that found it: the first answer of the #257 live check started 4.89 s into its slot (DT about +4.4 s), the audio cut to 10.1 s. Only one first transmission is on file since v0.59 (QA note `qa/rr-study/2026-10-23-1810-qa-o2-late-start-trace.md`).

This **supersedes the 2026-09-30 decision** (SUB-FEAS design 13.4, finding (g): late click, "NO CHANGE"), which rested on a wrong claim that OpenWSFZ's behaviour matched WSJT-X (Architect ledger E42). **What stays from 09-30:** a late click still transmits straight away; there is no refusal. **What changes:** the timing of a late transmission, and one cut-off. The Captain's decision, 2026-10-23: "Option A".

Architect spec: `qa/rr-study/2026-10-23-1735-architect-to-qa-spec-late-start-time-alignment.md` (`arch/late-start-align`, `47659e13`); QA (k) review with amendments M1 to M4: `qa/rr-study/2026-10-23-1745-qa-k-review-late-start-time-alignment.md`.

## What Changes

- `Ft8TimeHelper` gets one function that, for a start offset t and the full buffer, returns how many leading samples to skip and how many to load. `TransmitAsync` of **both** `QsoAnswererService` and `QsoCallerService` uses it.
  - t <= 2.36 s: the full buffer (606,720 samples at 48 kHz), unchanged from today. 2.36 s = 15 - 12.64 = `LateBatch.LatestWholeStart`.
  - 2.36 s < t < 11.25 s: skip the first round((t - 0.5) x 48,000) samples and load the rest. Playback ends about 13.14 s into the slot.
  - t >= 11.25 s: do not key (the existing zero-remaining skip path, now logged at Information).
- The existing boundary clamp stays as a safety net, applied after the skip.
- **Manual engages never fire at t >= 11.25 s:** the answerer's pending target and jump-in, and the caller's pending responder, are retained and fire in the next correct-phase window (about 19 s later; the 60 s stale expiry is unchanged).
- One Information log line at every late start (t > 2.36 s) with the offset, the samples skipped and the samples loaded, as milliseconds. No message text.
- A 240-sample (5 ms) raised-cosine fade-in on the first samples loaded after a skip, and a matching fade-out wherever the boundary clamp cuts the tail, so a cut at an arbitrary phase does not click on air; full, uncut clips are untouched.
- An aligned (shortened) transmission counts for retry, watchdog and ADIF exactly as a full one does today.

**Unchanged:** `LateBatch` (the auto-reply hold at 2.36 s), the audio synthesiser, anything in `native/`.

## Non-goals

`LateBatch`'s hold; style "M" (a smaller skip) as code, unless a later spec argues for it; pre-keying PTT earlier; the O1 log line; other receivers' DT ranges (JTDX and MSHV were not read).

## Capabilities

### Modified Capabilities

- `qso-answerer`: a late manual engage is time-aligned and never fires from 11.25 s.
- `qso-caller`: the same for the pending responder and for every caller transmission.

## Impact

`src/OpenWSFZ.Daemon/Ft8TimeHelper.cs`, `QsoAnswererService.cs`, `QsoCallerService.cs`, their tests. No `native/` change. `VERSION` bump per G9b (user-facing: yes).
