# cycle-audio-archive Specification

## Purpose

Specifies the daemon's ability to write each decode cycle's 15-second PCM window to a `.wav` file
on disk, under operator control. This gives an operator the same "save all / save decoded" capture
that WSJT-X, JTDX and MSHV already offer, and gives the project a permanent instrument for offline
re-decode investigation: the archive format is byte-compatible with WSJT-X's own recordings, so
the existing offline decode harness (`rewindow.py`, `run_phase.py`, `D001ParamSweep`) consumes an
OpenWSFZ capture with zero changes. Default mode is `Off`; recordings contain real off-air audio
and real third-party callsigns and are never written inside the repository (NFR-021).

## Requirements

### Requirement: Operator-controlled cycle audio archiving

The daemon SHALL be able to write each decode cycle's 15-second PCM window to a `.wav` file on
disk under operator control. The capability SHALL offer four modes: `Off`, `All`, `Decoded`, and
`NoDecodes`. `Off` SHALL be the default and SHALL result in no file being created, no directory
being created, and no measurable work on the decode path beyond a single configuration test.
`All` SHALL archive every framed window. `Decoded` SHALL archive only windows that produced at
least one decode. `NoDecodes` SHALL archive only windows that produced no decodes.

#### Scenario: Off is the default and writes nothing

- **WHEN** the daemon runs with no `cycleAudioArchive` section present in `config.json`
- **THEN** the effective mode SHALL be `Off`, no archive directory SHALL be created, and no `.wav`
  or manifest file SHALL be written for any decode cycle

#### Scenario: All mode archives every cycle

- **WHEN** the mode is `All` and three consecutive windows are decoded, yielding 5, 0 and 2 decodes
- **THEN** three `.wav` files SHALL be written, one per window

#### Scenario: Decoded mode archives only cycles that produced decodes

- **WHEN** the mode is `Decoded` and three consecutive windows yield 5, 0 and 2 decodes
- **THEN** exactly two `.wav` files SHALL be written, corresponding to the first and third windows

#### Scenario: NoDecodes mode archives only cycles that produced nothing

- **WHEN** the mode is `NoDecodes` and three consecutive windows yield 5, 0 and 2 decodes
- **THEN** exactly one `.wav` file SHALL be written, corresponding to the second window

---

### Requirement: Archive format is WSJT-X byte-compatible

Archived files SHALL be canonical RIFF/WAVE files containing 12 000 Hz, mono, 16-bit signed PCM,
with exactly 180 000 sample frames per file, named `YYMMDD_HHMMSS.wav` derived from the cycle-start
timestamp. Float samples SHALL be converted to 16-bit by scaling by 32767, rounding, and clamping
to `[-32768, 32767]`. The number of samples clamped SHALL be counted per cycle.

#### Scenario: Written file matches the format the offline harness requires

- **WHEN** a cycle is archived
- **THEN** the resulting file SHALL report 1 channel, a 12 000 Hz sample rate, 16 bits per sample,
  and exactly 180 000 frames when read by a standard WAV reader

#### Scenario: Full-scale samples clamp rather than wrap

- **WHEN** a window contains sample values of `+1.5` and `-1.5`
- **THEN** the written samples SHALL be `32767` and `-32768` respectively, and the cycle's clipped
  sample count SHALL be 2

#### Scenario: Archived audio decodes back to the same messages

- **WHEN** a window containing decodable FT8 signals is archived and the written file is then read
  back and passed to `Ft8Decoder`
- **THEN** the decoded message set SHALL equal the message set decoded from the original in-memory
  window

---

### Requirement: Archiving never blocks or perturbs the decode pipeline

All archive file I/O SHALL be performed on a dedicated background writer, not on the decode pump.
The decode pump SHALL hand off each candidate window by a non-blocking call and SHALL NOT await any
file operation. When the archive's internal queue cannot accept a window, the window SHALL be
dropped rather than blocking the pump.

#### Scenario: A stalled disk does not stall decoding

- **WHEN** the archive writer is blocked on a file operation that does not complete
- **THEN** the decode pump SHALL continue to decode, publish and log subsequent cycles without
  delay

#### Scenario: Enqueue is non-blocking when the queue is full

- **WHEN** the archive queue is at capacity and a further window is offered
- **THEN** the offering call SHALL return without blocking

---

### Requirement: Archive loss is counted and reported, never silent

Every path by which a window can fail to be archived SHALL increment a counter that is observable
by the operator. The implementation SHALL NOT rely on `ChannelWriter.TryWrite`'s return value to
detect a drop on a channel configured with any `BoundedChannelFullMode` drop mode, because such
channels never fail a write. The dropped-cycle count SHALL be logged at Warning on the first drop
and periodically thereafter, and SHALL be exposed on the daemon status endpoint.

#### Scenario: A dropped cycle increments an observable counter

- **WHEN** the archive queue is full and a window is dropped
- **THEN** the dropped-cycle count SHALL increase by one and SHALL be readable from the daemon
  status endpoint

#### Scenario: First drop is logged at Warning

- **WHEN** the first window of a session is dropped by the archive
- **THEN** a Warning-level log entry SHALL be emitted naming the archive and the dropped count

---

### Requirement: Sidecar manifest records per-cycle provenance

When manifest writing is enabled (the default), the archive SHALL maintain a `cycle-archive.csv`
in the archive directory with one row per archived cycle, containing the filename, the cycle-start
timestamp at millisecond precision, the true wall-clock instant at which the window closed, the
decode count, the dial frequency in MHz, the clipped-sample count, and the number of cycles dropped
since the previous row. A header row SHALL be written when the file is created. The manifest SHALL
contain no decoded message text and no callsigns.

#### Scenario: Manifest row is written per archived cycle

- **WHEN** four cycles are archived
- **THEN** the manifest SHALL contain a header row followed by exactly four data rows, in cycle
  order

#### Scenario: Manifest records the framer's off-grid offset

- **WHEN** a cycle whose `cycleStart` label is 5.958 s away from the true 15-second UTC grid is
  archived
- **THEN** the difference between that row's window-closed timestamp and its cycle-start timestamp
  SHALL reflect that offset, without the reader needing to consult the daemon log

#### Scenario: Dropped cycles appear as an explicit gap marker

- **WHEN** three cycles are dropped between two archived cycles
- **THEN** the later archived cycle's row SHALL record a dropped-since-previous count of 3

---

### Requirement: Retention is bounded and deletion is pattern-restricted

The archive SHALL enforce a maximum total size and a maximum file age, deleting oldest-first when
either is exceeded. Deletion SHALL be restricted to files within the configured archive directory
whose names match the archive's own naming pattern; the archive SHALL NOT delete any other file.
When free disk space on the archive volume falls below a documented floor, the archive SHALL stop
writing for the remainder of the session and log a Warning.

#### Scenario: Oldest files are removed when the size cap is exceeded

- **WHEN** the configured maximum size is exceeded after writing a new file
- **THEN** the oldest archived files SHALL be deleted until the total is within the cap, and newer
  files SHALL be retained

#### Scenario: Unrelated files in the archive directory are never deleted

- **WHEN** the archive directory also contains a file that does not match the archive naming
  pattern, and a retention sweep runs that would otherwise clear the directory
- **THEN** that file SHALL remain untouched

#### Scenario: Archiving stops when the disk is nearly full

- **WHEN** free space on the archive volume falls below the documented floor
- **THEN** no further files SHALL be written for the remainder of the session and a Warning SHALL
  be logged

---

### Requirement: Archive location defaults outside the repository

When no directory is configured, the archive SHALL resolve to a platform-appropriate per-user
application data directory, consistent with the daemon's existing configuration path resolution,
and SHALL NOT default to the repository or the executable directory. Recordings contain real
off-air audio and real third-party callsigns (NFR-021).

#### Scenario: Unconfigured directory resolves to the platform config location

- **WHEN** the mode is set to `All` with no directory configured
- **THEN** files SHALL be written beneath the platform per-user application data directory for
  OpenWSFZ, not beneath the repository or the executable directory

---

### Requirement: Filename collisions never overwrite an existing recording

The archive SHALL NOT overwrite an existing recording. When a target filename already exists, the
archive SHALL write to a suffixed name instead, preserving both recordings. This case is reachable
because the decode-cycle boundary correction can move the reported `cycleStart` backwards such that
two windows produce the same timestamp label.

#### Scenario: Repeated cycle label produces two files

- **WHEN** two windows are archived with the same `cycleStart` label
- **THEN** two distinct files SHALL exist and neither SHALL have been overwritten
