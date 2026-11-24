# Developer task: RF4-L1P-DEFAULT-ON (`decoder.coherentFallbackResidualUngated` and `decoder.lateSubtractionRound` are true when their keys are absent)

**Date:** 2026-11-09
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the Captain, 2026-11-09, via the Architect's spec: "option a. turn them both on" (both defaults ON now, no live ON run first; he was told the alternative). Spec: `qa/rr-study/2026-11-09-1634-architect-to-qa-spec-rf4-l1p-default-on.md` on `arch/rf4-l1p-default-on` (`3b09d198`; read it with `git show arch/rf4-l1p-default-on:<path>`). Evidence, each measured ALONE: R-F4 NET +1.470 pp [1.296, 1.638] (second night); L1' NET +0.772 pp [0.655, 0.889] (third night, ACCEPT-3N). Together: unmeasured, accepted by the Captain.
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative** (QA runs it on a clean checkout of the exact commit before any push).
**Branch:** `feat/rf4-l1p-default-on`, off `origin/main` (VERSION 0.68; re-fetch first, `main` moved by docs only). Never commit to `main`.
**OpenSpec:** amend the main specs `ft8-late-subtraction` and the COH-GATE-G (R-F4) requirement for the new default, in whatever change folder QA's convention gives you (name it `rf4-l1p-default-on`); `openspec validate --all --strict` must stay clean.
**Version:** user-facing, a default behaviour changes: bump **0.68 to 0.69** (re-check `origin/main` first; the closed #272 build used 0.69 on an unmerged branch, so it is free). Confirm with `python tools/check_version_bump.py origin/main` and quote its output.
🛑 **Licence:** nothing here needs any WSJT-X source. No `native/` change.

---

## 0. What changes, in one paragraph

When the saved configuration has no `coherentFallbackResidualUngated` key, R-F4 is ON; when it has no `lateSubtractionRound` key, L1' is ON. An explicit `false` still turns each one off, exactly as before. Same pattern as #264 (COH-MULTISET) and #240 (Deep).

## 1. Scope (line numbers at `e3db42cf`; re-find them)

1. `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: the `[JsonConstructor]` parameters `bool coherentFallbackResidualUngated = false` and `bool lateSubtractionRound = false` (about `:58`, `:60`) become `true`; their comments (`:57`, `:59`, "(default false)") say what is true now.
2. Same file: the two property declarations (`CoherentFallbackResidualUngated` about `:283`, `LateSubtractionRound` about `:294`) have NO initialiser today, so a `new DecoderConfig()` or a missing `decoder` section reads the CLR `false`. Give both `= true`. Their doc comments say "**Default `false`**: an absent key reads `false`": rewrite them (ON when absent, `false` turns it off, the R-F4 and L1' preconditions unchanged, the POST is an overlay, a new live era "RF4+L1' ON").
3. `src/OpenWSFZ.Daemon/Program.cs:855-856`: the two comments "default false (key absent = off)" say default true. The calls at `:964-965` are unchanged.
4. `src/OpenWSFZ.Ft8/Ft8Decoder.cs`, the backing fields and their comments (`:246`, `:259`, "the daemon sets the configured value (default false)"): the daemon always sets both from config before the first cycle and on every change, so the configured default decides behaviour. **Whether the `Ft8Decoder` fields themselves start `true` is your call, with QA reviewing it; state which way each went and why.** Leaving them `false` keeps every test that builds an `Ft8Decoder` directly exactly as it is; changing them changes those tests' behaviour.
5. **No change in `native/`.** If you find you need one, stop and say so.
6. Everything else that states the old default: `grep -rn "coherentFallbackResidualUngated\|CoherentFallbackResidualUngated\|lateSubtractionRound\|LateSubtractionRound"` over `src/`, `docs/`, `openspec/`, `tests/`, `README.md`, `REQUIREMENTS.md`; change it only where it states the default.

## 2. Tests that will change (QA found these; there may be more)

Six files mention the keys: `tests/OpenWSFZ.Config.Tests/CoherentFallbackResidualUngatedConfigTests.cs` (`CodeDefault_IsFalse_AbsentKeyReadsFalse`, `:31`, asserts the old default on `"decoder":{}`, on a body for another key, and on `new DecoderConfig`), `tests/OpenWSFZ.Config.Tests/LateSubtractionRoundConfigTests.cs` (its twin), `tests/OpenWSFZ.Web.Tests/CoherentFallbackResidualUngatedApiTests.cs`, `tests/OpenWSFZ.Web.Tests/LateSubtractionRoundApiTests.cs`, `tests/OpenWSFZ.Ft8.Tests/CoherentFallbackWiringTests.cs`, `tests/OpenWSFZ.Ft8.Tests/LateSubtractionRoundTests.cs`. Change a test **only where it asserted the old default**; list each change with FILE:LINE so QA can see nothing was weakened. Also look for any test that builds a `DecoderConfig` (or reaches the daemon wiring) with a key absent and then runs a decode or counts batches or timings: with the default ON it now gets batch 5 and the ungated R-F4 rows, and a count or timing assertion could move. Report each such test and what you did.

## 3. Rows (mechanical; QA checks each)

- **D1 (tests first, each able to fail), for EACH of the two keys.** (a) A configuration with the key absent gives `true` in the daemon's decoder: the `DecoderConfig` bound from JSON without the key (also `{"decoder":{}}` and no `decoder` section), **and** the `Ft8Decoder` the daemon sets up from it reads back true. (b) An explicit `false` gives `false` in both. Run (a) against the old default first and watch it FAIL (QA repeats that against `e3db42cf`). A config POST that does not mention the key leaves the current value as it was (the existing overlay tests must hold in both states, HK-035).
- **D2.** The existing COH-GATE-G (R-F4), LATE-SUB (L1'), `Coherent*`, config and overlay tests pass, with only the §2 changes. Full unfiltered `dotnet test OpenWSFZ.slnx` green: give the exact command line and per-project counts (HK-022; the `AwgnFpReplay` category is excluded in CI and on the Architect's runs, say which you ran). `openspec validate --all --strict` clean.
- **D3.** QA's HK-039 review record (`Reviewed-commit: <40-hex>` + `Verdict:`) is committed before anything is deployed. QA repeats four mutations: each new default reverted to `false` must fail its D1(a); each `false` branch forced to ignore the explicit key must fail its D1(b).

## 4. Report to QA

Commit hash(es); exact test command lines with counts; the D1 fail-then-pass evidence for both keys; the old-default assertions changed (FILE:LINE); any other test affected and what you did (§2); how you decided §1.4; the VERSION bump and `check_version_bump.py` output; confirmation that the diff touches nothing under `native/`. **Do not push.**

## 5. After your commit (QA, for your information)

HK-039 review record, then `pre_merge_check.py` from a clean checkout of the exact commit, then the Captain's push go and merge sign-off, then deploy. Before deploy QA re-reads the station config under `frans` (read 2026-11-09 16:39Z: no explicit key for either setting; `coherentFallbackAudio` Both, `decodingDepth` Deep, `coherentFallbackEnabled` true). The daemon start on the merged build starts a new live era, "RF4+L1' ON", stamped by QA with `date -u`. The first live session is reported, not gated.
