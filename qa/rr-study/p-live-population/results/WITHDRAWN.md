# P-LIVE Stage 1 — WITHDRAWN

**Files affected:** `p_live_stage1_report.json`, `p_live_stage1_run.log`,
`full_run_console.log` (this directory) and the per-row dump, moved out —
see below.

**Ruling:** `qa/rr-study/2026-08-18-1616-architect-to-qa-p-live-stage1-ruling-anchor-provenance-defect.md`
(2026-08-18 16:16Z).

**One-line reason:** Stage 1 anchored V0 extraction at WSJT-X's raw reported DT
and fed it directly to `ft8_extract_llrs_at`, whose third argument is
buffer-relative — the wrong time convention, off by ~+0.45–0.65s (~2.8–4
FT8 symbols). Every headline number (`f_cross`=0/15,389, "N5 CONFIRMED",
"both limbs of D-001 limb 2 close") is a symptom of that mis-anchoring, not a
measurement of anything real. **Do not cite any number from this directory's
`p_live_stage1_*` files in any form** — see the ruling Sec.4 for the full list.

**Per-row dump moved to:** `artefacts/2026-08-18-p-live-stage1-withdrawn/p_live_stage1_rows.json`
(29.6MB, blanket-gitignored — regenerable, see that directory's `README.md`).

**Corrective follow-up:** Stage 1R (`run_stage1r.py`) ran 2026-08-18 20:21Z →
**ROW A, ANCHOR BROKEN** — confirmed via a P-HIT positive control (chance-level
median BER_V0 at the raw anchor) and measured the corrected offset for this
entry point at **+0.65s**. See `p_live_stage1r_report.json` /
`p_live_stage1r_run.log` in this directory (those files are LIVE, not
withdrawn) and the QA report to the Architect for the full result and next
steps.

**Unaffected, still live in this directory:** `row0a_results.json` /
`row0a_run.log` — ROW 0a (audio-path correspondence) does not depend on the
DT convention and was not withdrawn.
