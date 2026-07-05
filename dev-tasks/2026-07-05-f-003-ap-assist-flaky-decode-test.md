# DEV TASK — f-003-ap-assist-nonstandard-callsigns: flaky end-to-end AP-decode test blocks merge

**Date:** 2026-07-05
**QA defect ID:** N/A — pre-merge code review finding on an unmerged branch, not a shipped defect
**Severity:** Blocking for merge — the test's own stated purpose (task 5.1: "proof that
AP-assisted decode succeeds") is not met by a test that only passes about half the time
**OpenSpec change:** `f-003-ap-assist-nonstandard-callsigns` (all 16 tasks marked complete;
this is the one gap found in QA's pre-merge review)
**Branch:** `feat/f-003-ap-assist-nonstandard-callsigns` (existing branch, no new branch needed)

---

## 1. Context

QA reviewed the full diff (`Ft8CallsignPacker.cs`'s `ihashcall` port and extended `Pack28`,
the `QsoCallerService`/`QsoAnswererService` wiring, and all new tests) and independently
re-derived the `ihashcall` formula from scratch to confirm the hash arithmetic — everything
there checks out exactly, including the 64-bit-wraparound-is-exact claim in the doc comment.
No issues with the packer, the special-token encoding, or the regression coverage for the
unchanged standard-basecall path.

**The one problem:** `tests/OpenWSFZ.Ft8.Tests/F003ApAssistNonstandardCallsignDecodeTests.cs`,
`ApDecode_NonstandardCallsignCoChannel_RecoversResolvedPlaintext` (task 5.1's real-native-decoder
end-to-end proof), is flaky. QA ran `dotnet test tests/OpenWSFZ.Ft8.Tests/` six times
back-to-back with no code changes in between:

| Run | Result |
|---|---|
| 1 | Pass |
| 2 | Pass |
| 3 | Pass |
| 4 | **Fail** |
| 5 | **Fail** |
| 6 | Pass |

The failure is always the same assertion — the co-channel decode result does not contain
the resolved nonstandard-callsign plaintext alongside `Mycall`. Yet the identical test passes
reliably every time when run alone or alongside only its three sibling native-decoder classes
(`HashedCallsignResolutionTests`, `D001H6ApDecodeTests`) — 2/2 clean runs of that 8-test subset.
Something about running under the full 266-test suite specifically tips it over.

**What QA ruled out:** the process-global `g_session_hash_table` (native shim, 256-slot
capacity, never reset for the process's lifetime — see `ft8_shim.c` D1/D3 comments). Only
7 call sites in the entire test assembly ever populate it (`grep -rn PackType4CqAnnounce
tests/OpenWSFZ.Ft8.Tests/*.cs`), nowhere near exhaustion, so table-capacity rejection is not
the mechanism.

**QA's working theory, not confirmed:** the test's own fixture is deliberately adversarial —
`BuildCoChannelFixture()` superimposes two equal-amplitude (0.35) signals on the same audio
tone, explicitly relying on AP to disambiguate ("blind decode of the composite is ambiguous;
AP anchors signal A" per the file's own doc comment). That's the right technique to prove AP
is doing real disambiguation work, but it sits right at a decode margin. Margins are exactly
where CPU scheduling/timing variance under full-suite load (contention from hundreds of other
tests' threads, GC pauses, JIT warm-up state) could plausibly flip a marginal LDPC/candidate-
search result. This is a hypothesis, not a confirmed root cause — please verify or find the
actual mechanism rather than assuming QA's theory is correct.

---

## 2. Actions

### 2.1 — Reproduce and diagnose

Run the full `OpenWSFZ.Ft8.Tests` suite repeatedly (QA needed ~6 runs to see 2 failures) to
confirm the flake reproduces in your environment too, then instrument
`F003ApAssistNonstandardCallsignDecodeTests` (or the native shim's diagnostic counters —
`g_hash_table_reject_count` is already there for a related purpose, see `ft8_shim.c` line 552)
to capture, on failure: whether cycle 1's Type 4 announcement was actually decoded and its
hash actually added to `g_session_hash_table` (rule out the ruled-out theory being wrong), and
what the raw decode result for cycle 2 actually was (empty result set? wrong candidate?
unresolved `<hash>` placeholder instead of plaintext?) — the failure mode determines the fix.

### 2.2 — Stabilize the test

Once the mechanism is understood, fix it at the root rather than papering over it with a
retry loop. Candidates, depending on what 2.1 finds:

- If it's genuinely a decode-margin timing sensitivity: widen the margin (e.g. slightly
  unequal signal amplitudes, or a cleaner separating condition) so AP is still doing
  real disambiguation work but the test isn't balanced on a knife-edge.
- If it's a real concurrency/ordering bug in the native decode path exposed by test-suite
  scheduling: that's a more serious finding and should be raised as its own defect against
  the native shim, not silently worked around in this test.
- A bare retry-and-hope is not an acceptable fix — if you're tempted to reach for one, stop
  and bring it back to QA/the Captain first.

Confirm the fix by running the full suite enough times to be confident (QA's bar: 10
consecutive clean full-suite runs before sign-off).

### 2.3 — Minor: fix a misleading test comment

In both `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs` and
`QsoCallerServiceTests.cs`, the new f-003 tests contain the comment:

```csharp
// Expected packed bytes, independently derived (not via the packer under test).
byte[] expectedMycallBits  = Ft8CallsignPacker.Pack28(OurCallsign);
byte[] expectedHiscallBits = Ft8CallsignPacker.Pack28(nonstandardPartner);
```

This calls `Ft8CallsignPacker.Pack28` — the very function under test — so "independently
derived" is inaccurate. It's not a functional defect (these are integration tests checking
that the service arms AP with whatever the packer produces rather than disabling it; packer
correctness itself is already covered independently in `Ft8CallsignPackerTests.cs`), but the
comment overstates what's being verified here and should be reworded to say what it actually
does (confirms the service passes the packer's own output through unmodified) — or drop the
"independently derived" claim entirely.

---

## 3. Acceptance criteria

The QA engineer will verify the following before approving merge:

- [ ] **AC-1** `F003ApAssistNonstandardCallsignDecodeTests` passes reliably — 10 consecutive
  full-suite (`dotnet test tests/OpenWSFZ.Ft8.Tests/`) runs with zero failures of this test.
- [ ] **AC-2** The root cause of the original flake is documented (in the test file's own
  remarks, or in this dev-task's notes section) — not just "it seems to pass now."
- [ ] **AC-3** If the root cause turns out to be a genuine native-decoder concurrency/ordering
  bug rather than a test-fixture margin issue, it is filed as its own defect (not silently
  absorbed into this change) and flagged to QA/the Captain before merge.
- [ ] **AC-4** The misleading "independently derived" comment (Action 2.3) is corrected in
  both test files.
- [ ] **AC-5** Full regression: `dotnet test` across `OpenWSFZ.Ft8.Tests` and
  `OpenWSFZ.Daemon.Tests` — 0 failures (both already pass reliably today; just confirming
  no new regression from whatever fix lands for AC-1).
- [ ] **AC-6** `openspec validate f-003-ap-assist-nonstandard-callsigns --strict` still passes
  (it does today; re-check after any tasks.md edits).

---

## 4. References

- `tests/OpenWSFZ.Ft8.Tests/F003ApAssistNonstandardCallsignDecodeTests.cs` — the flaky test
  (task 5.1)
- `tests/OpenWSFZ.Ft8.Tests/D001H6ApDecodeTests.cs` — source of the co-channel fixture
  technique this test mirrors
- `tests/OpenWSFZ.Ft8.Tests/HashedCallsignResolutionTests.cs` — source of the Type 4
  announce-cycle technique this test mirrors; also documents why assembly-wide test
  parallelization is disabled (`AssemblyInfo.cs`,
  `[assembly: CollectionBehavior(DisableTestParallelization = true)]`)
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` lines 517–593 — `g_session_hash_table` (process-global,
  256-slot, never reset), ruled out as the flake's cause but worth re-checking if 2.1's
  instrumentation says otherwise
- `tests/OpenWSFZ.Daemon.Tests/QsoAnswererServiceTests.cs`,
  `tests/OpenWSFZ.Daemon.Tests/QsoCallerServiceTests.cs` — the misleading-comment nit
  (Action 2.3)
- Everything else in the change (the `Ft8CallsignPacker.cs` packer/hash extension itself,
  the `QsoCallerService`/`QsoAnswererService` wiring, and all other new tests) was reviewed
  line-by-line and independently verified by QA — no further action needed there.
