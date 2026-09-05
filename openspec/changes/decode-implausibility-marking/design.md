# Design — `decode-implausibility-marking`

## Context

The decode pipeline already has two operator-controlled stages between the decoder and the panel:

- **`decode-noise-suppression`** — persisted, *removes* decodes (unknown region, R&R synthetic),
  evaluated upstream of the WebSocket broadcast and of `QsoAnswererService`/`QsoCallerService`
  eligibility. `ALL.TXT` never affected (its Decision 1).
- **`decode-panel-filtering`** — ephemeral column filter (`DecodeFilterState`,
  `DecodeFilterEvaluator`, `IDecodeFilterStore`), evaluated after suppression.

This change inserts a third stage with **different semantics from either**: it annotates without
removing. That distinction is the whole design, and D1 exists to keep it from eroding.

---

## D1 — Marking is a new capability, not a third suppression rule

**Decision:** add `decode-implausibility-marking` as its own capability rather than a third rule
inside `decode-noise-suppression`.

**Why.** `decode-noise-suppression`'s Purpose and its every Requirement are written around *removal*
("SHALL NOT be broadcast", "SHALL NOT be included in the batch"). Marking's default outcome is the
opposite: the decode **is** broadcast, **is** rendered, and **is** automation-eligible; it merely
carries an annotation. Folding an annotate-by-default rule into a capability whose contract is
remove-by-default would make the composite contract unreadable, and would invite a later change to
"simplify" marking into suppression without noticing it had crossed the Phase-1 boundary.

**Alternative rejected:** extending `decode-noise-suppression` with a `Mark` mode. Cheaper in files,
but it puts a display concern and an eligibility concern behind one setting — precisely the conflation
this design is trying to prevent.

---

## D2 — 🔴 The predicate is this change's ONE open parameter

The rule flags a decode when its grid is geographically inconsistent with the entity its callsign's
prefix resolves to. **Which construction of "inconsistent"** is not decided here:

| ID | Flags when… | Sensitivity on the six inspected FPs *(illustration, not a result)* |
|---|---|---|
| **R-CONT** | grid's continent ≠ prefix's continent | 4/5 — a VK6 call with a PNG grid stays inside OC |
| **R-CQZ** | grid's CQ zone ≠ prefix's CQ zone | 5/5 |
| **R-ENT** | grid square ∉ the DXCC entity's square set | 5/5 |

**All three are categorical and carry no tunable parameter** — no distance, no threshold — per the
PO's constraint that the feature introduce no threshold.

🛑 **`FP-MARK` measures all three and reports all three rates. The PO picks one from that table.
Selecting the candidate with the best number after seeing the numbers is HK-021(y) outcome-selection
in a new costume and is forbidden.** Until the pick is made this change must not be applied.

**Fixed here so it cannot drift:** Maidenhead decode — char 0 = longitude field, 20° per step from
180°W; char 1 = latitude field, 10° per step from 90°S; digits = 2°/1° squares; use the **square
centre**.

**Undefined-input contract (all candidates):** a decode with no grid, or with a prefix the region
store cannot resolve, is **NOT marked**. Marking requires positive evidence of contradiction, never
absence of evidence — "unresolvable" is already `decode-noise-suppression`'s territory, and
overloading it here would double-count the same decode against two different controls.

---

## D3 — `Dismissed` is a state, never a deletion

**Decision:** a marked decode moves `Marked → Dismissed` by operator action or by age-out. **It is
never removed from the record.**

**Why, and this is the load-bearing argument.** A quarantine that deletes its own contents cannot be
audited: with the evidence destroyed there is no way to ever measure the feature's false-suppression
rate, and no way to tune it. That is a self-inflicted instance of the HK-026 problem this project
already guards against elsewhere — an instrument that cannot observe its own blind spot. Retaining
dismissed decodes keeps the feature measurable after it ships.

The cost of getting it wrong is not evenly distributed: **46.6% of real distinct callsigns are heard
exactly once**, so anything that removes a genuine decode likely removes the only chance at that
station — and the marked population is enriched in `/P`, `/M`, `/MM` and DXpedition operators, who
legitimately transmit from grids far outside their prefix's entity. `FP-MARK` ROW 3 measures that
concentration.

`ALL.TXT` is untouched in every state, preserving `decode-noise-suppression` Decision 1 — which is
also what keeps the S5 AWGN FP metric unmoved (guard (e): there is still **no established baseline**,
so a change to that metric would be undetectable).

---

## D4 — Stage ordering, and staying off the live-verification path

**Order:** `decode-noise-suppression` (remove) → **`decode-implausibility-marking` (annotate)** →
`decode-panel-filtering` (ephemeral column filter).

**Rationale:** a decode already suppressed is gone and must not be marked (no marker for something
never shown). The ephemeral column filter stays last so it composes with marking exactly as it
already composes with suppression.

⚠️ **The show/hide setting is a *rendering* control, not a pipeline stage.** When "hide marked" is
enabled the decode is still broadcast and still automation-eligible; only its presentation changes.
This keeps the setting off `QsoAnswererService`/`QsoCallerService` eligibility entirely.

🔴 **Verify, do not inherit:** this ordering is *intended* to avoid touching `DecodeFilterState`,
`DecodeFilterEvaluator`, `IDecodeFilterStore` and the `QsoAnswerer`/`QsoCaller` filtering hook. **If
implementation touches any of them, the `decode-panel-filtering` live-verification policy applies** —
`qa/decode-filter-synth-verify/live_verify_9_axes.py` must be re-run against a real isolated daemon
before merge with its auto-generated report committed. Confirm mechanically which files the diff
touches; do not assume this design succeeded.

---

## D5 — No decoder change, no ABI change

Both inputs — message text (carrying the grid) and the callsign — already cross the native boundary
in `FT8Result` (`freq_hz`, `dt`, `snr`, `message[36]`; 48 bytes). Region resolution is existing
managed code. **No `FT8_SHIM_VERSION` bump, no struct-layout change, no native edit**, so
`Ft8NativeResult.ExpectedNativeSizeBytes` and the ABI self-test are untouched.

This matters beyond tidiness: `FT8_SHIM_VERSION` has a live renumbering conflict
(`20260051`/`20260052` reserved, `20260050` taken by L3), and a shim bump here would collide with it
for no benefit.

---

## Open questions

1. **The predicate (D2)** — resolved by the PO's pick from `FP-MARK`'s trade-off table. **Blocking.**
2. **Age-out interval for `Marked → Dismissed`** — the PO said "older than XX minutes" without fixing
   XX. Proposed: operator-configurable with a conservative default, since the cost of dismissing late
   is nil while dismissing early hides a real station. **Non-blocking**; QA to fix a default in
   `tasks.md`.
3. **Should `Dismissed` be reversible from the UI?** Recommended yes (an "undismiss"/show-dismissed
   view), consistent with D3's audit argument. **Non-blocking.**
4. **Phase 2 — automation ineligibility for marked decodes.** Deliberately out of scope; gated on
   `FP-MARK` ROW 1's measured band. Do not smuggle it in here.
