# PAYLOAD-FIT: fit every lean result from its payload, without the text gate

**To:** QA, who turns §2 into one Developer task (HK-015) and runs §3–§4
**From:** Architect, 2026-11-27
**Approved:** ⏳ **PROPOSED, waiting for the Product Owner's go.** Nothing is built until he gives it.
**Why:** QA's R1–R4 split (`qa/rr-study/results/2026-11-26-lc-base/r1r4-split-result.md`, QA `2dda1d07`) shows that the largest reason a K2 neighbour is never subtracted is the **text gate**: 71 / 17 / 50 % of the never-subtracted K2 neighbours on S40 / H40 / H20 (112 / 18 / 134). 91–96 % of those have a `<...>` hash placeholder in the text. The rest have fewer than three tokens.

**The code (`main` `326538fb`, `native/ftz_decoder/ftz_decoder.c`):**

- `:744` `ftz_text_reencodable` returns false if the text contains `<` or has fewer than three space-separated tokens. `:1501` stores it in `reenc[slot]`.
- `:1029` the round loop skips every result with `reenc[k] == 0` when it chooses what to fit.
- `:1076` the fit takes its 79 tones from **`ft8_encode(res_pl[k], …)`**, the 77-bit payload that was decoded (`:1500`), and **not from the text**.

The gate came from the classic `SubtractionPass.IsReencodable`, which built the tones from the TEXT and so could not pack `<...>`. The lean fit does not read the text. The payload holds the hash bits and every other field exactly as they were received, so `ft8_encode` gives back the tones that were sent, whether or not the hash resolves and however many tokens the text has. **The gate protects nothing in lean. It is a leftover.**

**Process:** the minimal-test rule. One Developer task, unit tests, QA's review (HK-039), **one replay** (§3), numbers reported, **no bars**. The Product Owner decides.

---

## 1. Where it is built

- On `main` (`326538fb` or later). It rides in the next sprint PR (one PR per sprint, Product Owner 2026-11-26).
- **Lean only.** The classic decoder (`SubtractionPass`, C#) keeps its gate: it encodes from the text, and it is no longer the default.

## 2. The change (Developer)

1. **Remove the text gate from the lean fit selection:** at `:1029`, drop `if (!reenc[k]) continue;`. Every result not yet subtracted then goes through the step-2e rule (`ftz_fit_needed`) unchanged.
2. Remove what is then dead (`reenc`, its allocation and `ftz_text_reencodable`), or keep them if a test or the probe still reads them. The Developer chooses and says which.
3. **Nothing else changes:** not the step-2e skip rule, the rounds, the deadline reserve, the DR-3 duplicate rule or the probe. No new flag: the change is the whole decoder change.
4. Shim/version bump as usual (`check_version_bump.py`).

**Unit tests:**

- (a) A result whose text has a `<...>` placeholder (a synthetic message with a hashed call that is not in the hash table of a fresh process, built with the existing modulator test helpers) and that has a failed candidate within its patch window **is fitted**: its round's `n_fits` counts it, and with the probe on there is a `SUB` row at its position. On `main` the same test shows no fit (the test fails before the change and passes after).
- (b) The same for a result with fewer than three tokens, if the existing helpers can build one. If they cannot, the Developer says so; (a) is enough.
- (c) The existing determinism tests (thread counts give the same bytes) still pass.

## 3. The replay (QA): ONE run, on the SUB-PROBE runs' audio and settings

- Build: `main` + this change, harness `-p:HasLean=true`, `libft8.dll` SHA pinned and stated.
- **Exactly the SUB-PROBE arm:** lean, 16 threads, `--lean-probe 1`, LC-BASE's L flags, **S40** (170 cycles), **H40** and **H20** (240 each). About 20 minutes.
- **Baseline: the SUB-PROBE runs already on disk** (`_qa-scratch\lc-base\runs\probe_{S40,H40,H20}_L_n*`, decoder `fc3d5b5c`, shim 20260080). This change is the only difference, so no baseline re-run. The probe costs no decodes (SUB-PROBE free check), so it stays on and gives §4.3 and §4.4.

## 4. What is reported (aggregates only, beside the R1–R4 split)

1. **SUB-PROBE Table 1 format**, per slice, new vs SUB-PROBE: WSJT-X decodes, matched, ours, **rate %**, **ours_only %**, and the deltas in pp.
2. **Cost:** CPU-s per cycle, `last_p95` ms, abandoned cycles, native errors, and per cycle: fits, `fitNone`, rounds run (`n_rounds`).
3. **The R1 neighbours (QA's script, unchanged):** of the 112 / 18 / 134 K2 cases whose neighbour was an R1 result, how many now have (i) a `SUB` row for that neighbour, (ii) **T matched** (the missed signal decoded). Also the new K2 never-subtracted count and its R1–R4/XC split (R1 should be 0).
4. **Knock-on:** matched decodes gained outside those cases (the total gain minus 4.3 (ii)), and decodes lost (matched in SUB-PROBE, not now). DR-3 showed that a change to what is subtracted moves the later rounds more than its own rows suggest.

## 5. What happens next

The Product Owner reads §4.1–4.2 and decides whether it stays. Then the Architect proposes the next change: **XC** (a round after the cross-cycle stage, §6) or **K2 decoding** (bit metrics / BP), whichever the numbers favour.

## 6. Parked: XC (cross-cycle results are never subtracted)

16 / 50 / 35 % of the never-subtracted K2 neighbours (25 / 52 / 94) are lean's batch 3: the cross-cycle template stage (`Ft8Decoder.cs`, `DecodeLeanAsync`) runs in managed code on the **final residual** that the native call returns, after the rounds. Fitting them needs one more subtract → spectrogram → search → decode round **after** that stage, across the managed/native boundary: a larger change than one line, with its own CPU cost (one more round per cycle that has an XC result). **Parked until PAYLOAD-FIT's numbers are in.** H40, where XC is half the class, is where it would matter most.

## 7. The Architect's expectations (priced, written before the run; scored in the ledger)

Upper bound on direct recoveries alone: 112 / 6,773 = **1.65 pp** (S40), 18 / 8,983 = **0.20 pp** (H40), 134 / 9,154 = **1.46 pp** (H20). The noise ceiling SUB-PROBE found (strong neighbours stop ~5 dB short) lowers it, and the knock-on (DR-3's lesson) can raise it.

| # | Prediction | P | Class |
|---|---|---:|---|
| PF-1 | S40 rate rises by ≥ 0.30 pp (over 84.70 %) | 0.55 | H |
| PF-2 | H20 rate rises by ≥ 0.30 pp (over 82.88 %) | 0.50 | H |
| PF-3 | H40 rate moves by less than 0.20 pp either way (from 86.27 %) | 0.70 | C |
| PF-4 | ours_only % rises by no more than 0.20 pp on every slice | 0.70 | C |
| PF-5 | CPU-s per cycle rises by no more than 10 % on every slice | 0.65 | C |
