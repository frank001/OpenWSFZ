## 1. Configuration model

- [ ] 1.1 Add `CycleAudioArchiveMode` enum (`Off`, `All`, `Decoded`, `NoDecodes`) and
      `CycleAudioArchiveConfig` record to `OpenWSFZ.Abstractions`, modelled on
      `DecodeLogConfig`. Apply the `[JsonConstructor]` + explicit-parameter-defaults pattern that
      `DecodeNoiseSuppressionConfig` documents — `MaxSizeMb` (2048), `MaxAgeHours` (168) and
      `WriteManifest` (true) all have non-CLR-zero defaults and will silently deserialise to
      `0`/`false` without it (design.md Decision 8).
- [ ] 1.2 Add `CycleAudioArchive` to `AppConfig`, register both new types in `ConfigJsonContext`,
      and add the null-backfill entry in `JsonConfigStore` alongside the existing `DecodeLog` and
      `DecodeNoiseSuppression` entries.
- [ ] 1.3 Add default-directory resolution using the same platform logic as `ConfigPathResolver`
      (`%AppData%\OpenWSFZ\cycle-audio\` on Windows, `~/.config/OpenWSFZ/cycle-audio/` elsewhere).
      Assert in a test that the resolved default is **not** under the repository or the executable
      directory (NFR-021, design.md Decision 8).
- [ ] 1.4 Add `cycle-audio/` and `cycle-archive.csv` to `.gitignore` as defence in depth against an
      operator pointing the setting at the repo.

## 2. WAV encoding

- [ ] 2.1 Implement `CycleWavWriter` — canonical 44-byte RIFF/WAVE header, 12 kHz mono 16-bit,
      exactly 180 000 frames. No NAudio dependency (Windows-only; this must stay cross-platform).
- [ ] 2.2 Implement float→int16 conversion with clamping and a per-cycle clipped-sample count
      (design.md Decision 4).
- [ ] 2.3 Unit tests: header field correctness (RIFF/WAVE/fmt/data chunk sizes, channels, rate,
      bits); exact frame count; clamping of `+1.5`/`-1.5` to `32767`/`-32768` with clip count 2;
      round-trip of a known sample pattern.

## 3. Archive service

- [ ] 3.1 Implement `CycleArchiveService` with a bounded queue (capacity 8) and a dedicated
      background writer task. `TryEnqueue` SHALL be non-blocking (design.md Decision 2).
- [ ] 3.2 Implement drop counting **without relying on `TryWrite`'s return value** — compare count
      against capacity before writing and increment `DroppedCycles` explicitly. Add a code comment
      naming the `WasapiAudioSource` unreachable-warning defect this exists to avoid repeating
      (design.md Decision 3).
- [ ] 3.3 Log the dropped count at Warning on first drop and every 100th thereafter; expose it on
      the daemon status endpoint.
- [ ] 3.4 Implement mode selection (`Off`/`All`/`Decoded`/`NoDecodes`) against the decode count.
- [ ] 3.5 Implement filename collision handling — suffix `_2`, `_3`, …; never overwrite; log at
      Debug (design.md Decision 5).
- [ ] 3.6 Unit tests for 3.1–3.5, including a stalled-writer test asserting the pump-side enqueue
      returns promptly and that the drop counter increments.

## 4. Manifest

- [ ] 4.1 Implement `cycle-archive.csv` append with header-on-create and the columns in design.md
      Decision 6, including `dropped_before` as an explicit gap marker.
- [ ] 4.2 Assert in a test that no decoded message text or callsign can reach the manifest
      (NFR-021).
- [ ] 4.3 Unit tests: header written once; one row per archived cycle in order; gap marker after
      simulated drops; `window_closed_utc − cycle_start_utc` reflects a synthetic off-grid offset.

## 5. Retention

- [ ] 5.1 Implement size-cap and age-cap enforcement, oldest-first, swept every 100 cycles on the
      writer task (design.md Decision 7).
- [ ] 5.2 Restrict deletion to the configured directory and the archive's own
      `YYMMDD_HHMMSS[_n].wav` pattern. **Never a directory wipe.**
- [ ] 5.3 Implement the free-space floor (500 MB): stop archiving for the session, log Warning.
- [ ] 5.4 Unit tests: size cap deletes oldest and retains newest; age cap; a non-matching file in
      the archive directory survives a sweep that would otherwise clear it; free-space floor halts
      writing.

## 6. Pipeline integration

- [ ] 6.1 Register `CycleArchiveService` in DI and start/stop it with the daemon lifetime.
- [ ] 6.2 Add the single `TryEnqueue` call to the `Program.cs` decode pump immediately after
      `DecodeAsync` returns, positioned alongside the existing `AllTxtWriter.AppendAsync` call.
      **Do not await it.**
- [ ] 6.3 Confirm by test that with mode `Off` the pump's added cost is one configuration test and
      no file-system access of any kind occurs.
- [ ] 6.4 **Do not modify `CycleFramer`.** It is the subject of an active unresolved investigation
      (`fix-cycle-boundary-clock-drift`) and this change must not perturb it.

## 7. Integration test

- [ ] 7.1 End-to-end test: feed a synthetic window containing known FT8 signals through the pump
      with mode `All`, read the written file back, decode it with `Ft8Decoder`, and assert the
      message set matches the in-memory decode (spec: "Archived audio decodes back to the same
      messages").
- [ ] 7.2 Verify the written file is accepted by the existing QA harness contract — mono, 12 kHz,
      16-bit, exactly 180 000 frames — the assertion `rewindow.py` and `D001ParamSweep` already
      make.

## 8. D-001 diagnostic — the reason this is being built now

- [ ] 8.1 With Phase 1 merged, run ~20 minutes of live capture with mode `All` while WSJT-X records
      the same audio concurrently, on an open band.
- [ ] 8.2 Decode both directories with the same `Ft8Decoder` at the same settings using the
      existing `run_phase.py` harness — unmodified, per design.md Decision 4.
- [ ] 8.3 Compare per-cycle decode yield between OpenWSFZ's own capture and WSJT-X's capture of the
      same cycles. **Materially fewer decodes from our capture ⇒ the defect is in the capture
      chain** (`WasapiAudioSource`'s 48 kHz → left-channel → `WdlResamplingSampleProvider` → 12 kHz
      path is the only non-trivial signal processing there, and is absent from WSJT-X's).
      **Parity ⇒ the defect is in the live decoder invocation**, and the next probe is a
      process-lifetime/restart-cadence test against `g_session_hash_table` and
      `hashTableRejectCount`.
- [ ] 8.4 Record the verdict in `qa/cycleframer-alignment-replay/` and report to the Captain before
      any further live endurance time is spent.

## 9. Closeout

- [ ] 9.1 Run `python3 tools/pre_merge_check.py` (HK-006) before any "ready" claim.
- [ ] 9.2 Confirm no UI control was added anywhere (design.md Decision 9 — the GUI is a separate
      later change; the standing convention is that controls appear only once the backend is fully
      implemented and testable end-to-end).
- [ ] 9.3 Confirm `git status` shows no `.wav`, no `cycle-archive.csv`, and no `cycle-audio/`
      directory tracked (NFR-021).

## 10. Deferred — GUI (separate change, do not implement here)

Recorded so the intent survives the handoff; see design.md Decision 9.

- Mode selector with plain-language descriptions, particularly for `NoDecodes`, whose value is not
  self-evident from its name.
- Directory picker with an "open folder" affordance.
- Retention controls plus a live "N files, M MB used" readout.
- A one-shot "record the next N cycles" button — the operator-friendly form of task 8.1, which
  avoids leaving `All` mode enabled by accident.
