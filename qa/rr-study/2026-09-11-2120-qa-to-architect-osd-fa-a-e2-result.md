# `OSD-FA-A` E2 — result: **`E2-B1`, decisive** — `osd_nhard_max` 60→40 costs **zero** genuine decodes under oracle truth

QA, 2026-09-11 21:20Z (`date -u`, HK-017). Per Amendment 1 §5.2, continuing after the Architect's
`E1-1` acceptance ruling (`2026-09-11-2048-...-e1-acceptance.md`, `arch/osd-fa-a` `5507063`).

**Headline: `E2-B1` fires, decisively.** Of `1,030` decodes the `60→40` tightening removed from
Part A's identical S8HN population, **zero** were genuine.

---

## 1. HK-020 — critical config

| config | value | source |
|---|---|---|
| Population/PCM | identical to Part A — 1,000 S8HN trials, same seeds (`SR.trial_seed(t,0)`) | Amendment 1 §5.2 |
| Legs | control `nhard=60`, treatment `nhard=40`, `k=10`, `corr=0.10` fixed both legs | Amendment 1 §5.2 |
| Pairing key | `(payload, freq ±4.0Hz)`, reused from `part_b.py` (HK-018) | base §6.1, Amendment 1 §5.2 |
| Matching | payload not text (`true_codeword()` bit comparison) | base §5.1 |
| Offset | none — full-decoder leg, extracts nothing | Part D3 acceptance ruling §4 |
| Power floor | `n_removed ≥ 100` | base §6.2, reused for E2 |

**Disclosed scheme (per the E1 acceptance ruling §3, stated up front this time):**
`ft8_set_decode_params` is called **twice per trial** (60, decode; then 40, decode), one process,
one thread, between complete synchronous `decode_all()` calls — never while a decode is in flight.
Ruled harmless for E1 on identical grounds (no thread-pool race is possible; production hot-applies
the same way, `Program.cs:867`); the same reasoning applies here. **Per-cycle arrays are persisted**
(`per_cycle_killed`, `per_cycle_removed`) so determinism is diffed, not inferred from scalars.

## 2. Result

```
total_60 (decodes at nhard=60) = 12,143
total_40 (decodes at nhard=40) = 11,113
present at 40, absent at 60 (confound check) = 0
n_caught (false decodes removed) = 1,030
n_killed (genuine decodes removed) = 0
n_removed = 1,030  (>= 100, power floor cleared)
Q40 = 0 / 1,030 = 0.0%
```

**Never citing a bootstrap `[0%, 0%]`** (per the Part B/E1 acceptance rulings' standing
correction — a zero-width resample interval is not a confidence interval). Citing instead,
independently computed via `scipy.stats.beta`:

- Decode-level: Clopper–Pearson 95% upper bound on `0/1,030` = **`0.358%`**.
- Cluster-level: `640` of `1,000` cycles carried ≥1 removal (max `6` in one cycle); CP95 upper
  bound on `0/640` = **`0.575%`**.

**Row: `CI_hi = 0.575% < 5% ⇒ E2-B1`**, by a wide margin (roughly 9× tighter than the bar) even at
the more conservative cluster-level bound.

**Consistency check (disclosed, not a gate, per the Architect's E1/E2 note):** the 60-leg's
`total_60 = 12,143` matches Part A's own independently-computed total **exactly**.

**Also reported, base §6.1:**

- Genuine decodes lost per 1,000 cycles: **`0`**.
- Decodes present at 40, absent at 60 (expected ≈0, else a disclosed confound): **`0`** — no
  confound.

**Determinism:** two independent processes. Not just matching scalars this time — the full
`per_cycle_killed`/`per_cycle_removed` arrays (1,000 entries each) are **element-wise identical**
between runs.

## 3. What this licenses, and what it doesn't

Per Amendment 1 §5.4: `E2-B1` is the second of three conditions (`E1-1 ∧ E2-B1 ∧ E3-N`) needed
before the Architect is cleared to **draft** a pre-registration for the default change — still not
a licence to build or change anything. `E2-B2`/`E3-H` (checked first, strict order) would have
overridden regardless of `E1`/this result; neither has fired here.

**Citation, matching the established convention:** *"`E2-B1`: under oracle truth, on the identical
`S8HN` PCM `E1` used, `osd_nhard_max` 60→40 removes `1,030` decodes and **zero** are genuine
(`CP95` upper `0.36%` decode-level, `0.58%` cluster-level)."* **This is a synthetic, oracle-labelled
result — it says nothing about live audio on its own.** `E3` is the only leg that can speak to live
harm, and per the `FP-FLOOR-LIVE-2` acceptance ruling's own standing principle, it can only ever
detect harm, never establish safety.

## 4. NFR-021

Not engaged — Q-prefix synthetic scene only (same population as Part A/B).
