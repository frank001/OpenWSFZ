# Developer task: COH-MULTISET-BUILD, default ON (`decoder.coherentFallbackMultiSet` is true when its key is absent)

**Date:** 2026-10-25
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the Captain, 2026-10-25, first-hand in the Architect's window: *"default on confirmed"* (Architect build spec §17, commit `1cae03f9` on `arch/coh-multiset`; QA has asked him to confirm it in QA's window as well). Basis: the decision replay, spec §16 (final): NET **+1.449 pp [1.339, 1.568]** against the Captain's D_bar 0.5 pp (D-GO), ΔU′ **+0.00486 per cycle [0.0021, 0.0080]** against his U′_bar 0.021 (U′-OK), validity rows V1 to V8 all PASS. Report: `qa/rr-study/results/2026-10-25-coh-multiset-build-replay/report.md` on `qa/refset` (`551bcff7`).
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative** (QA runs it on a clean checkout of the exact commit before any push).
**Branch:** `feat/coh-multiset-build` (a second change on top of `d7750bde`; the Stage 1/Stage 2 work is not merged yet, so this is one more commit on the same branch). Never commit to `main`.
**OpenSpec change:** `openspec/changes/coh-multiset-build/` was **amended** on QA's branch `qa/refset` (proposal, design decision 14, spec requirement, tasks section 4): copy the four files onto your branch unchanged in your first commit (`git show qa/refset:<path>` per file). `openspec validate --all --strict` must stay clean.
**Version:** the proposal now says `User-facing: yes` (a default behaviour changes), so gate G9b requires `VERSION` to differ from `origin/main` (0.62 today): **bump to 0.63** (re-check `origin/main` first) and update whatever else carries the version; confirm with `python tools/check_version_bump.py origin/main`. The shim version stays **20260071**.
🛑 **Licence (Captain, 2026-10-24):** method only. No WSJT-X source is opened, copied or ported. Nothing in this task needs any.

---

## 0. What changes, in one paragraph

When the saved configuration has no `coherentFallbackMultiSet` key, the multi-set walk is now ON. An explicit `false` still turns it off, exactly as before. That is all. Same pattern as the Deep decoding-depth default (#240): key absent means the new default.

## 1. Scope (line numbers at `d7750bde`; re-find them, they may have moved)

1. `src/OpenWSFZ.Abstractions/DecoderConfig.cs:54`, the constructor parameter `bool coherentFallbackMultiSet = false` becomes `true`.
2. `src/OpenWSFZ.Abstractions/DecoderConfig.cs:253`, the property initialiser `{ get; init; } = false;` becomes `true`; its doc comment (`:246-252`) says what is true now (ON when the key is absent, `false` turns it off, still acts only when `CoherentFallbackEnabled` is true, no Settings control, the POST is an overlay).
3. `src/OpenWSFZ.Daemon/Program.cs:808`, the comment `// COH-MULTISET: default false` says `default true`.
4. `src/OpenWSFZ.Ft8/Ft8Decoder.cs:219` (and `:216`), the doc comment on `SetCoherentFallbackMultiSet`: it describes the decoder object's own value at construction (`false`) separately from the configured default; say precisely what is true. **Whether `_coherentFallbackMultiSet` at construction (`:216`) and the native context's own construction default also change is your call, with QA reviewing it.** The daemon calls `SetCoherentFallbackMultiSet(initialDecoder.CoherentFallbackMultiSet)` before the first cycle (`Program.cs:808`) and again on every config change (`:912`), and the managed side sets the bit on every context before each cycle's `_process` calls (A1.1), so the configured default is what decides behaviour. A1.1's statement "a new context defaults to off natively" is about the native context and need not change.
5. **No change in `native/` beyond a default, and none is expected.** If you find you need one, stop and say so: the Architect's "no new replay is needed" lapses the moment `native/` changes beyond a default, and he rules again.
6. Anything else that states the old default (the config schema or sample, the docs, the Settings or API text): find it with `grep -rn "coherentFallbackMultiSet\|CoherentFallbackMultiSet"` over `src/`, `docs/`, `openspec/`, `tests/`, and change it only where it states the default.

## 2. Rows (mechanical; QA checks each)

- **D1 (tests first, each able to fail).** (a) A configuration with no `coherentFallbackMultiSet` key gives `CoherentFallbackMultiSet == true` in the daemon's decoder: the `DecoderConfig` bound from JSON without the key, **and** the `Ft8Decoder` the daemon sets up from it reads back true. (b) `"coherentFallbackMultiSet": false` gives false (OFF) in both. Run (a) against the old default first and watch it fail (QA repeats that against `d7750bde`). A config POST that does not mention the key leaves the current value as it was (the existing overlay test must still hold in both states).
- **D2.** The existing `Coherent*`, A1, A1.1, B3, B4 and M1 tests pass. A test that assumed the old default is changed **only where it asserted that default**; list each such test with FILE:LINE in your report so QA can see none was weakened. The full unfiltered `dotnet test OpenWSFZ.slnx` is green (quote the exact command line and the per-project counts; HK-022). `openspec validate --all --strict` clean.
- **D3.** QA's HK-039 review record (`Reviewed-commit: <40-hex>` + `Verdict:`) is committed **before any acceptance run**. QA reviews every changed line and repeats the mutation: the new default reverted to `false` must fail D1(a), and the `false` branch forced to ignore the explicit key must fail D1(b).
- **No new replay.** The MS arm already measured exactly this behaviour (flag ON) on the same native code (shim 20260071, pin `1ba8dc3d…db914`).

## 3. What QA does around it (not yours)

- Reads back the station's saved config: no explicit `"coherentFallbackMultiSet": false` (HK-035: it is an overlay and an explicit `false` would keep the station OFF). The check is a readback, not an assumption.
- At deploy QA stamps the **"MS ON" era** with `date -u` on the board; live figures are never pooled across it (same rule as `nhard` and the fallback flag).
- `pre_merge_check.py` from a clean checkout of the exact commit (HK-006: the branch has `native/` and `src/` changes), the Linux/macOS binary refresh chore (PR #254 precedent) so CI does not meet a stale 20260069 binary, then the Captain's push go and his merge sign-off (HK-010, HK-033).

## 4. Report back

Commit hash(es); the exact test command lines with counts; the D1 fail-then-pass evidence; the list of old-default assertions you changed (FILE:LINE); the `VERSION` bump and the `check_version_bump.py` output; confirmation that the diff touches no file under `native/` (or exactly what it does). Do not push.
