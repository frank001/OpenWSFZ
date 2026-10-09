# QA readiness note: the offline flag-OFF/ON replay of the 4 299 archived cycles, ahead of your spec

- **To:** Architect (cc Captain)  **From:** QA  **Date:** 2026-10-01 ~19:50Z
- **Status:** NOTHING BUILT OR RUN. This is a survey of what exists and a proposed shape, so your pre-registered spec can be written against real tooling and QA can start the moment it lands. Per the Captain's 2026-10-01 decision (item 6, option B: "draft the harness in parallel so it is ready").
- **Source of the task:** your ruling `2026-10-01-1500-architect-sub-feas-first-on-air-run-ruling.md` §3 (the five constraints). QA does not set a bar, a threshold or a verdict here; those are yours.

## 1. The five constraints, and how QA would meet each

| # | Your constraint | QA's reading and plan |
|---|---|---|
| 1 | Same build `247ac391`, same shim `20260056`, same pinned DLL SHA, flag the only difference; fresh process per arm; numeric ordered; 8 workers; `nhard` 40 | The on-air build is `247ac391` with `libft8.dll` `ee00d118…990e4c`. `main` now carries shim 20260056 too, but **QA will pin the harness to the DLL SHA, not to a branch name**, and assert actual == pinned at start and end (the "shim version identifies nothing" rule). Fresh process per arm, arms run back to back on the same machine state; `subtractionMaxThreads` 8 pinned and asserted; `nhard` 40 asserted from the config. |
| 2 | Reference is the live WSJT-X `ALL.TXT` for the same cycles; estimand = NET change in matched decodes OFF→ON, paired per cycle, OFF replay as the control | NET = (matched_ON − matched_OFF) over the same cycles, **both arms replayed**, so the replay artefact (the original-PCM replay alone gave 0.76 pp) cancels. Reference: `artefacts/20260930_1930_endurance_run-gathered/wsjt-x/ALL.TXT`. |
| 3 | Honest scope: a second night, same band and station, not a second band | Will be stated at the head of the report, in the words of your point 3. |
| 4 | Replay is not the live path (`ALL.TXT` is post-plausibility and post-dedup); compare outcome fields, never rendered text; HK-037: aggregates only | Both arms go through the same managed path, so the comparison is replay-vs-replay on outcome fields. The WSJT-X match is done by the **strict route** already used for Test B: the message text stays in one process's memory, WSJT-X's `ALL.TXT` is read in that same process, and only counts and stamps are written (per cycle, per SNR band). No text, callsign or text hash in any output file. |
| 5 | CPU is shared: no overlapping test suites or builds during the replay timing | See §4: the ON arm is hours of exclusive CPU; it needs a window the Captain gives, with the Developer and Engineer idle and nothing else running. |

## 2. What already exists (reuse map; all tracked on `main` since #196 unless noted)

| Need | Existing piece | State |
|---|---|---|
| Replay real cycles through the managed decode, both flag states | `qa/rr-study/sub-feas/replay81/Program.cs` with `replay81_run.py` / `replay81_rows.py` (the §8.1 and S1/S2 harness); `run_e1.py`, `select_e1.py` | Built and used on 905 and 161 cycles. Needs a cycle list of **all 4 299** and a per-arm output of decode outcome fields. |
| Match decodes to WSJT-X in memory, strict route, per cycle and SNR band | `testb_run.py` / `testb_rows.py` (Test B) | Used on the 161 E1 cycles. The match rule there: same message text, same cycle, within 10 Hz, paired one-to-one nearest-first; SNR bands A ≥ 0, B −10..−1, C −15..−11, D ≤ −16 dB. |
| Flag-OFF vs flag-ON comparison scripts | `flagoff_control.py`, `flagoff_managed_compare.py` | Compare outcome files byte for byte (numeric, ordered). Reusable for the "flag OFF replay equals the live path's flag-OFF" sanity check. |
| The archived audio | `artefacts/20260930_1930_endurance_run/cycle-audio/` (**4 300 WAV files**; 4 298 residual-pass lines in the daemon log; the 2 extra are the window-edge cycles, which the report already explained) | Gitignored data on this machine only. |
| The references | `…-gathered/wsjt-x/ALL.TXT` (live WSJT-X) and `…-gathered/owsfz/ALL.TXT` (OpenWSFZ live) | Gitignored. HK-037: read only inside the matching function. |
| Pre-registration and numeric-only output discipline | The Test B and S1/S2 reports; `preflight.json` pattern | Reuse the pre-flight checks (DLL SHA pinned, flags asserted, WSJT-X closed or not recorded). |

## 3. Gaps QA sees (decisions needed in your spec, not for QA to guess)

1. **The cycle set.** All 4 299 archived cycles (the Captain's wording) or exclude the 2 window-edge cycles and any cycle whose WAV is missing, clipped or has no WSJT-X window? QA proposes: all with a WAV and a WSJT-X cycle record, edge cycles excluded and counted.
2. **Paired estimand and its interval.** Per cycle, d_i = matched_ON,i − matched_OFF,i. Cycles are autocorrelated (band activity), so a plain cycle bootstrap understates the interval. QA proposes a **block bootstrap over contiguous cycle blocks** (e.g. 40 cycles = 10 min), but the block length is a registered choice, not QA's. Which denominator for the "pp": matched / WSJT-X decodes in the same cycles, as in Section 4 of the ANOVA?
3. **"Matched" definition.** Same as Test B (text, same cycle, 10 Hz, one-to-one) or the ANOVA's `match_pairs`? They differ in tolerance and tie-breaking; the report must use one and say which.
4. **Which decodes count in the ON arm.** `DecodeTwoStageAsync` batch 1 + batch 2 together (the union, what the operator eventually sees), with batch 1 equal to the OFF arm as already proven (S1 PASS 161/161). QA proposes the union, reported also split by batch.
5. **A negative control.** OFF-vs-OFF run twice (or replay vs the live OWS decodes of the same cycles) would show the noise floor of the paired estimand and any non-determinism. Cost is ~0.6 h; worth registering.
6. **WSJT-X contention.** The live night had WSJT-X resident, the replay will not. Both arms are replayed without it, so the NET is unaffected; say so explicitly.
7. **The false-positive question stays separate.** Test B (97.1 % of the 161-cycle extras corroborated, 20 not) is a different instrument. QA proposes the replay reports, as descriptive aggregates only, the not-corroborated rate of the ON-arm extras per SNR band over all 4 299 cycles; whether to register a bar on it is your call.

## 4. Cost and scheduling (estimates, labelled as such)

From the on-air record (pass p50/p95/max 5 001 / 6 423 / 9 421 ms at 8 workers, WSJT-X resident) and the first-pass profile (≈ 0.5 s): the **ON arm ≈ 4 299 × (0.5 + ≈ 5) s ≈ 6.5 h**, the **OFF arm ≈ 4 299 × 0.5 s ≈ 0.6 h**, a negative control another ≈ 0.6 h: **about 8 h of exclusive CPU**, run sequentially (the pass already uses 8 workers). It cannot overlap anything CPU-heavy; QA would propose an overnight window, detached supervised run (HK-013, HK-023), tear-down and orphan check (HK-019). Memory and flags sampled as in the on-air arm.

## 5. What QA needs from you

1. Your pre-registered spec (constraints 1 to 5 as ruled, plus the choices in §3).
2. Whether the **negative control** (§3.5) is in or out.
3. A go from the Captain for the overnight window (CPU).

## 6. Risks QA already sees

- **Same audio?** The report accepted that the two decoders heard the same 40m audio (matched-pair frequency means 1 482.4 vs 1 482.3 Hz); the open pre-flight item `wsjtx_ini_dial_freq_matches_daemon: false` is unresolved and the replay inherits it.
- **One night, one band, one station:** the ruling already says so; the NET cannot generalise beyond that.
- **Replay vs live path:** a raw replay is not the live path (post-plausibility, post-dedup `ALL.TXT`); handled by comparing replay-to-replay.
- **Build drift:** after the `decoding_improvement` sync the build differs from `247ac391`; the replay must run on the pinned DLL regardless, and the arm label must say so.
