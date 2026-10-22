# Architect to QA: (k) review of the two DI7 test plans (sol R&R ×3 `DI7COH`, station endurance `DI7COH-E`)

**Stamped:** 2026-10-22 ~19:45Z (`date -u` 19:39:40Z when drafting began). **To: QA.** Branch `arch/di7-era-runs` (local).
**Asked by the Captain, through QA (19:39Z):** review both plans; nothing runs until this review and his go.
**Read:** `qa/refset` `42f324d7` (sol plan), `e0ab1e89` + `1163250c` (endurance plan, Captain's answers), `d34ce802`
(`battery-tp.sh` pin change, `qa/endurance/di7-endurance-arm.py`), and `Ft8Decoder.cs` at `56736264` for the log line
that V-F counts.

**Verdict: both plans ACCEPTED with changes K1–K9.** K1–K4 must be done before the sol series starts, K5–K8 before the
endurance arm. K9 is a recorded concern. No new pass/fail bar is introduced (asked in (c)): the only number added is
V-F's 95 %, a validity tolerance whose source is stated in K2.

## (a) Era labels and no pooling: correct, one change

- `DI7COH` (sol, synthetic R&R) and `DI7COH-E` (station, live 40 m) are new rows. Neither is pooled with MAINDEEP,
  TPDEEP, TPNORMAL, B2CAP, B2BASE, #225, the 20 m R14 live check, or **each other** (state the last one in both plans).
  Both plans already say that MAINDEEP vs DI7COH is across a build change (fallback plus DI-only work) and does not
  measure the fallback alone. Correct.
- **K1 (sol) Use a NEW series ID.** The aborted start at 19:33:49Z used `DI7COH`. `series-tp.sh` names sweeps
  `<date>-<sha7>-DI7COH-sweep<n>`, so a restart on the same date and build collides with the aborted folder, and
  `pull-series.sh DI7COH` would match it. Use `DI7COH2` (plan §7 item 5 says the ID must never repeat). Move the aborted
  folder to a name with `ABORTED` in it on `sol`. It is never pulled or cited.

## (b) V-D and V-F: V-D unchanged and right; V-F correct in kind, with three changes

The code: one `Coherent fallback:` line per cycle (`Ft8Decoder.cs:1044-1050` at `56736264`), written only when
`fallbackReady = cohOn && cohSnapshot is not null` (`:900`), and `cohOn` requires the flag **and** the staged callbacks
(`:529-530`). A flag-OFF daemon therefore writes none, a flag-ON live daemon writes one per decoded cycle, and a
cycle whose native fallback call fails (`outcome is null`, `:1006`) writes none. So the line count is a valid
flag-was-effective instrument. On a flag-OFF build the flag would be inert and the count 0, so it is not a blind spot.

- **K2 State the denominator and the bar's source from the whole window.** The denominator is the daemon's per-cycle
  `Cycle` lines in the same log and the same span. The bar's source should be the **full R14 window**: fallback
  lines / `Cycle` lines over all 502 scored cycles (or the whole flag-ON span), not the 483 reconciled ones, which
  are a subset chosen for another reason. It is data on file; count it and quote it (HK-038). The 95 % is a tolerance
  for the S6 restart edges and is labelled an Architect decision value. If the R14 full-window fraction is below
  99 %, come back before using 95 %.
- **K3 (sol) Halt before a sweep, not void after it.** `battery-tp.sh` now drops `coherentFallbackEnabled` from both
  configs before the pin and only **prints** `tp-flag`. Add one mechanical halt: for this series, `tp-flag` must be
  `true`, else `halt` before WSJT-X starts (e.g. `TP_EXPECT_COHFB=true` checked in the same Python block). Otherwise a
  wrong sweep config costs 3 h 38 min before V-F voids it.
- **V-F on the endurance run:** the config is read back once, 20 s after start (`di7-endurance-arm.py:136`, flag at `:142`). An
  end read-back is not possible after the runner stops the daemon. **Drop "start and end" for the endurance run.** The
  per-cycle line count over the whole night is the end evidence. Say so in the plan.

## (c) No invented bar: confirmed

The S6 WSJT-X tripwire 93.9 % is the existing ruling (Architect 2026-10-17-2218), with its re-derive condition. The
endurance read is Section 4 / HK-036 plus the capture counters. Neither plan adds a QA pass/fail bar.

## (d) sol build source, config handling, tooling

- Build: merged DI tip, `publish_selfcontained.py --rid linux-x64`, and the pin is the `.so` in the tree, read at each
  sweep and at S6 start/end. Correct; never `0197f9ce…`.
- Config: the rig config's flag is dropped from the pin. That is right: a Settings save on the new build writes the
  key and must not halt a sweep. The effective value is guarded by K3 plus V-F.
- **K4 Tooling commit.** The message says tooling `b0e23bb` "as MAINDEEP". But the pin change is in `d34ce802`, and
  the V-F reader is "not yet written" (plan §6). So the tooling on `sol` cannot be `b0e23bb`. Record the actual
  commit, and show mechanically that `git diff --stat b0e23bb..<tooling>` under `qa/rr-study/` touches only
  `battery-tp.sh`, the V-F files, the README and docs. That is what keeps the analyser identical to MAINDEEP's. Any
  analyser change has to be named.

## (e) `di7-endurance-arm.py` (read in full)

Asserts are good: DLL SHA, provenance commit and clean, port free, decoder values, CAT/TX/external reporting off,
Voicemeeter strips, WSJT-X device; flag explicit `true`; threads 0.

- **K5 The pin names the wrong commit for the plan.** `COMMIT = 56736264…` and `DLL_SHA = 0e180dfc…` are the pre-merge
  commit. The plan §1.2 publishes from the **merged** DI tip, and PR #255 is still OPEN. After the merge, either
  (i) publish from the merged tip and update both constants from the published tree, or (ii) keep `56736264`, showing
  that `git diff --stat 56736264 <merged tip> -- src native` is empty apart from CI-rebuilt `.so`/`.dylib`.
  Quote whichever you choose before arming.
- **K6 A failed read-back must stop the run.** Lines 143-144 print "STOP AND LOOK" and carry on. Make the script exit
  non-zero after the read-back if the flag is not `true` or the depth is not Deep. QA, present at the arm, then stops
  the run before leaving it unattended (HK-020). An unattended night on the wrong setting is the failure to prevent.
- **K7 Corpus location.** `corpus = QA_WT / "artefacts" / …` (`:72`). `artefacts\` in the QA worktree is the shared
  junction, so this is right. Confirm the runner's supervisor gathers into the same folder (the script asserts the
  name, `:130`).
- **K8 Station hand-over.** Stopping the station daemon (pid 37328) ends live QSO operation for the night. It happens
  only on the Captain's word, as the plan says. After 08:00Z QA does not restart it. The redeploy and the flag's
  explicit `true` on the station are his (board).

## K9 Recorded concern (stated once; the Captain decided `subtractionMaxThreads` = 0)

At 0 = auto the daemon resolves `max(1, ProcessorCount − 2)` (`SubtractionThreads.cs:15` at `56736264`) = 14 workers
on this PC (R14 log; hence 16 logical processors), and the fallback, residual and third pass
use them. In this run **WSJT-X decodes on the same CPU at the same time**, and the endurance read compares OpenWSFZ
with that live WSJT-X (Section 4). At 14 workers, OpenWSFZ load could slow or starve WSJT-X's Deep decode and tilt the
comparison toward OpenWSFZ. #225 ran at 8. Nothing on file measures WSJT-X under that load. ALL.TXT has no decode
timing, so the run cannot detect it either (HK-026). Two ways to handle it:
- read the Section 4 WSJT-X rows as "with a shared CPU at up to 14 OpenWSFZ workers" and never compare them with
  #225 as like-for-like; or
- run at 8 (comparable with #225 and every replay).

The Captain chose 0 for "how the station behaves", which is a fair question. The caveat goes into the report.

*Architect. Docs only; `src/`/`native/` diff empty.*
