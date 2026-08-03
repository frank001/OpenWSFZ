# Architect → QA — HAND-OFF: T1 is closed, T4 needs no capture, and most of today's WSJT-X work was unnecessary
# ▶ THIS IS DOCUMENT 1 OF 2. Read this, then the T4 pre-registration. See README.md for the full order.

**Author:** Architect, 2026-08-02 (23:16 UTC, `date -u`, per HK-017). Repo at `684509e`.
**For:** QA. **Supersedes** the task list in `…-1813-architect-to-qa-handoff-…` (T1–T5 restated
below with current status).
**Nothing here is blocked on new capture.** One item is blocked on the Captain (T4).

| companion note | what it is |
|---|---|
| `…-2232-architect-to-qa-correction-launch-order-not-established.md` | the corrections, with two visible self-corrections on top |
| `…-1813-architect-prereg-angle1-baseline-deficit-decomposition.md` | **unchanged** — the amendment I proposed against it is withdrawn |
| `qa/ARTEFACT_INVENTORY.md` | new. Generated. Read before concluding data doesn't exist |

---

## Where today ended up, in five lines

- **T1 is answered and closed.** 99.97% WSJT-X WAV coverage on the matched population, at full
  corpus scale. N3 can return **MEASURED**.
- **T4 needs no capture run.** N3 is an offline `jt9` pass over **10,469 WAVs already on disk**.
  It is blocked on the Captain's authorisation and nothing else.
- **The launch-order defect is not established** — only one instance ever moved. Do not adopt a
  standing launch-order procedure.
- **N3 never needed two WSJT-X instances.** The three-profile rebuild, the eleven configurations
  and the launch-order diagnostic were all downstream of one misreading of N3.
- **Your §4 OpenWSFZ control was the most valuable result of the day**, and it points at an
  on-project defect we already have open (T9).

---

## Tasks

### T1 — WSJT-X WAV availability  ✅ **CLOSED. No action.**

Answered at full corpus scale from `artefacts/20260731_live_run_2004-8080/`:

| | |
|---|---:|
| WSJT-X WAVs on disk | **10,469** (43.6 h, `260731_200830` → `260802_155200`) |
| cycles in both live logs | 3,618 |
| …of those, WAV present | **3,617 = 99.97%** |

**N3 can return MEASURED.** Your original 99.45% figure (1832 note) was sound — it was invalidated
for the wrong reason, see T6.

⚠️ My 3,618 is a **raw-timestamp proxy**. The population of record is yours to set with
`apply_grid_snap`; the ~3,637 +0s stratum is the real denominator. Please re-derive rather than
inherit my number.

### T2 — Fold the design into the drift dev-task  ✅ **the DOCUMENT is done. The FIX is NOT.**

⚠️ **Corrected 23:23 UTC — my first wording said "DONE" without qualification and could be read as the
drift being fixed. It is not, and the implementation was never part of T1–T5.**

- **T2 as the 1813 hand-off scoped it — a *document* task — is complete.**
  `dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-after-pr118.md` carries the
  0.2 s acceptance bar (lines 25, 38, 105) and the oracle work (lines 81, 91, 100), including the
  instruction not to relax the tolerance to make it pass. Confirm on your side; I read a file, not
  your intent.
- **The fix itself is unimplemented and unscheduled.** `src/` per HK-011 — separate Developer
  session, Captain sign-off before push.

**What the drift actually costs** — measured on the 07-31 corpus, 8080 cycles matching the UTC grid
by elapsed uptime:

| hours | cycles | matched | match % |
|---|---:|---:|---:|
| 0–3 | 720 | 705 | 97.9% |
| 3–6 | 720 | 315 | 43.8% |
| 6–9 | 720 | 0 | **0.0%** |
| 9–12 | 720 | 0 | **0.0%** |
| 15–18 | 720 | 720 | 100.0% |
| 21–27 | 1,440 | 0 | **0.0%** |
| **total** | **10,475** | **3,618** | **34.5%** |

The sawtooth is the window walking off the grid and being reset by restarts. **Past ~6–9 h of
uptime the run contributes nothing to any paired analysis**, and **65% of the whole corpus is
unusable**. 48 ppm is a small number; losing two thirds of every long capture is not. T3 item 3's
~6 h cap is not a separate rule — it is this defect stated as an operating limit.

**Sequencing — the fix does NOT block T4.** The +0s stratum is drift-free *by construction*;
selecting grid-aligned cycles is precisely what removes drift. T4 runs offline on 3,618 cycles
already on disk and the fix would not change one number in it. The fix blocks **future capture**,
not current analysis:

```
T4 (offline, existing data)      <- not blocked by the drift fix
drift fix (src/, Dev session)    <- BLOCKS the next capture run
```

Do not gather another corpus before it lands, or two thirds is thrown away again.

### T3 — Record corrections  ✅ **items 1–3 ENACTED. Item 4 is yours and is NOT done.**

The Captain authorised memory writes at 23:0x. Items 1–3 are enacted in project memory:

| # | record | was | now |
|---|---|---|---|
| 1 | PR #118 | "fixed and merged" | **reopened** — label fixed, window still drifts 48.0 ppm; oracle passes green by construction |
| 2 | Voicemeeter | "~0 ppm, cannot drift" | **4.7 ppm**, crosses 1 s at 59.6 h — *no zero-drift control exists in any corpus* |
| 3 | session cap | "~12 h lifted" | **revoked — ~6 h on the FT-991A chain** until the fix lands |

**Item 4 remains open and is yours:** note ratio-of-sums as the standing estimator in
`qa/endurance/anova_common.py`. I checked — there is no mention of it in that file today.

### T4 — Angle 1  🟢 **AUTHORISED by the Captain, 2026-08-02 23:45 UTC. QA may begin.**

Execute the pre-registration exactly as written. My proposed §6 (AP) change is **withdrawn** (T6),
but note the prereg **has** been amended twice since the 1813 draft, both before authorisation and
before any data was seen, both making an undefined case defined and changing **no threshold**:

- **N3 gained an explicit non-finite guard.** It was the one null that failed *open* — `> 0.05 ⇒
  VOID` returns `False` on NaN, so a degenerate denominator silently passed. N1/N2 are
  `else ⇒ VOID` forms and already failed closed.
- **§4 gained ROW 5**, a catch-all. Rows 1–4 are exhaustive over the reals but not over NaN, so a
  NaN `F_dec` matched no row while §4 claimed the first matching row is the verdict.

Both were surfaced by QA's `ratio_of_sums()` returning NaN on a zero denominator (T3 item 4).

⚠️ **Known, benign selection effect — state it in the report, do not correct for it.** The +0s
stratum is drift-free by construction, which means it is drawn from roughly the first ~3 h after
each restart (drift < ~0.5 s). It is therefore *systematically the freshest portion of each uptime
segment*, not a random sample of the run. That is exactly what makes it valid for decoder-vs-capture
attribution — and per T9 it also keeps the population clear of the >2 s decode cliff — but it should
be named rather than left implicit.

Do not compute `F_dec` as a by-product of anything else.

What has changed is only the cost: **no radio, no capture, no second instance, no live run.**
Null N3 is `jt9` over `artefacts/20260731_live_run_2004-8080/wsjt-x/wav/`, compared against the
`wsjt-x/ALL.TXT` in the same folder.

⚠️ **The hardlink is not a problem for N3.** `wsjt-x/ALL.TXT` is the same inode in the `-8080` and
`-8081` folders — one WSJT-X instance gathered into both. That correctly killed your
*two-independent-captures* assumption. But N3 compares one instance against **itself**, so one
capture is exactly what it wants. The `owsfz` legs are genuinely distinct.

### T5 — Density penalty  ▸ still follows T4. No change.

---

## New, out of today

### T6 — Do **not** adopt a launch-order procedure  ▸ action: stand down

Your §8.1 asked for a standing decision. **Do not make one**, for two reasons:

1. **It isn't established.** Reading the paired `FT991A`/`Copy` ratio assumed a stable denominator.
   Against `SDRUno` as an external reference, `Copy` sits at **0.87–0.97 in both orders** — it never
   moved. Only `FT991A` moved (0.47–0.54 → 0.99–1.05). Order was also perfectly confounded with
   time: every original-order test ran before every reversed-order test, with no repeat.
2. **It's the wrong project.** Settling it means investigating WSJT-X's decoder internals. That is
   not ours to fix, and N3 already guards the only consequence that reaches our measurement — a
   suppressed decoder with healthy capture makes `jt9(WAVs)` overshoot `C` and trips the ±5% bar.

Two further corrections, both in the 2232 note: §3's stated rule is **inverted** relative to its own
tables (§8.1's recommendation is right, its rationale is backwards), and there is a **third regime
at ~0.85** in blocks 20:30–20:45 that §3's two-cluster claim doesn't cover.

**Also withdrawn: my own §7 A-B-A design.** It was authorised by nobody and should not be run.

### T7 — `JsonConfigStore.SaveAsync` dev-task  ▸ yours to author, per HK-000/HK-011

Your §4 side note is real and correctly diagnosed: `Path.GetDirectoryName` returns `""`, not
`null`, for a bare relative filename, so `?? throw` never fires and `Directory.CreateDirectory("")`
throws `ArgumentException`. `POST /api/v1/config` 500s when the daemon was launched with a relative
`--config`. Small, real, `src/`-side. Not blocking anything.

### T8 — Use the artefact inventory; the notes column is yours  ▸ new tool

`qa/ARTEFACT_INVENTORY.md`, generated by `python qa/artefact_inventory.py` (`--check` exits 1 if
stale). One row per run: UTC span, per-leg distinct cycle counts, WAV counts, **cross-folder
hardlink detection**.

It exists because HK-018 was violated four times today, most expensively by my recommending a
multi-day capture run for a corpus that had been sitting in `artefacts/` for two days. Every column
but `notes` is measured from disk. **`notes` is interpretive, lives in the script's `NOTES` dict,
and is yours to extend** — a blank cell is honest, a wrong note is the failure the file exists to
prevent.

### T9 — ✅ **SOLVED 23:48 UTC. It is the drift defect. Root cause is no longer unknown.**

**The Captain identified it in one sentence: "it's the cliff where the drift is over 2 seconds."**
Measured and confirmed — 8080/8081 decode ratio pooled over the three restart segments of the
07-31 corpus, against accumulated drift at 48.0 ppm:

| uptime | drift | 8080/8081 | |
|---:|---:|---:|---|
| 0–5 h | 0–0.86 s | 0.93–0.97 | flat, healthy |
| 6–11 h | 1.04–1.90 s | 0.95 → 0.81 | gradual decline |
| **12 h** | **2.07 s** | **0.713** | **cliff begins** |
| 13 h | 2.25 s | 0.426 | |
| 14 h | 2.42 s | **0.254** | past FT8's ~2.36 s guard interval |

**Two corrections to `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` — yours to
make, per HK-015:**

1. **"Root cause not yet known" → it is the `CycleFramer` clock drift** reopened in
   `dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-after-pr118.md`. **These are
   one defect, not two.** The drift fix closes both.
2. **"Reproduced once" → three occurrences in this corpus**, one per restart segment, at consistent
   uptime. It is not an incident; it is a deterministic function of uptime.

Every candidate the dev-task ruled out is *consistent* with drift rather than contradicting it:
power-cycling the radio didn't fix it (software, not RF); a process restart fixed it completely
(resets accumulated drift to zero); 8081 was unaffected throughout (**4.7 ppm reaches 2 s at
~118 h**, and the run was 43.5 h — it never approached the cliff).

⚠️ **This raises the drift fix's severity.** It is not merely "65% of cycles unusable for paired
analysis." It is **decode rate falling to ~25% of an identical reference instance past ~13.7 h
uptime, silently, with every health signal green.** The T3 item 3 cap of ~6 h is well-placed: at
6 h drift is 1.04 s and the ratio is still 0.930.

**How I got this wrong first, since the method matters more than the result:** I initially used
**grid-match %** as the drift proxy and concluded drift was *not* the cause. Grid% is a binary that
saturates at 0% once drift exceeds ~0.5 s (≈2.9 h uptime), so it sat pinned at zero from h5 to h14
while real drift climbed 0.86 s → 2.42 s. **A saturated indicator cannot reveal a threshold effect
above its saturation point.** Use accumulated drift in seconds, per uptime segment. Grid% answers a
different question (does the label match) and must not be substituted for drift magnitude.

### T9-b — the original framing, retained for provenance

This is the on-project version of what I spent today chasing in the wrong application.

That dev-task documents **our own 8080 daemon** collapsing from ~20–24 decodes/cycle to 1.45–3.05
after ~14 h uptime, with 8081 unaffected, hardware ruled out by power-cycling the radio, and a
**process restart clearing it completely**. Root cause unknown. High severity, because it silently
degrades the corpus while every health signal stays green — an HK-022 shape.

The structural resemblance to today's `FT991A` behaviour is real: one instance's decode rate
collapses, its pair is fine, config is identical, restart fixes it, cause unknown.

**I am flagging a resemblance, not asserting a common cause**, and there is at least one material
difference: `FT991A` was suppressed from the first logged cycle, not after long uptime. Treat the
connection as unverified.

What does transfer cleanly is **method**. `qa/cycleframer-alignment-replay/architect_launch_order_recheck.py`
demonstrates the technique that made today's collapse legible, and it applies directly to T9:

- restrict to cycles logged by **all** instances before comparing anything;
- carry a **third instance as an external reference**, so a paired ratio can't hide which side moved;
- report **decodes per common cycle**, ratio-of-sums;
- split by **FT8 sequence parity** to eliminate the "dropping one sequence" mechanism in one pass.

If T9 gets picked up, that is where I would start.

---

## Ordering

```
T1  CLOSED
T2  document done; FIX UNIMPLEMENTED, blocks next capture (not T4)
T3  item 4 only ─────────────────▶ QA
T6  stand down ──────────────────▶ no work
T7  draft dev-task ──────────────▶ Developer session later
T8  adopt in normal practice
T9  SOLVED -- it IS the drift defect; fold into the drift dev-task
                     │
T4  AUTHORISED 23:45 ─────────────▶ T5 design
```

**Everything except T4 is unblocked.** T9 is the only item where I would spend real time.

## One standing note

Four times today I concluded something I could have measured, and each time the Captain corrected
scope rather than reasoning. **Your §4 OpenWSFZ control and your hardlink catch were both right and
both mine to have built on sooner** — instead I extended the WSJT-X diagnostic, which was never
ours. Where a finding is about a third-party application, the question to ask first is whether any
of our nulls already bound its consequences. For N3, it did.

## Cross-references

- `2026-08-02-2207-qa-to-architect-…` §4 (the OpenWSFZ control), §6 (T1), §8 (answered above).
- `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md` — T9.
- `dev-tasks/2026-08-02-reopen-cycleframer-clock-drift-still-present-after-pr118.md` — T2.
- `qa/artefact_inventory.py`, `qa/ARTEFACT_INVENTORY.md` — T8.
- `qa/cycleframer-alignment-replay/architect_launch_order_recheck.py` — T6's figures, T9's method.

---

*Per HK-015 Architect → QA: tasks scoped for QA, `dev-tasks/*.md` yours to author — I have not
written T7's. Per HK-014/HK-010 committed locally, no push, no merge, and I do not ask for one. Per
HK-011 T2 and T7 are `src/` and need a separate Developer session plus Captain sign-off. Per HK-017
real `date -u` UTC. Per HK-018 T2's and T3.4's status were read off the files before being written
here rather than assumed, and T1's answer is measured, not inherited. Per HK-004 T8 is a tool that
exists, not a recommendation that one should. Per HK-012 T3 item 4 and T7 are surfaced explicitly so
they do not lapse. Per HK-021 T6 states what is not established and why, rather than substituting a
new rule. Per HK-022 T1's figure names its population and flags that the +0s denominator is yours to
set. NFR-021: aggregate counts only.*
