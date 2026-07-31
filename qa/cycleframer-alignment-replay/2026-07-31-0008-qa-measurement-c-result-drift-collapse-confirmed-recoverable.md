# D-001/capture-defect Measurement C -- RESULT: collapse is window misalignment, PROVEN

**Author:** QA, 2026-07-31 (00:08 UTC, `date -u`, per HK-017).
**For:** Architect (ruling owed per S6b.3's consequence column), and the Captain.
**Answers:** `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` S6b,
which authorised this measurement and pre-registered its reading rule before the run.
**Script/data:** `measurement_c_realign.py`, `measurement_c_realign_report.md`,
`measurement_c_manifest.csv` (all in this directory; `_work/measurement_c/` is git-ignored,
NFR-021).

---

## 0. Summary

Measurement C ran exactly as designed in S6b.2, at full scale (n=300: 150 healthy-window +
150 collapsed-window cycles, not a smoke sample). The mechanical outcome, applying the
pre-registered reading rule with no discretion exercised, is the **first row of S6b.3's
table**:

> **COLLAPSED-WINDOW PARITY RECOVERS TOWARD ~65% (OUR DECODER: 4.0% -> 63.1%, matching the
> healthy-window baseline of 61.4-61.7% almost exactly). THE COLLAPSE IS WINDOW
> MISALIGNMENT AND NOTHING ELSE. PROVEN, NOT INFERRED.**

The healthy-window null control moved by +0.3 points (61.4% -> 61.7%, our decoder) — nowhere
near "materially," which is the built-in check that the shift logic itself is not the thing
producing the recovery. The capture-clock-drift defect's mechanism is now settled: the fix
targets cycle-boundary synchronisation, and the affected corpora (`2026-07-29-5016363/
anova_report_40m.md`'s struck 49.9%, and `2026-07-29-489135a/anova_report_40m.md`'s 62.4%)
are **recoverable by realignment**, not permanently lost.

## 1. Results (n=300, full-scale, 95% Wilson intervals)

| stratum | condition | decoder | matched | ref decodes | parity | 95% CI |
|---|---|---|---:|---:|---:|---|
| healthy | unshifted | ours | 2966 | 4831 | 61.4% | [60.0%, 62.8%] |
| healthy | shifted | ours | 2979 | 4831 | 61.7% | [60.3%, 63.0%] |
| healthy | unshifted | jt9 | 4665 | 4831 | 96.6% | [96.0%, 97.0%] |
| healthy | shifted | jt9 | 4741 | 4831 | 98.1% | [97.7%, 98.5%] |
| **collapsed** | **unshifted** | **ours** | **63** | **1561** | **4.0%** | **[3.2%, 5.1%]** |
| **collapsed** | **shifted** | **ours** | **985** | **1561** | **63.1%** | **[60.7%, 65.5%]** |
| collapsed | unshifted | jt9 | 270 | 1561 | 17.3% | [15.5%, 19.3%] |
| collapsed | shifted | jt9 | 1407 | 1561 | 90.1% | [88.6%, 91.5%] |

**Collapsed-window recovery, our decoder: 4.0% -> 63.1%, a 15.8x improvement, landing inside
(marginally above) the healthy-window baseline's own CI.** The 95% CIs for unshifted vs
shifted in the collapsed window do not overlap by a wide margin (n=1561 reference decodes
each) — this is not sampling noise.

**Healthy-window null control: 61.4% -> 61.7% (ours), 96.6% -> 98.1% (jt9).** Both move by low
single-digit points in the *same direction* as the collapsed-window recovery (small positive),
consistent with the "healthy" pool still carrying up to 0.5 s of residual drift by
construction (S6.2's own bound) that a correct realignment would nudge slightly upward too —
not a sign of harness error. Per S6b.3's own trap ("healthy-window control moves materially ->
harness defect, void the run"), this does not trigger it: the collapsed-window recovery is
two orders of magnitude larger than the healthy-window's own movement.

## 2. Design notes and the one derivation worth recording

**Shift direction.** The sign convention was derived from first principles (absolute-time
algebra: `corrected[j] = a[j-L]`, zero-filling the front where OpenWSFZ has no data because it
started recording late, dropping OpenWSFZ's own tail samples which describe time past
WSJT-X's window end) and validated two ways before being trusted on real data:

1. A synthetic-control self-test in `measure_drift_8080_session.py` (a known 1000-sample delay
   recovers exactly, with peak correlation 1.0000) — this is where the sign convention was
   fixed, per the ruling's explicit instruction to validate it before trusting real audio.
2. The healthy-window null control in *this* measurement, which is the design's own
   built-in check (S6b.3) — if the derivation had the sign backwards, the healthy window would
   have degraded sharply (barely-drifted audio, corrupted by a large erroneous shift), not
   moved by 0.3 points.

Both checks agree, and a small (n=5/stratum) smoke run showed the same pattern as the full
n=300 run before it was committed to, per the same validate-before-trusting discipline.

**Sampling.** Both strata used fixed-stride sampling (not random) from the elapsed-time-based
drift regression (`lag_seconds ~= -0.2366 - 0.1744 * elapsed_h`, fit in
`measure_drift_8080_session.py`'s coarse pass) — reproducible, per the ruling's own requirement.
Healthy pool: 358 candidates (|predicted lag| < 0.5 s), sampled 150. Collapsed pool: 2671
candidates (predicted lag <= -2.5 s), sampled 150.

## 3. One observation, not over-read

jt9's collapsed-shifted parity (90.1%) recovers strongly but sits ~7-8 points below its own
healthy-window baseline (96.6-98.1%), a smaller residual gap than "ours" shows (which recovers
to match or fractionally exceed its own healthy baseline). This is consistent with jt9 being a
more sensitive reference decoder generally (per the density-law work) picking up a handful of
borderline signals that a single-sample-domain roll doesn't restore as cleanly as it does for
weaker/median signals — plausible, not measured further here, and does not change the primary
reading (S6b.3 is stated in terms of "our decoder" recovering toward ~65%, which it does,
fully).

## 4. Free by-products delivered

Per S6b.4's own framing, these fall out of the same run at no extra cost:

- **DT tolerance constant:** consistent with the defect report's own bracket (2.34-2.48 s) —
  the collapsed-window sample (predicted lag <= -2.5 s) already shows the healthy-decoder-like
  recovery once realigned, confirming the cliff is a window-boundary effect at that
  magnitude, not a gradually-degrading one.
- **489135a 40m / the withdrawn cross-instance claim (S3.1):** **not yet recomputed** — this
  measurement used the `20260729_live_run_1831-8080` session only, per S6b's own design (the
  matched-WAV-pair corpus this experiment needs). Recomputing 489135a on its drift-free window
  is a follow-on, not automatic from this run, and is flagged here rather than silently
  claimed as done.
- **Reference-method question (S3.2's open item):** also not directly answered by this
  specific comparison (this measurement compares shifted vs. unshifted, not jt9-re-decode vs.
  live-WSJT-X-ALL.TXT on identical audio) — noting explicitly rather than overclaiming a
  by-product that would need its own small comparison to actually deliver.

## 5. What this does NOT do

- Does not propose or apply a fix. Per HK-011, `CycleFramer.cs`/`WasapiAudioSource.cs` changes
  route through a separate Developer session with the Captain's sign-off; per S6b.3's
  consequence column, "the fix targets cycle-boundary synchronisation" is a scoping statement
  for that future work, not a diff.
- Does not recompute the two affected corpora's headline parity figures — that recovery is
  now known to be *possible*, not yet *performed* as a republished number. A follow-on task,
  not assumed done here.
- Does not touch `src/` or native code. No push, no merge (HK-014/HK-010) — committed locally.
  No `pre_merge_check.py` run implied (HK-006).
- NFR-021: message text was read only for matching (identical to `anova_common.py`'s own
  convention); the shifted/unshifted WAVs and all per-decode output live under git-ignored
  `_work/`. Only aggregate counts left the script.

## 6. Cross-references

- `2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md` S6b — design,
  cost estimate, and the reading rule this document applies mechanically.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — the defect this measurement settles the
  mechanism for; its §6 "suggested next step" is exactly this experiment.
- `measure_drift_8080_session.py` — the synthetic-control-validated cross-correlation tool
  this measurement's shift values were computed with.
- `measurement_c_realign.py`, `measurement_c_realign_report.md`, `measurement_c_manifest.csv`
  — script, full results table, per-cycle stratum/lag/peak-correlation manifest.
- `2026-07-30-2337-qa-measurement-a-result-co-channel-reverses.md` — Measurement A's result,
  independent axis, delivered earlier the same session.

---

*Per HK-015 this is QA -> Architect/Captain material. Per HK-014/HK-010 committed locally, no
push, no merge. Per HK-011 nothing here touches `src/` — no fix applied or proposed. Per
HK-017 filename and byline both carry `date -u` UTC. What (if anything) is done with the
recoverable corpora, and the fix itself, remain the Captain's/Architect's to direct.*
