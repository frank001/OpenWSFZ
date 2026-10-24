# SPEC — `COH-MULTISET-BUILD`: the coherent fallback tries four more bit-metric sets where V3 fails; flag-gated (default OFF); then an offline replay, as shipped vs with the sets

- **To:** QA (owner of the OpenSpec change, `tasks.md` and the Developer handoff; HK-015 / HK-000). **cc:** Captain. **From:** Architect.
- **Date:** 2026-10-24 14:55Z (`date -u` 14:54:40Z).
- **Branch:** `arch/coh-multiset` (local; the arm's spec, amendments and ruling live here). Docs only: `git diff --stat -- src/ native/` is empty.
- **The build is in `native/` and `src/`** (`native/ft8_lib_vendor/refine/coherent_fallback.c`, `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, the managed interop and config). It needs a separate Developer session (HK-011) and a new shim number, the next free one after `20260069`; QA confirms the number on `origin/main` before the handoff.
- **Authorised:** the Captain, Architect's window, 2026-10-24, after the COH-MULTISET ruling and its options: *"yes, write the build spec."*
  - **This spec authorises the build and the replay.** Merge (HK-010) and default ON stay the Captain's.
- **Status:** pre-registered for the acceptance rows (§5, §6). QA may amend mechanics before any decode, by a dated note. No row, bar or threshold changes after any acceptance decode has run.
- 🛑 **Licence (Captain, 2026-10-24, re-confirmed):** method only. **No WSJT-X source is opened, copied, transliterated or ported.** The reference is QA's own clean-room Python, written from the spec's prose (§2 R1). The new code carries a provenance header like `coherent_fallback.c:1–8`.

## 0. Evidence this rests on

| figure | value | source |
|---|---|---|
| X (C1 → J2 → J3 → N1, first CRC-valid, BP only) where G and C3 both fail, at WSJT-X's positions | **NET_X +2.115 pp [1.937, 2.302]**, 554 right / 15 wrong; f_X 2.64 % [1.60, 4.30] vs same-night f_C3 3.02 % | COH-MULTISET ruling `2026-10-24-1436` §1 (night `20261022_1949`, 974 cycles) |
| per set, right at all / only this set | C1 11 / 1, J2 269 / 64, J3 401 / 196, N1 177 / 71 | same, §3 |
| OSD in the fallback (L2) | +7 right for X, +19 / 1 for C3: **closed** | same, §3 |
| CPU, Python, per consulted row | four sets 0.031 s (C3 0.047 s, G 0.078 s) | same, §3 |
| the fallback as shipped, replay | NET +3.82 pp [3.44, 4.21], ΔU′ +0.0198 [0.0125, 0.0271]; wall median 215 ms, p95 352 ms | COH-FALLBACK §19 (`20260922_2056`) |
| positions → production | the fallback went from +5.25 pp at WSJT-X's positions to +3.82 pp in replay | COH-GAIN; COH-FALLBACK §19 |

🛑 **Not established, and measured here:**
- the gain from our own candidates, with the F1b gate on the outputs;
- false outputs on the product's noise candidates (U′);
- the native CPU cost;
- a second night.

**For scale only, not a bar or a prediction:** applying the positions → production ratio (0.73) to +2.1 pp gives about +1.5 pp.

## 1. What changes, in one paragraph

In the coherent fallback's per-candidate body (`cf_process_one`, `ft8_shim.c:2247`; the parallel twin is `ft8_coherent_fallback_process`, `:2634`), **when V3 + BP gives no CRC-valid output**, the same candidate gets up to four more tries, in this fixed order:
1. **C1** (order 1 on power);
2. **J2** (joint pairs);
3. **J3** (joint triples);
4. **N1** (order 1 on magnitudes, normalised bit by bit).

Each set is built from **the same per-symbol correlations `x_re/x_im` that `cf_v3_llrs` has just computed** at the same estimate (`coherent_fallback.c:392–416`). Each goes to BP only (as `cf_run_bp`, `ft8_shim.c:2236–2244`), and each is followed by the CRC.
- **The first CRC-valid output ends the walk.** From there it follows the existing path unchanged: the known-payload check, `cf_snr_db`, the F1b gate (≤ `CF_T1_DB`), the states, dedup, `IsPlausibleMessage`, batch 4.
- **If V3 gives a CRC-valid output, nothing new runs** (as the arm, A1.1).
- **The new work is gated by a flag.** Flag OFF, or the fallback OFF ⇒ nothing changes.

## 2. Requirements

| # | Requirement |
|---|---|
| **R1 the method is the measured one** | Port **exactly** `qa/rr-study/coh-multiset/ms_metrics.py` as frozen for the arm (last change `96aa80d4`; unchanged at `1d172b18`), using `coherent_extract.py`'s V1 for C1, as `ms_metrics.py` imports it. Grouping, the magnitude score, the Gray map, N1's division (0 when both maxima are 0), the bit order and the sign (positive = bit 1) are as that file. **An equivalent but faster computation is allowed only if B1 passes** (e.g. the J3 max-log over 512 hypotheses by any exact rearrangement). B1 is what "exactly" means. The arithmetic is double, as `cf_v3_llrs`. |
| **R2 when the sets run** | Only for a candidate on which the fallback's V3 ran and BP returned **no CRC-valid output** (state `NO_CRC` today: `ft8_shim.c:2663–2665` in `_process`, `:2507–2509` in the serial `_run`; both paths get the sets). Never when V3 is CRC-valid, whether the payload is known, new, gated or gated out. Never on a candidate the fallback did not attempt. |
| **R3 order and stop** | C1 → J2 → J3 → N1, fixed (the arm's order, chosen in advance, never tuned). The first CRC-valid output stops the walk. It then takes the **existing** path exactly as a V3 output would: KNOWN if its payload is in the snapshot's decoded list, otherwise SNR, F1b and the gate. **A known or gated-out payload is not retried with a later set.** |
| **R4 the gate applies to set outputs** | A set's new payload is published only if F1b ≤ `CF_T1_DB` (17.552 dB), the same constant and the same `cf_f1b_db` call as for V3 (`ft8_shim.c:2680–2683`; `_run` `:2527–2530`). **The arm did not apply this gate.** It can only lower both the gain and the false outputs, and the replay measures both. |
| **R5 decoder** | BP only: `ftx_ldpc_decode_llrs` with `osd_depth` −1, `K_LDPC_ITERATIONS`, production normalisation, then CRC-14, as `cf_run_bp`. **No OSD** (L2 closed). The raw set values are cast to float exactly as `cf_run_bp` casts V3. |
| **R6 provenance** | Every fallback result records which set produced its payload: 0 = V3, 1 = C1, 2 = J2, 3 = J3, 4 = N1, and −1 for none. It goes in the harness outputs and the per-cycle counters. **`ALL.TXT`, UDP and panel formats are unchanged.** |
| **R7 the flag** | `decoder.coherentFallbackMultiSet`, **default `false`**. It is read once per cycle, as `coherentFallbackEnabled` is. It acts only when `coherentFallbackEnabled` is true. Config POST is an overlay (HK-035): a partial update leaves it as it was (test). **No Settings-page control in this change.** The Developer chooses how the flag reaches native (a parameter of `_process`/`_run` or a per-call flag bit, **not** a process-global), and records it with FILE:LINE. |
| **R8 no mutable global state** | The per-candidate code stays free of mutable globals (`coherent_fallback.c:31`, the hash-state completeness test). Scratch lives in `cf_ctx_t` or on the stack. Parallel results stay deterministic: they are gathered in candidate order (step-4 R15). |
| **R9 diagnostic export** | A new diagnostic-only export, which the Developer names (e.g. `ft8_coherent_fallback_sets_at`), takes `(pcm, f0, t0)` exactly as `ft8_coherent_fallback_at` and returns: the estimate; V3's BP outcome; for **each** of C1/J2/J3/N1, its 174 raw values, BP rc, CRC flag and payload, **computed for every set regardless of R2/R3** (B1 needs all four); and the R3 walk's result. **The existing exports' contracts and struct layouts are unchanged** (`_at`, `_cycle`, `_snapshot`, `_run`, `_plan`, `_process`, `_unpack`). Any new field goes in a new struct or in an appended field with the C# side (`CohFallbackTypes.cs`) changed in the same commit, a size assertion and a test. |
| **R10 log line** | The per-cycle `Coherent fallback:` line (R12′) gains aggregates only: `sets=on/off`, the number of candidates that entered the walk, and CRC-valid counts per set (C1/J2/J3/N1). No text. |
| **R11 flag OFF ⇒ nothing changes** | With `coherentFallbackMultiSet` false: identical native calls, outputs, counters (apart from the added zeros) and order. With `coherentFallbackEnabled` false: as today (R13). Characterisation tests cover both. |
| **R12 nothing else moves** | Pass 0, the residual pass, the third pass, batches 1–3, F1b, `CF_T1_DB`, the estimator, V3, the deadline and abandonment rule (abandoned, never queued; R12′), the batch-4 publish and `LateBatch` capacity (A14.1 R14): **unchanged**. |
| **R13 era** | With the flag ON, decodes are a **new era**: never pooled with flag-OFF figures. `FT8_SHIM_VERSION` bumps, and the DLL SHA is what identifies a build. |

## 3. Stages

- **Stage 1: the native core and R9's export, no product wiring.** → B1, B2, B3.
- **Stage 2: the product wiring, R2–R8 and R10–R11.** It starts only after B1 passes.
- **Before the replay:** QA's HK-039 review of every Developer commit, with the `Reviewed-commit:` record committed before any acceptance run.
- **Before any push:** `pre_merge_check.py` from a clean checkout of the exact commit (HK-006, Captain 2026-10-23).

## 4. Who decides what

| step | needs |
|---|---|
| Stage 1 → Stage 2 | B1 PASS (Architect rules) |
| the replay | B2, B3, A1 green; HK-039 record; the Captain sets D and U′ bars after the REF arm, before any MS decode (§6.3) |
| merge with the flag OFF | A1, B1–B3, the unit and characterisation tests; `pre_merge_check.py`; **the Captain's sign-off** (HK-010) |
| default ON | D-GO and U′-OK (§6), then **the Captain's decision** (he may ask for a live check first, as R14 was) |

## 5. Stage acceptance (mechanical)

| row | predicate | guards | where the number comes from (HK-038) |
|---|---|---|---|
| **B1 port fidelity** | Native (R9 export) vs `ms_metrics.py` on the COH-MULTISET consulted rows (the 7,498 rows of `main_rows.csv` with `consulted = 1`, anchors as the arm), same DLL line. **For each of C1, J2, J3, N1:** the BP outcome (CRC-valid y/n and payload equality) agrees on **≥ 99.5 %** of rows; **and** the walk's result (which set, which payload) agrees on ≥ 99.5 %. Also **V3's outcome agrees on ≥ 99.5 %** (it must not have moved). | the method's identity with what was measured | 99.5 % is COH-FALLBACK A2(a)'s port margin for the same kind of floating-point difference, a decision value. 7,498 is the arm's own population |
| **B2 grouping and sign** | Unit tests (native): J2 makes 15 groups per half (14 pairs + 1 single), J3 makes 10 (9 triples + 1 pair); no group touches symbols 0–6, 36–42 or 72–78; on a noiseless synthetic signal every set's 174 signs equal the codeword's bits (positive = 1); with the Gray map replaced by the identity (a test-only hook, or a test copy of the routine), J2 and J3 fail on that same signal | the grouping and sign that B1's agreement could share with the Python by accident | the arm's A1.4 test and V2b, ported |
| **B3 determinism** | The existing row-by-row test between `_run` and the parallel `_process` (`CoherentFallbackStep4NativeTests`) passes with the sets ON, and the provenance (R6) is equal row by row | R8 | by construction |
| **A1 flag-OFF identity** | Existing suite green; characterisation: with `coherentFallbackMultiSet` false, `ALL.TXT` lines, UDP datagrams, panel events and QSO-channel batches for a fixed set of recorded cycles are **identical** (outcome fields) to the pre-change build, with the fallback ON and with it OFF | the merge | by construction (R11) |

## 6. The decision replay (offline; REF vs MS, the step-4 design)

### 6.1 Corpus

- **Inventory:** QA lists **every** `artefacts/` folder with full-cycle WAVs and a WSJT-X `ALL.TXT` (rule 2026-10-03).
- **The night:** QA picks one 40 m night that is **none of** `20261004_1634`, `20261009_1752`, `20261019_1905`, `20260922_2056`, `20260930_1930` and `20261022_1949`.
  - The Voicemeeter chain is preferred, and the 2026-10-17..19 OWS-recorded-WAV disposition applies.
  - The frozen ordered `selection.json` and its SHA are committed before any decode.
  - Use the whole night, or a systematic 1-in-k sample with k odd if the CPU projection is over 8 h. The choice is recorded before any decode.
- **If no such night exists,** QA says so, and the Captain chooses before any decode. His options are:
  - wait for a fresh night;
  - reuse `20260922_2056`, where no metric-set choice was made but the shipped fallback was accepted;
  - reuse `20261022_1949`, the arm's own night, which is not independent of the GO.

### 6.2 Fixed

- **One build:** the Stage 2 build, with the DLL SHA pinned at the start and end of every arm.
- **Settings:** harness mode as step 4, Deep, subtraction ON, `nhard` 24, sign fix ON, threads 8, `coherentFallbackEnabled` **true** in every arm.
- **Arms**, each in a fresh process with its flags read back:
  - **REF:** `coherentFallbackMultiSet` = false, i.e. as shipped;
  - **MS:** `coherentFallbackMultiSet` = true;
  - **MS-repeat:** the same as MS, over the first 320 cycles.
- **Match rule:** Test B exactly as implemented (`replay81/Program.cs`), in-process (HK-037).
- **U′:** the tone-presence instrument `cf_fbid.py` @ `ecc4c5e7` with its null and T as frozen, applied as in COH-FALLBACK §14 A14.3. Untestable counts as not shown present.

### 6.3 Estimands and bars

- **NET** = 100 × Σ(`M_ms,i` − `M_ref,i`) / Σ`W_i`, in pp of WSJT-X's decodes. `M` is the union of all batches, matched as one set.
- **ΔU′** = the mean over cycles of (U′_ms − U′_ref), paired.
- **Statistics for both:** a 95 % block bootstrap, blocks of 40 consecutive cycles, a ratio estimator for NET, B 10,000, seed 20261025.
- **The bars are set after the REF arm and before any MS decode.** They are frozen and never moved once MS data exists. QA runs REF and then writes a dated note giving:
  - U′0, the REF arm's U′ per cycle;
  - the projected half-widths of NET and ΔU′ at this cycle count (A11.2 form);
  - the two lines in §6.5.

  The Captain then sets:

| row | predicate | my proposal | where it comes from (HK-038) |
|---|---|---|---|
| **D-GO / D-STOP / D-OPEN** | `CI_lo(NET)` ≥ D_bar / `CI_hi(NET)` < D_bar / otherwise | **D_bar = 0.5 pp** | BAR_L, ratified by the Captain 2026-10-24 12:50:57Z as "the size of gain that justifies a Developer build" of exactly this change. Default ON asks the same question in production |
| **U′-OK / U′-FAIL / U′-OPEN** | `CI_hi(ΔU′)` ≤ U′_bar / `CI_lo(ΔU′)` > U′_bar / otherwise | **U′_bar = 0.021 per cycle** | half the 0.042 the Captain set for the **whole** fallback (A18.6, before ON data). The sets are an increment on the fallback, so they get at most half its false-output allowance. For scale: the whole fallback measured +0.0198 for +3.82 pp (§19), and the arm's f_X was no worse than C3's. A decision value |

**What the proposed bars can resolve (HK-038 / HK-025(k): counted from step 4 on file, `20260922_2056`, 961 cycles; QA's REF note replaces these with this night's figures):**
- **ΔU′.** Step 4's half-width was about 0.0073 at ΔU′ 0.0198 ([0.0125, 0.0271]). At 0.021:
  - OK needs ΔU′ ≤ about 0.014;
  - FAIL needs ΔU′ ≥ about 0.028;
  - 2 × 0.0073 = 0.015 ≤ 0.021, so OK is reachable for a set as clean per decode as the whole fallback (≈ 0.0052 per pp of NET × 1.5 pp ≈ 0.008).
- **NET.** Step 4's half-width was about 0.39 pp at +3.82. A smaller increment has a narrower one, about 0.2–0.3 pp, which is my estimate, not a count.
  - A true +1.0 pp would read D-GO.
  - A true +0.5 pp would read OPEN.
  - D-STOP needs NET below about 0.25.

### 6.4 Validity (any FAIL ⇒ no verdict)

| row | predicate |
|---|---|
| V1 | DLL pin equal at the start and end of REF, MS and MS-repeat |
| V2 | both flags read back in every run; `selection.json` SHA identical in every run |
| V3 | 0 access violations, 0 contained exceptions, 0 non-zero exits |
| V4 | batches 1, 2 and 3 identical MS vs REF, N/N, except cycles explained by abandonment in one arm (A3″(a)) |
| **V5** | cycles with any abandoned work ≤ 5 % in MS (step-4 V5) |
| V6 | MS-repeat: the per-cycle union multiset identical to MS, except cycles explained by abandonment in exactly one run (≤ 16 of 320); **unexplained = 0** |
| **V7 (new): V3 untouched** | per cycle, every batch-4 decode REF published from V3 (provenance 0) is also published by MS from V3, and MS has no V3-provenance decode that REF lacks; exceptions only for abandonment. **N/N** |

### 6.5 The two lines in QA's REF note (mechanical, answered before the Captain sets the bars)

- "With these half-widths, D_bar = 0.5 can / cannot resolve a true NET of 1.0 pp (CI_lo ≥ 0.5)."
- "U′_bar = 0.021 is / is not ≥ 2 × the projected ΔU′ half-width." If it is not, OK is unreachable for a fallback as clean as the shipped one. That is said **before** the bar is set.

### 6.6 HK-025(k), both ways

- **Sets that publish nothing:** NET ≈ 0 ⇒ D-STOP, and ΔU′ ≈ 0 ⇒ U′-OK. So D-GO is the row that can fail.
- **Sets that publish junk:** ΔU′ is large ⇒ U′-FAIL. Default ON needs both D-GO and U′-OK.

### 6.7 Descriptive, mandatory

- NET and ΔU′ by Test B SNR band (A–D).
- Set decodes per cycle by provenance, with their confirmed share.
- The R10 counters.
- **Cost:** fallback wall time per cycle (median, p95, max), MS against REF, and the batch-4 publish time from decode start (median, p95), MS against REF.
- The FP-watch on U′ by provenance, against REF's V3 rate.
- MS-repeat timing beside MS − REF.

## 7. Limits, stated in the report

- **Scope:** one night, one band, a replay rather than live operation.
- **U′** is an upper bound on false decodes: hashed texts are untestable and are counted against the sets.
- **The sets' order** was fixed on the arm's data, never tuned. Dropping C1, which had 1 unique row, is a possible later saving. It would change the walk, so it would need its own replay.
- **Cost:** a slower CPU (the `sol` class) is not measured here. If the MS wall p95 is more than double REF's, I raise it with the Captain before default ON.

## 8. Predictions (blind; scored at the rulings)

| # | prediction | P | class |
|---|---|---:|:---:|
| MB1 | B1 passes on the first Stage 1 build, all four sets and the walk | 0.65 | C |
| MB2 | V7 passes (V3 untouched) | 0.85 | C |
| MB3 | D-GO at D_bar = 0.5 pp (if the Captain sets 0.5) | 0.55 | H |
| MB4 | U′-OK at U′_bar = 0.021 (if the Captain sets 0.021) | 0.55 | H |
| MB5 | NET point in [0.5, 2.0] pp | 0.60 | H |
| MB6 | MS fallback wall median ≤ 2 × REF's on the PC | 0.70 | C |

⚠️ **Calibration note:** at the arm I was under-confident (X1/X2). MB3 and MB5 lean on the 0.73 positions → production ratio from one earlier change, and the F1b gate on set outputs is new. So they stay near even.

## 9. For QA, in order

1. (k) review of this spec: FILE:LINE against `main` `5a9667ee`, and the corpus inventory (§6.1).
2. The OpenSpec change, `tasks.md` and the Developer handoff (HK-015/HK-000), with the shim number confirmed.
3. After Stage 1: B1, then my ruling. After Stage 2: B2, B3 and A1, then the HK-039 review record.
4. The REF arm, then the REF note (§6.3, §6.5), then the Captain's bars, then MS and MS-repeat, then analysis by committed code and the report in COH-FALLBACK §19's format.

*Architect. Docs only; `src/`/`native/` diff empty.*

---

## §10 Amendment 1: QA's (k) review adopted, M1–M4 (Architect, 2026-10-24 14:59:24Z by `date -u`; before any code or decode)

QA's review: ACCEPT WITH 4 AMENDMENTS. Every FILE:LINE in R2, R4, R8 and §1 is confirmed against `5a9667ee`. All four amendments are adopted.

- **Shim number: `20260071`.**
  - `origin/main` is at `20260069`. `origin/decoding_improvement` already holds `20260070` (DI sync 7), and I checked this with `git grep`.
  - Taking `20260070` on `main` would collide at the next DI sync.
  - The handoff includes the Linux/macOS binary refresh step (as PR #254). G8/CI fails on a stale binary otherwise.
- **Handoff facts adopted:**
  - **R6:** provenance may use `FT8CohFallbackOut`'s `int32_t reserved` (`ft8_shim.h:1599`) **with no layout change**. This is preferred over a new field.
  - **R7:** the multi-set bit may use `ft8_coherent_fallback_run`'s reserved `flags` (`:1609`); `_process` gets the same as a parameter or flag. The test harness passes it through for B3; QA lists that as a test-support change.
  - REF has the fallback ON, as shipped (`DecoderConfig.cs:240`).
- **M1, R2 gets a row (added to B2/A1).** A native test on a fixed cycle checks:
  - the R10 "entered the walk" count equals that call's number of NO_CRC candidates;
  - a V3-CRC-valid candidate (known, new or gated out) and a not-attempted candidate show 0 walk entries;
  - their outputs equal flag OFF.

  B1 cannot see this half, because its rows are V3-fail by construction.
- **M2, B1's positive class (HK-021(k)).** Added to B1, keeping the ≥ 99.5 % overall rows:
  - **For each set, and for the walk:** among rows where the Python output is CRC-valid, the native output is CRC-valid with the same payload on **≥ 99 %**. For J3 that means at most 4 of 401.
  - **On the union of rows where either side has an output:** agreement **≥ 99 %**.

  The overall rate alone hides a port bug in the large both-empty class: 569 of 7,498 rows have any output.
- **M3, the corpus: `20260925_2010`, whole night (2,882 cycles), no sampling.**
  - It is 40 m, with full-cycle WAVs and a WSJT-X `ALL.TXT` (76,999 Rx lines). It was never used for a coherent decision (it was a sub-feas/DI replay night).
  - Projection: about 5.4 h for REF + MS + MS-repeat (320 cycles), under 8 h.
  - The Voicemeeter preference **cannot be met**: the only Voicemeeter nights are excluded. This is stated as a limit (§7). Audio from before the OSD fix is fine, because the replay decodes it with today's build, and Test B and U′ read WSJT-X's `ALL.TXT`, not OWS's.
  - **QA states which WAV folder the replay uses** (`owsfz/wav` or `wsjt-x/wav`) and how the 2026-10-17..19 OWS-recorded-WAV disposition applies, before `selection.json` is frozen.
  - **This is within §6.1, so the Captain does not need to choose.** The alternative `20260923_1730` would need k = 3.
- **M4:** `cf_fbid.py` @ `ecc4c5e7` is on `qa/refset`, not `main`. The report states that the U′ step is reproducible from `qa/refset`, not from `main` alone. The spec is unchanged.
- **Clarification (a):** R3 stands. A KNOWN set payload ends the walk. f_X's upper-bound nature is already in §7 / the arm's §10.

**Next:** QA writes the OpenSpec change `coh-multiset-build`, `tasks.md` (B1 with M2, B2 with M1, B3, A1) and the Developer handoff with shim `20260071`. Developer work may start from that handoff.

**A1.1 (15:03:01Z by `date -u`): how the bit reaches `_process`.**
- **QA's finding.** `ft8_coherent_fallback_process` has no flags argument (`ft8_shim.c:2634–2636`), and `_ctx_new` takes none (`ft8_shim.h:1638`). My "the same bit given to `_process`" assumed a parameter that does not exist (ledger E59).
- **QA's route in the handoff:** an added setter on the per-thread scratch context, with the existing signatures unchanged and the FILE:LINE recorded. This is accepted. A context is not a process-global (R7, R8).
- **Added requirement: the context is long-lived.** `CohFallbackLibBackend` holds `_ctx` as a field (`CohFallbackLibBackend.cs:22`), so a context outlives a cycle while the flag can change at run time.
  - The managed side **sets the bit on every context before each cycle's `_process` calls**, from the once-per-cycle flag read (R7).
  - The native default for a new context is **off**.
  - **Test:** one context, two consecutive cycles with the flag ON then OFF (and OFF then ON). Each cycle's outputs equal a fresh context with that cycle's flag.

## §11 RULING: Stage 1, B1 PASS. Stage 2 may start (Architect, 2026-10-24 15:28:25Z by `date -u`)

- **Build.** Developer `f5bf099a` on `feat/coh-multiset-build` (local): 16 files, +736/−3, shim `20260071`. The committed win-x64 `libft8.dll` is SHA-256 `15e8e436…e91ac40e`.
- **HK-039.** QA's record `3bc176cf` (`Reviewed-commit: f5bf099a…`, APPROVED, no required changes) is an ancestor of the B1 result `a4a7bf58`; I checked this with `git merge-base --is-ancestor`.
  - Clean detached tree at `f5bf099a`: the 5 new tests pass, and `Ft8.Tests` passes 585 / 0.
- **B1** (`b1_stage1_f5bf099a.json`, read by me): the native R9 export against `ms_metrics.py` @ `96aa80d4` on the 7,498 consulted rows, with 0 faults.

| item | overall | positive class (Python CRC-valid) | union (either side has an output) | max \|Δraw\| |
|---|---:|---:|---:|---:|
| C1 | 7,498 / 7,498 | 14 / 14 | 14 / 14 | 2.1e-8 |
| J2 | 7,498 / 7,498 | 274 / 274 | 274 / 274 | 6.1e-10 |
| J3 | 7,498 / 7,498 | 408 / 408 | 408 / 408 | 6.6e-10 |
| N1 | 7,498 / 7,498 | 186 / 186 | 186 / 186 | — |
| walk | 7,498 / 7,498 | 569 / 569 (= the arm's 554 + 15) | 569 / 569 | — |
| V3 | 7,498 / 7,498 | — | — | 3.2e-7 (float vs double) |

  - The estimate is equal on 7,498 / 7,498.
  - Every threshold is met with no disagreement at all: 99.5 % overall, 99 % on the positive class, 99 % on the union, 99.5 % for V3.
- **Verdict: B1 PASS. Stage 2 (R2–R8, R10, R11, A1.1) may start.** B2, B3 and A1, with M1 and the A1.1 stale-flag test, are judged on the Stage 2 build.
- **Limits, carried:**
  - No native mutation was rebuilt (QA's note N2); B2's identity-map test is the mutation check.
  - The binary is identified by its SHA, not byte-reproduced.
  - The Linux/macOS binaries are not refreshed yet (that comes before any push; G8/CI).
- **MB1** (B1 passes on the first Stage 1 build, 0.65 C): ✅ **HIT**.

## §12 Amendment 2: the walk order gets a product row; where the replay may run (Architect, 2026-10-24 15:54:19Z by `date -u`; before any Stage 2 acceptance row or replay decode)

**A2.1 QA's R-1 is adopted as a required row (B4).**
- **The gap.** QA reviewed Stage 2 (`ea2c1d14`, record `710b9052`). With the product loop's set order reversed in a scratch rebuild (DLL `482bb594`), all 99 `Coherent*` tests still passed. QA's real-audio cross-check caught the reversal on 225 of 225 multi-valid rows.
  - The R3 order had no product-path row. B1 covers only the Stage 1 export's own walk, and B3 compares `_run` with `_process`, which share the loop. That is my spec's gap: ledger E60, the same class as E58.
- **B4, the walk order.** A fixture with **≥ 2 CRC-valid sets** on a candidate. It asserts that the product path's provenance equals the **lowest-numbered** valid set, with `CohFallbackSetsAt` as the oracle, through both `_run` and `_process`. The reversed-loop mutation must fail it; QA confirms that at re-review.
- **Also recorded:** QA's real-audio cross-check on 150 cycles of the arm's night.
  - P1: provenance and payload equal to the export on all 20,980 attempted rows.
  - P2: the order is correct on all 852 multi-valid rows.
  - P3: with the flag OFF, the 4,882 V3-valid rows are unchanged.
  - P4: walk entries 16,098 = NO_CRC rows (M1).
  - The A1.1 runner mutation was killed (8 of 99 tests).
  - The full unfiltered solution passes, 0 failed.
  - These are QA's checks, not spec rows. B4 goes into the test suite because the suite is what guards later changes.
- **Noted, descriptive:** at the product's own candidates, **C1 wins 743 of 1,316 set wins**, against 11 of 554 at WSJT-X's positions in the arm. Many may be KNOWN duplicates, which end the walk without publishing (R3).
  - §6.7's per-provenance figures must therefore split each set's wins into **published / KNOWN / gated out**.
  - If C1 mostly produces KNOWN payloads, it is spending the walk's first try on payloads that are already decoded. That is a design question for after the replay. Nothing changes now, and the order stays frozen.
- **Build reproducibility (noted):** QA's clean rebuild (`228fb5ef`) and the Developer's (`1ba8dc3d`) differ in bytes but not in behaviour on P1–P4. The build of record is the committed DLL, pinned by SHA (V1).

**A2.2 Where the replay may run: the PC (recommended) or `sol`, the Captain's choice.**
- **The trade-off.** On the PC, the replay needs WSJT-X closed for about 5.4 h, because of CPU contention: work past the deadline is abandoned, which changes outcomes. On `sol`, WSJT-X can stay open.
- **Data on file (`74017b63`, step 4, `20260922_2056`, 961 cycles), `sol` against the PC:**
  - outcomes identical 961/961 in both arms; 0 abandoned on either machine;
  - but sol is about 2.5× slower: elapsed median 8.2 s vs 3.3 s; fallback wall median 485 ms vs 215 ms, max 1,041 ms;
  - **sol's minimum margin to the 13 s budget was 1,360 ms**, against 8.1 s on the PC.
- **Why the margin matters here.** MB6 expects the sets to cost up to about 2× the fallback's wall time. On sol's worst cycles that could exceed the 1.36 s margin, so the MS arm could abandon work that REF does not.
  - Work abandoned only in MS lowers both its gain and its false outputs. **That biases ΔU′ toward OK**, the direction that matters.
  - On the PC the margin makes this negligible.
- **Rule if the replay runs on `sol`:**
  - **Binary.** The Linux `.so` is built on sol from the exact reviewed commit and its SHA is pinned (V1). B1 is re-run on that `.so` (the 7,498 rows) before any arm.
  - **Abandonment.** V5 tightens to **≤ 1 % of cycles with any abandoned work in MS, and in REF**. Its source is sol's own 0/961 on step 4 (HK-038).
  - **If V5 fails on sol,** the verdict comes from a PC run. The sol run stays descriptive, as the cost line on the slower machine.
  - MB6 is scored on whichever machine runs MS.
  - The unit and characterisation tests (B2, B3, B4, A1) stay on the PC in either case, because the PC holds the build of record.
- **My recommendation: the PC, overnight, with WSJT-X closed.**
  - It is the build of record, it carries no abandonment bias, and the night costs no operating time.
  - Optionally, afterwards, one MS arm on sol as a **descriptive** cost check on the slower machine, which §7 lists as unmeasured.

**Next:** the Developer's B4 commit, then QA's re-review, then B2, B3, B4 and A1, then my ruling, then the REF arm on the machine the Captain picks.
