# DENSITY-SUB — pre-registration note (QA record of the Architect's spec with Amendment 1)

Written 2026-10-09 (UTC from `date -u` at commit), **before any stratified number exists**. The Captain gave the first-hand go in QA's window on 2026-10-09. The Architect's pre-registration and its Amendment 1 reached QA as messages; this note records the design QA will run, in the form QA will code it. If the Architect's text and this note differ, the Architect's text governs and QA stops and asks.

## Question
Does the subtraction pass (flag ON) remedy the near-neighbour density cost that DENSITY-LIVE found for the build without it? Analysis only: no `src/` or `native/` change is proposed or implied.

## Why the original premise changed
The per-row match output (`--matched-out`) was not recorded in the 2026-10-01 OFF/ON replay, so the existing files carry per-cycle counts only (`per_cycle.csv`, `testb_*.csv`, `outcomes_*.csv`; outcomes hold frequency, DT and SNR per decode, no text). Per-W-row matches need a new replay.

## Design (Amendment 1)
- **Sample:** every 10th cycle of the frozen 10-01 `ALL` stratum, starting at index 0: **430 of 4298 cycles** (`results/2026-10-09-density-sub/selection.json`, stratum `S10`, derived from the 10-01 selection whose LF SHA-256 is `55a951c8…977cf`).
- **Arms:** OFF (`--mode two0`) and ON (`--mode two1`, subtraction threads 8), each a fresh process, ascending stamp order, same decoder config as 10-01 (nhard 40, kMinScorePass2 10, osdCorrThreshold 0.10), `--matched-out` on.
- **Build:** the harness is rebuilt against the checkout at `247ac391`; `libft8.dll` SHA-256 must equal the 10-01 pin `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c`, checked at the start and end of each arm. (This is the 10-01 build, not the corrected-OSD build: the question is about the 10-01 corpus and its comparison with DENSITY-LIVE, and a different build would change the thing compared.)
- **Never overlap** the replay with an endurance run or other heavy load: the ON arm is CPU-heavy.

## Validity rows (computed in code, stated before the data)
Bars come from: V1 and V2 from the nature of a re-run (same build, same audio: identical counts expected); V3 from the Architect's amendment (≥ 200 EXPOSED rows keeps the interval from being empty at DENSITY-LIVE's cell minimum of 20); ROW 0a and ROW 0b from DENSITY-LIVE (spec §4.1, run on 2026-09-18, a different population but the same classifier).
- **V1:** per sampled cycle, re-run `M_off` and `M_on` equal `per_cycle.csv`. Exceptions only for an ON-arm abandonment that is explained in exactly one of the two runs; at most 5 % of sampled cycles; unexplained = 0. Else the arm is INVALID.
- **V2:** the strata partition the sampled W rows (every row in exactly one stratum).
- **V3:** EXPOSED ≥ 200 rows in the sample. Else DS-OPEN by size, stated as such.
- **ROW 0a (per arm):** the 95 % CI of D(PL,PF) lies inside [−0.05, +0.05]. Failing it makes the arm's D uninterpretable.
- **ROW 0b (per arm):** standardisation drops ≤ 5 % of EXPOSED rows and ≤ 5 % of the PL rows used in 0a.
- Strata come from W only (the WSJT-X decodes' own frequency and SNR), asserted identical in both arms.

## Estimands
D(EXPOSED,PL) per arm; matched rate per stratum; the live-cost equivalent in pp; NET per stratum; ΔD = D_on − D_off.

## Interval
Block bootstrap over sampled cycles, blocks of 4, B = 10,000, seed 20261009.

## Verdict rows (on the ON arm; exclusive and exhaustive)
Bar 0.170 is DENSITY-LIVE's D(EXPOSED,PL) bar (spec §3: 1.0 pp attributable cost), measured on a different population (the 2026-09-18 live corpus), so it is carried over and flagged as such.
- **DS-REMEDIED:** CI_hi(D_on) < 0.170.
- **DS-PERSISTS:** CI_lo(D_on) ≥ 0.170.
- **DS-OPEN:** otherwise.
Before the verdict row is read, QA reports the OFF-arm **point estimate** D_off to the Architect: if D_off < 0.170 the replay population does not show the problem the question assumes, and the verdict row would be read against a baseline that does not have it.

## What this cannot show
Offline replay of one 40 m night, one pass over a 1-in-10 sample; says nothing about live behaviour, other bands or the corrected-OSD build; the ON arm of 10-01 abandoned some cycles (tolerance above).

## Data and privacy
Per-row outputs are numeric indices, never message text (HK-037); ALL.TXT is read only inside the harness's matching function and inside the analysis function that derives frequency and SNR. Outputs go to the gitignored `artefacts/` folder; only aggregates and the rows file are committed.
