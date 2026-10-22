# Developer task: optional third decode pass ("Deep"), flag-gated, default off (#240, step 1)

**To:** Developer (or the Captain, if he codes it himself). **From:** QA. **Date:** 2026-10-18. **HK-000 handoff.**
**Spec (the Architect's, with QA's (k) review folded in):** `qa/rr-study/2026-10-18-1205-architect-to-qa-spec-third-pass-yield.md` on `arch/third-pass`, §1 and §2, plus its **Amendment 1** at the end (it overrides §3–§5). Read both before starting. **Captain's word (2026-10-18): "spec it"; earlier: "I'm planning to implement the 3rd pass anyhow".** This task builds it behind a flag; it does NOT decide whether it ever ships ON.
**HK-011:** this touches `src/`; Developer work, the Captain reviews the diff. **Not user-facing in step 1** (no UI, default off, so no `VERSION` bump unless `tools/check_version_bump.py` demands one; commit first, it reads from git).

## Branch and base
New branch `feat/third-pass-deep` off `origin/main` (currently `f52f8c4b`: B2, shim 20260062; re-check `git fetch` first). Not off `decoding_improvement`: QA's identity row V1 compares `Normal` with `main`. **Commit locally; do not push, do not open a PR, do not merge** (only QA pushes; merge is the Captain's, HK-010). The branch is NOT merged until QA has read the measurement.

## 1. What to build (spec §1: the definition)
"Deep" is **one more subtract-and-decode round, incremental, with the same thresholds**:
1. Run only when the residual pass **returned ≥ 1 new decode and was not abandoned**. Otherwise skip, and record the reason: `skipped-no-new` or `skipped-abandoned`.
2. Start from the **residual buffer the residual pass already produced** (pass-0 signals already subtracted). Fit and subtract **only the residual pass's new signals** from it. **Do not refit pass-0 signals.**
3. Decode that buffer with the **same decoder settings** as the residual decode (thresholds, nhard/OSD, AP constraints).
4. Return only decodes that are new against pass 0 AND the residual pass (same payload dedup, RR73-aware).
🛑 **Out of scope:** a lower sync threshold, more OSD, AP, extra candidates. If the incremental form (step 2) proves infeasible, **STOP AND REPORT**; do not build a "refit everything" variant (a different cost model that needs a spec amendment).

Where things are now (read on `c4867dae`; line numbers may have moved): `src/OpenWSFZ.Ft8/Subfeas/SubtractionPass.cs` (`RunAsync`, `RunCore`; the pass logs `Sub-feas residual pass: residualDecodes=… elapsedMs=… deadlineAbandoned=… containedException=… fittedSignals=…`); the call site is `Ft8Decoder.cs` around the two-stage branch (`onFirstBatch` publishes batch 1, the return value is batch 2); the 13 s cycle budget is `SubtractionCycleBudget` (`Ft8Decoder.cs:108`) and the fits' reserve is `SubtractionResidualDecodeReserve` (`SubtractionPass.cs:43`). Config keys follow the pattern of `SubtractionEnabled` / `SubtractionMaxThreads` (`OpenWSFZ.Abstractions/DecoderConfig.cs`, the config store, the status endpoint).

## 2. Requirements B1–B10 (spec §2, mechanical)
- **B1** Config `decoder.decodingDepth`, `"Normal"` / `"Deep"`, **default `"Normal"`**; config POST is an overlay (HK-035); the value the decoder is actually using is read back in `/api/v1/status` (or the decoder-params page).
- **B2** `Normal` is **inert**: output bit-for-bit today's.
- **B3** `Deep` is **additive only**: pass 0 and the residual pass untouched; the third pass only appends.
- **B4** It **shares the 13 s cycle budget** and its cancellation/reserve mechanism. **All-or-nothing:** an abandoned or failed third pass publishes nothing and keeps batches 1 and 2. Never time-gated or load-gated in any other way.
- **B5** Its decodes go out as **batch 3**, mapped exactly like batch 2. 🔴 **A hard dependency of QA's harness** (it scores batch 3 as its own kind).
- **B6** Counters in `/api/v1/status`, separate from the residual pass's: runs (started), skips by reason, abandons, failures, decodes.
- **B7** A **per-cycle log line** in the same shape as the residual pass's, aggregates only (HK-037: no message text): e.g. `Third pass: newDecodes=… elapsedMs=… outcome=<ran|skipped-no-new|skipped-abandoned|abandoned|failed>`. QA's parsers read it; tell QA the exact format.
- **B8** **Managed code only, no native change, preferred** (reuse the existing fit on the residual buffer). If a native change is unavoidable: stop and tell QA first; next free shim at work time (highest on any `origin/*` ref is 20260063 on `decoding_improvement`, so likely 20260064; re-check), HK-011, rebuild both binaries per `src/OpenWSFZ.Ft8/Native/BUILD.md`.
- **B9** Tests: `Normal` = today (golden); `Deep` additive; skip rules (both reasons); abandon and failure paths publish nothing.
- **B10** **No Settings-page UI in step 1.**

## 3. Hand-back (the Developer's report)
Branch and commit SHA(s); whether the build is managed-only (`git diff --stat origin/main..HEAD -- native/ src/OpenWSFZ.Ft8/Native/` empty, or the shim number and binary SHA-256s); the exact B7 log-line format and the B6 field names; the unfiltered test run on Windows (`dotnet test OpenWSFZ.slnx -c Release`, counts) and in WSL, filters quoted (HK-022); where batch 3 leaves the decoder (the callback or return shape), so QA can wire the harness.

## 4. Acceptance (QA checks; mechanical)
- The branch has the single parent `origin/main` (or the merge base stated); default config is `Normal`; with `Normal` QA's identity check against `main` `f52f8c4b` shows **0 differing cycles** and its OSD-sign-OFF control moves ≥ 1 cycle (spec V1).
- With `Deep`, pass-0 + residual decodes per cycle equal `Normal`'s (V2); two `Deep` runs agree on every cycle with no abandon (V3).
- The B6 counters and B7 line exist and read sensibly on a Deep-ON replay; batch 3 carries only decodes new against batches 1 and 2.
- `git diff --stat origin/main..HEAD -- native/` empty unless B8 was triggered and reported first.
- The test suite passes unfiltered on Windows and WSL; CI green on all legs when QA pushes.

## 5. After the hand-back (QA's part, not yours)
QA extends `Replay81` to carry batch 3 as its own kind and proves it on a fixture **before any Deep-ON data is read** (Amendment 1, A4); then V1/V2, then the measurement. No ship bar exists (HK-038); the Architect scores TP-1..3.

## 6. References
#240, #122; spec and Amendment 1 (above); QA's (k) review `qa/rr-study/2026-10-18-1204-qa-to-architect-k-review-third-pass-spec.md`; HK-000, HK-010, HK-011, HK-022, HK-035, HK-037.
