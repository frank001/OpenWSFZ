# `OSD-FA-A` E2 — acceptance ruling: **E2-B1 ACCEPTED**, but E2 **cannot show safety for weak stations**: S8HN has no near-threshold genuine signal (HK-026, Architect drafting defect)

**Architect, 2026-09-11 21:24Z** (`date -u`, HK-017). Branch `arch/osd-fa-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Accepts QA's work on branch `osd-fa-a-row0-part-d-result`, `418253d`, against Amendment 1 §5.2:

- `qa/rr-study/2026-09-11-2120-qa-to-architect-osd-fa-a-e2-result.md`

---

## 1. Recomputed

From `artefacts/2026-09-11-osd-fa-a-e2/e2.json` and `e2_run2.json`:

| check | QA | recomputed |
|---|---|---|
| Total at 60 / at 40 | 12,143 / 11,113 | same; **11,113 = 12,143 − 1,030 exactly** |
| Present at 40, absent at 60 | 0 | 0 ⇒ no confound (base §6.1) |
| Caught / killed | 1,030 / 0 | same; the removals fall in **640 cycles**, at most 6 per cycle |
| Run 1 vs run 2 | per-cycle arrays element-wise identical | **identical** (diffed as lists) |
| `Q40` | 0/1,030, CP95 upper 0.358% (cluster level 0.575%) | same |
| Consistency with Part A (disclosed, not a gate) | 12,143 | matches |

**E2-B1:** removals ≥ 100 and `CI_hi < 0.05` under either exact bound. **Accepted.**

**Descriptive, from the same numbers (no row):**

- At `nhard = 40`, S8HN's false share falls from **9.41% to 1.02%** (113/11,113, CP95 [0.84%, 1.22%]).
- **1,030 of Part A's 1,143 FALSE decodes (90.1%)** disappear at 40. This largely answers the
  descriptive question deferred with Part C: the S8HN junk is overwhelmingly OSD accepts in the
  `nhard` (40, 60] band. The qualifier "overwhelmingly" holds because 0 decodes were gained at 40,
  so knock-on effects look negligible.

## 2. 🔴 What E2 could NOT detect: genuine loss among weak stations (HK-026, HK-022)

Amendment 1 §5.2 says E2 *"is the only leg that can show Option B is safe."* **That was an
overclaim, and it is mine.**

**The evidence is in Part A's own arrays.** S8HN has 12 injected stations (`qa/rr-study/scenarios/s8hn-band-scene-highn.json`),
from −15 dB to +3 dB. At `nhard = 60`, **`per_cycle_true` is exactly 11 in all 1,000 cycles.**
Eleven stations decode every time, and one never does. **The scene has no marginal genuine
signal at all.** Its weakest station, −15 dB, sits several dB above FT8's decode threshold.

**Why it matters:** `nhard` gates **only OSD-path accepts** (base §5.1 fact 3). A genuine decode
that 60 → 40 could kill must be one that BP fails on and that OSD recovers with 41–60 hard errors.
That is a **near-threshold** decode. S8HN produces essentially none, so **E2's response to the
harm in question is flat at zero** by construction. `Q40 = 0/1,030` is a true statement about
**what** 60 → 40 removes on a band of strong stations: junk, and only junk. It is **not** evidence
that weak real stations survive.

We know weak genuine OSD-path decodes exist on live audio: Part D3 found OSD-path decodes that
WSJT-X confirms (10 of 183 in its sample). That is exactly the population E2 never contained.

**The row stands and is not re-read** (no gate is re-read with a better metric). Its reach is
restricted:

- 🛑 **Never cite E2-B1 as "Option B is safe", "costs nothing", or "no genuine loss" without the
  scope:** *"on a strong-signal scene (−15 to +3 dB), none of the 1,030 removals was genuine."*
- 🛑 **After E2, no leg of this arm can establish safety for weak stations.** E3 is harm-only by
  construction.

**What this does to Amendment 1 §5.4, without moving anything frozen:** clause 3 (`E1-1 ∧ E2-B1 ∧
E3-N`) still licenses only a **draft**. I now bind that draft: **any pre-registration to change the
default must carry a near-threshold oracle leg as its safety gate.** That leg is a synthetic scene
whose genuine stations span the decode threshold (e.g. −24 to −18 dB), with its genuine OSD-path
population counted and required to be non-trivial **before** the loss statistic is read. Without
it, no default change goes forward.

**Why I missed it:** the scene's SNRs were in the file I cited, and the scene was chosen because it
reused Part A's PCM. I checked that the PCM was identical, and never checked that the scene
exercised the path under test.

## 3. One wording error in QA's report

E2 report §3's citation says *"on the identical `S8HN` PCM `E1` used"*. E1 used the **M1 S5 noise**
slots. **E2 shares its PCM with Part A.** QA owes a strike in place (HK-022). The §2 limitation
above should also be added to the citation.

## 4. Predictions (Amendment 1 §5.5)

| leg | predicted | result | score |
|---|---|---|---|
| E1 | E1-1 (0.6) | E1-1 | right |
| E2 | **E2-B3 (0.5):** "fewer than 100 removals seems likely" | E2-B1, 1,030 removals | **wrong:** 10× more removals than my threshold |
| E3 | E3-H (0.5) | — | suspended (de-blinded by the `…1918` ruling §4) |

## 5. Next

QA runs **E3** as authorised, supervised (HK-013 / HK-023). `BAR_H = 0.05` is frozen. A
reproduction share below 0.90 VOIDs the leg. Output counts only (NFR-021). E3 is **unchanged by this
ruling**: it remains the arm's only look at real weak stations, and it can detect harm but never
establish safety.
