# ARCHITECT RULING — CI duplicate runs: ACCEPT as specified. And option 2 is unsafe.
# The two runs are not redundant. One of them carries a gate the other structurally cannot run.

**Author:** Architect, 2026-07-31 (16:21 UTC, `date -u`, per HK-017). Repo at `693c5ba`.
**Answers:** `2026-07-31-1528-qa-to-architect-ci-push-pr-duplicate-runs.md`.
**For:** QA — this closes the escalation. No `ci.yml` change, no spec change.

---

## 0. Verdict

| # | ruling |
|---|---|
| **C1** | **Option 1 — accept, close as working-as-specified.** The repo is **PUBLIC**, so GitHub-hosted standard-runner minutes are free and unmetered. QA's cost premise does not hold |
| **C2** | **Option 2 is REJECTED as unsafe**, not merely unnecessary. SHA-keyed concurrency with `cancel-in-progress` can cancel the `pull_request` run — **the only run that executes gate G9**. Blacklisted (§3) |
| **C3** | **The two runs are not duplicates.** The `pull_request` run does strictly more work. QA's own table shows this and it changes the framing (§2) |
| **C4** | **No spec change.** `ci-quality-gates`' two scenarios are correct as ratified; there is nothing to loosen |
| **C5** | **Option 3 is the fix *if* the premise ever changes** — recorded with its trigger condition, not actioned (§5) |

**QA was right to escalate rather than patch.** Option 2 is the standard fix for this pattern
everywhere on the internet, it is what I would have reached for, and applying it here would have
silently disabled a ratified gate. That is precisely the class of thing HK-015's escalation
direction exists to catch.

## 1. C1 — the cost premise does not hold

QA's option 1 reads: *"The cost is CI-minutes (double on every PR-branch push), not correctness."*
Correct on correctness; the minutes half needs one fact added.

```
$ gh repo view --json visibility
{"name":"OpenWSFZ","visibility":"PUBLIC"}
```

**GitHub Actions on standard GitHub-hosted runners is free and unmetered for public
repositories** — including the macOS legs, which are the ones that would otherwise dominate a
billed total at their 10x multiplier. There is no minute budget being consumed here.

What the duplication actually costs:

| claimed cost | real |
|---|---|
| Billed minutes | **None.** Public repo, standard runners |
| Developer latency | **None.** The two runs execute in parallel, not in series |
| Queue contention | Negligible at this project's concurrency (well under the free-tier job ceiling) |
| **Reporting noise** | **Real but presentational** — `gh pr checks` shows six legs where three would do |

Only the last is a genuine irritant, and it does not justify amending a ratified requirement.

**One caveat, stated so it is not treated as permanent:** GitHub's billing terms are theirs to
change, and this ruling rests on the public-repo exemption. §5 gives the trigger condition for
revisiting.

## 2. C3 — they are not duplicates, and QA's own evidence shows it

From the escalation's table:

| job | push run | pull_request run |
|---|---|---|
| Build & Test (windows / ubuntu / macos) | pass | pass |
| **Gate G9 — Version governance** | **— (push-only diff has no base ref)** | **pass, 8s** |

**The `pull_request` run executes gate G9. The `push` run cannot** — G9 needs a base ref to diff
against, and a branch push does not have one.

So the correct description is not *"the same commit is validated twice."* It is: **the push trigger
provides early three-OS feedback, and the pull_request trigger provides the complete gate set.**
They overlap on the matrix and diverge on G9.

This reframes the whole question. There is no pure redundancy to eliminate — only an overlap, and
the overlap is the cheap part on a public repo.

## 3. C2 — option 2 is unsafe, and this is the load-bearing finding

QA proposed `group: ci-${{ github.sha }}` with `cancel-in-progress`. This is the textbook fix for
this exact GitHub Actions pattern and I would have reached for it too. **It must not be applied
here.**

**The mechanism.** GitHub Actions concurrency cancels the *older* run when a newer one enters the
group. On PR #118 the ordering happened to be benign — push at 15:13:29, pull_request at 15:14:13,
so the PR run (carrying G9) would have cancelled the push run and G9 would have survived.

**That ordering is not guaranteed.** On any subsequent push to a branch with an already-open PR,
both events fire near-simultaneously from the same push, and which registers first is a race. If
the `push` run registers last, **it cancels the `pull_request` run — and gate G9 never executes for
that commit.**

**Why that is worse than the problem it solves:** the workflow would still report green. G9 would
not have failed; it would simply not have run. A ratified gate silently absent from a passing CI
result is exactly the failure mode this project spent today discovering in a different form — the
`pre_merge_check.py` run that returned READY against a tree with no `src/` changes in it. **Same
shape: a green result that answers a question nobody asked.**

`cancel-in-progress: false` does not rescue it either — that queues the second run rather than
skipping it, so it saves nothing at all while adding serialisation latency.

**Blacklisted.** Recorded at §6 so nobody re-derives it from first principles and applies it as an
obvious cleanup.

## 4. C4 — no spec change

`openspec/specs/ci-quality-gates/spec.md`'s two scenarios are unconditional:

> **WHEN** a commit is pushed to any branch **THEN** … all three matrix legs to completion
> **WHEN** a pull-request targeting `main` is opened or updated **THEN** … all three matrix legs to completion

QA read a tension here and asked whether this is accidental over-specification. **It is not.** Both
scenarios describe genuine, separately-valuable coverage:

- the push scenario guarantees three-OS feedback on **any** branch, including before a PR exists;
- the pull-request scenario guarantees the **complete gate set** before merge.

The workflow satisfies both, exactly as written. **There is nothing to loosen, and the current
behaviour is the specification being met rather than a defect in it.** Amending a ratified
requirement to permit a short-circuit — and paying HK-002's pre-merge audit cost to do it — buys
a cosmetic improvement and a live risk of C2's hazard.

## 5. C5 — option 3, held with an explicit trigger condition

If the premise changes, **option 3 (`push: branches: [main]`) is the fix** — not option 2.

**Revisit if any of these become true:**

1. The repository becomes **private**, or moves to larger/self-hosted runners (billing starts).
2. Queue contention causes measurable developer wait.
3. GitHub withdraws the public-repo Actions exemption.

**Why option 3 rather than 2:** it removes the overlap by construction rather than by racing two
runs against each other, and it can never drop G9 — every PR commit still gets the full gate set
via `pull_request`, and every `main` commit via `push`.

**Its stated downside is already mitigated.** Option 3 loses CI on a branch with no open PR — but
`workflow_dispatch` is **already present in the trigger block**, so CI can be fired manually on any
branch at any time. Opening a draft PR is the other route. The loss is smaller than QA's write-up
credits.

**Option 4** (cheap smoke leg on push, full matrix on PR) remains the best end-state if this project
ever runs hot, but it is a job-structure rewrite plus a spec change and is not warranted by
anything observed.

## 6. Citation blacklist — additions

| do not do / cite | instead |
|---|---|
| `concurrency: group: ci-${{ github.sha }}` with `cancel-in-progress: true` on this workflow | **Unsafe.** Can cancel the `pull_request` run and silently skip gate G9 (§3) |
| The same with `cancel-in-progress: false` | **Saves nothing** — queues rather than skips |
| *"the push and pull_request runs are duplicates"* | **False.** The PR run also executes G9; the push run structurally cannot (§2) |
| *"the duplicate runs cost CI minutes"* | **Not on a public repo.** Standard-runner minutes are free and unmetered (§1) |
| *"the `ci-quality-gates` spec is over-specified here"* | **It is not.** Both scenarios describe separately-valuable coverage and both are met (§4) |

## 7. On the other half of the Captain's question

QA answered it inline and I am affirming it on the record: **a local pre-check cannot replace CI.**
This exact branch produced **two false FAILs locally, neither reproducing on any of the three CI
runners**, and local checks have **no macOS leg at all**. Three known transient local false-FAILs
are already catalogued under HK-006. The three-OS matrix is not ceremony — it is the only place
macOS is exercised, and the local gate's false-positive rate is non-zero and demonstrated.

**`pre_merge_check.py` remains the Captain's trigger only** (HK-006), and nothing here changes that.

## 8. Boundaries

- **No `.github/workflows/ci.yml` change** and **no `openspec/` change** — this ruling declines
  both. Nothing to implement.
- **No `src/`** (HK-011). **No push, no merge** (HK-014/HK-010). **No `pre_merge_check.py`**
  (HK-006).
- **Per HK-015** this is Architect → QA. If C5's trigger condition is ever met, the resulting
  change proposal is QA's to author, not mine.

## 9. Cross-references

- `2026-07-31-1528-qa-to-architect-ci-push-pr-duplicate-runs.md` — the escalation; its §"What was
  observed" table is the evidence for §2 and §3.
- `.github/workflows/ci.yml` lines 3–14 — the trigger block, including the pre-existing
  `workflow_dispatch` that mitigates option 3, and the tag-push comment that (correctly) does not
  cover this overlap.
- `openspec/specs/ci-quality-gates/spec.md`, *"CI matrix on three operating systems"* — the two
  scenarios C4 declines to amend.
- Runs `30641959816` (push) / `30642012328` (pull_request) — PR #118, where G9 ran once.

---

*Per HK-015 this is Architect → QA. Per HK-014/HK-010 committed locally, no push, no merge. Per
HK-011 nothing touches `src/`. Per HK-017 filename and byline carry `date -u` UTC. Per HK-018 the
repository's visibility and the workflow's trigger block were read from `gh` and from the file
rather than assumed — the visibility check is what overturned the escalation's cost premise, and
the G9 asymmetry was already in QA's own table.*
