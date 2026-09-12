# `THRESH-A` — pre-registration: at the isolated weak-signal threshold, is the loss in finding the candidate or in reading its bits?

**Architect, 2026-09-12 17:24Z** (`date -u`, HK-017). Branch `arch/thresh-a` (cut from `origin/main`
`19737b32`). Docs-only; `git diff --stat origin/main -- src/ native/` empty.

**Status: cleared to run.** The Captain, 2026-09-12: *"proceed with your recommendations"*. The
recommendation named this arm as independent of `LIVE-GAP-NOW` and runnable alongside it. The bars
(§3.4) are Architect-set and gate no product change, only which follow-up arm is licensed.

---

## §0. What this is, why now, and what it reuses

**The deficit.** On one isolated signal in white noise, the S1–S8 battery's −21 dB rung (S1b P1)
reads **OpenWSFZ 0/24 vs WSJT-X 13/24 over 8 sweeps**, and nhard 60 → 40 does not change it (board,
2026-09-12 decode-gap review). That makes it the cleanest deficit we have. There is no neighbour,
no crowding, no channel and no reference-decoder ambiguity, and it is deterministic enough to have
held for 8 sweeps. **WSJT-X's 13/24 is the existence proof** that the signal is decodable.

**What we already know, without measuring anything new:**
- `NT` (`2026-09-12-0945-…`) ran the current binary in-process on an isolated single-station AWGN
  ladder. OpenWSFZ's 50% point is **−20.19 dB (nominal renderer units)**, and
  **all 710 genuine near-threshold decodes are BP-path, 0 OSD**, identical at `nhard` 60/40/0. ⇒ **The
  threshold is lost upstream of OSD.** No OSD or `nhard` change can move it.
- That leaves two places it can be lost, and nobody has split them at the isolated threshold:
  - **L-CAND:** the signal's cell is never tried or accepted as a candidate (sync score, the
    acceptance threshold, ranking, pass logic);
  - **L-BITS:** the cell is tried, but its non-coherent, single-symbol, magnitude-only LLRs are too
    noisy for BP.
- They lead to completely different remedies. L-CAND means candidate-stage logic, which may be
  cheap. L-BITS means bit formation, and the only remedy on the shelf is the coherent extractor,
  which isn't shippable (ROW 0g-2 still fires).

**Why this is not a re-read of a closed gate:**

| earlier arm | its population and question | this arm |
|---|---|---|
| RC1 (08-07) | **live** misses pooled over all SNR, "is a candidate present near the miss?" | isolated synthetic threshold, "does the **true** cell decode when forced?" |
| C-GAP-D (08-22) | extraction headroom against the **live D-001 gap** | no D-001 claim; the isolated threshold only |
| F-NBR-A (08-23) | the same forced-read method, on **near-neighbour** station F | a different population (no neighbour) |

🛑 **C-GAP-D's ruling stands untouched:** the coherent-LLR limb may not be described as a D-001
treatment. If this arm reads T2, §3.6 routes any B2 question to the Captain on **sensitivity**
grounds, with its own acceptance test. It is not a D-001 re-read.

**Reused, not rebuilt (HK-018):**

| what | where |
|---|---|
| scene, seeds, input contract, genuine predicate | `qa/rr-study/osd-fa-a/part_nt.py`: `MESSAGES`, `compute_seed('NHARD40-NT', rung_index, trial_index)`, `SR.render_scene`, `normalise_rms(…, 0.20)`, `is_true` + `FREQ_TOL_HZ = 4.0` |
| pinned decoder | `qa/rr-study/osd-fa-a/dll_pin.load_decoder(verify=True)`: `6b2e16a6…4f85c`, shim `20260050` |
| forced read | `qa/rr-study/f-nbr-a/row0._forced_success(dec, pcm, freq_hz, true_message, true_dt_s)`: `ft8_extract_llrs_at` at `dt + 0.16 s` (`dll_common.extraction_time_offset_s`, the B-orig-A one-symbol origin correction), then `ldpc_decode_llrs(max_iters=50, osd_depth=2)`, then CRC plus **payload equality with truth** |
| committed baseline to reproduce | `NT` result §6 (per-rung `p60`, n = 250) |

**Feasibility checked while drafting:** `ft8_extract_llrs_at` **snaps** the requested position to
production's own lattice (`ft8_shim.c:1856`ff, `lroundf` on `raw_bin × osr`). NT's four frequencies
and `dt = 0` map onto that lattice **exactly**: 700/1300/1900/2500 Hz are multiples of 3.125 Hz,
and `0.16 s` is two time sub-steps. ⇒ **A forced read at the true position is a read at the right
cell, with no sub-lattice gain mixed in.** That is what makes this a candidate-vs-bits split and not
a lattice experiment. ROW 0c asserts it in code.

⚠️ **No `THRESH-A` datum exists.** I have run nothing. The only numbers in this document are NT's
committed table and the resolution arithmetic in §3.5.

---

## §1. Scene

`NT`'s scene, **verbatim**: one Q-prefixed station per cycle, rotating `MSG-01/02/04/05` at
700/1300/1900/2500 Hz by `trial mod 4`, `dt_s = 0.0`. Ladder −26.0 to −16.0 dB (nominal renderer
units) in 0.5 dB steps, 21 rungs × 250 trials. Seed `compute_seed('NHARD40-NT', rung_index,
trial_index)`, input `normalise_rms(render_scene(seed), 0.20)`.

🛑 **Nominal renderer units. Never compare them numerically with S1b's −21 dB rung.** S1b goes
through a playback chain with its own SNR definition. This arm uses S1b only as the reason to look.

## §2. Legs (identical PCM, one process, one thread)

| leg | call | params | recorded per cycle |
|---|---|---|---|
| **P** (production) | `decode_all(pcm)` | `(10, 0.10, 60)`, NT's control leg | genuine present (0/1), number of decodes, number false |
| **F** (forced) | `_forced_success(dec, pcm, f_injected, msg_injected, true_dt_s=0.0)` | n/a | `success`, `crc_ok`, `path` (0 BP / 1 OSD / −1 none), `ldpc_errors`, `rc` |

🔴 **The primary counts forced successes on the BP path only (`F_BP`: `success ∧ path == 0`).**
`ldpc_decode_llrs` runs OSD at depth 2 with no production `nhard`/`corr` acceptance gate. Counting a
forced OSD accept would credit the forced leg with decodes production is never allowed to make. NT
§5 shows production's threshold decodes are 100% BP, so BP-only is the like-for-like comparison.
Report forced OSD-path successes separately (§3.7).

Persist per-cycle records for both legs, so a second process can diff them (ROW 0b) and every
number in the report is reproducible from the JSON. Roughly 10,500 native calls, the waterfall
being built in both. Expect 1–1.5 h serial; supervise it (HK-013 / HK-023).

## §3. Measurement

### 3.1 Primary rung set, fixed now from a committed table (HK-021(y))

**`R*` = {−21.0, −20.5, −20.0, −19.5, −19.0} dB**: the NT rungs with `0.05 ≤ p60 ≤ 0.95` in NT's
committed §6 table (`p60` = 0.120, 0.312, 0.620, 0.828, 0.936). This is fixed from a committed
document, before any forced datum, and never recomputed from this arm's own P-leg.

### 3.2 Definitions (predicates as code, HK-021(r))

- `genuine_P(c)` = NT's predicate: `is_true(payload) ∧ |f − f_inj| ≤ 4.0 Hz`.
- `M` = cycles in `R*` with `¬genuine_P` (**production misses**). `H` = cycles in `R*` with
  `genuine_P` (**production hits**).
- `F_BP(c)` = `success ∧ path == 0` on leg F.
- **`R_forced = |{c ∈ M : F_BP(c)}| / |M|`**, the gate statistic, with a Clopper–Pearson 95%
  interval.
- `R_ctrl = |{c ∈ H : F_BP(c)}| / |H|`, the positive control.

### 3.3 ROW 0: strict order

| row | check (as code) | on failure |
|---|---|---|
| **0a** | `dll_pin.load_decoder(verify=True)` passes (SHA `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c`, shim `20260050`) | VOID |
| **0b** | P-leg genuine counts per rung equal NT's committed counts on **all 21 rungs**: `[0,0,0,0,0,0,0,1,0,5,30,78,155,207,234,248,250,250,250,250,250]` (−26.0 → −16.0). If NT's `nt.json` is on disk, also diff the 60-leg arrays element-wise, and state which check ran. | STOP (not the same scene or the same binary) |
| **0c** | For each of the four `(f_inj, 0.0 + 0.16 s)`: `raw_freq_bin × 2` and `raw_time_bin × 2` (as computed in `ft8_extract_llrs_at`) are integers to within `1e-6` | STOP (the forced read would carry sub-lattice gain) |
| **0d** | positive control: `CP95_lo(R_ctrl) ≥ 0.90` | VOID (a forced read that can't reproduce production's own hits says nothing about its misses) |
| **0e** | zero harness faults (`rc ≠ 0`) on leg F, every rung | STOP |
| **0f** (power, routes) | `|M| ≥ 300` | Top up `R*` rungs in 250-trial blocks, continuing each rung's trial counter so seeds never repeat, at most 2 blocks. Still short ⇒ **T3**. |

**Why each row changes the verdict (HK-021(k)):**
- **0b:** if it fails, `R*` (picked from NT's table) no longer marks the threshold of *this* run.
- **0c:** if it fails, T1 could fire on sub-lattice gain and not candidate-stage loss (T1 would be
  misread).
- **0d:** if it fails, T2 could fire on a broken forced pipeline (T2 would be misread).
- **0e:** a fault is neither a success nor a failure. It would bias `R_forced` in an unknown direction.

⚠️ **What ROW 0 cannot detect (HK-022):** a renderer whose nominal SNR scale is off by a constant.
That shifts the dB labels, not `R_forced`, because `R*` is defined on the measured curve. It also
can't see anything about **off-lattice** signals, which is §4.

### 3.4 Gate rows (first match wins)

| row | predicate | reading |
|---|---|---|
| **T2** | `CP95_hi(R_forced) < 0.20` | **L-BITS dominates.** At least 80% of threshold misses don't decode even when handed the right cell. |
| **T1** | `CP95_lo(R_forced) ≥ 0.50` | **L-CAND dominates.** Most threshold misses decode when handed the right cell. |
| **T3** | otherwise, or ROW 0f short | **Both loci contribute.** |

The rows are mutually exclusive (`hi < 0.20` and `lo ≥ 0.50` cannot both hold).

### 3.5 Resolution, computed while drafting (HK-021(m))

`|M|` expected from NT's table: 220 + 172 + 95 + 43 + 16 = **546**. `|H|` = **704**. Clopper–Pearson,
exact (scipy `beta.ppf`):

| `|M|` | T1 needs `k ≥` | T2 needs `k ≤` |
|---:|---:|---:|
| 300 (0f floor) | 168 (0.560) | 46 (0.153) |
| **546 (expected)** | **297 (0.544)** | **90 (0.165)** |

At `|M| = 546` the half-width is about ±4 pp near 0.5 and about ±3.5 pp near 0.2. **T1 needs a true
`R_forced` of about 0.55 or more. T2 needs about 0.165 or less.** Anything between reads T3, which is
correct. ROW 0d at `|H| = 704` needs `k ≥ 650` (0.923). Readout quantum: `1/|M|` ≈ 0.18 pp, far
below every bar (HK-021(o)).

**Why 0.50 and 0.20:** T1 says "the bigger lever is the candidate stage", and a majority is the
natural cut. T2 says "candidate-stage work cannot be the threshold remedy", which needs the
unreadable share to be overwhelming (≥ 80%). F-NBR-A used 0.20 for the same reading. T1 sits at 0.50,
not F-NBR-A's 0.80, because its consequence is only a follow-up measurement arm (§3.6), not a
treatment.

### 3.6 Consequences

- **T1** ⇒ licenses **exactly one** follow-up pre-registration, which locates the loss inside the
  candidate stage: sync-score distribution at the true cell vs the acceptance threshold,
  rank under the unchanged budget, and pass-1/pass-2 logic. §3.7's `Δ50` sizes the prize in dB.
  🛑 **Not** a licence to raise caps or add passes (closed twice). **Not** OSR 2→4 (that needs its
  own FP-primary pre-registration). No `src/` change is licensed by this arm.
- **T2** ⇒ no candidate-stage work may be called a threshold treatment. The Architect writes the
  Captain a one-page decision note: the isolated-threshold loss is in bit formation, and the only
  remedy on the shelf is the coherent extractor (not shippable; ROW 0g-2). Whether to reopen Route
  B2 **on sensitivity grounds** is his call. Any reopening carries its own acceptance test and is
  **not** a D-001 claim (C-GAP-D stands).
- **T3** ⇒ report both shares per rung, with `Δ50` sizing each. Nothing is licensed. Any follow-up is
  a new proposal.

### 3.7 Descriptive (no row, report all)

- Per rung, all 21: `p_P`, `p_F_BP`, `p_F_any` (including OSD), each with n.
- **The two 50% points** by linear interpolation, `x50(P)` and `x50(F_BP)`, and **`Δ50 = x50(P) −
  x50(F_BP)`** in nominal dB. That is **the sensitivity a perfect candidate stage would buy on
  on-lattice signals**, in operator terms.
- On `M`: the share of forced successes by path (BP/OSD), the `ldpc_errors` distribution for forced
  successes and for failures, and the share with `path = −1`.
- On `H`: the count where F fails although P succeeded (the ROW 0d complement), split by rung.
- False decodes per cycle on leg P, which should reproduce NT's `0.1385`/cycle at 60 (a cheap
  cross-check, not a row).

---

## §4. What this arm does NOT do, and cannot see

- 🛑 **No `src/` or `native/` change, no rebuild, no capture, no push, no merge** (HK-011 / HK-014 /
  HK-010).
- **On-lattice only, by construction.** Real signals land uniformly off-lattice. What that costs at
  threshold is T1-era territory (`G`, direction confident and magnitude poorly determined), and it
  is **not reopened here**. A T1 reading is about on-lattice signals.
- **No WSJT-X claim** (HK-026). WSJT-X is absent from this arm. S1b is the reason, not a comparator.
- **Isolated station only:** no neighbour (NBR-A is closed, and the near-neighbour family is a
  different question), no crowding, no E4 channel effects, only the four rotated message types.
- Spectral locality stays barred. `nhard` is not moved (NT already showed it is inert here).
- **NFR-021:** Q-prefix synthetic messages only. Report counts and rates. Scan anyway.

## §5. Architect predictions: blind, on the record, before any datum

| row | probability | reasoning |
|---|---|---|
| **T3** | 0.45 | At threshold both loci plausibly bite: a sync score near its acceptance bar, and single-symbol magnitude LLRs that give up a dB or two to coherent metrics. A mixture is the default. |
| **T1** | 0.30 | ft8_lib's Costas sync is a magnitude sum over 21 symbols and should find a cell BP can already read. If the acceptance bar is conservative, forced reads convert. |
| **T2** | 0.25 | F-NBR-A's forced read at station F converted 0/100, but that was a neighbour-contaminated cell. Here the cell is clean, which argues against T2. |

**Point prediction:** `Δ50 ∈ [0.3, 1.5]` dB. **ROW 0d:** PASS, probability 0.85. NT §5 already read
710/710 hits on the BP path at the *reported* position. The true position should do no worse, and the
residual risk is the origin correction at `dt = 0`. My recent categorical calls are poor. Weight
accordingly.

## §6. Running order

| step | status |
|---|---|
| This spec | ✅ Captain: *"proceed with your recommendations"* |
| ROW 0a → 0c (static) → run both legs → 0b/0d/0e/0f → T-row → §3.7 | QA, in that order. Supervise it (1–1.5 h). |
| Report, committed locally | QA. Push/PR needs the Captain's go (HK-033). |

Independent of `LIVE-GAP-NOW`: different corpus, binary unchanged, no shared state. They can run in
either order or together, **but not in one process** (the hash table is process-global, and
`LIVE-GAP-NOW` loads a second DLL).

🔴 **HK-025 is available in full.** If any row here is a diagnostic dressed as a gate, name it,
evaluate both branches, and refuse it.
