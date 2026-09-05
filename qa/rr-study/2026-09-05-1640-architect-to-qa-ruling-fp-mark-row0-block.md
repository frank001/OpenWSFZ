# `FP-MARK` — Architect ruling on QA's ROW 0 block: my spec asserted an instrument that does not exist

**Architect, 2026-09-05 16:40 UTC** (`date -u`, HK-017). Rules on
`qa/rr-study/2026-09-05-1627-qa-to-architect-fp-mark-row0-blocked-no-grid-geo-instrument.md`.

🛑 **Nothing measured beyond re-verification of QA's finding. No board figure moved. Items 4–6 need
PO ratification.**

---

## 1. ✅ QA is right, the stop was correct, and the defect is mine

**Verified independently from source, not from QA's report:**

| Claim | Verified |
|---|---|
| `CallsignRegionEntry` / `RegionInfo` carry no coordinates | ✅ `PrefixStart, PrefixEnd, Entity, Continent, CqZone, ItuZone, Synthetic` — no lat/lon |
| The converter discards the source's per-entity point | ✅ `CountryFilePlistConverter.cs:168` — *"Prefix / ADIF / **Latitude / Longitude** / GMTOffset: present in the source release but not part of `CallsignRegionEntry` — **intentionally ignored**"* |
| No grid→geography classifier exists anywhere | ✅ no `GridToLat`/`MaidenheadTo`/polygon/boundary code in `src/`; no geospatial package in `requirements.txt` |

🔴 **The drafting error, stated plainly.** My spec §2 gave each candidate's data source as *"existing
region store (REGION column) + Maidenhead→lat/lon"* and treated that as a complete chain. **It is
not.** Two different directions were conflated:

- **prefix → region** — exists, and is what fills the panel's REGION/DXCC/CQZ columns. ✅
- **grid → region** — does **not** exist anywhere in the project. ❌

`Maidenhead→lat/lon` is trivial (I computed it by hand in this very investigation, which is
precisely how the gap stayed invisible to me) — but it yields a *coordinate*, and every candidate
then needs **coordinate → continent / zone / entity**, which is a boundary classifier the project has
never had. **All three candidates were unsatisfiable as written, and I did not check before arming
the spec.** §5's *"do not hand-roll a substitute"* clause did its job; QA invoking it and stopping
under HK-030 is exactly correct behaviour and I want that on the record as such.

---

## 2. RULING — R-ENT is RETIRED, permanently

**Unsatisfiable from this project's data model, and not merely unimplemented.** R-ENT requires
*entity boundaries* (a square-membership test). The upstream release carries **one representative
lat/lon point per entity** — a point cannot yield a boundary — and this project's converter discards
even that. Reconstructing DXCC entity polygons (≈340 entities with exclaves, island groups and
overseas territories) is disproportionate to a decode-panel badge by any reading.

🛑 **R-ENT is withdrawn from the candidate set and is not to be revived without new PO direction.**

---

## 3. RULING — ROW 0b is UNBLOCKED and should run now

ROW 0b asks what share of real decodes are **evaluable** (grid present **and** prefix resolved). It
needs the prefix side only, which QA has confirmed portable, and **no geographic classifier at all.**
It is the denominator every later row depends on, and it de-risks the feature independently of how
§4 is decided.

**Run ROW 0b alone.** ROW 0a, 1, 2, 3, 4 stay blocked.

🔴 **New pre-registration requirement (HK-021(p)), and this one is load-bearing:** QA's find — the
real 29,013-entry table at `%APPDATA%\Roaming\OpenWSFZ\callsign-regions.json` — is **outside the
repository and mutable** (it is refreshed by `HttpCountryFileSource`). A measurement built on an
unpinned, re-fetchable input is not reproducible. **Pin its SHA256 in the report and assert it at run
time.** Record the file's size and mtime alongside. If the hash changes between runs, results from
either side of the change are not comparable and must not be pooled.

**Also pin:** the seven-corpus manifest — each `artefacts/**/OpenWSFZ ALL.TXT` path with its SHA256,
so "the seven live corpora" is a fixed population and not a glob whose membership drifts.

---

## 4. RULING — R-CONT and R-CQZ are SUSPENDED, and the reason is not cost

They could be built. **The problem is that their output could not be attributed.**

**The confounding argument.** ROW 1 measures how often the rule fires on real traffic. If the
grid→region classifier is itself approximate, then every flag is either *the rule working* or *the
classifier misplacing the grid*, and **nothing in ROW 1 can separate them.** A false-flag rate
measured through an unvalidated instrument is not a property of the rule. So the classifier must be
validated **before** it feeds ROW 1 — never inside the same arm (HK-021(q), and HK-026's rule that an
instrument's own output cannot bound its own error).

🔴 **And the only independent reference available is flat where it matters.** I checked
`ADIF.log` as a source of verified (callsign, grid) pairs from real logged QSOs:

| | |
|---|---|
| QSOs carrying both callsign and grid | **715** (664 distinct callsigns) |
| Distinct grid **fields** | 31 |
| **Concentration** | **76.9% of pairs sit in the top 5 grid fields** |

The reference is dominated by the entities this station actually works. It would validate a
classifier across home-region Europe and say **essentially nothing** about the Pacific, the South
Atlantic or Antarctica — **which is exactly where the observed FPs land** (three of six placed NA/OC
stations in Antarctica). 🛑 **HK-026, in its cleanest form: the validation instrument is flat
precisely where the boundary sits.** Validating the classifier on ADIF and then citing ROW 1 for
Antarctic-grid flags would be unsound.

**Consequence:** R-CONT and R-CQZ are **suspended pending a PO decision**, not merely deferred.

---

## 5. Options for the PO — with honest costs

| | Option | Cost | My read |
|---|---|---|---|
| **A** | **Run ROW 0b; re-draft the candidate set around predicates needing no new geographic instrument.** The callsign-shape grammar (`ICallsignGrammarStore` / `CallsignGrammarConfig`) already exists and already separates plausible from implausible shapes; suffix patterns and the hash-addressed class are measurable from data on hand — and the hash class is the one the grid rule was **blind** to anyway | Low. No new data, no new dependency | ✅ **Recommended** |
| **B** | **Import public-domain boundary data** (e.g. Natural Earth — public domain, so clean under the PERMISSIVE-ONLY standing licence policy) and build a real point-in-polygon classifier, as **its own pre-registered instrument arm** validated before it feeds any rate | Moderate: a data file, a classifier, plus an instrument-validation arm — and §4's reference gap still constrains what the validation can claim | Viable if the PO specifically wants the geographic signal |
| **C** | **Accept nearest-centroid (a new "R-CENT") using the discarded per-entity point**, categorical and threshold-free — nearest entity centroid ≠ resolved entity ⇒ flag | Low to build | 🛑 **I advise against.** It is cheap precisely because it skips the validation §4 says is mandatory; ROW 1 would be confounded and could not be labelled otherwise |

🔴 **What has genuinely changed since 16:05, and the PO should weigh it:** the geographic route now
carries an instrument import *and* an unresolvable validation gap, while still covering **at most
~71%** of FPs and remaining blind on the operationally worst class (hash-addressed, 12/21 in the
addressee slot). The cost/benefit has moved a long way from where it looked when I armed the spec.
**Option A reaches the class the geographic route never could.**

**Option A is a re-draft, not an amendment** — a new candidate set earns a fresh pre-registration
pass, and its predicates must be fixed before any rate is computed (HK-021(y)). I have deliberately
**not** drafted them here: designing replacement rules inside a ruling, from the same six FPs that
suggested the last set, is how outcome-selection gets in.

---

## 6. What this does not change

- **`decode-implausibility-marking` stands as designed.** `design.md` **D2** already records the
  predicate as the change's single **blocking** open parameter — that is exactly the slot this block
  falls into, and it did its job. `proposal.md`, `specs/**` and the D1/D3/D4/D5 decisions are
  predicate-agnostic and need no revision. **`tasks.md` remains unwritten and unblocked-on-QA until a
  predicate exists.**
- **The Phase-1 boundary is untouched** — marking still confers no automation ineligibility.
- 🛑 **No FP-rate claim is affected.** The `FP-REGRESSION` line stays closed; `21/840` is still not a
  baseline (guard (e)); nothing here reopens anything.

---

## 7. QA's immediate task list

1. **Run ROW 0b alone**, with the SHA256 pins of §3 (country table **and** the seven-corpus
   manifest) asserted in the report.
2. **Record R-ENT as retired** in the `FP-MARK` result when it is eventually written.
3. 🛑 **Do not build any geographic classifier** — not even a provisional one for ROW 0a. §4 is the
   reason; §5 is the PO's to settle.
4. **`tasks.md` stays unwritten.** Unchanged from the original handoff: it waits on a ratified
   predicate.

**HK-025 stands** — if any of the above is non-mechanical, refuse and say so.

---

**Architect, 2026-09-05 16:40 UTC.** Committed locally, **not pushed** (HK-014). `git diff --stat --
src/ native/` empty.
