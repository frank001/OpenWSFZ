## Context

The repository is currently empty of build, source, CI, and rubric-enforcement infrastructure. Three architecture artefacts (`TECHNICAL_SPEC.md`, `TESTING_STRATEGY.md`, `IMPLEMENTATION_PLAN.md`) describe the v1 design but nothing in the repository enforces them. This change closes that gap before any feature work begins.

`prompts/DEVELOPER.md` and `prompts/QA.md` are being authored separately by the Product Owner and are not part of this change. The Serena MCP wiring is included because it is a code/config change (`.claude/` config edit) that the developer agent can deliver in the same review.

This change writes no product code and no test code. It writes only the scaffolding against which all subsequent code and tests will be judged.

## Goals / Non-Goals

**Goals:**

- A `dotnet build` of the empty solution succeeds on Windows, Linux, and macOS.
- A `dotnet test` against the empty solution succeeds (zero tests, exit code 0).
- The CI matrix workflow runs to completion and reports green on every push and pull-request.
- The two first-party gate tools (`TraceabilityCheck`, `LicenseInventoryCheck`) compile, run, and report sensibly against an empty solution.
- AOT publish (`dotnet publish -c Release -r <rid> --self-contained --p:PublishAot=true`) is exercised on each OS at least once to surface AOT-compatibility issues in the toolchain at the smallest possible code size (risk **R2** in `IMPLEMENTATION_PLAN.md`).
- Serena MCP is reachable from Claude Code sessions in the project's `.claude` configuration.

**Non-Goals:**

- No HTTP server, no audio code, no decoder, no UI &mdash; those land in later phases.
- No `prompts/DEVELOPER.md` / `prompts/QA.md` content; the Product Owner is authoring those.
- No GitHub branch-protection configuration; that is a one-click operational task performed by the Product Owner against the GitHub UI once this change merges.
- No public NuGet package publication; OpenWSFZ ships as source / executables, not as libraries.
- No release-tag mechanics; `release.yml` lands in Phase 7.

## Decisions

### D1 &mdash; Single solution file, multi-project layout

A single `OpenWSFZ.sln` at the repository root references every project under `/src/` and `/tests/`. The alternative of separate solutions per layer (daemon-only, tests-only) was rejected because:
- `dotnet build` / `dotnet test` from the repository root must work in CI and locally with one command.
- IDE refactoring across projects is materially easier with a single solution.
- The repository is small enough that solution-loading time is irrelevant.

### D2 &mdash; Central package management via `Directory.Packages.props`

NuGet package versions are pinned in a single file at the repository root, not per-project. This guarantees version uniformity across the solution and makes the licence inventory tool's job (and any future security-update sweeps) tractable.

### D3 &mdash; First-party gate tools instead of third-party

`TraceabilityCheck` and `LicenseInventoryCheck` are written in C# as small (&lt; 200 LoC each) console applications in `/tools/`. The alternative of a third-party tool was rejected because:
- The traceability rubric (`TESTING_STRATEGY.md` &sect;3) is project-specific; no existing tool implements it.
- The licence policy is project-specific (MIT-redistributable; FluentAssertions pinned at the last 6.x release; submodule manifests included).
- Both tools have very small surface areas and are themselves test-covered.
- They join the same .NET toolchain everything else uses, removing a per-OS install burden in CI.

### D4 &mdash; AOT enabled from the first executable

`<PublishAot>true</PublishAot>` will be set in the Daemon project when it lands in Phase 1, but the project file template and the CI `publish` step are wired in this change so that the AOT path is exercised on each OS at least once even at this empty-solution stage. The alternative of "enable AOT later when hardening" was rejected because AOT incompatibilities (with ASP.NET Core minimal APIs, Tomlyn, xUnit, or any other library) are dramatically cheaper to discover while the codebase is empty than at Phase 7.

For P0 specifically, the AOT exercise is performed against `OpenWSFZ.Abstractions` (which is a library, not an executable) by adding a minimal stub console project (`/src/OpenWSFZ.AotProbe/`) whose entire content is `return 0;`. The probe is built and AOT-published in CI per OS; if AOT publish fails on any OS, the PR is blocked. The probe project is deleted in Phase 1 when `OpenWSFZ.Daemon` takes over the AOT-publish responsibility.

### D5 &mdash; CI matrix limited to x86_64

The GitHub Actions runners `windows-latest`, `ubuntu-latest`, and `macos-latest` are all x86_64 in 2026-05; this matches the v1 portability target (NFR-001). ARM64 runners are available on GitHub Actions but are out of scope for v1 and are not configured.

### D6 &mdash; Coverage informational, not gating, in this change

Coverlet runs in CI and uploads its HTML report as an artefact, but no coverage threshold is set. This matches `TESTING_STRATEGY.md` &sect;3.2's explicit decision that coverage percentage is informational; the gating signal is requirement traceability.

### D7 &mdash; Serena MCP wired via `.claude/` configuration

Serena is integrated through Claude Code's MCP server configuration mechanism. The exact configuration file location and format follow Claude Code conventions (`.claude/mcp.json` or equivalent depending on Claude Code version). This change adds the necessary configuration entries; verification is by opening a Claude Code session in the project and confirming Serena's tools appear.

## Risks / Trade-offs

- **AOT toolchain incompatibility with .NET 10 on a specific OS** &rarr; CI exercise per OS in this change surfaces the problem now. If unsolvable, falls back to JIT publish for v1 with a tracked issue against AOT for v2. Documented under **R2** in `IMPLEMENTATION_PLAN.md` &sect;9.
- **`TraceabilityCheck` false positives** when `REQUIREMENTS.md` changes faster than tests &rarr; the tool reports each unmapped ID in its CI log; a missing mapping fails the build, which is the intended behaviour per **C1**. If this becomes noisy in practice, a brief `traceability-debt.md` file at the repository root may be permitted as an explicit grace-period mechanism &mdash; but only for IDs whose phase has not yet started.
- **`LicenseInventoryCheck` over-strictness** &mdash; some transitive NuGet dependencies are dual-licensed (Apache-2.0 / MIT) and the tool must read the entire SPDX expression, not just the first listed licence. The tool's spec (see `specs/dependency-licence-policy/spec.md`) covers SPDX-OR expressions explicitly.
- **Serena MCP availability drift** &mdash; if Serena's MCP server interface changes, the developer agent loses tooling but the build is unaffected. Documented as a quiet failure mode; surfaces in developer experience rather than CI.

## Migration Plan

Not applicable. The repository has no prior state to migrate from; the abandoned `add-project-skeleton` scaffolding was removed at the start of the architecture phase and is not being re-introduced.

## Open Questions

None gating this change. All architecture-level questions for P0 are answered in `TECHNICAL_SPEC.md` &sect;9, `TESTING_STRATEGY.md` &sect;7&ndash;9, and `IMPLEMENTATION_PLAN.md` &sect;5.0 / &sect;7.
