## Context

Three places currently name the project version and disagree: the sole git tag (`v0.11`,
stale), README.md/REQUIREMENTS.md prose (hand-reconciled to `v0.30` in `7f619fc`), and
`Directory.Build.props`'s `<Version>0.1.0</Version>`. The last of these is not inert — the SDK
promotes `<Version>` into `AssemblyInformationalVersionAttribute`, which
`src/OpenWSFZ.Web/AssemblyVersion.cs` reads at runtime and serves in the daemon's status API
(`WebApp.cs`, `WebSocketHub.cs`). So today the running application actively reports `0.1.0` to
its own operator. Fixing that value is urgent; fixing it *durably* requires collapsing to one
source and giving the OpenSpec archive workflow (the mechanism by which "a feature shipped"
already gets recorded) a way to require the bump mechanically, per issue #49.

The repository already has a precedent for this shape of problem:
`tools/check_native_version.py` is a small, dependency-free Python script invoked from a named
CI gate (see `.github/workflows/ci.yml` gate G8, `openspec validate --strict --all`) that fails
loudly with a remediation message. This change follows the same pattern rather than introducing
new tooling idioms.

## Goals / Non-Goals

**Goals:**
- Exactly one file (`VERSION`) is hand-edited to change the project's version; every other
  consumer (build, runtime status API, welcome banner, docs) is either derived from it or
  CI-checked against it.
- The existing `AssemblyVersion.cs` → status API path keeps working unmodified.
- A PR that archives a user-facing OpenSpec change without bumping `VERSION` fails CI (gate G9),
  with a clear remediation message, mirroring the tone of `check_native_version.py`.
- A PR where README.md/REQUIREMENTS.md's stated version has drifted from `VERSION` fails CI
  (folded into gate G9, since both are "the version story is inconsistent" failures).
- The `user_facing` declaration is a low-friction, grep-able convention that fits the current
  unstructured-prose `proposal.md` format rather than requiring a new parser or schema change.

**Non-Goals:**
- Automating git tag creation/pushing on merge. No CI currently reads or writes tags; wiring
  that up is a separate concern with its own failure modes (push permissions, race with
  concurrent merges) and is logged as a manual follow-up in tasks.md instead.
- Retrofitting `user_facing` markers onto already-archived changes. Gate G9 only inspects
  proposal files newly added under `openspec/changes/archive/` within the PR's diff against
  `main` — history before this change is untouched.
- Full semver automation (auto-incrementing `VERSION` on archive). The Captain still decides and
  writes the new number by hand; CI only verifies *that* it changed, not *what* it changed to.
  This keeps the human able to fold multiple features into a single bump if ever desired, and
  avoids CI needing to parse how many user-facing changes are in a PR vs. already on `main`.
- Editing the OpenSpec CLI's built-in `proposal` template. `@fission-ai/openspec@1.3.1` ships its
  templates inside the globally-installed npm package (confirmed: no project-local template
  override file exists under `openspec/`), so `openspec new change` will keep scaffolding the
  stock template. The `user_facing` line is added by convention (documented in the
  `release-versioning` spec and in QA's HK-002 pre-merge checklist) rather than by tooling.

## Decisions

**1. `VERSION` is a plain single-line text file, no leading `v`, trimmed on read.**
Alternatives considered: embedding the version only in `Directory.Build.props` (rejected — an
XML file is more awkward for a bash/Python CI script or a doc-drift checker to read than
`cat VERSION`, and the whole point is a source everything can cite cheaply); Nerdbank.GitVersioning
or similar (rejected — pulls in a new build-time dependency and git-history-derived versioning
scheme for a problem a five-line MSBuild property function already solves).

**2. `Directory.Build.props` reads the file via an MSBuild property function:**
```xml
<Version>$([System.IO.File]::ReadAllText('$(MSBuildThisFileDirectory)VERSION').Trim())</Version>
```
This requires no new MSBuild targets or tasks, evaluates at the same point `<Version>` was
previously hardcoded, and needs zero changes downstream — `AssemblyVersion.cs` already resolves
`AssemblyInformationalVersionAttribute`, which the SDK still populates from `<Version>` however
it was assigned.

**3. `WelcomeBannerEmitter.Emit(int port)` gains the version in its output line.**
It currently prints only the loopback URL. Since `Emit` lives in `OpenWSFZ.Daemon`, which
already references `OpenWSFZ.Web` (for the HTTP host), it can call the existing
`OpenWSFZ.Web.AssemblyVersion.Get()` rather than re-reading `VERSION` itself — one code path for
"what version is this build," not two. New banner: `OpenWSFZ v0.30 listening on
http://127.0.0.1:{port} — open this in your browser.` This is flagged in tasks.md as a
product-code change for the Developer persona, since it alters operator-visible stdout output
and deserves its own small test (e.g. a snapshot/contains assertion), not a silent tweak.

**4. Doc citation stays as prose, checked rather than eliminated.**
Both README.md and REQUIREMENTS.md already contain a single, near-identically-worded anchor
sentence: `The current release is **v0.30**.` / `The current release is v0.30.`. Rather than
inventing a templating mechanism (e.g. `{{VERSION}}` substitution at doc-build time, which this
project has no doc-build step to run), gate G9 greps each file for that exact anchor sentence,
extracts the version, and compares it to `VERSION`. The anchor wording is documented in the
`release-versioning` spec so a future doc edit that reword the sentence knows to keep the pattern
grep-able (or update the check alongside it).

**5. `user_facing` marker: a single line at the very top of `proposal.md`, before the `## Why`
heading:** `**User-facing:** yes` or `**User-facing:** no`. Considered a YAML frontmatter block
(`---\nuser_facing: true\n---`) instead — rejected because no other artifact in this OpenSpec
workflow uses frontmatter, `openspec validate` has no awareness of it and could plausibly choke
on or strip it, and a bolded prose line is consistent with how the rest of `proposal.md` is
already free-form Markdown.

**6. Gate G9 lives in a new, separate CI job (`version-governance`), not inside `build-test`.**
`build-test`'s checkout (ci.yml line 29) has no `fetch-depth` override (i.e. shallow, depth 1),
which is sufficient for every existing gate but not for G9's need to diff the PR branch against
`main`. Widening the shallow-clone-by-default checkout to `fetch-depth: 0` for all three matrix
legs was rejected as unnecessary cost (three OSes × full history vs. one Linux-only job).
Instead `version-governance` follows the existing `detect-native-changes`/`commit-native-binaries`
precedent (ci.yml line ~405) of a dedicated job with its own `fetch-depth: 0` checkout, and only
runs `if: github.event_name == 'pull_request'` (there is nothing to gate on a direct push, and
`main` itself is never the base of a diff against itself).

**7. G9's "newly archived" detection.** `git diff --name-only --diff-filter=A
origin/${{ github.base_ref }}...HEAD -- 'openspec/changes/archive/**/proposal.md'` lists
proposal files added by this PR. For each, grep the `**User-facing:**` line:
- Missing or malformed line → fail immediately (forces explicit declaration; see Non-Goals on
  not retrofitting history — this only fires for files the PR itself adds).
- `no` → no further check.
- `yes` → require `git diff origin/${{ github.base_ref }}...HEAD -- VERSION` to be non-empty
  (i.e. `VERSION`'s content changed in this PR relative to the base branch).

## Risks / Trade-offs

- **[Risk]** A PR that legitimately archives several changes in one batch, only one of which is
  user-facing, still only needs a single `VERSION` bump — G9's check (file differs at all, not
  "differs by exactly one minor") already tolerates this correctly, but a reviewer should still
  sanity-check the bump count matches the user-facing count by eye; G9 cannot detect "bumped by
  2 when only 1 feature shipped." → Mitigation: this is exactly the kind of judgement call left
  to human PR review; G9's job is to prevent the *zero-bump* failure mode that caused issue #49,
  not to fully automate arithmetic.
- **[Risk]** The doc-drift anchor-sentence grep is brittle to rewording. → Mitigation: documented
  explicitly in the `release-versioning` spec scenario text, and the check fails closed (CI red)
  rather than silently passing if the anchor sentence disappears entirely — a rewording that
  breaks the grep gets caught immediately rather than causing silent staleness.
- **[Risk]** `user_facing` is authored by whoever writes `proposal.md`, i.e. self-declared with
  no independent check on accuracy. → Mitigation: this is a process/discipline gap, not a
  tooling one; flagged in the proposal's Impact section as an addition to QA's HK-002 manual
  pre-merge audit line items until G9 has run long enough to trust.
- **[Trade-off]** Retiring the stale `v0.11` git tag and cutting `v0.30` is left manual (Non-Goals
  #1). → Accepted: low risk, low frequency, and automating git tag pushes from CI has its own
  permission/race-condition surface not worth opening for a once-per-feature action.

## Migration Plan

1. Add `VERSION` (containing `0.30`) and repoint `Directory.Build.props`.
2. Update `WelcomeBannerEmitter` and its test(s).
3. Add `tools/check_version_docs.py` (doc-drift half of G9) and
   `tools/check_version_bump.py` (user-facing-bump half of G9); wire both into a new
   `version-governance` CI job.
4. Update README.md/REQUIREMENTS.md wording only if needed to fit the anchor-sentence pattern
   the checker relies on (both already happen to match; verify during implementation).
5. No rollback complexity: this is additive tooling plus a one-line value fix. If G9 proves too
   strict in practice, it can be relaxed or disabled per-job without touching the VERSION
   mechanism itself.

## Open Questions

- Should the stale `v0.11` git tag be deleted, or left and simply superseded by a new `v0.30`
  tag? Deferred to the Captain as a manual follow-up (see tasks.md) — not a design blocker.
