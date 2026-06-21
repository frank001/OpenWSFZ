# D-009 R6 — Developer Diagnostic Handoff (nhard + sync histogram collection)

**Date:** 2026-06-20
**Raised by:** Architect (supersedes the diagnostic actions in
`2026-06-20-d009-nhard-diag.md` — this version adds the sync-score capture)
**Defect ID:** D-009 — OSD false-positive callsign manufacture in noise
**Severity:** High — merge-blocking
**Type:** Diagnostic only. **Do NOT implement a fix.** Stop at Action 3 and hand
`nhard_observations.md` back to the architect, who selects the R6 branch per
`2026-06-20-d009-r6-decision-fork.md`.

---

## 1. Context (read before starting)

D-009 R5 shipped `OSD_NHARD_MAX = 60` as an OSD output gate, claiming calibration
against histograms that were **never collected**. It failed the S5 noise gate on
the first trials (shim 20260028).

This handoff collects the data R5 skipped — and one extra column. For every OSD
hit we capture **two** numbers:

- **`nhard`** — Hamming distance between the OSD codeword and the channel hard
  decisions. Tests whether OSD *output* can be separated (FP vs genuine).
- **`sync`** — the candidate's sync score (`cand->score`). Tests whether OSD
  *entry* could be gated instead (the WSJT-X-style fix).

One run, two strategies evaluated. The architect's fork doc
(`2026-06-20-d009-r6-decision-fork.md`) maps the result to a fixed R6 action, so
there is no further "guess another threshold" round after this.

**Open question this run must answer:** ft8_lib's `osd_decode` runs at depth 2 and
Hamming-*minimises* by construction, so FP and genuine codewords may *both* sit
close to the channel — meaning `nhard` might not separate them. Confirm or refute
by measurement. If nhard fails, the `sync` column is the fallback discriminant.

---

## 2. Branch

```
fix/d009-fp-callsign-filter
```

Continue on the existing branch. This handoff produces a **diagnostic commit only**
(histograms + observation log). **No production binary, no shim bump, no fix.**

---

## 3. Actions

Diagnostic-only. **Stop at Action 3. Do not implement a fix.**

### Action 1 — Rebuild win-x64 with `NHARD_DIAG` enabled

The diagnostic probes already include the sync score (committed on this branch) at
both OSD sites in `native/ft8_lib_build/patched/ft8/decode.c`:

```c
#ifdef NHARD_DIAG
    fprintf(stderr, "OSD_NHARD_SITE1 %d corr %.3f norm %.3f sync %d\n",
            nhard, osd_corr, osd_norm, cand->score);
#endif
```

(`SITE2` is the AP-decode path; same format.)

Add `-DNHARD_DIAG` to the compile flags in `rebuild.ps1` (or the CMake invocation),
rebuild win-x64, and confirm the binary emits `OSD_NHARD_SITE*` lines on stderr on
every OSD hit. **Do not commit this binary** — it is diagnostic-only. The committed
win-x64 DLL at shim 20260028 stays unchanged.

> stderr from the native layer may not be visible through the .NET host. If not,
> temporarily redirect native stderr to a file at process launch, or route the probe
> through the existing file-logging path (MEMORY Lesson 8: confirm `Logging.FileEnabled`
> and `FileLogLevel = "Debug"` before the run — do not assume the default config
> captures it).

### Action 2 — Collect FP distribution (S5 AWGN)

Run OpenWSFZ with the diagnostic binary against pure AWGN for enough FT8 cycles to
observe **≥ 30** OSD hits that pass CRC-14 and produce Category B/D-style FP
messages. Capture all `OSD_NHARD_SITE*` stderr lines.

For each FP hit record the pair: **`nhard sync`** (plus the decoded message,
correlated by timestamp from ALL.TXT).

### Action 3 — Collect genuine distribution (S7 P0–P2), then STOP

With the same diagnostic binary, run S7 parts 0–2 (co-channel, 5 trials):

```
python harness/run_scenario.py scenarios/s7-compounding.json --parts 0,1,2 \
    --run-dir results/diag-nhard-s7
```

Capture `OSD_NHARD_SITE*` lines. Identify hits that correspond to genuine
co-channel recoveries (messages present in truth.csv) and record their
**`nhard sync`** pairs.

Then **produce and commit** these files under
`qa/rr-study/results/diag-nhard-2026-06-20/`:

1. `nhard_fp_s5.txt` — one `nhard sync` pair per line (Action 2 FP candidates)
2. `nhard_genuine_s7.txt` — one `nhard sync` pair per line (Action 3 genuine decodes)
3. `nhard_observations.md` — plain-text summary:
   - **nhard:** FP vs genuine — min / max / mean / median / shape; is there a gap and where?
   - **sync:** FP vs genuine — same stats; is there a separating floor and where?
   - Best single-axis threshold on each axis as a 2×2 confusion (FP-kept vs genuine-lost)
   - Representative FP and genuine messages tabulated with their `(nhard, sync)` pairs

Commit the three files. **Do not** author report.md Sections 1/2/5 (QA's obligation),
and **do not** generate a full harness report for this diagnostic run.

### Action 4 — Hand off to architect. Do not implement.

Present `nhard_observations.md` to the architect. The architect selects R6 branch
A / B1 / B2 from `2026-06-20-d009-r6-decision-fork.md` §2–3. **Do not** choose a new
`OSD_NHARD_MAX`, add an entry gate, or rebuild a production binary until the
architect has issued the R6 design.

---

## 4. Acceptance Criteria

| # | Criterion |
|---|---|
| AC1 | `nhard_fp_s5.txt`: ≥ 30 `nhard sync` pairs from S5 AWGN FP candidates |
| AC2 | `nhard_genuine_s7.txt`: ≥ 20 `nhard sync` pairs from S7 P0–P2 genuine recoveries |
| AC3 | `nhard_observations.md`: summary stats for **both** nhard and sync; explicit statement on whether each axis separates and where |
| AC4 | No production binary committed at a new shim — diagnostic build only |
| AC5 | No fix implemented; architect sign-off pending per the fork doc |
| AC6 | NFR-021: any callsigns quoted in observations are real off-air FPs from noise (coincidental) or Q-prefix synthetics — no real assignable third-party call introduced into VCS |

---

## 5. References

- `2026-06-20-d009-r6-decision-fork.md` — **architect's pre-committed R6 branches A / B1 / B2** (read this to understand what the data decides)
- `2026-06-20-d009-nhard-diag.md` — prior QA diagnostic handoff (superseded by this doc for the action list)
- `2026-06-20-d009-fp-filter-arch-design.md` — nhard design, measurement gate, AD1–AD8
- `2026-06-20-d009-fp-filter-arch-review.md` — Categories A–E, calibration ceiling
- `native/ft8_lib_build/patched/ft8/decode.c` — OSD sites (~636 SITE1, ~820 SITE2); `min_score` sync gate (~276); `cand->score`
- `qa/rr-study/scenarios/s5-noise-wide.json` — widened S5 noise gate
- `qa/rr-study/scenarios/s7-compounding.json` — S7 co-channel gate, P0–P2
- MEMORY Lesson 8 (file logging for diagnostics), Lesson 14 (separate result dirs per run)
