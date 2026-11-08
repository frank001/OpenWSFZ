# `SUB-COVER` (#273) ruling: **BETWEEN**, read as a lower bound; #273-proper **untested** (my instrument error); recommendation: park #273

**From:** Architect · **To:** QA, the Captain · **Date:** 2026-11-08 19:50:44Z (`date -u`) · **Branch:** `arch/sub-coverage`
**On:** QA's report `qa/rr-study/2026-11-08-1950-qa-sub-cover-report.md` (`ef2fc84b`, `qa/same-chain`, local); freeze `074e8132` (code `aa8ceda5`), made before any O★ output; spec `4f3a477a` (§0–§7). Docs only: `git diff --stat origin/main -- src/ native/` is empty.

## §1. Rows and outcome, adopted as reported

| row | result |
|---|---|
| O-REPRO | PASS, exact |
| O-BUILD | PASS, bit-identical in 400/400 cycles |
| O-CTRL | PASS (batch-1 vs R2 +0.04 pp [0.00, 0.10]; batch-2 vs R3 +0.75 pp [0.29, 1.26]; bar +2.0) |
| O-ENC | **fires**: 7.78 % against 2.33 % (537 unencodable + 251 fit-zero of 10,133). **By §2, every figure is a lower bound.** |

**Readout:**
- O★ subtracts 9,596 signals against R2's 6,877 (×1.40).
- **G★ +1.542 pp [1.322, 1.762]**: 187 of 1,589 NR rows.
- **G273 +0.544 pp [0.422, 0.678]**: CI_lo < 1.0 and CI_hi ≥ 0.5, so **BETWEEN** by the registered rule. It goes to the Captain.

## §2. What the bound does and does not say

**#273-proper was not tested. That is my error (E140).**
- §1's "oracle text" route re-encodes a decode from the matched WSJT-X text. The match requires text equality, so that text is ours by construction: 455 of 455 matched non-re-encodable decodes are identical, and `oracle_text_used` = 0.
- So the 112 rows whose stronger neighbours are hashed or short decodes were never given a subtracted neighbour. **Their 0 of 112 is not evidence.**
- I should have seen it from the matching rule. QA's Q41 is the same miss on the review side.

**What G273 consists of is L1′'s mechanism, not a new one.**
- Beyond L1′'s own stratum (CU-d with a batch-3/4 neighbour, +0.998 pp), the gain is **CS +0.388 and CW +0.132 pp**. Those are rows next to signals we already subtract, which become decodable once the batch-3/4 signals are also gone. That is what L1′ does.
- So part of G273 is plausibly **already inside L1′'s accepted +0.77 pp** (its own night, `20260930_1930`). The increment a separate #273 build could add beyond L1′ is **smaller than +0.544 pp, by an amount this instrument cannot separate.**
- Indicative only (a different night): L1′'s realised NET is about 0.77 of its stratum's oracle here (+0.77 vs +0.998). So L1′ cashes its ceiling well.

## §3. Recommendation to the Captain

1. **Park #273** (recommended), recording on the issue:
   - G★ +1.54 pp;
   - G273 ≥ +0.54 pp, mostly the L1′ mechanism;
   - #273-proper (re-encoding hashed/short decodes from payload bits, at most 112 rows = 0.92 pp of n_ref) untested.

   **Why not test it now:** a v2 builder from payload bits costs QA a few hours plus about 20 min of machine time. At #272's capture ratio (0.405, indicative) the best case is about 0.37 pp built. That is less than what is already accepted and waiting.
2. **The larger, cheaper gain is already built and switched OFF:**
   - **R-F4**: NET +1.470 pp [1.296, 1.638] on its second night;
   - **L1′**: NET +0.772 pp [0.655, 0.889] on its third night;
   - each measured alone; **together they are unmeasured**, and they need not add up.

   The one recorded blocker for an ON run (the three double-counting parsers) is gone (#276 merged). The `frans` chain is a new live era anyway (§7 of COH-RES-CAND), so turning them ON now costs no comparability.
3. **If he wants the defaults decided on live data:** one ON live run on the station under `frans` with R-F4 and L1′ both ON, read against WSJT-X on the same feed. That is the radio and antenna, his part. I would write that as a short run spec, not an arm.

## §4. Predictions (spec §5 / §6 A1.8), scored

| # | prediction | P | outcome |
|---|---|---:|---|
| SC-1 | O-REPRO, O-BUILD and O-CTRL pass on the first run (revised pre-data) | 0.60 | ✅ HIT |
| SC-2 | G★ point ≥ 1.0 pp | 0.50 | ✅ HIT (1.542) |
| SC-3 | CLOSE | 0.40 | ❌ MISS (BETWEEN) |
| SC-4 | BUILD-WORTH | 0.25 | ❌ MISS (correct side) |

**Brier 0.158 over 4.**
