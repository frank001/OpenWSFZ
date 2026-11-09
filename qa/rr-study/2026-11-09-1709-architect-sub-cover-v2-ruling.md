# `SUB-COVER v2` (#273) ruling: **BETWEEN**; recommendation: **close #273** (the build would be below what an arm resolves)

**From:** Architect · **To:** QA, the Captain · **Date:** 2026-11-09 17:08:59Z (`date -u`) · **Branch:** `arch/sub-coverage`
**On:** QA's report `qa/rr-study/2026-11-09-1710-qa-sub-cover-v2-report.md` (`fe299859`, `qa/same-chain`, local); freeze `8daa36fe` (code `4e7e7297`), made before any O★v2 output; spec `f68f4ce9` + Amendment 1 `50149101`. Docs only: `git diff --stat origin/main -- src/ native/` is empty.

## §1. Rows and outcome, adopted as reported

| row | result |
|---|---|
| O-REPRO, O-BUILD | PASS (unchanged from v1) |
| O-V1 | PASS, 400/400 bit-identical to O★v1 |
| O-CTRL | PASS (batch 1 CI_hi +0.152; batch 2 CI_hi +1.434; bar +2.0) |
| O-ORC (A1.1) | PASS: 11 of 211 route-2 decodes still decode, 5.21 % [2.45, 8.30], CI_lo < 5.44 % |
| O-ENC | report-only: 4.62 % (≥) |

Freeze facts (`8daa36fe`): `c` −0.640 s, `τ_f` 2.0 Hz, `τ_t` 0.080 s, from N 9,931 text-equal pairs. Both are inside the one-tone and one-symbol stop limits. **True ceiling 77 of 112 rows = 0.635 pp**, so BUILD-WORTH could fire.

**Decision number: Δ273p = +0.297 pp [0.199, 0.407]** (36 of the 112 rows; 47 % of the true ceiling).
- CI_lo 0.199 < 0.40 and CI_hi 0.407 ≥ 0.25, so **BETWEEN** by the registered rule. It goes to the Captain.
- Beside it: G★v2 +1.980 pp [1.735, 2.260]; G273v2 +0.932 pp [0.764, 1.124].

## §2. What this says, and what it does not

- **#273-proper is now tested, and it is real but small.** Removing hashed and short neighbours with their transmitted payload makes 36 of the 112 associated rows decodable at WSJT-X's positions. v1's "untested" (E140) is closed.
- **Δ273p reads slightly low, not high.** O-ORC's point is 5.21 %, above the 3.44 % R3 baseline, so some route-2 subtractions are incomplete. Whether that is a wrong hash or an ordinary partial fit, an incomplete subtraction can only hide gain. The bound is a lower bound in that respect, and its CI_hi is 0.407.
- **It is still an oracle bound, not a build forecast** (v1 §3): perfect payloads, forced legs at WSJT-X's position, no time budget.
  - At COH-RES-CAND's capture ratio, 0.405 (the one figure on file; PC, `20260930_1930`; a different night and lever, **indicative only**), a build lands near **0.12 pp** (0.297 × 0.405); even at CI_hi, near 0.16 pp.
  - COH-RES-CAND's 400-cycle NET had a half-width ≈ 0.2 pp. **One arm cannot tell a 0.12 pp build from zero**; acceptance would need about four times the cycles (half-width scales as 1/√n), i.e. several nights.
- **Attribution is not separated.** Of the 53 G★ rows new against v1, route 1 without the pre-filter (+121 decodes placed, no `native/` change needed) and route 2 (211 placed, needs the decoder's own 77 bits, a `native/` change) both contribute. This run does not split them. Splitting would cost one more O★ build with route 2 off (≈ 15 min machine), and the most it could show is a share of a ≤ 0.41 pp bound.

## §3. Recommendation to the Captain

| option | what it costs | what it can deliver |
|---|---|---|
| **1. Close #273** (recommended) | nothing | the issue closes with v1 + v2 on record: oracle Δ273p +0.30 pp, built ≈ 0.12 pp (indicative) |
| 2. Build it | `native/` change to expose the 77 payload bits (Developer session, HK-011) + `src/` subtraction of hashed/short decodes + HK-039 review + an acceptance arm of several nights | ≈ 0.12 pp, plausibly 0.05–0.2 pp, with a several-night acceptance for a gain the size of its own noise |
| 3. Attribution run first, then perhaps a `src/`-only build (drop the `IsReencodable` pre-filter only) | ≈ 15 min machine + QA's write-up; a build is then `src/` only but still needs the same long acceptance | a share of the same ≤ 0.41 pp bound |

**Why 1:** the gain is real, but at about a tenth of a point it is smaller than one arm can see, and the R-F4 + L1′ default-ON (+1.47 and +0.77 pp alone) already moves the station far more. This is housekeeping-sized either way: it does not change the station unless he picks 2 or 3.

## §4. Predictions (spec §4; V2-1 revised pre-data in A1), scored

| # | prediction | P | outcome |
|---|---|---:|---|
| V2-1 | O-V1 and O-ORC (as amended) pass on the first run | 0.75 | ✅ HIT |
| V2-2 | route 2 places ≥ 50 % of the decodes route 1 rejects | 0.55 | ✅ HIT (50.7 %, 211 of 416) |
| V2-3 | CLOSE | 0.50 | ❌ MISS (BETWEEN) |
| V2-4 | BUILD-WORTH | 0.15 | ❌ MISS (correct side) |

**Brier 0.134 over 4.** V2-2 was a narrow hit (50.7 % against a 50 % line).
