# `S5-STANDALONE` — Architect → QA spec: measure the S5 AWGN false-positive rate on the CURRENT build in the JULY context

**Architect, 2026-09-05 13:11Z** (`date -u`, HK-017). Base `main`@`10bbaad`.
Ordered by the PO on 2026-09-05 in response to the `S5-BASELINE` result (QA, 2026-09-04 20:10Z),
whose **ROW 0d fired**: pre-window and post-window each contain **zero** standalone-context S5 runs,
so era and battery context are confounded and `ROW 1` could not be reported as a ratio or a p-value.

The PO's ruling, in full: *"go with 1"* — Option 1 of the 2026-09-05 adjudication, *"design a run
that breaks the confound — a standalone S5 sweep on current `main`, matched to the July protocol
(cold decoder, N=300)."*

**This spec fills the empty cell.** It does not re-analyse anything; it produces the one measurement
that does not exist anywhere on disk.

---

## 0. What this arm is, what it is not, and two disclosures

### 0.1 What it is

**One live standalone S5 run**, N=300 AWGN slots, on the current `main` binary, in a **cold**
decoder context, using the **same scenario file and therefore the same 300 noise realisations** as
the July `a3738fc` run. Its purpose is a single contrast:

> **July `8/300` (standalone, cold, shipped `f-002` config) vs today `k/300` (standalone, cold,
> current build).** Context is held fixed by construction. Era/build is the only deliberate
> difference.

### 0.2 What it is NOT

- 🛑 **Not a bisect.** The two arms differ by two months of product change. This arm measures the
  *bundle*; it cannot attribute to a commit, and no row here may be read as attributing to one.
  `FP-REGRESSION`'s bisect is VOID (ROW 0a, 2026-09-04) and this does not revive it.
- 🛑 **Not an adjudication of `3.25×`.** `3.25×` is HELD by the PO's 2026-09-04 19:2xZ ruling and
  stays held. This arm supplies an input to that decision; QA draws no verdict on it (§6).
- 🛑 **Not a re-measurement of anything in §1.** Those facts are established. Do not re-derive them.
- 🛑 **Not a licence to change `src/` or `native/`.** HK-011 is not engaged and must not become
  engaged. If any row appears to need a product change, stop and escalate.

### 0.3 🔴 Disclosure — the Architect is de-blinded, and prediction scoring is suspended

While drafting this spec the Architect had in view, simultaneously: every admissible run's AWGN FP
count (from `S5-BASELINE` ROW 0a/0c) **and** the per-run delivery-cadence covariate computed in §2.3.
**Prediction scoring is suspended for every row in this document** (the `S5-BASELINE` §0.1 precedent).
§7's predictions are recorded for the calibration file only and **nothing gates on them**.

🔴 **The Architect has NOT computed the association between the §2.3 covariate and the FP counts,
and deliberately did not.** ROW 2 pre-registers that association with its statistic and threshold
fixed *before* anyone computes it. If QA finds evidence the Architect did compute it, ROW 2 is void
as a pre-registration and must be reported as exploratory.

---

## 1. What is already established — do not re-derive it (HK-018)

Every line is measured and on disk. Read them; do not re-run them to "check".

| Fact | Source | Status |
|---|---|---|
| The 12 admissible S5 runs, their eras, contexts, AWGN N and AWGN k | `S5-BASELINE` ROW 0a/0c, `s5_baseline_reconstruction_result.json` | **Solid**, 24/24 pairs reproduced against each run's own `report.md` gate line |
| **No Aug/Sep standalone S5 run exists** anywhere under `qa/rr-study/results/` | `S5-BASELINE` ROW 0c, enumerated from disk | **Solid, exhaustive.** This arm exists to create the first one |
| Era × context is confounded: pre-window and post-window each have **0** standalone runs | `S5-BASELINE` ROW 0d | **Solid** |
| July `a3738fc-f002-s5-n300` = **8/300** OpenWSFZ, **0/300** WSJT-X, standalone, `f-002` shipped | that run's own `report.md` §10; reproduced by ROW 0a | **Solid** |
| `s5-noise-wide-n300.json` is S5, **part 0 only**, `trials 0..299`, `noise_type: awgn`, no `level_dbfs` | the file; July run's `truth.csv` (300 rows, all part 0, trial 0–299) | **Solid** |
| `compute_seed` keys on the scenario's **`id` string** (`"S5"`), not the filename | `harness/common.py`; `S5-BASELINE` ROW 0b's disclosed finding | **Solid** ⇒ July's and today's trial *t* share a seed by construction |
| `s5-noise.json` p0 and `s5-noise-wide.json` p0 render **byte-identically** (30/30 SHA256) | `S5-BASELINE` ROW 0b | **Solid** for those two files. **Not yet shown for `-n300`** ⇒ ROW 0b below |
| S5 parts 2/3 are carrier/multi-carrier, **not AWGN**; only 0/1 are the AWGN population | `s5-level` ROW 0f | **Solid, exhaustive** |
| The daemon normalises every buffer to RMS 0.20 before `DecodeAll` ⇒ capture **gain** cannot move the in-chain rate | `Ft8Decoder.cs:52/271/303` | **Solid** |
| WSJT-X has produced **0/840** S5 FPs across all nine battery runs | `FP-COMPOSITION` C1 side finding | **Solid** — the rig is excluded |
| `Ft8NativeResult.Snr` is `int` ⇒ readout quantum **1 dB** | `Ft8NativeResult.cs:32` | **Solid** (HK-021(o)) |

**HK-031 discharged.** `Section 6 — Historical trend` of the latest sweep
(`results/2026-09-03-35378b9/report.md`) was read before this spec was written. The series being
reasoned about, quoted, OpenWSFZ column (one-sided 95% CP UB, per that table's own caveat):

> `06-06 0.0% · 06-06 0.0% · 06-07 0.0% · 06-14 0.0% · 06-20 91.7% FAIL¹ · 06-22 0.0% · 07-04 0.0% ·
> 08-05 0.0% · 08-15 0.8% · 08-21 0.8% · 08-22 3.3% FAIL² · 08-27 0.0% · 08-29 7.66% FAIL ·
> 08-30/31 5.15%⁴ · 09-02 14.61% FAIL · 09-03 10.12% FAIL`

🛑 **Never back-compute counts from that column** — it mixes rates and 95% UBs (HK-031). Every count
in this spec comes from each run's own gate line via `S5-BASELINE` ROW 0a.

---

## 2. The build and the stimulus — settled at drafting time, per HK-021(p)

> 🛑 *"PRE-REGISTER THE BUILD, NOT JUST THE SHA … 'which binaries exist on disk, and what does each
> differ from?' is a question for §2 of the spec, not for QA's first hour."*

### 2.1 The build — and a fact that makes this arm cheaper than it looks

Measured, not quoted:

| Ref | `libft8.dll` git blob | Meaning |
|---|---|---|
| `ac6150d` (shim `20260050`) | `93de78256f71123a7bbf463219c33f0b24f970bf` | the L3 export build |
| `35378b9` (the 2026-09-03 battery run) | `93de78256f71123a7bbf463219c33f0b24f970bf` | **same blob** |
| `main`@`10bbaad` (today) | `93de78256f71123a7bbf463219c33f0b24f970bf` | **same blob** |

`git diff --stat 35378b9..main -- src/ native/` is **empty**.

🔴 **Consequence, and it is the enabling fact of this arm:** the binary this run will exercise is
**the same binary** that produced the `2026-09-03-35378b9` battery run (`2/60` AWGN). So the new
standalone leg and an existing battery leg sit on **one build**, and the context contrast is
available at fixed build for free (ROW 3, secondary).

**Working-tree pin to assert (ROW 0a):**
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` SHA256 =
`6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c`
(independently corroborated — `Row0rCarryForwardTests` asserted this same value on 2026-09-04).

⚠️ **What the July arm differs from, stated plainly:** `a3738fc` → `main` is ~2 months of managed
*and* native change. That is the arm's **exposure**, not a confound to bound. It is also why §0.2
bars any per-commit attribution.

🔴 **And it is not assumed benign.** `ac6150d`'s commit message claims the shim bump is *"provably
non-perturbing to decode output"* on a 60-cycle/647-decode byte-identity check. **`AWGN-FP` ROW 0r
(2026-09-04) contradicts that on the population that matters here: 246 of 4,000 AWGN slots — 56.6%
of the event slots — changed decode set between `20260049` and `20260050`.** The byte-identity check
was run on signal-bearing audio; its instrument is flat where this boundary sits (HK-026). Treat the
shim bump as decode-relevant on noise. *(No action required in this arm; recorded so nobody re-imports
the "purely additive" argument.)*

### 2.2 The stimulus — same seeds as July, but the FILE changed since

`compute_seed('S5', 0, t)` is identical for July and today. **But `s5-noise-wide-n300.json` was
edited after the July run:**

| Commit | Date | Effect |
|---|---|---|
| `1e07425` | 2026-07-04 | the July run itself |
| `7ebc2b6` | 2026-09-03 | `S5-LEVEL` Option 2 — `level_dbfs` **deleted** |

`S5-LEVEL` ROW 0j asserted the deletion was byte-neutral (60/60 SHA256) **for `s5-noise.json`**.
It has **not** been asserted for `-n300`. ROW 0b closes that, at N=300 rather than by inheritance.

### 2.3 🔴 The delivery path changed between July and today — a real covariate, previously unraised

`dc4281f` (2026-08-29) replaced per-trial `sd.play()` with one batched, back-to-back stream
(`_flush_batch`), later capped at `_MAX_BATCH_TRIALS = 20` by `c30ec5b` (2026-08-31) because
unbounded batching made **"both appraisers' decode counts collapse to noise-hallucinated garbage
roughly 18–19 minutes in."** A harness path that can manufacture decodes out of noise is, in an FP
study, the instrument competing with the measurand.

`cycle_utc` in every run's own `truth.csv` already records the delivered cadence (HK-027 — the
instrument already records it; no human observation needed). Fraction of consecutive S5 trial pairs
delivered **more than one slot apart**:

| Run | n | gap fraction |
|---|---|---|
| `2026-07-04-a3738fc-f002-s5-n300` (**the July comparator**) | 300 | **12.7%** |
| `d011-fp-recheck-2026-07-04` | 120 | 11.8% |
| `2026-07-07-df4cc89` | 120 | 13.4% |
| `2026-08-05-3bd4cd0` | 120 | 3.4% |
| `2026-08-15-8d6e1b1` | 120 | 0.8% |
| `2026-08-21-7d36038` | 120 | **49.6%** |
| `2026-08-22-f5dec23` | 120 | **52.9%** |
| `2026-08-27-22b749c` | 60 | 27.1% |
| `2026-08-29-872ba65` | 60 | 0.0% |
| `2026-08-30-2e60949` | 120 | 0.0% |
| `2026-09-02-3b52608` | 60 | 3.4% |
| `2026-09-03-35378b9` | 60 | 3.4% |

Two things follow, and they cut in opposite directions — both are stated because neither is settled:

- ⚠️ **The covariate spikes exactly at the `FP-REGRESSION` window boundary** (`7d36038` 49.6%,
  `f5dec23` 52.9%) and is low on either side. A covariate that moves at the split is a candidate
  explanation for the step, and it has never been on the board.
- ⚠️ **But its direction is wrong for the simple story.** `f5dec23` is the *most gapped* run in the
  series and carries `4/60`, while the *least gapped* runs (`872ba65`, `2e60949`) carry `1/60`,
  `2/60`. If continuous playback manufactured FPs, this ordering would be reversed. The naive
  "it's a harness artefact" reading is **not** supported by the cadence data.

**For this arm the covariate is handled, not assumed away:** ROW 0e records today's cadence against
July's 12.7%, and ROW 2 tests the association across the historical series with a pre-registered
statistic.

---

## 3. Population, context, and how to run it

### 3.1 The population — exact

- Scenario file: **`qa/rr-study/scenarios/s5-noise-wide-n300.json`**, unmodified, at `main`@`10bbaad`.
- Part **0** only (the file has only part 0). Trials **0–299**. **N = 300 AWGN slots.**
- Appraisers: OpenWSFZ **and** WSJT-X, both on the same delivered audio, as in every S5 run.
- **Unit of rate: the slot.** An **event** is a slot carrying ≥ 1 decode. `events / slots`, always.
  🛑 **A decode row is not an event** (HK-021(i); `FP-PARITY` §2.1 — this exact confusion has
  already cost one reconciliation).

### 3.2 🔴 The context — this is the whole point of the arm; get it exactly right

**Standalone and cold.** Specifically, all four must hold:

1. Both applications **freshly started** for this run — OpenWSFZ restarted, WSJT-X restarted.
2. **S5 is the first and only scenario** the decoder sees in that process lifetime. No S1/S1b/S2/S3/S4
   before it, not even a partial battery (`2026-07-07-df4cc89` is classified `battery` on exactly
   this rule and would not be a valid replicate).
3. `truth.csv`'s only `scenario_id` value is `"S5"`.
4. The warm-up cycle (§3.4) is a **single** verification cycle, as in July — that is part of the
   July protocol and is not a battery.

⚠️ **Run S5 alone via `run_scenario.py`, not via `run_study.py --scenarios S5`.** The registry maps
`S5` → `s5-noise.json` (4 parts × 30 trials), **not** the N=300 file. `--scenarios` also bypasses
`_DEFAULT_BATTERY_PART_OVERRIDES` entirely, so that route would deliver the wrong population *and*
the wrong N.

### 3.3 🔴 Device — the default is wrong on this machine

Pass **`--device "Voicemeeter AUX Input"` explicitly.** `run_scenario.py`'s `--device` default is
still `"CABLE Input"`, which is unreliable here (standing capture-endpoint note; HK-020). Routing is
Voicemeeter AUX Input → B1.

### 3.4 Pre-flight, in order

1. Confirm the capture endpoint is **live**: `captureActive=true`. A stale endpoint GUID leaves the
   daemon "alive" and archiving nothing, with the friendly name unchanged (standing note).
2. **Clear / rotate both `ALL.TXT` files** before the run — WSJT-X's
   (`%LOCALAPPDATA%\WSJT-X - FT991A\ALL.TXT`) and OpenWSFZ's. An uncleared `ALL.TXT` contaminates
   `S5_matched.csv` with real callsigns (NFR-021) and inflates unmatched-decode rows. July disclosed
   this as a defect in its own §2; do not repeat it.
3. Warm-up: `harness/warmup.py --device "Voicemeeter AUX Input"`, and **verify the warm-up decode
   independently in both `ALL.TXT` files** — not on `warmup.py`'s own prompt alone. This is the July
   protocol, quoted from its §2: *"independently verified via both apps' `ALL.TXT` … not taken on
   `warmup.py`'s own prompt alone."*

### 3.5 Execution sketch (QA owns the detail; these are the bindings that must not change)

```
python harness/run_scenario.py scenarios/s5-noise-wide-n300.json \
    --device "Voicemeeter AUX Input" \
    --run-dir 2026-09-05-10bbaad-s5-standalone-n300
python harness/matcher.py --run-dir <that dir> --scenario S5
python harness/analyse.py --run-dir <that dir>
```

**Wall clock ≈ 75 min** of playback (300 × 15 s) plus warm-up and settle. If it is left unattended it
needs an HK-013 supervisor (kill + log + cooldown + restart, cap 5 retries); if it is attended, it
does not. ⚠️ HK-023: a `Monitor`-owned process dies at session end — use `nohup … & disown` with a
PID check, and a disposable `tail -f` for notification only.

⚠️ **`_MAX_BATCH_TRIALS = 20` must be left at 20.** 300 trials will flush as 15 batches of 5 min
each, well inside the ~18–19 min collapse point. Do not raise it "to save time".

---

## 4. Pre-registered rows

Every predicate below is mechanical: a stated threshold, a stated consequence, and rows that are
mutually exclusive (HK-021). **Ship the predicates as code** where a threshold is numeric
(HK-021(r)) so the run is re-runnable by anyone.

### ROW 0a — build pin. **Fires ⇒ STOP, do not run.**

All three must hold before playback starts:

| Check | Required value |
|---|---|
| SHA256 of `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c` |
| `git diff --stat -- src/ native/` | empty |
| `FT8_SHIM_VERSION` reported by the running daemon | `20260050` |

🛑 **Assert the SHA. Never infer the binary from the shim version** — `FT8_SHIM_VERSION` identifies
nothing on its own (two real collisions on record).

### ROW 0b — stimulus equivalence to July. **Fires ⇒ ROW 1 downgrades to counts-only.**

Render `s5-noise-wide-n300.json` part 0, trials 0–299, under **both**:

- **(i)** the current file (`main`@`10bbaad`), and
- **(ii)** the July-era file: `git show 1e07425:qa/rr-study/scenarios/s5-noise-wide-n300.json`

using the harness's **own** `compute_seed` / `_render_noise` / `_finalize_playback_samples`
(import them; **do not reimplement** — the `ACTION B` lesson, and the method `S5-BASELINE` ROW 0b
already validated). Render only; no device, no playback.

- **Does not fire:** 300/300 SHA256 pairs identical ⇒ July and today are the same stimulus, and
  ROW 1 is a clean two-arm contrast on identical noise.
- **FIRES:** any mismatch ⇒ the era contrast is stimulus-confounded ⇒ **ROW 1 may not be reported as
  a ratio or a p-value**, only as counts + Clopper–Pearson intervals, labelled *"stimulus not
  matched"*. Report the count and the trial indices that differ.

🔴 **Record all 300 full hashes** in the result JSON. "Byte-identical" must be mechanically diffed,
never asserted (standing rule).

### ROW 0c — capture liveness and log hygiene. **Fires ⇒ STOP.**

`captureActive=true` at arm time; both `ALL.TXT` files cleared/rotated before playback; the warm-up
decode present in **both** `ALL.TXT` files. Any one absent ⇒ stop and re-arm; do not "run it anyway
and note it".

### ROW 0d — context assertion. **Fires ⇒ the run is VOID as a standalone replicate.**

After the run: `truth.csv`'s set of `scenario_id` values is exactly `{"S5"}`, **and** the run's
`report.md` / session log shows no earlier scenario in the same process lifetime. Fires ⇒ the run
measured a battery context and does not fill ROW 0d's empty cell — re-run cold; do not reinterpret.

### ROW 0e — delivery cadence. **Descriptive; bounds ROW 1 per HK-021(p).**

Compute this run's gap fraction from its own `truth.csv` `cycle_utc`, by the §2.3 definition.

- **Report it against July's 12.7%**, always in the same sentence as ROW 1's ratio.
- 🔴 **The (p) bound, stated as a number:** if this run's gap fraction is **> 40%** — i.e. it lands
  in the `7d36038`/`f5dec23` regime rather than July's — the delivery path deviates from the
  comparator by more than any pair in the July-to-post-window record, and **ROW 1 is reported as
  descriptive counts only, not as an adjudicable ratio.**
- Below 40%, ROW 1 stands, with the cadence reported beside it.

### ROW 1 — **PRIMARY.** Is the current standalone rate elevated against July's, at the magnitude in dispute?

Population: today's `k/300` (OpenWSFZ, AWGN, standalone) vs July's `8/300` (`a3738fc`, standalone).
Statistic: **Fisher exact, one-sided** (upper tail — later-is-higher; the phenomenon is one-sided and
a sign-blind statistic on it is HK-021(l)).

> **ROW 1 FIRES iff `k ≥ 18`.**

That is not a chosen round number — it is the exact critical value, computed at drafting:

| `k` | rate | Fisher one-sided p vs 8/300 |
|---|---|---|
| 17 | 5.667% | 0.0502 |
| **18** | **6.000%** | **0.0346** |
| 19 | 6.333% | 0.0235 |

⇒ the gate fires at **≥ 2.25×** July's rate.

**Consequences, both branches stated (HK-021(t) — the cost sits on the complement, in the same row):**

- **FIRES ⇒** a regression at or above the disputed magnitude is confirmed *in the standalone,
  cold context, against the July shipped-config baseline*. The `S5-BASELINE` ROW 0d identifiability
  failure is broken **for this contrast only**. It remains silent on the battery series.
- **DOES NOT FIRE ⇒** report `k`, the rate, exact Clopper–Pearson 95% CI, and the ratio, labelled
  **"below the pre-registered magnitude bar; NOT adjudicated."**
  🛑 **A non-firing ROW 1 is NOT "no regression", and must never be reported as one.** See §5 — at
  the 1.35× that the July-vs-post-window comparison implies, this row has **2.5% power**. It is
  built to confirm a large effect, and is nearly blind to a small one. (HK-021(y)'s corollary: a
  finding that cuts against a claim in one direction does not become evidence for the other.)
- 🔴 **If ROW 0b fired:** counts + CP intervals only, no ratio, no p-value.

**Position, not width (HK-021(w)):** report explicitly whether today's CP interval and July's
`[1.158%, 5.187%]` **straddle** the 6.000% firing threshold, and which row each end would give.
Do not compare interval widths.

### ROW 2 — the delivery covariate across the historical series. **Pre-registered before computation.**

Population: the **12** admissible runs of `S5-BASELINE` ROW 0c, plus this run = **13**.
For each: AWGN `k`, AWGN `N`, gap fraction (§2.3).

Statistic: conditional permutation, exactly the `S5-BASELINE` ROW 2 design (condition on the total
event count, distribute events across runs with probability proportional to each run's AWGN `N`),
but scored by `sum(events_i × gap_fraction_i)` instead of chronological rank. Two-sided —
🔴 **two-sided deliberately: the §2.3 data suggest the association may run *either* way, and a
one-sided test here would be sign-blind in the direction the data actually point** (HK-021(n)).
N ≥ 2,000,000 MC draws, seeded, report the MC quantum (HK-021(o)).

- **FIRES iff `p < 0.05` AND no leave-one-run-out `p > 0.10`** (the same robustness condition
  `S5-BASELINE` ROW 2 used, so the two are comparable).
- **FIRES ⇒** delivery cadence is associated with the FP rate across the series ⇒ 🔴 **the entire
  historical S5 FP series carries an uncontrolled instrument covariate**, and every cross-run
  comparison on the board — including the HELD `3.25×` — needs re-examination before use. Escalate;
  do not adjudicate.
- **DOES NOT FIRE ⇒** no association detected at this power. **Not** "the harness is clean" — report
  it as "not detected at n=13 runs", with the power caveat.

### ROW 3 — context contrast at fixed build. **SECONDARY, descriptive, cannot change ROW 1.**

Today's standalone `k/300` vs `2026-09-03-35378b9`'s battery `2/60` — **the same `libft8.dll` blob**
(§2.1). Report counts + CP intervals only.

🛑 **No p-value, no ratio, and no adjudication.** At `n=60` on the battery side this contrast is
badly underpowered for the ~1.35× difference actually at issue (§5), and reporting a ratio would
invite exactly the over-reading this arm exists to prevent. It is recorded because it is free, it is
the only same-build context pair that will exist, and it is a genuine input to a future, properly
sized context arm.

---

## 5. Sizing, and the honest limit of this arm (HK-021(m) and (v))

**Resolution (m).** The readout is integer slots at N=300 ⇒ quantum **0.333 pp**. The gate sits at
`k = 18`; one slot either side moves p from 0.0502 to 0.0346 to 0.0235. The gate resolves its own
threshold comfortably.

**Power (v) — computed at drafting, against the Architect's own stated expectations, not asserted.**
`P(ROW 1 fires) = P(K ≥ 18)` under `Binom(300, p_true)`:

| True ratio vs July | True rate | P(ROW 1 fires) |
|---|---|---|
| 1.00× | 2.667% | 0.001 |
| **1.35×** (the July-vs-post-window figure from `FP-REGRESSION` Defect 3) | 3.600% | **0.025** |
| 1.50× | 4.000% | 0.059 |
| 2.00× | 5.333% | 0.338 |
| 2.50× | 6.667% | 0.711 |
| **3.25×** (the HELD figure) | 8.667% | **0.965** |
| 4.00× | 10.667% | 0.998 |
| 4.88× (RETIRED) | 13.013% | 1.000 |

🔴 **State this in the report, and state it before the result:** this arm is **well matched to the
question actually in dispute** — 96.5% power against the HELD `3.25×` — and is **nearly blind to a
small regression**, with 2.5% power at 1.35%. **A non-firing ROW 1 therefore carries almost no
evidence against a small effect.** That asymmetry is deliberate, it is the honest price of a
75-minute live run at N=300, and it is disclosed here rather than discovered afterwards.

🔴 **What this arm cannot do at any N reachable live:** resolve a 1.35× effect. That needs roughly
`n ≈ 2,700` per arm. It is not reachable through 15-second real-time playback; it **is** reachable
offline — the `AWGN-FP` seam decodes 4,000 slots in **3 m 48 s** (`Row0rCarryForwardTests`,
2026-09-04). §8 records that as the recommended follow-on, and it is **not** part of this arm.

---

## 6. What QA reports — and what QA must not conclude

**Report:** the mechanical outcome of ROW 0a–0e, ROW 1, ROW 2, ROW 3. For ROW 1: `k`, `N`, rate,
exact Clopper–Pearson 95% CI, the Fisher one-sided p, the ratio, the straddle statement (w), and the
cadence from ROW 0e in the same sentence as the ratio. WSJT-X's own `k/300` as the control, alongside
the standing `0/840`.

🛑 **QA draws no verdict on the regression, on `3.25×`, or on the re-scope.** Mechanical row outcomes
only, as in `S5-BASELINE` and `FP-COMPOSITION`. Adjudication is the Architect's; ratification is the
PO's (HK-015).

**Housekeeping, non-negotiable:**
- **NFR-021:** import `scan()` / `classify()` from `nfr021_pre_merge_scan.py` over the new files —
  **not** a directory walk, and the scanner **cannot scan an uncommitted directory** (false-green
  "CLEAN"). Scan `S5_matched.csv`, the raw `ALL.TXT` copies, **and the report prose**.
- **HK-016:** gather run artefacts into a dated, `README.md`'d `./artefacts/` directory before
  reporting done. `artefacts/` is blanket-gitignored, so real-callsign logs are safe there.
- **HK-009:** Windows console `stdout` is `cp1252` — write ASCII or `reconfigure(encoding="utf-8")`.
- **HK-014:** commit locally, **do not push**. `main` is 32 ahead of `origin/main` and carries
  `ac6150d`'s `src/`+`native/` diff, so the HK-029 direct-push exception is **N/A** — verify
  `git diff --stat -- src/ native/` and say so.
- 🔴 **HK-030:** every "STOP" in §4 means **pause and hand back**, not merely "don't push".

**HK-025 stands.** If any row here is non-mechanical, or a precondition cannot change a verdict,
QA may **refuse to run it** on HK-021(k) grounds without Architect agreement. Classify
(validity vs precision), evaluate both branches, and if the same row results either way it is
diagnostic ⇒ refuse.

---

## 7. Architect predictions — calibration only, nothing gates on them (§0.3: scoring SUSPENDED)

| Row | Prediction | Confidence |
|---|---|---|
| ROW 0a | does not fire | high |
| ROW 0b | does not fire — 300/300 identical | high |
| ROW 0d | does not fire | high |
| ROW 0e | gap fraction < 10% (batched path, capped) | moderate |
| **ROW 1** | **does not fire**; `k` lands in 6–14 (2.0%–4.7%) | **low** |
| ROW 2 | does not fire | low |

My honest central expectation is that ROW 1 **does not fire** and the true effect is nearer 1.35×
than 3.25× — which, per §5, is precisely the regime this arm cannot resolve. **I am pre-registering
an arm I expect to return "not adjudicated".** That is disclosed deliberately, because (v) requires
it and because it is the argument for the §8 follow-on, not against running this one: the standalone
cell is empty either way, and a 75-minute run that rules out a large regression in the cold context
is worth having before anyone designs against a magnitude.

---

## 8. Recommended follow-on — NOT part of this arm, PO's call

The `AWGN-FP` offline seam decodes **4,000 AWGN slots in 3 m 48 s** through the real managed + native
chain, and **ROW 0r proved it responds to a build change** (246/4,000 slots moved across a single
shim bump) — so HK-021(q) is already satisfied: the predicate demonstrably moves under the treatment.

Running that seam on a **built `a3738fc` worktree** and on current `main`, over one shared WAV
population, would give a **paired, n=4,000** build-to-build contrast with no device, no cadence, no
warm/cold and no era confound — powered for the 1.35× this arm cannot see.

**Two honest costs, both real:**
1. `Ft8LibInterop.ExpectedShimVersion` is a **compile-time constant**, so an old binary cannot be
   driven from current source — a second checkout **and build** is required (QA established this at
   ROW 0r §0). The July test harness does not exist at `a3738fc` and would need porting into that
   worktree. That is genuine engineering risk, not a formality.
2. The offline seam does **not** apply `NormalisePcm` ⇒ ≈**6.9 dB** quieter than production
   (`FP-PARITY` A2.2). That biases the **level** heavily; it biases a **build-to-build contrast**
   far less — but effect modification at a different operating point cannot be excluded, and must be
   disclosed rather than waved away.

⇒ **A separate pre-registration.** Not authorised here, and this spec does not depend on it.

---

## 9. What these rows cannot detect (HK-022's drafting question, per row)

- **ROW 0a:** a mismatch between the committed DLL and the one the *running daemon* actually loaded,
  if the daemon was started from a different tree. Mitigation: start it fresh from this tree (§3.2).
- **ROW 0b:** any difference introduced **after** `_finalize_playback_samples` — i.e. anywhere in the
  device chain. Not bounded here; the offline renderer's response is flat there (HK-026). This is the
  same residual `S5-BASELINE` ROW 0b carried, and it is unchanged.
- **ROW 0d:** a warm-up effect *within* the S5 run itself (early trials differing from late ones).
  Not tested. If wanted, it is a trial-index trend row in a future arm — **not** to be read off this
  run's data after the fact (HK-021(y)).
- **ROW 0e:** cadence is a proxy for the delivery path, not the path itself. Two runs with equal gap
  fractions may still differ in buffer construction (batched vs per-trial).
- **ROW 1:** anything below ~2.25× (§5). It also cannot separate managed from native change, by
  construction (§0.2).
- **ROW 2:** an association driven by a third variable that moves with both cadence and date. With
  n=13 runs this is not separable, and no row here claims otherwise.
- **ROW 3:** everything except a very large context effect; `n=60` on the battery side.

---

**Architect, 2026-09-05 13:11Z.** Committed locally, not pushed (HK-014). Nothing in this document
was measured by QA; no board figure moves on it. `4.88×` stays RETIRED, `3.25×` stays HELD.
