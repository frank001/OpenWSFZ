## 1. Solution and toolchain scaffolding

- [x] 1.1 Create `global.json` at the repository root pinning a .NET 10 LTS SDK feature band with `"rollForward": "latestFeature"`.
- [x] 1.2 Create `Directory.Packages.props` at the repository root enabling central package management (`<ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>`) and pinning the initial set of package versions (xUnit, Coverlet, ReportGenerator, FluentAssertions 6.x).
- [x] 1.3 Create `OpenWSFZ.slnx` at the repository root.
- [x] 1.4 Add a `.editorconfig` at the repository root with C# formatting defaults (4-space indent, LF line endings, UTF-8, file-scoped namespaces, sorted using directives) so all generated and hand-written code is consistent from day one.

## 2. Abstractions project

- [x] 2.1 Create `src/OpenWSFZ.Abstractions/OpenWSFZ.Abstractions.csproj` as a netstandard-compatible class library targeting `net10.0`, with `<Nullable>enable</Nullable>` and `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`.
- [x] 2.2 Add the project to `OpenWSFZ.sln`.
- [x] 2.3 Create placeholder interface files under `src/OpenWSFZ.Abstractions/` &mdash; one file per interface named in `TECHNICAL_SPEC.md` &sect;3.1 (`IAudioSource`, `IAudioDeviceEnumerator`, `IModeDecoder`, `IModeRegistry`, `IBindPolicy`, `IAuthPolicy`, `IHostLifecycle`, `IConfigStore`, `IConfigSnapshot`, `IClock`). Each file contains only an empty `public interface` declaration plus an XML doc comment naming the phase that implements it.
- [x] 2.4 Confirm `dotnet build` from the repository root succeeds with zero warnings.

## 3. AOT-probe project

- [x] 3.1 Create `src/OpenWSFZ.AotProbe/OpenWSFZ.AotProbe.csproj` as an executable targeting `net10.0` with `<PublishAot>true</PublishAot>` and `<RootNamespace>OpenWSFZ.AotProbe</RootNamespace>`.
- [x] 3.2 Add a `Program.cs` whose `Main` returns `0` immediately.
- [x] 3.3 Add the project to `OpenWSFZ.sln`.
- [x] 3.4 Document in the project file's `<PropertyGroup>` that this project is deleted in Phase 1 when `OpenWSFZ.Daemon` takes over the AOT-publish responsibility (as a code comment).

## 4. TraceabilityCheck tool

- [x] 4.1 Create `tools/TraceabilityCheck/TraceabilityCheck.csproj` as an executable targeting `net10.0`, added to `OpenWSFZ.sln`.
- [x] 4.2 Implement `--help` and basic CLI argument parsing (path to `REQUIREMENTS.md`; one or more paths to test assemblies; optional `--report <path>` for the output file).
- [x] 4.3 Implement `REQUIREMENTS.md` parsing to extract every `FR-###` and `NFR-###` identifier; fail on malformed identifiers with a clear message.
- [x] 4.4 Implement reflection over each supplied test assembly to enumerate `[Fact]` and `[Theory]` display names; respect `Skip` attributes by treating skipped tests as absent.
- [x] 4.5 Implement requirement-ID extraction from test display names per the parser rules in `specs/requirement-traceability/spec.md` (comma-separated IDs followed by a colon).
- [x] 4.6 Implement the missing-mapping check; exit non-zero with a clear message naming every unmapped ID.
- [x] 4.7 Implement the stale-reference check; exit non-zero on any test referencing an ID not in `REQUIREMENTS.md`.
- [x] 4.8 Implement `traceability.md` report emission, written even when the run fails.
- [x] 4.9 Add a minimal `TraceabilityCheck.Tests` xUnit project under `/tests/` with display names `"P0-Tool: <description>"` (the `P0-Tool` prefix is non-requirement and is ignored by the tool's own self-run, so the tool's tests can exist without polluting the rubric for `FR-###` / `NFR-###` IDs).
- [x] 4.10 Write tool tests covering each scenario in `specs/requirement-traceability/spec.md`.

## 5. LicenseInventoryCheck tool

- [x] 5.1 Create `tools/LicenseInventoryCheck/LicenseInventoryCheck.csproj` as an executable targeting `net10.0`, added to `OpenWSFZ.sln`.
- [x] 5.2 Implement `--help` and CLI argument parsing (path to the solution root; optional `--report <path>` for the output file).
- [x] 5.3 Implement detection of the missing-restore precondition (no `project.assets.json` files found) and surface a clear error message.
- [x] 5.4 Implement NuGet enumeration by reading each project's `obj/project.assets.json`; resolve direct and transitive references with their resolved versions and SPDX licence expressions.
- [x] 5.5 Implement submodule enumeration by walking `/native/` for git submodules, reading `LICENCE` / `LICENSE` / `LICENCE.txt` / `LICENSE.txt` at each submodule root, and recording the pinned commit SHA.
- [x] 5.6 Implement the allow-list check including SPDX-OR expression handling (`A OR B` passes when either alternative is allowed).
- [x] 5.7 Implement the FluentAssertions &geq; 7.0 block rule with a project-policy message.
- [x] 5.8 Implement `licence-inventory.md` report emission, written even when the run fails.
- [x] 5.9 Add a minimal `LicenseInventoryCheck.Tests` xUnit project under `/tests/` mirroring the pattern from task 4.9.
- [x] 5.10 Write tool tests covering each scenario in `specs/dependency-licence-policy/spec.md`.

## 6. CI workflow

- [x] 6.1 Create `.github/workflows/ci.yml` defining the matrix `{ windows-latest, ubuntu-latest, macos-latest }`, triggered on push and pull-request.
- [x] 6.2 Add steps per matrix leg: checkout (with submodules), set up .NET, `dotnet restore`, `dotnet build -c Release --no-restore`, `dotnet test -c Release --no-build --logger trx --collect:"XPlat Code Coverage"`, upload test results as artefacts.
- [x] 6.3 Add an AOT-publish step per matrix leg targeting the leg's RID (`win-x64` / `linux-x64` / `osx-x64`); fail the workflow on a non-zero publish exit.
- [x] 6.4 Add Linux-only steps invoking `tools/TraceabilityCheck` (parameters: path to `REQUIREMENTS.md`, paths to all test assemblies under `**/bin/Release/net10.0/*.Tests.dll`) and `tools/LicenseInventoryCheck` (parameter: solution root); fail the workflow on a non-zero exit from either.
- [x] 6.5 Add a Linux-only Coverlet + ReportGenerator step producing an HTML coverage report, uploaded as a build artefact and explicitly not used to fail the workflow.
- [x] 6.6 Add inert workflow steps for the performance gate (G2) and the strict-UI-visibility gate (G4) that succeed when no tagged tests are present; these become real gates in later phases.
- [x] 6.7 Configure caching: the .NET package cache (`~/.nuget/packages`) and the `obj/` directories keyed on `Directory.Packages.props` and `**/*.csproj` hashes.

## 7. Serena MCP integration

- [x] 7.1 Verify the existence and format of `.claude/mcp.json` (or the current Claude Code MCP configuration file) in the project's `.claude/` directory.
- [x] 7.2 Add a Serena MCP server entry to the configuration. The entry SHALL point at the developer's local Serena installation; the exact command line is captured from Serena's documentation.
- [x] 7.3 Document the Serena prerequisite in a single short note in `prompts/DEVELOPER.md` (to be authored separately by the Product Owner) &mdash; this task captures the documentation pointer only; no content is written to `prompts/DEVELOPER.md` in this change.
- [ ] 7.4 Verify in a Claude Code session that Serena's tools (`get_symbols`, `find_references`, etc.) appear and respond.

## 8. Repository housekeeping

- [x] 8.1 Update `.gitignore` to add `/obj/`, `/bin/`, `/*.user`, `coverage*/`, `TestResults/`, `*.coverage`, `traceability.md`, and `licence-inventory.md` (the last two are CI-artefact files; locally generated copies should not be committed).
- [x] 8.2 Update `README.md` to add a one-line note under "Status" pointing at this change proposal as the first OpenSpec change for v1, and to mention that v1 development proceeds through the OpenSpec workflow.

## 9. Exit-gate verification

- [x] 9.1 Run `dotnet build` from the repository root on Windows, Linux, and macOS; confirm zero errors and zero warnings.
- [x] 9.2 Run `dotnet test` from the repository root; confirm the tool-tests pass and the count of non-tool tests is 0.
- [x] 9.3 Run `dotnet publish -c Release -r <rid> --self-contained --p:PublishAot=true` against `OpenWSFZ.AotProbe` on each of Windows, Linux, and macOS; confirm a single-file native executable is produced on each.
- [ ] 9.4 Trigger the CI workflow on a feature branch by opening a draft pull-request; confirm all three matrix legs report green, the Linux-only `TraceabilityCheck` and `LicenseInventoryCheck` steps report green, and the coverage and inert-gate steps complete without error.
- [ ] 9.5 Inform the Product Owner that the workflow is in place and the branch-protection settings on `main` are ready to be configured (require all G1, G3, G5, and at-least-one-review).

## 10. Hand-off

- [ ] 10.1 Mark the PR ready-for-review and request the QA role's gate review.
- [ ] 10.2 Once merged, archive this change via `openspec archive p0-foundation` so its specs migrate to `openspec/specs/` as the live source-of-truth specifications.
- [ ] 10.3 Open the Phase 1 OpenSpec change proposal (`p1-walking-skeleton`) using `openspec new change p1-walking-skeleton` and reference `IMPLEMENTATION_PLAN.md` &sect;8 for its task seed.
