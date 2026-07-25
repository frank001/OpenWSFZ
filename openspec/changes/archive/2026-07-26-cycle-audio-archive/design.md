# Design — cycle audio archive

## Context

The daemon frames 15-second, 180 000-sample windows in `CycleFramer` and hands them to a decode
pump in `Program.cs` via `framerOutput` (a bounded channel, capacity 2, `DropOldest`). The pump
decodes, publishes to the UI, appends to `ALL.TXT` via `AllTxtWriter`, and fans out to the QSO
controllers. After that the PCM is unreferenced and collected.

This change adds a fifth consumer of that same window: an archive writer.

Two constraints dominate every decision below.

1. **The decode pump must never block on disk.** If the pump stalls, `framerOutput` fills and
   silently drops windows. The 2026-07-25 analysis established that this exact class of silent
   loss is what made five rounds of D-001 investigation unable to see what was happening.
2. **Loss inside this feature must be observable.** Same reason.

## Decision 1 — Hook the archive in the decode pump, not in `CycleFramer`

**Chosen: the decode pump, immediately after `DecodeAsync` returns.**

Alternatives considered:

| Option | Verdict |
|---|---|
| Write inside `CycleFramer` at window emit | **Rejected.** `Decoded` and `NoDecodes` modes need the decode count, which does not exist yet at emit time. Supporting them would require a callback from the pump back into the framer, coupling the framer to decode outcomes for no benefit. It would also put file I/O on the framing hot path, where a stall directly corrupts sample accounting. |
| A second reader fanned out from `framerOutput` | **Rejected.** `framerOutput` has one reader today; adding a second means each window goes to exactly one of them, not both. Making it a broadcast requires restructuring the pipeline for a feature that does not need it. |
| **The decode pump, post-decode** | **Chosen.** The decode count is in hand, the PCM is already referenced (no extra retention), and it is the same position `AllTxtWriter` already occupies — an established, tested pattern in this codebase. |

`CycleFramer` is untouched by this change. That is deliberate: it is the subject of an active,
unresolved investigation, and this change must not perturb it.

## Decision 2 — The pump enqueues; a dedicated writer task does all I/O

The pump calls `CycleArchiveService.TryEnqueue(pcm, cycleStart, closedUtc, decodeCount, dialMhz)`,
which is non-blocking and returns a `bool`. A long-running writer task drains the queue and
performs every file operation: WAV encode, write, manifest append, retention sweep.

Sizing: at 352 KB per window, a queue depth of 8 is ~2.8 MB of retained PCM and two minutes of
slack against a slow disk. That is ample; the failure mode we care about is a *stalled* disk, not
a slightly slow one, and no queue depth saves us from that.

**The pump SHALL NOT await the write.** A `Task` returned by the writer is never awaited on the
pump's path.

## Decision 3 — Drops are counted, and the channel mode makes them countable

**`FullMode = BoundedChannelFullMode.DropWrite`, and `TryWrite`'s return value is checked.**

This is a direct, deliberate correction of a defect found in the existing codebase on 2026-07-25:

```csharp
// WasapiAudioSource.cs — the channel is DropOldest, so TryWrite NEVER returns false.
// This warning is unreachable. Silent loss with unreachable detection.
if (!innerChannel.Writer.TryWrite(chunk))
    _logger?.LogWarning("Audio chunk dropped ...");
```

`DropOldest`, `DropNewest` and `DropWrite` all cause `TryWrite` to return **true** unconditionally
in .NET — a channel configured that way cannot report a drop through its return value at all.
Detection has to be built explicitly.

Therefore:

- The archive channel uses `DropWrite` (dropping the *newest* is correct here — an archive should
  be a contiguous prefix of what happened, not a window with holes punched in its middle).
- `TryEnqueue` compares the queue's count against capacity *before* writing and increments a
  `DroppedCycles` counter when it cannot accept, rather than relying on `TryWrite`'s return.
- The counter is logged at Warning on first drop and every 100th thereafter, exposed on the
  daemon status endpoint, and written to the manifest as a gap marker.

**Standing rule for this capability:** no drop path may exist that is not counted and reportable.

## Decision 4 — WSJT-X-byte-compatible format

12 000 Hz, mono, 16-bit signed PCM, canonical 44-byte RIFF/WAVE header, filename
`YYMMDD_HHMMSS.wav`.

Rationale, in order of weight:

1. **The existing QA harness reads it unmodified.** `rewindow.py` asserts mono/12 kHz/16-bit/
   exactly 180 000 frames; `D001ParamSweep` has `ExpectedSamples = 180_000` as a hard contract.
   Choosing any other format means porting the entire alignment-replay study to read it. Choosing
   this one means the D-001 experiment is a directory swap.
2. **Operators can use the files with existing tools** — WSJT-X, `jt9 -a`, Audacity.
3. **Consistency with an existing project convention** — `AllTxtWriter` already emits
   WSJT-X-compatible `ALL.TXT`.

Float→int16: `(short)Math.Clamp(MathF.Round(sample * 32767f), -32768f, 32767f)`.

**Clipped samples are counted per cycle and recorded in the manifest.** A nonzero clip count is a
direct, immediately visible indication of an input-level problem — worth having, costs one
comparison per sample.

**Accepted trade-off:** 16-bit quantisation is lossy relative to the internal `float[]`. For the
D-001 comparison this is not merely acceptable but correct — WSJT-X's reference recordings are
also 16-bit, so both sides of the comparison carry identical quantisation. A `Float32` option is a
plausible future addition and is deliberately **not** built now.

## Decision 5 — Filenames come from the framer's `cycleStart`, and collisions are handled

The filename uses `cycleStart` as the framer reports it — **not** a re-derived true-UTC value.

This means archived filenames will *not* always match WSJT-X's for the same cycle: the drift
correction slides `cycleStart` off the true 15-second grid (in the 0724 session only 452 of 2 839
labels were on-grid). That is the honest and useful behaviour — the filename records what the
daemon believed, and any divergence from true UTC is itself evidence.

Because a backwards correction can produce a repeated label, **collisions must not overwrite**.
On collision the writer appends `_2`, `_3`, … and logs at Debug.

## Decision 6 — The sidecar manifest is what makes the archive usable

`cycle-archive.csv`, appended one row per archived cycle, header written on file creation:

```
filename,cycle_start_utc,window_closed_utc,decode_count,dial_mhz,clipped_samples,dropped_before
```

- `cycle_start_utc` — the framer's label, millisecond precision.
- `window_closed_utc` — `DateTime.UtcNow` at window close. **The difference between these two is
  the framer's accumulated off-grid offset**, recorded directly instead of reconstructed.
- `dropped_before` — count of cycles dropped since the previous row, so gaps are explicit.

This single file removes the log-walking reconstruction step that the alignment-replay study spent
most of its effort on and got wrong twice (the sign inversion in SPEC §6.3, and the missed
mid-session restart in 11.10 §1). It contains no message text and no callsigns — it is safe to
share and to commit in derived form, unlike the `.wav` files themselves.

## Decision 7 — Retention is enforced by the writer

`All` mode: 240 cycles/hour × 352 KB ≈ **84 MB/hour ≈ 2 GB/day**. Unmanaged, this fills disks —
a well-known WSJT-X operational complaint.

- `MaxSizeMb` (default 2048) and `MaxAgeHours` (default 168) — oldest-first deletion.
- Sweep runs on the writer task every 100 cycles (~25 minutes), not per cycle.
- **Deletion is restricted to files in the configured directory matching the archive's own
  `YYMMDD_HHMMSS[_n].wav` pattern.** Never a directory wipe — a user pointing the setting at a
  populated folder must not lose data.
- If free disk space falls below 500 MB, archiving stops, mode is treated as `Off` for the
  remainder of the session, and a Warning is logged. This is a safety floor, not a retention
  policy.

## Decision 8 — Configuration shape and privacy default

`CycleAudioArchiveConfig` in `OpenWSFZ.Abstractions`, mirroring `DecodeLogConfig`:

```csharp
public sealed record CycleAudioArchiveConfig
{
    public CycleAudioArchiveMode Mode         { get; init; } = CycleAudioArchiveMode.Off;
    public string?               Directory    { get; init; } = null;   // null => platform default
    public int                   MaxSizeMb    { get; init; } = 2048;
    public int                   MaxAgeHours  { get; init; } = 168;
    public bool                  WriteManifest{ get; init; } = true;
}

public enum CycleAudioArchiveMode { Off, All, Decoded, NoDecodes }
```

**Deserialization note (the `DecodeNoiseSuppressionConfig` / Lesson 6 pattern):** `MaxSizeMb`,
`MaxAgeHours` and `WriteManifest` all have non-CLR-zero defaults, so a JSON object omitting those
keys would deserialise them to `0`/`false` under STJ source generation. An explicit
`[JsonConstructor]` with matching parameter defaults is required, exactly as
`DecodeNoiseSuppressionConfig` documents.

`JsonConfigStore` must add the null-backfill for this section alongside the existing
`DecodeLog` / `DecodeNoiseSuppression` entries.

**Default directory** resolves via the same platform logic `ConfigPathResolver` already uses:
`%AppData%\OpenWSFZ\cycle-audio\` on Windows, `~/.config/OpenWSFZ/cycle-audio/` elsewhere —
**never** the repository or the executable directory (NFR-021: these files contain real
third-party callsigns).

## Decision 9 — No GUI in this change

The standing project convention is that UI controls appear only once their backend is fully
implemented and testable end-to-end. Phase 1 therefore ships backend + config + REST + tests with
no UI, and the settings panel is a separate later change. Parking the GUI is the required
sequence here, not a compromise.

Recorded for that later change, so the intent is not lost:

- Mode selector (`Off` / `All` / `Decoded` / `NoDecodes`) with a plain-language description of
  each — particularly `NoDecodes`, whose value is not self-evident from its name.
- Directory picker with an "open folder" affordance.
- Retention controls, plus a live "N files, M MB used" readout — the number that tells an operator
  whether they are about to fill their disk.
- A one-shot **"record the next N cycles"** button: the operator-friendly form of the diagnostic
  capture, which avoids leaving `All` mode enabled by accident.

## Risks

| Risk | Mitigation |
|---|---|
| Disk I/O stalls the decode pump | Decision 2 — pump only enqueues, never awaits |
| Silent archive loss repeats the `DropOldest` blind spot | Decision 3 — explicit counting, no reliance on `TryWrite`'s return |
| Retention deletes a user's unrelated files | Decision 7 — pattern-restricted deletion within the configured directory only |
| Recordings leak real callsigns into VCS | Decision 8 — default `Off`, default path outside repo, `.gitignore` entry |
| Feature perturbs the active `CycleFramer` investigation | `CycleFramer` is not touched; default `Off` makes the pump's added cost one boolean test |
