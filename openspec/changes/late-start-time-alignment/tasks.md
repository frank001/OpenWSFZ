## 1. Tests first (each must be able to fail; inject `TimeProvider`, no unbounded sleeps)

- [ ] 1.1 **T1 helper table:** t = 0, 0.62 and 2.36 s: the full buffer, 606,720 samples loaded, identical to the input.
- [ ] 1.2 **T2 just past whole:** t = 2.37 s: 89,760 skipped, 516,960 loaded; **the first loaded sample equals input[89,760]** (the start is cut, not the tail).
- [ ] 1.3 **T3 the #257 L-2 case:** t = 4.9 s: 211,200 skipped, 395,520 loaded; the first loaded sample equals input[211,200].
- [ ] 1.4 **T4 last start:** t = 11.24 s: 515,520 skipped, 91,200 loaded.
- [ ] 1.5 **T5 cut-off:** t = 11.25 s and t = 14.9 s: nothing loaded, PTT never keyed, one Information log line.
- [ ] 1.6 **T6 manual engage past the cut-off:** an answerer pending target, an answerer jump-in and a caller pending responder, each consumed at 12 s into a correct-phase window: not fired, retained, and fired in the next correct-phase window.
- [ ] 1.7 **T7 manual engage late but before the cut-off:** the same three at 5 s and 6 s (today's D-CALLER-021 A and C cases): fires immediately, aligned as T3.
- [ ] 1.8 **T8 existing tests:** the D-CALLER-021 G case (8 s in) and the caller's 9 s case are rewritten to the new rule (8 s: 360,000 skipped, 246,720 loaded); the H/I cases and the retry-budget tests J stay; all green.
- [ ] 1.9 **T9 regression:** the full unfiltered suite.
- [ ] 1.10 The new offset check at the fire sites and in `TransmitAsync` reads `_timeProvider.GetUtcNow()`, not `DateTimeOffset.UtcNow` (design decision 2); the tests use the existing test-only arming helpers.

## 2. Implementation

- [ ] 2.1 `Ft8TimeHelper`: the helper of design decision 1; the existing clamp stays and is applied after the skip.
- [ ] 2.2 `QsoAnswererService.TransmitAsync` and `QsoCallerService.TransmitAsync`: call the helper; the Information log lines (design decision 5); a transmission not keyed at t >= 11.25 s keeps today's zero-remaining accounting (the Developer states in the commit what that is).
- [ ] 2.3 The three fire sites: retain at t >= 11.25 s (design decision 4).
- [ ] 2.4 No ramp on the cut start (design decision 7); the commit says so. Nothing in `LateBatch`, the synthesiser or `native/`; `git diff --stat` confirms.

## 3. Verification

- [ ] 3.1 `dotnet build`, the **full unfiltered** `dotnet test OpenWSFZ.slnx`; `openspec validate --all --strict`; quote the exact command lines and counts (HK-022).
- [ ] 3.2 `VERSION` bump per G9b (user-facing: yes) from the `origin/main` value, README and REQUIREMENTS anchors set to the same version in the same commit; `python tools/check_version_docs.py` (G9a). Commit before running `check_version_bump.py`.
- [ ] 3.3 The Developer does not push, merge or run `pre_merge_check.py` on its own initiative. QA reviews (HK-039) including the mutation (tail truncation restored: T2, T3 and T4 must fail; T1 passes either way), runs `pre_merge_check.py` on a clean checkout of the exact tip BEFORE any push, then asks the Captain for the push go; the merge is his.
- [ ] 3.4 Offline (QA, `sol`): the decodability grid H3 of the Architect's spec: styles O (today), A (aligned) and M (descriptive, no code), t in {0.62, 1.5, 2.36, 3.5, 4.9, 6.5, 8, 10} s, -8 and -16 dB, 5 seeds; the audio placed by sample offset in a 15 s buffer with every WAV cross-correlated against the DT = 0 render before decoding (M1); gates G1 (O at 4.9 s, -8 dB: 0/5, else stop) and G2 (A at 3.5 s, -8 dB: at least 4/5).
- [ ] 3.5 Live acceptance (the Captain at the radio, on his say-so; each step starts a QSO): L-1 a late double-click more than 3 s into the slot, the log line shows the offset and the skip, PTT ends about 13.1 to 13.4 s into the slot; L-2 the on-time transmissions in the same QSO load the full 12.64 s with no late-start line; descriptive: whether the other station answered.
