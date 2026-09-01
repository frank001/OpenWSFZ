# Architect → QA brief — `FR-064` flake fix (the §11.3 `main`-merge blocker)

**Author:** Architect · **UTC:** 2026-09-01 16:17Z · **Base:** `main` @ `75ea2c1`
**Test:** `ExternalReportingServiceTests.Follower_AbsoluteExclusion_AppliesBeforeRelay`
**Prior art:** `flaky-externalreportingservice-fr064-absoluteexclusion-todo.md` (2026-08-14 diagnosis
+ suggested fix), PO ruling **R1** of `2026-08-30-1617-architect-to-qa-spec-f001-sup-b-amendment-2-execution-pack.md`
**Authorises:** nothing on its own. HK-015: the `dev-tasks/*.md` is QA's to author. HK-011: the edit
is a separate Developer session with Captain diff review.

---

## 0. Why this is being picked up now

It is the only item blocking every other buildable thing. `TESTING_STRATEGY.md` §11.3: a repeat
flake on the same test before the issue is fixed escalates to **blocker — no merges to `main`**.
This test has flaked twice (2026-08-14 CI run `31820509725` `windows-latest`; 2026-08-30 local
full-suite, 620/621). The root-cause fix was written up on 2026-08-14 and **never applied**. Two
PRs (#135, #136) have merged since on clean CI draws — that is luck, not a fix.

Downstream of it: the `SUP-B` step-7 Option A build (PO-decided 2026-09-01), and any other `main`
merge.

---

## 1. The 2026-08-14 diagnosis still holds — re-verified against `main`, not inherited

Checked, not trusted (HK-018/HK-022). `git log --since=2026-08-14` over both
`tests/OpenWSFZ.Daemon.Tests/ExternalReportingServiceTests.cs` and
`src/OpenWSFZ.Daemon/ExternalReportingService.cs` is **empty** — neither file has changed since the
write-up. Re-read on `75ea2c1`:

| Claim | Confirmed at |
|---|---|
| `_lastHeartbeatSentUtc` defaults to `DateTimeOffset.MinValue`, never seeded before `StartAsync` | `ExternalReportingService.cs:143` |
| `TimerLoopAsync` runs its body **immediately** — the `Task.Delay(_statusPollInterval)` is at the *end* of the loop | `:567`, delay at `:610` |
| Heartbeat branch therefore fires unconditionally on the first tick, whatever `heartbeatInterval` says | `:577`–`:584` |
| A **follower**'s Heartbeat relays over HTTP through the handler the test asserts against | `:823` `DispatchOrRelayAsync` → `RelayToLeaderAsync` (role-gated) |

So: an independent background task posts one unaccounted request into `handler.Requests`, and the
test never models it. The absolute-exclusion logic is not exercised by that request at all — **this
is not an exclusion regression.**

---

## 2. 🔴 CORRECTION to the 2026-08-14 write-up — and it changes the fix

The write-up says the startup Heartbeat landing *before* the baseline capture is *"harmless — folded
into the baseline"*. **That is wrong.** The baseline is captured after a poll for `Count >= 1`
(`:1419`), which **either** producer can satisfy. Two independent emissions race one predicate that
only counts to one:

- **P_hb** — the startup Heartbeat (unconditional, per §1)
- **P_st** — the Status POST produced by the first (empty) `DecodeBatch`

| Ordering at the moment `countAfterFirstBatch` is read | Baseline | Lands in the 300 ms window | Result |
|---|---|---|---|
| P_st only | 1 | P_hb | `2 != 1` → **FAIL** |
| P_hb only | 1 | P_st | `2 != 1` → **FAIL** |
| P_st then P_hb, both before the read | 2 | — | PASS |
| P_hb then P_st, both before the read | 2 | — | PASS |

**The test fails whenever exactly one of the two startup emissions has landed at baseline-capture
time** — which of them is irrelevant. Both interleavings are failing interleavings.

⇒ **Consequence for the fix: "drain the startup Heartbeat before writing the first batch" is NOT
sufficient**, because P_st does not exist until that batch is written. The baseline must be captured
only after a predicate that is **stable** — i.e. after *both* known startup emissions have been
observed. Anything that polls for "one request" reproduces the bug with new words.

---

## 3. 🔴 SECOND FINDING — the test's other assertion cannot fire

`:1434`:

```csharp
handler.Requests.Should().NotContain(r => r.Body.Contains("Q1UNK"));
```

The relay body is `RelayBatchRequest` (`src/OpenWSFZ.Web/AppJsonContext.cs:412`), whose datagrams are
`RelayDatagramDto(string Type, string BytesBase64)` (`:403`) — the datagram is
**`Convert.ToBase64String`d** at `ExternalReportingService.cs:856`. The plaintext `Q1UNK` is
therefore **structurally incapable of appearing** in `r.Body`. The assertion passes unconditionally
and has never tested the leak it appears to guard against.

This is not speculation — **the sibling test 70 lines above does it correctly** and shows the right
idiom:

```csharp
handler.Requests.Any(r => r.Body.Contains("\"type\":\"Decode\""))   // :1365
JsonSerializer.Deserialize<RelayBatchRequest>(req.Body, RelayJsonOptions)  // :1371 — then inspect
```

Same class as the drafting question HK-022 puts on every ROW 0: *what error could this check not
detect?* Here, all of them. **Recommend fixing it in the same slice** — deserialise and assert over
the decoded datagram, as `:1371` already does — rather than leaving a green assertion that means
nothing. It is two lines from the same file's own established pattern.

---

## 4. Ruled out — do not re-investigate

- **`RecordingHttpHandler` is thread-safe.** `_requests` is `lock`-guarded on both add (`:130`) and
  read, and `Requests` returns a **snapshot copy** (`:119`). Not a data race, not the cause.
- **The 300 ms `Task.Delay` at `:1431` is not the cause, and must NOT be removed.** It is a
  *registered, justified* Gate G10 exception — `test-delay-debt.md:172`, entered 2026-07-30, in the
  "prove an absence" category that `TESTING_STRATEGY.md` §346 explicitly permits: *"there is no
  positive event to poll for when the assertion is that nothing further happened."* That reasoning
  is still correct. The defect is the **non-deterministic baseline**, not the absence proxy.
- **Scope is exactly one test.** The only other `handler.Requests`-counting poll in the file
  (`:1712`, FR-065 Halt-Tx fan-out) configures a **leader**, and `DispatchOrRelayAsync` (`:823`) is
  role-gated — a leader's startup Heartbeat goes out by UDP `DispatchAsync`, never through the HTTP
  handler. Verified by reading the role gate, not assumed from the test name. No sibling shares the
  assumption.

---

## 5. Recommended fix — option (b), **test-only**

The 2026-08-14 note offered (a) seed `_lastHeartbeatSentUtc = UtcNow` in `StartAsync`, or (b) make
the test independent of the race. **I recommend (b), and I recommend against (a).**

Reasoning, stated once: (a) fixes a test by changing **shipped daemon behaviour** — it removes the
immediate startup Heartbeat that a freshly-started follower currently sends to its leader. Nothing
has measured who depends on that promptness, and the tail should not wag the dog. (b) is confined to
one test file, and keeps the diff **trivially disjoint** from any `src/` diff, which is what ruling
R1's zero-file-overlap check wants to be able to verify.

**Change 1 — a stable baseline predicate.** Replace the `Count >= 1` poll at `:1419` with one that
waits for both known startup emissions by **content**, using the file's own `:1365` idiom rather
than a magic number:

```csharp
await Poll.UntilAsync(
    () => handler.Requests.Any(r => r.Body.Contains("\"type\":\"Heartbeat\""))
       && handler.Requests.Any(r => r.Body.Contains("\"type\":\"Status\"")),
    timeout: TimeSpan.FromSeconds(5));
var countAfterFirstBatch = handler.Requests.Count;
```

Content-based, not `Count >= 2`: it is identifiable from its own data, it fails loudly naming what it
waited for, and it does not silently pass on two Heartbeats. ⚠️ Whoever implements it must **confirm
the `Status` type string against the decode-loop's own relay call** rather than copying it from this
brief — I read `"Heartbeat"` directly at `:584`, but the grouped Status/Decode batch is assembled in
`DecodeLoopAsync` and I did not read its literals. If the two-condition predicate cannot be written
mechanically, **stop and escalate** — do not fall back to a count.

**Change 2 — §3's dead assertion.** Deserialise the body and assert the exclusion over the decoded
datagram, per `:1371`.

Everything else in the test stays, including the 300 ms absence delay.

---

## 6. Concern stated once, then it is yours

If the immediate startup Heartbeat *is* desired behaviour (and I think it probably is — a fresh
listener should hear from the daemon promptly), then note that it currently exists **by accident of
`MinValue` arithmetic, is documented nowhere, and is pinned by no test.** It is one refactor away
from disappearing silently. Recommend the same slice adds a small test that pins it deliberately.
That converts an accident into a specification. Not a blocker on the fix; do it or don't.

---

## 7. Acceptance criteria (mechanical, HK-021)

1. `dotnet test OpenWSFZ.slnx -c Release` — **full suite**, green, on Windows. Not the filtered
   single test: this flake only reproduces under full-suite parallel load, and an isolated re-run
   passed even on the day it failed.
2. The baseline capture at `:1419` is preceded by a predicate over **request content**, not a count,
   and the test contains **no new fixed-duration delay**.
3. Gate G10 passes. Matching is by *(file, exact call text)* and is line-drift tolerant
   (`check_test_delay_sync.py` docstring), so the existing entry needs **no** edit if the line moves
   — but **any newly added `Task.Delay(...)` is a hard gate failure.** If one is genuinely
   unavoidable, it needs its own `test-delay-debt.md` entry with a written justification, and that is
   an escalation, not a silent addition.
4. The `Q1UNK` assertion, after the change, **fails when deliberately broken** — demonstrate it
   (temporarily relax the exclusion, watch it go red, revert). An assertion that has never been seen
   to fail is not known to work; §3 is exactly that failure.
5. `git diff main --stat` touches **`tests/` only** under the recommended option (b). If it touches
   `src/`, option (a) has been taken instead — that is a different decision and needs the Captain,
   not a quiet substitution.
6. NFR-021 scan clean — run it **after** commit; untracked files are invisible to it beforehand.

⚠️ **Honest limit on criterion 1:** N green runs cannot prove a race is gone. What carries this fix
is the **structural** argument — the baseline is captured only after a predicate that cannot be
satisfied by a partial startup — and the runs corroborate it. Do not report "5/5 green ⇒ fixed";
report the structural change, with the runs as supporting evidence.

---

## 8. Routing and branch

- **Branch:** `fix/fr064-heartbeat-race`, **off `main`**, per PO ruling R1. Its own short branch — it
  gates `main` on its own account and must not wait behind, or ride along with, any feature branch.
- **QA:** authors `dev-tasks/2026-09-01-flaky-externalreportingservice-fr064-heartbeat-race.md` from
  this brief (HK-015), following the pattern of the two existing flaky-test dev-tasks of 2026-08-30.
  Then **stops** (HK-011).
- **Developer session:** makes the edit. **Captain:** reviews the diff, signs off, decides the merge
  (HK-010 — green CI is necessary, never sufficient).
- 🔴 **Ruling R1's standing rider:** if `FR-064` lands on `main` first, **re-pin any ROW 0 Sec.4
  manifest AFTER that merge, never before.** A manifest pinned to a superseded HEAD is a green gate
  pointed at the wrong tree.
- 🔴 **Zero file overlap with any other in-flight diff must be VERIFIED, not trusted.** If they are
  not disjoint, one of them has escaped its pre-registered scope ⇒ **STOP**.

---

## 9. What this brief does NOT license

- ❌ No third design. The fix is the 2026-08-14 TODO's option (b), refined by §2 — **not re-derived.**
- ❌ No change to `ExternalReportingService.cs` under the recommendation. Option (a) remains
  available but is the Captain's call, not a drop-in alternative.
- ❌ No removal or quarantine of the test. §11.3 permits it only with **QA + Product-Owner sign-off**,
  and neither has been given.
- ❌ Nothing about `SUP-B` Option A, `F-001` L3/site-6, or `SUP-A`. Clearing this blocker **unblocks**
  the merge path; it authorises no work on any of them.
