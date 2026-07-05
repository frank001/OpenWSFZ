# DEV TASK — f-004-operator-visibility-improvements: implementation kickoff

**Date:** 2026-07-05
**OpenSpec change:** `f-004-operator-visibility-improvements` — proposal/design/specs/tasks
complete, `openspec validate --strict` passes (7 capability deltas:
`daemon-status-visibility`, `tx-state-indicators`, `log-viewer`, `waterfall-cursors`,
`web-frontend`, `qso-controller`, `qso-caller`)
**Branch:** `feat/f-004-operator-visibility-improvements` (exists, pushed, rebased onto
current `main` as of `b42170d`)
**Status:** Ready for implementation — no application code has been written yet, only
OpenSpec artifacts (this is a genuinely fresh start, not a resumed branch)

---

## 1. Context

Four independent operator-facing GUI/status gaps, each grounded in an existing, already-wired
data path:

1. **Shim version visibility** — the native FT8 decoder shim's loaded ABI version is checked at
   startup but never exposed; surface it on `GET /api/v1/status` and the Advanced settings tab.
2. **TX/Call-CQ visual states** — `#tx-enable-btn` currently collapses "armed but idle" and
   "actually transmitting" into one flat colour; split into dark-red/bright-red.
3. **Waterfall click safety** — a bare unmodified click (including right-click) currently
   retunes RX/TX with zero confirmation; gate all four interactions behind Ctrl/Shift.
4. **Log viewer** — no way to inspect the daemon's log from the browser; add a polled tail tab
   plus a standalone full-log page.

A fifth item was folded in mid-review, and it's the one with real backend weight — don't
mistake it for a styling tweak:

5. **Call-CQ button graceful stop** — the Captain ruled that clicking `#tx-call-cq-btn` while a
   CQ session is engaged should stop it, not just recolour it. This revives a
   previously-drafted-but-never-shipped handoff, `dev-tasks/2026-06-26-caller-cq-stop.md`
   (FR-CQ-STOP-001) — see §2 below for how to use it safely.

Full rationale and all four/five decisions (including two rejected alternatives per decision)
are in `design.md` — read it before starting, it's short and answers most "why this way"
questions in advance.

## 2. Work breakdown & suggested sequencing

Follow `openspec/changes/f-004-operator-visibility-improvements/tasks.md` §1–§8 in order —
they're already dependency-ordered and each task cites its governing spec/design section. The
notes below are pitfalls found during spec review, not a restatement of the tasks themselves.

### §1 — Shim version visibility

Small and self-contained. No dependency on anything else in this change — a reasonable first
PR-sized chunk if you'd rather land the four/five items incrementally (design.md's own stated
goal is that each item's blast radius stays independently reviewable).

### §2 — TX-enable button visual states

Straightforward client-side mapping over existing `txState` fields (design.md Decision 2). No
server-side change.

### §3 — Call-CQ button: engaged colour + graceful stop

**This is the one with real backend surface.** Read design.md's Decision 2b in full before
touching code.

- New `IQsoController.GracefulStopAsync` (default no-op), `QsoCallerService` implementation,
  `QsoControllerRouter` delegation, `POST /api/v1/tx/stop-cq` — see the `qso-controller` and
  `qso-caller` spec deltas for exact requirements and scenarios.
- Frontend: `#tx-call-cq-btn`'s `disabled` condition changes from `state !== 'Idle'` to
  `role !== 'caller' && state !== 'Idle'`. This is a functional behaviour change (the button
  stays clickable throughout an engaged session), not a CSS-only change — confirm your diff
  touches the click handler and disabled logic, not just classes.
- Task 3.2's technical shape is **adapted from** `dev-tasks/2026-06-26-caller-cq-stop.md`
  (FR-CQ-STOP-001). That handoff has exact-looking code diffs — field names, line numbers,
  method bodies — but it predates five later caller-UX fixes (D-CALLER-006 through 015, all
  merged since). Treat it as a strong, verified-at-review-time starting point, **not a literal
  patch**: re-check every field/method/line it references against the current file before
  applying anything from it.
- **Do NOT** bring over that same handoff's FR-CQ-COLOUR-001 two-tone colour scheme (bright
  green only while transmitting the CQ itself, dark green once a resulting QSO is in progress).
  This change's own Decision 2 already settled on a single steady bright-green for the whole
  engaged period, independently and later. If you think the two-tone scheme is actually better,
  raise it with the Captain — don't silently swap it in because you found it in the old handoff.

### §4 — Waterfall click modifiers

Self-contained. The breaking change (existing plain-click muscle memory stops working) is
intentional per design.md Decision 3 — don't add a transition period, dual-scheme fallback, or
"still works but warns" compatibility shim. The point of the change is that an unmodified click
becomes inert.

### §5–§6 — Log viewer (backend + frontend)

Self-contained pair, no config schema changes, no interaction with §1–§4.

### §7 — Test coverage

Every ADDED/MODIFIED requirement across all seven capability delta files has explicit
Given/When/Then-style scenarios — each one wants a corresponding test; don't treat the spec
scenarios as documentation-only.

- Task 7.6 (`GracefulStopAsync` unit tests) needs explicit `WaitAnswer` **and** `WaitRr73`
  coverage — `WaitRr73` is the one state being newly added to the wakeup-eligible set, and it's
  the easiest case to forget since it doesn't come up anywhere else in this change.
- Task 7.3 needs the full state × armed × role matrix for both TX buttons, not just the "happy
  path" states — the `tx-state-indicators` and `web-frontend` spec files enumerate the exact
  cases expected.

### §8 — Handoff

Leave 8.3 (`/opsx:archive`) until after merge.

## 3. Before opening a PR

- `openspec validate --strict --changes` must still pass — it does today; don't let spec edits
  regress it.
- Full `dotnet test` — 0 new failures, including everything added under §7.
- Task 3.10 (visually confirming a mid-transmission "Stop CQ" click lets the sample finish
  audibly before the panel reverts) needs an actual manual run, not just code review — same
  category of risk as the flaky decode test found on `f-003-ap-assist` (see
  `dev-tasks/2026-07-05-f-003-ap-assist-flaky-decode-test.md`): a claim about runtime behaviour
  that reading the diff alone can't confirm.
- Rebase onto current `main` before opening the PR if it's moved further since `b42170d`.

## 4. QA review

Standard process: QA reviews the diff against this change's OpenSpec artifacts, checks
task-completion-on-archive and spec-sync state, and signs off before merge. Please hold the
merge for that review to land rather than proceeding once CI is green — `f-003-ap-assist`
merged this week with a self-documented blocking flaky-test finding still open (same commit,
one second before merge); let's not repeat that pattern on this one.

## 5. Post-merge clean-up

Implementation is happening in a separate git worktree
(`D:\Projects\claude\OpenWSFZ-gui-configuration`, branch
`feat/f-004-operator-visibility-improvements`), checked out alongside the main worktree
(`D:\Projects\claude\OpenWSFZ`, branch `main`) so that QA review and other work could continue
on `main` without disturbing implementation in progress, and vice versa. This is scaffolding
for the duration of this change only — once the PR is merged, remove it properly rather than
just deleting the folder:

```bash
# from the main worktree (D:\Projects\claude\OpenWSFZ)
git worktree remove D:/Projects/claude/OpenWSFZ-gui-configuration
git branch -d feat/f-004-operator-visibility-improvements
git worktree prune
```

`git worktree remove` will refuse if the folder has uncommitted or unpushed changes — treat
that as a signal to check rather than an obstacle to force past. Include this as part of §8's
handoff clean-up, after `/opsx:archive`.

## 6. References

- `openspec/changes/f-004-operator-visibility-improvements/{proposal,design,tasks}.md` — source
  of truth for everything above; read `design.md` first
- `openspec/changes/f-004-operator-visibility-improvements/specs/*/spec.md` — the seven
  capability deltas (four ADDED capabilities, three MODIFIED: `waterfall-cursors`,
  `web-frontend`, plus the two backend deltas for §3)
- `dev-tasks/2026-06-26-caller-cq-stop.md` — FR-CQ-STOP-001, prior art for §3's backend work;
  verify against current code before reusing any of its literal diffs
- `dev-tasks/2026-07-05-f-003-ap-assist-flaky-decode-test.md` — unrelated, separate open item on
  a different (now-merged) change; don't conflate the two while both are in flight
