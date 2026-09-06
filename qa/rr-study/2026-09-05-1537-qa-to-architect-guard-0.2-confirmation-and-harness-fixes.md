# Guard §0.2 mechanical confirmation, plus the two `S5-STANDALONE` harness fixes

**QA, 2026-09-05 15:37 UTC** (`date -u`, HK-017). Closes the one item the PO's 2026-09-05
ratification left open: *"re-run `analyse.py` on the unfiltered `S5-STANDALONE` logs; gate must
still read `6/300`/`0/300` — if it does not, the ruling re-opens"* (`BOARD.md`, "Left open,
QA's"). Also lands the two harness process-fixes filed as follow-ups in §6.1/§6.2 of
`2026-09-05-1505-qa-to-architect-s5-standalone-result.md`. No `src/`/`native/` touched — HK-011
not engaged; no adjudication drawn (HK-015 — this is a mechanical check plus two tooling
patches, not a ruling).

---

## 1. Guard §0.2 mechanical confirmation

**Claim under test** (Architect's 2026-09-05 15:17Z ruling, §0.2): `analyse.py`'s §10 gate is
computed from `fp_in_window` (`analyse.py:703–716`), which scopes false positives to the S5
injection window *before* the gate is read — so the fact that `matcher.py`'s pass-2 has no time
window of its own does not, by itself, corrupt the reported gate figure. The ruling asked for
this to be checked mechanically rather than taken on the architecture reading alone.

**Method.** The run's own committed `truth.csv` was combined with a reconstruction of the
*unfiltered* logs — the corrected, committed `owsfz-all.txt`/`wsjt-all.txt` (6 lines / 0 lines)
with the pre-run warm-up decode (`CQ Q1ABC FN42`, cycle `260905_133645`, OpenWSFZ SNR +8 dB,
WSJT-X SNR +7 dB — the exact values `2026-09-05-1505-qa-to-architect-s5-standalone-result.md`
§6.1 records) re-inserted at the front of each file, in the project's own ALL.TXT Format B. This
was verified faithful before being used for anything: running `matcher.py` against it reproduces
the exact raw counts already on record in
`artefacts/2026-09-05-s5-standalone/matcher_uncorrected_output.txt` (WSJT-X 1 FT8 line / 1 FP,
OpenWSFZ 7 FT8 lines / 7 FP) to the digit.

`analyse.py --run-dir <reconstruction> --scenario S5` was then run against the resulting
(unfiltered) `S5_matched.csv`:

```
S5 FP events (WSJT-X): 0/300 slots (event rate 0.00%; 95% UB 0.99%; decode rate 0.00%)
S5 FP events (OpenWSFZ): 6/300 slots (event rate 2.00%; 95% UB 3.91%; decode rate 2.00%)
```

**Result: gate line reads `6/300` (OpenWSFZ) / `0/300` (WSJT-X) — identical, digit for digit, to
the committed `report.md`'s §10 table row.** The ruling does not re-open.

This mechanically confirms guard §0.2 as written: `analyse.py`'s own windowing already excludes
the warm-up decode from the gate regardless of whether the log was pre-filtered by hand, so (i)
the historical battery series (which was never hand-filtered) is not contaminated by this class
of defect, and (ii) the manual filtering step QA applied in the original run was redundant with,
not a precondition for, the reported `6/300`/`0/300` gate figures.

Reconstruction artefacts, NFR-021-scanned (`({}, {})` on the report; the two log/CSV files carry
the same coincidental noise-decode tokens as the original run's own artefacts, gitignored):
`artefacts/2026-09-05-s5-standalone-guard-0.2-confirmation/`.

---

## 2. Harness fix — `matcher.py --since` (closes §6.1's process follow-up)

**Defect (unchanged from §6.1):** `matcher.py`'s pass-2 (`_match_appraiser`, `harness/matcher.py`)
has no time-window filter — every unconsumed candidate decode anywhere in the supplied ALL.TXT is
counted as a false positive for the scenario being matched. For a signal-free scenario like S5
this means a stray decode outside the run's own injection window (a pre-run warm-up decode, most
concretely) is counted as an in-scenario FP in the script's own printed summary and written
`*_matched.csv`, requiring an operator to remember to hand-filter the log first — exactly what
bit the July run (per its own finding #5) and again the 2026-09-05 `S5-STANDALONE` run.

**Fix:** `matcher.py` gains `--since YYYY-MM-DDTHH:MM:SSZ`. When given, both logs are filtered
(`_apply_since`) to drop any record with a cycle timestamp strictly before the cutoff, before
matching — the operator passes the run's own first truth-row `cycle_utc`, mechanically, instead
of relying on memory. `analyse.py`'s own gate is unaffected either way (see §1) — this fixes the
matcher's own raw per-appraiser count and the written `*_matched.csv`, which is what mattered for
the July/September manual-filter workaround.

Verified against the same reconstructed unfiltered logs used in §1:
`--since 2026-09-05T13:38:30Z` reports `WSJT-X: --since ... dropped 1 record(s)` /
`OpenWSFZ: --since ... dropped 1 record(s)` and yields `WSJT-X: 0 FP` / `OpenWSFZ: 6 FP` —
identical to the hand-filtered result QA produced manually on 2026-09-05.

Six new unit tests added to `tests/test_matcher.py` (`_parse_since`, `_apply_since`, and an
end-to-end regression guard reproducing this exact warm-up-line scenario); full suite
`tests/test_matcher.py` 12/12 pass.

---

## 3. Harness fix — `run_scenario.py --run-dir` `--help` text corrected (closes §6.2's follow-up)

**Defect (unchanged from §6.2):** `run_scenario.py`'s own `--help` claimed *"Relative paths are
resolved from qa/rr-study/results/"*, but the code (and an explanatory comment directly above it)
deliberately resolves a relative `--run-dir` against the current working directory, matching
`analyse.py`'s own `--run-dir` convention and avoiding a `results/results/…` double-nest. Taking
the `--help` text at face value (`cd qa/rr-study` then `--run-dir <bare-name>`) put the
2026-09-05 run's raw logs at `qa/rr-study/<name>/` — outside the `.gitignore` NFR-021 coverage
scoped to `qa/rr-study/results/*/…`.

**Fix chosen:** correct the `--help` text, not the resolution code. The CWD-relative behaviour is
intentional (per the code comment) and is what `RUNBOOK.md`'s own worked examples already assume
(e.g. §4.3's `--run-dir results/corpus-<date>`, which only lands in the right place because it
includes the `results/` prefix itself). Changing the resolution code instead would be the riskier
edit for no benefit — every existing call site already either omits `--run-dir` or supplies the
`results/` prefix explicitly. The corrected text now says paths resolve from CWD (same convention
as `analyse.py --run-dir`) and instructs the caller to include the `results/` prefix themselves.

Verified via `--help` output; no behavioural code path changed, so no test coverage gap opened.

---

## 4. NFR-021

`qa/rr-study/nfr021_pre_merge_scan.py`'s own `scan()` (not a directory walk) on every committed
file this note touches:

| File | Flagged | Grid-excluded |
|---|---|---|
| `harness/matcher.py` | 0 | 0 |
| `harness/run_scenario.py` | 0 | 0 |
| `tests/test_matcher.py` | 0 | 0 |
| This report (prose) | 0 | 0 |

---

## 5. Housekeeping

- **HK-016:** `artefacts/2026-09-05-s5-standalone-guard-0.2-confirmation/` — reconstructed
  unfiltered logs, the unfiltered `S5_matched.csv`, and the `analyse.py` report generated from
  them (all gitignored, coincidental noise-decode tokens same as the original run's own).
- **HK-011:** no `src/`/`native/` touched (`git diff --stat -- src/ native/` empty) — QA-owned
  tooling fix, no separate Developer session needed, consistent with the board's own disposition
  ("Both QA-owned, no `src/` ⇒ HK-011 not engaged").
- **HK-014/HK-029:** committing locally, not pushing. `main` remains far ahead of `origin/main`
  carrying earlier `src/`/`native/` diffs — the HK-029 direct-push exception stays N/A for this
  branch state regardless of this commit's own diff being tooling/docs-only.
- **HK-009:** all new code paths print ASCII.

---

**QA, 2026-09-05 15:37 UTC.** Committed locally, not pushed (HK-014/HK-029).
