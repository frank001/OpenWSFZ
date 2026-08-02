# QA result — drift screen, 8081/20m, per segment — PASS (segment 1 clears; S.1 may proceed)

**Author:** QA, 2026-07-31 (17:19 UTC, `date -u`, per HK-017). Repo at `d9057af`.
**Executes:** work order `1356` task 1, amended by `1602` V4 (report per segment rather than
pooled) and by the S.1 rev3 spec §2 (segment 1's own clearance is S.1's prerequisite).
**For:** the record, and to unblock arm S.1.

---

## 1. Method

Generalised `verify_dt_drift_489135a.py` to take `--ours`/`--control`/`--segment-cut` as
arguments (previously hardcoded to the 489135a corpus) rather than write a third script, per
the work order's own instruction. Backward compatibility checked first: run with no
arguments against the original 489135a/8080 corpus reproduces the ruling's own cited figures
exactly — OpenWSFZ 45.4 ppm slow, WSJT-X flat (0.6 ppm), FAIL against the 0.5 s bar. That is
the known-bad corpus the drift-fix PR was written against, so reproducing its numbers
unchanged is the regression check that the generalisation didn't silently change the method.

**Corpus:** `artefacts/20260729_live_run_1831-8081/owsfz/20m/ALL.TXT` (ours) vs
`.../jt9_ALL.TXT` (control).

**Control choice.** This session has no live WSJT-X counterpart — `config.json` shows
`decodingEnabled: false` and its own `contents.md` states `wsjt-x/ALL.TXT` has 0 lines. Per
`anova_common.py`'s own documented rationale (an SDR-fed instance with no live counterpart
uses its jt9 re-decode as the only available second appraiser), the control here is
**jt9**, not WSJT-X. This differs from the 489135a corpus's control (real WSJT-X, a
genuinely independent capture) — noted so the two runs aren't read as measuring identically
independent things, only as using the same slope/ppm/peak-drift *method*.

**Segment cut:** `2026-07-30 00:00:00`, identical to `measurement_d_segment_rerun.py`'s
`CUT` — the same boundary the `1530` ruling established for this corpus's two sessions.

**Reading (fixed by the work order before this ran):** drift stays well inside `|drift| <
0.5 s` across the window -> screen passes. Approaches or crosses 0.5 s -> stop, escalate.

## 2. Result

| window | span | rel. slope (ours − jt9) | peak drift over span | verdict |
|---|---:|---:|---:|---|
| pooled (24.14 h, spans the 18h28m inter-session gap) | 24.14 h | +0.0016 s/h | 0.039 s | PASS |
| **segment 1** (< 2026-07-30 00:00) | **2.72 h** | **−0.0500 s/h** | **0.136 s** | **PASS** |
| segment 2 (>= 2026-07-30 00:00) | 2.96 h | +0.0000 s/h | 0.000 s | PASS (not S.1's concern — VOID on Measurement D self-check 2 per `1602`, cited here only for completeness) |

**Segment 1 — the figure that gates S.1 — passes with more than 3.5x headroom under the bar**
(0.136 s vs 0.5 s).

Both OpenWSFZ and jt9 show a near-constant DC offset in absolute DT (~+1.0-1.2 s vs ~+0.4-0.5
s) — a fixed reference-point difference between the two decoders' DT convention, not drift.
The screen reads the *relative slope*, not the absolute level, precisely so this offset does
not contaminate the reading.

This replaces the qualitative record at `DEFECT-capture-clock-drift-silent-decode-loss.md`
§2.4 ("stable parity throughout") with a measured figure, as task 1 asked.

## 3. Consequence

**Segment 1's prerequisite is satisfied. Arm S.1 (rev3 spec) may proceed on its corpus as
specified.** No healthy-window restriction is needed — the whole of segment 1 clears.

## 4. Boundaries

- No `src/`, no rebuild (HK-011) — frozen artefacts and Python only, exactly as the work
  order specified for this task.
- Script generalised in place (`verify_dt_drift_489135a.py`) rather than forked into a third
  script, per the work order's own preference; original hardcoded-path behaviour preserved
  and verified via the regression check in §1.
- NFR-021: aggregate counts and fitted slopes only; no message text touched by this script.

## 5. Cross-references

- `2026-07-31-1356-…-work-order-after-measurement-d.md` §1 — the task this executes.
- `2026-07-31-1602-…-segment-2-void-on-self-check-2.md` V4 — the per-segment amendment.
- `2026-07-31-1649-…-arm-s1-spec-rev3-segment-1-execution-ready.md` §2 — S.1's prerequisite,
  now cleared.
- `qa/cycleframer-alignment-replay/verify_dt_drift_489135a.py` — the generalised script.
