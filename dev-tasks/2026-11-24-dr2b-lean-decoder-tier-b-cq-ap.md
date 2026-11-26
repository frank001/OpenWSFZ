# Developer task: DR-2 step 2b, the lean engine's tier B (coherent) and CQ-AP, inside `ftz_decode_cycle`

**Date:** 2026-11-24
**Prepared by:** QA
**Audience:** Developer (to execute)
**Authorised by:** `docs/decoder-rebuild/spec-dr2-lean-decoder.md` §2.3 (S2 steps 3 and 4) and §3 step 2b, on `arch/decoder-rebuild` (read with `git show arch/decoder-rebuild:docs/decoder-rebuild/<file>`); the Captain approved the plan on 2026-11-24.
**Status:** Proposed. HK-011: `src/` and `native/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). Do not push, open a PR or merge; QA pushes.
**Branch:** `feat/lean-2b`, a child of `feat/lean-2a` once step 2a's CI is green (QA tells you); until then branch from `19d8f9fb`.
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay, no on-air period, no extra nights, no statistical gate. Run tests per project (HK-022) and read the per-assembly "Passed: N" lines. Run the golden and lean tests once with `DOTNET_PROCESSOR_COUNT=4` as well: step 2a's golden failed CI because it depended on the host's processor count.

---

## 0. Why

Step 2a decodes what the classic **primary pass** decodes. The classic decoder's coherent fallback adds +5.2 pp of WSJT-X-confirmed decodes on the same audio (DR-0, Slice 40, A2 to A3, `qa/decoder-rebuild/dr0-result.md`), and CQ-AP is on in every arm, so the lean engine needs both before it can be compared with the baseline. This step adds them to round 0 (the original audio). The residual rounds are step 2c.

## 1. What to build

| Id | What |
|---|---|
| **D1 Order** | In S2, per cycle, on the candidate list of step 2a: **tier A** for every candidate (unchanged), then **tier B** for every candidate that failed tier A **and is eligible** (§3 below), then **CQ-AP** for every candidate that failed both. Tier B and CQ-AP run on the worker pool (a candidate is one item); the **sort by (frequency, time, payload) before anything touches the callsign table stays**, now over the union of the three tiers' hits, so the output is independent of the thread count. |
| **D2 Tier B** | Fine sync, then the coherent LLRs (multi-set on, as today: the first set plus four further sets), BP, CRC, unpack, using the building blocks of spec §2.2 (`ft8_refine_candidate` / `cf_estimate`, `cf_v3_llrs`, `cf_multiset_llrs*`, in `coherent_fallback.c` and `coherent_llr.c`). Reuse the per-candidate function the classic fallback already runs (`cf_process_one`, `ft8_shim.c:2399`) rather than rewriting it; the lean call lives in the same translation unit. A candidate's tier-B row is **published** iff it is CRC-valid, its payload is **new** (not in this cycle's payload set so far), and its **F1b is at most T1 = 17.552446 dB** (`coherent_fallback.h:39`). F1b is computed only for a CRC-valid new payload (output-first, as today's default order). Rows with the same payload at several lattice positions: keep the first, in the sorted order, whose estimate is not at the window edge (the classic `CoherentFallbackSelector.Select` rule). **The residual-run ungating (R-F4) does not apply in round 0**: it concerns residual audio, step 2c. |
| **D3 CQ-AP** | Exactly as today (FR-103, `ft8_shim.c:2018-2025`, `ftx_decode_candidate_cq_ap`, BP only, the same force pattern). It runs only when `decoder.cqAp` is on (today's setting, **default on**; the lean engine keeps reading it). Count attempts and decodes as the classic path does. |
| **D4 Context pool** | The coherent context (`cf_ctx_t`) is not thread-safe: **one per worker**, created once with the pool, freed in `ftz_shutdown`. No per-candidate allocation. |
| **D5 Bounds and safety** | Everything of step 2a stands: every index bounded by a size the call computed, checked allocations, an access violation caught (MSVC) and returned as `FTZ_ERR_FAULT`, no per-cycle thread creation. The cycle's wall-clock budget (13 s less the publish reserve) is passed to the native call and checked between candidates: a tier-B run past it stops, flags `abandoned`, and the results found so far are returned. |
| **D6 Log line** | The per-cycle `lean:` line gains aggregates only: tier-B eligible, attempted, CRC-valid, F1b computed, gated (passed), published, edge; CQ-AP attempts and decodes; per-tier wall and CPU ms. No message text (HK-037). |
| **D7 C# side** | `DecodeLeanAsync` hands the budget in and logs the new fields. No new setting: tier B has no switch in this step (`effort` arrives in 2d). |
| **D8 Documents** | `REQUIREMENTS.md`: extend FR-108 or add the next free FR number (FR-106 and FR-107 are held by the stopped LR-BUILD branch); the OpenSpec change `lean-decoder` (tasks and delta spec) updated and validated `--strict`. **VERSION:** none, the engine stays internal and default `classic`; run `check_version_bump.py` (G9b) after committing. |

## 2. Tests (unit tests only)

1. **Tier-B equality.** Find or build a fixture where the classic coherent fallback publishes at least one row on the **original** audio (the existing `CoherentFallback*` tests and fixtures are the place to look; say which you used). The lean engine, with CQ-AP off, must publish the same set of payloads for that audio as the classic fallback's first run publishes after the primary pass. Compare payload sets, never rendered text across processes.
2. **Tier-B gate.** A CRC-valid new payload with F1b above T1 is **not** published; a payload already decoded by tier A is not published again; the same payload at two lattice positions is published once, from the first non-edge row.
3. **CQ-AP.** On a fixture where the classic path decodes a message only through CQ-AP (the CQ-AP tests have one), the lean engine decodes it with `cqAp` on and not with it off; attempts and decodes counted as classic counts them.
4. **Order and determinism.** The same audio and starting hash state, run twice and at `threads` = 1, 2 and 4: byte-identical output, mechanically diffed. A candidate decoded by tier A is never attempted by tier B or CQ-AP.
5. **Budget.** A budget of zero or a few ms returns early with `abandoned` set and no crash; the results returned are a prefix of the full run's.
6. **Memory safety.** The ASan + UBSan fuzz harness (`native/ftz_decoder/tests/ftz_fuzz.c`) extended so the 10,000-run fuzz and the determinism run include tiers B and CQ-AP, on random, clipped, silent, DC and truncated audio. The CI `native-asan` job runs it.
7. **Step 2a unchanged.** The step-2a tests and the classic golden stay green, with `DOTNET_PROCESSOR_COUNT` at 4 and at the host's own value; the existing suites per project.

## 3. The rule for "eligible" (read from the code by QA, `main` `452af459`)

Today's coherent fallback takes a candidate from the cycle's snapshot when it is **not already decoded** (`decoded` false; a CQ-AP decode counts as decoded) **and** not a duplicate position (an earlier candidate in the same snapshot with the same `freq_hz` and the same `dt`). Source: `ft8_shim.c:2845-2878` (`ft8_coherent_fallback_plan`) and the same test in `ft8_coherent_fallback_run`. It is not limited by score beyond the candidate list's own `min_score`.

**One deliberate difference from classic, from the spec's order:** classic runs CQ-AP before it marks a candidate eligible, so a candidate that CQ-AP decodes is never tried by the fallback. The lean order is tier A, tier B, CQ-AP (spec S2 steps 2, 3, 4), so a candidate the fallback would have lost to CQ-AP may now be decoded by tier B first. The payload is the same if both succeed; say in the task result if you see a case where it differs.

## 4. Out of scope

The residual rounds and the patch search (2c), the F1b ungating for residual rows (2c), XC wiring and the three batches (2d), `effort` (2d), OSD (off in the lean engine), any new gate, any threshold re-tuning, any closed arm.

## 5. Report back

The commit SHA; the per-project "Passed: N" lines; the fixture(s) used for tests 1 and 3; the result of the `DOTNET_PROCESSOR_COUNT=4` run; whether you saw any candidate where the lean order changed the outcome (section 3).
