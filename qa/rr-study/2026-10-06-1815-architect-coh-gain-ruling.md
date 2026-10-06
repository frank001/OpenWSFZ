# RULING — `COH-GAIN` (A′ step 1): **COH-OPEN**. Coherent bit formation is a real but *complementary* extractor, and it helps most in crowded cycles. A sign-corrected OSD is not a lever

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-06 18:16Z (`date -u`, HK-017)
- **Branch:** `arch/coherent-limb2`. Docs only: `git diff --stat -- src/ native/` empty.
- **Reviewed:** QA report `qa/rr-study/results/2026-10-06-coh-gain/report.md` + `analysis.json` @ `c7402b49` (`qa/coh-gain`, local); V4′ manifest `4b8d0089`; per-row numeric data `qa/rr-study/results/2026-10-06-coh-gain-run/rows.csv` (read, numeric only).
- **Against:** `2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md` + Amendments 1–3. `BAR_G` = 1.0 pp, ratified before any datum.

## 1. Verdict: COH-OPEN, accepted

**`NET_C3` = +1.33 pp of WSJT-X's (encodable) decodes, 95 % CI [+0.57, +2.03]** (9,522 rows, 309 cycles, block 8, 39 blocks). `CI_lo` < 1.0 ≤ `CI_hi` ⇒ **COH-OPEN**. Rescaled to all WSJT-X decodes (636 unencodable rows credited zero): +1.25 [+0.54, +1.90].

**Validity:** V1, V2 (b′), V3 (edge 2.2 %), V5 (0/300) and **V4′ (G = 0.969 on P1, n 5,521)** all PASS. V4′'s descriptives back QA's cause: G reads 0.5 % of the batch-2-only rows, and the replay's batch-2 share is 17.6 %.

**Recomputed by the Architect from `rows.csv` (HK-018):**

- successes G 5,367 / C1 4,654 / C3 5,494 / C3\* 5,544 / GO 5,368 / C3O 5,519;
- `NET_C3` = +1.334 pp; my own cycle-block bootstrap gives **[0.58, 2.05]**;
- C3 gains 500, losses 373;
- **on live misses (n 2,825): 361 gains and 7 losses. On live hits (n 6,697): 139 gains and 366 losses.**
- **GO:** 1 true OSD recovery and 271 CRC-valid wrong payloads on 4,155 BP-fail rows. **C3O:** 25 true and 34 wrong.

All match QA.

🔴 **First-paragraph flag, as QA reports:** the top 5 blocks carry 50.4 % of the positive gain (237 of 309 cycles carry a non-zero net). The gain is real across the night (CI excludes 0 by a wide margin), but it leans on the busiest stretches. That is consistent with §2's load gradient, not with a harness artefact.

QA's two disclosures are accepted as handled: the `fine_sync` padding crash (`c2815cd3`, V5 covers the rows written before the fix), and the overwritten and restored `rows.json` (SHA equal to the pin, plus a regression test). QA also saw the NET before my V4 ruling, which I made blind.

## 2. What it means, and where my review was wrong

**The shape is not the one my review assumed.** The review (§4) priced A′ as a **uniform SNR shift** of our decode curve. The measured G and C3 curves differ by a **median −0.08 dB**, so there is no shift. Instead C3 is **complementary**:

- it recovers **12.8 % of the signals we currently miss** (361 of 2,825 live misses, with 7 losses there);
- it loses **5.5 % of the signals we currently get** (366 of 6,697 live hits);
- its net gain **rises with crowding**: by load quintile Q1…Q5 it is −0.68, 0.00, +1.91, +1.68, **+3.43** pp; by SNR it is ≈ 0 below −6 dB and +2 to +3 above.

**Reading (best fit, not tested here):** coherent 2/3-symbol metrics plus per-signal fine sync work like a **narrower, better-aligned filter**. They pull out signals that a crowded spectrogram smears, which is the **interference-limited loss GAP-LOCATE located** (strong signals lost at the right position, with D5's "another transmission dominates the cell"). In my review I wrote that coherent combining "is a noise-limited sensitivity gain, a different mechanism". **That was wrong in kind.** On real audio its value is in the crowding, not the noise. The Captain's overrule of my "park" recommendation is vindicated by the measurement.

**Order 1 alone (C1) is −7.49 pp**, much worse than what we ship. So **the 2- and 3-symbol coherent groups are essential**, and fine sync alone does nothing useful. C3\* (oracle sync) adds only +0.53 pp over C3, so the data-free estimator is close to good enough. Step 3 should not spend effort there.

## 3. The design this points to (POST-HOC: a lead to register, not a result)

Because the two extractors fail on **different** signals, the obvious build is **C3 as a second chance when the shipped extractor fails**, not C3 instead of it. At WSJT-X's positions, that union is **+5.25 pp over G** (QA: CI [4.69, 5.77]).

🛑 **It is post-hoc**: it was found by looking at this data. It **may not be cited as a result**, and it has a visible cost. On the 4,155 rows where G fails, C3 returns **198 CRC-valid WRONG payloads** against its **500** correct ones. Some may be genuine other stations sharing the cell (not separated). A fallback design needs a false-decode watch from the start.

## 4. The OSD sign fix (#215): not a lever at true signal positions

- **GO vs G = +0.011 pp [0.000, 0.033].** Corrected OSD recovered **1** true payload and produced **271 CRC-valid wrong payloads** (6.5 % of BP-fail rows). At `nhard` 40 / corr 0.10, a **working** OSD on our LLRs is mainly a **false-decode generator**. Its gate was calibrated on inverted output and is far too loose for a correct one.
- **On C3's LLRs it does slightly better** (+0.26 pp; 25 true vs 34 wrong). Better bits make OSD useful, as theory says. That is a step-3 detail, not a standalone lever.
- **The shipped (inverted) OSD** accepted a codeword on 17 rows, **none with the sent payload**: false decodes at real positions, as the sign finding predicts.
- ⇒ **For #215 the evidence now favours "OSD off" over "OSD fixed"** for the shipped extractor. Whether switching it off **gains** anything (fewer false decodes subtracted before the residual pass) is the `nhard` = 0 replay I offered earlier. The Captain deferred it until this run finished. It is his call now.

## 5. Next step under COH-OPEN (the Captain's decision)

Spec §6: add cycles under the same rows, or stop. **My recommendation: extend, on fresh cycles, and register the fallback design before its data exist.**

- **Cycles:** positions **`i mod 10 == 5`**, not `== 7` as the spec says. `== 7` hosted the 50 pilot rows, whose outcomes QA has seen. `== 5` is untouched. ≈ 310 cycles, ≈ 10 min wall on 4 workers.
- **Primary (unchanged):** `NET_C3` pooled over both samples (≈ 618 cycles), same rows and `BAR_G`.
- **Registered now, before the data, as a SECONDARY row on the fresh cycles only:** `NET_U` = (G ∪ C3 success − G success)/N, where C3 is consulted only on rows where G fails. **U-GO** iff `CI_lo(NET_U)` ≥ 1.0 pp (`BAR_G`: per HK-038, its number comes from the Captain's 2026-10-06 ratification of what justifies a native build; it is not carried from older data). **Report alongside it, descriptive:** the fallback's CRC-valid wrong payloads per row.
- **If either row fires GO,** the next step is step 2 (the ROW 0g-2 re-check) and a step-3 build spec for **C3 as a fallback extractor**: flag OFF by default, with an FP watch and a noise leg in its replay.

## 6. Predictions, scored at ruling time (ledger rule 1)

| # | prediction | P | class | outcome |
|---|---|---:|:---:|---|
| CG1 | COH-GO at 2.0 | 0.35 | H | ❌ MISS (OPEN at 2.0 as well) |
| CG2 | COH-STOP at 2.0 | 0.35 | H | ❌ MISS |
| CG1′ | COH-GO at 1.0 | 0.45 | H | ❌ MISS (OPEN) |
| CG2′ | COH-STOP at 1.0 | 0.25 | H | ❌ MISS (OPEN) |
| CG3 | `NET_C3` in [0.5, 4.0] pp | 0.55 | H | ✅ HIT (+1.33) |
| CG4 | C3\* − C3 ≥ 1.0 pp | 0.50 | H | ❌ MISS (0.53) |
| CG5 | losses ≥ 1 % of rows | 0.60 | H | ✅ HIT (3.92 %) |
| CG6 | V2 passes first time | 0.55 | C | ❌ MISS (already scored) |
| CG7 | `NET_GO` ≥ +0.5 pp | 0.45 | H | ❌ MISS (+0.011) |
| CG8 | V4′ passes | 0.75 | C | ✅ HIT (0.969) |

**The informative miss is not a row.** My review's mechanism (an SNR shift, so "park it") was wrong, and the Captain's instinct was right. The ledger's known bias ran the **other** way this time: I under-predicted a lever, because I priced it with the wrong model.
