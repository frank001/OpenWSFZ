# Architect → QA — spec: D-009 parameter recalibration

**Author:** Architect, 2026-08-05 (20:03 UTC, `date -u`, per HK-017).
**Authorises:** design only. QA authors its own `tasks.md` / work order from this (HK-015).
**Requested by:** the Captain, 2026-08-05, overruling the Architect's proposed alternative scoping.
**Answers:** `qa/rr-study/2026-08-05-1942-qa-to-architect-d009-recalibration-setup.md`.
**Triggering evidence:** S1–S8 repeat at `3bd4cd0`, Finding 1 (`ddcc455`).

---

## 1. Scope — what this is, and what it is not

**In scope.** Re-derive the operating point for the three D-009 parameters
(`k_min_score_pass2`, `osd_corr_threshold`, `osd_nhard_max`) against a current, post-`be5960a`
corpus, and report where the shipped baseline `(10, 0.10, 60)` now sits relative to the Pareto
frontier.

**Out of scope, by the Captain's scoping decision.** Bisecting the three commits QA flagged;
adding a density term to the gate; the two managed-filter rule gaps in §6.3; `K_MAX_CANDIDATES_PASS2`.
These are recorded here so they are not lost, not reopened.

**No `src/` change. No capture run. No Developer session. No rig time.** This is a QA-tooling
sweep over corpora already on disk, following the `2026-07-22-ea88d12` precedent exactly.

---

## 2. Findings that shape this design

Four things established while preparing this spec. They change the design, so they are stated
before it, not after.

**2.1 `bb3790c` is eliminated as a cause — no run required.** The compile-time → runtime promotion
is semantically inert: `decode.c` retains `#define OSD_CORR_THRESHOLD s_osd_corr_threshold`
compatibility aliases so the gate code compiles unchanged; native defaults are byte-identical
(`10`, `0.10f`, `60`); the System.Text.Json zero-default trap is guarded by a `[JsonConstructor]`
with matching defaults; and both call sites use `?? new DecoderConfig()`. One of QA's three flagged
commits is ruled out at zero cost. **QA need not test it.**

**2.2 "The D-009 guard" is two mechanisms, and this spec tunes only one.** The log line
`filtered implausible message … (false-positive guard)` originates in `IsPlausibleMessage`
(`Ft8Decoder.cs`) — a *managed* structural grammar filter with **no runtime knobs**. The three
parameters swept here are the *native* OSD gate. QA's §2 evidence that "the guard is working but
not sufficient" is evidence about the managed filter; this recalibration acts on the native one.
Both are legitimate targets; they are not the same target.

**2.3 The managed filter is at a structural ceiling for the shape actually leaking.** All 17
scrubbed FPs are 3-token `CALL CALL GRID`. The filter's grid test rejects only Maidenhead leading
letters beyond `R`, but ft8_lib's unpacker emits `A–R` for that branch by construction — 0 of 17
leaked grids carried a letter in `S–Z`, against ~30% under uniform randomness. Across the run the
filter caught 60 and leaked 19 (76%); the residual is precisely the well-formed shape no syntactic
test can reject. **Consequence for this spec: the native gate is the only lever in scope that can
move the leak, which is what makes the recalibration worth running.**

**2.4 The leak is dose-responsive in candidates per cycle, not signals per scenario.** Measured
against the daemon's own candidate telemetry, aligned mechanically (−15 s; decode-count mismatch
67 vs 521/525 for the alternatives):

| candidates/cycle | cycles | FP lines | FP per 100 cycles |
|---|---|---|---|
| 0–9 | 103 | 0 | 0.0 |
| 10–24 | 228 | 8 | 3.5 |
| 25–49 | 75 | 4 | 5.3 |
| 50–99 | 14 | 1 | 7.1 |
| 100+ | 12 | 6 | 50.0 |

FP-bearing cycles average 64.1 candidates vs 19.5 for clean ones. This resolves QA's S7-vs-S8
non-monotonicity: co-channel stacks generate many marginal candidates from few signals.

> ⚠️ **Citation limit.** Exploratory, buckets not pre-registered, n=18 FP lines, 12 cycles in the
> top bucket. **A pointer for design, never a verdict, never a gate result.** Do not cite these
> numbers as a finding. §5.4 re-derives the stratification under pre-registration.

---

## 3. Design

### 3.1 Reuse, do not rebuild

`qa/rr-study/d001-param-sweep-2026-07-22/` is **fit for purpose as-is** — QA flagged its existence
without asserting fitness; the Architect has now checked it. It:

- drives parameters via `Ft8Decoder.SetDecodeParams` per grid point — **no rebuild per point**,
  a capability that did not exist when D-009 was first calibrated in June (it required diagnostic
  builds);
- reads per-slot WAVs directly and decodes in-process — **offline, deterministic, no rig, no timing**;
- already computes the Pareto frontier and a two-sided verdict (`assemble`);
- reuses the study's scorers verbatim, so results stay comparable to prior work.

**Do not re-derive the grid, the scorers, or the win rule.** Reuse them.

### 3.2 The grid — unchanged, 45 points

| Parameter | Values |
|---|---|
| `k_min_score_pass2` | 5, 7, 10, 15, 20 |
| `osd_corr_threshold` | 0.10, 0.15, 0.25 |
| `osd_nhard_max` | 40, 60, 80 |

Baseline **B = (10, 0.10, 60)**. Identical to `2026-07-22-ea88d12` so the two grids are directly
comparable cell-for-cell.

### 3.3 Corpora

**Recall arm — `20260803_live_run_1713`, `owsfz` leg WAVs, WSJT-X leg `ALL.TXT` as reference.**
Restrict to the **contiguous decisive epoch from `260803_185914`** (18.96 h), not the full folder
span. Chosen because it is post-`be5960a`, drift screen ROW 5 PASS (+0.0 ppm), and — uniquely —
carries both decoders on **one verified audio path** (median |r| = 0.987 over 8 WAV pairs,
lags ≤ 34 ms), which is what makes WSJT-X a valid same-audio reference here. Inventory-confirmed:
`owsfz` 4,971 WAVs / 4,614 cycles, `wsjt-x` 4,963 WAVs / 4,531 cycles.

> This corpus is read-only here. It is also Arm R.D's corpus (specced, unrun); nothing in this
> spec consumes or mutates it.

**FP arm — synthetic, regenerate from seed.** S5 (`s5-noise-wide.json`, ≥120 slots pure AWGN) and
S7 (`s7-compounding.json`, 21 parts). Seeded and reproducible; no capture needed.

**Why not the 07-06 corpus the previous sweep used:** it was captured pre-`be5960a`, so it embeds
the old framing. Calibrating on it would tune for alignment the product no longer has.

### 3.4 Optional Arm A — attribution. **NOT authorised by this spec.**

Re-running the same 45 points on the **07-06 corpus** (`20260706_live_run_2308`, 4,075 WAVs, on
disk) would be directly comparable to `2026-07-22-ea88d12` and would isolate the managed-code delta.
Recorded as a costed option only; it doubles compute and the Captain has not funded it. **Do not
run it without separate authorisation.**

Reference row from `ea88d12`, should it ever be wanted:
`k10_c0.10_n60 → recall 36.138%, s5_fp/slot 0.00833, s7_fp/slot 0.07619, s7_recovery 84.651%`.

---

## 4. Execution constraints — mandatory

1. **S5 and S7 must run sequentially, never concurrently.** The June `d009-k10-confirm-s5` /
   `-s7` pair was VOIDed because both were played into the same VB-CABLE device and the OS mixer
   combined the streams. Their `CONTAMINATED.md` files are the precedent. **Violating this VOIDs
   the FP arm.**
2. **NFR-021.** All raw artefacts — WAVs, `ALL.TXT`, `truth.csv`, per-point decode output — stay
   local under the harness's git-ignored `_work/`. Only the aggregate grid CSV and `report.md`
   (coordinates, counts, rates; no callsigns, no message text) are committed.
3. **Sharding.** Disjoint WAV subsets in separate processes, each with its own native globals, per
   the harness's existing note. Run `sweep_driver.py plan` first and report the split before
   executing.
4. **HK-009.** Console output ASCII-only or `reconfigure(encoding="utf-8")`.
5. **`--debug-log` for the FP arm only** (225 slots), not the recall arm (~4,600 × 45). Needed for
   §5.4; enabling it across the recall arm would generate unmanageable logs for no gated purpose.
6. **HK-016.** Gather the daemon/decode logs into the result directory *before* reporting done.
   The `3bd4cd0` study's log survived only in `src/OpenWSFZ.Daemon/bin/Release/net10.0/logs/` —
   one `dotnet clean` from loss, and every §2.4 number depends on it. Do not repeat that.

---

## 5. Pre-registered decision rule

Fixed before any decode runs. Rows are evaluated in strict order; **the first matching row wins and
evaluation stops.** Rows are mutually exclusive and exhaustive.

Definitions, all read from the assembled grid CSV:

- `rec(p)` = recall %, `s5(p)` = S5 FP/slot, `s7(p)` = S7 FP/slot, for grid point `p`.
- **WIN(p)** ≔ `rec(p) > rec(B)` **AND** `s5(p) <= s5(B)` **AND** `s7(p) <= s7(B)`.
  (The 07-22 two-sided rule, verbatim: a recall gain bought with an FP regression is a trade-off,
  never a win. **The two arms are never blended into a single score.**)
- **RELIEF(p)** ≔ `s5(p) <= 0.50 * s5(B)` **AND** `s7(p) <= s7(B)` **AND** `rec(p) >= rec(B) - 1.00`.
- **B_on_frontier** ≔ no point `p` exists with `rec(p) >= rec(B)` and `s5(p) <= s5(B)` and
  `s7(p) <= s7(B)` and `p != B`.

| Row | Condition | Consequence |
|---|---|---|
| **ROW 1** | ∃ `p` : `WIN(p)` | ⇒ The optimum has **MOVED**. Report every winner, the full Pareto frontier, and nominate `argmax rec(p)` among winners as the candidate. **⇒ Captain sign-off required before any value ships. QA does not ship it.** |
| **ROW 2** | No `WIN`, and ∃ `p` : `RELIEF(p)` | ⇒ No strict improvement, but a **trust-first option exists**: ≥50% FP reduction for ≤1.00 pp recall. Report as a costed menu row. **⇒ Captain decision required.** |
| **ROW 3** | No `WIN`, no `RELIEF`, and `B_on_frontier` | ⇒ Baseline `(10, 0.10, 60)` is **still Pareto-optimal on this corpus**. **⇒ Recalibration returns NO CHANGE.** This is a valid and complete result, not a failed run. |
| **ROW 4** | No `WIN`, no `RELIEF`, and **not** `B_on_frontier` | ⇒ Contradiction: `B` is dominated yet no point qualifies. **⇒ VOID the run and report a harness defect.** Do not interpret the grid. |

### 5.4 Density stratification — reported, not gated

For the FP arm only, parse `candidates found` from the per-point decode logs and emit, **per grid
point**, FP/slot stratified by the pre-registered buckets `0–9 / 10–24 / 25–49 / 50–99 / 100+`.

This is a **reported column, not a gate.** It carries no ROW and cannot VOID anything. Its purpose:
because a single constant triple is applied to cycles whose candidate load varies ~20×, the chosen
operating point is necessarily a compromise across that range. This table makes the compromise
visible in the output instead of hidden inside an average. It also puts §2.4 on a pre-registered
footing, so a future study may cite it where §2.4 itself may not be cited.

---

## 6. Deliverables

**6.1** `qa/rr-study/results/2026-08-XX-<sha>-d009-recalibration/` containing:
- `sweep_grid.csv` — 45 rows, same schema as `2026-07-22-ea88d12/sweep_grid.csv`;
- `fp_by_density.csv` — §5.4 stratification;
- `report.md` — QA authors Sections 1/5 and the Section 2 framing (HK-001 / NFR-024); rendered via
  `render_report.py`.

**6.2** `report.md` must state, explicitly: the ROW fired; the Pareto frontier; where `B` sits on
it; the §5.4 table; and, if ROW 1 or ROW 2, the costed menu for the Captain. **No recommendation
ships without his sign-off** — the June D-009 investigation ended with the trade declared
irreducible and a Captain-accepted compromise that already fails one of its own gates
(`co_channel_sweep` 86.67% < 89%). Expect a menu, not a winner.

**6.3 Recorded, not actioned** (out of scope per §1, for whoever next touches the managed filter):
the FP count in the `3bd4cd0` study is **19, not 17** — two structurally-impossible lines carry no
`[FP-CALL]` marker because the scrubber keys on callsign-shaped tokens. Both should have been caught
by existing rules: the 4-token rule validates only that token 0 is `CQ` and never checks the
callsign position, and a 2-token `<hash> <11-char junk>` slipped `IsCallsignShapeInvalid` despite a
code comment saying that exact pattern was already fixed once. Two cheap, testable gaps. `src/`, so
Developer session + Captain authorisation.

---

## 7. Limitations — stated once

1. **This sweep cannot observe the drift fix.** The harness consumes pre-framed per-slot WAVs and
   bypasses `CycleFramer` entirely. It recalibrates the parameters; it **cannot** establish whether
   `be5960a` moved the optimum. Using a post-fix corpus (§3.3) means we calibrate against current
   framing, which is what the product needs — but attribution stays open. Only Arm A (§3.4) or a
   live re-run would close it.
2. **A single constant triple has no density term** (§2.4, §5.4). Whatever ROW fires, the result is
   an operating point averaged across a ~20× range of candidate load.
3. **The FP arm is synthetic.** S5/S7 measure FP under controlled conditions, not on-air ones. The
   recall arm is real off-air audio; the two are never blended (§5).

---

## 8. What QA does not do

- Does not ship, merge, or push any parameter value — `report.md` and the CSVs only (HK-010/HK-014).
- Does not run `pre_merge_check.py`; that is the Captain's initiative only (HK-006).
- Does not touch `src/` — including §6.3 (HK-011).
- Does not declare "ready for merge" unprompted.
- **Escalates rather than adapts** if the harness needs any change to execute this: say so and stop.

QA authors its own task breakdown from this spec.
