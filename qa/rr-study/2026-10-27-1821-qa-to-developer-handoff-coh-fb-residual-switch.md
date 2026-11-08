# Developer task: COH-FB-RESIDUAL, one replay-only switch

**To:** Developer · **From:** QA · **Date:** 2026-10-27 18:21Z (`date -u`) · **Base:** `main` `d20059c3` (v0.65) · **Branch:** `dev/coh-fb-residual` (new, from `main`)
**Spec (read it first):** `git show bc9abc8f:qa/rr-study/2026-10-27-1818-architect-to-qa-coh-fallback-residual-replay-spec.md` (Architect, branch `arch/coh-fallback-residual`, local).
**Authority:** the Captain's go, 2026-10-27 ("send it to QA, go ahead"), covers this Developer round. It does **not** cover any push or merge (HK-033, HK-014). This build is for REPLAY ONLY and is never merged.

## What to build

One environment variable, **`OPENWSFZ_COHFB_AUDIO`**, read once at `Ft8Decoder` construction, in the style of `OPENWSFZ_SUBTRACTION_BUDGET` (`f6a1aa79`, `Subfeas/SubtractionBudget.cs`). Not a config key, nothing in Settings, nothing in `native/`, no shim change.

- Unset, or any value other than exactly `residual`: **behaviour unchanged**. Emit nothing extra except the new log field (below), which is `audio=original`.
- `residual`: the coherent fallback (`RunCoherentFallback(normalisedPcm, ...)`, `Ft8Decoder.cs:1013` on `main`) is given the **cycle's last residual buffer** instead of `normalisedPcm`. The candidate snapshot (`cohSnapshot`, taken at `:646`) is **unchanged**: same candidates in both modes. Do NOT add residual-decode candidates.
- One construction-time warning when active (as the budget switch does).

## Which buffer: three points QA wants settled in the code, not assumed

1. **Source buffer.** Priority: (a) the third pass's own subtracted copy, if the third pass ran and subtracted anything; else (b) `report.Residual` (`SubtractionPass.cs:427`, `stats.Residual`). **Today (a) is not exposed:** `ThirdPassResult` (`SubtractionPass.cs:198`) carries no buffer and "the pass works on a copy". Expose that buffer on the result (read-only to callers, like `ResidualPassReport.Residual`), or state in your report why (b) alone is what you chose and QA will ask the Architect. Do not silently pick (b).
2. **`report` exists only on Deep** (`Ft8Decoder.cs:917`: `deep ? new ResidualPassReport() : null`). The probe is Deep. On Normal depth with the switch set: treat as `residual-unavailable`, do not change the Normal path.
3. **When is the buffer "available"?** `report.Residual` is assigned at step 3 (`:427`), BEFORE the residual decode, so it exists even when the pass is later abandoned. The spec says abandoned ⇒ unavailable. Define it as: unavailable when `report.DeadlineAbandoned || report.ContainedException || report.Residual is null`, or when nothing was subtracted (zero fitted signals). Then use the original audio and count it.

The buffer must be passed to the fallback **read-only** and must not be mutated or returned to any pool while the fallback runs (it runs on worker threads, `Task.Run`). If any buffer is shared, say so.

## The log field

Append to the existing `Coherent fallback:` line, **at the end** (after `crcN1`, so every existing positional parser is untouched): `audio=original|residual|residual-unavailable`. `residual-unavailable` means the switch was set but the original audio was used. Always present, in both modes.

## Tests (xUnit, in the existing Ft8 test project; no fixed delays, TESTING_STRATEGY §11)

- Switch parsing: unset / `residual` / `RESIDUAL` / `1` / empty ⇒ which are active (QA expects exactly `residual`, ordinal, active; everything else inactive and silent).
- The audio selector as a pure function (inputs: switch, depth, report, third-pass buffer; output: buffer + label): each of the available/unavailable cases above, including abandoned and contained-exception.
- A decoder-level test that, with the switch unset, the buffer handed to the fallback is the same reference as `normalisedPcm` and the label is `original`.
- Run the full suite on Windows and report the counts.

## R0, before any replay (Developer produces the evidence, QA checks it)

With the variable unset, the probe build must reproduce `main` (`d20059c3`, same DLL SHA-256) **byte for byte on 20 cycles** of night `20260925_2010` (frozen selection `81372df5`, first 20 cycles after the warm-up stamp): same decode rows, **mechanically diffed** (sorted, hash-randomisation-safe), not eyeballed. The only permitted difference anywhere is the new trailing `audio=original` field on the fallback log line. Quote: both build SHAs, the DLL SHA-256 pair, the exact replay command, the diff command and its empty output. Write rows to a gitignored `_out/` or `D:\Projects\claude\_qa-scratch\coh-fb-residual\`; **no callsign text in anything committed** (NFR-021, HK-037).

## Report back (HK-001 sections), then STOP

Commit hash on `dev/coh-fb-residual`; the three points above answered with file:line; test counts; the R0 evidence. **Do not push.** QA then does the HK-039 review (`Reviewed-commit:` + `Verdict:` record) and `pre_merge_check` is NOT required (nothing merges); only after the HK-039 record may any replay run (hook-enforced).
