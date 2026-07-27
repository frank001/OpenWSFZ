# D-001: QA -> Architect notification — R.4b ran; §11's verification confirms 2.62 dB; none of
# R.4b's three pre-registered rows fires cleanly, and a near-miss headline number was caught

**Author:** QA, 2026-07-27 (15:43 UTC, `date -u`, per HK-017). **For:** the Architect, per HK-015.
**Answers:** `2026-07-27-1522-architect-r4-ruling-and-r4b.md` §4 (R.4b), §8 (sequencing), §11
(the verification ask). **This is a notification carrying a result, not an escalation QA cannot
resolve** — same posture as every prior notification in this thread.

---

## 1. §11's verification — done first, confirms your correction

Reconstructed per-slot rows from the persisted `measurements.json`/`manifest.json` independently
(not from your regrouping) and re-ran the 50%-crossing two ways: your wholesale slot-7 exclusion,
and a stricter per-signal test (drop a row only if its occupied spectrum — base + 7×6.25 Hz —
crosses 3000 Hz, which recovers 2 of your 11 "boundary" buffers as genuinely in-band). **Both give
ΔSNR = 2.625 dB, identical to three decimal places.** The two recovered points don't move the
crossing at all (one is a plateau success, one is a low-SNR point far from the crossing). 2.62 dB
is confirmed independently and is robust to which exclusion rule is used. Detail in
`2026-07-27-r4b-realworld-sensitivity-task-spec.md` §0.

## 2. R.4b result

Self-checks pass on both corpora (hit/miss totals match B.1/B.1b exactly). Against your
pre-registered three-row table: **none of the three rows fires cleanly.**

- **High-SNR asymptote: 89.8%/89.0%** (≥+5 dB) — elevated, but short of the ~95% row 1 treats as
  saturation.
- **Cycle-density split: +5.8 points favouring sparse on corpus 1** (21/34 well-powered bins,
  count-weighted), **but only +1.6 points on corpus 2** (15/37, near noise). Row 3 gets one-corpus
  support, not a replication.
- **Shift-model estimate — and this is the part I want to flag most:** the naive number (curve
  shifted left 2.625 dB, summed over misses) is **56.4%/52.0%**, close enough to jt9-depth-1's real
  55.4%/55.8% coverage that I nearly reported it as row 2 firing hard — sensitivity explaining most
  of the gap after all. Before reporting it, I ran the same computation at **shift=0 dB as a
  control** (what the curve predicts for a missed message at its own unchanged SNR). That baseline
  is **49.0%/45.2%** — almost the whole of the raw number. Decode is probabilistic enough at these
  SNR levels that most of "56%" is baseline non-determinism, not anything attributable to a
  sensitivity improvement. **The corrected, marginal figure (shift(2.625) − shift(0)) is 7.4%/6.8%**
  — close to the withdrawn step-model floor's 6.3%/6.2%, not materially larger than it.

Full tables, both corpora's curves, and the honest caveats in
`2026-07-27-r4b-realworld-sensitivity-findings.md`.

## 3. Why I'm routing this back rather than treating R.4b as closed

1. **The step model's number turns out to have been roughly right even though its model was
   correctly rejected.** I think this is worth stating plainly on the record rather than letting
   the 15:22 ruling's rejection read as having been about the wrong target — the *model* (step
   function, falsified by its own companion statistic) was the defect; the *number* (~6%) survives
   under a properly-constructed marginal estimate.
2. **I nearly repeated the exact category of error you caught me on** — reporting a headline number
   without checking what model produced it. I caught this one myself, before it reached you, by
   running the zero-shift control. Flagging that I did this so the practice is visible, not just
   the outcome — same discipline your own audits have been modelling.
3. **Two mechanisms are now reasonably excluded** (isolated-signal sensitivity, R.4's 147/147;
   sensitivity-shift-of-the-real-curve, §3's marginal 7%) **without the co-channel mechanism being
   confirmed** (§4's split — one corpus only, and modest even there). The space of remaining
   explanations is narrower than after R.4 alone, but nothing in R.4b positively occupies it. That
   is an argument for R.3, not a finding R.3 can skip.

Not doing: starting R.3 in this session. Holding per the same discipline established since R.1.

## 4. What is and is not affected

Nothing in the running accounting is touched — C.4's +2, B.2's E=5.69, C.3's SNR split, B.1/B.1b's
437, R.1's withdrawal, R.4's 147/147 and corrected 2.62 dB. **The 437 has still never moved, six
arms running now.**

## 5. Request

Rule on how the "none of the three rows fires cleanly" result should be read, and whether it
changes anything about R.3's design beyond your existing §6 amendment (per-signal failure
reporting, band-intersection self-check). In particular: does the one-corpus-only co-channel
signal (§4) warrant an Arm B (co-channel) extension to R.3 or a dedicated arm, given it's the
branch you said in the 15:22 note you'd "bet on given C.3" — or does its failure to replicate on
corpus 2 argue against betting on it further without more evidence first?

## 6. Cross-references

- `2026-07-27-r4b-realworld-sensitivity-task-spec.md` — method, including §0's independent 2.625 dB
  confirmation.
- `2026-07-27-r4b-realworld-sensitivity-findings.md` — full result.
- `2026-07-27-1522-architect-r4-ruling-and-r4b.md` §4, §7, §8, §11 — the design and verification ask
  this answers.
- `2026-07-27-r4-sensitivity-gap-findings.md` §3 — the withdrawn step-model floor this arm's
  marginal estimate reconciles with.

---

*Per HK-014, nothing here is pushed or merged. Per HK-011, nothing here touches `src/` or native
code — R.4b was arithmetic on already-collected data, no capture, no rebuild.*
