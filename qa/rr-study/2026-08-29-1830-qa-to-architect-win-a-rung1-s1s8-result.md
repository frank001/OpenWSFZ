# WIN-A Rung 1 S1-S8 RESULT -- S7 gap held constant, S5 single-event FAIL, S3 confounded by a harness defect discovered in this same run

**QA → Architect.** 2026-08-29 18:30Z (`date -u`, HK-017). Branch `experiment/win-a-hamming-rung1` @
`872ba653ce880791c9e3eea587167aaed7cb7af1` (shim `20260047`), live capture per the Captain's direct
instruction (WSJT-X - FT991A pre-configured, Voicemeeter AUX1->B1 routing pre-configured; OpenWSFZ
setup, ALL.TXT hygiene, and the full run were QA's).

Full report: `qa/rr-study/results/2026-08-29-872ba65/report.md` (+ `.html`), Sections 1/5/6 authored.
Committed locally not yet done -- awaiting the Captain's go-ahead per standing rule, same as every
prior sweep.

---

🔴 **Headline: do not treat this run as a clean arm of the S7+S5 gate.** S3 (DT precision) went from
PASS to MARGINAL, and the cause is a harness defect discovered inside this run's own data -- not the
Rung 1 decoder change. The same defect class threatens S7's trustworthiness (S7's entire mechanism is
precise per-signal timing/frequency separation), even though S7's OpenWSFZ-vs-WSJT-X gap happens to
have held exactly constant against baseline. S5 is a separate, real single-event FAIL that stands on
its own regardless of the S3/S7 question.

---

## 1. What actually happened, in order

1. Built fresh from `872ba65` (`dotnet build -c Release`, 0 warnings/errors) -- the on-disk Release
   binary predated the Rung 1 commit and would have silently run the pre-treatment decoder otherwise.
   Confirmed shim `20260047` loaded via the daemon's own startup log and `/api/v1/status`.
2. Found and cleared a stale `ALL.TXT` (430 lines, 2026-08-27 run) before arming -- backed up per the
   existing `_pre-run-backups/` convention.
3. `harness/run_scenario.py`'s per-trial cadence had a real, deterministic defect (not incidental
   jitter): a blocking one-slot `sd.play()`/`sd.wait()` returns essentially exactly on the next 15 s
   boundary, and `_next_cycle_boundary()`'s "don't play into an already-started cycle" guard then
   advances a further full slot **every single trial**, unconditionally -- confirmed against
   `rr_study_2026-08-27_s1s8_full_run.log`'s `cycle=` timestamps (uniform 30 s cadence). Fixed by
   concatenating consecutive ordinary (exactly-one-slot) trials into one continuous buffer played with
   a single `sd.play()`/`sd.wait()` call. Verified via dry-run across all eight scenarios and a
   fake-clock/fake-`sounddevice` simulation of the full battery (8460 s -> 4422 s, 47.7% reduction)
   before this run. Simulation cannot model real driver behaviour under one very long continuous
   buffer, and this run is the first live use.
4. This run's own S3 data shows that assumption was wrong -- see Section 2.

## 2. Finding 1 -- S3 broke because the harness did; S7 must be read as provisional

S3 batches 24 of its 30 trials into one ~360 s continuous buffer -- the most aggressive batching in the
default battery. WSJT-X's own code did not change between this run and `22b749c`, yet its DT residual
(reported - true) moved:

| | Baseline `22b749c` (unbatched) | This run (batched) |
|---|---|---|
| WSJT-X DT residual | **-0.800 s, SD = 0.000** (all 30 trials, exact constant) | -1.200 s mean, **SD = 0.330 s**, range -0.8 to -1.8 s |
| OpenWSFZ DT residual | -0.177 s, SD 0.042 | -0.153 s, SD 0.050 (unchanged) |
| S1 SNR bias, both apps (same run) | -- | unchanged |

A reference decoder's timing residual moving from a perfect constant to a noisy, larger-magnitude
figure, while SNR estimation (integrates over the whole slot, insensitive to sub-second timing) stays
flat in the same run, is the signature of playback-timing jitter, not decode-quality change. Per-trial
residuals oscillate rather than climb monotonically, which rules out simple linear sample-clock drift
over the long buffer as the sole mechanism; not further diagnosed this session.

**S7 consequence:** S7's OpenWSFZ-vs-WSJT-X recovery gap held **exactly constant** at 19.07pp (this
run 93.02%/73.95%, baseline 97.67%/78.60%) even though both absolute figures dropped ~4.65pp together.
That is consistent with the timing jitter being immaterial to S7's outcome -- but it does not prove it;
the same coincidence could arise from an unrelated shared cause (e.g. real off-air band conditions on a
different day, both runs being live captures). I am not resolving this call myself -- it decides
whether S7+S5 can be armed off this run's data or needs a bounded-batch re-run first, and that call
belongs to you/the Captain per HK-015, same as the dev-task's own "report, don't resolve unilaterally"
convention that's been the pattern all through this arm.

## 3. Finding 2 -- S5: one genuine event, weak evidence on its own

Correctly windowed to S5's own 60 injection cycles (see Finding 3 for why that windowing matters): one
OpenWSFZ false positive, `CS-bc7b58 CS-1811db/P OE65` decoded out of pure AWGN at 17:36:15Z, reported SNR
-26 dB. WSJT-X 0/60. Baseline was 0/60 both appraisers. Flips the 95% Clopper-Pearson UB from 4.87% to
7.66%, crossing the ratified 6% gate. This study's own precedent (`22b749c`'s hedge on `f5dec23`'s
4/120 FAIL) treats a single small-N FP swing as ordinary tail variance pending a second occurrence --
same posture recommended here, not an escalation on this evidence alone. Sits alongside Finding 1 in
the same run, which is the only reason it's flagged this carefully rather than filed as routine noise.

## 4. Finding 3 -- `matcher.py` Pass 2 is not scoped to the scenario's own injection window (pre-existing, not new, does not change any reported number)

`S5_matched.csv` contains 417 `false_positive=True` OpenWSFZ rows, not 1 -- spanning 16:49:15Z to
18:05:00Z, over an hour outside S5's actual ~15-minute window, including S1/S3/S7's own genuine
messages and real off-air callsigns picked up mid-session. Root cause: `_match_appraiser()`
(`harness/matcher.py:128-189`) Pass 2 iterates every slot bucket from the *entire* `ALL.TXT`, not just
the scenario's own truth-row cycles. **The reported gate number is unaffected** --
`analyse.py::_compute_fp_rates()` (~line 705) independently re-windows to `s5_cycles` before counting,
which is why "1/60" in report.md is correct despite the raw CSV holding 417 rows. Two low-priority
consequences: (a) any future metric reading `false_positive` from another scenario's matched CSV would
need the same re-window; (b) real off-air callsigns land in per-scenario matched CSVs rather than only
the session-wide raw log -- confirmed still `.gitignore`d, not committed, no NFR-021 exposure, but wider
blast radius than necessary. Full report.md Section 5 Finding 3 has the complete writeup.

## 5. What I need from you

- A ruling on whether S7+S5 can be armed off this run's data given Finding 1's caveat, or whether a
  bounded-batch re-run is required first.
- Whether Finding 2 (S5 single event) should be treated as this arm's own confirmatory data point once
  Finding 1 is settled, or held separately.
- Recommendations 2-3 in report.md Section 5 (bound the harness batch size; scope `matcher.py` Pass 2)
  are QA-tooling-only fixes (HK-011) -- flagging for your awareness, not asking permission, unless you
  want a different priority than "low, no reported number is wrong."

Nothing here authorises `src/` change, merge, or push -- QA has committed nothing beyond this report and
awaits direction, same as every prior sweep.
