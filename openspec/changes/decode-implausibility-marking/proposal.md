**User-facing:** yes

---

# 🛑 WITHDRAWN — NOT IMPLEMENTED, NOT TO BE APPLIED (PO-ruled 2026-09-05)

**Nothing in this change was built.** No `tasks.md` was ever authored; no Developer session ran; no
`src/` line was written. **The requirements in `specs/**` describe a capability that DOES NOT EXIST
and must never be folded into `openspec/specs/`.**

**Why it was withdrawn — measured, not assumed.** Two pre-registered arms tested seven candidate
predicates for the marking rule:

- **`FP-MARK`** — the geographic set (R-CONT / R-CQZ / R-ENT) was **unsatisfiable**: no
  `grid → region` classifier exists in this project, and the one independent validation reference
  (`ADIF.log`) is **76.9% concentrated in five grid fields** — flat exactly where the observed false
  positives land (HK-026). R-ENT retired; R-CONT/R-CQZ suspended.
- **`FP-MARK-2`** — the no-new-instrument set: **R-UNALLOC and R-SUFFIX both failed their
  sensitivity control** (25.9% / 21.1% against a 40% bar, post-`f-002` scoped). **R-HASH cleared its
  false-flag band and was still rejected on base-rate arithmetic**: it marks 16.7% of FPs against
  7.63% of real decodes — a **likelihood ratio of 2.19×** and a **badge precision of 2.2–16.0%**,
  i.e. **6 to 46 badges shown per true false positive caught**. R-SOLO is 2.15×.

⇒ 🛑 **No cheaply-available feature separates false positives from real traffic well enough to mark
on.** A badge that wrong trains the operator to ignore it, which is worse than no badge.

**What was NOT withdrawn, and must not be read as dismissed:**

- The **hash-addressed FP class is real** — 29.2% of labelled FPs carry a hash reference, 12/21 in
  the **addressee** slot — and remains an accepted **High**-severity defect
  (`DEFECT-twelve-bit-hash-misresolution.md`). This change simply is not its remedy.
- **Option B** (importing public-domain boundary data to build a real grid classifier) remains
  available and un-tried. It is the only route that ever looked strong on sensitivity; its
  false-flag rate is unmeasurable without the import.
- The **`SuppressUnknownRegion` pricing arm** was commissioned in the same ruling and is unrelated to
  this change — it prices an **already-shipping suppressor**, not a proposed marker.

**Rulings:** `qa/rr-study/2026-09-05-1640-architect-to-qa-ruling-fp-mark-row0-block.md` ·
`qa/rr-study/2026-09-05-1850-architect-to-qa-ruling-fp-mark-2-adjudication.md` (§5 option 1,
PO-ratified 2026-09-05).

🔴 **Everything below this banner is the original proposal, retained as the record of what was
designed and why. It is history, not intent.**

---

## Why

Decoder false positives are not evenly shaped, and the decode panel currently presents them exactly
like real traffic. On the 2026-09-05 `S5-STANDALONE` run the operator observed six FPs that were
visually obvious as noise — and the measurement bears that out: of the **72** labelled S5 FP decodes
on record, **51 (70.8%) carry both a plain callsign and a grid**, and every one of the six inspected
carried a grid **geographically impossible for its own callsign** — three placed North-American or
Indonesian stations in **Antarctica**, one put a Saudi station 172° of longitude away.

This is detectable without touching the decoder. The grid and the callsign both already cross the
native boundary in `FT8Result`, and prefix→region resolution already exists (it fills the panel's
REGION/DXCC/CQZ/ITZ columns). **The check is categorical — the grid either falls inside the entity
the prefix resolved to or it does not — so it introduces no threshold and no tunable parameter.**

The mechanism the operator originally proposed — suppress a suspicious decode until a second sighting
corroborates it, then delete it after a timeout — was measured and **partly refuted**:

- ✅ **The corroboration premise holds:** across the 72 labelled FPs, **0 of 161 distinct FP callsign
  tokens ever repeat**. A CRC-14 coincidence redraws a 77-bit payload; it does not recur.
- 🔴 **But it cannot be a general policy: 46.6% of 21,242 real distinct callsigns** across seven live
  corpora are heard **exactly once**. Corroboration-gating would hold roughly half of all genuine
  stations.
- 🔴 **And deletion destroys its own audit trail** — a quarantine that deletes cannot be measured for
  false-suppression, and the loss concentrates on rare DX (`/P`, `/M`, `/MM`, DXpeditions) whose
  operators legitimately transmit from far outside their prefix's home entity.

**PO ruling, 2026-09-05:** mark, never delete; "dismissed" instead of delete; a settings toggle to
show or hide marked decodes.

## What Changes

- **Adds a new capability, `decode-implausibility-marking`** — a pipeline stage that *annotates* a
  decode as geographically implausible **without removing it**. Marking is not suppression: a marked
  decode is still broadcast, still rendered, still automation-eligible (see the Phase-1 boundary
  below).
- **Adds a decode-panel visual marker** for marked decodes, and a **`Dismissed` state** reachable by
  operator action or by age-out. 🛑 **A marked decode is never deleted** — `Dismissed` hides it from
  the default view while it remains counted and retrievable, and `ALL.TXT` is untouched throughout.
- **Adds one persisted setting** — show or hide marked decodes in the panel — alongside the existing
  `decode-noise-suppression` controls on the settings page, following that capability's established
  interactive/persisted pattern.
- **Modifies `decode-noise-suppression`** only to fix **composition and ordering** between the
  existing suppression rules, this new marking stage, and the ephemeral `decode-panel-filtering`
  column filter, so the three cannot interact ambiguously.

## Phase-1 boundary — deliberately drawn, and it is the safety property

🛑 **This change does NOT make a marked decode ineligible for QSO automation.** Marking is
display-and-state only.

That boundary is what makes the change safe to implement **before** the rule's false-flag rate on
real traffic is known: a visual badge costs nothing if the rule is noisy, whereas automation
suppression at an unmeasured false-flag rate could silently cost genuine contacts — concentrated,
per the cost analysis, on exactly the rare DX worth most. Whether marked decodes should also become
automation-ineligible is **deferred to a separate Phase-2 change**, gated on the measured rate.

## Preconditions

1. 🔴 **`FP-MARK` must report first** (`qa/rr-study/2026-09-05-1605-architect-to-qa-spec-fp-marking-rule-validation.md`).
   Three candidate predicates — **R-CONT** (continent), **R-CQZ** (CQ zone), **R-ENT** (DXCC entity
   square set) — are pre-registered together with all their rates reported. **The PO picks one from
   the published trade-off table.** `design.md` D2 records the predicate as this change's single open
   parameter; **the change must not be applied before that pick is made.**
2. **`tasks.md` is QA's to author** (HK-015), inside this change, on the PO's explicit direction to
   use OpenSpec rather than a standalone `dev-tasks/*.md`. This change ships `proposal.md`,
   `design.md` and `specs/**` only — `openspec validate --strict` passes without a `tasks.md`.
3. **HK-011:** a separate Developer session runs `opsx:apply`; the Captain reviews the diff pre-push.

## What this explicitly does not do

- 🛑 **It does not address the hash half of the FP population.** **29.2%** of labelled FPs carry a
  hash reference and **12 of 21** put it in the addressee slot — the shape `QsoAnswererService` reads
  as "calling me". There is no prefix there, so no region, so **no contradiction to detect**. This
  rule is *blind* to that class, not merely weak, and ROW 4 of `FP-MARK` reports the coverage ceiling
  (~71%) so it cannot be forgotten.
- 🛑 **It does not address the severe case** — an FP resolving by 12-bit collision to this station's
  own callsign (`DEFECT-twelve-bit-hash-misresolution.md`, accepted, High). **0 of 241,000 decodes
  across all live corpora name `PD2FZ`**, so own-call h12 residency has never occurred and every
  corpus we own has **structural exposure zero** — an exposure of zero, not an absence (HK-021(j)),
  and HK-026 forbids reading those corpora as reassurance.
- 🛑 **It changes no decoder behaviour, no native code, and no ABI.** No `FT8_SHIM_VERSION` bump.
  Both inputs already cross the boundary in `FT8Result`.
- 🛑 **It does not alter `ALL.TXT`**, preserving `decode-noise-suppression`'s Decision 1 — which is
  also what keeps the S5 AWGN FP metric (a metric with **no established baseline**, guard (e))
  unmoved by this change.
