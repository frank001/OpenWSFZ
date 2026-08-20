# Architect+Captain -> QA: S3 re-grid ruling, and G4 pre-registration

**UTC:** 2026-08-20 14:55Z
**Trigger:** Captain's direct instruction, this session: "we need to finish the S3b instrument."
**Disclosure (HK-015):** no separate Architect session is live this session. The two decisions
below were reserved for "Architect + Captain" on the board. The Captain's instruction is read as
authorising this session to draft both, under the same one-directional discipline (written before
any run, QA executes, no retroactive editing to match an outcome). Both are cheap, reversible, and
argued from evidence already on disk (HK-018) rather than fresh judgement calls.

**Does NOT authorise:** the full S3b live sweep (10 parts x 100 trials, ~4.2h unattended, HK-013
supervisor required), any `src/` change, any push or merge. Only S3's re-grid flag and G4 (a single
25-minute live part) are in scope.

---

## Sec.1 -- S3 re-grid ruling: option (b), no re-grid

**The question**, reserved 2026-08-19 in `2026-08-19-1630-...-route-b-negative-dt-build-spec.md`
Sec.0 and repeated at every G3 checkpoint since: S3's parts 8/9 (`dt_s` +2.4 / +2.7) exceed the
2.36s single-slot cap now that the positive-clamp defect is fixed. Two honest options were named:
(a) re-grid S3's parts to <= 2.36s, or (b) let the signal run into the next slot (the same
`requires_extended_dt` contract S3b already uses for its negative-DT parts).

**This is no longer an open judgement call -- G3 already measured it.** G3's primary gate
(`2026-08-19-1801-...-g3-jt9-sweep-results-row1-fires.md`) ran option (b) rendered for *both*
S3 parts 8/9 and all ten S3b parts, and read it on two independent instruments:

- WSJT-X `File > Open` (spot check, 3 files incl. `S3_part9_dt+2.7`): decoded clean.
- `jt9` x 20 files x 2 runs, byte-identical both times: **N = 20/20**, including
  `S3_part8_dt+2.4.wav` (15.04s) and `S3_part9_dt+2.7.wav` (15.34s) -- the exact two files this
  ruling is about.

Option (b) is not a proposal any more; it is a measured PASS across the full grid, on the same
render path S3 would use. Option (a) buys nothing that isn't already proven, and it would shrink
S3's own tested DT range for no compensating benefit -- purely a regression against the currently
validated grid.

**RULING: adopt option (b).** `s3-dt-offset.json` gets `"requires_extended_dt": true`, identical
to `s3b-dt-boundary.json`. No re-grid. Applied in this commit.

Scope check: this only lets S3's harness render parts 8/9 without raising (`run_scenario.py:249`'s
`ValueError` fires only when the flag is unset). It does **not** re-run S3's own Gage R&R study --
that stays a separate, non-blocking item. It exists purely so `run_scenario.py` no longer treats
S3 as a special case next to S3b, which is what actually blocks S3b (S3 and S3b share
`_render_single`; the un-set flag was a landmine for anyone re-running S3 after this build, not a
block on S3b itself -- flagged for completeness, not because it was gating this task).

---

## Sec.2 -- G4 pre-registration: live decode-rate gate at dt=0

**Committed before any run exists.** HK-021: mechanical thresholds, consequence stated as an
assertion, rows mutually exclusive, metric identifiable from `run_study.py`'s own output.

### Sec.2.1 Why (restated from the board, HK-026)

Without a baseline showing the LIVE chain (synthetic playback -> Voicemeeter AUX Input -> B1 ->
WSJT-X + OpenWSFZ, both decoding concurrently) decodes reliably at `dt_s = 0.0`, a failure
anywhere in the full S3b DT sweep is ambiguous between "the DT boundary" (the thing being
measured) and "this chain's general SNR/routing margin" (an instrument property). G4 resolves that
ambiguity for a cost of ~25 minutes instead of finding out 4.2 hours in.

### Sec.2.2 Reuse, not new tooling (HK-018)

`s3b-dt-boundary.json`'s own `part_index: 0` **is** `dt_s: 0.0, snr_db: 0` -- exactly the cell G4
needs, already pre-registered, already sized. No new scenario file. G4 is:

```
python run_study.py --scenarios S3b --parts 0 --device "Voicemeeter AUX Input" --skip-warmup
```

`--skip-warmup` is used because `harness/warmup.py` blocks on an interactive `input()` confirmation
that cannot be answered from this session. Substituted with a mechanical pre-check that is at
least as strong as the human "yes" it replaces (Sec.2.4) -- read from the instruments, not asked of
a person (HK-027).

**Sizing reused verbatim, not re-derived**, from `s3b-dt-boundary.json`'s own `_sizing_note`:
100 trials/part gives a decode-rate SE of ~4.9pp at p=0.5 (1.96*SE ~= 9.8pp half-width), tighter
near the 95% region this gate actually reads. That note already established 100 as the mechanically
required floor for this response family -- reusing it here, not re-deriving.

### Sec.2.3 Gate (mechanical, HK-021(o) -- integer counts out of 100, no CI needed)

Primary metric: **OpenWSFZ's** decode count of `CQ Q1ABC FN42` out of 100 trials at
`dt_s = 0.0, snr_db = 0`. OpenWSFZ is the system under test; WSJT-X's simultaneous count at the
same cell is reported alongside as context only and does not gate (WSJT-X is the known-reliable
reference appraiser -- its own decode rate at 0dB/dt=0 is not in question).

| Row | Condition (OpenWSFZ decode count / 100) | Verdict |
|---|---|---|
| **1** | **>= 95** | **PASS.** Chain baseline is sound. The full S3b sweep may be sized and armed as its own, separate go/no-go (NOT auto-authorised by this row -- see Sec.4). |
| **2** | 90 - 94 | **MARGINAL -- escalate.** Do not arm the full sweep. Diagnose (SNR margin vs routing vs a real decoder regression) before spending 4.2h on data that would need this same caveat applied to every cell. |
| **3** | <= 89 | **FAIL.** The live chain is not reliable enough to interpret a DT sweep at all. STOP. No S3b live run. Escalate to Captain -- likely a routing/device problem, not a DT-boundary finding. |

Rows are mutually exclusive count bins over the exhaustive range 0-100; no straddle is possible
(HK-021 exclusivity trivially satisfied by construction).

**Prediction, recorded before running:** ROW 1, decode count 95-100. `dt=0, SNR=0dB` is the easiest
cell in the entire S3b/S3 grid (no timing stress at all), and this exact configuration (message,
frequency, SNR) has already decoded cleanly through every offline instrument checked so far
(G1/G2 placement, G3's jt9 and WSJT-X `File > Open` reads). The live chain adds device/routing
variance G3 could not exercise, which is the one thing this gate is actually for.

### Sec.2.4 Mechanical pre-flight (replaces `warmup.py`'s human confirmation)

Before arming, verified directly from the instruments, not asked of a person:

1. `wsjtx.exe` running under the `FT991A` profile, with its `jt9.exe` helper pointed at
   `WSJT-X - FT991A` -- confirms the same profile G3's pre-flight already checked.
2. `OpenWSFZ.Daemon.exe` started (was not running at pre-flight time -- confirmed via
   `GET /api/v1/status` returning connection-refused before start), then re-checked:
   `"state":"Running"`, `"captureActive":true`, `"audioDevice"` containing `Voicemeeter Out B1`.
3. Daemon's on-disk config (`%APPDATA%\OpenWSFZ\config.json`) already carries
   `"audioDeviceFriendlyName": "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"` and
   `"decodeLog": {"enabled": true, "path": "ALL.TXT"}` -- unchanged, not edited for this task.

If either process is not in the expected state, G4 does not run -- same STOP the human warm-up
prompt would have produced, just read from the machines instead of asked of the Captain.

---

## Sec.3 -- Commit hygiene

`s3-dt-offset.json`'s one-line flag flip and this document are the only changes in this commit.
No `src/` change (HK-011 not engaged). No push (HK-014). G4's own results, once run, get their own
report and their own commit -- not folded into this one, so the pre-registration is never edited
to match an outcome.

## Sec.4 -- What this document does NOT authorise

Even on a G4 PASS, the full S3b sweep (10 parts x 100 trials x 2 appraisers, ~4.2h unattended) is
its own commitment: it needs an HK-013-compliant supervisor (kill+log+cooldown+restart, cap 5
retries, live-tested -- none exists yet for this specific run) and ties up the Captain's live rig
for the better part of an evening. G4's result gets reported and the full-sweep go/no-go is asked
for explicitly at that point, not assumed.
