# RULING — `decoding_improvement` (DI) sync sequencing after default-ON reached `main` first

- **To:** QA (owner of the sync) — cc Captain  **From:** Architect  **Date:** 2026-10-02 ~18:25Z (HK-017)
- **Branch:** `arch/subtraction-feasibility`. Docs only: `git diff --stat -- src/ native/` empty.
- **Asked by:** QA, at the Captain's request, 2026-10-02. **Supersedes** §4.4 of `2026-10-02-0710-architect-to-qa-spec-sub-feas-default-on.md` ("land the sync first"). That order was overtaken when PR #201 merged at 10:23Z. No fault is found.

## Facts checked by the Architect (not only quoted from QA)

- DI `51e40b55` is 57 behind and 17 ahead of `origin/main`. The prepared sync `sync/di-with-main-3` = `effb9fb7` merged `9bade2bc` (VERSION 0.53).
- **`git diff 9bade2bc origin/main -- native/ src/OpenWSFZ.Ft8/Interop` is EMPTY.** Everything main gained since then (#199/#200, #201 default-ON, #202, the flake fixes, #205/#206, the gatherer fix) is managed code, tests, web or docs. **The native merge resolution in `effb9fb7`, and the DLL/.so it rebuilt, are not touched by bringing current main in.**
- Shim `20260057` appears on **no ref other than `sync/di-with-main-3`** (grep over every local and remote branch). Main is `20260056`, DI `20260054`.
- Main's REQUIREMENTS has revision rows 1.50, 1.51, **1.54** and FR-082, with **no FR-078..081 and no rows 1.52/1.53.** Main left exactly the gaps the prepared sync fills.

## Answers

**(a) Neither as you put it: keep `effb9fb7` and merge current `origin/main` into it.** Not a redo from scratch, and not "land v0.53 first". Branch `sync/di-with-main-4` from `effb9fb7` and merge `origin/main` into it. That keeps the prepared conflict resolution and its history. The second merge has no native content, so its conflicts are managed and docs only (REQUIREMENTS, VERSION, README, Program.cs, WebApp.cs, settings.html, app.css). Landing v0.53 alone would push a DI that is stale on arrival and needs a second verification cycle anyway. **One tip, one verification, one push.**

**(b) Shim: `20260057` stands, and the DLL is not rebuilt for this merge.** It is unique, and it names a native export set (main ∪ DI) that neither parent holds. Mechanical check, as a row in QA's verification: `git diff effb9fb7 <sync-4 tip> -- native/` is **empty**, and the win-x64 DLL and linux-x64 .so SHA-256s at the tip equal those at `effb9fb7`. If either check fails, stop: something native moved, and the shim question reopens. Pin the DLL by SHA-256 in every later report (the shim number identifies nothing on its own).

**(c) DI inherits default-ON at the sync. No DI-side OFF pin in code.** The Captain decided default ON and the one-time migration. A DI-only default would be a standing divergence from main, re-conflict at every sync, and quietly contradict his decision. Measurement continuity is a **per-run config pin**, recorded in `arm_config.json`, never a code default.

**(d) No standing reason to keep DI runs flag-OFF.** The rules that do apply:
1. 🛑 **Never pool across the boundary.** The first DI endurance run on the synced build is the DI flag-ON boundary. Record its UTC start in the guards beside main's 2026-10-02 10:23:45Z. Its Section 4 header says that Section 4 moves by about the NET because of the flag, not a decoder change (HK-036).
2. A specific run whose question is "DI decoder change X versus the flag-OFF history" may pin OFF. That is the run's design, decided when it is specified, not a branch default.
3. Flag-ON endurance with live WSJT-X is **useful**: it is the first multi-night flag-ON evidence for the band-D FP watch.

**(e) Keep the prepared numbering: DI's FR-078..081, rows 1.52/1.53, main's FR-082 and row 1.54 unchanged.** Main's published numbers never move, and the DI numbers fill main's deliberate gaps. Add **one new row above 1.54** for this second merge, numbered per `check_version_bump.py` (QA commits before re-running G9b). VERSION at the tip is **no lower than 0.54**. The gate decides whether it must be 0.55.

## Additions to QA's plan (steps 1–5 accepted otherwise)

- **Step 1 (pause DI endurance) is accepted, with one more reason.** DI builds predate #196: they do not know `subtractionEnabled` or the #199/default-ON markers, and their config POST is a **full replace** (HK-035). A Settings save from a DI daemon against the station's real `%APPDATA%\OpenWSFZ\config.json` would drop those keys, and main would re-run its migrations on its next start. **Until the sync lands, any DI daemon runs with a `--config` copy.** QA brackets the station config (mtime and hash, plus a read-back of `subtractionEnabled`, `osdNhardMax` and both markers) around any DI daemon start, as is now done around test runs.
- **Step 3 must exercise flag ON on the merged DLL.** `effb9fb7` was verified at v0.53, where the flag defaulted OFF. The residual pass has never run inside DI's DLL (decoder-param-readout tuning constants and the density probe tap, together with subtraction). Add an A8-style short live run on the `sync-4` tip **with the flag at its new default**, RX only: batch-2 decodes > 0, 0 abandoned, 0 access violations, flag and markers read back. Also run the config-POST **overlay** check that was still owed on the merged daemon.
- **Also in step 3:** the native rows of (b), and a fresh-install migration check (start with no config: `subtractionEnabled` = true, `osdNhardMax` = 40, both markers written; restart with an explicit 60: still 60). This is the #199 regression check on the merged tree.

## What the Developer needs before starting (HK-000 / HK-011)

1. **The Captain's go for a separate Developer session**, given to QA directly (a relayed go is not a go).
2. QA's handoff in `dev-tasks/` naming: base `effb9fb7`, new branch `sync/di-with-main-4`, merge `origin/main` at a named SHA, **no native edits and no DLL rebuild** (if the merge seems to need one, stop and report), the numbering of (e), and the managed-conflict file list.
3. Confirmation from QA that no DI daemon is running against the station config, and that endurance on DI is paused. That pause is the Captain's word, and QA asks him directly.
