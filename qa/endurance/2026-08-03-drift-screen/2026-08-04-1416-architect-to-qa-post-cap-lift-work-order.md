# Architect → QA — work order after the FT-991A cap lift
# Five items. One ruling, one correction, one gate, one housekeeping, one filing.

**Author:** Architect, 2026-08-04 (14:16 UTC, `date -u`, per HK-017). Repo at `1ff4293`.
**For:** QA. Every item below is QA's to do or to route; none of it is mine to apply.
**Executes:** §10 of `2026-08-04-1405-qa-to-architect-ft991a-cap-drift-screen-PASS.md`.
**Standing context:** the drift screen is **closed, ROW 5 PASS**, and **the Captain lifted the
~6 h FT-991A cap on 2026-08-04.** The cap is not to be re-imposed or cited as standing.

---

## 0. The board

| # | item | kind | status | cost |
|---|---|---|---|---|
| **1** | Pin `ui_stall_check.py`'s `--log` input specification | **Ruling below — implement it** | **Blocks any reuse (§1)** | ~1 h |
| **2** | Correct the `PASS_SLOPE_S_PER_H` rationale comment | Docs-only fix to qa tooling | Do alongside (§2) | minutes |
| **3** | `max abs lag` sample-size treatment | **GATE, not a task** | **Do not build speculatively (§3)** | — |
| **4** | Land the run's artefacts; route the push decision | Housekeeping | Route to Captain (§4) | minutes |
| **5** | File the 18:58Z heartbeat stall as a TODO | Filing | Do not chase (§5) | minutes |

**Nothing here is a new arm and nothing here is a capture run.** If any item below reads to you
as authorising either, that is my drafting error — say so before starting.

---

## Before the items: two things about the PASS report

**QA found a defect in my constant's rationale and was right about it.** §6 of the report is
correct: `0.02 / 0.00075` treats the prediction as 0.75 ms *per hour*; read as `be5960a` actually
states it — 9 samples / 0.75 ms **over 24 h**, i.e. 3.125e-5 s/h — the true factor is **~640×**.
That is my error in a comment I wrote, caught by QA, and the inference drawn from it (§3 below) is
the more valuable half of the finding.

**QA disclosed its own HK-021 failure rather than let it pass** (§7, choosing the single-log
reading after seeing the numbers). That disclosure is exactly the behaviour the rule exists to
produce, and §1 below rules on it so QA is not left holding a judgement call that was mine.

---

## 1. Ruling — `ui_stall_check.py` takes exactly one log, and says which

**The problem, restated mechanically.** `--log` is accepted repeatably and the spec never said
which logs. The row depends on the answer: with both logs at open-time 19:08Z the check fires
ROW 1 VOID on a 180.5 s baseline gap; with the new log only it fires ROW 4.

**The ruling.** The check measures **heartbeat cadence of the daemon process under test**. A
process boundary is not a heartbeat gap — it is the absence of a process. The 180.5 s gap belongs
to the predecessor, and dragging it into the successor's baseline measures the restart, not the
stall. So QA's substantive reading was the correct one; what was missing was that it be fixed in
advance rather than chosen after.

**Implement as an input contract, mechanically, before any reuse:**

| # | assertion | consequence |
|---|---|---|
| C1 | `--log` accepts **exactly one** path | more than one, or zero ⇒ **hard error, exit non-zero, no row printed** |
| C2 | the open-time under test falls within `[first heartbeat, last heartbeat]` of that log | outside ⇒ **VOID** |
| C3 | available baseline before the open-time ≥ the required baseline window | shorter ⇒ **VOID** (never silently truncate) |

C3 is a second defect your §7 disclosed and I am ruling it a VOID rather than a truncation,
because a baseline shorter than the window is not a smaller baseline — it is a different
measurement wearing the same name.

**Consequence you should expect, and it does not change the reported result.** On my arithmetic
from the epoch start 18:59:14Z, a 900 s required baseline puts 19:08Z (~534 s) and 19:12Z (~766 s)
under C3 ⇒ both VOID; 19:30Z (~1,846 s) clears. Verify that mechanically rather than taking my
subtraction. **ROW 4 NOT REPRODUCED still stands on the 19:30Z reading**, so the conclusion
survives the fix.

**Do NOT re-run the check against this corpus to "confirm" ROW 4.** The row is reported and
stands as reported. Re-running a pre-registered check after seeing its result buys no information
and launders a post-hoc reading into a fresh-looking verdict. The fix is for the *next* use.

**And the row still does not clear the settings page.** Your §7 is right that no row votes "safe".

## 2. Correction — the `PASS_SLOPE_S_PER_H` comment

`drift_screen.py:90-93`. **The constant does not change.** `PASS_SLOPE_S_PER_H = 0.02` was fixed
in git before the run, governed this verdict, and stays exactly as it is — editing a threshold
after a result is the one thing that would retroactively damage the PASS.

Correct **only the comment**, so the next reader inherits the right figure: the bar sits **~640×**
above the 0.75 ms/24 h the fix predicts, not ~27×. Note in the same comment that the error was
conservative — it made the bar look tighter than it is.

Docs-only change to qa tooling, so HK-011 does not apply and this needs no Developer session.

## 3. Gate — `max abs lag` is monotonic, and the cap lift is what makes this live

**Do not build anything for this now.** This is registered so it cannot be forgotten, not
scheduled.

**The problem.** `PASS_MAX_ABS_LAG_S = 0.2` is checked against a **point maximum** over
correlations, which is monotonically non-decreasing in sample count. On the 18.96 h epoch it read
0.095 s — 2.1×, the tightest margin in the whole result, where every other statistic cleared by an
order of magnitude. A longer corpus raises that figure on noise alone, with a perfectly stationary
window, and drifts the screen toward ROW 4 INCONCLUSIVE for no physical reason.

**Why it is live now.** The ~6 h cap was the only thing preventing the long runs that break this
bar. Removing the cap removed the protection.

**The gate, as an assertion:** *any future drift screen run over an epoch materially longer than
18.96 h ⇒ `PASS_MAX_ABS_LAG_S` must be re-derived first; it may not be inherited unexamined.*
The same sentence applies to `PASS_SLOPE_S_PER_H` for a screen intended to catch **partial**
regression — a 640× bar is a considerably blunter instrument than a 27× one, and §6 of your report
makes that point better than my original comment did.

**My lean, for when this is actually designed — not a decision, and the Captain's to make.** Split
the two jobs the statistic is currently doing: keep a fixed absolute bar as a *catastrophe*
detector on the FAIL row (0.5 s is insensitive to sample size in any realistic corpus), and
replace the PASS row's point maximum with a high quantile, which is stable under growing N. The
slope is already the drift statistic; the point max should not be a second, worse one. Alternatives
worth costing at the time: scaling the bar with expected max of N, or dropping lag from the PASS
row entirely and resting it on slope. **I am not confident enough in any of these to fix one now,
which is the main reason this is a gate and not a task.**

## 4. Housekeeping — land the run, route the push

**Untracked / modified as of 14:16Z:**

- `qa/ARTEFACT_INVENTORY.md` (modified — regenerated, `--check` clean)
- `2026-08-04-1405-qa-to-architect-ft991a-cap-drift-screen-PASS.md`
- `drift_curve_20260803_live_run_1713.csv` (4,971 rows)
- `status-check-loop.log` — **decide, don't default**: commit it as a run artefact or gitignore
  it. It is adjacent to the open TODO on ad hoc console-log sinks; either answer is fine, an
  untracked file sitting there indefinitely is not.

**Four commits are unpushed on `main`, not one:** `becb344`, `eac11a9`, `dabf0fe`, `1ff4293`.
My memory note said "`becb344` unpushed" and understated it. **The push decision is the Captain's**
— route it to him with that corrected list. Per HK-014 I do not push or merge and am not asking to.

## 5. Filing — the 18:58Z heartbeat stall

File as a TODO; **do not chase it.** One occurrence, one non-recurrence, no mechanism. Record:
daemon PID 14600 went silent with the process still up, no `[ERR]`/`[FTL]`, `config.json`
unmodified, supervisor caught a >90 s stall at 2026-08-03 18:58:09Z and restarted, costing 4 cycles
and splitting this corpus into two epochs. Cadence over the full 18.96 h epoch was 13,655
heartbeats at 5.00 s with **zero** gaps ≥ 30 s and one 23.40 s excursion at 19:08:29Z.

Two things worth carrying in the TODO because they will not be obvious later: the settings page is
**not cleared**, and the sole anomaly in eighteen hours sits close to where the reproduction
attempt would have been. It cleared no bar and mandates no action. It is not nothing.

## 6. Not authorised by this work order

- **No capture run.** Check `qa/ARTEFACT_INVENTORY.md` before proposing one regardless — the cap
  lift makes long runs *permissible*, not *needed*.
- **No new arm.** S.1 authorisation, the B.3 menu and the T5 density penalty remain open under
  D-001 and are untouched here.
- **No `src/` change.** Everything above is docs or qa tooling.
- **No re-reading of §8.** The 8080-vs-WSJT-X decode correspondence carries no pre-registered rule
  and must not acquire verdict status by repetition.
