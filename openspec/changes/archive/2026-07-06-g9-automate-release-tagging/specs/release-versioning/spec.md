## MODIFIED Requirements

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
follow-on action keeps every other surface derived from or consistent with it. Every surface,
including the git tag, is either automatically consistent by construction or CI-automated (see
the `ci-quality-gates` capability's gate G9, which includes a `tag-release-version` job that cuts
the annotated tag on every push to `main` where one is missing) — no surface in this list depends
on a human remembering a manual step.

#### Scenario: All surfaces agree after a version change

- **WHEN** `VERSION` is changed to a new value and the change is merged to `main`
- **THEN** the built assemblies' informational version, the daemon status API, the daemon welcome banner, the `README.md` anchor sentence, and the `REQUIREMENTS.md` anchor sentence SHALL all report that same new value, and an annotated git tag matching it SHALL be cut automatically by CI, with no manual git command required

#### Scenario: A surface drifts from VERSION

- **WHEN** any one of these surfaces reports a version different from `VERSION`'s content
- **THEN** this SHALL be treated as a defect against this requirement, regardless of which surface drifted or why
