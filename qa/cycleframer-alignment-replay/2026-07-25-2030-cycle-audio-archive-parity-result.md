# `cycle-audio-archive` D-001 diagnostic (tasks.md §9): capture-chain parity confirmed

**Author:** QA, 2026-07-25 (20:30). **Status:** answers `tasks.md` §9.1-9.4. Executes the
decisive experiment the Architect proposed in
`2026-07-25-1200-architect-second-mechanism-located.md` §5.

---

## 0. Verdict

**Parity.** OpenWSFZ's own captured audio (`WasapiAudioSource`'s 48 kHz -> left channel ->
`WdlResamplingSampleProvider` -> 12 kHz path) decodes just as well as WSJT-X's independent
recording of the same off-air RF, at production decoder settings. **The capture chain is not
the defect.** Per the Architect's own decision tree (§5, item 3), this points the D-001
live-path investigation at the *live decoder invocation* (process-lifetime native state) as
the next probe, not at `WasapiAudioSource`/the resampler.

## 1. Method

- Daemon already running live on 40 m (7.074 MHz dial), device "Microphone (2- USB Audio
  CODEC )" -- the same device the D-001 clock-rate finding (`phase3_clockrate_results_usbcodec.json`)
  was measured against.
- `cycleAudioArchive.mode` set to `all` via the live `POST /api/v1/config` endpoint (no
  restart needed -- `CycleArchiveService` reads `IConfigStore.Current` per cycle).
- ~20.5 minutes of concurrent capture: OpenWSFZ's own archive
  (`%AppData%\OpenWSFZ\cycle-audio\`) alongside WSJT-X's own recording
  (`C:\Users\Frank\AppData\Local\WSJT-X\save`), same rig input, same dial frequency,
  overlapping wall-clock window.
- `DroppedCycles: 0` throughout on our side; `cycle-archive.csv` shows zero clipped samples
  and zero gaps (`dropped_before` all zero) across every row.
- Filename-matched intersection: both arms independently write `YYMMDD_HHMMSS.wav` (rounded
  to the same UTC second). **68 of our 84 files and 68 of WSJT-X's 75 files shared an exact
  filename** -- restricting to this common set is the fairest per-cycle pairing available,
  and does not depend on either side's own cycle-boundary timing being correct (each side's
  filename is that side's own claim about which 15 s slot the audio belongs to; where the two
  independently-clocked systems agree on the label, comparing the audio each captured for that
  label is meaningful).
  - Note in passing: WSJT-X's own directory has irregular gaps (e.g. `..0500` -> `..0530`,
    skipping `..0515`; `..2645` -> `..2715`, skipping `..2700`) -- WSJT-X's own save cadence is
    not perfectly regular either. Not investigated further; out of scope for this diagnostic.
- Decoded both 68-file sets with the restored `D001ParamSweep` harness
  (`qa/rr-study/d001-param-sweep-2026-07-22/`, brought back to `main` from the paused PR #108
  branch -- see companion commit `009199f`), restricted to `--points k10_c0.10_n60` (the
  production baseline: `kMinScorePass2=10`, `osdCorrThreshold=0.10`, `osdNhardMax=60`, matching
  live `config.json` exactly), `--dial-mhz 7.074`, `--fresh-decoder-per-wav` (SPEC.md
  section 7.4(b) -- prevents `Ft8Decoder`'s process-lifetime hash-table state from leaking
  across the comparison, which the alignment-replay study's cross-input-determinism control
  found otherwise reorders message text non-deterministically).
- Compared per-cycle decode yield and message-level (deduplicated by exact text) overlap.
  Ad hoc comparison script: `qa/cycleframer-alignment-replay/_work/compare_ours_vs_wsjtx.py`
  (git-ignored `_work/`, aggregate output only -- NFR-021).

## 2. Results

| | value |
|---|---|
| cycles compared | 68 |
| total decodes -- ours | 1284 |
| total decodes -- WSJT-X | 1288 |
| message-level: common to both | 1204 |
| message-level: only ours | 80 |
| message-level: only WSJT-X | 84 |
| naive pooled recall, ours vs. WSJT-X's messages | 0.935 |
| naive pooled recall, WSJT-X vs. ours' messages | 0.938 |
| cycles where ours = 0 but WSJT-X found >=1 | **0** |
| cycles where WSJT-X = 0 but ours found >=1 | **0** |
| cycles where both = 0 | **0** |
| `hashTableRejectCount` at end of run -- ours (68-file arm) | 656 |
| `hashTableRejectCount` at end of run -- WSJT-X (68-file arm) | 595 |

Per-cycle decode counts track each other closely throughout the full 68-cycle window (full
detail in `_work/compare_ours_vs_wsjtx.py`'s run output, not committed -- real callsigns).
Total decode counts differ by 0.3% (1284 vs. 1288); message-level overlap is ~94% each
direction, with the ~6% one-sided messages symmetric in count (80 vs. 84) and, by inspection,
consistent with ordinary near-threshold SNR noise (a borderline signal caught by one capture
chain's particular resampling-phase realization and not the other) rather than a systematic
one-directional bias. **Zero cycles collapsed to no decodes on one side while the other found
signals** -- the signature the 11h51m live endurance round (`2026-07-25-40m-band-9.5-fail`)
showed in 55-61% of cycles in its worst deciles is entirely absent here.

## 3. Interpretation

This directly executes the Architect's §5 decision tree:

> If OpenWSFZ's own capture yields materially fewer decodes than WSJT-X's capture of the same
> cycles, the defect is in the capture chain... If the two match, the defect is in the *live
> decoder invocation* (process-lifetime native state -- `g_session_hash_table`,
> `hashTableRejectCount`), and the next probe is a process-lifetime/restart-cadence test.

**The two match.** `WasapiAudioSource`'s 48 kHz -> left-channel -> `WdlResamplingSampleProvider`
-> 12 kHz path is exonerated as a source of the D-001 live-path recall loss, at least at this
session scale (~20 minutes, fresh-ish process: daemon had been running ~20-25 minutes total by
the end of this capture, `hashTableRejectCount` only in the hundreds -- nowhere near the 25,465
the 11h51m round reached).

**This finding is scale-limited, not yet a full closure.** The zero-decode collapse this
investigation is chasing is a phenomenon that emerges hours into a session (55-61% zero-decode
deciles appeared only in the second half of an 11h51m run) -- this diagnostic was deliberately
cheap (~20 minutes) and was never going to reproduce that by design. What it rules out is a
*constant* capture-chain defect (bad resampling, wrong channel, systematic level/clipping
issue) that would show up regardless of session length. It does not yet test whether the *live
decoder invocation's* process-lifetime state (native hash table, `hashTableRejectCount`) is
what degrades over many hours -- that is explicitly the next probe, not this one.

## 4. Consequences for `tasks.md` / next steps

1. `cycle-audio-archive/tasks.md` §9.1-9.4: **done**, this document is the 9.4 report.
2. §9.5 (disposition of paused PR #108): unaffected by this finding either way -- the Architect's
   recorded recommendation (re-scope §10's reset-conflation fix as correctness hygiene, not D-001
   recovery) stands; this diagnostic neither strengthens nor weakens that specific
   recommendation, since it addresses a different mechanism (capture chain vs. cycle-boundary
   timing) than PR #108 was chasing in the first place.
3. **Escalating to Architect/Captain per §9.4's instruction, before further live endurance time
   is spent:** the next probe this result points to is a process-lifetime/restart-cadence test
   -- does periodically restarting the decoder (or otherwise resetting
   `g_session_hash_table`/`hashTableRejectCount`) during a long live session recover the
   zero-decode collapse the 11h51m round showed? That is a new, not-yet-scoped piece of work,
   not something QA should simply start building off the back of one diagnostic result.
