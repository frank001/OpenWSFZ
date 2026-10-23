# QA (k) review: the late-start time-alignment spec (Option A)

**Stamped:** 2026-10-23 ~17:45Z (`date -u` 17:34:37Z at the start of the read). **To: Architect.** QA, branch `qa/refset`.
**Reviewed:** `arch/late-start-align` `47659e13`, spec `qa/rr-study/2026-10-23-1735-architect-to-qa-spec-late-start-time-alignment.md`.
**Go:** relayed by the Architect ("Option A", the Captain, ~17:30Z). QA is confirming it in its own window before filing the issue or handing off; this review is read-only analysis.
**Read against:** `origin/main` `85fbaadc` (PR #258 merged 17:30:36Z).

## Verdict: ACCEPT, with amendments M1 to M4 (none blocking). No refusal on HK-021(k) grounds. The 2.36 s full-clip band is not pushed back on (see M5).

## 1. FILE:LINE and arithmetic re-check

| Spec reference | On `origin/main` `85fbaadc` | Result |
|---|---|---|
| answerer pending target `QsoAnswererService.cs:783-801` | phase check `:783-784`, fire `:795-801` | ✅ |
| answerer jump-in `:715-730` | `:715-730` (phase check, then "regardless of how many seconds", `ExecuteJumpInAsync`) | ✅ |
| caller pending responder `QsoCallerService.cs:778` | the phase check sits at `:777-784`, `// Wrong phase — retain pending responder.` | ✅ |
| `TransmitAsync` answerer `:1614`, caller `:1321` | `:1614` and the clamp call at `:1321` | ✅ |
| `Ft8TimeHelper.cs:46-59` | `ClampSampleCountToWindowBoundary` `:46-59` | ✅ |
| `LateBatch.CanStartWhole` / `LatestWholeStart` (`LateBatch.cs:104-116`) | `LatestWholeStart` = 15 000 - 12 640 ms (2.36 s) at `:108-111`; `CanStartWhole` `:119` | ✅ (the method is a few lines past 116) |

Arithmetic, all checked: 12.64 s x 48,000 = **606,720**; T2 (2.37 - 0.5) x 48,000 = **89,760**, loaded **516,960**; T3 (4.9 - 0.5) = **211,200**, loaded **395,520**; T4 (11.24 - 0.5) = **515,520**, loaded **91,200**; T8 8 s: **360,000** skipped, **246,720** loaded. The sample rate is 48 kHz (the L-2 line "485508 samples (10115 ms)" = 48,000.8). 3.0 s skipped = 18.75 of 79 symbols (0.16 s each); the first Costas array (symbols 0 to 6) is gone and the other two are intact, as the spec says. 11.25 s = 0.75 x 15 s, and the next correct-phase window is 30 s - 11.25 s = 18.75 s later ("about 19 s"), so R2's retention is well inside the 60 s stale expiry.

## 2. Amendments

- **M1 (H3: assert where the audio went; required before any decode).** QA's standing lesson (memory note `modulator-positive-clamp-and-dt-convention-defects.md`): the S3 `modulator.py` clamped `dt_s` for 2.5 months and "two labels, identical audio" went unnoticed, because nothing asserted the render matched its label; it now raises instead of clamping and supports `extended=True`, but H3 needs partial clips (style O's cut tail, style A's skipped start) that the DT parameter does not describe. **H3 will therefore build each WAV by placing a full product-synthesised clip at sample offsets in a 15 s buffer, not through the modulator's DT parameter, and before any decode will cross-correlate every rendered WAV against the DT = 0 render and assert the lag (or the start of the signal) to the sample.** The Architect's G1 is only meaningful if the O-style audio really sits at +4.4 s. Add this to H3 as a mechanical row.
- **M2 (R1's reference time, and the "clamp never fires" sentence).** `t` is the moment `TransmitAsync` is about to load audio. Actual audio starts later: PTT KeyDown, the lead time (the station config has `ptt.leadTimeMs` 50 ms; the L-2 PTT assert came 12 ms after the log line) and the output device's latency. So the first symbol lands about 0.05 to 0.3 s after the computed `t`: harmless for DT (the window is ±2.48 s), but **at the band edge (t = 2.36 s, full clip) the clip ends about 0.1 to 0.3 s past the 15 s boundary, so the retained clamp CAN still fire there**, contrary to "with the rule above it never fires". Not a regression (today's auto-replies start at up to 2.36 s with the same spill). Ask the Developer to log, in the R3 line, `t` at the moment the skip is computed, and to leave the clamp as the safety net.
- **M3 (test determinism).** The fire sites arm and expire with `DateTimeOffset.UtcNow`, not the injectable `_timeProvider` (`ArmPendingTarget` sets `_pendingTargetSetAt = DateTimeOffset.UtcNow`, `:466`; the 60 s expiry reads `UtcNow`, `:764`). T6 and T7 need `t` (the offset into the window) from `_timeProvider`, so the new check must use `_timeProvider.GetUtcNow()` (as `TransmitAsync` already does at `:1627-1628`) and the tests the existing test-only arming helpers (`:482-500`). Say so in the handoff.
- **M4 (a question for the Architect, not blocking): a cut that starts mid-tone.** Skipping N samples starts playback in the middle of a symbol, with no ramp, and the key goes down with a tone already at full amplitude: a key-click risk on air. Today's tail truncation already ends abruptly at the boundary (no ramp), so this is consistent, but the new start-cut is the first change that makes the START abrupt. QA has not read WSJT-X's `Modulator` for a ramp on a late start. If a short raised-cosine ramp-in is wanted, T2 to T4's "first loaded sample equals input[N]" must be reworded (the first ~5 to 10 ms would be scaled). **QA asks: ramp, or no ramp; and if no ramp, record that as a decision.**

## 3. Checks on the rows (HK-025(k), validity and precision)

- **G1 (O at 4.9 s, -8 dB must decode 0/5; if it decodes, STOP):** the validity branch: it fires only if the DT analysis is wrong, and then the arm stops; it cannot fire the same way on the other branch. Good control; M1 makes sure the audio really is at +4.4 s.
- **G2 (A at 3.5 s, -8 dB decodes >= 4/5):** the bar's source is stated as "no data on file, reasoned" (HK-038 satisfied); not a precision row that fires either way (it fails if the skipped-start clip is undecodable). Keep.
- **T1 to T9:** discriminate as written. The mutation (tail truncation restored): T2, T3, T4 fail; T1 passes either way (full clip below 2.36 s), as the spec says. T5 and T6 would fail on today's code, since today fires at any lateness.
- **R2:** the three fire sites are the right three. One consequence to state: a manual engage past 11.25 s is retained and fires about 18.75 s later; the operator sees nothing for that time. That is the spec's Option A; no change asked.

## 4. M5: the 2.36 s band (the spec asks for push-back)

QA does not push back. The band edge equals `LateBatch.LatestWholeStart` (15 - 12.64 = 2.36 s), so the auto-reply hold and this rule agree on one number. In the band the clip keeps its full length at DT up to +1.86 s, inside WSJT-X's ±2.48 s sync search, and WSJT-X would instead skip (t - 0.5) s there; the spec and H3 measure exactly this (t = 0.62 and 2.36 s at style A). What this review cannot say: JTDX and MSHV ranges (the spec says they were not read). **Optional, cheap, descriptive: add t = 1.5 s to the A rows of H3's grid, to see the band's interior, since only its two ends are measured.**

## 5. Next

(1) The Captain's go and the issue text in QA's window (QA files only with his approval of the text). (2) The OpenSpec change (MODIFIED, the four requirements named in R6) and the dev-task, with M1 to M4 applied. (3) Developer, HK-039 review with the mutation, `pre_merge_check.py` on a clean checkout before any push. (4) H3 on `sol`.
