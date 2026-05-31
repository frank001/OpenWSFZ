# Developer Briefing — Iterative Signal Subtraction
## Product Decision Record & QA Acceptance Criteria

**To:** Developer / Architect  
**From:** QA  
**Date:** 2026-05-31  
**Status:** Product decision confirmed by Captain — implementation required

---

## 1. Product decision

The Captain has directed that iterative signal subtraction **must be implemented**. This is
not deferred, not optional, and not subject to re-negotiation as a "product decision." It
is the direction.

This decision resolves the ambiguity in `QA-ALIGNMENT-2026-05-31.md` §2, which described
the 33.4% recovery gap as an "open product decision." It is now closed: Option A.

---

## 2. Specification grounding — this is not new work

Iterative signal subtraction is **already mandated** by the live ft8-decoder specification.
`openspec/specs/ft8-decoder/spec.md`, line 10:

> *"The FT8 decoder **SHALL** complete a full decode cycle — including all time-domain
> analysis, sync candidate detection, LDPC decode, **iterative signal subtraction**, and
> message unpacking — within 13 seconds..."*

The feature appears inside a SHALL statement as a named component of a complete decode
cycle. The current implementation is therefore non-compliant with its own specification.
This change closes that gap.

Additionally, `RECOVERY_PLAN.md` §7 defines Phase 2A exit criteria as:

> *"real-signal fixtures decode at parity with WSJT-X; full suite green."*

Phase 2A has not met its exit criteria. This change is the vehicle by which it does.

---

## 3. What iterative signal subtraction means

WSJT-X performs two decode passes per cycle:

1. **First pass** — decode all signals above the noise floor. Each decoded signal is
   precisely located in the spectrogram (frequency bin, time offset, amplitude).
2. **Subtraction** — for each decoded signal, suppress its contribution from the
   spectrogram (zero or attenuate the relevant tiles).
3. **Second pass** — decode the residual spectrogram. Signals previously masked by
   stronger co-channel transmissions now become visible.

This is why WSJT-X recovers signals we do not: it strips the strong signals away and
decodes into the quiet that remains. `ft8_lib` as supplied by `kgoba` does not implement
this. The 296-signal gap in the 42-cycle corpus is the direct consequence.

---

## 4. Architectural paths — decision required from Architect

Three implementation paths exist. QA does not choose; the Architect must specify the
chosen path in the change design document, with rationale.

### Path A — Implement in C within the ft8_lib fork (recommended)

The spectrogram (`monitor_t` waterfall) is computed once and lives in C memory throughout
the decode. Implementing subtraction at the C level gives direct access to the waterfall
tiles — the right abstraction for this operation. The approach:

1. After each decode pass, for each recovered signal, locate its tiles in the waterfall
   using the known frequency bin and time offset.
2. Zero or attenuate those tiles (suppress the signal's energy).
3. Re-run candidate detection and LDPC decode on the modified waterfall.
4. Iterate until no new signals are found or a maximum iteration count is reached.

**Prerequisite:** the submodule fork (item B1 in `DEV-ALIGNMENT-2026-05-31.md`) must be
in place before implementation begins. This change cannot be built on uncommitted
submodule state.

**Advantage:** operates at the right level of abstraction; the C code already has all the
frequency/timing data needed for accurate subtraction.

**Disadvantage:** diverges from upstream `kgoba/ft8_lib`. The fork must be maintained.

### Path B — Implement in C# at the `Ft8Decoder` wrapper boundary

After the first ft8_lib pass returns decoded messages:

1. Reconstruct each decoded signal as a time-domain PCM waveform (requires knowing the
   signal's dial frequency offset, DT, and amplitude — all present in `Ft8NativeResult`).
2. Subtract the reconstructed signal from the original PCM buffer.
3. Call ft8_lib again on the modified PCM.
4. Merge and deduplicate results.

**Advantage:** leaves the C library unmodified; no fork divergence.

**Disadvantage:** PCM-domain subtraction is less accurate than spectrogram-domain
subtraction because the FT8 signal reconstruction must be exact (correct amplitude,
phase, timing) to subtract cleanly. Any error in reconstruction leaves residual energy
that degrades rather than improves the second pass. This path is materially harder to
implement correctly.

### Path C — Source a different library

Locate a permissively-licensed FT8 decoder that already implements iterative subtraction
and does not require reading GPL-3.0 source. QA is not aware of one that satisfies the
licence constraint; this path requires research before commitment.

---

## 5. Acceptance criteria

The following criteria govern QA approval of this change. All must be satisfied for merge
to `main`.

---

### AC-IS-1 — Replay harness recovery rate ≥ 80%

The 42-cycle corpus measurement (`ReplayHarnessTests`, run locally against the full
corpus) must show a recovery rate of **≥ 80%** against WSJT-X decodes.

| Metric | Current baseline | Required for merge | Aspiration |
|---|---|---|---|
| Matched decodes | 591 / 887 | ≥ 710 / 887 | ≥ 754 / 887 (85%) |
| Recovery rate | 66.6% | **≥ 80.0%** | ≥ 85% |
| False positive rate | 3.9% | ≤ 6% | ≤ 4% |

The false positive allowance is slightly relaxed from today's 3.9% because a second pass
naturally surfaces some borderline decodes. If false positives exceed 6%, QA will require
a minimum SNR or confidence threshold before merge.

The findings.md file must be regenerated and committed to reflect the post-implementation
measurement.

---

### AC-IS-2 — G6 fixture answer keys expanded and gate remains green

The current `.expected.txt` answer keys cover only high-SNR signals (≥ +6 to ≥ +14 dB).
With iterative subtraction, the decoder should recover medium-SNR signals from the same
fixtures. The answer keys must be expanded accordingly.

**Process:**
1. After a successful local implementation, run the replay harness on the three committed
   fixture WAVs to identify which WSJT-X decodes are now recovered.
2. Expand each `.expected.txt` to include all signals recovered at SNR ≥ 0 dB
   (moderate confidence). Do not include signals below 0 dB SNR in the CI answer key
   — those are subject to noise-floor variability and would create a flaky gate.
3. The G6 gate must pass on all three platforms (Windows x64, Linux x64, macOS ARM64)
   with the expanded answer keys.

QA must review and approve the expanded answer keys before the PR is opened.

---

### AC-IS-3 — 13-second timing budget preserved on all platforms

The decode cycle elapsed time, as reported in the Information log line, must remain within
the budget defined in FR-026 / the ft8-decoder spec.

| Platform | Hard limit (per spec) | CI limit (per spec) |
|---|---|---|
| Development machine | 13 000 ms | — |
| CI runner | — | 30 000 ms |

A second decode pass adds wall-clock time. The Architect must confirm that the second
pass completes within the remaining budget after the first pass. If the first pass
currently consumes ~2–3 seconds, the budget is comfortable. If edge cases (30+
simultaneous signals) push the first pass to 8–10 seconds, the second pass may not fit.
Characterise this before implementation, not after.

The existing `Ft8DecoderPerformanceTests` timing assertions must remain green.

---

### AC-IS-4 — Iteration count is bounded and configurable

The subtraction loop must not run indefinitely. The implementation must enforce a maximum
number of passes (suggested default: 2 passes total — one first pass, one residual pass,
matching WSJT-X behaviour). The maximum pass count must be:

- A named constant, not a magic number.
- Logged at Debug level per cycle: `"iterative subtraction: pass {n} of {max}, {k} new decodes"`
- Applied consistently across all platforms.

---

### AC-IS-5 — No new platform dependency introduced

The three-platform CI matrix must pass without introducing an additional native binary,
build tool, or system library. If Path A is taken, the ft8_lib fork (already a dependency)
is the only C component; no new library is added.

---

### AC-IS-6 — Phase 2A exit criteria formally closed

`RECOVERY_PLAN.md` must be updated in this change to record:

- That Phase 2A exit criteria have been satisfied.
- The achieved recovery rate (from the replay harness measurement).
- The date and the change that achieved it.

This is a documentation obligation, not optional housekeeping.

---

### AC-IS-7 — Design document must specify architectural path with rationale

The change design document must address:

1. Which of the three architectural paths (A, B, or C) was selected.
2. Why the other paths were rejected.
3. How signal energy is located in the spectrogram/PCM for subtraction.
4. How the iteration termination condition is determined.
5. What "parity" means numerically for this project — i.e., what recovery rate the
   Architect considers acceptable as a long-term steady state.

QA will not approve a change proposal that omits these.

---

## 6. Dependencies — what must be resolved first

| Dependency | Document | Status |
|---|---|---|
| Submodule fork (MSVC patches committed) | DEV-ALIGNMENT-2026-05-31.md — B1 | **BLOCKING** |
| Stale comments in RealSignalFixtureTests.cs | DEV-ALIGNMENT-2026-05-31.md — C1, C2 | Before next PR |
| Decision-gate logic in ReplayHarnessTests.cs | DEV-ALIGNMENT-2026-05-31.md — C3 | Before next PR |
| findings.md footer updated and committed | DEV-ALIGNMENT-2026-05-31.md — C4 | Before next PR |

The submodule fork is a hard dependency if Path A is chosen. Do not begin implementation
until B1 is resolved.

---

## 7. Suggested change identifier

`p15-iterative-subtraction` — opened after B1 through C4 are cleared.

FR-030 (logging hot-reload) was previously considered p15. It should be re-sequenced to
`p16-logging-hot-reload`. The iterative subtraction gap is a correctness issue against a
SHALL requirement; it takes precedence.

---

## 8. What QA will verify at review

- Replay harness results file (findings.md regenerated with new numbers).
- Expanded `.expected.txt` answer keys — QA approves each addition individually.
- The design document answers all six questions in AC-IS-7.
- Timing test results on all three platforms.
- The iteration count constant is named, not a literal.
- `RECOVERY_PLAN.md` is updated per AC-IS-6.
- The submodule pointer in the superproject reflects a committed fork, not uncommitted
  working-tree patches.

---

*QA sign-off required before this change may be opened as a PR.*  
*Product decision recorded: 2026-05-31.*
