# D-001: QA -> Architect escalation — R.6's control is still broken; all three named fallbacks
# are excluded by measurement; a fourth diagnostic points at the sync/candidate stage, not levels.

**Author:** QA, 2026-07-27 (19:36 UTC, `date -u`, per HK-017). **For:** Architect.
**Follows:** `2026-07-27-1921-architect-to-qa-r6-handoff.md` (the handoff this responds to).
**Trigger:** the handoff's own §5 closing line — *"Escalate to me if the level sweep is flat and
none of §5's three fallbacks explain the control — that would mean the two arms differ in
something I have not thought of, and the design needs revisiting rather than the harness."*
**That condition is now met.** This note is the evidence.

---

## 1. What I was asked to do, in order (handoff §9)

1. Run the level sweep. 2. Fix the ln(2) bias, re-read SC1/SC4. 3. Add SC3 as a hard gate. 4. Only
then scale up. 5. Author the task spec. **I did 1-3 and 5 (task spec:
`2026-07-27-r6-clean-graft-task-spec.md`); I did not do 4 — SC3 still fails, so the handoff's own
rule blocks it.** This note covers why 4 stays blocked and reports one diagnostic beyond what was
asked for, because 1-3 alone did not resolve the puzzle and the escalation condition is explicit
about needing all three fallbacks excluded first.

## 2. Level sweep: hypothesis dead, confirmed by measurement

`r6_level_sweep.py`: pure AWGN, in-band SNR fixed at -6 dB (the point where R.6's real arm read 63%
and its AWGN arm read 0%), broadband sigma swept `3.1e-3 -> 5.3e-1` (~45 dB, spanning R.6's control
level up to R5's `noise_std_ref` loud reference), 8 repeats x 4 grafts/sigma, both decoders.

```
     sigma |             ours |              jt9
--------------------------------------------------
   3.1e-03 |   0.0% (  0/ 32) |   0.0% (  0/ 32)
   3.1e-02 |   0.0% (  0/ 32) |   0.0% (  0/ 32)
   3.1e-01 |   0.0% (  0/ 32) |   0.0% (  0/ 32)
   5.3e-01 |   0.0% (  0/ 32) |   0.0% (  0/ 32)
```

Flat. Absolute level is not the cause, at 45 dB of headroom, for either decoder.

## 3. The ln(2) fix lands exactly as predicted, and confirms the arms ARE matched

Applied your §6 correction (`MEDIAN_BIAS_CORRECTION = math.log(2.0)` dividing the per-bin median
before the RMS conversion). Re-ran the exact defective smoke configuration
(`R6_N_CYCLES=6 R6_SNRS=-14,-10,-6`):

| statistic | before (biased) | after (corrected) | your prediction |
|---|---:|---:|---|
| SC1 arm-to-arm offset | -1.54 dB | **+0.06 dB** | "should move to ~0" |
| SC4 baseline median | +1.59 dB | **+0.00 dB** | exactly `ln(2)` in dB |

Both landed exactly where you said they would. **The two arms are now confirmed matched in
measured local in-band SNR to within measurement noise.** This closes fallback #3 (amplitude-vs-SNR
convention) — the convention is delivering what it claims.

Decode rates at that same corrected -6 dB point, same run:

```
    -6 |  62.5% ( 15/ 24) |   0.0% (  0/ 24) |  79.2% ( 19/ 24) |   0.0% (  0/ 24) |
       ours REAL           ours AWGN          jt9 REAL           jt9 AWGN
```

## 4. SC3 added, and it correctly fails hard on this data

`r6_clean_graft.py` now gates on `>=90%` AWGN decode at the grid's top SNR, both decoders, and
exits non-zero on failure. Confirmed working:

```
SC3 [HARD GATE] AWGN control must reach >=90% at top of SNR grid (SNR=-6): ours=0.0%  jt9=0.0%
  [FAIL] CONTROL ARM IS BROKEN -- DO NOT QUOTE ANY R.6 NUMBER
```

This is exactly the mechanical catch you asked for in §7 — no more relying on a human noticing a
0.0% row.

## 5. All three named fallbacks are now excluded. A fourth diagnostic, using instrumentation
##    already in the shim, points somewhere new.

Your §5 fallback list, checked in order:

1. **write_wav peak normalisation** — excluded for "ours": it decodes the float buffer directly,
   never touches `write_wav`, and still reads 0%.
2. **16-bit quantisation floor** — same exclusion, same reasoning. jt9 (which does go through the
   WAV) also reads exactly 0%, same as "ours" — if quantisation were the cause I would expect jt9
   to suffer distinctly worse than "ours"; instead both are identically zero.
3. **Amplitude convention vs in-band SNR definition** — excluded by §3 above: SC1 shows the arms
   matched to 0.06 dB.

Since none of the three explained it, and per HK-018 ("prefer a five-minute measurement to a
paragraph of reasoning"), I used the shim's existing `ft8_get_last_candidate_diag` export
(unmodified — already called elsewhere in this thread's own `b2_synthetic_calibration.Native`) to
look one stage earlier, at the sync/candidate population itself, across 4 cycles at -6 dB
(`r6_candidate_diag.py`):

```
=== 260725_180615 -- 4 grafts @ SNR=-6 dB ===
  REAL: n_candidates=140  score min/mean/max=11/17.4/38
    planted @ 272.8Hz: nearest candidate score=17 decoded=True
    planted @ 476.8Hz: nearest candidate score=17 decoded=True
    planted @ 892.8Hz: nearest candidate score=16 decoded=True
    planted @ 2555.8Hz: nearest candidate score=18 decoded=True
  AWGN: n_candidates=10  score min/mean/max=10/10.1/11
    planted @ 272.8Hz: nearest candidate score=10 decoded=False
    planted @ 476.8Hz / 892.8Hz / 2555.8Hz: NO candidate within tolerance
  AWGN (noise-only background, no grafts): n_candidates=10
```

Same pattern held across all 4 cycles checked:

- **Real buffers: exactly 140 candidates every time** — hitting `K_MAX_CANDIDATES`, the cap.
  Scores span ~11-38 (mean ~16-17). Every planted signal's own candidate scores 15-19 and decodes.
- **AWGN buffers: only 5-15 candidates, never near the cap.** Scores cluster at exactly 10 — the
  score floor passed to `ft8_set_decode_params(10, 0.10, 60)`. The planted signal's own candidate,
  when it appears at all, sits exactly at that floor and never decodes.
- **AWGN background alone (no graft) produces almost the same candidate count as AWGN-with-graft**
  (10 vs 10, 5 vs 5, 3 vs 6, 12 vs 15 across the 4 cycles) — nearly everything AWGN finds is a
  noise-driven false hit, and the planted signal barely clears that floor rather than standing out
  from it.

I then checked the one hypothesis this pattern most obviously suggests — that flat AWGN, being
"loud" at the local target density across the *entire* spectrum rather than only the 43.75 Hz gap,
might be feeding some broadband-referenced part of the scoring stage a noisier picture than a real
buffer would, even at matched local SNR. **Measured, it is backwards:**

```
260725_180615: real broadband RMS=0.01196  awgn broadband RMS=0.00439  ratio(awgn/real)=-8.7 dB
260725_180630: real broadband RMS=0.01227  awgn broadband RMS=0.00178  ratio(awgn/real)=-16.8 dB
260725_180700: real broadband RMS=0.01480  awgn broadband RMS=0.00194  ratio(awgn/real)=-17.6 dB
260725_180715: real broadband RMS=0.01119  awgn broadband RMS=0.00270  ratio(awgn/real)=-12.3 dB
```

The AWGN buffer's overall RMS is **lower** than the real buffer's in every cycle checked (real
buffers are dominated by multiple genuinely strong transmissions elsewhere in the band). If
anything, AWGN is the objectively quieter buffer overall — a naive "louder broadband reference
hurts detection" story predicts the opposite of what we see. **This hypothesis is also excluded.**

## 6. Where this leaves things

At local in-band SNR now confirmed matched to 0.06 dB, the identical planted signal:

- scores 15-19 in real audio (rich with genuine other signals, high broadband RMS) and decodes;
- scores exactly 10 — the bare minimum — in flat AWGN (no other signals, lower broadband RMS) and
  does not decode;
- and in AWGN, the candidate search finds almost nothing else either (5-15 total vs real's 140,
  hitting the cap) — the graft is not being outcompeted by a flood of other candidates, it simply
  never rises above the noise floor's own score.

None of your three fallbacks explain this, and the one further mechanism I could test cheaply
(broadband level acting as a noisier reference in AWGN) measures backwards. I don't have a
confirmed explanation to hand you — per your own escalation clause, that's the point of this note
rather than something I should paper over with a fourth guess. Two live possibilities I have *not*
excluded, for your judgement on where to look next:

- The sync-correlation/candidate-scoring stage may reference some statistic of the buffer's own
  candidate-score distribution (order statistics, a percentile, a running estimate) rather than a
  fixed absolute or purely-local threshold — in which case a buffer that legitimately contains many
  strong real signals (real arm, 140 candidates, wide score spread) versus one that contains almost
  none (AWGN, 5-15 candidates, narrow score spread near the floor) could produce systematically
  different scores for an identical local SNR signal, independent of level. This is a hypothesis
  about the **decoder's own candidate-scoring algorithm's use of the candidate population**, not
  about the harness construction — if true, it would mean R.6's AWGN control, no matter how it is
  built, cannot serve as a "no environment" baseline for a decoder whose scoring is population-
  relative, and the clean-graft design (handoff §3) would need to graft against a background that
  preserves a *comparable candidate population*, not just a matched local SNR.
- Alternatively there may be a narrower, more mundane construction bug I have not found in 4 cycles
  of manual inspection — I have not exhaustively ruled that out, only the three you named plus one
  I added.

## 7. What I did and did not do, so nothing here is overstated

- **Did**: level sweep (§2), ln(2) bias fix + re-verification (§3), SC3 hard gate + verification
  that it fires (§4), candidate-population diagnostic + broadband-RMS check (§5), the task spec
  (`2026-07-27-r6-clean-graft-task-spec.md`).
- **Did not**: run the full-scale sweep (handoff §9 item 4) — blocked by SC3, per your own rule.
  Did not modify `src/` or native code (HK-011). Nothing pushed or merged (HK-014). No
  `pre_merge_check.py` run (HK-006, your call to trigger).
- **No R.6 number is established**, same as your handoff's own §10 — this note adds diagnostic
  evidence about *why* the control fails, it does not produce a trustworthy real-vs-awgn figure.

## 8. Cross-references

- `2026-07-27-1921-architect-to-qa-r6-handoff.md` — the handoff this responds to.
- `2026-07-27-r6-clean-graft-task-spec.md` — the task spec, status BLOCKED, §5 summarises this note.
- `r6_level_sweep.py`, `r6_candidate_diag.py` — the two new diagnostics.
- `r6_clean_graft.py` — `band_noise_rms_robust` (ln(2) fix), SC3 gate, both in this session's diff.
- `artefacts/d001_r6_level_sweep/results.json`, `artefacts/d001_r6_clean_graft/measurements.json` —
  git-ignored run outputs backing every number quoted above.

---

*Per HK-015, this is QA escalating to Architect on the handoff's own invitation, not a routine
task-spec handoff. Per HK-014, committed locally, no push, no merge. Per HK-011, no `src`/native
change. Per HK-018, §5's broadband-RMS check was a five-minute measurement run before writing this
note, not a hypothesis left as reasoning-only.*
