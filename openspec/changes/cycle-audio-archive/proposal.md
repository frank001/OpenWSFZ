**User-facing:** yes

## Why

Two independent reasons converge on the same capability.

**1. Operators need it, and every comparable program has it.** WSJT-X, JTDX and MSHV all offer
"save all / save decoded" `.wav` capture of each receive cycle. It is how an operator answers
"was that a bad decode or a bad signal?", how they send a recording to someone for help, and how
they re-decode a session offline after changing settings. OpenWSFZ has no equivalent: once a
15-second window has been decoded, its audio is gone forever.

**2. It is the missing instrument for D-001.** The 2026-07-25 Architect analysis
(`qa/cycleframer-alignment-replay/2026-07-25-1200-architect-second-mechanism-located.md`)
established from the 0724 session's own logs that the live-path half of D-001 is **not** a
cycle-boundary timing defect:

- the capture path loses nothing (0 of 2 836 windows lost even one chunk),
- every framed window reached the decoder (2 682 emitted == 2 682 decoded),
- the audio on zero-decode cycles is indistinguishable from the audio on decoding cycles
  (RMS ratio 1.01, same noise floor, exactly 180 000 samples every time),
- and the entire loss sits at LDPC: the candidate list is saturated at `K_MAX_CANDIDATES = 140`
  on 99.8 % of zero-decode cycles — sync finds the signals — while `failCands` climbs 82 → 136.

What remains unknown is why the *live* path's audio yields worse LLRs than a replay of WSJT-X's
capture of the same RF. Answering that requires exactly one thing the project does not have:
**OpenWSFZ's own captured audio, on disk, in a form the existing offline harness can decode.**

Every previous round of this investigation has had to reconstruct the live path's behaviour
indirectly — walking daemon logs, reconstructing `cycleStart` from correction sums, joining
against WSJT-X's recordings on a grid our own labels had slid off. That reconstruction work has
been the single largest cost of the last five rounds and a repeated source of error.

Building this as a **product feature rather than a throwaway diagnostic harness** costs little
extra — the write path is the same either way — and means the instrument is permanently
available for the next investigation instead of being deleted with the current one.

## What Changes

- **New capability: cycle audio archive.** The daemon SHALL be able to write each decode cycle's
  15-second PCM window to a `.wav` file, under operator control, with four modes: `Off`
  (default), `All`, `Decoded` (cycles yielding at least one decode), and `NoDecodes` (cycles
  yielding none).
- **`NoDecodes` has no equivalent in WSJT-X and is deliberate.** It captures precisely the
  failure population — the cycles where the band was open and OpenWSFZ heard nothing — at a
  fraction of `All`'s disk cost. It is directly useful to an operator diagnosing a quiet
  receiver, and it is the mode this project's own open defect most needs.
- **Format is byte-compatible with WSJT-X's recordings**: 12 kHz mono 16-bit PCM,
  `YYMMDD_HHMMSS.wav`. This is not cosmetic — the entire existing QA harness (`rewindow.py`,
  `run_phase.py`, `D001ParamSweep`, the whole alignment-replay study) already consumes exactly
  this format and will read OpenWSFZ's own captures with no changes at all. It also lets an
  operator open the files in WSJT-X, Audacity, or `jt9 -a`. This mirrors the existing project
  convention that `AllTxtWriter` emits WSJT-X-compatible `ALL.TXT` (FR-027/028).
- **A sidecar manifest (`cycle-archive.csv`) is written alongside the audio**, recording per
  cycle: filename, the framer's `cycleStart` at millisecond precision, the true wall-clock instant
  the window closed, decode count, dial frequency, and clipped-sample count. This is what makes
  the archive scientifically usable rather than merely a pile of files — it is precisely the join
  key the alignment-replay study had to reconstruct by hand from log-walking, and it removes that
  entire class of work (and error) from every future investigation.
- **Retention is managed, not left to the user.** `All` mode costs ~84 MB/hour (~2 GB/day). The
  writer enforces a size cap and an age cap, deleting oldest-first, and stops archiving with a
  Warning if free disk space falls below a floor. WSJT-X does not do this and its users routinely
  fill disks.
- **Archive drops are counted and reported, never silent.** Directly per a defect found on
  2026-07-25: `WasapiAudioSource` logs a warning when `TryWrite` fails on a `DropOldest` channel,
  but `DropOldest` never fails a write, so that warning is unreachable dead code. This change
  SHALL NOT repeat that pattern — see `design.md` Decision 3.
- **No GUI in this change.** Per the standing UI-visibility convention (UI controls appear only
  once their backend is fully implemented and testable end-to-end), Phase 1 delivers the backend,
  configuration, REST surface and tests; the settings-panel work is a separate, later,
  GUI-focused change. Phase 1 is fully usable via `config.json` and the existing config REST API,
  which is all the D-001 diagnostic needs.

## Impact

- **Affected capabilities:** new `cycle-audio-archive` spec. Touches `configuration` (new config
  section) and `decode-control` (the decode pump gains an enqueue call).
- **Affected code:** new `CycleWavWriter` + `CycleArchiveService` in `OpenWSFZ.Daemon` (modelled
  directly on the existing `AllTxtWriter` pattern and position); new
  `CycleAudioArchiveConfig` in `OpenWSFZ.Abstractions`; registration in `ConfigJsonContext` and
  the `JsonConfigStore` null-backfill list; one enqueue call in the `Program.cs` decode pump.
- **Decode pipeline safety:** the pump only enqueues; all file I/O happens on a dedicated writer
  task. The pump must never block on disk — a stalled pump would cause silent window drops at
  `framerOutput` (capacity 2, `DropOldest`), which is exactly the failure mode this project has
  just spent five rounds failing to see. See `design.md` Decision 2.
- **Privacy (NFR-021):** recordings contain real off-air audio and real third-party callsigns.
  Default mode is `Off`; the default directory is the platform config directory
  (`%AppData%\OpenWSFZ\cycle-audio\`), never the repository; the path is added to `.gitignore`
  defensively.
- **Testing:** unit coverage for WAV encoding (header correctness, float→int16 conversion,
  clipping count), mode selection, filename collision handling, manifest content, and retention
  sweeps; an integration test decoding a written file back through `Ft8Decoder` to prove
  round-trip fidelity.
- **No** change to decode behaviour, decode results, `ALL.TXT`, or any existing interface when
  the feature is `Off` (the default) — the pump's added work is one `if` against a config flag.
- **No** new external dependency: the WAV writer is ~40 lines against `System.IO`; NAudio is
  already referenced but is Windows-only and is not used here, keeping the feature cross-platform.
