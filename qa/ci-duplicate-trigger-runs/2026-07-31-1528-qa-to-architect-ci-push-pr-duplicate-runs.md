# QA → Architect — CI runs the full three-OS matrix twice per PR commit

**Author:** QA, 2026-07-31 (15:28 UTC, `date -u`). Repo at `298cefa` (main, post-merge of PR #118).
**For:** Architect. This is a proposed change, not a fix already applied — nothing in
`.github/workflows/ci.yml` has been touched. Routed here per HK-015 (QA escalates design
questions to Architect; QA does not unilaterally change CI contract behaviour).
**Origin:** the Captain asked, after PR #118 came back green, whether it's necessary to "go
through 5 CI each time" and whether a local pre-check plus PR-only could replace that. The
local-pre-check half of that question is answered elsewhere in this session (short answer: no —
this exact branch's local runs threw two different false FAILs, neither of which reproduced on
any of the three real CI runners, and local checks have no macOS leg at all). This document is
the other half: the CI runs themselves are, concretely, running twice per commit once a PR is
open, and that duplication looks fixable.

## What was observed

`git push -u origin fix-cycleframer-clock-drift-boundary-resync` (a plain branch push) and then
`gh pr create` (opening PR #118 against `main`) fired **two independent workflow runs against the
identical commit**:

| job | run 30641959816 (push) | run 30642012328 (pull_request) |
|---|---|---|
| Build & Test (windows-latest) | pass, 4m55s | pass, 5m10s |
| Build & Test (ubuntu-latest) | pass, 4m43s | pass, 4m2s |
| Build & Test (macos-latest) | pass, 2m49s | pass, 2m34s |
| Gate G9 — Version governance | — (push-only diff has no base ref) | pass, 8s |

Six full matrix legs for one commit, not three. `gh pr checks 118` is where this was actually
seen, not inferred.

## Root cause, in the workflow file

`.github/workflows/ci.yml` lines 10–14:

```yaml
on:
  push:
    branches: ['**']
  pull_request:
    branches: [main]
```

Both triggers are live for the same event: a push to a branch that already has (or is about to
have) an open PR targeting `main` satisfies both `push` and `pull_request`, and GitHub Actions
does not deduplicate across trigger types on its own. The header comment (lines 4–9) explains why
`push` is scoped to `branches: ['**']` rather than an unfiltered `push:` — so a tag push (from
gate G9's own release-tagging job) doesn't re-fire the workflow — but says nothing about the
push+pull_request overlap, which looks like a separate, unaddressed cost rather than something
that comment's reasoning covers.

## Why this isn't just a YAML edit — `openspec/specs/ci-quality-gates/spec.md` already speaks to it

The spec's first requirement, **"CI matrix on three operating systems,"** states two separate,
already-ratified scenarios:

> **WHEN** a commit is pushed to any branch **THEN** the workflow SHALL be triggered and SHALL
> run all three matrix legs to completion

> **WHEN** a pull-request targeting `main` is opened or updated **THEN** the workflow SHALL be
> triggered and SHALL run all three matrix legs to completion

Both are worded unconditionally — neither scenario carves out "except when the other trigger
already covered this exact commit." Any fix that causes one of the two triggered runs to be
skipped or cancelled for a shared commit is, read literally, in tension with whichever scenario's
run didn't complete. That may be exactly the kind of accidental-over-specification a design pass
should tighten, or the two-independent-triggers behaviour may be intentional (e.g. so a branch
with no PR yet still gets full CI feedback on every push) — I don't think QA should guess which,
which is why this is going to you rather than being patched directly.

## Options, roughly cheapest/lowest-risk first

1. **Do nothing.** The cost is CI-minutes (double on every PR-branch push), not correctness — every
   run observed was a true PASS both times. If the "push to any branch, before a PR exists" signal
   is valued (catching build breaks on exploratory branches early), this may be the accepted price
   of that.
2. **Concurrency group keyed by commit SHA, spanning both event types**
   (`group: ci-${{ github.sha }}`, `cancel-in-progress: true`, or `false` to let the first
   finish and skip the second rather than cancel it mid-run). Standard, well-known fix for this
   exact GitHub Actions pattern; a few lines, no trigger-scope change. Consequence: whichever of
   the two triggers loses the race does **not** run its matrix to completion for that commit —
   which is the literal scenario tension above. Would need the spec's two scenarios reworded to
   permit this (e.g. "…SHALL run all three matrix legs to completion, unless an identical commit
   already has a run in progress or completed under the other trigger").
3. **Narrow `push:` to `branches: [main]`.** Removes the overlap entirely (a feature-branch push
   would no longer independently trigger CI; only the PR would). Simplest text change, but
   directly contradicts the "pushed to any branch" scenario as written — a real spec rewrite, not
   just an implementation change, and it removes the pre-PR feedback signal outright rather than
   just deduplicating it.
4. **Split the matrix cost instead of the trigger.** Full three-OS matrix stays PR-gated only;
   plain branch pushes (no open PR) run a cheaper single-OS smoke leg. Preserves early feedback on
   solo branch work without tripling it, but is the largest change here — new job structure, and
   still a spec rewrite (the "pushed to any branch… all three matrix legs" scenario would no
   longer hold).

**QA's recommendation, not a decision:** option 2 is the standard shape of this fix and the
smallest real change, but it can't be applied without you (or whoever owns `ci-quality-gates`)
first deciding whether the spec's two scenarios should be loosened to permit a shared-commit
short-circuit, or whether the double-run is acceptable as-is (option 1) and this is closed as
"working as specified."

## Not on QA's list

- Editing `.github/workflows/ci.yml` or `openspec/specs/ci-quality-gates/spec.md` — this is a
  proposed change for your review, not applied.
- Any judgement on whether the pre-PR push-feedback signal is worth the duplication cost — that's
  a design trade-off, yours to weigh.

## Cross-references

- PR #118 (`fix-cycleframer-clock-drift-boundary-resync` → `main`), run IDs `30641959816` /
  `30642012328` — the observed evidence.
- `.github/workflows/ci.yml` lines 3–14 (trigger block) and its existing comment on the tag-push
  exclusion, which does not cover this overlap.
- `openspec/specs/ci-quality-gates/spec.md`, requirement "CI matrix on three operating systems."
- HK-006 (`tools/pre_merge_check.py` — the local-pre-check half of the same conversation, answered
  inline, not written up separately: two false FAILs this session, neither reproduced on any CI
  runner, no macOS coverage locally at all).
