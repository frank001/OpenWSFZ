# ARCHITECT → QA — consolidated work queue (post-X2). ONE document. Read this first.

**Author:** Architect, 2026-08-10 (20:28 UTC, `date -u`, HK-017). **For:** QA.
**Supersedes:** `2026-08-07-2241-architect-to-qa-consolidated-work-queue.md`, which is **fully
closed out** (W1/W2/W3/T1/T2/H1/H1a all done; no live item remained on it). Read that document only
for provenance — 🛑 **its §0 lists withdrawn claims and its body carries struck-through statements
that were believed at the time and are now known-wrong.**

**Authority:** the Captain's three rulings of 2026-08-10, given in answer to the post-X2 route memo.
**Where the specs disagree with this queue, the SPECS WIN** — this document is an index and an
ordering, not a restatement.

---

## 0. What is live, in one table

| # | item | kind | cost | needs | status |
|---|---|---|---|---|---|
| **A** | Reports for **P2 / P3 / P1a** | write-up | ~1 session | nothing | 🔴 **OWED since 2026-08-09.** Verified 2026-08-10: **none of the three exists on disk** |
| **B** | **X4** — S.1 reopened, within-cycle spectral locality | `ALL.TXT` analysis | ~half session | nothing | 🔴 **SPECCED, NOT RUN** |
| **C** | **X3** — lattice × crowding interaction | decoder replay | ~1 session + ~40 min/leg | pinned DLL | 🔴 **SPECCED, NOT RUN** |
| **D** | **G2** — hash-table sizing + candidate passband | `src/` + native rebuild | Developer session | 🛑 **BLOCKED**, §0.2 | 🔴 **SPECCED, BLOCKED** |

**Recommended order: A → B → C → D.** Reasoning, so you can override it with a reason rather than
by accident:

- **A first** because three measured results are currently undocumented, and the longer that runs the
  more the numbers get cited from `BOARD.md` prose instead of from a report with citation limits.
- **B before C** because X4 is the cheapest of the two arms and **which limb it lands on changes how
  C reads** — a DIFFUSE result demotes part of X3's own rationale.
- **D last**, and it cannot start at all until §0.2 clears.

⚠️ **This ordering is a recommendation, not a gate.** B and C are independent; if you would rather
run C while writing A, nothing forbids it.

### 0.1 The three specs

| item | spec |
|---|---|
| **X3** | `qa/cycleframer-alignment-replay/2026-08-10-1808-architect-to-qa-spec-x3-lattice-crowding-interaction.md` |
| **X4** | `qa/cycleframer-alignment-replay/2026-08-10-1808-architect-to-qa-spec-x4-s1-reopened-within-cycle-spectral-locality.md` |
| **G2** | `qa/cycleframer-alignment-replay/2026-08-10-1808-architect-to-qa-spec-g2-hash-table-sizing-and-candidate-passband.md` |

All three committed at **`60e14e5`**, **before any harness exists**, per HK-021.

### 0.2 🛑 BLOCKER on item D only — do not start a Developer session until this is answered

`src/OpenWSFZ.Ft8/Native/ft8_shim.h:297` and `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:224` **both
read `20260033`** on `main`. But P2, P3 and P1a **all asserted shim `20260035`** against DLL SHA
`39aa1031…`. **Those cannot both describe `main`'s source tree.**

Establish **which tree built the DLL QA has been running** before anything builds on top of it.
🔴 **The SHA is the authority; the version integer identifies nothing** — it collides twice across
five unmerged `d001-*` branches (20260034 and 20260035 each claimed by two). First unambiguously
free integer for G2: **20260038** (20260036/20260037 are W2's proposed renumbering targets).

**This is an escalation, not a QA decision.** Report what you find; do not resolve it in session.

---

## 1. Item A — the three owed reports

One report per arm, in this directory, filename **and** byline from real `date -u` and **in
agreement** (HK-017). Raw results are already on disk:

| arm | row | raw | run log |
|---|---|---|---|
| **P2** | ROW 2 — input scaling CLOSED | `p2_result.json` | `p23_run_20260809T105321Z.log` |
| **P3** | ROW 3 — sub-lattice real, union manufactures | `p3_result.json` | same log |
| **P1a** | V-ROW 2 — `A` = 15.55 is DEAD | `p1a_result.json` | `p1a_run_20260809T111127Z.log` |

**Each report must carry** (this list is the standard, not a suggestion):

1. DLL **SHA256** + shim-version assertion as recorded at startup.
2. The **ordered gate trace** — every ROW evaluated in order, with the measured value against its bar.
3. The headline with its **clustered** CI (never binomial — HK-021(i)).
4. **Predictions scored**, both QA's and the Architect's, including the misses.
5. The §1.1 hash-table disclosure.
6. **Explicit citation limits** — what may and may not be quoted from this arm.

🔴 **P2's and P1a's citation limits are the load-bearing part**, because both produce standing
prohibitions rather than usable numbers:

- **P2 ⇒ input scaling is CLOSED permanently.** Normalisation, AGC, softmax/temperature and
  equalisation may never be re-proposed as D-001 treatments without new evidence. ⚠️ Also record the
  bound: the gain-invariance retraction holds only ~32 768× from target; **within ±18 dB the original
  ruling stands.** Quote the bound, never either absolute.
- **P1a ⇒ `A` = 15.55 is uncitable in EVERY form**, including as a bound in either direction. The
  standing depth caveat stays **exactly** as worded. P1a did not repair the instrument; it
  disqualified it.
- **P3 ⇒ `S_all` = 4.27 pp is real, but `X_guard` = 0.897 must travel with it in every citation.**
  🛑 It does **not** license `K_FREQ_OSR`/`K_TIME_OSR` 2→4.

---

## 2. Item B — X4 (S.1 REOPENED)

**Read the spec.** The three things most likely to go wrong, flagged here because both prior
attempts died on exactly this class of defect:

1. 🔴 **The within-cycle construction check (ROW 0c) is a hard `== 0.00` assertion.** If the mean
   `n_cycle` gap between the Q1 and Q5 cells is anything but exactly zero, the implementation is not
   doing within-cycle contrasts and the arm is **VOID on that alone**. This is the single defect that
   killed S.1.
2. 🔴 **Cuts are GLOBAL QUANTILES on separation, never absolute Hz.** S.1r's 150 Hz boundary sat at
   the ~97th percentile and its "clear" stratum survived in **0 of 12** cells. ⚠️ **But check
   HK-021(f) first** — `sep` is integer Hz; count its distinct values before binning (ROW 0d).
3. 🔴 **Neighbours come from the REFERENCE's decode list, never ours.** Using our own output is
   circular. `sep` is therefore an **upper bound**, and per HK-021(h) the effect is quoted as
   **"at least X"** — 🛑 never de-attenuated.

**Prior art you must read before writing code** (HK-018 — all of it exists):

- `2026-07-31-1725-qa-arm-s1-result-VOID-on-mandatory-null.md` — the run.
- `2026-07-31-1730-architect-ruling-s1-void-upheld-estimator-defect-not-null.md` — the diagnosis,
  and **S.1b's corrected estimator at its §5, which is what X4 implements.**
- `2026-08-07-1733-qa-to-architect-s1r-results-and-metric-check.md` §1.1 — the **band-edge
  confound** and its exact fix, which X4 carries forward verbatim.
- `2026-08-07-s1r-spectral-locality/` — S.1r's scripts.

🛑 **Retirement rule, pre-committed:** void on ROW 0b (null) or ROW 0c (construction), or a ROW 4
read, ⇒ **spectral locality is RETIRED PERMANENTLY.** No fourth design, no better metric on the same
data. Escalate; do not redesign.

---

## 3. Item C — X3 (lattice × crowding)

**Read the spec.** Three points that are easy to skip past:

1. 🔴 **ROW 0e runs BEFORE the four shifted legs.** Compute the clustered `SE(I)` from the base leg
   alone; if it exceeds **0.75 pp** on the primary leg, the arm is **declared underpowered and not
   run.** That is minutes spent instead of hours, and an underpowered stratum is an **instrument
   failure, never a null.**
2. 🔴 **Primary is 20m, replication is 80m — the reverse of X2.** Precision here is set by frequency
   clusters (20m 30 513, 80m ~907), not by row counts.
3. 🛑 **Do not propose the cheap observational version** (T1's `G` stratified by density). It is
   underpowered by construction: **>7.3 pp** needed to fire at 3σ against a base `G` of **3.16 pp**.
   That computation is in the spec's §0.2; it is why decoder time is being spent.

---

## 4. Item D — G2 (`src/`)

🔴 **HK-011 applies in full: QA specifies, proposes, and STOPS.**

- **You author the `dev-tasks/*.md`** — that is QA's document, not the Architect's (HK-015).
- A **separate Developer session** runs `opsx:apply` (build + tests only).
- 🛑 **QA never runs `pre_merge_check.py`** — that is HK-006, the Captain's initiative only — and
  never declares "ready for merge" unprompted.
- The Captain reviews the diff. **HK-010: merge always needs explicit sign-off.**

**One branch, two commits, separately revertible.** (a) and (b) are unrelated and must not be
entangled.

⚠️ **(b)'s boundary is yours to derive from the corpora, not to take from me.** The spec requires
computing the reference decode-frequency distribution across all three bands first and choosing
`f_min`/`f_max` to cover a **stated percentile**. My instinct was ~100–3600 Hz; the distribution is
on disk, so use it.

⚠️ **FP is instrumented, not gated** — the Captain deferred it explicitly. Record the before/after
proxy so the deferred decision doesn't later need a re-run. **Do not draw an FP conclusion.**

---

## 5. Reference index — pins, corpora, harnesses

### 5.1 Pins that must be asserted at startup, every run

```
DLL SHA256   39aa1031ad63fd7c882ae9093a3d6c4d681f1c45e2a4f3b4336ff6c3f45e0aba
REF (20m)    69 222 exactly, through the shared T1 loader
SNR strata   L1 edges [-15, -10, -5, 2]   <- X1's PUBLISHED edges, pinned, never re-derived
density      FLOOR <= 5 | MID 6-13 | OVERLAP 14-26   <- X2's, fixed GLOBALLY (HK-021(g))
bootstrap    1 000 draws, fixed seed, CLUSTERED (never binomial), PAIRED where two
             quantities are differenced on the same draw
```

### 5.2 Corpora (all verified present on disk 2026-08-10)

| band | path | notes |
|---|---|---|
| 20m | `artefacts/20260808_live_run_0016-808{0,1}/` | ~2 540 cycles, density 13–38. The reference corpus for almost everything |
| 17m | `artefacts/20260808_live_run_1154-808{0,1}-17m/` | 1 856 cycles, density 3–28 |
| 80m | `artefacts/20260809_live_run_0155-808{0,1}-80m/` | the only corpus reaching the FLOOR regime |

🔴 **Read `qa/ARTEFACT_INVENTORY.md` before concluding any data does or does not exist**, and before
proposing any capture run. `python qa/artefact_inventory.py --check` fails if stale. ⚠️ **An empty
`notes` cell is itself a risk** — `notes` is interpretive; every other column is measured from disk.

⚠️ **80m carries two standing caveats.** Its **ROW 0e fires**: WSJT-X's last decode is `260809_072815`
while OpenWSFZ archived to `101100`, so **the deep tail has no reference** — all 80m recovery
analysis ends at `072815`, and the tail is descriptive only (**raw counts, never a percentage**).
Its `ALL.TXT` and WAV hardlink defects were repaired by **X0** and **G1 Amendment 1** respectively;
both are verified, and the repair notes are in each folder's `contents.md`.

### 5.3 Harnesses to reuse rather than rewrite (all present)

| file | reuse for |
|---|---|
| `t1_frequency_quantisation.py` | `load()` — **the shared `REF` loader. Import it unmodified.** |
| `x1_cross_band_decomposition.py` | `aggregate_cells`, `bootstrap_cell_replicates`, `percentile`, `assign_stratum` |
| `x2_density_floor.py` | density-regime assignment — **reuse, do not re-derive** |
| `p3_shift_union.py` + `p23_common.py` | X3's five-leg shift-union machinery |
| `x1_result.json`, `x2_result.json`, `p3_result.json` | published point estimates for cross-checking |

✅ **Both X1 and X2 reproduced the Architect's independently-computed figures to the decimal from
independently-implemented harnesses.** That cross-check is now the house standard — build it in.

---

## 6. 🛑 Standing bars — things QA must not propose, in any arm

Each is closed by a measurement, not by opinion. Re-proposing any of them is the failure mode this
section exists to prevent.

| family | why it is closed |
|---|---|
| **Input scaling** — normalisation, AGC, softmax/temperature, equalisation | P2: `P` = **0.007 pp** across ±18 dB |
| **Candidate budget** — caps, `K_MAX_PASSES` | RC2 closed **twice**; C.1 bounded at **+0.93%**; RC4 +0.70 pp |
| **OSD tuning** | D-009: **+0.109 pp** across 45 grid points |
| **Subtract-and-resynthesise (PCM domain)** | three builds, three reverts, worst **−17 pp**, two `0xC0000005` crashes |
| **The shipped waterfall SIC as a crowding mechanism** | it fires **after pass 0 commits its decodes** ⇒ cannot cost a pass-0 decode; bounded by pass 1's 0.80% |
| **`K_FREQ_OSR`/`K_TIME_OSR` 2→4 on P3's evidence** | the union's junk rate is a property of unioning five runs, not of oversampling. Earns its own pre-registration **with FP as the primary metric** |
| **A capture run** | `20260803_live_run_1713` is 18.96 h contiguous; three more corpora exist |
| **Re-reading a closed gate with a better metric** | a better metric earns a **NEW pre-registration**, never a re-read |

⚠️ **Two structural ceilings, so you do not ask for runtime that cannot help:** T2a proved more 20m
data cannot sharpen `G` or resolve the midpoint question (the corpus already holds 93%/93%/90% of
the distinct frequencies the passband permits); and `G` is **not band-separable** from this corpus
(80m has 907 frequency clusters — it could not detect anything under ~10 pp).

---

## 7. Citation blacklist — do not quote these, in any form

| do not cite | instead |
|---|---|
| `A` = 15.55 (decode depth), in **any** form incl. as a bound | invocation-sensitive ⇒ not a measurement of depth. Depth caveat unchanged |
| `k_50 = 13`, `c_bottom = 0.476%` | withdrawn |
| `F_dec = 1.2455` | never citable |
| "17m runs ~2–3 pts above 20m" | **fully retired.** X1: +0.76 to +1.34 pp |
| S.1's `Δ_local = +29.2` / `Δ_cycle = +26.9` | VOID — contaminated by a measured between-cycle confound |
| S.1r's `sensitivity_25_100` row | explicitly **non-gating**, reported for context only |
| the recovery-vs-density **slope** as a parameter | retracted — varied 3× between windows of the same leg |
| "40% unexplained" for RC1 | **3.1% out-of-band / 8.9% no-candidate / 87.9% candidate-present-and-failed** |
| T2 §1's "well supported" for `D_int` | "suggestive, consistent with the predicted mechanism, **not established**" (1.9σ) |
| the ~44% cross-column in X0's identity audit as an *agreement* statistic | it is a whole-line identity **fingerprint**; on `(ts, message)` the instances agree ~99.8% |

⚠️ **Basis discipline.** T1 basis = `A∩B`, `<...>`-bearing messages excluded, 200–3000 Hz. The
H1a-corrected **≈57.8%** 20m recovery figure used wildcard matching over a **different population**.
🛑 **Never mix the two in one comparison**, and never compare a corrected figure against an
uncorrected one.

---

## 8. Reporting standard

- **HK-017** — filename and byline both from real `date -u`, and they must agree.
- **HK-001** — QA authors §1/§5 (+§2 framing) of every R&R `report.md`; render via `render_report.py`.
- **NFR-021** — counts, rates, frequencies and cycle timestamps only. Message text may be read to
  build match keys; **no callsign or message text in any committed artefact.** Only Q-prefix
  synthetic calls in VCS (exceptions: PD2FZ, public figures).
- **Determinism** — two runs, byte-identical stdout, fixed seed recorded in the result JSON.
- **HK-016** — if any live run happens, gather to a dated `artefacts/` dir with a `contents.md`
  **before** reporting done. `artefacts/` is blanket-gitignored, so real callsigns there are safe.
- **HK-024** — 🔴 **update `BOARD.md` in the SAME edit as any board-changing result.** It is not
  auto-loaded. A session ending with the board contradicting what happened is a defect.
- **HK-022** — if a report claims downstream documents were updated, **open them and check.** That
  claim has been wrong twice in one day.

## 9. Escalate rather than settle in session

- The **§0.2 shim-version discrepancy**.
- **X4's retirement outcome**, if it fires.
- Any result implying an `src/` change — **recommendation to the Captain with a number, never work**.
- Any gate that turns out to be **mis-drafted**. 🔴 **Every pre-registration failure so far has been
  an Architect drafting defect and QA executed correctly every time.** Report the void, decline to
  interpret, escalate. That is the correct behaviour and it has protected three results.

---

*Per HK-015 this is Architect → QA; `dev-tasks/*.md` are yours to author. Per HK-014/HK-010 the
Architect commits locally and does not push, merge, or ask. Per HK-011 nothing in items A–C touches
`src/`; item D does and stops at the proposal.*
