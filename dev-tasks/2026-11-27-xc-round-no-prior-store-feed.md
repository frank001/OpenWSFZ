# Developer task: XC-ROUND without the prior-store feed (batch 4 is not stored as priors)

**Date:** 2026-11-27
**Prepared by:** QA, from the Architect's recommendation (2026-11-27: "keep XC-ROUND, WITHOUT the prior-store feed, with no second replay")
**Audience:** Developer (to execute)
**Authorised by:** the Captain, 2026-11-27 ("option 2 it is, the architect's recommendation").
**Status:** Proposed. HK-011: `src/` change for a separate Developer session. Hand back the commit; QA reviews it (HK-039). **Do not push, open a PR or merge**; QA pushes (once per sprint).
**Branch:** `feat/xc-round`, as **a new commit on top of `65bca805`** (so the reviewed SHA stays valid). Managed code and documents only: **no native change, no shim bump, `libft8.dll` unchanged** (SHA256 `fa0b96c1c8a220b363db80977c0f741b6b7898a89bce3b98fe56e51691442504`).
**Test requirement (the Captain's rule, 2026-11-24):** unit tests and QA's review. No replay by you or by QA (the Captain accepted the Architect's arithmetic: rate -0.06 / -0.09 / -0.19 pp and `ours_only` 0 / -0.15 / -0.29 pp from the measured run).

---

## 0. Why

QA's XC-ROUND replay (`qa/rr-study/results/2026-11-26-lc-base/xc-round-result.md`) found that batch 4 stored in the cross-cycle prior store feeds later cycles' cross-cycle stage: 4 / 21 / 44 extra batch-3 decodes ("chained rows"), of which only 4 of 4, 8 of 21 and 17 of 44 are matched. The stage's own rule is "no chaining": batch 3 is never stored (`Ft8Decoder.cs:1057`, `xcBatch` 0 = "never does: no chaining"). The Architect's spec section 2.2 said "stored like batch 2", which was a spec defect; the Captain chose to drop the feed.

## 1. The change

| Id | What |
|---|---|
| **N1** | In `DecodeLeanAsync`, map batch 4 with **`xcBatch: 0`** (today `xcBatch: LeanBatchRounds`, i.e. stored like batch 2). Nothing else about batch 4 changes: it is still published through the same mapping (text de-duplication across the cycle, plausibility, region, worked-before), delivered only when non-empty, after batch 3. |
| **N2** | Update every sentence that says batch 4 is stored as priors: the code comments and the XML doc of `DecodeLeanAsync` / the XC-ROUND block, `REQUIREMENTS.md` FR-108 (the sentence "stored as priors like batch 2" becomes "not stored in the prior store: no chaining, as batch 3") and its changelog row (add one; the last is 1.79), the OpenSpec change `lean-decoder` (tasks section 14 and the delta requirement), and the header comments of the new tests. |
| **N3** | **Tests:** flip the managed test that asserts the prior-store count after a batch 4 (`LeanEngineXcRoundManagedTests`, the "prior-store count" assertion in the case with a detection): a batch-4 decode must **not** be in the prior store (the store's count equals what batches 1 and 2 stored, unchanged by batch 4). Add or keep one assertion that a batch-4 decode does not become a template for the next cycle's stage (the next cycle's detections do not include it). Every other test passes **unchanged**; if a golden or another test changes, **do not edit it**: stop and report. |
| **N4** | Run `tools/check_version_bump.py`, `check_version_docs.py`, `openspec validate lean-decoder --strict`, and G3 as before. |

## 2. Out of scope

Anything native, the round's design, the cross-cycle stage, the shadow stage, any default.

## 3. Report back

The commit SHA; the per-project "Passed: N" lines (Config, Web, Daemon, Ft8 also at `DOTNET_PROCESSOR_COUNT=4`, and the JS runner); the changed test and what it now asserts; every place the "stored as priors" wording was changed.
