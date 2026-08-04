# QA → Architect — Task 2 re-scope: the daemon-bringup blocker is gone; a second, deeper one exists

**Author:** QA, 2026-08-04 (19:02 UTC, `date -u`, per HK-017).
**Executes:** `qa/2026-08-04-1848-architect-to-qa-revised-board-after-consolidated-handoff.md` §7, T2.
**Verdict: still BLOCKED — but not for the reason my own 15:35 report gave.** Task 5 refutes that
reason. A different, previously-unflagged blocker sits underneath it, found by reading the harness
code rather than re-asserting the old blocker (HK-018).

---

## 0. What was asked

Re-scope Task 2's Sec.4 OpenWSFZ-only fallback (`qa/rr-study/2026-08-04-1535-…-BLOCKED-loopback-rig.md`)
against the rig Task 5 demonstrated. My own §2 called it blocked on "a running daemon on the
loopback device"; Task 5 stood one up. Confirm or refute; if still blocked, say why.

## 1. The precondition my 15:35 report cited — REFUTED

Task 5's `run_isolated_replay_generic.py::start_daemon`/`configure_daemon` brought up
`OpenWSFZ.Daemon.exe` against **`CABLE Output`** (the same VB-CABLE capture endpoint STUDY-SPEC
§4.1/§4.2 specifies) entirely through the daemon's own REST API
(`/api/v1/audio/devices`, `/api/v1/config`, `/api/v1/decode/start`) — no GUI automation tool
needed, contrary to what blocked WSJT-X's side of the rig.

Re-checked live, just now:

```
Get-Process wsjtx  → PID 29796, StartTime 8/3/2026 8:37:19 PM   (same PID as my 15:35 report)
Get-Process OpenWSFZ.Daemon → none running
```

`wsjtx.exe` has been running continuously since before Task 5 and through it, on whatever device
its normal live 20m monitoring uses (not CABLE — the standing rule is FT-991A/SDR Uno off the
antenna splitter). Task 5's daemon ran against CABLE concurrently with it for ~2.5h without
incident. That is direct evidence, not inference, that **CABLE is free and independent of the
currently-running WSJT-X instance**, and that QA can bring an OpenWSFZ daemon up on it safely and
repeatably without touching WSJT-X's Qt GUI.

**So: the specific thing my 15:35 report called blocked — "no way to get a running OpenWSFZ daemon
on the loopback device without GUI automation" — is refuted. Confirmed, as the Architect read it.**

## 2. What I found underneath it — the fallback has no code path

Sec.4's own line: *"If the WSJT-X leg is unavailable on the rig, run OpenWSFZ-only and disclose
it — the FP gate is a single-appraiser statistic and survives."* Re-scoping this task meant
checking whether the harness can actually do that, not just whether a daemon can be raised. It
cannot, today:

- **`qa/rr-study/run_study.py:182-187`** unconditionally does
  `shutil.copy2(WSJT_ALL_TXT, wsjt_dest)`, where `WSJT_ALL_TXT` (line 33) is the **live,
  currently-running WSJT-X install's own log** —
  `C:\Users\Frank\AppData\Local\WSJT-X\ALL.TXT`. There is no flag to skip this step.
- **`qa/rr-study/harness/matcher.py:71-72`** hard-exits (`ERROR: WSJT-X ALL.TXT not found`) if the
  resolved WSJT-X path doesn't exist. There is no `--owsfz-only` or equivalent, and `--wsjt` is
  effectively mandatory (`_resolve_paths`, lines 49-76).
- Repo-wide search for an OpenWSFZ-only code path (`openwsfz.only`, `owsfz_only`, `WSJT-X leg`,
  etc.) returns **zero hits outside the two prose sentences in the spec itself.** Sec.4's fallback
  was written into `STUDY-SPEC.md` and never implemented.

**This is not merely "the file is missing" (which would at least fail loudly).** Because
`wsjtx.exe` is genuinely running right now — live 20m monitoring, as it always is — `WSJT_ALL_TXT`
**does exist and has real content.** `run_study.py` would copy it without error, and
`matcher.py` would parse it without error. The failure mode is not a crash; it is silent
corruption: every real off-air decode WSJT-X logs during the test window, on whatever frequency
it's actually monitoring, gets matched against S5's signal-free truth slots by `cycle_utc`, and
counted as a spurious false positive for the WSJT-X appraiser column — a number with no relationship
to the instrument under test. That is a worse outcome than the clean single-appraiser degradation
Sec.4 describes, and it would look like a normal run.

**Getting the actually-intended OpenWSFZ-only behaviour** (skip the WSJT-X copy/match branch
entirely, report only the OpenWSFZ FP column) needs a small `run_study.py`/`matcher.py` change to
make the WSJT-X leg genuinely optional. That is a change to the ratified instrument, which Sec.4
itself says not to do here (*"Execute the ratified rule as it stands. Do not draft a new one"*) —
I have not made it, and it needs disclosure/authorisation the way Task 5's adaptations got theirs,
not a silent patch inside this task.

## 3. Disposition

**Confirmed:** the rig/daemon-bringup blocker Task 2 cited is gone — Task 5 is direct, reproducible
proof, re-verified live today.

**Refuted (partially) / stays BLOCKED:** Sec.4's OpenWSFZ-only fallback cannot be run as specified
without a harness change, because that fallback was never implemented, only described. Running it
against the currently-running WSJT-X's real log would not fail — it would quietly produce a wrong
number.

**Not done here:** no harness edit, no S5 run, no dummy ALL.TXT workaround. All three would be a
QA judgement call on a ratified instrument's contract, which is the Architect's or the Captain's to
authorise, not mine to improvise (HK-004 cuts the other way once the fix needed is a code change
rather than an operational step).

**S5 proper** (WSJT-X + OpenWSFZ both live) remains blocked on WSJT-X's GUI, unchanged, and is the
Captain's per the original disposition.

## 4. What would unblock the fallback, priced small

1. `matcher.py`: make `--wsjt` optional; when absent, skip WSJT-X parsing/matching entirely rather
   than defaulting to a path.
2. `run_study.py`: gate the `WSJT_ALL_TXT` copy behind a flag (e.g. `--openwsfz-only`), and skip
   passing `--wsjt` to the matcher when set.
3. `analyse.py` already tolerates a single appraiser's data being empty (`_fp_rate` iterates per
   appraiser, line ~662-709) — no change looked necessary there on inspection, but this wasn't
   exercised end-to-end and should be checked once 1-2 land.

Rough cost: under an hour of `qa/`-tooling edit (not `src/`, HK-011 doesn't gate it) plus the ~1h
S5 run itself. Not started — flagging the price per HK-004, not doing it unprompted, since it
touches a ratified instrument's argument contract.
