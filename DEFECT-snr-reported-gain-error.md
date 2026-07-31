# Defect: Reported SNR Carries a Gain Error, Not an Offset

**Raised by:** QA, 2026-07-30 (23:51 UTC, `date -u`, per HK-017), on the Captain's direction,
per the Architect's ruling S7.
**Severity:** Moderate-to-high, **product-facing**. Not a D-001 finding and not folded into that
thread — raised standalone so it isn't lost, per the Captain's explicit instruction.
**Affects:** reported SNR in QSO records, live decode display, and outbound spots (external
reporting). Likely locus: `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — `compute_noise_floor` /
`compute_local_noise_floor_db` and the SNR formula (`SNR = signal_db - noise_floor_db - 26.5`).
**No fix proposed here.** Per HK-011/HK-015 this is QA-authored, routes to a Developer session
with the Captain's sign-off, and the correction shape is itself the open decision (§4).

---

## 1. The measurement

OpenWSFZ's own reported SNR is systematically **low relative to the reference decoder, by an
amount that grows with signal strength** — a slope problem, not a constant bias.

**Corpus-mean level** (Architect's ruling S7.1, `2026-07-30-2253-architect-ruling-cross-band-
density-law-and-capture-chain.md`), on matched decodes (identical message, identical cycle,
found by both decoders):

| corpus | our mean SNR | reference mean SNR | we read low by |
|---|---:|---:|---:|
| 80m (jt9) | +1.417 dB | +9.454 dB | 8.04 dB |
| 10m (jt9) | -4.950 dB | -1.755 dB | 3.20 dB |
| 20m (jt9) | -3.704 dB | +1.898 dB | 5.60 dB |
| ~~40m (live WSJT-X)~~ | ~~-13.061 dB~~ | ~~-0.563 dB~~ | **excluded — this corpus sits on the drifting capture device (see `DEFECT-capture-clock-drift-silent-decode-loss.md`) and is not a clean SNR sample** |

**Per-decode level** (this defect's own follow-on measurement, S7.4.2 —
`qa/cycleframer-alignment-replay/measurement_a2_snr_gain_regression.py`, re-run 2026-07-30/31,
n=41 668 matched decodes across the three jt9-referenced corpora, reusing `anova_common.py`'s
matching logic unmodified):

```
POOLED (80m + 10m + 20m, n=41668):
  ours ~= 0.6865 * reference - 4.742 dB
  slope 95% CI: [0.6824, 0.6906]        -- excludes 1.00 by a wide margin
  intercept 95% CI: [-4.793, -4.691] dB
```

Per-corpus slopes vary (80m 0.563, 10m 0.854, 20m 0.723) but **none reach 1.00**, and every
corpus's 95% CI excludes it. **A pure offset requires slope = 1.00. It does not hold anywhere.**
This confirms the ruling's three-point corpus-mean regression (`0.585x - 4.28`, residuals
+-0.53 dB) at full per-decode resolution — not an artefact of only having three points to fit.

The committed per-decode scatter (`qa/endurance/2026-07-29-5016363/anova_report_20m_snr_
scatter.png`, n=24 201) confirms this visually: the cloud crosses `y = x` near -20 dB and falls
progressively further below it as signal strength rises.

## 2. Why this matters

- **Certain, and it reaches the wider network.** Reported SNR is wrong in QSO records and in
  outbound spots, by up to ~8-12 dB on strong signals. Given the recent external-reporting work
  (leader/follower relay to PSK Reporter and similar), this error propagates off this machine.
- **D-002 did not fix this.** D-002 (June 2026) corrected an SNR bias with a *constant* — the
  shim's bandwidth term, -26.0 -> -26.5 dB (`SNR = signal_db - noise_floor_db - 26.5`). **A
  constant cannot correct a slope.** That is the likely reason SNR bias keeps re-appearing after
  being marked closed.
- **It is NOT density-driven.** Checked explicitly (ruling S7.2) because the alternative would
  have tied it to D-001's cross-band density law (see the escalated Measurement A result,
  `2026-07-30-2337-qa-measurement-a-result-co-channel-reverses.md`): the sparsest band (80m)
  shows the *largest* offset at corpus-mean level. The gain model explains all three corpora
  without a density term. **The two findings are independent** — do not conflate them.

## 3. A hypothesis considered and rejected — recorded so it isn't re-formed

`snr_db` is not merely reported metadata: it feeds the soft-suppression ramp
(`K_SOFT_SUPP_SNR_MIN_DB = -5.0`, `K_SOFT_SUPP_SNR_MAX_DB = +15.0`) that attenuates decoded
signals before the pass-1 candidate search. Under-reported SNR could mean strong signals are
under-suppressed, an attractive mechanism linking this defect to D-001's core gap.

**This is already tested and rejected.** `ft8_shim.c`'s own history records
`diag-d001-h5-suppression-tuning` (`FT8_SHIM_VERSION 20260011`), which shifted the ramp 10 dB and
was **REJECTED at -10.75 pp** (S7 46.24% vs H4 56.99%): "Over-suppression confirmed."

The one narrow reason this may not fully close the question: H5 translated the window (both
endpoints -10 dB, an *offset* correction), whereas this gain error needs a *slope* correction —
a translation over-suppresses weak signals while still under-suppressing strong ones, which is
exactly what H5's rejection note describes. **This is a caveat, not a claim, and no work is
proposed on it.** If it becomes live again, it needs its own measurement.

## 4. What is NOT established

- **The estimator mechanism.** The working hypothesis is a signal-contaminated noise-floor
  estimate (both estimators are histogram medians over waterfall bins — `compute_noise_floor`
  globally, `compute_local_noise_floor_db` over a K=32-bin sideband window per signal, from
  `fix-d004-local-noise-floor`). **Not measured. Not a finding.**
- **The correction shape.** Gain correction, full estimator redesign, or something else —
  genuinely open, and is the actual decision a fix would need to make.
- **Whether the slope is stable over time/hardware**, or varies with propagation/noise
  conditions beyond the three sessions measured here.

## 5. Recommended next step (not a fix)

Per HK-011/HK-015: author a dev-task scoping the estimator investigation (read
`compute_noise_floor`/`compute_local_noise_floor_db`, decide gain-vs-offset-vs-redesign) for a
Developer session with the Captain's sign-off. **No code change is proposed by this document.**

## 6. Process

Per HK-015 this is QA-authored. Per HK-011 nothing here touches `src/` — no fix is proposed; a
future dev-task for the *investigation* (not a fix) is separate. Per HK-014/HK-010 committed
locally only; no push, no merge implied. Per HK-006 no `pre_merge_check.py` run implied. Per
NFR-021 only aggregate figures appear here; the underlying `ALL.TXT`/WAV material stays under
git-ignored `artefacts/`.

## 7. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md`
  S7 — the original measurement and its rulings on scope (§7.2-7.4).
- `qa/cycleframer-alignment-replay/measurement_a2_snr_gain_regression.py` /
  `measurement_a2_snr_gain_regression.md` — this document's own per-decode confirmation.
- `qa/endurance/2026-07-29-5016363/anova_report_20m_snr_scatter.png` — the per-decode visual.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — why the 40m corpus is excluded here.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — SNR formula, `compute_local_noise_floor_db`,
  `K_SOFT_SUPP_*`, the H5 rejection record.
- D-002 (June 2026, constant-bias correction) — superseded assumption this defect corrects.
