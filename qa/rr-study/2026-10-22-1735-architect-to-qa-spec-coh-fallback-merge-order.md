# Architect to QA: COH-FALLBACK step 4 merge: `main` first, then `decoding_improvement`

**Stamped:** 2026-10-22 ~17:35Z (`date -u` 17:31:53Z when drafting began). **To: QA.** Branch `arch/coherent-limb2`.
**Basis:** step-3 spec §19 (replay ruled) and §21 (R14 live check ruled, `4cf43e70`). The Captain, first-hand in the
Architect's window, after §21: *"I call that a total success! tell qa to update the relevant gh issues when waiting for
CI during the merge. spec the correct merge order, main first and then decoding_improvement."* **That is his merge go
(HK-010)** for step 4 into `main`, followed by the `decoding_improvement` sync. QA carries out every push, PR and merge
(HK-014). The Architect pushes nothing.

## What is being merged (facts, checked 17:31Z)

| item | value |
|---|---|
| Branch | `feat/coh-fallback-stage1` (local only, **not on the remote**). The name is stale: it carries Stage 1, Stage 2 **and** step 4 |
| Tip | `b8fc732ec679744ca8340612c7203b6d0c6411f4` (shim 20260069; DLL SHA-256 `aaf6b03e…` as pinned in R14) |
| Base | `origin/main` `9d5ba635` is an ancestor: 5 commits ahead, 0 behind ⇒ **no rebase, no conflict expected** |
| Size | 37 files, +5,059 / −112 against `origin/main` |
| HK-039 review | record on `qa/refset` `5759895c` carries `Reviewed-commit:` lines for `db3d7df5` and `b8fc732e` |
| Flag default in code | `DecoderConfig.CoherentFallbackEnabled = false` (`DecoderConfig.cs:239`). See M5 |
| `decoding_improvement` | `origin/decoding_improvement` `c4867dae` (DI sync 6). After M4 it is **195 + 5 behind `main`** and 45 ahead |

## Part 1: `main`

- **M1 Pre-merge gates, on `b8fc732e`, in a scratch worktree under `D:\Projects\claude\_qa-scratch\coh-merge\`
  (never the root).**
  - (a) **A1 = the unfiltered test suite** (`dotnet test OpenWSFZ.slnx`) plus the native self-test. Give the
    Captain its cost before you start, from your last run of it (E24). This is the only A1 leg now (§21 A21.5).
  - (b) `check_version_bump.py` (G9b) and the NFR-021 pre-merge scan (`nfr021_pre_merge_scan.py`), including PR
    prose.
  - (c) The HK-002 OpenSpec audit. I found no open OpenSpec change for COH-FALLBACK under `openspec/changes/`. Report
    what the audit finds. A missing change is reported to the Captain and does not block on its own.
  - (d) `pre_merge_check.py` only if the Captain asks for it (HK-006).
  - Any red ⇒ stop and report. No fix by QA in `src/` or `native/` (HK-011).
- **M2 Push and PR.** Push the branch. Open a PR to `main` that states the evidence by reference: §19 replay (D-GO′ NET
  +3.82 pp [3.44, 4.21], U′-OK), §21 live check (L1a 0 missing, L2 no defect with the deferral path not exercised live,
  L3), and the deviations. Say that the `src/`/`native/` diff is the Developer's (HK-011), that it was reviewed per
  HK-039, and that the flag ships default OFF in code (M5). Aggregates only, no callsigns.
- **M3 While CI runs: update the relevant GitHub issues (the Captain's instruction).** In my reading:
  - **#3** (D-001 decode gap vs WSJT-X): COH-FALLBACK result, replay NET and live check, with the PR link.
  - **#240** (optional third pass, Deep): the fallback runs as batch 4 on Deep and batch 3 on Normal, behind
    `decoder.coherentFallbackEnabled`.
  - **#251** (external-reporting loopback): add only that the station currently runs on the port-2238 workaround
    (Captain's choice), if that is not already in it.
  - **#252** (radio control): nothing unless the run produced something for it.
  - Add any other issue the merge closes or touches, at your judgment. NFR-021 applies to every comment.
- **M4 Merge** on green CI. CI runs twice per PR, which is accepted; never use a SHA-keyed cancel. Record the merge
  SHA and the merge time in UTC from `date -u`. **That time is the data-era boundary: never pool across it.**
- **M5 Flag ON on the station: the Captain's choice, not yet made.** The code default is `false`. Two routes:
  - (a) Set `decoder.coherentFallbackEnabled = true` on his station through the config API, read it back, and log
    the time. That is the same mechanism as R14. No code change. A settings reset would put it back to false.
  - (b) Change the code default to `true`. That needs a Developer commit, an HK-039 review, the suite and a PR, so
    it is a separate small change after the merge.
  - The Architect's recommendation is (a) now. He is the only user, so (a) gives exactly the default-ON outcome
    today. (b) can follow later if he wants it. **Do nothing on M5 until he answers.**

## Part 2: `decoding_improvement` (only after M4 has landed)

- **M6 DI sync 7.** Copy the DI sync 6 precedent (`61a480cd`, PR #247; HK-034):
  - Cut `sync/di-with-main-7` from `origin/decoding_improvement` and merge `origin/main` into it.
  - Conflicts in `src/` or `native/` (shim manifest, `Ft8LibInterop.cs`, `ft8_shim.c/.h`, `libft8.version.txt`,
    binaries) are resolved by a **Developer session** (HK-011). The next DI shim number follows sync 6's convention.
  - QA reviews the resolution and commits the `Reviewed-commit:` record (HK-039) before any run.
  - Then the suite, push, a PR to `decoding_improvement`, CI, an issue update if one applies, and the merge.
- **M7 After each merge,** nudge the persona worktrees that carry the merged work (HK-032).

## Not in this spec

- No change to the deployed station build: the station keeps what it runs now until the Captain says otherwise.
- The controlled late-only-CQ test, a post-merge follow-up per the Captain (QA note `2026-10-22-1632-…`).
- The docs branches (`arch/coherent-limb2`, QA's local `qa/refset` commits). Their push or landing is a separate go
  from the Captain (HK-033), docs only, with `src/`/`native/` diff empty (HK-029).

*Architect. Docs only; `src/`/`native/` diff empty.*
