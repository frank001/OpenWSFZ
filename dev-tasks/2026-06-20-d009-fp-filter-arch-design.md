# D-009 OSD False-Positive Filter — Architectural Design

**Date:** 2026-06-20
**Author:** Architect
**Companion to:** `dev-tasks/2026-06-20-d009-fp-filter-arch-review.md` (QA review)
**Defect:** D-009 — OSD false-positive callsign filter
**Status:** Design proposed; supersedes the calibration-loop approach in
`dev-tasks/2026-06-20-d009-fp-filter-r4.md` Action 3.

---

## 1. Decision summary

The R4 handoff (Action 3) instructs the developer to keep stepping `OSD_CORR_THRESHOLD`
until S5 shows 0 FP. The architectural review has already shown this loop terminates at
AC11 ("calibration ceiling reached, stop and report"): AC5 (0 FP on S5) needs ≥ 0.40,
AC6 (S7 not regressed) needs ≤ 0.35. **There is no value of a single `corr/norm` threshold
that satisfies both.** Continuing the R4 calibration loop is therefore wasted effort.

This document replaces the "keep tuning the one knob" strategy with a layered design whose
primary fix is a **second, orthogonal native discriminant** (`nhard`), and which defers the
ABI-breaking struct change behind a measurement gate.

---

## 2. Root-cause reframing

Two problems are conflated in the current investigation:

- **P1 (statistical, native):** OSD manufactures CRC-14-valid codewords from pure noise.
  In pure noise BP fails on (almost) every candidate, so OSD runs on (almost) every
  candidate; each OSD call explores up to 529 trial codewords, each given a CRC-14 check
  (P ≈ 529 / 16 384 ≈ 3.2 % of finding *some* false hit per candidate). Over ~140 noise
  candidates this approaches certainty — hence the 75 % slot FP rate at threshold 0.10.

- **P2 (plumbing, C#):** `IsPlausibleMessage` cannot safely reject `/P` / `/R` 3-token
  messages because the same text string is a false alarm when OSD-derived and valid traffic
  when LDPC-derived. The filter lacks the decode-origin bit.

The review's three paths all address **P2** (or, in Path 3, dodge it). **None address P1.**
P1 is *why* the threshold is ceilinged, and P1 is the only thing that can touch Category E.

### Why one threshold cannot work

`corr/norm` is **magnitude-weighted** (`corr = Σ hard_pm1·llr`, `norm = Σ|llr|`). It conflates
"is this a real codeword?" with "how strong is the signal?":

- A genuine **−27 dB** decode has tiny `|llr|` everywhere → low `corr/norm` → indistinguishable
  from noise on this axis.
- To clear the noise population you must raise the threshold into the genuine population →
  the observed S7 P0 collapse 85 % → 57 % at 0.40.

This is structural. No amount of tuning the same statistic escapes it.

---

## 3. The lever: hard-decision Hamming distance (`nhard`)

The discriminant WSJT-X uses for exactly this purpose (`nharderrors`, `osd174_91.f90`) is the
**Hamming distance between the OSD codeword and the channel hard decisions**:

```
hd[i]  = (llr_for_osd[i] > 0) ? 0 : 1      // channel hard decision (matches the existing
                                           // hard_pm1 sign convention in the corr gate)
nhard  = Σ_i [ plain174[i] != hd[i] ]      // 0..174
```

- **Genuine signal:** the reliable bits are mostly correct; OSD re-encodes from them and fixes
  only the residual errors → codeword is Hamming-*close* to the channel (**small `nhard`**),
  *independent of SNR*. This is the crucial property the `corr/norm` axis lacks.
- **Noise false alarm:** there is no underlying codeword; OSD lands on a random CRC-14
  coincidence → Hamming distance ≈ 87 (half of 174).

`nhard` is:
- **orthogonal** to `corr/norm` (integer count, magnitude-independent),
- **free** — `plain174[]` and `llr_for_osd[]` are already in scope at *both* OSD gate sites
  (`ftx_decode_candidate` ~line 628 and `ftx_decode_candidate_ap` ~line 800 in
  `native/ft8_lib_build/patched/ft8/decode.c`),
- the **only** axis that can suppress Category E (structurally-perfect noise FPs), which no
  text rule can reach.

A two-feature gate (`corr/norm` AND `nhard`) separates the two populations where one feature
alone cannot — and lets `corr/norm` stay at a low value (≤ 0.35) that preserves S7.

---

## 4. Layered design (defense in depth)

### Tier 1 — `nhard` gate in `decode.c`  *(primary fix; NO ABI change)*

Add an `nhard` rejection alongside the existing `corr/norm` test, at both OSD gate sites:

```
compute nhard from plain174 + llr_for_osd        // same loop that already computes corr/norm
if (nhard > NHARD_MAX) return false;              // new
if (osd_norm > 0 && corr/osd_norm < OSD_CORR_THRESHOLD) return false;   // existing, keep ≤0.35
```

- New `#define NHARD_MAX <calibrated>` near the existing `OSD_CORR_THRESHOLD` define.
- Calibrate `NHARD_MAX` empirically: genuine S7 OSD decodes should cluster well below it;
  S5 noise FPs cluster near 87. Pick a value in the gap (WSJT-X operates in the ~40–50 region,
  but **calibrate against our corpora, do not copy the constant**).
- `OSD_CORR_THRESHOLD` stays at **≤ 0.35** (whatever the highest S7-safe value is — likely
  back to 0.10–0.15, since `nhard` now carries the noise rejection).

**No struct change, no shim ABI break for Tier 1.** (A shim version bump is still appropriate
because decode behaviour changes — but it is not an ABI/layout change.)

### Tier 3 — global zero-FN text rules in `IsPlausibleMessage`  *(NO ABI change)*

Land regardless of Tier 1's outcome; safe for any decode origin:

- **Rule A:** reject single-token messages (`!text.Contains(' ')`) — no valid FT8 decode is
  ever a single token. (Closes Cat A; complements the existing hex-dump rule.)
- **Rule B:** reject 5+ token messages — currently fall through `if (spaces != 2) return true`.
  (Closes Cat B.)
- **Rule C:** reject `CQ <hash>` (`token0 == "CQ" && token1.StartsWith('<')`) — not a reachable
  FT8 form. (Closes Cat C.)

### Measurement gate — STOP here if it works

After Tiers 1 + 3, run S5 (≥ 100 slots — see §6) and S7 P0–P2.
**If S5 FP rate = 0 and S7 co_channel_sweep ≥ 89 % → ship. Do not implement Tiers 2/4.**
The ABI break is not paid unless measurement proves it necessary.

### Tier 2 — `is_osd` origin flag  *(ABI change; only if Tiers 1+3 leave residual FPs)*

This is the review's Path 1, demoted to second line of defense:

1. `decode.h` (patched copy): add `bool is_osd;` to `ftx_decode_status_t`.
2. `decode.c`: set `status->is_osd = true;` in the OSD success branch of *both*
   `ftx_decode_candidate` and `ftx_decode_candidate_ap` (right where `status->ldpc_errors = 0;`
   is set); ensure it is `false` on the BP-success path.
3. `ft8_shim.c` (~line 1225, the `FT8Result* r = &results[num_decoded++];` block): copy
   `status.is_osd` into the new result field.
4. `ft8_shim.h`: add `uint8_t is_osd;` to `FT8Result`. Layout becomes
   `int(4) + float(4) + int(4) + char[36] + uint8(1)` → padded to **52 bytes**. Update the
   header comment block.
5. `Ft8NativeResult.cs`: add `public byte IsOsdDerived;` after `Message`; update
   `ExpectedNativeSizeBytes` 48 → 52 and the layout doc comment.

Use `ftx_decode_status_t` (not a new out-parameter) so the flag rides the existing status
plumbing all the way to the result-build site.

### Tier 4 — OSD-origin-gated strict text profile  *(uses Tier 2; only if Tier 2 is taken)*

In `IsPlausibleMessage`, add an `isOsdDerived` parameter. When `true`, apply a stricter
profile to 3-token messages: reject `/P` and `/R` callsign suffixes (Category D). Because the
flag fires only on OSD output, valid BP-decoded portable QSOs are untouched → **zero FN for
non-OSD traffic.** This also resolves question 3 (`/R`) without a band-specific global rule.

`Ft8Decoder.cs` ~line 229 passes `nr.IsOsdDerived != 0` into the call. All
`IsPlausibleMessage` unit-test call sites gain the parameter (default `false` for existing
non-OSD cases).

---

## 5. Answers to the review's four questions (§9)

1. **ABI change acceptable?** Yes, but **deferred**. Take the 48→52 byte bump only if the
   measurement gate after Tiers 1+3 shows residual FPs. Do not pay it speculatively.

2. **Path 2 SNR boundary?** **Reject Path 2.** It mis-models the defect: the co-channel
   decodes OSD was introduced to rescue sit at **~0 dB**, not low SNR, so an SNR gate would
   fail to protect them while maximally endangering genuine weak `/P` decodes below −21 dB.
   If ever forced, −24 dB conservative — but the flag (Tier 2) is strictly better.

3. **`/R` unconditional?** **No global band-specific rule.** Fold `/R` and `/P` into the
   OSD-origin-gated Tier 4 rule: identical FP coverage on the corpus, zero FN, no band coupling
   inside a band-agnostic decoder.

4. **Category E tracking?** **Yes — formal residual risk (track as D-009-E).** Tier 1
   (`nhard`) is the only lever that touches it. Additionally, **AC5 as written ("0 FP on 12
   slots") is statistically under-powered** — it does not bound P(FP). See §6.

---

## 6. Acceptance & verification (replaces R4 Action 3 calibration loop)

| # | Criterion |
|---|---|
| AD1 | Tier 1 `nhard` gate + Tier 3 global rules implemented; `OSD_CORR_THRESHOLD` ≤ 0.35 |
| AD2 | `NHARD_MAX` calibrated against S5 (noise) and S7 (genuine); value + per-population `nhard` histograms recorded in the result `report.md` §3 |
| AD3 | **S5 (≥ 100 slots): FP rate = 0**, reported as FP-per-slot-hour with a 95 % upper confidence bound — not merely "0 / 12" |
| AD4 | S7 P0–P2 K=5: `co_channel_sweep ≥ 89 %` (no regression > 3 pp vs `d70aad5` 92.14 %) |
| AD5 | If measurement gate passes → **no Tier 2/4**, no struct change; ship |
| AD6 | If residual FPs persist → Tier 2 ABI bump (48→52) + Tier 4; re-run AD3/AD4 |
| AD7 | `dotnet build` 0/0; `dotnet test` all pass; struct-size self-test green if Tier 2 taken |
| AD8 | NFR-021: Q-prefix callsigns only in all test/handoff artefacts (carried over from R4 Action 2 — still required) |

**Statistical note for QA (NFR-023 §1 hypothesis):** "0 on 12 slots" gives only a ~22 % upper
bound on the true per-slot FP probability at 95 % confidence (rule of three: 3/12 ≈ 0.25).
A meaningful "matches WSJT-X" claim needs the S5 sample widened to ≥ 100 slots (rule of three →
≤ 3 % upper bound) and the metric stated as a rate with a confidence interval. Recommend the
S5 scenario be extended before this AC is treated as a gate.

---

## 7. Why this is better than the review's recommendation

- **Attacks P1, not just P2.** `nhard` removes the *cause* of the ceiling; the review's Path 1
  only relabels symptoms so a text heuristic can fire.
- **Touches Category E.** The review concedes Category E is "not tractable at the text layer."
  It is tractable at the `nhard` layer — the only place it can be.
- **Defers ABI cost behind measurement.** The struct break is taken only if proven necessary,
  not on spec.
- **Matches the reference implementation.** `nhard` is precisely WSJT-X's OSD acceptance metric,
  so converging on its FP behaviour is principled rather than coincidental.
- **No band-specific rules.** `/R`/`/P` handling rides the origin flag, keeping the decoder
  band-agnostic.

---

## 8. References

- `dev-tasks/2026-06-20-d009-fp-filter-arch-review.md` (QA review; Categories A–E, paths 1–3)
- `dev-tasks/2026-06-20-d009-fp-filter-r4.md` (calibration-loop handoff — Action 3 superseded)
- `native/ft8_lib_build/patched/ft8/decode.c` — OSD gate sites (~628, ~800); `osd_decode` ~465
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — FT8Result build site (~1225)
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — `FT8Result` struct (~240); `FT8_SHIM_VERSION`
- `src/OpenWSFZ.Ft8/Interop/Ft8NativeResult.cs` — managed struct mirror
- `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — `IsPlausibleMessage` (~361); call site (~229)
- WSJT-X `lib/ft8/osd174_91.f90` — `nharderrors` acceptance metric (reference for `nhard`)
- MEMORY Lesson 14 — separate result directories per calibration step
- MEMORY Lesson 9/10 — LLR normalisation tautology / prenorm-var refutation (why `corr/norm`
  alone is a weak discriminant; `nhard` is magnitude-independent)
