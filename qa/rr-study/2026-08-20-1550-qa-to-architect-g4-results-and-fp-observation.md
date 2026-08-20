# QA -> Architect: G4 result -- ROW 1 fires, PASS. Plus an unplanned FP observation (no verdict).

**UTC:** 2026-08-20 15:50Z
**Executes:** `2026-08-20-1455-architect-to-qa-s3-regrid-ruling-and-g4-preregistration.md` Sec.2,
gate committed at `13f2890` before this run existed.
**Result: OpenWSFZ decode count = 100/100 at dt=0, SNR=0dB -> ROW 1 fires -> PASS.**

---

## 1. Pre-flight (Sec.2.4 of the pre-registration)

- `wsjtx.exe` (PID 30016) running under the `FT991A` profile, `jt9.exe` helper pointed at
  `WSJT-X - FT991A` -- same profile G3 confirmed warm.
- `OpenWSFZ.Daemon.exe` was **not** running at task start (`GET /api/v1/status` -> connection
  refused). Started from the existing Release build
  (`src/OpenWSFZ.Daemon/bin/Release/net10.0/win-x64/publish/`, `shimVersion 20260042`,
  `libft8.dll` SHA256 `6890d84c...`). Re-checked after start: `"state":"Running"`,
  `"captureActive":true`, `"audioDevice":"Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"` --
  matches the daemon's on-disk config (`%APPDATA%\OpenWSFZ\config.json`), unedited.

## 2. Run

```
python run_study.py --scenarios S3b --parts 0 --device "Voicemeeter AUX Input" --skip-warmup
```

100 trials, `S3b` part 0 only (`dt_s = 0.0, snr_db = 0`), ~50 minutes wall clock
(14:58:45Z - 15:48:45Z, one trial per 30s slot pair). `--skip-warmup` used because
`harness/warmup.py` blocks on an interactive confirmation this session cannot answer; substituted
with the mechanical pre-flight above, which checks the same two facts the human "yes" would have.

Run directory: `qa/rr-study/results/2026-08-20-13f2890/` (named for the commit the code was at).

## 3. Gate read (verbatim from the pre-registration, Sec.2.3)

Matcher output: **WSJT-X 100/100 matched (100.0%), 0 misses. OpenWSFZ 100/100 matched (100.0%),
0 misses.**

| Row | Condition (OpenWSFZ decode count / 100) | Fired? |
|---|---|---|
| **1** | **>= 95** | **YES -- 100/100. PASS.** |
| 2 | 90 - 94 | not reached |
| 3 | <= 89 | not reached |

**Row fired: 1 -- PASS.** The live chain (synthetic playback -> Voicemeeter AUX Input -> B1 ->
WSJT-X + OpenWSFZ) decodes the dt=0 baseline reliably. Per Sec.4 of the pre-registration, this
does **not** by itself authorise the full 10-part/4.2h S3b sweep -- that stays its own go/no-go,
asked for below.

## 4. Unplanned FP observation -- Captain's direction: recorded, no verdict (option 1)

**Not part of G4's gate. Does not affect the ROW 1 result above** -- the matcher keys on message
content, so these are a separate bucket the 100/100 count above already excludes correctly.

**Context, so this isn't read as new:** raised by the Captain mid-run, 2026-08-20. Same complaint,
same mechanism family the Captain raised 2026-08-04 (`d57ebb2`,
`2026-08-04-1500-architect-to-qa-spec-false-positive-surge-and-window4-closure.md`) about
`be5960a` (the capture-window drift fix) -- *"a whole lot of false positives since the drift
fix."* That spec's Task 2 (the ratified S5 gate, signal-free slots, PASS iff FP rate <=6.0%
Clopper-Pearson UB) was never completed -- blocked needing WSJT-X's GUI live alongside a bench
daemon, per `project-state-2026-08-04-post-lift-board-closed-pr121-merged.md`. Task 3 (candidate-
budget saturation/rivalry) landed PARTIAL, not promoted to a finding.

**What G4 incidentally captured is not that gate** -- S5 needs signal-free slots; every G4 cycle
carries our injected signal. It cannot close Task 2. But it is a clean, unplanned WSJT-X-vs-
OpenWSFZ comparison on identical live input, which that thread never actually got, so it is
recorded here factually, same discipline as the 2026-08-04 spec's own Task 4 ("report the
distributions, draw no verdict"):

| | Total decodes | Correct (`CQ Q1ABC FN42`) | Extra/spurious |
|---|---|---|---|
| WSJT-X | 100 | 100 | **0** |
| OpenWSFZ | 108 | 100 | **8** |

Window: `260820_145845` - `260820_154845` (the full run), read directly from both `ALL.TXT`s and
manually time-bounded -- **not** taken from `S3b_matched.csv`'s own FP column (see Sec.5, that
figure is uninterpretable). All 8 extra OpenWSFZ decodes: SNR -25 to -29 dB (deep noise floor,
nowhere near a real signal), small negative DT (-0.4 to -1.6 s), frequencies away from the
injected 1500 Hz tone. 8 distinct cycles, no cycle produced more than one.

**One fact worth carrying forward, stated as an observation not a conclusion (HK-021(i) --
observation is not independence, n=8 is not a rate with a usable CI):** this scenario is
single-signal-per-cycle. `K_MAX_CANDIDATES` (140 pass 0, 200 pass 1) is nowhere near saturated --
one injected candidate plus incidental noise-floor candidates, not the dense multi-signal
condition Task 3's saturation/rivalry hypothesis was built around. The phenomenon still occurred.
That is mild evidence the mechanism is not *purely* candidate-budget rivalry (which needs
saturation to bite) -- consistent with a base per-candidate false-decode rate that saturation
would compound on top of, not replace. **Not a finding. Flagging it so it is available when Task 2
(or its replacement) is eventually run**, not re-derived from scratch.

## 5. Instrument note, not a finding: `S3b_matched.csv`'s own "FP" column is not usable

`run_study.py`'s log-collection step copies the **entire** `ALL.TXT` (57,921 lines, accumulated
since long before this run -- the file's last write before this session was 2026-08-15) rather
than a time-windowed slice. `matcher.py` then counts every unmatched line in that whole file as an
"FP" against this scenario's 100 truth rows: `57,921 - 100 = 57,821`, exactly the number the
matcher reported. **That is not a false-positive rate measurement of anything** -- it is the
accumulated decode history of the machine, mostly from prior real listening sessions, misattributed
to a 50-minute synthetic run. This is the same class of defect already on record
(`rr-study-matched-csv-nfr021-contamination.md` -- an uncleared `ALL.TXT` contaminating a
`*_matched.csv`'s denominator), reproduced here rather than newly discovered. No action taken --
`S3b_matched.csv` is gitignored (Sec.6) and the number was never going to be cited. Flagging so the
next scenario run against an unwindowed `run_study.py`/`matcher.py` isn't surprised by an
implausible FP count again; a real fix would time-window the copy or the match, priced not
authorised here (out of scope for this task).

## 6. Commit hygiene

Every file in `results/2026-08-20-13f2890/` checked individually against `.gitignore` before
staging anything:

| File | Status | Checked |
|---|---|---|
| `owsfz-all.txt`, `wsjt-all.txt`, `S3b_matched.csv` | gitignored (`.gitignore:162-164`) | confirmed via `git check-ignore`, not staged |
| `report.md` | tracked | grepped for `Q1ABC`/`CQ ` and message text -- clean, aggregate numbers only |
| `truth.csv` | tracked | our own synthetic truth, `CQ Q1ABC FN42` only, Q-prefix, NFR-021-clean |
| `wsjt-version.txt`, `S3b_decode_rate.png` | tracked | version string / aggregate chart, no message content |

This report and Sec.4's table above contain no message text beyond the synthetic `CQ Q1ABC FN42`
and no real callsigns.

---

**STOP.** No `src/` change. HK-011 not engaged. No push (HK-014). The full S3b sweep (10 parts x
100 trials x 2 appraisers, ~4.2h unattended, needs an HK-013 supervisor not yet built for this run)
is **not** authorised by this result -- G4 clears the one precondition it was built to clear;
arming the full sweep is its own go/no-go, asked for now that G4 is in hand.
