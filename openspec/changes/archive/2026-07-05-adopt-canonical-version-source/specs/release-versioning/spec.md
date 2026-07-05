## ADDED Requirements

### Requirement: Canonical version source

A file named `VERSION` SHALL exist at the repository root, containing exactly one line: the
current project version with no leading `v` and no trailing content beyond an optional trailing
newline (e.g. `0.30`). `VERSION` SHALL be the single hand-edited source of the project's version;
no other file SHALL declare a version value independent of it.

#### Scenario: VERSION file present and well-formed

- **WHEN** the repository is inspected at the root
- **THEN** a `VERSION` file SHALL exist containing a single `MAJOR.MINOR` (or `MAJOR.MINOR.PATCH`) line with no `v` prefix

### Requirement: Version consistency across all surfaces

At all times on `main`, every surface that reports or states the project's version SHALL agree
with `VERSION`'s content. This is the umbrella invariant the other requirements in this
capability exist to serve; it is listed explicitly, and separately, so it can be checked as a
single fact rather than inferred piecemeal. The surfaces are: `VERSION` itself; the assembly
version derived from `Directory.Build.props` (and therefore `AssemblyInformationalVersion` on
every built assembly); the daemon's status API (`GET /api/v1/status` and the WebSocket
equivalent); the daemon's stdout welcome banner; the anchor sentence in `README.md`; the anchor
sentence in `REQUIREMENTS.md`; and, following each release, the corresponding annotated git tag.
A change to `VERSION` SHALL be accompanied, in the same commit or pull request, by whatever
follow-on action keeps every other surface derived from or consistent with it (most surfaces are
automatically consistent by construction — see the other requirements in this capability — but
the git tag is cut manually and SHALL NOT be forgotten).

#### Scenario: All surfaces agree after a version change

- **WHEN** `VERSION` is changed to a new value and the change is merged to `main`
- **THEN** the built assemblies' informational version, the daemon status API, the daemon welcome banner, the `README.md` anchor sentence, and the `REQUIREMENTS.md` anchor sentence SHALL all report that same new value, and an annotated git tag matching it SHALL be cut

#### Scenario: A surface drifts from VERSION

- **WHEN** any one of these surfaces reports a version different from `VERSION`'s content
- **THEN** this SHALL be treated as a defect against this requirement, regardless of which surface drifted or why

### Requirement: Build reads the canonical version

`Directory.Build.props` SHALL derive its `<Version>` MSBuild property by reading `VERSION` at
build time rather than declaring a literal value. Every assembly built from the solution SHALL
therefore carry `VERSION`'s content as its `AssemblyInformationalVersion`.

#### Scenario: Build picks up VERSION without a source change

- **WHEN** `VERSION`'s content is changed and the solution is rebuilt with no other edits
- **THEN** every built assembly's `AssemblyInformationalVersionAttribute` SHALL reflect the new value

#### Scenario: Status API reports the current version

- **WHEN** the daemon is running and a client requests status via the HTTP or WebSocket API
- **THEN** the `Version` field in the response SHALL equal `VERSION`'s content (via the existing `AssemblyVersion.Get()` resolution path)

### Requirement: Welcome banner reports the running version

The daemon's startup banner (`WelcomeBannerEmitter.Emit`) SHALL include the running build's
version alongside the loopback URL it already prints.

#### Scenario: Banner includes version on daemon start

- **WHEN** the daemon finishes starting its HTTP listener and emits the welcome banner
- **THEN** the banner line written to stdout SHALL include the current version string

### Requirement: Documentation cites the canonical version

`README.md` and `REQUIREMENTS.md` SHALL each state the current version in a sentence matching
the pattern `The current release is **v<VERSION>**.` (bold markers optional) so that the value
can be mechanically checked against `VERSION`. Neither document SHALL be the source of truth for
the version — both cite it.

#### Scenario: Doc version matches VERSION file

- **WHEN** `VERSION` contains `0.30`
- **THEN** the anchor sentence in `README.md` and in `REQUIREMENTS.md` SHALL each read `v0.30`

### Requirement: Minor-version-per-user-facing-feature rule

Every user-facing feature merged to `main` SHALL increment the minor version component of
`VERSION` by exactly one relative to its value on `main` before the merge. A feature is
"user-facing" if and only if the OpenSpec change that ships it declares `user_facing: yes` (see
the OpenSpec proposal marker requirement below). Non-feature changes (defect fixes, diagnostics,
QA-study runs, CI/tooling, documentation-only changes) SHALL NOT be required to change `VERSION`.

#### Scenario: User-facing change bumps the minor version

- **WHEN** an OpenSpec change declared `user_facing: yes` is archived in a pull request
- **THEN** that pull request SHALL also change `VERSION`'s content relative to `main`

#### Scenario: Non-feature change does not require a bump

- **WHEN** a pull request archives one or more OpenSpec changes all declared `user_facing: no`
- **THEN** that pull request SHALL NOT be required to change `VERSION`

### Requirement: OpenSpec proposals declare user-facing status

Every `proposal.md` SHALL declare, on a single line before its `## Why` heading, whether the
change ships operator-visible behaviour, in the exact form `**User-facing:** yes` or
`**User-facing:** no`. This declaration is the sole input the minor-version-bump rule and its CI
enforcement (gate G9, see the `ci-quality-gates` capability) use to classify a change.

#### Scenario: Proposal declares user-facing status

- **WHEN** a new OpenSpec change's `proposal.md` is authored
- **THEN** it SHALL begin with a `**User-facing:** yes` or `**User-facing:** no` line before the `## Why` heading

#### Scenario: Missing or malformed declaration is treated as non-compliant

- **WHEN** a `proposal.md` being archived lacks the `**User-facing:**` line or its value is neither `yes` nor `no`
- **THEN** the change SHALL be treated as failing this requirement and SHALL be corrected before archive
