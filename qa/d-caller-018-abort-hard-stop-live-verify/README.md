# D-CALLER-018/016 abort hard-stop — live verification

`live_verify_abort_hardstop.py` is the live, hardware-in-the-loop verification required by
`dev-tasks/2026-07-12-answerer-abort-hard-stop-and-reengage-timing.md` §5. It starts a real,
isolated `OpenWSFZ.Daemon` instance (own scratch port/config, never touches the Captain's real
config) and drives it over its real HTTP/WebSocket API — no `FakeTimeProvider`, no mocked
`IPttController` — reproducing the exact production sequence from
`logs/openswfz-20260712T211150Z.log` (arm a pending CQ target, let the late-start guard defer it,
hammer the dedicated Abort button while Idle, wait past the next matching-phase window, confirm no
re-engagement).

Run it after `dotnet build OpenWSFZ.slnx -c Release`:

```
python qa/d-caller-018-abort-hard-stop-live-verify/live_verify_abort_hardstop.py
```

Requires a real audio output device (no virtual cable needed — `AudioOnlyPttController`'s CQ
transmission doesn't require a decode input). Exit 0 = PASS, 1 = FAIL, 2 = ENVIRONMENT-UNAVAILABLE
(report still written in that case).

## `live-reports/` — what's in here

- **`2026-07-12T221248Z-d3eff84.md` — PASS.** Run against the fix (`AbortAsync`'s unconditional
  clear + `MaxLateStartSeconds = 2.0`). Both phases pass: A (sanity control — a timely arm fires a
  real transmission, then Abort mid-TX stops it promptly — AC-3 live regression) and B (the actual
  defect — a late-armed target is hammered with Abort while Idle, then never fires ~30 s later).
- **`2026-07-12T221403Z-d3eff84.md` — FAIL, deliberate control run.** Same script, run with
  `QsoAnswererService.cs`'s fix temporarily reverted (`git stash` of just that file) to prove the
  script actually catches the regression rather than false-passing. Phase B fails exactly as the
  production log did: `Q9BUG` fires ~29 s after the 14-click Abort hammer
  (`"QsoAnswererService: pending CQ target 'Q9BUG' at 1600 Hz - answering at A phase."` in the log
  tail). The fix was restored and rebuilt immediately after this run.
- **`2026-07-12T221518Z-d3eff84.md` — PASS.** Final confirmation run with the fix restored, kept
  as the PR's attached evidence per dev-task §5.

(An earlier run, `2026-07-12T221048Z-d3eff84.md`, failed on a script bug — a regex requiring the
literal em dash `—` that the daemon's console sink silently downgrades to a plain hyphen on
Windows, the same encoding gotcha `qa/tx-keying-live-verify/live_verify_keying.py` already
documents — not a product bug. Fixed in the script and the report was deleted to avoid confusion.)

## AC-5 (D-CALLER-019 front-end cleanup) — verified separately, not by this script

The `web/js/main.js` dblclick-handler cleanup (removing the redundant legacy `postTxAnswerCq`
listener) was verified live in a real headless Chromium browser against a real running daemon:
loaded the real `index.html`, injected a synthetic `decode` WebSocket frame so the real,
unmodified `handleDecodes()` created a real `<tr class="decode-cq">`, then performed a real
browser double-click on it. Result: exactly one outbound `POST /api/v1/tx/engage-decode`, zero
`POST /api/v1/tx/answer-cq` calls, zero console errors. That one-off Playwright driver was not
committed (this repo has no Node/Playwright dependency anywhere else) — the result is recorded
here for the record; see the PR description for the raw evidence.
