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

## 1a. AMENDMENT 2026-08-22 16:57Z — the slope above is STALE as of shim `20260046`

**Author:** Architect. **Trigger:** the negative-`time_offset` SNR fix
(`c3a9ea8`, `FT8_SHIM_VERSION` 20260045 -> 20260046,
`openspec/changes/fix-negative-time-offset-snr-collapse/`), which corrects a
`signal_db` indexing defect affecting every candidate whose sync position precedes
the decode window.

**The §1 slope and intercept were measured on pre-fix output and may no longer be
quoted as current.** The verdict is unchanged -- the slope is still nowhere near
1.00 and this defect still stands -- but the headline numbers move.

**Sizing (an ESTIMATE, not a re-measurement).** Measured on the WINDOW_20M replay
pair `qa/rr-study/r2-coherent-llr-instrument/results/replay_win_amend2.json`
(pre-fix) vs `replay_win_negdt_fix.json` (post-fix), 250 cycles, 4,842 decodes,
identical on both platforms:

| quantity | value |
|---|---:|
| decodes with `dt < 0` (pre-fix) | 117 (2.42 %) |
| decodes whose SNR changed | 95 (1.96 %) |
| mean change on those | **+5.54 dB** |
| their mean SNR (pre-fix) | -24.7 dB (corpus median -11.0 dB) |
| aggregate corpus mean SNR shift | **+0.109 dB** |
| estimated OLS slope shift | **-0.021** (0.6865 -> ~0.666) |

**The aggregate shift is negligible; the slope shift is not.** The affected decodes
sit at the *low* end of the range, so they ROTATE the fit rather than translate it.
The estimated -0.021 is roughly **5x the published 95 % CI half-width (+-0.0041)**,
i.e. it moves the point estimate outside its own interval.

🔴 **Direction, stated because it is counter-intuitive: the fix moves the slope AWAY
from 1.00.** The negative-`dt` defect was slightly MASKING this gain error. Corrected,
the gain error reads marginally WORSE, not better.

⚠️ **Three limits on the figures above -- do not over-read them:**

1. **This is a projection, not a re-measurement.** It applies WINDOW_20M's 2.42 %
   `dt < 0` rate to §1's fit. The three corpora §1 actually measured may carry a
   different rate.
2. **Re-deriving requires an AUDIO REPLAY through the fixed binary.**
   `measurement_a2_snr_gain_regression.py` parses archived `ALL.TXT`, so re-running
   it as-is reproduces the stale pre-fix SNRs verbatim and would look like a
   confirmation. The WAVs exist (`20260729_live_run_1831-8081`, 5,773 `owsfz` WAVs
   per `qa/ARTEFACT_INVENTORY.md`), so this is feasible but not cheap.
3. **§1's corpora are jt9-referenced, and offline `jt9 -d 3` is VOIDed as a reference
   decoder** (see `MEMORY.md`). Per the project's own rule -- bias corrupts LEVELS far
   more than SLOPES -- the slope half of §1 largely survives that; it is the "we read
   low by 3.20-8.04 dB" LEVEL column that is the more suspect half, independently of
   this fix.

**No re-run is proposed.** This amendment exists so the §1 numbers are not re-quoted
as current.

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

✅ **DIRECTLY MEASURED 2026-08-22, and the rejection now has a second, independent
leg.** On the 250-cycle WINDOW_20M replay above, the negative-`time_offset` fix changed
95 decodes' SNR by up to +15 dB and produced **zero new decodes and zero lost decodes**.
The reason is mechanical, not luck: every affected decode sits below the ramp's own
`K_SOFT_SUPP_SNR_MIN_DB = -5.0` floor both before (-34..-12 dB) and after (-33..-10 dB)
the correction, so the attenuation factor stayed pinned at 1.0 on every one of them --
**0 ramp crossings, 0 factor movement**, an identical pass-1 waterfall. On this corpus
the suppression path was provably dormant. ⚠️ **That is a statement about this corpus,
not a general one:** a STRONG early signal (`time_offset < 0`, true SNR well above -5 dB)
would have been under-reported INTO the no-suppression zone pre-fix and left unsuppressed,
masking weaker neighbours in pass 1. WINDOW_20M contained no such signal. The fix closes
that hole prospectively; it did not cash out here.

**The H5 result below is already tested and rejected.** `ft8_shim.c`'s own history records
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
- `openspec/changes/fix-negative-time-offset-snr-collapse/` + `c3a9ea8` (shim `20260046`) --
  the negative-`time_offset` `signal_db` fix that makes §1's slope stale; see §1a.
- `qa/rr-study/2026-08-22-1623-qa-to-architect-fix-negative-time-offset-snr-collapse-acceptance.md`
  -- QA's acceptance of that fix (B-dt-C3 re-run, `max_p delta(p)` 17.4 dB -> 0.400 dB).
