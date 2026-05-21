# p5-ft8-decoder — Session Resume

**Date:** 2026-05-21
**Branch:** `feat/p5-ft8-decoder`
**Commit ahead of main:** `910dbef` (housekeeping only — no implementation yet)

---

## What happened this session

1. **README.md rewritten** for the newly public repository — status table, "What works today",
   prerequisites, build & run instructions, architecture summary, contributing section.
2. **p4-audio-pipeline archived** to `openspec/changes/archive/2026-05-21-p4-audio-pipeline/`.
3. **Delta specs promoted to live:**
   - Created `openspec/specs/audio-capture/spec.md` (new capability)
   - Updated `openspec/specs/audio-device/spec.md` (STA threading requirement + scenario added)
4. **QA review conducted** on the housekeeping commit. See findings below.

---

## QA findings — action before merge

### R-1 — Required

**File:** `README.md`, line 49

**Current text:**
> changes are persisted to a **TOML** config file

**Correct text:**
> changes are persisted to a **JSON** config file

The implementation uses `JsonConfigStore` and writes `config.json`.
`TECHNICAL_SPEC.md` originally specified TOML but the implementation chose JSON.
The README must reflect what was built.

### A-1 — Advisory

The status table in `README.md` shows p5 as `🔧 in progress`. No implementation
exists on the branch yet. Consider changing to `⬜ planned` until the first
implementation commit lands. Not a blocker.

---

## p5 state — ready to implement

All OpenSpec artifacts are written and waiting:

| Artifact | Location |
|---|---|
| Proposal | `openspec/changes/p5-ft8-decoder/proposal.md` |
| Design | `openspec/changes/p5-ft8-decoder/design.md` |
| Tasks | `openspec/changes/p5-ft8-decoder/tasks.md` |
| Delta specs | `openspec/changes/p5-ft8-decoder/specs/` |

All 45 tasks are unchecked. Run `opsx:apply` to begin.

---

## Key context before you start

### The `OpenWSFZ.Ft8` project directory already exists

`src/OpenWSFZ.Ft8/` has `bin/` and `obj/` folders from prior build scaffolding but
**no source files and is not in the solution**. Task 1.1–1.3 creates the `.csproj`
and adds it to `OpenWSFZ.slnx`. Do not assume the project is wired up.

### Pure C# DSP — no native libs

The design explicitly rejects P/Invoke, LibVLCSharp, and any GPL-sourced code.
Everything from Goertzel through LDPC is plain C# using `Span<T>` and
`System.Numerics`. No new NuGet packages are expected.

### WAV fixture (task 8.1–8.2) is blocking for the integration test

Task 7.3 (the full-pipeline integration test) depends on `ft8-sample.wav` and
`ft8-sample.ref` being committed to `tests/OpenWSFZ.Ft8.Tests/Fixtures/`.
Either capture a clean 15-second 12 kHz mono clip from a live 20m FT8 session
or synthesise one with a reference encoder. Capture from real air is preferred.
Do not let the integration test block the rest of the implementation — stub it
with `Assert.Skip` until the fixture is ready, then fill it in.

### Traceability debt

`FR-001` and `FR-009` are currently in `traceability-debt.md`. Task 13.1 removes
them once implemented. The TraceabilityCheck CI gate will pass throughout p5
because the debt file covers them — no CI breakage expected mid-implementation.

### Notes deferred from p4 QA (non-blocking)

These were flagged in `qa-review.md` as future-phase work. They are relevant context:

- **N-1** — `WasapiAudioSource` allocates `new float[2048]` per drain iteration;
  `ArrayPool<float>` would reduce GC pressure. Fix in p5 if convenient, else p6.
- **N-3** — `CaptureManager.StopAsync` swallows all exceptions silently; inject
  `ILogger<CaptureManager>` when you touch `Program.cs` in task 10.x.

### WebSocket connection tracking (task 11.4)

The existing `WebSocketHub` manages a single connection loop. Broadcasting `decode`
events to all connected clients requires a thread-safe connection set. Task 11.4
covers this but it is a structural change to the hub — review existing WebSocket
tests before modifying so you do not inadvertently break the heartbeat path.

---

## Suggested task order

The task list is ordered correctly but the following grouping avoids blocking:

1. **Tasks 1–2** — scaffold projects and flesh out abstractions. Gets the solution
   building clean.
2. **Tasks 3–6** — DSP components (Goertzel → Costas → LDPC → unpack) with their
   unit tests. These are self-contained and form the bulk of the work.
3. **Task 8** — WAV fixture. Can be done in parallel with DSP if you have a
   suitable clip available.
4. **Tasks 7, 9** — assemble `Ft8Decoder` and `CycleFramer` once the primitives
   are solid.
5. **Tasks 10–12** — daemon wiring, WebSocket broadcast, and UI handler. Should be
   the last thing wired up to avoid partial behaviour in the running app.
6. **Task 13** — traceability, build verification, smoke test, PR.
