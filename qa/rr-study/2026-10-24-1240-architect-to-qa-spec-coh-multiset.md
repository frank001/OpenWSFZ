# SPEC — `COH-MULTISET` (L1 + L2): does the coherent fallback gain from decoding several bit-metric sets separately, and from OSD?

- **To:** QA (owner)  **cc:** Captain  **From:** Architect  **Date:** 2026-10-24 12:40Z (`date -u` 12:39:08Z)
- **Authorised:** the Captain, 2026-10-24, Architect's window: "go" (D2 of the Deep read).
  - D1 decided at the same time: *"my requirements only said look at the method, don't copy code from wsjt-x. I think that still stands as long as there is no direct copying of the code."*
- **Source of the question:** `qa/rr-study/2026-10-24-1235-architect-wsjtx-deep-read.md` §2–§3 (levers L1, L2).
- **Branch:** `arch/coh-multiset` (local; carries the Deep read). Docs only; `git diff --stat -- src/ native/` is empty.
- **Kind:** offline, Python + the existing native BP/OSD export. **No Developer build, no `src/`/`native/` change, no radio, no live station.**
  - It runs on `sol` or the PC. CPU exclusivity is not needed, because no timing is compared.

## 1. The question, in one sentence

**At the positions where WSJT-X decoded a signal on a fresh 40 m night, how many more of those signals become correct decodes if every signal that both our shipped extractor (G) and today's fallback set (C3 = V3) fail on gets further tries: four other coherent bit-metric sets, each decoded on its own? And what does each such try cost in wrong payloads?**

**Scope sentence (report head, verbatim):** *"Offline, Python, at WSJT-X's own positions on one 40 m night. Extraction and decode only; candidate search, subtraction, the managed layer and the live path are not exercised. WSJT-X's AP is off on this station. A gain here is an upper-side estimate for a build: the fallback in production starts from our own candidate positions, not WSJT-X's."*

## 2. Data already on file (HK-018, read before writing this)

| what | figure | source |
|---|---|---|
| C3 vs G at WSJT-X positions | NET +1.33 pp [+0.57, +2.03]; C3 recovers 361 of 2,825 live misses | COH-GAIN ruling `2026-10-06-1815` §1–§2 (`20261004_1634`) |
| order-1 coherent alone (C1) | **−7.49 pp** vs G | same §2 |
| G ∪ C3 over G (post-hoc) | +5.25 pp [4.69, 5.77]; on G-fail rows C3 gives **500 right, 198 CRC-valid wrong** | same §3 |
| C3 + corrected OSD (C3O, `nhard` 40) | **+0.26 pp**; 25 true, 34 wrong | same §4 |
| the fallback as shipped, replay | NET +3.82 pp [3.44, 4.21], ΔU′ +0.0198 | COH-FALLBACK step-3 spec §19 (`20260922_2056`) |
| V3's construction | order 1 **plus the summed** order-2/3 contributions; "a documented judgement call … not dictated by the spec text" | `coherent_extract.py:50–58` |

**Era of these figures (HK-038):**
- COH-GAIN ran on 2026-10-06, before the OSD sign fix (#215) and with `nhard` 40, on the Windows PC.
- **G's figures are of that era.** G now runs the fixed OSD at 24, so G is re-measured here, never carried over.
- **C3's figures (500 right / 198 wrong, used for the W bar in §6) are BP-only on the coherent extractor.** Neither change touched that path: BP is `ldpc.c`, unchanged by #215, and the extractor is `coherent_extract.py`. So the bar carries, and V3 (§5) checks the extractor against today's DLL.

**What this means for the design:**
- C1 alone is weak, so the question is **not** whether any one set beats V3. It is whether the sets **add rows V3 misses**: a union, consulted only where G and C3 both fail.
- OSD on coherent bits has already been seen to be small. **So L2 is a descriptive factor here, not a gate.**

## 3. Arms

Every coherent arm uses **C3's own fine-sync estimate** for that row: one estimate per row, shared by all coherent arms, so the arms differ only in how the bits are formed. Each arm's raw 174 values go to `ft8_ldpc_decode_llrs` with 50 iterations and no other scaling. This is exactly how the fallback feeds V3: `cf_run_bp`, `ft8_shim.c:2236–2244`, casts and passes. The export normalises every input to the same variance before BP (`ftx_normalize_logl`, `decode.c` `ftx_ldpc_decode_llrs` step 3, "MANDATORY"), so the sets' different raw scales do not bias the comparison.

| arm | bits from | decode | role |
|---|---|---|---|
| **G** | shipped `ft8_extract_llrs_at`, GAP-LOCATE's 9 lattice cells, any cell | BP, then OSD depth 2 at today's shipped gate (`nhard` 24, corr 0.10, sign fix ON), **read back** | the primary-path control |
| **C3** | `coherent_extract.py` V3, as committed | **BP only** (osd_depth −1), as the fallback ships (`ft8_shim.c:2242`) | today's fallback |
| **C1** | coherent order 1 (V1) | BP only | extra set (a) |
| **J2** | **joint 2-symbol** metric (§3.1) | BP only | extra set (b) |
| **J3** | **joint 3-symbol** metric (§3.1) | BP only | extra set (c) |
| **N1** | coherent order 1, **normalised bit by bit** (§3.1) | BP only | extra set (d) |
| **X** | first of C1, J2, J3, N1 (that order) giving a CRC-valid payload, consulted **only on rows where G and C3 both fail** | — | **the L1 candidate** |
| L2 factor (descriptive) | C3, and each of C1/J2/J3/N1, again with OSD depth 2 at the shipped gate after BP fails | BP + OSD | L2 |

### 3.1 The three new metric sets: the method, in prose

This is written from the method only. **No WSJT-X code is to be opened, copied or transliterated** (licence policy; Captain 2026-10-24). QA implements it in Python from this text and from FT8's public constants.

- **Symbol spectra:** the complex per-symbol DFT values X[s][tone] that V1–V3 already compute (`correlate_symbols`), at C3's estimate.
- **Groups:**
  - The 58 data symbols form two halves of 29 (symbols 7–35 and 43–71).
  - **J2** splits each half into consecutive non-overlapping pairs; the 29th symbol of each half is a group of one.
  - **J3** splits each half into consecutive non-overlapping triples; the last two symbols of each half form a pair.
  - Groups never straddle a Costas block.
- **Joint score:** for a group of n symbols and each of the 8ⁿ tone hypotheses, score = |Σⱼ X[sⱼ][toneⱼ]|. This is the **magnitude** of the coherent sum, not the power. It assumes the carrier phase is constant across the group, which fine sync provides.
- **Bit value:**
  - Each of the group's 3n bits gets the Gray-mapped (map 0,1,3,2,5,6,4,7) max-log value: the maximum score over hypotheses where the bit is 1, minus the maximum where it is 0.
  - A group of one is plain order-1 on magnitudes.
- **N1:** order-1 on magnitudes, with each bit's value divided by the larger of its two maxima (0 if both are 0).
- **Scaling:** none beyond the export's own normalisation (§3).
- **Sign convention:** positive = bit 1, as the extractor and BP use (`ldpc.c:149`). V2b (§5) checks it.

## 4. Corpus, rows, truth

- **Night:**
  - QA lists **every** `artefacts/` folder with full-cycle WAVs and a WSJT-X `ALL.TXT` (rule 2026-10-03). It picks **one 40 m night that is none of** `20261004_1634` (COH-GAIN, T1), the 2026-10-09 Stage 2 night (`20261009_1752`; QA confirms the folder), `20261019_1905` (Q-GATE-2), `20260922_2056` (step 4) and `20260930_1930` (OSD-FIX TEST).
  - Voicemeeter chain preferred; the 2026-10-17..19 OWS-recorded-WAV disposition applies.
  - **If none exists,** QA says so and the Captain chooses before any decode. The reuse option is `20260922_2056`, because no metric-set choice was made on it.
- **Cycles:** systematic sample, odd k, **≥ 600 cycles** (≈ 2 × COH-GAIN's 309, for the narrower increment), frozen `selection.json` + SHA committed **before any decode**.
- **Rows:**
  - every WSJT-X decode in the selected cycles;
  - anchors as COH-GAIN (Amendment 2, δ = 0.7 s, frozen);
  - unencodable rows are credited zero and counted.
- **Truth and success:** as COH-GAIN §4: `out_crc_ok` AND `comparator.payload_match` with `v_star`.
- **Wrong payload:** `out_crc_ok` and NOT `payload_match`. It may be a genuine other station sharing the cell; this is not separated here.
- 🔒 **HK-037:** text and bit arrays live only inside the per-row evaluation function; only numbers are persisted.

## 5. Validity rows (mechanical; all must pass before any gate is read)

| row | predicate | guards | where the number comes from (HK-038) |
|---|---|---|---|
| **V1 pins** | DLL SHA-256 equal at start and end of every process; Python extractor and analysis script SHAs equal to the freeze commit; OSD gate read back as `nhard` 24, corr 0.10, sign fix 1 | all | by construction |
| **V2a synthetic decode** | 200 synthetic isolated signals (QA's `scene_render`, **Q-prefix** messages, off-lattice, −14 dB as COH-GAIN V2): C1, J2, J3, N1 each decode ≥ 0.99 | L1 gate | COH-GAIN V2(a): C3 scored 1.000 on that construction. A set below 0.99 on clean signals is a harness defect |
| **V2b mutation** | the same 200 with J2's and J3's Gray map replaced by the identity: each decodes ≤ 0.50 | that V2a can fail (HK-021 (k)) | a wrong bit map must break a correct metric; 0.50 is a decision value, far from 0.99 |
| **V3 C3 matches the build** | on the first 100 rows, C3's 174 values from Python equal the native fallback's (`ft8_coherent_fallback_at`, `out_llr174`) within the tolerance A2 used for COH-FALLBACK Stage 1 (QA quotes it) | C3, and with it X's population | COH-FALLBACK A2 established the equality; this checks the harness against today's DLL |
| **V4 control** | on rows our live run decoded (`live_hit` from a V4′-style replay, as COH-GAIN), G success ≥ 0.90 | all | COH-GAIN V4 used 0.90, against GAP-LOCATE's `P_ctrl` 95.96 % |
| **V5 determinism** | a second fresh process over the first 300 rows: every per-row field identical | all | all arms are deterministic |

## 6. Gates (computed by committed code; predicates are pure functions with tests that show each fires and does not fire, as `cg_rows.py`)

Statistics: the cycle-block bootstrap of `cg_rows.py` (blocks of 8 sampled cycles, B 10 000, seed 20261024, numerator and denominator resampled together).

- **N** = all WSJT-X rows in the sample, including unencodable rows.
- **NET_X** = 100 × (rows where G and C3 fail and X succeeds) / N, in pp.
  - It cannot be negative by construction: X is consulted only where both fail.
- **f_X** = X's wrong share = wrong / (wrong + right) on the rows where X returned a CRC-valid payload.

| row | predicate | guards | where the number comes from (HK-038) |
|---|---|---|---|
| **L1-GO** | `CI_lo(NET_X)` ≥ **BAR_L** | a Developer build spec | **BAR_L is the Captain's, ratified before any real-audio decode (§9 D3).** I propose 0.5 pp (§9) |
| **L1-STOP** | `CI_hi(NET_X)` < BAR_L | — | same |
| **L1-OPEN** | otherwise | — | — |
| **W-FAIL** | Wilson `CI_lo(f_X)` > **0.284** | blocks L1-GO from licensing a build | 0.284 = C3's own wrong share on G-fail rows in COH-GAIN, 198 / (198 + 500): the cost already accepted when the fallback was built. A set clearly worse than that is not a candidate |

**Outcomes:**
- **L1-GO and not W-FAIL** ⇒ I write a build spec for `coherent_fallback.c` (Developer, HK-011). Its replay carries the U′ instrument and a U′ bar set before ON data, as step 4 did. **That replay, not this arm, is the false-decode gate.**
- **L1-STOP** ⇒ L1 closes.
- **L1-OPEN** ⇒ the Captain chooses: more cycles on fresh positions, or stop.

## 7. Descriptive, mandatory (no row; cannot stop or license anything)

- **Per set:** rows where it is the first success in X, and rows where it succeeds at all on G∧C3-fail rows (overlaps shown as a 4-set table), each with its wrong count.
- **L2:**
  - C3 + OSD (shipped gate) over C3 BP-only: extra right and extra wrong;
  - the same for X with OSD.
  - Compare with C3O on file: +0.26 pp, 25 / 34 at `nhard` 40.
- **NET of G ∪ C3 over G** on this night, beside COH-GAIN's post-hoc +5.25. It is a sanity line, never a result.
- **By SNR tercile and by load quintile:** NET_X and f_X (COH-GAIN found C3's gain in crowding).
- **Noise leg:**
  - The 200 pinned NHARD-REP V2 noise WAVs, 10 seeded positions each (seed 20261024).
  - Report CRC-valid outputs per set, BP-only and with OSD.
  - ⚠️ HK-026: this leg has read 0 at every setting ever tried, so it bounds gross failure only and cannot rank sets.
- **Wall time per arm** (median per row), so a build spec can price the cost.

## 8. Order of work

1. QA's (k) review of this spec (FILE:LINE against `main` `5a9667ee`).
2. Corpus inventory and night choice, `selection.json` + SHA, and the metric-set code with its tests. All of it is committed before any real-audio decode.
3. The Captain ratifies BAR_L (D3), before any real-audio decode.
4. V2a/V2b (synthetic only), then V1, V3, V4, V5 and the main extraction. Detached and supervised (HK-013/HK-023), orphan check (HK-019).
5. Analysis by the committed script; QA's report (HK-034 format of the COH-GAIN report). Copy the run folder to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\` (standing rule).
6. My ruling and the prediction scoring.

**Estimate:**
- spec review + code ≈ ½–1 day;
- run ≈ 1–2 h CPU (COH-GAIN: 310 cycles ≈ 10 min on 4 workers for four arms; here 600+ cycles, 7 arms + L2 + the anchor replay);
- ruling ≈ 1 h.

## 9. For the Captain

**D3, BAR_L: the size of gain that justifies a Developer build of the fallback change.** It is set before any real-audio decode and never moved after (HK-038).

| option | what it means | consequence |
|---|---|---|
| **0.5 pp (recommended)** | about one-eighth of what the fallback itself added (+3.82 pp) | the change is contained in one native file plus its tests, smaller than the step-3 build that BAR_G guarded, so a smaller bar is proportionate. It would license a build on a gain of about 1 extra decode in 200 of WSJT-X's |
| 1.0 pp (BAR_G) | the bar you ratified 2026-10-06 for a native coherent build | stricter; more likely to read OPEN on one night, which means another run or a stop |

**Expected resolution:**
- For scale only, not a bar: on COH-GAIN's 309 cycles, C3's NET had a CI half-width of ≈ 0.7 pp.
- NET_X counts only gains, on fewer rows, so its interval should be narrower at 600+ cycles. QA reports the projected half-width from the pilot before D3 is asked, so the choice is made knowing what each bar can resolve.

## 10. Limits (to travel with any figure)

- **Positions:** the rows are WSJT-X's, not our candidates. In production the fallback works from our candidate positions and its gate (F1b), so a build's gain will be smaller: the fallback went from +5.25 at positions to +3.82 in replay.
- **Scope:** one 40 m night, one band; no subtraction interaction (a new decode in production is also subtracted, which this arm does not see).
- **Wrong payloads** include genuine co-channel stations; f_X is an upper bound on false decodes.
- **The joint metrics are QA's implementation of a prose method.** V2a/V2b show they decode clean signals and break when mis-mapped. They do not show the result is identical to WSJT-X's, and that is not the aim.

## 11. Predictions (blind; scored at the ruling)

| id | prediction | P | class |
|---|---|---:|:---:|
| X1 | NET_X point ≥ 0.5 pp | 0.40 | H |
| X2 | L1-GO at BAR_L = 0.5 pp | 0.30 | H |
| X3 | J2 and J3 together give more than half of X's first successes | 0.60 | H |
| X4 | W-FAIL fires | 0.20 | H |
| X5 | L2: C3 + OSD adds ≤ 0.3 pp over C3 BP-only | 0.75 | C |
| X6 | V2a passes first time for all four sets | 0.60 | C |

*Architect. Docs only; `src/`/`native/` diff empty.*
