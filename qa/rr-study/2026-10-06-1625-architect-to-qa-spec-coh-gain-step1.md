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

## 12. Amendment 2 — 2026-10-06 17:10Z (`date -u`): production OSD receives sign-inverted LLRs. Two descriptive arms added. Still no main-extraction datum

**QA's finding (on the 50 DISCARDED pilot rows, `i mod 10 == 7`, disjoint from the sample; harness `fcd553df`, pilot choice `dcb23a74`, `qa/coh-gain`, local).** Across those rows G decodes 37 by BP and **0 by OSD**, with 13 failing. With OSD forced on G's LLRs (`ft8_ldpc_decode_llrs`, `max_iters` 1, depth 2, `nhard` 40), it recovers the true payload on **0/50 as shipped and 16/50 with the LLR signs negated** (all 16 are rows BP also decodes).

**Verified by the Architect from source at `be3cc5ac` (HK-018). The sign mismatch is real:**

- **Extractor:** `ft8_extract_symbol` computes `logl = max(bit-1 tones) − max(bit-0 tones)`, i.e. log p(1)/p(0). **Positive = bit 1.**
- **BP:** `ft8_lib_vendor/ft8/ldpc.c:149`: `plain = (sum > 0) ? 1 : 0`. **Positive = bit 1, consistent with the extractor.** (`ldpc.c:9`'s comment says the opposite; the code governs.)
- **OSD:** `patched/ft8/decode.c` `osd_decode`, whose header says "positive = bit 0" and whose code is `hard = (llr < 0) ? 1 : 0`. **Positive = bit 0.**
- **Call site** (`ftx_decode_candidate`, `decode.c:~643–666`): `llr_for_osd` is a plain copy of the same normalised `log174` BP receives, passed to `osd_decode` **unnegated**. The gate's `hd = (llr > 0) ? 0 : 1` and `hard_pm1` follow OSD's convention, so the gate is internally consistent with the inversion and never flags it.
- ⇒ **Since OSD shipped (shim 20260025), production OSD has searched near the complement of the received hard decisions.** The all-ones word is not a codeword of this LDPC code (its parity rows have weight 6–7), so OSD returns a different codeword near the complement. That passes CRC-14 only by chance (≈ 2⁻¹⁴ per attempt). **On this reading every production OSD accept has been a chance-CRC false decode.**

**It explains, with one mechanism:**

- `NT` 0/710 and `CC` 0/3,681 genuine OSD rescues at **any** `nhard`;
- the D-009 / OSD-FA-A false-accept history, with the `nhard` gate (R5) calibrated on chance-valid output;
- `NHARD-REP`'s signature: 40 → 60 adds 2 confirmed and +207 unconfirmed decodes, and the batch-2 loss fits false decodes being subtracted.

⚠️ **Not yet established:** (1) **how much a corrected OSD would add**: QA's 16/50 were all BP-decodable rows, and 0 of 13 BP failures were rescued, n = 50; (2) its **false-decode cost** at the current gate values, which were tuned on the inverted path and need re-calibration; (3) the D3 "10 WSJT-X-confirmed OSD-path decodes" and E3's "2 corroborated removals", whose path classification had a known blind spot (E3 ruling §4). A chance-CRC payload essentially cannot match a WSJT-X message, so those were probably misclassified.

**Ruling: QA's proposal is ACCEPTED. Two DESCRIPTIVE arms are added (no row; they cannot stop or license anything):**

| arm | definition |
|---|---|
| **GO** | G's LLRs. BP exactly as production. **If BP fails, OSD on the NEGATED LLRs** via `ft8_ldpc_decode_llrs` (`max_iters` 1, depth 2, `nhard` 40, corr 0.10, all with the gate in the corrected convention because the gate reads the same negated vector). It emulates a one-line sign fix of the production path. |
| **C3O** | the same, on C3's LLRs |

**Report, per arm:** success; `NET_GO` = (succ GO − succ G)/N and `NET_C3O` − `NET_C3`, with the same cycle-clustered CI; the number of rows where BP failed and corrected OSD recovered the **true** payload; and 🔴 **the number where corrected OSD returned a CRC-valid but WRONG payload** (a false decode at a true signal's position, which is the at-position half of the FP cost). Any `path` = 0 on the negated call (BP "converging" on the complement) is counted and reported, and counted as a failure.

**What these arms cannot see, stated now:** the false-decode cost on **empty or crowded** positions. Every row here is a real WSJT-X signal. **A product fix therefore needs its own spec**: a native one-line change plus a gate re-calibration (Developer, HK-011), measured by an offline flag-OFF/ON replay against WSJT-X with an FP watch (the SUB-FEAS pattern) and a noise leg. **Not licensed here.**

**Consequences for closed work (HK-022: correct a record where it lives):**

- **`NHARD-REP` N-CLOSED stands as measured.** It is a statement about the shipped decoder. Its **reading changes**: the cap acted only on false decodes, so the result says nothing about a correct OSD's `nhard`.
- **`NT`, `CC`, `E3`, OSD-FA-A and D-009 R5** measured a **sign-inverted** OSD. 🛑 **Never cite them as "OSD cannot rescue genuine decodes" or as calibrations of a correct gate.** The board's citation guards are updated in the same pass.
- The `#3` comment posted today (6021435358) gives the "cap below 40" lead. That lead is **superseded**: with OSD fixed, the cap question has to be asked again from scratch. A correction is to be posted on #3 if the Captain wants it.

**Unchanged:** the COH-GAIN verdict rows, `BAR_G` (1.0 pp, frozen), V1–V5, the sample, and the predictions. **The main extraction still needs the Captain's go in QA's window.**

**Prediction (blind; descriptive; scored at the COH-GAIN ruling):** CG7: `NET_GO` point estimate ≥ +0.5 pp, P = 0.45 (H). The pilot's 0 of 13 argues low; WSJT-X's own OSD gain near threshold argues higher.

---

## 13. Amendment 3 — 2026-10-06 17:30Z (`date -u`): V4 re-specified on the population it was meant for. **Ruled BLIND**: the Architect has not seen any NET or arm figure

**QA's report (main extraction done 17:18:26Z–17:27:48Z, 9,524 rows, 309 cycles, pin equal at start and end; verdict withheld):**

- V1, V2 (b′), V3 (edge 2.2 %) and V5 (300 rows, 0 differences) PASS. **V4 FAIL: G success on live-hit rows = 0.800 (n 6,697) vs 0.90.**
- QA has seen the descriptive NET figures, **withheld them from the Architect on purpose**, and has not committed or copied `rows.json`. That was correct, and it makes this ruling blind.
- **Incident accepted:** a fixed zero-pad in `fine_sync` crashed on a late anchor (IndexError). Out-of-stream samples are zero by the spec's convention, so this was a harness bug. It was fixed with regression tests (`c2815cd3`) and the run resumed. The 8,624 rows already written could not have touched the overrun, and V5's fresh-process repeat covers them.

**Cause, accepted, and computable from outcome-free figures:**

- With subtraction ON, **14.1 % of the live path's matched decodes are batch 2** (`NHARD-REP` N40: 953/6,759): decodes found only in the **residual** audio.
- **G reads the original audio**, so it cannot reproduce them, and its ceiling on "live hits" is ≈ 0.86 before any harness question.
- G's rate rises with SNR (0.68 → 0.94) and falls with load (0.846 → 0.739). On ≥ 0 dB, lightest-load rows (n 473) it is **0.966**, matching GAP-LOCATE's `P_ctrl` 95.96 %.
- 0 of 5,356 G successes are by OSD, as the sign finding predicts.

**Ruling:**

- **The defect is the Architect's.** V4's 0.90 came from `P_ctrl`, a **pre-subtraction** population, and I applied it to a flag-ON live population without accounting for batch 2. That makes three computed bars set wrong today (NR3, CG6, V4). The fault is the same each time: **I wrote the bar without computing what the instrument reads on this build's own population.**
- **Option (i) is ADOPTED, with the bar unchanged.** **Option (ii) is REFUSED**: a stratum picked from this run's data is outcome-adjacent. **Option (iii) is not needed.**

| row | predicate (as code) |
|---|---|
| **V4′** | Replay the 309 sampled COH-GAIN cycles through the **`NHARD-REP` harness at `nhard` 40** (same build, pin, flag ON, threads 8, Test B match rule), with the matched output extended to carry **each match's batch**. Population **P1** = COH-GAIN rows (encodable WSJT-X decodes) matched by that replay **in batch 1**. **PASS iff G success on P1 ≥ 0.90.** Rows matched only in batch 2, and rows unmatched by the replay, are not in P1. |

- **Why this is the right population:** P1 is "what the decoder found on the original audio at this build", defined by an instrument **independent of G**. It is exactly what G is supposed to reproduce, and it is the analogue of `P_ctrl`. **The bar is not lowered.**
- **Also report (descriptive, it tests QA's hypothesis directly):** G success on rows matched **only in batch 2** (expected low), the replay's batch-2 share on these cycles, and |P1|.
- If V4′ **FAILS**, the verdict is VOID. QA reports and stops; the Architect rules.

**Release scope (HK-025(ab): scope a stop rule to what it guards):** V4 guards the **G arm and the anchor mapping**, which every NET uses (`NET_C3`, `NET_GO`, `NET_C3O`, and C3\* relative to G). **Nothing is released or scored until V4′ is evaluated.** QA's stratified G rates above are V4 diagnostics and may be cited as such.

**Prediction (blind; scored at the COH-GAIN ruling):** CG8: V4′ passes. P = 0.75 (C).

**Order:** the V4′ replay (≈ 35 min, PC free, CPU only), committed with the batch-labelled matched output **before** any further scoring; then V4′; then, if PASS, the verdict and the descriptive arms as specified. The Captain's go for the main extraction covers this replay: it is a validity check inside the same arm, with no station time. If the Captain wants a separate go, he says so.

---

## 14. Amendment 4 — 2026-10-06 18:19Z (`date -u`): the COH-OPEN extension, plus the fallback design registered BEFORE its data exist

**Licence:** the ruling `2026-10-06-1815-architect-coh-gain-ruling.md` (`418a6941`) reads COH-OPEN. **The Captain chose "Extend + fallback row"** (2026-10-06 ~18:1xZ). Nothing below touches the first sample's figures.

**E1, the extension sample:** cycle positions **`i mod 10 == 5`** of the same frozen ordered list. **Not `== 7`**, as §6 originally said: `== 7` hosted the 50 discarded pilot rows, whose outcomes QA has seen. `== 5` is untouched. ≈ 310 cycles. Same harness (`qa/coh-gain` at its current commit), pin, anchor δ 0.7 s, exclusion rules, all arms (G, C1, C3, C3\*, GO, C3O), V1, V3 and V5 (V5 on the first 300 extension rows). **V4′ is re-evaluated on the extension** with its own batch-labelled replay of the `== 5` cycles (bar 0.90, unchanged). V2 is not re-run: it is a synthetic, sample-independent check, already passed.

**Primary, unchanged: `NET_C3` POOLED** over both samples (≈ 618 cycles), block 8 over the pooled cycle order (each sample's blocks kept within that sample, then pooled), the same B and seed, and the **same rows (COH-GO / STOP / OPEN) at `BAR_G` = 1.0 pp.** If the pooled verdict is again OPEN, the Captain decides; there is no automatic third sample.

**Secondary, registered now, on the EXTENSION ROWS ONLY** (the first sample produced the idea, so it may not test it):

- **`NET_U`** = 100 × (Σ success_U − Σ success_G)/N, where **U = G, and if G fails, C3** (C3 is consulted only on G-fail rows; a C3 success there counts; **a C3 CRC-valid wrong payload there counts as a false decode, not a success**). Same CI method.
- **U-GO** iff `CI_lo(NET_U)` ≥ 1.0 pp. **U-STOP** iff `CI_hi(NET_U)` < 1.0 pp. **U-OPEN** otherwise.
- **HK-038, where the bar comes from:** 1.0 pp is `BAR_G`, which the Captain ratified today as the gain that justifies a native build. It is a decision value, not one carried from an older measurement.
- ⚠️ **How to read U-GO (QA's HK-025(k) note, accepted 2026-10-06 18:32Z, before any extension datum):** the union cannot lose a row, so `NET_U` is C3's gain rate on G-fail rows (first sample: 5.25 % [4.69, 5.77]) against a 1.0 pp bar. **U-GO is therefore a REPLICATION check of that gain on fresh data, not a hard hurdle.** U-STOP would mean the first sample's gain was an artefact. **The design is decided by the false-decode count below**, which the step-3 spec gates on. The bar is NOT changed.
- **Reported with it (descriptive, mandatory):** **the fallback's false decodes**. That is the number of G-fail rows where C3 returns a CRC-valid payload that is not the sent one, per row and per correct recovery (first sample: 198 per 500, not citable). A fallback that buys 1 pp at a high wrong-payload rate is not shippable as it stands, and the step-3 spec must gate on it.

**Order:** freeze and commit the extension row list (SHA) and its V4′ replay manifest **before** any extension extraction. Then V4′ (extension) → extraction → V5 → pooled primary → U row. QA reports; the Architect rules.

**Predictions (blind to the extension; scored at its ruling):**

| # | prediction | P | class |
|---|---|---:|:---:|
| CE1 | pooled verdict COH-GO | 0.35 | H |
| CE2 | pooled verdict COH-OPEN again | 0.50 | H |
| CE3 | **U-GO** on the extension | 0.80 | H |
| CE4 | fallback wrong payloads ≥ 0.25 per correct recovery on the extension | 0.65 | H |

---

**On the ledger:** in the review I leaned *against* a build and the Captain overruled me. These probabilities are deliberately near even. Measurement geometry has cost limb 2 most of its time before, which is why V2 sits at 0.55.

---

## 15. Amendment 6 — 2026-10-07 10:30Z (`date -u`): `WRONG-ID`, what are the fallback's "wrong payloads"? To: QA

**Licence:** the Captain, Architect's window, 2026-10-07 (*"yes, write it up for QA"*), after he leaned to parking COH-GAIN and asked whether the false-decode problem includes the OSD bug. **Running it needs his go in QA's window (HK-033).** No station, no PC exclusivity, a few minutes of CPU.

### 15.0 Amendment 5 (QA-authored, overnight): accepted as executed

QA wrote Amendment 5 (`04e79355`) under the Captain's overnight authorisation while this session was closed. **Checked:** it was committed before any extraction (22:41 local); each sample's V4′ manifest was committed before that sample's extraction (`07a100ad` … `8cbeaf12`); it changed no threshold, row, arm or bar. **The six fresh samples and their rows are accepted as data.** What the marginal pooled COH-GO **means** (`CI_lo` 1.06 against 1.0; dropping r9 gives 0.97) is ruled **after** this check, together with it, because this check decides whether the fallback (U), not C3 alone, is the design.

### 15.1 Why this check (the facts it rests on, all from the persisted rows, fresh samples = ext + r1/r2/r4/r6/r8/r9, 64,455 rows)

On the 27,571 rows where G fails, split by the decoder path C3 succeeded through:

| C3 on G-fail rows | path 0 (BP) | path 1 (OSD, sign-inverted) |
|---|---:|---:|
| correct payload | **3,382** | **0** |
| CRC-valid wrong payload | **1,352** | **215** |

The same split for **G itself** (all rows): 533 CRC-valid wrong payloads on path 0 and 112 on path 1.

- **The +5.25 pp needs no OSD.** Every correct recovery is BP. The 215 OSD wrongs are #215's chance-CRC false decodes. Turning OSD off removes them and leaves 1,352 (0.40 per correct recovery).
- **A BP wrong is unlikely to be chance.** BP converging to a valid codeword that also passes a 14-bit CRC by luck needs on the order of 10⁴ convergences to wrong codewords per CRC pass. The more likely sources are: **(a) another real transmission at that position** (overlapping stations, crowded 40 m), or **(b) a truth-comparison artefact** (the row's truth is not what is at that position). **(c) a genuine false decode** is the remainder.
- 🔴 **Correction to what I told the Captain (HK-022):** I said the wrong messages "differ from the expected one in 79 of 174 bits". **That is wrong.** `C3_nbe` is the number of C3's **raw hard decisions** that disagree with the **sent** codeword (mean 79 on these 1,352 rows), not the distance between the decoded and the sent message. It still says C3's bits there are nearly uncorrelated with the sent signal, which fits (a). It does not measure the message distance. That distance is unknown until this check.

### 15.2 What QA does

1. **Rows:** every fresh-sample row where **C3 returned CRC-valid and not the truth on a G-fail row** (expected 1,567: 1,352 path 0 + 215 path 1), plus, as a comparison set, **every row where G returned CRC-valid and not the truth** (expected 645). Selected from the persisted `rows.csv` files by those numeric fields alone, **before** any re-extraction; the row list is committed (SHA) first.
2. **Re-extract** those rows with the same harness, pin and parameters (it is deterministic; V5 showed 0 differing fields).
3. **Inside the function that reads `ALL.TXT`** (HK-037; the `leg_fk2.py` discipline), compare the recovered 77-bit payload against **every WSJT-X decode in the same cycle** (re-encoded, `payload_match` with `V_STAR`, the same equivalence as truth), and against **OpenWSFZ's own live decodes in that cycle** from the night's OWS log. Persist **numbers only**, per row:
   - `cls`: **M-NEAR** = equals a WSJT-X decode in the same cycle with |Δf| ≤ 12.5 Hz (2 tone bins) and |Δt| ≤ 0.32 s (2 symbol steps) of the row's anchor; **M-FAR** = equals a WSJT-X decode in the same cycle outside that window; **M-OWS** = no WSJT-X match but equals an OWS live decode in that cycle; **M-NONE** = no match. First match wins, in that order.
   - for M-NEAR / M-FAR: `widx` of the matched WSJT-X row, Δf (Hz), Δt (s), that row's SNR, and whether it is itself a row in the sample (`in_sample`).
   - `dist`: Hamming distance between the recovered payload and the truth payload (77 bits). This is the figure I mis-stated above.
4. **Never** persist text, bits or a text-derived hash.

### 15.3 Validity (any FAIL ⇒ no reading; the report names the row and stops)

| row | predicate | why, and where the number comes from (HK-038) |
|---|---|---|
| **W1** reproduction | on every selected row, re-extraction gives the same `C3_ok`, `C3_crc`, `C3_path`, `C3_nbe` (and `G_*` for the G set) as the persisted row | Exact: V5 showed this harness reproduces every field. No number is carried. |
| **W2** negative control | of the 215 path-1 (OSD) wrongs, **M-NEAR + M-FAR ≤ 5 %** | A sign-inverted OSD output is a chance codeword; a chance 77-bit match against ≤ ~60 payloads in a cycle has probability ~10⁻²⁰. So the expected rate is 0, and 5 % (≈ 11 rows) is a tolerance for the comparator, not a carried figure. If it fails, the matcher is too loose and every M-count is withheld. |
| **W3** geometry | among BP (path 0) wrongs that match a WSJT-X decode, **M-NEAR ≥ 80 %** of the matches | A different signal can only be decoded at the anchor if it sits within about one tone bin and one symbol step. Many M-FAR rows would mean the truth or the row indexing is misaligned (source (b)), not overlap. 80 % is a decision margin. |

### 15.4 Reading (exclusive, first match wins; on the **1,352 path-0 wrongs**)

Let `F` = (M-NEAR + M-OWS) / 1,352, with a 95 % block-bootstrap CI (blocks of 8 cycles within each sample, B 10,000, seed 20261006, as the primary).

| row | predicate | reading |
|---|---|---|
| **W-REAL** | `CI_lo(F)` ≥ 0.50 | Most of the fallback's "wrong" outputs are **other real signals** at that position. In the product they are either duplicates of a decode we already show (text dedup removes them) or genuine extra decodes. The false-decode gate the step-3 spec needs is much smaller than 0.40 per recovery. |
| **W-FALSE** | `CI_hi(F)` < 0.50 | Most are **not** explained by any decode in the cycle: they stay an upper bound on false decodes, and the step-3 spec must gate on them as before. |
| **W-MIXED** | otherwise | Report the split; the Captain decides. |

**HK-038:** 0.50 is the decision value the question implies ("most of them"). It is not carried from any measurement.

**Reported with it (descriptive, mandatory):**
- the same classification for the 645 **G** wrongs (is this a property of any extractor in a crowded band, or of C3?);
- **M-NONE per correct recovery** after OSD off: the residual false-decode upper bound for the fallback (M-NONE / 3,382);
- the `dist` distribution for each class;
- for M-NEAR: the share with `in_sample` = 1 whose own row G **already** decodes (a duplicate in the product, so no harm and no gain) vs not (a genuine extra the product could show);
- M-NONE split by WSJT-X SNR band of the row.

### 15.5 What this check does NOT answer

- **Noise-only positions.** All rows here are positions where WSJT-X found a signal. How many false decodes the fallback adds where the product's candidate search fires on noise is **unmeasured**. The right instrument is the step-3 offline flag OFF/ON replay through the real candidate search, not random positions here (random positions are easier than real candidates, so they would understate it).
- Whether the product's own candidate search finds the 3,382 signals. Native cost. A second night.

### 15.6 Predictions (blind; scored at ruling time)

| # | prediction | P | class |
|---|---|---:|:---:|
| CW1 | W1 passes | 0.90 | C |
| CW2 | W2 passes (OSD wrongs ≤ 5 % matched) | 0.90 | C |
| CW3 | W-REAL | 0.55 | H |
| CW4 | G's wrongs are M-NEAR at ≥ 50 % (descriptive) | 0.55 | H |

⚠️ CW3 is my inference from the CRC argument, offered to the Captain before any data. The ledger says my HYPOTHESISED calls lean toward the tidy explanation. Hence 0.55, not higher.
