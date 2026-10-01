# SUB-FEAS merge-readiness status (facts only)

- **Date (UTC):** 2026-09-30 (`date -u`). **From:** QA. **To:** Architect, for the Captain's merge plan ("we'll merge everything before Stage B, including the config fix").
- **Nothing here is a recommendation.** Every number below was read from git, the checkers or the files named. Where something is unverified it says so.
- **`src/`/`native/` diff of this note:** none.

## 1. Which gates are MERGE gates and which are LIVE-USE gates, in the change's own words

Source: `feat/sub-feas-native-subtraction` @`ab95bea1`, `openspec/changes/sub-feas-native-subtraction/` (the authoritative copy; the `qa/sub-feas` copy of `tasks.md`/`design.md` is older, see §4).

| Gate | The change's own words | Status of the record |
|---|---|---|
| **§8.1 runtime, §8.2 independent-corpus decode rate, §8.3 Captain decision** | `tasks.md` §8 header: *"these gate LIVE USE, not this change's own merge"*. Spec, "Live-use readiness": *"Both are gates on live use, not on this change's own merge — per the Captain's 2026-09-28 decision, the native build may land and be measured before these are read, but the flag SHALL remain OFF in any live run until they are."* Scenario: *"the build MAY merge with the flag OFF by default, but the flag SHALL NOT be enabled in any live endurance or production run until the runtime measurement is taken and reported."* | **LIVE-USE gates, explicitly.** §8.1 is measured (the §8.1 replay, then Stage A: registered FAIL on R2′, accepted by the Captain). §8.2 and §8.3 are **open** and gate live use only. |
| **§7 sustained stability** | `tasks.md` §7 header: *"Stability gate — independent of decode-rate accuracy (spec ADDED requirement)"*. Spec: *"The residual-decode pass, when enabled, SHALL run for a sustained, multi-hour period without crashing the host process ..."*. Scenario: multi-hour run, flag enabled, varied real or replayed audio (silence, single-signal, dense), no crash, no unbounded memory growth. **Neither the spec nor the header says merge gate or live-use gate.** `tasks.md` 10.1 (first sentence): *"§3 (memory safety), §7 (stability gate), and §8 (measurement gates) are treated as hard blockers, not advisory."* | **Not assigned to either side.** 10.1's first sentence lists §7 **and §8** as hard blockers, which contradicts the §8 header and the spec for §8. 10.1's most recent list (pass 3): *"Open before merge: 6.8 Linux/macOS, 5.1 UI checkbox, 6.7 deferred, 6.6 native half unmet by design, Captain merge sign-off."* **§7 and §8 are not in it.** §7 has not been run and reported as such. |
| §3 memory safety | 10.1 hard blocker | 3.1–3.3 are unticked on the branch's `tasks.md`, though the heap-only workspace pool exists and was reviewed (QA review passes 1-3 approved the code). A tick reconciliation, not a missing artefact. |

**A correction to QA's own Stage A report.** It listed "base-change §7 and §8.2/§8.3" next to "the merge gate". That is wrong for §8.x (above). Corrected in the report where it lives (`qa/rr-study/results/2026-09-30-sub-feas-speed-stage-a-acceptance/report.md`, item 4 of Section 5).

**What stability evidence exists (facts, not a §7 result).** Flag-ON multi-hour replay with **0 access violations, 0 contained exceptions, 0 non-zero process exits**: the §8.1 replay (20:49Z to 00:27Z, about 3.6 h, 905 timed cycles plus R6) and the Stage A acceptance (10:11Z to 13:54Z, about 3.7 h, 905 flag-ON cycles plus R6 plus the 4-worker row); the R&R paired runs (436 flag-ON cycles); unit tests for AV containment and a many-workers-many-cycles pool stress test. **What it is not:** it is not the varied mix §7 names (no silence or single-signal cycles were selected; the corpus is busy real cycles), and no long-run memory measurement was taken beyond the pool's plateau test. It was never reported as §7.

**Other open items in the base change's own list** (`tasks.md` at `ab95bea1`): 6.8 full `dotnet test` on all three platforms (Windows only so far; CI would run Linux and macOS); 5.1 the Settings-page checkbox gap (the flag has no control on the Settings page); 6.6 native half not started (`[~]`); 6.7 deferred by the Captain; 1.3 shim-renumber check preliminary; 9.1-9.5 documentation and spec reconciliation (including 9.4, a `REQUIREMENTS.md` FR entry for the **flag**: only FR-077, the thread count, has been added); 10.2 diff-scope check.

## 2. Branch chain and ancestry

All four SUB-FEAS branches are **linear** and cut from `origin/main` `c3f42362`, which is still the tip of `origin/main` (fetched 2026-09-30; **0 commits behind**).

```
origin/main c3f42362
 └─ feat/sub-feas-native-subtraction   ab95bea1   (11 commits; code 2b39cf18, shim 20260055)
     └─ feat/sub-feas-speed-redesign   ca0bcd9b   (+6; Stage A, shim 20260056)
         └─ feat/sub-feas-two-stage-publish 247ac391 (+1; no native change, libft8.dll ee00d118… unchanged)
```

`git merge-base --is-ancestor` confirms base ⊂ speed-redesign ⊂ two-stage. The top branch is **18 commits ahead, 0 behind** `origin/main` (11 + 6 + 1). **One PR from `feat/sub-feas-two-stage-publish` to `main` is structurally possible**: it is a single branch on `main`, not a stack, so the HK-008 stacked-PR/squash trap (retarget-then-conflict) does not arise from the SUB-FEAS chain itself. It arises only between two independent PRs that both target `main` (SUB-FEAS and config-save, §3).

**What the top branch does NOT contain:** the OpenSpec change `sub-feas-speed-redesign/` (proposal, design, spec delta, tasks) exists **only on `qa/sub-feas`** (`User-facing: no`). A PR from the top branch would land the base change's OpenSpec directory but not the Stage A / two-stage / Stage B change that describes the same code.

## 3. Collisions with config-save (`feat/config-save-preserves-unsent-settings` @`93dddf4b`, 6 commits, also cut from `c3f42362`)

A no-checkout `git merge-tree` of the top branch with the config-save branch: **one conflict, `REQUIREMENTS.md`; `src/OpenWSFZ.Web/WebApp.cs` auto-merges cleanly.** Files changed on both sides: `REQUIREMENTS.md` and `WebApp.cs` only (59 files on the SUB-FEAS side, 28 on the config-save side).

| Item | SUB-FEAS side | Config-save side | Fact |
|---|---|---|---|
| **REQUIREMENTS.md FR order** | adds **FR-077** (thread count) | adds **FR-074-FR-076**, amends FR-004 | FR-077 was numbered on the assumption that config-save merges first (Developer's Stage A report, item 3). If SUB-FEAS merges first, config-save must renumber; if config-save merges first, no renumbering, only the header/change-log conflict below. Base task 9.4 (an FR for the `subtractionEnabled` flag) is open and would need the next free number. |
| **REQUIREMENTS.md header and change log** | `**Version:** 1.51`, date 2026-09-30, change-log row **1.51** | `**Version:** 1.50`, row **1.50**, and the sentence "The current release is v0.52" | This is the textual conflict. |
| **VERSION** | **0.51** (unchanged from `main`) | **0.52** | 🔴 **The `check_version_bump.py origin/main` gate FAILS on the top branch today (exit 1):** the base change's `proposal.md` declares `**User-facing:** yes` and VERSION is unchanged. It needs a bump whenever SUB-FEAS merges. If config-save merges first (`main` = 0.52), SUB-FEAS needs **0.53**, and `check_version_docs.py` then requires README and REQUIREMENTS to cite it (it passes on the top branch today at 0.51). `sub-feas-speed-redesign` declares `no` and is not on the top branch. |
| **DecoderConfig.cs** | adds `SubtractionMaxThreads` (0 = auto); base branch adds `SubtractionEnabled` | not changed | **No file overlap.** Semantically, config-save makes `POST /api/v1/config` an overlay so an omitted key keeps its stored value, and the Settings page sends neither SUB-FEAS key. **Not test-merged or tested together by anyone**: the Developer's Stage A report says so, and QA has only run the no-checkout merge. |
| WebApp.cs | adds a `subtractionMaxThreads` clamp-with-warning block in the POST handler | overlay merge of the POST handler | auto-merges; not compiled or tested in combination. |

## 4. What else must travel, or be decided

- **`qa/sub-feas`** (30 commits ahead of `origin/main`, local, not pushed): the OpenSpec change `sub-feas-speed-redesign`, three Developer handoffs in `dev-tasks/`, and 65 files under `qa/rr-study/` (the R&R paired-run reports, §8.1, Stage A, S1/S2 harness, scripts, rulings). Anything committed to `main` needs the NFR-021 scan; the reports were scanned as written. It also holds an **older** copy of the base change's `tasks.md`/`design.md` than `feat/sub-feas-native-subtraction` does (the feat copy is authoritative; the qa copy differs by 56 insertions and 285 deletions).
- **`qa/live-gap-map`**: `qa/rr-study/run_study_detached.py` is on that branch only (last commit `345e75ff`), not on `main`; the Engineer's config-drift check waits on it. Independent of SUB-FEAS but named in the Captain's earlier instruction.
- **`arch/subtraction-feasibility`** (the Architect's specs, rulings, amendments 1-4 and ledger): `qa/rr-study/` files on that branch. The Architect never pushes or merges (HK-014); QA lands them on the Captain's go.
- **`ci.yml`**: the Developer changed the Linux and macOS native recipes to compile `subfeas_fit.c` (they never did). Linux compile was verified locally via WSL; **macOS is unverified**. The Linux/macOS `.so`/`.dylib` are CI-built, not committed.
- **Shim numbers:** `main` `20260051`, `decoding_improvement` `20260054` (DI), base `20260055`, Stage A `20260056`; two-stage has no bump. The known `FT8_SHIM_VERSION` collisions (`20260034`, `20260035`) are on unmerged `d001-*` branches, not this chain.

## 5. Evidence state of the merge build (the top branch, `247ac391`)

| Item | State |
|---|---|
| QA code review | base passes 1-3 approved; Stage A and two-stage reviewed by QA, no defect found |
| Full unfiltered `dotnet test OpenWSFZ.slnx` | **1646 passed, 0 failed**, run by QA on `247ac391` (the Developer's run was the same); `libft8.dll` `ee00d118…990e4c` |
| E1 (Stage A bit-identity, real corpus) | PASS, 3878/3878 rows; pass-0 outcome hashes identical between the base and candidate DLLs on 161 real cycles |
| Stage A timing rows | registered "FAIL on R2′" (p95 6 410.8 vs 6 000 ms), accepted by the Captain; every other row PASS |
| Two-stage S1 / S2 (and the interim managed flag-OFF comparison) | **running now** (started 15:01Z), results pending; **S2b not yet started** |
| Flag-OFF control, native **and** managed | **not run**; back in the queue for the merge build (the Captain's decision via the Architect) |
| §7 stability, §8.2, §8.3 | open (§7 unassigned, §8.x live-use gates, §1) |
| G9b `check_version_bump` | **FAILS** on the top branch as it stands (§3) |
| Linux / macOS CI | not run on this chain (base task 6.8) |
