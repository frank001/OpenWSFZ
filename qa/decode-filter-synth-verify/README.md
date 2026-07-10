# decode-filter-synth-verify

Standalone, manually-run verification tool for the `decode-panel-filtering` capability.

Closes the gap left by `openspec/changes/decode-panel-filtering/tasks.md` task 6.4, which was
left as a manual, hardware-dependent end-to-end check ("no audio device, no FT8 signal source
wired into this environment"). This tool proves the same thing — filtering a station out means
it is never engaged, while a non-filtered station is engaged normally, in the same session —
without needing real audio hardware or a virtual audio cable (VB-CABLE).

**This is deliberately not part of `OpenWSFZ.slnx` and is never run by
`dotnet test OpenWSFZ.slnx`.** It is a console program you run yourself, on demand, when you want
to re-confirm this behaviour — not a regression-suite test collected automatically by CI or the
main build.

## Coverage

`DecodeFilterState` has nine independent axes (four attribute allow-lists, five worked-before
tri-states) and gates two separate services (`QsoAnswererService`'s CQ-scan,
`QsoCallerService`'s responder-scan/`SelectResponderAsync`). This tool exercises:

- **All nine axes**, one representative scenario each, against `QsoAnswererService`'s real
  CQ-selection gate: `AllowedEntities`, `AllowedContinents`, `AllowedCqZones`, `AllowedItuZones`,
  `ContactStates`, `CountryStates`, `ContinentStates`, `CqZoneStates`, `ItuZoneStates`.
- The **"every candidate filtered out"** case (service stays `Idle`, no transmission).
- **`QsoCallerService`'s three distinct gating mechanisms**: `CallerPartnerSelect.First` skipping
  a filtered-out responder in favour of another, `First` mode with every responder filtered out
  (stays in `WaitAnswer`), and `CallerPartnerSelect.None`'s `SelectResponderAsync` rejecting a
  filtered-out callsign outright.

The nine-axis matrix is only run once, against the answerer, because `DecodeFilterEvaluator` is a
single shared predicate both services call identically — re-running all nine axes a second time
against the caller would just prove the same evaluator logic twice, not anything new about the
caller's own gating mechanism. What genuinely differs per service is *where* and *how* the gate is
consulted, which is what the three caller-specific scenarios are for.

## What it actually does

1. **Synthesises four real FT8 signals, fresh, every run** — two CQs (`CQ Q1AAA JO22`,
   `CQ Q1BBB KP20`) and two responses to our own CQ (`Q1OFZ Q1AAA JO22`, `Q1OFZ Q1BBB KP20`) — by
   shelling out to `qa/rr-study/synth_wav.py`, the R&R study's own Python signal generator.
   Nothing here is a pre-baked fixture; the synthesiser genuinely runs each time.
2. Sums each pair into one 15-second cycle and decodes both cycles with the **real, unmocked
   `Ft8Decoder`** — a genuine P/Invoke call into `libft8`, the same native decoder the daemon
   ships with — confirming it actually recovers all four messages before proceeding.
3. Attaches each callsign to fixed region (continent/entity/CQ-zone/ITU-zone) and worked-before
   data via small in-memory `ICallsignRegionStore`/`IWorkedBeforeIndex` stand-ins, so every one of
   the nine `DecodeFilterState` axes has real, decoder-attached metadata to filter on — the real
   `callsign-regions.json`/`ADIF.log` have no entries for synthetic Q-prefix test calls, by design
   (NFR-021).
4. Feeds the real-decoded batches through real, in-process `QsoAnswererService`/
   `QsoCallerService` instances — the exact same production classes the daemon runs — with a real
   `IDecodeFilterStore`/`DecodeFilterEvaluator` filtering one axis at a time.
5. Prints a clear per-scenario `OK`/`FAIL` line plus an overall `PASS`/`FAIL` report, and exits `0`
   on success, non-zero on any failed check.

## What it does not cover

The real audio-**capture** layer (microphone / WASAPI / virtual-audio-cable input) and real PTT
hardware are not exercised — this tool starts from in-memory PCM buffers and a small recording
`IPttController` stand-in that just notes whether `KeyDownAsync` was called. Everything from
"audio samples exist" through "the correct station gets engaged, on every filter axis, on both
services" is proven against real production code; the physical hardware capture path itself is
covered instead by the companion script below.

---

## Companion script: `live_verify_9_axes.py` — real hardware-in-the-loop

`live_verify_9_axes.py`, in this same directory, closes the one gap the tool above leaves open:
it runs the same nine-axis matrix against a **real, isolated `OpenWSFZ.Daemon` process**, with
genuinely synthesised audio played into a **real virtual audio cable** (VB-CABLE or Voicemeeter)
that the daemon captures from over its real WASAPI pipeline, decoded by the real native decoder,
gated by the real `DecodeFilterEvaluator`/`IDecodeFilterStore`, and answered by the real
`QsoAnswererService` — verified through the real HTTP API, not in-process. See the script's own
module docstring for the full mechanics (audio device auto-discovery, the isolated
ADIF-log/region-file overrides used to make the four attribute axes distinguishable, per-axis
abort/re-arm sequencing, and the independent daemon-log cross-check).

**Policy (see `MEMORY.md` → `decode-panel-filtering-live-verification-policy.md`): any change
that touches `decode-panel-filtering` must re-run this script against a real daemon before
merge, and the report it writes must be committed.**

### Prerequisites (this script only)

- A virtual audio cable installed and enumerable by the OS (VB-CABLE or Voicemeeter — the script
  auto-detects either by device-name substring).
- The Release daemon already built: `dotnet build src/OpenWSFZ.Daemon -c Release` from the repo
  root (this script does not build it for you, to avoid a surprise multi-minute build on every
  invocation).
- `numpy` and `sounddevice` in the `qa/rr-study` venv (already present — the same venv
  `synth_wav.py` uses).

### Running it

From the repo root:

```
qa/rr-study/.venv/Scripts/python qa/decode-filter-synth-verify/live_verify_9_axes.py
```

(`.venv/bin/python` on Linux/macOS.) It is fully self-contained: it builds its own scratch
temp directory (isolated config/ADIF/region-override files, port `18765`), never touches your
real `%APPDATA%\OpenWSFZ\` config, `ADIF.log`, or `callsign-regions.json`, and tears itself down
— isolated daemon process killed, temp directory removed — whether it passes, fails, or the
environment prerequisites (virtual cable) aren't met.

**Reporting is automatic**: every run writes a timestamped Markdown report to
`qa/decode-filter-synth-verify/live-reports/<UTC-timestamp>-<git-sha>.md`, recording the git
commit it ran against, a per-axis PASS/FAIL table, and the independent daemon-log cross-check
count. Commit that report alongside whatever change triggered the run. Exit code `0` = PASS,
`1` = FAIL, `2` = environment prerequisites not met (report still written, marked
ENVIRONMENT UNAVAILABLE, so a run on a machine without a virtual cable never produces a false
PASS or a silently-missing report).

## Prerequisites

- The R&R study's Python venv must be set up: `qa/rr-study/.venv/` (see
  `docs/rr-synth-cli-guide.md` if it doesn't exist yet —
  `cd qa/rr-study && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt` on
  Windows, `.venv/bin/pip` on Linux/macOS).
- The rest is plain .NET — no other setup.

## Running it

From this directory:

```
dotnet run -c Release
```

Or from the repository root:

```
dotnet run -c Release -p qa/decode-filter-synth-verify
```

Expected output on success (abridged):

```
decode-panel-filtering — synthesised-signal verification
=========================================================

[1/4] Synthesising four FT8 signals via qa/rr-study/synth_wav.py ...
      wrote 4 WAVs (2 CQs, 2 responses).
[2/4] Decoding both cycles with the real Ft8Decoder (libft8 P/Invoke) ...
      CQ cycle recovered:       CQ Q1AAA JO22 | CQ Q1BBB KP20
      response cycle recovered: Q1OFZ Q1AAA JO22 | Q1OFZ Q1BBB KP20
[3/4] QsoAnswererService — all nine DecodeFilterState axes, plus all-filtered-out:
      OK  [AllowedEntities                     ] partner = Q1BBB
      ... (nine axes plus the all-filtered-out case)
[4/4] QsoCallerService — First-mode skip, all-filtered, and None-mode rejection:
      OK  [Caller First-mode skip      ] partner = Q1BBB
      OK  [Caller First-mode all-filtered] stayed WaitAnswer, no partner selected
      OK  [Caller None-mode SelectResponderAsync rejection] filtered-out callsign rejected outright

RESULT: PASS — filtering and TX-automation gating behave as intended across all nine axes and both services.
```

Exit code `0` on `PASS`, `1` on `FAIL` (script-friendly).
