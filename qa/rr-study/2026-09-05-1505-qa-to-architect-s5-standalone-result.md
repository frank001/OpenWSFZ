# `S5-STANDALONE` — QA to Architect: live standalone S5 result, current `main`

**QA, 2026-09-05 15:05 UTC** (`date -u`, HK-017). Executes
`2026-09-05-1311-architect-to-qa-spec-s5-standalone-current-build.md` (Captain-initiated,
PO's "go with 1" ruling). Base `main`@`df13da0` (one docs-only commit ahead of the spec's own
`10bbaad`; `git diff --stat 10bbaad..df13da0 -- src/ native/` empty, so the build the spec
pre-registered against is unchanged).

**Mechanical row outcomes only. No verdict drawn on the regression, on `3.25×`, or on the
re-scope — that is the Architect's and PO's, per spec §6/HK-015.**

---

## 0. Result directory and reproducibility

`qa/rr-study/results/2026-09-05-10bbaad-s5-standalone-n300/` — `report.md` (committed),
`report.html` (committed), `truth.csv` (committed), `owsfz-all.txt` / `wsjt-all.txt` /
`S5_matched.csv` (gitignored — NFR-021, see §5). Supporting computation scripts and their
JSON outputs are gathered under `artefacts/2026-09-05-s5-standalone/` (HK-016).

---

## 1. ROW 0a–0d — preconditions, all evaluated before/at arm time

| Row | Check | Result |
|---|---|---|
| **0a** build pin | `libft8.dll` SHA256 = `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c` (matches pin exactly, measured via `certutil`); `git diff --stat -- src/ native/` empty; running daemon's `/api/v1/status` reports `shimVersion: 20260050` | **does not fire** — proceed |
| **0b** stimulus equivalence | 300/300 trials of `s5-noise-wide-n300.json` part 0 rendered byte-identical (SHA256) between the current file and `git show 1e07425:…`, via the harness's own `compute_seed`/`_render_noise`/`_finalize_playback_samples` (imported, not reimplemented) | **does not fire** — ROW 1 stands as a clean ratio, not counts-only |
| **0c** capture liveness + log hygiene | `captureActive: true` at arm time; both `ALL.TXT` files rotated (renamed, not deleted — `*.pre-s5-standalone-2026-09-05.bak`) before the warm-up; warm-up decode `CQ Q1ABC FN42` independently present in **both** logs before proceeding (OpenWSFZ SNR +8 dB, WSJT-X SNR +7 dB, cycle `260905_133645`) | **does not fire** |
| **0d** context assertion | `truth.csv`'s `scenario_id` set is exactly `{"S5"}`; daemon and WSJT-X were both freshly started for this run and saw no scenario before it in the same process lifetime (only the single warm-up cycle, which §3.2(4) excludes from the battery rule) | **does not fire — this run fills the empty cell as a valid standalone/cold replicate** |

Daemon rebuilt fresh (`dotnet build -c Release`) from `main`@`df13da0` before starting, per the
ROW 0a residual note in §9 of the spec (mitigates "daemon started from a different tree").

---

## 2. ROW 0e — delivery cadence

Computed from this run's own `truth.csv` `cycle_utc` (§2.3 definition: fraction of consecutive
S5 trial pairs delivered more than one 15 s slot apart):

**14/299 consecutive pairs gapped → gap fraction = 4.68%.**

Against July's 12.7% — **today's cadence is tighter than July's, not looser**, and far under the
40% bound (`7d36038`/`f5dec23` regime). **ROW 1 stands as an adjudicable ratio, not
descriptive-only.**

---

## 3. ROW 1 — PRIMARY

| | `k` | `N` | rate | exact 95% CP CI |
|---|---|---|---|---|
| **Today** (`main`@`df13da0`, standalone, cold) | **6** | 300 | **2.000%** | **[0.737%, 4.302%]** |
| July (`a3738fc`, standalone, cold, shipped `f-002`) | 8 | 300 | 2.667% | [1.158%, 5.187%] |

- **Fisher exact, one-sided (upper tail): p = 0.7908.** The data do not merely fail to confirm
  an elevation — today's point rate sits *below* July's (**ratio 0.75×**).
- **Firing rule:** ROW 1 fires iff `k ≥ 18`. **`k = 6` — does not fire, by a wide margin** (12
  slots short of the gate; the Architect's own low-confidence prediction was `k` in 6–14, and 6
  is its floor).
- **Straddle, not width (§4/HK-021(w)):** the firing threshold is 6.000%. Today's CI
  `[0.737%, 4.302%]` sits **entirely below** it; July's CI `[1.158%, 5.187%]` also sits entirely
  below it. Neither interval straddles the gate.
- **WSJT-X control: 0/300** (0.0%, 95% UB 0.99%) — consistent with the standing `0/840` across
  the battery series; the rig remains excluded as a source.

🛑 **Per §5 of the spec, stated again here because it matters for how this is read:** this arm
has **96.5% power against the HELD `3.25×`** and only **2.5% power at the `1.35×`** the
July-vs-post-window comparison implies. A non-firing ROW 1 rules out a large regression in this
standalone, cold context; it says almost nothing about a small one. This result does **not**
resolve `3.25×` and does **not** constitute "no regression" at any magnitude below ~2.25×.

---

## 4. ROW 2 — delivery-cadence covariate, full 12+1 = 13-run population

Population: the 12 `S5-BASELINE` ROW 0c admissible runs, plus today. Per-run AWGN `(N, k,
gap fraction)` reused from `S5-BASELINE`'s own table (§1 of the spec) and this spec's own §2.3
table — not re-derived (HK-018).

- **Observed statistic** (`Σ events_i × gap_fraction_i`): **4.947**
- **Two-sided conditional-permutation p** (condition on total events = 36, distribute across
  runs ∝ each run's AWGN `N`; `N = 2,000,000` MC draws, seed `20260905`, MC quantum `5×10⁻⁷`):
  **p = 0.4448** (`p_≥` = 0.2224, `p_≤` = 0.7776; two-sided taken as `2·min(p_≥, p_≤)`, capped
  at 1 — this specific two-sided construction was not pinned down in the spec text; recorded
  here for reproducibility, and it is not outcome-load-bearing: `p = 0.4448` is nowhere near the
  0.05 gate under any of the standard two-sided conventions).
- **Leave-one-out:** all 13 single-run-dropped p-values lie in **[0.213, 0.597]** — none near
  0.05, so this is moot for the firing decision, but recorded per the spec's robustness
  condition.
- **FIRES iff `p<0.05` AND no leave-one-out `p>0.10`.** `p = 0.4448` already fails the first
  clause. **ROW 2 does not fire.** Per the spec's own wording: **not** "the harness is clean" —
  not detected at this power, n=13 runs.

---

## 5. ROW 3 — context contrast at fixed build (secondary, descriptive, no adjudication)

Same `libft8.dll` blob (`93de7825…`) at today's run and `2026-09-03-35378b9`:

| | `k/N` | 95% CP CI |
|---|---|---|
| Today (standalone) | 6/300 | [0.737%, 4.302%] |
| `35378b9` (battery) | 2/60 | [0.406%, 11.528%] |

Wide, heavily overlapping intervals at `n=60` on the battery side. **No ratio, no p-value, no
adjudication** — recorded only because it is free and it is the only same-build context pair
that will exist (per spec §4 ROW 3).

---

## 6. Two operational defects found and corrected in-flight — disclosed, not adjudicated

Both are mechanical/process findings within QA's own remit (no `src/`/`native/` touched;
HK-011 not engaged). Flagging both for the backlog since neither was on the board before today.

### 6.1 `matcher.py`'s false-positive pass has no time-window filter — reproduces the July defect

`matcher.py`'s pass-2 FP extraction (`_match_appraiser`, lines ~183–189) treats **every**
unconsumed decode record in the supplied `ALL.TXT` file as a false positive for the scenario
being matched, with **no check that the record's timestamp falls anywhere near the run's own
truth-row cycle window.** For a signal-free scenario like S5 (every truth row has an empty
`true_freq_hz`, so `match_found` is never `True`), this means *any* stray decode anywhere in the
file — including the pre-run warm-up decode that spec §3.4.3 requires be present in both logs —
gets counted as an in-scenario FP.

This is **not a new defect**: the July run's own `report.md` (finding #5, §2 data-integrity
note) documents hitting exactly this and manually filtering WSJT-X's persistent log before the
final match. It reproduced today because §3.4 of this spec clears/rotates `ALL.TXT` **before**
the warm-up but does not call for a second clear **after** the warm-up and before the timed run
— so the warm-up decode lands in the same log the study measures.

**Correction applied, mirroring July's own documented method exactly:** before running
`matcher.py`, both copied logs (`owsfz-all.txt`, `wsjt-all.txt`) were filtered to drop any line
timestamped before the run's first truth-row `cycle_utc` (`2026-09-05T13:38:30Z`). Effect:
OpenWSFZ raw-count 7 → corrected 6; WSJT-X raw-count 1 → corrected 0. **All counts reported in
§§1–5 above are the corrected counts.** The uncorrected `matcher.py` output (7 FP / 1 FP) is
preserved in `artefacts/2026-09-05-s5-standalone/matcher_uncorrected_output.txt` for audit.

Recommend: either (a) `RUNBOOK.md`'s pre-flight sequence adds an explicit second
clear-OpenWSFZ/`--since`-cutoff step after the warm-up (July's own finding #5 recommendation,
never actioned), or (b) `matcher.py` gains a `--since` cutoff parameter so this stops depending
on operator memory. Filing as a process follow-up, not blocking — same disposition July gave it.

### 6.2 `run_scenario.py --run-dir <bare name>` resolves against CWD, not `results/`, contrary to its own `--help` text

`run_scenario.py --help` states *"Relative paths are resolved from qa/rr-study/results/"*, but
the actual code (`run_scenario.py` ~line 941–942) resolves a relative `--run-dir` against
`Path.cwd()`. Running the spec's execution sketch literally (`cd qa/rr-study`, then
`run_scenario.py … --run-dir 2026-09-05-10bbaad-s5-standalone-n300`) therefore created the run
directory at `qa/rr-study/2026-09-05-10bbaad-s5-standalone-n300/` — **outside** the
`qa/rr-study/results/*/…` tree the `.gitignore` NFR-021 rules are scoped to. Caught before any
`git add` (the raw `owsfz-all.txt`/`wsjt-all.txt`/`S5_matched.csv` would otherwise have been
stageable); the directory was moved into `results/` to restore ignore coverage and match every
other run's location. Recommend fixing the `--help` text or the resolution code so the two
agree; filing as a process follow-up, not blocking.

---

## 7. NFR-021

Scanned via the project's own `scan()`/`classify()` (`qa/rr-study/nfr021_pre_merge_scan.py`),
not a directory walk, against the **committed** files:

| File | Flagged | Grid-excluded |
|---|---|---|
| `results/…/report.md` | 0 | 0 |
| `results/…/truth.csv` | 0 | 0 |
| This report (prose) | 0 | 0 |

`owsfz-all.txt` (9 flagged tokens, all coincidental CRC-pass noise decodes per RUNBOOK §7.5 —
e.g. `13Q6LPFI`, non-standard callsign shapes, not real transmissions) and `S5_matched.csv`
(same 9, inherited) are **not committed** — gitignored per §6.2's fix, matching every prior S5
run's convention. `wsjt-all.txt` (post-correction, 0 lines) has nothing to flag.

---

## 8. Housekeeping

- **HK-016:** artefacts gathered at `artefacts/2026-09-05-s5-standalone/` — daemon log, pipeline
  log, uncorrected/corrected matcher output, ROW 0b and ROW 0e/1/2/3 computation scripts +
  JSON results, `README.md`.
- **HK-009:** all scripts write ASCII to `stdout`.
- **HK-014/HK-029:** committing locally, **not pushing**. `git diff --stat -- src/ native/` at
  `HEAD` is empty, but `main` remains far ahead of `origin/main` carrying earlier `src/`/`native/`
  diffs (`ac6150d` etc.) — the HK-029 direct-push exception is **N/A** for this branch state
  regardless of this commit's own diff being docs/results-only.
- **HK-030:** no ROW's STOP condition fired; nothing was paused-and-handed-back mid-arm. The one
  pause that did happen (before starting the live capture) was a Captain go/no-go check on
  hijacking an actively-in-use machine for ~75 minutes — not a spec STOP — and the Captain
  answered "proceed now."

---

## 9. What this arm does and does not settle (repeating spec §0.2, because it is the point)

This is a bundle contrast (`a3738fc` → `df13da0`, ~2 months of change) at 96.5% power against
`3.25×` and 2.5% power against `1.35×`. **ROW 1 does not fire.** That confirms no *large*
regression is present in the standalone, cold context against the July shipped-config baseline.
It is silent on the battery series, silent on anything below ~2.25×, and it is **not** an
adjudication of `3.25×` or the re-scope. That ruling is the Architect's to draw and the PO's to
ratify (HK-015).

---

**QA, 2026-09-05 15:05 UTC.** Committed locally, not pushed (HK-014/HK-029).
