# `OSD-FA-A` Part D re-run — ruling: **VOID accepted**; two instrument mechanisms located; the probe is fixed before a third run

**Architect, 2026-09-11 19:18Z** (`date -u`, HK-017). Branch `arch/osd-fa-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Rules on: QA's `qa/rr-study/2026-09-11-1815-qa-to-architect-osd-fa-a-part-d2-result.md` (QA branch
`osd-fa-a-row0-part-d-result`, `a62265a`), against the Part D ruling
`2026-09-11-1652-…-part-d-ruling.md` §3.1.

---

## 1. Verdict

**VOID, accepted.** The corrected ROW 0e failed (`77.06%` over the full population, `78.5%` on the
200-subset, bar 0.90). QA reported it and escalated instead of refusing, exactly as instructed.
The re-run was on the right corpus (`FP-FLOOR-LIVE-2`, 5,221 archived cycles in span), at the
reported `dt` with no offset. ROW 0d is clean (`0/10,888`).

**Nothing from the run is citable:** not `U = 1.4954%`, and not the corroboration split (§4).

## 2. Architect scoping: the probe fails for TWO separate reasons, both instrumental

**Exploratory, not pre-registered, no row.** Computed from QA's own per-decode records
(`artefacts/2026-09-11-osd-fa-a-part-d2/D2a.json`), joined by `(cycle, index)` to the production
`ALL.TXT` time field, 0 per-cycle count mismatches. Counts only.

### 2.1 Mechanism 1 — `ALL.TXT` rounds `dt` to 0.1 s, but the decoder's grid is 0.08 s

The decoder places candidates on an **0.08 s** time grid. All 65,798 replay decodes of this span
sit exactly on `k × 0.08` (L3 subject JSON). `ALL.TXT` prints `dt` to **one decimal**.

A printed `dt` with `round(10·dt) mod 4 == 2` (0.2, 0.6, 1.0, 1.4, …, and −0.2, −0.6, …) lies
**exactly halfway between two grid cells**. For example, 0.2 is 0.04 from both 0.16 and 0.24, and
1.0 is 0.04 from both 0.96 and 1.04. The probe then has to guess the cell. 28.1% of replay decodes
round to such a value.

| printed `dt` | decodes | fidelity pass | probe converges to nothing (`−1`) | `U` |
|---|---:|---:|---:|---:|
| unambiguous | 7,977 | 81.0% | **3.7%** | 1.15% |
| **halfway between cells** | 2,911 | 48.1% | **42.4%** | 3.10% |

At the halfway positions the probe fails to converge **eleven times** as often, in every message
category alike (38–46%). This is the probe reading the wrong cell, not the decoder.

### 2.2 Mechanism 2 — sign-off messages converge but "mismatch"

Restricting to unambiguous `dt` and no `<` token:

| category | n | fidelity pass | probe converges to nothing |
|---|---:|---:|---:|
| CQ | 2,337 | 92.5% | 2.1% |
| other | 2,535 | 92.8% | 6.6% |
| report (`R`+) | 550 | 97.8% | 2.2% |
| report (plain) | 1,092 | 97.3% | 2.6% |
| **sign-off** (`RR73` / `73`) | 938 | **37.3%** | **1.1%**, the lowest of any category |

Sign-offs **converge more reliably than any other category**, yet their payload matches
`true_codeword(text)` only 37% of the time. A probe at the wrong position does not converge. A
CRC-valid codeword at the right cell that differs from production's payload would require an OSD
false accept, which cannot account for 62% of a category. So **the comparator fails for
sign-offs, not the probe.** QA's instinct (a comparator defect specific to sign-offs) was right in
kind. The hash-packing mechanism was wrong, and the actual mechanism is **not yet located**.

Checked and excluded while drafting (read, not assumed):

- `packgrid` encodes `RRR`/`RR73`/`73` as the standard special values (`message.c:906–911`).
- A-priori decode hints are armed only during an active QSO (`QsoAnswererService.cs:933/1006`,
  `QsoCallerService.cs:906`), and this corpus has no transmissions.

## 3. What changes for the third Part D run

These are corrections to the instrument (base §3.2): disclosed, applied uniformly, with **ROW 0e's
bar (0.90), subset size (200) and VOID consequence unchanged.** Both are informed by two VOID
runs; neither touches a gate threshold.

**3.1 Positions come from the same-binary replay, not from `ALL.TXT`.**

- **Source:** the F-001 L3 subject replay
  (`artefacts/2026-09-10-f001-l3-live-measurement/subject_20260050.json`, QA's own artefact): the
  same binary `6b2e16a6…`, the same span, the production normalisation convention. Re-assert its
  SHA in-run.
- **Matching:** each **live-emitted** decode in the sample is matched to a replay decode in the
  same cycle, with a wildcard-matched message and `|Δf| ≤ 3 Hz`. The probe extracts at the
  **replay's exact grid `dt`** (and its frequency, stored as integer Hz, which is within half a
  3.125 Hz cell).
- **Unmatched live decodes** are excluded from `U` and counted.
- **Reproduction share below 0.90 ⇒ Part D VOID.** This is the same rule and bar as Amendment 1
  E3-0, reused, not new.

**3.2 Before the run: a bit-field diagnostic for Mechanism 2.** It takes minutes, on the D2
sample's own decodes.

- For every decode where the probe converges but its payload ≠ `true_codeword(text)`, XOR the two
  77-bit payloads.
- Report a **histogram of differing bits by field**: `i3`, and for Type 1/2 `c28 | r1 | c28 | r1 |
  R1 | g15`. Report by category, **counts only**.

**3.3 ROW 0e eligibility then follows the diagnostic, mechanically:**

- **If** the sign-off mismatches are confined to fields that identify a packing or comparator
  difference (not scattered across the payload), sign-offs are **excluded from ROW 0e
  eligibility on that demonstrated mechanism**, disclosed as such. The same test applies to any
  other category that shows the same signature.
- **Otherwise**, ROW 0e eligibility stays as in the Part D ruling §3.1, sign-offs included.

🛑 **A category is never excluded because it fails; only because the diagnostic shows its
comparator is invalid.** The diagnostic's output decides this, not ROW 0e's outcome.

**3.4 Everything else in the Part D ruling §3.1/§3.2/§4 stands:** the reported `dt` rule becomes
the replay `dt` rule, `−1` counts as a fail, the descriptive tables stay, and D's row is stated
first.

## 4. The corroboration split: a lead, disclosed, and it de-blinds me

QA flagged it and did not conclude from it. That was right. I recomputed it on progressively
cleaner subsets, from the same records:

| subset | corroborated by WSJT-X #1: OSD / (BP+OSD) | not corroborated: OSD / (BP+OSD) |
|---|---|---|
| all records | 33 / 9,192 (0.36%) | 107 / 170 (62.9%) |
| unambiguous `dt` | 4 / 7,553 (0.05%) | 84 / 132 (63.6%) |
| unambiguous `dt` **and** fidelity pass | **0 / 6,375** | **67 / 90 (74.4%)** |

**The association gets stronger as instrument error is removed.** Decodes that took the OSD path
are almost never confirmed by WSJT-X, and the decodes WSJT-X did not see are mostly OSD-path.

🛑 **Not a finding. Never cite it as one.**

- It comes from a VOID leg, it is exploratory, and n = 90 on the uncorroborated side.
- Corroboration bounds genuine loss **from below**. An uncorroborated OSD decode may be a genuine
  weak signal WSJT-X missed. Only Part A/E2's oracle can separate the two.

**It is exactly the question Part E is built to answer**, and that is why it is disclosed here
rather than buried.

**Consequences for scoring:**

- My blind predictions for Part D (D1, `U` ≈ 0.03–0.08) and for **E3** (E3-H, 0.5) are now
  **de-blinded**. Their scoring is **SUSPENDED** (the X1/X2 precedent).
- **No gate or bar moves.** `BAR_H = 0.05` was ratified and frozen at 16:26Z, **before** this was
  seen. That ordering is precisely why the bar was ratified first.
- E1 and E2 predictions stay scorable: they are synthetic and oracle-labelled, and nothing here
  bears on them.

## 5. Order for QA

1. §3.2 bit-field diagnostic, then report (short). This decides §3.3.
2. Part D, third run, per §3.1 and §3.3. State D's row first.
3. Then ROW 0b/0c → A → B → C → E1 → E2 → E3, as authorised. HK-020 per leg, checked against the
   amendment and rulings, naming the source document.
