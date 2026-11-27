# FINE-GRID: thin the candidate list, then try a finer search grid (lean only)

**To:** QA, who turns §2 into one Developer task (HK-015) and runs §3–§4
**From:** Architect, 2026-11-27
**Approved:** Product Owner, 2026-11-27 ("write the spec for the finer decoder grid"). The classic-era closures on the grid and the candidate budget do not bind lean (Product Owner, 2026-11-27: "with the lean decoder we have a 'new' decoder imho. so all options are on the table").
**Why:** after PAYLOAD-FIT and XC-ROUND, lean is at **87.5 %** of WSJT-X's decodes, counting only those WSJT-X confirms. It is at **94.8 %** if our unconfirmed decodes count as real (S40 / H40 / H20 pooled, XC-ROUND replay). Subtraction depth found no room (FIT-DEPTH §8.5c). The grid is the last search-side lever named.

---

## 0. What the data say before anything is built (Architect, counts from the shipped build's probe rows)

Source: the XC-ROUND confirmation runs `_qa-scratch\lc-base\runs\xn_{S40,H40,H20}_*\probe.tsv` (build `f9662335` = `main`'s decoder; numbers only; `CAND` rows = kind 2). The Architect's one-off script is not committed; QA re-counts it in §4.1.

1. **The candidate caps are full in every cycle and every round.**
   - Round 0 has exactly 140 candidates in 170/170, 240/240 and 239/240 cycles.
   - Every residual round has exactly 200 (606/606, 849/849, 867/867 rounds).
   - Caps: `ftz_decoder.c:1012` (`max_c`, 140) and `:1163` (`res_cap`, 200).
2. **Most of that cap is spent on copies of the same signal.** `ftx_find_candidates` (`native/ft8_lib_build/patched/ft8/decode.c:290–330`) keeps the best N grid positions by sync score **with no local-peak suppression.** A strong signal therefore fills many slots at neighbouring sub-positions and offsets. A candidate is counted **shadowed** when a higher-scoring candidate of the same round lies within **6.25 Hz and 0.16 s** of it:

   | Slice | Round 0: shadowed | Residual rounds: shadowed |
   |---|---|---|
   | S40 | 15,569 / 23,800 (**65.4 %**) | 48,442 / 121,200 (40.0 %) |
   | H40 | 20,719 / 33,600 (**61.7 %**) | 65,642 / 169,800 (38.7 %) |
   | H20 | 19,907 / 33,598 (**59.3 %**) | 63,494 / 173,400 (36.6 %) |

   So round 0 looks at roughly **50 distinct places per cycle**, against about 40 WSJT-X decodes per cycle on these slices.
3. **Every failed kept candidate went through all three tiers.** Each one ends as `CQ_FAIL`, after tier A, tier B and CQ-AP.
4. **Tier B already finds the precise position itself.** `cf_estimate` searches ±2.0 Hz in 0.1 Hz steps and time in 5 ms steps around the candidate (`native/ft8_lib_vendor/refine/coherent_fallback.c:68–70`; called from `cf_process_one`, `src/OpenWSFZ.Ft8/Native/ft8_shim.c:2414`).
   - **A finer grid cannot help tier B**, and so cannot help most K2 misses: the candidate was found, and tier B tried it at a precise position.
   - What a finer grid can still change is the **search**: a weak signal between grid points scores lower and may miss the floor or the cap (K3 9 %, K4 ~6 % of the crowded misses; SUB-PROBE). It can also change **tier A's** bit reading.
5. **How the grid is built today** (`native/ft8_lib_build/patched/common/monitor.c:72–82`): `nfft = block_size × freq_osr`, and the Hann window spans the **whole** `nfft`. At `freq_osr` 2 the window is 2 symbols long.
   - **Raising `freq_osr` to 4 as the code stands would stretch the window to 4 symbol periods** and smear neighbouring symbols together. That is a different (and worse) change than "finer bins".
   - The finer frequency grid must therefore come from **zero-padding**: the same 2-symbol window inside a longer FFT. Every second bin is then today's bin.

**Consequence for the design:** a finer grid without thinning would give each strong signal about 4× as many copies in an already-full cap, pushing weak candidates out. **Thinning is a prerequisite, and it may be a lever by itself.** So the build carries both, each switchable, and the one replay measures thinning alone and thinning plus the fine grid.

## 1. The two changes

### 1a. THIN: one candidate per place

Before the cap is applied, candidates are taken in descending score order. Ties are broken by lower frequency, then earlier time, so the result is deterministic. **A candidate is dropped if a candidate ALREADY KEPT lies within 6.25 Hz and 0.16 s of it** (one tone spacing, one symbol). This is greedy peak suppression. The cap (140 / 200) then takes the best of the survivors.

*Clarified 2026-11-27, after QA's task draft:* the suppressor must be a **kept** candidate, not any higher-scoring one. With "any", a chain A > B > C (each within the window of the next, A and C farther apart) drops C because of B, which was itself dropped. C can be a real second signal, and on the fine grid such chains are four times as common. The first check still holds exactly: no two survivors lie within the window, by construction.

Two real signals that close overlap in every tone. The stronger one is decoded and subtracted, and the weaker is found in a later residual round, which is how lean already treats them.

### 1b. FINE: a finer search grid

`time_osr` 2 → 4 (hop 0.04 s instead of 0.08 s) and `freq_osr` 2 → 4 (1.5625 Hz instead of 3.125 Hz, **by zero-padding**, window unchanged). The sync search, tier A and CQ-AP read the finer waterfall. Tier B is unchanged (it reads PCM). **FINE is only ever run with THIN on.**

## 2. The change (Developer)

**Lean only.** Classic (`ft8_shim.c`, its `K_FREQ_OSR` / `K_TIME_OSR` at `:538–539`) stays bit-identical.

1. **Runtime parameters** in `ftz_params_t`: `thin` (0/1), `time_osr`, `freq_osr` (2 or 4; 0 = today's value). **Defaults: thin 0, osr 2/2 = no change.** Harness options to set them (QA's side). The Product Owner sets the shipped default after the replay.
2. **The monitor (`monitor.c`):** a window length separate from `nfft`. A new field, where 0 means `nfft`, which is today's behaviour and what classic always gets.
   - With `freq_osr` 4 under lean, the Hann window is `2 × block_size` long, zero-padded to `4 × block_size`, and normalised as today's 2-symbol window (`fft_norm` from the window length, not from `nfft`).
   - The `timedata[8192]` buffer (`monitor.c:154`) holds `nfft` 7,680. Assert it.
   - `time_osr` 4 needs no monitor change beyond the hop (`subblock_size`).
3. **Thinning (`ftz_decoder.c`):** a lean search wrapper (e.g. `ftz_find_candidates`). It scores every grid position as `ftx_find_candidates` does, with the same floor and the same score. It keeps all positions above the floor (sized for the grid in use) and applies §1a. It then returns the best `cap` of the survivors, sorted as today. Used in round 0 (`:1012`), in the residual rounds (`:1163`) and in the XC round. The vendored `ftx_find_candidates` is not touched. With `thin` 0 the wrapper calls `ftx_find_candidates` directly.
4. **Every conversion between a candidate and Hz / seconds reads the waterfall's own `time_osr` / `freq_osr`**, never `K_*`. Known places: `ftz_decoder.c:585–604`, `:656`, `:884`. Also check `native/ft8_lib_vendor/refine/coherent_llr.c:417`, `:490`, which snap to the `K_*` lattice: if lean reaches them, they take the runtime values. **The Developer greps for `K_FREQ_OSR`, `K_TIME_OSR`, `freq_osr` and `time_osr` and lists every hit with what was done.**
5. **The stale comment** at `ftz_decoder.c:15` ("window, oversampling and scaling are closed arms") is reworded: these are lean parameters now.
6. Probe: the `CAND` row carries the grid sub-position (time_sub, freq_sub) if it does not already. Shim/version bump as usual. **Do NOT run ASan/UBSan/fuzz locally** (CI's `native-asan` job runs them on the PR).

**Unit tests:**
- (a) **Defaults change nothing:** with thin 0 and osr 2/2, published output is byte-identical to `main` on the committed `synth-qso-*.wav` files. Classic's waterfall is bit-identical.
- (b) **Zero-padding is right:** on a synthetic tone WAV, the `freq_osr` 4 waterfall's even frequency sub-positions equal the `freq_osr` 2 waterfall's cells, within 1 LSB of the stored magnitude. A tone half-way between two old bins peaks at the new odd sub-position.
- (c) **Thinning:** a synthetic strong signal yields one surviving candidate within 6.25 Hz / 0.16 s. Two synthetic signals 20 Hz apart both survive. The order is deterministic across thread counts.
- (d) **FINE decodes:** a synthetic signal placed half a bin and half a hop off today's grid decodes under FINE, and its candidate sits on an odd sub-position.

## 3. The replay (QA): ONE run, two arms

- Build: `main` + this change; harness as for XC-ROUND (lean, 16 threads, `--lean-probe 1`, XC on); `libft8.dll` SHA pinned and stated. S40 / H40 / H20.
- **Arm T:** thin 1, osr 2/2.
- **Arm F:** thin 1, osr 4/4.
- **Baseline: the XC-ROUND confirmation runs on disk** (`xn_*`, the same decoder as `main`). No baseline re-run: unit test (a) covers "defaults change nothing".
- **First check, before any rate is read** (the rule of 2026-11-27: show that the changed part did work):
  - Arm T: shadowed share in round 0 and in the residual rounds = **0** (by §0.2's predicate).
  - Arm F: **> 0** published decodes whose candidate sits on an odd time or frequency sub-position, and the probe's grid confirms osr 4/4.
  - If either fails, stop and tell the Architect.
- **Run time:** arm F's CPU may be several times arm T's. If QA's projection for both arms exceeds 2 hours, QA asks the Product Owner for the go with that projection (rule of 2026-11-18). If he declines, arm F runs on H20 only.

## 4. What is reported (aggregates only; the XC-ROUND result's format)

1. **The re-count of §0:** caps full, and the shadowed shares for the baseline (QA's own script).
2. **Table 1:** per slice and arm: rate %, ours_only %, ours ÷ WSJT-X %, deltas in pp against the baseline, and arm F against arm T.
3. **Cost:** CPU-s per cycle, `last_p95` ms, abandoned cycles, native errors, distinct candidates per round (round 0 and residual).
4. **Where the gain comes from:** K2 / K3 / K4 counts (`sub_probe_analyze.py`'s classes) against the baseline; added decodes by round (0, 1–3, XC); matched lost.
5. **The ours_only check** (`pf_oo_check.py`, unchanged) on each arm's added decodes.

No bars. The Product Owner decides the shipped defaults (thin on or off; osr 2/2 or 4/4) from these numbers.

## 5. The Architect's expectations (priced before the run; scored in the ledger)

Freeing about 90 round-0 slots for distinct places is a large change in what round 0 looks at. But residual rounds already search again with a 200 cap, and K3 + K4 are only about 15 % of the crowded misses, so the rate gain is bounded. The fine grid cannot help tier B (§0.4). The ledger shows hypothesised "findable" calls are biased high, so they are priced down.

| # | Prediction | P | Class |
|---|---|---:|---|
| FG-1 | Arm T: rate rises by ≥ 0.20 pp against the baseline on at least two of the three slices | 0.40 | H |
| FG-2 | Arm F: rate exceeds arm T's by ≥ 0.20 pp on at least two slices | 0.20 | H |
| FG-3 | Arm T: K3 + K4 together fall on all three slices | 0.55 | H |
| FG-4 | Arm T: ours_only rises by ≤ 0.30 pp on every slice | 0.60 | C |
| FG-5 | Arm F: CPU-s per cycle is ≥ 1.5 × arm T's on every slice | 0.60 | C |
| FG-6 | The first check (§3) passes for both arms | 0.85 | C |
