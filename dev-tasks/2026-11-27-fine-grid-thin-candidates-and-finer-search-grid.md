# Developer task: FINE-GRID, thin the candidate list (THIN) and a finer search grid (FINE), lean only, both runtime parameters, default off

**Date:** 2026-11-27
**Prepared by:** QA, from the Architect's spec `docs/decoder-rebuild/spec-fine-grid.md` (`arch/decoder-rebuild` `4f147930`, docs only; not on `main` yet, so this task repeats what you need; read it with `git show 4f147930:docs/decoder-rebuild/spec-fine-grid.md`)
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-27 ("write the spec for the finer decoder grid"; lean is a new decoder, the classic-era grid and candidate-budget closures do not bind it), relayed by the Architect.
**Status:** Proposed. HK-011: `native/` and `src/` changes for a separate Developer session. Hand back the commit; QA reviews it (HK-039). **Do not push, open a PR or merge**; QA pushes (once per sprint).
**Branch:** `feat/fine-grid` from `origin/main` (`git fetch origin` first; `main` moved today, the libs PR #303 is on it). Independent of `feat/interface-no-defaults` (the other open task); if both touch `IFt8NativeInterop`, QA merges them.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay by you. Read the per-assembly "Passed: N" lines (HK-022). **Do NOT run ASan, UBSan or the fuzz locally** (the Captain, 2026-11-27: it slows the Developer too much; CI's `native-asan` job runs them on the PR).

---

## 0. Why (data, QA's re-count of the Architect's figures from the shipped build's probe rows)

Source: `_qa-scratch\lc-base\runs\xn_{S40,H40,H20}_*\probe.tsv`, CAND rows, script `qa/decoder-rebuild/fg_recount.py`. **A candidate is shadowed** when another candidate of the same cycle and round with a higher score lies within **6.25 Hz and 0.16 s** (ties: the lower frequency, then the earlier time, wins).

| Slice | Round 0: candidates (all cycles) | shadowed | Residual rounds: candidates | shadowed |
|---|---:|---:|---:|---:|
| S40 | 23,800 (140 in every one of 170 cycles) | **65.4 %** | 121,200 (200 in every one of 606 rounds) | 40.0 % |
| H40 | 33,600 (140 in 240 of 240) | **61.7 %** | 169,800 (200 in every one of 849) | 38.7 % |
| H20 | 33,598 (140 in 239 of 240) | **59.3 %** | 173,400 (200 in every one of 867) | 36.6 % |

The Architect's figures reproduce (to 2 candidates in 15,571 for S40 round 0). The caps (`max_c` 140 at `ftz_decoder.c:1012`, `res_cap` 200 at `:1163`) are full everywhere and about 60 % of round 0's slots are copies of the same signal. `ftx_find_candidates` (`native/ft8_lib_build/patched/ft8/decode.c:290-330`) keeps the best N grid positions with **no local-peak suppression**.

Two changes, each switchable, because a finer grid without thinning would give every strong signal four times as many copies in a full cap:

- **THIN:** drop a candidate shadowed by a higher-scoring one, **before** the cap.
- **FINE:** the search grid `time_osr` 2 to 4 and `freq_osr` 2 to 4 (frequency by **zero-padding**, the window unchanged). FINE is only ever run with THIN on.

## 1. The change

**Lean only. Classic (`ft8_shim.c`, its `K_FREQ_OSR` / `K_TIME_OSR` at about `:538-539`) stays bit-identical.**

| Id | What |
|---|---|
| **G1 Runtime parameters** | In `ftz_params_t`: `thin` (0 or 1), `time_osr`, `freq_osr` (2 or 4; **0 means today's value**). **Defaults: thin 0, osr 0 = 2/2, no change at all.** Reject any other value with a clear error code. The Product Owner sets the shipped defaults after QA's replay, so nothing is on by default. Expose them to the managed side the way `LeanCycleParams` carries the other lean parameters, and add the matching harness-facing options (QA wires its harness; you only need the managed `LeanCycleParams` fields). |
| **G2 The monitor** | `native/ft8_lib_build/patched/common/monitor.c:72-82`: `nfft = block_size * freq_osr` and the Hann window spans the whole `nfft` (2 symbols at `freq_osr` 2). **Raising `freq_osr` to 4 as the code stands would stretch the window to 4 symbol periods** (a different, worse change). Add a window length separate from `nfft`: a new field where **0 means `nfft`** (today's behaviour, what classic always gets). With `freq_osr` 4 under lean: Hann window `2 * block_size` long, zero-padded to `4 * block_size`, normalised **as today's 2-symbol window** (`fft_norm` from the window length, not from `nfft`). **Sizes (QA checked at `origin/main`):** `nfft` is `block_size * freq_osr` = 1,920 x 2 = **3,840 today** (the comment at `monitor.c:154` says "max nfft=3840"); at `freq_osr` 4 it is **7,680**, which fits the existing `timedata[8192]` (`:154`) and its 3,841 bins fit `freqdata[4097]` (`:155`), so **no resize is needed; assert both bounds** (the Architect's spec says 15,360 and a resize: that is not right for 12 kHz). **Which samples feed the FFT matters:** `timedata[pos] = window[pos] * last_frame[pos]` (`:171`) reads `nfft` samples; with a 2-block window the input is the **most recent `2 * block_size` samples, zero-padded to `nfft`** (check what `last_frame` holds and how it is shifted, and keep today's 2-symbol alignment, so that every second bin equals today's bin: test (b)). `time_osr` 4 needs only the hop (`subblock_size`, `:73`). |
| **G3 Thinning** | In `ftz_decoder.c` a lean search wrapper (e.g. `ftz_find_candidates`) that scores every grid position **exactly as `ftx_find_candidates` does** (same floor, same score, same sort), keeps all positions above the floor (sized for the grid in use: the above-floor list at osr 4/4 is about 4x today's), and applies the rule: **drop a candidate if ANY higher-scoring above-floor candidate (not only a surviving one) lies within 6.25 Hz and 0.16 s of it** (ties: the lower frequency, then the earlier time, wins). The cap (140 / 200) then takes the best of the survivors, **sorted as today**. Used in round 0 (`:1012`), in the residual rounds (`:1163`) and in the XC round. **The vendored `ftx_find_candidates` is not touched.** With `thin` 0 the wrapper calls `ftx_find_candidates` directly. (A survivor is a local maximum, so after thinning no two survivors are within the window: QA's first check relies on exactly this predicate.) |
| **G4 Every candidate-to-physical conversion reads the waterfall's own oversampling** | Never `K_FREQ_OSR` / `K_TIME_OSR`. Known places: `ftz_decoder.c:585-604`, `:656`, `:884`. Also check `native/ft8_lib_vendor/refine/coherent_llr.c:417` and `:490`, which snap to the `K_*` lattice: if lean reaches them they take the runtime values. **Grep for `K_FREQ_OSR`, `K_TIME_OSR`, `freq_osr` and `time_osr` over `native/` and `src/` and list every hit with what you did (changed, or why it is classic-only).** |
| **G5 Stale comment** | `ftz_decoder.c:15` ("window, oversampling and scaling are closed arms"): reword, they are lean parameters now. |
| **G6 Probe and versions** | The probe's `CAND` row must carry the grid sub-position (`time_sub`, `freq_sub`) **if it does not already** (QA's first check reads it to show arm F decodes on odd sub-positions); say whether you added it. The shim version moves (a rebuilt `libft8.dll`, SHA256 stated; the Linux and macOS libraries are CI's). Run `tools/check_version_bump.py` and follow it for `VERSION`. **Amend `REQUIREMENTS.md` FR-108** in the same work (the lean search: THIN and the finer grid as lean runtime parameters, default off; add the shim number to its list and a changelog row after the latest); keep the OpenSpec change `lean-decoder` (tasks and delta, strict) in step. |
| **G7 Out of scope** | Tier A, tier B, CQ-AP, the subtraction, the accept rules, the batches, the XC round's design, the cap values, the search floor, any default, the classic decoder, the daemon and Settings page. |

## 2. Tests (unit tests, the spec's §2)

1. **(a) Defaults change nothing:** with `thin` 0 and osr 2/2, the published output is **byte-identical to `main`** on the committed `synth-qso-*.wav` files; classic's waterfall is bit-identical (compare the waterfall bytes for a fixed input through the classic path before and after).
2. **(b) Zero-padding is right:** on a synthetic tone WAV the `freq_osr` 4 waterfall's **even** frequency sub-positions equal the `freq_osr` 2 waterfall's cells **within 1 LSB of the stored magnitude**; a tone half-way between two old bins peaks at the new **odd** sub-position.
3. **(c) Thinning:** a synthetic strong signal yields **one** surviving candidate within 6.25 Hz and 0.16 s; **two synthetic signals 20 Hz apart both survive**; the surviving list is identical across 1, 2, 4, 8 and 16 threads; **no two survivors lie within the window** (property over a few thousand random candidate sets, also with exactly tied scores).
4. **(d) FINE decodes:** a synthetic signal placed **half a bin and half a hop off** today's grid decodes under FINE (thin 1, osr 4/4) and its candidate sits on an odd sub-position.
5. **(e) Bounds and parameters:** every new index is bounds-checked; an invalid `thin` or osr value returns the error code; add the new parameters to the fuzz driver (10,000 runs) but **do NOT run it locally** (CI's `native-asan` does).
6. **(f) Nothing else moved:** every existing test passes **unchanged**. If a golden or lean test changes, **do not edit it**: stop and report which and by how much (QA decides).
7. **Run each project separately** and quote each "Passed: N": Config, Web, Daemon, Ft8 (also at `DOTNET_PROCESSOR_COUNT=4`), and the JS runner.

## 3. After your hand-back (QA, not you)

HK-039 review, the harness part (options for `thin`, `time_osr`, `freq_osr`; the sub-position columns into `lean.csv`), `pre_merge_check` once at the sprint PR, and **one replay, two arms**: lean, 16 threads, `--lean-probe 1`, XC on, on S40 (170), H40 and H20 (240 each); **arm T** = thin 1, osr 2/2; **arm F** = thin 1, osr 4/4; baseline = the XC-ROUND confirmation runs on disk (`xn_*`; no re-run: your test (a) covers "defaults change nothing"). **First check, before any rate is read:** arm T has shadowed share 0 in every round; arm F has published decodes on odd sub-positions and the probe confirms osr 4/4. If either fails, QA stops and tells the Architect. If the projection for both arms exceeds 2 h, QA asks the Captain for the go with the projection; if he declines, arm F runs on H20 only. QA reports Table 1 with deltas (arm T and arm F against the baseline, F against T), the cost (CPU-s per cycle, `last_p95`, abandoned cycles, native errors, candidates per round), K2/K3/K4 against the baseline, added decodes by round, and the ours_only check. **No bars; the Captain sets the shipped defaults.**

## 4. Report back

The commit SHA; the new shim number and `libft8.dll` SHA256; the per-project "Passed: N" lines (Ft8 also at 4 processors) and the JS result; **the grep list of G4 (every `K_*OSR` / `freq_osr` / `time_osr` hit and what you did)**; how you fed the zero-padded FFT (which samples) and sized the above-floor list for osr 4/4; whether you added `time_sub`/`freq_sub` to the CAND row; the cost of the wrapper at thin 1 and osr 2/2 if you measured it; anything that differs from the neighbouring tests' pattern.
