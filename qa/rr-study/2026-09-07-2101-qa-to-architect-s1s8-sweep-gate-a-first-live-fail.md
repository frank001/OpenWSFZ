# QA → Architect: 2026-09-07 R&R S1-S8 sweep — Gate A FAILs on its first live exercise

**Run:** `qa/rr-study/results/2026-09-07-4cc1984/report.md` (redacted, HTML rendered).
**Binary:** OpenWSFZ `4cc1984c8082ce1f07d7569d96ce74d6f504e1c6` — content-identical to
`origin/main`'s squashed `65d4fff` (PR #144, S5-GATE-SIZING Amendment 1). Shim `20260050`.
**Requested by:** the Captain — routine housekeeping sweep against the latest local binary, no
defect ID under investigation going in.

## Headline

**Overall verdict: FAIL.** Cause: Gate A (S5 AWGN, parts 0/1) — **3/120 slots, 95% UB 6.33% > 6%
ceiling.** Check B (narrowband, parts 2/3) is clean: 0/60. Every other section (S1/S2/S3 GR&R,
S1b, S4/S5 pooled κ, S7, S8) is unchanged from the established pattern — nothing new there.

This is **the first live S1–S8 battery to exercise R&R-010's Gate A/Check B split**
(`STUDY-SPEC.md` §16, implemented 2026-09-06 in the branch you and I just merged). The board
already flagged this as the open item this run closes: *"Next real S1–S8 sweep is the first to
exercise Gate A/Check B live... Section 6 needs its footnote then."*

## What I verified before writing this up

1. **The 3 events are genuinely inside Gate A's window**, not bleed-through from an adjacent
   scenario. I filtered `S5_matched.csv` to `cycle_utc` within parts 0/1's own truth-row range
   (2026-09-07T19:11:00Z–19:42:00Z, taken directly from this run's `truth.csv`) rather than
   trusting the per-scenario matcher summary line, which — I confirmed separately — attributes
   *every* unmatched decode in the whole session's `ALL.TXT` to *every* scenario's own FP count
   (the S8 scenario's messages and the pre-flight warm-up decode all show up identically in all
   eight `S*_matched.csv` files). `harness/analyse.py`'s Gate A/Check B computation already
   re-scopes correctly by `cycle_utc` (the same fix R&R-010 made for the part-index NaN defect),
   so the reported verdict is not affected by this — I flag it in Section 5 only so nobody reads
   a raw matched-CSV "FP" count directly in the future.
2. **All three events are noise-floor hallucinations**, not signal misattribution: −26, −26,
   −27 dB true SNR, all in part 1 (none in part 0). Matches RUNBOOK.md §7.5's documented
   phenomenon exactly.
3. **WSJT-X registered zero false positives** on the same 120 slots — as it has in every routine
   sweep to date. The control stays clean, so I don't read this as a shared harness/routing
   artefact.
4. **NFR-021:** the three hallucinated tokens plus 23 others (S7/S8 near-collision garbled
   decodes) were callsign-shaped and non-synthetic. Redacted before anything else touched git —
   `qa/rr-study/redact_s1s8_20260907_decodes.py` (same method as the 2026-09-03 sweep's own
   redaction pass, reusing `nfr021_pre_merge_scan.py`, not reimplemented), guard passed (0 of 26
   flagged tokens found inside any injected truth message), 0 remaining after rewrite.
   `REDACTION-MAP.md` committed alongside.

## The one thing I'm handing to you, not ruling on myself

**Correction, made at the Captain's direction after the first version of this note and the
report were already up:** the table originally here showed seven rows starting 2026-08-27,
selected by my own judgment and not disclosed as a selection — it omitted, among others, a
`793a298` (2026-07-04) row reading 22.09% UB, a bigger number than anything the table showed. The
report's Section 6 now carries the complete `trend.csv` series, every row, none excluded, each
cross-checked against its own source `report.md` where one exists (a few rows could not be fully
traced this pass and are flagged as such rather than guessed at — see the report). Read that
table, not a summary of it, before ruling. The corrected top-line figures:

Restricting to properly-gated, comparable observations (N≥49 AWGN-only readings; excluding the
pre-2026-07-04 block, which used a different metric definition entirely, and the `793a298` row,
which is an ungated INFO line at N=12) there are **13** such readings since the gate's 2026-07-04
ratification, of which **6 FAIL**. The longest PASS streak in the record is 4 in a row
(2026-07-07 to 2026-08-21). **The longest FAIL streak is also 4 — and it is the most recent four**
(2026-09-02, 2026-09-03, 2026-09-06, and today). Today's reading extends that run; it is not an
isolated event, though the raw event count (3) is unchanged from 2026-09-06 and the per-AWGN-slot
point rate is not obviously higher than several historical PASSes — the Clopper–Pearson UB is not
linear in the point rate, so N and k both matter and neither alone explains the pattern.

I am not ruling on whether this is a fresh regression, a persisting one, or noise at N=120 — that
reading is yours (HK-015), and R&R-010 was explicitly designed to answer it with a properly-
powered series this run is only the first point of. No `src/` change is proposed from this run
alone.

## Housekeeping, not gating

- `harness/matcher.py`'s per-scenario FP summary line is session-wide, not scenario-scoped (see
  point 1 above). Doesn't affect any ratified verdict; worth a docstring note next time that file
  is touched, not urgent.
- Binary/routing setup: audio device, port, shim version all verified against the pinned values
  before arming (`_qa_preflight_check.py` PASSED). Full account in
  `artefacts/2026-09-07-rr-s1s8-4cc1984/README.md` (gitignored, operational record only).

## Files in this commit

- `qa/rr-study/results/2026-09-07-4cc1984/` — full run directory, redacted, HTML rendered.
- `qa/rr-study/redact_s1s8_20260907_decodes.py` + its `REDACTION-MAP.md`.
- `qa/rr-study/trend.csv` — new row appended by `analyse.py` (unedited by hand).
- This note.
