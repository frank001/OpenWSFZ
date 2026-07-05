**User-facing:** yes

## Why

The project version is currently named by hand in prose across multiple places and they
disagree. As of the v0.30 documentation refresh (`7f619fc`), the sole git tag reads `v0.11`,
and — more urgently — `Directory.Build.props` still declares `<Version>0.1.0</Version>`. That
property is not a dead docs artefact: `AssemblyVersion.cs` reads it (via
`AssemblyInformationalVersionAttribute`) and the daemon serves it back to the browser client in
the status API (`WebApp.cs`, `WebSocketHub.cs`). The running application is therefore currently
telling its own operator it is version **0.1.0** while every doc claims **v0.30** — a live
runtime discrepancy, not merely a documentation one. The true current version had to be
reconstructed by hand-counting archived OpenSpec changes, which is error-prone and guaranteed to
drift again on the next merge. GitHub issue #49 requests a single canonical source and a
mechanical rule tying it to feature shipment, rather than a fact remembered by whoever last
touched the docs.

## What Changes

- Introduce a `VERSION` file at the repository root (single line, e.g. `0.30`) as the sole
  canonical source of the project's version.
- `Directory.Build.props` reads `<Version>` from that file via an MSBuild property function
  (`File.ReadAllText`) instead of hardcoding the value. No change is required to
  `AssemblyVersion.cs` or its callers — they already resolve `AssemblyInformationalVersionAttribute`,
  which the SDK derives from `<Version>` — so the status API and any future consumer of assembly
  version metadata pick up the fix automatically.
- Fix the immediate drift: `VERSION` is created containing `0.30`, matching the already-agreed
  current release and retiring the stale `0.1.0`.
- `WelcomeBannerEmitter` gains the version in its stdout banner line, since a trustworthy source
  now exists and the banner is the first thing an operator sees on daemon start.
- README.md and REQUIREMENTS.md continue to state the version in prose (removing it entirely
  would hurt human readability of a document meant to stand alone), but a new CI check verifies
  the prose-stated version in each doc matches `VERSION`, so the two can no longer silently
  diverge the way they did before this change.
- Formalise the "one merged user-facing OpenSpec change = one minor version bump" rule: every
  change's `proposal.md` must declare a `user_facing: true|false` marker (a one-line field at the
  top of the document, keeping the existing prose-header structure otherwise unchanged) stating
  whether it ships operator-visible behaviour.
- **New CI gate (G9)**: `.github/workflows/ci.yml` gains a step that inspects a pull request
  archiving one or more OpenSpec changes (i.e. adding entries under
  `openspec/changes/archive/`); if any newly-archived change's `proposal.md` declares
  `user_facing: true`, the gate fails unless `VERSION` differs from its value on `main`.
  Non-feature changes (defect fixes, diagnostics, QA studies, CI/tooling, docs-only) are
  unaffected regardless of how many are archived in the same PR.
- Annotated git tags remain a *release marker*, not the source of truth: retiring the stale
  `v0.11` tag and cutting a fresh `v0.30` tag is called out as a manual follow-up in tasks.md, not
  automated by this change (no CI currently reads or writes tags, and adding tag-push automation
  is judged out of scope here).

## Capabilities

### New Capabilities
- `release-versioning`: defines the canonical `VERSION` file, its consumption by
  `Directory.Build.props`/the assembly-version pipeline, the welcome-banner and doc-citation
  requirements, and the `user_facing` proposal marker convention that downstream tooling
  (including the new CI gate) relies on.

### Modified Capabilities
- `ci-quality-gates`: adds gate **G9** — a pull request that archives a `user_facing: true`
  OpenSpec change SHALL NOT merge unless `VERSION` has changed relative to `main`.

## Impact

- **Build config**: `Directory.Build.props` (version now read from file, not hardcoded).
- **New file**: `VERSION` at repo root (contains `0.30`).
- **Product code**: `src/OpenWSFZ.Daemon/WelcomeBannerEmitter.cs` (banner now includes version).
  No change expected to `src/OpenWSFZ.Web/AssemblyVersion.cs` or its call sites.
- **Docs**: `README.md`, `REQUIREMENTS.md` (version citation wording); OpenSpec proposal template
  gains the `user_facing` field (`openspec/` tooling config, if the schema template is editable,
  otherwise documented as a required manual convention).
- **CI**: `.github/workflows/ci.yml` gains gate G9 and a VERSION/doc-drift check.
- **Process**: every future `proposal.md` must declare `user_facing`; QA's HK-002 pre-merge
  audit checklist gains one more manual line item (confirm the marker is present and accurate)
  until G9 is proven reliable.
