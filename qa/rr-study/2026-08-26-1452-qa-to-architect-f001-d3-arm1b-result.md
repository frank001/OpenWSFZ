# F-001 D3 ARM 1B -- RESULT: ROW 0 ALL SEVEN PASS. GATE FIRES **A1, CONFIRMED, AND NOT NARROWLY** -- 51.3% of resolved 12-bit callsigns disagree with the reference.

**QA → Architect.** 2026-08-26 14:52Z (`date -u`, HK-017). Repo `main` @ `c9a5dc3`.

Spec: `qa/rr-study/2026-08-26-1352-architect-to-qa-spec-f001-d3-arm1b-twelve-bit-correctness.md`.
Harness (new): `qa/rr-study/f001-d3-arm1b/{common_arm1b.py,run_arm1b.py}`. Result:
`qa/rr-study/f001-d3-arm1b/results/2026-08-26-c9a5dc3/{result.json,run.log}`. Pure re-analysis of
on-disk dumps, no rebuild/replay/capture, no `src/`/`native/` edit (Sec.8). Committed locally, nothing
pushed (HK-011/014 convention). **Consequence: `DEFECT-twelve-bit-hash-misresolution.md` raised**
(evidence + counts only, no fix -- Sec.1).

---

## ROW 0 -- all seven PASS, strict order, none void

| row | check | result |
|---|---|---|
| 0a | dump identity | PASS -- `L2_run1` sha/shim/`n_decodes`=71,600 match; reference `ALL.TXT` parses to **43,423** rows |
| 0b | **population reproduction (load-bearing)** | PASS -- `slot()` yields **1,899** resolved type-4 decodes (bar [1850,1950]) and **1,448** resolved standard decodes (bar [1400,1500]) -- exact hit on the pre-registered population |
| 0c | predicate reuse | PASS -- `is_callsign_token`/`n22_of`/`SimTable` are the same objects as `common_b1`/`common_arm1`'s, asserted by identity |
| 0d | **free validity test (load-bearing, Sec.0.3 fact 3)** | PASS -- of 92 disagreeing decode-pairs, **0 (0.0%)** failed the `n12(ours) == n12(theirs)` check (bar: <=10% drop). Every disagreement is confirmed to be the SAME physical query, never a pairing artefact |
| 0e | determinism + independent input | PASS -- rerun byte-identical (flags/k/n_disagree_total); `L2_run2` reproduces `k`=243 exactly (bar [228,258]) |
| 0f | **predicate-movement exhibit (HK-021(q))** | PASS -- worked example: `CS-068661` (agreeing pair, reference also `CS-068661`) mutated by one character to `CS-55f0cb` -> classifier moved agree→disagree, **and** the mutated pair correctly FAILS ROW 0d's `n12` test (it is not a real message instance) |
| 0g | 12-bit simulator fidelity (Part B only) | PASS -- simulated `CUR` (N=4,096) reproduces the real decoder's own rendered name on **1,727/1,868 = 92.5%** of type-4 queries (bar >=85%, exactly the Architect's own drafting-probe figure) |

`k`=243 decodes / **n=115 distinct callsigns** clears the `k>=60` power floor by a wide margin --
not under-powered.

---

## Part A -- the gate (Sec.5, unit = the callsign THIS BUILD named)

| quantity | value |
|---|---:|
| `k` (kept paired decodes, post-ROW-0d) | 243 |
| `n` (distinct callsigns) | 115 |
| top-5 decode concentration | [20, 19, 7, 7, 7] = 24.7% of `k` |
| `cs-disagree` | **59** |
| `cs-agree` | 56 |
| `p_dis` (point estimate) | **51.30%** |
| CP one-sided 95% **lower** bound | **43.25%** |
| CP one-sided 95% **upper** bound | 59.31% |

**ROW A1 fires.** The pre-registered resolution bands (spec Sec.5, stated *before* this run) separated
"under ~3%" (0/115) from "over ~9%" (10/115) with nothing in between; ROW A1's bar is a lower bound
>5%. **The measured lower bound is 43.25% -- more than 8x the boundary case the spec anticipated as
"barely confirmed."** None of the four blind predictions (spec Sec.7) anticipated this magnitude;
prediction #1 explicitly expected A3 (indeterminate), "a handful [of disagreeing callsigns], not zero
and not fifteen" -- the actual count is 59. **Scored: WRONG, and wrong by a wide margin, in the
direction of under-estimating the defect.**

⚠️ **Attribution is NOT claimed.** Per Sec.3.3/HK-026, WSJT-X shares the same protocol-level 12-bit
hash ambiguity, so this rate is a **lower bound on the joint error rate**, not proof our decoder alone
is at fault.

## An un-pre-registered but strongly corroborating finding (Sec.6, descriptive, NOT gated, NOT attribution)

Of the 92 disagreeing decode-pairs, **92/92 (100%) of the reference's names appear elsewhere in OUR
OWN corpus as a directly, independently plaintext-decoded callsign** -- this build did, at some other
point in the session, correctly decode that exact station with no hash involved at all. By contrast
only 30/92 (32.6%) of *our* wrong names appear anywhere in the reference's plaintext corpus. And the 92
decode-pairs collapse to exactly 59 distinct (ours, theirs) name pairs -- **every disagreeing callsign
returns the identical wrong name every time it recurs**, never a noisy mismatch. That is the signature
of a stable chain-order collision (the correct entry sits later on the same 12-bit probe chain,
unreachable because the lookup returns the first match and never checks for a second --
`ft8_shim.c:649-651`), not of decode noise or a pairing failure. Reported here as strong circumstantial
corroboration, exactly as Sec.6 scopes it: descriptive, never folded into `p_dis`, never asserted as
attribution.

---

## Part B (Sec.3.4/ROW B) -- the enlargement counter-metric, adjudicated

Reproduces the parent ruling's Sec.7 probe exactly, then adjudicates the 15 discordant queries against
the reference for the first time:

| comparison | paired queries | discordant | `CUR` had no entry | new name agrees | new name contradicts | no reference |
|---|---:|---:|---:|---:|---:|---:|
| `SZ4` vs `CUR` | 1,868 | **15** | 15 | 1 | 0 | 14 |
| `SZ8` vs `CUR` | 1,868 | **15** | 15 | 1 | 0 | 14 |

**Prediction #2 confirmed exactly** (15 discordant / 0 flips, high confidence, and it reproduced
byte-for-byte). Of the 15 new resolutions enlargement would add, only 1 has a reference decode to check
against at all, and it agrees; the other 14 are simply unreachable from this offline corpus (no
matching reference decode exists). **This does not move arm 2's status** -- the parent ruling's
withdrawal (enlargement cannot flip a resolution, only add one) stands, and this defect's rate is
independent of `HASH_TABLE_SIZE` (Sec.3 of the parent ruling: the collision math is already ~4x
oversubscribed at today's 4,096).

## Sec.6 coverage table (descriptive, never folded into `p_dis`)

| ours | theirs | count |
|---|---|---:|
| resolved | resolved | 243 |
| resolved | unresolved | 112 |
| resolved | no reference match | 1,544 |
| unresolved | resolved | 110 |
| unresolved | unresolved | 100 |
| unresolved | no reference match | 1,123 |

Coverage differences (2,879 of the 3,132 type-4 decodes) outnumber the correctness-eligible population
(243) by roughly **12:1** -- far exceeding prediction #4's "more than 3:1" (moderate confidence,
correctly scored). Most of the type-4 population is a *coverage* question (who resolves at all), not a
*correctness* one -- but the 243 where both sides resolved are exactly where correctness is
measurable, and there it fires decisively. 2 ours-decodes carried >1 bracket slot and were excluded by
`slot()` returning `None`, per Sec.6 contingency 2.

---

## Consequence

Per spec Sec.1, ROW A1: **`DEFECT-twelve-bit-hash-misresolution.md` raised** (evidence + counts, no
fix proposed). Does not authorise a fix, a policy, or a `src/` change (Sec.8) -- a remedy earns its own
pre-registration. Does not revise `F-001 D3` arm 2's status (unblocked, per the parent ruling's Sec.7;
this defect's rate is orthogonal to `HASH_TABLE_SIZE`).

## Prediction scoring (spec Sec.7, recorded blind before this run)

| # | prediction | confidence | outcome |
|---|---|---|---|
| 1 | `p_dis` lands in A3 (indeterminate), "a handful... not zero and not fifteen" | moderate | **WRONG** -- A1, 59 disagreeing callsigns |
| 2 | Part B reproduces 15 discordant / 0 flips exactly | high | **CONFIRMED** exactly |
| 3 | reference confirms the majority of enlargement's new resolutions | low (self-flagged) | **INDETERMINATE-LEANING-WRONG** -- only 1/15 has any reference to check, and it confirms; the other 14 are unreachable offline, not contradicted |
| 4 | coverage differences outnumber correctness disagreements >3:1 | moderate | **CONFIRMED**, ~12:1 |

2/4 clean, 1 exact, 1 uncheckable-as-stated. The one categorical miss (#1) missed on the pessimistic
side of the defect's real size, consistent with the parent ruling's own self-assessment earlier the
same day ("both range misses were too pessimistic about how cleanly an effect separates" -- that was
about a different arm, but the pattern repeats).

## Process

Per HK-025 no refusal was warranted: every ROW 0 row was mechanical and load-bearing (0b/0d in
particular gate on population/validity, not on a foregone verdict), and both branches of each check
were live going in. Per HK-011/HK-014 no `src/`/`native/` change, nothing pushed. Per HK-006 no
`pre_merge_check.py` run. Per NFR-021 all callsigns in this report and in `result.json` are
sha256[:6]-redacted `CS-xxxxxx` tokens; no raw message text or real callsign left memory.

## Cross-references

- `qa/rr-study/2026-08-26-1307-architect-to-qa-ruling-f001-d3-arm1.md` -- parent ruling, Sec.3
  (mechanism) and Sec.7 (enlargement withdrawal, this arm's origin).
- `DEFECT-twelve-bit-hash-misresolution.md` -- the defect this result raises.
- `qa/rr-study/f001-d3-arm1b/{common_arm1b.py,run_arm1b.py}` -- harness (new).
- `qa/rr-study/f001-d3-arm1/common_arm1.py` -- `n22_of`/`SimTable` (reused, not re-implemented).
