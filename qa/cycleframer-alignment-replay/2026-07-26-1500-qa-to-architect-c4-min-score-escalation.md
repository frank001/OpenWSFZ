# D-001: QA → Architect escalation — C.4 result contradicts the consolidation doc's decomposition

**Author:** QA, 2026-07-26 (15:00). **For:** the Architect, per HK-000/HK-015 (escalation runs
Dev → QA → Architect; QA does not let a Developer session revise the consolidation doc directly,
and does not quietly revise it either).
**Trigger:** `dev-tasks/2026-07-26-d001-c4-min-score-sweep.md` §9 ("If the result contradicts the
consolidation doc's decomposition table in any way, escalate to the Architect rather than quietly
revising it") and `2026-07-26-c4-min-score-sweep-findings.md` §10, which asks for exactly this
document.
**Captain sign-off obtained:** the one `src/` change surviving the C.4 branch —
`Ft8LibInterop.cs`'s `MaxPass0Candidates` raised 140 → 600 — is approved to keep, per HK-011.
Scope note: **that sign-off covers only the dormant diagnostic-capture constant.** It is not
sign-off on any production `K_MIN_SCORE`/`K_MAX_CANDIDATES` change — none is proposed here or
shipped anywhere in this branch. The question below is what to do about the *finding*, not the
diagnostic plumbing.

---

## 1. What your consolidation doc said

`2026-07-26-0015-d001-consolidation-and-clean-slate.md` §3 localised the 740-decode decoder gap
to two separable mechanisms, both reachable from `ldpc_stats.py`'s decile data:

1. **Candidate-list truncation** — pass 0's array caps at 140 and is saturated; if the true
   candidate population exceeds 140, real candidates are discarded by array size before LDPC
   ever sees them.
2. **LDPC survival collapse** — `failCands`/`meanAbsLLR`/`prenormVar` degrade sharply on
   zero-decode cycles even though candidate *yield* (140) looks identical to decoding cycles.

§6.3 held a third avenue in reserve only as a last resort, if both closed nothing: a structural
comparison against WSJT-X's extra decode passes (SIC, more a-priori decoding) — explicitly framed
as "a product question... a Captain decision."

## 2. What the three follow-up experiments actually found

| experiment | mechanism tested | verdict |
|---|---|---|
| C.1 (`K_MAX_CANDIDATES` 140→600) | §3.1, candidate-array truncation | Real but small: +12 decodes, +1.6% of the 740-share gap. Quickly plateaus. Confirmatory of "not a dead end, but not the answer either." |
| C.2 Phase 1 (LLR-normalisation) | §3.2, LDPC survival collapse | Confirmed as a real mechanism, but bounded: caps out at ~17% of the *remaining* gap (135 of 793 missed messages) even in the fully-successful case. Phase 2 (the actual fix) scoped, not shipped. |
| C.3 (candidate-generation-gap population) | neither — a byproduct of C.2's own matching | **The dominant population isn't §3.1 or §3.2 at all.** Of 793 missed messages, 648 (81.7%) have *no candidate of ours anywhere near that frequency/time* — not an array-truncation casualty, not an LDPC-survival casualty. Co-channel masking (§6.3's own fallback hypothesis) refuted, in the wrong direction (p=5.4×10⁻⁵²). Plain weak-signal sensitivity strongly supported instead (p=1.1×10⁻⁷⁴; median WSJT-X SNR −8 dB for the gap population vs +1 dB for shared hits). |
| **C.4 (`K_MIN_SCORE` sweep, this document's trigger)** | the mechanism C.3 pointed at: the pass-0 sync-score floor, upstream of both §3.1 and §3.2 | **Confirmed, and large.** Recovers 16.2% (at the shipped floor of 10) → 50–51% → 55–91% → 58–95%+ of C.3's 648-message population as the floor drops to 8/6/4, with a bounded false-positive ratio (0.34–0.61, never runaway). Qualitatively different shape from C.1: rapidly rising, not quickly plateauing. |

## 3. Why this is an escalation and not a footnote

Your §3 decomposition was two mechanisms because that was what the decile data supported at the
time, and it said so explicitly ("these are the only two things standing between us and the
740"). C.3/C.4 together show there is a **third, separable mechanism** — `K_MIN_SCORE`, the
sync-candidate score floor at `ft8_shim.c:472`, which discards candidates **before** they are
placed in the heap (`decode.c:285-286`) — entirely upstream of both the array-size question
(§3.1/C.1) and the LDPC-survival question (§3.2/C.2). It is not a refinement of either: a
candidate rejected by the floor never reaches the array C.1 tested or the LDPC stage C.2 tested.

Scale matters here, not just novelty. C.1's effect was confirmatory-small (+1.6% of gap). C.2
Phase 1's effect, even fully shipped, tops out at ~17% of the *post-C.3-split* remaining gap. C.4's
effect, on its own population, is 3–6x either of those — and the ceiling-free number (§4.2 of the
findings doc) is still unresolved on the high end (K=4 saturates even at `K_MAX_CANDIDATES=2000`;
95.4% recovery is a floor, not a ceiling). If this holds up under the validation §5 below requires,
`K_MIN_SCORE` alone may account for a majority of the 740-decode decoder gap — larger than §3.1
and §3.2 combined, on the population each of them was measured against.

This is what the dev-task's escalation clause was written for.

## 4. What is *not* being asked of you

- Not a request to approve shipping a new `K_MIN_SCORE` value. The findings doc (§10) explicitly
  recommends against that from this branch alone, and QA agrees — see the concurrent QA review.
- Not a request to re-litigate C.1's or C.2's own verdicts; both stand as reported.
- Not a claim that the mechanism is proven to be "SNR sensitivity" in a strict sense — `score` is
  a sync-correlation metric, not SNR directly (C.3 §4's own hedge, C.4 §9 repeats it). C.4
  confirms the floor is *a* real, large constraint; it does not independently re-derive *why*.

## 5. What is being asked of you

Two decisions, both properly yours per §6.3's own framing ("a Captain decision" — routed through
you as Architect first, per HK-015, before it reaches the Captain as a product decision):

1. **Does D-001's decomposition table need formal revision?** §3.1/§3.2's two-mechanism frame
   should, on this evidence, become at least three: array truncation (closed, minor), LDPC
   survival (partially scoped, bounded), and score-floor rejection (large, largely unscoped). If
   you agree, the consolidation doc — or a superseding note in the same style as your own
   2026-07-25/26 documents — should say so explicitly, the way §5.2/§5.3 of that document
   withdrew your own prior recommendations when they stopped surviving new evidence.
2. **Does §6.3 (the structural-comparison-against-WSJT-X fallback) still belong in the sequencing
   it currently has?** It was reserved for "if 6.1 and 6.2 do not close the gap" — framed as the
   expensive, product-level option of last resort. If `K_MIN_SCORE` alone is capable of closing
   the majority of the gap once properly validated, the structural-rewrite avenue may not need to
   be reached at all, or at least not next. That resequencing call is yours to make, not QA's or
   Dev's to assume.

Findings doc §10 (`2026-07-26-c4-min-score-sweep-findings.md`) already specifies what a validated
follow-up would need, for reference once you've made the above calls: (a) resolving the true
ceiling-free recovery number at K=4 with a properly safety-tested higher `K_MAX_CANDIDATES`, (b)
re-calibrating D-009's OSD gate against the much larger candidate population a lower floor would
send to LDPC/OSD, (c) a full R&R S1–S8 rerun before any shipped-constant decision. QA is not asking
you to scope that dev-task yet — only to make the two decisions above, which determine whether it
gets scoped at all and how it is sequenced against C.2 Phase 2.

## 6. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md` — the
  decomposition this escalation concerns, §3 and §6.3 specifically.
- `qa/cycleframer-alignment-replay/2026-07-26-c1-candidate-cap-sweep-findings.md` — C.1, closed,
  small effect, confirmatory.
- `qa/cycleframer-alignment-replay/2026-07-26-c2-llr-normalization-findings.md` — C.2, Phase 1
  confirmed/bounded, Phase 2 scoped not shipped.
- `qa/cycleframer-alignment-replay/2026-07-26-c3-candidate-generation-gap-findings.md` — C.3, the
  648-message population and the refuted/supported hypotheses.
- `qa/cycleframer-alignment-replay/2026-07-26-c4-min-score-sweep-findings.md` — C.4 itself, full
  method, results tables, and the recommendation this document escalates.
- `dev-tasks/2026-07-26-d001-c4-min-score-sweep.md` §9 — the escalation instruction this document
  satisfies.
