# Developer task: COH-FB-AUDIO B1, the fallback-audio config key (Original | Residual | Both)

**To:** Developer · **From:** QA · **Date:** 2026-10-27 19:44:23Z (`date -u`) · **Base:** `origin/main` `453d3d02` (v0.65) · **Branch:** `dev/coh-fb-audio` (new, from `origin/main`; reuse your `dev/coh-fb-residual` work, `e5b90320`, by cherry-pick or by hand)
**Spec (read §5, §5a, §5b):** `git show fc642fe2:qa/rr-study/2026-10-27-1818-architect-to-qa-coh-fallback-residual-replay-spec.md` (Architect, branch `arch/coh-fallback-residual`, local).
**Authority:** the Captain's decision of 2026-10-27 (spec §5b, his words quoted there): the residual-audio fallback becomes the product default with no bar, and "both audios" is to be measured. This is a product change that goes to `main` by the normal path: QA review (HK-039), `pre_merge_check.py` from a clean checkout (HK-006), his push go (HK-033), his merge sign-off (HK-010). **You do not push.** The OpenSpec change (proposal, design, tasks) is QA's to write; do not create one.

## What to build

1. **Config key** `decoder.coherentFallbackAudio`: an enum `Original | Residual | Both` on `DecoderConfig` (`src/OpenWSFZ.Abstractions/DecoderConfig.cs`), in the style of `DecodingDepth` and `CoherentFallbackMultiSet`: constructor parameter, init property with doc comment, JSON as the enum NAME, case-insensitive on read as the existing enums are. **An absent key reads `Residual`.** An explicit value is kept. Config file and API only; **no Settings-page control** in this step. Plumb it like `SetDecodingDepth` (`Program.cs:805` initial, `:910` on change): read once per window, effective on the next window. HK-035: the config POST is an overlay on `main`; show a test that posting `{decoder:{coherentFallbackAudio:"Both"}}` changes only that key. An invalid value: follow the existing enum validation (state what it does; do not invent a new behaviour).
2. **Remove the env switch** `OPENWSFZ_COHFB_AUDIO` and `CohFallbackAudio.IsActive/EnvironmentVariable`; the key is the only control. Keep the `Select()` step-down logic (third pass `ran` → residual3; else residual pass completed → residual2; else unavailable → original audio), it is what the probe measured.
3. **`Original`** = `main` today, byte-identical (same `normalisedPcm` reference, same log text except the new field, below).
4. **`Residual`** = the probe's RES mode, unchanged (the build `e5b90320`, RES arm).
5. **`Both`** (new): with the same candidate snapshot, run the fallback on the original audio AND on the step-down residual buffer, then **merge the two result sets by payload before `CoherentFallbackSelector.Select`** and publication. Where both runs found the same payload, **keep the residual row** (its SNR/DT are measured with the neighbours removed). One shared fallback budget (the existing `budgetMs`; the 13 s ceiling is what matters), one batch 4, one per-cycle text de-duplication exactly as now. Sequential or parallel is your choice; say which and why, and state the worst-case wall time you expect (the probe's fallback wall was median 252 ms / max 605 ms on the original audio, 334 / 608 ms on residual, 8 workers; `Both` runs it twice). If the budget runs out between the two runs, define and document what is published (QA's expectation: whatever completed, counted as abandoned, as today). When the residual is unavailable (the step-down reached the original audio), `Both` must not run the same audio twice: say what you do and log it.
6. **Log line** (`Coherent fallback:`), the field currently `audio=` at the end: `audio=original|residual3|residual2|residual-unavailable` for the three modes as in the probe, and in `Both` `audio=both(<level>)` where `<level>` is `residual3|residual2|unavailable`, followed by `fromOriginal=N, fromResidual=N, inBoth=N` (payload counts after the merge: found only on original / only on residual / on both). Keep it a trailing group so every existing parser is untouched; QA updates Replay81's regex.
7. **VERSION**: minor bump from 0.65. Update every place the gate checks (last time `REQUIREMENTS.md` was missed, #266 R-1); run `check_version_bump.py` and the G9a/b gates yourself before you report.
8. `native/` must stay unchanged: report `git diff --stat origin/main -- native` (empty) and the `libft8` DLL SHA-256 (pin `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`).

## Tests (xUnit; no fixed delays, TESTING_STRATEGY §11)

- Absent key → `Residual`; explicit `Original` / `Residual` / `Both` round-trip through the config file and the API; the overlay test above.
- The `Both` merge as a pure function on a fixed pair of result sets: exactly one row per payload; the residual row wins where both found it; counts `fromOriginal` / `fromResidual` / `inBoth` correct; empty inputs.
- `Select()` cases from the probe kept (available/unavailable, abandoned, contained exception).
- Decoder-level: `Original` hands the fallback the same reference as `normalisedPcm`; `Both` calls the fallback with both buffers once each, or once with the original when the residual is unavailable.
- Full Windows suite; report the counts. The existing `CoherentFallbackWiringTests` assertions on the log tail will change with the new fields.

## R0 (before QA's replay; you produce the evidence, QA checks it)

On the same 20 cycles of night `20260925_2010` (selection `81372df5`, `FULL[:20]`, warm-up kept; your `selection20.json`), mechanical diffs with `r0_diff.py` as before:
- `Original` vs `origin/main` `453d3d02` (build it in a detached worktree under `_qa-scratch\coh-fb-residual\`): byte-identical, only the new trailing `audio=original` allowed to differ.
- `Residual` vs the probe build `e5b90320` RES arm on the same 20 cycles: byte-identical, only the label text allowed to differ if any. (A 20-cycle RES output of `e5b90320` is not on disk; run it, with the env switch.)
- Pin the `libft8.dll` SHA-256 at the start and end of each arm. Check `tasklist` for `OpenWSFZ.Daemon|wsjtx|jt9|Replay81` before you start (the station daemon is stopped; the sol chain runs on sol, not here). The PC is yours until you report.
- No callsign text in anything committed (NFR-021); rows only under `_qa-scratch`.

## Report back (HK-001 sections), then STOP

Commit hash on `dev/coh-fb-audio`; points 1 to 8 answered with file:line (especially the `Both` design choices in 5); test counts; R0 evidence. **Do not push.** QA reviews (HK-039 record as a `*code-review*.md` FILE), then runs the three B2 arms.
