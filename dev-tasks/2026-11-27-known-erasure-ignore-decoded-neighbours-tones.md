# Developer task: KNOWN-ERASURE, ignore a decoded strong neighbour's tones when reading a weak signal's bits (lean only)

**Date:** 2026-11-27
**Prepared by:** QA, from the Architect's spec `docs/decoder-rebuild/spec-known-erasure.md` §2 (`arch/decoder-rebuild` `50c86605`; docs only; not on `main` yet, so this task repeats what you need; read it with `git show 50c86605:docs/decoder-rebuild/spec-known-erasure.md`)
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-27 ("yes, write it": the decode-step change after XC-ROUND), relayed by the Architect.
**Status:** Proposed. HK-011: `native/` and `src/` changes for a separate Developer session. Hand back the commit; QA reviews it (HK-039). **Do not push, open a PR or merge**; QA pushes (once per sprint).
**Branch:** `feat/known-erasure` from `main` (`a1e1c84c` or later: XC-ROUND, PAYLOAD-FIT and the probe are all on it; check `git fetch origin`). You can start now.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay by you. Read the per-assembly "Passed: N" lines (HK-022).

---

## 0. Why

After PAYLOAD-FIT and XC-ROUND the largest class of crowded misses is **K2**: a candidate is found at the missed signal T and tried, but no tier decodes it (SUB-PROBE: 65 to 75 % of the classified crowded misses). K2 rises steeply with the neighbour N's strength (`sub-probe-result.md` Table 3), and strong neighbours are only partly removed by the subtraction (those at -10 dB or stronger stop a median 4.8 to 5.8 dB short of the noise ceiling).

**The mechanism (code at `main` `a1e1c84c`):** tier A reads each symbol's bits from the 8 tone bins of the waterfall (`ft8_extract_likelihood`, `native/ft8_lib_build/patched/ft8/decode.c:379`; `static`, reached through the exported thread-safe `ftx_decode_candidate_tier_a`). A bit's likelihood comes from the **strongest** bin with that bit = 1 against the strongest with that bit = 0. A strong neighbour within 50 Hz puts one of its own tones, at each of its symbols, into or next to one of T's 8 bins; what is left of it after subtraction is still above a weak T, so **that bin wins the maximum and T's bit for that symbol is read from N's tone**. N's tones are known exactly (a published result: payload `res_pl`, frequency, time). Treating those bins as **erased** costs T little (one bin of eight in the symbols where N lands on it) and stops N from being read as T.

## 1. The change

**Where:** lean only; **rounds 1 to 3 and the XC round** (round 0 decodes all its candidates in parallel before any result is known and is **not touched**). **Tier A and CQ-AP** (both read `ft8_extract_likelihood`). **Tier B (coherent) is not touched.**

| Id | What |
|---|---|
| **K1 The erasure mask, per round** | Before the round's tier A, for every result already published **in this cycle** with **SNR >= -10 dB** (the SUB-PROBE boundary: weaker signals are removed to the noise floor and leave nothing to erase; use the result's own reported SNR), mark in a mask the same size as the waterfall every cell where that result transmits: for each of its **79 symbols**, the bin of its tone (`ft8_encode(res_pl[k])`, tones from the payload as in the fit) at its frequency and time on the waterfall's oversampled grid, **+-1 frequency bin** (3.125 Hz at `freq_osr` 2), and **every time block its symbol overlaps**. `ftz_probe_footprint_power` (`ftz_decoder.c:583`) already maps a signal's frequency and time to waterfall cells (`fb`, `fs`, `tb`, `ts`); reuse that placement. |
| **K2 The extraction with the mask** | A variant of `ft8_extract_likelihood` (or a mask argument): **the vendored function stays bit-identical when the mask is NULL.** In each symbol of the candidate, replace an erased bin's magnitude with **the median of that symbol's non-erased bins** before `ft8_extract_symbol`; if 7 or 8 of the 8 bins are erased, the symbol's three bits get likelihood 0. |
| **K3 Not on itself** | A known result's own cells are **not** erased for a candidate within **+-3.2 Hz and +-0.16 s** of that result (it is the same signal: a re-decode is a duplicate anyway, and erasing it would leave noise). |
| **K4 Nothing else changes** | Not the search, the subtraction, tier B, the accept rules, round 0, the batches, the DR-3 duplicate rule, the step-2e rule, XC-ROUND's design. **No flag.** Classic untouched. |
| **K5 Versions and documents** | The shim version moves (a rebuilt `libft8.dll`, SHA256 stated; the Linux and macOS libraries are CI's). Run `tools/check_version_bump.py` and follow it for `VERSION`. **Amend `REQUIREMENTS.md` FR-108 in the same work** (the sentence that describes what a residual round decodes now says tier A and CQ-AP read the bits with the known strong results' tone cells erased; add the shim number to its list and a changelog row after 1.80); keep the OpenSpec change `lean-decoder` (tasks and delta, strict) in step. |

### Two design points the spec does not settle (yours to decide, say what you chose)

1. **The XC round does not know the cycle's results.** `ftz_xc_round` (shim 20260082) gets the batch-3 detections only (79 tones, frequency, time) and the residual; the cycle's native state is gone. For the mask it needs **every published result of the cycle** (rounds 0 to 3 and the batch-3 detections that are at -10 dB or stronger): tones, frequency, time, SNR. The managed side holds the results' **text**, which cannot be re-encoded for a `<...>` result (the very reason of PAYLOAD-FIT). Suggested: let `ftz_decode_cycle` hand back each result's 79 tones beside `out_tiers` / `out_rounds` (a pure addition, an optional output pointer) and pass them, with frequency, dt and SNR, into `ftz_xc_round` (an extension of `ftz_xc_t`). If you restrict the XC round's mask to text-encodable results instead, say so: QA reports the share.
2. **The report needs a counter.** QA must report the share of tier-A candidates in rounds 1 to 3 (and the XC round) that had **at least one erased bin**. Add two counts per round to the existing round statistics (tier-A candidates decoded, of them with an erased bin) and to the per-round group of the lean log line (`r1[...]`, `xcRound[...]`: counts only, never text).

## 2. Tests (unit tests, the spec's §2)

1. **(a) The mask:** for a synthetic known result, the marked cells are **exactly** its 79 tone cells +-1 bin over the blocks each symbol overlaps; results below -10 dB mark nothing. (Expose the mask builder to the test as the other test exports are.)
2. **(b) The effect:** a synthetic residual (the existing modulator test helpers, as `LeanEnginePayloadFitTests` and `LeanEngineXcRoundNativeTests` do) with a strong signal **S**, 15 dB above a weak signal **W**, 10 to 20 Hz apart, at different time offsets, S given as a known result: **tier A on W's candidate fails without the mask and decodes with it.** If no geometry the helpers can build shows this, say so and show the LLR change on W's symbols instead (with the numbers). Say what "red" means (it fails on the 20260082 binary or without the mask).
3. **(c) Unchanged:** a NULL mask gives **bit-identical likelihoods**; **round 0 is unchanged** (the round-0 results and the round-0 probe rows are identical to the 20260082 build on the committed `synth-qso-*.wav` files); determinism across 1, 2, 4, 8 and 16 threads.
4. **(d) Bounds:** every mask index is bounds-checked (cells outside the waterfall are skipped); add the mask path to the fuzz driver (10,000 runs, with the probe on) and run the ASan + UBSan fuzz locally if you can.
5. **(e) Nothing else moved:** every existing test passes **unchanged**; if a golden or lean test changes because a residual round now reads bits differently, **do not edit it**: stop and report which one and by how much (QA decides).
6. **Run each project separately** and quote each "Passed: N": Config, Web, Daemon, Ft8 (also at `DOTNET_PROCESSOR_COUNT=4`), and the JS runner.

## 3. After your hand-back (QA, not you)

HK-039 review, the harness part (reading the new counters from the log line into `lean.csv`), `pre_merge_check` once at the sprint PR, and **one replay**: exactly the XC-ROUND arm (lean, 16 threads, `--lean-probe 1`, XC on) on S40 (170), H40 and H20 (240 each), about 22 minutes, against the XC-ROUND confirmation runs on disk (`_qa-scratch\lc-base\runs\xn_*`, build `f9662335`). **Free check (the Architect's, stated against §2): the round-0 CAND rows' numeric columns (position, score, `a_code`, `a_unsat`, `b_code`, `b_unsat`) are identical to the baseline in every cycle**; published batches may differ through the hash table and the prior store and are **not** part of it. If it fails QA stops and tells the Architect. QA reports: Table 1 with deltas, the cost and the erased-bin share, the K2 count by `dSNR` band and how many baseline K2 T are now matched, the knock-on and the losses, and the ours_only check on the added decodes. No bars; the Captain decides.

## 4. Out of scope

Anything in round 0, tier B, the search, the subtraction or the fit, the accept rules, the cross-cycle stage, OSD or any "near-miss rescue" (the Architect's §0: not the lever), a flag, the classic decoder, the daemon and Settings page, any default.

## 5. Report back

The commit SHA; the new shim number and `libft8.dll` SHA256; the per-project "Passed: N" lines (Ft8 also at 4 processors) and the JS result; **your two design decisions** (how the XC round learns the cycle's results; the counters); the red-before / green-after statement for test (b) (or the LLR numbers); the cost of the mask per round if you measured it; anything that differs from the neighbouring tests' pattern.
