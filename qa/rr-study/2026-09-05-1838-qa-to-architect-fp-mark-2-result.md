# `FP-MARK-2` result — both instrument-based candidates fail ROW 0a; R-HASH is the live number

**QA, 2026-09-05 18:38 UTC** (`date -u`, HK-017). Answering
`qa/rr-study/2026-09-05-1823-architect-to-qa-spec-fp-mark-2-no-geo-candidates.md`.

Script: `qa/rr-study/fp_mark_2_analysis.py`. Raw output (aggregate only, NFR-021):
`artefacts/2026-09-05-fp-mark-2/`. `git diff --stat -- src/ native/` **empty**. No geographic
classifier used or built.

🛑 **QA recommends no candidate and draws no verdict on shipping (HK-015).**

---

## 1. Pins asserted, unchanged (spec §0)

Region table SHA256 `bcf0bee2…c98e6` and the seven-corpus manifest — both asserted equal to the
2026-09-05 18:09Z ROW 0b pin at run time; the script hard-fails if either has drifted. Both matched.

**Banked linear-vs-binary mechanical diff, run BEFORE any rate below (spec §5, per the 18:20Z
verification's requirement):** 5,000 seeded real callsign-position tokens (seed `20260905`),
`RegionIndex.resolves()` vs a fresh, untouched linear port of `TryMatchPrefix`
(`CallsignRegionStore.cs:48-73`) — **0 mismatches.** Behavioural identity mechanically diffed, not
asserted.

## 2. 🔴 Self-correction before any row ran: the "13 runs" list was wrong

I first assembled the 13 admissible S5 runs from a sub-agent's citation of a document
(`2026-09-05-1311-...`) that **does not exist in this repository.** That list produced **36**
windowed FP decodes, not the established **72** — the script's own `== 72` assertion (built in per
HK-018 discipline) caught this before any candidate's numbers were computed, not after.

**Root cause, verified directly:** the wrong list included two runs that are windowed to **zero**
(`2026-07-07-df4cc89`, `2026-08-05-3bd4cd0`) and omitted three runs that are **not**
(`2026-06-20-6e821fa`=11, `2026-06-20-8eea3c4`=9, `2026-06-20-d40b4cd`=16 — summing to exactly the
missing 36). **Corrected by scanning every `S5_matched.csv` under `qa/rr-study/results/` directly**
(22 directories, not taken from any prior citation) and applying the same `fp_in_window` scoping to
each: the grand total across all 22 is **exactly 72**, and **exactly 13** of them are non-zero — this
is what the established fact means by "13 runs." The corrected list is recorded in the script with
this provenance note, so it is not re-guessed next time.

## 3. 🔴 R-HASH definition discrepancy — flagged, not silently resolved

The spec cites `IsUnresolvedHashMarker` (all-dots-only, `QsoMessageParsing.cs:52-53`) as R-HASH's
instrument. Implemented literally, it reproduces only **10/72** with a hash in token 0 — not the
spec's own established **12/72 = 16.7%.**

**Checked directly, not guessed:** of the 72 FP messages, exactly **12** have a token 0 starting with
`<` at all; of those, **10** are the strict all-dots `<...>` shape and **2** are bracket-wrapped but
carry other content — a resolved-looking hash reference (real traffic shows the same shape whenever a
hash-compressed callsign was successfully resolved) rather than the unresolved `<...>` marker. The
broader **"token 0 starts with `<`"** check — equivalent to failing
`IsCandidateCallsignToken`'s own `token[0] != '<'` guard (`Ft8Decoder.cs:913`), the same exclusion
`ExtractPrimaryCallsignToken` already applies — reproduces **12/72 exactly**, and **21/72** for
"any position," matching the spec's own **21 (29.2%)** figure too. This also matches the design's own
stated rationale for why the class is blind ("no prefix in the addressee slot" is true for *any*
bracketed token, not only the all-dots one).

**Used the broader definition for R-HASH below**, since it is what reproduces the spec's own cited
constant — flagging the mismatch between the spec's instrument citation and its own established
number rather than picking silently. If the narrower, strictly-cited shape was actually intended,
ROW 1's number changes (see §6).

## 4. The 72-decode FP population, reconstructed

| Run | Windowed FP decodes |
|---|---|
| `2026-06-20-6e821fa` | 11 |
| `2026-06-20-8eea3c4` | 9 |
| `2026-06-20-d40b4cd` | 16 |
| `2026-07-04-a3738fc-f002-s5-n300` | 8 |
| `d011-fp-recheck-2026-07-04` | 7 |
| `2026-08-15-8d6e1b1` | 1 |
| `2026-08-21-7d36038` | 1 |
| `2026-08-22-f5dec23` | 4 |
| `2026-08-29-872ba65` | 1 |
| `2026-08-30-2e60949` | 2 |
| `2026-09-02-3b52608` | 4 |
| `2026-09-03-35378b9` | 2 |
| `2026-09-05-10bbaad-s5-standalone-n300` | 6 |
| **Total** | **72** |

## 5. 🔴 ROW 0a — BOTH R-UNALLOC and R-SUFFIX FIRE

| Candidate | Evaluable (of 72) | Flags | Flag-of-evaluable | Bar | Outcome |
|---|---|---|---|---|---|
| **R-UNALLOC** | 66 (91.7%) | 17 | **25.8%** | fires if < 40% | 🛑 **FIRES — STOPPED** |
| **R-SUFFIX** | 43 (59.7%) | 6 | **14.0%** | fires if < 40% | 🛑 **FIRES — STOPPED** |

Per spec §4: *"If both fire, continue with R-HASH/R-SOLO only — not a whole-arm stop."* Both
mechanism-derived candidates (an unallocated prefix; a doubly-suffixed exchange) **fail to catch even
40% of the labelled FPs they are evaluable for.** Neither candidate is a reliable *detector* of this
FP class, whatever its real-traffic behaviour turns out to be — reported below for completeness, not
as a validated result.

## 6. ROW 1 / 2 — the one trade-off table (spec §7)

| Candidate | ROW 0a (FP-side) | ROW 1 — real traffic, decode-level, CP95 | Band |
|---|---|---|---|
| 🛑 **R-UNALLOC** (STOPPED, §5) | 25.8% of 66 evaluable | k=1,671 / n=241,849 → **0.6909%** [0.6583%, 0.7247%] | <1% |
| 🛑 **R-SUFFIX** (STOPPED, §5) | 14.0% of 43 evaluable | k=1,089 / n=149,265 → **0.7296%** [0.6870%, 0.7741%] | <1% |
| ✅ **R-HASH** (ROW 0a N/A, §4) | 16.7% of 72 (known constant) | k=18,457 / n=241,858 → **7.6313%** [7.5258%, 7.7379%] | 1–10% |
| ✅ **R-SOLO** (ROW 0a N/A, §4) | 100% of 72 (known constant, cited) | **46.6%** [range 7.9–57.5% across the 7 sessions] — cited, spec §1, not re-derived | 1–10% .. ≥10% |

🔴 **R-HASH under the narrower, literally-cited `IsUnresolvedHashMarker` shape instead** (§3): FP-side
10/72 (13.9%, not the established 16.7%); real-side k=14,924/n=241,858 → **6.1706%** [6.0750%,
6.2672%] — still the same **1–10%** band either way, so the discrepancy does **not** change ROW 1's
band for R-HASH, only its exact value. Recorded so the choice of definition is visible, not buried.

**ROW 3 (coverage, of 72):** R-UNALLOC 23.61% · R-SUFFIX 8.33% · R-HASH 16.67% · R-SOLO 100%.

## 7. ROW 4 — pairwise overlap on the 72 labelled FPs (descriptive)

| Of A's marks… | …R-UNALLOC also marks | …R-SUFFIX also marks | …R-HASH also marks | …R-SOLO also marks |
|---|---|---|---|---|
| **R-UNALLOC** (17) | — | 2 (11.8%) | 0 (0.0%) | 17 (100.0%) |
| **R-SUFFIX** (6) | 2 (33.3%) | — | 0 (0.0%) | 6 (100.0%) |
| **R-HASH** (12) | 0 (0.0%) | 0 (0.0%) | — | 12 (100.0%) |
| **R-SOLO** (72) | 17 (23.6%) | 6 (8.3%) | 12 (16.7%) | — |

**R-HASH shares zero overlap with either R-UNALLOC or R-SUFFIX** — it is catching a completely
disjoint slice of the 72. R-SOLO trivially contains all three (100% coverage, a calibration anchor,
not informative here).

## 8. NFR-021 / housekeeping

Scanned with the project's own `scan()`/`classify()` before commit — including this report's prose,
per the standing note both the Architect and I have separately tripped today. `artefacts/2026-09-05-fp-mark-2/`
gathered with a `README.md` (HK-016), gitignored, not committed. No `src/`/`native/` change.
Committed locally, **not pushed** (HK-014).

---

**QA, 2026-09-05 18:38 UTC.** Mechanical outcomes only. R-ENT retired, R-CONT/R-CQZ superseded by
this re-draft (unchanged from the 16:40Z ruling). `tasks.md` for `decode-implausibility-marking`
stays unwritten — D2's predicate waits on the PO's pick from §6's table above.
