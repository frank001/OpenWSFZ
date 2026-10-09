# COH-GAIN (A′ step 1) — how many WSJT-X-decoded signals would coherent bit formation, with per-signal fine sync, recover over our shipped extractor?

**QA report to the Architect.** Run 2026-10-06: main extraction 17:18:26Z → 17:27:48Z, V4′ replay 17:36:19Z → 18:11:38Z (`date -u`). Spec `2026-10-06-1625-architect-to-qa-spec-coh-gain-step1.md` (branch `arch/coherent-limb2`) with Amendments 1 (V2(b′), V2-T, denominator), 2 (the GO / C3O arms) and 3 (V4′). `BAR_G` = 1.0 pp, ratified by the Captain before any datum, FROZEN.

**Scope (verbatim):** *Offline, Python, at WSJT-X's own positions on one 40 m night. Extraction and decode only; candidate search, the managed layer and the live path are not exercised. WSJT-X's AP is off on this station.*

## Verdict: **COH-OPEN**

**NET_C3 = +1.33 pp of WSJT-X's decodes, 95 % CI [+0.57, +2.03]** (9,522 rows in 309 cycles, cycle-clustered block bootstrap, block = 8 sampled cycles, 39 blocks, B = 10 000, seed 20261006). `CI_lo` 0.57 < `BAR_G` 1.0 ≤ `CI_hi` 2.03, so the row is COH-OPEN: unresolved, the Captain's call (§6: more cycles at positions *i* mod 10 = 7, or stop). Blocks of 4 and 16 (reported, not used): [0.65, 1.98] and [0.42, 2.15].

🔴 **First-paragraph flag (spec §5): the top-5 blocks carry 50.4 % of the positive net gain**, which is more than one half, narrowly. 237 of 309 cycles carry a non-zero net difference, the largest |Σ d| in one block is 15 rows, so the gain is spread over many cycles but is not uniform across blocks. Read the interval with that in mind.

**Denominators (Amendment 1 item 4).** The verdict uses the **9,522 encodable rows** (9,524 frozen, 2 faulted). Rescaled to **all WSJT-X decodes in the sampled cycles** (the 636 rows the encoder could not pack are credited **zero** gain): NET_C3 = **+1.25 pp [+0.54, +1.90]**. Both are stated; the verdict row is the same on either.

## All validity rows PASS

| row | result |
|---|---|
| **V1** DLL pin | PASS: `libft8.dll` SHA-256 `2fa6d993…f365` (shim 20260058) equal at the start and end of the main run (and of the V4′ replay). |
| **V2** synthetic alignment (Amendment 1's (b′)) | PASS on the same 200 signals: (a) C3 success 1.000; (b′) median \|est_df − true_df\| 0.162 Hz ≤ 0.20, signed median −0.001 Hz (≤ 0.05), median \|est_dt − true_dt\| 1.3 ms ≤ 7.5 ms; (c) G success 1.000. Under the original (b) bar of 0.15 Hz it had failed; see "Method". |
| **V3** window | PASS: C3 estimate on the window edge in 212 of 9,522 rows (2.2 % ≤ 5 %). |
| **V4′** control reproduces (Amendment 3) | **PASS: G success on P1 = 0.969** (P1 = the 5,521 rows the batch-labelled replay matched in **batch 1**; bar 0.90, unchanged). The replay's per-cycle WSJT-X line count equals the row list's `ws_load` in all 309 cycles. |
| **V5** determinism | PASS: a fresh process over the first 300 rows, 0 differing fields (this includes rows computed before the padding fix). |

**V4 (original) FAILED and was replaced.** G success on all live-hit rows was **0.800** (6,697 rows) against 0.90. The Architect ruled the 0.90 bar a pre-subtraction calibration (`P_ctrl`), adopted V4′ blind (before seeing any NET), and refused a data-chosen stratum. V4′'s own descriptives confirm the cause: **G reads 0.5 % of the 1,182 rows the replay matched only in batch 2** (the residual-pass decodes it cannot see in the original audio), and 0.35 % of the 2,819 rows the replay did not match; the replay's batch-2 share of its matches is **17.6 %**. G's stratified rates on live hits (SNR bands 0.68 / 0.72 / 0.85 / 0.94; load quintiles 0.846 → 0.739; 0.966 on ≥ 0 dB in the lightest quintile, n = 473) are V4 diagnostics only.

## What the arms show (descriptive; the verdict is NET_C3 only)

| arm | success (rows) | NET vs G (pp) [95 % CI] | gains / losses vs G |
|---|---:|---|---|
| **G** (shipped, best of 9 cells) | 5,367 (56.4 %) | — | — |
| **C1** (coherent order 1, own fine sync) | 4,654 (48.9 %) | **−7.49 [−8.38, −6.64]** | 148 (1.55 %) / **861 (9.04 %)** |
| **C3** (orders 1+2+3, own fine sync) | 5,494 (57.7 %) | **+1.33 [+0.57, +2.03]** | 500 (5.25 % [4.69, 5.77]) / 373 (3.92 % [3.45, 4.40]) |
| **C3\*** (oracle, all 79 tones) | 5,544 (58.2 %) | +1.86 [+1.00, +2.66] | 531 (5.58 %) / 354 (3.72 %) |

- **The fine-sync estimator leaves ≈ 0.5 pp on the table** (C3\* − C3 = +0.53 pp), less than the Architect's CG4 expected (≥ 1.0 pp), and **the coherent orders matter**: C1 alone is much *worse* than G.
- **C3 wins and loses a lot, in different places (losses reported separately, as required).** Of C3's 500 gains, **361 are on live *misses*** (rows WSJT-X decoded and the live OpenWSFZ did not) and 139 on live hits; of its 373 losses, **366 are on live hits** and 7 on misses. NET_C3 **on live misses only = +12.53 pp [+11.10, +13.95]** of those 2,825 rows. By SNR band the gain is in the strong bands (≤ −16 dB: gains 109 / losses 113; −15…−6: 195 / 172; −5…+4: 157 / 75; ≥ +5: 39 / 13); by WSJT-X load it rises with crowding (Q1…Q5 NET_C3: −0.68, 0.00, +1.91, +1.68, **+3.43 [+2.98, +3.83]**).
- **dB shift between the G and C3 success-vs-SNR curves: median −0.08 dB** (per-level −0.08 / −0.09 / +1.00 at success 0.3 / 0.5 / 0.7). There is **no uniform SNR shift**: the gain is a rearrangement of which signals each extractor reads, not "better bits by x dB". The review §4 shift estimator (reconstructed from its description, an upper bound) gives −0.14 pp for that shift, so it does not predict the direct +1.33.
- **C3's estimates** (histograms): df is 6,655 of 9,522 within ±0.5 Hz and 8,800 within ±1 Hz; **dt is centred well below zero** (8,589 of 9,522 are negative; the 0.03 s bins from −0.12 s upward hold 1,153 / 2,377 / 2,544 / 2,515 / 657 / 55 / 65 / 156), i.e. the anchor δ of 0.7 s sits about 0.04–0.05 s above the true mean offset, consistent with the measured mean of 0.659 s. The ±0.12 s window still holds it (edge share 2.2 %), but a recentred δ (a step-3 detail) would put the estimates mid-window.
- **Post-hoc, NOT pre-registered (for the Architect's attention, do not cite as a result):** the union "G or C3" succeeds on 5,867 rows (61.6 %), i.e. **+5.25 pp over G** (this equals C3's gains, [4.69, 5.77]); it ignores cost and needs both extractors. Alongside it, CRC-valid-but-not-the-sent-payload rows: **G 69 (0.72 %), C1 187 (1.96 %), C3 202 (2.12 %), C3\* 146 (1.53 %)**. Part of those may be genuine different messages at the position; this was not separated.

## Amendment 2: sign-corrected OSD (descriptive, no row)

| arm | NET [95 % CI] | BP-fail rows | true payload recovered by corrected OSD on BP-fail rows | rows where corrected OSD returned a CRC-valid **wrong** payload | negated call returned path 0 |
|---|---|---:|---:|---:|---:|
| **GO** vs G | **+0.011 pp [0.000, 0.033]** | 4,155 | **1** | **271 (2.85 % of rows, 6.52 % of BP-fail rows)** | 0 |
| **C3O** vs C3 | +0.263 pp [+0.158, +0.371] | 4,028 | 25 | 34 (0.36 % of rows, 0.84 % of BP-fail rows) | 0 |
| C3O vs G | +1.60 pp [+0.83, +2.29] | | | | |

**At WSJT-X's positions a sign-corrected OSD (depth 2, `nhard` 40) is not a lever**: on G's LLRs it recovers 1 true payload in 4,155 BP failures while returning a CRC-valid wrong payload on 271 rows. For reference, G's own shipped (inverted) OSD returned an accepted codeword on 17 rows, **none** with the sent payload. The cost side (wrong payloads) is the at-position false-decode risk the Amendment asked to see.

## Descriptive tier V2-T (Amendment 1; −20 dB synthetic isolated signals; **NEVER cited as the gain**)
G 0.19, C1 0.67, C3 0.99, C3\* 0.985 on 200 off-lattice synthetic signals; estimator median errors 0.165 Hz / 1.4 ms (oracle 0.027 Hz / 1.4 ms). On real audio the same ordering does not hold (C1 loses to G by 7.5 pp), which is exactly why this tier is not a gain estimate.

## Method notes and findings along the way

- **The data-free Costas estimator has grating lobes.** Three 7-symbol blocks 36 symbols (5.76 s) apart make the df surface periodic at 1/5.76 s = **0.174 Hz** with near-equal lobes, so the argmax picks the wrong lobe about as often as the right one (median error ≈ one lobe, 0.162 Hz; not a bias, not noise, not a harness defect: the oracle on the same signals is 0.023 Hz). The spec's original V2(b) bar (0.15 Hz) was unpassable by construction; Amendment 1 replaced it. The grating ambiguity (0.17 Hz) is harmless for a 3-symbol coherent group.
- **Anchor mapping.** Per GAP-LOCATE Amendment 2: `t = WS_DT + δ`, raw, `freq` = WSJT-X's whole-Hz value; δ = **0.7 s** measured on this night (median of OWS_DT − WS_DT over 68,525 exact matches; mean 0.659 s, logging resolution 0.1 s), frozen in code.
- **Production OSD is sign-inverted (QA's finding, verified by the Architect from source).** `osd_decode` assumes positive LLR = bit 0 (`decode.c:501`); the extractor and BP use positive = bit 1 (`decode.c:1248–1250`). On 50 discarded pilot rows forcing the OSD path recovered the true payload on 0 of 50 as shipped and 16 of 50 with the sign negated. Consequence for this report: the **shipped** arms (G, C1, C3, C3\*) include the inverted OSD exactly as production does; GO / C3O are the corrected-sign emulation.
- **Instrument incidents, all disclosed:** (1) the first main run crashed (`IndexError`) on a late-starting row because `fine_sync`'s fixed zero-padding was shorter than a late anchor's symbols; fixed by sizing the padding from the requested indices (commit `c2815cd3`, regression tests), rows written before the crash never touched the overrun, V5 covers them. (2) The first analysis run wrote its result to `rows.json`, the frozen row list's own name, and overwrote it; restored from git (SHA equals the pin `34b97c22…`), the analysis output is now `analysis.json`, regression test added. The extraction had already finished with the frozen file. (3) **QA saw the descriptive NET figures before the V4 ruling** (it printed the analysis file before reading V4); the Architect did not, and ruled V4′ blind.

## Pins, build and instrument (HK-022)

- **DLL:** `libft8.dll` actual = pinned = `2fa6d99302c6c602231c870c1e61755aeeddb7ad1b9ce392fb98a4bdbd94f365` (shim 20260058, `origin/main` `be3cc5ac`), verified at load and recorded at the start and end of the main run and of the replay (`pins.jsonl`). The copy used is `artefacts/rr_2026-10-06_coh_gain/bin/libft8_20260058.dll`.
- **Frozen inputs, pinned by LF SHA-256 in code and asserted before extraction:** `rows.json` `34b97c22fa61f0cb17a3ac57b8a9cad385375467fa93b96ba1d3803ea6e5c0b6` (9,524 rows in 309 cycles, positions *i* mod 10 = 3 of the NHARD-REP frozen list; 636 rows excluded before extraction: 523 hashed-call tokens, 113 other); `synthetic_set.json` `ab787588…6a0e`; `synthetic_set_t.json` `3b5422ca…89fb`. The 1-in-10 sample stood (pilot: 50 rows from the disjoint *i* mod 10 = 7 cycles, 0.164 CPU s/row, 0.43 h projected for all rows).
- **Decode parameters:** every arm through `ft8_ldpc_decode_llrs` with `max_iters` 50, OSD depth 2, `nhard` 40, `kMinScorePass2` 10, `osdCorrThreshold` 0.10. GO / C3O: BP-only stage (`osd_depth` −1), then OSD on the negated LLRs with `max_iters` 1.
- **Commits (local, branch `qa/coh-gain`, not pushed):** harness and frozen inputs `fcd553df`, pilot `dcb23a74`, OSD arms `72590300`, padding fix `c2815cd3`, V4′ runner `20348645`, replay manifest `4b8d0089` (committed **before** V4′ was computed). **No test suite `--filter`** applies (the harness is Python run directly); 61 tests passing, mutants caught (11 of 12 first set, 6 of 7 on the OSD arms, one equivalent).
- **V4′ replay:** the NHARD-REP arm N40 over the 309 cycles, same build and pin, flag ON, threads 8, `nhard` 40, Test B rule, harness `--matched-batch-out`; exit 0 in 2,119 s; the V2′ probe passed at both points (P_hi rejected at 40).

## Not done / limits

One 40 m night; a 1-in-10 sample; WSJT-X's own positions (candidate search not exercised, so every gain here presupposes the signal is found); the **original** audio only (no residual or early-decode path); Python cost is not native cost; the 17.6 % of live hits that are batch-2 decodes are invisible to every arm here, and genuine decodes WSJT-X also missed cannot be seen (HK-026). The shipped decoder's batch-2 loss mechanism for the NHARD-REP finding is a separate question.

## Architect predictions, facts for the ledger (scoring is the Architect's)

| # | prediction | outcome |
|---|---|---|
| CG1′ | COH-GO at `BAR_G` 1.0 (0.45) | **COH-OPEN**: not GO |
| CG2′ | COH-STOP at 1.0 (0.25) | not STOP |
| CG3 | NET_C3 in [0.5, 4.0] pp (0.55) | **+1.33**: inside |
| CG4 | NET_C3\* − NET_C3 ≥ 1.0 pp (0.50) | **+0.53**: miss |
| CG5 | losses (G ok, C3 fails) ≥ 1 % of rows (0.60) | **3.92 %**: hit |
| CG6 | V2 passes first time (0.55) | no (the original (b) failed; (b′) passed) |

## Files
Run folder `artefacts/rr_2026-10-06_coh_gain/` (copied to `D:\Projects\claude\OpenWSFZ\qa\rr-study\results\2026-10-06-coh-gain-run`, files only, DLL copy not copied): `rows.csv` (numeric fields per row), `synthetic.csv`, `synthetic_t.csv`, `v5.csv`, `pilot_part.csv`, `pins.jsonl`, `v4p/` (replay outputs). Tracked here: this report, `analysis.json`, `rows.json` (frozen list), `pilot_result.json`, `v4p_replay_manifest.json`.
