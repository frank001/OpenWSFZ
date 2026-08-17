# SPEC — `P-LIVE`: replicate N1/N2/N4/N5 on the live-decode population. The blocker was fictional.

**Author:** Architect
**UTC:** 2026-08-17 18:06Z (`date -u`, HK-017)
**Branch:** `qa/n1-ber-results` @ `f6323df`
**Supersedes:** `2026-08-17-1744-...-20m-repoint-spec.md` **§8 in its entirety** — including §8.3's "blocker", which does not exist. §1–§7 of that document (the N4 infeasibility retraction) stand unchanged.
**Authority:** Captain, this session — "spec it for QA."

---

## 1. What changed: there is no replay-product blocker

My §8.3 claimed the 20m corpora cannot feed the N-series because they carry no `candidate_diag.csv`, and offered QA three outcomes, two of which said **STOP** (HK-011 escalation, or a 32-hour VB-CABLE replay).

**Withdraw all of it.** The blocker was an artefact of insisting the population be rebuilt with the 07-25 recipe (which needs `candidate_diag.csv` to establish *candidate-present-and-failed*), rather than asking what the measurement needs.

The Captain's 2×2 capture design already contains everything:

- **WSJT-X's `ALL.TXT`** gives the cycle, the frequency, the DT, and the message text ⇒ position **and** ground-truth codeword.
- **Our `ALL.TXT`** for the same cycle says whether we decoded it ⇒ the miss.
- **The WAV** is on disk ⇒ re-extraction.

That is a complete row. No diagnostic build, no `FT8_ENABLE_RAW_LLR_CAPTURE`, no replay, no capture run, **HK-011 not engaged.**

**Measured this session**, built from live decodes only:

| Run | WSJT-X cycles | OpenWSFZ cycles | Failed rows | Clusters | rows w/ WAV |
|---|---|---|---|---|---|
| `20260803_live_run_1713` | 4,531 | 4,614 | 18,012 | **4,108** | 17,940 |
| `20260808_..._0016-8080` | 2,745 | 2,745 | 33,303 | **2,732** | 32,844 |
| `20260808_..._0016-8081` | 2,648 | 2,652 | 31,160 | **2,638** | 30,825 |
| `20260808_..._1154-8080-17m` | 1,856 | 1,856 | 14,276 | **1,849** | 14,276 |
| `20260809_..._0155-8080-80m` | 1,197 | 1,210 | 2,354 | **817** | 2,354 |

**~12,100 clusters** (07-31 excluded — see §6). **N5 ran on 67.**

---

## 2. `P-LIVE` — the population, defined mechanically

For a run directory `R` and a leg pair (`wsjt-x`, `owsfz`) **within the same run directory**:

1. Parse both `ALL.TXT` with `c2_phase2c_ber_measurement.parse_all_txt` (⚠️ `ALL.TXT` `[5]` is DT, `[6]` is frequency in **integer Hz** — inverting them inverts the result exactly).
2. Normalise every message with `normalize_hash_tokens` (unchanged convention).
3. A **row** is a WSJT-X decode whose normalised message does **not** appear in our `ALL.TXT` for the same `ts`.
4. Anchor = WSJT-X's reported `freq` (integer Hz) and `dt`.
5. True codeword via `Encoder.true_codeword()`; drop and count `no_true_codeword` (N5 dropped 36/441 ≈ 8%).
6. Audio = the WAV for that `ts` **from the leg that supplied the anchor** (§3 governs which).
7. **Cluster = `ts`.** Always. Report cluster counts, never bare row counts.

### 2.1 🔴 `P-LIVE` IS NOT `THE 135`/`THE 567` — do not compare them numerically

`THE 135`/`THE 567` required **our decoder to have a candidate at that position and fail**. `P-LIVE` requires only that **WSJT-X decoded it and we did not** — a **superset** that also contains cycles where we detected nothing at all.

For D-001 the superset is arguably the more relevant population (it is the actual miss population). But:

- 🛑 **Do NOT present any `P-LIVE` number as a replication of N1's or N5's point estimates.** Different population, different denominator.
- ✅ **`f_cross` is well-defined on either** — "does BER at this position fall below `B50` under the treatment" does not depend on how the row was selected. That is what makes the replication meaningful.
- Report `P-LIVE`'s own median `BER_V0`. Expect it **at or above** N5's 43.97%, since rows with no candidate at all should be worse. **A `P-LIVE` median materially BELOW 43.97% is a red flag** — report and stop rather than explain it away.

---

## 3. ROW 0 preconditions — mechanical, evaluated before any statistic

🔴 **HK-025 refusal available on every row.** Classify each, evaluate both branches, refuse if a row is diagnostic-only.

### ROW 0a — audio-path correspondence (VALIDITY; the load-bearing one)

The anchor comes from WSJT-X, the miss-judgement from us. **If the two legs sat on different receivers, WSJT-X's frequency does not describe our audio** — and every N-series statistic is *about* anchor accuracy, so a cross-chain offset corrupts the whole measurement.

⚠️ **`contents.md` says "Audio device: Microphone (2- USB Audio CODEC)" for BOTH `0016-8080` and `0016-8081`. That field is recorded at GATHERING time, not per-instance during the run. It is not evidence. Do not use it.**

**Test (the method already proven on this corpus):** cross-correlate `owsfz/wav/<ts>` against `wsjt-x/wav/<ts>` for **≥8 cycles spread across the run**, report **median |r| and lag**.

- **FIRES** if median |r| < 0.90 **or** median |lag| > 50 ms ⇒ that run's legs are **different chains**.
- **Consequence if it fires:** that run is **restricted to same-leg-only analysis** — anchor, miss-judgement and audio all from one leg — or dropped. **It is not fatal to the round**; `20260803_live_run_1713` is documented single-path (median |r| = 0.987, lags ≤ 34 ms) and carries 4,108 clusters on its own.
- 🔴 **Run this per corpus. Do NOT inherit 08-03's verdict** — the inventory says so explicitly.

### ROW 0b — instrument identity (VALIDITY)

Before any new number, re-run N5's harness **unchanged** against the 07-25 default and confirm it still reproduces **67 clusters / 405 rows / `THE 135` median `BER_V0` = 43.97% (±0.5pp)**.

- **FIRES** on any mismatch ⇒ the harness has drifted; **STOP**, nothing downstream is trustworthy.

### ROW 0c — power (PRECISION, classified honestly)

- **FIRES** if the assembled population carries **< 500 rows or < 200 clusters** after `no_true_codeword` drops.
- **Consequence:** report and stop. At that point the corpus did not deliver what §1 measured and the discrepancy is itself the finding.

### ROW 0d — sign tests (VALIDITY)

Re-run **both** (`n5_stats_sign_test.py`, `n4_sign_unit_test.py`) **fresh. Do not inherit N4's or N5's pass.**

### ROW 0e — the treatment can move (VALIDITY)

Median hard-decision disagreement `V0` vs `V3_cum` **≥ 5 bits / 174**. **FIRES** below ⇒ the contrast cannot move and no null is interpretable. (N5 measured 21.0.)

---

## 4. Order of work — cheapest and most decisive first

🛑 **Stop after each stage and report.** Do not run the whole ladder unattended.

### Stage 1 — N5 on `P-LIVE` (~20 minutes of compute)

N5 measured 405 rows in **7.6 s** (≈0.11 s/cluster; no frequency sweep). At ~12,000 clusters this is **minutes**.

- Primary: **`f_cross`**, cluster bootstrap over `ts`, `n_draws=2000`, reusing `n5_stats.f_cross_row` **verbatim**.
- Mandatory alongside, per Amendment A1.2: **`f_break`** and **`f_net`**, own CIs, 🛑 **never pooled**. `f_break`'s denominator will now be large — it was 2 rows in N5 and DESCRIPTIVE-ONLY; at this scale it becomes a real quantity, and **`f_net` genuinely gates for the first time.**
- 🔴 **Report the rule-of-three bound explicitly alongside the bootstrap CI.** If `n_cross = 0` the bootstrap CI is **degenerate by construction** (every resample returns zero — this is the defect in my own N5 gate, §6 of the retraction). The honest bound is `1 − 0.05^(1/n_clusters)`.

**What it settles:** at 12,000 clusters a zero gives an upper bound of **~0.025%**, against N5's 4.37%. **Limb 2 closes or opens properly, for the first time.**

### Stage 2 — N1 on `P-LIVE`

`d_ber` and `f_cross` under **refinement** (limb 1). N1's headline was `d_ber` = −4.02pp on `THE 135`, p=0.000 — harm on the strong-candidate stratum. 🛑 **This does NOT reopen R2** (§7); it tests whether the harm replicates.

### Stage 3 — N2 on `P-LIVE`

The `V0 < V1 < V2 < V3` ladder (2.87% → 8.05%) on the **control** population — messages we DID decode and WSJT-X also decoded. Same runs, opposite selection.

### Stage 4 — N4 on `P-LIVE` (~13 hours, overnight)

Slice B was 630 s / 40 clusters = **15.75 s/cluster** (71-point grid). At ~3,000 clusters ≈ 13 h. **Cap at 2,000 clusters unless Stage 1–3 justify more; drop whole CLUSTERS if a cap binds, NEVER grid points.**

🔴 **HONEST EXPECTATION, PER HK-021(m) — DO NOT OVERSELL THIS ONE.** The straddle resolves only if the CI half-width falls below `|H − cut|` = 0.0065 Hz. Scaling N4's 0.1244 Hz by `√(40/n)`:

| clusters | expected CI half-width | resolves? |
|---|---|---|
| 4,108 (08-03 alone) | ~0.0123 Hz | **no** — still straddles |
| 12,100 (pooled) | ~0.0071 Hz | **marginal** — likely still straddles |
| 14,838 | 0.0065 Hz | the boundary, by construction |

⚠️ **And pooling bands may INFLATE σ, pushing the requirement up.** So N4 probably **does not** resolve the straddle even at full corpus. Going from 19.3× too wide to ~1.1× too wide is still a transformation of what we know, and the point estimate's stability across bands is informative in its own right — **but QA should not expect a verdict, and I should not have implied one was cheap.**

---

## 5. Confirmatory vs descriptive — state this in the report

- ✅ **CONFIRMATORY**: `f_cross` against the **existing** 5% cut, and `H_3^cum` against the **1.5625 Hz lattice half-cell**. Both thresholds predate this data — 1.5625 is a hardware constant (`K_FREQ_OSR=2`, 3.125 Hz step), not a data-derived number.
- ⚠️ **DESCRIPTIVE, with CIs, gating nothing**: everything else, including all per-band and per-leg breakdowns.
- 🛑 **I know `H_3^cum` ≈ 1.569 and `f_cross` = 0/403. I therefore may not write ANY new threshold.** Anything beyond the two cuts above earns a fresh pre-registration.
- 🔴 **Report SLOPE + CI + p on every gate statistic, never a bare `r`.**

### 5.1 Stratify — do not only pool

Report **per run and per band**, alongside pooled. 08-03 is 18.96 h (day into night, shifting SNR); 07-25 was 20 minutes. If a statistic varies with band or SNR, the pooled CI is tight around a **mixture**. Stratified reporting is also the first chance we have had to ask whether the frequency requirement depends on SNR at all.

### 5.2 🛑 Leg handling

Count clusters **within-leg**. `0016-8080` and `0016-8081` observe the **same cycles**: measured median per-cycle decode-set Jaccard **1.000 / 0.909 / 1.000**, so the second leg is worth ~2–10% as a cluster multiplier, **not 2×**. Pooling them as independent clusters is the HK-021(i) error that already cost N1/N2/N3 a ≈3.8× CI understatement. **Report each leg separately; do not sum their cluster counts.**

---

## 6. Corpus notes

- **Primary: `20260803_live_run_1713`** — documented single verified audio path, 18.96 h contiguous, 20m, drift screen PASS. 4,108 clusters. ROW 0a should pass trivially; **run it anyway.**
- **Extension: `0016-8080`/`-8081` (20m), `1154-*-17m`, `0155-*-80m`** — subject to ROW 0a per run.
- 🔴 **EXCLUDE `20260731_live_run_2004-*` from the primary analysis.** It yields 290,554 rows over only 3,618 WAV-backed clusters (~80 rows/cluster against ~12 everywhere else) and its `wsjt-x` leg is **the one genuinely HARDLINKED pair** (shared inode `281474977010995`). Something is structurally different; **diagnose before use, do not include and hope.**
- ⚠️ `20260729_live_run_1831-*` is flagged **pre-drift-fix** in the inventory. Excluded.

---

## 7. Prohibitions — unchanged, and none of this touches them

- 🛑 **R2 STAYS EXCLUDED.** N1 killed limb 1 on outcome evidence and refinement measurably harmed the strong-candidate stratum. Stage 2 tests replication of that harm; it is **not** a rehabilitation route. R0/R1/R1b ~1.1 ms / 0.5 Hz prohibition **UNCHANGED**.
- 🛑 No `src/`. No Developer session. No DLL rebuild. No capture run. **HK-011 NOT engaged.** Pin the DLL SHA256 (`6890d84c…`/shim 20260042) and **re-hash the on-disk file before arming** — do not infer it from a label.
- 🛑 No per-row frequency search. Common `df` only — that is what keeps R2 excluded. Rectangular window only.
- 🛑 The §3 OSR margin table remains post-hoc and authorises nothing.
- 🔴 **NFR-021 — SHARPER HERE THAN IN ANY PRIOR ROUND.** `P-LIVE` is **built from message text**, and these `wsjt-x/ALL.TXT` carry **real callsigns** (4.9 MB + 2.5 MB). Emit **`{ts, freq, dt, ber_*, ...}` only — never `message`**. Grep **every** emitted file individually before committing; a report's own cleanliness does not extend to its CSVs (203,920 contaminated rows in one `S1_matched.csv`, 2026-08-15).
- **HK-009** ASCII console. **HK-016** gather artefacts. **HK-013/HK-023** if anything runs unattended, use a validated supervisor and `nohup … & disown`, not a `Monitor`-owned process.
- 🛑 **Do not edit `c2_phase2c_ber_measurement.py:56` in place** — N1–N5's committed results read it. New module; parameterise; ROW 0b asserts the old default still reproduces.

---

## 8. Predictions — 🛑 nothing gates on these

- `f_cross` on `P-LIVE`: **0.000–0.005** (range class). P(`f_cross` upper bound lands below 1%) ≈ 80%.
- `f_break` becomes non-trivial with a real denominator: **P ≈ 70%** it is > 0 with a CI clearing zero — N2 measured V3 monotonically worse than V0, and this is the first population large enough to see it.
- `P-LIVE` median `BER_V0` ≥ 43.97%: **P ≈ 75%**.
- ROW 0a fires on **at least one** split run: **P ≈ 50%**.
- N4 straddle resolves at full corpus: **P ≈ 20%** (see §4 Stage 4).

Calibration, per standing rule: **categorical 6/11 · ranges 9/16 · DIRECTIONAL 2.5/5.5 · mechanical 3/4.** Categorical is below 55%; my intervals land and my row calls miss. **This spec exists because three successive categorical judgements of mine about the corpus were wrong, and the Captain overrode each one.**

---

## 9. NEXT

🔴 **QA runs ROW 0a/0b first, reports, then Stage 1.** Stage 1 alone is expected to settle limb 2 — the most decision-relevant number left in D-001.

🔴 **N5 remains UNRULED** and should stay so until Stage 1 reports. Its ROW 2 fired on a degenerate CI whose honest bound is 4.37%; Stage 1 replaces that with a real one.

A2/A3 still open, must not become a round; A1 done.
