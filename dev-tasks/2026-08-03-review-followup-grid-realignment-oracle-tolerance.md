# Dev-task — review follow-up on `fix/cycleframer-grid-realignment`: the oracle's audio bound is looser than the bar it guards

**Author:** QA, 2026-08-03 (15:21 UTC, `date -u`, per HK-017).
**Branch:** `fix/cycleframer-grid-realignment` — continue on it, do **not** branch afresh.
**Commits reviewed:** `0c15749` (oracle), `6700e71` (fix). Both **unpushed**; HK-011 sign-off intact.
**Reviewing:** `dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-after-pr118.md`.

**Verdict: the implementation is APPROVED.** One item below is required before merge; it is a
`tests/` change only. Nothing in `src/CycleFramer.cs` needs to change.

---

## 0. What was verified, so you know what is already settled

Independently reproduced by QA rather than read off the commit message:

- `src/OpenWSFZ.Ft8/CycleFramer.cs` reverted to pre-fix, new tests left in place ⇒ **5 of 5 oracle
  cases RED**. Restored, then **18/18 green** on the fix. The regression-oracle discipline holds.
- Assertion 2 is genuinely **not** self-referential — `expected` derives from
  `device.ExpectedFirstSampleIndex(...)`, the harness's own model of which source sample was being
  captured at wall-clock `G`, not from the framer's bookkeeping. A label-snapping implementation
  cannot satisfy it. That was §4.2's whole purpose and it is discharged.
- The `CycleFramerTests.cs` change is a fixture accommodation (more samples fed), not a weakened
  assertion.

Two things you did that the design did not ask for, both correct and both worth keeping: the
`firstSampleUtc` correction for the unconsumed remainder of the current chunk (up to 2 048 samples
≈ 171 ms of systematic bias, which would otherwise have eaten most of the 0.2 s budget), and making
`AlignToCycleStart` tick-exact.

---

## 1. REQUIRED — the audio bound is inverted across the four cases

`tests/OpenWSFZ.Ft8.Tests/CycleFramerClockDriftOracleTests.cs`

| case | perturbation | label bound | **audio bound** |
|---|---|---|---|
| 1 — 24 h at 48.4 ppm (line ~153) | none | `ToleranceSeconds` (0.2 s) | ⚠️ `MaxCorrectionSamples` (3 000 = **250 ms**) |
| 2 — dropped chunk (line ~220) | 2 s drop | 0.2 s | `ToleranceSeconds`, after settling ✅ |
| 3 — restart epochs (line ~271) | none | 0.2 s | ⚠️ `MaxCorrectionSamples` (**250 ms**) |
| 4 — NTP step (line ~326) | clock step | 0.2 s | `ToleranceSeconds`, after settling ✅ |

**The two cases with no clock step carry the loosest bound.** That is the wrong way round: cases 2
and 4 have something to converge *from* and legitimately need slack plus a settling window; cases 1
and 3 have nothing to converge from and the clamp should never engage in them at all.

**The number is also above the programme's own bar.** 250 ms > the 0.2 s acceptance bar in the
drift dev-task §5, which is itself set from measured decode loss (−3.8% at 1 s, −29.8% at 2 s), not
from taste. An oracle guarding a 0.2 s bar must not pass at 0.24 s.

**Scale of the slack.** At 48.4 ppm the expected steady-state misalignment is one cycle's
accumulation:

```
15 s x 48.4 ppm = 726 us = ~8.7 samples
```

— which your own assertion message states. The bound permits **3 000**, roughly **333x** the
expected value. An implementation that applied the correction every other cycle, or at half
strength, would pass green. Given that this entire defect was an oracle that could not fail, an
oracle that cannot fail *usefully* is the same mistake one notch quieter.

### The change

In cases 1 and 3, assert the audio misalignment against **`ToleranceSeconds`**, the same bar their
own label assertions already use. Convert samples to seconds (as cases 2 and 4 do via
`SampleMisalignment(...) / (double)SampleRate`) rather than converting the tolerance to samples, so
one constant remains the single source of truth.

**Do not invent a tighter number.** ~9 samples is what the arithmetic predicts and 0.2 s is what the
programme has anchored to measured decode loss; anything in between would need its own justification
per HK-021, and does not have one. If you find 0.2 s does not hold in these cases, **stop and raise
it** — that would be a finding about the fix, not a reason to pick a looser constant.

### Leave this alone

`AssertNoCycleExceedsTheClamp` must keep using `MaxCorrectionSamples`. It asserts a different
property — that no single cycle's correction exceeds the clamp — and there the constant is exactly
right. Only the two absolute-misalignment assertions change.

### Acceptance

Both edited cases green, and — per §4.3.1 of the parent dev-task — **still red against unfixed
`src/CycleFramer.cs`**. Re-run the revert check; a tightened bound that stopped being red would mean
something else broke.

---

## 2. WORTH A LOOK — not required, and may well be a non-issue

`firstSampleUtc` assumes the framer reads a chunk promptly after the device hands it over:

```csharp
DateTime firstSampleUtc = _clock.UtcNow.AddSeconds(-remaining / (double)SampleRate);
```

If the framer is *late* to the chunk — a stalled decode pump, a long GC pause, a busy host —
`_clock.UtcNow` runs ahead of the true capture instant and the correction is biased late by the lag.
Bounded per cycle by the clamp, and self-correcting once the lag clears, so this is very likely
benign in production.

What makes it worth a moment is that **the oracle cannot see it**: `SimulatedCaptureDevice` derives
the clock from its own production position, so the harness is lag-free by construction and no
existing case would go red if this mattered.

Two acceptable outcomes, both fine:

1. Reason it through, conclude it is bounded and benign, and **record that reasoning in a comment**
   next to `firstSampleUtc` — the next reader will otherwise ask the same question.
2. If it is *not* obviously bounded, say so and stop. A harness change to inject processing lag is a
   scope increase and needs QA/Architect agreement, not a unilateral extension of this branch.

Please do not add speculative defensive code here. The current line is correct for the normal case
and a comment is worth more than a guard nobody can test.

---

## 3. Boundaries (unchanged from the parent dev-task)

- **HK-011:** local build/tests only. **Show the diff to the Captain for sign-off before `git push`.**
- **HK-006:** do **not** run `python3 tools/pre_merge_check.py`, and do not add it to any checklist —
  Captain's trigger only, at merge time.
- **HK-010:** merge to `main` needs the Captain's explicit sign-off regardless of green CI.
- Do not amend, squash or rebase `0c15749` / `6700e71`. The test-then-fix commit order is the
  evidence that the oracle was red first; keep it legible in the history.
- Scope is §1, plus optionally §2's comment. Anything else, **stop and escalate**.

## 4. Traceability

- `dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-after-pr118.md` — the parent
  task; §4.2 (the assertion this strengthens) and §5 (the 0.2 s bar).
- `qa/cycleframer-alignment-replay/2026-08-02-1813-architect-design-cycleframer-grid-realignment.md`
  — §5's acceptance table, the source of the 0.2 s figure.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — closes once this branch merges.
- `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` — the same defect; closes with it.
