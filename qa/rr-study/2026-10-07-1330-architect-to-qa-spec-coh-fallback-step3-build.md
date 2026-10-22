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

---

## §8 Amendment 1: the era refresh (Architect, 2026-10-20 17:10Z by `date -u`; before any Stage 1 code or timing)

**Why.** Q-GATE-2 ruled G2-OK (ruling `2026-10-20-1710`, `d1c13992`). The Captain then gave "go on both, step-3 build and stage 2" in QA's window on 2026-10-20. That go was relayed by QA: it is the Captain's go, not a peer's. QA's first (k) review of this spec found stale points, and this amendment folds them in.
- Several things changed after 10-07: the product now has a third pass (Deep is the default), late batches reach the QSO services, `nhard` is 24 with the OSD fix, and a new night is on disk.
- **Nothing here touches R1, R3–R5 or R8–R13, or A1, A2 and its tolerances, or D-GO's 1.0 pp.**
- Stage 1 may start on this amendment as written. A0's slack definition (A1.3) and the corpus (A1.4) are the only Stage 1 items it changes.

**A1.1 Base branch: `origin/main` (QA's choice, confirmed).** `decoding_improvement` is 195 commits behind `main`. It
lacks the third pass, the Deep default, late batches and B2, so a build there could not be accepted against today's
product.
- The change lands on `main` by PR (HK-010). `decoding_improvement` picks it up at its next sync.
- Shim **20260066**, as QA assigned. The expected version-file conflict with #225 is resolved at whichever merge lands second.

**A1.2 Where the fallback publishes, and its deadline (replaces R6's "batch 2 only" and R7's "batch-2 deadline").**
- **R6′ publish slot.** Fallback decodes are published in the cycle's **last supplementary batch**: batch 3 on the Deep
  path, batch 2 on Normal.
  - **There is no new batch number.** So `LateBatch`, the QSO channel capacity (`Program.cs:345`, "up to 3 batches per
    cycle") and the panel's batch handling are unchanged.
  - The same per-cycle `seen` text dedup, `IsPlausibleMessage` and noise-suppression filter apply.
  - A fallback text already published in any earlier batch of the cycle is not published again.
  - Batch 1 is untouched (A3). With the flag OFF, everything is as R13 says.
- **R7′ deadline.** The fallback shares the **13 s cycle budget** (`SubtractionCycleBudget`, `Ft8Decoder.cs:108`) with
  the residual pass and the third pass.
  - **Order and parallelism are the Developer's design (FILE:LINE).** The one constraint: the fallback must not delay
    batch 2's publish on the Deep path, so it may hold back only the last batch.
  - When the deadline arrives, unfinished fallback work is **abandoned, never queued**. The R12 log line counts it.
- **R2′ eligibility, made explicit.** Eligible: candidates of the ordinary `ft8_decode_all` call that were not decoded
  by it. A candidate whose text the residual or third pass has already published may still be attempted, but its
  output is dropped by dedup. Whether to skip such candidates early, to save CPU, is the Developer's choice (FILE:LINE).
  It must not change what is published.

**A1.3 A0 cost gate, restated per cycle (replaces A0's `S`).** Summing p95s of three passes overstates the time they
use together. It also ignored the third pass, which ran at a median of 0.78 s and a maximum of 1.4 s on the 10-19 live
night (QA).
- **Per-cycle slack** on the OFF build (today's `main`, Deep, read back): `s_i` = 13.0 s − the elapsed time from
  decode start to the end of the cycle's last ordinary pass (pass 0, residual and third), from the build's own timing
  (FILE:LINE).
  - QA measures it on A0's 100 cycles and commits it as a dated note **before any Stage 1 timing is seen**.
- **A0 predicate (paired):** on the same 100 cycles, take `f_i`, the Stage 1 diagnostic export's per-cycle fallback
  wall time. **PASS iff #(`f_i` > `s_i`) ≤ 5** (5 %).
  - This assumes the fallback runs **serially after the last pass**, the worst case. A parallel design can only do
    better, so A0 PASS stands for it too.
  - **Conditions:** the station PC, 8 threads, OFF slack and Stage 1 timing measured in one session, one after the
    other, with no other heavy job running.
- **Where the 5 % comes from:** V5's abandonment ceiling (sub-feas replay design, 2026-10-01), so the cost gate and the
  replay's abandonment row use the same tolerance.
- **FAIL ⇒** unchanged (no Stage 2; the Architect drafts a design amendment for the Captain).

**A1.4 Corpus: `20261009_1752_endurance_run-gathered` (40 m), not `20261019_1905`.**
- **Why another night.** QA proposed 10-19. But Q-GATE-2's G2-OK rests on 10-19, and `T1` was trained on 10-04. A
  third night makes the build's decision independent of both.
- **Why the product era doesn't decide it.** The night's product era is not what matters for a replay. `nhard`, the OSD
  fix and Deep are decoder settings that the replay sets itself (rule 2026-10-03: never pre-filter recorded audio by
  them).
- **What a night must have:** full-cycle WAVs from the Windows capture (not tainted, per the 10-16 ruling) and WSJT-X's
  `ALL.TXT`. ~~10-09 has 7,264 WAVs, about 30 h~~ 🔴 **CORRECTED (§9 A2.1, QA, checked on disk): 3,634 WAVs under
`owsfz/wav/`, gap-free, 15.14 h** (7,264 was owsfz + wsjt-x counted together, my error), plus `wsjt-x/ALL.TXT`
(93,611 rows over 3,628 cycles).
- #225 V1 used 455 of its cycles, but nothing was tuned on them.
- **QA still lists every `artefacts/` folder (rule 2026-10-03)** and confirms 10-09 meets §5.3. If it fails that check,
  QA falls back to `20261019_1905` and records why, before any decode.
- **Sample.** Use the whole night, or a systematic 1-in-*k* sample over the gap-inclusive slot list if the projection
  exceeds 8 h, as before. ***k* must be odd** so that both slot parities are sampled (Q-GATE-2 A1.1), and V-P from
  Q-GATE-2 applies: even and odd counts within 2 % of each other. The choice of *k* is recorded before any decode.
- **A0 and A2(d)** use the first 100 selected cycles of this corpus.

**A1.5 Fixed configuration (replaces §5.3 "Fixed").** One Stage 2 build, with its DLL SHA pinned at the start and end
of every arm, and harness mode `two1`.
- **Decoder settings, as shipped on the base:** subtraction ON, **Deep** (the third pass), **`nhard` 24, OSD sign fix
  ON**, threads 8.
  - **Every one is read back in every run:** the third pass via `thirdPass.decodingDepth`, `nhard` and the OSD fix as
    #225 S0 read them.
- **Arms:** OFF and ON, each in a fresh process. The early decode is not involved.
- **NET and Test B:** `M` is the union of **all batches** (1, 2 and 3) matched as one set, so NET counts only what the
  fallback adds beyond the third pass.

**A1.6 The U budget, rebased on today's build (HK-038; replaces U-OK/U-FAIL's 0.15 and the [0.30, 0.65] guard).**
- **Why 0.15 no longer stands.** It was +30 % on 0.47 Test-B not-confirmed decodes per cycle, from `be3cc5ac` (`nhard`
  40, OSD OFF, no third pass). None of those holds today. No Test-B not-confirmed rate from today's build is on file,
  and the live 0.170 OWS-only rate is a different instrument.
- **Rule: the OFF arm runs first.** QA computes `U0` = the OFF arm's not-confirmed decodes per cycle (point), then
  freezes `U_max` = **0.30 × `U0`**, rounded to 3 decimals, in a dated note **before any ON-arm decode**. The OFF arm
  contains no fallback output, so this sees nothing of the result.
- **Rows:** U-OK `CI_hi(ΔU)` ≤ `U_max`; U-FAIL `CI_lo(ΔU)` > `U_max`; U-OPEN otherwise.
- **Where the 30 % comes from:** it is the rule behind both of the Captain's budgets. 0.15 was about +30 % on 0.47
  (10-07), and 0.05 was about +30 % on 0.17 (Q-GATE-2, today).
- ⏳ **The Captain confirms the rule before the OFF arm runs** (§8 end). It is his decision value. QA's (k) review can
  go ahead meanwhile.

**A1.7 V5 and V6, restated (QA's (k) note 4).**
- **V5:** cycles with residual, third-pass **or** fallback work abandoned ≤ 5 % of the ON arm's cycles. Report n and
  the Wilson interval.
- **V6 (repeat):** the ON-repeat runs on **every 3rd selected cycle**, not on the first 160. 160 consecutive cycles
  are one stretch of one evening; a stride spreads the check across the night.
  - **Bar:** unexplained differences = **0**, and cycles explained by abandonment in exactly one run ≤ 5 % of the
    repeated cycles.
  - **Precision, stated:** with n ≈ 300 or more repeated cycles, 0 unexplained bounds the non-determinism rate at
    Wilson upper ≤ 1.2 %. QA reports n and that bound.
- **Bootstrap:** blocks of 40 consecutive **selected** cycles. B and the seed are unchanged.

**A1.8 Predictions.**
- **SF1, SF3 and SF5 stand as written** (their rows are unchanged).
- **SF2 and SF4 are VOID by design change** (A0's predicate and U's bar changed after registration; precedent S6P3,
  2026-10-15). They are not scored.
- **Registered now, before any Stage 1 code or timing, and before the OFF arm:**

| # | prediction | P | class |
|---|---|---:|:---:|
| SF2′ | A0 (A1.3) passes without a design amendment | 0.40 | H |
| SF4′ | U-OK at `U_max` = 0.30 × `U0` | 0.55 | H |
| SF6 | `U0` (OFF-arm not-confirmed per cycle) in [0.25, 0.60] | 0.50 | H |

⚠️ **SF4′ is priced with Q-GATE-2's UPC 0.014 in view.** That figure covers real-signal positions only. The noise-only
candidates, the thing it can't see, are the risk, so I've kept the price near even.

**Waiting on the Captain:** confirm the A1.6 rule (`U_max` = 0.30 × the OFF arm's not-confirmed rate, frozen before
any ON decode), or name a fixed value. **Waiting on QA:** the (k) review of this amendment, and the A1.4 inventory check.

---

## §9 Amendment 2: QA's (k) review of §8, adopted (Architect, 2026-10-20 17:14Z by `date -u`, after QA's review; before any decode or Stage 1 timing)

QA ACCEPTED §8 with no row refused. It found one factual error and asked for two required changes, plus notes. All are
adopted here. Stage 1 is unchanged.

**A2.1 Factual error, mine (HK-038): the corpus size.** 10-09 has **3,634 WAVs** (gap-free, 261009_175200 to
261010_090015, **15.14 h**), not 7,264 or 30 h. I counted the owsfz and wsjt-x folders together. This is corrected in
place in A1.4.
- **QA's inventory check: 10-09 MEETS §5.3.** No other night is better. 10-04 is excluded (T1 training), and 10-18 is
  partial and direct-CODEC.
- **CPU projection:** ≈ 3.7 h per arm at 3.7 s per cycle. OFF + ON + repeat exceeds 8 h, so the night is sampled.
- **Adopted: *k* = 3** (odd), giving 1,212 cycles of the 3,634 slots. V-P applies. QA freezes the selection with its
  SHA before any decode.

**A2.2 Required 1: a row for "must not delay batch 2 / may hold back only the last batch".** That requirement had no
check. A3 covers batch 1 only. Holding back the last batch delays the **third pass's own** decodes, and those feed the
QSO late-batch logic: a reply is immediate only if it is ready by slot + 2.36 s, otherwise it is deferred.
- **Kept: the same-batch design** (R6′), with a new row, **A3′**. Rejected for now: QA's alternative of a batch of
  its own after batch 3, because a fourth batch changes `LateBatch` and the QSO channel capacity, which were validated
  live at 3 batches. **If A3′ fails, a separate batch is the design amendment**, for the Captain.
- **A3′ (the merge and default ON), mechanical, on the acceptance replay, per cycle, ON vs OFF:**
  - **(a) Content.** Batch 2 is identical N/N. Batch 3 with the fallback's decodes removed (`path` = 2, R11) is
    identical N/N, except cycles explained by abandonment in one arm (counted, ≤ 5 % as V5).
  - **(b) Batch 2's publish time is not delayed:** p95 of (ON − OFF) ≤ **50 ms**.
  - **(c) Batch 3's publish time:** p95 of (ON − OFF) ≤ **250 ms**.
- **Where the numbers come from (HK-038).** Both are **decision values (the Architect's), not measured**. The Captain
  may change them before any acceptance decode.
  - **50 ms** is a scheduling-jitter allowance. Batch 2 must not be held at all, so the bar is "nothing beyond jitter".
  - **250 ms** is about a third of the third pass's own median run time (0.78 s, the 10-19 live night, QA). Within that
    allowance, the fallback costs less delay than the third pass itself adds.
  - **Descriptive, mandatory:** QA reports the ON − OFF delay distributions (p50, p95, max) for batches 2 and 3, and
    how many OFF batch-3 decodes the ON delay would push across the 2.36 s reply guard. The guard test uses the
    replay's per-batch time relative to decode start, plus the live decode-start offset. **If that offset isn't
    recorded, QA says so and the count is not reported** (HK-027: what the instrument records).

**A2.3 Required 2: the precision statement in A1.7, corrected.** 0 of 300 gives a Wilson upper bound of **1.26 %**.
≤ 1.2 % needs **n ≥ 316**.
- With *k* = 3 the repeat (every 3rd selected cycle) has **n ≈ 404**, so the upper bound is **0.94 %** at 0 unexplained.
- QA reports n and the bound.

**A2.4 Notes, adopted.**
- **(a) U_max can't be smaller than the instrument can resolve.** QA's U-freeze note (A1.6) also gives the **projected
  ΔU 95 % half-width**, from the OFF arm's per-cycle not-confirmed variability (it uses no ON data). If `U_max` < 2 ×
  that half-width, U-OPEN is close to certain by construction.
  - **This goes to the Captain with the freeze note, before any ON decode.** He keeps the 30 % rule and accepts a
    likely U-OPEN, or sets `U_max` to a value of his choosing.
  - **What a U-OPEN would mean:** the instrument can't resolve the budget, which is not the same as the budget being
    breached. Default ON would then be his decision, made on the point estimate and the CI.
  - 🛑 **The bar is never moved after ΔU is seen.**
- **(b) A new limit for §6: 10-09 is the direct USB-CODEC chain.** T1 was trained on a Voicemeeter-chain night (10-04)
  and Q-GATE-2 tested on another (10-19). F1b is a ratio, so it doesn't depend on level. But the gate has never been
  seen on this chain, so **D-GO/D-STOP on 10-09 also tests transfer** to it. The report states it.
- **(c) A1.3, cycles with no slack.** A cycle with `s_i` ≤ 0 (the ordinary passes used the whole budget) counts as
  `f_i` > `s_i` whatever `f_i` is. That is the honest reading. QA reports how many such cycles there are.
- **(d) Row exclusivity:** confirmed by QA. A3′ is one pass/fail row: PASS iff (a), (b) and (c) all hold. A FAIL ⇒
  no merge and no default ON, as for A3, and the separate-batch design amendment goes to the Captain.

**Predictions:** unchanged. A3′ is a new row, and I register **SF7: A3′ passes, 0.60 H**, before any data.

✅ **CAPTAIN'S DECISION, 2026-10-20 17:25Z (by `date -u`), Architect's window: "30 % of the OFF rate is fine".** The A1.6 rule is confirmed: `U_max` = 0.30 × `U0`, frozen by QA in a dated note before any ON decode. A2.4(a) still applies: if `U_max` < 2 × the projected ΔU half-width, it goes back to him before any ON decode. He saw beforehand what the rule means in decodes: about 1 per cycle of WSJT-X's ≈ 25.8 is 3.9 pp; at `U0` 0.25 / 0.40 / 0.60 the cap is 0.075 / 0.12 / 0.18 per cycle (≈ 18 / 29 / 43 per hour), i.e. at most 1 unconfirmed per ≈ 4–10 extra correct at a 3 pp gain, but only 1 per ≈ 1.4–3.4 at the 1 pp bar. He was offered a ratio cap (gain-scaled) in addition, and did not take it. The full OFF arm may now run.

**Order:** QA freezes the *k* = 3 selection and measures the OFF slack `s_i` on the first 100 selected cycles before
any Stage 1 timing. Neither needs the Captain's A1.6 answer. The full OFF arm (U0) waits for that answer.

---

## §10 Amendment 3: Stage 1 cost: the gate runs after BP, not before (Architect, 2026-10-20 17:35Z by `date -u`; before any clean A0 or A2 run)

**What QA saw (a smoke test, not a result).** The Stage 1 build is `feat/coh-fallback-stage1` `44f0df4e` (shim
20260066, `libft8.dll` `7af6f893…a4d3`). QA ran it on 2 of A0's 100 cycles **while the OFF arm was loading the CPU**.
- **Wall time:** `f_i` = 17.9 s and 18.2 s, against `s_i` = 9.0 s and 9.3 s.
- **Split per cycle (median):** estimate 0.71 s, **F1b 16.8 s (≈ 94 %)**, C3 + BP 0.35 s.
- **Counts per cycle:** 165 eligible, 141 gated, ≈ 34 CRC-valid, ≈ 4 CRC-valid with a payload not already decoded.
- **Fidelity:** A2 on 3 cycles (53 rows) agrees with the Python reference (max F1b difference 0.0 dB).
- The timings are inflated by contention. But even halved, the gate-first order overruns the slack on both cycles.
  **The problem is the cost of F1b, not the port.**

**A3.1 Ruling: the gate order may be reversed. It is an "equivalent but faster computation" under R1, not a design
change.**
- **Why it publishes the same thing.** A candidate publishes iff (CRC-valid BP output) AND (F1b ≤ T1) AND (its text is
  new to the cycle).
  - These are three per-candidate predicates. None of them depends on the order in which they are evaluated, or on any
    other candidate.
  - So F1b is needed **only where the other two can still hold**: on CRC-valid outputs whose payload the ordinary
    `ft8_decode_all` call has not already decoded.
- **It is also what Q-GATE-2 measured.** "Kept" there was a C3 BP output with F1b ≤ T1: 822 of 1,111 outputs.
- **R4′.** The fallback runs the estimate, C3 and BP (no OSD) on every eligible candidate (R2′). It computes F1b only
  for CRC-valid outputs whose payload is not among the ordinary call's decodes. It publishes iff F1b ≤ T1, under the
  same dedup as R6′.
  - The final dedup at publish is unchanged: texts from the residual or third pass still drop there.
  - T1, the F1b definition and BP-only are unchanged.
- **The cost, projected:** the estimate on 165 candidates is ≈ 0.8 s, C3 + BP is ≈ 0.4 s, and F1b on ≈ 4 to 34 outputs
  is ≈ 0.4 to 3.5 s. Under the same contention that is ≈ 1.6 to 4.7 s a cycle, roughly a quarter to a tenth of the 17.9–18.2 s QA measured, against a slack of at least 8.7 s.
  - **This is my arithmetic from QA's smoke split, not a measurement.** A0 measures it.
- **R12′ counters, restated:** `eligible`, `attempted` (estimate + C3 + BP run), `crcOk`, `f1bComputed`, `gated`
  (F1b ≤ T1 among those), `published`, `abandoned`, `elapsedMs`.
- **Under the deadline,** reversing the order changes which candidates finish before abandonment. A0 and V5 cover that,
  as they did before. A cheaper order can only abandon less.

**A3.2 A new check that the reordering really is equivalent: A2(e), mechanical.**
- **Where:** on A0's first 100 cycles, at the product's own candidates.
- **How:** the cycle-level export runs twice, in **gate-first mode** (harness only; R4 already allows a harness
  override) and in the shipped **output-first** order, both with **no deadline**.
- **Predicate:** the multiset of published payloads per cycle is identical, **N/N cycles**. Any difference ⇒ A2 FAILS.
- **A2(a)–(c) are unchanged.** The per-row harness still computes F1b for **every** row, whatever the product order,
  so A2(c) is still read on all 4,949 F1b rows.

**A3.3 What runs on which build.**
- **A2(a)–(c)** may run on `44f0df4e` as soon as the CPU is free. That scores SF1 on the first Stage 1 build.
- **On the reworked build:** QA diffs the per-candidate functions (`ft8_coherent_fallback_at`, the F1b code) against
  `44f0df4e`. If they are unchanged, A2(a)–(c) carry over. If not, they are re-run.
- **A2(d), A2(e) and A0 run on the reworked build only.**
- 🛑 **A0 is NOT spent on `44f0df4e`.**
  - The smoke already shows the gate-first order can't fit. A clean number on it would answer a question nobody is
    asking.
  - The predicate, the 100 cycles and the slack note are unchanged, so nothing is being re-tried until it passes.
  - **QA reports the smoke as descriptive history in the A0 report.**

**A3.4 If A0 still fails on the reworked build, the next steps, in order.**
1. **The shared per-cycle reference-peak grid (QA's (a)).** This is still inside R1, still "equivalent iff A2 passes",
   so no design amendment is needed.
2. **Only then, as a design amendment for the Captain:**
   - eligibility by top-K or a prefilter (QA's (b)). This changes the attempted set, so it needs its own acceptance row,
     and Q-GATE-2 never tested it;
   - or a budget split (QA's (c)). This changes R7′ and A3′.

**A3.5 Predictions, honestly scored.**
- 🔴 **SF2′ ("A0 passes without a design amendment") is scored ❌ MISS now, on the smoke.** The order as specified
  (gate first) would overrun on 2 of 2 cycles, at twice the slack even after halving for contention.
  - The reorder is within R1, so it isn't formally a design amendment. Scoring SF2′ a hit on the reworked build would
    reward a fix that was prompted by seeing the data.
  - SF2′ was about whether **the specified design** fits the budget.
- **Registered now, before the clean run:**

| # | prediction | P | class |
|---|---|---:|:---:|
| SF8 | A0 passes on the reordered build | 0.70 | C |
| SF9 | A2(e) equivalence N/N on the first run | 0.80 | C |

SF8 is COMPUTED from QA's split. The risk is the estimate's cost, which now runs on all 165 candidates rather than 141.

**Order:** the Developer reworks Stage 1 (R4′, R12′, and the harness gate-first mode) while QA runs A2(a)–(c) on
`44f0df4e` after the OFF arm ends. Then come A2(d), A2(e) and A0 on the reworked build. The Captain is told, but there
is nothing to decide: the change is within the spec.

---

## §11 Ruling on the U freeze (Architect, 2026-10-20 18:22Z by `date -u`; before any ON decode)

**The note:** QA `qa/refset` `8a1b7368`, `results/2026-10-20-coh-fallback-u-freeze/note.md`, read in full.
- **The OFF arm:** `main` `5229beec`, Deep, `nhard` 24, the OSD sign fix read back, selection `9c20b921`, 1,211 cycles,
  0 exceptions, 0 abandoned passes.
- **`U0` = 0.2603** per cycle over 1,210 cycles, so **`U_max` = 0.078**.

**A11.1 The cycle with no WSJT-X reference is excluded: 1,210 cycles, `U_max` 0.078 stands.**
- Cycle 261009_175215 precedes WSJT-X's `ALL.TXT`, so its 27 decodes **cannot** be corroborated, whatever they are.
- Counting it would add an instrument artefact to `U0`. That isn't a choice of the stricter figure: excluding it is the
  correct one.
- The exclusion is mechanical (`ws` = 0) and paired: the same cycle is out of the ON arm and out of ΔU.
- **Generalised:** any cycle with `ws` = 0 is out of every Test-B row, in both arms.

**A11.2 Which half-width governs A2.4(a): the paired projection (ii). The trigger does NOT fire.**
- **Why (i) is the wrong quantity.** It is the uncertainty of U_off's mean.
  - ΔU is a per-cycle **paired** difference.
  - Batch 1 is identical by A3, and batches 2 and 3 without the fallback's decodes are identical by A3′.
  - So ΔU_i is the fallback's own not-confirmed count in cycle i, plus abandonment noise (≤ 5 % of cycles, V5).
  - U_off's cycle-to-cycle variance cancels out of the difference.
- **Why (ii) is realistic, not merely optimistic: there is data on file (HK-038).**
  - On Q-GATE-2, the same kind of rare-event count per cycle (UPC 0.014, n = 931) has a Poisson projection of
    1.96 × √(0.014/931) = **0.0076**.
  - Its block-bootstrap half-width was **0.008**, so the dispersion is ≈ 1.1.
- **With twice that dispersion for safety** (clustering in busy cycles, or abandonment), the half-width at ΔU = U_max is
  1.96 × √(2 × 0.078/1210) = **0.022**.
  - 2 × 0.022 = 0.045 < 0.078, so the trigger doesn't fire even then.
- **Nothing goes to the Captain under A2.4(a).** He is told the result. The bar does not move.
- **What the U rows can and can't resolve, said before the data:**
  - U-OK needs ΔU at about ≤ 0.056 (U_max − 0.022).
  - U-FAIL needs ΔU at about ≥ 0.10.
  - Between those, U-OPEN.
  - Q-GATE-2's real-signal UPC was 0.014, but noise candidates are what this row adds.

**A11.3 A gap I'm closing: the OFF arm must be the Stage 2 build's own.** The spec's design (§5.3, A1.5) is **one
Stage 2 build, with arms OFF and ON**. `U0` came from `main` `5229beec` because no Stage 2 build exists yet. That is
legitimate for freezing **only if** the Stage 2 OFF arm reproduces it. `main` may move before Stage 2 is cut: #225
changes how type 0.1 rows are handled, which can change Test-B counts.
- **The new validity row V-U0:** the Stage 2 build's own OFF arm runs **first**, on the same 1,210 cycles.
  - Its per-cycle decode multiset is compared with `5229beec`'s OFF arm, cycle by cycle.
  - **N/N identical ⇒ `U_max` 0.078 stands.**
  - **Otherwise,** `U_max` is re-frozen from the Stage 2 OFF arm by the same rule (0.30 × its `U0`), in a dated note,
    **before any ON decode**. QA reports both figures and the cycles that differ.
  - Either way the bar is fixed blind to ON data, so this doesn't loosen the pre-registration.
- **ΔU and NET are always paired against the Stage 2 build's OFF arm,** never against `5229beec`.

**A11.4 Prediction scored at this ruling:** SF6 (`U0` in [0.25, 0.60], 0.50 H): ✅ **HIT, narrowly** (0.2603). It is
also a hit on the 1,211-cycle basis (0.2824).

**Status noted:** the reworked build is `d926bdc6` (shim 20260067, `libft8.dll` `60963686…c3db`). QA's diff shows
`ft8_coherent_fallback_at` and the F1b code are byte-identical to `44f0df4e`, so A2(a)–(c) carry over under A3.3. The
smoke test (shared CPU, not A0) gave `f_i` ≈ 1.4–1.6 s against `s_i` ≈ 9.0–9.3 s, with identical gate-first and
output-first payloads. That is not a result. A0, A2(d) and A2(e) on an idle CPU are what count.

---

## §12 RULING: Stage 1 acceptance. A0 PASS, A2 PASS (A2(d) ruled on its population); Stage 1 → Stage 2 (Architect, 2026-10-20 18:57Z by `date -u`)

**On:** QA's report `results/2026-10-20-coh-fallback-stage1-acceptance/report.md` (`qa/refset`, local; root copy read
in full). The builds were SHA-verified: `44f0df4e` and `d926bdc6`.

| row | result |
|---|---|
| A2(a) BP outcome | PASS, 27,571 / 27,571 (4,734 outputs both) |
| A2(b) estimate + edge flag | PASS, 27,571 / 27,571 |
| A2(c) F1b and gate decision | PASS, 4,949 / 4,949 (max difference 0.0 dB) |
| A2(e) order equivalence | PASS, 100 / 100 |
| A0 cost | PASS, 0 of 100 over slack (`f_i` max 1.37 s against `s_i` min 8.71 s) |
| A2(d) anchor convention | dt median PASS; edge rate FAIL **as written** (6.85 %). The population is ruled below |

**A12.1 A2(d): the population is the primary decodes. On it, A2(d) PASSES.** I wrote the row badly, and I'm saying so
before ruling it.
- **What the row is for.** §5.1 says A2(d) tests **R3**, the mapping from a lattice position to the estimator's
  anchor, "so that the window is centred on the true signal".
  - Its reference is "**the decode's own** refined position", one per decode. Only the candidate behind a reported
    result has one.
  - A neighbour that duplicates the payload at the next lattice position (3.125 Hz away) cannot have its ±2 Hz window
    centred on that signal **under any mapping**. Its edge rate measures the lattice spacing, not R3.
- **So the row's purpose fixes the population: the 1,975 primaries.** On them the edge rate is **0.41 %** (8; bar
  2 %), and the dt median is 0.000 s, with an absolute median of 0.015 s. **PASS.**
- **Guarding against reading my own bar in my own favour (the standing prohibition):**
  - **It is a clarification of a row's population, not a better metric.** The predicate and the bar are unchanged.
  - **The literal FAIL stays on the record.** It is QA's reading as written, and it is cited beside this ruling.
  - **The ambiguity is my specification error,** and it is counted (A12.4).
- **What the 3,471 neighbours do tell us, carried forward:**
  - **Cost only, already paid.** Duplicates are dropped by dedup (R2′), and A0 passed with them included.
  - **One small real effect, to Stage 2.** If two fallback outputs in a cycle carry the same payload, dedup keeps
    whichever comes first. That could be an edge neighbour, which publishes a frequency up to about 3 Hz off. Test B's
    ±10 Hz match is unaffected. **R6″ (new, Stage 2):** among fallback outputs with the same payload in a cycle,
    publish one whose estimate is **not** at the window edge, and the first in candidate order among those. It is
    deterministic. A unit test covers it.
  - **QA's other worry: a neighbour at the edge failing where its centred sibling would succeed.** That doesn't lose a
    decode: the sibling is eligible too and is attempted once. Whether the product's lattice candidates find the signals
    at all, compared with Q-GATE-2's WSJT-X positions, is exactly what NET measures in Stage 2.
  - **Stage 2 descriptive:** the fallback's edge-flag rate per cycle among published outputs.

**A12.2 A0's "one session" condition was not met strictly.** The slack was taken at 17:14Z and the timing at 18:29Z,
on the same machine and the same day, but not back to back.
- **Accepted.** The margin is about 6×: `f_i` max 1.37 s against `s_i` min 8.71 s.
- A shift in machine state between the two can't plausibly close that gap. Recorded as a deviation.

**A12.3 A2's Python reference** is the persisted COH-GAIN result set (DLL `2fa6d993`, `nhard` 40). A2(a) compares
**BP-only** outcomes, with the Python path-1 rows counted as no output. BP doesn't depend on `nhard` or on the OSD
defect, so the reference is valid for this row. Recorded, not re-run.

**A12.4 Predictions scored at this ruling.**
- **SF8** (A0 passes on the reordered build, 0.70 C): ✅ **HIT.**
- **SF9** (A2(e) N/N, 0.80 C): ✅ **HIT.**
- **SF1** (A2 passes on the first Stage 1 build, 0.60 H): **VOID, not credited.**
  - A2(a)–(c) passed on `44f0df4e`. A2(d) ran only on `d926bdc6`, and it passes only under my own ruling on an
    ambiguity in my own wording.
  - Crediting a hit there would be scoring my reading of my own row. **It is counted as an Architect specification
    error** (an ambiguous population), with the RSE2 and S6P2 precedents.

**A12.5 Stage 1 → Stage 2: the condition in §4 is met** (A0 PASS and A2 PASS, the Architect rules). **Stage 2 starts
on the Stage 1 branch** (`feat/coh-fallback-stage1` at `d926bdc6`), under the Captain's go for both stages.
- **No separate Stage 1 merge (my recommendation; the merge is the Captain's, HK-010).** Stage 1 adds thread-local
  candidate retention inside `ft8_decode_all`, the production decode path, with nothing yet proving that it is
  outcome-neutral. A1, the flag-OFF identity, is the row that proves it, and A1 belongs to Stage 2.
  - **One merge at the end** has A1, A2, A3 and A3′ all behind it.
  - **If the Captain wants Stage 1 on `main` sooner,** a flag-free identity check of `ft8_decode_all` (outcome fields,
    a fixed set of recorded cycles) would have to run first.
- **Stage 2 carries:** R6′/R7′/R2′ (§8), R4′/R12′ (§10), the new R6″ (A12.1), and V-U0 (§11).
- **The replay's order:** V-U0, the Stage 2 build's own OFF arm, runs **first**, then ON, then the ON-repeat.

---

## §13 RULING: Stage 2 decision replay. D-GO, U-FAIL, A3′ FAIL, FP-watch fires ⇒ no merge, no default ON; three options go to the Captain (Architect, 2026-10-21 16:0xZ by `date -u`)

**On:** QA's message (2026-10-21) and `D:\Projects\claude\_qa-scratch\coh-fallback\analysis\stage2.json`, read in full.
The script is `qa/rr-study/coh-fallback/cf_stage2_analysis.py` (uncommitted). The raw outputs are in
`qa/rr-study/results/2026-10-20-coh-fallback-stage2-replay-raw/` (root). I re-checked them where a figure looked odd
(HK-018). Build `feat/coh-fallback-stage1` `1405ada4` (shim 20260068), `libft8.dll` `581331da…5f5d1`. Selection
`9c20b921`: 1,211 cycles, 1,210 with a WSJT-X reference. The Stage 2 code was read at `Ft8Decoder.cs:864-935`.

| row | result |
|---|---|
| V-U0 | PASS, N/N against `5229beec` ⇒ `U_max` **0.078** stands |
| V1 | **Deviation, accepted (A13.1)** |
| V2 | PASS: flags read back (off2 False, on and onrep True) |
| V3 | PASS: 0 exceptions, 0 access violations, 0 non-zero exits |
| V4 = A3 | PASS: batch-1 multiset 0 cycles differing |
| V5 | PASS: 0 of 1,211 cycles abandoned (Wilson upper 0.32 %) |
| V6 | PASS: 0 of 404 differing (Wilson upper 0.94 %) |
| **D-GO** | **D-GO**: NET **+6.56 pp [5.95, 7.22]** (2,057 more matches over 31,355 WSJT-X decodes; 67.72 % → 74.28 %) |
| **U** | **U-FAIL**: ΔU **+0.102 [0.082, 0.124]** per cycle; `CI_lo` 0.082 > `U_max` 0.078 |
| **A3′** | **FAIL**: (a) PASS; (b) FAIL; (c) FAIL. The populations are ruled in A13.3; the verdict is the same on either one |
| FP-watch | **FIRES** (A13.4) |

The arithmetic agrees across files. 2,180 fallback decodes were published; 94.36 % confirmed is 2,057, which equals
ΣΔM. The other 123 are not confirmed: 123 / 1,210 = 0.1017, which equals ΔU. By band, ΔU's increments are
A +2, B −2, C +7, D +116, total 123.

**A13.1 V1: no end pin per arm, accepted as a deviation.** The chain hashed `libft8.dll` once, at 19:35Z. QA
re-hashed it after the run and got the same SHA. All three arms loaded that one file, from one folder, one after
another, while the Developer kept the PC idle. V1's purpose is to show that one build ran in every arm. Three other
rows show the same thing independently: V-U0 is N/N against `main`, V4 is N/N, and V6 is 0 of 404. Recorded as a
deviation, with A12.2 as the precedent. **For the next chain: write a pin at the start and end of each arm.**

**A13.2 D-GO stands, and it also passes the transfer question (A2.4(b)).** 10-09 is a direct USB-CODEC night, and
T1 was trained on a Voicemeeter night. The gain held on this chain. NET is larger than Q-GATE-2's 3.03 pp on 10-19.
That is a different night, with a lower OFF match share (67.7 %), so there is more to recover. It is not evidence that
the gain grew.
- **NET by band, the mandatory descriptive QA could not get from `matched.csv`.** It comes from `testb.csv` instead:
  the batch-3 corroborated increase, ON − OFF, by the Test-B band of OpenWSFZ's own decode. This is my arithmetic; QA
  confirms it with `path` = 2.
  - B: +22 (**+0.07 pp**)
  - C: +388 (**+1.24 pp**)
  - D: +1,645 (**+5.25 pp**)
  - **80 % of the gain is in band D, the same band as 94 % of the unconfirmed outputs.** The gain and the U cost come
    from the same signals. A cut on band D alone would remove both.

**A13.3 A3′: (b) and (c) fail. The population is undefined where a batch is absent, and that error is mine.**
- **The defect.** `run.csv` writes `-1` for a batch that was not published. OFF has no batch 3 in **1,057** of 1,211
  cycles, and ON has one in 868 of those, because the fallback's decodes are its only content. QA's p50 of 2.3 s and
  p95 of 3.77 s take `ON tb3 − (−1)` as a delay. A3′ said "p95 of (ON − OFF)" and gave no rule for that case. That is
  an Architect wording error (ledger E10), and the third population ambiguity on this arm.
- **The population, ruled on the row's purpose (A2.2).** The row is for "the third pass's own decodes" being held
  back. A cycle with no OFF batch has no decode to delay. So (b) and (c) are read on the cycles where **both arms
  published that batch**. QA's literal figures stay on record beside these.

| | cycles | p50 | p95 | max | bar | |
|---|---:|---:|---:|---:|---:|---|
| (b) batch 2, both arms | 1,005 | 86 ms | **496 ms** | 756 ms | 50 ms | **FAIL** |
| (c) batch 3, both arms | 154 | 145 ms | **756 ms** | 902 ms | 250 ms | **FAIL** |
| whole cycle (`elapsed_ms`), descriptive | 1,211 | 87 ms | 677 ms | 958 ms | — | |

- **This does not read my bar in my favour.** It is a defect in a computation, a `-1` taken as a time, and the
  verdict does not change.
- **QA, please:** recompute (b), (c) and the noise floor (ON-repeat vs ON) on the both-published population. Report
  them beside the literal figures, and state the count of cycles where only ON published batch 3.
- **What the data say about the mechanism (my reading of the code and `run.csv`; not a measurement).** The fallback
  starts at batch 1 on **one extra thread** and runs **concurrently** with the residual and third passes
  (`Ft8Decoder.cs:876-886`).
  - Batch 2 is late by a median of 86 ms. Nothing waits for the fallback before batch 2, so this is the fallback's
    thread slowing the residual pass through contention.
  - Batch 3 also waits for the fallback to finish (`:927-928`).
  - **So a separate batch alone would fix (c) but not (b).** A design that passes both must start the fallback only
    after batch 3 has been published. With the flag ON, its decodes would then arrive about 1.4 s (median) to 2.3 s
    (p95) after the third pass, which is well inside the slack (≥ 8.7 s, A0).
- **Ledger E11, mine:** the 250 ms bar was never checked against the fallback's own cost once A0 measured it.

**A13.4 FP-watch fires. It goes to the Captain with this ruling.**
- **Overall:** fallback not-confirmed rate **5.6 % [4.7, 6.7]**, against batch 1's **1.4 % [1.3, 1.6]**.
- **By band** (the spec asks for the flag per band; my arithmetic from `testb.csv` increments, QA confirms):

| band | fallback not-confirmed | batch-1 not-confirmed | flag |
|---|---|---|---|
| D | 119 / 1,764 = **6.7 % [5.7, 8.0]** | 50 / 2,391 = 2.1 % [1.6, 2.8] | **fires** |
| C | 8 / 396 = 2.0 % [1.0, 3.9] | 1.3 % [1.0, 1.7] | does not fire |
| B | 1 / 23 | 1.5 % | n too small |

- **What it means.** In band D, a fallback output is about 3× as likely as a batch-1 output to go unconfirmed by
  WSJT-X.
- **What it does not mean.** Not confirmed is an **upper bound** on false decodes (§6): it also counts real
  transmissions that WSJT-X missed, and hashed texts. This instrument cannot tell those apart (HK-026).
- **For scale.** There are 2,057 confirmed decodes per 123 unconfirmed, about **17 : 1**. The Captain was shown a cap of
  "1 per 4–10 at 3 pp" (§9) and declined a ratio cap. 🛑 **The U row is read as frozen. U-FAIL is the record.**

**A13.5 What the spec now says, mechanically.**
- A3′ FAIL ⇒ **no merge and no default ON**, and the separate-batch design amendment goes to the Captain (A2.4(d)).
- U-FAIL ⇒ **no default ON** (§4: default ON needs D-GO **and** U-OK).
- **Neither fix covers the other.** A timing redesign does nothing for U, and nothing done about U fixes the timing.
- 10-09 is now **seen data**. It may train a U remedy, but it cannot test one.

**A13.6 The Captain's options (decision 1 of 2 matters; decision 2 is mostly housekeeping).**

**Decision 1: what happens to COH-FALLBACK next.**

| option | what it costs | what it leads to |
|---|---|---|
| **(P) Park it.** Record the result; the branch stays local | nothing | +6.56 pp on this night is not delivered. It can be reopened later from this record |
| **(I) Identify first (offline, my recommendation).** Tone-match the 123 not-confirmed fallback outputs against the audio, with a confirmed sample as the control (the FIELD-ID method; per-message working files only in `_qa-scratch`, HK-037) | QA CPU time; no build | Tells us whether U-FAIL is mostly false decodes or mostly WSJT-X misses. **It does not change the verdict.** It decides whether (R) is worth doing, and what a U remedy should target |
| **(R) Redesign (step 4).** (1) Timing: the fallback starts **after batch 3** in a **batch of its own** (a design amendment, because `LateBatch` and the QSO capacity were validated live at 3 batches and would need a live check). (2) U: a stricter gate for weak outputs, trained on 10-04 + 10-09, tested on a **fresh** 40 m night (QA lists the candidates). A new U bar, set by the Captain **before** that replay | a Developer build (HK-011), a live late-batch check, about 2.5 h of replay | Could pass every row. The risk is in A13.2: the gain and the U cost sit in the same band, so a U gate may cost most of the gain |

- **Why I recommend (I) before (R).** (R) needs a build, a live check and a fresh replay, and its value depends on a question (I) answers offline, with no build.
  - If most of the 123 are real signals, the U remedy should be light, or the Captain may want a different
    U instrument for the next arm.
  - If most are noise, a gate trained on 10-09's band D is the target.
- ⚠️ **A new U bar for a new night (R) is legitimate. Reading this night's U row differently is not.** I recommend
  against a default-ON override on this data: A3′ has failed too, so the code that would ship is not the code that
  would pass.

**Decision 2: the merge (housekeeping, unless he wants the code on `main`).** The spec says no merge, and I recommend
holding to it.
- The scheduling code would be rewritten by (R).
- A flag-OFF merge would put dormant code and the TLS retention in `ft8_decode_all` on `main` before A1's evidence
  is complete. QA's re-run of the unfiltered test suite and the ASan run on `1405ada4` are still to do.

**A13.7 Predictions scored at this ruling.**
- **SF3** (D-GO, 0.45 H): ✅ **HIT.**
- **SF5** (NET point in [1.0, 4.0], 0.50 H): ❌ **MISS** (6.56).
- **SF4′** (U-OK at 0.30 × `U0`, 0.55 H): ❌ **MISS.**
- **SF7** (A3′ passes, 0.60 H): ❌ **MISS** (on either population).
- **Architect errors E10 and E11** are recorded in the ledger.

**A13.8 QA's confirmation (2026-10-21, after this ruling).**
- **A3′ on the both-published population: confirmed exactly.**
  - Batch 2: n 1,005, p95 496 ms. Batch 3: n 154, p95 756 ms.
  - Cycles that published batch 3 in ON only: 868. In OFF only: 0.
- **Noise floor** (ON-repeat − ON, both published):
  - batch 2 p95 **119 ms** (n 326)
  - batch 3 p95 **139 ms** (n 345)
  - Both delays are well above it, so they are real.
- **NET by band: confirmed** (B +0.07, C +1.24, D +5.25, A 0.00 pp).
- 🔴 **My FP counts by band included the no-reference cycle `261009_175215`, against A11.1's rule that a `ws` = 0
  cycle is out of every Test-B row (ledger E12, mine).** QA's figures on the 1,210 cycles replace mine in A13.4:
  - **D** 118 / 1,763 = **6.7 % [5.6, 8.0]** against batch-1 49 / 2,390 = 2.1 % [1.6, 2.7]: **FIRES**
  - **C** 7 / 395 = 1.8 % [0.9, 3.6] against 54 / 4,398 = 1.2 % [0.9, 1.6]: does not fire
  - **B** 0 / 22
  - The flags are unchanged.
- **Test B corroboration in batches 1–2** moves by ±2 matches out of 31,355 while the decodes are unchanged: a
  one-to-one matching reassignment, immaterial.

**A13.9 Option (I), done by QA: the 123 unconfirmed outputs are mostly real signals.** This is descriptive. It
changes no verdict in §13.
- **Source:** QA `qa/refset` `ecc4c5e7`, `results/2026-10-20-coh-fallback-stage2-replay/fbid.json` (read in full;
  numbers only). The text working file has been deleted (HK-037).
- **The re-run is valid.** QA re-ran the ON arm on 210 cycles: 0 differ from the original ON arm, and the DLL was
  pinned at the start and the end.
- **Method.** Each output's text is re-encoded to its 79 tones and located from its Costas symbols only. The score is
  the share of the 58 data symbols whose strongest bin is the transmitted tone.
  - The null comes from other messages' tones at the same place: n = 10,040, mean 0.147, max 0.362.
  - T = 0.276 is its 99th percentile, set from the nulls alone.

| set | n testable | tones present | median score |
|---|---:|---|---:|
| unconfirmed (encodable) | 103 | **97 = 94.2 % [87.9, 97.3]** | 0.64 |
| confirmed control | 399 | 387 = 97.0 % [94.8, 98.3] | 0.72 |
| confirmed, SNR-matched | 378 | 96.8 % | 0.72 |

- **Upper bound on noise:** at most 26 of the 123 can be noise. Those are the 6 with no tones plus the 20 hashed
  outputs, which can't be re-encoded.
  - That is 0.005–0.021 per cycle, against ΔU 0.102.
  - **Only 6 outputs have positive evidence of being noise, and 2 of those are "other CQ" texts.** The instrument
    finds tones in 0 of 7 *confirmed* "other CQ" outputs, so it is blind there (HK-026). Positive evidence of noise is
    therefore **≤ 4 of 2,180** outputs.
  - For scale: about 10.5 chance CRC passes are expected from 172,385 BP attempts at 2⁻¹⁴, before the F1b gate and
    dedup cut that further.
- **What this does not show.**
  - Tones present proves that a signal with those tones is in the audio, not that every bit of the decoded message is
    right. The unconfirmed set scores lower than the control (median 0.64 against 0.72).
  - Batch 1's own unconfirmed decodes were not tested. So the FP-watch comparison (5.6 % against 1.4 %) is now known
    to be mostly decodes WSJT-X misses, **on the fallback side only**.
- **What it means for the next step.**
  - Test B's not-confirmed count (the U instrument) mostly counts **WSJT-X's misses** here. A stricter gate aimed at U
    would mostly cut real decodes. The (R) U-gate leg of A13.6 is therefore **not recommended**.
  - 🛑 **U-FAIL stays the record for this night.** A different U instrument (no tones, rather than not confirmed by
    WSJT-X) may be pre-registered **only for a new night**, with its own OFF-arm baseline on the same instrument and a
    bar the Captain sets beforehand. The "other CQ" blind spot and hashed texts must be handled by a stated rule.

**Waiting on QA:** the A13.3 recomputation (done, A13.8); confirmation of A13.2's NET by band and A13.4's per-band FP flag, using
`path` = 2; the committed analysis script. ~~and the A1 evidence runs when the CPU is free~~ 🔴 **Withdrawn (2026-10-21, QA, relayed by the Captain): A1 evidence is a merge gate, and no merge is pending (A13.5), so it is not owed now. It runs only if a later build is put up for merge. Listing it as waiting was my error (ledger E13).** **Waiting on the Captain:**
decision 1, and his go on QA's report commit (HK-033).

---

## §14 Amendment 4 (step 4, R′): the timing-only redesign. The fallback runs after batch 3, in parallel, and publishes in batch 4; tested on a fresh night (Architect, 2026-10-21 16:37Z by `date -u`; before any code)

**Authorised:** the Captain, Architect's window, 2026-10-21: *"go with the timing-only redesign"*. He also asked
*"can we even speed it up more, like using c/c++?"*, which A14.2 answers. **This amendment authorises a build and a
replay. Merge (HK-010) and default ON stay the Captain's.** It goes `To: QA`. QA writes the Developer handoff (HK-015).
`src/` and `native/` need a separate Developer session (HK-011).

**What stays.** The fallback's method stays as it is: R1, R2′, R3, R4′, R5, R6″, R8, R9, R10, R11, R12′ and R13. Its
per-candidate native code (`coherent_fallback.c`, A2 PASS) is **not touched**, except for the threading in A14.2.
**Rejected:** a stricter gate aimed at U (A13.9: it would mostly cut real decodes).

**A14.1 R6‴ / R7‴: when the fallback runs and where it publishes (replaces R6′ and R7′).**
- **Start.** The fallback starts only **after the cycle's last ordinary batch has been handed off**: batch 3 on Deep,
  batch 2 on Normal. On Deep, that is after the third pass, whether or not batch 3 had any decodes. **Nothing in the
  fallback may run concurrently with pass 0, the residual pass or the third pass.** That is what removes the
  contention behind A3′(b) (A13.3).
- **Publish.** The fallback's decodes go out as a **batch of their own**, after every ordinary batch: batch 4 on Deep,
  batch 3 on Normal. It is delivered only if it is non-empty.
  - The same per-cycle `seen` dedup, `IsPlausibleMessage`, noise-suppression filter and R6″ apply.
- **Deadline.** It shares the 13 s cycle budget (`SubtractionCycleBudget`, `Ft8Decoder.cs:108`). Unfinished work is
  abandoned, never queued, and counted (R12′).
- **R14 (new): the extra batch reaches the QSO services and the panel.** `LateBatch` and the QSO channels
  (`Program.cs:345-348`, "up to 3 batches per cycle", capacity 8) must carry **up to 4 batches per cycle** with the
  flag ON.
  - The Developer recomputes the capacity and records the arithmetic with FILE:LINE.
  - **With the flag OFF, the capacity and the behaviour are unchanged** (R13).
  - Unit tests cover the 4-batch case: no drop, the order kept, and the reply-deferral logic applied to batch 4
    exactly as to any late batch.

**A14.2 Speed: the Captain's question, answered.**
- **The fallback is already C.** `ft8_coherent_fallback_at` and the cycle loop live in `libft8`
  (`native/ft8_lib_vendor/refine/coherent_fallback.c`, `ft8_shim.c`). C# only calls them. Rewriting it in C or C++
  would gain nothing.
- **Where the time goes.** The loop runs over about 140–170 eligible candidates per cycle, **on one thread**. It took a
  median of 1.40 s, p95 2.31 s and max 3.32 s on the ON arm (`coh.csv`, 1,211 cycles), and that was while it competed
  with the ordinary passes.
- **R15 (new): parallel over candidates.**
  - The cycle loop splits the eligible candidates across `EffectiveSubtractionThreads` worker threads
    (`Ft8Decoder.cs:93`, 8 on the station). After batch 3, those threads have nothing else to run.
  - The per-candidate code has no mutable global state (`coherent_fallback.c:31`), so each candidate is independent.
  - **Determinism is required.** Results are gathered **in candidate order** before F1b, dedup and R6″, so the
    published set and its order do not depend on scheduling. V6 checks this. A2(e)'s mode switch stays in the harness.
  - **Projected: about 0.2–0.4 s median.** That is 1.40 s ÷ 8 with an allowance for imperfect scaling. **This is my
    arithmetic, not a measurement.** S4-T (A14.4) measures it.
- **Not now: the shared per-cycle downconversion and SIMD.** R1 already allows both as "equivalent iff A2 passes".
  They are worth doing only if S4-T or the old-CPU station shows the parallel version is still too slow. Each would
  need A2 re-run.
- **Why speed still matters once nothing waits for it.** Batch 4 arrives later than batch 3, so these decodes show up
  later in the panel. A reply to one of them is more likely to be deferred (A14.4 reports this). On a slower CPU (the
  `sol` class) the budget is tighter.

**A14.3 The fresh night, and a U instrument the fallback cannot fool (replaces U for this replay only; HK-038).**
- **Corpus.** QA lists every `artefacts/` folder (rule 2026-10-03) and picks **one 40 m night that is none of 10-04
  (T1 training), 10-09 (§13) and 10-19 (Q-GATE-2)**. It needs full-cycle WAVs and WSJT-X's `ALL.TXT`.
  - The Voicemeeter chain is preferred, since 10-09 already covered direct-CODEC.
  - Sample with an odd *k*, V-P, a frozen `selection.json` and its SHA, before any decode, as A1.4.
  - **If no such night exists,** QA says so and the Captain decides between waiting for one and a recorded night that
    is not independent. No decode runs until he does.
- **U′, the instrument.** The tone-presence test of A13.9 (`qa/rr-study/coh-fallback/cf_fbid.py` @ `ecc4c5e7`, null
  and T frozen as committed) is applied to every **Test-B not-confirmed** decode in both arms.
  - **U′_i** = the cycle's not-confirmed decodes that are **not shown present**.
  - **Not shown present** = tones below T, **or untestable** (hashed text, or a shape on which the instrument fails
    its own confirmed control, e.g. "other CQ").
  - Counting untestable decodes as not shown present is the conservative rule. It makes U′ an upper bound, as U was.
  - **ΔU′** = the mean over cycles of (U′_on − U′_off), paired, with the same bootstrap as §5.3.
- **The bar is set before any ON decode.**
  - QA runs the OFF arm first and computes **U′0** = the OFF arm's U′ per cycle.
  - QA proposes **U′_max = 0.30 × U′0** (the Captain's 30 % rule, §9) and the projected half-width (A2.4(a)), in a
    dated note.
  - **The Captain confirms it or names a value, before any ON decode.**
  - **Rows:** U′-OK `CI_hi(ΔU′)` ≤ U′_max; U′-FAIL `CI_lo(ΔU′)` > U′_max; U′-OPEN otherwise.
  - The old Test-B ΔU is reported beside it, descriptive only.
- ⚠️ **What 10-09 lets me say, and what it doesn't.** On 10-09 the fallback's ΔU′ would have been at most
  0.005–0.021 per cycle (A13.9). OFF's U′0 is unknown: batch 1's own unconfirmed decodes were never tone-tested. If
  most of them turn out to be real, U′0 is small and so is the bar. The Captain's confirmation step exists for exactly
  that.

**A14.4 Acceptance on the step-4 replay (same harness and design as §5.3 with A1.5; arms OFF, ON, ON-repeat; V-rows
V1–V6 as amended).**
- **V1 now needs a pin at the start and the end of every arm** (A13.1).

| row | predicate | guards | where the number comes from (HK-038) |
|---|---|---|---|
| **A3″ (a) content** | batches 1, 2 and 3 identical ON vs OFF, N/N, except cycles explained by abandonment in one arm (≤ 5 %, V5) | merge, default ON | by construction (A14.1) |
| **A3″ (b) time** | for batches 2 and 3, on the cycles where **both arms published that batch**: p95 of (ON − OFF) ≤ **150 ms** | merge, default ON | the measured repeat noise floor on this harness, p95 119 ms (batch 2) and 139 ms (batch 3), A13.8, rounded up. "Not delayed beyond what a repeat of itself shows" |
| **S4-T fallback time** | descriptive, mandatory: the batch-4 publish time from decode start and the fallback's wall time (median, p95, max) | — | — |
| **D-GO′** | `CI_lo(NET)` ≥ **1.0 pp** (D-STOP and D-OPEN as §5.3) | default ON | `BAR_G`, unchanged |
| **U′** | A14.3 | default ON | the Captain's bar, set before ON |

- **Population rule, written in this time** (E9, E10): every timing statistic is read **only on cycles where the
  batch is published in both arms**. The counts for ON-only, OFF-only and neither are reported beside it.
- **Descriptive, mandatory:**
  - NET and ΔU′ by band.
  - The FP-watch per band, on U′.
  - R12′ counters and the abandonment count.
  - **How many batch-4 decodes would miss the 2.36 s reply guard.** If the live decode-start offset is not recorded,
    that is said and the count is not reported (A2.2).
- **R14 live check before default ON (not a merge gate).** One live session on the station with the flag ON shows
  batch 4 reaching the panel and both QSO services, with no channel drops (the daemon log). QA specifies it after the
  replay.
- **Merge** needs A1, A2 (carried; A2(e) re-run on the parallel build, 100/100), A3″, the unit tests and the
  Captain's sign-off. **Default ON** needs D-GO′, U′-OK, the R14 live check and the Captain's decision.

**A14.5 Predictions (registered before any code or data).**

| # | prediction | P | class |
|---|---|---:|:---:|
| SG1 | A3″ passes, (a) and (b) | 0.75 | H |
| SG2 | fallback wall time median ≤ 0.5 s on the station (R15) | 0.65 | C |
| SG3 | D-GO′ on the fresh night | 0.70 | H |
| SG4 | U′-OK at the bar the Captain confirms | 0.55 | H |
| SG5 | A2(e) N/N on the parallel build, first run | 0.85 | C |

⚠️ SG4 sits near even on purpose: U′0's size is unknown (A14.3), and so is the bar.

**Order:** QA's (k) review of this amendment and the night inventory → the Developer handoff (QA) → the build → A2(e)
→ OFF arm → the U′ note → the Captain → ON and ON-repeat → the ruling. **Waiting on QA:** the (k) review and the
inventory. **The Captain is waiting on nothing yet.** His next decision is U′_max, after the OFF arm.

---

## §15 Amendment 5: QA's (k) review of §14 adopted, with K2 replaced (Architect, 2026-10-21 16:4xZ by `date -u`; before any code or decode)

**On:** QA `qa/refset` `bffe8544`, `2026-10-21-1646-qa-to-architect-k-review-s14-and-night-inventory.md`, read in
full. Verdict: ACCEPTED, no row refused, with three required changes, K1–K3.

**A15.1 K1 adopted: A3″(a) has no fallback-abandonment exception.**
- The fallback starts after batch 3 (A14.1), so its own abandonment cannot change batches 1–3. Carrying the A3′
  wording over was my error (ledger E15).
- **A3″(a), restated.** Batches 1, 2 and 3 are identical, ON vs OFF, N/N. The **only** exception is a cycle where an
  **ordinary pass** (residual or third) hit `SubtractionCycleBudget` in exactly one arm, read from the ordinary-pass
  counters (`abandon.csv`), not from R12′.
- Those cycles are counted and listed by slot. **Any other difference fails the row.**

**A15.2 K2: QA is right that the margin is too thin. But both of its options fail the (k) test on data on file, so
the row is replaced (HK-025(k), HK-038).**
- **The check.** I took the ON-repeat vs ON pairs from §13's raw outputs. There the two runs are identical by
  construction, so this is a zero-effect null. I put a block-40 bootstrap on the p95.

| statistic, null (ON-repeat − ON, both published) | n | point | 95 % CI |
|---|---:|---:|---|
| p95, batch 2 | 326 | 119 ms | [76, 288] |
| p95, batch 3 | 345 | 139 ms | [110, 412] |
| **median**, batch 2 | 326 | −1.7 ms | **[−11.5, +10.6]** |
| **median**, batch 3 | 345 | −2.2 ms | **[−11.2, +8.5]** |
| median, §13 ON − OFF (the failed design), batch 2 | 1,005 | 86 ms | [65, 113] |
| median, §13 ON − OFF (the failed design), batch 3 | 154 | 145 ms | [107, 253] |

- **Option (ii), a CI on p95 against 150 ms,** would read OPEN for a build with **no effect at all** (CI_hi 288 and
  412 ms). The row could never pass.
- **Option (i), a point estimate with a floor,** keeps the 11 ms margin problem QA found.
- **A tail statistic from about 150–1,000 cycles is too noisy to gate on. The median is not:** the null's CI is within
  ±12 ms, and the design that failed sits 65–253 ms out.
- **A3″(b), restated (mechanical, exclusive, first match wins):**
  - **Statistic.** The median of the **signed** (ON − OFF) publish time, for batch 2 and for batch 3 separately. It is
    read only on cycles where both arms published that batch (A14.4's population rule). Block-40 bootstrap,
    B 10,000, seed 20261007.
  - **FAIL** if `CI_lo` > 50 ms for either batch.
  - **PASS** if `CI_hi` ≤ 50 ms for both.
  - **OPEN** otherwise. An OPEN is not a merge verdict, and it goes to the Captain.
- **Where 50 ms comes from (HK-038).** It is the Architect's decision value from A2.2 ("nothing beyond jitter"). It
  was checked here against both branches on this harness:
  - the null passes with ≈ 40 ms to spare;
  - the §13 design fails (CI_lo 65 and 107 ms).
- **The p95, as descriptive with its CI:** reported beside the same night's ON-repeat vs ON p95 and CI.
- **My error (ledger E14):** I set a p95 point bar 11 ms above a floor without checking how noisy a p95 is.

**A15.3 K3 adopted, with one correction of framing.**
- **The correction.** 0.021 is 10-09's **observed** upper bound (A13.9), not a ceiling on what a new night can do. So
  U′-FAIL is not impossible. The real problem is that the bar may sit so far above what is expected that the row
  cannot catch a meaningful degradation. That is still a (k) defect, and K3's remedy fits it.
- **The U′ note must report, before the Captain is asked:**
  - U′0, split into tested-and-absent and untestable;
  - U′_max = 0.30 × U′0;
  - the projected half-width.
- **It must also state one mechanical line:** "U′_max is / is not ≤ 2 × 0.021 = 0.042." In words: would this bar
  catch a fallback twice as noisy as 10-09's?
  - **If it is not,** the Captain chooses knowingly between keeping the 30 % rule (the row is weak, and is reported
    as such) and a fixed value he names.
  - **QA does not choose.**
- **My error (ledger E16):** I did not check whether the U′ bar could discriminate, against A13.9's bound, before
  registering it.

**A15.4 Notes N1–N4 accepted as written.**
- The depth is **Deep** (read back from the config).
- V1 is a fail-closed re-hash at both ends of every arm.
- The live R14 check covers wall time under live load (SG2 is a harness figure only).
- A2(e) 100/100 on the parallel build is a QA acceptance step.

**A15.5 The night: the Captain's choice (it trades independence against sample size).**
- **`20260922_2056` (QA's and my recommendation).**
  - Voicemeeter chain, 40 m (QA confirms the band correction before freezing), 12.0 h, gap-free, ≈ 960 cycles at
    k = 3.
  - **No verdict has read it.**
  - The cost is a somewhat wider CI than 10-09's 1,211 cycles. By Stage 2's NET half-width (±0.6 pp), D-GO′'s 1.0 pp
    bar is not at risk unless the gain falls about 5 pp.
- **`20260930_1930`, the alternative.**
  - ≈ 1,430 cycles.
  - It is the OSD-FIX TEST night and the SUB-FEAS flag-ON replay night, so it is not independent of two other
    verdicts.

**A15.6 Predictions.**
- SG1 refers to A3″ as restated here. Its probability is unchanged (0.75), and it is restated before any data, with
  the precedent of RC-14's restatement.
- SG2–SG5 are unchanged.

**Order:** QA writes the Developer handoff on §14 + §15 now. The night is frozen once the Captain picks.

**A15.7 Recorded (2026-10-21, from QA): the night and the handoff. No decode has run.**
- **The Captain chose `20260922_2056`.**
- **40 m confirmed** by the run's band-correction note: the daemon's live status read `dialFrequencyMHz` 7.074, and the
  Captain confirmed it directly.
  - 🛑 The `arm_config` field `dial_freq_hz` = 14074000 is stale. **Never cite it.**
- **Selection frozen before any decode:** k = 3, 961 of 2,882 gap-free slots.
  - V-P PASS: even 480 / odd 481.
  - SHA-256 (LF) `9ce4fbb4…7c28`.
  - File: `_qa-scratch\coh-fallback\step4\selection.json`.
- **Developer handoff:** `dev-tasks/2026-10-21-coh-fallback-step4.md` (`qa/refset` `d8033b25`).
  - The Architect spot-checked it against §14 + §15 and found it faithful: the start after the last ordinary batch,
    R14 for 4 batches, the gather in candidate order, abandon-never-queue, A2(e), and A3″(b) as the median row.

---

## §16 Pre-OFF-arm analysis (Captain's request): A2(e) on the parallel path, the sol impression, and the U′ instrument made mechanical (Architect, 2026-10-21 18:2xZ by `date -u`; before any step-4 replay decode)

**On:**
- QA's message of 2026-10-21.
- QA `qa/refset` `1bc3b5c9` (`results/2026-10-21-coh-fallback-step4-a2e/`): A2(e) 100/100, A0 0/100 (`f_i` median 0.94 s,
  p95 1.25 s, max 1.40 s), A2(d) the same as Stage 1.
- The code review `5759895c` (R-1 to R-3 fixed in `b8fc732e`).
- The two sol impressions.
- `cf_fbid.py` (`shape_class`, `:91`).

**A16.1 Question 1: the A2(e) run tested the old path. A parallel-path run on the same 100 cycles is required (HK-022).**
- **What the run shows.** `cf_a0.py` drives `ft8_coherent_fallback_run`, the single-thread entry point. The result
  shows that the new DLL leaves that path unchanged, which is worth having. But **it never ran the code that ships**:
  the plan and process exports, and the managed parallel runner with its gather in candidate order.
- **Why the other evidence isn't the same thing.**
  - The Developer's real-library test is a unit test on a few inputs.
  - The sol comparison is 10 cycles and 15 decodes, an impression.
  - V6 compares ON with ON-repeat. **Both** of those are parallel, so V6 shows that the parallel path is
    deterministic, **not that it equals the single-thread result**. A gather bug that is stable from run to run would
    pass V6.
- **The wording was mine.** "Re-run on the parallel build" could be read as "on the new DLL". I meant the path. That
  is ledger E17, the same class as E9.
- **A2(e′), required before the OFF arm.**
  - **Where:** the same first 100 selected cycles of 10-09.
  - **How:** through `Run(…)` in Replay81's harness, at 8 workers, with no deadline.
  - **Predicate:** the published payload list per cycle, **in order**, is identical to the single-thread output-first
    export of `1bc3b5c9`. **N/N cycles.** Any difference ⇒ FAIL, and there is no step-4 replay until it is explained.
  - QA estimates ≈ 8 minutes.
- **SG5** (A2(e) N/N on the parallel build, first run, 0.85 C) is **scored on A2(e′)**, not on `1bc3b5c9`.

**A16.2 Question 2: the sol impression changes no row. It adds one requirement to the live check.**
- **It confirms the design.**
  - Batches 1–3 had no systematic delay: medians −0, −51 and −68 ms, against +170 ms in Stage 2.
  - The scaling was ≈ 7.6× at 8 workers.
  - The minimum margin to the budget was 3.9 s, with 0 abandoned.
- **The PC figures fit that.** A0's single-thread median of 0.94 s on an idle PC is lower than Stage 2's 1.40 s, which
  was measured under contention. So §13's fallback time was inflated by the contention itself.
  - At ≈ 7× scaling the PC should give ≈ 0.13–0.2 s, which would make SG2 (≤ 0.5 s) comfortable. That is my
    arithmetic. The replay's S4-T measures it.
- **The OFF-arm plan: unchanged.**
- **The ON rows: unchanged.** A3″(b)'s median row reads timing in the harness. Batch 4's lateness is outside every
  verdict row by design (A14.4, S4-T descriptive).
- **The R14 live check (specified by QA after the replay): add one row of measurement.**
  - On sol, batch 4 arrives a median 7.9 s after the decode starts.
  - Its decodes therefore reach the QSO services well past the 2.36 s reply guard: any reply to one is deferred, by
    construction.
  - **The live check must therefore record, per cycle with a batch 4:**
    - the batch-4 publish time **from slot start**, using the live decode-start offset (which the live log has in ms);
    - whether a QSO service acted on a batch-4 decode, and whether it deferred.
  - This is HK-027: measure what the instrument can record.
  - **Descriptive.** But if a QSO service acts on a batch-4 decode *without* deferring, that is a defect and it blocks
    default ON.

**A16.3 Question 3: one thing must be made mechanical before the OFF arm. The U′ "untestable" rule is not yet code
(HK-021).**
- **Why it matters now.** A14.3 says "untestable = hashed text, or a shape on which the instrument fails its own
  confirmed control, e.g. 'other CQ'". "Fails" has no threshold. **U′0 comes from the OFF arm,** so the rule has to be
  frozen before the OFF arm is read.
- **U′ test, frozen (a script constant, committed before the OFF arm runs):**
  - **Instrument:** `cf_fbid.py` @ `ecc4c5e7`, with T = **0.276** frozen from 10-09's null.
    - The 09-22 null is computed and reported **descriptively**.
    - If its p99 differs from 0.276 by more than 0.03, QA flags it to the Architect before any ON decode. The ruling
      comes first, and it is blind to ON data.
  - **Shape classes:** `shape_class()` (`:91`), as committed.
  - **Untestable:**
    - (i) the text is hashed (`<…>`) or cannot be re-encoded; or
    - (ii) its shape class is **not testable on this night**.
  - **A shape class is testable iff** the OFF arm's **confirmed** decodes of that class have **n ≥ 10** (a random
    sample of up to 50 per class, seed 20261007) **and** a present rate ≥ **80 %**.
  - On 10-09 this rule makes "other CQ" untestable (0 / 7) and keeps the others (≥ 95 %).
  - **The class list is frozen from the OFF arm alone,** before any ON decode, and applies to both arms.
- **Where 80 % and n ≥ 10 come from (HK-038):**
  - The testable classes on 10-09 scored 95–100 % on their confirmed controls.
  - A class whose own true decodes show their tones less than 80 % of the time cannot evidence absence.
  - **n ≥ 10 is a minimum sample, a decision value.** At n = 10 the 80 % bar is loose: 8 / 10 has a Wilson lower bound
    of only 49 % (computed). So QA reports every class's rate with its Wilson CI. A class with n < 10 counts as
    untestable, the conservative direction.
  - Both are decision values.
- **The OFF-arm U′ note (A14.3 + A15.3) also reports:**
  - the class table: n, the confirmed present rate, testable yes or no;
  - U′0 split three ways: tested-absent, hashed or unencodable, and an untestable class;
  - U′_max = 0.30 × U′0, the projected half-width, and the "≤ 0.042" line.
- **Pre-flight before the OFF arm (HK-020):**
  - the DLL pin `aaf6b03e…` with a fail-closed re-hash at both ends;
  - the flag read back as false;
  - Deep, `nhard` 24 and the OSD fix read back;
  - the selection SHA `9ce4fbb4…`;
  - `ws` = 0 cycles excluded, paired;
  - Replay81 built against `b8fc732e`.

**Order:** A2(e′) → (Captain's go) OFF arm → the U′ note with the class table → the Captain sets U′_max → ON and
ON-repeat → the ruling.

---

## §17 A2(e′) PASS; the Captain may set the U′ untestable thresholds after the OFF arm, under conditions (Architect, 2026-10-21 by `date -u` at commit; before any step-4 replay decode)

**A17.1 A2(e′): PASS.** Source: QA `qa/refset` `5de1bb47`, `results/2026-10-21-coh-fallback-step4-a2eprime/`.
- **The run:** build `b8fc732e`, DLL `aaf6b03e…`, the first 100 selected cycles of 10-09, production-normalised input,
  8 workers, no deadline.
- **Result:** the published payload list, in order, is identical to the single-thread path on **100 / 100** cycles,
  with every row field identical as well. 1 and 2 workers also give 100 / 100.
- **Timing, descriptive:**
  - single thread: median 1.08 s per cycle;
  - 8 workers: median **0.26 s**, p95 0.39 s, max 0.49 s.
  - These are harness figures on 10-09. **SG2 is still scored on the step-4 replay's S4-T.**
- **Count against the Stage 1 export: 98 / 100 cycles agree.** In the other two, the count is one lower (301 against
  303). QA's hypothesis is R6″, which Stage 2 added: it collapses a same-payload duplicate that the Stage 1 export
  counted twice. That is plausible but unverified. QA checks it **descriptively** with the two payloads' estimates; it
  is not a gate. A difference that is not an R6″ collapse comes back to me.
- **The raw-audio pass** (89 / 100 against Stage 1, an input-normalisation mismatch in QA's harness) is kept as a
  record only.
- **SG5** (A2(e) N/N on the parallel build, first run, 0.85 C): ✅ **HIT**, scored on A2(e′) as §16 said.

**A17.2 The Captain's request: set the U′ untestable rule after the OFF run.**
- **What the timing protects.** The verdict's blind is **ON data**: the OFF arm holds no fallback output. That is the
  Captain's own rule from 2026-10-08: "blind only where it protects a verdict".
- **The one real exposure, and I'm stating it once.** The rule feeds `U0′`, and U′_max = 0.30 × U′0. A rule chosen
  after seeing the OFF arm's per-class rates could raise or lower the bar.
  - The direction isn't fixed. Declaring more classes untestable raises U′0, and the bar with it at 0.30 ×. But it
    also counts the fallback's outputs in those classes against ΔU′, at 1 ×.
  - The exposure is small, but it is real. §5's clause ("no threshold changes after any acceptance decode") would
    forbid it as written.
- **The Captain owns decision values. So this is allowed, under four conditions that keep it visible and keep it blind
  to ON:**
  1. **Frozen before the OFF arm (QA scripts it now):** the instrument `cf_fbid.py` @ `ecc4c5e7`, T = 0.276,
     `shape_class()`, the sampling (up to 50 per class, seed 20261007), and the three-way split of U′0. Only the
     **two thresholds** (minimum n and minimum present rate) are left open.
  2. **After the OFF arm, before any ON decode:** QA's U′ note shows the per-class table (n, present rate, Wilson CI).
     **Beside the Captain's choice it shows U′0 and U′_max under §16's default (n ≥ 10, ≥ 80 %),** so any effect of
     the choice is on the record.
  3. **The Captain writes the two values down before any ON decode.** They apply to both arms and are never changed
     afterwards.
  4. **The U′ note records this as a deviation from §5's clause,** with today's date and his words.
- **My recommendation:** keep §16's default unless the table shows a class sitting right at a threshold. Two
  reasons: it was set without data, and on 10-09 it gave the right answer (only the class the instrument cannot test
  was left out).

**Order:** QA freezes A17.2(1) in its script → (Captain's go) OFF arm → the U′ note with the table and the default
beside it → the Captain sets the thresholds and U′_max → ON and ON-repeat → the ruling.

✅ **CAPTAIN'S DECISION, 2026-10-21 18:45Z (`date -u`), Architect's window: "go with your recommendations".**
- **The thresholds are §16's default, n ≥ 10 and present rate ≥ 80 %.** They are frozen **now, before the OFF arm**,
  together with the rest of the procedure. A17.2's after-the-OFF-arm option is **not used**, so there is no deviation
  from §5 to record.
- **The OFF arm has the go.** Pre-flight as §16 A16.3.
- **A17.3 The "distinct + 1" in the Stage 1 export, checked descriptively by QA: NOT an R6″ collapse. Not chased.**
  - **What QA found.** In both cycles the shipped selector publishes exactly the number of distinct payloads, whether
    keyed on 10 bytes or 12. The edge flag does not separate them either. The Stage 1 export counts one more.
  - **The code.** I read the export's count (`ft8_shim.c:2362-2396`). It seeds `seen` from the ordinary call's
    payloads and adds a payload only when it publishes. On that reading, a second copy of a payload is "known".
    The +1 is not explained by that reading. I did not trace it further.
  - **Why it is not chased.**
    - The export is a Stage 1 diagnostic and is not shipped.
    - Every verdict reads the shipped selector: the Stage 2 replay, the step-4 replay, and A2(e′), whose two sides
      are both the shipped path.
    - The direction is the safe one: the shipped path publishes fewer, never more.
  - **Recorded as an open descriptive item.** It is reopened only if a shipped-path count ever disagrees with its
    own distinct-payload count.
- **The Captain's remaining decision is U′_max.** QA proposes 0.30 × U′0 with the half-width and the ≤ 0.042 line,
  and he confirms it or sets his own before any ON decode.

## 18. The step-4 OFF arm and the U′ note, reviewed (Architect, 2026-10-21 ~19:5xZ by `date -u`)

**Read:** QA's note `qa/rr-study/2026-10-21-1950-qa-uprime-note-step4-off-arm.md` (`qa/refset`, local) and
`results/2026-10-21-coh-fallback-step4-off/{uprime_off.json, status.txt}`. No ON decode has run.

**A18.1 The OFF arm is valid.**
- The night was `20260922_2056`, 961 cycles, 18:51:24Z to 19:41:13Z.
- Build `b8fc732e`. The DLL `aaf6b03e…` was hashed at both ends of the arm (V1 as amended). The selection SHA
  `9ce4fbb4…7c28` was checked at launch.
- Read back at both ends: flag false, Deep, nhard 24, OSD fix 1, shim 20260069.
- 0 exceptions and 0 abandoned cycles. One cycle has `ws` = 0 and is excluded, paired, which leaves 960.
- The procedure (`cf_uprime.py`, `93fa9d2b`) was committed before the arm ran. The `cf_fbid.py` blob was asserted
  equal to `ecc4c5e7`. Every §16 pre-flight item is met.

**A18.2 The class table and U′0 are as reported. I re-added them from `uprime_off.json`.**
- **Testable classes:** RR73/73/RRR 47/50, grid 48/50, grid CQ 48/50, report 47/50. The lowest is 94 %, so no class
  is near the 80 % line and A17.2's reopen condition does not arise.
- **Untestable classes:** other CQ 2/50 (by rate) and other 8 (n < 10).
- **The night's null p99** is 0.2759, against the frozen T of 0.276. There is no flag.
- **U′0 = 179 / 960 = 0.1865**:
  - tested-absent 36 (0.0375);
  - hashed or unencodable 135 (0.1406);
  - untestable class 8 (0.0083).
- Of the 147 unconfirmed decodes in testable classes, 111 (76 %) show their tones.
- **The proposal arithmetic checks.** U′_max = 0.0559. The A11.2 half-width at that level,
  1.96 × √(2 × 0.0559 / 960), is 0.0212, and twice that is 0.0423 ≤ 0.0559, so A2.4(a) does not fire. The
  A15.3 line reads **NO**.
- The OK and FAIL thresholds QA solved for (0.038 / 0.082 at 0.0559; 0.027 / 0.065 at 0.042) use the same
  A11.2 form at ΔU′ = the value. I re-solved them and they agree.

**A18.3 What the A15.3 line could not say, and my error in writing it (ledger E21).**
- The line asked whether the bar "would catch a fallback twice as noisy as 10-09's" by testing U′_max ≤ 0.042.
- **That test is wrong.** A bar of 0.042 does not catch a true ΔU′ of 0.042: the estimate sits on the bar and the
  row reads OPEN. QA's note shows this. To fail a fallback at 0.042, the bar must lie below
  0.042 − 1.96 × √(2 × 0.042 / 960) = 0.024.
- **At 960 cycles, no bar does both jobs.**
  - Passing a 10-09-like fallback (0.021) needs a bar ≥ 0.021 + 0.013 = 0.034.
  - Failing one twice as noisy needs a bar < 0.024.
  - These conflict. With this sample the row cannot separate 1× from 2×, whatever the bar.
- **What the bar chooses** is therefore where the OPEN band sits, i.e. which fallbacks pass as OK without coming
  back to the Captain:
  - **0.0559 (the 30 % rule):** OK up to about 0.038, i.e. up to about 1.8 × 10-09. FAIL from 0.082 (3.9 ×).
  - **0.042 (fixed):** OK up to about 0.027 (1.3 ×). OPEN from 0.027 to 0.065. FAIL from 0.065 (3.1 ×).
- **Scale, from the Stage 2 replay (HK-038, 10-09, not this night):**
  - The fallback added about 1.7 confirmed decodes per cycle (2,057 over 1,211).
  - ΔU′ = 0.042 would be about one counted decode per 25 cycles, roughly every 6 minutes of FT8. That is about
    2.5 % of the fallback's confirmed yield.
  - This is for scale only, not a bar: a ratio rule would read ON data and is not offered.

**A18.4 My recommendation to the Captain: a fixed U′_max = 0.042. He decides.**
- **Why:**
  - It is the value my own A15.3 line was written to test against.
  - A fallback like 10-09's still reads OK: at 0.021 the CI upper bound is about 0.034.
  - A fallback 1.3–3 × noisier comes back to him as OPEN instead of passing silently as OK.
- **The cost:** a higher chance of U′-OPEN from night-to-night variation, i.e. one more decision for him later. It is
  not a block, because OPEN is not a breach. There is no merge pending either way.
- **Keeping the 30 % rule** is also defensible. It is the rule he confirmed for U, and it was set before any data. The
  row is then reported as weak, as A15.3 says.
- 🛑 **Whatever he sets is frozen before any ON decode, and it is never moved after ΔU′ is seen** (A2.4).
- **SG4** (U′-OK, 0.55) is scored against the bar he sets. The probability is not revised.

**A18.5 THE CAPTAIN'S DECISION: keep the 30 % rule. U′_max = 0.0559375 per cycle, frozen.**
- **Source.** The Captain said it in QA's window at 2026-10-21T19:47:56Z (`date -u`, QA, first-hand): "keep the
  30% rule". He said it after reading QA's U′ note, which sets out both options and their consequences.
  - My A18.4 recommendation (0.042) reached him only after he had decided. It is superseded.
- **The freeze.** QA records it in `qa/rr-study/2026-10-21-1948-qa-uprime-max-frozen-step4.md` (`qa/refset`, local),
  with the class list SHA `da559b55…`.
- **The rows:**
  - U′-OK: `CI_hi(ΔU′)` ≤ 0.0559375.
  - U′-FAIL: `CI_lo(ΔU′)` > 0.0559375.
  - U′-OPEN otherwise.
- **The A15.3 line stands as NO, and the Captain accepted its consequence.** A fallback twice as noisy as 10-09's
  would read U′-OPEN. The row is reported as weak (A18.3).
- 🛑 **This bar is never moved after ΔU′ is seen.** SG4 is scored against it.
- **Next:**
  - QA commits the step-4 analysis script before any ON decode.
  - The ON arm then needs the Captain's go, which QA asks for separately.

**A18.6 SUPERSEDES A18.5: the Captain changed his decision before any ON decode. U′_max = 0.042 per cycle (fixed),
frozen.**
- **Source.** In the Architect's window at 2026-10-21T19:49:24Z (`date -u`, first-hand), after reading the A18.4
  recommendation with both options and their consequences, he said: "alright, go with your recommendations."
  - The only open recommendation was the fixed 0.042.
  - No ON decode had run, so this is still the before-ON setting that A14.3 and A15.3 allow.
  - A18.5 (0.0559375, 19:47:56Z) is kept as the record of the earlier choice.
- **The rows:**
  - U′-OK: `CI_hi(ΔU′)` ≤ 0.042.
  - U′-FAIL: `CI_lo(ΔU′)` > 0.042.
  - U′-OPEN otherwise.
- **What the rows can resolve (A11.2):** OK needs ΔU′ ≤ about 0.027, FAIL needs ΔU′ ≥ about 0.065. A2.4(a) does
  not fire: 2 × 0.0183 = 0.0367 ≤ 0.042.
- **The weakness is the same as in A18.3.** A fallback twice as noisy as 10-09's sits on the bar and reads OPEN.
- 🛑 **Never moved after ΔU′ is seen.** SG4 is scored against 0.042.
- QA re-freezes its note and puts 0.042 into the analysis script before any ON decode.
- **Confirmed at 2026-10-21T19:53:33Z (`date -u`, Architect's window, first-hand).**
  - The Captain asked whether 0.042 is too tight, given that the fallback looks like a real improvement and false
    decodes could be reduced afterwards.
  - I answered:
    - only FAIL blocks, and FAIL needs ΔU′ ≥ about 0.065, about 3 × 10-09's largest;
    - a fallback like 10-09's reads OK;
    - OPEN goes to him and is not a rejection;
    - raising the strength gate later is possible, but needs its own test.
  - He replied: "go with your recommendations". **0.042 stands.**

---

## §19 RULING: the step-4 replay. A3″ PASS, D-GO′, U′-OK; every replay row passes. Default ON now waits only on the R14 live check and the Captain (Architect, 2026-10-22 ~14:3xZ by `date -u`)

**Read:** QA's message of 2026-10-22 ~14:25Z, and `_qa-scratch\coh-fallback\step4\analysis_step4.json` with the
per-cycle U′ aggregates (`off\uprime_off.json.percycle.csv`, `on\uprime_on.json.percycle.csv`) and `chain4.log`.
The raw copy in `qa/rr-study/results/2026-10-21-coh-fallback-step4-replay-raw/` is not yet committed. No message
text was read: counts only (HK-037).

**Order of events, checked.** U′_max = 0.042 was frozen at 19:49–19:55Z (§18 A18.6) and the analysis script was
committed with it (`qa/refset` `9448cb92`) before the ON arm started at 20:00:27Z (`chain4.log`). ON finished
20:53Z, ON-repeat 21:11Z. **No bar was set or moved after any ON decode.**

**A19.1 The rows.** Night `20260922_2056` (40 m, Voicemeeter chain), 961 cycles (960 with a WSJT-X reference),
build `b8fc732e` / `db3d7df5` line, DLL `aaf6b03e…`, Deep, nhard 24, OSD fix, 8 workers.

| row | result | verdict |
|---|---|---|
| V1 DLL pin, start and end, every arm | equal in OFF, ON, ON-repeat | PASS |
| V2 read-backs | all three arms | PASS |
| V3 exceptions | 0 / 0 / 0 | PASS |
| V4 = A3 batch 1 identical | covered by A3″(a): 0 cycles differ | PASS |
| V5 abandonment | 0 / 961 (Wilson hi 0.40 %); ordinary 0, fallback 0 | PASS |
| V6 ON-repeat | 0 / 321 differ | PASS |
| **A3″(a)** batches 1–3 identical | 0 / 0 / 0 cycles differ; 0 ordinary-budget exception cycles | **PASS** |
| **A3″(b)** median signed delay, both-published | batch 2: −0.3 ms [−12.5, +10.2], n 909; batch 3: −4.0 ms [−18.9, +12.1], n 238. Both CI_hi ≤ 50 | **PASS** |
| **D-GO′** | NET **+3.82 pp [3.44, 4.21]** (71.68 → 75.50 %; ΣΔM 1,170 / ΣW 30,656, re-divided: 3.817) vs CI_lo ≥ 1.0 | **D-GO′** |
| **U′** | ΔU′ **+0.0198 [0.0125, 0.0271]** (U′0 179/960 = 0.1865 → U′ 198/960 = 0.2063, re-subtracted: 19/960 = 0.0198) vs CI_hi ≤ 0.042 | **U′-OK** |
| S4-T (descriptive) | fallback wall median **215 ms**, p95 352, max 532; starts at median 3.07 s from decode start; batch 4 published in 668 / 961 cycles, median **3.35 s**, p95 4.10, max 4.86 s from decode start; min margin to the 13 s budget 8.1 s | — |

- **Population (A14.4):** batch 2 both 909 / ON-only 0 / OFF-only 0 / neither 52; batch 3 both 238 / 0 / 0 / 723.
- **The p95s, descriptive:** batch 2 94.5 ms [79, 113] against this night's ON-repeat − ON 297 ms [48, 424];
  batch 3 111 ms [79, 142] against 233 ms [63, 495]. ON − OFF is no wider than a repeat of itself.
- **Where the margin is.** U′'s CI_hi (0.0271) sits on the ≈ 0.027 that A18.6 said OK needs. It passes, but not
  by much. The bar was not moved and is not reinterpreted.

**A19.2 FP-watch: it trips on Test B, and §14 asked for it on U′. Computed both; the tones say the extra
unconfirmed outputs are mostly real signals, and the rest are hashed texts the instrument cannot test.**
- **QA's flag (sub-feas rule, on Test B not-confirmed):** batch 4 54 / 1,224 = **4.4 % [3.4, 5.7]** against batch
  1's **1.1 % [1.0, 1.3]**: it **trips**. By band: D 47 / 972, C 7 / 225, B 0 / 27.
- **§14 A14.4 asked for the FP-watch "on U′".** Batches 1–3 are identical in both arms (A3″(a)), so the per-cycle
  ON − OFF difference of each U′ component is exactly the fallback's. No cycle has ON < OFF in any component.
  From the per-cycle aggregates (my arithmetic):

| fallback's 54 not-confirmed outputs | n | per output (of 1,224) | OFF arm, all batches (of 22,264) |
|---|---:|---|---|
| tones shown present | **35** | — | 111 |
| tested and absent | **2** | **0.16 % [0.04, 0.59]** | 36 = **0.16 % [0.12, 0.22]** |
| hashed or unencodable | 17 | 1.4 % | 135 = 0.61 % |
| untestable class | 0 | — | 8 |
| **U′ (not shown present)** | **19** | **1.55 % [1.00, 2.41]** | 179 = **0.80 % [0.69, 0.93]** |

- **Read mechanically on U′, it still trips, narrowly** (CI_lo 1.00 % > CI_hi 0.93 %). The comparator is the OFF
  arm's **all-batch** U′, because the per-cycle U′ file has no batch split (my error E22 below). **The whole excess
  is hashed texts.** On the testable outputs, the fallback is **as clean as the ordinary decoder**: tested-absent
  0.16 % in both. 35 of its 37 testable unconfirmed outputs show their tones (94.6 %, as 10-09's 94.2 %, A13.9).
- **What that says.** Most of the fallback's Test-B "unconfirmed" outputs are signals WSJT-X did not decode. The 17
  hashed ones are the instrument's blind spot (HK-026): they are counted against the fallback, as the conservative
  rule says, and they are inside the U′-OK above.
- **What it does not say.** Tones present proves that a signal with those tones is in the audio, not that every bit
  of the message is right (A13.9). Why the fallback's hashed share is 2.3× the ordinary decoder's is not known.
- **The FP-watch is descriptive.** It goes to the Captain beside this ruling. It changes no row.
- **The old Test-B ΔU is +0.056 [0.041, 0.072].** It is descriptive by A14.3 and is not compared with 0.042, which
  is a U′ bar. 🛑 It is never cited as a U verdict.

**A19.3 What the rows now allow (A14.4).**
- **Merge** needs A1, A2 (carried; A2(e′) 100 / 100, §17), A3″ (**PASS**), the unit tests (code review APPROVED,
  `db3d7df5`) and the Captain's sign-off. **A1 (flag-OFF identity, §5.2) has not run on this build.** It was
  withdrawn as not owed while no merge was pending (E13). **It is owed now, if the Captain wants this put up for
  merge.**
- **Default ON** needs D-GO′ (**met**), U′-OK (**met**), **the R14 live check (not run)** and the Captain's decision.
- **Limits, stated:** one night, Voicemeeter chain, 40 m, replay timing (not live); 10-09 (direct-CODEC) gave NET
  +6.56 pp, this night +3.82 pp, so the size of the gain varies by night. Reply-guard misses are not reported:
  the replay has no live decode-start offset (A2.2).

**A19.4 The R14 live check: what QA's specification must contain (A14.4, A15.4 N3, A16.2).** QA writes it as a
dated spec; the Architect (k)-reviews it; **the Captain's go is needed to run the step-4 build live with the flag
ON on the station.** It is not a merge gate.
- **Pre-flight (HK-020, HK-035):** the DLL hash at the start and the end; the flag set **through the config API**
  and read back true (never a hand edit of the station config); Deep, nhard 24 and the OSD fix read back.
- **Size:** at least **200 cycles with a batch 4** (≈ 70 % of cycles had one here, so about 2 h of a busy 40 m
  evening). A decision value; QA may propose another with its reason.
- **L1 delivery (PASS/FAIL):** every batch-4 decode the daemon logs reaches the panel and both QSO services, in
  order, and the daemon log shows **0 channel drops**. Any drop or missing delivery ⇒ FAIL, which blocks default ON.
- **L2 deferral (defect check):** for every batch-4 decode a QSO service acts on, it deferred. **Acting without
  deferring is a defect and blocks default ON** (A16.2). If no QSO service acted on any batch-4 decode, L2 reads
  **NOT EXERCISED** and says so: it is not a pass (HK-022).
- **L3 descriptive:** per cycle with a batch 4: publish time **from slot start** (the live decode-start offset +
  the time from decode start); how many batch-4 decodes fall past the 2.36 s reply guard; fallback wall time under
  live load (median, p95, max) and the R12′ and abandonment counters.
- **HK-037:** aggregates only; no message text leaves the function that reads `ALL.TXT` or the daemon log.
- **QA states** what the daemon log records for deliveries and drops before specifying L1 (HK-027): if it does not
  record a drop, the row cannot read 0 drops and must say how it will be measured.

**A19.5 Owed by QA (descriptive, mandatory under A14.4, not blocking this ruling):** NET by band; ΔU′ by band; the
FP-watch on U′ by band. And commit the raw-results copy with the analysis output.

**A19.6 The sol cross-check.** Descriptive (§16); no row depends on it. The rerun is housekeeping. It goes ahead on
the Captain's go, as QA has asked.

**A19.7 Predictions, scored now (§14 A14.5).**
- **SG1** A3″ passes, (a) and (b), 0.75 H: ✅ **HIT**.
- **SG2** fallback wall median ≤ 0.5 s on the station, 0.65 C: ✅ **HIT** (215 ms).
- **SG3** D-GO′ on the fresh night, 0.70 H: ✅ **HIT** (CI_lo 3.44 pp).
- **SG4** U′-OK at the Captain's bar, 0.55 H: ✅ **HIT**, narrowly (CI_hi 0.0271 vs 0.042).
- SG5: ✅ already scored (§17).

**My error (ledger E22):** A14.4 asked for "the FP-watch per band, on U′" without saying what U′ is compared with.
The sub-feas rule compares with batch 1, and U′ is recorded per cycle, not per batch, so batch 1's U′ rate cannot
be read from the outputs. The comparator above (OFF arm, all batches) is my choice at the ruling. The row is
descriptive, so no verdict depends on it.

**Waiting on the Captain:** (1) whether to put step 4 up for merge (A1 then runs first); (2) his go for the R14
live check once QA has specified it; (3) the sol rerun (housekeeping). **Waiting on QA:** the R14 specification
(A19.4); the A19.5 descriptive items; committing the raw copy (HK-033 for any push).

---

## §20 A19.5 received; (k) review of QA's R14 live-check spec: ACCEPTED with changes K4–K8 (Architect, 2026-10-22 ~14:3xZ by `date -u`)

**A20.1 A19.5, by band (QA `qa/refset` `75c46b99`, descriptive).**
- NET: D +3.02 pp of the 3.82; C +0.71; B +0.09; A 0.
- ΔU′: D +0.0177 (17 of the 19); C +0.0021 (2).
- FP-watch on U′: D 1.75 % [1.09, 2.78] against 1.03 % [0.75, 1.41]; C 0.89 % [0.24, 3.18] against 0.67 %.
- **So the gain, the U′ cost and the FP-watch excess all sit in band D, as on 10-09 (A13.2).** C is indistinguishable
  from the ordinary decoder. The per-cycle U′ files were regenerated byte-identical. Recorded; no row changes.

**A20.2 The spec reviewed:** `qa/rr-study/2026-10-22-1430-qa-r14-live-check-spec-step4.md` (`qa/refset` `3f748351`),
read in full, with the code of the build under test (`b8fc732e`: `LateBatch.cs:119-120`,
`QsoAnswererService.cs:1225-1295`). **Verdict: ACCEPTED, with five required changes.**

**K4: QA's L2 correction is right, and adopted. My A16.2 / A19.4 wording was wrong (ledger E23).**
- "Acting without deferring is a defect" was written from sol's impression (batch 4 at a median 7.9 s). On the PC,
  26 of 668 batch-4 cycles publish early enough that acting immediately is legal.
- The predicate QA wrote matches the code. `CanStartWhole` is `now − (cycleStart + 15 000 ms) ≤ 2.36 s`
  (`LateBatch.cs:119-120`), so a defect is an `applied-immediate` on batch 4 logged after
  cycleStart + 15 s + 2.36 s.
- The ±50 ms band is listed, not scored. Adopted as written.

**K5: L1a must not count `superseded` lines as deliveries.**
- `SupersedeDeferred` (`QsoAnswererService.cs:1231-1236`) logs a second `late batch 4 superseded` line for a held
  reply, against the batch that created it, at a later batch 1.
- Counted as written, that line could hide a missing delivery: one cycle's line goes missing while another cycle's
  superseded line fills the count.
- **L1a counts the outcome lines written by `ProcessLateBatchAsync`** (`:1294`), excluding `superseded`. The
  `superseded` lines are counted separately and reported.

**K6: L1a and L1b must cover batches 2, 3 and 4, not batch 4 alone.**
- The channel drops the **oldest** item (`DropOldest`). A drop caused by the extra batch would therefore lose an
  earlier batch, and batch 4 itself would arrive.
- **L1a predicate:** for N = 2, 3 and 4, per service, the count of `late batch N` processing lines equals the count of
  cycles that published batch N, in order. QA states where the published count for batches 2 and 3 comes from in the
  live log.
- **Batch 1:** QA states whether the services log one line per batch 1. If they don't, a batch-1 drop is **not
  observable** under (i), and the report says so (HK-022).

**K7: no vacuous pass.**
- "Every service that logs" lets a service that logs nothing pass. Both services must be **running** and must log a
  line per supplementary batch. `ProcessLateBatchAsync` logs `no-match` even when Idle and not auto-answering
  (`:1276-1294`), so this holds under option A too.
- A service that is not running reads **NOT EXERCISED** for L1a. It is not a pass.

**K8: the run is a separate data era.**
- With the flag ON live, the station's decoder differs from every endurance and R&R run.
- **The window must not overlap any endurance or R&R run, and its data is never pooled with flag-OFF data**
  (cf. SUB-FEAS flag-ON/OFF).
- The flag is set back OFF through the config API at the end, and read back.

**Accepted as written:** the HK-027 table (§0); the pre-flight P1–P4; the stop rule (200 batch-4 cycles, 90-minute
floor: it stops on a count, not on an outcome); L3; the reading rules; L1c as a 10-cycle unscored pilot whose
predicate is frozen before the scored run (NOT OBSERVABLE if neither source ties a decode to batch 4).
- **The pilot is itself a live flag-ON run.** It needs the Captain's go too, and he can give both goes at once.

**A20.3 The two decisions QA leaves to the Captain, with what each rests on.**
1. **The drop counter (L1b).**
   - **(i) Inference** costs nothing. Under K6 it detects a lost batch 2, 3 or 4, but not a lost batch 1 (if K6
     finds no batch-1 line), and it cannot tell a drop from a service that stalled.
   - **(ii) A counter in `TrimmingWriter`** needs a Developer change (HK-011), a QA code review and HK-039 before the
     run. It touches the daemon's queue only, not the decoder, so the replay verdicts carry over.
   - **I recommend (ii), as QA does.** The capacity change (8 → 10) is R14's real risk, and it is the one thing no
     test so far can audit. A drop needs the service to fall about 2–3 cycles behind (my arithmetic from the
     capacity, not measured). That is most likely while it is waiting to transmit, i.e. under option B.
2. **TX policy.**
   - **(A) Receive-only:** L1 and L3 are fully scored, and L2 reads NOT EXERCISED.
   - **(B) Auto-answer on air** for a window the Captain names: L2 is exercised (a batch-4 CQ was present in about
     25 % of the replay's cycles), and the station transmits on 40 m.
   - **If he chooses A,** default ON rests for L2 on the unit tests (batch-4 deferral, R14) and the code review alone.
     He decides that knowingly. The NOT EXERCISED stays on the record.

**A20.4 Spot-check of QA's amendment (`qa/refset` `1334bbec`, diff against `3f748351` read in full): faithful to
K4–K8.**
- L1a covers N = 2, 3 and 4, and gives each count's live-log source.
- Batch 1 is stated NOT OBSERVABLE under (i).
- `superseded` lines are excluded from the count and reported separately.
- A service that is not running reads NOT EXERCISED.
- P5 and P6 are added.
- **One item stays open, as QA states:** whether the batch-2 and batch-3 log counts equal the published counts.
  The pilot freezes that predicate before the scored run. **The spec is ready for the Captain.**
