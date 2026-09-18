# `NBR-RERUN` — pre-registration: is the near-neighbour exclusion still there on the shipped decoder?

**Architect, 2026-09-16T17:45Z** (`date -u`, HK-017). Branch `arch/e4-channel-impairments`, docs-only;
`git diff --stat origin/main...HEAD -- src/ native/` is empty. **Captain-directed**, 2026-09-16:
*"can't we simply use the recorded audio and tests from that branch and use the latest decoder to see
if it makes any difference?"*

**No station time. No `src/` or `native/` change. No new harness.** It re-runs an existing
Captain-authorised arm's own scenes and seeds against the currently shipped binary.

---

## §0. Why this exists, and the gap it closes in my own assessment

### 0.1 🔴 The gap

My density assessment (`2026-09-16-1730-…-assessment-density-near-neighbour-exclusion.md`) sizes
near-neighbour exclusion at **≈ 5.9 pp** — the largest identified contributor on the board. **Every
decoder number underneath that sizing comes from `F-NBR-A`, measured 2026-08-23 on DLL
`bc8efcf1…b051d7f`.** The shipped binary is now **`91997e38…ad2c6`** (shim `20260051`).

**One hour before writing that assessment I made it mandatory that a closure record the binary it was
closed against** (`E4-STAGE2` §10.7) — and then rested a 5.9 pp sizing on a three-week-old measurement
without checking whether it still holds. **The Captain caught it.** This arm closes it.

### 0.2 Why the binary difference is material, not nominal

Two decoder changes landed between `F-NBR-A` and now:

- **`NHARD40`** (PRs #157–#168) — `nhard` 60 → 40, i.e. **fewer LDPC hard-decision attempts**. That is
  exactly the marginal-decode regime this defect lives in.
- **`PASSBAND-140`** (PRs #175/#176, shim `20260051`) — a **frontend passband** change.

**Neither obviously touches tone-set handling in extraction, which is where Gate A localised the defect
(A2 = extraction locus, not candidate selection). That is a reason to predict no change — not a reason
to skip the measurement.**

### 0.3 🟢 It sidesteps the prohibition question entirely

The assessment's §6 recommendation (a live-concentration check) is **blocked** pending a Captain ruling,
because stratifying live recovery by neighbour distance sits close to retired spectral locality.
**This arm does not go near that.** It is controlled synthetic scenes with established causality — the
safe column of the 2026-08-27 §2 prohibition table. 🛑 **Nothing here may be read as evidence about
live crowding, local or diffuse.**

### 0.4 What it reuses — verified on disk while drafting (HK-018)

| piece | location | note |
|---|---|---|
| harness | `qa/rr-study/f-nbr-a/` | `scene_render.py`, `dll_common.py`, `row0.py`, `part_a/b/c.py`, `run_all.py` — all present |
| scene | `qa/rr-study/scenarios/s8hn-band-scene-highn.json` | committed, Q-prefix synthetic |
| recorded baseline | `qa/rr-study/f-nbr-a/results/f-nbr-a-results.json` | the 08-23 numbers to compare against |
| determinism | `F-NBR-A` ROW 0d | **PASS** — two runs byte-identical. 🟢 **This arm has no statistical noise to fight.** |

🔒 **NFR-021: Parts A and C are 100% synthetic, Q-prefix. `part_b.py` reads a live `ALL.TXT` — DO NOT
RUN PART B.** It is not needed here and is out of scope.

---

## §1. ROW 0 — strict order

| row | check (as code) | on failure |
|---|---|---|
| **0a** old binary reproduces | Retrieve DLL **`bc8efcf1…b051d7f`** (git history at the `F-NBR-A` commit, or `artefacts/`), and re-run C1/C2/C3 with it. Every cell must reproduce `f-nbr-a-results.json` **exactly** (the arm is deterministic). | **STOP.** Without this the comparison confounds *binary* with three weeks of harness/interpreter/library drift, and any difference found would be uninterpretable. If the old DLL cannot be retrieved at all, **say so and stop** — do not proceed with a one-sided comparison. |
| **0b** new binary pinned | SHA-256 of the DLL under test = **`91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6`**, hashed from the file actually loaded, not assumed. Record `nhard`, `max_iters`, `osd_depth` read from the running build. | **STOP** |
| **0c** determinism holds | Two full runs on the new binary produce byte-identical JSON. | **STOP** — a non-deterministic result invalidates the exact-match logic in 0a and the gates below. |
| **0d** scene identity | The scene JSON and seed set are the committed ones, mechanically diffed against `origin/main`. | **STOP** |

**Why 0a changes the verdict (HK-021(k), both branches):** passed, the only variable between the two
result sets is the binary, and a difference means the decoder changed. Failed, a difference means
nothing at all — it could be Python, numpy, or the renderer.

---

## §2. What is measured

Exactly what `F-NBR-A` measured, same scenes, same seeds, on the new binary:

- **C1** — neighbour ablation: `R(F)` with E present vs E removed, 100 trials each.
- **C2** — separation sweep: `R(Δ)` at Δ ∈ {6.25, 12.0, 18.75, 25.0, 31.25, 50, 100} Hz, E at
  1150 Hz/−5 dB, F at −8 dB, 100 trials each.
- **C3** — level sweep: `R(snr_F)` at `snr_F` ∈ {−2, −5, −8, −11} dB, Δ fixed 12 Hz, E at −5 dB.

**Recorded 08-23 values, for reference:** C1 `0/100` → `100/100`. C2 `0, 0, 0, 27, 98, 100, 100`.
C3 `100, 0, 0, 0`.

---

## §3. Readings (first match wins)

| row | predicate | reading |
|---|---|---|
| **G1** | `R(F)` at baseline ≤ 0.05 **and** the first Δ with `R ≥ 0.90` is within one grid step of 31.25 Hz | **UNCHANGED.** The defect survives the current binary. 🟢 **The assessment's ≈5.9 pp sizing stands and density stays the largest item on the board.** |
| **G2** | `R(F)` at baseline ≥ 0.50 | **MATERIALLY REDUCED.** Something already shipped has moved it. 🔴 **The assessment is STALE — every number in it re-sizes. Report and stop; do not re-derive the sizing in this arm.** |
| **G3** | otherwise | **MOVED, NOT RESOLVED.** Re-measure the zone boundary and hand back; the sizing needs redoing at the new geometry. |

**Descriptive, no row:** report all three curves side by side with the 08-23 values, and any cell that
moved by more than the readout quantum (1/100), including cells the gates do not look at.

⚠️ **What this arm cannot detect (HK-022, HK-026).**
- **Whether the defect matters live.** One synthetic geometry. Exposure is the assessment's §2 and the
  live-concentration question is still gated on the Captain's prohibition ruling.
- **Which mechanism** (M1 tone-set contention vs M2 tile artefact). Untouched here, still unresolved.
- **Anything about other neighbour geometries** — one scene, one pair, two sweeps through it.
- 🛑 **A G1 is not evidence that the defect is unfixable, and a G2 is not evidence that anyone fixed it
  deliberately.** Neither shipped change was aimed at this.

---

## §4. Architect prediction, blind, on the record

| prediction | P |
|---|---:|
| **G1 — unchanged** | **0.78** |
| G3 — moved, not resolved | 0.15 |
| G2 — materially reduced | 0.07 |
| ROW 0a passes (old DLL retrievable **and** reproduces) | 0.70 |

**Reasoning:** Gate A localised the defect to **extraction**, and neither `NHARD40` (LDPC attempt
count) nor `PASSBAND-140` (frontend passband edges) touches tone-set handling there. `nhard` 60 → 40 is
*fewer* attempts, so if anything moved in the marginal regime it moved **down** — and `R(F)` is already
at the 0/100 floor and cannot. **The only way G2 fires is if something helped by accident.**

🔴 **Weight accordingly: 1 of 7 on hypothesised calls, and my last mechanism call was backwards**
(`architect-prediction-ledger.md`).

---

## §5. Ownership

| step | owner | gate |
|---|---|---|
| ROW 0a–0d | QA | STOP rows; nothing is compared until all four pass |
| C1/C2/C3 on the new binary | QA | after ROW 0 |
| Acceptance ruling, G1–G3 | Architect | — |

**Queued behind the `E4-STAGE2` census — that runs first.** Nothing here is urgent; the defect has
been there since August and one more day changes nothing.

**HK-025 applies: QA may refuse any row here on mechanical grounds without my agreement.** ROW 0a is
the one I expect trouble from — if the old DLL is not cleanly retrievable, **say so and stop** rather
than improvising a one-sided comparison.
