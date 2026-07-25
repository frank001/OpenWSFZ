# Developer handoff: `cycle-audio-archive` — save decode-cycle audio as `.wav`

**Status:** Ready for a Developer session. Proposal, design and task breakdown are
Architect-authored and committed (`openspec/changes/cycle-audio-archive/`, commit `d1b1027`);
`openspec validate --strict --all` passes 58/58. This document is the narrative companion that
hands off the `src/` work per HK-011 — **QA does not implement this itself.** Work item-by-item
against `openspec/changes/cycle-audio-archive/tasks.md`; this file carries the context, the
branching logistics, and the codebase-specific landmines that `tasks.md` does not repeat.

**Captain's direction (2026-07-25):** option 1 — pause the `CycleFramer` thread, chase the capture
chain, and build the WAV saving as **a real feature with GUI options, not throwaway diagnostic
code**. The GUI half is deliberately parked for a later GUI-focused session; see "Out of scope"
below and `tasks.md` §10.

---

## 1. Branching — read this first, it is not the usual situation

The proposal was committed onto **`docs/propose-fix-cycle-boundary-clock-drift`** (PR #108), which
is 29 commits ahead of `main` and is the branch for a change the Captain has just **paused**.
`cycle-audio-archive` is independent of that change and must not inherit its merge hold.

Two commits are relevant, both **local and unpushed** as of this handoff:

| commit | contents | where it belongs |
|---|---|---|
| `f8461d5` | `qa/cycleframer-alignment-replay/2026-07-25-1200-architect-second-mechanism-located.md` + three probe scripts | Independent analysis, zero `src/`. Belongs on `main` regardless of #108's fate — it is the justification this proposal cites, and the probes are reusable tooling. |
| `d1b1027` | `openspec/changes/cycle-audio-archive/**` | This change. |

**Recommended (QA's call to execute, not the Developer's):** cherry-pick **both** onto a fresh
branch off `main` — `feat/cycle-audio-archive` — and open its own PR. Rationale: if `f8461d5` stays
only on #108 and #108 never merges, `proposal.md`'s central citation dangles on `main`, and the
three probe scripts are lost with it.

**Do not branch from `docs/propose-fix-cycle-boundary-clock-drift`.** It carries an **uncommitted**
working-tree diff in `src/OpenWSFZ.Ft8/CycleFramer.cs` and
`tests/OpenWSFZ.Ft8.Tests/CycleFramerTests.cs` (Decision 9's fix, live-untested, under HK-011 hold).
That diff must survive this work untouched. Confirm `git status` is clean on your branch before
starting.

## 2. Why this is being built now

The short version — full evidence in
`qa/cycleframer-alignment-replay/2026-07-25-1200-architect-second-mechanism-located.md`.

D-001's live-path loss is **not** a cycle-boundary timing defect. Established from the 0724
session's own logs, with no new live run:

- the capture path loses nothing (0 of 2 836 windows lost even one 750-sample chunk);
- every framed window reached the decoder (2 682 emitted == 2 682 decoded, exactly);
- the audio on zero-decode cycles is indistinguishable from the audio on decoding cycles (RMS
  1.290e−2 vs 1.308e−2, ratio 1.01; same noise floor; exactly 180 000 samples every time);
- the entire loss sits at LDPC — the candidate list is saturated at `K_MAX_CANDIDATES = 140` on
  99.8 % of zero-decode cycles (sync **is** finding the signals) while `failCands` climbs 82 → 136.

What is still unknown is why the *live* path's audio yields worse LLRs than an offline replay of
WSJT-X's capture of the same RF. Answering that needs one thing the project has never had:
**OpenWSFZ's own captured audio on disk, in a form the existing offline harness can decode.**

Every prior round reconstructed the live path indirectly by log-walking, and that reconstruction was
the single largest cost of the last five rounds — and got it wrong twice (the sign inversion in
`SPEC.md` §6.3, and the missed mid-session restart in 11.10 §1). This feature removes that entire
class of work permanently, which is why it is worth building properly rather than as a harness.

## 3. What to build

Work `tasks.md` §1–§7 in order. §8 is **QA's**, not yours (see "Out of scope"). Do not re-derive the
design — `design.md` Decisions 1–9 are settled and each records why the alternatives were rejected.

The shape in one paragraph: a `CycleArchiveService` with a bounded queue and a dedicated writer
task; the decode pump in `Program.cs` gains **one non-blocking `TryEnqueue` call** placed alongside
the existing `AllTxtWriter.AppendAsync`; a `CycleWavWriter` emits 12 kHz mono 16-bit WAV
byte-compatible with WSJT-X's recordings; a `cycle-archive.csv` sidecar records per-cycle
provenance; retention is enforced by the writer. Four modes: `Off` (default), `All`, `Decoded`,
`NoDecodes`.

## 4. Landmines — every one of these is verified against the current tree

These are the things that will cost you an afternoon if you meet them cold. Each is a real,
documented failure in this codebase, not a hypothetical.

**4.1 — AOT: register the new types in `ConfigJsonContext` or it fails at publish, not at build.**
`src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj:18` sets `PublishAot=true` whenever a
`RuntimeIdentifier` is set, and `ConfigJsonContext` exists specifically because reflection-based STJ
is unavailable. Add **both** `CycleAudioArchiveConfig` and `CycleAudioArchiveMode`
`[JsonSerializable]` entries. `tools/pre_merge_check.py` runs an AOT publish and will catch it, but
long after the fact.

**4.2 — Non-CLR-zero config defaults silently deserialise to `0`/`false` without a
`[JsonConstructor]`.** `MaxSizeMb` (2048), `MaxAgeHours` (168) and `WriteManifest` (true) are all
affected. `src/OpenWSFZ.Abstractions/DecodeNoiseSuppressionConfig.cs:14–21` documents this trap
(Lesson 6 / D-WFC-001) — read that comment and copy the pattern exactly. A user whose `config.json`
omits these keys would otherwise get a 0 MB size cap and no manifest.

**4.3 — Enum wire values are PascalCase unless you pin them, and the camelCase naming policy will
not save you.** Use `[JsonConverter(typeof(JsonStringEnumConverter<CycleAudioArchiveMode>))]` (the
generic form — the non-generic one is not AOT-safe) **and** an explicit
`[JsonStringEnumMemberName("off")]` / `"all"` / `"decoded"` / `"noDecodes"` on each member.
`src/OpenWSFZ.Abstractions/WorkedBeforeState.cs:11–30` documents exactly this shipping once without
the explicit names and rendering every worked-before indicator in the live UI empty. Note that file's
own warning that `TxRole`/`CallerPartnerSelectMode` are **not** working counter-examples. Getting
this wrong now means the parked GUI change inherits a broken wire contract.

**4.4 — Do not use NAudio for the WAV writer.** `src/OpenWSFZ.Audio/OpenWSFZ.Audio.csproj:27`
package-references NAudio under `Condition="$([MSBuild]::IsOSPlatform('Windows'))"`, and the Daemon
csproj excludes NAudio-referencing files on non-Windows. A `WaveFileWriter` call would break the
Linux and macOS builds (which use `arecord`/`sox`). A canonical 44-byte RIFF header against
`System.IO` is ~40 lines — `design.md` Decision 4 has the format.

**4.5 — `TryWrite` cannot report a drop on a `DropOldest`/`DropNewest`/`DropWrite` channel.** All
three modes make `TryWrite` return `true` unconditionally. `WasapiAudioSource.cs` guards a
drop-warning with `if (!innerChannel.Writer.TryWrite(chunk))` on a `DropOldest` channel — that
warning is **unreachable dead code**, found 2026-07-25. Count drops explicitly by comparing count
against capacity before writing (`tasks.md` 3.2), and put a code comment naming that defect so the
next person does not reintroduce it. `design.md` Decision 3 makes "no uncounted drop path" a
requirement of this capability.

**4.6 — Never `await` the enqueue on the decode pump.** A stalled pump fills `framerOutput`
(capacity 2, `DropOldest`) and silently drops windows — the exact blind spot that cost five rounds
of D-001 investigation. `design.md` Decision 2.

**4.7 — Add the `JsonConfigStore` null-backfill entry.** `src/OpenWSFZ.Config/JsonConfigStore.cs:143`
and `:156` show the `DecodeLog` / `DecodeNoiseSuppression` pattern. Omitting it reintroduces the
D-010 null-section class of bug.

**4.8 — Do not modify `CycleFramer.cs`.** `tasks.md` 6.4. It is the subject of an active unresolved
investigation and carries an uncommitted diff (§1 above). If you believe you need to change it,
stop and escalate instead.

**4.9 — Retention must never wipe a directory.** Delete only files in the configured directory
matching the archive's own `YYMMDD_HHMMSS[_n].wav` pattern (`tasks.md` 5.2). An operator pointing
the setting at a populated folder must not lose data.

## 5. Definition of done

- [ ] `tasks.md` §1–§7 all checked, with any deviation recorded in the task text itself (this
      project's convention — see the `**Done:**` annotations in
      `fix-cycle-boundary-clock-drift/tasks.md`).
- [ ] `python3 tools/pre_merge_check.py` green (HK-006) — G9a, Release build + tests, G3
      traceability, G8 `openspec validate`, G9b, AOT publish. **No "ready" claim before this runs.**
      Three known transient false-FAILs are catalogued in HK-006; retry and diagnose before
      trusting a red.
- [ ] `openspec validate --strict --all` still passes.
- [ ] **No UI control added anywhere** (`tasks.md` 9.2) — the standing convention is that controls
      appear only once their backend is fully implemented and testable end-to-end.
- [ ] `git status` shows no `.wav`, no `cycle-archive.csv`, no `cycle-audio/` tracked
      (`tasks.md` 9.3, NFR-021 — recordings carry real third-party callsigns).
- [ ] The round-trip integration test (`tasks.md` 7.1) passes: a window archived, read back, and
      decoded through `Ft8Decoder` yields the same message set as the in-memory decode.

## 6. Out of scope — do not do these here

- **The GUI.** Parked for a later GUI-focused session by the Captain's explicit direction.
  `tasks.md` §10 records the intent (mode selector with plain-language descriptions, directory
  picker, retention controls with a live "N files, M MB used" readout, and a one-shot "record the
  next N cycles" button) so it survives the handoff. Phase 1 is fully usable via `config.json` and
  the existing config REST API.
- **`tasks.md` §8, the D-001 diagnostic.** That is QA's work once this merges — it needs live radio
  time and the offline harness, not `src/` changes.
- **Anything in `CycleFramer` or `fix-cycle-boundary-clock-drift`.** Paused.
- **A `Float32` archive format option.** Considered and deliberately deferred (`design.md`
  Decision 4) — 16-bit matches WSJT-X's own recordings, which is what makes the comparison fair.

## 7. Review and merge protocol

Per HK-011, the Captain reviews the `src/` diff **before it is pushed** — tighter than HK-010's
merge-only gate. Per HK-010, `gh pr merge` always requires the Captain's explicit sign-off, every
time, green CI notwithstanding.

Sequence: implement → self-check §5 → present the diff to the Captain → push on approval → PR →
green CI → **ask** before merging.

## 8. Cross-references

- `openspec/changes/cycle-audio-archive/{proposal,design,tasks}.md` — the authoritative artifacts.
- `qa/cycleframer-alignment-replay/2026-07-25-1200-architect-second-mechanism-located.md` — why
  this is being built now; contains the three reproducible probes.
- `qa/cycleframer-alignment-replay/2026-07-25-1110-alignment-vs-second-mechanism-findings.md` —
  QA's falsification of the alignment hypothesis that preceded it.
- `src/OpenWSFZ.Daemon/AllTxtWriter.cs` — the sibling writer pattern to model against, and the
  position in the decode pump to sit alongside.
- `src/OpenWSFZ.Abstractions/DecodeLogConfig.cs` — the sibling config record to model against.
