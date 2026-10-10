# RULING — SUB-FEAS first on-air run (flag ON, 8 workers, 17.9 h, receive only)

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-01 ~15:00Z
- **Reviewed:** `qa/rr-study/results/2026-10-01-sub-feas-first-on-air-run/report.md` @ `7c3e7147` (`qa/sub-feas`, local, not pushed)
- **`src/` / `native/` diff:** none (docs only; `git diff --stat -- src/ native/` empty)
- **Claims NOT made:** no decode-rate claim; the +12 pp matched-% movement in Section 4 is NOT cited (different night, build, shim and flag at once; no concurrent flag-OFF control).

## 1. Is this enough for §8.2 live use at 8 workers?

**For the stability half: yes. For §8.2 itself: no, and the report is right not to say it is.**

- §7 (sustained stability) is **MET on this record**: 4 298 passes, 0 abandoned, 0 contained exceptions, 0 WRN/ERR/FTL, memory −0.94 MB/h with 45.7 % of steps rising (no leak signature), no flag drift, no restarts. Accepted.
- It is evidence that **8 workers is safe on this CPU with WSJT-X running** on a typical 40m night. It is **not** evidence for the 29+ band (10 cycles, no bound) and it does not separate load from band activity (Measure B is correlational, as the report says).
- §8.2 is the question whether the extra decodes are real. Nothing here answers it. **The flag stays OFF by default.** Continued flag-ON, RX-only, pinned-config runs at 8 workers are fine. Turning it on by default, or letting batch 2 reach the answerer on air, remains the Captain's decision and is not supported by this run.

## 2. Default thread count

**No change on this data.** The run supports 8 as the *pinned arm value* only. It did not test 12, 14 (the spec A4 default, `max(1, ProcessorCount − 2)`) or a different CPU. The default stays as specced until the 12-worker quiet check and the per-fit completion log are in. Do not argue a default from a pinned-8 night.

## 3. Offline flag-OFF/ON replay of the 4 299 archived cycles — **yes, this is the controlled test**

Approved as the next decode-rate step, ahead of Stage B. Constraints I will hold it to (spec to follow from me, pre-registered and mechanical):

1. Same build `247ac391`, same shim `20260056`, same pinned DLL SHA, **flag is the only difference**; fresh process per arm; numeric ordered; 8 workers; `nhard` 40.
2. Reference is the live WSJT-X `ALL.TXT` for the same cycles; the estimand is the NET change in matched decodes (OFF→ON), paired per cycle, with the OFF replay as the control (the lesson from the 0.76 pp original-PCM replay).
3. Honest scope: this is **a second night on the same band and station**, not a second band. It satisfies "second-corpus" only for night-to-night, not for band. Say so in the report.
4. Replay is not the live path (`ALL.TXT` is post-plausibility and post-dedup); compare outcome fields, never rendered text. HK-037 applies: aggregates only.
5. The station is released, but the PC's CPU is shared: no overlapping test suites or builds during the replay timing.

## 4. Smaller notes

- Pre-arm flag `wsjtx_ini_dial_freq_matches_daemon: false` was not re-investigated. Matched-pair frequency means agree (1 482.4 vs 1 482.3 Hz), so I accept it for this run; log it as an open pre-flight item, not a closure.
- Two cycles without a residual line (4 300 vs 4 298): accepted as window edges only if you confirm that from the stamps. One line in the next report is enough.
- Summariser case fix accepted.
- No same-chain (B1) spectrum control exists; the cross-chain comparison is fine for "no anomaly", not for a chain claim.
