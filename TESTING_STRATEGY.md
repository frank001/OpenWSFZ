# OpenWSFZ &mdash; Testing Strategy

**Version:** 1.0
**Date:** 2026-05-18
**Status:** Draft &mdash; pending Product Owner approval
**Author:** ARCHITECT role (AI-assisted)
**Source of requirements:** [`REQUIREMENTS.md`](./REQUIREMENTS.md) v1.1, especially **NFR-006** (meaningful behaviour coverage) and **NFR-007** (red builds block progress)
**Companion to:** [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md) &sect;10

> **Reading order**
> 1. `REQUIREMENTS.md` &mdash; the requirement IDs this strategy is gated against.
> 2. `TECHNICAL_SPEC.md` &mdash; the components being tested.
> 3. This document &mdash; how, where, and to what bar they are tested.

---

## 1. Purpose

This document defines **what "tested" means** for OpenWSFZ v1. It is the operational reference for the **QA role** (and for the DEVELOPER role when writing tests alongside code). It resolves REQUIREMENTS &sect;8 Question 7 ("define the rubric for meaningful coverage").

If a disagreement arises about whether a change is adequately tested, this document is the tie-breaker.

---

## 2. Principles

1. **Tests are first-class artefacts.** A change is not complete until its tests are written, passing, and merged with the change.
2. **Coverage is *behavioural*, not *line-based*.** Coverage percentage is **informational only**. The gating signal is **requirement traceability** (&sect;5).
3. **Red builds block everything (NFR-007).** No merge with a failing test, no release with a failing test, no "we'll fix it after". Flaky tests are bugs to fix, never to silence (&sect;11).
4. **Determinism is mandatory.** A test that passes only "most of the time" is broken. We never use real wall-clock waits, real network I/O, real audio devices, or real randomness without seeding.
5. **Speed matters.** The full test suite runs in **&leq; 60 seconds** in CI (TECHNICAL_SPEC &sect;11). Slow tests are factored or moved to the soak / nightly tier (&sect;4.6).
6. **Test what's observable, not what's implemented.** A unit test should fail when the *requirement* is violated, not merely when an internal helper is renamed. This makes the suite a refactoring ally, not a refactoring enemy.
7. **One source of truth for test names.** Test names embed the requirement ID they cover (&sect;6). The CI traceability gate (&sect;7) is what makes this enforceable.

---

## 3. The "Meaningful Coverage" Rubric (NFR-006)

This is the explicit answer to REQUIREMENTS &sect;8 Q7.

A requirement (any `FR-###` or `NFR-###`) is considered **meaningfully covered** if and only if **all** of the following hold:

| Criterion | Definition |
|---|---|
| **C1** &mdash; mapped | The requirement ID appears in at least one test method name. |
| **C2** &mdash; observable | The named test asserts on the requirement's **observable behaviour** (output, side effect, state visible through a public interface), not on a private implementation detail. |
| **C3** &mdash; failing-by-mutation | If the production code that delivers the requirement is mutated to no longer deliver it (deleted, inverted, no-opped), at least one mapped test must fail. This is verified by code review during PR; mutation testing tooling is a v2 ambition (&sect;13). |
| **C4** &mdash; runnable in CI | The test is included in the standard CI run (not skipped, not `[Trait("manual")]`, not `[Fact(Skip = "...")]`). |
| **C5** &mdash; deterministic | The test passes consistently. A test that needs a wall-clock delay, real I/O, or unseeded randomness fails this criterion. |

The CI **traceability gate** (&sect;7.1) enforces **C1** and **C4** automatically. **C2, C3, C5** are enforced at code review by the QA role.

### 3.1 What "meaningful coverage" does *not* require

* It does **not** require a specific line-coverage percentage.
* It does **not** require multiple tests per requirement (one well-named test is enough if it asserts the requirement's full behaviour).
* It does **not** require a test for every internal helper; helpers earn tests when they encapsulate non-trivial logic worth verifying in isolation.

### 3.2 Why this rubric and not "100% line coverage"

Line-coverage targets reward the wrong behaviour: tests written to touch lines, not to verify behaviour. A 95%-line-covered code base can still ship the wrong feature. **Requirement traceability** binds the test suite to the contract with the Product Owner. **Coverage tooling** continues to run (&sect;9) as a useful smell-detector, but it does not gate the build.

---

## 4. The Testing Pyramid for OpenWSFZ

Tests live in six tiers, listed cheapest-and-fastest first.

### 4.1 Unit tests

* **Scope:** one class or one small cluster of classes. No I/O. No network. No real audio devices. Time is injected via `IClock`.
* **Tool:** xUnit + FluentAssertions (optional ergonomic helper, MIT).
* **Speed budget:** any individual unit test &lt; 50 ms. Whole unit-test suite &lt; 10 s.
* **Where:** every `OpenWSFZ.*` library project has a sibling `OpenWSFZ.*.Tests` project.

### 4.2 Decoder fixture tests &mdash; the FT8 correctness linchpin

* **Scope:** the FT8 decoder, end to end, against pre-recorded WAV inputs with known expected decode payloads.
* **Tool:** xUnit + a `WavFixtureTheoryDataProvider` that enumerates `*.wav` files in the corpus directory and pairs each with its `*.expected.json` companion.
* **Assertion:** for each fixture, the decoder produces exactly the expected set of `Ft8DecodeMessage` records (decoded text, audio offset, time offset within tolerance, SNR within tolerance).
* **Tolerances:** offset &plusmn; 1 Hz, time offset &plusmn; 0.1 s, SNR &plusmn; 1 dB. Decoded text must match exactly.
* **Live in:** `tests/OpenWSFZ.Decoding.Ft8.Tests/`, with the corpus under `tests/OpenWSFZ.Decoding.Ft8.Tests/Fixtures/Wav/`. Corpus sourcing in &sect;5.
* **Speed budget:** whole decoder-fixture suite &lt; 20 s on Linux. Larger fixtures are tagged `[Trait("corpus", "extended")]` and run nightly only.

This tier is the **single most important** part of the suite. It is what proves OpenWSFZ decodes FT8 correctly, and it is what makes the clean-room MIT story defensible (we can demonstrate correctness against the same fixtures the upstream `ft8_lib` and the WSJT-X reference suite use).

### 4.3 Integration tests (in-process)

* **Scope:** boot the daemon with `WebApplicationFactory<Program>`, hit real HTTP endpoints and a real WebSocket on a loopback ephemeral port, but with `IAudioSource` swapped for a `WavFileAudioSource` that replays a fixture instead of opening a microphone.
* **Tool:** `Microsoft.AspNetCore.Mvc.Testing` (MIT).
* **Asserts** the contract between subsystems: that a known WAV in produces the expected `decode` WS events out; that `/api/v1/status` reflects state changes; that `PUT /api/v1/config` round-trips through disk; that the welcome banner appears on stdout; that the loopback-pin overrides config attempts to bind elsewhere.
* **Live in:** `tests/OpenWSFZ.Web.Tests/` (the assembly name is historical; this is the integration tier).
* **Speed budget:** whole integration suite &lt; 20 s on Linux.

### 4.4 End-to-end tests (built-binary)

* **Scope:** **the actual published AOT binary**, launched as a subprocess on each OS in CI, exercised through real HTTP and WebSocket from the test runner.
* **Tool:** xUnit driving `System.Diagnostics.Process`, plus `System.Net.WebSockets.ClientWebSocket`.
* **What they catch that integration tests don't:** packaging regressions (missing native libraries, broken AOT trimming, wrong runtime identifier), startup banner regressions, real port-binding behaviour, real process-lifecycle (Ctrl-C handling).
* **Quantity:** small &mdash; perhaps half a dozen tests. This tier is for regressions integration tests are blind to, not for breadth.
* **Live in:** `tests/OpenWSFZ.E2E.Tests/`.
* **Speed budget:** whole E2E suite &lt; 15 s per OS in CI (including binary startup).

### 4.5 Performance tests

* **Scope:** the budgets in TECHNICAL_SPEC &sect;11 &mdash; decode latency, waterfall jitter, WS end-to-end latency, idle CPU, RSS, cold start.
* **Tool:** xUnit (one test per budget), backed by `System.Diagnostics.Stopwatch` and `Process.GetCurrentProcess().WorkingSet64`.
* **Where they run:** **Linux runner only**, in CI, in a dedicated `Performance` test category. Windows / macOS GitHub-runner variability makes performance assertions unreliable there.
* **Pass criterion:** the p95 over a small batch of measurements falls under the budget. Single-shot outliers are tolerated; the p95 is what's gated.
* **Live in:** `tests/OpenWSFZ.Web.Tests/Performance/` (alongside integration tests because they share the same harness).

### 4.6 Soak / long-running tests (nightly only)

* **Scope:** NFR-015 stability target &mdash; &geq; 8 hours of continuous capture with no crash and no unbounded memory growth.
* **What runs:** a single `[Trait("tier", "soak")]` test that boots the daemon, runs synthetic audio through it for 8 hours, samples RSS every 60 s, and asserts that the working-set growth slope across the last 6 hours is below a small threshold.
* **Where it runs:** **scheduled nightly GitHub Actions workflow** on Linux only. Not on every PR.
* **Failure handling:** a soak failure files a tracking issue but does **not** retroactively fail recent PRs &mdash; it gates the next release tag.

---

## 5. Test Data Strategy

### 5.1 WAV fixture corpus &mdash; the decoder ground truth

* **Storage:** `tests/OpenWSFZ.Decoding.Ft8.Tests/Fixtures/Wav/`.
* **Pairing:** every `name.wav` has a sibling `name.expected.json` listing the expected decodes:

  ```json
  {
    "source": "ft8_lib test corpus, file 14060_2017-08-09_000130.wav, MIT",
    "cycle_utc": "2017-08-09T00:01:30Z",
    "decodes": [
      { "audio_offset_hz": 1234, "time_offset_s": 0.2, "snr_db": -12, "text": "CQ K1JT FN42" },
      { "audio_offset_hz": 1850, "time_offset_s": 0.1, "snr_db": -18, "text": "K1JT Q1AW 73"  }
    ]
  }
  ```

* **Corpus provenance:** sourced from two **MIT-compatible** origins only:
  1. **`ft8_lib`'s own test corpus** (MIT-licensed alongside the library).
  2. **The WSJT-X reference recordings** that are explicitly distributed for testing under permissive terms by the K1JT group via QEX article supplements. Each entry's `source` field documents its origin.
* **Forbidden corpus sources:** any recording shipped under GPL terms, any recording obtained from a non-public source. The license-inventory CI gate verifies every fixture has a `source` entry pointing to an approved origin.
* **Size discipline:** keep the standard corpus under 50 MB total (commits to git directly). An extended corpus, used by the nightly tier only, may live in a sibling submodule or LFS once we have one identified.

### 5.2 Other fixtures

* **Config-file fixtures:** `tests/.../Fixtures/Config/{valid_minimal.toml, valid_full.toml, invalid_unknown_key.toml, invalid_bad_type.toml}`. Test `OpenWSFZ.Configuration` against each.
* **HTML / static-asset fixtures:** the real `/web` folder is the fixture for the strict UI visibility test (&sect;6.3).
* **Fake audio device list:** an `InMemoryAudioDeviceEnumerator` returns a configurable list to exercise the Settings page without touching PortAudio.

### 5.3 What is not used as test data

* No live USB audio device in CI or PR runs. Every device-shaped test uses `WavFileAudioSource` or `InMemoryAudioDeviceEnumerator`.
* No real network endpoints. Loopback `127.0.0.1:<ephemeral>` only.

---

## 6. Test Naming and Traceability

### 6.1 Naming convention

Every test method follows the form:

```
Public method name:  When_<context>_Should_<expected_observable>
Display name (xUnit `[Fact(DisplayName = ...)]`):
                     "FR-007: When the daemon starts it should emit the welcome banner on stdout"
```

The **display name MUST begin** with one or more requirement IDs (`FR-###` or `NFR-###`), comma-separated, followed by a colon and a human-readable description.

Examples:

* `"FR-001: When a fixture cycle is fed, the decoder should produce the expected messages"`
* `"FR-002, NFR-004: When the daemon is asked to bind to a non-loopback address, it should bind to 127.0.0.1 anyway"`
* `"NFR-003: When a single cycle is decoded, the run should complete in less than 1500 ms p95"`

### 6.2 The traceability gate (CI)

A small console tool, `tools/TraceabilityCheck`, runs in CI on Linux only and performs:

1. Parses every `FR-###` / `NFR-###` from `REQUIREMENTS.md`.
2. Reflects over every test assembly's discovered `Fact`/`Theory` display names.
3. Asserts that **every requirement ID has at least one display name beginning with that ID**.
4. Asserts that **every ID referenced in a display name actually exists in REQUIREMENTS.md** (catches typos and stale references).
5. Emits a `traceability.md` report listing requirement -> tests, included as a CI artifact.

A missing or stale ID **fails the build**. This implements rubric criterion **C1**.

### 6.3 The strict UI visibility gate (FR-016)

An integration test parses `/web/index.html` and `/web/settings.html`, enumerates every interactive control (`<button>`, `<input>`, `<form>`, `<a href>` with `data-action`), and asserts that each one resolves to:

* a wired HTTP endpoint that returns 2xx for a sensible probe; or
* a wired WebSocket message-type the server handles; or
* a documented client-only behaviour annotated with `data-client-only`.

Any unbound control fails the build. This implements FR-016 directly.

---

## 7. CI Gates &mdash; What Blocks a Merge to `main`

`main` is protected. A pull request must satisfy **all** of the following before merge:

| # | Gate | Where it runs |
|---|---|---|
| G1 | All unit, decoder-fixture, integration, and E2E tests pass | Matrix: Windows + Linux + macOS |
| G2 | Performance suite passes | Linux only |
| G3 | Traceability check passes (&sect;6.2) | Linux only |
| G4 | Strict UI visibility check passes (&sect;6.3) | Linux only |
| G5 | License-inventory check passes (TECHNICAL_SPEC &sect;9.4) | Linux only |
| G6 | Decoder-correctness gate: real-signal fixture integration test passes (FR-029 / NFR-016) | Matrix: Windows + Linux + macOS (runs inside G1 `dotnet test`) |
| G7 | At least one human review approval | GitHub PR settings |

G6 is structurally active from the moment the real-signal fixture integration test is committed to `tests/OpenWSFZ.Ft8.Tests/`. It runs inside the existing G1 `dotnet test` step — no separate CI step is required. See `RECOVERY_PLAN.md` and `p10-decoder-ground-truth` for context.

The **soak** tier (&sect;4.6) does **not** block PRs. It gates the next release tag (&sect;10.2).

### 7.1 Why some gates are Linux-only

Performance and traceability gates do not benefit from being run on three OSes; they would just triple their cost and risk OS-specific noise. The matrix value comes from G1, which exercises the actual production code paths on each OS.

---

## 8. Workflow &mdash; How Tests Integrate with Development

### 8.1 Test-first discipline for new behaviour

When a DEVELOPER picks up an OpenSpec change:

1. Identify the requirement IDs the change touches (from the proposal).
2. Write or extend tests with display names that reference those IDs.
3. Run the suite; the new tests should fail.
4. Implement the change.
5. Run the suite; everything should be green.
6. Open the PR.

The QA role reviews **the tests first**, then the implementation.

### 8.2 When a test fails locally

* **Do not skip.** Skipping is a code smell that the QA review will catch.
* **Do not increase a tolerance to make it pass.** Investigate; if the tolerance genuinely needs widening, that's a separate change with its own justification documented in the test.
* **Do not retry.** A flaky test is filed as a bug under tier `flake`, not "rerun until green" (&sect;11).

### 8.3 When a requirement changes (REQUIREMENTS.md updates)

1. The ANALYST updates `REQUIREMENTS.md` and bumps its revision.
2. The traceability check now lists changed / removed IDs.
3. The QA role identifies which tests are affected (the report points at them).
4. Tests are updated alongside the requirement change in the same PR / OpenSpec change.

### 8.4 Decoder defect process rule (NFR-016)

This rule is mandatory. It exists because 18 consecutive speculative fixes failed to produce
a single real decode, and the failure mode was a validation gap — not a DSP gap. See
`RECOVERY_PLAN.md` for full context.

**Rule:** A decoder defect "root cause" claim is not accepted until a **failing reproducible
test over a committed real-signal WAV fixture** exists that demonstrates the defect.

Concretely:

1. **Before proposing a fix:** add a test to `tests/OpenWSFZ.Ft8.Tests/` (or the replay
   harness) that decodes a committed WAV fixture and fails because of the defect. The test
   must cite the defect's associated requirement ID in its display name.
2. **The fix is validated by making that test green.** If the fix does not make the failing
   test pass, it does not fix the defect.
3. **Live smoke tests are confirmation only.** A positive live smoke test (real signals
   appearing in `ALL.TXT`) confirms the fix works end-to-end; it does **not** substitute
   for a reproducible CI test.
4. **A failing live smoke test is a bug report, not a root cause.** Translate it into a
   reproducible failing test first, then diagnose.

The G6 CI gate (§7, gate 6) enforces this rule structurally: a change that regresses
real-signal recovery fails CI and cannot merge.

---

## 9. Tools and Frameworks

| Tool | Role | Licence |
|---|---|---|
| xUnit | Test runner & assertions | Apache-2.0 |
| FluentAssertions | Assertion ergonomics | Apache-2.0 (v6.x line, before licence change) |
| Coverlet | Coverage collection | MIT |
| ReportGenerator | Coverage report formatting | Apache-2.0 |
| Microsoft.AspNetCore.Mvc.Testing | Integration host (WebApplicationFactory) | MIT |
| `tools/TraceabilityCheck` | First-party, this repo | MIT (project licence) |
| `tools/LicenseInventoryCheck` | First-party, this repo | MIT |

> **FluentAssertions note:** the 7.x release re-licensed away from Apache-2.0. We pin **the last permissive 6.x release** in `Directory.Packages.props`. The license-inventory gate enforces this pin.

### 9.1 Coverage tooling (informational)

Coverlet runs on every CI build. ReportGenerator emits an HTML report uploaded as a build artifact. We **do not** gate on a coverage percentage, but we surface the report so dramatic drops are visible at PR-review time.

---

## 10. Test Suite Composition per Subsystem

A snapshot of what each test project owns, so the DEVELOPER knows where to add a new test.

| Test project | Covers | Notable test types |
|---|---|---|
| `OpenWSFZ.Daemon.Tests` | Composition root wiring, CLI parsing, banner emission, lifecycle | Unit + small in-process integration |
| `OpenWSFZ.Configuration.Tests` | TOML schema, load / save, default bootstrap, validation errors | Unit |
| `OpenWSFZ.Audio.Tests` | `IAudioSource` contract, `WavFileAudioSource`, device-enumerator behaviours | Unit |
| `OpenWSFZ.Decoding.Ft8.Tests` | The FT8 decoder against the WAV-fixture corpus | Decoder fixture (the linchpin) |
| `OpenWSFZ.Web.Tests` | HTTP endpoints, WS hub, status push, config round-trip, loopback pin, UI visibility gate, performance suite | Integration + performance |
| `OpenWSFZ.E2E.Tests` | The published binary as a subprocess on each OS | End-to-end |

### 10.1 Special tests that have an opinion across subsystems

* **`UiVisibilityTests`** (in `OpenWSFZ.Web.Tests`) &mdash; FR-016 enforcement.
* **`TraceabilityRoundTripTest`** (in `OpenWSFZ.Daemon.Tests`) &mdash; sanity check that the `TraceabilityCheck` tool finds the same set of IDs the runtime would log; protects against silent drift if requirement IDs change format.
* **`LicenceManifestTests`** (in `OpenWSFZ.Daemon.Tests`) &mdash; verifies every dependency in the published output has a manifest entry with a permitted licence.

### 10.2 Release gate (in addition to PR gates)

Before a release tag is cut, **all PR gates** plus:

| # | Gate |
|---|---|
| R1 | Most recent nightly soak run is green |
| R2 | Decoder-fixture extended corpus run is green |
| R3 | A confirmed two-way FT8 QSO completed by the Product Owner on their own station using OpenWSFZ (RX + CAT + TX), confirmed by the operator and documented in the release notes. |

The release tag triggers `release.yml` (TECHNICAL_SPEC &sect;9) to publish AOT binaries per OS.

---

## 11. Flaky Test Policy

**A flaky test is a bug.** It is *never* an acceptable steady state.

1. The first flake on any test files an issue tagged `flake` and assigned at the next planning step.
2. The test is **not** muted, skipped, or wrapped in retry. Muting hides the bug; retry hides the bug while wasting CI minutes.
3. A repeat flake on the same test before the issue is fixed escalates to **blocker** &mdash; no merges to `main` until the test is fixed or removed (the latter requires QA + Product-Owner sign-off).
4. The root cause is documented in the closing commit so the pattern doesn't recur.

Common flake causes we will pre-empt:

* **Time:** all time-dependent code uses `IClock`, never `DateTime.Now` directly. Tests inject a deterministic clock.
* **Threading:** no `Thread.Sleep` in tests. Wait on `TaskCompletionSource` or `Channel<T>` events with a generous timeout that fails loudly.
* **Ports:** integration / E2E tests bind to `127.0.0.1:0` (ephemeral) and read the actual port back; never hard-coded.
* **File system:** every test that touches disk uses `Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString())` and cleans up on `IAsyncLifetime.DisposeAsync`.

---

## 12. The QA Role &mdash; What It Owns

(Sketched here; the formal QA role prompt will live at `prompts/QA.md` as a separate artefact.)

| Owns | Does not own |
|---|---|
| Reviewing tests on every PR before reviewing implementation | Writing implementation code |
| Enforcing the rubric criteria (&sect;3) | Choosing language, framework, or architecture |
| Maintaining the traceability and license-inventory gates | Maintaining production code |
| Triaging flakes (&sect;11) | Operational on-call (there is none for v1) |
| Curating the WAV fixture corpus | Sourcing fixtures from non-approved origins |
| Authoring `prompts/QA.md` content as the workflow matures | Modifying `REQUIREMENTS.md` (that is the ANALYST's) |

QA is invoked **whenever a PR is opened**. The QA review is a gate, not a recommendation.

---

## 13. Out of Scope for v1

These are explicitly **not** in v1's testing scope; they are recorded so they don't get re-litigated mid-build.

* **Mutation testing.** Stryker.NET (Apache-2.0) is the obvious tool when we add it; v2 ambition. Until then, rubric criterion **C3** is enforced by code review.
* **Fuzz testing of HTTP / WS surfaces.** SharpFuzz is available; deferred to when the auth surface gains complexity in v2.
* **Property-based testing.** FsCheck / CsCheck would benefit the DSP edges; v2 nice-to-have.
* **UI screenshot / pixel-diff testing.** The frontend is intentionally simple; visual regression tooling adds more flake than value at v1.
* **Load testing.** v1 is loopback only; there is no concurrency story to load-test. Returns when LAN/auth arrives in v2.
* **Real-radio integration testing.** Cannot run in CI. Stays a manual release-gate step (R3).

---

## 14. Summary

* The build is gated by **requirement traceability** (every FR-### / NFR-### appears in a test name), **not** by line-coverage percentage.
* Six test tiers: unit, decoder-fixture, integration, end-to-end, performance, soak.
* The decoder-fixture tier is the correctness linchpin and the clean-room MIT evidence.
* A flaky test is a bug; never a steady state.
* The QA role enforces the rubric at PR review.
* The soak and extended-corpus tiers run nightly and gate releases, not PRs.

---

**End of TESTING_STRATEGY.md v1.0 (draft).**
