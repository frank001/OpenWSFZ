# Developer handoff: fix `FR-064` — `ExternalReportingServiceTests.Follower_AbsoluteExclusion_AppliesBeforeRelay` flake (the §11.3 `main`-merge blocker)

**Authored by:** QA, 2026-09-01 (16:28 UTC, `date -u`, HK-017), per HK-000/HK-015.
**Follows:** `qa/2026-09-01-1617-architect-to-qa-brief-fr064-heartbeat-race-fix.md` (Architect, `fe4e20d`
on this branch) — that brief re-verified and **corrected** the 2026-08-14 diagnosis in two places;
this document is the Developer-facing transcription of it, not a re-derivation.
**Status:** 🔴 **Proposal, not approved work in itself (HK-011).** A separate Developer session makes
the edit. The Captain reviews the diff and rules on the merge (HK-010) — QA does not declare
readiness. No push, no merge, no `pre_merge_check.py` from this document (HK-006/HK-014).
**Branch:** `fix/fr064-heartbeat-race`, off `main` @ `75ea2c1`, per PO ruling R1. This branch gates
`main` on its own account — do not let it wait behind, or ride along with, any feature branch, and
verify (`git diff main --stat`) that its file set stays disjoint from any other in-flight diff before
merging anything.

**QA independently re-read every cited line against this branch's current tree before writing this
document (HK-018/HK-022 — not taken on the brief's word) and all of them check out exactly as
quoted below**, including one point the brief itself left open (§2, `"Status"` literal).

---

## 0. Why this blocks everything

`TESTING_STRATEGY.md` §11.3: a repeat flake on the same test before it's fixed is a **blocker — no
merges to `main`** until fixed or removed (removal needs QA + PO sign-off, which this does not have
and is not being requested). This test has flaked twice — 2026-08-14 CI (`windows-latest`, run
`31820509725`) and 2026-08-30 local full-suite (620/621) — and a root cause was written up on
2026-08-14 but never applied. Two PRs have merged since on clean CI draws; that's luck, not a fix.
Downstream and waiting on this: the `SUP-B` step-7 Option A build (PO-decided 2026-09-01) and any
other `main` merge.

## 1. The test and what it's racing

`tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs`,
`Follower_AbsoluteExclusion_AppliesBeforeRelay` (confirmed at lines 1395–1439 on this tree).

Two independent facts about `src/OpenWSFZ.Daemon/ExternalReportingService.cs`, both confirmed by
re-read, not inherited:

- `_lastHeartbeatSentUtc` defaults to `DateTimeOffset.MinValue` and is never seeded before
  `StartAsync` (`:143`).
- `TimerLoopAsync`'s body runs **immediately** on the loop's first iteration — the
  `Task.Delay(_statusPollInterval)` sits at the *end* of the loop (`:610`), so the Heartbeat branch
  fires unconditionally on tick 1 (`:577`–`:584`), whatever `heartbeatInterval` is configured to.
- The SUT in this test is a **follower** (`role: "follower"`, line ~1402). A follower's Heartbeat
  routes through `DispatchOrRelayAsync` (`:823`) → `RelayToLeaderAsync` → the HTTP handler the test
  asserts against (`:838` onward) — confirmed by reading the role gate, not assumed from the test
  name.

⇒ An independent background task (the startup Heartbeat) posts one unaccounted-for request into
`handler.Requests`. The test's absolute-exclusion logic is never actually exercised by that request
— **this is not an exclusion regression**, it's a baseline race.

## 2. 🔴 Why "drain the Heartbeat first" is NOT the fix (correction to the 2026-08-14 write-up)

The test's baseline is captured after polling for `handler.Requests.Count >= 1` (line 1419). **Two**
independent emissions can each satisfy that predicate on their own:

- `P_hb` — the startup Heartbeat (unconditional, §1)
- `P_st` — the Status POST produced by the first (empty) `DecodeBatch`, built in `DecodeLoopAsync`
  and added to the follower's grouped batch as `("Status", ...)` at **`:510`** — literal confirmed
  by QA re-read, resolving the one thing the brief itself flagged as unverified. The wire JSON key is
  `"type"` (lower-case) per `RelayDatagramDto`'s own doc comment,
  `src/OpenWSFZ.Web/AppJsonContext.cs:401` (`{"type":"Decode","bytesBase64":"..."}`), and the
  existing sibling assertion at test line 1365 (`r.Body.Contains("\"type\":\"Decode\"")`) already
  proves that convention works against a live response body.

| Ordering when `countAfterFirstBatch` is read | Baseline | Lands in the 300 ms window | Result |
|---|---|---|---|
| `P_st` only | 1 | `P_hb` | `2 != 1` → **FAIL** |
| `P_hb` only | 1 | `P_st` | `2 != 1` → **FAIL** |
| `P_st` then `P_hb`, both before the read | 2 | — | PASS |
| `P_hb` then `P_st`, both before the read | 2 | — | PASS |

The test fails whenever **exactly one** of the two startup emissions has landed at baseline-capture
time — it doesn't matter which. `P_st` doesn't exist until the first batch is written, so "drain the
Heartbeat before writing the batch" reproduces the bug with new words. **The baseline must be
captured only once BOTH known startup emissions have been observed.**

## 3. 🔴 Second, independent defect — the leak-guard assertion cannot fire

Line 1434:

```csharp
handler.Requests.Should().NotContain(r => r.Body.Contains("Q1UNK"));
```

The relayed body is a `RelayBatchRequest` (`src/OpenWSFZ.Web/AppJsonContext.cs:412`) whose
datagrams are `RelayDatagramDto(string Type, string BytesBase64)` (`:403`), and `BytesBase64` is
produced via `Convert.ToBase64String` at `ExternalReportingService.cs:856`. The plaintext `Q1UNK`
**cannot structurally appear** in `r.Body` — this assertion passes unconditionally regardless of
whether the exclusion logic works, and has never once been seen to fail. The sibling assertion 70
lines above (test line 1371) shows the correct idiom already in this file:
`JsonSerializer.Deserialize<RelayBatchRequest>(req.Body, RelayJsonOptions)`, then inspect the decoded
object.

## 4. Ruled out — do not re-investigate

- **`RecordingHttpHandler` is not the cause.** `_requests` is `lock`-guarded on add and read, and
  `Requests` returns a snapshot copy — not a data race.
- **The 300 ms `Task.Delay` at line 1431 is not the cause and must NOT be removed.** It is a
  registered Gate G10 exception (`test-delay-debt.md:172`, entered 2026-07-30) in the "prove an
  absence" category `TESTING_STRATEGY.md` explicitly permits (line 346: *"there is no positive event
  to poll for when the assertion is that nothing further happened"*) — still correct. The defect is
  the non-deterministic **baseline**, not the absence proxy that follows it.
- **Scope is exactly this one test.** The only other `handler.Requests`-counting poll in the file
  (line ~1712, FR-065 Halt-Tx fan-out) configures a **leader**, whose startup Heartbeat goes out by
  UDP `DispatchAsync`, never through the HTTP handler — verified by reading the role gate, not
  assumed. No sibling test shares this bug.

## 5. The fix — two changes, both test-only

### Change 1 — stable baseline predicate

Replace the `Count >= 1` poll at line 1419 with a content-based predicate that waits for **both**
known startup emissions, using the file's own line-1365 idiom rather than a magic count:

```csharp
await Poll.UntilAsync(
    () => handler.Requests.Any(r => r.Body.Contains("\"type\":\"Heartbeat\""))
       && handler.Requests.Any(r => r.Body.Contains("\"type\":\"Status\"")),
    timeout: TimeSpan.FromSeconds(5));
var countAfterFirstBatch = handler.Requests.Count;
```

The `"Status"` literal is confirmed against `ExternalReportingService.cs:510` (§2 above) — this is
not a placeholder to re-derive. If, on your read of the current tree, that literal has drifted from
what's quoted here, **stop and escalate rather than substitute a count-based predicate** — a count
reproduces exactly this bug under a different name.

### Change 2 — make the leak-guard assertion capable of failing

Deserialise the relayed body and assert the exclusion over the decoded datagrams, per the line-1371
idiom already in this file, in place of the string-contains check at line 1434. **Demonstrate it can
fail**: temporarily relax the absolute-exclusion logic, confirm the new assertion goes red, then
revert. An assertion never seen to fail is not known to work — that's exactly how §3's defect was
sitting unnoticed.

Everything else in the test — including the 300 ms delay — stays as-is.

## 6. What NOT to do

- ❌ **Do not seed `_lastHeartbeatSentUtc = UtcNow` in `StartAsync`** (the 2026-08-14 note's option
  (a)). That changes **shipped daemon behaviour** — it removes the immediate startup Heartbeat a
  freshly-started follower currently sends its leader — to fix a test, and nobody has measured who
  depends on that promptness. Option (b) above is the recommended, and only authorised, fix; it also
  keeps the diff disjoint from any `src/` diff, which is what R1's zero-overlap check needs to
  verify. If you believe (a) is actually necessary, stop and raise it — it is the Captain's call, not
  a drop-in substitution.
- ❌ Do not remove or quarantine the test. §11.3 permits that only with QA + PO sign-off, neither
  given.
- ❌ Do not touch anything else on this branch — no `SUP-B` Option A work, no `F-001` L3/site-6, no
  `SUP-A`. This branch exists solely to clear the §11.3 blocker.
- ❌ Do not add any new fixed-duration delay anywhere in this file without a `test-delay-debt.md`
  entry and a written justification — that is an escalation, not something to add silently. (Gate
  G10's matching is by `(file, exact call text)` and is line-drift tolerant, so the *existing* line
  1431 entry needs no edit regardless of where the line ends up — but a genuinely new delay is a hard
  gate failure without its own entry.)

## 7. Optional, not a blocker

§6 of the brief: the immediate startup Heartbeat is very likely intentional behaviour (a fresh
follower should hear from the daemon promptly) but currently exists only as a side effect of
`MinValue` arithmetic — undocumented, unpinned by any test, one refactor from silently vanishing. A
small test pinning it deliberately would convert the accident into a specification. Do it in the same
slice if convenient; skip it if not — either is fine.

## 8. Definition of done

- [ ] Change 1 applied: baseline capture at (the former) line 1419 preceded by a content predicate
      over both `"Heartbeat"` and `"Status"` types, no `Count >=` check
- [ ] Change 2 applied: the `Q1UNK` assertion deserialises the body and checks the decoded datagrams;
      demonstrated to go red under a deliberately-broken exclusion, then reverted clean
- [ ] No new fixed-duration delay added anywhere in the file (or, if unavoidable, a fresh
      `test-delay-debt.md` entry with written justification — flag this explicitly if it happens)
- [ ] `dotnet test OpenWSFZ.slnx -c Release` — **full suite**, green, on Windows (this flake only
      reproduces under full-suite parallel load; an isolated single-test run is not sufficient
      evidence either way)
- [ ] Gate G10 (`tools/check_test_delay_sync.py`) passes
- [ ] `git diff main --stat` touches `tests/` only — if it touches `src/`, option (a) has been taken
      by accident; stop, do not proceed, that needs the Captain
- [ ] NFR-021 scan run **after** commit (untracked files are invisible to it beforehand) — clean
- [ ] Commit message states the structural argument for the fix (the baseline is now captured only
      after a predicate no partial startup can satisfy), not "N green runs ⇒ fixed" — N green runs
      are corroborating evidence, not the proof; that distinction belongs on the record

🛑 **Then stop.** No push, no merge, no request for either (HK-010/HK-014). No `pre_merge_check.py`
(HK-006 — Captain's initiative only). The Captain reviews the diff and decides on the merge; QA does
not declare readiness unprompted.

🔴 **Standing rider, from PO ruling R1:** if `FR-064` lands on `main` first, re-pin any ROW 0 Sec.4
manifest **after** that merge, never before — a manifest pinned to a superseded HEAD is a green gate
pointed at the wrong tree.
