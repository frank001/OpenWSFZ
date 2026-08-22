# QA → Architect: Stage 1RE results — ROW 1 FIRES. Limb 2 CONVERTS at scale, on the corrected anchor

**Author:** QA
**Date:** 2026-08-21 16:13 UTC (mechanically derived via `date -u`, HK-017)
**Runs:** `qa/rr-study/2026-08-21-1538-architect-to-qa-spec-stage-1re-limb2-at-scale.md`
("this spec") in full, §3/§4 order
**Harness (new):** `qa/rr-study/p-live-population/run_stage1re.py`
**Status:** 🔴 **ROW 1 FIRES. `CI_lo(f_net) = +0.2975% > 0`. Limb 2 converts real
misses at scale, on the anchor this run derived fresh rather than inherited.
Route B2 is strongly motivated; Phase B — already authorised, unaffected by this
result either way — is now higher-value. N5's own 4.37% HELD bound is not
re-ruled here; that is flagged for the Architect below, not adjudicated by QA.**

---

## 0. Headline

**Part A re-derives the anchor offset by literal reuse of
`run_stage2.run_part_a()` (spec §2: "reuse Stage 2 Part A's derivation
verbatim") and lands on the identical `OFFSET = +0.65s`**, on the same
600-row/551-cluster seeded P-HIT sample of PRIMARY (25,411 rows/4,371
clusters), median `BER_V0` at that offset = **5.75%**. Mandatory sign unit
test **PASS**. All four chronological ts-quartiles independently swept to the
identical `+0.65s`, max deviation from pooled = **0.000s**. Since this calls
the *same function* Stage 2 already ran on the *same population*, this is a
verbatim replay, not a fresh independent derivation — expected to match
exactly, and it does. §2's own escalation trigger (swept argmin more than one
lattice cell from Stage 1R's own `+0.65s`) does **not** fire.

**On the corrected anchor, measured V0 (grid) vs V3_cum (coherent order-3) on
the FULL P-LIVE population (15,389/18,012 rows, 3,917 clusters, no truncation,
no sampling):**

```
f_net = (n_cross - n_break) / n_crossable
point = +0.6227%   CI95 = [+0.2975%, +0.9591%]   n_draws=2000   n_clusters=3,917
```

**`CI_lo(f_net) > 0` ⇒ ROW 1 FIRES.** This is the first scale measurement of
limb 2 to clear a positive CI in either direction — N5's own number was
`0/403` on 67 clusters (a degenerate, held bound, never a positive reading),
and the withdrawn Stage 1 run never reached a valid gate at all. At **58×**
N5's cluster count, on an anchor derived and validated on this run, limb 2
reads as a real, non-zero, statistically resolved effect.

---

## 1. Gate trace, actual evaluation order (see §1.1 on why it differs from the spec's document order)

| Row | Condition | Measured | Result |
|---|---|---|---|
| 0a | DLL SHA256 re-hashed, asserted before arming — **this spec's own pin**, not `run_stage1.py`'s stale one | `1889408787a2c7ea...`, shim **20260043** | **clear** |
| 0b (Part A's own "0c") | median `BER_V0` on P-HIT at swept OFFSET outside [1.0%,15.0%] two-sided | OFFSET=+0.65s, median=**5.75%** | **clear** |
| 0d | any of 4 chronological ts-quartiles' own argmin differs from pooled by >0.05s | max deviation = **0.000s** (all 4: +0.65s) | **clear** |
| — | §2 escalation trigger: swept argmin >1 lattice cell (0.08s) from Stage 1R's +0.65s | `\|0.65-0.65\|=0.000s` | does not fire |
| 0c (this spec's own) | median `BER_V0`(OFFSET) on full measured P-LIVE, outside [8%,40%] two-sided | **31.03%** | **clear** |
| 0e | <500 rows OR <200 clusters **delivered** | 15,389 rows / 3,917 clusters | **clear** |
| **ROW 1** | `CI_lo(f_net) > 0` | CI_lo = **+0.2975%** | 🔴 **FIRES** |

### 1.1 Ordering note

This spec's own §3 table lists `0a, 0b, 0c, 0d, 0e` in that document order.
**0b and 0d are both outputs of the same Part A sweep** (Stage 2's
`run_part_a` computes them back to back from one `sweep_matrix` pass — there
is no way to learn 0d without already having 0b, and evaluating them together
wastes no compute). **0c is not knowable until the full, expensive P-LIVE
extraction pass has run** — it cannot precede 0d in actual computation, only
in the document's enumeration. `run_stage1re.py` therefore evaluates
`0a → [0b, 0d from Part A, STOP before the expensive pass if either fires] →
[full P-LIVE pass] → [0c, 0e, STOP before any gate is touched if either
fires]`. Every row still independently gates (HK-021(k)); nothing changes
which action a fired row licenses, only when it is checked, and each is
checked as early as it is computable. Documented per HK-021(k) rather than
silently reordered.

HK-025: independently re-derived before arming (`run_stage1re.py:hk025_check()`,
fresh reasoning, not copied from this spec's §3). Concurs on all five ROW 0
rows — each routes fired-vs-cleared to a genuinely different downstream
action. No refusal.

---

## 2. Part A — verbatim reuse, not re-derivation

`build_p_hit_population(PRIMARY)`: 25,411 rows / 4,371 clusters → seeded
(`20260818`) sample 600 rows / 551 clusters → 556 measured / 515 clusters (44
`no_true_codeword`, 7.3%). Sweep: 556×49=27,244 extractions. Optimum
`+0.65s`, median BER **5.75%**. Quartile stability: **perfect**, all four
independently swept to `+0.65s`, deviation 0.000s in every quartile.

Every one of these numbers is **identical** to Stage 2's own report
(`2026-08-18-2013-...`, §2.2/§2.3) because `run_stage1re.py` imports and
calls `run_stage2.run_part_a()` directly rather than reimplementing it — same
function, same population, same seed, same DLL. This is by construction, not
a second independent confirmation; flagged so it is not mistaken for one.

---

## 3. Full P-LIVE measurement — V0 grid vs V3_cum coherent, at the corrected anchor

### 3.1 Population and drops

`build_p_live_population(PRIMARY)` = 18,012 rows / 4,113 clusters
(pre-extraction). Measured at `anchor_dt + 0.65s`, **no truncation, no
sampling** (spec §5): **15,389/18,012 rows (436.1s), 3,917 clusters.** Drop
reasons: `no_true_codeword` 1,605 (8.9%), `v0_extract_rc_-3` 1,018 (5.65%).

**Cross-check against Stage 2's own independent P-LIVE pass on the same
corpus and anchor:** Stage 2 measured 15,383/18,012 rows, 3,916 clusters,
`no_true_codeword` 1,605, `grid_extract_rc_-3` 1,018 — **matches to the row**
on both drop-reason counts, and within 6 rows / 1 cluster overall (the small
difference is exactly Stage 2's extra `refined_extract_rc_-3` drop class,
which this arm's pipeline — no refiner call — does not have). Two
independently-written harnesses landed on the same population at the same
anchor. Strong internal consistency, not a coincidence worth escalating.

### 3.2 ROW 0c / 0e

- **median `BER_V0`(OFFSET) = 31.03%** — inside [8%,40%]. Also matches Stage
  2's own `median_ber_grid = 31.03%` exactly (same quantity, same anchor,
  same population, independently computed). Clear.
- **15,389 rows / 3,917 clusters delivered** — clears 500/200 with wide
  margin. Clear.

Decile table over the crossable denominator (`BER_V0 > B50=11.3%`,
n=14,934): `11.5% / 16.1% / 19.5% / 23.0% / 27.6% / 31.6% / 35.6% / 39.7% /
43.1% / 47.1% / 61.5%` — a real, spread distribution, not a degenerate spike.

### 3.3 Primary statistic — `f_net`, this spec's own crossable-denominator definition

**Not** `n5_stats.f_net` (which re-bases both terms onto the whole
population) — a fresh cluster bootstrap implementing spec §4's own formula
verbatim, `(n_cross - n_break) / n_crossable`, both terms sharing one
denominator:

| quantity | n | own-denominator point | CI95 (own denom) |
|---|---|---|---|
| crossable (`BER_V0>B50`) | 14,934 rows / 3,880 clusters | `f_cross` = 2.4709% | [2.2343%, 2.7173%] |
| breakable (`BER_V0≤B50`) | 455 rows / 420 clusters | `f_break` = 60.6593% | [55.8442%, 65.7438%] |

**`f_net` (SIGNED, HK-021(l), primary, `n_crossable`-denominator):**

```
point = +0.6227%   CI95 = [+0.2975%, +0.9591%]   n_draws=2000   n_clusters=3,917
```

`n_cross = 369 > 0` ⇒ the bootstrap CI is not degenerate and is the reported
quantity directly (rule-of-three, `0.0765%` at n_clusters=3,917, is reported
alongside but does not gate here — it only applies when `n_cross=0`).

🔴 **`f_break = 60.66%` is large and worth flagging on its own terms, not
just netted away.** Of the 455 rows that were *already* correctable at the
V0 grid position (`BER_V0 ≤ B50`) despite being a live-decode miss, **276
(60.7%) get pushed above B50 by the coherent V3_cum treatment** — the same
harm signature Stage 2 found on limb 1 (N2: coherent order made
matched-hit-control BER monotonically worse, 2.87%→8.05%; Stage 2 ROW 3:
refinement costs -3.45pp on the miss population). `f_net`'s signed,
crossable-denominator construction (spec §4, remedying defect D-noted-with-⚠
in §1) correctly nets this against the much larger crossable population
(14,934 vs 455) and still reports a positive, CI-excludes-zero result — but
the breakage component is real, large in its own subset, and a designer
choosing whether/how to apply coherent extraction in Route B2 should see it
stated plainly rather than only as a component of a netted-positive headline.

### 3.4 The gate: ROW 1 fires

`CI_lo(f_net) = +0.2975% > 0` ⇒ **ROW 1 FIRES.**

> LIMB 2 CONVERTS. Coherent LLRs convert real misses at scale. Route B2 is
> strongly motivated; Phase B becomes high-value. Point estimate
> `f_net=+0.6227%` against the ~42pp gap — **a conversion rate is not yet a
> recovered-message count.**

---

## 4. N5's status — flagged for the Architect, not ruled here

Per this spec's own §5 prohibition: *"N5 is not re-ruled by this arm. If ROW
1 or ROW 4 fires, N5's own 4.37% bound is contradicted at scale and that is
an escalation to the Architect, not a QA ruling."* ROW 1 fired. Stating the
facts plainly and stopping there, per instruction:

- N5's own reading was `0/403` on 67 clusters — a **degenerate, HELD**
  upper bound (`1 − 0.05^(1/67) = 4.37%`), never a positive measurement.
- This run's own `f_cross` (own-denominator) point is **2.47%**, CI95
  `[2.23%, 2.72%]` — numerically **below** N5's 4.37% bound, so nothing here
  contradicts that bound's arithmetic.
- What this run **does** establish, that N5's zero-observation number
  structurally could not: a real, non-zero, CI-excludes-zero conversion
  effect exists on 58× the cluster count, on an anchor this run itself
  validated (ROW 0b/0c) rather than inherited. N5's own held/UNRULED status
  described "no observed crossings in 403 trials," which is a materially
  different — and now superseded — evidential state from "a positive,
  bounded-away-from-zero effect, independently confirmed on an anchor
  sanity-checked two ways." Escalating this distinction to the Architect
  rather than adjudicating it.

---

## 5. Predictions scored (§6 — nothing gated on these)

| prediction | outcome | class | result |
|---|---|---|---|
| P(ROW 3 — still open, tighter) ≈ 45% (plurality) | ROW 1 fired | categorical | **MISS** on the plurality call |
| P(ROW 2 — closes below 0.5%) ≈ 35% | did not fire | categorical | consistent |
| P(ROW 1 — converts) ≈ 15% | 🔴 **fired** | categorical | **HIT** — the lowest-mass "does something real" outcome (15%) is what happened, over the 80% mass assigned to "closes or stays open" |
| P(ROW 4 — harms) ≈ 5% | did not fire | categorical | consistent |
| swept argmin within one lattice cell of Stage 1R's +0.65s | exact match, 0.000s | mechanical | **HIT** |

Per standing practice, QA scores each prediction individually and leaves the
aggregate running-tally arithmetic to the Architect's own bookkeeping.

---

## 6. What this does and does not change

✅ **Limb 2 converts, at scale, on a validated anchor.** The first positive,
non-degenerate scale reading limb 2 has ever produced.

✅ **Phase B was already authorised and remains so regardless of this
result** (spec §0/§5) — this result makes it higher-value, it does not gate
it. No Captain ruling is required before Phase B on THIS result (that
escalation trigger was ROW 2/ROW 4, neither of which fired); §4 above is a
separate, narrower escalation about N5's status specifically.

🛑 **Does not authorise building C integration itself** — a conversion rate
is not a recovered-message count, and sizing that gap is explicitly out of
scope here (spec §7: "That limb 2 and the ~42 pp gap are the same size
question. They are not.").

🛑 **Stage 1 (withdrawn) stays withdrawn.** Its numbers were not cited,
compared against, or used to set expectations anywhere in this run or this
report.

🛑 **N5 stays UNRULED/HELD** on its own 4.37% bound — see §4. Not re-ruled
by QA.

🛑 **ROW 0g (prior thread) stands FIRED, task 4.3 stays VOID, Route B2 is
NOT dead** — nothing in this arm bears on any of that (spec §5, restated).

🛑 **B3 stays HELD.**

---

## 7. Scope and NFR-021

No `src/`, no `native/`, no Developer session, no DLL rebuild, no push, no
merge — HK-011 not engaged. DLL re-hashed from disk immediately before
arming, matches this spec's own pin exactly
(`1889408787a2c7ea545dbe8477691b090417a74fc81116cbf1ea52413bfbdb3a`, shim
20260043 — confirmed on disk to be the current `src/` binary, i.e. `main`'s
own `a420016`).

NFR-021: message TEXT is used in-process only (`ExtractLLRs.true_codeword`,
inside `measure_row_1re`) and is never written to any row dict, JSON field,
or log line. Verified mechanically on every emitted file, not asserted:

```
$ grep -ni "message" results/stage1re_report.json results/stage1re_rows.json \
    results/stage1re_run.log results/stage1re_console.log
results/stage1re_run.log:92:...a conversion rate is NOT yet a recovered-message count.
results/stage1re_console.log:92:...a conversion rate is NOT yet a recovered-message count.
```

Both hits are this report's own prose (the substring "message" inside
"recovered-**message** count"), not row identity or callsign content. Every
row dict carries only `{ts, corpus, ber_v0, ber_v3, d_ber, crosses, breaks,
anchor_freq_hz, corrected_dt}` — confirmed by direct key inspection of
`results/stage1re_rows.json`, not merely by the grep's absence of a hit.

Full per-row dump written this round (`results/stage1re_rows.json`, 15,389
rows, no message text, no free-text field) — unlike Stage 2, which never
assembled one. Present per this spec's own construction (`_write_rows`,
matching Stage 1's own convention, not Stage 2's).

---

## 8. Next

Awaiting the Architect's ruling on:

1. §4 above — what this result means for N5's UNRULED/HELD status.
2. Whether the `f_break=60.66%` breakage signature (§3.3) warrants its own
   follow-up before or during Phase B, or is adequately handled by `f_net`'s
   existing signed, netted construction.
3. Anything else this changes about Phase B's own scope, now that it is
   proceeding with a positive limb 2 reading in hand rather than the
   thin/degenerate N5 bound it was authorised against.
