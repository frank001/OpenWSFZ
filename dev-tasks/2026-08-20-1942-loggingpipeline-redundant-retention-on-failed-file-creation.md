# Developer handoff: `LoggingPipeline.Apply()` runs retention against a directory it already knows does not exist

**Authored by:** QA, 2026-08-20 (19:42 UTC, `date -u`, HK-017), per HK-000/HK-015.
**Origin:** the Captain's observation of warning noise at the tail of a green
`OpenWSFZ.Ft8.Tests` run (314/314), 2026-08-20. QA investigated; the noise itself is
**correct test behaviour**, but the investigation surfaced one real defect (§2).
**Status:** 🔴 **Proposal, not approved work in itself (HK-011).** A separate Developer session
runs `opsx:apply` (build + tests only — never `pre_merge_check.py`, that is HK-006, the Captain's
initiative alone). The Captain reviews the diff before any push or merge (HK-010/HK-014). QA does
not declare readiness.

🛑 **Programme context — read before scheduling this.** The board holds **one live route**
(Route B2 Phase 1, `openspec/changes/r2-coherent-llr-instrument/tasks.md`). This item is **not**
Route B2. It is a one-line guard change with no bearing on D-001, and it is written down here
precisely so it does **not** consume attention now. The Captain chose "draft it so it can ride
along"; ride-along is the intended disposition, not a priority claim.

---

## 1. What the Captain actually saw — and why it is NOT a defect

```
[20:16:33 WRN] Cannot create log directory 'C:\...\openwsfz-lp-test-gb0sfzl3.jy2\blocking.txt\subdir' - file sink disabled.
System.IO.IOException: Cannot create '...\blocking.txt' because a file or directory with the same name already exists.
[20:16:33 WRN] Could not enforce log retention in 'C:\...\openwsfz-lp-test-gb0sfzl3.jy2\blocking.txt\subdir'.
System.IO.DirectoryNotFoundException: Could not find a part of the path '...'
```

Two tests in `tests/OpenWSFZ.Ft8.Tests/LoggingPipelineTests.cs` deliberately construct an
unusable log directory — a **file** used as a parent directory, which
`Directory.CreateDirectory()` refuses on every platform:

```csharp
var blockingFile = Path.Combine(_tempDir, "blocking.txt");
File.WriteAllText(blockingFile, "I block directory creation");
var invalidDir = Path.Combine(blockingFile, "subdir");
```

- `Apply_FallsBackToConsoleOnly_WhenDirectoryIsInvalid` (line 67) — asserts `Apply()` does not
  throw and creates no log file.
- `CurrentLogFilePath_IsNull_WhenDirectoryIsInvalid` (line 208) — asserts the path property
  reflects the failure.

Both **pass**. The warnings and stack traces are the graceful-degradation path *working as
designed* and reporting itself. The two different temp paths in the Captain's paste
(`…gb0sfzl3.jy2` and `…esijujhl.xeu`) are the two tests' independent per-instance fixtures, not
leakage between them.

🛑 **Do not "fix" this by deleting, weakening, or silencing those two tests, and do not remove
the `Cannot create log directory` warning.** That warning is the daemon's only operator-facing
signal that file logging has silently degraded to console-only. §4's check is two-sided
specifically to catch a fix that takes the easy route.

---

## 2. 🔴 The one real defect — retention is attempted after the sink was already disabled

`src/OpenWSFZ.Daemon/Logging/LoggingPipeline.cs:169-170`:

```csharp
if (config.FileEnabled)
    EnforceRetention(config.Directory, config.MaxFiles);
```

The guard tests the **requested** configuration, not the **achieved** one. By the time control
reaches line 169, `TryCreateLogFile()` may already have failed (line 121), logged
`Cannot create log directory …`, returned `null`, and left the file sink out of the logger
entirely — with `CurrentLogFilePath` correctly reset to `null` at line 117 and never assigned.

Retention then runs anyway, against a directory the code has just proven does not exist:
`Directory.GetFiles()` throws `DirectoryNotFoundException`, the `catch` at line 205 swallows it,
and a **second** warning is emitted — the less informative of the two, since it names the symptom
(could not enumerate) rather than the cause (the parent is a file).

### Why this is worth fixing, beyond tidiness

`Rotate()` is `Apply(_config, _consoleLevel)` (line 177). A daemon running 24/7 with a
misconfigured or since-deleted log directory therefore emits **two** warnings, one of them
redundant, on **every scheduled rotation** — plus a futile filesystem enumeration each time.
The redundant line is pure dilution of the operator's log at exactly the moment the operator
most needs the real diagnostic to stand out.

Severity: **minor**. No data loss, no incorrect decode behaviour, no crash — the exception is
caught and handled. This is a log-quality and wasted-work defect, not a correctness one.

### The fix

Change the guard at line 169 to test the achieved state:

```csharp
if (CurrentLogFilePath is not null)
    EnforceRetention(config.Directory, config.MaxFiles);
```

`CurrentLogFilePath` is assigned at line 144 from the same `path` local that the sink was built
on, and is `null` on both the file-disabled and creation-failed paths. It is therefore the exact
predicate wanted: *"is there a real, open log file in a real directory?"* No other change is
required — do not restructure `Apply()`, do not alter `TryCreateLogFile()`, do not touch
`EnforceRetention()` itself.

Add a brief comment saying **why** the guard is on the achieved state rather than
`config.FileEnabled`, so a future reader does not "simplify" it back.

---

## 3. Blast radius — verified, not assumed (HK-022)

| question | answer | how QA checked |
|---|---|---|
| Other production callers of `LoggingPipeline.EnforceRetention`? | **None.** Line 170 is the only one. | `grep -rn "EnforceRetention" src/ tests/` |
| Do the three direct-call retention tests break? | **No.** `EnforceRetention_LeavesFiles_WhenWithinLimit` / `_DeletesOldestFiles_WhenOverLimit` / `_ClampsMaxFilesToOne_WhenZeroOrNegative` (lines 239/253/283) all call the `public static` method **directly** with a valid `_tempDir`. They never route through `Apply()`, so the guard is not in their path. | read all three |
| Any test asserting retention *does* run when file creation failed? | **None.** | `grep -rn "invalidDir\|blocking" tests/` — only the two §1 tests |
| Any other test that `Apply()`s an invalid directory? | **None.** Those two are the only producers of `Could not enforce log retention` in the entire suite — which is what makes §4's zero-hit check mechanical. | same grep, plus `grep -rln "LoggingPipeline" tests/` (4 files; the other 3 use valid dirs) |
| Confusable sibling? | ⚠️ **Yes.** `CycleArchiveService.EnforceRetention` (`CycleArchiveService.cs:404`) is a **different, private** method with a different signature, called from lines 321 and 475. **It is out of scope. Do not touch it.** | grep above |
| Native / DLL impact? | **None.** This is managed `src/OpenWSFZ.Daemon/` only. **No shim rebuild, no `FT8_SHIM_VERSION` bump, no DLL SHA movement** — nothing in this change can perturb a decode measurement or detach existing evidence from its pinned binary. | file path |

---

## 4. Verification — two-sided, mechanical (HK-021)

There is **no unit test proposed for this**, and QA wants the reason on the record rather than a
weak test that appears to cover it:

> The redundant warning is emitted at line 170, i.e. **after** the new inner logger has been
> installed (lines 150-167). It therefore goes to the pipeline's own freshly built, console-only
> logger — **not** to the ambient `Serilog.Log.Logger` a test could swap out beforehand. (The
> *first* warning, from `TryCreateLogFile` at line 121, is emitted **before** installation and
> would be capturable that way — but that is the warning we want to keep.) Capturing the second
> would require a seam to inject a sink into the pipeline's own `LoggerConfiguration`, which does
> not exist. Adding one to service a minor log-hygiene fix is not proportionate.

A test asserting only the capturable half would assert the behaviour we are **not** changing —
coverage without meaning. So the check is on the suite's own output instead, and it is
mechanical.

Run the full suite capturing console output, then assert **both** of these on the same run:

```bash
dotnet test tests/OpenWSFZ.Ft8.Tests > lp-run.txt 2>&1
grep -c "Could not enforce log retention" lp-run.txt   # MUST be 0   (redundant warning gone)
grep -c "Cannot create log directory"     lp-run.txt   # MUST be 2   (real diagnostic still fires, once per test)
```

- **`0` and `2` → PASS.**
- `0` and `0` → **FAIL**: the real diagnostic was suppressed too. Revert and re-do.
- non-zero first count → **FAIL**: the guard is not on the achieved state.

⚠️ **HK-009:** grep those **ASCII substrings only**. The full template is
``Cannot create log directory '{Directory}' — file sink disabled.`` with an **em dash**, which the
Windows console renders as `-` under `cp1252` (visible in the Captain's own paste). Matching the
dash will silently return 0 and read as a false PASS.

---

## 5. Branch handling

**Recommended: its own branch off `main`, one commit, its own PR.** It is independent of Route B2
and reviews in about thirty seconds.

🔴 **Do not fold it into `feat/r2-coherent-llr-phase1`** (currently `5d3cac5`, B2 Phase 1's
`ft8_coherent_llr_at` diagnostic export). That branch carries instrument work whose evidence
chain the board treats as pinned; an unrelated logging change in the same diff makes both harder
to review and muddies what that branch is a record of. If the Captain would rather not open
another PR, the fallback is a **clearly separate commit** on whatever branch the Developer is
already on — never squashed together with B2 work.

---

## 6. Definition of done

- [ ] `LoggingPipeline.cs:169` guard changed to `CurrentLogFilePath is not null`, with a comment
      explaining why it is not `config.FileEnabled`
- [ ] **Nothing else touched** — not `TryCreateLogFile`, not `EnforceRetention`, not
      `CycleArchiveService`, not either of the two §1 tests
- [ ] §4 run and **both** counts reported explicitly (`0` retention warnings AND `2`
      create-failure warnings) — reported as observed numbers, not as "verified"
- [ ] Full `OpenWSFZ.Ft8.Tests` suite green; **report the count** (314/314 at the time of writing —
      re-verify, do not assume it stays 314; HK-022)
- [ ] Managed build clean, 0 warnings
- [ ] Confirmed in the commit message: no native rebuild, DLL byte-identical, no
      `FT8_SHIM_VERSION` bump

🛑 **Then stop.** No push, no merge, no request for either (HK-010/HK-014). No
`pre_merge_check.py` (HK-006). The Captain reviews the diff and decides; QA does not declare
readiness unprompted.

---

## 7. Open standing question for the Captain (no work implied)

§4 declines a unit test on proportionality grounds. That judgement is QA's, made against a
**regression-test policy that has never been explicitly ruled** — "must every bug fix be
accompanied by a regression test?" remains on the list of testing-strategy items awaiting the
Captain's agreement. If the answer is "yes, always, without exception", then this fix needs the
sink seam described in §4 and becomes a materially larger job, and QA would want to say so before
starting rather than after. **A ruling is welcome but not required to proceed** — the §4 check is
mechanical and two-sided as it stands.
