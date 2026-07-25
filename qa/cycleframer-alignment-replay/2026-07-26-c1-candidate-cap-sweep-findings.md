# D-001 C.1 — candidate-cap sweep findings

**Author:** Developer session (HK-011), 2026-07-26. **For:** QA/Architect (per HK-000/HK-015 —
Dev reports up to QA, not directly to the Architect/Captain).
**Source:** `dev-tasks/2026-07-26-d001-candidate-cap-sweep.md`.
**Build under test:** worktree branch `d001-c1-candidate-cap-sweep`, off `main` @ `3c82fd0`.

---

## 1. Prerequisite: the §2 stack-safety fix

Applied before any cap value was tested. `ft8_shim.c`'s pass-loop local `candidates[]` array was
hardcoded to `K_MAX_CANDIDATES_PASS2` (200) on the assumption that 200 is always the larger
per-pass cap — true only while `K_MAX_CANDIDATES <= 200`. Added `K_MAX_CANDIDATES_ANY_PASS =
max(K_MAX_CANDIDATES, K_MAX_CANDIDATES_PASS2)` and resized the array to it. At the shipped
`K_MAX_CANDIDATES = 140` this is a behavioural no-op (verified: rebuilding at 140 with the fix
applied reproduces the reference figure — 1288 decodes, `hashTableRejectCount` 595 — byte-for-byte
identical to the pre-fix build). **`FT8_SHIM_VERSION` was NOT bumped** for this fix, since it has
zero effect at the currently-shipped constant; this is recorded in `win-x64/libft8.version.txt`
and the commit message.

Without this fix, 300/600 would have silently overrun a 200-element stack array on pass 0 — the
sweep below would not be trustworthy.

## 2. Method

Three native rebuilds (`K_MAX_CANDIDATES` ∈ {140, 300, 600}, pass 0 only —
`K_MAX_CANDIDATES_PASS2` untouched throughout), each re-decoding the same fixed 68-cycle corpus:
the **filename-matched intersection** of `artefacts/20260725_live_run_1806/owsfz/wav/` (84 files)
and `.../wsjt-x/wav/` (75 files) — 68 files — via `qa/rr-study/d001-param-sweep-2026-07-22`
at `--points k10_c0.10_n60 --dial-mhz 7.074`. The 140 baseline reproduced the reference figure
(1288 decodes) from `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §1 exactly, confirming
harness/corpus setup before trusting the 300/600 deltas.

**Pitfall hit and corrected:** the harness's native DLL is a `Content` item copied to the build
output only during an actual `dotnet build`; `dotnet run --no-build` does not refresh it. The
first 300/600 attempts silently ran against the stale 140 DLL (pass-0 candidate counts stuck at
exactly 140 and identical 1288-decode totals gave this away). Re-ran both after an explicit
`dotnet build` between each native rebuild; `hashTableRejectCount` changing between runs (595 →
690) and pass-0 candidate counts genuinely exceeding 140 (161–295) confirmed the correct binary
was loaded for the reported numbers below.

**Deviation from "harness unmodified" (§3.5):** added an opt-in `--debug-log` flag to
`qa/rr-study/d001-param-sweep-2026-07-22/Program.cs` (default off — zero behavioural change for
every other caller). When set, one `ILogger<Ft8Decoder>` per grid-point directory writes
`<out-dir>/<point>/decode.log`, formatted to match `ldpc_stats.py`'s `RE_LLR`/`RE_PASS`/`RE_DEC`
regexes exactly (`{yyyy-MM-dd HH:mm:ss.fff} +00:00 [LVL] {message}`, mirroring Serilog's default
`{Level:u3}` template), via a `SwitchablePointLogger<T>` that repoints to the current grid point's
writer before each decode — needed because the harness's `sharedDecoder` is constructed once and
reused across every WAV/grid-point in a run.

## 3. Results

All figures over the same 68 matched cycles. `failCands`/`meanAbsLLR`/`prenormVar` are pass-0
only (mirrors `ldpc_stats.py`'s "pass 1" = pass-index-0 convention), aggregated median/mean per
`ldpc_stats.py`'s existing methodology.

| setting | total decodes | Δ vs. 140 | pass-0 candidates (median) | failCands (median/mean) | meanAbsLLR (median/mean) | elapsed ms (median/p90) |
|---|---:|---:|---:|---:|---:|---:|
| 140 (baseline) | 1288 | — | 140.0 | 90.0 / 91.43 | 4.067 / 4.0665 | 660 / 972 |
| 300 | 1300 | **+12 (+0.93%)** | 220.0 | 166.5 / 167.29 | 4.081 / 4.0791 | 745 / 1036 |
| 600 | 1300 | **+12 (+0.93%)** | 220.0 | 166.5 / 167.29 | 4.081 / 4.0791 | 749.5 / 827 |

300 and 600 produce **byte-identical decode sets** (diff of sorted `ALL.TXT` = 0 lines). Pass-0
candidate counts never exceed 295 even with an array sized to 600 — the real candidate population
in this corpus caps out around ~220–295, well short of either raised ceiling. No crash or hang at
600 (exit code 0, all 68 WAVs decoded; confirms the §2 fix holds at 4.3× the shipped cap).

## 4. Interpretation

**Neither of the dev-task's two clean branches fits exactly.** Decodes did rise (not flat), but
only marginally (+12 of the 751-decode D-001 gap ≈ **1.6% of the total gap**, or ~1.6% of the
740-decode decoder-attributable share). `failCands` nearly doubled (90 → 166.5 median) in lock
step with the candidate-count rise, while `meanAbsLLR` stayed essentially flat (4.067 → 4.081) —
the additional ~80 candidates found beyond 140 are overwhelmingly the same low-confidence
population the existing 140 already contains plenty of, not a materially higher-quality set that
LDPC was being denied. A small number (12) do carry a real signal and get through; the
overwhelming majority do not.

**This does not contradict the 98.5%-decoder decomposition in
`2026-07-26-0015-d001-consolidation-and-clean-slate.md` §1 — it refines it.** Of the
740-decode decoder-attributable share, this experiment accounts for 12 (1.6%); the remaining
~728 (98.4% of the decoder share) is untouched by raising this cap and routes to C.2
(LDPC/LLR-normalisation), per §7 of the dev-task. No escalation to the Architect is warranted; this
is confirmatory, not a contradiction.

**Timing:** no budget concern at any setting. Median/p90 stayed in the 660–1036 ms range
(15 s production budget), even at 600 — the dev-task's speculative "~4× pass-0 work" scenario did
not materialise, because the real candidate population plateaus around ~300 regardless of the
array ceiling offered to it.

## 5. Recommendation

**Do not change the shipped `K_MAX_CANDIDATES` default (140) as part of this branch.** The
committed `src/` state on this branch is: the §2 stack-safety fix (behaviourally a no-op at 140,
verified) + `K_MAX_CANDIDATES` left at 140. 300 is a safe, zero-cost, small win (+12 decodes,
no timing or stability cost, plateaus there — 600 adds nothing further) and could reasonably be
adopted in a separate, deliberate follow-up with its own Captain sign-off (HK-011/HK-010), but a
1.6%-of-gap recovery does not on its own justify bundling a shipped-constant change into this
diagnostic branch. QA/Architect should decide whether that follow-up is worth scoping given C.2 is
likely to dominate.

## 6. Cross-references

- `dev-tasks/2026-07-26-d001-candidate-cap-sweep.md` — the task spec this executes.
- `qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md` §1 —
  the decomposition this refines.
- `qa/cycleframer-alignment-replay/ldpc_stats.py` — the aggregation methodology mirrored here.
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — rebuild provenance note for this branch.
