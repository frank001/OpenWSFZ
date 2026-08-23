# G2A-REMEASURE-A — what did the merged hash-table fix actually buy?

**Architect → QA.** Drafted 2026-08-23 21:27Z (`date -u`, HK-017). Captain-directed.

**Status: pre-registration. No `src/` change, no rebuild, no capture run — offline replay of
archived WAVs through two pinned binaries.**

---

## §0. Why this exists

**G2(a) — the callsign hash table, 256 → 4096 — merged to `main` on 2026-08-13 (`9500e03`).
Its effect has never been measured.**

Its own source notes record the symptom it was built to fix: the table keys on a 10-bit bucket
(1,024 distinct values) and places on first probe at `(h10 * 23) % HASH_TABLE_SIZE`, so at
`N = 256` placement **collided 4:1 by construction, before the table was ever full**. Measured:
`hashTableRejectCount` = **35,379** on the 2026-08-08 20 m leg, against 595 across an entire
68-cycle corpus — and **5.5 % of our decodes carrying `<...>` against the reference's 1.7 %**.

🔴 **Every headline D-001 figure in play was captured before that merge.** The replication corpus
is 2026-08-03; the weekend corpora are 08-08 and 08-09; the merge is 08-13. **Nothing in the
programme's evidence base has ever run on a binary carrying the fix.**

Today's census (`GAP-CENSUS-A`, exploratory figures) puts bucket **B1** — reference decodes we
*did* decode but rendered with an unresolved hash — at **693 excess = 1.60 pp** of the gap.
**That is the population G2(a) targets, and it is the second-largest recoverable item on the
board.**

### 0.1 ⚠️ One measured fact that complicates the story, and must not be dropped

On the 2026-08-03 replication corpus, **our unresolved-hash rate is 6.75 % against the
reference's 6.61 %** — near parity, nothing like the 5.5 %-vs-1.7 % gap that motivated G2(a) on
the 08-08 leg.

Both cannot be a complete description. Either the two corpora differ materially, or one of the
two measurements is measuring something the other is not. **This arm is the place that gets
settled, and §5 gates on it.** Do not resolve it by preferring the more convenient number.

### 0.2 What I did not run

I have **not** replayed anything through either binary. The primary statistic is unmeasured by
me and predictions are in §7, blind. (Unlike `GAP-CENSUS-A`, this arm is **not** de-blinded —
prediction scoring is live.)

---

## §1. The question

> **On identical audio, how much of the gap does the merged hash-table fix actually close — and
> does it close bucket B1, or something else?**

Two things make this answerable cleanly and cheaply:

- **The audio already exists.** `artefacts/20260803_live_run_1713/owsfz/wav/` holds **4,971**
  archived WAVs, and the reference leg's own decodes are archived beside them.
- **The change is a pure binary swap.** No capture is needed, and a capture would confound the
  binary change with a different sky.

🛑 **This arm does NOT propose a capture run.** `qa/ARTEFACT_INVENTORY.md:38` flags this corpus
*"D-001 replication corpus — DO NOT PROPOSE A CAPTURE RUN FOR D-001"*, and that flag is
respected: the design is offline replay precisely so no new capture is required.

---

## §2. Design — three legs, one audio set

| leg | binary | purpose |
|---|---|---|
| **L0** | the archived `ALL.TXT` as captured, 2026-08-03 | the historical record |
| **L1** | **pre-G2(a)** DLL, offline replay of the archived WAVs | **instrument-validity control** |
| **L2** | **post-G2(a)** DLL, offline replay of the same WAVs | the treatment |

**L1 exists to answer the question the treatment cannot answer for itself:** does offline replay
reproduce what the live daemon produced? Cycle framing, buffer boundaries and time origin all
differ between a live capture and a replay. **Without L1, any L2−L0 difference is confounded with
"offline replay is not live capture", and the arm reads nothing.**

The measured contrast is **L2 − L1** (same path, same audio, binary is the only difference).
**L1 − L0 is the validity check, not a result.**

### 2.1 Binary identity — pin by SHA256, never by label

| leg | shim | SHA256 |
|---|---|---|
| L1 | pre-G2(a) | to be established and pinned by QA at ROW 0a |
| L2 | post-G2(a) | to be established and pinned by QA at ROW 0a |

The current working-tree DLL is `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`
(shim **20260046**), which post-dates G2(a) (20260038) and is a valid L2 candidate. **The
pre-G2(a) binary must be located and hashed** — candidates on disk include
`native/ft8_lib_build/libft8_prod_backup.dll` and the `libft8_cfg*.dll` set, none of which QA may
assume anything about. The board records the pre-G2(a) `main` pin as `f2f30c89…`/20260033 and
G2(a)'s own build as `c559a049…`/20260038.

🔴 **`FT8_SHIM_VERSION` identifies nothing** — the version label has collided twice across five
unmerged branches. **Assert every leg's SHA256 against a pre-registered manifest; never infer a
binary from a label.**

⚠️ **L1 and L2 must differ ONLY in G2(a).** If the only available pre-G2(a) binary also differs
in other shim versions, that is a **disclosed confound**, must be stated in the report with the
version delta enumerated, and downgrades the gate to descriptive. **Do not paper over it.**

---

## §3. ROW 0 — preconditions, strict order

| row | check | bar | consequence |
|---|---|---|---|
| **0a** | Both DLLs located, hashed, pinned; version delta between them enumerated | both SHAs recorded; delta stated | **VOID** if the pre-G2(a) binary cannot be located or hashed. |
| **0b** | `ft8_get_hash_table_reject_count()` responds on both legs, and reads **higher on L1 than L2** on the same audio | `reject(L1) > reject(L2)` | **VOID.** If the counter does not move in the expected direction, the two binaries do not differ in the way claimed and nothing below is interpretable. |
| **0c** | **Replay fidelity:** L1's decode set reproduces L0's | **≥ 0.95** of L0's decodes present in L1 (matched on `(cycle, message)`) | **VOID.** Below this, offline replay is not reproducing live capture and L2−L1 measures the harness. |
| **0d** | Determinism: two independent full L2 runs, result JSON **mechanically diffed** | byte-identical | **VOID.** Diffed, not asserted. |
| **0e** | Audio integrity: WAV count and per-cycle coverage match the inventory | 4,971 WAVs, `--check` clean | **VOID.** |

### 3.1 ⚠️ What ROW 0c cannot detect (HK-022)

If replay and live capture share a defect — a common time origin, a shared framing convention —
0c passes while both are wrong together. It certifies **agreement**, not **correctness**. State
that in the report; do not upgrade 0c into a claim that the replay path is validated in general.

⚠️ **Carry the +0.16 s waterfall-origin correction** if any position-driven extraction is used
(B-orig-A, CONFIRMED 2026-08-21). Apply it **uniformly** across all legs or not at all.

---

## §4. Part A (PRIMARY, GATED) — what the fix bought

**Statistic:** `H` = the reduction in unresolved-hash decodes, as a share of our own decodes:

```
H = rate_unresolved(L1) − rate_unresolved(L2)
```

where `rate_unresolved` is the fraction of a leg's decodes whose message text carries an
unresolved-hash marker. Signed (HK-021(l)); 95 % CI by **cycle-clustered** bootstrap.

| row | condition | consequence |
|---|---|---|
| **A1** | `CI_lo > 0.02` | **The fix works and the programme's evidence base is stale.** Every D-001 figure captured pre-merge understates our text quality, and the headline gap must be restated on a post-fix basis before any further DSP arm is funded. |
| **A2** | `CI` includes 0, or `CI_hi < 0.02` | **The fix did not materially change text rendering on this corpus.** Bucket B1 is then not primarily a sizing problem, and the T3 callsign-character population inherits the question. |
| **A3** | `CI_hi < 0` | 🔴 **Regression** — the fix made text rendering worse. Escalate immediately; do not proceed to Part B. |

### 4.1 Resolution, computed while drafting (HK-021(m))

Prior: 6.75 % unresolved on this corpus (L1's expected level). At 4,614 cycles and ~14 decodes
per cycle ≈ 64,000 decodes in ~4,600 clusters, the expected 95 % half-width on a difference of
proportions is **≈ ±0.004**. **The 0.02 bar is resolvable unless `H` lands inside
[0.016, 0.024].** A2 is a real and expected outcome, not a failure.

Readout quantum (HK-021(o)): a ratio of integer counts over ~64,000 decodes ⇒ ~1.6×10⁻⁵, three
orders below the half-width. Sampling-limited, not readout-limited.

---

## §5. Part B (GATED) — does it close bucket B1?

Text quality improving is not the same as the **gap** closing. Recompute the `GAP-CENSUS-A`
partition with L2 in place of L0 and read bucket B1.

**Statistic:** `ΔB1` = B1's pp-of-gap on L1 minus B1's pp-of-gap on L2, cycle-clustered.

🔴 **The null is mandatory**, exactly as in `GAP-CENSUS-A` §5.2 — ≥ 200 circular-shift offsets,
computed separately for the hash and non-hash sub-buckets, plus a second null of different
construction. **A co-location count without a null is not a result**; that error cost the
Architect a factor of two earlier today and is disclosed there in full.

| row | condition | consequence |
|---|---|---|
| **B1** | `ΔB1` CI excludes zero and is positive | **The gap itself is smaller than the record says**, by a measured amount. Restate before funding further DSP work. |
| **B2** | `ΔB1` CI includes zero while Gate A fired A1 | **Text improved but the gap did not** — our `<...>` decodes were not the ones the reference was resolving. A genuinely informative negative; report it as such. |
| **B3** | ROW 0e of `GAP-CENSUS-A`'s null adequacy standard not met | Unresolved. Report counts and null; propose nothing. |

### 5.1 The §0.1 discrepancy must be settled here

Report our unresolved-hash rate **and the reference's** on this corpus for both legs, alongside
the 5.5 %-vs-1.7 % figure from the 08-08 leg. **If the two corpora disagree, say so and do not
choose between them** — replicate on `20260808_live_run_0016-8080` as a secondary leg and report
both.

---

## §6. Part C (DESCRIPTIVE — NOT GATED)

`hashTableRejectCount` on both legs; the distribution of unresolved-hash decodes by SNR stratum
on X1/X2's **pinned** L1 edges `[-15, -10, -5, 2]` (never re-derived); and total decode counts
per leg — the fix is documented as **unable to change the decode count**, so any difference in
total decodes is a finding that contradicts the source and must be escalated rather than
absorbed.

🛑 **No stratification by frequency separation to a neighbouring decode, in any form, under any
name** — that is the retired spectral-locality metric. Refuse under HK-025 if a leg drifts there.

---

## §7. Architect predictions — blind, on the record

| gate | prediction | confidence |
|---|---|---|
| **A** | **A1**, `H` ≈ 0.03–0.05 | moderate |
| **B** | **B2** — text improves but bucket B1 barely moves, because our 6.75 % and the reference's 6.61 % are near parity on this corpus, which suggests our unresolved decodes are largely ones the reference did not resolve either | low |

⚠️ Predictions A and B are deliberately **in tension** — I expect the fix to work and the gap not
to move much. If that combination fires, the honest reading is that G2(a) was a real defect fix
that is **not** worth 1.60 pp of gap, and the ledger's bucket B1 estimate needs revising down.
**Do not smooth that into a cleaner story.**

---

## §8. Scope

- 🛑 No capture run. No `src/` change. No rebuild. No push, no merge (HK-011, HK-014, HK-010).
- 🛑 No spectral-locality metric, under any name.
- 🛑 Does not authorise a further hash-table change — including the still-absent eviction policy
  (F-001 D3). A2/B2 would make eviction *interesting*; it would not make it authorised.
- Does not subsume `GAP-CENSUS-A` (which establishes the partition) or `OSD-FA-A` (which audits
  our exclusive decodes). Distinct questions.

---

## §9. Reporting and stopping

1. ROW 0 first, strict order, stop at the scope each row names.
2. Report `L1 − L0` as a **validity check**, never as a result.
3. Never report a co-location count without its null in the same sentence.
4. Cluster counts throughout, never bare row counts.
5. Disclose every correction in full.
6. Stop at the gate. No push, no merge, no `pre_merge_check.py`.
7. 🔴 **HK-025 stands: QA may refuse this spec without my agreement.** If any ROW 0 row cannot
   change a verdict, name it, evaluate both branches, and stop — no partial run.
