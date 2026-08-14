# QA tasks — D-009 parameter recalibration (executing the Architect's spec)

**Author:** QA, 2026-08-05 (20:18 UTC, `date -u`, per HK-017).
**Executes:** `qa/rr-study/2026-08-05-2003-architect-to-qa-spec-d009-recalibration.md` (`f6c5b46`).
**Per HK-015:** QA authors this breakdown itself; nothing here needs Developer or Architect
sign-off to *run* — only the eventual recommendation (ROW 1/2) needs the Captain's.

This is QA's own execution plan, not a new spec. Where a design choice below isn't dictated by
the Architect's spec, the reasoning is given inline so it can be checked.

---

## T1 — Verify corpora on disk (DONE)

- `20260803_live_run_1713/owsfz/wav`: **4,971** WAVs total (matches inventory). Two daemon logs
  exist: `...171326Z.log` (420 WAVs, `171330`→`185914`) and `...185914Z.log` (the rest). The
  spec's "contiguous decisive epoch from 260803_185914" is the **second** log's span only —
  **4,551** owsfz WAVs with filename stem `>= 260803_185914`, confirmed by direct listing.
- `20260803_live_run_1713/wsjt-x/wav`: 4,963 total; **4,542** at/after `260803_185914`.
- The spec's §3.3 "Inventory-confirmed: owsfz 4,971 / wsjt-x 4,963" cites the *whole-folder*
  inventory row, not the restricted-epoch subset — read as confirming the corpus exists and
  matches inventory, not as overriding the explicit restriction instruction two sentences
  earlier. **Acting on the restriction (4,551 / 4,542), not the whole-folder counts.** If this
  reading is wrong, the Architect should say so; the two numbers differ by exactly the 420/421
  pre-restart WAVs, so the ambiguity is auditable, not silent.
- `wsjt-x/ALL.TXT` and `owsfz/ALL.TXT` both present. Recall reference = `wsjt-x/ALL.TXT`,
  restricted to rows with `ts >= 260803_185914` (same cutoff, applied on the scoring side).

## T2 — Harness fitness (DONE — no `src/`, no rebuild)

`qa/rr-study/d001-param-sweep-2026-07-22/` (`Program.cs` + `sweep_driver.py`) already supports
everything this spec needs with **zero code changes**:

- `--index-start`/`--index-end` on the sorted-by-filename WAV list → restricts to the decisive
  epoch without copying/moving any WAV (index of the first `>=260803_185914` filename computed
  at run time, not hardcoded, so it's correct even if the corpus directory changes).
- `--debug-log` already exists (added 2026-07-26 for the candidate-cap sweep) and already emits
  the exact `Iterative subtraction: pass N of 2, X candidates found, Y decoded.` line §5.4 needs,
  via one `decode.log` per grid point.
- Sharding (`--shard-index`/`--shard-count`) already runs disjoint WAV subsets in separate
  processes (separate native globals — no shared-global race), exactly per spec §4.3.
- **No tune/validate split is used here** (unlike `ea88d12`). The Architect's spec §5 decision
  rule is defined directly on `rec(p)`/`s5(p)`/`s7(p)` for the *whole* restricted corpus — there
  is no held-out arm in this design. `sweep_driver.py score-recall` takes `--split-ts` as an
  arbitrary restriction set, not necessarily a half-split; passing it the *full* set of in-epoch
  timestamps (no held-out half) reuses the existing command unmodified while matching the new
  spec's rule.

**New tooling required (spec §5.4 has no precedent in the 07-22 harness):**
a per-grid-point `fp_by_density.csv` stratifier. Design (§T5 below) rather than modify the
existing scorers, per §3.1 "do not rebuild."

## T3 — Throughput benchmark → sharding decision

40-WAV benchmark (`--limit 40`, single process, all 45 points/WAV) launched on `owsfz/wav`
at 22:15:36 local. CPU time is climbing (not hung), but is markedly slower than `ea88d12`'s
2,037-WAV tune arm — full 45-point-per-WAV decode is CPU-bound (OSD/LDPC dominate). **Sharding
plan finalised once the benchmark's first `--progress-every` line lands**; this repo has 16
logical cores, so `NSHARDS=16` (one WAV subset per core, matching `run_sweep.sh`'s existing
per-shard-process model) is the default unless the benchmark says otherwise. Reported before
the real decode is kicked off, per spec §4.3's "report the split before executing."

## T4 — FP arm: S5 then S7, strictly sequential (spec §4.1)

Regenerate both from seed via `run_scenario.py --dry-run --dump-wav-dir` (offline synth, no
playback device involved — but the spec's constraint is honoured literally regardless: **no
concurrent processes touching S5 and S7, generation or decode, at any point**). Then decode
each under all 45 points with `--debug-log`, score via `matcher.py` (unmodified) exactly as
`ea88d12`'s Phase B/C.

## T5 — §5.4 density stratification (new script)

`density_stratify.py` (new, `qa/rr-study/d001-param-sweep-2026-07-22/`): for one grid point's
`decode.log`, pair consecutive `pass 1 of 2` / `pass 2 of 2` lines exactly as
`candidate_saturation_check.py` already does (reused pairing logic, not reinvented) — one pair
per WAV, in WAV-iteration order, which is also canonical-slot order for the FP arm (synthetic
timestamps are assigned in the same sorted-WAV order by `fp-corpus`). `candidates` per
cycle = pass-0 + pass-1 count (the total raw OSD load the QA→Architect note's Finding 1 and the
spec's §2.4 both describe as "raw candidates in one 15 s cycle"). Join against that point's
`S5_matched.csv`/`S7_matched.csv` `false_positive=True` rows by slot index to get FP-per-cycle,
then bucket into the pre-registered `0–9/10–24/25–49/50–99/100+` buckets and emit one row per
(point, scenario, bucket): `fp_count`, `slot_count`, `fp_per_100_slots`. Reported column only —
touches no ROW (spec §5.4).

## T6 — Recall arm: single full decode, no split

Decode `owsfz/wav` restricted to the decisive-epoch index range, sharded 16-way, 45 points,
**no `--debug-log`** (spec §4.5 — recall arm is ~4,551 × 45 ≈ 205k decodes; debug logs here
would be unmanageable for no gated purpose). Score with `score-recall --split-ts <full in-epoch
ts list>` against `wsjt-x/ALL.TXT` filtered to the same epoch.

## T7 — Assemble, apply the pre-registered rule, write deliverables

`assemble` → `sweep_grid.csv`. Evaluate ROW 1–4 in strict order exactly as written in the spec
(mechanical — the row conditions are already boolean expressions over the CSV columns). Write
`report.md` (QA authors Sections 1/5 + the Section 2 framing, HK-001/NFR-024), render via
`render_report.py`. Gather `decode.log`s / shard logs into the result directory **before**
declaring done (HK-016 — the `3bd4cd0` study's log survival near-miss is the standing example).

## T8 — NFR-021 / housekeeping

Raw WAVs, `ALL.TXT`, `truth.csv`, per-point decode output stay under this harness's git-ignored
`_work/`. Only `sweep_grid.csv`, `fp_by_density.csv`, `report.md` (+ rendered `.html`) are
committed, under
`qa/rr-study/results/2026-08-05-<sha>-d009-recalibration/` (spec §6.1). No `pre_merge_check.py`
(HK-006 — Captain's initiative only). No push, no merge (HK-010/HK-014 — QA doesn't merge
anyway). No recommendation ships without Captain sign-off (spec §6.2, ROW 1/2 only).

---

## Execution note

Given the WAV count and per-WAV decode cost (see T3), the recall arm alone is expected to run
for hours even sharded 16-way. This will be launched as a detached background process
(HK-023 — `nohup ... & disown`, PID-verified, not a bare `Monitor`/`CronCreate` job) with its
own log, so it survives independently of this session. QA will report the sharding split and
estimated wall-clock once T3 lands, then check back — no ROW result, Pareto frontier, or
recommendation will be reported before the run actually completes.
