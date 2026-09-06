# `S5-BASELINE` -- reconstruct the S5 AWGN false-positive baseline (QA task result)

**QA, 2026-09-04 20:10Z** (`date -u`, HK-017). Runs
`qa/rr-study/2026-09-04-1911-architect-to-qa-spec-s5-baseline-reconstruction.md`
(Architect -> QA, 19:11Z), PO-ratified via the 19:2xZ ruling ("`S5-BASELINE` is now the only
thing between here and a re-scope draft, and it is QA's to start").

**No decode. No capture. No playback. No `src/`/`native/` change.** `git diff --stat -- src/
native/` is **empty**. Pure re-analysis of already-committed run directories under
`qa/rr-study/results/`, plus one in-process render (ROW 0b) that reuses the harness's own
`compute_seed` / `_render_noise` / `_finalize_playback_samples` -- it does not reimplement
them (the ACTION B ruling's lesson). ROW 0a and the AWGN-restricted per-run counts reuse
`fp_composition_per_part.load_s5_part_map` / `scoped_fp_events` -- the ROW-C1-verified join
from `FP-COMPOSITION` (2026-09-04 18:48Z, 18/18 pairs reproduced exactly) -- rather than
re-implementing the truth.csv/`S5_matched.csv` join a second time.

Script: `qa/rr-study/s5_baseline_reconstruction.py`. Run with `python
qa/rr-study/s5_baseline_reconstruction.py`. Full transcript:
`qa/rr-study/s5_baseline_reconstruction_results.txt`. Machine-readable row outcomes (includes
all 30 ROW 0b hash pairs in full, and the ROW 0c per-run reason lists):
`qa/rr-study/s5_baseline_reconstruction_result.json`.

🛑 **Per spec Section 6: this report states the mechanical row outcomes only. It does not
rule on what any of this means for the arm, the re-scope, or the regression.** Adjudication
is the Architect's; ratification is the PO's.

---

## ROW 0a -- reproduction gate: **does not fire**

Recomputed `(events, N)` from each admissible run's own `truth.csv` + `S5_matched.csv`
against that run's own `report.md` gate line (never Section 6's pooled column -- HK-031),
both appraisers, all 12 admissible runs (see ROW 0c for how the set was built):

| Run | Appraiser | Recomputed | report.md | Match |
|---|---|---|---|---|
| `2026-07-04-a3738fc-f002-s5-n300` | OpenWSFZ | 8/300 | 8/300 | OK |
| `2026-07-04-a3738fc-f002-s5-n300` | WSJT-X | 0/300 | 0/300 | OK |
| `d011-fp-recheck-2026-07-04` | OpenWSFZ | 7/120 | 7/120 | OK |
| `d011-fp-recheck-2026-07-04` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-07-07-df4cc89` | OpenWSFZ | 0/120 | 0/120 | OK |
| `2026-07-07-df4cc89` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-08-05-3bd4cd0` | OpenWSFZ | 0/120 | 0/120 | OK |
| `2026-08-05-3bd4cd0` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-08-15-8d6e1b1` | OpenWSFZ | 1/120 | 1/120 | OK |
| `2026-08-15-8d6e1b1` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-08-21-7d36038` | OpenWSFZ | 1/120 | 1/120 | OK |
| `2026-08-21-7d36038` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-08-22-f5dec23` | OpenWSFZ | 4/120 | 4/120 | OK |
| `2026-08-22-f5dec23` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-08-27-22b749c` | OpenWSFZ | 0/60 | 0/60 | OK |
| `2026-08-27-22b749c` | WSJT-X | 0/60 | 0/60 | OK |
| `2026-08-29-872ba65` | OpenWSFZ | 1/60 | 1/60 | OK |
| `2026-08-29-872ba65` | WSJT-X | 0/60 | 0/60 | OK |
| `2026-08-30-2e60949` | OpenWSFZ | 2/120 | 2/120 | OK |
| `2026-08-30-2e60949` | WSJT-X | 0/120 | 0/120 | OK |
| `2026-09-02-3b52608` | OpenWSFZ | 4/60 | 4/60 | OK |
| `2026-09-02-3b52608` | WSJT-X | 0/60 | 0/60 | OK |
| `2026-09-03-35378b9` | OpenWSFZ | 2/60 | 2/60 | OK |
| `2026-09-03-35378b9` | WSJT-X | 0/60 | 0/60 | OK |

**24/24 pairs reproduce exactly.** The 18 pairs already covered by `FP-COMPOSITION` (the nine
2026-08+ battery runs) reproduce identically to that task's own numbers; the 6 new pairs
(the two July standalone runs plus the newly-discovered `df4cc89`) reproduce cleanly against
their own `report.md` gate lines for the first time here.

*What this row cannot detect (recorded per HK-022's drafting question, as the spec asks):*
an error present identically in both the generator and the report -- a shared-code blind
spot. ROW 0b is the independent check on the stimulus side.

---

## ROW 0b -- audio-condition equivalence: **does not fire**

**THE LOAD-BEARING ROW.** `s5-noise.json` part 0 and `s5-noise-wide.json` part 0, rendered
for `trial_index` 0..29 via the harness's own `compute_seed` (from `harness/common.py`) and
`_render_noise` + `_finalize_playback_samples` (from `harness/run_scenario.py`). Render only
-- no device, no playback, no decode.

**Disclosed rather than hidden:** both scenario files declare `"id": "S5"`, and
`compute_seed(scenario_id, part_index, trial_index)` keys on that string, not the filename --
so the per-trial seed is *identical* for both files by construction. What this row actually
tests is whether the two files' part-0 **configuration** (`noise_type`, and whatever
`level_dbfs` each declares or omits) renders to the same buffer given that shared seed. Both
files currently declare `noise_type: awgn` with no `level_dbfs` (both deleted 2026-09-03,
S5-LEVEL) -- so the render path is expected to agree, and it does:

| trial | seed | SHA256 (`s5-noise.json`) | SHA256 (`s5-noise-wide.json`) | match |
|---|---|---|---|---|
| 0 | 1561858501 | `03734beb738a5d4b3de85bc6a6b9f0138233c8bbc44ce22749a275477dbba398` | `03734beb738a5d4b3de85bc6a6b9f0138233c8bbc44ce22749a275477dbba398` | MATCH |
| 1 | 960283802 | `90ace92da0993e36...` | `90ace92da0993e36...` | MATCH |
| 2 | 892021093 | `b78de822d869d890...` | `b78de822d869d890...` | MATCH |
| 3 | 1972790602 | `a0f6ee7fd28b0ffd...` | `a0f6ee7fd28b0ffd...` | MATCH |
| 4 | 522357441 | `6e8572b9d2b42524...` | `6e8572b9d2b42524...` | MATCH |
| 5 | 434100809 | `495f9a790b373800...` | `495f9a790b373800...` | MATCH |
| 6 | 1987541040 | `b838dca6f7a0d717...` | `b838dca6f7a0d717...` | MATCH |
| 7 | 1550731733 | `3fea1bf15a3ffc54...` | `3fea1bf15a3ffc54...` | MATCH |
| 8 | 978267978 | `ad927c79356d7b98...` | `ad927c79356d7b98...` | MATCH |
| 9 | 1361001477 | `cafe359248626f48...` | `cafe359248626f48...` | MATCH |
| 10 | 1672796167 | `60fc0864908cbe1e...` | `60fc0864908cbe1e...` | MATCH |
| 11 | 363339928 | `4ac9f1f2f85960cc...` | `4ac9f1f2f85960cc...` | MATCH |
| 12 | 920581965 | `18a9fd9c9e010c93...` | `18a9fd9c9e010c93...` | MATCH |
| 13 | 1985403058 | `c3618e3e47b2db32...` | `c3618e3e47b2db32...` | MATCH |
| 14 | 1613680917 | `0d0d145ba8c13a3b...` | `0d0d145ba8c13a3b...` | MATCH |
| 15 | 1930000429 | `d88e104adb96ec4b...` | `d88e104adb96ec4b...` | MATCH |
| 16 | 216305983 | `f05b603560d23613...` | `f05b603560d23613...` | MATCH |
| 17 | 312112809 | `7d938562513eddde...` | `7d938562513eddde...` | MATCH |
| 18 | 1052303369 | `c74a8790dc898db2...` | `c74a8790dc898db2...` | MATCH |
| 19 | 217579570 | `a39e123fece5ce96...` | `a39e123fece5ce96...` | MATCH |
| 20 | 99964177 | `4f50ecd7a0b57292...` | `4f50ecd7a0b57292...` | MATCH |
| 21 | 490683040 | `2519ed4cdcf3322c...` | `2519ed4cdcf3322c...` | MATCH |
| 22 | 1940961689 | `7baa366dfd8ea38e...` | `7baa366dfd8ea38e...` | MATCH |
| 23 | 1454648504 | `485d50b80f9de735...` | `485d50b80f9de735...` | MATCH |
| 24 | 558398644 | `f2eb56bf2f74088e...` | `f2eb56bf2f74088e...` | MATCH |
| 25 | 1286326493 | `d11f80e34b540d81...` | `d11f80e34b540d81...` | MATCH |
| 26 | 905618129 | `63e0dab378ece790...` | `63e0dab378ece790...` | MATCH |
| 27 | 649442228 | `e3ef33895b04c9d8...` | `e3ef33895b04c9d8...` | MATCH |
| 28 | 1033628820 | `38521510ca3035f5...` | `38521510ca3035f5...` | MATCH |
| 29 | 815515411 | `17aa9bdc6b1b9d2f...` | `17aa9bdc6b1b9d2f...` | MATCH |

*(full untruncated hashes for every trial are in `s5_baseline_reconstruction_result.json`'s
`row0b_pairs`, per the spec's "byte-identical must be mechanically diffed, never asserted"
standing rule.)*

**30/30 trial pairs byte-identical.** ROW 0b does not fire. §0.2(B)'s "same physical
condition" claim, tested for the first time against rendered bytes rather than prose, holds.
July's July runs remain admissible under criterion 4.

*What this row cannot detect:* a difference introduced **after**
`_finalize_playback_samples` -- i.e. in the playback device chain. Recorded as a residual per
the spec, not bounded (HK-026: the offline renderer's response is flat there).

---

## ROW 0c -- census completeness: **FIRES (not a stop)**

Enumerated **directly from disk**: every directory under `qa/rr-study/results/` (recursive,
not just its immediate children) whose `truth.csv` contains at least one `scenario_id=='S5'`
row -- **not** gated on `S5_matched.csv` presence, since four such directories on disk carry
real S5 truth rows with no matched file at all (`d009-k10-confirm-s5[-clean]`,
`2026-06-20-ccda50c-s5-wide`, `diag-nhard-2026-06-20`) -- gating on the matched file would
have silently repeated the exact blind spot this row exists to catch.

**34 directories found. 12 admissible, 22 excluded.**

### Admissible (12)

| Run | Date | Era | Context | AWGN N | AWGN k (OpenWSFZ) |
|---|---|---|---|---|---|
| `2026-07-04-a3738fc-f002-s5-n300` | 2026-07-04 | 2026-07 | standalone | 300 | 8 |
| `d011-fp-recheck-2026-07-04` | 2026-07-04 | 2026-07 | standalone | 120 | 7 |
| `2026-07-07-df4cc89` | 2026-07-07 | 2026-07 | **battery** | 60 | 0 |
| `2026-08-05-3bd4cd0` | 2026-08-05 | pre-window | battery | 60 | 0 |
| `2026-08-15-8d6e1b1` | 2026-08-15 | pre-window | battery | 60 | 1 |
| `2026-08-21-7d36038` | 2026-08-21 | pre-window | battery | 60 | 1 |
| `2026-08-22-f5dec23` | 2026-08-22 | post-window | battery | 60 | 4 |
| `2026-08-27-22b749c` | 2026-08-27 | post-window | battery | 60 | 0 |
| `2026-08-29-872ba65` | 2026-08-29 | post-window | battery | 60 | 1 |
| `2026-08-30-2e60949` | 2026-08-30 | post-window | battery | 60 | 2 |
| `2026-09-02-3b52608` | 2026-09-02 | post-window | battery | 60 | 4 |
| `2026-09-03-35378b9` | 2026-09-03 | post-window | battery | 60 | 2 |

🔴 **`2026-07-07-df4cc89` was NOT in the pre-registration's §0.2(B) table -- ROW 0c fires on
this run alone.** It is a partial battery (S1 + S4 + S5, per its own `truth.csv`; S1 and S4
both precede S5 in `run_study.py`'s `_CONTROLLED_SCENARIO_IDS` order, so the decoder was
**warm**, not cold, when it reached S5) -- mechanically classified `context=battery` on the
same rule as every other run here (`standalone` iff `truth.csv`'s only `scenario_id` is
`"S5"`). AWGN-restricted (parts 0/1 of `s5-noise.json`, 30 trials each): **0/60**.

**Consequence (per spec, not a stop): added above; ROW 0d/1/2 all run on the full 12-run
set**, not the 11 named in the pre-registration.

### Excluded (22), with the mechanical reason(s) each was dropped

| Run | Date | Reason(s) |
|---|---|---|
| `2026-06-06-4c34ef6` | 2026-06-06 | pre-R&R-004 (plain decode-rate metric); no ratified-format table; AWGN N=6 |
| `2026-06-06-6bab388` | 2026-06-06 | pre-R&R-004; no ratified-format table; AWGN N=6 |
| `2026-06-07-4b3a4ca` | 2026-06-07 | pre-R&R-004; no ratified-format table; AWGN N=6 |
| `2026-06-14-815b652` | 2026-06-14 | pre-R&R-004; no ratified-format table; AWGN N=6 |
| `2026-06-20-6e821fa` | 2026-06-20 | pre-R&R-004; no ratified-format table; AWGN N=6 |
| `2026-06-20-8eea3c4` | 2026-06-20 | pre-R&R-004; no ratified-format table; AWGN N=12 |
| `2026-06-20-ccda50c-s5-wide` | 2026-06-20 | pre-R&R-004; no ratified-format table; AWGN N=23; **carries its own `INCOMPLETE.md`** |
| `2026-06-20-d40b4cd` | 2026-06-20 | pre-R&R-004; no ratified-format table; AWGN N=6 |
| `diag-nhard-2026-06-20` | 2026-06-20 | pre-R&R-004; no ratified-format table; AWGN N=44 |
| `d009-ablation-2026-06-21/cfg1-s5` | 2026-06-21 | pre-R&R-004; no ratified-format table |
| `d009-ablation-2026-06-21/cfg2-s5` | 2026-06-21 | pre-R&R-004; no ratified-format table |
| `d009-ablation-2026-06-21/cfg4-s5` | 2026-06-21 | pre-R&R-004; no ratified-format table |
| `diag-pass1-sweep-2026-06-21/p{0..4}-*/s5` (5 dirs) | 2026-06-21 | pre-R&R-004; no ratified-format table |
| `2026-06-22-f11f438` | 2026-06-22 | pre-R&R-004; AWGN N=6 |
| `2026-07-01-b03998f` | 2026-07-01 | pre-R&R-004; AWGN N=6 |
| `2026-07-04-793a298` | 2026-07-04 | AWGN N=6 (<49 -- INFO by construction; its own report.md confirms `INFO`, not PASS/FAIL, at N=12 total) |
| `d009-k10-confirm-s5` | *(none found)* | no date found; no ratified-format table (no `report.md` at all); **carries its own `CONTAMINATED.md`** naming a co-channel mixing defect with a concurrent S7 run |
| `d009-k10-confirm-s5-clean` | *(none found)* | no date found; no ratified-format table (no `report.md` at all) -- **N=120, would otherwise be borderline-interesting, but `cycle_utc` in its `truth.csv` dates it 2026-06-21, pre-R&R-004, via the mechanical git-log cross-check done outside the script (not itself a script predicate)** |

*Full reason strings, verbatim, for all 22 are in `s5_baseline_reconstruction_result.json`'s
`row0c_excluded`.*

🔴 **This directly answers the spec's own "highest-value" open question (§0.2 / ROW 0d):
does an Aug/Sep standalone S5 run exist?** The named candidates
(`d009-k10-confirm-s5*`, `2026-06-20-ccda50c-s5-wide`, `diag-nhard-2026-06-20`, the `diag-*`
dirs) are **all dated 2026-06-20/21 -- pre-R&R-004, several months before Aug/Sep, and two
of them are independently disqualified anyway** (contamination, N<49). **No Aug/Sep
standalone S5 run exists anywhere on disk under `qa/rr-study/results/`.**

*What this row cannot detect:* an S5 run committed outside `qa/rr-study/results/` (per spec).

---

## ROW 0d -- identifiability of battery context: **FIRES**

Era x context cross-tabulation over the 12 admissible runs:

| Era | standalone | battery |
|---|---|---|
| `2026-07` | 2 (`a3738fc-f002-s5-n300`, `d011-fp-recheck-2026-07-04`) | 1 (`df4cc89`) |
| `2026-08-05..08-21` (pre-window) | **0** | 3 |
| `2026-08-22..09-03` (post-window) | **0** | 6 |

**FIRES**, on both `pre-window` and `post-window`: each has a populated `battery` cell and a
**complementary `standalone` cell of zero**. (The `2026-07` era, notably, is *not*
confounded -- `df4cc89`'s discovery in ROW 0c fills that cell -- but that does not rescue the
comparison ROW 1 actually needs, which is pre-window against the July baseline.)

**Consequence (per spec): ROW 1's cross-era contrast must not be reported as a p-value or a
ratio.** Reported below as counts with exact Clopper-Pearson intervals, labelled
**"not identifiable -- context confounded with era."**

*What this row cannot detect:* a within-battery ordering effect (S5 always sits in the same
position), or any exposure difference not captured by the era/context axes (per spec).

---

## ROW 1 -- is the pre-window below the shipped-configuration baseline?

**Not identifiable -- context confounded with era** (ROW 0d fired). Reported as counts +
exact Clopper-Pearson 95% intervals only, no ratio, no p-value:

| Arm | k / N | Rate | 95% CP CI |
|---|---|---|---|
| Pre-window (battery context; `3bd4cd0`, `8d6e1b1`, `7d36038`) | 2/180 | 1.111% | [0.135%, 3.956%] |
| July shipped-config (standalone; `a3738fc-f002-s5-n300` only -- `d011` excluded, pre-f-002) | 8/300 | 2.667% | [1.158%, 5.187%] |
| July shipped-config, battery context (`df4cc89`) -- **informational only, n=1 run, does not resolve the confound alone** | 0/60 | 0.000% | [0.000%, 5.963%] |

**Position (HK-021(w)):** the pre-window CI `[0.135%, 3.956%]` and the July standalone CI
`[1.158%, 5.187%]` **overlap**. An interval-valued readout's ignorance here is decisive by
position, not width: the two intervals overlapping is not itself "no difference" -- it means
the identifiability failure (ROW 0d) leaves this comparison unable to distinguish era from
context in the first place, independent of what the intervals happen to show.

---

## ROW 2 -- boundary-free trend: **does not fire**

Population: the 9 battery-context runs in the pre-window/post-window eras (excludes the
2026-07 era entirely, by construction -- `df4cc89` and the two July standalone runs are not
part of this continuous battery series):

| Run | Date | AWGN N | AWGN k (OpenWSFZ) |
|---|---|---|---|
| `2026-08-05-3bd4cd0` | 2026-08-05 | 60 | 0 |
| `2026-08-15-8d6e1b1` | 2026-08-15 | 60 | 1 |
| `2026-08-21-7d36038` | 2026-08-21 | 60 | 1 |
| `2026-08-22-f5dec23` | 2026-08-22 | 60 | 4 |
| `2026-08-27-22b749c` | 2026-08-27 | 60 | 0 |
| `2026-08-29-872ba65` | 2026-08-29 | 60 | 1 |
| `2026-08-30-2e60949` | 2026-08-30 | 60 | 2 |
| `2026-09-02-3b52608` | 2026-09-02 | 60 | 4 |
| `2026-09-03-35378b9` | 2026-09-03 | 60 | 2 |

Conditional permutation test: condition on the total event count (15), distribute events
across the 9 runs multinomially with probability proportional to each run's AWGN N (all
equal here, 60 each), score by `sum(events_i x chronological_rank_i)`, one-sided
(later-than-expected). Observed statistic: **76.0**.

**p = 0.0610045** (N = 2,000,000 Monte-Carlo draws, seed = 20260904, MC quantum 5.0e-7).

Leave-one-run-out:

| Dropped run | p (remaining 8) |
|---|---|
| `2026-08-05-3bd4cd0` | 0.1851 |
| `2026-08-15-8d6e1b1` | 0.0905 |
| `2026-08-21-7d36038` | 0.0909 |
| `2026-08-22-f5dec23` | 0.0170 |
| `2026-08-27-22b749c` | 0.0574 |
| `2026-08-29-872ba65` | 0.0580 |
| `2026-08-30-2e60949` | 0.0739 |
| `2026-09-02-3b52608` | 0.1808 |
| `2026-09-03-35378b9` | 0.0452 |

**FIRES iff `p < 0.05` AND no leave-one-out `p > 0.10`.** Neither the full-population p
(0.061, already above 0.05) nor the leave-one-out robustness condition holds (dropping
`3bd4cd0` or `3b52608` alone lifts p above 0.10). **ROW 2 does not fire.**

⚠️ This is a materially different test statistic and MC design from the Architect's
disclosed, non-citable exploratory figure (`p = 0.056`, §0.1) -- the qualitative reading
agrees (trend not robust to single-run removal, load-bearing on `3bd4cd0`/`3b52608` in
particular) but the exact numbers should not be treated as the same measurement.

**Consequence (per spec): the trend is load-bearing on individual runs (named above). This
does NOT restore "no regression" -- direction is unchanged (18:11Z ruling).**

---

## NFR-021

`scan()` (imported from `qa/rr-study/nfr021_pre_merge_scan.py` directly, not the CLI over a
committed ref and not a raw directory walk -- both false-green on uncommitted files, per
standing instruction) run against every new file:

- `qa/rr-study/s5_baseline_reconstruction.py` -- `({}, {})`
- `qa/rr-study/s5_baseline_reconstruction_results.txt` -- `({}, {})`
- `qa/rr-study/s5_baseline_reconstruction_result.json` -- `({}, {})`
- This report -- `({}, {})`

No raw decode rows, message text, or callsign-shaped tokens appear anywhere in the script,
its outputs, or this report -- only counts, dates, directory names, and SHA256 hashes of
rendered noise buffers.

---

## Hard stop

Per spec Section 6: **the session stops after ROW 2, on either branch (HK-030 -- pause and
hand back, not merely "do not push").** `git diff --stat -- src/ native/` is empty. `main` is
local-only (unpushed, per HK-014/HK-029 -- carrying `ac6150d`'s `src/`+`native/` diff, so the
direct-push exception does not apply). Committing this task's four new files locally and
handing back. No `src/`/`native/` change, no capture, no decode, no re-scope drafted.
