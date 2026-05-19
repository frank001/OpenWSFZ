## ADDED Requirements

### Requirement: Solution structure

The repository SHALL contain a single `OpenWSFZ.sln` at the root that references every project under `/src/` and `/tests/`. A `dotnet build` invocation from the repository root SHALL build every project in dependency order with zero errors and zero warnings.

#### Scenario: Empty solution builds clean

- **WHEN** a developer runs `dotnet build` at the repository root with no source files beyond placeholder interface stubs
- **THEN** the command SHALL exit with code 0 and report zero errors and zero warnings

#### Scenario: New project added is picked up by the solution

- **WHEN** a project file is added under `/src/` or `/tests/` and referenced in `OpenWSFZ.sln`
- **THEN** the next `dotnet build` from the repository root SHALL build the new project

### Requirement: .NET SDK version pinning

A `global.json` file at the repository root SHALL pin the .NET SDK feature band that every developer and every CI runner uses. The pinned version SHALL be a .NET 10 LTS feature band.

#### Scenario: Mismatched SDK is rejected

- **WHEN** a developer runs `dotnet build` with an SDK that does not satisfy the `global.json` constraint
- **THEN** the command SHALL fail with an SDK-resolution error before any project is compiled

### Requirement: Centralised NuGet package versions

A `Directory.Packages.props` file at the repository root SHALL declare every NuGet package version used in the solution. Project files SHALL NOT specify a `Version=` attribute on `<PackageReference>` elements.

#### Scenario: Project declaring an inline version fails the build

- **WHEN** a project file is added that specifies an inline version on a `<PackageReference>` element
- **THEN** `dotnet build` SHALL fail with the central-package-management diagnostic

### Requirement: AOT-publish readiness verified on each supported OS

A minimal stub executable project SHALL be present in the solution with `<PublishAot>true</PublishAot>` enabled. The CI workflow SHALL run `dotnet publish` with the AOT flag for `win-x64`, `linux-x64`, and `osx-x64` and SHALL fail the build if any of those publish invocations fail.

#### Scenario: AOT publish succeeds on each target OS

- **WHEN** the CI workflow runs on each of `windows-latest`, `ubuntu-latest`, and `macos-latest`
- **THEN** `dotnet publish -c Release -r <rid> --self-contained --p:PublishAot=true` SHALL exit with code 0 and produce a single-file native executable artefact

#### Scenario: AOT-incompatible code blocks merge

- **WHEN** a developer adds code that fails AOT publish on any target OS
- **THEN** the CI workflow SHALL fail and the pull request SHALL be blocked from merging
