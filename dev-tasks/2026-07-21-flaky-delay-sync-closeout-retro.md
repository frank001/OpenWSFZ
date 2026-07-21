# Retrospective — fix-flaky-test-delay-synchronization (closeout)

**Date:** 2026-07-21
**Change:** `fix-flaky-test-delay-synchronization` (proposed 234eeab; Phases 0–3 = PRs #94/#95/#96/#98)
**Status at closeout:** all `tasks.md` items complete; archived.

## What shipped

A shared polling library (`tests/OpenWSFZ.TestSupport/Poll.cs`, `Poll.UntilAsync` + typed
`WaitFor*` wrappers) replacing hand-duplicated per-test wait helpers, plus **Gate G10**
(`tools/check_test_delay_sync.py`) — a blocking-from-day-one lint that fails any *new/untracked*
bare `Task.Delay(<numeric literal>)` used as a synchronization barrier under `tests/**` (except the
library's own implementation), tolerating a pre-enumerated debt backlog exactly like Gate G3's
`traceability-debt.md`. ~150 audited sites migrated across four phases in disjoint files.

## The four originally-confirmed flakes — all now covered

- `WaitReport_Retry_BracketsRetransmissionWithTxAnswer` (retry-bracket) — Phase 1/2 migration onto
  the shared library. This is the flake `dev-tasks/2026-07-20-flaky-waitreport-retry-delay-sync.md`
  had tracked as an open follow-up; it is now resolved by this change.
- `WaitRr73` retry-bracket (PR #94's original target) — migrated.
- `PttWatchdogTests.Disarm_BeforeTimeout_CallbackNeverInvoked` — Phase 1, fully diagnosed, migrated.
- (fourth confirmed site in the same retry-bracket/Answerer family) — migrated.

**Explicitly out of scope** (different root causes, not addressed here): N8; F-003
(`f-003-ap-assist-flaky-decode-test`).

## Gate G10 health

Green (no untracked-debt failures) since Phase 0 landed. At closeout the debt file holds **19
tracked entries** — all legitimate and permanent, NOT residual backlog: simulated mock/IO latencies
inside test feeds (`Task.Delay(10, feedCts.Token)` etc.), real `DaemonStartup` timing (300/250 ms),
and the `PollTests` primitive's own deterministic delays (20–30 ms). The design's "complete when the
debt file is empty" wording was an idealization; Decision 4 already provided the safety valve for
intentional tracked exceptions, which is what these are.

## Closeout gotcha (worth remembering)

The G10 debt file originally lived inside the change dir with a **hard-coded default path** in
`check_test_delay_sync.py`, and the gate is *permanent* CI infra (wired into `pre_merge_check.py` +
`ci.yml`). A naive `/opsx:archive` would have moved the debt file to `openspec/changes/archive/…`
out from under that default → gate exit 2 (file-not-found) → **broken CI on every subsequent PR**.
Fix at closeout: relocated `test-delay-debt.md` to the **repo root** alongside `traceability-debt.md`
(G3's precedent) and repointed `DEFAULT_DEBT_FILE`. Lesson: when a change introduces a permanent gate
whose allowlist/debt file lives in the change dir, relocating that file is part of the closeout, not
an afterthought.
