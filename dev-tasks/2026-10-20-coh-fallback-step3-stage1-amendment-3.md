# Developer task: COH-FALLBACK Stage 1, AMENDMENT 3 - F1b only on CRC-valid outputs (output-first order)

To: Developer. From: QA, on the Architect's ruling (spec section 10, Amendment 3, `b5347fe9` on `arch/coherent-limb2`; read it with `git show arch/coherent-limb2:qa/rr-study/2026-10-07-1330-architect-to-qa-spec-coh-fallback-step3-build.md`). Within the Captain's existing step-3 go; nothing for him to decide.
Base: your `feat/coh-fallback-stage1` `44f0df4e` (shim 20260066). Keep the shim number unless your convention requires a bump for the changed export; say which.

## Why (QA measured, smoke only)
On 2 of the 100 acceptance cycles, with the CPU shared, `ft8_coherent_fallback_cycle` took about 18 s per cycle against about 9 s of slack: F1b (24 reference surfaces per candidate, about 165 eligible candidates per cycle) was about 94 % of it; the estimate was 0.7 s and C3 + BP 0.35 s. The port itself agreed with the Python reference on all rows of 3 cycles (A2 smoke), so this is a cost problem, not a fidelity problem.

## The change (the Architect's R4' and R12')
A candidate publishes iff it has a CRC-valid output AND F1b <= T1 AND its text is new. These are independent per-candidate predicates, so the order may change without changing what is published:
1. **R4' (output-first, now the DEFAULT of `ft8_coherent_fallback_cycle`):** for every eligible candidate run the estimate, C3 and BP. Compute **F1b only for a candidate whose BP output is CRC-valid and whose payload the ordinary `ft8_decode_all` call has NOT already decoded** (and not already produced earlier by the fallback in this call). Gate = F1b <= T1 (`CF_T1_DB`, unchanged). A candidate without such an output never needs F1b.
2. **Harness-only gate-first mode** (new flag, e.g. `FT8_COH_FLAG_GATE_FIRST = 16`): the OLD order (F1b on every eligible candidate, then C3 + BP only where gated). It exists only so QA's row A2(e) can compare the two orders; document it as harness-only. Default flags = output-first.
3. **`ft8_coherent_fallback_at` and the F1b code are NOT to change** (arithmetic, shortcuts S1-S3, results). QA's A2(a)-(c) were smoke-tested on `44f0df4e` and carry over only if these functions are byte-identical in your diff; if you must touch them, say so and QA re-runs A2(a)-(c). A2(c) keeps computing F1b on all 4,949 gate rows through the per-row export, so keep a way (flags as today) to get F1b for any anchor.
4. **R12' counters** (replace the cycle stats' counts so they read as the spec's log line): `eligible`, `attempted` (C3 + BP run), `crcOk`, `f1bComputed`, `gated` (F1b computed and <= T1), `published` (CRC-valid, gated, payload new in this call), `abandoned` (0 in Stage 1: there is no deadline yet), `elapsedMs`; keep the per-stage milliseconds (estimate, F1b, C3 + BP) and the existing candidate/decoded/duplicate-position/edge counts. Appending fields to `FT8CohFallbackCycleStats` is fine (these structs exist only in this shim); give the new `sizeof`s, and update your managed smoke tests. `FT8CohFallbackRow` should say per row: whether F1b was computed, F1b, gated, and whether it would publish.
5. Same eligibility as before (R2), same dedup by payload, same BP only (no OSD), no product wiring, no change to any existing export or struct.

## Tests and hand-back
- Native self-test: output-first and gate-first publish the SAME payload multiset on synthetic cycles (several signals, some below and some above T1, noise-only candidates, a duplicate payload); `f1bComputed` <= `crcOk` + (0) in output-first; counters consistent (`gated` <= `f1bComputed` <= `crcOk` <= `attempted` <= `eligible`).
- Unfiltered `dotnet test OpenWSFZ.slnx` (state the command), ASan/UBSan run AFTER your last edit, Windows `libft8.dll` and Linux `libft8.so` SHA-256, `git diff --stat` against `44f0df4e`, and the confirmation that `ft8_coherent_fallback_at` and the F1b code are unchanged (or what changed).
- Do not publish timing conclusions: QA runs A0 on the reworked build (spec A1.3, the committed slack note stands).

## Acceptance (QA runs; mechanical)
- **A2(e) (new):** on A0's 100 cycles, with no deadline, the cycle export in gate-first mode and in output-first mode: the published payload multiset per cycle identical, N/N, else A2 FAILS.
- A2(a)-(c) carry over if the per-anchor code is unchanged; A2(d) and A0 run on the reworked build only.
- If A0 still fails after this, the next step (still no design amendment) is a shared per-cycle reference-peak grid for F1b (spec R1 allows it iff A2 passes); top-K or a budget split would be a Captain design amendment.
