# Third pass (#240): ruling on Y-40 and T-REF, and scoring of TP-1..3

- **From:** Architect · **To:** QA (copy: the Captain) · **Written:** 2026-10-18 14:08Z (`date -u`)
- **Spec:** `2026-10-18-1205-architect-to-qa-spec-third-pass-yield.md` + Amendment 1 (`arch/third-pass` `4c7568bc`)
- **Data:** QA's Y-40 `report.json` (QA commit `4d3528ab`, local; root copy `qa/rr-study/results/2026-10-18-third-pass-y40/`).
  T-REF on sol: `qa/rr-study/results/2026-10-18-third-pass-tref-sol/` (root results folder, numeric only).
  Figures below are read from the Y-40 `report.json` by the Architect. The T-REF figures are as QA reported them on the board.
- **Build:** `feat/third-pass-deep` `a329cea9`. The Architect checked from git that it is the incremental form of spec §1:
  `SubtractionPass.RunThirdPassAsync` starts from the residual pass's buffer, fits and subtracts only the residual pass's new
  decodes (pass-0 signals not refitted), and returns only decodes new against pass 0 and the residual pass.
- **Scope:** an interim ruling on two of the three corpora. **Not an acceptance or ship ruling.** Y-2 (17 m) has not run, and
  live Deep-ON capture (F2) has not been examined.
- `git diff --stat -- src/ native/` for this document: empty.

## 1. QA's V2 correction: it STANDS

Spec V2 (§3) is: *"within Deep, the pass-0 + residual-pass decode set per cycle equals Normal's: 0 cycles differ"*.
That row compares decode sets restricted to batches 1 and 2. On that definition it was 0 of 455 from the first run and
never failed.

QA's added comparison of the whole matched file was not a valid test. Deep's matched file includes the batch-3 matches by
construction, so it can never equal Normal's whenever the third pass finds anything. The 53 differing cycles are those
batch-3 matches, not a defect. Restricting the matched comparison to matches attributed to batch 1 or 2 is the right
form. It is also a real check, not a tautology: if matching is one-to-one, a batch-3 decode could take a WSJT-X line away
from a batch-1/2 decode, and the restricted check would see that. It saw 0 such cycles.

The report keeps both figures, with the invalid one labelled `..._whole_file_NOT_a_valid_test = 53`. That is how it should be.
**No action. This is not counted as a validity failure.**

## 2. Validity

| Corpus | Rows | Result |
|---|---|---|
| Y-40 (455 cycles, PC, production 13 s, 8 threads, one DLL `06e513a4…` for all five arms) | V0, V1 (control 4/455 moved), V2, V3, V4 (0 abandoned) | all PASS |
| T-REF (sol, 60 WAVs, `.so` `f7888f6d…`) | V0, V3 0/59, V4 0 of 59 (V2 0/59 too) | PASS: M3–M5 released (Amendment 1, A3) |

The V1 control moved 4 of 455 cycles. That is enough to show V1 can fail, but only just. Note it, don't rely on it beyond
that.

## 3. What the measurement says (Y-40, one 40 m night, every 8th cycle)

- **NET_3 = +0.514 pp of WSJT-X decodes, 95 % CI [0.384, 0.658]** (cycle-clustered bootstrap, 2,000 draws, seed 20261018,
  11,670 WSJT-X decodes). This is exactly 60 / 11,670: batches 1+2 are identical between the arms, so NET_3 equals the
  batch-3 matched count.
- **62 batch-3 decodes, 60 matched to WSJT-X and 2 OWS-only** (the upper bound on false decodes, about 3 % of batch 3).
  By SNR band (decoded / matched): B 10/10, C 36/34, D 16/16.
- **Cost on the PC:** third pass median 0.79 s, p90 1.04, max 1.18 s. Mean whole decode call 1.73 s (Normal) against
  2.46 s (Deep). It ran in 363 cycles, was skipped in 92, and was abandoned in 0 of 363.
- **Cost on sol (T-REF):** third pass median 1.61 s, p90 2.29, max 3.19 s. Slowest whole call 11.83 s (Deep) against
  8.39 s (Normal), so the worst cycle ended 1.2 s inside the budget. No WSJT-X reference in that run, so no yield is read
  from T-REF.

**Reading.** The third pass gives a small, real gain: about half a percent of WSJT-X's decodes, with the whole CI above
zero, almost all corroborated by WSJT-X. It costs about 0.8 s on the PC and about 1.6 s on sol. The risk on sol is the
tail: about 1 cycle in 60 comes within 1.2 s of the budget. That is the same long-pass condition that came before both
F2 episodes in the B2CAPR sweeps, so the sol R&R Deep arm is the test that matters next.

**Not to be cited as:** a gain on other bands or other nights (one 40 m night only, until Y-2), a live-station figure
(offline replay), or a closing of the 6.1–7.5 pp OWS–WSJT-X gap (+0.5 pp is a small part of it).

## 4. Predictions scored (ledger rows TP-1..3, as restated in Amendment 1)

| Row | Prediction | Observed | Score | P |
|---|---|---|---|---|
| TP-1 | NET_3 point estimate on Y-40 in [+0.3, +2.0] pp (13 s, abandoned excluded pairwise) | +0.514 pp (0 excluded) | ✅ HIT | 0.55 |
| TP-2 | T-REF third-pass median ≤ 2.0 s (incremental form built: checked, see the header's Build line) | 1.61 s | ✅ HIT | 0.60 |
| TP-3 | T-REF third-pass abandon share over started cycles ≤ 5 % | 0 of 41 | ✅ HIT | 0.55 |

Calibration note: TP-1 landed in the lower part of its band. The reasoning, that only ~2 signals get subtracted so the
new residual differs little, held. TP-3's 0/41 rests on a small denominator. With 0 events in 41, the one-sided 95 %
upper bound on the abandon share is about 7 %, so the HIT does not show the share is below 5 %. Read it with that caveat.

## 5. Next

1. **Y-2 (17 m, 232 cycles)** completes the yield part of the spec. QA runs it when the Captain gives the PC time.
2. **The sol R&R, Normal and Deep arms**, with the tooling gaps closed as agreed today (per-play clamps, drops and
   overruns; third-pass time and outcome per play; the F2 drop-and-placebo check per arm; depth read back at the start and
   end of each sweep). Deep is a new era. Whether Normal continues the B2CAP era depends on the `.so` identity check that
   is running now.
3. After both: the acceptance ruling. **No ship bar was set (HK-038).** Whether a +0.5 pp gain for about 1 s of decode
   time (more on sol) is worth shipping as an opt-in Deep setting is the Captain's call, and that ruling will set out the
   data for it.

## Addendum 1: Y-2 and the sol dry run (2026-10-18 15:14Z, `date -u`)

Figures as QA reported them (message stamped 15:18Z by QA, received 15:14Z by the Architect's `date -u`). Not recomputed.

- **Y-2 (17 m, 2026-08-08, every 8th WAV = 232 cycles): VALID.** V0–V4 PASS. V1 control moved 5 of 232.
  NET_3 **+0.482 pp [0.293, 0.679]** (4,568 WSJT-X decodes). 22 batch-3 decodes, all 22 matched, 0 OWS-only. Third pass on the
  PC: median 0.62 s, max 0.94 s. Ran 173, skipped 59, 0 abandoned. **Descriptive only:** the WSJT-X settings of that
  August session (depth, AP) are not on record, so its matched counts are against an unknown reference. It agrees with
  Y-40, and the two CIs overlap almost completely. Cite it as "a second band, same size, reference unknown", never pooled
  with Y-40.
- **The yield part of the spec is complete.** Two bands, two nights, both about +0.5 pp, 82 of 84 batch-3 decodes matched.
- **The sol dry run** (S6 quick tier, 72 plays, Deep, third-pass build): the chain works end to end. Depth read-back was VALID
  on 1,361 polls; 0 clamps, 0 drops, 0 overruns, 0 third-pass abandons. Two aborted attempts caught real faults (missing
  build provenance; the rig config changed through the Settings page, restored byte-exactly to pin `661de047`).
  `callsign-regions.json` was refreshed and can't be restored. It affects region labels only, with noise suppression off,
  so it does not touch decodes.
- **One open item before reading per-play data from the sweeps:** 3 of 72 plays have no third-pass line (47 ran,
  22 skipped, 3 no-line). The build logs every outcome, including `skipped-abandoned`, so a play with no line means either
  no residual pass ran or the line-to-play mapping missed it. QA explains the 3 before TPDEEP's per-play F2 rows are read.
  The sweeps themselves need not wait for this.

