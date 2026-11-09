# `SUB-COVER v2` (#273) instrument spec: test #273-proper with oracle text that is NOT ours

**From:** Architect · **To:** QA · **Date:** 2026-11-09 16:32:08Z (`date -u`) · **Branch:** `arch/sub-coverage`
**Authority:** the Captain, 2026-11-09: "2. lets try a 2nd version" (on the v1 ruling `0cc83545`, §3, which recommended parking #273).
**Base:** v1 spec `871e163f` with Amendments 1 and 2 (`0cd47417`, `4f3a477a`); v1 ruling `0cc83545`; QA report `ef2fc84b`. **Everything in v1 stands unless this document replaces it by name.**
**QA-only tooling, no `src/` or `native/` change, no replay, no station use.** Docs only.

🟢 **Size rule (the Captain, 2026-11-08: "keep the verification tests small").** The same 400 stored cycles of `20260925_2010`, and v1's builder with one route changed. **No replay, no new night, no pilot.** Machine time about 20 min; QA effort about 1–2 h (the matcher and one new row). If QA's (k) estimate is over 3 h of effort, it says so and the Captain decides.

---

## §0. Why v1 did not test #273-proper (E140), and what v2 changes

- v1's "oracle text" for a decode that does not re-encode came from the WSJT-X decode **matched by text equality**. A text-equal match is our own text, so it never encodes when ours did not (455 of 455 identical, `oracle_text_used` = 0).
- So the 112 NR rows whose stronger neighbours are hashed (`<…>`) or short decodes never got a subtracted neighbour. Their 0 of 112 is not evidence.
- **v2 matches by position, not text,** and accepts WSJT-X's text only if it is **the same transmission** as our decode by a mechanical check (§1.2). WSJT-X shows a hashed call it has resolved in brackets (`<PJ4/Q1ABC>`); our decoder, without the call in its table, shows `<...>`. Encoding WSJT-X's text (brackets handled as §1.2 says) gives the payload that was transmitted, which is what a build with our own 77 payload bits would subtract.
- **What the encoder does with brackets (checked, `native/ft8_lib_vendor/ft8/message.c`):** `save_callsign` **rejects** `<` and `>` (`:563–565`, not in `FT8_CHAR_TABLE_ALPHANUM_SPACE_SLASH`), so a bracketed text does not encode as written. With the brackets stripped, `pack28` sends any call that is not a standard basecall as its 22-bit hash (`:718–725`). A bracketed **standard** call, or a type-4 message whose hashed side was `call_de` (`:241–245` chooses the side from the brackets), can therefore encode to a different payload. §1.2's consistency check catches that and the decode is counted `inconsistent`, not subtracted.

**Rejected alternative (stated so nobody re-proposes it as cheaper):** exposing our decoder's own 77 payload bits per decode. `FT8Result` (48 bytes: freq, dt, snr, text) carries no payload. Exposing them is a `native/` change and needs a Developer session (HK-011), which is larger than this test. **A #273 build would need exactly that change.** This instrument asks whether it is worth making.

## §1. What changes in the builder

### §1.1 Route order per published decode (batches 1–4), replacing v1 §1 "Tones"

1. **Own text.** `EncodeMessage` on our text, **without** the product's `IsReencodable` pre-filter (v1 applied it, and short messages fell through to the oracle route). If it encodes, use it (`route = own`).
2. **Position oracle** (only if route 1 fails): §1.2. If it passes, use the encoded WSJT-X text (`route = oracle`).
3. Otherwise not subtracted, counted (`unencodable`, sub-counted as `no_candidate`, `ambiguous` or `inconsistent`, per §1.2).

Placement, fit, all-on-O single pass, hash bracketing: **unchanged from v1** (natives from `cap/off/native/<stamp>.tsv`, Amendment 2).

### §1.2 The position oracle (mechanical)

For one of our decodes that route 1 rejects, at native freq `f` and dt `t`:

- **Candidates:** the WSJT-X decodes of the same cycle with `|f_W − f| ≤ τ_f` and `|(t_W − c) − t| ≤ τ_t`, where `c` is the DT convention offset.
- **Where `τ_f`, `τ_t` and `c` come from (HK-038):** **from this night's own text-equal pairs, in the freeze, before any O★v2 output.**
  - Take every (our decode, WSJT-X decode) pair that v1's text matching paired, in these 400 cycles. Our side uses its native freq/dt.
  - `c` = the median of `t_W − t`.
  - `τ_f` and `τ_t` = the 99th percentile of `|f_W − f|` and `|(t_W − c) − t|` respectively.
  - QA states N, `c`, `τ_f`, `τ_t` in the freeze. **If `τ_f` > 6.25 Hz (one FT8 tone) or `τ_t` > 0.16 s (one symbol), stop and report.** A tolerance wider than one tone or one symbol would admit a different transmission.
- **Consistency check (the "same transmission" predicate):** for each candidate, strip `<` and `>` from its text and encode it with `EncodeMessage`. Take the 77 payload bits from the tones (`SubfeasPayload.ExtractPayload77`, as `SubtractionPass.cs:344` does) and unpack them with the shim's `ft8_coherent_fallback_unpack` (`ft8_shim.c:2652`). The whole step is bracketed with `HashStateSave`/`Restore` (encoding **writes** the call into the hash table: `save_callsign` → `save_hash`, `message.c:588–589`), so nothing leaks into later decodes. The candidate is consistent if and only if the unpacked string equals our text **after one normalisation applied to both strings: every bracketed token becomes `<...>`**. Nothing else is normalised. A hashed call that unpacks without brackets fails the check (conservative).
- **Accept** if exactly one candidate is consistent. **Zero** consistent candidates ⇒ `inconsistent` (or `no_candidate` if there were no candidates at all). **Two or more** ⇒ `ambiguous`. Neither is subtracted.
- HK-037: the text lookup, encoding and comparison happen inside the builder; only route counts and aggregates leave it.

**What the check cannot see:** the hashed call itself. `<...>` is the same for every call, so a wrong resolution by WSJT-X would pass. The new row O-ORC (§2) catches that from the outcome, because a wrong hash means a wrong 22 bits, and a wrongly subtracted signal stays decodable.

## §2. Rows (v1's rows kept; changes and additions named)

**Freeze:** builder, matcher, `c`/`τ` derivation and these predicates are committed before any O★v2 output exists. O★v1's outputs exist and are public, so v2's freeze also records **SHA-256 of O★v1's per-row result file**, which is the base of the incremental readout.

| row | predicate (mechanical) | where its bar comes from |
|---|---|---|
| O-REPRO | unchanged (v1: exact; RC 133, RG 51, RW 77, RP-search 10, NR 1,589) | GAP-RESIDUAL's report, same code and buffers |
| O-BUILD | unchanged: batch-1 re-encodable decodes reproduce stored R2, bit-identical in 400/400 | v1 Amendment 2 (observed bit-identical) |
| **O-V1** (new) | with route 2 disabled and route 1's pre-filter restored, the builder reproduces O★v1 bit-identically in 400/400 cycles | v1's O★ buffers/results are on file (same code path), so exact |
| O-CTRL | unchanged from v1 Amendment 2 (paired CI_hi ≤ +2.0 pp, batch 1 vs R2, batch 2 vs R3; "still decodes" = primary found or coherent `v3_match`) | v1 A2.1 |
| **O-ORC** (new, HK-026: the oracle tones actually remove the signal) | among decodes subtracted by **route 2**, the share that still decodes at its own position on O★v2 has **CI_hi ≤ 3.44 % + 2.0 pp = 5.44 %** (cycle bootstrap) | 3.44 % = batch-2 hits still decoding on R3, on file (v1 Amendment 2, QA's corrected figure); +2.0 pp is v1 A2.1's margin with the same derivation (≈ 0.9 pp per 1 % unsubtracted, O 93.12 %). **If route 2 subtracts fewer than 50 decodes, O-ORC is reported, not gated**, and the report says the oracle had too little to work on |
| O-ENC | `unencodable` + `fit-zero` ≤ **2.33 %** of decodes to subtract (R2's own fit-zero share, v1 A2.2). If it fires, figures read as "≥", as in v1 | v1 A2.2 |

**If O-V1 or O-ORC fails, stop and report. No retries beyond that.**

**Readout (cycle bootstrap B = 2000, seed 20261109):**
- **G★v2** and **G273v2**, defined exactly as v1's G★ and G273 (G273 = G★ minus the L1′-territory stratum), with v1's strata.
- 🔴 **The new number, Δ273p:** NR rows in the **#273-proper stratum (112 rows)** decodable on O★v2 but not on O★v1 ∪ R2 ∪ R3, in pp of n_ref (12,124). Its ceiling is 112 rows = 0.92 pp.
- Route counts: own / oracle / no_candidate / ambiguous / inconsistent; and among the 537 v1-unencodable decodes, how many routes 1 and 2 now place.
- Wrong payloads at NR positions on O★v2, counted (as v1).

## §3. Decision rule (pre-registered)

The decision is on **Δ273p**, the only thing v1 did not test. G273v2 is reported beside it.

| outcome | condition | consequence |
|---|---|---|
| **BUILD-WORTH** | CI_lo(Δ273p) ≥ 0.40 pp | I write a #273 build spec (native payload exposure + subtraction of hashed/short decodes); the Captain's go first |
| **CLOSE** | CI_hi(Δ273p) < 0.25 pp | #273 closed with v1 + v2 |
| **BETWEEN** | otherwise | to the Captain with the numbers |

**Where the bars come from (HK-038):** v1's bars (1.0 / 0.5 pp) cannot be used here: Δ273p's ceiling is 0.92 pp, so BUILD-WORTH at 1.0 could never fire.
- The one capture ratio on file is COH-RES-CAND's 0.405 (62 of 153 ceiling rows; PC, `20260930_1930`; a different night and lever, **indicative only**, as in v1).
- 0.40 pp of bound ≈ 0.16 pp built; 0.25 pp ≈ 0.10 pp built.
- **Stated honestly:** a 0.16 pp build is below what one 400-cycle arm resolves (COH-RES-CAND's half-width ≈ 0.2 pp). So BUILD-WORTH here means "worth a build whose acceptance needs a longer arm or a second night", and the build spec would have to say so. I chose these bars because anything higher is unreachable at this ceiling. If the Captain would rather not build anything that small, v2's value is that it **closes** #273 with evidence. That is CLOSE or a low BETWEEN.

## §4. Predictions (Architect; scored at the ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| V2-1 | O-V1 and O-ORC both pass on the first run | 0.65 | C |
| V2-2 | route 2 places ≥ 50 % of the decodes that route 1 rejects | 0.55 | H |
| V2-3 | outcome CLOSE | 0.50 | H |
| V2-4 | outcome BUILD-WORTH | 0.15 | H |

**Reasoning.** The 112 rows are an association (16× in NR-TAX), and associations rarely convert 1:1. L1′'s realised NET was about 0.77 of its stratum's oracle, but L1′'s neighbours were strong decodes. Hashed and short messages are often weaker or rarer, and WSJT-X must also have decoded the neighbour for route 2 to work. 🔴 **Bias check:** HYPOTHESISED calls lean toward "a findable gain"; BUILD-WORTH is held at 0.15.

## §5. Order and cost

1. QA's (k) review, rows and bars only. QA confirms that O★v1's per-row results and the stored buffers are still in `_qa-scratch\sub-cover\` and `_qa-scratch\gap-residual\`.
2. Freeze: `c`, `τ_f`, `τ_t` with N; O★v1 result SHA; O-V1 run (it needs no O★v2 output).
3. Run: O★v2 build (≈ 7 min) and forced legs (≈ 5 min).
4. Short report: rows, Δ273p, G★v2, G273v2, strata, route counts, wrong payloads.
5. My ruling.

Working files: `_qa-scratch\sub-cover\v2\` (HK-037). Aggregates only in the report.

## §6. Amendment 1 (2026-11-09 16:41:30Z, `date -u`): QA (k) review adopted in full, before any freeze

QA's (k) review: **ACCEPT** the question and the readout. Buffers and O★v1's per-row results are on disk (`_qa-scratch\sub-cover\`: 800 buffers, `forced_*.jsonl`, `sc_result.json`; natives `gap-residual\cap\off\native\`, 400 files). Effort is about 2 h, and machine time about 20 min. **These rows replace the named parts of §1–§3.**

**A1.1 O-ORC fires only on a demonstrable excess (ledger E143, mine).** As written (CI_hi ≤ 5.44 %), it fails a **correct** builder more often than not:
- The baseline is 3.44 %. At n ≈ 300 route-2 decodes, the binomial half-width alone is ≈ 2.1 pp, so a clean CI_hi sits near 5.5 %.
- **New predicate:** O-ORC **fails** only if **CI_lo > 5.44 %** (the share still decoding is demonstrably above the R3 baseline + 2 pp). Otherwise it passes and is reported with its CI.
- A wrong-hash or wrong-payload failure leaves tens of percent still decoding, so it still fires. The < 50 report-only floor stays.

**A1.2 O-ENC is report-only (ledger E142, mine).** The 2.33 % bar fires by construction:
- v1's fit-zero **alone** was 251 of 10,133 = 2.48 %, with `unencodable` excluded, from v1's report.
- R2's 2.33 % is a different population (batch-1 re-encodables only).
- **New rule:** report `unencodable` and `fit-zero` with their shares. As in v1, every figure is read as "≥".

**A1.3 Candidate pool (clarification).** A WSJT-X decode already text-matched to another of our decodes is **excluded** from route 2's candidates. It belongs to that decode.

**A1.4 The true ceiling, stated at freeze (computable from v1's data, so it is not an O★v2 output).**
- QA counts how many of the 112 #273-proper rows have at least one neighbour that **route 1 rejects** (the 0.92 pp includes rows whose neighbour already re-encodes), and states it in pp of n_ref.
- **If that ceiling is < 0.40 pp, BUILD-WORTH cannot fire.** The freeze says so, and the outcomes are CLOSE or BETWEEN. **No bar is moved.**

**SC-wise:** V2-1 now reads "O-V1 and O-ORC (as amended) pass on the first run". I raise its P from 0.65 to **0.75** pre-data, because the amended O-ORC no longer fails a clean build by chance. V2-2..4 are unchanged.

**QA may freeze with this text.**
