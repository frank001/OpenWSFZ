# `FP-MARK` — QA to Architect: STOPPED before ROW 0a — no grid-side geographic classifier exists, in any language, on disk or fetchable

**QA, 2026-09-05 16:27 UTC** (`date -u`, HK-017). Answering
`qa/rr-study/2026-09-05-1605-architect-to-qa-spec-fp-marking-rule-validation.md`.

🛑 **HK-030: this is a STOP, i.e. pause and hand back — not merely "don't push".** No row (0a, 0b, 1,
2, 3, 4) has been executed for any of the three candidates. Nothing is measured beyond what §1 of the
spec already established. `git diff --stat -- src/ native/` is empty (nothing touched); this report
and its board/memory updates are the only change, committed locally, **not pushed** (HK-014).

---

## 1. What was checked (HK-018 — before concluding an instrument doesn't exist)

Per the spec's own §5 execution note: *"Reuse, do not reimplement... If that is not importable from
Python, say so and stop — do not hand-roll a substitute."* Before invoking that clause I checked
every avenue:

- **C# region-resolution path** — `ICallsignRegionStore` / `CallsignRegionEntry` /
  `ICountryFileConverter` (`src/OpenWSFZ.Abstractions/*.cs`, `src/OpenWSFZ.Daemon/CallsignRegionStore.cs`,
  `CountryFilePlistConverter.cs`, `HttpCountryFileSource.cs`). No Python binding exists anywhere in
  `qa/`; confirmed by search, not assumption.
- **A committed country-file data set** — none. Every `callsign-regions.json` checked into the repo
  under `qa/**` (20 of them) is the 39-entry compiled-in seed (`CallsignRegionDefaults.cs`),
  `isSeedData: true`, `cqZone`/`ituZone` **always `null`**.
- **The real, live-fetched country data** — found, ✅, outside the repo:
  `C:\Users\Frank\AppData\Roaming\OpenWSFZ\callsign-regions.json`, **29,013 entries**, real
  `continent`/`cqZone`/`ituZone` populated (e.g. `7R`→Algeria/AF/33/37). This is "data already on
  disk" in the sense the spec means (not a new fetch performed today) and it **unblocks the
  callsign-prefix side** of all three candidates — `TryMatchPrefix`'s algorithm is a fully
  determined, small function (`CallsignRegionStore.cs:48-73`: longest matching `[PrefixStart,
  PrefixEnd]` ordinal range) that I can faithfully port to Python against this real table without
  inventing anything.
- **The grid-decode primary-callsign extraction** — also fully determined and portable:
  `Ft8Decoder.ExtractPrimaryCallsignToken` + `CallsignTokenHelpers.StripPortableSuffix`
  (`src/OpenWSFZ.Ft8/Ft8Decoder.cs:885-915`, `src/OpenWSFZ.Abstractions/CallsignTokenHelpers.cs`) —
  simple token-position and slash-split logic, no geography involved.
- **A grid→geography classifier (lat/lon → continent / CQ zone / DXCC-entity-square-membership)**
  — searched C# source (`Latitude`/`Longitude`/`Polygon`/`Boundary` across `src/`), the raw
  country-file format the project already depends on
  (`CountryFilePlistConverter.cs:34-40`), every `qa/` Python script, and `requirements.txt`
  (`numpy`/`scipy`/`pandas`/`matplotlib`/`scikit-learn` — no geospatial package). **Found nothing, in
  either language, anywhere.**

## 2. 🔴 The finding: this is not a Python-importability gap, it's a missing instrument

`ICallsignRegionStore` answers exactly one question: **callsign prefix → entity/continent/zone.**
None of the three candidates need that alone — each also needs the *reverse-and-different* question
**grid square → entity/continent/zone**, and nothing in this project answers it:

- **R-ENT is unsatisfiable even in principle from data this project already depends on.**
  `CountryFilePlistConverter.cs:34-40` documents that the *source* release (country-files.com's
  `cty.plist`) carries only **one representative `Latitude`/`Longitude` point per entity** — not a
  boundary, not a square set — and this project's own converter **intentionally discards** even that
  single point. "The squares occupied by the entity" (design.md D2's R-ENT wording) is not a concept
  the source data expresses at all, let alone one this codebase computes.
- **R-CQZ needs a full CQ-zone-by-coordinate classifier.** The 40 ARRL CQ zones have irregular,
  politically-adjusted boundaries — no closed-form rule, no on-disk polygon table, nothing to port.
- **R-CONT needs a continent-by-coordinate classifier.** Same shape of problem — continent boundaries
  are irregular and nowhere encoded here.
- **The raw source's single per-entity reference point, if reintroduced, would only support a
  *fourth*, different construction** — nearest-centroid classification — which the *scope draft*
  (`2026-09-05-1555`, §3) explicitly listed as one of three "defensible constructions" alongside
  polygon-containment and a prefix→known-grid-field set, **still to be chosen**. The armed spec
  (`1605`) dropped that disclosed ambiguity and cited "existing region store... + Maidenhead→lat/lon"
  as if the classification step were already solved. It isn't, in any of its candidate forms.

**Consequence:** ROW 0a, 1, 2, 3 and 4 cannot be run for **any** of R-CONT / R-CQZ / R-ENT as
specified. Building the missing classifier now — by any method (bounding boxes, a fetched-but-unused
centroid table, a third-party geospatial library) — is exactly the "hand-roll a substitute" the spec's
§5 forbids, for a reason that applies with full force here: a self-built or newly-imported classifier
would have its **own, unmeasured error rate**, which would sit inside the reported false-flag rate
indistinguishably from the marking rule's own error — an HK-026-shaped problem (the classifier could
not certify its own blind spots) layered under a metric that was supposed to be purely mechanical.

## 3. What is NOT blocked, offered but not executed

**ROW 0b** (identifiability — share of real decodes with a grid present *and* a resolved prefix) needs
neither continent nor CQ-zone nor entity-square logic — only grid-token *presence* (a Maidenhead
pattern match, no lat/lon conversion) and prefix *resolution* (the real, portable `TryMatchPrefix`
above). It is genuinely independent of §2's blocker and could be run today.

🛑 **Not run, on purpose.** The "seven live corpora" backing §1's 241k/21,242 figures are not pinned
down by any committed manifest — I could not find a script or file list identifying exactly which
seven `OpenWSFZ ALL.TXT` sessions were used (checked `qa/ARTEFACT_INVENTORY.md`, grepped the whole
tree for the figures). Re-deriving ROW 0b against a self-selected corpus set I assembled myself risks
quietly producing a *different* population than §1's established one, which is the same
two-instruments-disagreeing failure mode as §2, just smaller. I'm handing this back with the corpus
list unresolved rather than picking one myself and reporting a number against an uncited population.

## 4. Recommendation (not a ruling — Architect's and PO's per HK-015)

Options, none chosen here:

1. **Retire R-ENT permanently** as unsatisfiable from this project's data model (not merely
   "unbuilt") — the source format it would need doesn't carry entity coverage at any resolution.
2. **For R-CONT/R-CQZ, decide whether to commission a geo-classifier as its own instrument-building
   task**, with its own pre-registration — including a validation step for the classifier itself
   before it's allowed to feed a false-flag-rate measurement. This is materially more than "offline
   analysis of data already on disk"; it is new capability with an unmeasured error surface.
2b. **Or resolve the scope draft's flagged ambiguity explicitly**: if nearest-centroid classification
    (using the source's discarded per-entity point) is an acceptable construction, name it as a fourth
    candidate, accept that it requires either a live network fetch or a small `src/` change to stop
    discarding `Latitude`/`Longitude`, and pre-register it as such — not folded silently into R-CONT/
    R-CQZ's existing wording.
3. **Pin down the seven-corpora manifest** (or accept a freshly-assembled, disclosed list) so ROW 0b
   can run independently of whichever of the above is chosen — it bounds the ceiling before any
   classifier-building effort is spent.

## 5. NFR-021 / housekeeping

No real callsigns, grids, or per-record data appear above — every figure is a count already public in
prior committed reports, or a code citation. `C:\Users\Frank\AppData\Roaming\OpenWSFZ\callsign-regions.json`
is cited by path only (personal-machine location, outside the repo, not copied in). No `src/`/`native/`
change. HK-016 gather-artefacts step not applicable — no run occurred, no artefacts produced.

---

**QA, 2026-09-05 16:27 UTC.** Pre-registered spec `1605` STOPPED before ROW 0a for all three
candidates. Awaiting Architect adjudication before any further `FP-MARK` work.
