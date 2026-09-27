# Architect → QA: OpenSpec archive sweep (4 unarchived changes)

**Authored:** 2026-09-27 16:41Z (mechanically derived, `date -u`, HK-017)
**From:** Architect · **To:** QA (HK-015: this is a spec, not a dev-task; QA authors any dev-task that
falls out of it)
**Base:** `main` @ `4c21280d`, shim `20260051`, `openspec validate --strict --all` = **64 passed, 0 failed**
(Architect's baseline, same tip)
**Authorised:** the Captain, 2026-09-27: *"proceed with the writeup"*, after the Architect proposed one
sweep covering all four changes. Format follows the last sweep,
`qa/2026-09-02-1521-architect-to-qa-spec-openspec-archive-and-repo-hygiene.md` (HK-034).

---

## 0. Why this exists, and what is load-bearing

`openspec/changes/` holds **four** unarchived changes. Three shipped; one was withdrawn before anything was
built.

| Change | State on `main` | `tasks.md` `[x]` / `[ ]` | Delta specs |
|---|---|---|---|
| `decode-implausibility-marking` | **WITHDRAWN** 2026-09-06; nothing built | no `tasks.md` | ADDED (new capability) + **MODIFIED** `decode-noise-suppression` |
| `f001-l3-unresolved-by-code-export` | shipped: shim `20260050`, via PR #140 → `1b7ca295` (2026-09-06). Its L3 arm then ran and **CLOSED** (PR #156, `463f9819`) | 14 / 10 | **MODIFIED** `ft8lib-interop` ABI + ADDED export; ADDED `hashed-callsign-resolution` |
| `capture-stall-detection-unattended` (#188) | shipped: PR #190 → `42cf88f7` (21 files, including `src/`) | **0 / 35** | ADDED ×3 `audio-capture` |
| `capture-device-reresolution` (#187) | shipped: PR #191 → `9f54e6af` (27 files, including `src/`) | **0 / 36** | ADDED ×3 `audio-capture`; ADDED ×1 `audio-device` |

Verified by the Architect on `4c21280d`:

1. 🔴 **Two deltas would DAMAGE the base specs if synced blindly.**
   - `decode-implausibility-marking`'s MODIFIED `decode-noise-suppression` requirement would rewrite a
     **live** requirement with text for a feature that was **never built**.
   - `f001-l3`'s MODIFIED "ABI self-test on first load" pins `20260050`. The base spec already pins
     **`20260051`** (`ft8lib-interop/spec.md:49`, matching `ft8_shim.h:731` and
     `Ft8LibInterop.cs:444`), so a blind sync **rolls the documented pin backwards** and drops the
     `passband-140` entry.
   - ⇒ **both archive with `--skip-specs`**, and f001's two ADDED requirements plus one history line are
     merged **by hand** (§3).
2. The base spec's ABI paragraph already flags the gap explicitly: *"⚠️ `20260050`
   (`f001-l3-unresolved-by-code-export` …) is **NOT** reconstructed here — a pre-existing,
   separately-tracked spec-sync gap"*. This sweep closes it.
3. **Both capture `tasks.md` files are false records** (0 of 71 ticked for shipped, live-accepted work). 🔴
   And **`42cf88f7`'s squash title says "no src/ diff" while it carries `src/`** (`CaptureHealthMonitor.cs`
   +232, `Program.cs`, `WebApp.cs` …). `main`'s history is not rewritten. The correction lives in the
   archived `tasks.md` note (§4.1).
4. **Board Task 1.9 is still open, and it lands here.** `openspec/specs/audio-device/spec.md:17` says
   *"one per **active** WASAPI capture endpoint"*, while #187's ADDED requirement *"Enumerated devices
   report their availability"* makes disabled or unplugged endpoints enumerable with `available=false`.
   The base spec contradicts shipped behaviour (HK-002 item 3).
5. `audio-capture`: all six capture requirements are ADDED, and **none is in the base spec yet** (checked by
   header). #188 and #187 add **different** requirement names, so there is no collision. Archive in merge
   order anyway (#188, then #187) so the spec's history reads as it happened.

---

## 1. Preconditions: evaluate mechanically, STOP if any fails (HK-021(r))

```bash
cd "D:/Projects/claude/OpenWSFZ/worktrees/qa"
git fetch origin
git rev-parse --short origin/main              # MUST be 4c21280d (or later: then STOP and escalate if any
                                               #   later commit touches openspec/ or ft8_shim.h)
grep -n "define FT8_SHIM_VERSION" src/OpenWSFZ.Ft8/Native/ft8_shim.h      # MUST be 20260051
grep -c "20260051" openspec/specs/ft8lib-interop/spec.md                   # MUST be >= 1
ls openspec/changes | grep -v '^archive$'      # MUST be exactly the 4 changes above
npx -y @fission-ai/openspec@1.3.1 validate --strict --all   # record the count (Architect: 64/0)
```

Work on a new branch off `origin/main`: **`qa/openspec-archive-sweep`**.

**Scope (HK-011):** docs under `openspec/` only, plus `tasks.md` record corrections. **No `src/`, no
`native/`, no rebuild, no shim bump, no VERSION bump** (nothing here changes behaviour). If any step appears
to need a `src/` edit, that is a defect in this spec: **stop and escalate, do not improvise.**

---

## 2. Task A: archive `decode-implausibility-marking` as WITHDRAWN (first; lowest risk; proves `--skip-specs`)

1. Precondition: `grep -rn "Geographically implausible decodes are marked\|Marked decodes transition to
   Dismissed" openspec/specs/` **MUST be empty.** The withdrawn text never reached a base spec. If it did,
   STOP. (Do **not** grep bare `implausib`: `callsign-structure-validation` and
   `engagement-target-validation` use "implausible" legitimately. The Architect's first draft made that
   mistake, and it was caught by dry-running the gate on `4c21280d`.)
2. Add one line at the top of its `proposal.md`, under the existing WITHDRAWN banner:
   `**Archived 2026-09-27 as WITHDRAWN — delta specs deliberately NOT synced (--skip-specs).**`
3. `openspec archive decode-implausibility-marking --skip-specs --yes`
4. Re-run check 1: still empty. `git diff origin/main -- openspec/specs/decode-noise-suppression/` is
   **empty**, so `--skip-specs` held. `openspec validate --strict --all` passes.
5. 🛑 No `tasks.md` exists, and **none is created**: nothing was built, so there is nothing to record.

---

## 3. Task B: `f001-l3-unresolved-by-code-export`: record correction, hand-sync, archive `--skip-specs`

### 3.1 Close the 10 open tasks by evidence or classification, never by ticking to pass tooling

| task | disposition |
|---|---|
| **5.2** full suite green | Evidence exists on an **unmerged local branch**: `f001-l3-task-5-2-confirmation` @ `4d1b8413` (2026-09-10, *"filtered suite confirmed green post shim 20260050"*). Cherry-pick it, or tick 5.2 citing `4d1b8413`. After that, the branch can be deleted (HK-003) |
| **7.1** Captain hard stop | Discharged by the merge: PR #140 → `1b7ca295`. 🔴 **Verify that the Captain's go for #140 is on record** (grep `board-archive-to-2026-09-24.md` for `#140` or `20260050`). If you cannot find it, mark `[~] merged via #140; sign-off record not located` and **say so in your report**. Do not tick it as if you had found it |
| **8.1** archive-ordering check | Tick with the evidence: no other unarchived change touches `ft8lib-interop` or `hashed-callsign-resolution` (both capture changes touch only `audio-*`, and `decode-implausibility-marking` is already archived by Task A) |
| **8.2 / 8.3** spec sync | Done **by hand** in §3.2. Tick them with a note that the MODIFIED ABI delta was deliberately not applied (it would regress `20260051`→`20260050`) |
| **8.4 / 8.5** validate / archive | §3.3 |
| **9.1** board + SHA | `[~] SUPERSEDED`: the shim has since advanced to `20260051`, and the L3 arm has already run and **closed** (#156, `463f9819`). The board records the closure. The Architect updates the board for this sweep (§7) |
| **9.2** branch hygiene | Tick after deleting the merged local `f001-l3-own-hash-compare-result` (merged; no remote ref) and `f001-l3-task-5-2-confirmation` (after 5.2). No worktree exists for either |
| **9.3** validate after archive | §3.3 |

### 3.2 Hand-sync into `openspec/specs/`

- `hashed-callsign-resolution/spec.md`: **append** the change's ADDED requirement *"Observable 12-bit hash-path
  unresolved-lookup sizing, by code"* verbatim, after the existing SUP-B sizing requirements.
- `ft8lib-interop/spec.md`:
  - **append** the ADDED requirement *"Diagnostic 12-bit hash-path unresolved-by-code native export"*
    verbatim.
  - In the ABI self-test paragraph (`:49`), **replace only** the sentence beginning
    `⚠️ \`20260050\` (\`f001-l3-unresolved-by-code-export\`, between \`20260049\` and this entry) is **NOT**
    reconstructed here` with one history sentence recording `20260050`: MEASURE-ONLY, the diagnostic
    `ft8_get_h12_unresolved_by_code` export (4,096-row, complement of `ft8_get_h12_by_code`), **no managed
    binding**, no decode-output change.
  - 🛑 **The pin stays `20260051`.** Every other word of that paragraph is carried verbatim.

### 3.3 Archive

`openspec archive f001-l3-unresolved-by-code-export --skip-specs --yes`, then
`openspec validate --strict --all` MUST pass.

---

## 4. Task C: `capture-stall-detection-unattended` (#188): audit tasks, sync, archive (before Task D)

### 4.1 Back-fill `tasks.md` as a RECORD CORRECTION (35 tasks)

🔴 Tick **only** a task for which you can name the artefact that discharges it. Known anchors:
- Build: `95d3a923` (*feat(capture-stall-detection): CaptureHealthMonitor daemon-lifetime ticker*). QA's
  review of it: approved 2026-09-24 (board, *Recently closed*).
- Merge: PR #190 → `42cf88f7` (Captain sign-off 2026-09-24 ~21:10Z).
- Live acceptance: `qa/capture-self-healing-live-verify/2026-09-25-l1-l4-results.md` (L1–L4 all PASS, the
  station, built from `9f54e6af`).
- Requirements/VERSION: `REQUIREMENTS.md` FR-020 amended plus the new FRs, VERSION 0.49 → 0.51 (board
  2026-09-24).
- The handoff in the change dir: `architect-to-qa-handoff.md`.

Rules:
- A task that did not happen: `→ DEFERRED (reason)` with a **real tracked follow-up** (a GitHub issue),
  or escalate. Never `[x]` (HK-002 item 1). The TX-device follow-on is already **#189**.
- macOS items: the standing CI-owned deferral. It is expected, not a finding.
- **Add one note at the top of `tasks.md`:** `Record correction 2026-09-27: boxes back-filled at archive
  time against named evidence. Note: squash commit 42cf88f7's title says "no src/ diff", but it carries
  src/ (CaptureHealthMonitor.cs etc.); the title is wrong, the merge is correct.`

### 4.2 Sync and archive

The deltas are ADDED-only, into `audio-capture`, so a **normal** archive syncs them:
`openspec archive capture-stall-detection-unattended --yes`. Then confirm the three requirement headers now
appear in `openspec/specs/audio-capture/spec.md`, and that `validate` passes.

---

## 5. Task D: `capture-device-reresolution` (#187): audit tasks, sync, archive, then close board Task 1.9

1. Back-fill `tasks.md` exactly as §4.1 (36 tasks; merge anchor PR #191 → `9f54e6af`; the same L1–L4
   results file). Note the rebase: #191 was rebased `--onto` after #190's squash, content-diff-verified
   (board, 2026-09-24).
2. `openspec archive capture-device-reresolution --yes` (ADDED-only: `audio-capture` ×3, `audio-device` ×1).
3. **Task 1.9 reconciliation (HK-002 item 3), after the archive:** `audio-device/spec.md:17`'s "one per
   **active** WASAPI capture endpoint" contradicts the requirement just added.
   - **Read the shipped code first** (`src/OpenWSFZ.Audio/WasapiAudioDeviceProvider.cs`,
     `src/OpenWSFZ.Abstractions/AudioDeviceInfo.cs`), and state in your report what it actually
     enumerates (which `DEVICE_STATE_*` mask it uses).
   - Then edit that scenario so it describes that, and nothing more.
   - 🛑 Do not guess the mask from the spec. If code and requirement disagree with each other, **STOP**:
     that is a `src/` question, not a docs fix.
4. `openspec validate --strict --all` passes.

---

## 6. Task E: verification gate (mechanical; any failure ⇒ STOP, never hand-patch to pass)

```bash
cd "D:/Projects/claude/OpenWSFZ/worktrees/qa"
# 1. The pin did NOT regress  <-- THE check that catches a blind f001 sync; it is otherwise silent
grep -c "20260051" openspec/specs/ft8lib-interop/spec.md              # >= 1
grep -n "SHALL be \*\*\`20260050\`\*\*" openspec/specs/ft8lib-interop/spec.md   # MUST be empty
# 2. The 20260050 gap is closed, the export is specified, the gap note is gone
grep -c "ft8_get_h12_unresolved_by_code" openspec/specs/ft8lib-interop/spec.md  # >= 1
grep -c "is \*\*NOT\*\* reconstructed here" openspec/specs/ft8lib-interop/spec.md  # 0
grep -c "unresolved-lookup sizing, by code" openspec/specs/hashed-callsign-resolution/spec.md  # 1
# 3. The withdrawn feature never reached a base spec
grep -rn "Geographically implausible decodes are marked\|Marked decodes transition to Dismissed" openspec/specs/  # MUST be empty
git diff origin/main -- openspec/specs/decode-noise-suppression/       # MUST be empty
ls openspec/specs | grep -c "decode-implausibility-marking"            # 0
# 4. The capture requirements landed, once each
grep -c "^### Requirement: Capture health is evaluated independently"   openspec/specs/audio-capture/spec.md  # 1
grep -c "^### Requirement: Stale capture device identifier is re-resolved" openspec/specs/audio-capture/spec.md  # 1
grep -c "^### Requirement: Enumerated devices report their availability" openspec/specs/audio-device/spec.md   # 1
grep -n "one per active WASAPI" openspec/specs/audio-device/spec.md    # MUST be empty (Task 1.9)
# 5. Nothing left open
ls openspec/changes | grep -v '^archive$'                              # MUST be empty
# 6. Validator, and the no-src guard
npx -y @fission-ai/openspec@1.3.1 validate --strict --all              # pass; count >= the §1 baseline
git diff --stat origin/main -- src/ native/                            # MUST be empty
```

Check 1 is the one that matters. A blind sync of f001's MODIFIED delta **still validates**; only the pin
grep sees it (HK-022).

**G9b:** commit first (`check_version_bump.py` reads proposals from git), then run it. Archiving moves two
`User-facing: yes` proposals. If G9b demands a VERSION bump for a pure archive move, **STOP and escalate. Do
not bump**: no behaviour changed.

---

## 7. Report and landing

- Report: the §1 baseline and the §6 outputs verbatim, each task's disposition (with **7.1's sign-off
  record found or not**), the Task 1.9 mask you read from the code, and any escalations.
- Commit locally on `qa/openspec-archive-sweep`. **Push and merge need the Captain's go** (HK-033/HK-010).
  It is docs-only, so HK-029's direct-merge exception is available **if the Captain says so**, with the
  empty `src/`/`native/` diff stated.
- The Architect updates `BOARD.md` on the result (Task 1.9 closed, the OpenSpec backlog cleared).
- 🔴 HK-025: if any step reads as a judgement dressed as a check, refuse it before running.
