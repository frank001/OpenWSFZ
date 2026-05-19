## Why

OpenWSFZ v1 will be delivered through nine sequential OpenSpec changes. Before any of the feature-bearing changes (walking skeleton, configuration, audio, decoder, waterfall, polish, hardening, release) can be reviewed against meaningful gates, the build, CI, and rubric-enforcement tooling must exist. Without these in place, "tests pass" is a claim with nothing behind it, and the strict requirement-traceability rule the project commits to (NFR-006, NFR-007) is unenforceable.

This change establishes the empty-but-gated foundation. It writes no product behaviour and closes no `FR-###` / `NFR-###` from `REQUIREMENTS.md`; it ensures that every subsequent change is judged against the rubric defined in `TESTING_STRATEGY.md`.

## What Changes

- **NEW** `OpenWSFZ.sln` solution at the repository root with `global.json` pinning the .NET 10 SDK feature band and `Directory.Packages.props` centralising NuGet versions.
- **NEW** `src/OpenWSFZ.Abstractions/` class-library project containing placeholder interface files (`IAudioSource.cs`, `IModeDecoder.cs`, `IModeRegistry.cs`, `IBindPolicy.cs`, `IAuthPolicy.cs`, `IHostLifecycle.cs`, `IConfigStore.cs`, `IConfigSnapshot.cs`, `IClock.cs`). Each file is empty save for an XML doc comment naming the phase in which it is implemented; the project compiles green.
- **NEW** `tools/TraceabilityCheck/` first-party console application enforcing rubric criteria **C1** (every `FR-###` / `NFR-###` in `REQUIREMENTS.md` appears in at least one test display name) and **C4** (the mapped test is included in the standard CI run). Exits non-zero on a missing or stale requirement ID. Emits a `traceability.md` report as a CI artefact.
- **NEW** `tools/LicenseInventoryCheck/` first-party console application enforcing the dependency-licence policy. Walks every `obj/project.assets.json` for NuGet references and every entry under `/native/` for submodule licences. Exits non-zero on any non-MIT-redistributable licence. Emits a `licence-inventory.md` report.
- **NEW** `.github/workflows/ci.yml` defining the PR gate set:
  - Build + test on the `{ windows-latest, ubuntu-latest, macos-latest }` matrix.
  - Linux-only `TraceabilityCheck` and `LicenseInventoryCheck` invocations.
  - Linux-only Coverlet coverage collection, ReportGenerator HTML output uploaded as a build artefact (informational, non-gating).
- **NEW** Serena MCP server wired into the project's Claude Code configuration so the DEVELOPER role has symbol-aware tooling available from the first implementation task.
- **NOT IN THIS CHANGE** (Product-Owner-owned and authored separately): `prompts/DEVELOPER.md`, `prompts/QA.md`, and the GitHub branch-protection settings that enforce the CI gates. This proposal lands the tooling; protecting the branch is a one-click operational task on GitHub once the workflow exists.

## Capabilities

### New Capabilities

- `build-pipeline`: the solution layout, the .NET 10 toolchain pin, the central package version policy, and the AOT-publish posture that every later subsystem builds against.
- `ci-quality-gates`: the matrix CI build + test workflow, the six PR gates **G1**&ndash;**G6** named in `TESTING_STRATEGY.md` &sect;7 (build/test on three OSes, perf, traceability, UI visibility, licence, review), and the wiring point for the three release gates **R1**&ndash;**R3** which become active in later phases.
- `requirement-traceability`: the `TraceabilityCheck` tool's contract for parsing `REQUIREMENTS.md`, reflecting over test assemblies, and validating rubric criteria **C1** and **C4**.
- `dependency-licence-policy`: the `LicenseInventoryCheck` tool's contract for enumerating NuGet and submodule dependencies and asserting MIT-redistributable licensing.

### Modified Capabilities

None. This is the first OpenSpec change after the deletion of the abandoned `add-project-skeleton` scaffolding.

## Impact

- **Repository root**: `OpenWSFZ.sln`, `global.json`, `Directory.Packages.props` added.
- **New source tree**: `src/OpenWSFZ.Abstractions/`.
- **New tooling tree**: `tools/TraceabilityCheck/`, `tools/LicenseInventoryCheck/`.
- **CI**: `.github/workflows/ci.yml` added; this is the file that protects `main` from this change forward.
- **Developer environment**: Serena MCP wired into Claude Code; affects the DEVELOPER role's session capabilities, not the runtime binary.
- **External integrations**: GitHub branch protection becomes meaningful once the workflow exists; operationalised by the Product Owner after this change merges.
- **Performance, security, runtime behaviour**: none. This change ships no executable artefact.
- **Risk surface**: validates `TECHNICAL_SPEC.md` &sect;9.3 (build flow) and surfaces .NET 10 AOT-compatibility issues (risk **R2** in `IMPLEMENTATION_PLAN.md`) at the earliest possible moment, while the codebase is empty enough to refactor cheaply.
