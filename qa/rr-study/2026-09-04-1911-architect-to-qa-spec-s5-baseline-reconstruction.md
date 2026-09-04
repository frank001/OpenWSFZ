# Architect → QA — SPEC `S5-BASELINE`: reconstruct the S5 AWGN false-positive baseline

**Author:** Architect · **UTC:** 2026-09-04 19:11Z (mechanically derived, HK-017)
**Status:** PRE-REGISTERED. Nothing executed. Requires PO ratification of §0.2 before QA runs it.
**Type:** Pure re-analysis of committed run directories. **No capture, no playback, no decode, no
`src/` or `native/` change** ⇒ no Developer session (HK-011 not engaged).

---

## 0. Why this exists

The `FP-REGRESSION` arm is blocked on choosing an effect size to power a re-scoped arm against. Two
candidates are on the table: the ratified **`4.88×` / p = 0.0154** and the composition-normalised
**`3.25×` / p = 0.0765** (18:11Z / 18:20Z rulings; `FP-COMPOSITION` cleared the inputs to the
latter at 18:48Z).

**Both are contrasts against a pre-window that has never been shown to be a baseline.** This spec
tests whether it is one. It is the first input to the re-scope's design, and it is cheap.

### 0.1 🔴 DISCLOSURE — this spec is written on partly de-blinded data (HK-021 calibration)

While verifying the 18:11Z ruling I ran an **exploratory, non-pre-registered** analysis that
produced the numbers below. They are **NOT results**, carry **no ROW**, and **must not be cited**.
They are disclosed because they de-blind ROW 1 and ROW 2:

| Exploratory quantity | Value |
|---|---|
| Post-window vs `a3738fc` (July, N=300) | 1.35×, Fisher one-sided p = 0.3231 |
| Pre-window vs `a3738fc` | 1.111% vs 2.667%, p = 0.2083 |
| Boundary-free permutation trend, nine battery runs | p = 0.056 |

⇒ 🛑 **Architect prediction-scoring is SUSPENDED for ROW 1 and ROW 2** (precedent: the 2026-08-10
X1/X2 scoping-run disclosure). It is **NOT** suspended for **ROW 0b, ROW 0c, ROW 0d**, which I did
not compute and cannot predict from what I have seen. Those three rows are where this task's real
information is; ROW 1/ROW 2 are reproduction with an independent implementation.

### 0.2 🔴 Two Architect findings this spec rests on — PO must ratify before QA runs

**(A) The window boundary was chosen by inspecting the outcome.** The `FP-REGRESSION` spec §2
annotates `f5dec23` as *"first clearly elevated"* — the 08-22 split sits where the step looks
largest in the same data the p-value is computed from. **Both `4.88×` and `3.25×` therefore report
p-values that do not have their nominal meaning.** This is adjacent to HK-021 sibling **(s)** but
distinct: (s) is a threshold miscalibrated against exposure share; here the **split location itself**
is data-chosen. **Proposed new sibling (y)** — text in §7.

**(B) The pre-window may be a low excursion, not a floor.** Two gate-era S5 runs dated 2026-07-04
are absent from Section 6 (which lists routine full batteries only) and from every FP-REGRESSION
document. Both use `s5-noise-wide`, whose own `channel_note` reads *"Wideband AWGN only (no
noise_cutoff_hz), **matching s5-noise.json** and the single-signal path"*, with the same
`compute_seed('S5', part_index, trial_index)` formula and the same single delivered level. `f-002`
**shipped** (PR #37 `238ee45`; `IsCallsignShapeInvalid` is on `main`), so `a3738fc` measures the
shipped configuration:

| Date | Run | Config | AWGN k/N | Rate |
|---|---|---|---|---|
| 07-04 | `d011-fp-recheck-2026-07-04` | pre-`f-002` | 7/120 | 5.83% |
| 07-04 | `a3738fc-f002-s5-n300` | **`f-002`, shipped** | **8/300** | **2.67%** |
| 08-05 → 08-21 | pre-window (3 runs) | `main` | 2/180 | 1.11% |
| 08-22 → 09-03 | post-window (6 runs) | `main` | 13/360 | 3.61% |

🛑 **This is a hypothesis, not a finding, and it has a named confound** — see ROW 0d. Do not treat
the July rows as admissible until ROW 0b and ROW 0d have been evaluated.

---

## 1. The question, stated so it can be answered wrong

> **Over the ratified-gate era, is the 2026-08-05 → 08-21 window distinguishable from the earlier
> shipped-configuration S5 AWGN false-positive rate — and is the population that would answer that
> question identifiable at all?**

**The second clause is not decoration.** If battery context is perfectly confounded with era, the
first clause has no answer from this corpus, and saying so is the deliverable.

---

## 2. Population and admissibility

**Unit:** one signal-free **AWGN slot**. **Metric:** per-slot FP **event** (≥1 OpenWSFZ decode in
that slot), collapsed to the gate's own unit — **events, not decode rows.** This is the likeliest
way to get the task wrong (it was called out in `FP-COMPOSITION` for the same reason).

**Admissible** iff all four hold, each verified mechanically, never from prose:

1. Run is at or after the **R&R-004 ratified UB gate** (2026-07-04) — earlier rows report a plain
   decode rate, a different metric (Section 6 footnote 1).
2. Scenario `id == "S5"` and the contributing part has `noise_type == "awgn"`.
3. Slot count at the AWGN condition **N ≥ 49** (below it the gate is INFO by construction).
4. **ROW 0b passes for that run's scenario file** (audio-condition equivalence).

**Excluded, and state the reason in the report:** carrier (part 2) and multi-carrier (part 3)
slots — `FP-COMPOSITION` ROW C3 measured 15/15 all-time events in parts 0/1, zero in 2/3, so they
are denominator with no numerator and pooling them re-introduces exactly the composition defect the
18:11Z ruling identified.

---

## 3. ROW 0 — instrument gates, evaluated IN ORDER

For each row, the drafting question of HK-022 was asked: *what error could this row NOT detect?* The
answer is recorded with the row.

### ROW 0a — reproduction gate. Evaluated FIRST.

Recompute each admissible run's FP **event** count and N from its committed `*_matched.csv` +
`truth.csv`, and compare against **that run's own `report.md` §10 gate line** (never Section 6's
`S5 FP` column, which mixes rates and 95% UBs — HK-031).

- **FIRES iff** any run's recomputed `(count, N)` differs from its own gate line.
- **Consequence: STOP.** Report the mismatch; change nothing. An instrument that cannot reproduce
  nine ratified readings has no standing to re-attribute a tenth.
- *Cannot detect:* an error present identically in both the generator and the report (shared-code
  blind spot). ROW 0b is the independent check on the stimulus side.

### ROW 0b — 🔴 audio-condition equivalence. THE LOAD-BEARING ROW.

§0.2(B) rests entirely on `s5-noise-wide` part 0 being the **same physical condition** as
`s5-noise` parts 0/1. That claim is currently supported only by a `channel_note` — **prose**. Verify
it against delivered samples.

**Method — reuse the harness's own functions, do not reimplement them** (the ACTION B ruling's
lesson): import `compute_seed` from `harness/common.py` and `_render_noise` +
`_finalize_playback_samples` from `harness/run_scenario.py`. For `trial_index` 0..29, render part 0
of `s5-noise.json` and part 0 of `s5-noise-wide.json`, finalise each, and SHA256 the resulting
buffer. **Render only — no device, no playback, no decode.**

- **FIRES iff** fewer than **30/30** trial pairs are byte-identical.
- **Consequence: STOP; the July runs are INADMISSIBLE and §0.2(B) is withdrawn.** ROW 1 does not
  run; ROW 2 runs on the nine battery runs only.
- ⚠️ **"Byte-identical" must be mechanically diffed, never asserted** (standing rule). Report the
  hashes, not a claim about them.
- ⚠️ Sort every collection at construction — hash-randomised set iteration silently breaks seeded
  determinism (standing rule).
- *Cannot detect:* a difference introduced **after** `_finalize_playback_samples` — i.e. in the
  playback device chain. Record that as a residual, do not attempt to bound it (HK-026: the offline
  renderer's response is flat there).

### ROW 0c — census completeness

Enumerate every S5-bearing run directory **directly from disk** under `qa/rr-study/results/`.
🔴 **Do not source this from `qa/ARTEFACT_INVENTORY.md`** — its only root is `artefacts/`, so its
response is flat over `qa/` (15:07Z ruling, HK-026). Do not source it from Section 6, which lists
routine batteries only — that omission is how the July runs were missed for two months.

- **FIRES iff** any run meeting §2's admissibility criteria is absent from §0.2(B)'s table.
- **Consequence: NOT a stop.** Add it, rebuild the series, and run ROW 1/ROW 2 on the full set.
  Report which runs were added and by which criterion.
- *Cannot detect:* an S5 run committed outside `qa/rr-study/results/`.

### ROW 0d — 🔴 identifiability of battery context. THE ROW THAT DECIDES WHAT MAY BE REPORTED.

`run_study.py:76` sets `_CONTROLLED_SCENARIO_IDS = ["S1","S1b","S2","S3","S4","S5","S7"]` ⇒ in a
battery run, **S5 is played after S1/S1b/S2/S3/S4** — hundreds of slots carrying real FT8 signals.
A standalone S5 run meets a cold decoder. That is a real, named difference in exposure between the
July runs and the Aug/Sep runs, and it is a candidate cause of any rate difference.

Classify every admissible run on two axes and cross-tabulate:
- **era** ∈ {`2026-07`, `2026-08-05..08-21`, `2026-08-22..09-03`}
- **context** ∈ {`standalone`, `battery`} — determined from the run's own committed
  `truth.csv` / report scenario list (which scenarios ran), **not** from the directory name.

- **FIRES iff** any cell of the era × context cross-tabulation containing an admissible run has a
  complementary cell of **0** — i.e. context is perfectly confounded with era.
- **Consequence if it FIRES:** 🛑 **ROW 1's cross-era contrast MUST NOT be reported as a p-value or
  a ratio.** Report both arms as counts with exact Clopper–Pearson intervals and the label
  **"not identifiable — context confounded with era"**. This is the honest answer and it is
  decision-relevant: it means the baseline cannot be established from the existing corpus and the
  re-scope must either accept that or budget a cold/warm control.
- **Consequence if it does NOT fire:** at least one run breaks the confound; ROW 1 proceeds
  **stratified by context**, never pooled across it.
- *Cannot detect:* a within-battery ordering effect (S5 always sits in the same position), or any
  exposure difference not captured by the two axes.

🔴 **This row is genuinely diagnostic, not decorative (HK-021(k)/HK-025):** both branches change what
QA is permitted to report, and I do not know which way it goes — whether an Aug/Sep standalone S5
run exists (`d009-k10-confirm-s5*`, `s5-noise-diag40`, `2026-06-20-ccda50c-s5-wide` and the `diag-*`
dirs are candidates ROW 0c will resolve) is unknown to me and is the highest-value thing in this task.

---

## 4. ROW 1 and ROW 2 — the measurement

### ROW 1 — is the pre-window below the shipped-configuration baseline?

Runs only if ROW 0b passes. Reported per ROW 0d's branch.

- **Statistic:** pre-window AWGN events/slots vs July shipped-configuration (`a3738fc`, and any run
  ROW 0c adds at the same configuration) AWGN events/slots.
- **Test (only if ROW 0d does not fire):** Fisher exact, **one-sided in the stated direction**
  (pre-window **lower**). 🔴 Report the **signed** difference, never `|x|` — HK-021(l); a sign-blind
  statistic on a one-sided phenomenon has been an Architect-authored fault three times.
- **Intervals:** exact **Clopper–Pearson**. 🛑 **No bootstrap SE** — the readout quantum is one
  event in N slots and that quantum sets the resolution floor, not a resampled SE (HK-021(o)).
- **Base rate in the same sentence as any ratio** (HK-021(u)).
- **FIRES iff** the pre-window rate is below the baseline rate at p < 0.05 one-sided.
- **Consequence if it FIRES:** the pre-window is an excursion, not a floor; **`3.25×` may not be
  used as the re-scope's effect size** and the contrast must be re-derived against the baseline.
- **Consequence if it does NOT fire (equally costly — HK-021(t)):** the pre-window is not shown to
  differ from the July baseline **either way**; report the CP interval's **position** relative to
  the baseline, because for an interval-valued readout ignorance is decisive by position, not by
  width (HK-021(w)). A wide interval spanning both is "underpowered", **not** "no difference".

### ROW 2 — boundary-free trend

The 08-22 split is data-chosen (§0.2(A)), so also compute a statistic that needs **no** change point.

- **Statistic:** conditional permutation test — condition on the total event count, distribute
  events across runs proportional to each run's admissible AWGN N, score by run date, one-sided
  (later than expected).
- **Report:** the p-value **with its Monte-Carlo quantum stated** (e.g. `N = 2,000,000 ⇒ 5e-7`), and
  a **leave-one-run-out** table. Seed the RNG explicitly and record the seed.
- **FIRES iff** p < 0.05 **and** no single run's removal lifts it above 0.10.
- **Consequence if it FIRES:** the upward trend survives without a change point, and the re-scope
  may be powered against a trend rather than a step.
- **Consequence if it does NOT fire:** the trend is load-bearing on individual runs; name them.
  This does **not** restore "no regression" — direction is unchanged (18:11Z).

---

## 5. Mechanical acceptance

- `qa/rr-study/s5_baseline_reconstruction.py` exists and **ships every predicate above as code**
  (HK-021(r)), re-runnable by anyone, deterministic, seed recorded.
- ROW 0a reports one line per admissible run: recomputed `(k, N)` and the run's own gate line.
- ROW 0b reports **30 hash pairs**, not a summary claim.
- ROW 0c reports the disk enumeration and every added/rejected run with its criterion.
- ROW 0d reports the full era × context cross-tabulation, including zero cells.
- **NFR-021:** S5 FP rows carry hallucinated callsign-shaped tokens by construction. Import
  `scan()` / `classify()` from `nfr021_pre_merge_scan.py` **directly** and run them over the new
  files — 🔴 **do not use the CLI over a committed ref and do not do a directory walk**; both
  false-green on uncommitted files. A flagged token means the join grabbed something it should not:
  **investigate, do not redact past it.** Scan report **prose** too.
- `git diff --stat -- src/ native/` **empty**, and say so.
- Commit locally. **Do not push** (HK-014). `main` currently carries `ac6150d`'s `src/`+`native/`
  diff, so HK-029's direct-push exception does **not** apply — verified this session.

---

## 6. Reporting standard

🛑 **QA reports the table and the mechanical row outcomes. QA does NOT rule on what this means for
the arm, the re-scope, or the regression.** Fusing measurement and adjudication is what put `4.88×`
where it is (18:20Z). Adjudication is the Architect's; ratification is the PO's.

🔴 **HARD STOP: the session stops after ROW 2, on either branch.** Per HK-030, a written hard stop
means **pause and hand back**, not merely "do not push".

**QA may refuse this spec on HK-021(k) grounds without Architect agreement (HK-025).** If a row
looks diagnostic-only — same consequence on both branches — classify and refuse; do not run it and
flag it afterwards.

---

## 7. Proposed new HK-021 sibling (y) — PO's call, not adopted by this document

> 🔴 **A change point chosen by inspecting the outcome series is not a pre-registered split.** A
> p-value computed across it does not have its nominal meaning. Either derive the split from a
> **mechanism** fixed independently of the outcome (a merge, a build, a config change, with its
> date taken from version control), or use a statistic that needs no change point — and say which.
>
> **Tell:** a window boundary annotated with a superlative drawn from the data itself — *"first
> clearly elevated"*, *"the last clean sweep"*.
> **Drafting question:** *"if I had not already seen the counts, what would have told me to put the
> boundary here?"*

Distinct from **(s)**: (s) is a threshold miscalibrated against exposure share; (y) is the split
**location** being outcome-selected. Both can occur in the same gate.

---

## 8. What this task must NOT do

- 🛑 No capture, no playback, no decode, no rebuild, no `src/`/`native/` edit.
- 🛑 Do not re-measure the WSJT-X `0/840` control — standing instruction.
- 🛑 Do not repair, exclude, or "clean" any run's committed data. A moving numerator is the PO's to
  rule on (the `8d6e1b1` precedent).
- 🛑 Do not re-read a closed gate with a better metric — that earns a NEW pre-registration.
- 🛑 Do not cite `3.333%` as a baseline; the regression/trend baseline is `2/360 = 0.556%` and is
  itself what ROW 1 puts in question.
