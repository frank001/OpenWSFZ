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

- [x] 1.1 Add `CycleAudioArchiveMode` enum (`Off`, `All`, `Decoded`, `NoDecodes`) and
      `CycleAudioArchiveConfig` record to `OpenWSFZ.Abstractions`, modelled on `DecodeLogConfig`
      (`src/OpenWSFZ.Abstractions/DecodeLogConfig.cs`). Apply the `[JsonConstructor]` +
      explicit-parameter-defaults pattern `DecodeNoiseSuppressionConfig.cs:14-27` documents —
      `MaxSizeMb` (2048), `MaxAgeHours` (168) and `WriteManifest` (true) all have non-CLR-zero
      defaults and will silently deserialise to `0`/`false` without it (design.md Decision 8).
- [x] 1.2 Add `CycleAudioArchive` to `AppConfig`, register both new types in `ConfigJsonContext`
      with `[JsonSerializable]` (design.md Decision 8; `OpenWSFZ.Daemon.csproj:18` sets
      `PublishAot=true` whenever a `RuntimeIdentifier` is set — an AOT publish, not a build, is
      where a missed registration surfaces), and add the null-backfill entry in
      `JsonConfigStore.cs` alongside the existing `DecodeLog`/`DecodeNoiseSuppression` entries
      (`:143`, `:156`).
- [x] 1.3 Add default-directory resolution using the same platform logic as `ConfigPathResolver`
      (`%AppData%\OpenWSFZ\cycle-audio\` on Windows, `~/.config/OpenWSFZ/cycle-audio/` elsewhere).
      Assert in a test that the resolved default is **not** under the repository or the executable
      directory (NFR-021, design.md Decision 8).
- [x] 1.4 Add `cycle-audio/` and `cycle-archive.csv` to `.gitignore` as defence in depth.
- [x] 1.5 Pin the enum's wire values explicitly:
      `[JsonConverter(typeof(JsonStringEnumConverter<CycleAudioArchiveMode>))]` (the **generic**
      form — the non-generic one is not AOT-safe) plus an explicit `[JsonStringEnumMemberName]` on
      each member (`"off"`/`"all"`/`"decoded"`/`"noDecodes"`, matching this project's lowerCamelCase
      wire convention). `WorkedBeforeState.cs:11-30`'s remarks document this exact mistake shipping
      once and blanking every worked-before indicator in the live UI — do not rely on
      `AppJsonContext`'s `CamelCase` property-naming policy, it does not touch enum *values*.

## 2. WAV encoding

- [x] 2.1 Implement `CycleWavWriter` — canonical 44-byte RIFF/WAVE header, 12 kHz mono 16-bit,
      exactly 180 000 frames. **No NAudio** (`OpenWSFZ.Audio.csproj:27` package-references it under
      `Condition="$([MSBuild]::IsOSPlatform('Windows'))"`; a `WaveFileWriter` call breaks the Linux
      `arecord`/macOS `sox` builds). A canonical header against `System.IO` is ~40 lines.
- [x] 2.2 Implement float→int16 conversion:
      `(short)Math.Clamp(MathF.Round(sample * 32767f), -32768f, 32767f)`, with a per-cycle
      clipped-sample count (design.md Decision 4).
- [x] 2.3 Unit tests: header field correctness (RIFF/WAVE/fmt/data chunk sizes, channels, rate,
      bits); exact frame count; clamping of `+1.5`/`-1.5` to `32767`/`-32768` with clip count 2;
      round-trip of a known sample pattern.

## 3. Archive service

- [x] 3.1 Implement `CycleArchiveService` with a bounded queue (capacity 8) and a dedicated
      background writer task. `TryEnqueue(pcm, cycleStart, closedUtc, decodeCount, dialMhz)` SHALL
      be non-blocking and SHALL NOT be awaited by any caller (design.md Decision 2).
- [x] 3.2 Channel config: `FullMode = BoundedChannelFullMode.DropWrite`. Implement drop counting
      **without relying on `TryWrite`'s return value** — all three drop modes (`DropOldest`,
      `DropNewest`, `DropWrite`) make `TryWrite` return `true` unconditionally in .NET. Compare
      queue count against capacity *before* writing and increment `DroppedCycles` explicitly. Add a
      code comment naming `WasapiAudioSource.cs:165`'s unreachable-warning defect
      (`if (!innerChannel.Writer.TryWrite(chunk))` on a `DropOldest` channel — verified 2026-07-25,
      dead code) as the reason this capability counts drops explicitly instead (design.md
      Decision 3). **No drop path in this capability may be uncounted — standing rule.**
- [x] 3.3 Log the dropped count at Warning on first drop and every 100th thereafter; expose it on
      the daemon status endpoint.
- [x] 3.4 Implement mode selection (`Off`/`All`/`Decoded`/`NoDecodes`) against the decode count.
- [x] 3.5 Implement filename collision handling — suffix `_2`, `_3`, …; never overwrite; log at
      Debug (design.md Decision 5). Reachable because the (paused) drift correction can move
      `cycleStart` backwards, producing a repeated label.
- [x] 3.6 Unit tests for 3.1-3.5, including a stalled-writer test asserting the pump-side enqueue
      returns promptly and the drop counter increments.

## 4. Manifest

- [x] 4.1 Implement `cycle-archive.csv` append with header-on-create and columns per design.md
      Decision 6: `filename,cycle_start_utc,window_closed_utc,decode_count,dial_mhz,clipped_samples,dropped_before`.
- [x] 4.2 Assert in a test that no decoded message text or callsign can reach the manifest
      (NFR-021).
- [x] 4.3 Unit tests: header written once; one row per archived cycle in order; gap marker
      (`dropped_before`) after simulated drops; `window_closed_utc − cycle_start_utc` reflects a
      synthetic off-grid offset.

## 5. Retention

- [x] 5.1 Implement size-cap (`MaxSizeMb`, default 2048) and age-cap (`MaxAgeHours`, default 168)
      enforcement, oldest-first, swept every 100 cycles on the writer task (design.md Decision 7).
- [x] 5.2 Restrict deletion to the configured directory and the archive's own
      `YYMMDD_HHMMSS[_n].wav` pattern. **Never a directory wipe** — an operator pointing the setting
      at a populated folder must not lose data.
- [x] 5.3 Implement the free-space floor (500 MB): stop archiving for the remainder of the session,
      log Warning.
- [x] 5.4 Unit tests: size cap deletes oldest and retains newest; age cap; a non-matching file in
      the archive directory survives a sweep that would otherwise clear it; free-space floor halts
      writing.

## 6. Pipeline integration

- [x] 6.1 Register `CycleArchiveService` in DI and start/stop it with the daemon lifetime.
- [x] 6.2 Add the single `TryEnqueue` call to the `Program.cs` decode pump, immediately after
      `DecodeAsync` returns (`Program.cs:746`), positioned alongside the existing
      `AllTxtWriter.AppendAsync` call (`:758`). **Do not await it.**
- [x] 6.3 Confirm by test that with mode `Off` the pump's added cost is one configuration test and
      no file-system access of any kind occurs.
- [x] 6.4 **Do not modify `CycleFramer.cs`.** It carries an active, uncommitted, HK-011-held diff on
      a different branch (`docs/propose-fix-cycle-boundary-clock-drift`) and is the subject of an
      unresolved investigation. If a change there seems necessary to complete this section, stop
      and escalate rather than proceeding.

## 7. Integration test

- [x] 7.1 End-to-end test: feed a synthetic window containing known FT8 signals through the pump
      with mode `All`, read the written file back, decode it with `Ft8Decoder`, and assert the
      message set matches the in-memory decode (spec scenario "Archived audio decodes back to the
      same messages").
      **Done (deviation recorded):** implemented as `CycleAudioArchiveRoundTripTests.cs` in
      `OpenWSFZ.Ft8.Tests` exercising `CycleWavWriter.Encode` → file write → `WavReader.Read` →
      `Ft8Decoder.DecodeAsync`, rather than literally routing through the live `Program.cs` decode
      pump (which is inline top-level statements, not unit-testable in isolation). Source PCM is
      the committed `synth-qso-01` fixture (same one `RealSignalFixtureTests`/G6 uses) rather than
      a freshly-packed `TestFt8Encoder` signal: `Ft8DecoderFixtureTests`' own remarks note that
      `TestFt8Encoder.PackType1`'s payload (i3=0) is rejected by the native decoder for correctness
      purposes, making it unsuitable as a "must actually decode" source — the fixture sidesteps
      that entirely since it is already known-decodable. The pump-side wiring itself (the
      `TryEnqueue` call and `Off`-mode no-op) is covered separately by `CycleArchiveServiceTests.cs`
      (task 3.6) and the pipeline-integration code in `Program.cs` (task 6.2).
- [x] 7.2 Verify the written file is accepted by the existing QA harness contract — mono, 12 kHz,
      16-bit, exactly 180 000 frames — the assertion `rewindow.py` and `D001ParamSweep` already
      make, so the alignment-replay study can read this archive's output with zero changes.
      **Done:** covered by the same test via `WavReader.Read` (which enforces this exact contract,
      throwing `InvalidDataException` otherwise) plus an explicit 180 000-frame count assertion.

## 8. Closeout (Developer-session responsibility, before handing back to QA)

- [x] 8.1 Run `python3 tools/pre_merge_check.py` (HK-006) before any "ready" claim — G9a, Release
      build+tests, G3 traceability, G8 openspec validate, G9b, AOT publish (this is where a missed
      §1.2 registration would otherwise surface unexpectedly late).
      **Verified by QA post-merge (2026-07-25), retroactively checking the boxes this section left
      unticked:** PR #109's own "Test plan" checklist records all 10 gates PASS (build, full test
      suite — Web.Tests 262/262, Daemon.Tests 587/587, Ft8.Tests 295/295 — G3 traceability, WSL
      Debian compile+test, G8 `openspec validate`, self-contained publish, AOT publish).
- [x] 8.2 Confirm no UI control was added anywhere (design.md Decision 9 — the GUI is a separate,
      later, GUI-focused change; standing convention: controls appear only once their backend is
      fully implemented and testable end-to-end).
      **Verified by QA post-merge:** `grep -rli CycleAudioArchive web/ src/OpenWSFZ.Daemon/wwwroot`
      on current `main` returns nothing.
- [x] 8.3 Confirm `git status` shows no `.wav`, no `cycle-archive.csv`, and no `cycle-audio/`
      directory tracked (NFR-021 — recordings carry real third-party callsigns).
      **Verified by QA post-merge:** the only tracked `.wav` files on `main` are the pre-existing
      `tests/OpenWSFZ.Ft8.Tests/Fixtures/synth-qso-0{1,2,3}.wav` synthetic fixtures; no
      `cycle-archive.csv` or `cycle-audio/` tracked anywhere. `Mode` defaults to
      `CycleAudioArchiveMode.Off` (`CycleAudioArchiveConfig.cs`).
- [x] 8.4 Per HK-011: present the `src/` diff to the Captain for explicit pre-push sign-off before
      pushing. Per HK-010: `gh pr merge` always needs the Captain's explicit sign-off, green CI
      notwithstanding.
      **Verified by QA post-merge:** PR #109's "Test plan" checklist records both sign-offs
      granted; PR merged 2026-07-25T17:40:56Z as `027ce22`.

## 9. QA's own follow-on work — not part of the Developer handoff, do not implement in §1-8

This is the reason the feature exists. It is QA-scoped (live radio time + the existing offline
harness, zero further `src/` changes) and runs **after** §1-8 merge, per
`architect-to-qa-handoff.md` §2.4-2.6.

- [x] 9.1 Run ~20 minutes of live capture with mode `All`, on an open band, while WSJT-X records the
      same audio concurrently.
      **Done, 2026-07-25 20:06-20:27 local, 40 m (7.074 MHz dial), "Microphone (2- USB Audio
      CODEC )":** ~20.5 minutes, mode `All` set live via `POST /api/v1/config` (no restart —
      `CycleArchiveService` reads `IConfigStore.Current` per cycle), `DroppedCycles: 0`
      throughout, zero clipped samples/gaps in `cycle-archive.csv`. Reverted to `Off` once the
      target was met.
- [x] 9.2 Decode both directories with the same `Ft8Decoder` at the same settings using the existing
      `run_phase.py` harness — **unmodified** (design.md Decision 4's whole point).
      **Deviation recorded:** used `D001ParamSweep` directly (`--points k10_c0.10_n60`
      matching production `config.json` exactly, `--dial-mhz 7.074`,
      `--fresh-decoder-per-wav`) rather than `run_phase.py`. `run_phase.py` orchestrates
      `rewindow.py`'s delta-*offset* rewindowing on top of `D001ParamSweep` — machinery this
      comparison doesn't need, since both arms already share one filename/timestamp convention
      with no offset between them. `D001ParamSweep` is the actual decode driver `run_phase.py`
      itself calls; "unmodified" is satisfied at that layer. Also restored both tools from the
      paused PR #108 branch to `main` first (commit `009199f`) — they only existed there.
- [x] 9.3 Compare per-cycle decode yield between OpenWSFZ's own capture and WSJT-X's capture of the
      same cycles.
      **Materially fewer decodes from our capture ⇒ the defect is in the capture chain**
      (`WasapiAudioSource`'s 48 kHz → left-channel → `WdlResamplingSampleProvider` → 12 kHz path is
      the only non-trivial signal processing there, and is entirely absent from WSJT-X's path).
      **Parity ⇒ the defect is in the live decoder invocation**, and the next probe is a
      process-lifetime/restart-cadence test against `g_session_hash_table` and
      `hashTableRejectCount` (live session final value 25 465, per `f8461d5`'s findings doc).
      **Result: PARITY.** 68 filename-matched cycles: 1284 vs. 1288 total decodes (0.3%
      apart), ~94% message-level overlap each direction, **zero** cycles where one side found
      signals and the other found none. Full detail:
      `qa/cycleframer-alignment-replay/2026-07-25-2030-cycle-audio-archive-parity-result.md`.
      **Addendum (§3a of that doc):** cross-checked against the Captain-gathered live
      real-time `ALL.TXT`s (`artefacts/20260725_live_run_1806/`, git-ignored). Live OpenWSFZ
      decode vs. offline re-decode of its own captured audio: 0.995 (no live-invocation
      shortfall visible at this scale). Live WSJT-X vs. our `Ft8Decoder` re-decoding WSJT-X's
      own audio: 1.575 — the pre-existing, already-tracked decoder-sensitivity gap (D-001's
      original finding), **not** a capture-chain or cycle-boundary signal; confirmed
      decoder-tracking, not capture-tracking, since it reproduces even on WSJT-X's own audio.
      **Second addendum (2026-07-25 21:45):** raw-waveform cross-correlation of the same 68
      pairs (no decoder involved at all — PCM samples only), reported in
      `qa/cycleframer-alignment-replay/2026-07-25-2145-raw-audio-crosscorrelation-check.md`.
      11/68 pairs contain a signal strong enough to lock a clean correlation peak (>0.95); all
      11, independently, land on a lag ≡4 (mod 12) samples — i.e. a fixed 0.333 ms sub-ms
      residual with only whole-millisecond jitter varying between them, and **no trend with
      elapsed session time**. This corroborates capture-chain parity on a second, independent
      line of evidence (raw signal alignment, not decoded message counts) and specifically rules
      out an accumulating clock-rate error in `WasapiAudioSource`'s resampling path over this
      session's ~21-minute span. The remaining 57/68 pairs are inconclusive (not contradictory)
      by this time-domain method — most 15 s windows are noise-dominated in raw amplitude terms
      even when they contain decodable FT8 signal, so a clean lag only resolves when one signal
      is strong enough to also dominate in the time domain. A frequency-domain (band-limited
      coherence) refinement could sharpen those 57 further; not attempted, flagged only.
- [x] 9.4 Report the verdict in `qa/cycleframer-alignment-replay/` and escalate to the
      Architect/Captain **before any further live endurance time is spent** on
      `fix-cycle-boundary-clock-drift`.
      **Done:** `2026-07-25-2030-cycle-audio-archive-parity-result.md`. Verdict: capture chain
      exonerated (at this ~20-minute session scale); next probe per the Architect's own decision
      tree is process-lifetime/restart-cadence, not `WasapiAudioSource`. That next probe is
      new, unscoped work — not started here.
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
