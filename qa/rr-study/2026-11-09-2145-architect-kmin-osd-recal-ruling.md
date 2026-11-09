# `KMIN-OSD-RECAL` ruling: **KEEP-5**. The station's 5 / 0.05 is validated as a pair, a small gain at no measured cost

**From:** Architect · **To:** QA, the Captain · **Date:** 2026-11-09 21:45:50Z (`date -u`) · **Branch:** `arch/kmin-osd-recal`
**On:**
- QA's report `qa/rr-study/2026-11-09-2145-qa-kmin-osd-recal-report.md` (`7ec55cd2`, `qa/same-chain`, local);
- freeze `823f62a3` (code `58b6f321`, harness `7122404e`), made before any arm output;
- spec `a79f9cf7` + Amendments 1 (`ca345413`) and 2 (`5fe706ce`).

Docs only: `git diff --stat origin/main -- src/ native/` is empty.

## §1. Rows and verdict, adopted as reported

| row | result |
|---|---|
| V-NAT / V-SET | PASS (pin at the start and end of both arms; readbacks exact, R-F4 and L1′ ON, nhard 24) |
| V-WIRE | PASS. The `kMin` wire is clear on residual buffers. The OSD wire is **thin** (1 vs 0 in one cycle) and not isolated |
| **N-BETTER** | **fires: NET_B−A +0.146 pp [0.057, 0.236]** (+18 corroborated rows of 12,292) |
| **U-OK** | **fires: ΔU′_ta 0.005 per cycle [0.000, 0.0125]** vs 0.021 (2 tested-absent rows in 400 cycles) |
| HK-026 flag | **False** (B's untestable-class outputs 0, hashed 0) |

**Verdict: KEEP-5, read as the pair** (Amendment 2: the OSD wire is thin). QA's slip on a descriptive line (Q46) touches no row.

## §2. What it says

- **On today's decoder, with R-F4 and L1′ ON, the station's 5 / 0.05 is slightly better than the code default 10 / 0.10, at no measured cost:**
  - +0.146 pp of corroborated decodes;
  - unconfirmed output inside the bar, with 2 rows in 400 cycles;
  - 0 abandons in either arm.
- **D-009's values are superseded for this configuration.** They were set on the inverted OSD and before subtraction.
- **Where the gain comes from:** the floor acts on the subtracted buffers, not the first decode. B-only rows are mostly batch 4 (11) and batch 2 (9). The OSD-path rows rise by 17, consistent with the looser gate, but not isolated.
- **The cost is time.** The latest batch arrives about **+0.8 s later** (median 3.8 → 4.6 s, max 6.4 → 7.2 s), still far from the 13 s cycle. Batch 1, the one the QSO controllers use, is the first decode, which this setting does not touch (the cap binds there). So this should not move TX timing. I have not measured that directly.
- **Size:** about a tenth of R-F4's gain. It is real by the registered rows but small, one night, 40 m.

## §3. For the Captain

1. **Nothing to change on the station:** it already runs 5 / 0.05, and that is now validated.
2. **Optional, housekeeping:** make 5 / 0.05 the code default, so a regenerated config matches what was tested. It is a small `src/` change (a Developer session plus QA's review). It does not change your station. I recommend it only for tidiness; it can wait.

## §4. Predictions (spec §5), scored

| # | prediction | P | outcome |
|---|---|---:|---|
| KO-1 | V-NAT, V-SET, V-WIRE pass on the first run | 0.70 | ❌ MISS (V-WIRE's first population could not fire, E151) |
| KO-2 | NET_B−A point > 0 | 0.55 | ✅ HIT (+0.146) |
| KO-3 | U-FAIL fires | 0.35 | ❌ did not occur |
| KO-4 | KEEP-5 | 0.25 | ✅ HIT |
| KO-5 | REVERT-10 | 0.35 | ❌ did not occur |

**Brier 0.300 over 5.** KEEP-5 at 0.25 was the under-confident call. I priced the U side as the likely failure, and it was not.
