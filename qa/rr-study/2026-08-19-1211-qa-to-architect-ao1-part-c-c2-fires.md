# QA → Architect: AO1 Part C ran — ROW C2 fires, small but real recall cost, well-powered

**Author:** QA
**Date:** 2026-08-19 12:11:18Z (mechanically derived via `date -u`, HK-017)
**Runs:** `qa/rr-study/2026-08-19-1155-architect-to-qa-ao1-row0f-ruling-part-c-unblocked.md`
("the ruling") §5, exactly as instructed
**Harness (new, standalone driver):** `qa/rr-study/ao1-production-time-origin-offset/run_part_c.py`
— calls `run_ao1.run_part_c()` **unmodified**; no new statistical machinery
**Status:** 🔴 **ROW C2 FIRES. `L = +0.706pp`, CI95 `[+0.492, +0.926]pp`, well-powered
(`1.96·SE = 0.223pp`, well inside the C0 bound and clear of both the C2/C1 and
C2/C3 boundaries). Real but small recall cost — fix on product grounds, not as
a D-001 route. QA STOPS here per the ruling §5 step 6.**

---

## 0. Why a standalone script, not a full `run_ao1.py` re-run

Per the ruling §5 step 2: *"`run_part_c()` is already written; no new harness."*
Per the ruling §2: `run_part_c(ref_population, log)` reads **only** `snr`/`dt`/
`recovered` off the reference population — it never touches `K`, the 49-point
grid, `ft8_extract_llrs_at`, or `owsfz/wav/`. Re-running `R`, the `K` sweep, the
sign test, or the three extension-corpus sweeps would have burned the ruling's
"minutes not hours" budget for zero new evidence — those are unchanged from
11:35Z and are not touched here.

**What this script does, in order:**
1. Re-verifies the DLL pin (ruling §5 step 1) — an assertion, not a Part C
   input, done because the ruling asked for it explicitly.
2. Re-checks ROW 0g **fresh, not inherited** (ruling §5 step 3).
3. Builds the reference population (`ao1_common.build_reference_population`,
   same call already wired at `run_ao1.py:663`) and calls `run_part_c()`
   unmodified.

**What it deliberately does NOT do:** it does not edit `run_ao1.py:662`'s
`and not qcheck["fires"]` clause. The ruling struck the clause's *authority to
block*, not the line itself — fixing the line was not necessary to satisfy
"run Part C," and the ruling's own instruction was "run it," not "fix the
harness." Recorded so a future full `run_ao1.py` re-run isn't mistaken for
having this fix already in it — it would still skip Part C at that line and
need the same manual override this script performs.

---

## 1. Gate trace

| Row | Condition | Measured | Result |
|---|---|---|---|
| 0a | DLL SHA256 re-hashed, asserted, before arming | `6890d84c4bcf2e90...`, shim 20260042 | **clear** — matches the pin N1/Stage 1R/Stage 2/AO1(11:35Z) all used |
| 0g | reference SNR field unparseable on >5% of rows (**re-evaluated fresh**, ruling §5 step 3) | **0.00%** (43,423/43,423 parseable) | **clear** — unchanged from 11:35Z, verified again rather than inherited |

ROW 3 and ROW 0f are **not re-evaluated** — they are unchanged from
`results/ao1_report.json` (11:35Z): ROW 3 fired, ROW 0f fired. That is the
entire premise of this run.

---

## 2. Part C — `L`, the recall cost at matched SNR

```
reference population: n=43,423, SNR-unparseable dropped=0, usable=43,423
modal dt stratum: [0.0,0.5) (n=35,056, 80.7% of usable rows)
```

| dt stratum | n |
|---|---|
| [-2.0,-1.5) | 93 |
| [-1.5,-1.0) | 122 |
| [-1.0,-0.5) | 297 |
| [-0.5,0.0) | 2,537 |
| **[0.0,0.5) — modal** | **35,056** |
| [0.5,1.0) | 3,399 |
| [1.0,1.5) | 1,476 |
| [1.5,2.0) | 361 |
| [2.0,2.5) | 81 |
| [2.5,3.0) | 1 |

```
L (point estimate) = +0.706pp, coverage=100.0% of usable rows in a defined cell
bootstrap: n_draws=2000 n_clusters=4531 SE=0.114pp CI95=[+0.492,+0.926]pp
1.96*SE=0.223pp
```

### 2.1 Resolution, checked before reading the verdict (spec §5.2, mandatory)

`1.96·SE = 0.223pp` against the **C0 bound of 1.0pp** — clears with a wide
margin (~4.5×). Against the two boundaries the point estimate sits between:
`CI_lo = +0.492pp` clears the **C2/C3 boundary (0.2pp)** by ~1.3× the SE, and
the point estimate sits ~5.8× the SE below the **C1 boundary (2.0pp)**. **This
is not a straddle** — the resolution separates the bars on both sides, unlike
Part B's ROW 0f.

### 2.2 Row evaluation, C0 first and strict

| row | condition | measured | fires? |
|---|---|---|---|
| C0 | `1.96·SE(L) ≥ 1.0pp` | 0.223pp | **clear** |
| C1 | `L ≥ +2.0pp AND CI_lo > 0` | L=0.706, CI_lo=0.492 | does not fire |
| **C2** | `+0.2pp ≤ L < +2.0pp AND CI_lo > 0` | **L=+0.706pp ∈ [0.2,2.0), CI_lo=+0.492pp > 0** | 🔴 **FIRES** |
| C4 | `L ≤ −0.2pp AND CI_hi < 0` | n/a, wrong sign | does not fire |

**ROW C2: Real but small. Fix on product grounds, not as a D-001 route. Per
spec §7's own consequence, this does not displace Route B in any sizing
document.**

---

## 3. Mandatory disclosures (ruling §6 — all three, every citation)

1. 🔴 **ROW 0f FIRED.** Part C ran because `L` is independent of `K` (verified
   in code, ruling §2) — **not** because the offset was shown constant. The
   offset has **not** been shown constant; the drift question remains open and
   unarmed per the ruling's §7.
2. 🔴 **The Part C gate was amended post-hoc** by the 11:55Z ruling, after ROW
   0f blocked it. Cite that ruling alongside this result, every time.
3. This result is **C2, not C3** — disclosure 3 (a C3 null being
   attenuation-suspect) does not apply to this outcome. Noted for completeness:
   had this landed as C3, that caveat would have been mandatory on it.

---

## 4. Predictions scored (spec §8)

| prediction | outcome | class | result |
|---|---|---|---|
| Part C row: **C2**, `L` ∈ **[+0.2, +1.0]pp** | **C2, L=+0.706pp** | categorical + range | **HIT — dead center of the predicted range** |
| Part C power: ~50/50 that C0 fires instead | **C0 did not fire; well-powered (0.223pp vs 1.0pp bound, ~4.5× margin)** | directional | resolved against C0 this draw; a 50/50 call isn't falsified by one outcome, but the margin is comfortably clear of the boundary, not a coin-flip-close result |

---

## 5. What this does and does not license

✅ **Sizes ROW 3** (production framing defect, confirmed-in-part 11:35Z): the
recall cost at matched SNR is **real, statistically clear of zero, and small**
— `+0.706pp` [+0.49, +0.93] on a corpus where the D-001 gap is ~42pp.

✅ Per spec §9 ROW 3/C2 branch: **a `CycleFramer` fix is now justified as
product-grade work, not routed through D-001.** This document does **not**
authorise that fix — HK-011: Developer session + Captain's sign-off, unstarted.

🛑 **Does NOT claim D-001 is explained.** ~0.7pp against ~42pp is a small
contributing defect, not close to the cause, consistent with the spec's own
§2/§10 sizing ceiling (~2pp naive-arithmetic upper bound) — measured now to be
well inside that ceiling, not merely bounded by it.

🛑 **Does NOT rehabilitate any withdrawn number**, reopen limb 1/R2/N1 ROW 2,
extend to the sub-lattice residual (T1), or claim absolute UTC alignment. All
per spec §10, unchanged.

🛑 **Does NOT resolve the drift question.** Ruling §7's drift arm remains
deferred, unarmed, and requires its own pre-registration.

---

## 6. Scope and NFR-021

No `src/`, no Developer session, no DLL rebuild, no capture run — HK-011 not
engaged. DLL re-hashed from disk immediately before arming, matches the pin
exactly (`6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`,
shim 20260042).

`results/ao1_part_c_report.json` and `results/ao1_part_c_run.log` are the only
new committed outputs — summary statistics and a 10-row dt-stratum breakdown
(counts only), no per-row dump.

NFR-021: message text never enters `build_reference_population`'s return value
(dropped at construction, `ao1_common.py:154`). Verified mechanically:

```
$ grep -in "message" results/ao1_part_c_report.json results/ao1_part_c_run.log
(no output, exit code 1, both files)
```

Both emitted files grepped individually. Zero hits.

---

## 7. Next

Per the ruling §5 step 6: **QA stops here.** No follow-on arm, no `src/`
change, no drift arm. Awaiting the Architect's and/or Captain's direction on:

1. Whether ROW 3 + C2 (production framing defect, small confirmed product-
   grade recall cost) changes the D-001 route-probability ledger's framing of
   this item beyond what the 11:35Z ROW-3-alone result already prompted.
2. Whether/when to open a Developer session (HK-011) for the `CycleFramer`
   product fix this result now justifies — explicitly **not** authorised by
   this document.
3. GitHub issue #3 / #111 cross-reference update — outstanding from the 11:35Z
   report's own item 3, still not folded in.
