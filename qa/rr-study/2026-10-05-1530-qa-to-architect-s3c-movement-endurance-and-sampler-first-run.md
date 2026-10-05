# QA to Architect, 2026-10-05 15:30Z (by `date -u`): S3c movement, the 2026-10-04 endurance run, the sampler's first live run

To: Architect (next session). From: QA. No reply needed unless you want an arm.

## 1. S3c OpenWSFZ E -2.00 moved: 32/32 (baseline-194: 17 and 16 of 32)

R&R S1-S8 on `main` 766f9cc2 (VERSION 0.56, shim 20260058, flag ON), report
`qa/rr-study/results/2026-10-04-766f9cc/report.md`. Overall PASS. r_ref 0.282, guard row PASSES.
This is the THIRD S3c battery, so S3C1/S3C2 scoring is yours. Cause NOT established: the only
decoder-touching commits since `cddd7e34` are step 4's (`fee81a2b`, `ca8e3118`), and one battery
cannot separate that from luck. Proposed separating test (parked on #194, needs the Captain's go):
replay with `earlyDecodeEnabled` off and on. Not run.

## 2. Endurance run 20261004_1634 (40 m, 12.93 h, `main` 040613d9, flag ON, nhard 40)

Section 4, same-band live-WSJT-X rows. This row is flag-ON; only 2026-09-30 is comparable to it.

| run | matched pairs | matched % of WSJT-X | OWS-only % | SNR gap (dB) | DT gap (s) |
|---|---:|---:|---:|---:|---:|
| 2026-09-30 (flag ON) | 94 307 | 72.8 | 1.1 | -1.546 | +0.6611 |
| 2026-10-04 (flag ON) | 68 387 | 70.3 | 1.1 | -2.280 | +0.6588 |

Descriptive only: one night each, different lengths, no build effect claimed. Four monitoring-test
windows (26 cycles per appraiser) were excluded by timestamp on the Captain's ruling. Spectrum scan:
hum consistent with the 09-30 control, top spur resolved as real station traffic, no clipping.

## 3. #194 sampler, first live run (the "first integrated run" the five-run review waits on)

Coverage 100.0 % of 46 594 s, 0 crashes, 0 restarts, 64 change records (24 inside the Captain's
tests, 40 outside), `unverified_start_diff` 0, start and end snapshots differ in 5 fields.
It caught both movie-on-B1 changes and 5/5 slow toggles; of about 15 fast taps only 5 on/off pairs
were logged (about 1 in 3), `vm_dirty_nonzero` 14 in that heartbeat (mechanism untested). The
WSJT-X slider test was VOID (it was the TX slider). The ledger
`qa/audio-setup/integrated_runs.csv` holds only its header: this run is run 1 of the five. Its row
is NOT yet written: it needs the scan-flagged-slot join (`summarize.py --flagged`), which the
endurance summary says was not computed. The R&R of 2026-10-04 had NO sampler output.

## 4. Housekeeping

PR #211 (`qa/main-with-sampler`, QA tooling only, src/native diff empty) is open, NOT merged;
merge needs the Captain. The supervisor recorded `osd_nhard_max` null in `arm_config.json`
(nhard 40 comes from the config), so Section 4 shows `?` unless stated in the radio-chain cell.
