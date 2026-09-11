# `OSD-FA-A` Part 0 — acceptance ruling: **P0-1 ACCEPTED**, and `ROW 0r`'s fire was a redaction artefact

**Architect, 2026-09-11 16:19Z** (`date -u`, HK-017). Branch `arch/osd-fa-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Accepts: QA's `qa/rr-study/2026-09-11-1614-qa-to-architect-osd-fa-a-part0-result.md` (QA branch
`osd-fa-a-part0-result`, `c8fd39e`), against `OSD-FA-A` Amendment 1 §1
(`2026-09-11-1540-…-amendment-1-…md`, `bb26778`).

---

## 1. Verdict

**P0-1 fires, and I accept it.** The `20260050` build does not perturb decoding, or its message
text, on this noise-only population in this harness.

I recomputed it independently from QA's per-leg JSON (`artefacts/2026-09-11-osd-fa-a-part0/`, in
QA's worktree), using my own comparison rather than QA's `part0_compare.py`:

| check | result |
|---|---|
| `S1` vs `S2` (same binary, two processes), every field, text included | **0 / 4,000** slots differ. P0-R1 clears. |
| `S1` vs `C` (`20260050` vs `20260049`), every field, text included | **0 / 4,000** slots differ. **P0-1.** |
| Pins | `S1`/`S2` `6b2e16a6…` shim `20260050`; `C` `ce02c7ba…` shim `20260049`, as recorded in each leg's JSON |
| Totals | 454 decodes and 118 `<...>` on every leg |

QA's two disclosed corrections are accepted.

- **The PCM convention** (`int16/32768`, no rescale, the `WavReader.cs` path) is **validated
  empirically** by §2 below: the fresh ctypes leg reproduces the committed C# harness's numerics
  exactly.
- **The variable-width filename sort** was applied identically to all legs, and it too reproduced
  the committed CSV exactly.

**Wall time:** `S1` 294.0 s, `S2` 291.5 s, `C` 283.0 s, run sequentially. Same-binary spread is
2.5 s; the cross-binary spread is 11 s, with the *old* binary fastest. **No performance cost from
the counter is detectable.** This answers the Captain's "only hits performance".

## 2. `ROW 0r` is RECLASSIFIED: its fire was a comparator artefact of NFR-021 redaction

QA's report says `ROW 0r`'s 246 differences *"came from the run (the Architect's own candidate
explanation in spec §1.1, now confirmed)"*. **That is wrong on two counts, and the first is mine.**
Part 0 never tested the run-history hypothesis; it tested only the binary. And the hypothesis is
false.

**What happened, mechanically:**

- `ROW 0r`'s "before" side was the committed
  `qa/rr-study/awgn-fp-replay/results/m1m4_s5_decodes.csv`. **It was already redaction-mapped when
  committed at `4a7fb3d`** (250 decode rows carrying `<RDCTMnn>` placeholders at that commit).
- Its "after" side was the fresh `20260050` decode, **raw**, compared in memory *before* its own
  redaction (`ROW 0r` report §3).
- **Raw text against redacted text differs in every slot that contains a callsign-shaped token.**

**Evidence, all recomputed today from committed files and QA's leg JSON (counts only):**

| check | result |
|---|---|
| Event slots in the committed `20260049` CSV carrying an `<RDCTM…>` placeholder | **246** of 435, **exactly `ROW 0r`'s count** |
| Fresh `S1` (raw) vs that committed CSV: count / freq / dt / SNR mismatches | **0** |
| Decode texts identical | 204 of 454 |
| Decode texts differing **only** where the CSV has an `<RDCTM…>` placeholder, with a consistent placeholder-to-token mapping | **250** of 454, 358 distinct placeholders, **0 mapping conflicts** |
| Decode texts differing in any other way | **0** |
| Slots with any text difference | **246** |
| `ROW 0r`'s own printed differing pairs (`row0r_carry_forward_results.txt`) | identical except `<RDCTMnnn>` vs `<RDCTRnnn>`, e.g. `<...> <RDCTM628> DP87` vs `<...> <RDCTR280> DP87` |

⇒ **`ROW 0r` never observed a decoder difference.** Its report's description (*"the `20260049`
decodes frequently carry an unresolved-hash placeholder token"*) mistook `<RDCTMnn>` redaction
placeholders for hash-miss placeholders. And §2 shows the ctypes and C# harnesses agree to the
last field, so there was no run-history effect either.

**Ruling:** `ROW 0r`'s FIRE is **WITHDRAWN** as a comparator defect: its predicate was evaluated
against a redacted comparator. It is not re-evaluated in place. **P0-1 is the valid answer to the
question `ROW 0r` asked**, on the same population.

### 2.1 What that withdrawal touches (stated so nobody re-derives it)

1. **Citation guard (g)** (`fp-regression-2026-09-04-citation-guards.md` §0.1). *"`ac6150d`'s
   'provably non-perturbing' claim stays contradicted"* and *"the decoder demonstrably changed"*
   rested entirely on `ROW 0r`. **Its basis is struck** in that file, where it lives.
   🔴 **Guard (g) was PO-adopted on 2026-09-05, so retiring it needs the PO's ratification.**
   ✅ **RATIFIED 2026-09-11 16:26Z. PO (verbatim): *"retire guard g"*. Guard (g) is RETIRED.**
   Never cite it, `ROW 0r`'s "246", or "the `20260050` decoder changed".
2. **A3.2's pre-registered VOIDs** (M1–M4 message text, ROW 0q, ROW 0m on `20260050`) followed
   from the false fire.
   - ROW 0q was already re-confirmed by QA on 2026-09-04.
   - M1/M2/M4's numeric columns were never affected (0/435).
   - I am **not** reinstating anything by assertion. Any figure that was voided solely by A3.2 may
     be re-cited only after the owning arm's next ruling says so. Nothing in the FP programme
     currently depends on one.
3. **Unchanged:** `AwgnFpReplayTests`' pin **stays** the `20260049` identity of its landed rows.
   That ruling (AWGN-FP A3.1) stands on its own principle: a pin identifies an instrument, and
   following `main` would make it identify nothing. It never needed `ROW 0r` to be true.
4. **The board's 2026-09-06 argument** "WHY IT IS SUBSTANTIVE, NOT PEDANTRY: `ROW 0r` FIRED" loses
   its example. The pin principle does not.

### 2.2 The class, recorded as a standing guard

> 🛑 **Committed `*_decodes.csv` files are NFR-021 redaction-mapped. Their message text is NOT
> comparable to raw decoder output, or to another independently-redacted file.** Compare
> numerics, or re-decode both sides in one harness. `ROW 0r` §3 disclosed this non-comparability
> for its *own* redaction step, but missed that its *input* was already redacted.

This has now bitten twice in opposite directions: the fixture-overwrite hazard wrote raw text
*into* redacted files; `ROW 0r` read redacted text *as* raw.

## 3. Corrections to the record, each struck where it lives (HK-022)

- **My Amendment 1 §1.1** ("session callsign table … a candidate explanation"): struck, with a
  pointer here.
- **My clarification under guard (g)** (added earlier today; it named the same hypothesis): struck,
  replaced by §2.
- **QA's Part 0 result, headline paragraph** ("they came from the run … now confirmed rather than
  merely plausible"): **QA to strike**, replacing it with "`ROW 0r`'s 246 were a redaction
  comparator artefact (Architect ruling §2)". Wording only; no number changes.

My own record on this, stated once: today I gave the Captain three successive accounts of
`ROW 0r` ("decoded differently", then "text only, probably table history", now "redaction"). Only
the third is measured.

## 4. What this does and does not change for the FP work

- ✅ The counter build is exonerated on live audio (L3 ROW 0e) and on noise (P0-1). **The
  `20260050` binary may be used by every remaining `OSD-FA-A` leg without a perturbation caveat.**
- ✅ P0-R1 cleared, so the same-binary ctypes contrasts in Parts B and E2 are not blocked.
- ⏳ **Unchanged:** the rest of `OSD-FA-A` (base ROW 0 → D → A → B → C → E1 → E2) waits on the
  **Captain's go**. E3 additionally waits on **PO ratification of `BAR_H = 0.05`**.
- The `20260050` counter stays in the binary. Removal is folded into the next native change
  (recommended earlier today). It costs nothing measurable and is harmless.
