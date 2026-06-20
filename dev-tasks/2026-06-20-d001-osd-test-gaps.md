# Developer Handoff — D-001 OSD Test Coverage Gaps

**Date:** 2026-06-20
**QA Engineer:** OpenWSFZ QA
**Status:** Ready for implementation

---

## 1. Context

Post-merge review of `fix/d001-osd-fallback` (shim 20260025, merged `1809ce7`) identified
two test coverage gaps that should have been caught during the QA review. Both are in
`tests/OpenWSFZ.Ft8.Tests/`.

**Gap A — `BlindDecode_WithoutApBits_FailsOnCoChannel` has stale semantics**

This test in `D001H6ApDecodeTests.cs` was written for shim 20260021 (before OSD). Its
intended meaning was: *"blind decode of a Δ0 Hz co-channel fixture produces no results
because BP deterministically fails."* With OSD active (shim 20260025), BP still fails at
Δ0 Hz (LLRs are genuinely near-zero — equal energy from two interferers at the same
frequency), but OSD now runs 529 CRC trials per candidate before giving up. The test still
passes because OSD's random search cannot reliably reconstruct Q1OFZ or Q9XYZ from
coin-flip hard decisions; however:

1. The XML doc comment still says "BP consistently fails" — this was true for shim
   20260021 but is now an incomplete explanation.
2. The assertion is `NotContain(Q1OFZ or Q9XYZ)` but it does not assert that `results`
   is empty. OSD might produce spurious CRC-passing codewords that encode neither callsign;
   these would silently pass the test while being false positives from the decoder. The
   current assertion does not catch this.

**Gap B — OSD in `ftx_decode_candidate_ap` is not covered by any test**

`osd_decode` was wired into both `ftx_decode_candidate` (the blind path) and
`ftx_decode_candidate_ap` (the AP-constrained path used by H6). The blind path is tested
by `D001OsdDecodeTests`. The AP path's OSD fallback — where AP constraints are provided,
BP still fails, and OSD recovers the message — is not tested.

Engineering a *deterministic* integration test for this path is not straightforward: with
±40.0 hard constraints on 56 bits, BP reliably converges, so OSD never fires in the
standard H6 use case. Nonetheless, the omission should be acknowledged and documented.

---

## 2. Branch Name

```
chore/d001-osd-test-gaps
```

Do **not** commit directly to `main`.

---

## 3. Actions

### Action 1 — Fix Gap A: update `BlindDecode_WithoutApBits_FailsOnCoChannel`

In `tests/OpenWSFZ.Ft8.Tests/D001H6ApDecodeTests.cs`:

**3a — Update the XML doc on `BlindDecode_WithoutApBits_FailsOnCoChannel`:**

Replace the existing summary/remarks that describe the test as relying on deterministic BP
failure. The updated doc must explain:

- At Δ0 Hz, the two signals produce near-zero LLRs across all 174 bits (equal energy at
  competing tones). BP fails for this reason.
- With OSD active (shim 20260025+), OSD runs 529 CRC trials per candidate using coin-flip
  hard decisions. The probability of OSD accidentally reconstructing a CRC-valid codeword
  that encodes Q1OFZ or Q9XYZ is negligible (≈ 1/2^63 per trial), so the `NotContain`
  assertion remains valid. The test is not flaky.
- OSD *may* produce occasional spurious decoded messages that encode neither callsign (CRC
  hit on a random-looking message). These are not caught by the current assertion; see 3b.

**3b — Strengthen the assertion:**

The current assertion:
```csharp
results.Should().NotContain(
    r => r.Message.Contains(Mycall, ...) ||
         r.Message.Contains(Hiscall, ...), ...);
```

Replace with **two** assertions:

```csharp
// Primary gate: no target callsign may be decoded blind.
results.Should().NotContain(
    r => r.Message.Contains(Mycall, StringComparison.OrdinalIgnoreCase) ||
         r.Message.Contains(Hiscall, StringComparison.OrdinalIgnoreCase),
    because: "blind decode of a Δ0 Hz co-channel fixture must not recover " +
             "the target callsign pair — coin-flip LLRs make OSD's chances of " +
             "hitting Q1OFZ or Q9XYZ negligible (≈1/2^63 per trial)");

// Secondary gate: the result set must be empty.
// At Δ0 Hz, OSD is exploring random bit patterns; any non-empty result would
// indicate a spurious CRC false-positive from the decoder. A genuine false
// positive at this fixture would be a product defect worth investigating.
results.Should().BeEmpty(
    because: "blind decode of a Δ0 Hz co-channel fixture should produce zero " +
             "decoded messages — near-zero LLRs should cause both BP and OSD " +
             "to fail for every candidate");
```

**Note for the developer:** If `BeEmpty()` turns out to be flaky (i.e., OSD occasionally
produces a spurious decode at Δ0 Hz in CI), report this to QA before weakening it back to
`NotContain`. A spurious decoded message from near-zero LLRs is a real concern worth
measuring.

---

### Action 2 — Address Gap B: document the AP+OSD coverage limitation

**3c — Add an XML doc `<remarks>` to the `D001H6ApDecodeTests` class:**

After the closing `</para>` of the existing class-level `<summary>`, add a `<remarks>`
block:

```xml
/// <remarks>
/// <para>
/// <b>Coverage limitation (shim 20260025):</b>
/// <c>osd_decode</c> was also wired into <c>ftx_decode_candidate_ap</c> in
/// shim 20260025.  The combined AP+OSD path — where AP constraints are provided,
/// BP still fails despite them, and OSD recovers the message — is not exercised
/// by any test in this class.
/// </para>
/// <para>
/// Engineering a deterministic fixture for this path is not currently feasible:
/// with ±40.0 hard constraints on 56 bits (the H6 standard constraint strength),
/// BP reliably converges and OSD never fires.  A scenario where AP constraints are
/// provided but insufficient for BP convergence would require either a weaker
/// constraint strength (not supported by the current C# API) or a more destructive
/// interference geometry (e.g., 3-stack equal-SNR, which defeats both BP and OSD).
/// </para>
/// <para>
/// Risk assessment: LOW.  <c>osd_decode</c> is validated by
/// <c>D001OsdDecodeTests</c>.  The OSD wiring in <c>ftx_decode_candidate_ap</c>
/// is an exact structural copy of the wiring in <c>ftx_decode_candidate</c>; any
/// defect in the copy would be a trivially detectable compile or logic error.
/// This gap is recorded in <c>traceability-debt.md</c>.
/// </para>
/// </remarks>
```

**3d — Add a traceability-debt entry for the AP+OSD gap:**

Append to `traceability-debt.md` under a new section at the bottom:

```
## Pending — D-001 OSD test coverage gaps (fix/d001-osd-fallback)

# AP+OSD combined path: ftx_decode_candidate_ap with OSD fallback is not covered
# by an integration test. Rationale and risk assessment in D001H6ApDecodeTests.cs
# class-level <remarks>. Not a requirement ID; tracked here for completeness.
# Remove when a deterministic fixture for the AP+OSD combined path is engineered
# (requires either a weaker SetApConstraints API or a new fixture geometry).
D001-AP-OSD-GAP
```

---

## 4. Acceptance Criteria

| # | Criterion |
|---|---|
| AC1 | `dotnet test OpenWSFZ.slnx -c Release` — all tests green (471 total; no new tests required, Gap B is documented not tested) |
| AC2 | `BlindDecode_WithoutApBits_FailsOnCoChannel` carries an updated XML doc explaining OSD semantics under shim 20260025 |
| AC3 | The same test asserts `results.Should().BeEmpty()` in addition to the existing `NotContain` assertion |
| AC4 | `D001H6ApDecodeTests` class doc carries a `<remarks>` block documenting the AP+OSD coverage gap and risk assessment |
| AC5 | `traceability-debt.md` carries a `D001-AP-OSD-GAP` entry under a new section |
| AC6 | No production code changes — this branch touches only test files and `traceability-debt.md` |

---

## 5. References

- `fix/d001-osd-fallback` — merged to `main` at `1809ce7` (shim 20260025)
- `tests/OpenWSFZ.Ft8.Tests/D001H6ApDecodeTests.cs` — file to be modified
- `tests/OpenWSFZ.Ft8.Tests/D001OsdDecodeTests.cs` — reference for the blind OSD test
- `native/ft8_lib_build/patched/ft8/decode.c` — `ftx_decode_candidate_ap` lines 716–783
- `traceability-debt.md` — file to be extended
- QA review miss: `dev-tasks/2026-06-20-osd-review-r1.md` AC7 specified "OSD success path
  covered" but scoped only the blind decode path; the AP path was not mentioned.
