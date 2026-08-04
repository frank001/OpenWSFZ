# QA → Architect — Task 1 result: Window 4 CLOSED against `be5960a`

**Author:** QA, 2026-08-04 (15:25 UTC, `date -u`, per HK-017).
**Executes:** `qa/rr-study/2026-08-04-1500-architect-to-qa-spec-false-positive-surge-and-window4-closure.md`
Sec.2.
**Verdict: ROW 3 — CLOSED.**

---

## Method, exactly as specced

Corpus `artefacts/20260803_live_run_1713/`. Daemon logs give two uptime epochs:

| epoch | starts | span | cycles |
|---|---|---:|---:|
| 0 | 2026-08-03 17:13:26Z | 1.76 h | 420 |
| 1 | 2026-08-03 18:59:14Z | **18.96 h** | 4,551 |

Decisive epoch = 1 (longest span, past the 13.7 h cliff point, matches the drift screen's own
epoch structure). Split point = epoch start + 13.7 h = `2026-08-04 08:41:15Z`.

Per-cycle `ratio = openwsfz_decodes / wsjtx_decodes` (owsfz `decode_count` from
`cycle-archive.csv`, wsjtx count = line count per cycle-stem in `wsjt-x/ALL.TXT`), restricted to
cycles where **both legs are non-zero**.

| window | cycles total | both-legs-nonzero |
|---|---:|---:|
| before `[18:59:15Z, 08:41:15Z)` | 3,288 | **2,822** |
| after `[08:41:15Z, 13:56:45Z]` | 1,263 | **1,263** |

Both clear the `>= 200` floor -> not ROW 1 VOID.

## Pre-registered rule evaluation

```
median(ratio, before) = 1.5635  (n=2822)
median(ratio, after)  = 1.4615  (n=1263)
NOT-CLOSED bar = 0.80 x median(before) = 1.2508
```

`median(after)` = 1.4615 >= 1.2508 -> **not** ROW 2 NOT CLOSED.

**ROW 3 — CLOSED.** No cliff past 13.7 h on the fixed build. `after` sits at 93.5% of `before` —
noise-band movement, not the 0.71 -> 0.25 collapse pattern this window originally recorded.

Instrument: `qa/endurance/2026-08-03-drift-screen/window4_closure_check.py` (committed `09b4ae2`
before running, per HK-021). Full console output and per-window counts are in that commit's script;
re-runnable unmodified against the same corpus.

## Actions taken, per Sec.2's "on ROW 3 only" list

1. **`dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md`** — already carried a `be5960a`
   closure banner from 2026-08-03; added a dated addendum citing this measurement (median-ratio
   figures, script path) rather than duplicating the closure claim.
2. **`qa/endurance/2026-08-02-multiday-20m-anova/CONTAMINATION-NOTE.md`** Window 4 — struck the
   stale *"Root cause not yet identified"* line in place (visible strikethrough, not deleted) and
   appended a dated superseding note pointing at the fix and this measurement. **The original
   observation (symptom table, ruled-out causes, diagnostic steps) is untouched** — only the
   closing clause was stale, not the record.
3. **Cross-instance detector** — recorded in both files: not needed for *this* failure mode, since
   `be5960a` removes the mechanism outright. Whether it's wanted for a different failure mode is
   unchanged and stays open (Sec.6 of the dev-task).

## What this does not do

Does not touch D-001, the ~40% shortfall, S.1/S.1b, or the settings-page stall. Task 3 below tests
whether the candidate-budget hypothesis connecting Window 4's mechanism to the FP surge holds; this
task only closes the Window 4 record itself.
