# QA → Architect — OpenSpec archive sweep (4 changes): results

**Authored:** 2026-09-27 16:56Z (mechanically derived, `date -u`, HK-017)
**From:** QA · **To:** Architect
**Spec:** `qa/2026-09-27-1641-architect-to-qa-spec-openspec-archive-sweep-4-changes.md`
(`arch/openspec-archive-sweep` `2086540e`)
**Branch:** `qa/openspec-archive-sweep` off `origin/main` `4c21280d`, 5 commits, **local, not pushed**
(HK-033). No `src/`, no `native/`, no `VERSION` change anywhere in the branch.
**Status:** Tasks A–E complete. All Task E checks pass. G9b passes clean (no bump needed, none taken).

---

## 1. §1 preconditions — verbatim

```
$ git rev-parse --short origin/main
4c21280d
$ grep -n "define FT8_SHIM_VERSION" src/OpenWSFZ.Ft8/Native/ft8_shim.h
731:#define FT8_SHIM_VERSION 20260051
$ grep -c "20260051" openspec/specs/ft8lib-interop/spec.md
1
$ ls openspec/changes (excl. archive/)
capture-device-reresolution
capture-stall-detection-unattended
decode-implausibility-marking
f001-l3-unresolved-by-code-export
$ npx -y @fission-ai/openspec@1.3.1 validate --strict --all
Totals: 64 passed, 0 failed (64 items)
```

All four preconditions held, matching your baseline exactly.

---

## 2. Task A — `decode-implausibility-marking` (WITHDRAWN, `--skip-specs`)

Precondition grep (`"Geographically implausible decodes are marked\|Marked decodes transition to
Dismissed"` over `openspec/specs/`) was empty before touching anything. Added the archived-as-withdrawn
line under the banner, archived with `--skip-specs --yes`. Re-checked after: still empty; `git diff
origin/main -- openspec/specs/decode-noise-suppression/` empty (the `--skip-specs` flag held); `validate
--strict --all` → **63/0**. Commit `01dafb50`.

---

## 3. Task B — `f001-l3-unresolved-by-code-export` (hand-sync, `--skip-specs`)

**Task disposition table (§3.1), each cell verified, not assumed:**

| task | disposition |
|---|---|
| 5.2 | `[x]`, cherry-picked `4d1b8413` (`f001-l3-task-5-2-confirmation`, content-diff-verified identical before the source branch was force-deleted) |
| 7.1 | `[~]` — discharged by the merge (PR #140 → `1b7ca295`), but **no Captain sign-off record for #140 specifically was located** after a real search of `board-archive-to-2026-09-24.md` (the entry there describes the merge's mechanics — CI ran, fast-forwarded, 53 commits — not a quoted go-ahead). Marked `[~]` per your own fallback instruction, not ticked as found. Say if you know where it actually is. |
| 8.1 | `[x]`, checked directly: only `capture-device-reresolution`/`capture-stall-detection-unattended` remained unarchived at that point, neither touches `ft8lib-interop`/`hashed-callsign-resolution` |
| 8.2/8.3 | `[x]`, done by hand — see below |
| 8.4/8.5 | `[x]` |
| 9.1 | `[~] SUPERSEDED` — shim now `20260051`, L3 arm already closed (#156, `463f9819`) |
| 9.2 | `[x]` — both branches deleted (`f001-l3-own-hash-compare-result` merged; `f001-l3-task-5-2-confirmation` force-deleted after a content-diff confirming it was byte-identical to its cherry-pick) |
| 9.3 | `[x]` |

**Hand-sync:** appended the ADDED `hashed-callsign-resolution` requirement verbatim. For
`ft8lib-interop`, appended the ADDED export requirement verbatim, and replaced **only** the sentence
`⚠️ 20260050 (...) is **NOT** reconstructed here — a pre-existing, separately-tracked spec-sync gap...`
with one history sentence recording what `20260050` actually was (measure-only, the diagnostic export,
no managed binding, no decode-output change). The `20260051` pin itself, and every other word of that
paragraph, untouched. Archived `--skip-specs --yes`. `validate --strict --all` → **62/0**. Commits
`c8b9d9b7` (cherry-pick), `614fe47a`.

---

## 4. Task C — `capture-stall-detection-unattended` (#188)

Back-filled all 35 tasks against named evidence — every tick cites a specific file/line, a commit-message
figure, or a test `DisplayName`, not a blind check. Highlights, verified by direct inspection, not
assumed from the commit message:

- **Shutdown ordering (1.4):** read `Program.cs:1031-1046` directly — `captureHealthMonitor.DisposeAsync()`
  fires first, inside the `restartSemaphore.Wait()` guard, before `captureManager` teardown, with a
  comment citing this exact task.
- **All three `DaemonStatus` construction sites (3.6):** found and checked all three (`WebApp.cs:347,
  820, 850`), not just the first — all read `AudioActive` from the shared snapshot, none reintroduces
  the amplitude latch.
- **`AudioActivityMonitor` disposition (4.3):** marked `[~]`, not `[x]`. It was legitimately **not
  deleted** (the task allows this), and I confirmed by grep it's genuinely dead now (fed data, never
  read from), but the task's own "leave a one-line note in the PR description" sub-clause wasn't
  findable in `42cf88f7`'s message — recorded here instead of asserted done.
- **Your own squash-title note confirmed:** `git show --stat 42cf88f7` — 21 files, `+2076/-73`,
  including `CaptureHealthMonitor.cs` (+232), `Program.cs`, `WebApp.cs`, `WebSocketHub.cs`,
  `DataFlowMonitor.cs`, `DaemonStatus.cs`, `AudioWatchdog.cs`. The note is in the tasks.md header now.

Archived normally (ADDED-only, no `--skip-specs` needed). Three requirements landed in `audio-capture`.
`validate --strict --all` → **61/0**. Commit `041d2f24`.

---

## 5. Task D — `capture-device-reresolution` (#187) + board Task 1.9

Same discipline, all 36 tasks. A few read directly rather than trusted from the commit message:

- **Deadlock guard (4.3):** `Program.cs:919-968`'s `configStore.OnSaved` handler still uses `_ =
  Task.Run(async () => { ... await RestartPipelineAsync(...) ... })` — not awaited inline. Read
  directly.
- **Backoff formula (6.1):** `CaptureBackoffSchedule.cs:24-31` — `min(5 × 2^(k−1), 60)`, byte-for-byte
  match to the task and to `REQUIREMENTS.md` FR-071's shipped text.
- **State derivation (5.2):** `CaptureRecoveryState.cs:140-148` `DeriveCaptureState` matched line by
  line against design D5's table.
- 4.2 (no double restart) ticked on architectural evidence (the coordinator and `OnSaved` share one
  `startCaptureAsync`/`RestartPipelineAsync` delegate, not two independent start paths) — I did not
  find and cite a specific test name for the double-restart-count assertion; said so in the task note
  rather than overclaiming.

Archived normally. Four requirements landed (3 `audio-capture`, 1 `audio-device`). `validate --strict
--all` → **60/0**.

**Board Task 1.9, closed in the same commit.** Read the shipped code first, as instructed:
`src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs:62` enumerates `DataFlow.Capture, DeviceState.Active |
DeviceState.Disabled`, and line 72 sets `Available: ep.State == DeviceState.Active`. The base spec's
scenario (`audio-device/spec.md`, was line 15 — line 17 had drifted by the time I got there) said "one
per **active** WASAPI capture endpoint," directly contradicted by the requirement this same change just
added ("Enumerated devices report their availability" — disabled endpoints ARE listed). Edited the
scenario to state the actual mask (Active-or-Disabled, availability carried separately), not a
reworded guess. `grep -n "one per active WASAPI" openspec/specs/` — empty. Commit `f3fb22cc`.

---

## 6. Task E — verification gate, verbatim

```
--- check 1 (the one that matters) ---
$ grep -c "20260051" openspec/specs/ft8lib-interop/spec.md
1
$ grep -n "SHALL be \*\*\`20260050\`\*\*" openspec/specs/ft8lib-interop/spec.md
(empty)
--- check 2 ---
$ grep -c "ft8_get_h12_unresolved_by_code" openspec/specs/ft8lib-interop/spec.md
9
$ grep -c "is \*\*NOT\*\* reconstructed here" openspec/specs/ft8lib-interop/spec.md
0
$ grep -c "unresolved-lookup sizing, by code" openspec/specs/hashed-callsign-resolution/spec.md
1
--- check 3 ---
$ grep -rn "Geographically implausible decodes are marked\|Marked decodes transition to Dismissed" openspec/specs/
(empty)
$ git diff origin/main -- openspec/specs/decode-noise-suppression/
(empty)
$ ls openspec/specs | grep -c "decode-implausibility-marking"
0
--- check 4 ---
$ grep -c "^### Requirement: Capture health is evaluated independently" openspec/specs/audio-capture/spec.md
1
$ grep -c "^### Requirement: Stale capture device identifier is re-resolved" openspec/specs/audio-capture/spec.md
1
$ grep -c "^### Requirement: Enumerated devices report their availability" openspec/specs/audio-device/spec.md
1
$ grep -n "one per active WASAPI" openspec/specs/audio-device/spec.md
(empty)
--- check 5 ---
$ ls openspec/changes | grep -v '^archive'
(empty)
--- check 6 ---
$ npx -y @fission-ai/openspec@1.3.1 validate --strict --all
Totals: 60 passed, 0 failed (60 items)
$ git diff --stat origin/main -- src/ native/
(empty)
```

**On "count >= the §1 baseline":** the final count is **60**, below the baseline **64** — by exactly 4,
the number of changes archived. I checked this isn't a defect: each archived change's own validation
entry disappears from the total the moment it archives (64→63→62→61→60, one per task, confirmed at
every intermediate step above), and none of the four created a *new* spec file — everything synced into
specs that already existed. `64 = 60 spec files + 4 unarchived changes` at the start; `60 = 60 spec
files + 0` at the end. This matches the 2026-09-02 sweep's own precedent exactly (`qa/2026-09-02-1551-
...-results.md`: 63→62 after archiving one change, same arithmetic). I read "count >= baseline" as an
expectation that didn't account for this, not a defect in the sweep — flagging the exact numbers rather
than silently either ignoring the clause or treating it as a STOP-worthy failure.

**G9b:** committed first, then ran `python tools/check_version_bump.py origin/main` → `Result: OK —
this PR introduces no new OpenSpec change proposals; no version bump required.` No bump taken, none
needed.

---

## 7. Commits

```
01dafb50 qa(openspec): archive decode-implausibility-marking as WITHDRAWN (--skip-specs)
c8b9d9b7 docs(f001-l3): tick task 5.2 -- filtered suite confirmed green post shim 20260050
614fe47a qa(openspec): archive f001-l3-unresolved-by-code-export -- hand-sync, --skip-specs
041d2f24 qa(openspec): archive capture-stall-detection-unattended (#188) -- back-filled tasks.md, ADDED sync
f3fb22cc qa(openspec): archive capture-device-reresolution (#187) -- back-fill, sync, Task 1.9 reconciliation
```

Local on `qa/openspec-archive-sweep`. Push and merge need the Captain's go (HK-033/HK-010) — docs-only,
so HK-029's direct-merge exception is available if the Captain says so; `git diff --stat origin/main --
src/ native/` is empty for the whole branch, stated above and re-verified after every task.

HK-025: nothing in this spec read as a judgement dressed as a mechanical check, except the count-baseline
clause discussed in §6, which I disclosed rather than silently resolved either way.
