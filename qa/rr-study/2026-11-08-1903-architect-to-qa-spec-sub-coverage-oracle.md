# `SUB-COVER` (#273) instrument spec: an offline oracle-subtraction bound, small, no build

**From:** Architect · **To:** QA · **Date:** 2026-11-08 19:03:52Z (`date -u`) · **Branch:** `arch/sub-coverage`
**Authority:** the Captain, 2026-11-08: "go with your recommendations, move on to #273". My recommendation was #273's cheap causal test: offline, no `src/` change. His standing size rule from earlier the same day applies: "keep the verification tests small".
**Base:** `main` `e3db42cf`. **QA-only tooling, no `src/` or `native/` change, no replay of the station, no station use.** This document is docs only.

🟢 **Size rule.** One offline pass over GAP-RELOCATE's 400 cycles of `20260925_2010`, buffers and forced legs only. **No replay arm, no second night, no pilot.** Compute budget about 1 h on the PC; if QA's estimate in the (k) review is over 2 h, it says so and the Captain decides.

---

## §0. The question, in one paragraph

**#273 asks:** would subtracting **more of what we already decode** recover the WSJT-X decodes that sit next to them?
- Today, decodes that fail `IsReencodable` (hashed `<…>` calls, < 3 tokens: 375 of 8,578 batch-1/2 decodes, 4.4 %) are never subtracted.
- Batches 3 and 4 are subtracted only by L1′'s late round, which ships OFF.

NR-TAX found the unreached rows sit next to such neighbours **16× as often** as reached rows (CU-d, 333 rows, 2.75 pp). That is an association. **This instrument measures the bound:** subtract **every** signal we decode, perfectly placed and with the correct payload, then ask the frozen forced extractors whether the unreached rows become decodable. If even the oracle recovers little, #273 is closed without a build.

## §1. The instrument

**Corpus and populations:** exactly GAP-RESIDUAL's.
- Night `20260925_2010`, GAP-RELOCATE's 400 cycles in its order (`selection400.json`, sha `42e09239…`), n_ref 12,124.
- NR = the 1,589 rows no extractor reaches on O, R2 or R3.
- Hits = 9,931.
- NR-TAX's categories as frozen in `nrtax_defs.py` (`cebd2acf`).
- The BOTH/OFF arm's decode dump gives "what we decode", with natives: unrounded `OutDtS`, `OutFreqHz`, every batch 1–4.

**The oracle buffer O★ per cycle:** O (the cycle's normalised PCM, as captured for GAP-RESIDUAL) minus the fit of **every decode the product published in that cycle, batches 1–4**.
- **Tones:** from our decoded text if `IsReencodable` and `EncodeMessage` accept it. **Otherwise** from the matched WSJT-X text for that decode (this is the oracle part: it stands in for "re-encode from the payload bits"). If neither encodes, the decode is not subtracted and is counted (`unencodable`).
- **Placement:** our own native dt and freq (never WSJT-X's DT: the convention offset is about 0.7 s, MEMORY).
- **Fit:** the product's own fitter through the interop, `SubfeasFitSignal` as `SubtractionPass.cs:395` calls it, on the analytic signal of O (`:352`). All fits are on O and subtracted together, as the residual pass does (`:425–431`). A fit that returns −3 is counted (`fit-zero`), not hidden (NR-TAX V4's blind spot).
- **Hash state:** bracketed with `HashStateSave`/`Restore` around anything that decodes or unpacks, as in GAP-RESIDUAL.

**The forced legs:** GAP-RELOCATE's own `gr_forced.force_cycle`, unchanged (frozen δ_p 0.6 s, δ_c 0.7 s, the same comparator). Only the PCM argument changes, to O★, exactly as GAP-RESIDUAL changed it to R2/R3. They run on O★ for **every NR row** and **every hit that was subtracted into O★** (the control, row O-CTRL).

## §2. Rows

**Freeze:** the code, the O★ builder and these predicates are committed before any O★ output exists.

| row | predicate (mechanical) | where its bar comes from |
|---|---|---|
| **O-REPRO** | the forced legs on the stored R2 ∪ R3 buffers give GAP-RESIDUAL's class counts exactly (RC 133, RG 51, RW 77, RP-search 10) | GAP-RESIDUAL's report; the same code and buffers, so exact |
| **O-CTRL** (HK-026, the subtraction actually removes) | of the hits subtracted into O★, the share the forced legs **still decode at their own position** on O★ ≤ the same share on R2 for the batch-1 hits that R2 subtracted, **+ 2 pp** | NR-TAX B4(b) already ran the legs on R2 for every hit (35,493 records), so R2's figure is **on file**. QA computes it **in the freeze, before O★ exists**. The +2 pp is mine, for single-pass vs sequential fitting; QA may challenge it in (k) |
| **O-ENC** | `unencodable` + `fit-zero` ≤ 2 % of the decodes to subtract | none on file for O★; it is a validity floor, and if it fires the bound is read as "≥" only |

**Readout (the bound), with a cycle bootstrap B = 2000, seed 20261108:**
- **G★** = NR rows decodable on O★ by any leg (primary or coherent, as GAP-RESIDUAL's classes) that are **not** already decodable on R2 ∪ R3, as pp of n_ref.
- Split by NR-TAX category:
  - CU-d with a batch-3/4 neighbour (**L1′'s territory**: L1′ already subtracts these when ON);
  - CU-d with only non-reencodable batch-1/2 neighbours (**#273 proper**);
  - CU-u;
  - CS;
  - the rest.
- **G273** = G★ **minus the L1′-territory stratum.** This is what a #273 build could add beyond L1′.
- **Wrong payloads** on O★: the legs' non-matching outputs at NR positions, counted. That is the U-side warning COH-RES-CAND taught.

**Decision rule (pre-registered):**

| outcome | condition | consequence |
|---|---|---|
| **BUILD-WORTH** | CI_lo(G273) ≥ 1.0 pp | I write a #273 build spec (the Captain's go first) |
| **CLOSE** | CI_hi(G273) < 0.5 pp | #273 is closed with this bound |
| **BETWEEN** | otherwise | to the Captain with the numbers |

**Bars (HK-038):** both come from COH-RES-CAND (2026-11-08, PC, `20260930_1930`), the only lever with both a measured ceiling and a build result.
- Its build captured **62 of 153** ceiling rows, **0.405**. That is a different night and a different lever, so it is indicative only; I state it as the one data point on file, not a law.
- A 1.0 pp bound at that capture is ≈ 0.4 pp built, about what COH-RES-CAND's NET resolved with 400 cycles (CI_lo 0.29).
- A 0.5 pp bound is ≈ 0.2 pp built, which a 400-cycle arm cannot separate from 0 (half-width ≈ 0.2 pp).

## §3. What this does not measure

- **Fit quality for signals we already subtract (CS, 700 rows).** O★ uses the same fitter, so the CS stratum shows coverage effects only. "Subtract better" is a different question.
- **Neighbours we never decoded (CU-u):** O★ does not subtract them, so it is not an oracle for "decode more first". CU-u gains, if any, come only through other subtracted signals.
- **Time:** O★ has no budget. A build would have to fit within the 13 s cycle.
- **Not a replay:** forced legs at WSJT-X's position are an upper bound on what a build at the product's own positions would reach.

## §4. Order and cost

1. QA's (k) review, rows only. **QA confirms that the stored O / R2 / R3 buffers and the dump are still on disk** (`_qa-scratch\gap-residual\`, 1.3 GB at 19:05Z, `cap\` present; I have not opened them). If they are gone, a re-capture is GAP-RESIDUAL's OFF arm again (about +45 min), and the Captain is told.
2. Freeze, including the R2 control figure for O-CTRL.
3. Run: build O★ (400 cycles of fits, from the stored O) and the forced legs. NR-TAX's B4(b) did 35,493 records in 848 s, and this is under half that many records plus the fits, so **about 30–60 min**.
4. A short report: rows, G★, G273 and the strata, wrong payloads.
5. My ruling: BUILD-WORTH, CLOSE or BETWEEN.

Working files go in `_qa-scratch\sub-cover\` (HK-037: no message text leaves the functions that read it; the oracle's text lookup happens inside the builder). Aggregates only in the report.

## §5. Predictions (Architect; scored at the ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| SC-1 | O-REPRO and O-CTRL pass on the first run | 0.70 | C |
| SC-2 | G★ point estimate ≥ 1.0 pp | 0.50 | H |
| SC-3 | outcome CLOSE | 0.40 | H |
| SC-4 | outcome BUILD-WORTH | 0.25 | H |

**Reasoning.**
- L1′ already took most of the batch-3/4 neighbourhood: +0.77 pp on its night, from 221 CU-d rows with such neighbours on this one.
- #273-proper is the 112-row stratum, 0.92 pp **associated**, and an association rarely converts at 1:1.
- So G273 is more likely small than large.

🔴 **Bias check:** HYPOTHESISED calls lean toward "a findable gain". BUILD-WORTH is held at 0.25.

## §6. Amendment 1 (2026-11-08 19:09:23Z, `date -u`): QA (k) review adopted in full

QA (by message): **ACCEPT** the question, the decision rule and the readout; three row changes and one premise correction. All are adopted, and they replace the named parts of §1 and §2. **Buffers: intact** (1,182 files, every SHA-256 matching `capture_index.tsv`; `forced_all.jsonl` 35,493 records; dumps present). No re-capture.

**A1.1 Premise corrected (ledger E137, mine).** §1 said the dump gives unrounded natives. **It does not:**
- `nc_dump` has dt to 0.01 s and integer freq;
- the population rows carry the published 0.1 s dt;
- the product feeds the fitter the **unrounded** native dt (`SubtractionPass.cs:395`).

Fitting at published values would misplace by up to 50 ms and make O★ a worse subtractor than R2. **Now:**
- **Batches 1–3:** re-run native `DecodeAll` on the stored O, R2 and R3 buffers (the product's own inputs) to recover unrounded dt and freq. Hash state is bracketed.
- **Batch 4** (fallback rows, 1,227 of 9,931 hits = 12.4 %) has no stored natives. Place them from the published values and let the fitter refine. The report says so, and O-ROUND decides whether that stratum reads as a lower bound.

**A1.2 New row O-BUILD** (the builder is the new instrument, and O-REPRO does not test it).
- Given only the batch-1 re-encodable decodes with their recovered natives, the builder reproduces the stored R2 for all 400 cycles. The test is bit-identical, or, if the fitter's parallel order matters, **max |diff| ≤ 1e-5 × the buffer's peak**. The observed figure is stated in the freeze.
- **If O-BUILD fails, stop and report. No retries beyond that.**

**A1.3 New row O-ROUND** (a freeze-time sensitivity, on the same batch-1 set).
- Rebuild with dt rounded to 0.1 s and freq to integer, and report the change in the still-decoded share.
- **If it exceeds 0.5 pp, the batch-4 stratum (placed from rounded values) is read as a lower bound.**

**A1.4 O-CTRL replaced (ledger E138, mine).** My +2 pp margin was unsupported on three counts, and the data on file runs the other way:
- (a) R2 is built by the same single-pass procedure, so my justification does not apply.
- (b) On the same 7,239 batch-1 hits, the share still decoded is: O 88.16 %, R2 17.16 % [16.42, 17.88], R3 14.46 %. So R3 − R2 = −2.69 pp [−2.97, −2.41]: subtracting more neighbours **lowers** it, and +2 pp would let a degraded builder through.
- (c) The populations differed.

**New O-CTRL, paired and stratified:**
- the 7,239 batch-1 hits: CI_hi(share_O★ − share_R2) ≤ 0;
- the 1,339 batch-2 hits: CI_hi(share_O★ − share_R3) ≤ 0 (R3 subtracted them, and the records are on file);
- batches 3–4 and oracle-rescued decodes have no on-file comparator, so they are **reported, not gated**.

**Bar source (HK-038):** the on-file R3 − R2 drift, stated in the freeze. **"Still decodes at its own position"** = primary leg found **or** coherent `v3_match` (either leg). The definition is frozen, because the legs alone give 5.11 % vs 16.2 %.

**A1.5 O-ENC's bar (ledger E139, mine).** The 2 % had no data behind it.
- The freeze states the **fit-zero share of R2's own fits** (from `stage.csv` or the residual-pass counts) as the bar's source.
- The bar is that figure. 2 % is kept only if the figure supports it.
- `unencodable` is reported beside it. The oracle text should make it tiny, given today's 4.4 % `IsReencodable` failures.

**A1.6 Paths.** The Frank-path check on `gr_forced`, `gr_common` and `nrtax_force` goes in the freeze commit (as COH-RES-CAND A1.5).

**A1.7 Cost.** Machine time is about 30–60 min (QA measures the `DecodeAll` rate in the freeze). QA's own effort is the builder: a few hours, Python/ctypes or a small C# tool through the interop, **no `src/` or `native/` change**, and O-BUILD is its test. It is within the size rule: no replay, no new night.

**A1.8 Prediction SC-1, revised pre-data** (the rows changed):
- now "O-REPRO, O-BUILD and O-CTRL (as amended) pass on the first run", **P 0.60** (was 0.70 for two rows);
- SC-2 to SC-4 are unchanged.

**QA may proceed to the freeze with this text.**

## §7. Amendment 2 (2026-11-08 19:33:07Z, `date -u`): freeze-time facts; O-CTRL re-ruled before any O★ output

**No O★ output exists** (QA stopped before building it). Everything here is fixed **before** the readout.

**Freeze-time results (QA):**
- **O-BUILD PASS.** R2 is reproduced bit-identically in 400 of 400 cycles (max relative diff 0.0; 6,877 fits).
- **O-REPRO PASS.** Exact: RC 133, RG 51, RW 77, RP-search 10, NR 1,589.
- **O-ROUND:** −0.014 pp [−0.042, 0.000] on 7,239 batch-1 hits, ≪ 0.5 pp. **The batch-4 stratum is NOT read as a lower bound** for placement reasons.
- **A1.1's re-decode is replaced.** The capture already stores the product's own unrounded natives (`cap/off/native/<stamp>.tsv`, in production order), and they are read directly (QA Q39).

**QA's correction (QA ledger Q40):** the shares quoted in its (k) review were keyed per cycle index only, so cycles overwrote each other. **Corrected**, keyed by (stamp, idx), "still decodes" = either leg:
- batch-1 hits: O 93.12 %, R2 2.82 %, R3 2.87 % (6,978 rows with R3);
- **drift R3 − R2 = +0.10 pp [+0.03, +0.18]**;
- batch-2 hits on R3: 3.44 %.

The "−2.69 pp" in A1.4(b) is **withdrawn**. The on-file drift is slightly positive, so A1.4's bar `CI_hi ≤ 0` has no support and could fire on a correct builder.

**A2.1 O-CTRL, final (replaces A1.4's bar; pairing and strata kept):**
- the 7,239 batch-1 hits: **CI_hi(share_O★ − share_R2) ≤ +2.0 pp**;
- the 1,339 batch-2 hits: **CI_hi(share_O★ − share_R3) ≤ +2.0 pp**;
- batches 3–4 and oracle-rescued decodes: reported, not gated.
- "Still decodes" = primary found or coherent `v3_match`.

**Where +2.0 pp comes from (HK-038),** all from QA's corrected on-file figures, `main` `c2c85c45` capture, `20260925_2010`, PC:
- An unsubtracted hit still decodes at about 93 % (O 93.12 %), and a subtracted one at about 2.8 %. A builder that fails to subtract a fraction f of the hits therefore shows about **+0.90 pp per 1 % of f**, so +2.0 pp catches a failure on about ≥ 2.2 % of the hits.
- The legitimate drift from removing more neighbours is +0.10 pp for +1,339 subtracted signals (+19 %). O★ subtracts roughly +5,000 more than R2 (QA's estimate, to be stated in the report). A linear extrapolation of the drift gives about +0.4 pp, well inside the bar.
- **Stated honestly:** the number equals my original margin, but its first justification (single-pass vs sequential) was wrong. E138 stands for that justification, not for the number.
- The batch-1 check is nearly redundant with O-BUILD. **The informative gate is batch-2 against R3.**

**A2.2 O-ENC, final:** the bar is **R2's own fit-zero share, 160 of 6,877 = 2.33 %**. My original 2 % would have fired on R2 itself (E139). `unencodable` is reported beside it.

**QA proceeds:** freeze commit, O★ build (about 7 min), forced legs (about 5 min), report.
