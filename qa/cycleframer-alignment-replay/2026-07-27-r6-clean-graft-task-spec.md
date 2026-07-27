# D-001 R.6 — the clean graft, QA task spec

**Author:** QA, 2026-07-27 (19:36 UTC, `date -u`, per HK-017). **Operationalises:**
`2026-07-27-1921-architect-to-qa-r6-handoff.md` §3 (design) plus §§4-7 (known-defect notes),
per that handoff's own §9 item 5 instruction and HK-015 (task spec is QA's to author).
**QA-runnable directly: no `src`/native change (HK-011 does not apply), no push/merge (HK-014),
no `pre_merge_check.py` (HK-006), no `dev-tasks/` entry** — same posture as every prior arm.

**Status: BLOCKED.** SC3 (§4 below) fails on every configuration run so far, including after the
fixes this spec bakes in. §5 records new evidence, gathered this session, that rules out every
candidate cause the handoff's own §5 fallback list proposed. Per the handoff's own escalation
clause, this is now referred back to the Architect (`2026-07-27-qa-to-architect-r6-control-
escalation.md`) rather than resolved here. **Do not run the full-scale sweep (§3.4) until that
returns a verdict.**

---

## 1. Question (unchanged from the design)

Grafting a synthetic Q-message into unmodified real audio, at a controlled local in-band SNR, in a
frequency gap WSJT-X decoded nothing in: does the resulting decode rate match an identical graft in
flat AWGN at the same measured SNR (→ environment is not the problem, the gap is in real *signal*
properties) or fall well short of it while jt9 holds up (→ noise-adaptive handling is the problem)?
This is the bisection of the (A)/(B) fork left open by R.5's 2→4 step (handoff §2.3).

## 2. What this spec inherits unchanged from the handoff

- The construction: graft into unmodified real audio at a controlled **local** in-band SNR measured
  from that buffer's own noise in the exact occupied band (43.75 Hz, 8-tone alphabet), no notch, no
  hole. Control arm: identical signals at identical in-band SNR in flat AWGN. (Handoff §3.)
- **Defect 1** (amplitude pinned to a contaminated raw in-band RMS, inflating the real arm) — already
  found and fixed by the Architect via `band_noise_rms_robust`'s median-based estimator. Unchanged
  here. (Handoff §4.)
- Self-checks SC1 (measured-vs-nominal SNR, both arms) and SC2 (gap clearance) as already
  implemented in `r6_clean_graft.py`. Unchanged here.

## 3. Operational fixes this spec adds (handoff §9 items 2-3)

### 3.1 `band_noise_rms_robust`'s ln(2) bias — fixed

Per handoff §6: the median of a chi-squared(2 dof) periodogram bin is `ln(2)` times its mean, so the
median-based robust estimator read noise power ~1.6 dB low. Fixed by dividing the per-bin median by
`MEDIAN_BIAS_CORRECTION = math.log(2.0)` before the RMS conversion, in both
`band_noise_rms_robust` call sites (the noise estimate used to set graft amplitude, and the SC1
measurement itself, since both route through the same function). **Verified**: a smoke re-run
(`R6_N_CYCLES=6 R6_SNRS=-14,-10,-6`, matching the committed defective smoke run exactly) moved SC1's
arm-to-arm offset from -1.54 dB (biased) to **+0.06 dB** and SC4's baseline median from +1.59 dB to
**+0.00 dB**, exactly the predicted corrections. The two arms are now confirmed matched in measured
local in-band SNR to within measurement noise.

### 3.2 SC3 — added as a hard gate

Per handoff §7 (the docstring claimed this check existed; it did not). **SC3: the AWGN control arm
must reach `>= SC3_CEILING` (default 90%) at the top (warmest) point of the SNR grid, both
decoders.** Implemented in `r6_clean_graft.py`'s `main()`, printed as `[PASS]`/`[FAIL]`, written into
`measurements.json` (`sc3_pass`, `sc3_ceiling`, `sc3_top_snr`, `sc3_ours_p`, `sc3_jt9_p`), and wired
to the script's own exit code (non-zero on failure) so a broken control cannot be silently treated
as a valid run by anything that shells out to this script. **Verified**: re-running the same smoke
configuration correctly reports `SC3 ... [FAIL] CONTROL ARM IS BROKEN -- DO NOT QUOTE ANY R.6
NUMBER` and exits 1 — this is the exact failure mode described in handoff §1, now caught mechanically
rather than requiring a human to notice a 0.0% row.

### 3.3 SC4's reported statistic

Per handoff §6, SC4 now reports the bias-corrected median (should sit near 0 dB) plus the p95/max
upper tail as the informative contamination statistic, both persisted to `measurements.json`.

### 3.4 Full-scale run — NOT YET RUN, blocked

Handoff §9 item 4 (34 cycles × 4 grafts × 6-point SNR grid, both arms, both decoders, ~400 jt9
invocations) is specified but **not executed by this task**, because SC3 fails on every
configuration tried so far (§5) — running the full sweep against a control known to be broken would
produce exactly the "table row instead of a hard FAIL" outcome SC3 exists to prevent. Do not run
until the escalation (§5) returns a design verdict.

## 4. Self-checks (must all pass before any number is trusted)

1. **SC1** — measured-minus-nominal in-band SNR, both arms; arm-to-arm offset `< 1.0 dB` [PASS
   at +0.06 dB in the 6-cycle smoke configuration, post-fix].
2. **SC2** — zero gap-clearance violations [PASS, 0 in every run to date].
3. **SC3 — HARD GATE** — AWGN control `>= 90%` at the grid's warmest point, both decoders
   [**FAIL** in every configuration run to date; blocks §3.4].
4. **SC4** — gap contamination, bias-corrected; median should sit near 0 dB, upper tail (p95/max)
   is the informative statistic for undecoded-carrier leakage into a nominally clear gap.

## 5. New evidence gathered this session (why this is escalated, not resolved)

The handoff's own §5 named three fallback candidates if the (now-confirmed-dead) level-sensitivity
hypothesis failed to explain SC3's failure. All three are now excluded by direct measurement:

- **Level sensitivity** — `r6_level_sweep.py`: pure AWGN, in-band SNR fixed at -6 dB, broadband
  sigma swept 3.1e-3 → 5.3e-1 (~45 dB, spanning R.6's control up to R5's loud reference level).
  Flat 0/32 at every sigma, both decoders. **Dead** — confirmed by measurement, not just excluded by
  the fix in §3.1.
- **write_wav peak normalisation / 16-bit quantisation** — excluded for "ours": it reads the float
  buffer directly, bypassing both, and still reads 0% on the control.
- **Amplitude-vs-SNR convention** — excluded by §3.1's fix: SC1 now shows the two arms matched to
  within 0.06 dB measured local in-band SNR, yet decode rates remain 62.5%/79.2% (ours/jt9) on real
  vs 0%/0% on AWGN control at -6 dB (the post-fix smoke run, §3.1).

A fourth, new diagnostic (`r6_candidate_diag.py`, using the shim's existing
`ft8_get_last_candidate_diag` export unmodified) went one level deeper, into the sync/candidate
population itself, across 4 cycles at -6 dB:

- **Real buffers**: exactly 140 candidates every time (the `K_MAX_CANDIDATES` cap), scores ranging
  ~11-38 (mean ~16-17); the planted signal's own candidate scores 15-19 and decodes.
- **AWGN buffers**: only 5-15 candidates total (never near the cap), scores clustered at 10 (the
  minimum score threshold passed to `ft8_set_decode_params`); the planted signal's own candidate,
  when found at all, scores exactly 10 and never decodes.
- **AWGN background alone (no graft)** produces almost the same candidate count as AWGN-with-graft
  (e.g. 10 vs 10, 5 vs 5, 3 vs 6, 12 vs 15) — nearly all AWGN "candidates" are noise-driven, and the
  planted signal barely clears that floor.
- **Broadband RMS check** (one more cheap measurement, per HK-018): the AWGN buffer's overall RMS is
  actually **lower** than the real buffer's, by 8.7-17.6 dB across the 4 cycles checked (real
  buffers are dominated by multiple genuinely strong transmissions). This rules out a "flat noise
  floods the whole spectrum louder than real" mechanism — if anything AWGN is the objectively
  quieter buffer overall, yet it is the one that fails to decode.

**Net**: at matched local in-band SNR, confirmed to within 0.06 dB, the identical synthetic signal
scores far higher in real audio's sync/candidate search than in an objectively quieter flat-AWGN
buffer. None of the handoff's three named fallbacks explain this. Full analysis and the escalation
question are in `2026-07-27-qa-to-architect-r6-control-escalation.md`.

## 6. Cross-references

- `2026-07-27-1921-architect-to-qa-r6-handoff.md` — the handoff this operationalises.
- `2026-07-27-qa-to-architect-r6-control-escalation.md` — the escalation this spec's §5 summarises.
- `r6_clean_graft.py` — the harness, now with §3.1/§3.2 fixes applied.
- `r6_level_sweep.py`, `r6_candidate_diag.py` — the two new diagnostics run this session.
- `artefacts/d001_r6_clean_graft/measurements.json`, `artefacts/d001_r6_level_sweep/results.json` —
  git-ignored run outputs.
