# D-001: QA -> Architect notification — B.1 (jt9 ablation) and B.2 (synthetic BER calibration) both report; B.3's two measured prizes are in hand

**Author:** QA, 2026-07-26 (23:50). **For:** the Architect, per HK-015.
**Answers:** `2026-07-26-2330-architect-capability-pricing-plan.md` — both steps it scoped for
QA, run in the same session, per its own "may run in either order or in the same session; B.3
waits for both."
**This is a notification, not an escalation.** Both measurements land inside the ranges the plan
and the 22:30 ruling anticipated; nothing here contradicts a prior ruling. One methodological
self-correction is disclosed in full (B.2's clipping catch) rather than only reporting the fixed
number, per this thread's standing practice.

---

## 1. Headline

**Both prizes are now measured, independently, by two different methods that answer different
questions and happen to agree on the shape of the picture:**

- **B.1 (jt9 ablation):** the 789-message gap between WSJT-X's live decode and ours is **almost
  entirely recoverable by WSJT-X's own decoder without any session/GUI context** — 98.0% of it at
  full offline effort, and even at **minimum** effort (depth 1, no AP, no context) WSJT-X recovers
  **55.4%** of it while out-decoding our full-effort offline decoder by **30%** on the identical
  audio. This points the gap mostly at **front-end/sync quality**, not at the subtraction/effort
  stack alone — plan §3.4's row 3 fires, not row 2.
- **B.2 (synthetic calibration):** **E = 5.7** (of 135) — a real but small decode-path residue,
  landing inside the 1–15 band, close to the Architect's own stated prior (5–15). This bounds how
  much of THE 135 specifically is a correctable LLR-quality defect in *our own* decode path, as
  opposed to signals we never had a fighting chance at.

Read together: B.2 says our own BP/OSD correction stage is leaving only a small, single-digit
number of THE 135 on the table. B.1 says the *much larger* 789-message gap sits mostly outside
that stage entirely — in whatever WSJT-X's front end does that ours does not, recoverable by
WSJT-X's own decoder at trivial effort. These are not in tension: THE 135 (score ≥10, a candidate
existed) was always the smaller, more tractable slice of the total gap; B.1 measures the whole
789 and finds most of it never became a scored candidate for us in the first place, which is a
front-end question, not a BP/OSD question — consistent with, not contradicted by, B.2's small E.

## 2. B.1 detail

Full method and tables: `2026-07-26-b1-jt9-ablation-findings.md`. Self-checked against
`c4_matched_decode_verification.py`'s own printed anchor (1300 offline-decode total, 1239
matched, 789 missed — a small, noted drift from the plan's own citation of "1288/793/1235",
not investigated further, flagged in the findings doc's §1).

| arm | depth | total | miss coverage of 789 |
|---|---:|---:|---:|
| A0 | 3 | 2039 | 773 (98.0%) |
| A1 | 2 | 1947 | 683 (86.6%) |
| A2 | 1 | 1693 | 437 (55.4%) |

A0 (2039) slightly *exceeds* the live GUI anchor (2028) — an unplanned finding: offline batch
replay needs no upward correction for session/GUI context on this corpus; if anything the live
GUI does not out-decode a context-free offline pass. Price list: T(3)−T(2)=92, T(2)−T(1)=254 —
most of the depth-axis gain sits in the 1→2 step, not 2→3.

**Optional arm A4** (jt9 on our own byte-compatible capture): 2113, exceeding even A0 — symmetric
to the `cycle-audio-archive` parity finding; the capture chain remains exonerated.

## 3. B.2 detail

Full method and tables: `2026-07-26-b2-synthetic-calibration-findings.md`. Self-check: Arm A's
own curve reaches P(decode)=100% at BER≈0% (n=1653) and falls to single digits by BER 17.5%, the
physically required shape, obtained with the channel (not an implementer) setting the LLRs.

Arm A and Arm B **diverge** (Arm B reads systematically higher P(decode) than Arm A at the same
measured BER through the transition region) — the ruling's §5 explicitly anticipated this
possibility and its consequence: `E` is computed from Arm B, not Arm A. The likely mechanism is a
location-rate selection effect, detailed in the findings doc §3, including a flagged matching
artefact specific to the Δf=0 slice (both planted co-located messages resolve to the same
candidate object, inflating that slice's apparent "100% located" rate). This does not move the
reading-rule band (Arm A's own E=4.45 lands in the same 1–15 row).

**One self-correction disclosed in full:** the first pass hard-clipped the synthesised buffer,
which turned out not to be cosmetic (median 41% of samples clipped inside the BER 5–20%
transition region) — a nonlinear channel the ruling's own design principle argues against.
Fixed by a global linear rescale (preserves the SNR ratio exactly, produces zero clipped
samples). E moved 5.97 -> 5.69 across the fix — a small shift, not a reversal — and the clean run
is the only one trusted for the verdict.

E = 5.69 of 135 (~4.2%) reads: *"a real but small decode-path residue. Chase it if the cause is a
single constant or gate; otherwise fold the count into §6.3's framing and proceed."* Per the
ruling's own conservative framing, this is a lower bound.

## 4. What this delivers for B.3, and what it does not decide

Both measured prizes the plan's §5 skeleton asked for are now in hand:

- Row 2 (PCM-domain SIC re-attempt): B.1's price list is available (T(3)−T(1)=346 messages, of
  which 254/346=73% comes from the depth 1→2 step alone) — **caveat unchanged from the B.1
  findings doc: depth is a bundle, not a clean subtraction toggle**, so this ceiling is the whole
  depth-axis, not SIC isolated.
- Row 3 (decode-effort constants — BP iterations, OSD depth/gates): B.2's E=5.69 is inside the
  1–15 band, so per the ruling's own rule this row is live for the Captain to weigh (not
  "measured ≈0, closed"), but it is a small number against B.1's much larger front-end signal.
- Row 4 (front-end/sync work): **fires** — B.1's A2≫our-offline-anchor result (30% margin at
  minimum jt9 effort) is the plan's own trigger condition for this row, and it is now the largest
  of the three measured prizes.
- Row 5 (adopt WSJT-X's decoder core, GPLv3): unaffected by either measurement; still a flag, not
  a decision, per the plan's own framing.
- Row 1 (accept the gap): unaffected; still available as the zero-cost option.

**QA has not written §6.3 itself** — per the plan's own division of labour, that memo is the
Architect's to write from these two measurements, and the plan was explicit that it is "recorded
now so B.1/B.2 collect the right numbers," not that QA drafts it. Nothing here is a recommendation
on which menu row the Captain should pick.

## 5. What this does not authorise or settle

- **No native or `src/` change.** Both sessions used only exports that already ship (opt-in,
  default-off), consistent with HK-011 not applying.
- **No push, no merge** (HK-014).
- **No `pre_merge_check.py`** — Captain's trigger per HK-006, not run this session.
- **The branch's outstanding housekeeping items are untouched**: the `libft8.dll` size question
  flagged at the 20:30 ruling §9 and the 19:35 notification §6 remains open and is not addressed
  by either B.1 or B.2 — neither session touched `src/` or triggered a rebuild.
- **NFR-021**: all raw jt9 output, synthetic-signal candidate/LLR data, and message text stay
  under git-ignored `artefacts/d001_b1_jt9_ablation/` and `artefacts/d001_b2_synthetic_
  calibration/` respectively (verified via `git check-ignore -v` on a sample file from each);
  only aggregate statistics appear in either findings doc or here.

## 6. Cross-references

- `2026-07-26-2330-architect-capability-pricing-plan.md` — the plan both steps execute.
- `2026-07-26-2230-architect-sec6-redesign-ruling.md` — B.2's design and reading rule, unchanged.
- `2026-07-26-b1-jt9-ablation-task-spec.md` / `-findings.md` — B.1 full detail.
- `2026-07-26-b2-synthetic-calibration-task-spec.md` / `-findings.md` — B.2 full detail.
- `b1_jt9_ablation.py`, `b2_synthetic_calibration.py` — drivers.

---

*Per HK-015, §6.3 is the Architect's to write from the two measurements above; QA has not framed
a recommendation between the costed-menu rows. Per HK-014, nothing here is pushed or merged. Per
HK-006, `pre_merge_check.py` remains the Captain's trigger, not run this session.*
