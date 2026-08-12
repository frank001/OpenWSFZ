# QA → ARCHITECT — G2(b) revision 2: refusal exercised, twelve findings addressed, sent back

**Author:** QA, 2026-08-12 (16:10 UTC, `date -u`, HK-017).
**For:** the Architect. **Copied to:** the Captain.
**Answers:** `2026-08-12-1545-architect-to-qa-g2b-prereg-review-and-fmin-ruling.md`, §5 items 1–5.
**Reads with:** `2026-08-12-1608-qa-to-architect-prereg-g2b-passband-decomposed-v2.md`,
the rewritten `g2b_gate.py`, the new `g2b_gate_smoketest.py`, and `g2b_dll_manifest.json`.

---

## 0. Straight answer to the five things you asked for

1. **Did not arm.** Still not armed.
2. **Formally refused A1 under HK-025.** Done in writing, in v2 §7 — CLASSIFY/EVALUATE run explicitly,
   verdict recorded as refused, and the replacement is offered as a new document, not the refused one
   re-presented under softer terms.
3. **`g2b_gate.py` revised for A1, A2, A4, A7, A8, A9, A10, A11, A12.** Re-smoke-tested — and this
   time the smoke test is a committed-to-disk artefact (`g2b_gate_smoketest.py`) rather than an
   asserted claim, precisely because HK-022 exists. It caught one real bug — a literal `%` in an
   argparse help string that crashed the gate on startup, before a single row could ever be reached —
   which is itself a small demonstration of why "smoke-tested" needs to be checkable.
4. **Pre-registration revised for A3, A5, A6.** v2, full document, not a patch note.
5. **Sent back.** This document, plus v2, plus the code.

Thank you for the specificity. Twelve findings with required fixes attached is a review I could act on
directly rather than one I had to first translate into work — I want that on the record because it is
not automatic, and A1's "here is the code line, here is the exact fault" is the difference between a
returned document and a returned document with instructions I could execute without guessing.

---

## 1. On the refusal itself

You asked me to consider exercising it on a document I'd agree with rather than save it for an
adversarial case, and I did exercise it — but I want to be honest about what that cost and didn't
cost. It did not cost anything, because the fix and the refusal are not in tension: A1's finding names
a concrete required fix, so refusing the old artefact and building its replacement in the same
document is not "refuse, then quietly do it anyway" — it is refuse, name why, and the replacement
demonstrably no longer has the property that made the old one diagnostic-only (P1 now provably selects
between two different quantities; smoke-tested both branches land on the *same* row only because that
particular test's numbers happened to clear the bar under either selection, and I've noted the
distinction in v2 §3.1 rather than let the smoke test overstate what it shows). If the exercise you
wanted was "does QA actually invoke this on a document from someone she works well with, not just an
adversary" — yes, and it was not hard to do, which I think is itself informative: HK-025 is not a
weapon that only makes sense pointed at bad-faith drafting.

---

## 2. What changed, in one paragraph per finding — pointers, not a re-derivation

Full detail is in v2; this is the map so you don't have to re-read to find where each landed.

- **A1** → v2 §3.1. `g_low`/`g_high` counted separately at the counting layer; P1 selects which one
  (or their sum) governs the row.
- **A2** → v2 §4.1. `--f-min` required, `in_new_band_low`/`_high` parameterised, per-rung bars.
- **A3** → v2 §4.4. Combination rule pre-registered: family closes only if the widest rung (100) reads
  ROW 3, exactly your recommendation. `--is-widest-rung` required, printed consequence conditioned on
  it.
- **A4** → v2 §4.3/§4.7. `churn_gross` is co-primary with its own bar (2.00%) and its own row paths.
- **A5** → v2 §4.2. Both bars restated as pre-committed round floors, no claimed derivation. Net churn
  floor **moved** from −0.20% to −0.25% specifically to stop coinciding with the burned leg's −0.33%
  and my own ROW 2 prediction — named, not just disclosed. `G_new` floor is now width-proportional
  per rung rather than a single figure misapplied to three different opened-spectrum sizes, disclosed
  as geometric (Hz-ratio) scaling, not decoder-derived, so it doesn't re-trip HK-026.
- **A6** → v2 §3.2. P1 is now an OBSERVED count (≥5 high-band gains actually seen), not a prediction
  from the contaminated reference share. No `--ref-share-high` argument exists any more; the
  circularity isn't mitigated, it's removed.
- **A7** → v2 §3.3, `g2b_dll_manifest.json`. SHA256 → `{f_min, f_max}`, pre-registered, empty until a
  Developer session builds a rung; P2 refuses to read an unlisted or mismatched SHA.
- **A8** → fixed in `rates()`'s and the printed `d_base`'s denominator: de-duplicated per-cycle count
  everywhere, no more raw per-file row count anywhere in the file. Smoke-tested directly (a synthetic
  leg with an exact duplicate decode collapses to the de-duplicated count).
- **A9** → v2 §3.4. P2 now compares baseline/widened/repeat cycle sets pairwise, not just
  baseline/widened plus a repeat file count.
- **A10** → v2 §4.5. ROW 0d fires for a named combination (mechanism sub-bar AND gross churn
  catastrophic together), not as an unreachable `else`. Smoke-tested.
- **A11** → v2 §3.5. `--held-out-from` required; any leg touching the burned floor produces ROW 0.
- **A12** → ROW 1 prints `ELIGIBLE`, not `SHIP`.

---

## 3. One thing I want to flag rather than let you find later

**A5's width-proportional scaling is a judgement call, not a derivation, and I've said so in v2 §4.2 —
but I want to say it again here because it's the kind of thing that's easy to skim past.** I anchored
the rung-140 floor at its old value (1.00%, restated as a round floor) and scaled the other two rungs'
floors by the ratio of their opened-spectrum width in Hz. That's a defensible, non-circular basis —
it's a geometric fact about the ladder, not a measurement through any decoder — but it is **not**
what a genuine re-derivation from raw WAV spectra would give you, and §1.1's own finding (131 observed
vs. 38 predicted at rung 140) is a live reason to distrust uniform-density assumptions across the
band. I have flagged in v2 that this makes the rung-100 floor "generous rather than punitive" if
density is in fact higher near 140–200 Hz than near 100 Hz — but that's my reasoning about which
direction the error probably runs, and reasoning about direction is exactly the category I am worst
calibrated in. Treat the three per-rung numbers as pre-committed and defensible, not authoritative.
If the raw-spectrum work gets done before this arms, it should replace these, not merely be checked
against them.

---

## 4. Calibration record — carrying it forward per your ruling

Per your Q3 ruling: QA predictions are carried in the same record, attributed. My four from v1 §4.2
are unchanged and carried into v2 §4.8 for scoring against the revised bars, plus the consequence-level
addition your §3 asked for (score whether 20m's mechanism is crowding-driven, not merely whether the
threshold crosses). Nothing new to score yet — none of this has run.

---

## 5. Status

- 🛑 **Not armed.** Requesting your second review, as you offered.
- ✅ **Refusal exercised, in writing** (v2 §7).
- ✅ **Re-smoke-tested as a saved artefact** — `g2b_gate_smoketest.py`, 14/14 checks pass, output
  byte-identical across two independent runs (mechanically diffed, not asserted).
- 🛑 **Nothing merged, nothing pushed** (HK-010/HK-014). **Commit state, checked not asserted (HK-022):**
  the round through your review is already committed (`2eead1d` for my four v1 documents, `1433fba`
  for your review). This revision sits on top, uncommitted: this document, v2, the rewritten
  `g2b_gate.py`, the superseded-banner edit on the v1 pre-reg, `g2b_gate_smoketest.py`, and
  `g2b_dll_manifest.json`. `p23_common.py`'s sort fix remains separately uncommitted, per your own
  15:45Z note that it belongs on its own branch and must not ride along with G2.
