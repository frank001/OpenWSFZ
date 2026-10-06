# SPEC — `COH-GAIN` (A′ step 1): how many WSJT-X-decoded signals would coherent bit formation, with per-signal fine sync, recover over our shipped extractor, on real audio? Offline Python, no build

- **To:** QA or the Engineer (one owner, recorded on the board; the Captain assigns)  **From:** Architect  **Date:** 2026-10-06 16:22Z (`date -u`, HK-017)
- **Branch:** `arch/coherent-limb2` (off `origin/main` `be3cc5ac`). Docs only: `git diff --stat -- src/ native/` empty.
- ✅ **`BAR_G` = 1.0 pp RATIFIED by the Captain, 2026-10-06 ~16:26Z (`date -u`), over the proposed 2.0 pp, before any harness, synthetic set or extraction exists. FROZEN. Owner: QA (Captain).**
- **Status:** ~~DRAFT until §9 Q1 (`BAR_G`) is ratified. After that,~~ PRE-REGISTERED: the harness, the frozen row list and the synthetic set are committed **before any real-audio extraction**. Nothing below may change after real data has been extracted, except by a dated amendment that says why.
- **Needs before arming:** Q1, an owner, and the Captain's go. CPU only: **no station, no PC exclusivity** (practical load is fine, Captain 2026-10-03). It runs after `NHARD-REP` finishes, so the two don't share the CPU.

---

## 0. Licence for this arm: the Captain reopened limb 2

- **Review:** `2026-10-06-1610-architect-a-prime-limb2-review.md` (`ca47a06c`) recommended keeping A′ parked. **The Captain rejected that** (2026-10-06 ~16:1xZ): *"after pushing on the most probable improvement for the decoding we find we can maybe close the 30.2 pp gap with 17.88% and your advice is to park it. right."* The Architect withdrew the recommendation. The Captain then said **"yes, write the step-1 spec"**.
- ⇒ **The C-GAP-D ruling (2026-08-22, "limb 2 may NOT be described as a D-001 treatment; Phase C NOT authorised on gap-closing grounds") is lifted by the Captain for this programme.** The figures it rested on are not re-read or withdrawn. The decision is the Captain's: a lever worth a bounded share of the gap is worth pursuing.
- **This is step 1 of 3** (review §5/§6, revised): (1) measure the real gain offline, **this spec**; (2) close the void instrument gate, ROW 0g-2 on today's DLL, a separate short spec; (3) the native build, flag-gated, only if step 1 says so.

## 1. Question

**Q:** at the positions where WSJT-X decoded a signal on a real night, how many more of those signals become **CRC-valid, correct decodes** if their bits come from a **coherent multi-symbol extractor with its own per-signal fine frequency/time estimate**, instead of our shipped extractor, through the **same** LDPC/OSD decode?

It answers what the review could only bound: **the realistic gain**, in pp of WSJT-X's decodes and in dB.

**Scope sentence (report head, verbatim):** *"Offline, Python, at WSJT-X's own positions on one 40 m night. Extraction and decode only; candidate search, the managed layer and the live path are not exercised. WSJT-X's AP is off on this station."*

## 2. Arms: the same signal, four bit-formation methods, one decoder

Every arm feeds its 174 LLRs to **`ft8_ldpc_decode_llrs`**: production's own BP → OSD → CRC on the pinned DLL, `nhard` 40, production `max_iters` and OSD depth (`gl_dll_pin` constants, reused).

| arm | bits from | fine sync | role |
|---|---|---|---|
| **G** | **shipped extractor**, `ft8_extract_llrs_at`, best of GAP-LOCATE's 9-cell lattice neighbourhood around WSJT-X's position (`lattice.py`, Amendment 2's position convention, `leg_fk2.py`) | none (lattice: 3.125 Hz / 0.08 s) | **the control: what we have** |
| **C1** | coherent **order 1** (single symbol), `coherent_extract.py` V1 | **own estimate** (§3) | isolates the fine-sync effect alone |
| **C3** | coherent **orders 1+2+3**, `coherent_extract.py` V3 (cumulative, as documented in its header) | **own estimate** (§3) | **the A′ candidate** |
| **C3\*** | as C3 | **oracle**: data-aided fit on all 79 tones of WSJT-X's message | the ceiling: a perfect estimator. Not a buildable decoder. |

**The C3 vs C3\* difference shows how much the fine-sync estimator leaves on the table**, which tells step 3 where to spend its effort.

**Clean-room (standing licence policy; the August N2 rule):** no WSJT-X source may be opened. Methods come from FT8's public constants, standard coherent demodulation theory, and **our own** `sync_refiner.c` (clean-room by its header). `coherent_extract.py` already complies, per its provenance note.

## 3. The fine-sync estimator (the one new piece; the history says it is the enabler)

For each signal, starting from GAP-LOCATE's anchor (WSJT-X's frequency and DT mapped by Amendment 2's convention):

- search **df ∈ [−2.0, +2.0] Hz in 0.1 Hz steps** and **dt ∈ [−0.12, +0.12] s in 5 ms steps**;
- objective: the **coherent Costas correlation**. That is the magnitude of the complex sum over the 21 known sync symbols at the hypothesised carrier, the method of `sync_refiner.c`'s `costas_coherent_sum`, re-implemented in NumPy. It is **data-free**: it uses only the sync tones, so it is a buildable estimator, not an oracle;
- take the argmax, with no interpolation finer than the grid.

**C3\*'s oracle fit** uses the same grid, with the objective extended to all 79 tones of the re-encoded WSJT-X message.

⚠️ **Why the windows are this size:** WSJT-X logs frequency to 1 Hz and DT to 0.1 s. GAP-LOCATE measured the position convention at Amendment 2's offset. ±2 Hz and ±0.12 s cover the logging resolution plus the convention's residual. **Row V3 checks that the windows are wide enough.**

## 4. Population, truth, outcome

- **Night:** `20261004_1634` (`…-gathered/owsfz/wav/`, `…-gathered/wsjt-x/ALL.TXT`). It is the same night and build family as the review and `NHARD-REP`.
- **Rows:** every WSJT-X decode in a **systematic sample of cycles**, positions `i mod 10 == 3` of the frozen ordered cycle list (the `NHARD-REP` construction, a different residue, so no cycle is shared). ≈ 310 cycles, ≈ 9,800 rows. **If the timing pilot (§7 step 2) projects more than 6 h of CPU for all four arms**, take positions `i mod 20 == 3` instead (≈ 4,900 rows) and record which before any real extraction.
- **Truth:** re-encode WSJT-X's message text (the vendored encoder). **Success** = `out_crc_ok` AND GAP-LOCATE's **`comparator.payload_match`** with ROW 0f's `v_star` (the RR73 equivalence). **Unencodable rows** (non-standard types the encoder cannot pack) are excluded **before** extraction and counted by reason.
- 🔒 **HK-037 / NFR-021:** message text and every 77-bit array live only inside the row loop (the `leg_fk2.py` discipline). Persisted per row: `cycle_index, ws_snr, ws_load (WSJT-X decodes in that cycle), live_hit (OWS matched it live, Test B rule), and per arm: success, path, ldpc_errors, n_bit_err (vs truth codeword), est_df, est_dt`. **No text, no bits, no text-derived hash.**

## 5. Statistics

- **Primary: `NET_C3`** = 100 × (Σ success_C3 − Σ success_G) / N_rows, in **pp of WSJT-X's decodes** (the review's unit, and the gap's).
- **Interval:** 95 % percentile CI, **cycle-clustered** non-overlapping block bootstrap over the sampled cycle order. Block = 8 sampled cycles; B = 10,000; seed 20261006; numerator and denominator resampled together. Blocks of 4 and 16 are reported but not used for the verdict.
- **Also with CIs (descriptive, no row):** `NET_C1`, `NET_C3*`, and the paired split **gains** (C3 succeeds, G fails) vs **losses** (G succeeds, C3 fails). **Report losses separately.** A coherent arm that wins many and loses many is a different build risk from one that only wins.
- **dB equivalent (descriptive):** the horizontal shift between the G and C3 success-vs-`ws_snr` curves, by linear interpolation at success levels 0.3/0.5/0.7, medianed. Then the review §4 shift estimator applied to that dB (upper bound) for comparison with `NET_C3` (direct).
- **By stratum (descriptive):** `NET_C3` by `ws_snr` band (≤ −16, −15…−6, −5…+4, ≥ +5 dB), by `ws_load` quintile, and **on live misses only** (`live_hit` = 0). The last is the subset the gap is made of.
- 🔴 **Unit of independence** (the S3c §2 lesson): report the distinct cycles carrying net gains, and the share of `NET_C3` carried by the top 5 blocks. If that share is > ½, say so in the first paragraph.

## 6. Rows

### Validity (any FAIL ⇒ no verdict; the report names the row and stops)

| row | predicate (as code) |
|---|---|
| **V1 pin** | DLL SHA-256 = the `NHARD-REP` pin (`2fa6d993…f365`, shim 20260058), asserted in code at start and end |
| **V2 synthetic alignment** (guards stall 1: a one-symbol origin error, rounding, a lattice-reconstructed frequency) | 200 synthetic isolated signals rendered by our own modulator (`scene_render`), Q-prefix messages, **off-lattice on purpose**: true df uniform in [−1.5, +1.5] Hz from the lattice, true dt offset uniform in [−0.06, +0.06] s, at nominal −14 dB (well above our threshold), fed through the **same** anchor mapping as real rows. **PASS iff** (a) C3 success ≥ 0.95, (b) median \|est_df − true_df\| ≤ 0.15 Hz and median \|est_dt − true_dt\| ≤ 7.5 ms, (c) G success ≥ 0.90. (c) guards that the anchor mapping is right before the coherent arms are trusted. |
| **V3 window** | on real rows, the share of C3 estimates on the **edge** of the df or dt search window ≤ 5 %. Above that, the windows are too narrow, and an amendment widens them before any verdict. |
| **V4 control reproduces** | on real rows with `live_hit` = 1, G success ≥ 0.90 (GAP-LOCATE's `P_ctrl` was 95.96 % on this kind of population) |
| **V5 determinism** | a second fresh process over the first 300 rows: every per-row field identical (all arms are deterministic: no randomness after the frozen seeds) |

### Verdict (exclusive, first match wins; `BAR_G` from §9 Q1)

| row | predicate | consequence |
|---|---|---|
| **COH-GO** | `CI_lo(NET_C3) ≥ BAR_G` | **Coherent bit formation with fine sync measurably recovers WSJT-X decodes.** ⇒ step 2 (ROW 0g-2), then a step-3 build spec (Developer, HK-011; flag OFF by default; offline OFF/ON replay). |
| **COH-STOP** | `CI_hi(NET_C3) < BAR_G` | **Not worth a native build at this bar.** A′ closes, citing `NET_C3` [lo, hi]. |
| **COH-OPEN** | otherwise | Unresolved. The Captain decides: more cycles (positions `i mod 10 == 7`), or stop. |

**HK-025(k), both ways:**

- **COH-GO cannot fire on a broken coherent arm**: V2 proves alignment against known truth, and success needs a correct payload, not just a valid CRC.
- **COH-STOP cannot fire on a broken coherent arm either**: V2(a) means C3 decodes clean off-lattice signals. A C3 that loses to G on real audio is then a real-audio property, not a harness defect.
- **What neither row sees:** signals WSJT-X missed too (HK-026), candidate search, the subtraction interaction (C3 is read on the **original** audio, not the residual), and runtime. All of those are step 3's.

## 7. Run order

1. Ratify `BAR_G` (§9), recorded here before any extraction.
2. Owner: harness (reusing `coherent_extract.py`, `gap-locate/{lattice,leg_fk2,forced_success,comparator,pack77_fields,loader,wavio}.py`, `ldpc_decode_ctypes.py`), the frozen row list (SHA-recorded) and the V2 synthetic set. **Then a timing pilot on 50 real rows**, all arms, discarded from the analysis, to choose the 1-in-10 or 1-in-20 sample under §4's 6 h rule. **Commit all of it before the main extraction.**
3. V2 → V1 → main extraction (all four arms per row) → V5 → analysis. Detached and supervised (HK-013/HK-023), orphan check (HK-019).
4. **Report:** numeric only, NFR-021 prose scan, folder copied to `qa\rr-study\results` at the root (Captain, 2026-10-04).

## 8. What this arm does NOT do

- 🛑 No `src/` or `native/` change, no rebuild, no push, no merge (HK-011/HK-014/HK-010).
- 🛑 It does not read the residual (post-subtraction) audio or the early-decode path.
- It does not answer runtime: Python cost is not native cost.
- One 40 m night: no band replication.
- **HK-025 is available in full.**

## 9. Questions for the Captain

**Q1, needed BEFORE any real-audio extraction: ratify `BAR_G`, the smallest NET gain worth weeks of native work.** Proposed: **`BAR_G` = 2.0 pp of WSJT-X's decodes.**

- **Why:** the review's exploratory table puts ≈ 1 dB of better bits at ≈ 1.9 pp. A build that buys less than about 1 dB is unlikely to survive the live path's losses (residual audio, the deadline). 2 pp is also about ⅙ of what subtraction bought (+11.7 pp), for comparable effort.
- **Alternative: 1.0 pp.** It is more permissive and would fire COH-GO on a ~½ dB effect. Resolution isn't the limit: with ≈ 9,800 paired rows the CI half-width should be ≈ 0.5–1 pp after clustering (computed while drafting, HK-021(m); V5 and the bootstrap check it).
- 🛑 Once ratified, FROZEN for this arm. Moving it after `NET_C3` is known VOIDs the verdict.

> ✅ **CAPTAIN'S RULING, 2026-10-06 ~16:26Z: `BAR_G` = 1.0 pp** (over 2.0 pp). Recorded before any `COH-GAIN` datum. **FROZEN.** **Q2: owner QA.**

**Q2 (not blocking):** owner, QA or the Engineer. `NHARD-REP` (QA) is running now; this arm runs after it either way.

## 10. Architect predictions (blind; scored at ruling time)

| # | prediction | P | class |
|---|---|---:|:---:|
| CG1 | Verdict **COH-GO** at `BAR_G` = 2.0 | 0.35 | H |
| CG2 | Verdict COH-STOP | 0.35 | H |
| CG3 | `NET_C3` point estimate in [0.5, 4.0] pp | 0.55 | H |
| CG4 | `NET_C3*` − `NET_C3` ≥ 1.0 pp (the estimator leaves a material share) | 0.50 | H |
| CG5 | Losses (G succeeds, C3 fails) ≥ 1 % of rows | 0.60 | H |
| CG6 | V2 passes first time | 0.55 | C |
| **CG1′** | *(added at ratification, before any datum; CG1/CG2 above were written at 2.0 and are kept as written)* Verdict **COH-GO at the ratified `BAR_G` = 1.0** | 0.45 | H |
| **CG2′** | Verdict COH-STOP at 1.0 | 0.25 | H |

---

## 11. Amendment 1 — 2026-10-06 16:58Z (`date -u`): V2(b) re-specified; a near-threshold descriptive tier. Synthetic data only so far, no real-audio datum

**QA's report (message received ~16:5xZ):** the first V2 run, on the 200 synthetic signals only, passes (a) C3 1.000, (c) G 1.000 and (b)'s dt half (median 1.3 ms ≤ 7.5 ms). It **fails (b)'s df half: median |est_df − true_df| = 0.162 Hz > 0.15.** C1 and C3\* are both 1.000. df error quantiles 10/50/90/99 % = 0.004 / 0.162 / 0.182 / 0.350 Hz. The oracle's median is 0.023 Hz.

**Cause, accepted as measured:** the data-free objective sums three 7-symbol Costas blocks **36 symbols (5.76 s) apart** coherently. Its df surface therefore has **grating lobes every 1/5.76 s = 0.174 Hz** at nearly equal height, and the argmax lands one lobe off about as often as not.

- It is **not a bias** (signed median −0.01 Hz), **not noise** (same spread at +20 dB), and **not the harness**: the oracle is tight on the same signals, and a unit test shows the matmul form equals naïve per-hypothesis downconversion.
- **It does not hurt decoding at this level:** 0.17 Hz is ≈ 0.17 rad per symbol, negligible inside a 3-symbol coherent group, and C1/C3 decode 200/200.

**Ruling (HK-025(k), QA's case accepted):** **(b) as written was a bar the specified estimator cannot pass on any run.** It sat inside the estimator's own lobe spacing, and it was not needed to catch what V2 exists for: a one-symbol origin error is 160 ms, integer-Hz rounding gives ≥ 5 ms or ≤ 0.5 Hz offsets, and a lattice-reconstructed frequency is off by up to 1.56 Hz. The defect is **mine**: I set 0.15 Hz without computing the estimator's ambiguity, which is a computable miss of the kind the ledger already records. **Re-specifying it now is not a re-read of a result**, because no real-audio datum exists, and the new bar still fires on every defect the row was written for.

| row | was | now |
|---|---|---|
| **V2(b)** | median \|est_df − true_df\| ≤ 0.15 Hz AND median \|est_dt − true_dt\| ≤ 7.5 ms | **(b′)** median \|est_df − true_df\| **≤ 0.20 Hz** (the 0.174 Hz lobe period plus half a grid step) **AND \|median signed est_df − true_df\| ≤ 0.05 Hz** (no bias) **AND** median \|est_dt − true_dt\| ≤ 7.5 ms. (a) and (c) unchanged. |

V2 is **re-evaluated on the same 200 synthetic signals** under (b′). No re-render, no new seed.

**Added, DESCRIPTIVE ONLY (no row, cannot stop or license anything): V2-T**, a near-threshold tier. 200 more synthetic signals, same construction, at nominal **−20 dB**, decoded by all four arms. **Why:** at −14 dB every arm saturates at 1.000, so V2 can see only gross misalignment. V2-T shows G vs C1 vs C3 vs C3\* where the differences live, and whether the lobe ambiguity starts to cost anything near threshold (C3 vs C3\*). Its seed comes from a new label, `COH-GAIN-V2T`. It is committed with the harness before any real extraction. 🛑 It is synthetic AWGN: never cite it as the gain.

**Also ruled, from QA's facts:**

- **The anchor offset δ = 0.7 s (median; mean 0.659 over 68,525 exact matches)** is accepted and frozen. It agrees with the board's known ≈ 0.70 s DT convention difference.
- **The 636 excluded rows** (523 hashed-call tokens, 113 other unencodable) are excluded before extraction, as specified. The **denominator is therefore encodable WSJT-X decodes (9,524)**. The report must **also** give `NET_C3` rescaled to **all** WSJT-X decodes in the sampled cycles, crediting the excluded rows with zero gain (conservative), and state both. **The verdict uses the specified (encodable) denominator.**
- **The 1-in-10 sample stands** (≈ 1.3 h of CPU projected at ≈ 0.5 s per signal; the timing pilot still runs, as specified, from disjoint `i mod 10 == 7` cycles).

**Scored now (ledger rule 1):** **CG6 "V2 passes first time" (0.55, C): 🔴 MISS**, on my own bar. CG1–CG5, CG1′ and CG2′ stay open.

**Still required before real extraction:** V2 PASS under (b′), the pilot, everything committed, and **the Captain's go in QA's window** after `NHARD-REP`.

---

**On the ledger:** in the review I leaned *against* a build and the Captain overruled me. These probabilities are deliberately near even. Measurement geometry has cost limb 2 most of its time before, which is why V2 sits at 0.55.
