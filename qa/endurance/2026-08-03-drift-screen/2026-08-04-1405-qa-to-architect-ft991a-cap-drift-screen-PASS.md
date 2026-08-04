# FT-991A cap drift screen executed as pre-registered: ROW 5 PASS. The framer holds the UTC grid over 18.96 h on real hardware.

**Author:** QA, 2026-08-04 (14:05 UTC, `date -u`, per HK-017). Repo at `1ff4293`.
**For:** Architect.
**Executes:** `qa/endurance/2026-08-03-drift-screen/2026-08-03-1652-qa-run-spec-24h-20m-drift-screen.md`,
authorised by the Captain 2026-08-03, against the pre-registered check committed at `becb344`
**before** the run — no threshold altered, no row skipped, no parameter tuned post hoc.
**Corpus:** `artefacts/20260803_live_run_1713/`.

---

## 0. Headline

The screen fires **ROW 5 — PASS**, reported verbatim:

```
VERDICT: ROW 5 -- PASS

  No drift detectable over 18.96 h of uninterrupted uptime (worst audio slope
  +0.0054 s/h, worst |lag| 0.095 s, worst |label| 0.000 s).
  QA RECOMMENDS the Captain lift the ~6 h FT-991A cap.
  The lift remains his decision, not this script's.
```

**The `CycleFramer` grid re-anchoring merged in `be5960a` holds on the real FT-991A chain.** The
capture window does not drift past 13.7 h, the point at which the pre-fix defect became total.
Against a chain with a documented **48.0 ppm** device drift, the framer returns **+0.0 ppm**. It is
compensating in full.

**The cap lift is the Captain's decision and remains unmade.** QA recommends it; that is the
strongest output this instrument can produce, and it is not a lift.

---

## 1. What was authorised, and what was actually run — a disclosed deviation

The Captain authorised **24 h 20 m** of wall clock from 2026-08-03 17:13:26Z. The run was stopped
early, at **2026-08-04 13:57:13Z — 20.73 h wall clock**, on the Captain's explicit instruction.

I record the stopping discipline in full, because a pre-registered check stopped early is only
sound if the stop was not conditioned on the result:

- **Nothing was measured before the decision.** `drift_screen.py` was not run, in whole or in part,
  against this corpus at any point prior to the Captain's instruction to stop. The first execution
  is the one reported here.
- **The stated reason was external** — unwillingness to wait a further ~4 h. Not a peek, not a
  partial result, not a trend.
- I put the optional-stopping hazard to the Captain explicitly before he decided, and declined a
  pre-decision look when the option was open.

**This matters more than the four hours did.** Every VOID gate had already been cleared at the
moment of the stop (§2), so the deviation cost statistical precision only, not verdict eligibility.

One further point for the record, since it bears on how much weight the deviation deserves: I
advised the Captain that stopping early risked a ROW 4 INCONCLUSIVE from a noisier slope fit over a
shorter baseline. **That advice was wrong in proportion.** The measured slope came in 200× under the
PASS bar. The remaining hours could not have changed the row, and I overweighted the risk.

### Two epochs, not one

A heartbeat stall at **2026-08-03 18:58:09Z** (§7) caused a supervisor restart, splitting the corpus.
`drift_screen.py` detects epochs from **daemon log files**, not from gaps — deliberately, since a
60 s supervisor cooldown sits far below the 300 s fallback gap rule and would silently merge two
epochs and average a sawtooth into nothing. So the ~86 s restart *does* split the corpus, correctly.

The consequence, which the Captain identified independently and which the Architect should note: the
**decisive epoch is 18.96 h, not the 20.73 h wall clock**. Wall clock and decisive epoch are not the
same quantity, and only the latter is measured.

---

## 2. Corpus and contiguity — established before analysis (spec §6 step 2, self-check 5)

Gathered per HK-016 via `tools/gather_live_run_artefacts.py`, WSJT-X root pinned by exact path to
the FT-991A instance (four WSJT-X data directories exist here; three are frozen corpora).

| | |
|---|---|
| cycles archived | 4,971 |
| span | 2026-08-03T17:13:15Z → 2026-08-04T13:56:45Z (20.73 h) |
| OpenWSFZ WAVs | 4,971 |
| WSJT-X WAVs | 4,963 |
| gaps > 5 min | **none** — contiguous by the spec's own bar |
| `_pre-run-20260803/` contamination | **0 files** (verified explicitly) |
| zero-decode cycles | 357 / 4,971 = 7.18 % |

Epoch structure, from daemon log boundaries:

| epoch | first | last | cycles | span | decodes/cycle min/med/max/mean |
|---|---|---|---|---:|---|
| 0 | 17:13:30Z | 18:59:00Z | 419 | 1.76 h | 0 / 20 / 30 / 19.6 |
| **1 (decisive)** | 18:59:15Z | 13:56:45Z | 4,551 | **18.96 h** | 0 / 14 / 29 / 12.3 |

---

## 3. The measurement

Decisive epoch (1), against the constants fixed in `becb344`:

| statistic | measured | PASS bar | FAIL bar | margin to PASS bar |
|---|---:|---:|---:|---:|
| audio slope | **+0.0001 s/h** | < 0.02 | ≥ 0.05 | **200×** |
| implied drift | **+0.0 ppm** | — | — | vs −47.3 ppm pre-fix |
| label slope | +0.0000 s/h | — | — | — |
| max \|lag\| | **0.095 s** | < 0.2 | ≥ 0.5 | 2.1× |
| max \|label\| | **0.000 s** | — | ≥ 0.5 | — |
| locked pairs | **456** | ≥ 200 | — | 2.3× |
| epoch span | **18.96 h** | ≥ 14.0 | — | 1.35× |

Epoch 0 (1.76 h, 41 locked) fitted +0.0054 s/h — the worst slope across both epochs, and still 3.7×
under the PASS bar and 9× under FAIL. It qualifies for a slope under both admissibility bars
(`SLOPE_MIN_SPAN_H = 1.0`, `SLOPE_MIN_POINTS = 20`) and is reported as the worst-case figure the
verdict actually cites.

Row-by-row, in the pre-registered strict order:

| row | condition | evaluated |
|---|---|---|
| 1 VOID | epoch < 14.0 h | 18.96 h — **not fired** |
| 2 FAIL | \|slope\| ≥ 0.05 or max\|lag\| ≥ 0.5 or max\|label\| ≥ 0.5 | 0.0054 / 0.095 / 0.000 — **not fired** |
| 3 VOID | < 200 locked pairs | 456 — **not fired** |
| 4 INCONCLUSIVE | \|slope\| ≥ 0.02 or max\|lag\| ≥ 0.2 | 0.0054 / 0.095 — **not fired** |
| **5 PASS** | none of the above | **FIRED** |

Accumulated drift over the decisive epoch is ~1.9 ms, at the instrument's reporting resolution
floor. The fix predicts 0.75 ms over 24 h. These agree to within the resolution of the measurement;
I would not claim better agreement than that from a slope reported to four decimal places.

---

## 4. Why the instrument can be trusted on *this* corpus

The pre-flight validation against the pre-fix control (`20260731_live_run_2004-8080`, ROW 2, −47.3 /
−48.6 / −47.7 ppm recovered) proves only that the instrument *can see drift*. It cannot validate a
null result. Three further checks, internal to this run, support the PASS:

1. **Live self-test.** The screen injected a known 1,000-sample delay (83.3 ms) and recovered
   `L = 1000, peak corr = 1.0000, lag = −0.0833 s`, sign included. Validated against this corpus,
   not merely against the control.
2. **100 % lock rate.** 497 pairs correlated at stride 10; 497 locked (41 + 456) at peaks 0.93–0.999.
   Nothing was silently discarded, so the null cannot be an artefact of a collapsed lock rate.
3. **Pairing is not masking anything.** Time-based pairing recovered 4,956 pairs; exact-filename
   pairing would have recovered the same 4,956. On the pre-fix corpus exact-filename pairing dropped
   65 % of pairs precisely *because* drift displaced the filenames. That failure mode is absent here
   — which is itself corroborating evidence of a stationary window.

---

## 5. The one number I would watch

`max |lag| = 0.095 s` against a 0.2 s bar is the tightest margin in the result — 2.1×, where every
other statistic clears by an order of magnitude or more.

I do not think it indicates residual drift: it is a point maximum over 497 correlations, and both
the flat +0.0001 s/h slope and the 0.000 s label drift say the window is stationary. Noise, not
trend. But it is the statistic that would move first if something regressed, and note that point
maxima are **monotonically non-decreasing** — a longer run can only increase this figure, never
reduce it. If this screen is re-run over a longer epoch, expect this number to rise somewhat on
noise alone, and do not read a rise as regression without a slope to match it.

---

## 6. Minor defect found in the pre-registered constants' *justification* (not the constants)

`PASS_SLOPE_S_PER_H = 0.02` carries the comment: *"~27x above the 0.75 ms/24 h the fix predicts"*.

That factor appears to be computed as though the prediction were 0.75 ms **per hour**
(0.02 / 0.00075 ≈ 26.7). Read as the fix actually states it — 9 samples / 0.75 ms **over 24 h**, a
slope of 3.125 × 10⁻⁵ s/h — the true factor is **~640×**, not 27×.

**This does not affect the verdict.** The constant itself is unambiguous, was fixed in git before the
run, and governs regardless of how its rationale is worded. The error is in the **conservative**
direction: it made the bar look tighter than it is. But the Architect should know that the PASS bar
sits ~640× above predicted drift rather than ~27×, because that is the figure that determines how
much of a regression this screen could actually catch — and a 640× bar is a considerably blunter
instrument than a 27× one. **A future screen intended to detect *partial* regression should not
inherit 0.02 s/h unexamined.** For this run it did not matter: the measured slope cleared it by 200×.

---

## 7. Adjacent result: the settings-page heartbeat stall — ROW 4 NOT REPRODUCED

Pre-registered separately at `1ff4293` ("outcome unknown"), before the reproduction attempt.

**Background.** On 2026-08-03 the 8080 daemon (PID 14600, up 1 h 45 m, no `[ERR]`/`[FTL]`) went
silent while the Captain viewed the decoder-settings page. The supervisor caught a > 90 s heartbeat
stall at 18:58:09Z and restarted it, costing 4 cycles and splitting this run's corpus (§1). The
daemon did **not crash** — it went silent with the process still up. `config.json` was unmodified.

**Result.** The Captain confirms he made the reproduction attempt and it did not recur.
`ui_stall_check.py` fires **ROW 4 — NOT REPRODUCED**.

The exact open-time was not recorded, so I established that the row does not depend on it: the
largest heartbeat gap **anywhere** in the complete 18.96 h epoch is **23.40 s**, below the 30 s SOFT
bar, so rows 1–3 are unreachable for any open-time in that log. Verified at 19:08:00Z (deliberately
adversarial — placing the sole anomaly inside the attribution window), 19:12:00Z and 19:30:00Z; all
three fire ROW 4. Cadence over the full epoch: **13,655 heartbeats at 5.00 s, zero gaps ≥ 30 s, one
23.40 s excursion** — measured against the gathered artefact log, so it covers the epoch to the
moment of teardown, not merely to the point the check was first run.

**Per the rule's own design, this does not clear the settings page.** No row votes "safe". The
18:58Z event happened, and one non-recurrence cannot disprove an intermittent hang.

### A defect in my own pre-registered rule, disclosed

`ui_stall_check.py` accepts `--log` repeatably and **never specified which logs**. That is not
cosmetic — it changes the row:

| logs passed | open-time | row |
|---|---|---|
| new log only | 19:08Z | ROW 4 NOT REPRODUCED |
| **both logs** | **19:08Z** | **ROW 1 VOID** (180.5 s baseline gap) |
| both logs | 19:30Z | ROW 4 NOT REPRODUCED |

Including the predecessor log drags the *restart itself* — a 180.5 s process boundary — into the
baseline window and voids the check. I report ROW 4 on the reading that the daemon under test is the
process started 18:59:14Z, and that the 180.5 s gap belongs to its predecessor. **That reading was
applied after seeing the numbers**, which is precisely the failure mode HK-021 exists to prevent. I
declare it rather than let it pass. Any reuse of this check must fix the input specification first.

Two lesser weaknesses: the baseline window was truncated (~8.9 min available against 900 s required)
for open-times near 19:08Z; and the 23.40 s excursion at 19:08:29Z is the **only** anomaly in
eighteen hours and sits close to where the attempt would have been. It cleared no bar and mandates
no action, but it is not nothing.

---

## 8. Secondary observation, carrying no verdict: 8080 vs WSJT-X decode correspondence

**No pre-registered rule governs this comparison.** It is reported as an observation and must not
acquire verdict status by repetition. Matched on exact `(cycle timestamp, message)`, hashed
callsigns normalised, over the window both files cover:

| | count |
|---|---:|
| WSJT-X decodes | 41,730 |
| 8080 decodes | 61,991 |
| matched in both | 24,480 |
| WSJT-X only | 17,250 |
| 8080 only | 37,511 |

| | |
|---|---:|
| WSJT-X decodes also found by 8080 | **58.66 %** |
| 8080 decodes also found by WSJT-X | **39.49 %** |
| Jaccard | 30.89 % |
| 8080 volume vs WSJT-X | 148.6 % |

**8080 logs 48.6 % more decodes than WSJT-X yet misses 41.3 % of what WSJT-X finds.** This is not a
superset relationship; the two decoders produce substantially different decode sets.

Controls run before reporting the figure:

- **Grid alignment** — both files sit exactly on the 15 s grid; a ±1 cycle tolerance recovers
  **zero** additional matches, so no label offset inflates the miss count. (The gain at ±2 cycles is
  FT8's 30 s alternating sequence re-matching repeated transmissions, not misalignment.) This is
  independent corroboration of §3, from decode labels rather than audio correlation.
- **Formatting** — WSJT-X resolves hashed callsigns from cache (`DK5UP <OH2026NY> R+00`) where 8080
  prints `<...>`. Real but small: normalising moved the headline from 57.11 % to 58.66 %.
- **Dead cycles** — only **0.61 %** of misses fall in cycles where 8080 logged nothing. This is
  per-signal disagreement, not lost capture. 16.6 % of misses had an 8080 decode within 10 Hz in the
  same cycle, consistent with the competition mechanism already confirmed under D-001.

**A higher raw line count is not a better decoder.** ALL.TXT lines are unvalidated; nothing here
establishes that 8080's extra 37,511 decodes are correct. Distinguishing "finds more signal" from
"is less disciplined" requires a validity oracle, which this is not.

---

## 9. What this run does NOT decide

- **It does not lift the cap.** ROW 5 is a recommendation. The ~6 h FT-991A cap stands until the
  Captain lifts it explicitly. This run's own 20.73 h breach was authorised as a one-off.
- **It says nothing about D-001.** Competition remains the confirmed mechanism; the baseline deficit
  and density penalty are untouched here. Drift did not explain D-001 before this run and does not
  now.
- **It does not clear the settings page** (§7).
- **`jt9` offline is not a reference leg** and was not used as one. The reference throughout is the
  live WSJT-X FT-991A instance.
- **It does not establish decoder quality** (§8).

---

## 10. Open for the Architect

1. **The `PASS_SLOPE_S_PER_H` rationale (§6)** — 640× rather than 27× above predicted drift. Worth a
   decision on whether a partial-regression screen should inherit that constant.
2. **`ui_stall_check.py`'s `--log` input specification (§7)** must be pinned before any reuse.
3. **The 18:58Z heartbeat stall remains unexplained** and cost this run its single-epoch structure.
   One occurrence, one non-recurrence.
4. **`max |lag|` monotonicity (§5)** — if a longer screen is ever designed, that bar needs a
   sample-size-aware treatment rather than a fixed 0.2 s.

**Artefacts:** corpus `artefacts/20260803_live_run_1713/` (4,971 + 4,963 WAVs, both logs, both
ALL.TXTs, `cycle-archive.csv`); per-cycle curve
`qa/endurance/2026-08-03-drift-screen/drift_curve_20260803_live_run_1713.csv` (4,971 rows);
`qa/ARTEFACT_INVENTORY.md` regenerated, `--check` clean.
