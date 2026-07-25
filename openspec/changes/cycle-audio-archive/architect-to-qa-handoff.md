# Architect → QA handoff: `cycle-audio-archive`

**Prepared by:** Architect
**Date:** 2026-07-25
**Change:** `openspec/changes/cycle-audio-archive/` (`proposal.md`, `design.md`, `specs/`)
**Direction from the Captain (2026-07-25):** option 1 — pause the `CycleFramer` thread, chase the
capture chain, and build the WAV saving as **a real feature with GUI options, not throwaway
diagnostic code**. The GUI half is deliberately parked for a later GUI-focused session.

**Chain discipline (HK-015).** This document goes Architect → QA and stops. The Architect does not
author `tasks.md` and does not author `dev-tasks/*.md`; **both are QA's to write and issue.**
Everything below marked *material* is raw input for QA to use, revise or discard — it is not an
instruction to the Developer, and the Architect has not issued one. Escalation runs the chain in
reverse: Developer → QA → Architect.

---

## 1. What is ready

`proposal.md`, `design.md` and `specs/cycle-audio-archive/spec.md` are complete and
Architect-ratified. `openspec validate --strict --all` passes 58/58 **without a `tasks.md`** —
validity does not depend on it, so QA is free to structure the task breakdown however it sees fit.

`design.md` carries nine settled decisions, each recording why the alternatives were rejected.
Those are the contract. QA should not need to re-derive any of them; if one looks wrong, escalate
rather than work around it.

## 2. QA's tasks

- [ ] **2.1 Create the branch.** Captain has approved a fresh branch off `main` (confirmed
      2026-07-25, "the fresh branch is ok, no issues"). Cherry-pick **both** commits:
      `f8461d5` (the findings doc + three probe scripts) and the `cycle-audio-archive` proposal
      commits. Both currently sit on `docs/propose-fix-cycle-boundary-clock-drift` (PR #108),
      which is **paused** and carries an uncommitted `CycleFramer` diff under an HK-011 hold —
      this change must not inherit that hold, and the `CycleFramer` diff must survive untouched.
      Taking `f8461d5` matters: if it stays only on #108 and #108 never merges, `proposal.md`'s
      central citation dangles on `main` and the probes are lost with it.
- [ ] **2.2 Author `tasks.md`** for the change. Appendix A is suggested material.
- [ ] **2.3 Author the Developer handoff** (`dev-tasks/*.md` per HK-000) if QA judges one is
      needed. Appendix B is suggested material — nine codebase landmines, each verified against
      the current tree on 2026-07-25.
- [ ] **2.4 Run the D-001 diagnostic once the feature has merged.** This is QA's own work, not the
      Developer's — it needs live radio time and the offline harness, not `src/` changes. See §3.
- [ ] **2.5 Report the diagnostic verdict** in `qa/cycleframer-alignment-replay/` and escalate to
      the Architect/Captain **before any further live endurance time is spent** on
      `fix-cycle-boundary-clock-drift`.
- [ ] **2.6 Decide what happens to PR #108.** It is paused, not abandoned. The Architect's
      recommendation is on record in
      `qa/cycleframer-alignment-replay/2026-07-25-1200-architect-second-mechanism-located.md` §6:
      10.1–10.4 are sound but small (≤4.3 % of the zero-decode population), and should be
      re-scoped as correctness hygiene rather than D-001 recovery. That is a recommendation, not a
      decision — it needs the Captain.

## 3. The diagnostic this feature exists to enable (QA task 2.4)

Once `All` mode ships:

1. Run ~20 minutes of live capture with mode `All`, on an open band, while WSJT-X records the same
   audio concurrently.
2. Decode both directories with the same `Ft8Decoder` at the same settings using the existing
   `run_phase.py` harness — **unmodified**. This works because `design.md` Decision 4 pins the
   archive format to the contract `rewindow.py` and `D001ParamSweep` already assert (mono, 12 kHz,
   16-bit, exactly 180 000 frames).
3. Compare per-cycle decode yield between OpenWSFZ's capture and WSJT-X's capture of the same
   cycles.

**Materially fewer decodes from our capture ⇒ the defect is in the capture chain.**
`WasapiAudioSource`'s 48 kHz → left-channel → `WdlResamplingSampleProvider` → 12 kHz path is the
only non-trivial signal processing there, and is entirely absent from WSJT-X's path.

**Parity ⇒ the defect is in the live decoder invocation**, and the next probe is a
process-lifetime / restart-cadence test against `g_session_hash_table` and `hashTableRejectCount`
(live session final 25 465).

## 4. Why this is being built now — the one-paragraph version

Full evidence in
`qa/cycleframer-alignment-replay/2026-07-25-1200-architect-second-mechanism-located.md`.

D-001's live-path loss is **not** a cycle-boundary timing defect. From the 0724 session's own logs,
with no new live run: the capture path loses nothing (0 of 2 836 windows lost even one 750-sample
chunk); every framed window reached the decoder (2 682 emitted == 2 682 decoded); the audio on
zero-decode cycles is indistinguishable from the audio on decoding cycles (RMS ratio 1.01, same
noise floor, exactly 180 000 samples every time); and the entire loss sits at LDPC — the candidate
list is saturated at `K_MAX_CANDIDATES = 140` on 99.8 % of zero-decode cycles, so sync **is**
finding the signals, while `failCands` climbs 82 → 136. What remains unknown is why the live path's
audio yields worse LLRs than an offline replay of WSJT-X's capture of the same RF, and answering
that needs OpenWSFZ's own captured audio on disk.

---

# Appendix A — material for `tasks.md` (QA to own, revise, issue)

Not an instruction to the Developer. A suggested sequence only.

**Configuration model.** `CycleAudioArchiveMode` enum + `CycleAudioArchiveConfig` record in
`OpenWSFZ.Abstractions`, modelled on `DecodeLogConfig`. Add to `AppConfig`, register in
`ConfigJsonContext`, add the `JsonConfigStore` null-backfill entry. Default-directory resolution via
the same platform logic as `ConfigPathResolver`, with a test asserting the default is **not** under
the repository or the executable directory (NFR-021). Add `cycle-audio/` and `cycle-archive.csv`
to `.gitignore`.

**WAV encoding.** `CycleWavWriter` — canonical 44-byte RIFF/WAVE header, 12 kHz mono 16-bit,
exactly 180 000 frames, no NAudio. Float→int16 with clamping and a per-cycle clipped-sample count.
Tests: header field correctness, exact frame count, `+1.5`/`-1.5` → `32767`/`-32768` with clip
count 2, round-trip of a known pattern.

**Archive service.** `CycleArchiveService` with a bounded queue (capacity 8) and a dedicated writer
task; non-blocking `TryEnqueue`. Explicit drop counting (see Appendix B.5). Warning on first drop
and every 100th thereafter, exposed on the daemon status endpoint. Mode selection against the
decode count. Filename collision handling — suffix `_2`, `_3`, never overwrite. Tests including a
stalled-writer case asserting the enqueue returns promptly and the drop counter increments.

**Manifest.** `cycle-archive.csv`, header-on-create, columns per `design.md` Decision 6 including
`dropped_before` as an explicit gap marker. Test that no message text or callsign can reach it.
Tests: header once; one row per cycle in order; gap marker after simulated drops;
`window_closed_utc − cycle_start_utc` reflects a synthetic off-grid offset.

**Retention.** Size cap and age cap, oldest-first, swept every 100 cycles on the writer task.
Deletion restricted to the configured directory and the archive's own `YYMMDD_HHMMSS[_n].wav`
pattern. Free-space floor (500 MB): stop archiving for the session, log Warning. Tests including a
non-matching file surviving a sweep that would otherwise clear the directory.

**Pipeline integration.** DI registration and lifetime. One `TryEnqueue` call in the `Program.cs`
decode pump immediately after `DecodeAsync` returns, alongside the existing
`AllTxtWriter.AppendAsync`. **Not awaited.** Test that mode `Off` costs one configuration test and
touches no file system.

**Integration test.** Feed a synthetic window with known FT8 signals through the pump at mode
`All`, read the file back, decode with `Ft8Decoder`, assert the message set matches the in-memory
decode. Verify the file satisfies the existing QA harness contract.

**Closeout.** `python3 tools/pre_merge_check.py` green (HK-006) before any "ready" claim.
No UI control added anywhere. `git status` clean of `.wav`, `cycle-archive.csv`, `cycle-audio/`.

**Deferred to a separate GUI change** (`design.md` Decision 9) — record so the intent survives:
mode selector with plain-language descriptions (particularly `NoDecodes`, whose value is not
self-evident from its name); directory picker with an "open folder" affordance; retention controls
plus a live "N files, M MB used" readout; and a one-shot "record the next N cycles" button, the
operator-friendly form of §3's capture that avoids leaving `All` enabled by accident.

---

# Appendix B — verified landmines, material for QA's Developer handoff

Each verified against the current tree on 2026-07-25. Each is a real documented failure in this
codebase, not a hypothetical.

**B.1 — AOT: register new types in `ConfigJsonContext` or it fails at publish, not at build.**
`OpenWSFZ.Daemon.csproj:18` sets `PublishAot=true` whenever a `RuntimeIdentifier` is set, and
`ConfigJsonContext` exists precisely because reflection-based STJ is unavailable. Both
`CycleAudioArchiveConfig` and `CycleAudioArchiveMode` need `[JsonSerializable]` entries.
`pre_merge_check.py` runs an AOT publish and will catch it, but long after the fact.

**B.2 — Non-CLR-zero config defaults silently deserialise to `0`/`false`.** `MaxSizeMb` (2048),
`MaxAgeHours` (168) and `WriteManifest` (true) are all affected.
`DecodeNoiseSuppressionConfig.cs:14–21` documents this trap (Lesson 6 / D-WFC-001) — copy the
`[JsonConstructor]` + explicit-parameter-defaults pattern exactly. Otherwise a `config.json` that
omits these keys yields a 0 MB size cap and no manifest.

**B.3 — Enum wire values are PascalCase unless pinned, and the camelCase policy will not save
you.** Needs `[JsonConverter(typeof(JsonStringEnumConverter<CycleAudioArchiveMode>))]` (the
**generic** form; the non-generic one is not AOT-safe) **and** an explicit
`[JsonStringEnumMemberName]` on each member. `WorkedBeforeState.cs:11–30` documents this exact
mistake shipping once and blanking every worked-before indicator in the live UI, and warns that
`TxRole`/`CallerPartnerSelectMode` are **not** working counter-examples. Getting it wrong now bakes
a broken wire contract into the parked GUI change.

**B.4 — Do not use NAudio for the WAV writer.** `OpenWSFZ.Audio.csproj:27` package-references
NAudio under `Condition="$([MSBuild]::IsOSPlatform('Windows'))"`, and the Daemon csproj excludes
NAudio-referencing files on non-Windows. A `WaveFileWriter` call breaks the Linux and macOS builds
(`arecord`/`sox`). A canonical RIFF header against `System.IO` is ~40 lines.

**B.5 — `TryWrite` cannot report a drop on any drop-mode channel.** `DropOldest`, `DropNewest` and
`DropWrite` all make `TryWrite` return `true` unconditionally. `WasapiAudioSource.cs` guards a
drop-warning with `if (!innerChannel.Writer.TryWrite(chunk))` on a `DropOldest` channel — that
warning is **unreachable dead code**, found 2026-07-25. Count drops explicitly by comparing count
against capacity before writing, and leave a comment naming that defect. `design.md` Decision 3
makes "no uncounted drop path" a requirement of the capability.

**B.6 — Never `await` the enqueue on the decode pump.** A stalled pump fills `framerOutput`
(capacity 2, `DropOldest`) and silently drops windows — the exact blind spot that cost five rounds
of D-001 investigation. `design.md` Decision 2.

**B.7 — Add the `JsonConfigStore` null-backfill entry.** `JsonConfigStore.cs:143` and `:156` show
the `DecodeLog` / `DecodeNoiseSuppression` pattern. Omitting it reintroduces the D-010 null-section
class of bug.

**B.8 — Do not modify `CycleFramer.cs`.** It is the subject of an active unresolved investigation
and carries an uncommitted diff. If a change there seems necessary, stop and escalate.

**B.9 — Retention must never wipe a directory.** Delete only files in the configured directory
matching the archive's own naming pattern. An operator pointing the setting at a populated folder
must not lose data.
