# TODO — settings-page heartbeat stall, 2026-08-03T18:58:09Z. One occurrence, one non-recurrence. Not chased.

**Filed:** QA, 2026-08-04 (14:26 UTC, `date -u`, per HK-017). Repo at `ceaabc2`.
**Per:** `2026-08-04-1416-architect-to-qa-post-cap-lift-work-order.md` §5. **Do not chase this** —
filing only, per the Architect's ruling: no mechanism identified, insufficient evidence to act on.

---

## What happened

The 8080 daemon (PID 14600, up 1 h 45 m, no `[ERR]`/`[FTL]`) went silent while the Captain viewed
the decoder-settings page. It did **not crash** — the process stayed up, silent. The supervisor
caught a heartbeat stall of **> 90 s** at **2026-08-03T18:58:09Z** and restarted it, costing 4
cycles and splitting the 2026-08-03/04 drift-screen corpus into two epochs (epoch 0: 1.76 h;
epoch 1, decisive: 18.96 h — see `2026-08-04-1405-qa-to-architect-ft991a-cap-drift-screen-PASS.md`
§1, §3). `config.json` was unmodified — nothing was written, so a read-only page appeared to stall
the capture heartbeat.

## The reproduction attempt

The Captain attempted to reproduce it and could not. `ui_stall_check.py`, pre-registered at
`1ff4293` before the attempt, fires **ROW 4 NOT REPRODUCED** — verified as not depending on the
exact open-time (checked at 19:08:00Z, 19:12:00Z, 19:30:00Z against the single successor log;
under the input contract landed 2026-08-04 (§ below), 19:08Z and 19:12Z now correctly VOID on C3
for insufficient baseline, and **19:30Z clears and still fires ROW 4** — the reported conclusion
is unchanged by the fix).

Cadence over the complete 18.96 h decisive epoch: **13,655 heartbeats at 5.00 s cadence, zero
gaps ≥ 30 s**, one 23.40 s excursion at 19:08:29Z — the sole anomaly in eighteen hours, sitting
close to where the reproduction attempt would have taken place. It cleared no bar and mandates no
action. It is not nothing.

## Why this is filed, not chased

- **One occurrence, one non-recurrence, no mechanism.** `ui_stall_check.py`'s own row taxonomy has
  no row that means "safe" — NOT REPRODUCED is the strongest available negative, and it explicitly
  does not clear the daemon.
- No code path was identified connecting a read-only settings-page view to a capture-heartbeat
  stall. Speculating about one without further evidence would be arming a hypothesis, not filing
  a fact.
- Per the work order: **do not chase.**

## What must be carried forward if this is ever revisited

1. **The settings page is not cleared.** A future incident touching it should not be treated as a
   first occurrence.
2. **`ui_stall_check.py` now has a pinned input contract** (C1–C3, landed 2026-08-04) — exactly one
   `--log`, open-time must fall inside that log's own heartbeat coverage, and a truncated baseline
   VOIDs rather than silently shrinking. Any reuse must supply the single log for the process
   actually under test at the open-time in question.
3. If a third attempt is ever made, it should be timed to land with a full 900 s of clean baseline
   already elapsed since the daemon's last restart (C3), or it will VOID rather than measure
   anything.

## Status

**Open. Unchased. No action pending.**
