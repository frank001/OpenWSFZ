# QA → Architect — G2A-REMEASURE-A results: instrument confound found and disclosed at ROW 0a (no clean G2(a)-only binary exists), Part A reads A2 (no effect), Part B reads B1 (both nulls agree) but is DESCRIPTIVE, not causal, for the same reason

**Author:** QA, 2026-08-25 17:16Z (`date -u`, HK-017). Repo `main` at `6dc1a2d`.
**Spec:** `qa/rr-study/2026-08-23-2127-architect-to-qa-spec-g2a-remeasure-a.md`, **amended by**
`qa/rr-study/2026-08-25-1550-architect-to-qa-null-validity-finding-and-g2a-remeasure-amendment.md` §3.
**Status:** COMPLETE. ROW 0 evaluated in strict order — 0a/0b/0c/0d/0e all **PASS**, but **0a's own
pass carries a disclosed confound that downgrades Parts A and B from a causal isolation of G2(a) to
a descriptive pre-08-13-vs-current-main comparison**, exactly as spec §2.1 anticipates. Part A
(gated) fires **A2** — no material change. Part B (gated, amended) fires **B1** — both nulls agree —
but must be read through the ROW 0a confound. Captain-authorised via "read the board and perform
the tests" (same standing pattern as `GAP-CENSUS-A`); the spec is pre-registered, no-`src/`,
no-rebuild, no-capture, so I did not stop to ask before running it.

**Harness:** `qa/rr-study/g2a-remeasure-a/` (`decode_corpus.py`, `common_g2a.py`, `nulls_pq.py`,
`row0.py`, `part_a.py`, `part_b.py`, `part_c.py`, `run_all.py`), committed alongside this report.
Raw per-decode dumps (real callsign text, NFR-021): `artefacts/2026-08-25-g2a-remeasure-a/`
(blanket-gitignored). Results (counts/rates only): `qa/rr-study/g2a-remeasure-a/results/2026-08-25-6dc1a2d/`.

---

## 0. NFR-021 disclosure

Message text is decoded in-process by `decode_corpus.py` and dumped to
`artefacts/2026-08-25-g2a-remeasure-a/*_decodes.json` (blanket-gitignored, `git check-ignore -v`
confirmed on all four files). `common_g2a.rows_from_dump` reads those dumps, derives
`message_norm`/`has_hash` via `gap-census-a/common.py`'s own helpers, and discards the raw string
immediately — identical discipline to `GAP-CENSUS-A`. `result.json` and this report were grepped
for callsign-shaped tokens before writing (`grep -RnE "[A-Z0-9]{1,3}[0-9][A-Z]{1,4}\b"`, filtered
for report vocabulary) — none found.

---

## 1. ROW 0

| row | check | result | verdict |
|---|---|---|---|
| 0a | both DLLs located, hashed, pinned; version delta enumerated | see §1.1 | **PASS, confound disclosed** |
| 0b | reject count reads higher on L1 than L2 | L1=102,549 vs L2=63,956 | **PASS** |
| 0c | replay fidelity: L1 reproduces ≥0.95 of L0's decodes | 0.9909 (63,829/64,417) | **PASS** — but see §1.2 |
| 0d | determinism: two independent full L2 runs, mechanically diffed | byte-identical on `dll_sha256`, `shim_version`, `n_wavs`, `n_decodes`, `n_native_av`, `native_av_files`, `final_hash_table_reject_count`, `records` | **PASS** |
| 0e | audio integrity: WAV count matches the inventory | 4,971/4,971 | **PASS** |

### 1.1 ROW 0a — no G2(a)-only binary exists on this machine; disclosed confound, not a VOID

I located and SHA256-verified every `libft8*.dll`-family binary I could find on disk:

| candidate | SHA256 | shim | usable as |
|---|---|---|---|
| `OpenWSFZ-8080/8081-capture/libft8.dll` | `f2f30c89…` | 20260033 | **L1** — matches the board's own pre-G2a `main` pin exactly |
| `native/ft8_lib_build/libft8.dll` (current) | `bc8efcf1…` | 20260046 | **L2** — post-G2a, but also post-everything-else since |
| `libft8_cfg1..4.dll`, `libft8_prod_backup.dll` | four distinct SHAs | 20260028/29 | older than L1, no `ft8_get_hash_table_reject_count` export — unusable for this arm either way |

**No candidate reports shim 20260038 (G2(a)'s own build, `c559a049…`)** — it was never built as a
standalone artefact; only L1 (20260033, before it) and L2 (20260046, eleven native commits after it)
exist. Per spec §2.1 this is the explicit disclosed-confound path, not a VOID: I enumerated the full
native-touching commit range between the two shims:

```
9500e03  g2(a): HASH_TABLE_SIZE 256 -> 4096 (shim 20260038)         <- THE measured treatment
3bc2b9d  feat(native): r0-reproducible-native-build (rebuild all 11 objects from source)
0b39805  fix(native): silence dormant monitor.c LOG_INFO stderr spam
6fd9410  chore(native): rebuild Linux binary to shim 20260039
af2f466  feat(ft8): r1-sync-refiner-instrument-validation (AC-3 unresolved, escalated)
aa434cb  feat(ft8): r1b-sync-refiner-instrument-correction
4c73130  docs(ft8): A1 -- correct the withdrawn AC-3 mechanism comment
56ef0c0  feat(ft8): n1-extract-llrs-at-position, shim 20260042
5d3cac5  feat(r2): Route B2 Phase 1 -- ft8_coherent_llr_at diagnostic export
7ed8b0c  feat(r2): Phase B build -- origin fix (B1), fusion normalisation (B2), LDPC export
c3a9ea8  fix(ft8): negative time_offset SNR collapse (shim 20260046)  <- THE current build
```

🔴 **Two of those eleven are not cosmetic: R1/R1b (the sync-refiner instrument), separately measured
on P-LIVE Stage 2 as ROW 3 HARM (`d_ber = -3.45pp`, CI95 [-3.45,-2.87]), and R2 Phase B (a waterfall
time-origin fix plus fusion normalisation).** Both plausibly move decode counts and matching, by a
mechanism that has nothing to do with the hash table. **Per spec §2.1 this downgrades Part A and
Part B from a clean isolation of G2(a) to a descriptive "pre-08-13 vs current main" comparison** —
stated here in full, applied throughout §§3–4 below, not papered over.

### 1.2 ⚠️ A finding ROW 0c's own bar does not surface: offline replay produces ~11% MORE decodes than the live capture did

L1 (offline replay through the pre-G2a DLL) produced **71,530 distinct `(ts, message_norm)` keys**
against L0's (live-captured) **64,417** — replay reproduces 99.09% of what the live daemon actually
decoded (ROW 0c's own statistic, and it clears the 0.95 bar comfortably) but **also produces roughly
7,100 keys L0 never had**, an 11.0% inflation. I checked directly rather than let ROW 0c's pass imply
more than it does: L0's own raw unresolved-hash rate is **6.74%** (4,344/64,417 — matches the
board's "6.75%" figure exactly), but **L1's is 9.65%** — nearly 3 points higher, even though the
reference's own rate is essentially unchanged (6.61% here vs 6.61% recorded). The extra ~7,100
replay-only decodes carry a disproportionate share of hash markers.

Per §3.1's own HK-022 warning, ROW 0c "certifies agreement, not correctness" — this is exactly that
gap made concrete. **I am not treating this as a VOID** (0c's own bar is about reproducing L0, not
about matching its rate, and it passes on its own terms), but the absolute unresolved-hash LEVELS
below (9.65%/9.66%) should not be read as representative of the live production system's rate
(~6.7%, per L0). **The CONTRAST (H = L1 minus L2, ΔB1 = L1's excess minus L2's excess) is what this
arm is built to answer, and the replay-inflation effect is common-mode across L1 and L2 — both are
offline replays through the same harness over the same corpus** — so it should largely cancel in the
contrast even though it distorts each leg's own absolute level.

---

## 2. Part A (PRIMARY, GATED) — H = rate_unresolved(L1) − rate_unresolved(L2)

| quantity | value |
|---|---:|
| rate_unresolved(L1, pre-G2a) | 6,910/71,583 = **9.6531%** |
| rate_unresolved(L2, post-G2a) | 6,913/71,600 = **9.6550%** |
| `H` (point) | **−0.0019 pp** |
| `H` 95% CI (cycle-clustered bootstrap, 2,000 draws, 4,627 cycles) | **[−0.0135 pp, +0.0097 pp]** |

**ROW A2 fires**: CI includes 0 and `CI_hi` (0.0097 pp) is far under the 0.02 bar. **The fix did not
materially change our own text-rendering rate on this corpus.** This directly **misses** the
Architect's own recorded prediction (A1, `H` ≈ 0.03–0.05) — the effect is two orders of magnitude
below the predicted range, and the CI is roughly 15× narrower than the pre-registered resolution
estimate (±0.004, §4.1) suggested, which is itself informative: at ~71,600 decodes over 4,627
clusters the arm had ample power to see an effect of the predicted size, and did not.

---

## 3. Part B (GATED, AMENDED) — does the fix close bucket B1?

### 3.1 The §5.1 discrepancy, reported both ways as required

| | ours | reference |
|---|---:|---:|
| L1 (pre-G2a, this arm) | 9.65% | 6.61% |
| L2 (post-G2a, this arm) | 9.66% | 6.61% |
| 08-08 leg (on record, motivated G2(a)) | 5.5% | 1.7% |

The two corpora disagree in absolute level on both sides, and — per §1.2 above — **this arm's own
9.65%/9.66% are inflated by the replay-vs-live effect and are not comparable to the 08-08 leg's
live-captured 5.5%/1.7% at all.** Not resolved by choosing one; reported as required, not smoothed.

### 3.2 Observed, nulls, and the amended ROW B3/B1/B2 decision

Nulls **P** (i.i.d. resample of whole `(freq_hz, has_hash)` pairs, count held) and **Q**
(density-matched derangement) per the 2026-08-25-1550 amendment §3.1, 200 trials each, run
independently on L1's and L2's own partition. Null **R** (circular shift) computed only as the
diagnostic the amendment permits, laid beside arm #1's figures, **not gated**.

| leg | observed B1 | null P mean (sd) | null Q mean (sd) | null R mean (sd, DIAGNOSTIC) |
|---|---:|---|---|---|
| L1 (pre) | 1,060 | 130.1 (10.2) | 142.4 (12.0) | 91.4 (10.1) |
| L2 (post) | 953 | 128.8 (11.6) | 139.6 (11.2) | 90.4 (10.1) |

| excess B1 | L1 (pre) | L2 (post) |
|---|---|---|
| under null P | 929.95, 95% CI [895.6, 964.3] | 824.21, 95% CI [792.2, 856.3] |
| under null Q | 917.64, 95% CI [881.0, 954.3] | 813.37, 95% CI [781.9, 844.8] |
| under null R (diagnostic) | 968.65 | 862.61 |

**ΔB1 = excess_B1(L1) − excess_B1(L2)**, evaluated independently under each null:

| null | ΔB1 | 95% CI | pp of D-001 | per-null candidate |
|---|---:|---|---:|---|
| P (primary) | 105.74 | [58.76, 152.72] | 0.244 pp | `excludes_zero_positive` |
| Q (mandatory second) | 104.28 | [56.02, 152.53] | 0.240 pp | `excludes_zero_positive` |
| R (diagnostic, not gated) | 106.04 | [60.46, 151.61] | 0.244 pp | — |

**Both nulls agree ⇒ ROW B1 fires** (amendment §3.2): *"The gap itself is smaller than the record
says, by a measured amount."* The two constructions land within 1.4% of each other (105.7 vs 104.3)
— unlike arm #1's Part B, where P/Q-style disagreement on bucket B2 drove ROW B3, **this contrast is
null-robust**.

🔴 **But ROW 0a's confound governs how this may be cited.** A null-robust ΔB1 tells you the P/Q
disagreement is not the reason to doubt this number — it says nothing about whether **G2(a)
specifically**, as opposed to R1/R1b or R2 Phase B, is what moved it. **I am reporting ROW B1 as the
row the amended gate mechanically produces, and reading it as descriptive of "pre-08-13 vs
current-main," not as evidence that G2(a) closes ~0.24pp of the gap.** See §5 for why I think the
more parsimonious read is that it isn't G2(a) at all.

### 3.3 Bucket B2 on L1, re-derived per the amendment (descriptive, NOT gated)

| null | B2 excess on L1 | 95% CI |
|---|---:|---|
| P | 6.71 | [−69.0, 82.4] — includes zero |
| Q | −164.86 | [−246.7, −83.0] — **excludes zero, negative** |

The Architect's own §2.1 analytic claim was "B2 collapses to ~0 under the most faithful null." Null P
(the amendment's own primary, and analytically the closer of the two to "most faithful") **agrees**
— CI spans zero, consistent with ~0. Null Q goes further and reads **significantly negative** — fewer
B2 co-locations than even a density-and-occupancy-matched null predicts by chance. This is not gated
and I am not proposing anything from it, but it is a genuinely new wrinkle worth the Architect's
attention: it would mean our text-difference co-locations are *rarer* than chance once density and
occupancy are both controlled for, which is a different (and stronger) claim than "not an effect."

---

## 4. Part C (descriptive, not gated)

| | L1 (pre) | L2 (post) |
|---|---:|---:|
| `hashTableRejectCount` (full-session, single continuous process) | **102,549** | **63,956** |
| total decodes | 71,583 | 71,600 (diff **+17**, +0.024%) |

**The reject-count drop is the cleanest, least-confounded signal in this whole arm** — nothing else
in the eleven-commit delta touches hash-table sizing, so a 38,593-reject reduction (102,549 →
63,956, −37.6%) is fairly attributed to G2(a) specifically. It shows the mechanism G2(a) targets
(fewer 256-slot placement collisions) is real and working as designed. **It is a different
mechanism from "a decode's message text carries `<...>`"** — a rejected *table insert* means a new
callsign entry couldn't be added; an unresolved *message* means a callsign lookup failed when a
decode was rendered — related but distinct, which is consistent with Part A finding no rate change
even though the reject counter clearly moved.

⚠️ **Decode count differs by +17 (0.024%) between L1 and L2.** G2(a)'s own commit message states the
hash-table fix cannot change the decode count. Given the ROW 0a confound, I am not escalating this
as a defect in G2(a) — 17 decodes out of 71,600 is well within what any one of the other ten
commits in the delta could produce as a side effect — but it is recorded here as required by the
spec rather than silently absorbed.

**SNR-stratum distribution of unresolved-hash decodes** (pinned L1 edges `[-15,-10,-5,2]`), both legs
near-identical in shape:

| stratum (dB) | L1 share | L2 share |
|---|---:|---:|
| (−∞, −15] | 38.5% | 37.5% |
| (−15, −10] | 22.1% | 22.5% |
| (−10, −5] | 16.4% | 16.5% |
| (−5, 2] | 15.0% | 15.3% |
| (2, +∞) | 8.0% | 8.2% |

No stratification by frequency separation to a neighbouring decode was performed, in any form
(spec §6 prohibition respected).

---

## 5. Reading the tension: Part A says no effect, Part B says a small one — and the confound explains why they might not actually disagree

Part A (H, a rate over the WHOLE decode set, same-leg-pair contrast) reads flat. Part B (ΔB1, the
SIZE of a specific reference-matched bucket) reads a small, null-robust positive shift. These are not
computed the same way and are not required to agree, but the more parsimonious explanation, given
§1.1's confound, is that **Part B's movement is not G2(a) at all**. Two candidates from the
eleven-commit delta plausibly explain a change in *which* decodes land near a reference decode
without changing the *overall* hash-marker rate: R2 Phase B's waterfall-origin fix (which shifts
matching positions) and R1/R1b's sync-refiner work (independently measured to change the decode set
at scale, `d_ber=-3.45pp` on P-LIVE Stage 2). **I am not asserting this — it is not something this
arm's design can separate — I am naming it so the Architect does not read ROW B1 as license to
re-cite G2(a) at ~0.24pp without re-running this arm against a binary that isolates it.**

**The Architect's own predictions (A1+B2, deliberately in tension) both miss**, in the same direction
each time: Part A undershoots A1 (no effect, not the predicted 0.03–0.05), and Part B overshoots B2
(a null-robust movement, not "barely moves") — but §1.1/§5's confound means neither miss is
attributable to G2(a) with confidence either.

---

## 6. What this arm does not settle, and what is still queued

- **Does not cleanly isolate G2(a).** No G2(a)-only binary exists; building one is a native rebuild
  and out of QA's scope this session (HK-011) — flagged separately to the Architect/Captain, same as
  the `140 Hz` rung's blocker.
- **Does not replicate on the 08-08 corpus**, which spec §5.1 asks for when the two corpora's rates
  disagree (they do — see §3.1). Not run this session; flagged as undone (HK-004), not silently
  skipped — it would need its own ~70-minute-per-leg replay pass against a different corpus and WAV
  count, on top of the three already run here.
- **Does not resolve** whether the Part B movement is attributable to G2(a), R1/R1b, or R2 Phase B —
  named as the open question in §5, not something this design can separate.
- Per HK-011/014/010: no `src/`/`native/` change, no rebuild, no push, no merge, no
  `pre_merge_check.py`. Committed locally only.
