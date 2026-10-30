# `LATE-SUB`: ruling. L-COST and C-COST. The late primary decode is cheap; the two fallback steps carry the cost

**From:** Architect · **To:** the Captain, QA · **Date:** 2026-10-30 06:55:14Z (`date -u`) · **Branch:** `arch/late-sub`
**On:** QA report `qa/rr-study/results/2026-10-30-late-sub/report.md` (`4e790030`, `qa/refset`, local). Spec `5c33391f` + Amendment 1 `e2f7c5b2`; QA (k) review `809e4f7e`; harness `664c5e97`. Bars re-used by the Captain's "agreed" (2026-10-29T19:22:19Z). Docs only; `git diff --stat origin/main -- src/ native/` is empty.

---

## §1. Validity: accepted

- **V0–V5 pass in both configurations, on all 1,200 cycles** (`check_off.json`, `check_on.json`, `ALL_PASS: true`).
  - V0: the DLL matches the pin.
  - V1: product output is byte-identical to the on-disk R-F4 arms in 1,200 of 1,200 cycles.
  - V2: batches 1, 2 and 3 and the R3 buffer are reproduced exactly.
  - V3: batch 4 is reproduced exactly.
  - V4: 0 snapshots missing; 5 diagnostics-switch checks, 0 differ.
  - V5: 0 abandoned.
- **Buffer levels:** R3 in 1,124 cycles, R2 in 76. L ran in 1,173 cycles; in the other 27 there was nothing new to subtract.
- **The fit list was refused for 279 of its 5,020 entries (5.6 %)**, by the product's own `IsReencodable`/`EncodeMessage`. That matches the product's behaviour, so it is not a deviation.
- **Selection.** QA ran `selection1200.json` (`328c85d4`), the pin from Amendment 1 (E112). QA could not trace `81372df5`. **It is a git commit**, not a file hash: the COH-MULTISET-BUILD selection freeze of 2026-10-24 15:04:50Z. That commit holds the whole-night `selection.json`: 2,882 stamps, file SHA-256 (LF) `53d9ba4e…`. ~~"It is the … `selection.json`"~~ (I named the commit as if it were the file, ledger E115.) **QA confirmed it on 2026-10-30:** `selection1200.json` (`328c85d4`) equals the first 1,200 stamps of that list, element for element, and the warm-up stamp is its first stamp. So the spec and the run name the same night and the same list. The check does not affect validity, because V1 matched the on-disk arms cycle by cycle.
- **NET is conservative** (Amendment 1 D3, hash-state bracketing). Hashed outputs are 1.5 % of L's additions, so the bias is small.

## §2. Verdict (OFF, TEST cycles 401–1,200, n_ref 23,158)

| arm | NET pp [95 % CI] | ΔU′_ta [CI] | H-SHARE | row |
|---|---|---|---:|---|
| C | +0.838 [0.722, 0.953] | 0.035 [0.024, 0.049] | 2.9 % | **C-COST** |
| L | +2.863 [2.637, 3.086] | 0.066 [0.050, 0.084] | 1.5 % | **L-COST** |

These are mechanical rows from the frozen spec (§4). Both arms clear `BAR_G`, and both fail `U_bar_G` 0.021 by their whole CI. As the spec defines L-COST: **the gain is real, and so is its cost; the Captain decides with the table in hand.** ON (descriptive) changes no row: L +3.666, C +0.885, ΔU′ 0.074 / 0.035.

## §3. What the decomposition says (my reading; the rows are QA's)

Rows are published per step and are disjoint, so cost can be attributed step by step. The step ΔU′ figures below are **differences of point estimates**. They carry no CI of their own.

| step | what it is | rows | corroborated | ≈ tested-absent rows (ΔU′ × 800) | NET pp | ΔU′ per pp |
|---|---|---:|---:|---:|---:|---:|
| **C** | fallback on B, B's own candidates | 238 | 194 (81.5 %) | ≈ 28 | 0.838 | ≈ 0.042 |
| **L1** | subtract batch 3 + 4 + C from B, **primary decode** on R4 | 282 | 264 (**93.6 %**) | ≈ 4 | 1.140 | **≈ 0.004** |
| **L2** | fallback on R4, R4's own candidates | 260 | 205 (78.8 %) | ≈ 21 | 0.885 | ≈ 0.029 |
| *reference: R-F4 (shipped)* | residual fallback rows ungated, original candidate snapshot | 522 | 93.3 % | — | 2.103 | ≈ 0.002 |
| *reference: multi-set (shipped)* | | | | | 1.449 | ≈ 0.003 |

**Reading.**
1. **The primary decoder on the late residual is clean.** L1 costs about as much per pp as the two levers already shipped (R-F4 and multi-set).
2. **The cost sits in the two fallback steps that build their own candidate list from a residual buffer** (C and L2). Each costs 10–20 times more per pp.
3. R-F4 also runs the fallback on the residual buffer, but it uses the *original* audio's candidate snapshot, and it is clean.
4. My hypothesis (not shown by this data): candidates found in a residual buffer include subtraction remnants, and the fallback's lower bar turns some of them into unconfirmed decodes.

**Mechanism check on TRAIN (descriptive, NR-TAX tags):**
- **The late round reaches CU-d.** In OFF it recovers 118 of 333 rows, 76 of them in L1, exactly where NR-TAX pointed.
- **CU-u is reached only in ON**: 64 of 228 rows, against 2 of 228 in OFF.
- **The never-offered rows come mostly from C** (111 of 153). They are cheap to find but expensive in U′ (row 1 above).

**Timing is not the constraint on the PC.** L's worst cycle ends at 6.5 s of the 13 s budget. sol's margin is narrower (its fallback ends at 11.1 s), and that is a build-spec row.

## §4. Ledger (scored at ruling time)

| # | prediction | P | result |
|---|---|---:|---|
| LS-1 | V0–V5 pass on the first harness build, no amendment | 0.55 | ✅ HIT |
| LS-2 | L-GO (OFF) | 0.40 | ❌ FALSE (L-COST) |
| LS-3 | NET_L point ≥ 1.0 pp | 0.30 | ✅ HIT (2.863) |
| LS-4 | C-GO (OFF) | 0.35 | ❌ FALSE (C-COST) |
| LS-5 | NET_L − NET_C point ≥ 0.3 pp | 0.45 | ✅ HIT (2.025) |
| LS-6 | ΔU′_ta,L point ≤ 0.021 | 0.70 | ❌ FALSE (0.066) |

**Brier 0.295 over 6.** **Calibration note:** I under-called the yield (LS-3 at 0.30, LS-5 at 0.45) and over-called cleanliness (LS-6 at 0.70). I priced the fallback on a residual buffer as being as clean as R-F4. It is not, once it chooses its own candidates. The "findable localised defect" bias check held the GO calls down (LS-2 at 0.40, LS-4 at 0.35), and both missed.

## §5. For the Captain: options

The levers find real rows: **+2.9 pp for L, more than R-F4's +2.10 on the same cycles**. The cost is **about one extra unconfirmed decode every 15 cycles** (ΔU′ 0.066 per cycle, about 4 minutes of operation). These are decodes WSJT-X tested and found absent, and live they would be shown and uploaded to PSK Reporter. Against today's level of about 0.13 per cycle (COH-GATE-G TRAIN figure, approximate), that is roughly half as many again.

1. **L1′: a late round with the primary decoder only (recommended).** Subtract batch 3 + 4 from the residual buffer, decode once with the primary decoder, and run no extra fallback.
   - **Expected:** NET somewhat below L1's +1.14 pp (C's rows are no longer in the fit), so about +0.8–1.1 pp, at a cost per pp like the shipped levers.
   - 🔴 **The verdict must come from a fresh night.** I picked L1 out because it looked cheap on these TEST cycles, so re-testing it on the same cycles would be reading my own selection. The candidate is `20261022_1949` (R-F4's second night). The refset TEST cycles are reported alongside, descriptively.
   - **Cost:** about 1 h for me to write a short spec, the same harness minus two steps, and a few hours of QA time. If that night only exists on sol, sol must be woken.
   - **If it passes:** a Developer build spec (HK-011), with the sol timing row.
2. **Accept L as measured** (+2.86 pp at +0.066 per cycle), with a build spec now.
   - My concern, stated once: it triples the per-pp cost of anything we have shipped, and the extra decodes go on air.
   - If you choose it, I write the build spec with a live U′ watch row.
3. **Cheapen C and L2 with a gate on the residual-candidate fallback rows** (like COH-GATE-G did for R-F4). The freeze is on TRAIN; the verdict needs a fresh night for the same reason as option 1. This is worth doing only after 1, because it chases the expensive 1.7 pp.
4. **Stop here**: record L-COST/C-COST and return to the other NR-TAX pointers: payload subtraction (0.92 pp), and an oracle subtraction or residue measurement for CS (5.77 pp).

**My recommendation: option 1.** It keeps the half of the gain that costs almost nothing, and it is a small spec on a harness that already passed V0–V5.
