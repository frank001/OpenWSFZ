# QA session handoff — context about to be cleared, live run ended, moving to ANOVA reports next

**Author:** QA (this session), 2026-08-02 16:18Z (`date -u`, per HK-017). Written specifically
because the Captain is clearing this conversation's context before starting work on ANOVA
reports. This supersedes both prior handoffs
(`2026-08-01-2001-qa-context-clear-handoff-multiday-20m-live-run.md`,
`2026-08-01-2216-qa-context-clear-handoff-2-loop-replaces-cron.md`) for run-state purposes — the
run they describe **has now ended**. Read this one first; the older two are provenance/history
only, nothing in them describes current reality.

---

## 1. The live run is over — nothing is running, verify before assuming otherwise

The multi-day 20m 8080/8081 live run (started 2026-07-31) was deliberately ended
2026-08-02 ~15:52Z. Full teardown completed and verified:

- Both daemons killed (8080, 8081), both supervisor process trees killed, the standing
  `status-check-loop.sh` killed, a full orphan sweep run twice (caught and killed two stray
  `tail.exe` — one a known HK-023 half-detached-`TaskStop` artifact, one a genuine leftover from
  an earlier supervisor incarnation predating this session).
- Re-verified clean immediately before writing this handoff (16:17Z) — zero matches for
  `OpenWSFZ.Daemon.exe`, `supervisor-8080/8081`, or `status-check-loop` in `Win32_Process`
  (aside from harmless self-matches from the verification command itself, and unrelated
  `claude.exe` background sessions that merely have those directories in their `--add-dir` list).
- **Do not assume this is still true without re-checking** if picking this up much later — but as
  of this handoff, confirmed stopped.

## 2. Final corpus location

- `artefacts/20260731_live_run_2004-8080/` — 184,918 `ALL.TXT` lines, 10,489 WAVs, all 5 daemon
  log files spanning every restart this run had, WSJT-X-side comparison copy.
- `artefacts/20260731_live_run_2004-8081/` — 212,422 lines, 10,512 WAVs, single continuous
  daemon log, WSJT-X-side comparison copy.
- Both have `contents.md`/`contents.html` with mechanical facts filled in; **"Headline result" is
  still TODO in both** — whoever writes up this run's analysis needs to fill that in.
- **Read `artefacts/README.md` before touching either folder's `wsjt-x/` subdirectory.** The
  WSJT-X-side data in both is **hardlinked together** (de-duplicated 2026-08-02, ~3.5GB freed,
  all 10,470 files hash-verified identical first) — deleting one side is always safe, but most
  backup tools don't preserve hardlinks, so a backup/restore cycle can silently turn it back into
  two full independent copies (harmless, just loses the space saving). This was a direct Captain
  request ("make a note of this... important whenever I restore a backup") — the README is the
  durable record, not this handoff.

## 3. New tooling capability this session — uncommitted, your call whether to commit

`tools/gather_live_run_artefacts.py` gained `--wsjtx-link-from` and `--dedupe-existing`
(hardlink-based de-dup for the WSJT-X-side data shared between paired `-8080`/`-8081` gathers,
with a full copy-fallback path if the two folders aren't on the same volume). **This is a real,
tested, working change but it is NOT committed** — `git status` shows
`M tools/gather_live_run_artefacts.py` sitting in the working tree. Per HK-011, qa-tooling
changes (not `src/`) are QA's to make directly, but nothing here commits on its own initiative —
ask the Captain, or he'll ask for it, before creating a commit. Both new flags were proven
end-to-end this session (scratch-directory tests for hardlink/fallback/mismatch-detection
behavior, then the real 3.5GB de-dupe on the actual run's artefacts) — not just written and
hoped to work.

Also cleaned up a stray `nul` file that had appeared at the repo root (a `2>nul` redirect
mis-interpreted by git-bash during a Windows `rmdir` attempt, not anything meaningful) — gone,
don't be alarmed if you see it referenced in scrollback.

## 4. The open engineering thread from this run — still unresolved, now well-characterized

The 8080 decode-collapse defect (first found 2026-08-01) recurred **twice more** during this
session before the run ended — Windows 6 (`00:39Z`) and 7 (`13:43Z`), both handled correctly by
the QA-judgment autonomous restart policy, both confirmed recovered. Autonomous-restart tally
finished at **2/5**, cap never approached.

**The one finding worth carrying forward prominently:** recurrence interval (uptime-since-prior-
restart) was ~14h → ~13h42m → ~13h03m across the three occurrences — tight enough to strongly
suggest an uptime/state-accumulation trigger rather than time-of-day or band conditions. Full
detail: `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` §8 (the update section
added this session) and `qa/endurance/2026-07-31-2dacd1a/CONTAMINATION-NOTE.md` Windows 6/7. Root
cause is still **not identified** — this is the top open item from the whole run, not something
this session solved, just characterized better.

Also found and logged in Window 7: a restart that passed its own single-point heartbeat
confirmation died again ~76 seconds later, only caught by the supervisor's independent
heartbeat-stall watchdog. Flagged in the dev-task as a reason not to trust a single post-restart
heartbeat check as proof of durable recovery, for whoever eventually improves this tooling.

## 5. What's next: ANOVA reports

The Captain's stated direction for the next session, **no further detail given yet** — do not
assume scope, ask first. Likely-relevant pre-existing tooling, not yet inspected this session for
fitness against the new corpus: `qa/endurance/anova_common.py`, `endurance_anova_jt9.py`,
`endurance_anova_wsjtx.py`. Whether these target the freshly-gathered `artefacts/
20260731_live_run_2004-{8080,8081}/` data, the live (now-static) `OpenWSFZ-{8080,8081}-capture/`
directories directly, or something else entirely (a different corpus, a different question) is
unknown — get that from the Captain, don't guess and start running analysis scripts.

## 6. Where everything lives

- Final corpus: `artefacts/20260731_live_run_2004-8080/`, `-8081/`, and `artefacts/README.md`
  (hardlink/backup policy note).
- Run history/incident record: `qa/endurance/2026-07-31-2dacd1a/CONTAMINATION-NOTE.md` (now
  marked RUN ENDED at the top, 7 windows total, final tally 2/5).
- Open defect: `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` (§8 is the
  freshest section).
- Tooling change pending commit decision: `tools/gather_live_run_artefacts.py` (git diff shows
  ~220 new lines — `link_or_copy`, `link_or_copy_wsjtx_from`, `dedupe_wsjtx_in_place`,
  `sha256_file`, `count_lines`, plus the `--wsjtx-link-from`/`--dedupe-existing` CLI wiring).
- Prior handoffs (history only, run-state superseded by this doc):
  `qa/cycleframer-alignment-replay/2026-08-01-2001-...md`,
  `qa/cycleframer-alignment-replay/2026-08-01-2216-...md`.
- Project memory still doesn't know about the hardlink/backup gotcha (no direct memory-write
  tool available this session) — `artefacts/README.md` is the durable record regardless; worth
  confirming it made it into standing memory next time memory state is visible.

## 7. First thing to do in a fresh session picking this up

1. `date -u` for a real timestamp.
2. `git status` — confirm whether `tools/gather_live_run_artefacts.py` is still uncommitted, and
   whether anything else changed since this handoff.
3. Re-verify nothing from the old run is still running (§1's `Win32_Process` query) if there's
   any doubt — should be clean, but don't inherit that as an assumption without a beat of
   checking, especially if significant time has passed.
4. Ask the Captain what specifically he wants from "ANOVA reports" before opening the
   `qa/endurance/*anova*.py` scripts — §5 above, this session doesn't know the scope.

Per HK-011/HK-014, nothing here touches `src/` uncommitted beyond the tooling script noted in §3;
per HK-017 timestamp is real `date -u`, not hand-typed.
