# KNOWN-ERASURE: ignore a decoded neighbour's tones when reading a weak signal's bits

**To:** QA, who turns §2 into one Developer task (HK-015) and runs §3–§4
**From:** Architect, 2026-11-27
**Approved:** Product Owner, 2026-11-27 ("yes, write it": the decode-step change after XC-ROUND).
**Why:** after PAYLOAD-FIT and XC-ROUND, most crowded misses are **K2**: a candidate is found at the missed signal T and tried, but no decoder decodes it (SUB-PROBE: 65–75 % of the classified crowded misses). **K2 rises steeply with the neighbour N's strength** (H40: 14 cases with a weaker N, 83 within ±3 dB, 215 and 183 with a stronger N; `sub-probe-result.md` Table 3). Strong neighbours are only partly removed: those at −10 dB or stronger stop a median 4.8–5.8 dB short of the noise ceiling, a quarter of them 8–11 dB short (SUB-PROBE §5.1, decoder `fc3d5b5c`).

## 0. What the data rule out (Architect, from the shipped build's probe rows; counts only)

"The best failed attempt is 5–6 parity checks short" (SUB-PROBE) **is not a near-miss signature.** Over all kept candidates that failed every tier in the XC-ROUND confirmation runs (`_qa-scratch\lc-base\runs\xn_*\probe.tsv`, build `f9662335`), **15,469 of 45,322 (S40), 24,238 of 69,543 (H40) and 23,769 of 70,117 (H20)** end ≤ 5 unsatisfied checks on their best tier. Most of those are noise. So:

- **OSD or any "almost decoded" rescue is not the lever.** It would act on tens of thousands of noise candidates per slice. OSD also measured NET ≈ 0 in DR-0 (plan K5; lean has it OFF, spec-dr2 §2.3).
- **More BP iterations** buys the same thing more slowly.
- A-priori decoding cannot be checked against the reference, which runs with AP off.

What does separate the K2 misses is **the strong neighbour**. That is where this change acts.

## 1. The mechanism (code at `main` `a1e1c84c`)

- Tier A reads each symbol's bits from the 8 tone bins of the waterfall, `ft8_extract_likelihood` → `ft8_extract_symbol` (`native/ft8_lib_build/patched/ft8/decode.c:379`, `:1466`). A bit's likelihood comes from the **strongest** bin with that bit = 1 against the strongest with bit = 0.
- A strong neighbour within 50 Hz puts one of its own tones, at each of its symbols, into or next to one of T's 8 bins. What is left of it after subtraction is still several dB above the noise, and above a weak T. **That bin wins the maximum, and T's bits for that symbol are read from N's tone.**
- **N's tones are known exactly:** it is a published result, and its payload, frequency and time are in the cycle (`res_pl`, `results[]`, `ftz_decoder.c`). Treating those bins as **erased** (unknown) costs T little: it loses one bin of eight in the symbols where N lands on it. It stops N from being read as T.

## 2. The change (Developer)

**Where:** lean only, **rounds 1–3 and the XC round** (round 0 decodes all its candidates in parallel before any result is known, and is not touched). **Tier A and CQ-AP** (both read `ft8_extract_likelihood`). Tier B (coherent, `cf_process_one`) is not touched.

1. **The erasure mask, per round:** before the round's tier A, for every result already published in this cycle **with SNR ≥ −10 dB** (the SUB-PROBE boundary: weaker signals are removed to the noise floor and leave nothing to erase), mark in a mask the same size as the waterfall every cell where that result transmits. For each of its 79 symbols: the bin of its tone (`ft8_encode(res_pl[k])`) at its frequency and time on the waterfall's oversampled grid, **± 1 frequency bin** (3.125 Hz at `freq_osr` 2), and **every time block its symbol overlaps**.
2. **The extraction with the mask:** a variant of `ft8_extract_likelihood` (or a mask argument; the vendored function stays bit-identical when the mask is NULL). In each symbol of the candidate, replace an erased bin's magnitude with **the median of that symbol's non-erased bins** before `ft8_extract_symbol`. If 7 or 8 of the 8 bins are erased, the symbol's three bits get likelihood 0.
3. **Not on itself:** a known result's own cells are not erased for a candidate within ±3.2 Hz and ±0.16 s of that result (it is the same signal: a re-decode is a duplicate anyway, and erasing it would leave noise).
4. **Nothing else changes:** not the search, the subtraction, tier B, the accept rules, round 0 or the batches. No flag.
5. Shim/version bump as usual.

**Unit tests:**

- (a) **The mask:** for a synthetic known result, the marked cells are exactly its 79 tone cells ±1 bin, over the blocks each symbol overlaps. Results below −10 dB mark nothing.
- (b) **The effect:** a synthetic residual (the existing modulator test helpers) with a strong signal S, 15 dB above a weak signal W, 10–20 Hz apart, at different time offsets, and S given as a known result. Tier A on W's candidate **fails without the mask and decodes with it**. If no geometry the helpers can build shows this, the Developer says so and shows the LLR change on W's symbols instead.
- (c) **Unchanged:** mask NULL gives bit-identical likelihoods. Round 0 is unchanged. Determinism across thread counts.

## 3. The replay (QA): ONE run

- Build: `main` + this change, harness as for XC-ROUND, `libft8.dll` SHA pinned and stated.
- **The XC-ROUND arm** (lean, 16 threads, `--lean-probe 1`, XC on), S40 / H40 / H20.
- **Baseline: the XC-ROUND confirmation runs already on disk** (`xn_*`, build `f9662335`). No baseline re-run.
- **Free check, stated against §2 this time:** the **round-0 CAND rows' numeric columns** (position, score, `a_code`, `a_unsat`, `b_code`, `b_unsat`) are identical to the baseline in every cycle. Round 0 never sees the mask, and these columns do not depend on the hash table or the prior store. Published batches may differ (later cycles learn from new decodes), so they are **not** part of the check. If it fails, stop and tell the Architect.

## 4. What is reported (aggregates only, the XC-ROUND result's format)

1. **Table 1:** rate %, ours_only %, deltas in pp, lean minus classic.
2. **Cost:** CPU-s per cycle, `last_p95` ms, abandoned cycles, native errors, and the share of tier-A candidates in rounds 1–3 that had at least one erased bin.
3. **K2:** the K2 count against the baseline, by `dSNR` band (CS-MAP's bands), and how many baseline K2 T are now matched.
4. **Knock-on and losses:** matched gained outside the K2 cases, matched lost.
5. **The ours_only check** (`pf_oo_check.py`, unchanged) on the added decodes.

## 5. What happens next

The Product Owner decides keep or drop. If K2 does not move: the remaining strong-neighbour lever is **subtraction depth**, a better fit for signals ≥ −10 dB, which stop 4–6 dB short.

## 6. The Architect's expectations (priced before the run; scored in the ledger)

There is no clean bound. K2 is 350 / 478 / 577 cases after PAYLOAD-FIT. Of those, the cases with a stronger neighbour are the target: on H40, 398 of 495 in SUB-PROBE. How many have N landing on T's bins is not known. Knock-on is priced at about the direct effect (one more decode can open a patch).

| # | Prediction | P | Class |
|---|---|---:|---|
| ER-1 | S40 rate rises by ≥ 0.20 pp (over 88.20 %) | 0.45 | H |
| ER-2 | H20 rate rises by ≥ 0.30 pp (over 86.28 %) | 0.45 | H |
| ER-3 | K2 falls on all three slices | 0.60 | H |
| ER-4 | ours_only rises by ≤ 0.30 pp on every slice | 0.60 | C |
| ER-5 | CPU-s per cycle rises by ≤ 5 % on every slice | 0.75 | C |
| ER-6 | The free check passes | 0.90 | C |
