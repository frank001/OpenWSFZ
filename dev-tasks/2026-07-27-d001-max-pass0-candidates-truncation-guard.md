# Developer handoff: `MaxPass0Candidates` truncation guard (D-001, Q2 — long owed)

**Authored by:** QA (per HK-011/HK-015), following the Architect's consolidated handoff
`qa/cycleframer-alignment-replay/2026-07-27-1752-architect-to-qa-consolidated-handoff.md` §4 Q2.
**Branch:** continue on `d001-c4-min-score-sweep`, stacked after
`dev-tasks/2026-07-27-d001-shim-version-correction-and-capabilities.md` (Q1) — no conflict expected
(Q1 touches `ExpectedShimVersion`/`RawLlrCaptureCapabilityBit`/`SetCandidateDiagLlrCapture`/
`GetLastCandidateLlr174`'s `-1` handling; this task touches `GetLastCandidateDiagnostics` and
`GetLastCandidateLlr174`'s `n <= 0` boundary, a few lines further down the same functions — merge
by hand if both land in the same session).
**Status:** overdue by the Architect's own account — first flagged as a ruling on 2026-07-26 20:30
("the third time it happens it should become a guard"), still unauthored as of this handoff. This is
that guard.
**Shape:** QA's call per the handoff. Design and rationale below — read §2 before assuming a
different shape is obviously simpler; the naive version (throw whenever a capacity-bound getter
returns exactly its capacity) is wrong for three of the five capacity-bound getters in this file
and would break production every cycle. §2.2 explains why.

---

## 1. Context — five instances, one is fixable this way

The Architect's ruling counts five occurrences of "a diagnostic export silently truncated instead of
erroring loudly": C.4's `MaxPass0Candidates=140` truncation, THE 567's 279/567 subsample, C.1's
stale-DLL run, R.4's out-of-band slot 7, and Q1's gated-off silent zero (now fixed). These are not
all the same bug at the same layer — a stale DLL, a frequency-clamping artefact, and an analysis
script reading half a corpus are each their own failure mode with their own fix. **This dev-task
targets the one that recurs at this specific layer**: a native export with a fixed-capacity output
array silently returning `min(actual, capacity)` with no signal that `actual > capacity` ever
happened. That is exactly the C.4 bug (`dev-tasks/2026-07-26-d001-c4-min-score-sweep.md`, and the
retrospective doc comment already in `Ft8LibInterop.cs:283-304`): raising native `K_MAX_CANDIDATES`
to 600 did nothing for the diagnostic CSV because the managed `capacity` parameter, still baked in
at 140, silently capped the copy back down — and nothing about the return value (`140`, a perfectly
plausible real candidate count) looked wrong.

## 2. Design

### 2.1 The five capacity-bound getters, and which ones this guard applies to

`Ft8LibInterop.cs` has five methods with the shape "native writes into a caller-sized buffer, caller
passes `capacity`, native returns `n <= capacity`, managed slices to `[..n]`":

| method | `capacity` argument | what `capacity` represents | is `n == capacity` ever the *expected*, non-truncated case? |
|---|---|---|---|
| `GetLastPassCounts` | `maxPasses` (`MaxDecodePasses` = 2, `Ft8LibInterop.cs:323`) | the **exact, fixed** number of decode passes this build runs | **Yes — every single cycle.** 2 passes always run; `n == 2 == capacity` is the normal case, not truncation. |
| `GetLastCandidateCounts` | `maxPasses` (same) | same as above | **Yes**, same reasoning. |
| `GetLastLlrStats` | `maxPasses` (same) | same as above | **Yes**, same reasoning. |
| `GetLastCandidateDiagnostics` | `MaxPass0Candidates` (600, `Ft8LibInterop.cs:304`) | **headroom** — an upper bound sized with margin over an unknown, per-cycle candidate count | **No.** `MaxPass0Candidates` exists specifically so real candidate counts stay comfortably under it; hitting it exactly is the anomaly C.4 was. |
| `GetLastCandidateLlr174` | `MaxPass0Candidates` (same) | same headroom | **No**, same reasoning. |

**This is the reason a single blanket "throw when `n == capacity`" rule is wrong**, and why it is
called out explicitly rather than left for a future session to "simplify": applying it to the first
three would make `GetLastPassCounts`/`GetLastCandidateCounts`/`GetLastLlrStats` throw on **every
production decode cycle**, since 2 passes always fill a capacity-2 buffer. Per HK-018 (check whether
the axis can actually distinguish "truncated" from "expected" before applying a rule) — here it
cannot, for those three, and can, for the last two. **Scope this guard to
`GetLastCandidateDiagnostics` and `GetLastCandidateLlr174` only.**

### 2.2 The guard: cross-check against the independently-captured pass-0 candidate count

`GetLastCandidateCounts(MaxDecodePasses)[0]` already reports pass 0's **actual** candidate count —
`ftx_find_candidates`'s own return value (`ft8_shim.c:1533`, `tls_candidate_counts[pass] = ncands`),
captured every cycle regardless of whether the C.2 diagnostic capture is even enabled, and **not**
bounded by `MaxPass0Candidates` (it is bounded by native `K_MAX_CANDIDATES`, currently 600, verified
crash-free at that ceiling by C.1). Same cycle, same pass, comparable 1:1 against
`GetLastCandidateDiagnostics`/`GetLastCandidateLlr174`'s own `n` — this is a **real cross-check
already available today**, not a new native export.

If the diagnostic capture returned exactly `MaxPass0Candidates` (`n == capacity`) while the
independently-captured pass-0 candidate count is *larger*, candidates were silently dropped between
the two. If they agree, `n == capacity` was coincidence, not truncation, and nothing is wrong.

**Known residual gap, out of scope here:** this only detects truncation between the diagnostic
capture layer and `ftx_find_candidates`'s own cap. If `ftx_find_candidates` itself silently drops
candidates beyond its own `K_MAX_CANDIDATES` argument (inside `decode.c`, a different function this
guard cannot see into), `tls_candidate_counts[0]` would already be truncated and this cross-check
would agree with a wrong number. That is a different, lower-priority concern — C.1 already verified
600 is a safe crash-free ceiling, and there is no evidence of pass-0 candidate populations anywhere
near 600 in this study (§2.2 of the Architect's handoff: "population plateaus at ~220–295/cycle").
Not this task's job to close; noted so it is not mistaken for closed.

### 2.3 Implementation — pure logic separated from TLS wiring, so it is unit-testable

Add to `Ft8LibInterop.cs`, near `MaxPass0Candidates` (`Ft8LibInterop.cs:304`):

```csharp
/// <summary>
/// Guards against a repeat of the D-001 C.4 truncation bug (see the retrospective note on
/// <see cref="MaxPass0Candidates"/> above): a capacity-bound diagnostic getter returning
/// exactly its capacity is ambiguous on its own — it could be the true count, or it could
/// mean data was silently dropped. <paramref name="actualPass0Candidates"/> is an
/// independent, same-cycle cross-check (<see cref="GetLastCandidateCounts"/>'s pass-0
/// entry, NOT bounded by <see cref="MaxPass0Candidates"/> — see <c>ft8_shim.c</c>'s
/// <c>tls_candidate_counts</c>) that can tell the two apart.
/// <para>
/// Pure comparison logic, deliberately taking plain <c>int</c>s rather than reaching into
/// TLS state itself, so this can be unit-tested without a real decode cycle. Callers are
/// responsible for supplying <paramref name="actualPass0Candidates"/> from the same cycle
/// as <paramref name="captured"/>/<paramref name="capacity"/> — see
/// <see cref="GetLastCandidateDiagnostics"/> / <see cref="GetLastCandidateLlr174"/> for the
/// real wiring.
/// </para>
/// Scoped deliberately to the two candidate-capacity-bound getters — do NOT apply this to
/// <see cref="GetLastPassCounts"/>/<see cref="GetLastCandidateCounts"/>/
/// <see cref="GetLastLlrStats"/>, whose capacity (<see cref="MaxDecodePasses"/>) is the
/// exact expected pass count, not headroom; <c>n == capacity</c> there is the normal case
/// every single cycle, and this guard would misfire on every production decode if applied
/// there. (dev-tasks/2026-07-27-d001-max-pass0-candidates-truncation-guard.md §2.1)
/// </summary>
/// <exception cref="InvalidOperationException">
/// Thrown when <paramref name="captured"/> == <paramref name="capacity"/> AND
/// <paramref name="actualPass0Candidates"/> is strictly greater — i.e. candidates were
/// confirmed dropped, not merely suspected.
/// </exception>
internal static void GuardCandidateCaptureTruncation(
    string callerName, int captured, int capacity, int actualPass0Candidates)
{
    if (capacity <= 0 || captured < capacity)
        return; // strictly below capacity: definitely complete, nothing to check

    // captured == capacity here (native never returns more than capacity). Ambiguous
    // without the cross-check.
    if (actualPass0Candidates <= captured)
        return; // cross-check agrees (or is unavailable, signalled by -1) -- not truncation

    throw new InvalidOperationException(
        $"{callerName}: diagnostic capture returned exactly its capacity ({capacity}) while " +
        $"pass 0 actually found {actualPass0Candidates} candidates this cycle -- " +
        $"{actualPass0Candidates - captured} were silently dropped. Raise MaxPass0Candidates " +
        "(Ft8LibInterop.cs) -- and the native K_MAX_CANDIDATES it must stay >= to, if that is " +
        "also the binding constraint -- before trusting this capture again. This is the D-001 " +
        "C.4 truncation bug pattern; see dev-tasks/2026-07-26-d001-c4-min-score-sweep.md and " +
        "dev-tasks/2026-07-27-d001-max-pass0-candidates-truncation-guard.md.");
}
```

Wire it into both call sites, immediately after each native call and its `n`, **before** either
method's existing `if (n <= 0) return ...` early-return (so the guard runs even though the
subsequent early-return path is unaffected when `n < capacity`):

`GetLastCandidateDiagnostics` (`Ft8LibInterop.cs:715-719`):
```csharp
int n = NativeGetLastCandidateDiag(
    freqHz, dt, score, decodedRaw, prenormVariance, postnormMeanAbsLlr, MaxPass0Candidates);

GuardCandidateCaptureTruncation(
    nameof(GetLastCandidateDiagnostics), n, MaxPass0Candidates,
    ActualPass0CandidateCount());

if (n <= 0)
    return ([], [], [], [], [], []);
```

`GetLastCandidateLlr174` (`Ft8LibInterop.cs:758-761` — coordinate with Q1's dev-task, which also
edits this method's `n <= 0`/`n == -1` handling immediately below this point):
```csharp
var flat = new float[MaxPass0Candidates * LlrPerCandidate];
int n = NativeGetLastCandidateLlr(flat, MaxPass0Candidates);

GuardCandidateCaptureTruncation(
    nameof(GetLastCandidateLlr174), n, MaxPass0Candidates,
    ActualPass0CandidateCount());

if (n <= 0) return [];
```
(If Q1 already landed first, its `n == -1` check goes *before* this guard — a capability-absent `-1`
is not a truncation case and should throw Q1's more specific exception first. `-1 < MaxPass0Candidates`
so `GuardCandidateCaptureTruncation` itself would no-op on `-1` regardless of ordering — `captured <
capacity` — but the clearer exception message belongs to Q1's check, so keep it first if both are
present.)

Add the small helper both call sites share, next to them:
```csharp
/// <summary>
/// Pass 0's actual candidate count this cycle (<see cref="GetLastCandidateCounts"/>'s
/// first entry), NOT bounded by <see cref="MaxPass0Candidates"/> — the independent
/// cross-check <see cref="GuardCandidateCaptureTruncation"/> needs. Returns -1 (meaning
/// "no cross-check available", never treated as "more candidates than captured") if
/// <see cref="GetLastCandidateCounts"/> itself returns nothing this cycle.
/// </summary>
private static int ActualPass0CandidateCount()
{
    var counts = GetLastCandidateCounts(MaxDecodePasses);
    return counts.Length > 0 ? counts[0] : -1;
}
```

## 3. Why this belongs in `Ft8LibInterop.cs`, not `IFt8NativeInterop`/`Ft8Decoder.cs`

Same placement reasoning as Q1's capability guard: the truncation signal is intrinsic to the static
P/Invoke layer that already owns `MaxPass0Candidates`, `MaxDecodePasses`, and the ABI self-test —
not a concern of the `IFt8NativeInterop` abstraction (used for decoder-level mocking in the eight
test files that stub these methods as no-ops) or of `Ft8Decoder.cs`'s per-cycle orchestration. No
change needed to `IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`, or `Ft8Decoder.cs`.

## 4. Acceptance criteria

- [ ] `GuardCandidateCaptureTruncation` is a pure function of its four `int`/`string` arguments —
      no TLS/native calls inside it — and is `internal` (testable via `InternalsVisibleTo
      ("OpenWSFZ.Ft8.Tests")`, already declared in `AssemblyAttributes.cs`).
- [ ] Unit tests (new, e.g. in `Ft8LibInteropTests.cs` or a new `TruncationGuardTests.cs`) exercise
      the pure logic directly, no real or mocked decode cycle needed:
      - `captured < capacity` → never throws, any `actualPass0Candidates` value (including values
        larger than `captured` — still not truncation, since capacity was never hit).
      - `captured == capacity`, `actualPass0Candidates <= captured` (including `-1`, the
        "unavailable" sentinel) → does not throw.
      - `captured == capacity`, `actualPass0Candidates > captured` → throws
        `InvalidOperationException` whose message names both the capacity and the actual count.
      - `capacity <= 0` → never throws regardless of the other arguments (degenerate guard).
- [ ] `GetLastCandidateDiagnostics` and `GetLastCandidateLlr174` both call the guard with
      `ActualPass0CandidateCount()` before their existing `n <= 0` early-return.
- [ ] **`GetLastPassCounts`, `GetLastCandidateCounts`, and `GetLastLlrStats` are unchanged** — confirm
      by `git diff` that no line inside those three methods moves. This is the one thing most likely
      to be "simplified" wrongly by a future pass; the acceptance check is here specifically to catch
      that.
- [ ] The existing 297-test suite stays green — in particular, confirm no existing test that calls
      `GetLastCandidateDiagnostics`/`GetLastCandidateLlr174` via the **real** (non-mock) interop
      starts throwing. (The eight mock-based test files are unaffected — they stub
      `IFt8NativeInterop` directly and never reach `Ft8LibInterop`.)
- [ ] `git diff --stat` confined to `Ft8LibInterop.cs` and the new/edited test file(s). No change to
      `IFt8NativeInterop.cs`, `Ft8NativeInteropAdapter.cs`, `Ft8Decoder.cs`, or any native (`.c`/`.h`)
      file — this is a managed-only, cross-check-based guard using data already exported today.
- [ ] **Not on this checklist, deliberately:** `pre_merge_check.py` (QA's own step, HK-006/HK-011).

## 5. References

- `qa/cycleframer-alignment-replay/2026-07-27-1752-architect-to-qa-consolidated-handoff.md` §4 Q2 —
  the task, and the five-instance count.
- 2026-07-26 20:30 Architect ruling (referenced in the handoff, not separately filed) — "the third
  time it happens it should become a guard that errors rather than truncates."
- `dev-tasks/2026-07-26-d001-c4-min-score-sweep.md` — the original C.4 truncation bug this guard
  targets.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:283-304` — the existing retrospective doc comment on
  `MaxPass0Candidates`, already recording the C.4 history this guard formalises into code.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1508-1534` — `ftx_find_candidates`'s call and
  `tls_candidate_counts[pass] = ncands`, the independent, non-`MaxPass0Candidates`-bounded count
  this guard cross-checks against.
- `[HK-018]` (added 2026-07-27, in QA's memory) — check whether the axis can actually distinguish
  "truncated" from "expected" before applying a rule; directly informs §2.1's scoping decision.

---

*Per HK-011, this is `src/` work — stays in a Developer session, diff reviewed by QA, Captain
sign-off before push. Per HK-014/HK-015 convention applied to Developer sessions in this thread,
nothing is pushed or merged from here; hand the diff back to QA when done.*
