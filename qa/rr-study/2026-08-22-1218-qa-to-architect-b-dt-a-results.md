# QA -> Architect: arm B-dt-A results -- ROW 2 FIRES, B1 does NOT fix the SNR collapse

**Author:** QA
**Date:** 2026-08-22 12:18 UTC (`date -u`, HK-017)
**Spec:** `qa/rr-study/2026-08-21-2334-architect-to-qa-preserve-phase-b-binaries-and-spec-b-dt-a.md`, section 3.
**Status:** TASK 1 (section 1.3, verify-don't-inherit) discharged. TASK 2 (arm B-dt-A) RUN.
**Headline: ROW 2 FIRES -- the DT=0.0 SNR collapse survives the Phase B origin fix (B1)
essentially unchanged. Amendment 2, as corrected by Amendment 3, PROCEEDS. The getter build
is required.**

---

## 0. TASK 1 section 1.3 -- verification performed, not inherited

Independently re-checked before relying on the archive for anything below:

1. `sha256sum -c SHA256SUMS` -- **PASS** in both `artefacts/2026-08-21-phase-b-pre-amendment-2-binaries/`
   (D:) and `C:\Users\Frank\.claude\projects\D--Projects-claude-OpenWSFZ\preserved-binaries\2026-08-21-phase-b-pre-amendment-2\`
   (C:). `cmp` byte-for-byte between the two archive locations: identical.
2. Hashes equal section 1.1's values exactly: `libft8.dll` = `a3d32b7839a0fd73...`,
   `libft8.so` = `13d9799d91388d9e...`.
3. `ft8_get_last_snr_terms` -- **absent** from all four binaries (grep-on-binary, 0 hits).
   `ft8_ldpc_decode_llrs` -- **present** (1 hit in both DLLs, 2 in both SOs, consistent with
   two call sites/one string table entry pattern). Confirms: this is Phase B, this is
   pre-Amendment-2.
4. **The working tree's own `src/OpenWSFZ.Ft8/Native/{win-x64/libft8.dll,linux-x64/libft8.so}`
   already hash to the same two values** -- the build under test did not need copying in from
   the archive; it was already live. No `src/` edit was made to arrange this.

A backup nobody has verified is not a backup. This one now has been, independently.

---

## 1. Preconditions (spec section 3.3) -- all asserted, not assumed

| # | Precondition | Result |
|---|---|---|
| 1 | Binary identity == `a3d32b78...` / `13d9799d...` | **PASS** (section 0.4 above) |
| 2 | `--device "Voicemeeter AUX Input"` passed explicitly | **PASS** -- confirmed in run log: `Device 'Voicemeeter AUX Input' matched 3 host-API entries; selected [80] Voicemeeter AUX Input (VB-Audio Voicemeeter VAIO) via Windows WASAPI (48000 Hz)` |
| 3 | `captureActive=true` before arming | **PASS** -- live daemon heartbeat confirmed `captureActive=True, audioActive=True, dataFlowing=True` immediately pre-run |
| 4 | `ALL.TXT` cleared before the run | **PASS** -- both WSJT-X's and OpenWSFZ's `ALL.TXT` cleared to 0 lines before arming (WSJT-X's by the Captain, OpenWSFZ's by QA); pre-clear copies of both preserved non-destructively in `qa/rr-study/results/2026-08-21-7d36038/*.livecopy-preclear` rather than discarded |

Scenario JSONs re-confirmed unchanged since `7d36038` immediately before the run:
`git diff 7d36038 -- s2-freq-sweep.json s3-dt-offset.json s8-band-scene.json` empty on all
three. The pre/post contrast is not confounded by a scenario edit.

`--skip-warmup` used, same deviation the `7d36038` sweep itself used minutes earlier on
identical routing (that sweep completed clean, PASS verdict, same device string) -- disclosed,
not silent.

Run directory: `qa/rr-study/results/2026-08-22-d4ce254/` (date + current HEAD short SHA, per
`make_run_dir`). Scenarios run: S3, S2, S8, targeted (`--scenarios S3,S2,S8`), bypassing the S8
prompt. S4/S7 not run -- schedule did not call for them and the spec says not to cut S3/S2/S8
to fit them in.

---

## 2. Definitions used (spec section 3.4, unchanged)

- `M0` = mean(reported_snr - true_snr), OpenWSFZ matched decodes, `true_dt_s == 0.0`, pooled
  across S3+S2+S8.
- `Mplus` = same, `true_dt_s > 0.0`.
- Cluster = distinct `(scenario_id, part_index, true_freq_hz)` triple.
- Readout quantum = 1 dB. All distances below resolved against that quantum, not a bootstrap SE.

---

## 3. ROW 0 -- VALIDITY

| | dt=0.0 | dt>0.0 |
|---|---|---|
| Clusters (OpenWSFZ matched) | **10** | **20** |

Both clear the `>= 10` floor. **ROW 0 does NOT fire.** Matches the Architect's own recorded
prediction (85%) -- HIT.

Cluster composition, dt=0.0: S3 part 0 (1500 Hz) + nine of S8's ten stations (450, 650, 850,
1050, 1150, 1500, 1900, 2150, 2550 Hz). S8's tenth station (I, 1650 Hz) sits at `true_dt > 0`
and falls in the other stratum, alongside S3 parts 1-9 (nine clusters, all 1500 Hz) and all
ten S2 clusters. **S8 station F (1162 Hz) contributes to neither stratum** -- OpenWSFZ did not
decode it at all this run (0/5, per `report.md`'s per-station table), continuing the
three-sweeps-running pattern already on the board. That is a separate, pre-existing defect,
not scoped here, and it does not touch ROW 0's count either way.

---

## 4. ROW 1 / ROW 2 -- THE GATE

| | M0 (dB) |
|---|---|
| **Post-B1 (this run)** | **-14.104** |
| Pre-B1 (`7d36038`, same three scenarios) | -14.333 |
| Pre-B1 (`7d36038`, pooled across all eight scenarios, Amendment 3 sec. 2.2) | -13.9 |

`M0 = -14.104 dB`.

**ROW 1 (`M0 >= -5.0 dB`) does NOT fire.**
**ROW 2 (`M0 < -5.0 dB`) FIRES -- COLLAPSE PERSISTS.**

Distance from the -5.0 dB line: **9.1 dB (9.1 quanta)** clear, not a boundary call
(HK-021(m)). Matches the Architect's recorded prediction (ROW 2, 65%) -- HIT.

**Movement from pre-B1 to post-B1 is +0.229 dB on the matched three-scenario baseline** --
well under one readout quantum, i.e. **statistically and operationally indistinguishable from
no movement at all.** B1 (the waterfall origin fix) does not partially attenuate this defect;
it does not touch it.

---

## 5. Reported, not gated (spec section 3.6)

**5.1 Full S3 per-part profile, post-B1 (OpenWSFZ, n=3/part):**

| Part | true_dt (s) | mean err (dB) | mean reported_dt (s) |
|---|---|---|---|
| 0 | 0.0 | **-15.67** | -0.200 |
| 1 | 0.3 | 1.00 | 0.167 |
| 2 | 0.6 | 1.33 | 0.400 |
| 3 | 0.9 | 2.00 | 0.700 |
| 4 | 1.2 | 2.00 | 1.000 |
| 5 | 1.5 | 1.67 | 1.400 |
| 6 | 1.8 | 1.33 | 1.600 |
| 7 | 2.1 | 2.00 | 1.900 |
| 8 | 2.4 | 2.00 | 2.200 |
| 9 | 2.7 | 1.00 | 2.500 |

Only part 0 (true_dt = 0.0) collapses. Every other part sits at +1.0 to +2.0 dB, matching
Amendment 3's pre-B1 shape almost exactly (pre-B1 parts 8/9 were +2.0/+1.0 per the spec's own
note that these two are no longer mislabelled). **B1 moved nothing in this profile's shape.**

**5.2 `Mplus` and `M0 - Mplus`:**

`Mplus = 1.339 dB` (post-B1) vs `1.258 dB` (pre-B1, same three scenarios) -- also
sub-quantum movement. `M0 - Mplus = -15.443 dB` post-B1 vs `-15.591 dB` pre-B1. The
within-run contrast is unchanged.

**5.3 `reported_dt` at S3 part 0:**

**-0.2 s, 3/3, identical pre- and post-B1.** This is the single cleanest number in this run:
if B1 had touched the mechanism, the reported DT is exactly where it would show first, and it
did not move at all. Matches the Architect's recorded prediction (60%) -- HIT.

Individual post-B1 rows, OpenWSFZ, S3 part 0 (true_snr=0, true_dt=0.0, freq=1500):

| reported_snr (dB) | reported_dt (s) | reported_freq (Hz) |
|---|---|---|
| -15.0 | -0.2 | 1500.0 |
| -16.0 | -0.2 | 1500.0 |
| -16.0 | -0.2 | 1500.0 |

WSJT-X, same three trials, same cycles: reported_snr **+1.0 / +1.0 / +1.0**, reported_dt
**-0.8** (WSJT-X's own convention offset, unrelated -- see section 5.5). The 16-17 dB gap
between the two appraisers on identical audio is unchanged from Amendment 3's pre-B1 reading.

**5.4 Composition diff (OpenWSFZ matched clusters, pre-B1 vs post-B1, S3+S2+S8):**

**Zero dropped, zero gained, 30/30 common.** The identical set of 30 `(scenario, part,
freq)` clusters decoded both before and after B1 -- this is the strongest form of "no swap
at constant count" available: not merely equal cardinality (which ROW 0 already can't tell
apart from a swap per the spec's own HK-022 note) but an exact set match, verified by
computing both sets independently from the matched CSVs and diffing them.

**5.5 WSJT-X on the same run, all strata (standing cross-check):**

| | M0 (dB) | Mplus (dB) |
|---|---|---|
| WSJT-X, this run | **+0.911** | +0.742 |
| WSJT-X, `7d36038` pooled (Amendment 3) | "+0.5 to +1.0 across all seven" | -- |

Stable, no collapse, consistent with the pre-B1 reading and with Amendment 3's discriminator.
**The audio and truth labels did not move between runs.** The defect stays localised to
OpenWSFZ's own SNR estimator, not the harness.

Per spec section 3.7: the `wsjt_dt_correction_s: 0.55` calibration note does not touch
anything gated or reported here -- every row above stratifies on **true** DT and compares
**SNR**, never reported DT between appraisers.

---

## 6. What this does and does not settle

**Settled:** B1 (the waterfall origin fix) does not fix, and does not measurably move, the
DT=0.0 SNR collapse. The composition diff rules out a swap at constant yield as an
alternative explanation. Amendment 2, as corrected by Amendment 3, is **not deferred** --
per the spec's own ROW 2 consequence, it **proceeds**, and the `ft8_get_last_snr_terms`
getter remains the only remaining way to localise the defect to `signal_db` vs
`local_noise_db`.

**Not settled, and not claimed here (unchanged from Amendment 3 section 2.6/2.5):** that
this costs decodes; that fixing it helps D-001; the boundary shape between DT 0.0 and 0.2/0.3
(still unmeasured, still HK-026-blind between those two grid points); anything about negative
DT (`S3b`, still built-not-run).

Gage R&R side effects of this run, informational only, matching `report.md`: S2/S3 GR&R both
PASS (%GR&R 0.0%/0.4%, ndc 1491/22); S8 holistic decode rate 83.33% OpenWSFZ vs 96.67%
WSJT-X, station F (1162 Hz, -8 dB) again 0/5 for OpenWSFZ -- fourth consecutive full/partial
sweep with that exact result, now worth a dedicated look on its own, separate from this arm.

---

## 7. Predictions scored (spec section 5)

| Prediction | Confidence | Outcome |
|---|---|---|
| ROW 0 does not fire (yield holds) | 85% | **HIT** |
| ROW 2 fires -- B1 does NOT fix the SNR collapse | 65% | **HIT** |
| `reported_dt` at S3 part 0 is still -0.2 post-B1 | 60% | **HIT** |
| If ROW 2 fires, collapse localises to `signal_db`, not `local_noise_db` | 80% | **UNSCORED -- requires the getter, not yet built** |

Three of four score HIT; the fourth is exactly the one the getter build exists to answer, and
stays open until that build runs.

---

## 8. What this does NOT license (unchanged from spec section 4)

No `src/`, native, or `ft8_shim.c` change was made here -- read-only analysis plus the file
copy in section 0. HK-011 is not engaged by this document. Does not license S3b or any
negative-DT work. Does not touch H5, the SNR formula, suppression, or
`K_SOFT_SUPP_SNR_*`. Does not bear on ROW 0g (still FIRED), task 4.3 (still VOID), Route B2
(not dead), or B3 (HELD).

**Next:** per ROW 2's own consequence, the Amendment 2 getter spec is unblocked to proceed to
a Developer session -- that is an HK-011 Captain call, not QA's to open. QA stops here and
reports.
