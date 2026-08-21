# Architect → QA: SPEC — B-pos-A, the lattice-position arm (Route B2, Phase B)

**Author:** Architect
**Date:** 2026-08-21 13:30 UTC (`date -u`, HK-017)
**Authorised by:** the Captain, 2026-08-21 — *"go with B-pos-A now with B3 held."*
**Predecessors:** `2026-08-21-1201-architect-to-qa-b2-row0g-native-fix-triage-and-phase-a-deconfounding.md`
(Phase A spec) · `2026-08-21-1242-qa-to-architect-phase-a-deconfounding-results.md` (Phase A results)
**Binary under test:** current merged `main` (`a420016`), shim 20260043, DLL SHA256 `1889408787...`

---

## 0. Status, and what this is NOT

🔴 **DIAGNOSTIC ONLY. This spec defines NO ROW, NO PASS/FAIL, NO `f_net`, and NO gate.**

- 🛑 **ROW 0g is not re-read, re-metriced or amended.** It stands exactly as run: **FIRED**, the
  Phase 1 gate (task 4.3) is **VOID**, **ROW 3 is not declared**, **Route B2 is not dead.**
- 🛑 **No `src/` or `native/` edit, no DLL rebuild, no push, no merge.** HK-011 is **not engaged** —
  this arm requires no native change at all (see §2.3). If you find yourself wanting one, **stop and
  escalate** rather than widen the arm.
- 🛑 This arm **measures what design.md D1 costs. It does not authorise changing D1.** Amending D1
  is the Captain's ruling and remains owed (1201 spec §5).
- 🛑 **B3 (`out_diag`) is HELD, not killed.** Do not build it, do not pre-empt it.

---

## 1. The question

design.md **D1** binds the coherent path to form LLRs at the **grid candidate's own, unrefined
position**. Phase A's A3 control — that shared anchor, with **zero** injected residual — already
read `d_clean = -61.0` against ROW 0g-2's real `d_real = -67.0` CI95 `[-71, -65]`.

So the shared-position mandate, not any injected residual, carries ~90% of the collapse. **This arm
asks what that costs on the REAL population**, by letting each path read at its own best lattice
point instead of a shared one.

---

## 2. Measured facts this spec is built on

All four measured this session against the merged binary, not quoted from the board.

### 2.1 The position axis is quantised, and the export snaps to it

Probed by sweeping requested positions and watching the output change in blocks:

```
time   0.00-0.03 | 0.04-0.11 | 0.12-0.19 | 0.20-0.27 | 0.28-0.35   => quantum 0.08 s
freq   one block spans 1498.50 ... 1501.50                          => quantum 3.125 Hz
```

🔴 **Consequence, and it is a correction to how Phase A's A2 should be read:** the 49-point sweep
resolved only ~5 distinct time positions. A2's *"displaced ~0.12-0.15 s"* is more precisely
**displaced by exactly 2 time quanta = 0.16 s = one full FT8 symbol period** (grid's best block is
the `0.16` snap, coherent's is the `0.00` snap). Resolve against the readout quantum, never the
requested value (HK-021(o)). **Report offsets in QUANTA in this arm, with seconds secondary.**

### 2.2 Two benign explanations for that displacement are RULED OUT (code-read, this session)

- **Symbol-index mapping is identical.** `coh_sym_time_index(p) = p + ((p<29) ? 7 : 14)`
  (`coherent_llr.c:193-197`) is identical in form to `decode.c:373`'s own
  `sym_idx = k + ((k < 29) ? 7 : 14)`. **No off-by-one in the logical-to-real symbol map.**
- **FIR group delay is compensated.** `downconvert_decimate` (`sync_refiner.c:144-175`) indexes
  `idx = center + (t - half)` — a centred FIR, so `out[m]` aligns to `pcm[m*decim]`. **No
  uncompensated 121-tap delay.**

=> A one-symbol displacement between the two paths is **currently unexplained**, and that is
precisely what makes §5.1's primary readout worth running.

### 2.3 The arm needs NO native change

`ft8_coherent_llr_at(pcm, pcm_len, freq_hz, time_offset_s, out_log174)` already takes the position
as **two floats** and snaps internally. A per-path position search is therefore a **caller-side
loop**. Nothing to build, bump, rebuild, or merge.

### 2.4 Cost is negligible

Measured per-call: **coherent 8.32 ms, grid 4.22 ms.** ROW 0g-2 measured 193 rows x both paths at
**one** position in **2.6 s**. The 21-cell grid of §3.1 is therefore approximately **55 s**. Budget
generously; there is no reason to economise, and no reason to truncate the sample.

### 2.5 What ROW 0g-1 structurally could not have detected (HK-022)

0g-1 swept 49 offsets **per path and took each path's own minimum**. A **constant origin offset
between the two paths is invisible to that construction** — it is absorbed by the per-path minimum.
0g-1's PASS therefore does **not** bear on §5.1's question. Do not cite it as if it did.

---

## 3. Design

### 3.1 The offset grid

Reuse ROW 0g-2's population, sample, seed and anchor **verbatim** (HK-018) — `build_p_hit_population`
+ `deterministic_sample(..., N_REAL_SAMPLE=200, SEED)`, anchor `round(anchor_freq_hz)` and
`anchor_dt + STAGE2_ANCHOR_OFFSET_S`. **Do not re-derive, re-sample or re-seed.** Never pass
`limit=` to any population helper (HK-021(i)).

For each row, extract **both** paths at every cell of:

| axis | offsets (quanta) | quantum | span |
|---|---|---|---|
| time `m` | -3 ... +3 (7 points) | 0.08 s | +/-0.24 s |
| freq `n` | -1, 0, +1 (3 points) | 3.125 Hz | +/-3.125 Hz |

**21 cells.** `n` is capped at +/-1 deliberately: +/-2 quanta = 6.25 Hz = a full tone spacing, which
aliases onto a different tone rather than probing a residual.

### 3.2 Primary statistic — GLOBAL per-path offset, not per-row argmin

🔴 **This is the important design call. Read the rationale before changing it.**

Choose **one** offset cell per path, pooled across the whole sample:

- `(m*_g, n*_g)` = the cell minimising the **cluster-median** `n_err_grid`
- `(m*_c, n*_c)` = the cell minimising the **cluster-median** `n_err_coh`

then form the paired per-row difference at those two fixed cells and pass it to
`cluster_bootstrap_median_diff` (reused **verbatim** from `n1_stats`, HK-018):

```
d_global(i) = n_err_grid(i, m*_g, n*_g)  -  n_err_coh(i, m*_c, n*_c)
```

**Why global and not per-row argmin.** A per-row minimum over 21 noisy cells is
**winner's-curse biased**, and the bias is *larger for the path whose response varies more across
position*. A2 says coherent's response is narrow/peaked and grid's is a wide plateau — so per-row
argmin is biased **precisely toward the conclusion "coherent recovers"**, which is the conclusion
that would push us to amend D1. A single global cell chosen from 190 clusters over 21 candidates
carries negligible selection bias, and it is also the **more architecturally honest** question:
a production fix would be a fixed convention offset, not a per-signal search.

⚠️ Per-row argmin is still computed, but only as the §5.1 **primary shape** readout, and any number
derived from it must be reported **with this bias named in the same sentence**.

---

## 4. Preconditions — mechanical, evaluated BEFORE any headline number

Both STOP the run. Neither is a gate on the *result*; they are instrument checks (HK-025 does not
apply — no verdict branches on them, they only decide whether the instrument is trustworthy).

### P1 — the control cell must reproduce ROW 0g-2 EXACTLY

The `(m=0, n=0)` cell is, by construction, the identical computation ROW 0g-2 already ran. Assert
**all three**, exactly:

```
n_delivered          == 193
n_clusters_delivered == 190
d_control            == -67.0
```

**Any deviation => STOP AND ESCALATE.** Do not proceed, do not "investigate and continue". A control
cell that fails to reproduce means the harness is not calling what 0g-2 called, and every other cell
is then uninterpretable.

### P2 — the chosen optimum must be INTERIOR (HK-026)

If `m*` for **either** path lands on `+/-3` (the swept boundary), the grid has measured its own edge
rather than the path's optimum. **Widen `m` by 2 quanta each side and re-run.** Report the widened
range. Do not report a boundary optimum as an optimum.

`n*` on `+/-1` is **not** a breach (that cap is physical, §3.1) — record it, do not widen.

---

## 5. Readouts

### 5.1 PRIMARY — is the displacement CONSTANT or SCATTERED?

This is the reading I most want, and it is the one this arm is uniquely able to give.

Compute, per row, the coherent path's own argmin cell `m*_c(i)`. Report:

- the **modal** `m*_c` and `frac_at_mode` = fraction of rows attaining it
- the same for the grid path
- the **null**: if argmin were pure noise over 21 cells, `frac_at_mode` is approximately
  `1/21 = 0.048`

**Interpretation aid — a reading aid, NOT a gate, no verdict attaches:**

| `frac_at_mode` (coherent) | reads as |
|---|---|
| high, at a **non-zero** mode | a **constant convention/origin offset** between the paths — cheap to fix, and it would be a large result |
| diffuse, near the null | a **genuine per-signal position sensitivity** — D1 itself is the problem |

⚠️ State the winner's-curse bias (§3.2) in the same sentence as any per-row argmin number.

### 5.2 SECONDARY — does an own-best global offset close the gap?

Report `d_global` with its **cluster-bootstrap CI95** and `n_clusters`, alongside
`d_control = -67.0 [-71, -65]`. Report the two chosen cells `(m*_g, n*_g)`, `(m*_c, n*_c)` **in
quanta**.

### 5.3 Reporting requirements

- **CLUSTER counts, never bare row counts** (HK-021(i)); `n_clusters` on every interval.
- **Offsets in quanta**, seconds secondary (§2.1).
- ⚠️ **Do not report an absolute optimal `dt`** — design.md D3, the axis zero is uncalibrated. A
  **relative displacement in quanta between the two paths** is exactly what is identifiable, and is
  what to report.
- Record any mid-run correction in the **script itself**, not only the report (the Phase A
  precedent, HK-018/HK-022).
- HK-001 report sections; `qa/rr-study/2026-08-21-HHMM-qa-to-architect-b-pos-a-results.md`.

---

## 6. Blind predictions (Architect, recorded before the run — calibration)

Scored later against the result; **not** bars, and nothing branches on them.

1. **P1 reproduces exactly** — ~90%.
2. **`frac_at_mode` for coherent is HIGH (>=0.6) at a non-zero mode** — ~55%. This is the
   one-symbol-displacement hypothesis. I hold it above even odds only because §2.2 ruled out the two
   obvious benign causes and the A2 displacement was suspiciously close to exactly one symbol.
3. **`d_global` is materially less negative than -67, i.e. CI95 excludes -67** — ~70%.
4. **`d_global` reaches >= 0 (coherent at parity or better)** — ~30%. I expect partial recovery, not
   full.
5. **P2 fires (boundary optimum, needs widening)** — ~15%.

---

## 7. What happens next, by branch (Architect's, not QA's — recorded so the arm has a purpose)

- **Constant displacement (5.1 high at non-zero mode)** => a narrow, D1-compatible fix becomes the
  candidate, and B3 likely stays held. I bring the Captain the ruling with numbers.
- **Scattered (5.1 near null)** => D1 itself is implicated; the 1201 spec §5 ruling becomes live, and
  B3's fusion question moves back up.
- **`d_global` barely moves** => position is not the lever, the defect is inside the correlator or
  the fusion, and **B3 earns its Developer session.**
