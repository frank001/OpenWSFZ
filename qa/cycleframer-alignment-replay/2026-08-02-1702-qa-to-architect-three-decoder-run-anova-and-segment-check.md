# Three-decoder multi-day 20m run: QA -> Architect -- ANOVA tables, segment check, open gaps

**Author:** QA, 2026-08-02 (17:02 UTC, `date -u`, per HK-017). Repo at `bf3d5a9`.
**For:** Architect, ahead of any D-001 interpretation of this run's data.
**Supersedes nothing** -- additive to `2026-07-31-1907-architect-to-qa-preflight-brief-
multiday-20m-live-run.md` (the standing brief for this run) and to the memory TODO
`three-decoder-antenna-split-run-2026-07-31-todo.md` (Angle 1/2, hardware table, caveats).
Read both first if you haven't already; this note assumes their content.
**Authorisation:** the preflight brief's §8 states plainly "No analysis arms... this run
gathers, it does not measure." The Captain directed the three ANOVA reports below in this
session (standard per-endurance-session tooling, 2026-07-27 standing instruction -- not a
new arm). **No decomposition, interpretation, or density-penalty analysis has been
performed** -- everything past raw tables and mechanical cross-checks in this note is
explicitly left for you, per that same §8 and per the TODO file's own "pre-register before
the data is read" discipline for Angle 1.

---

## 0. Summary -- the one thing to read if you read nothing else

Three matched-decode ANOVA reports now exist for this run (`qa/endurance/2026-08-02-
multiday-20m-anova/`), covering every pairwise comparison the three decode logs support.
Before writing this up I checked the run against your own preflight brief and found:

1. **Good news, verified mechanically, not assumed:** 8080 stayed on 14.074 MHz for
   100% of its 184,918 lines; 8081 also stayed on 14.074 MHz for 100% of its 212,422 lines
   (it never hopped, despite being free to -- full-run same-band overlap, the "genuine
   bonus" your §4 named). WAV counts match expected cycle counts almost exactly on both
   instances, confirming `mode = "all"` archiving held throughout, not `decoded`.
2. **A process gap I'm not going to hide:** your §7 ordered three post-run steps --
   gather artefacts, run jt9 over 8080's WAVs, **then** produce a contiguity/segment
   report **before any analysis**. I did the ANOVA reports before checking segment
   structure. I've now run that check post-hoc (§2 below) -- the result is reassuring
   (one small gap, not the "secretly two sessions" failure mode your brief was guarding
   against) -- but the order was wrong and I'd rather say so than let it pass quietly.
3. **Two things your brief asked for are still not done:** the jt9 offline re-decode of
   8080's WAVs (§7.2 -- "with it we have three decoders on identical audio") and, more
   importantly, your §0's actual named research question for this run -- **"does WSJT-X
   suffer the same density penalty we do?"** -- is not what matched-decode ANOVA tests.
   The three reports below answer a *different*, narrower question (do the two appraisers'
   reported SNR/DT/frequency values differ on matched decodes) than the one this run was
   built to answer. See §6.

## 1. Compliance check against your preflight brief

| Your requirement | Status | Evidence |
|---|---|---|
| §3: 8080 stays on 14.074 MHz, no gap, whole run | **Met** | 184,918/184,918 lines at 14.074 MHz (checked every line, not sampled) |
| §3: `cycleAudioArchive.mode = "all"` on 8080 | **Met** (inferred) | 10,489 WAVs vs 10,490 expected cycles at 15s cadence over the actual capture span -- WAV count tracks cycle count, not decode count (184,918 decode lines would be far more WAVs than exist if `mode="decoded"` were somehow in effect, and far fewer if archiving had stopped) |
| §3: no Settings-page saves on 8080 | **Not directly checked** -- no observable signature either way from ALL.TXT/cycle-archive.csv alone; flagging as unverified rather than assumed |
| §4: record 8081 band/retunes | **8081 never retuned** -- 212,422/212,422 lines at 14.074 MHz, same band as 8080 for the entire run |
| §5: supervisor kill+log+cooldown+restart, cap 5, rotation guard ported | **Met** -- confirmed in `qa/endurance/2026-07-31-supervisor-8080/8081.sh` when securing these scripts earlier this session (HK-013 addendum guard present in both) |
| §6: watch WAV count, disk, `\|dt\|`, decode ratio, restart count | Not this note's business to re-litigate -- see `qa/endurance/2026-07-31-2dacd1a/CONTAMINATION-NOTE.md` for the run's own live health record (final tally: 2/5 autonomous restarts used, cap never approached) |
| §7.1: gather artefacts (HK-016) | **Done**, though a real bug surfaced doing it -- see §7 below |
| §7.2: jt9 offline re-decode of 8080's WAVs | **Not done** -- see §6.2 |
| §7.3: contiguity/segment report before analysis | **Done, but after the ANOVA reports, not before** -- see §0.2 and §2 |
| §8: no decoder experiment branches, shipped `main` only | Not independently re-verified this session; `contents.md` notes "uncommitted changes present" at gather time -- worth a `git diff` against the actual build if this matters for anything precise |

## 2. Segment/contiguity check (should have come before §3-4, ran it just now)

Detected via a straightforward >5-minute gap scan over each instance's own
`cycle-archive.csv` `cycle_start_utc` column (10,489 / 10,512 rows respectively):

**8080:** 2 segments.
- Segment 1: 2026-07-31T20:04:15Z -> 2026-08-02T13:45:00Z (41.68h, 10,001 cycles, mean
  17.63 decodes/cycle)
- **Gap: 5.2 min** (13:45:00Z -> 13:50:15Z)
- Segment 2: 2026-08-02T13:50:15Z -> 2026-08-02T15:52:00Z (2.03h, 488 cycles, mean 17.65
  decodes/cycle)

This single gap lines up precisely with the already-documented **Window 7** incident in
`CONTAMINATION-NOTE.md` (decode-collapse restart ~13:43Z) and its own log evidence
(`openswfz-20260802T134348Z.log` / `openswfz-20260802T135024Z.log`, ~6 minutes apart,
matching the handoff's note that this particular restart's own heartbeat check passed
and then it died again ~76s later, only caught by the supervisor's independent watchdog).
The other three restarts this run (5 log files total = 4 restarts) recovered inside the
5-minute threshold and don't register as formal segment breaks.

**8081:** 1 segment, zero gaps >5 min, fully contiguous across the entire 43.80h span.

**Reading this against your brief's actual concern** (the last 20m corpus turning out to
be two unrelated sessions, discovered a month into analysis): this is not that failure
mode. 8080 is 95.3% one segment / 4.7% a short tail with matched mean decode density
(17.63 vs 17.65/cycle -- essentially identical, not a density-regime change), and 8081 has
no segmentation at all. I don't think this changes how the three ANOVA reports should be
read, but that's a judgement for you to make, not me -- I'm reporting the measurement, not
clearing it.

## 3. The three ANOVA reports -- tables

All in `qa/endurance/2026-08-02-multiday-20m-anova/`, generated via
`endurance_anova_wsjtx.py` (no re-decode -- both live ALL.TXTs already on disk) and the
new `endurance_anova_two_alltxt.py` (generic two-ALL.TXT variant, written this session
since nothing existing did an OpenWSFZ-vs-OpenWSFZ comparison).

### 3.1 `anova_report_8080_vs_wsjtx.md` -- 8080/FT-991A vs WSJT-X, same feed

184,918 vs 354,831 decodes, 64,275 matched (34.8% / 18.1%).

| Response | Appraiser F | P | OpenWSFZ mean | WSJT-X mean | Gap (WSJT-X minus OpenWSFZ) |
|---|---:|---:|---:|---:|---:|
| SNR (dB) | 33,664.5 | 0.0000 | -7.923 | -2.492 | +5.43 dB |
| DT (s) | 12,598.1 | 0.0000 | 0.3220 | 0.2127 | -0.109 s |
| Freq (Hz) | 134.7 | 0.0000 | 1503.1 | 1503.0 | -0.1 Hz |

### 3.2 `anova_report_8081_vs_wsjtx.md` -- 8081/SDR Uno vs WSJT-X, cross-hardware

212,422 vs 354,831 decodes, 201,834 matched (95.0% / 56.9%).

| Response | Appraiser F | P | OpenWSFZ mean | WSJT-X mean | Gap (WSJT-X minus OpenWSFZ) |
|---|---:|---:|---:|---:|---:|
| SNR (dB) | 19,048.0 | 0.0000 | -3.892 | -2.103 | +1.79 dB |
| DT (s) | 1,354,728.8 | 0.0000 | 0.7743 | 0.2108 | -0.564 s |
| Freq (Hz) | 20,608.6 | 0.0000 | 1522.5 | 1510.8 | -11.7 Hz |

### 3.3 `anova_report_8080_vs_8081.md` -- same decoder, hardware-only variable

184,918 vs 212,422 decodes, 62,775 matched (33.9% / 29.6%).

| Response | Appraiser F | P | 8080 mean | 8081 mean | Gap (8081 minus 8080) |
|---|---:|---:|---:|---:|---:|
| SNR (dB) | 24,306.9 | 0.0000 | -7.754 | -4.287 | +3.47 dB |
| DT (s) | 106,304.0 | 0.0000 | 0.3229 | 0.8132 | +0.490 s |
| Freq (Hz) | 3,327,925.7 | 0.0000 | 1504.2 | 1516.5 | +12.3 Hz |

## 4. Cross-report consistency check

Three pairwise gaps over three overlapping-but-not-identical Part populations ought to
roughly compose (A-C ≈ (A-B)+(B-C)) without matching exactly. They do:

- **Frequency** is the cleanest signal in the whole dataset: the 8081-vs-8080 gap
  (+12.3 Hz) and the 8081-vs-WSJT-X gap (-11.7 Hz) are near-mirrors, while 8080-vs-WSJT-X
  sits at essentially zero (-0.1 Hz). Internally consistent with a fixed calibration
  difference specific to the 8081/SDR-Uno chain -- 8080 and WSJT-X agree because they
  share the FT-991A.
- **DT**: composing 8081->8080 (+0.490s) and 8080->WSJT-X (-0.109s) predicts an
  8081->WSJT-X gap of ~+0.60s; measured is +0.564s. Same sign, same order of magnitude.
- **SNR**: composing 8081->8080 (+3.47dB) and 8080->WSJT-X (+5.43dB) predicts an
  8081->WSJT-X gap of ~+1.96dB; measured is +1.79dB. Also consistent.

## 5. Methodological notes to read the tables by

1. **Every P-value in all nine tables is 0.0000.** With 60,000-200,000 matched pairs,
   even a trivial mean difference clears significance instantly -- the F/P columns confirm
   "real," never "how much it matters." The gap magnitudes are the only numbers worth
   reading for size.
2. **The match-rate spread is a live confound, not just a hardware signature.** 8080's
   match rate is ~34% against both WSJT-X and 8081; 8081's match rate against WSJT-X is
   95%. Before reading that as "same-hardware pairing decodes worse," note 8080 took
   restarts this run (§2) and 8081 didn't -- coverage loss from 8080's own downtime is at
   least as plausible an explanation as anything about the FT-991A/decoder pairing itself.
3. **"Same feed" (8080 vs WSJT-X) is not a clean 2x2 isolation of decoder-only variance.**
   The TODO file's Angle 1 states this pairing gives a decoder-attributable difference
   "full stop -- no capture explanation available." That's in tension with the
   already-established finding in `2026-07-30-2221-qa-to-architect-capture-chain-and-
   cross-band-findings.md` §3: even when WSJT-X and OpenWSFZ independently record the
   *same physical device*, a real ~10-13% capture-chain effect was measured between
   WSJT-X's own recorded WAV and OpenWSFZ's own recorded WAV of the identical instant, fed
   to the *same* decoder afterward. That prior measurement used offline re-decodes of
   matched WAV pairs (a controlled 2x2); this run's 8080-vs-WSJT-X comparison is two apps
   independently live-capturing and live-decoding concurrently, which is the same
   confound, not a cleaner version of it. The observed +5.43dB SNR / -0.109s DT gaps here
   are much larger than that prior ~10-13% effect, so decoder-attributable is almost
   certainly still dominant -- but "full stop" overstates what this pairing alone proves.

## 6. What this does NOT cover

### 6.1 Interpretation / decomposition

No claim is made here about what any of the above means for D-001, the baseline deficit,
or the row 1/4/5 menu. That's explicitly yours, per the preflight brief §8 and the TODO
file's pre-registration discipline.

### 6.2 The jt9 third-decoder comparison (preflight brief §7.2)

Not run. `endurance_anova_jt9.py` exists and is ready (`--all-txt
artefacts/20260731_live_run_2004-8080/owsfz/ALL.TXT --wav-dir
artefacts/20260731_live_run_2004-8080/owsfz/wav --out ...`) but re-decoding ~10,489 WAVs
through jt9 was not attempted this session. Given the Captain's direction that "we have
done all the ANOVAs we can do with this dataset," I'm flagging this as outstanding against
your own brief rather than running it -- your call whether it's still wanted.

### 6.3 The actual named research question (preflight brief §0)

Your brief's stated reason this run mattered: *"does WSJT-X suffer the same density
penalty we do?"* Matched-decode ANOVA over SNR/DT/frequency does not test that -- it would
need a density-stratified recall comparison (something in the shape of Measurement D /
arm S.1's sparse-vs-dense methodology, applied to WSJT-X's decode log instead of, or
alongside, OpenWSFZ's), which has not been attempted against this corpus. This is the
biggest gap between what this run was built to answer and what's been delivered so far.

### 6.4 Angle 2 -- PR #118 drift validation at multi-day scale

The TODO file's Angle 2 (validating the clock-drift fix against 8080's known -45ppm
capture chain over multiple days, with 8081's zero-drift SDR chain as a control) is also
untouched this session. `verify_dt_drift_489135a.py` was already generalised to take
`--ours`/`--control` per that file -- no new tooling needed if this is wanted.

## 7. Tooling changes made in the course of this work

- `endurance_anova_wsjtx.py`: added `--method-note` to override its previously-hardcoded
  "same physical radio feed" sentence, which was accurate for 8080-vs-WSJT-X but actively
  misleading for 8081-vs-WSJT-X (different receiver hardware behind the same split
  antenna). Backward compatible.
- `endurance_anova_two_alltxt.py` (new): generic two-ALL.TXT ANOVA entry point with
  arbitrary appraiser labels and a **required** `--method-note` (no default -- this script
  can't guess the relationship between two arbitrary inputs the way the other two scripts'
  hardcoded assumptions could silently be wrong).
- `gather_live_run_artefacts.py`: fixed a real bug found while double-checking this run's
  own metadata -- `load_owsfz_config()` reads one single global config location with no
  per-instance awareness, so a multi-instance gather (this run) silently wrote the *same*
  audio-device/dial-frequency snapshot into both instances' `contents.md`, and for 8080 it
  was stale (28.074 MHz, a post-run retune) while for 8081 it was outright wrong (8080's
  USB CODEC instead of 8081's own Voicemeeter feed). Fixed to prefer a config.json
  colocated with `--owsfz-alltxt`, with an `--owsfz-config` override available. **Only the
  descriptive metadata block was affected -- the actual ALL.TXT/log/WAV data gathered for
  each instance was always correctly instance-scoped**, confirmed by re-checking both
  corpora's dial-frequency columns directly (§1 above). Both `contents.md` files corrected
  by hand to state the true values and explain why the old text was wrong.

## 8. Recommendations (procedural, not interpretive)

1. Decide whether §6.2 (jt9) and §6.4 (drift validation) are still wanted against this
   corpus, or whether the Captain's "done with ANOVAs" direction covers those too --
   they're different analyses from what's been run, but consume the same dataset.
2. If a real density-penalty answer (§6.3, your brief's actual stated purpose for this
   run) is wanted, that needs its own pre-registered design before touching the data,
   consistent with the TODO file's own discipline and the S.1 precedent.
3. §1's "no Settings-page saves on 8080" row is unverified either way -- if it matters,
   the only way to check now is against whatever session logs/scrollback exist from the
   run itself; ALL.TXT/cycle-archive.csv alone can't answer it.

## 9. Cross-references

- `2026-07-31-1907-architect-to-qa-preflight-brief-multiday-20m-live-run.md` -- the
  standing brief this note checks compliance against.
- `three-decoder-antenna-split-run-2026-07-31-todo.md` (QA memory) -- Angle 1/2, hardware
  table, the four caveats, suggested pickup order.
- `2026-07-30-2221-qa-to-architect-capture-chain-and-cross-band-findings.md` -- source of
  the ~10-13% capture-chain effect cited in §5.3.
- `qa/endurance/2026-08-02-multiday-20m-anova/` -- the three ANOVA reports themselves.
- `qa/endurance/2026-07-31-2dacd1a/CONTAMINATION-NOTE.md` -- Window 7 incident detail
  matching §2's detected gap.
- `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` -- the still-open
  decode-collapse defect behind 8080's restarts and its one segment break.
- `artefacts/20260731_live_run_2004-8080/contents.md`, `-8081/contents.md` -- corrected
  this session; "Headline result" now points at the three ANOVA reports.

---

*Per HK-015 this is QA -> Architect material. Per HK-014/HK-010 committed locally, no push,
no merge implied. Per HK-011 the tooling changes in §7 are qa/tools-scope, not `src/`,
made directly. Per HK-017 filename and byline carry real `date -u` UTC. Per HK-020/HK-022
§1-2 verify this run's actual configuration and segment structure mechanically rather
than inheriting them from the brief or from what "should" be true. The row 1/4/5 menu
decision, any D-001 decomposition, and whether §6's gaps are worth closing all remain
yours and the Captain's.*
