# `COH-RES-CAND` (#272) acceptance ruling: **FAIL** (U-FAIL); not merged

**From:** Architect · **To:** QA, the Captain · **Date:** 2026-11-08 18:59:03Z (`date -u`) · **Branch:** `arch/coh-res-cand`
**On:**
- QA's report `qa/rr-study/2026-11-08-1900-qa-coh-res-cand-acceptance-report.md` (`qa/same-chain`, local);
- freeze `5770ed8b`, analysis `crc_analyse.py` at `87c5486a`;
- build `b0d01f4f` (v0.69), spec `2026-11-08-1614` with Amendments 1–3 (`14f4e28d`).

Docs only: `git diff --stat origin/main -- src/ native/` is empty.

## §1. Verdict

**FAIL, by the registered rule** (spec §3: FAIL iff N-STOP or U-FAIL).

| row | result |
|---|---|
| B-NAT, B-OFF (40/40), B-WIRE (400/400, R3 389 / R2 11), B-DUP (0), B-AB (0 vs 0) | PASS |
| V1-3N | 399/400. The one cycle (`260930_200230`) is where sol's OFF arm abandoned the fallback and the PC's did not: 5 extra batch-4 rows in A, 0 in `untestable_class`. **A1.4: the night stays.** |
| N-GO | **fires.** NET **+0.504 pp [0.286, 0.717]** (A 10,118 → B 10,180 corroborated of n_ref 12,292) |
| U-FAIL | **fires.** ΔU′_ta **0.0475 [0.0274, 0.0700]** per cycle against the bar 0.021. The lower limit is above the bar: 19 tested_absent outputs in 400 cycles, about one every 21 cycles (≈ 5 min) |

The gain is real: its interval excludes 0 by a wide margin. So is the cost: the wrong-payload proxy's interval sits entirely above the bar, at 2.3× it. The bar was ratified for exactly this trade (COH-GATE-G, 2026-10-28) and was kept for this arm. **No bar is moved after the data.**

**Consequence:** `b0d01f4f` is **not merged**, not even with the setting OFF. B-OFF passed, so it would be harmless, but an OFF setting that failed acceptance is dead code. `pre_merge_check.py` is not run. The branch stays local as the record.

## §2. What the data says about the design (my error, E136)

§0 said "nothing is merged: every candidate offered today is still offered, on the audio it came from". **That was wrong for the residual audio.**
- Today the residual run reads the residual audio with the original list. The build **replaced** that pairing; it did not add to it.
- **B-only:** 150 texts (120 corroborated). **A-only:** 79 texts (58 corroborated). Net +62 corroborated, which is the NET.
- About a third of the gross gain was given back by a design choice I described as lossless.

## §3. Predictions (spec §8), scored

| # | prediction | P | outcome |
|---|---|---:|---|
| CR-1 | no `native/` change needed | 0.75 | ✅ HIT (snapshot before the diagnostics `continue`, `ft8_shim.c:1858–1884` vs `:1893`; QA review) |
| CR-2 | B-OFF and B-WIRE pass on the first commit | 0.75 | ✅ HIT |
| CR-3 | ACCEPT | 0.45 | ❌ MISS (FAIL) |
| CR-4 | NET point ≥ 0.3 pp | 0.45 | ✅ HIT (0.504) |
| CR-5 | U-OK fires | 0.80 | ❌ MISS (U-FAIL) |

**Brier 0.254 over 5.** The miss that matters is CR-5. I reasoned that "no gate is loosened, only better-placed candidates", so there would be no U cost. The data says better-placed candidates on residual audio produce unconfirmed payloads at about 2× the bar. A candidate the original audio never offered is, more often than I assumed, one the fallback should not decode.

## §4. Options for the Captain (none is started without his word)

1. **Close #272 at this result** (recommended). Record it on the issue: +0.50 pp NET at ΔU′ 0.0475, FAIL. The lever exists, but at this design its wrong-decode cost is above the station's bar.
2. **A v2 arm: merged list plus a stricter gate on the residual-list-only rows.**
   - Keeping the original list on the residual audio (a third fallback run, managed only) would recover the 58 A-only rows at **no new U cost**, because they are today's rows.
   - On its own that leaves U-FAIL in place, because the 19 tested_absent come with the new rows.
   - It needs a gate tuned on those rows, which means a pilot, a frozen gate and a fresh night. That is **at least the size of this arm again**, against his "keep the tests small", and the gain ceiling is about +0.5 to +0.65 pp.
3. **Move to the next lever.** The candidates are #273's cheap causal test (oracle subtraction, offline, no `src/`) or #240.

My recommendation is **1, then 3**. Option 2 is a tuning exercise whose most likely outcome is a smaller NET at a U just under the bar.
