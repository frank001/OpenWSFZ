# Developer handoff: `cycle-audio-archive` — save decode-cycle audio as `.wav`

**Authored by:** QA (per HK-000/HK-015 — this is QA's document to write and issue, not the
Architect's; the Architect's material arrived as `architect-to-qa-handoff.md` and has been
reviewed, independently spot-verified against the tree, and adopted below with QA's own framing).
**Status:** Ready for a Developer session. `openspec/changes/cycle-audio-archive/` (`proposal.md`,
`design.md`, `specs/`, `tasks.md`) is complete; `openspec validate --strict --all` passes 57/57.
Work `tasks.md` §1-8 item-by-item; this file carries the narrative context and the
codebase-specific landmines `tasks.md` doesn't repeat in full.

**Captain's direction (2026-07-25):** pause the `CycleFramer` thread, chase the capture chain, and
build WAV saving as **a real feature with GUI options, not throwaway diagnostic code**. The GUI
half is deliberately parked for a later GUI-focused session; see "Out of scope" below and
`tasks.md` §10.

---

## 1. Branching — already done, confirm before you start

**Branch:** `docs/propose-cycle-audio-archive`, cut off `main` (QA task 0.1, already complete —
this is not something you need to do). It carries exactly four commits: `f8461d5` (the LDPC
findings doc + three reusable probe scripts — independent of this feature but its central
citation), `d1b1027` (the proposal/design/spec), `ec08753`+`47e353e` (an authorship correction,
HK-015 — ignore the history noise, the net state is what matters).

**It does not carry the paused `fix-cycle-boundary-clock-drift` branch's uncommitted `CycleFramer`
diff, and never has.** That diff lives only on `docs/propose-fix-cycle-boundary-clock-drift`
(PR #108), under an HK-011 hold, live-test-failed. QA confirmed byte-for-byte (`git diff --stat`
before and after) that it survived this branch's creation untouched. Run `git status` on your
checkout before starting — it should be clean.

## 2. Why this is being built now

Full evidence: `qa/cycleframer-alignment-replay/2026-07-25-1200-architect-second-mechanism-located.md`
(this is the `f8461d5` findings doc, present on your branch).

D-001's live-path recall loss is **not** a cycle-boundary timing defect — that was the working
theory for five straight live-endurance rounds, and it is now falsified. From the 0724 session's
own logs, with no new live run:

- the capture path loses nothing (0 of 2 836 windows lost even one 750-sample chunk);
- every framed window reached the decoder (2 682 emitted == 2 682 decoded, exactly);
- the audio on zero-decode cycles is indistinguishable from the audio on decoding cycles (RMS
  1.290e-2 vs 1.308e-2, ratio 1.01; same noise floor; exactly 180 000 samples every time);
- the entire loss sits at LDPC — the candidate list is saturated at `K_MAX_CANDIDATES = 140` on
  99.8% of zero-decode cycles (sync **is** finding the signals) while `failCands` climbs 82 → 136.

What remains unknown is why the *live* path's audio yields worse LLRs than an offline replay of
WSJT-X's capture of the same RF. Answering that needs one thing the project has never had:
**OpenWSFZ's own captured audio on disk, in a form the existing offline harness can decode
unmodified.** That is what you are building. The D-001 diagnostic itself (`tasks.md` §9) is QA's
own follow-on work once this merges — not yours to run.

## 3. What to build

Work `tasks.md` §1-7 in order, then §8 (closeout). §9 (the D-001 diagnostic) and §10 (deferred GUI)
are explicitly **not yours** — see "Out of scope". Do not re-derive the design — `design.md`
Decisions 1-9 are settled, each with its rejected alternatives on record; if one looks wrong,
escalate rather than work around it (HK-015: Developer → QA → Architect).

The shape in one paragraph: a `CycleArchiveService` with a bounded queue and a dedicated writer
task; the decode pump in `Program.cs` gains **one non-blocking `TryEnqueue` call**, at `:746-758`,
placed alongside the existing `AllTxtWriter.AppendAsync` call; a `CycleWavWriter` emits 12 kHz mono
16-bit WAV byte-compatible with WSJT-X's own recordings; a `cycle-archive.csv` sidecar records
per-cycle provenance; retention is enforced by the writer. Four modes: `Off` (default), `All`,
`Decoded`, `NoDecodes`.

## 4. Landmines — each independently re-verified against the tree by QA on 2026-07-25

These will cost you an afternoon if you meet them cold.

**4.1 — AOT: register the new types in `ConfigJsonContext` or it fails at publish, not at build.**
`src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj:18` — `<PublishAot Condition="'$(RuntimeIdentifier)'!=''">true</PublishAot>`
— confirmed present. `ConfigJsonContext` exists specifically because reflection-based STJ is
unavailable under AOT. Add **both** `CycleAudioArchiveConfig` and `CycleAudioArchiveMode`
`[JsonSerializable]` entries. `tools/pre_merge_check.py` runs an AOT publish and will catch a miss,
but long after the fact.

**4.2 — Non-CLR-zero config defaults silently deserialise to `0`/`false` without a
`[JsonConstructor]`.** `MaxSizeMb` (2048), `MaxAgeHours` (168) and `WriteManifest` (true) are all
affected. `src/OpenWSFZ.Abstractions/DecodeNoiseSuppressionConfig.cs:14-27` — confirmed present,
read the comment and copy the pattern exactly. A `config.json` omitting these keys would otherwise
silently get a 0 MB size cap and no manifest.

**4.3 — Enum wire values are PascalCase unless you pin them, and the camelCase naming policy will
not save you.** Use `[JsonConverter(typeof(JsonStringEnumConverter<CycleAudioArchiveMode>))]` (the
generic form — the non-generic one is not AOT-safe) **and** an explicit
`[JsonStringEnumMemberName("off")]`/`"all"`/`"decoded"`/`"noDecodes"` on each member.
`src/OpenWSFZ.Abstractions/WorkedBeforeState.cs:11-30` — confirmed present — documents exactly this
mistake shipping once and rendering every worked-before indicator in the live UI empty, because
`AppJsonContext`'s `CamelCase` `PropertyNamingPolicy` only renames JSON *properties*, never enum
*values*. That file's own remarks note `TxRole`/`CallerPartnerSelectMode` are **not** working
counter-examples — every call site serialising those puts a plain `.ToString().ToLowerInvariant()`
string on the wire instead, so their attributes are never actually exercised. Getting this wrong
now bakes a broken wire contract into the parked GUI change.

**4.4 — Do not use NAudio for the WAV writer.** `src/OpenWSFZ.Audio/OpenWSFZ.Audio.csproj:27` —
confirmed present — package-references NAudio under
`Condition="$([MSBuild]::IsOSPlatform('Windows'))"`, and the Daemon csproj excludes
NAudio-referencing files on non-Windows. A `WaveFileWriter` call breaks the Linux (`arecord`) and
macOS (`sox`) builds. A canonical 44-byte RIFF header against `System.IO` is ~40 lines —
`design.md` Decision 4 has the exact format.

**4.5 — `TryWrite` cannot report a drop on a `DropOldest`/`DropNewest`/`DropWrite` channel.** All
three drop modes make `TryWrite` return `true` unconditionally in .NET.
`src/OpenWSFZ.Audio/WasapiAudioSource.cs:165` — confirmed present —
`if (!innerChannel.Writer.TryWrite(chunk))` guards a drop-warning on a `DropOldest` channel; that
warning is **unreachable dead code**. Count drops explicitly by comparing count against capacity
before writing (`tasks.md` 3.2), and leave a code comment naming this defect so the next person
does not reintroduce it. `design.md` Decision 3 makes "no uncounted drop path" a requirement of
this capability, not a nice-to-have.

**4.6 — Never `await` the enqueue on the decode pump.** A stalled pump fills `framerOutput`
(capacity 2, `DropOldest`, `Program.cs:344`) and silently drops windows — the exact blind spot that
cost five rounds of D-001 investigation before it was diagnosed. `design.md` Decision 2.

**4.7 — Add the `JsonConfigStore` null-backfill entry.** `src/OpenWSFZ.Config/JsonConfigStore.cs:143`
and `:156` — confirmed present — show the `DecodeLog`/`DecodeNoiseSuppression` pattern. Omitting it
reintroduces the D-010 null-section class of bug.

**4.8 — Do not modify `CycleFramer.cs`.** `tasks.md` 6.4. It is the subject of an active,
unresolved investigation and carries an uncommitted diff on a *different* branch (§1 above). If you
believe a change there is necessary to complete this feature, stop and escalate — do not proceed.

**4.9 — Retention must never wipe a directory.** Delete only files in the configured directory
matching the archive's own `YYMMDD_HHMMSS[_n].wav` pattern (`tasks.md` 5.2). An operator pointing
the setting at a populated folder must not lose data.

## 5. Definition of done

- [ ] `tasks.md` §1-7 all checked, with any deviation recorded in the task text itself (this
      project's convention — see the `**Done:**` annotations throughout
      `fix-cycle-boundary-clock-drift/tasks.md` for the expected style).
- [ ] `python3 tools/pre_merge_check.py` green (HK-006) — G9a, Release build + tests, G3
      traceability, G8 `openspec validate`, G9b, AOT publish. **No "ready" claim before this runs.**
      Three known transient false-FAILs are catalogued in HK-006; retry and diagnose before
      trusting a red.
- [ ] `openspec validate --strict --all` still passes.
- [ ] **No UI control added anywhere** (`tasks.md` 8.2) — controls appear only once their backend
      is fully implemented and testable end-to-end.
- [ ] `git status` shows no `.wav`, no `cycle-archive.csv`, no `cycle-audio/` tracked
      (`tasks.md` 8.3, NFR-021 — recordings carry real third-party callsigns).
- [ ] The round-trip integration test (`tasks.md` 7.1) passes: a window archived, read back, and
      decoded through `Ft8Decoder` yields the same message set as the in-memory decode.

## 6. Out of scope — do not do these here

- **The GUI.** Parked for a later GUI-focused session by the Captain's explicit direction.
  `tasks.md` §10 records the intent (mode selector with plain-language descriptions — particularly
  `NoDecodes`, whose value is not self-evident from its name — a directory picker, retention
  controls with a live "N files, M MB used" readout, and a one-shot "record the next N cycles"
  button) so it survives the handoff. Phase 1 is fully usable via `config.json` and the existing
  config REST API.
- **`tasks.md` §9, the D-001 diagnostic.** QA's work once this merges — needs live radio time and
  the offline harness, not further `src/` changes.
- **Anything in `CycleFramer` or `fix-cycle-boundary-clock-drift`.** Paused, held, not yours.
- **A `Float32` archive format option.** Considered and deliberately deferred (`design.md`
  Decision 4) — 16-bit matches WSJT-X's own recordings, which is what makes the D-001 comparison
  fair.

## 7. Review and merge protocol

Per HK-011, the Captain reviews the `src/` diff **before it is pushed** — tighter than HK-010's
merge-only gate. Per HK-010, `gh pr merge` always requires the Captain's explicit sign-off, every
time, green CI notwithstanding.

Sequence: implement → self-check §5 → present the diff to the Captain → push on approval → PR →
green CI → **ask** before merging.

## 8. Cross-references

- `openspec/changes/cycle-audio-archive/{proposal,design,tasks}.md` — the authoritative artifacts.
- `openspec/changes/cycle-audio-archive/architect-to-qa-handoff.md` — the Architect's original
  material this handoff was reviewed against and adopted from.
- `qa/cycleframer-alignment-replay/2026-07-25-1200-architect-second-mechanism-located.md` — why
  this is being built now; contains the three reproducible probes (`f8461d5`).
- `src/OpenWSFZ.Daemon/AllTxtWriter.cs` — the sibling writer pattern to model against, and the
  position in the decode pump to sit alongside.
- `src/OpenWSFZ.Abstractions/DecodeLogConfig.cs` — the sibling config record to model against.
