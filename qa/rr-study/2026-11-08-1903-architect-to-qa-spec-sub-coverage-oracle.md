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
