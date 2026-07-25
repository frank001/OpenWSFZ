# Tasks — `cycle-audio-archive`

**Authored by:** QA (per HK-015 — the Architect hands QA material, QA writes `tasks.md`).
**Source:** `architect-to-qa-handoff.md` Appendix A, reviewed and adopted. Every codebase claim in
this file (file paths, line numbers, existing patterns) was independently re-verified against the
tree on 2026-07-25 before issue, not merely inherited — see §0.

## 0. Provenance and scope

- [x] 0.1 Branch created off `main` (not off the paused `docs/propose-fix-cycle-boundary-clock-drift`,
      per the handoff §2.1): `docs/propose-cycle-audio-archive`. Cherry-picked `f8461d5` (findings
      doc + three probe scripts) and the three `cycle-audio-archive` proposal commits (`d1b1027`,
      `ec08753`, `47e353e`) from PR #108, in that order. All four applied cleanly, no conflicts.
      The paused branch's uncommitted `CycleFramer.cs`/`CycleFramerTests.cs` diff (attempt #4/§10's
      fix, HK-011 hold) was stashed before each branch switch and restored byte-identical afterward
      (`git diff --stat` confirmed unchanged: 442 insertions/16 deletions across the same two files)
      — it does not exist on this branch and was never at risk.
- [x] 0.2 `openspec validate --strict --all`: 57/57 on this branch, confirming the Architect's claim
      that validity does not depend on a `tasks.md` being present at proposal time.
- [x] 0.3 Spot-verified every file:line claim in `architect-to-qa-handoff.md` Appendix B against the
      current tree before adopting it below: `DecodeNoiseSuppressionConfig.cs`'s `[JsonConstructor]`
      pattern, `WorkedBeforeState.cs`'s enum-wire-value remarks, `OpenWSFZ.Daemon.csproj:18`'s
      `PublishAot` condition, `OpenWSFZ.Audio.csproj:27`'s NAudio Windows-only condition,
      `JsonConfigStore.cs:143/156`'s null-backfill pattern, and `WasapiAudioSource.cs:165`'s
      unreachable `TryWrite` guard — all confirmed exactly as described. Also located the precise
      decode-pump insertion point independently: `Program.cs:746` (`DecodeAsync` returns) /
      `:758` (`AllTxtWriter.AppendAsync` call to sit alongside).

## 1. Configuration model

- [ ] 1.1 Add `CycleAudioArchiveMode` enum (`Off`, `All`, `Decoded`, `NoDecodes`) and
      `CycleAudioArchiveConfig` record to `OpenWSFZ.Abstractions`, modelled on `DecodeLogConfig`
      (`src/OpenWSFZ.Abstractions/DecodeLogConfig.cs`). Apply the `[JsonConstructor]` +
      explicit-parameter-defaults pattern `DecodeNoiseSuppressionConfig.cs:14-27` documents —
      `MaxSizeMb` (2048), `MaxAgeHours` (168) and `WriteManifest` (true) all have non-CLR-zero
      defaults and will silently deserialise to `0`/`false` without it (design.md Decision 8).
- [ ] 1.2 Add `CycleAudioArchive` to `AppConfig`, register both new types in `ConfigJsonContext`
      with `[JsonSerializable]` (design.md Decision 8; `OpenWSFZ.Daemon.csproj:18` sets
      `PublishAot=true` whenever a `RuntimeIdentifier` is set — an AOT publish, not a build, is
      where a missed registration surfaces), and add the null-backfill entry in
      `JsonConfigStore.cs` alongside the existing `DecodeLog`/`DecodeNoiseSuppression` entries
      (`:143`, `:156`).
- [ ] 1.3 Add default-directory resolution using the same platform logic as `ConfigPathResolver`
      (`%AppData%\OpenWSFZ\cycle-audio\` on Windows, `~/.config/OpenWSFZ/cycle-audio/` elsewhere).
      Assert in a test that the resolved default is **not** under the repository or the executable
      directory (NFR-021, design.md Decision 8).
- [ ] 1.4 Add `cycle-audio/` and `cycle-archive.csv` to `.gitignore` as defence in depth.
- [ ] 1.5 Pin the enum's wire values explicitly:
      `[JsonConverter(typeof(JsonStringEnumConverter<CycleAudioArchiveMode>))]` (the **generic**
      form — the non-generic one is not AOT-safe) plus an explicit `[JsonStringEnumMemberName]` on
      each member (`"off"`/`"all"`/`"decoded"`/`"noDecodes"`, matching this project's lowerCamelCase
      wire convention). `WorkedBeforeState.cs:11-30`'s remarks document this exact mistake shipping
      once and blanking every worked-before indicator in the live UI — do not rely on
      `AppJsonContext`'s `CamelCase` property-naming policy, it does not touch enum *values*.

## 2. WAV encoding

- [ ] 2.1 Implement `CycleWavWriter` — canonical 44-byte RIFF/WAVE header, 12 kHz mono 16-bit,
      exactly 180 000 frames. **No NAudio** (`OpenWSFZ.Audio.csproj:27` package-references it under
      `Condition="$([MSBuild]::IsOSPlatform('Windows'))"`; a `WaveFileWriter` call breaks the Linux
      `arecord`/macOS `sox` builds). A canonical header against `System.IO` is ~40 lines.
- [ ] 2.2 Implement float→int16 conversion:
      `(short)Math.Clamp(MathF.Round(sample * 32767f), -32768f, 32767f)`, with a per-cycle
      clipped-sample count (design.md Decision 4).
- [ ] 2.3 Unit tests: header field correctness (RIFF/WAVE/fmt/data chunk sizes, channels, rate,
      bits); exact frame count; clamping of `+1.5`/`-1.5` to `32767`/`-32768` with clip count 2;
      round-trip of a known sample pattern.

## 3. Archive service

- [ ] 3.1 Implement `CycleArchiveService` with a bounded queue (capacity 8) and a dedicated
      background writer task. `TryEnqueue(pcm, cycleStart, closedUtc, decodeCount, dialMhz)` SHALL
      be non-blocking and SHALL NOT be awaited by any caller (design.md Decision 2).
- [ ] 3.2 Channel config: `FullMode = BoundedChannelFullMode.DropWrite`. Implement drop counting
      **without relying on `TryWrite`'s return value** — all three drop modes (`DropOldest`,
      `DropNewest`, `DropWrite`) make `TryWrite` return `true` unconditionally in .NET. Compare
      queue count against capacity *before* writing and increment `DroppedCycles` explicitly. Add a
      code comment naming `WasapiAudioSource.cs:165`'s unreachable-warning defect
      (`if (!innerChannel.Writer.TryWrite(chunk))` on a `DropOldest` channel — verified 2026-07-25,
      dead code) as the reason this capability counts drops explicitly instead (design.md
      Decision 3). **No drop path in this capability may be uncounted — standing rule.**
- [ ] 3.3 Log the dropped count at Warning on first drop and every 100th thereafter; expose it on
      the daemon status endpoint.
- [ ] 3.4 Implement mode selection (`Off`/`All`/`Decoded`/`NoDecodes`) against the decode count.
- [ ] 3.5 Implement filename collision handling — suffix `_2`, `_3`, …; never overwrite; log at
      Debug (design.md Decision 5). Reachable because the (paused) drift correction can move
      `cycleStart` backwards, producing a repeated label.
- [ ] 3.6 Unit tests for 3.1-3.5, including a stalled-writer test asserting the pump-side enqueue
      returns promptly and the drop counter increments.

## 4. Manifest

- [ ] 4.1 Implement `cycle-archive.csv` append with header-on-create and columns per design.md
      Decision 6: `filename,cycle_start_utc,window_closed_utc,decode_count,dial_mhz,clipped_samples,dropped_before`.
- [ ] 4.2 Assert in a test that no decoded message text or callsign can reach the manifest
      (NFR-021).
- [ ] 4.3 Unit tests: header written once; one row per archived cycle in order; gap marker
      (`dropped_before`) after simulated drops; `window_closed_utc − cycle_start_utc` reflects a
      synthetic off-grid offset.

## 5. Retention

- [ ] 5.1 Implement size-cap (`MaxSizeMb`, default 2048) and age-cap (`MaxAgeHours`, default 168)
      enforcement, oldest-first, swept every 100 cycles on the writer task (design.md Decision 7).
- [ ] 5.2 Restrict deletion to the configured directory and the archive's own
      `YYMMDD_HHMMSS[_n].wav` pattern. **Never a directory wipe** — an operator pointing the setting
      at a populated folder must not lose data.
- [ ] 5.3 Implement the free-space floor (500 MB): stop archiving for the remainder of the session,
      log Warning.
- [ ] 5.4 Unit tests: size cap deletes oldest and retains newest; age cap; a non-matching file in
      the archive directory survives a sweep that would otherwise clear it; free-space floor halts
      writing.

## 6. Pipeline integration

- [ ] 6.1 Register `CycleArchiveService` in DI and start/stop it with the daemon lifetime.
- [ ] 6.2 Add the single `TryEnqueue` call to the `Program.cs` decode pump, immediately after
      `DecodeAsync` returns (`Program.cs:746`), positioned alongside the existing
      `AllTxtWriter.AppendAsync` call (`:758`). **Do not await it.**
- [ ] 6.3 Confirm by test that with mode `Off` the pump's added cost is one configuration test and
      no file-system access of any kind occurs.
- [ ] 6.4 **Do not modify `CycleFramer.cs`.** It carries an active, uncommitted, HK-011-held diff on
      a different branch (`docs/propose-fix-cycle-boundary-clock-drift`) and is the subject of an
      unresolved investigation. If a change there seems necessary to complete this section, stop
      and escalate rather than proceeding.

## 7. Integration test

- [ ] 7.1 End-to-end test: feed a synthetic window containing known FT8 signals through the pump
      with mode `All`, read the written file back, decode it with `Ft8Decoder`, and assert the
      message set matches the in-memory decode (spec scenario "Archived audio decodes back to the
      same messages").
- [ ] 7.2 Verify the written file is accepted by the existing QA harness contract — mono, 12 kHz,
      16-bit, exactly 180 000 frames — the assertion `rewindow.py` and `D001ParamSweep` already
      make, so the alignment-replay study can read this archive's output with zero changes.

## 8. Closeout (Developer-session responsibility, before handing back to QA)

- [ ] 8.1 Run `python3 tools/pre_merge_check.py` (HK-006) before any "ready" claim — G9a, Release
      build+tests, G3 traceability, G8 openspec validate, G9b, AOT publish (this is where a missed
      §1.2 registration would otherwise surface unexpectedly late).
- [ ] 8.2 Confirm no UI control was added anywhere (design.md Decision 9 — the GUI is a separate,
      later, GUI-focused change; standing convention: controls appear only once their backend is
      fully implemented and testable end-to-end).
- [ ] 8.3 Confirm `git status` shows no `.wav`, no `cycle-archive.csv`, and no `cycle-audio/`
      directory tracked (NFR-021 — recordings carry real third-party callsigns).
- [ ] 8.4 Per HK-011: present the `src/` diff to the Captain for explicit pre-push sign-off before
      pushing. Per HK-010: `gh pr merge` always needs the Captain's explicit sign-off, green CI
      notwithstanding.

## 9. QA's own follow-on work — not part of the Developer handoff, do not implement in §1-8

This is the reason the feature exists. It is QA-scoped (live radio time + the existing offline
harness, zero further `src/` changes) and runs **after** §1-8 merge, per
`architect-to-qa-handoff.md` §2.4-2.6.

- [ ] 9.1 Run ~20 minutes of live capture with mode `All`, on an open band, while WSJT-X records the
      same audio concurrently.
- [ ] 9.2 Decode both directories with the same `Ft8Decoder` at the same settings using the existing
      `run_phase.py` harness — **unmodified** (design.md Decision 4's whole point).
- [ ] 9.3 Compare per-cycle decode yield between OpenWSFZ's own capture and WSJT-X's capture of the
      same cycles.
      **Materially fewer decodes from our capture ⇒ the defect is in the capture chain**
      (`WasapiAudioSource`'s 48 kHz → left-channel → `WdlResamplingSampleProvider` → 12 kHz path is
      the only non-trivial signal processing there, and is entirely absent from WSJT-X's path).
      **Parity ⇒ the defect is in the live decoder invocation**, and the next probe is a
      process-lifetime/restart-cadence test against `g_session_hash_table` and
      `hashTableRejectCount` (live session final value 25 465, per `f8461d5`'s findings doc).
- [ ] 9.4 Report the verdict in `qa/cycleframer-alignment-replay/` and escalate to the
      Architect/Captain **before any further live endurance time is spent** on
      `fix-cycle-boundary-clock-drift`.
- [ ] 9.5 Decide, with the Captain, what happens to the paused PR #108. The Architect's recorded
      recommendation (`qa/cycleframer-alignment-replay/2026-07-25-1200-architect-second-mechanism-located.md`
      §6): §10's nominal-reset-conflation fix is sound but small (≤4.3% of the zero-decode
      population per the LDPC findings) and should be re-scoped as correctness hygiene rather than
      D-001 recovery. This is a recommendation on record, not a decision QA can make unilaterally.

## 10. Deferred — GUI (separate later change, do not implement here)

Recorded so the intent survives the handoff; see design.md Decision 9.

- Mode selector with plain-language descriptions, particularly for `NoDecodes`, whose value is not
  self-evident from its name.
- Directory picker with an "open folder" affordance.
- Retention controls plus a live "N files, M MB used" readout.
- A one-shot "record the next N cycles" button — the operator-friendly form of §9's capture, which
  avoids leaving `All` mode enabled by accident.
