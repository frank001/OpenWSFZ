# QA session handoff — §8.1 real-band replay IN FLIGHT (restart requested by the Captain)

- **Written (UTC):** 2026-09-29 20:54 by the outgoing QA session. **Only the QA session restarts.** The Architect and Developer sessions are untouched.
- **Read first:** `MEMORY.md` + `BOARD.md` (the board's 2026-09-29 20:00Z and 19:33Z entries), then this file. If the HK rules are not in your context at session start, STOP and tell the Captain.
- **Persona / branch:** QA, worktree `D:\Projects\claude\OpenWSFZ\worktrees\qa`, branch `qa/sub-feas` (check `git branch --show-current`). **Nothing is pushed** (HK-033). Stage by path only.

## 1. What is running RIGHT NOW (survives the restart)

A **detached** unattended replay, started 2026-09-29 20:49Z with the Captain's explicit go ("go for option 2"): the SUB-FEAS §8.1 real-band runtime replay on build `2b39cf18`.

| Item | Value |
|---|---|
| Spec | `qa/rr-study/2026-09-29-2010-architect-sub-feas-8-1-real-band-runtime-replay-spec.md` (Architect's worktree, branch `arch/subtraction-feasibility`) incl. **Amendment 1** (R0 via the producing DLL, R6 allowance constant 3000 ms) and **Amendment 2** (build fixed at `2b39cf18`, log grep prefix, R4 denominator = log lines) |
| Orchestrator | `qa/rr-study/sub-feas/replay81_run.py` (committed `cd36bb42`), running as a detached python process; resumable |
| Output dir (gitignored) | `D:\Projects\claude\OpenWSFZ\worktrees\qa\artefacts\rr_2026-09-29_replay81\` : `status.json`, `orchestrator.log`, `process_exits.log`, `preflight.json`, `r0.json`, `time\*.csv/*.log`, `env_start.txt` |
| Frozen selection | `qa/rr-study/results/2026-09-29-sub-feas-8-1-replay/selection.json`, SHA-256 `730d6ea61f25ba8cad90520a17266b3efe0e1e476b1bd1ce29d1a6cbcc3b1f15` (committed `f16d23be` BEFORE any timing). 60 pilot (20/run), 605 H, 300 M, 20 R6 pairs. |
| Builds (scratch, still on disk) | harness outputs `C:\Users\Frank\w-replay81-out-{2b39cf18,84cac119,51e40b55}`; checkouts `C:\Users\Frank\w-replay81-{2b39cf18,84cac119,51e40b55}` (git worktrees, detached). `libft8.dll` actual SHA-256: `2b39cf18` → `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5`; `84cac119` and `51e40b55` → `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba` (also the value recorded in each endurance run's `arm_config.json`). No independent pin exists (self-references only). |
| Harness commit (for the report) | `cd36bb42017012a805b561418c6b55f9cac87873` (harness + orchestrator); rows script `0a53979e`. |
| R0 (instrument validity) | **PASSED** for all three runs, 20/20 within ±1 each (`r0.json`). Timing began 20:49Z. |
| Expected duration | up to ~6.5 h worst case, likely far less. Phase order: H then M per run (`20260922_2056`, `20260923_1730`, `20260925_2010`), then R6. |

## 2. The Captain's standing instructions for this run (verbatim in substance)

He will be **asleep and unreachable**. "Check in on each run every 2 hours after monitoring it for 10 minutes, **no analysis at all**. Then do the analysis and final report." **Do not open, summarise or interpret any timing value while the run is in progress.** WSJT-X `FT991A` is cleaned and listening to B1 (AUX1) if ever needed; it is **not** needed for this offline replay.

## 3. What the outgoing session set up, and what dies with it

- The check-in schedule was created with `CronCreate` (session-only). **It dies with the session.** The new session must **re-create it**:
  - one-shot 10-minute monitor: skip (the run is already >10 minutes old by the time you read this);
  - recurring 2-hourly check: `3 1,3,5,7,9,11,13 * * *` (local time, machine is UTC+2), prompt below.
- **Check-in procedure (no analysis):** read `status.json`; last 15 lines of `orchestrator.log` and `process_exits.log`; `wc -l` the CSVs under `time\`; confirm the orchestrator python and `dotnet ... Replay81.dll` are alive (`Get-CimInstance Win32_Process`). If the orchestrator is dead and `status.json` phase is not `DONE`/`STOPPED_R0_FAILED`, **relaunch it** (it resumes; the harness skips rows already in the CSVs):
  ```
  cd D:\Projects\claude\OpenWSFZ\worktrees\qa\qa\rr-study\sub-feas
  nohup ../.venv/Scripts/python.exe replay81_run.py >> D:/Projects/claude/OpenWSFZ/worktrees/qa/artefacts/rr_2026-09-29_replay81_orchestrator.out 2>&1 & disown
  ```
  Report one short line to the Captain (phase, rows per file, any rc ≠ 0, alive yes/no).
- If `status.json` phase is `STOPPED_R0_FAILED`: report it, take no timing, stop.

## 4. When `status.json` says DONE — the analysis phase

1. `cd qa/rr-study/sub-feas && ../.venv/Scripts/python.exe replay81_rows.py` → writes `rows.json` and prints R0..R7 aggregates (mechanical; thresholds are the spec's constants; **do not tune them**).
2. Read the per-run/stratum aggregate table before summarising (HK-036 spirit). R1 is read **jointly with R4**; `fittedSignals` means signals **selected**, not fitted; R7 is descriptive only, **no decode-rate claim**; the blind spot (no real cycle above 32 signals, R6 is synthetic) goes up front (spec §3).
3. Write the final report **in the standard R&R format** (HK-034: copy the last instance's structure: header with SHA pair, Section 1, body tables, Section 5, **Section 6**, and the actual/pinned SHA pairs; quote the exact greps: `Sub-feas residual pass: residualDecodes=`, AV `WARN-TEMPLATE .*access violation`, contained `WARN-TEMPLATE Sub-feas residual pass failed`; quote **no `--filter`**, the selection SHA, harness commit `cd36bb42…`, `env_start.txt`/`env_end.txt` (what else was running). Model it on `qa/rr-study/results/2026-09-29-0d6b193-ON/report.md`.) Interpretations made before timing are in `select_81.py`'s header (pilot 20 per run; R6 pairs from the pooled H list sorted by stamp) and must be disclosed.
4. Commit by path on `qa/sub-feas`, local only; update `BOARD.md` in the same edit (HK-024); tell the Architect (`ListAgents`, **confirm persona**; they are `openwsfz-80` at the time of writing).
5. Clean up (HK-019): remove the three scratch worktrees `C:\Users\Frank\w-replay81-{2b39cf18,84cac119,51e40b55}` (`git worktree remove --force`; check for orphan `dotnet`/`Replay81` processes first) after copying anything needed; keep the gitignored raw output.
6. 🔒 NFR-021 / HK-037: aggregates and stamps only; no message text anywhere in a committed file.

## 5. Other state you inherit

- **Local, unpushed commits on `qa/sub-feas`** (HK-033: push only on the Captain's explicit go): `be18f7f1` (review report), `38ce9674`, `08cb8400`, `11aa51e1`, `bd3e645d`, `811fc6ae`, `795428ec` (R&R paired-run reports/configs/standard dirs), `6ecf2a37`, `4c77045d`, `7e4fe882` (flag-OFF control), `f16d23be`, `cd36bb42`, `0a53979e` (§8.1 replay). Untracked and deliberately left: `dev-tasks/2026-09-29-sub-feas-4-2-residual-pass-log-line-and-tests.md` (already executed by the Developer), `dev-tasks/2026-09-28-192-…`, the older `qa/**` untracked items.
- **Developer branch** `feat/sub-feas-native-subtraction`: `2b39cf18` (§4.2 log line + tests 6.3/6.5/6.6 managed) approved by QA (DLL unchanged); `ab95bea1` (tasks.md update). Local, not pushed. **Merge/push are the Captain's** (HK-010/033).
- **Decisions on record (Captain, 2026-09-29):** the `5f17b43` S1-audio follow-up is DROPPED; the paired S1–S8 OFF/ON sweep line for this build is CLOSED; the S1 +1.45 dB bias stays unexplained and is **never** cited as a build effect; §4.2 go given; §8.1 go given (this run). Merge sign-off is still open. §7 stability gate, §8.2 (independent real corpus) and §8.3 (live-use decision) are **not** satisfied; the flag stays OFF by default and in every live run.
- **Filed issues:** [#193](https://github.com/frank001/OpenWSFZ/issues/193) (Settings-page save resets `cycleAudioArchive`), [#194](https://github.com/frank001/OpenWSFZ/issues/194) (R&R WAV triage, discussion only).
- **Board** already has the 19:33Z, 20:00Z entries; **add the §8.1 result when it lands.**
- **Caveat on the flag-OFF control claim:** wherever "flag OFF is byte-identical" is cited it carries: native `ft8_decode_all` only, managed flag-OFF branch unexercised, synthetic audio, no independent DLL pins.
