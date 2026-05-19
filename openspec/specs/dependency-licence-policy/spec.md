## Requirements

### Requirement: Tool exists and runs from CI

A first-party .NET console application SHALL exist at `tools/LicenseInventoryCheck/` and SHALL be invocable from CI via `dotnet run --project tools/LicenseInventoryCheck/ -- <args>`. The tool SHALL accept the path to the solution root and SHALL discover NuGet references and `/native/` submodules without further configuration.

#### Scenario: Tool builds and runs with `--help`

- **WHEN** a developer runs `dotnet run --project tools/LicenseInventoryCheck/ -- --help`
- **THEN** the tool SHALL exit with code 0 and print usage information

### Requirement: Enumeration of NuGet dependencies

The tool SHALL enumerate every NuGet package referenced (directly or transitively) by every project in `OpenWSFZ.slnx`. The enumeration source SHALL be each project's `obj/project.assets.json` produced by `dotnet restore`.

#### Scenario: Direct NuGet reference is enumerated

- **WHEN** a project declares `<PackageReference Include="xunit" />`
- **THEN** the tool's report SHALL include `xunit` with its resolved version and licence

#### Scenario: Transitive NuGet reference is enumerated

- **WHEN** a referenced NuGet package itself depends on `Microsoft.Extensions.Logging.Abstractions`
- **THEN** the tool's report SHALL include `Microsoft.Extensions.Logging.Abstractions` with its resolved version and licence

### Requirement: Enumeration of native submodules

The tool SHALL enumerate every git submodule under `/native/`. For each submodule, the tool SHALL read its declared licence from a `LICENCE`, `LICENSE`, `LICENCE.txt`, or `LICENSE.txt` file at the submodule root and SHALL record its pinned commit SHA from `.gitmodules` and `git ls-tree`.

#### Scenario: Submodule with a LICENSE file is enumerated

- **WHEN** `/native/ft8_lib/` is a submodule containing a `LICENSE` file
- **THEN** the tool's report SHALL include `ft8_lib` with the licence's SPDX identifier and the pinned commit SHA

#### Scenario: Submodule without a recognised licence file fails the run

- **WHEN** a submodule under `/native/` has no `LICENCE` / `LICENSE` file at its root
- **THEN** the tool SHALL exit non-zero with a message naming the submodule

### Requirement: Allowed-licence policy

The tool SHALL fail when any enumerated dependency has a licence that is not on the allow-list. The allow-list SHALL include: `MIT`, `BSD-2-Clause`, `BSD-3-Clause`, `Apache-2.0`, `CC0-1.0`, `0BSD`, `ISC`, the PortAudio licence, and SPDX-OR expressions where at least one alternative is on the allow-list.

#### Scenario: MIT-licensed dependency passes

- **WHEN** a NuGet package declares `MIT` as its licence
- **THEN** the tool SHALL accept it and NOT contribute to a non-zero exit

#### Scenario: Apache-2.0 or MIT (SPDX-OR) dependency passes

- **WHEN** a NuGet package declares its licence as `Apache-2.0 OR MIT`
- **THEN** the tool SHALL accept it and NOT contribute to a non-zero exit

#### Scenario: GPL-licensed dependency fails

- **WHEN** any enumerated dependency declares `GPL-3.0-only`, `GPL-3.0-or-later`, `GPL-2.0-only`, `LGPL-3.0`, or any other GPL variant
- **THEN** the tool SHALL exit non-zero and the failure message SHALL name the dependency and its licence

#### Scenario: Unknown licence fails

- **WHEN** any enumerated dependency declares a licence not on the allow-list and not on a documented block-list
- **THEN** the tool SHALL exit non-zero and request explicit policy review

### Requirement: FluentAssertions pinned to permissive release

The tool SHALL fail if `FluentAssertions` is referenced at a version of `7.0.0` or later. The pin SHALL be enforced regardless of whether `FluentAssertions` is referenced directly or transitively.

#### Scenario: FluentAssertions 6.x is accepted

- **WHEN** the solution references `FluentAssertions` at version `6.12.0`
- **THEN** the tool SHALL accept it

#### Scenario: FluentAssertions 7.x is rejected

- **WHEN** the solution references `FluentAssertions` at version `7.0.0` or later
- **THEN** the tool SHALL exit non-zero and the failure message SHALL state the project policy on FluentAssertions versions

### Requirement: Report artefact

On every run, the tool SHALL emit a `licence-inventory.md` report listing every enumerated dependency, its version, its licence, and its provenance (NuGet package id or submodule path). The report file path SHALL be configurable via a CLI option and SHALL default to `licence-inventory.md` in the current working directory.

#### Scenario: Report file is produced even when the run fails

- **WHEN** the tool exits non-zero due to a policy violation
- **THEN** the `licence-inventory.md` report SHALL still be written to disk for inspection

### Requirement: Restore precondition

The tool SHALL detect when `dotnet restore` has not been run for the solution and SHALL emit a clear error rather than producing a misleading empty inventory.

#### Scenario: Missing project.assets.json halts the run

- **WHEN** the tool is invoked against a solution whose projects have not been restored
- **THEN** the tool SHALL exit non-zero with a message instructing the operator to run `dotnet restore` first
