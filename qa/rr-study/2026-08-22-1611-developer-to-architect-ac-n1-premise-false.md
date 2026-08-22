# Developer → Architect/QA: AC-N1 regression check's own premise is false

**2026-08-22 16:11 UTC** · Developer session, `/opsx:apply fix-negative-time-offset-snr-collapse`,
branch `fix/negative-time-offset-snr-collapse`. Escalating per the Captain's explicit
direction (asked, mid-session, whether to accept the mechanical evidence and proceed or
stop for review — Captain chose stop).

## Where this sits in the change

Sections 1-5 of `tasks.md` are complete and locally verified (native fix applied per
design.md Decision 1; `FT8_SHIM_VERSION` bumped 20260045→20260046; win-x64 + linux-x64
binaries rebuilt and SHA256-recorded, osx-arm64 deferred by Captain's separate decision;
`Ft8LibInterop.cs` updated; `dotnet build`/`dotnet test` clean, `OpenWSFZ.Ft8.Tests.dll`
317/317, G6 gate 3/3). Section 6 (AC-N1 replay regression) is where this finding surfaced.
**Section 7 (B-dt-C3 acceptance re-run) has NOT been started** — stopping before it per
the Captain's instruction.

## The finding

`proposal.md` (§What Changes, bullet 5) and `tasks.md` §6.1 both state the eight committed
`qa/rr-study/r2-coherent-llr-instrument/results/replay_*.json` corpora have **"every
recorded decode `time_offset >= 0`"**, and frame the regression check on that basis: replay
the same window against the fixed binary and expect **zero** differences, with any
difference read as proof the fix's arithmetic is wrong even on the branch it claims not to
touch (`tasks.md` §6.2's literal stop condition).

That premise does not hold. I replayed the same window (`WINDOW_20M`, 250 cycles,
`260808_004000`..`260808_014215`, `start_index=0` — identical to the eight committed files)
against the freshly rebuilt 20260046 binaries on both platforms:

- **win-x64**: rebuilt DLL, SHA256 `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`
  → `qa/rr-study/r2-coherent-llr-instrument/results/replay_win_negdt_fix.json`
- **linux-x64**: rebuilt `.so` (via WSL2 Debian, GCC 14.2.0 — no git available there, so
  I mirrored CI's clone+overlay recipe using this repo's own `native/ft8_lib_vendor/` tree,
  which is byte-identical to the `msvc-compat` branch's unpatched upstream sources per
  `PROVENANCE.md`), SHA256 `9394a8e3bf7578428f08ad71be95385f29605c3966e20d4b2e3b6a47c5267386`
  → `qa/rr-study/r2-coherent-llr-instrument/results/replay_linux_negdt_fix.json`

Diffed each against its platform's committed pre-fix reference
(`replay_{win,linux}_amend2.json`, shim 20260045) using the existing
`qa/cycleframer-alignment-replay/r0_ac1_ac2_diff.py` plus a small ad-hoc analysis script
(not committed, shown below) to classify every differing entry by sign of `dt`.

**Mechanical result, both platforms, exactly:**

| | win-x64 | linux-x64 |
|---|---|---|
| Cycles differing | 85 / 250 | 85 / 250 |
| Same 85 timestamps on both platforms? | yes (verified: identical `set()`) | |
| Entry-level diffs where **both** sides have `dt >= 0` (should be 0 per the fix's own invariant) | **0** | **0** |
| Entry-level diffs involving a **negative** `dt` | 95 | 95 |
| Of those, diffs where `dt`/`freq_hz`/`message` also changed (would mean non-SNR corruption) | 0 | 0 |
| Of those, diffs where **only `snr`** changed | 95 | 95 |
| `snr` delta range observed | 1-15 dB | (same entries, not separately re-measured) |

In plain terms: **every single difference, on both platforms, is an SNR-only change on a
candidate that already had a negative `dt` before the fix** — i.e. the real 20m off-air
corpus this "regression" window was drawn from already contains early-arriving
(`time_offset < 0`) decodes, contrary to the stated premise. Zero decodes were added,
removed, or changed in message/frequency/DT. Zero `dt >= 0` decode was touched. This is
structurally identical to what B-dt-C3 predicts a correct fix should do — it is just
happening on real traffic instead of a synthesized sweep, and the magnitude (1-15 dB
rather than B-dt-C3's headline 17.4 dB) is consistent with these being much weaker,
marginal real decodes (several already at -20 to -27 dB pre-fix) where the "right vs
wrong tone bin" distinction matters less against noise than it does for B-dt-C3's own
strong synthesized signal.

## Why I stopped instead of just proceeding

`tasks.md` §6.2 is a **pre-registered gate** with its own literal stop condition, and it
fired (85 ≠ 0 cycles differ). The evidence strongly suggests the gate's own *premise*
(no negative-`dt` decodes in this corpus) was wrong, not that the fix's arithmetic is
wrong — but reinterpreting a QA/Architect-authored pre-registered gate's premise, and
deciding it's safe to proceed past a literal stop condition, is a call this project's
process reserves above a Developer session (this mirrors the spirit of HK-021(k)/HK-025:
a precondition turning out false doesn't let the person running the check unilaterally
wave the gate through). I asked the Captain how to proceed; the Captain's instruction was
to stop here and escalate rather than accept the evidence myself.

## What I have NOT done

- Not run §7 (B-dt-C3 acceptance re-run against the fixed binaries).
- Not marked §6 complete in `tasks.md` — left as an open finding (see that file's own
  annotation at §6.1/6.2).
- Not touched `proposal.md`/`design.md`/the spec deltas' wording about the AC-N1 corpus's
  `time_offset >= 0` premise — that correction, if wanted, is an artifact-authorship call,
  not mine to make unilaterally either.
- Not pushed or merged anything (HK-014). Two commits are staged locally on
  `fix/negative-time-offset-snr-collapse` per the Captain's earlier branching decision
  (one for the pre-existing r2-coherent-llr-instrument Amendment 2/3 work already sitting
  uncommitted in the working tree, one for this fix's own §1-6.1 work) — not pushed.

## Suggested next step (not a decision, just a pointer)

If the Architect/QA read of this evidence agrees it's the fix working as intended on a
corpus whose real-world content simply doesn't match the proposal's stated assumption,
the likely fix is a **wording correction** to `proposal.md`/`tasks.md` §6 (the AC-N1
premise and what "regression" means here — probably reframing the check as "zero diffs
on `dt >= 0` entries, SNR-only diffs permitted on `dt < 0` entries" rather than "zero
diffs, period"), followed by resuming at §7. That rewrite is an Architect call, not this
session's to make.

## Supporting files (uncommitted, this session's own output)

- `qa/rr-study/r2-coherent-llr-instrument/results/replay_win_negdt_fix.json`
- `qa/rr-study/r2-coherent-llr-instrument/results/replay_linux_negdt_fix.json`
