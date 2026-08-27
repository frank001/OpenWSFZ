# Architect → QA — outstanding work order (everything still owed after the 2026-08-27 sweep)

**Author:** Architect, 2026-08-27 21:41Z (`date -u`, HK-017).
**Context:** closes out the session that produced the sweep review (`dee9d90`), the R1–R4
corrections (`1000c2d`), the `NBR-FIX` route spec (`427a5cf`) and the Programme Dossier (PR #133).
**Status:** WORK ORDER. Items 1–2 are authorised now (qa/ tooling, HK-011's exception). Items 3–4
are dev-tasks **for QA to author**, not for me (HK-015). Items 5–6 are priced and **NOT
authorised** — they need a Captain decision first. Item 7 is housekeeping.

🔴 **This document authorises no `src/` change.** Every item below is either `qa/` tooling, a
document, or a dev-task that routes to a separate Developer session with the Captain's sign-off.

🔴 **HK-025 stands on everything here.** If any acceptance criterion below is not mechanical —
if you evaluate it and land on the same conclusion either way — name the item, say so, and stop.
No Architect agreement is required to refuse.

---

## 0. Read this before starting anything

**Do not commit, at all, while a live study run is in progress.** This bit us on 2026-08-27:
a docs-only `RUNBOOK.md` commit landed between the S1 and S1b scenarios and split the run's truth
data across two directories, crashing the matcher *after* a two-hour live capture had completed
cleanly. No data was lost, but only because the two files happened to be schema-identical with no
scenario-ID overlap. Item 1 removes the mechanism; the discipline stands regardless.

**Check `qa/rr-study/trend.csv` after any ad-hoc analyser run.** `analyse.py` appends to it
unconditionally — including on partial, scenario-filtered regenerations. I dirtied it during the
R2 fix this session and reverted it by hand. Item 2 removes that trap.

---

## 1. Pin the run directory once per battery — AUTHORISED

**Priority: highest. This is the one that has already cost a run.**

### The defect, mechanically located

`harness/run_scenario.py` derives its own output directory from the **live**
`git rev-parse --short HEAD` on every invocation, via `make_run_dir()` in `harness/common.py:89-97`
(`results_root/<YYYY-MM-DD>-<git-sha7>/`). The parent never pins one:

- `run_study.py:199` — `run_args = ["harness/run_scenario.py", str(sf), "--device", args.device]`.
  **No `--run-dir` is passed**, so every scenario resolves its own.
- `run_study.py:208` — `run_dir = _find_run_dir()` runs *after* the scenario loop and assumes a
  single directory exists.
- `run_scenario.py:1182` — **`--run-dir` is already an accepted argument.** Nothing needs
  inventing; it simply is not passed.

⇒ any commit landing mid-battery, however unrelated to `src/`, silently splits the run's truth
data and crashes the matcher on whichever scenario falls on the wrong side.

### What to do

Compute the run directory **once**, before the scenario loop, and pass it explicitly to every
`run_scenario.py` invocation via the flag that already exists. `_find_run_dir()` then becomes
redundant for the battery path and should either take the pinned value or be removed.

### Acceptance — mechanical

| # | Check | Pass condition |
|---|---|---|
| 1a | Every `run_scenario.py` invocation in `run_study.py` carries `--run-dir` | Grep shows the flag on the constructed arg list; zero invocations without it |
| 1b | Simulated mid-battery SHA change | With a commit made between two scenarios, **all** scenarios' outputs land in one directory. Reproduce by stubbing the SHA source or committing a throwaway docs change against a scratch results root — do **not** run a live capture to test this |
| 1c | Matcher and analyser still resolve | A full re-run of matcher + analyser against an existing results directory produces a `report.md` identical to the current one |
| 1d | No behaviour change for a single-scenario run | `run_scenario.py` invoked directly, with and without `--run-dir`, behaves as before |

⚠️ **1b is the row that matters.** If you cannot construct a test in which the SHA changes
mid-battery, say so — a fix whose failure mode cannot be exercised is not verified (HK-022).

---

## 2. Stop the analyser polluting `trend.csv` on ad-hoc runs — AUTHORISED

### The defect

`harness/analyse.py:2305` calls `_append_trend(...)` unconditionally from `main()`. The function
(`:2041-2087`) opens `qa/rr-study/trend.csv` in append mode. There is no guard for a
scenario-filtered run, so **any** ad-hoc regeneration writes a row into the historical series that
carries the study's own trend.

Observed this session: regenerating S8 alone into a scratch directory appended
`r2-s8-regen,dee9d90…` to the real `trend.csv`. Caught and reverted with `git checkout`, but only
because I looked.

### What to do

Your call on shape; the two obvious options are a `--no-trend` flag defaulting to *append*, or
suppressing the append automatically whenever `--scenario` is passed (a filtered run is by
definition not a full battery). I lean to the second because it is safe by default and needs no
one to remember a flag — but you are closer to the harness than I am, and this is a QA-owned
decision, not an Architect ruling.

### Acceptance — mechanical

| # | Check | Pass condition |
|---|---|---|
| 2a | Filtered run does not append | `analyse.py --run-dir <scratch> --scenario S8`, then `git diff --stat qa/rr-study/trend.csv` is **empty** |
| 2b | Full battery still appends | An unfiltered run appends **exactly one** row |
| 2c | Existing rows untouched | The file's pre-existing content is byte-identical after 2a and after 2b apart from the single appended row |

---

## 3. File the self-contained-publish crash as a dev-task — QA TO AUTHOR

**This is a real build defect and it currently exists only inside a report's Section 1, where it
will be lost.**

### What was found (2026-08-27, during sweep setup)

`dotnet publish -r win-x64 --self-contained` produces a daemon that **crashes on real WASAPI
capture**: `MMDeviceEnumeratorComObject..ctor()` throws "invalid program" at runtime. The
project's `.csproj` silently upgrades that invocation to a **NativeAOT** build once a
`RuntimeIdentifier` is set, and the failure matches the build's own ILC trim warnings.

Workaround used for the sweep: a plain framework-dependent `dotnet build`, which started cleanly.

### Why it matters beyond the sweep

The sweep only needed a working local daemon, so a workaround sufficed. But this is the
publish path anyone would reach for to produce a distributable artefact, and it fails at runtime
rather than at build time — the worst shape of failure. The README records the project as
pre-release, source-only, no binaries distributed; that is exactly the state this defect would
block changing.

### What the dev-task needs to carry

- The exact invocation, the runtime exception, and the corresponding ILC trim warnings.
- Whether the NativeAOT upgrade in the `.csproj` is intentional. If it is, the trim roots for the
  WASAPI/COM interop path need declaring; if it is not, a `RuntimeIdentifier` should not imply it.
- A decision on whether self-contained publish is a supported configuration at all right now —
  if it is not, it should fail loudly at build time rather than at first capture.

🔴 **HK-015: this dev-task is yours to author, not mine.** I am specifying the problem, not the
task file. It routes to a separate Developer session with the Captain's sign-off (HK-011).

---

## 4. Consider filing the flaky archive test — QA'S JUDGEMENT

`tests/OpenWSFZ.Daemon.Tests/CycleArchiveServiceTests.cs:182`
(`Manifest_WritesOneRowPerArchivedCycle_InOrder`) failed **2 of 2** full-suite runs and passed
**3 of 3** in isolation, always via `Poll.UntilAsync` timing out at the 5 s default waiting for the
manifest to reach five lines. Recorded 2026-07-28; it meets `TESTING_STRATEGY` §11.3's blocker bar
and has never been filed.

I am not directing this — it is a month old, it may have been overtaken, and you own the test
estate. **Verify it still reproduces before filing anything**; if it no longer does, say so and
retire the note rather than leaving it open indefinitely.

---

## 5. S5 "OpenWSFZ-only" fallback — PRICED, NOT AUTHORISED

**Do not start this without a Captain decision.** Recorded here so it is not lost again.

`STUDY-SPEC.md` §4 states that if the WSJT-X leg is unavailable, the study may run OpenWSFZ-only
and disclose it, because the FP gate is a single-appraiser statistic. **That was never coded**, and
the gap is verified rather than asserted:

- `run_study.py:182-187` unconditionally copies from the live WSJT-X install's own `ALL.TXT`; no
  flag skips it.
- `harness/matcher.py:71-72` hard-exits if that path does not resolve; `--wsjt` is effectively
  mandatory.
- A repository-wide search finds no OpenWSFZ-only code path outside the spec's own prose.

🔴 **The risk is not that it fails — it is that it might not.** A degraded run that silently
counted real off-air decodes as S5 false positives would produce a plausible-looking FP number
that is simply wrong. Priced at roughly an hour of `qa/` work.

---

## 6. S3 re-grid — PRICED, NOT AUTHORISED

The modulator positive-DT clamp defect meant synthetic truth was **wrong for 2 of 10 S3 parts**
from 2026-06-06 onward. Consequence, still live: **every S3 bias, linearity and GR&R figure since
that date was scored against wrong truth for those parts.** The clamp is fixed; the contaminated
history is not retired.

Also unresolved, and it belongs with this work: the WSJT-X DT convention offset (`0.55 s`) is an
**unknown-accuracy correction, not a stable constant** — measured between 0.531 and 0.674 across
three builds. Any S3 re-grid that applies it as a constant inherits that uncertainty into its own
results.

⚠️ **This needs its own pre-registration before it runs**, not just a re-run. Do not fold it into
a routine sweep.

---

## 7. Housekeeping

| Item | Action |
|---|---|
| `qa/rr-study/results/2026-08-27-2ae939c/` | Orphaned split-run directory, untracked, harmless. Captain may want it removed — ask, do not delete unilaterally; it is the only physical evidence of the incident |
| `daemon_rr_setup_2026-08-27*.log`, `rr_study_2026-08-27_s1s8_full_run.log` | Untracked run logs. Confirm gitignore coverage or gather them per HK-016 |
| `qa/rr-study/results/_pre-run-backups/` | Untracked. Confirm intent — keep or discard |
| `daemon_rr_setup_2026-08-22.log` | Shows as **modified** in a tracked path. Check whether it should be tracked at all |

---

## 8. Blocked — do NOT start

| Item | Why blocked |
|---|---|
| **`NBR-A`** (near-neighbour discriminator arm) | Spec `2026-08-27-2100-architect-to-qa-spec-nbr-a-…` is stopped at a Captain/PO decision (§5 of that spec). One of its three options is "accept the gap and stop proposing arms" |
| **Anything touching the coherent extractor** | Phase B's kill gate is VOID with ROW 0g-2 still firing. The route may not be advanced *or* called dead |
| **Any `src/` change** | Separate Developer session + Captain sign-off (HK-011) |
| **PR #133 merge** | Captain's decision (HK-010) |

---

## 9. Suggested order

1. **Item 1** (run-dir pin) — highest value, already cost a run, and item 2 is easier to verify
   once the harness is being touched anyway.
2. **Item 2** (trend guard) — small, and removes a trap that silently corrupts the series everyone
   reads.
3. **Item 3** (publish-crash dev-task) — authoring only; gets a real defect out of a report section
   before it is lost.
4. **Item 4** — verify-then-decide, cheap.
5. **Items 5–7** — only after a Captain decision, except item 7's questions, which can be asked at
   any time.

---

## 10. Standing-rule notes

- **HK-015** — Architect → QA. `dev-tasks/*.md` are yours to author; I have specified problems
  here, not written task files.
- **HK-011** — items 1, 2 and 7 are `qa/` tooling and docs, so no Developer session is required.
  Items 3–6 either are or may become `src/` work and route accordingly.
- **HK-014** — I commit this locally and stop. Nothing pushed, no merge.
- **HK-025** — you may refuse any item here on HK-021(k) grounds by naming the item and its
  evaluation. Item 1b is the acceptance row most likely to warrant it.
- **HK-022** — for each fix, ask what error the acceptance check could *not* detect. Item 1's
  whole point is a failure mode that only appears when the SHA moves mid-run; a test that never
  moves it proves nothing.
