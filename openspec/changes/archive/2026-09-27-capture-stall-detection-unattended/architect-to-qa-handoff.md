# Architect → QA handoff: capture self-healing (#188 + #187)

**Prepared by:** Architect
**Date:** 2026-09-24 (UTC, `date -u` 18:51Z at start)
**Base:** `origin/main` @ `5a9290c6`. All code citations were verified against that ref.
**Changes covered (one handoff for both, because they ship in sequence):**

| Order | Change | Issue | Folder |
|---|---|---|---|
| 1 | `capture-stall-detection-unattended` | #188 | `openspec/changes/capture-stall-detection-unattended/` |
| 2 | `capture-device-reresolution` | #187 | `openspec/changes/capture-device-reresolution/` |

**Why this order:** #187's status fields extend #188's. #187's recovery-success signal is #188's
last-chunk timestamp. #187's live tests are read through #188's headless status surface. #188 is
useful on its own. #187 without #188 is not verifiable unattended.

**Why this matters now:** the Captain has made both issues the precondition for direct-USB-CODEC
capture ever becoming a default (`BOARD.md`, 2026-09-24 endurance entry).

**Chain discipline (HK-015).** This document goes Architect → QA and stops. The Architect has not
written `tasks.md` or any `dev-tasks/*.md`; **both are QA's.** Everything marked *material* is
for QA to use, revise or discard. It is not an instruction to the Developer. Both changes touch
`src/` only (no `native/`), so a separate Developer session is required (HK-011).

---

## 0. Captain decisions — ✅ RATIFIED 2026-09-24 ~19:00Z ("1. yes. 2. yes")

| # | Decision | Ruling | Where |
|---|---|---|---|
| C1 | What `audioActive` means | ✅ **Option A:** equals the last window's `dataFlowing` on every surface. Amend FR-020; the amplitude monitor may be deleted. | #188 `design.md` D4 |
| C2 | Persist a re-resolved device ID to `config.json`? | ✅ **Yes (option A).** One restart path; Settings page and next startup stay consistent. | #187 `design.md` D3 |

Both specs were written for these options, so no requirement text changes.

Settled in the designs and not reopened here: exact, unique, active-only name matching with no
guessing; a backoff of 5 → 60 s that never stops; the `Heartbeat:` line format kept byte-identical.

## 1. QA's tasks

- [x] **1.1 Put the Captain's C1/C2 answers on record.** Done by the Architect in §0 and on the board, 2026-09-24.
- [ ] **1.2 Author `tasks.md` for each change.** Appendix A is suggested material.
- [ ] **1.3 Author the Developer handoff(s)** (`dev-tasks/*.md`, HK-000). Appendix B lists the verified landmines.
      Recommendation: two PRs in order, #188 then #187. Each is independently reviewable.
- [ ] **1.4 `REQUIREMENTS.md`:** amend FR-020 per C1, and add FR IDs for the new behaviour (next free
      ID is **FR-067**). NFR-020 traceability applies.
- [ ] **1.5 Run the live acceptance tests in §2** after each change is built, on the Captain's
      station. Gather everything into `artefacts/` (HK-016).
- [ ] **1.6 QA tooling follow-up (after #187 merges, zero `src/`):** give `endurance_supervisor.py`
      the health predicate
      `captureState == "Capturing" and dataFlowing and lastChunkAgeMs < 10000`, and add
      `captureRestartCount` / `watchdogRestartCount` to its events log. **Keep** the independent
      newest-WAV-mtime check: an instrument cannot bound its own blind spot (HK-026).
- [ ] **1.7 Open a new issue** for the same defect class on the TX output device
      (`audioOutputDeviceId`, `operational-note-audio-endpoint-guid-goes-stale` records that it rotated in
      the same 2026-08-03 event). It is out of scope for both changes.
- [ ] **1.8 Branch reach.** Endurance arms run on `decoding_improvement`. The Captain's periodic
      `merge origin/main` is what brings these fixes to the branch that is actually run. The
      direct-CODEC adoption gate is met only when **the branch being run** carries both changes.
      Check the DLL/daemon build before claiming it.
- [ ] **1.9 HK-002 at archive:** `audio-device/spec.md` currently says "one per **active** endpoint"
      while the code lists disabled ones too. #187's `available` flag makes both true. Reconcile
      the main spec on sync.

## 2. Live acceptance tests (pre-registered, mechanical — HK-021)

General conditions for all of them: the Windows station and the standing daemon build under test, with
**no browser tab open**. That is verified mechanically: the count of `WebSocket connection accepted`
lines in the daemon log during the test window must be **0**, or the test is VOID. Poll
`GET /api/v1/status` every 5 s and log each response with a UTC timestamp (HK-017). Take a backup of
`config.json` into `artefacts/` before any test edits it, and restore it only **with the daemon stopped**
(the daemon rewrites the file on shutdown, and a POST is a full replace, HK-035).

### L1 — headless heartbeat and live status (#188)

30 min, device configured, decoding enabled.

| Row | Predicate | Verdict |
|---|---|---|
| L1-0 | `ws_accepted == 0` | else VOID |
| L1-1 | `330 <= heartbeat_lines <= 370` and `max_gap_between_heartbeat_lines_s <= 7` | PASS / FAIL |
| L1-2 | every poll after the first 10 s has `dataFlowing == true` and `lastChunkAgeMs < 2000` | PASS / FAIL |
| L1-3 | `watchdogRestartCount == 0` at the end | PASS / FAIL |

**What L1 cannot detect:** L1 does not exercise stall recovery. A silent WASAPI stall cannot be
induced on demand; pulling the cable produces a thrown failure (L4's path). The stall path's
proof is **unit-level only** (Appendix A, U3). A green L1 must never be reported as "stall recovery
verified live" (HK-022).

### L2 — stale ID at startup is adopted (#187)

Deterministic stand-in for the 2026-08-03 incident. Stop the daemon. In `config.json`, set
`audioDeviceId` to `{0.0.1.00000000}.{00000000-0000-0000-0000-000000000000}` and leave
`audioDeviceFriendlyName` unchanged. Start the daemon.

| Row | Predicate | Verdict |
|---|---|---|
| L2-0 | the configured friendly name matches exactly one `available: true` entry in `GET /api/v1/audio/devices` | else VOID (the precondition does not hold) |
| L2-1 | within 30 s of process start: `captureState == "Capturing"` and `dataFlowing == true` | PASS / FAIL |
| L2-2 | `config.json.audioDeviceId` equals that entry's `id`, and the friendly name is byte-identical to the backup | PASS / FAIL |
| L2-3 | exactly **1** adoption Warning in the log, and exactly **1** capture start after it | PASS / FAIL |

### L3 — unresolvable device is loud, bounded and never guessed (#187)

Stop the daemon. Set a bogus `audioDeviceId` as in L2, and set `audioDeviceFriendlyName` to
`"QA-NONEXISTENT-DEVICE"`. Start and run for 300 s.

| Row | Predicate | Verdict |
|---|---|---|
| L3-1 | within 30 s: `captureState == "DeviceUnavailable"` and `lastCaptureError != null` | PASS / FAIL |
| L3-2 | `captureRestartCount` at t = 300 s is between **5 and 9** inclusive. Expected 7: automatic attempts at +5, +15, +35, +75, +135, +195, +255 s after the failed startup attempt. 🛑 Do **not** count Error lines: an attempt that finds no matching device never opens capture, so it writes no FR-021 termination line | PASS / FAIL |
| L3-3 | `config.json.audioDeviceId` unchanged; zero adoption Warnings | PASS / FAIL |

### L4 — physical unplug and replug, no operator action (#187 + #188)

The Captain unplugs the FT-991A's USB cable for about 120 s, then replugs it. **The human is the actuator, not
the sensor (HK-027).** Reappearance time is taken from the instrument: the first 5 s poll of
`GET /api/v1/audio/devices` in which the configured friendly name is listed `available: true`
again (`t_avail`). Recovery time `t_rec` is the first status poll with `captureState == "Capturing"`
and `dataFlowing == true` after `t_avail`.

| Row | Predicate | Verdict |
|---|---|---|
| L4-0 | `ws_accepted == 0`, and at least one poll during the unplug shows `captureState ∈ {Recovering, DeviceUnavailable}` | else VOID (the unplug was not observed) |
| L4-1 | `t_rec − t_avail <= 70 s` | PASS / FAIL |
| L4-2 | after `t_rec`: `consecutiveCaptureFailures == 0`, and `lastCaptureError` is still non-null | PASS / FAIL |
| L4-3 | report whether the GUID rotated (adoption Warning present or absent) | **descriptive only**: either outcome passes |

Note for L4: WSJT-X reads the same physical device on a direct-CODEC arm and has **no**
equivalent recovery. Don't run L4 during a live endurance window.

## 3. Out of scope, recorded

- The TX output device has the same defect class (task 1.7).
- The container-ID matching key is the upgrade path if a future incident shows the friendly name
  itself renumbering (`"2-"` → `"3-"`). In that case #187 goes loud (`DeviceUnavailable`), not silent,
  but it does not recover (#187 `design.md` D2).
- #181 (`CatPollingService` `_cts` race) is a similar lifecycle class, but unrelated. It is not
  touched here.

---

## Appendix A — suggested test material (for QA's `tasks.md`)

- **U1 Resolver table (#187).** Every outcome in #187 D1: configured present (including when its name
  differs); one exact match adopted; trailing-space name; `"2-"` vs `"3-"` near-miss; case
  difference; two matches → Ambiguous(2); disabled-only → NotFound; empty enumeration →
  CannotResolve; null friendly name → CannotResolve.
- **U2 Backoff (#187).** `FakeTimeProvider`: attempts at 5/10/20/40/60/60/60 s. Reset on first chunk.
  Watchdog restarts and `CaptureFailed` share one counter.
- **U3 Headless watchdog (#188).** Zero clients; a fake `IAudioSource` that stops yielding **without
  throwing**; exactly one restart after 3 windows. With 3 clients over 10 windows: exactly 10 ticks
  and 10 consumes.
- **U4 `lastChunkAgeMs` (#188).** Not reset by `DataFlowMonitor.Reset()`. `null` before the first chunk.
  Monotonic: a wall-clock change does not affect it.
- **U5 Single start per adoption (#187).** The fake source counts `CaptureAsync` calls: exactly 1 per
  adoption. The test completes under a timeout, proving no semaphore deadlock (Appendix B, item 3).
- **U6 Surfaces agree (#188).** REST `audioActive` == WS `status.audioActive` == last heartbeat value.
- **U7 Heartbeat format (#188).** A regex on the emitted line, lowercase booleans, one per window.

## Appendix B — landmines, verified at `5a9290c6` (material, not instructions)

1. **Silent fake sources in existing integration tests** will now trip the headless watchdog
   (#188 design, Risks 1). Sweep the test fixtures that host the daemon.
2. **Double restart on adoption.** `SaveAsync` → `OnSaved` → the device-change transition already
   restarts (`Program.cs:897-912`). The adoption path must not start the pipeline a second time
   (#187 D3.1).
3. **Semaphore ordering.** Adoption runs inside `RestartPipelineAsync`'s `restartSemaphore`. This is
   safe only while `OnSaved` *schedules* its restart with `Task.Run` (as it does today) and never
   awaits it inline (#187 D3.3).
4. **HK-035 full replace.** Build the saved config as `store.Current with { AudioDeviceId = … }`, read
   immediately before the save.
5. **Shutdown ordering.** Stop the ticker inside the existing `restartSemaphore` shutdown guard
   (`Program.cs:977-980`) before `captureManager` is disposed.
6. **`Heartbeat:` rendering is lowercase** (`captureActive=true`). Older bash supervisors match
   `=false` case-sensitively.
7. **`CaptureManager.IsCapturing` flips `true` synchronously in `StartAsync`** and back to `false` in
   `finally` (`CaptureManager.cs:22-38`). Neither is a success signal. Success is the first chunk.
8. **FR-021** requires one log entry per capture termination. Do not "fix" the log volume by
   suppressing them. Backoff alone takes it from about 17k lines/day to about 1.4k lines/day.
