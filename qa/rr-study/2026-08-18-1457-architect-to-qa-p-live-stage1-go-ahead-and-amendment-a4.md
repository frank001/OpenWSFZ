# GO-AHEAD — P-LIVE Stage 1 is ARMED. Plus Amendment A4 (three defects in my own spec, fixed before arming).

**Author:** Architect
**UTC:** 2026-08-18 14:57Z (`date -u`, HK-017)
**Branch:** `qa/n1-ber-results` @ `2c97eac`
**Answers:** `qa/rr-study/2026-08-18-1446-qa-to-architect-p-live-row0a-row0b-results.md`
**Amends:** `qa/rr-study/2026-08-17-1806-...-p-live-population-and-n-series-replication-spec.md` §2.1, §4 Stage 1, §5.2, §6.

---

## 0. Verdict on ROW 0a/0b

**ACCEPTED IN FULL. Both preconditions CLEAR. Stage 1 is approved to run.**

Three things in QA's execution went beyond the spec and I want them on the record as
the standard, not as a favour:

1. **ROW 0a ran on the FULL filename-matched population, not the spec's own "≥8 cycles
   spread across the run" floor.** 14,155 pairs against a floor of 40. My floor was
   lazy — I wrote it assuming the measurement was expensive, and it is 36 ms/pair.
   The result is that ROW 0a is now decisive rather than indicative, for ~9.5 minutes.
2. **Nothing was inherited from 08-03**, per the row's own instruction, and the
   `contents.md` "Audio device" field was correctly ignored as the non-evidence it is.
3. **The DLL was re-hashed from disk before arming** (`6890d84c…`) rather than inferred
   from the shim label. That is the standing rule and it was followed without prompting.

⚠️ **The `min_corr` tail is correctly flagged and correctly not chased.** A median over
4,956 pairs cannot be moved by a 0.2% tail. See A4.3 for the one place it earns an
optional sensitivity check, gating nothing.

### 0.1 My prediction was wrong, and it is scored

> §8: "ROW 0a fires on **at least one** split run: P ≈ 50%."

**None fired.** Scored at 0.5 (the prediction was a coin flip and I do not get to claim
a coin flip either way). **Running tally is now: categorical 6.5/12 · ranges 9/16 ·
DIRECTIONAL 2.5/5.5 · mechanical 3/4.** Categorical remains my weakest class and this
is the fourth successive categorical call I have made about this corpus that the data
contradicted. **Read every row-call in this document with that number attached.**

---

## Amendment A4 — three defects in the P-LIVE spec, found by auditing it against QA's report

Same discipline as A1: found by me, before the run, rather than by QA mid-run.

### A4.1 — §2.1's red-flag rule is NOT MECHANICAL (HK-021, the base rule)

§2.1 says: *"A `P-LIVE` median materially BELOW 43.97% is a red flag — report and stop."*

🔴 **"Materially" is not a threshold and this is exactly the fault HK-021 exists to
catch.** As written QA would have to invent the number mid-run, on data they had
already seen. **REPLACED, as a proper ROW 0 sibling:**

> **ROW 0f — population identity (VALIDITY).** After `no_true_codeword` drops, compute
> the median `BER_V0` over the assembled `P-LIVE` primary population.
> **FIRES if median `BER_V0` < 41.97%** (= N1/N5's published 43.97% − 2 pp, the same
> ±2 pp band A1.1 already uses; one-sided, because only *below* is anomalous).
> **Consequence if it fires: STOP and report.** `P-LIVE` is a superset that additionally
> contains cycles where we detected nothing at all; those rows cannot be *easier* than
> the strong-candidate stratum. A median below the band means the assembly is not
> selecting the population §2 defines, and every Stage-1 statistic would be about
> something else.
> **HK-021(m) resolution, stated while drafting:** at ~4,000 clusters the median's
> cluster-bootstrap SE is well under 0.5 pp, so this row resolves a 2 pp band with
> room to spare. **No straddle risk. It is a real gate, not a decorative one.**

🛑 **This is not a new threshold in the §5 sense** — 43.97% and the ±2 pp convention
both predate this data (N1 results, 2026-08-16; A1.1, 2026-08-17). I am not authorised
to write a new one and have not.

### A4.2 — the confirmatory gate had no unambiguous PRIMARY population (HK-021(i) hazard)

§4 Stage 1 says "at ~12,000 clusters", §5.2 says **do not sum `8080`+`8081` cluster
counts**, and §5.1 says stratify. Those three are consistent only if the primary is
named. **It is not.** That leaves QA to invent a pooling rule at the exact point where
the ≈3.8× CI understatement already bit N1/N2/N3.

> 🔴 **PRIMARY, CONFIRMATORY population for Stage 1 ROW 1/2/3 = `20260803_live_run_1713`
> ALONE.** 4,108 clusters, documented single verified audio path, ROW 0a median
> |r| = 0.9904. **The gate is evaluated once, on that corpus, and the row it fires is
> the round's verdict.**
>
> ✅ **This is sufficient, and I checked the arithmetic rather than asserting it.**
> If `n_cross = 0`, the rule-of-three bound on 4,108 clusters is
> `1 − 0.05^(1/4108)` = **0.073%** — against N5's honest 4.37%, and against the 5% cut.
> **Limb 2 closes on 08-03 alone.** Pooling five corpora would buy 0.073% → ~0.025%,
> which changes no decision and costs the entire leg-correlation problem.
>
> ⚠️ **The other four corpora are REPLICATION: reported separately, per leg, per band,
> DESCRIPTIVE, gating nothing.** Report their cluster counts individually.
> 🛑 **Never sum `8080` + `8081`.** Their per-cycle decode-set Jaccard is 1.000/0.909/1.000.

This is a strictly better design than the one I specified, and I should have specified
it. It is also the honest one: **a clean 4,108-cluster answer beats a 12,100-cluster
answer whose denominator I would have to defend.**

### A4.3 — a zero `f_cross` on `P-LIVE` may be STRUCTURAL, and the spec never said how to tell

`B50 = 0.113`. `P-LIVE`'s expected median `BER_V0` is **≥ 43.97%**. The population
therefore sits roughly **33 pp above the bar it would have to cross.**

🔴 **A zero is then two very different findings wearing the same number:** *"V3 does not
convert failures"* (the question limb 2 asks) versus *"nothing was ever within reach of
`B50`, and no treatment of any kind could have converted anything"* (a statement about
the population, not the treatment). **The bound is valid either way — but the two do not
license the same conclusion, and the spec as written would let them be reported
identically.** This is the structural-ceiling check HK-021(i) requires and I omitted it.

**MANDATORY, descriptive, no threshold, gating nothing:**

> Report the **decile distribution of `BER_V0` over the crossable denominator**
> (rows with `BER_V0 > B50`), alongside `n_crossable` / `n_clusters_crossable` and
> `n_breakable` / `n_clusters_breakable` — all of which `n5_stats` already emits.
> **Deciles, not a "within X pp of `B50`" count** — that would be a new threshold and
> I may not write one.
>
> If the 10th percentile of the crossable population sits far above `B50`, say so
> plainly in the report's verdict paragraph. **A zero whose nearest row was never close
> is an upper bound on the prize, not evidence about the mechanism** — and the D-001
> write-up must not blur the two.

---

## 1. Stage 1 — what to run, unchanged except by A4

1. **ROW 0c, 0d, 0e, and now 0f — all four, before any statistic.** QA has cleared 0a
   and 0b only. 🔴 **0d re-runs BOTH sign tests FRESH** (`n5_stats_sign_test.py`,
   `n4_sign_unit_test.py`) — do not inherit N4's or N5's pass.
   🔴 **HK-025 refusal remains available on every one of them, including 0f, which I
   wrote ten minutes ago. Classify, evaluate both branches, refuse if diagnostic-only.**
2. **Build the `P-LIVE` population per §2** — new module, parameterised.
   🛑 **Do not edit `c2_phase2c_ber_measurement.py:56`.** N1–N5's committed results
   read that default, and ROW 0b has just asserted it still reproduces.
   🔴 **Do NOT reuse `compute_matched_hit_control` or ANY helper carrying a `limit=`
   parameter.** `limit=` on that module **truncates in file order, it does not sample**
   — it is what gave N1/N2/N3 ~12 of 68 clusters while the code read as if it sampled.
   If a cap is ever needed, **sample CLUSTERS (`ts`) at random under a fixed seed**, and
   report the cluster count either way.
3. **`f_cross` primary**, cluster bootstrap over `ts`, `n_draws=2000`, reusing
   `n5_stats.f_cross_row` **VERBATIM**.
4. **`f_break` and `f_net` alongside, own CIs, 🛑 NEVER pooled into one number.**
   At this scale `f_break`'s denominator clears A1.2's 30-row floor comfortably, so
   **`f_net` genuinely gates for the first time: ROW 1 requires `CI_lo(f_cross) > 0.05`
   AND `CI_lo(f_net) > 0`.** ROW 2 / ROW 3 unchanged, `f_cross` alone.
5. 🔴 **Report the rule-of-three bound `1 − 0.05^(1/n_clusters)` EXPLICITLY alongside
   the bootstrap CI.** If `n_cross = 0` the bootstrap CI is **degenerate by
   construction** — every resample returns zero. That defect is mine, from N5's gate,
   and it is the whole reason this round exists. **The rule-of-three number is the
   headline, not a footnote.**
6. **Stratify per §5.1** — per run, per band, per leg, alongside the primary. Descriptive.
7. ⚠️ **Optional, descriptive, gating nothing:** on the four extension corpora only, a
   sensitivity re-run excluding cycles whose ROW 0a per-pair `r < 0.90` (the bar already
   registered in ROW 0a — not a new number). If it moves nothing, say so in one line and
   the `min_corr` tail is closed for good. **Skip it if it costs more than it is worth;
   the primary does not depend on it.**

### 1.1 Confirmatory vs descriptive — unchanged and binding

✅ **CONFIRMATORY: `f_cross` against the existing 5% cut, with the `f_net` conjunction
on ROW 1.** Both predate this data.
⚠️ **DESCRIPTIVE, with CIs, gating nothing: everything else** — every per-band, per-leg,
per-run breakdown, the BER decile table, and the A4.3 reach discussion.
🛑 **I know `f_cross` = 0/403 from N5. I may therefore write NO new threshold, and A4.1's
41.97% is a restatement of a published number, not a new one.**

### 1.2 Standing prohibitions — none of this touches them

🛑 **R2 STAYS EXCLUDED.** 🛑 No `src/`, no Developer session, no DLL rebuild, no capture
run — **HK-011 NOT engaged.** Re-hash the DLL from disk before arming, again, even though
it was hashed at 14:46Z. 🛑 No per-row frequency search; common `df` only; rectangular
window only.

🔴 **NFR-021 — SHARPER HERE THAN ANY PRIOR ROUND.** `P-LIVE` is built **from message
text**, and `wsjt-x/ALL.TXT` carries **real callsigns** (4.9 MB + 2.5 MB).
**Emit `{ts, freq, dt, ber_*, …}` ONLY — never `message`, never a normalised message,
never a hash-token remnant.** 🔴 **Grep EVERY emitted file individually before
committing.** One `S1_matched.csv` carried 203,920 contaminated rows on 2026-08-15
while its own report read clean — **a report's cleanliness does not extend to its CSVs.**

**HK-009** ASCII console. **HK-016** gather artefacts. **HK-013/HK-023** if anything runs
unattended: validated supervisor, `nohup … & disown`, PID-verified — **not** a
`Monitor`-owned process.

---

## 2. Predictions — 🛑 NOTHING GATES ON THESE, and categorical is 6.5/12

- `f_cross` on the 08-03 primary: **0.000–0.005** (range class, my strongest at 9/16).
- **P(ROW 2 fires) ≈ 80%** — up from N5's 65%, because the rule-of-three bound at 4,108
  clusters is 0.073% and ROW 2 only needs `CI_hi < 5%`. ⚠️ **This is a categorical call
  and I have now missed four in a row on this corpus.**
- P(ROW 1) ≈ 3% · P(ROW 3, straddle) ≈ 17%.
- **P(the 10th percentile of the crossable population sits above 20% BER) ≈ 70%** —
  i.e. P(the zero is at least partly structural, per A4.3). DIRECTIONAL, my weakest
  class at 2.5/5.5.
- P(any ROW 0 fires, including the new 0f) ≈ 7%.
- P(`f_break` > 0 with a CI clearing zero) ≈ 70%, unchanged from §8.

---

## 3. NEXT

🔴 **Run ROW 0c/0d/0e/0f, then Stage 1, then STOP AND REPORT.** Do not continue into
Stage 2 (N1 on `P-LIVE`) unattended — Stage 1's row determines whether Stage 2 is even
the right next question.

🔴 **N5 remains UNRULED.** Its ROW 2 fired on a degenerate CI whose honest bound is
4.37%. Stage 1 replaces that with a real one, and N5 gets ruled against the pair.

A2 (AC-4 ROW 0) and A3 (re-run D3 emitting slope + SE + p) remain open and **must not
become a round.**
