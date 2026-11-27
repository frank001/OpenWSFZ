# DR-0 / DR-1: measure today's decoder, then cut its CPU with settings only

**To:** QA (Engineer may run any part as a QA peer)
**From:** Architect, 2026-11-24
**Plan:** [`plan.md`](plan.md), §5 Phases 0 and 1. The Product Owner approved the plan and all five §9 answers on 2026-11-24.
**Process:** the light process in the plan's §6:
- no pre-registration, confidence intervals or amendments
- one replay per question
- the bars below are mechanical and final
- if something in this spec is wrong or cannot be done, QA fixes the obvious and notes it in the result. Write to the Architect only when a bar itself would change.

---

## 0. First: stop LR-BUILD (Product Owner, 2026-11-24)

- Stop the LR-BUILD validation run (V-OFF, V-EQ, V-LIMITS, PC timing) wherever it stands. **`feat/lr-full` is not merged.**
- Keep the branch and the review worktree as they are: archived, not deleted.
- Tell the Developer.
- Any results already on disk stay where they are. Nobody writes them up.

## 1. The fixed test set (used by every DR check from here to Phase 4)

QA picks it once. Following the replay-corpus rule, QA lists every `artefacts/` folder that has WAVs, then chooses:

- **Slice 40:** one hour (240 cycles) from a recorded **40 m** night, with the WSJT-X `ALL.TXT` recorded alongside on the same audio. The night must be from the MS ON era or later (since 2026-10-25T11:22Z). Pick the busiest hour.
- Write the choice into [`test-set.md`](test-set.md) (new; aggregates and folder names only, NFR-021): night, start cycle, cycle count, WSJT-X decode count. **It does not change after that.**
- *(Slice 20 was dropped on 2026-11-24 at the Product Owner's direction.)*

## 2. DR-0: the measurement

### 2.1 What is measured on each arm

Every arm replays Slice 40 through the full staged decode path (`DecodeStagedAsync`, as the daemon calls it) on **build `main` at the v1.0 merge, or `66b3ddf1` if v1.0 has not landed** (the decoder is identical). Run on the station PC with nothing else heavy running, one arm at a time.

| Column | Definition |
|---|---|
| `cpu_s` | Process CPU-seconds (user + kernel) of the replay process over the slice, divided by the number of cycles. Sample `Process.TotalProcessorTime` or the OS equivalent at start and end. No `src/` change is needed. |
| `last_p95` | p95 of the time from cycle end to the last batch done (ms), from the existing log lines |
| `abandoned` | cycles where any step was abandoned |
| `ours` | distinct published decodes over the slice, after the live path's text de-duplication |
| `matched` | `ours` that match a WSJT-X decode on the same slice (QA's standing matching rule, as used for LR-FULL) |
| `rate` | `matched / WSJT-X decodes on the slice`, in % |
| `ours_only` | `ours − matched`, as % of WSJT-X decodes |

### 2.2 The arms (cumulative: each adds one step to the one above)

CQ-AP and the hash table stay as today throughout. Depth is Normal unless the row says otherwise. Threads are at today's default unless the row says otherwise.

| Arm | Configuration |
|---|---|
| **A0** | decoding switched off: the idle cost of the replay host. If the harness cannot idle, leave this row empty and set `cpu_s` floor = 0. |
| **A1** | primary only: subtraction off, fallback off, XC off |
| **A2** | A1 + residual pass (`subtractionEnabled`) |
| **A3** | A2 + coherent fallback at today's default settings (both audios, multi-set, residual ungated) |
| **A4** | A3 at **Deep** (adds the third pass) |
| **A5** | A4 + late round (`lateSubtractionRound`) |
| **A6** | A5 + XC (`crossCyclePrior` ON, frozen threshold) = **the station's configuration today, the BASELINE** |
| **A7** | A6 with OSD off, by the same means as programme step 2 (2026-11-12) |
| **A8** | A6 with the early decode off. If the replay path never runs the early decode, report A8's `cpu_s` saving as A1's `cpu_s` − A0's, and say so. |
| **A9** | A6 with the worker threads capped at 2 (`subtractionMaxThreads` = 2 and the fallback's workers likewise, wherever that is set) |

### 2.3 Time limit

- Run a 10-cycle pilot of A6 first and extrapolate the total. **All arms together must fit in 2 hours of PC time.**
- If they don't, shorten the slice for **every** arm to the largest whole number of cycles that fits, with a minimum of 120. Record the length in `test-set.md`.
- If even 120 cycles does not fit, stop and ask the Product Owner for a go. Give the estimate, per the runs-over-2-h rule.

### 2.4 Output: `dr0-result.md`, one table plus three derived rows

- The table: one row per arm with every column from §2.1.
- **Per step**, from consecutive arms (A1→A2 is the residual pass, …, A5→A6 is XC; A6→A7 is OSD; A6→A8 is the early decode):
  - `Δcpu_s` = the arm's `cpu_s` − the previous arm's
  - `NET` = `rate(arm) − rate(previous)` in pp
  - `NET per CPU-s` = `NET / Δcpu_s`
- **Baseline for everything after this:** A6's `rate`, `ours_only`, `cpu_s − cpu_s(A0)` (`cpu_net`) and `last_p95`.

No verdict is written. DR-0 is a measurement.

## 3. DR-1: quick relief, settings only — ❌ SKIPPED (Product Owner, 2026-11-24)

> **Not built and not shipped.** DR-0 (`qa/decoder-rebuild/dr0-result.md`) measured the relief at ≈ 0 CPU-s per cycle. The Product Owner: *"there will be no shipping for a long time. we'll continue with the lean decoder for quite a while."* The early decode's removal folds into DR-4. OSD is OFF in the lean engine (DR-2 §2.3, NET −0.015 < 0.30). The rules below are kept as the record of what DR-0 was read against.

### 3.1 What goes off, decided mechanically from DR-0

1. **The early decode goes OFF** (the Product Owner's decision, plan §9 question 4). This doesn't depend on the table.
2. For each of these steps (third pass via A3→A4, late round A4→A5, OSD A6→A7):

   **It goes OFF iff its `NET` < 0.30 pp on Slice 40.** For OSD, "NET" means `rate(A6) − rate(A7)`.
3. **Thread cap at 2 goes ON iff** A9's `last_p95` ≤ 11,000 ms **and** A9's `abandoned` = 0.
4. The residual pass, the fallback and XC stay ON, whatever the table says. They are what the lean decoder replaces in Phase 2, not here.

### 3.2 One confirming arm

- **A10** = A6 with every OFF/ON choice from §3.1 applied together, on Slice 40.
- **DR-1 PASSES iff:**
  - `rate(A10) ≥ rate(A6) − 1.00 pp` (the decode budget, plan §9 question 2)
  - `ours_only(A10) ≤ ours_only(A6) + 0.50 pp`
  - `abandoned(A10) = 0`
- **If A10 misses:** QA reports the numbers and the Product Owner decides. There is no re-run.

### 3.3 Shipping DR-1

- **A Developer change of defaults only** (HK-011). QA writes the dev task with:
  - the new defaults
  - a one-time migration that rewrites the explicit old values in an existing `config.json` to the new defaults, logged once (same pattern as the FR-085 migration)
  - `REQUIREMENTS.md` FR updates for each changed default
  - **VERSION 1.1** (user-facing), with the README and REQUIREMENTS anchors
- **Checks:**
  - unit tests (per project, not `dotnet test OpenWSFZ.slnx`; HK-022)
  - QA's code review (HK-039)
  - **no extra replay:** A10 is the replay
- **The Product Owner merges it when he chooses.** The PR body states: A6 vs A10 `cpu_net`, `rate`, `ours_only`, `last_p95`.

### 3.4 Output

Append to `dr0-result.md`: the §3.1 decisions as a table with the number each rests on, A10's row, and PASS/FAIL. Update the board.

## 4. What DR-0/DR-1 do not do

- They do not change any algorithm, the fallback's internals or XC, and they do not re-tune any threshold.
- No second night.
