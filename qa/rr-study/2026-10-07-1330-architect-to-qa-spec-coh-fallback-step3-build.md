# SPEC — `COH-FALLBACK` (A′ step 3): a coherent-extraction fallback for candidates the ordinary decode fails, strength-gated, flag-gated (default OFF), published in batch 2; then an offline flag OFF/ON replay through the product

- **To:** QA (owner: the OpenSpec change, `tasks.md`, the Developer handoff; HK-015 / HK-000). cc Captain. **From:** Architect. **Date:** 2026-10-07 13:30Z (`date -u`, HK-017).
- **Branch:** `arch/coherent-limb2` (local). Docs only: `git diff --stat -- src/ native/` is empty. **The build is `native/` + `src/`**: a separate Developer session (HK-011), a new shim number (next free after 20260058; QA confirms it on `origin/main` before the handoff).
- **Authorised:** the Captain, Architect's window, 2026-10-07 ~13:2xZ: *"lets do the Step-3 build spec"*, after the ENC-ID ruling (`2026-10-07-1330-architect-enc-id-ruling.md`) and the options table it answered. **This spec authorises the build and the replay. Merge (HK-010) and default ON stay the Captain's.**
- **Status:** PRE-REGISTERED for the acceptance rows (§5). QA may amend mechanics before any decode, by a dated note. No row, bar or threshold changes after any acceptance decode has run.

## 0. Evidence this rests on (all offline, one 40 m night `20261004_1634`, WSJT-X's own positions, Python)

| figure | value | source |
|---|---|---|
| fallback (C3 where G fails), ungated | **+5.25 pp [5.05, 5.46]**, 3,382 recoveries, **all through BP** | ruling `2601b555` |
| strength gate GA (F1b ≤ **17.552 dB**, chosen on TRAIN) on held-out TEST | **+4.07 pp [3.81, 4.33]**; unexplained **0.178 [0.145, 0.213]** per cycle, an upper bound | Q-GATE ruling `7313db6f`; thresholds `1e8a5270` |
| the unexplained outputs | real transmissions in the audio (tone match 0.98); ~half are type-4 messages that the **offline truth** mis-packs (mechanism verified from source) | FIELD-ID / ENC-ID rulings |
| OSD inside the fallback | contributes only chance decodes (215 wrong, 0 right) | WRONG-ID |

🛑 **Not established:** whether the product's candidate search finds these signals; false outputs on **noise-only candidates**; native CPU cost; any second night or band. **This spec exists to measure exactly those, on the product.** The type-4 truth defect does not touch this replay: Test B matches by **text**.

## 1. What changes, in one paragraph

After the ordinary decode of a cycle (`ft8_decode_all`, all its passes) has finished, every candidate it **did not** decode becomes eligible for the fallback. For each, the fallback computes a **strength feature F1b**. If **F1b ≤ 17.552 dB**, it runs the **fine-sync estimator** (coherent Costas search over df ±2.0 Hz × dt ±0.12 s) and **C3 coherent extraction** (order-1+2+3 max-log LLRs) at the estimate, then **BP only** (no OSD), then CRC. A CRC-valid result goes through the ordinary message decode and dedup, and is published in **batch 2** with the residual pass's decodes. **Batch 1 is untouched.** Flag OFF ⇒ nothing changes.

## 2. Requirements

| # | Requirement |
|---|---|
| **R1 the method is the measured one** | Port **exactly** `qa/rr-study/coh-gain/fine_sync.py` (data-free mode: the 21 Costas symbols, `estimate()`, first-maximum argmax) and `qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py` (`downconvert_decimate` at 2 kHz with the 61-tap Hann-sinc at 900 Hz, `correlate_symbols`, `extract_variants` → **V3**, including `TIME_ORIGIN_CORRECTION_SAMPLES_2K`), and **F1b** = `cg_gate_features.costas_snr_noise_ref_db` (the anchor's Costas peak over the median of the same peak at the 24 offsets ±40…±150 Hz that fall within 200–3000 Hz), all at `qa/coh-gain` `44c70ea2`. These files are our own and clean-room by their headers; no WSJT-X source. Reuse `native/ft8_lib_vendor/refine/` (`sync_refiner.c`'s 2 kHz fine stage, `refine_common.h`) where it is identical. **An equivalent but faster computation is allowed** (e.g. one shared downconversion per cycle, a precomputed per-cycle reference-peak grid for F1b) **iff A2 passes**. A2 is what "exactly" means. |
| **R2 eligible candidates** | The ordinary decode's own candidates (from `ftx_find_candidates`, every pass of that `ft8_decode_all` call) that were **not** decoded in any pass. Each is attempted at most once. Payloads already decoded in that call are skipped (the existing dedup). The Developer exports or retains that list (e.g. TLS, as the existing failing-candidate diagnostics already are, `ft8_shim.c` near `:1640`) and records the choice with FILE:LINE. |
| **R3 anchor convention** | The candidate's grid position maps to the estimator's anchor `(f0, t0)` so that the ±0.12 s / ±2 Hz search window is **centred** on the true signal. The offline anchor was WSJT-X's DT plus δ; the product's is the 3.125 Hz / 0.08 s lattice. The Developer derives the mapping and records it with FILE:LINE. **A2(d) tests it.** |
| **R4 gate** | Run C3 on a candidate only if F1b ≤ **`T1` = 17.552 dB**, a constant in code with a comment citing `gate_thresholds.json` @ `1e8a5270`. It is not user-configurable. A harness-only override is allowed for A2. |
| **R5 decoder** | BP only (`osd_depth` −1, 50 iterations, production normalisation as in `ft8_ldpc_decode_llrs`), then CRC-14. **No OSD in the fallback.** The ordinary path's OSD is unchanged (OSD-off is parked). |
| **R6 where it publishes** | **Batch 2 only**, through the existing two-stage publish (`DecodeTwoStageAsync` / `MapNative`): the same per-cycle `seen` text dedup, `IsPlausibleMessage`, noise-suppression filter. A fallback decode whose text already appeared in batch 1 or in the residual pass is not published twice. **Batch 1's content and its publish time are unchanged** (A3). |
| **R7 budget** | The fallback runs inside the existing batch-2 deadline (`SubtractionPass.SubtractionResidualDecodeReserve`, `SubtractionPass.cs:43`, and the cycle budget it is measured against). Order and parallelism with the residual pass are the Developer's design (FILE:LINE), under one rule: **when the deadline arrives, unfinished fallback work is abandoned, never queued**, and the abandonment is counted per cycle. |
| **R8 no subtraction of fallback decodes** | Fallback decodes are **not** fed into the residual pass's subtraction in this change. The residual pass is unchanged. |
| **R9 the early decode never runs the fallback** | (#122 step 4) The early decode's pass-0-only entry is unchanged. The hash-table snapshot/restore stays valid: the fallback writes the hash table only through the ordinary message decode, after batch 1, like any other decode. |
| **R10 config** | `decoder.coherentFallbackEnabled`, **default `false`**. It is read once per cycle, as the subtraction flag is. Config POST is an overlay (HK-035): a partial update leaves it as it was (test). |
| **R11 provenance tag** | Every internal decode result carries a numeric `path` (0 ordinary, 1 residual, 2 fallback) in the replay harness outputs and the per-cycle log line. **ALL.TXT, UDP and panel formats are unchanged.** |
| **R12 log line** | One per cycle (file log, ms stamps): `Coherent fallback: eligible=…, gated=…, attempted=…, crcOk=…, published=…, abandoned=…, elapsedMs=…`. Aggregates only, no text. |
| **R13 flag OFF ⇒ nothing changes** | With the flag OFF: same native calls, same outputs, same order (characterisation tests, as two-stage publish's P-9). |

## 3. Two build stages, with a cost gate between them

**Stage 1, native core + diagnostic export (no product wiring):** `ft8_coherent_fallback_at(pcm, freq_hz, time_offset_s, …)` returns the estimate (df, dt, edge), F1b, the 174 V3 LLRs, the BP outcome (CRC, path, payload) and elapsed time. Plus a cycle-level diagnostic export that applies the fallback to every eligible candidate of an `ft8_decode_all` call (R2) and returns counts and timing. → **A0 and A2.**

**Stage 2, product wiring:** R6–R13. Starts **only after A0 passes** or after the Captain has decided an A0 design amendment.

## 4. Who decides what

| step | needs |
|---|---|
| Stage 1 → Stage 2 | A0 PASS and A2 PASS (the Architect rules) |
| merge to `main` with the flag OFF | A1, A2, A3, unit and characterisation tests green; **the Captain's sign-off** (HK-010) |
| default ON | D-GO **and** U-OK (§5), then **the Captain's decision** (a live check may be asked for first) |

## 5. Acceptance (mechanical; each stop scoped to the outputs it guards, HK-021 (ab))

### 5.1 Stage 1

| row | predicate | guards |
|---|---|---|
| **A0 cost gate** | On **100 cycles** of the acceptance corpus (§5.3, its first 100 selected cycles), with 8 threads on the station PC under practical load: **p95 per-cycle fallback wall time ≤ `S`**, where **`S` = the batch-2 slack**. QA computes it **before any Stage 1 timing is seen**, from **today's build on that corpus**: (cycle budget) − (pass-0 p95) − (residual-pass p95) − 1.5 s reserve, each read from the OFF build's own timing (FILE:LINE for the budget constant). Committed as a dated note. **FAIL ⇒ Stage 2 does not start.** The Architect drafts a design amendment (e.g. eligibility by top-K sync score, cheaper F1b, or a budget split with the residual pass) for the Captain. | Stage 2 only |
| **A2 port fidelity** | Native vs the Python reference, on the frozen COH-GAIN fresh-sample rows (G-fail rows, 27,571; F1b rows from `gate_features.csv`, 4,949), at WSJT-X's positions exactly as the offline harness anchored them: **(a)** BP outcome (CRC-valid y/n and payload equality with the Python C3 output, Python path-1 rows counting as no output) agrees on **≥ 99.5 %** of rows; **(b)** the (df, dt) estimate equal to the Python grid argmax on **≥ 99 %**; **(c)** F1b within **±0.25 dB** on **≥ 99 %**, and the gate decision (F1b ≤ 17.552) equal on **≥ 99.5 %**; **(d) anchor convention (R3):** on the acceptance corpus's first 100 cycles, for candidates the ordinary decode **did** decode, the estimate's dt median within **±0.02 s** of the decode's own refined position and the window-edge rate **≤ 2 %** | the method's identity with what was measured |

### 5.2 Stage 2, product

| row | predicate | guards |
|---|---|---|
| **A1 flag-OFF identity** | Existing suite green; characterisation tests: with the flag OFF, ALL.TXT lines, UDP datagrams, panel events and QSO-channel batches for a fixed set of recorded cycles are **identical** to the pre-change build (outcome fields) | the merge |
| **A3 batch 1 untouched** | On the acceptance replay, per cycle, the ON arm's batch-1 numeric multiset (freq, dt, snr) equals the OFF arm's: **N/N** (this is V4 below). Live batch-1 publish time is not re-measured: the fallback runs after batch 1 by construction (R6), and the code review checks that (FILE:LINE) | the merge |

### 5.3 The decision replay (offline flag OFF/ON, the sub-feas replay's design)

- **Corpus:** QA lists **every** `artefacts/` folder with full cycle audio plus a WSJT-X `ALL.TXT` (feedback rule 2026-10-03), and picks **one 40 m night other than `20261004_1634`**, whose cycles trained `T1`. Commit the frozen ordered `selection.json` (SHA) before any decode. Whole night, or a systematic 1-in-k sample if the CPU projection exceeds 8 h (the choice is recorded before any decode).
- **Fixed:** one build (the Stage 2 branch build, DLL SHA pinned at the start and end of every arm), harness mode `two1` (`DecodeTwoStageAsync`), subtraction ON as shipped, `nhard` 40, early decode not involved (replay), threads 8; arms **OFF** (`coherentFallbackEnabled = false`) and **ON**, each in a fresh process, read back.
- **Match rule:** Test B, exactly as implemented (`replay81/Program.cs`, same text, same cycle, |Δf| ≤ 10 Hz, one-to-one nearest-first), in-process (HK-037).
- **Estimands:**
  - **NET** = 100 × Σ(`M_on,i` − `M_off,i`) / Σ`W_i` (pp of WSJT-X's decodes), with `M` the union of batches 1 and 2, matched as one set.
  - **ΔU** = mean over cycles of (not-confirmed decodes ON − OFF), the **same** not-confirmed count as Test B.
  - Both with a 95 % block bootstrap: blocks of 40 consecutive cycles, ratio estimator for NET, B 10,000, seed 20261007.

**Validity (any FAIL ⇒ no verdict):**

| row | predicate |
|---|---|
| V1 | DLL pin equal at the start and end of OFF, ON and ON-repeat |
| V2 | flags read back in every run; `selection.json` SHA identical in every run |
| V3 | 0 access violations, 0 contained exceptions, 0 non-zero exits |
| V4 (= A3) | batch-1 multiset ON = OFF, N/N |
| V5 | cycles with residual **or** fallback work abandoned ≤ 5 % of cycles in the ON arm |
| V6 | ON-repeat over the first 160 cycles: per-cycle union multiset identical to the main ON arm, except cycles explained by abandonment in exactly one run (≤ 8); **unexplained = 0** (sub-feas replay Amendment 1's rule) |

**Verdict rows (two, independent; each exclusive, first match wins):**

| row | predicate |
|---|---|
| **D-GO** | `CI_lo(NET)` ≥ **1.0 pp** |
| **D-STOP** | `CI_hi(NET)` < 1.0 pp |
| **D-OPEN** | otherwise |
| **U-OK** | `CI_hi(ΔU)` ≤ **0.15** per cycle |
| **U-FAIL** | `CI_lo(ΔU)` > 0.15 |
| **U-OPEN** | otherwise |

**Where the numbers come from (HK-038):**
- **1.0 pp** is `BAR_G`, the Captain's build-worthy gain (2026-10-06), a decision value.
- **0.15 per cycle** is `U_max`, the Captain's ratified budget (2026-10-07). Its basis is about +30 % on the **0.47** Test-B not-confirmed decodes per cycle of today's build (`be3cc5ac`, N40, OSD-OFF ruling). **This replay measures exactly that quantity**, so the budget now sits on its own instrument. QA reports the OFF arm's not-confirmed per cycle on the new corpus beside it. If it falls outside **[0.30, 0.65]**, QA flags it to the Architect **before** reading the U row (the budget's basis would not transfer), and the Architect rules on the reading first.
- **5 % / ≤ 8 of 160 / block 40** are carried unchanged from the sub-feas replay design (2026-10-01), on the same harness family.
- **A2 tolerances** are port margins for floating-point differences, decision values.
- **`S`** is computed from today's build on the corpus itself.

**HK-025(k), both ways:** a fallback that publishes nothing gives NET ≈ 0 ⇒ D-STOP, and ΔU ≈ 0 ⇒ U-OK; so D-GO is the row that can fail. A fallback that publishes junk gives ΔU large ⇒ U-FAIL, even if NET passes. Default ON needs both.

**Descriptive, mandatory:** NET and ΔU by Test B SNR band (A–D); fallback decodes per cycle and their confirmed share; R12 counters (eligible, gated, attempted, CRC-ok, published, abandoned); fallback wall time per cycle (median, p95); the FP-watch flag per band (sub-feas rule: `CI_lo` of fallback not-confirmed rate > `CI_hi` of the batch-1 rate ⇒ FLAG to the Architect and the Captain); replay fidelity of the OFF arm against the live OpenWSFZ `ALL.TXT` (counts).

## 6. Limits, stated in the report

One night, one band, replay not live. Test B's not-confirmed count is an upper bound on false decodes: hashed `<...>` texts cannot match, so it counts them as not confirmed in both arms. The type-4 offline truth defect does not apply here. `T1` was trained on another night of the same band and chain. A second band is a later question.

## 7. Predictions (blind; scored at the rulings)

| # | prediction | P | class |
|---|---|---:|:---:|
| SF1 | A2 passes on the first Stage 1 build | 0.60 | H |
| SF2 | A0 passes without a design amendment | 0.40 | H |
| SF3 | D-GO | 0.45 | H |
| SF4 | U-OK | 0.35 | H |
| SF5 | NET point estimate in [1.0, 4.0] pp | 0.50 | H |

⚠️ My HYPOTHESISED calls today ran toward the tidy explanation (CW3). SF2 and SF4 are deliberately below even: the product runs the fallback on noise candidates the offline work never saw, and 25 coherent searches per candidate for F1b is expensive as specified.
