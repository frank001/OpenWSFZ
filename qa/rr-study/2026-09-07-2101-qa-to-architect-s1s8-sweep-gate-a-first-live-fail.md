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

Section 6 of the report quotes every dated Gate-A-population observation since the 2026-08-27
sweep, verified from each historical report's own gate line (never inferred from date — the
run report is the authority for which era it belongs to, per the standing warning in
`STUDY-SPEC.md` §16):

| Date | SHA | Design | OpenWSFZ Gate A | Verdict |
|---|---|---|---|---|
| 2026-08-27 | `22b749c` | R&R-009, N=60 | 0/60 (UB 4.87%) | PASS |
| 2026-08-29 | `872ba65` | R&R-009, N=60 | 1/60 (UB 7.66%) | FAIL |
| 2026-08-30 | `2e60949` | targeted, N=120 | 2/120 (UB 5.15%) | PASS |
| 2026-09-02 | `3b52608` | R&R-009, N=60 | 4/60 (UB 14.61%) | FAIL |
| 2026-09-03 | `35378b9` | R&R-009, N=60 | 2/60 (UB 10.12%) | FAIL |
| 2026-09-06 | `4c7d5ad` | targeted, N=60 (R&R-010 trigger) | 3/60 (targeted, no full report) | FAIL |
| **2026-09-07** | **`4cc1984`** | **R&R-010, N=120 (first live)** | **3/120 (UB 6.33%)** | **FAIL** |

Four of the last five dated observations FAIL. Today's run is the first data point under your
new N=120 design, so it has no same-era predecessor to compare against on the UB — but the raw
event count is identical to the immediately preceding observation (3, on 2026-09-06, which was
your own trigger for asking whether the increase persists), and per-AWGN-slot the point rate
actually *halved* between those two (5.0% → 2.5%) even though both fail the same 6% ceiling.

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
