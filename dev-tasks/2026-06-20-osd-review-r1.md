# Developer Handoff — OSD Review Round 1 (fix/d001-osd-fallback)

**Date:** 2026-06-20
**QA Engineer:** OpenWSFZ QA
**Status:** Returned for changes — do NOT merge to `main`

---

## 1. Context

QA review of the OSD fallback implementation (shim 20260025) on branch
`fix/d001-osd-fallback` (commit `d70aad5`) has identified three blocking items.

The implementation itself is algorithmically correct and the code quality is high.
The blocks are: (a) the R&R acceptance-criteria diagnostics specified in the original
handoff (`dev-tasks/2026-06-20-osd-implementation.md`) were not run; (b) the decode
timing budget was not verified; (c) there is no integration test that proves OSD
actually recovers a message in a scenario where BP fails.

---

## 2. Branch Name

```
fix/d001-osd-fallback
```

Continue on this branch. Do **not** create a new branch and do **not** commit to `main`.

---

## 3. Actions

### Action 1 — Run S7 P16 K=10 diagnostic (AC2 from original handoff)

```
cd qa\rr-study
python harness/run_scenario.py scenarios/s7-compounding.json --parts 16
```

Then run the matcher:

```
python harness/matcher.py --run-dir results/<sha> \
    --wsjt results/<sha>/wsjt-all.txt \
    --owsfz results/<sha>/owsfz-all.txt
```

Pass criterion: **MSG-01 rate ≥ 80%** (vs 60% at shim 20260024; WSJT-X is 100%).

If the result is 60–79%, investigate whether passing the BP iteration-2 LLR snapshot
to OSD (rather than the pre-BP snapshot) improves the rate. If ≥ 80%, proceed to
Action 2.

Produce a compliant `report.md` in the result directory per NFR-023 (all five sections;
Sections 1, 2, 5 to be completed by hand). The QA engineer will author Sections 1 and 5
after you commit the result directory with the harness-generated Sections 3 and 4 present.

### Action 2 — Run full S7 R2 regression (AC4 from original handoff)

If Action 1 passes, run the full S7 scenario:

```
python harness/run_scenario.py scenarios/s7-compounding.json
```

Pass criterion: no per-part regression vs shim 20260021 baseline; S7 overall within the
H4 variability band (43–57%) or higher.

Commit the result directory alongside a skeleton `report.md` (Sections 3 and 4
harness-generated; Sections 1, 2, 5 left for QA to complete).

### Action 3 — Measure decode cycle latency (AC6 from original handoff)

Confirm that a full decode cycle under shim 20260025 completes in < 500 ms on the
development machine. OSD adds Gaussian elimination + 529 CRC trials for every candidate
that BP fails on; under the S7 P16 co-channel scenario this will fire frequently.

Acceptable measurement: enable `Logging.FileEnabled = true` and inspect the elapsed-time
log lines for one decode cycle during an S7 P16 run, or instrument the shim temporarily.
Note the measured latency in the `report.md` Section 2 produced in Action 1.

### Action 4 — Add an integration test for the OSD success path (new requirement)

The current test suite has no test that would fail if `osd_decode` were replaced with
`return 0`. That is not acceptable coverage for the primary change on this branch.

Add a new test class `D001OsdDecodeTests.cs` in `tests/OpenWSFZ.Ft8.Tests/` containing
at minimum one `[Fact]` that:

1. Builds a **Δ7 Hz co-channel fixture**: Signal A at 1500 Hz encoding
   `"Q1OFZ Q9XYZ JO33"`, Signal B at 1507 Hz encoding `"Q9XYZ Q1OFZ RR73"`, equal
   amplitude (0.35 each), no noise, 180 000 samples at 12 kHz — same geometry as
   `run_h6_probe.py`.

2. Calls `decoder.DecodeAsync(pcm, CancellationToken.None)` with **no AP constraints**
   (blind decode).

3. Asserts that at least one of `Q1OFZ` or `Q9XYZ` appears in the decoded results.

This test will:
- Pass with OSD active (OSD closes the Δ7 Hz gap for the dominant signal).
- Fail without OSD (blind BP rate at Δ7 Hz is ~40%, so the fixture will not reliably
  decode without OSD; the assertion on a specific callsign provides a deterministic
  gate).

Use the `BuildCoChannelFixture` pattern from `D001H6ApDecodeTests.cs` as a reference.
The only difference from that fixture is the 7 Hz offset on Signal B.

Confirm all 470 + 1 tests pass before resubmitting.

---

## 4. Acceptance Criteria

The QA engineer will verify the following before approving the merge:

| # | Criterion |
|---|---|
| AC1 | `dotnet test OpenWSFZ.slnx -c Release` — all tests green (≥ 471 with the new OSD test) |
| AC2 | S7 P16 K=10 diagnostic: OpenWSFZ MSG-01 rate ≥ 80%; WSJT-X remains 100% |
| AC3 | No regression in S7 P0 (co_channel Δ7 Hz original part) vs shim 20260024 baseline |
| AC4 | Full S7 R2 regression passes (no per-part regression; overall within 43–57% band or higher) |
| AC5 | Shim version check passes at application startup (already satisfied; must remain satisfied) |
| AC6 | Decode elapsed time per cycle < 500 ms |
| AC7 | New `D001OsdDecodeTests` integration test is present and passes (OSD success path covered) |

---

## 5. References

- Original handoff: `dev-tasks/2026-06-20-osd-implementation.md` (on `diag/d001-ldpc-iter-hypothesis`, commit `836b100`)
- D-001 defect: GitHub issue #3
- H_ITER diagnostic: `qa/rr-study/results/2026-06-19-62f7a86/report.md`
- H_ITER2 + WSJT-X source findings: `qa/rr-study/results/2026-06-19-b43b600/report.md`
- H6 AP decode probe: `qa/rr-study/results/2026-06-20-266aeea/` (20/20 at Δ7 Hz with AP armed)
- NFR-023: R&R report structure (5 mandatory sections)
- HK-000: QA engineer handoff procedure
