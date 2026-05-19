## MODIFIED Requirements

### Requirement: AOT-publish readiness verified on each supported OS

The `OpenWSFZ.Daemon` executable project SHALL carry `<PublishAot>true</PublishAot>`. The CI workflow SHALL run `dotnet publish` with the AOT flag for `win-x64`, `linux-x64`, and `osx-x64` and SHALL fail the build if any of those publish invocations fail.

#### Scenario: AOT publish succeeds on each target OS

- **WHEN** the CI workflow runs on each of `windows-latest`, `ubuntu-latest`, and `macos-latest`
- **THEN** `dotnet publish -c Release -r <rid> --self-contained -p:PublishAot=true` against `OpenWSFZ.Daemon` SHALL exit with code 0 and produce a single-file native executable artefact

#### Scenario: AOT-incompatible code blocks merge

- **WHEN** a developer adds code that fails AOT publish on any target OS
- **THEN** the CI workflow SHALL fail and the pull request SHALL be blocked from merging

## REMOVED Requirements

### Requirement: Solution structure references OpenWSFZ.AotProbe

**Reason:** `OpenWSFZ.AotProbe` was a Phase 0 placeholder whose sole purpose was to verify AOT publish works before any real code existed. `OpenWSFZ.Daemon` now fulfils this role as a production executable.

**Migration:** Remove `src/OpenWSFZ.AotProbe/` from the repository and from `OpenWSFZ.slnx`. Update CI steps that reference `OpenWSFZ.AotProbe` to target `OpenWSFZ.Daemon` instead.
