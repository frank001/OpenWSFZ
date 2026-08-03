# START HERE — reading order for this folder

**Maintained by:** Architect. **Last updated:** 2026-08-02 23:59 UTC (`date -u`, HK-017).
**Why this exists:** this folder now holds 20+ notes, several of which correct or withdraw parts of
earlier ones — including parts of themselves. Without an explicit order, the most likely failure is
acting on a withdrawn section. That has already happened once today.

---

## 🟢 If you are QA and picking up work right now, read these two, in this order:

### 1. `2026-08-02-2316-architect-to-qa-handoff-t1-closed-and-corrected-scope.md`
**THE ENTRY POINT.** Current status of every task, T1–T9. Start here even if you think you know
what you're doing — three tasks changed status after it was first written, and those changes are
marked inline.

### 2. `2026-08-02-1813-architect-prereg-angle1-baseline-deficit-decomposition.md`
**T4, AUTHORISED — this is the live work.** Execute exactly as written.
⚠️ It has been **amended twice**, both before authorisation and before any data was seen, both
marked inline: N3 gained a non-finite guard (it was the one null that failed *open*), and §4 gained
ROW 5 (rows 1–4 were exhaustive over the reals but not over `NaN`). **No threshold changed.**

**That is everything needed to start T4. Nothing below is required reading for it.**

---

## Read only if the entry point sends you there

| document | status | what it is |
|---|---|---|
| `2026-08-02-2359-architect-prereg-8081-decoder-leg-and-selection-check.md` | ⏸ **NOT authorised. Runs AFTER T4 reports.** | Does the +0s selection bias T4? Uses 8081's 10,409 aligned cycles. Does not amend T4, does not compute `F_dec`. |
| `2026-08-02-2232-architect-to-qa-correction-launch-order-not-established.md` | ⚠️ **§6.2 rewritten, §7 WITHDRAWN — DO NOT EXECUTE §7** | Why the launch-order rule isn't established, and two self-corrections. Read the correction blocks at the top *first*; they change what the body means. |
| `2026-08-02-1813-architect-to-qa-handoff-drift-fix-corrections-and-angle1.md` | 🔶 **task list SUPERSEDED** by the 2316 hand-off | Still the source for T2's design detail and T3's four record corrections. |
| `2026-08-02-1813-architect-design-cycleframer-grid-realignment.md` | ✅ current | The drift fix design. Folded into the dev-task already. |
| `2026-08-02-1813-architect-corrections-to-record-drift-controls-and-my-own-errors.md` | ✅ current | Six corrections; §6 is the ratio-of-sums / sign-flip case. |
| `2026-08-02-1741-qa-to-architect-grid-snapped-anova-rerun-result.md` | ✅ current | Tables A/B/C and the +0s stratum everything else builds on. |
| `2026-08-02-2207-qa-to-architect-wsjtx-launch-order-defect-and-t1-result.md` | ⚠️ **§3 rule inverted, §8.1 superseded** | QA's diagnostic. §4's OpenWSFZ control and the hardlink catch stand and matter. |
| `2026-08-02-1832-qa-to-architect-t1-wsjtx-wav-availability.md` | ❌ superseded | Its 99.45% figure was actually sound — it was invalidated for the wrong reason. See 2316 §T1. |
| earlier `2026-07-*` notes | 📚 provenance | Read only to trace how something was decided. |

## Tooling in this folder

- `architect_launch_order_recheck.py` — the three-way comparison method: restrict to cycles logged
  by all instances, carry an external reference leg, decodes per common cycle, parity split.
  **Reusable** — this is how the drift cliff was found.
- everything else — per-measurement scripts, named for their measurement.

## Two rules that have already been broken here

1. **Read the correction blocks at the top of a note before its body.** Several notes withdraw
   their own sections. The body does not always say so.
2. **Before concluding data doesn't exist, or proposing any capture run, read
   `qa/ARTEFACT_INVENTORY.md`.** A multi-day capture run was recommended today for a corpus that had
   been sitting in `artefacts/` for two days.
