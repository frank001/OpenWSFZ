# `FP-PARITY` — ROW 1 result: the in-chain genuine excess floor `F` (P4a)

**QA, 2026-09-04 ~13:37Z** (`date -u`, HK-017). Spec:
`qa/rr-study/2026-09-03-1616-architect-to-qa-spec-fp-parity-and-inchain-floor.md` §4 ROW 1,
corrected by **Amendment 1** (2026-09-04, A1.1/A1.2/A1.3). Execution order:
`qa/rr-study/2026-09-04-1322-architect-to-qa-execution-pack-post-shim-bump.md`, block **P4a** —
"no binary, no dependency, can start immediately, in parallel with P1." This report covers **ROW 1
only.** ROW 2/ROW 3 (P4b) are explicitly **held**, per the pack, until ROW 0n/0o (P3) close — see
§3 below.

Script: `qa/rr-study/fp-parity/row1_excess_floor.py` (HK-021(r) — the predicate/measurement ships
as code). Raw output: `qa/rr-study/fp-parity/row1_excess_floor_results.txt`. `git diff --stat --
src/ native/`: **empty**, verified before this report was written — this row touches no binary and
no `src/`/`native/` file.

**This is not an `AwgnFpReplayTests` (`Category=AwgnFpReplay`) run** — it reads five sweeps'
already-landed `owsfz-all.txt`/`truth.csv` from `qa/rr-study/results/`, not that xUnit class — so
A3.1's "quote the `--filter` line and ROW 0a's SHA pair" mandate does not apply to this report;
noted so its absence isn't mistaken for an omission.

---

## 0. What was on disk

The five frozen sweeps (Amendment 1 A1.1), re-verified present today before running anything
(HK-018):

| Sweep dir | `truth.csv` | `owsfz-all.txt` | S1b truth rows found |
|---|---|---|---|
| `results/2026-08-27-22b749c` | ✅ | ✅ | 12 |
| `results/2026-08-29-872ba65` | ✅ | ✅ | 12 |
| `results/2026-08-30-2e60949` | ✅ | ✅ | 12 |
| `results/2026-09-02-3b52608` | ✅ | ✅ | 12 |
| `results/2026-09-03-35378b9` | ✅ | ✅ | 12 |

All five, all 12/12 — nothing missing, nothing rendered. Per A1.1, this list is now **frozen**; no
sixth sweep may be added after this reading.

## 1. Method

Per spec §4 ROW 1, corrected by ROW 0q's settled rule (round-half-away-from-zero, not truncation —
`fp-parity/results/2026-09-03-row0q-row0m-report.md`). For each frozen sweep: load `truth.csv`,
keep rows with `scenario_id == "S1b"` (4 parts × 3 trials = 12 slots/sweep, `true_snr_db` ∈
{−24, −21, −18, −15}); load `owsfz-all.txt` via **`harness/common.py`'s `parse_all_txt`
only — never `matcher.py`** (HK-026, its FP column is still unscoped); for each S1b slot, a decode
is **truth-matching** iff its parsed message text equals that slot's `message_text` (`"CQ Q1ABC
FN42"` throughout). For every truth-matching decode: `excess = int(reported_snr_db) + 26.5`
(§2.2), then ROW 0q's conservative correction **−0.5 dB** applied uniformly (the direction that
makes `F` smaller, per spec).

## 2. Result

**Pooled population: 60 S1b slots (5 sweeps × 12, frozen). n = 30 truth-matching decodes.**

Per-rung decode rate, pooled across all 5 sweeps:

| Injected rung | Truth-matching / total | Rate |
|---|---|---|
| −15 dB | 15/15 | 100.0% |
| −18 dB | 15/15 | 100.0% |
| −21 dB | 0/15 | 0.0% |
| −24 dB | 0/15 | 0.0% |

**`F` (min corrected excess) = +8.00 dB. p01 = +8.00 dB. p05 = +8.45 dB. n = 30.**
Readout quantum: **1 dB** (`Ft8NativeResult.Snr` is `int`).
Weakest injected rung producing any truth-matching decode: **−18 dB**, decode rate at that rung
**15/15 (100.0%)**.

🛑 **Truncation statement (mandatory, spec §2.3): bottom-rung rate is 100.0% (> 50%) ⇒ `F` MUST be
reported as an UPPER BOUND on the true floor, never as the floor.** This exactly matches Amendment
1 A1.2's advance disclosure, now confirmed on the full pooled 60-slot population rather than the
single 2026-09-03 sweep A1.2 was written from: **0/15 pooled at −24 dB and 0/15 pooled at −21 dB**.
The true floor sits lower — the 2026-09-03 sweep alone already showed WSJT-X taking 2/3 at −21 dB
on the same slots OpenWSFZ took 0/3. The instrument's response is flat exactly where the boundary
sits (HK-026).

**Lowest 5 reconstructed (corrected) excess values** (A1.3 disclosure format):

| excess | reported SNR | injected rung | sweep | cycle_utc |
|---|---|---|---|---|
| +8.00 dB | −18 dB | −18 dB | `2026-09-02-3b52608` | 2026-09-02T17:00:15Z |
| +8.00 dB | −18 dB | −18 dB | `2026-09-03-35378b9` | 2026-09-03T18:05:00Z |
| +9.00 dB | −17 dB | −18 dB | `2026-08-27-22b749c` | 2026-08-27T18:06:00Z |
| +9.00 dB | −17 dB | −18 dB | `2026-08-27-22b749c` | 2026-08-27T18:06:30Z |
| +9.00 dB | −17 dB | −18 dB | `2026-08-27-22b749c` | 2026-08-27T18:07:00Z |

**14 distinct decodes** sit within ±1 dB of the published 8.622 dB fire line (full list in the raw
output file) — every one of them is one of the two `−18 dB → excess 8.00` slots or one of twelve
`−18 dB → excess 9.00` slots. There is effectively **no decode below −18 dB rung** in this
population at all: the entire near-line mass is the single ±1 dB readout-quantum step around one
injected level, exactly the "decided by one decode's readout quantum" shape Amendment 1 A1.3
predicted in advance.

## 3. ROW 2 / ROW 3 — deliberately **not decided** in this report

Per the execution pack's P4a/P4b split: `T = C + 1.0 dB` is an **offline**-anchored quantity, and
spec §3's two repairs (`NormalisePcm` parity — ROW 0n; decode-param parity — ROW 0o) are what make
it production-valid. Those are P3, not yet run. Rendering a ROW 2/3 verdict off today's `F` would
be citing `T` before it is confirmed to mean what the gate needs it to mean.

**For situational awareness only, not a verdict, and not new arithmetic** (already published in
Amendment 1 A1.3): with `T = 2.622 dB` unmoved as of the 2026-09-03 sweep, the fire line is
`F ≥ 8.622 dB`. Today's `F = +8.00 dB` is `< 8.622 dB` ⇒ **if** `T` is confirmed unchanged by P3,
this lands on **ROW 3** (margin `T − F = 0.622` dB short of the 6.0 dB policy margin — i.e. the
measured gap `F − T = 5.378` dB, matching Amendment 1's own `−18 dB → margin 5.38` row exactly).
This is **not** the ROW 2/3 reading — it is P3's to confirm or move.

## 4. Standing bars (unchanged)

This report proposes no capture run. It builds no filter — ROW 2 (dev-task authorisation) has not
fired, and could not fire in this report regardless, since ROW 2/3 are held for P3. NFR-021: both
new files (`row1_excess_floor.py`, `row1_excess_floor_results.txt`) scanned via the shipped
scanner's own `scan()`/`classify()` imported directly (it cannot scan an uncommitted directory,
HK-022) — **0 hits, 0 shapes, both files.**
