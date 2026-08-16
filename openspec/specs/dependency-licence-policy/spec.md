# dependency-licence-policy Specification

## Purpose

Specifies the licence-inventory tool: how it enumerates NuGet dependencies and native
submodules (including `kgoba/ft8_lib`), applies the allowed-licence policy, and produces
its report artefact from CI.

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

---

### Requirement: ft8_lib native dependency is vendored and approved

The `ft8_lib` library (the `frank001/ft8_lib` fork of upstream `kgoba/ft8_lib`, `msvc-compat` branch) SHALL be integrated by **vendoring** the source files actually required to link `libft8` into version control under `native/ft8_lib_vendor/`, preserving the upstream `LICENSE` verbatim (see the `native-build-provenance` capability for the vendored file list and provenance requirements). It SHALL NOT be integrated as a git submodule. ⚠️ **Correction to the prior version of this requirement:** it previously stated `ft8_lib` "SHALL be added as a git submodule at `/native/ft8_lib/`" — that was never implemented (`.gitmodules` is empty, `git submodule status` returns nothing), and this delta corrects the requirement to match the vendoring approach actually taken, which is also how this codebase already handles the two MSVC-VLA-patched files (`decode.c`, `monitor.c`) under `native/ft8_lib_build/patched/`. `LicenseInventoryCheck`'s `SubmoduleEnumerator` walks every directory under `/native/` and records an entry for any directory containing a recognised `LICENSE`/`LICENCE` file when `.gitmodules` declares no `native/*` submodules (the current state), so it SHALL opportunistically pick up `native/ft8_lib_vendor/`'s vendored `LICENSE` without further tool changes; this CI-facing enumeration is a **separate** obligation from, and does not substitute for, the shipped `THIRD-PARTY-NOTICES.md` this change adds below — the inventory report is a build artefact for policy enforcement, the notices file is what travels with the distribution.

#### Scenario: Vendored ft8_lib is enumerated with MIT licence

- **WHEN** `LicenseInventoryCheck` is run against the solution root after `native/ft8_lib_vendor/`
  has been vendored with its `LICENSE` file present
- **THEN** the `licence-inventory.md` report SHALL include an entry for `native/ft8_lib_vendor`
  with licence `MIT`

#### Scenario: No git submodule is required or expected

- **WHEN** `.gitmodules` is inspected after this change lands
- **THEN** it SHALL still contain no `native/ft8_lib` entry, and the absence of a submodule SHALL
  NOT be treated as a policy violation by any CI gate

#### Scenario: G5 gate remains green after ft8_lib is vendored

- **WHEN** `dotnet run --project tools/LicenseInventoryCheck` is run in CI after the vendored tree
  is committed
- **THEN** the tool SHALL exit 0 (MIT is on the allow-list) and SHALL NOT produce any licence-policy
  warning for the vendored `ft8_lib` files

### Requirement: Shipped third-party notices file

The repository SHALL contain `THIRD-PARTY-NOTICES.md` at its root, reproducing in full: the MIT licence text with Kārlis Goba's copyright notice (for `ft8_lib`, `ft8/` and `common/`), and the BSD-3-Clause licence text with Mark Borgerding's copyright notice (for KISS FFT, `fft/kiss_fft.c`/`kiss_fftr.c`/`_kiss_fft_guts.h`) — reproduced in full rather than referencing a `COPYING` file, since no such file exists in the vendored `fft/` directory despite the upstream header's "See COPYING file" comment. A case-insensitive scan of the vendored tree for the strings `GNU General Public`, `GPL`, and `Affero` SHALL find zero hits — this includes the two known, Captain-ruled flagged-not-blocking WSJT-X-attribution comments in `ft8/constants.h` (lines 75 and 78, which credit WSJT-X as the historical source of two LDPC parity-table constants, are not themselves GPL-licensed text, and — measured during r0-reproducible-native-build's implementation — do not contain any of the three scanned strings in the first place, reading only "From WSJT-X's ...") — any hit at all SHALL block this requirement from being satisfied.

#### Scenario: Notices file contains both required licence texts

- **WHEN** `THIRD-PARTY-NOTICES.md` is inspected after this change lands
- **THEN** it SHALL contain the full MIT licence text with Kārlis Goba's copyright, and the full
  BSD-3-Clause licence text with Mark Borgerding's copyright

#### Scenario: GPL/AGPL scan finds zero hits

- **WHEN** the vendored tree is scanned (case-insensitive) for `GNU General Public`, `GPL`, and
  `Affero`
- **THEN** the scan SHALL find zero hits — the WSJT-X-attribution comments at `ft8/constants.h`
  lines 75 and 78 are confirmed present and unremoved (verified separately, by scanning for
  `WSJT-X`) but do not themselves contain any of the three scanned strings, so they were never
  going to register as hits under this scan — and any hit that does occur SHALL be treated as a
  licence-policy violation

#### Scenario: Fortran-only directory is absent

- **WHEN** the vendored tree is inspected
- **THEN** no `ft4_ft8_public/` path SHALL exist anywhere under it (no licence header of any kind;
  not needed by any build step)
