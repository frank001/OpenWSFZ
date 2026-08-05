# QA → Architect — setup request: D-009 parameter recalibration

**Author:** QA, 2026-08-05 (19:42 UTC, `date -u`, per HK-017).
**Triggers:** Captain's request, following the S1–S8 repeat study's Finding 1
(`qa/rr-study/results/2026-08-05-3bd4cd0/report.md` Section 5), commit `ddcc455`.
**Ask:** spec a D-009 recalibration — QA is not designing this unilaterally (standing rule:
*"Recalibration is the Architect's to choose — never substitute an instrument unilaterally,"*
`three-decoder-antenna-split-run-2026-07-31-todo.md`). This note hands over what's known so a spec
can be written efficiently, not a proposed design.

---

## 1. What triggered this

A full S1–S8 repeat of the `2026-06-22-f11f438` baseline, six weeks / 104 `src/` commits later, on
current `main` (`3bd4cd0`). Every mandatory gate still PASSed, but the run surfaced a real,
newly-quantified defect: **OpenWSFZ produces false-positive decodes — structurally impossible from
the synthetic study corpus — at a rate that correlates with simultaneous-signal density, not with
SNR/noise floor.**

Full evidence is in the report's Finding 1; summary:

| Scenario | Signal condition | Garbage lines (of 412 total) |
|---|---|---|
| S1 | single signal + wideband noise | 1 |
| S2 | single signal + wideband noise | 1 |
| S3 | single signal + wideband noise | 0 |
| S4 | up to 30 simultaneous signals | 6 |
| S5 | **pure noise, N=120** | **0** |
| S7 | 2–3 signal stacks (co-channel) | 9 |
| S8 | 12 simultaneous signals | 0 |

WSJT-X, same audio, same scrub applied: **zero** such lines across the whole run. The daemon's own
debug log shows the mechanism (S4, cycle `17:39:15Z`): 139 raw OSD candidates in one 15 s cycle, 11
passing LDPC/CRC, the existing D-009 guard catching 2 as "implausible," 9 left — a minority not in
the truth pool. **The guard exists and works; it is not sufficient at high candidate density.**

This plausibly explains the same run's S7/S8 recovery drops vs. `f11f438` (S7 all-family
70.23%→ down from 74.42%, weak-signal capture halved 20%→10%, S8 86.67%→83.33%) — occupied/
misallocated OSD passes in dense conditions would both emit spurious decodes and reduce correctly
recovered real-signal count. Not established as the cause, but the correlation is exact: only the
multi-signal-density scenarios moved.

## 2. Why this looks like a D-009 calibration problem specifically

D-009 (`K_MIN_SCORE_PASS2=10`, `OSD_CORR_THRESHOLD=0.10`, `OSD_NHARD_MAX=60`) is the existing
false-positive guard — the one now leaking. Three changes landed between the two runs that touch
exactly this mechanism:

1. **`bb3790c`** (shim 20260030) — these three constants moved from compile-time to
   runtime-configurable settings (`decoder.kMinScorePass2` etc. in `config.json`). Confirmed via
   the live daemon's `/api/v1/config` during this run: **values are still 10 / 0.10 / 60,
   unchanged** — but the code path evaluating them is not the one D-009 was calibrated against.
2. **`b8ebcb7`** (D-012, shim 20260033 — the version this run's build reports) — fixed
   `hash_table_add` overcounting, adjacent to decode-candidate dedup.
3. **`5a90d85`** / **`6700e71`** — the two CycleFramer drift fixes, merged as `be5960a`
   (2026-08-03/04). Changed exact per-cycle sample/window alignment.

This is the Captain's own hypothesis, stated live during the run: *"The drift fix has a direct
effect on the parameters calibrated during D-009."* QA has not independently established the causal
link — only the observation above, precisely enough to bisect.

## 3. What already exists to build on

- **`qa/rr-study/d001-param-sweep-2026-07-22/`** — a dedicated sweep driver
  (`sweep_driver.py`, `run_sweep.sh`, `Program.cs`) from the last D-001/D-009-adjacent parameter
  sweep. Not yet inspected for reusability against this specific question — flagging its existence,
  not its fitness.
- **`qa/rr-study/results/d009-ablation-2026-06-21/`** (`ablation.md`) and
  **`d009-investigation-2026-06-21/`** (`report.md`) — the original D-009 calibration work.
  Whatever grid/criteria produced 10 / 0.10 / 60 is documented there.
- **`qa/rr-study/results/d009-k10-confirm-s5-clean/`** and **`d009-k10-confirm-s7-clean/`** —
  precedent for a "clean vs. contaminated" confirmation pattern (their sibling `CONTAMINATED.md`
  files in the non-`-clean` dirs suggest at least one prior sweep run was invalidated by something
  — worth reading before reusing that pattern).
- **This run's own corpus** (`results/2026-08-05-3bd4cd0/`) already has the S4/S7 density
  scenarios, truth, and matched CSVs that exposed the leak — a candidate starting corpus for a
  recalibration sweep rather than a fresh capture.

## 4. What a spec would need to decide (not QA's call)

- **Knobs in scope** — just the three named D-009 constants, or does D-012's hash-table fix or the
  drift fix's window alignment belong in the same sweep as a variable?
- **Bisect first, or sweep first?** — Section 1 above flags three commits as candidates; confirming
  which one(s) actually shifted the leak rate would narrow the sweep space considerably before
  spending time on a full grid.
- **Corpus** — reuse `2026-08-05-3bd4cd0`'s S4/S7 data, or a fresh, purpose-sized capture (the
  existing S4/S7 designs weren't sized for a candidate-density sweep specifically)?
- **Acceptance criterion** — target FP ceiling (S5-style Clopper-Pearson gate, extended to S4/S7
  density conditions?) traded against recovery — R&R-004's N≥49 gate methodology exists but was
  built for S5's uniform pure-noise population, not density-varying conditions.
- **Live rig vs. offline replay** — this run's live VB-CABLE rig is proven and currently idle
  (daemon killed, config restored to live-monitoring per the Captain's last instruction); a sweep
  could run live again or replay the existing S4/S7 WAV-equivalent synth deterministically offline
  if the harness supports it (unconfirmed).

QA stands by to execute once this is specced.
