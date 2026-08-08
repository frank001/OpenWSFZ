# Architect → QA: spec P1 — how much of the D-001 gap is decode DEPTH rather than capability?

**Author:** Architect, 2026-08-08 (23:57 UTC, from `date -u`, per HK-017 — local had rolled to 08-09;
UTC governs). Repo `main` at `0eeb6b9`.
**Status:** offline replay of WAVs already on disk and inventory-verified. No `src/` change, no
capture, no rebuild, no Developer session, **and nothing to reconfigure in WSJT-X.**
NFR-021: counts and rates only — **no message text or callsign in output, report, or harness.**

---

## 0. The question, and why it might shrink the problem rather than describe it

Every recovery figure in this programme means **"against WSJT-X at `NDepth = 3`"** while OpenWSFZ runs
`K_MAX_PASSES = 2` with candidate caps 140/200. That asymmetry has been **on record since 2026-08-06
and never quantified.** It is the only stated reason to think part of the ~42% deficit is
*configuration* rather than *capability*.

If depth turns out to be worth little, a caveat that currently rides on every recovery figure gets
replaced by a measured bound — and the architectural case for sync refinement hardens. **This is the
one open arm that can make the problem smaller rather than better-described.**

Context that bounds expectations before anything runs: **`FT8AP = false`** — a priori decoding, WSJT-X's
biggest recall lever, is **off**. And **RC4 already showed a third pass in *our* decoder buys nothing**
(ROW 2). Neither settles this: WSJT-X's depth dial and our pass count are different mechanisms.

## 0.1 🔴 Why the barred instrument is admissible here — LEVEL vs CONTRAST

**`jt9 -d 3` offline is barred as a reference decoder.** It overshoots WSJT-X by **+11.2%** on
WSJT-X's own audio and OpenWSFZ by **+93.8%** on OpenWSFZ's, and it emits duplicate `(ts, message)`
pairs. That bar is real and stands.

**It bars a LEVEL. This spec measures a CONTRAST.** `jt9 -d1` vs `jt9 -d3` on *identical files
through an identical invocation* differs in one flag; the overshoot and the duplication are
**common-mode and cancel.** The standing rule attached to that very bar says so explicitly:
*"before assuming the bar kills a figure, check whether it is a LEVEL or a CONTRAST — bias corrupts
levels far more than slopes."* This is that check, applied.

## 0.2 🛑 The result is an UPPER BOUND, and the gate is deliberately asymmetric

The barred-instrument note carries a named, unverified hypothesis for the overshoot: **live decoders
run under a ~15 s real-time budget; offline batched jt9 has none and can exhaust the full depth-3
multi-pass search per file.**

If that is right, some of what `-d3` finds offline is bought with *time WSJT-X did not have live*.
**So this measurement overstates depth's true live contribution.** Therefore:

> **A small result CLOSES the question. A large result does NOT establish that depth costs us that
> much** — it establishes only that depth costs us *at most* that much, and that a time-budgeted
> instrument is needed before anyone acts on it.

**Say this in the report regardless of which row fires.** A one-directional instrument is still worth
running when it is this cheap and the closing direction is the useful one.

---

## 1. Scope and prohibitions

**In scope:** the 20m leg, clean window `260808_004000`..`260808_111500`, **WSJT-X FT991A's own WAVs**
— `artefacts/20260808_live_run_0016-8080/wsjt-x/wav/` (2 748 files, named `260808_HHMMSS.wav`).

**Use WSJT-X's own audio, not ours.** It removes the capture-path variable, exactly as Angle 1's N3
null did. Do not mix in the OpenWSFZ `wav/` directories.

🛑 **1.1 `jt9` output may NEVER be quoted as a level, a reference, or a decode count in its own right.**
Only the d1↔d3 contrast leaves this document. `F_dec = 1.2455` remains uncitable.
🛑 **1.2 Do not re-read T1, T2, H1 or H1a.** Different thread; none of `G`, `D_int`, `U`, `M` appear here.
🛑 **1.3 Do not reconfigure WSJT-X, or propose that anyone does.** WSJT-X setup is the Captain's, and
this arm exists precisely so nothing has to change.
🛑 **1.4 No capture run.** Everything needed is on disk and `--check` clean.

---

## 2. Method

Invocation, identical on both legs but for `-d`:

```
jt9.exe -8 -d 1 <file>        D:/WSJT/wsjtx/bin/jt9.exe
jt9.exe -8 -d 3 <file>
```

Record the exact command line and jt9 build in the report. Parse decodes to `(ts, message)` keys,
`ts` taken from the **filename** (`260808_HHMMSS`), so keys join directly against `ALL.TXT`.

**Dedupe `(ts, message)` identically on both legs.** Angle 1's N4 established jt9 emits duplicates
from its own multi-pass search; that is common-mode but must be handled the same way on each side.
**Report raw and deduped counts for both legs.**

### 2.1 Timing probe FIRST — do not launch a blind multi-hour run

Run **20 files at each depth**, measure wall-clock, extrapolate to 2 748 × 2.

- **Extrapolated total ≤ 90 min** ⇒ run the full window.
- **> 90 min** ⇒ run a **random subsample of 1 000 cycles**, seed recorded, **drawn before any decode
  output is inspected.** Both depths run on the *identical* subsample.

Report which path was taken and the measured rate. ⚠️ **Choosing the subsample after seeing results
is fishing — the seed and the draw go in the report.**

### 2.2 Populations

- `REF` = intersection of the two WSJT-X instances on `(ts, message)`, same window — **the same 69 222
  denominator T1/T2/H1 use.** Restrict to cycles actually replayed.
- `MISS` = `REF` \ OpenWSFZ 8080 — the gap this programme is about.
- `D1`, `D3` = deduped jt9 decode sets at each depth.

### 2.3 Metrics

```
A = 100 * |MISS  ∩  (D3 \ D1)| / |REF|      <- the headline: the share of the reference
                                               population that we miss AND that only
                                               depth-3 recovers.  Same axis as G, D_int, M.
B = 100 * |D3 \ D1| / |D1|                  <- raw depth yield, context only
C = 100 * |D1 ∩ REF| / |REF|                <- what offline d1 alone already recovers
```

`A` is the decision-relevant number: a percentage-point contribution to the gap, directly comparable
to `G = 3.16`, `D_int = 4.03`, `M = 2.26`.

⚠️ **`C` is worth reading carefully.** If offline `d1` already recovers most of `REF`, then the
**unbudgeted-time effect dominates over depth**, `A` will be small for a reason that has nothing to do
with the depth dial, and §0.2's caveat becomes the whole story. Report `C` prominently either way.

### 2.4 🔴 Cluster the error bars — HK-021(i), and it is three hours old

`A` is a count over decodes, and **decodes cluster by frequency** (`r` and recovery are station-level;
design effect measured at **3.5–4.2×** on this same corpus, `t2a_design_effect_diagnostic.py`).

**Report a frequency-clustered bootstrap CI on `A`** — resample distinct reference frequencies with
replacement, ≥400 draws, seed recorded. 🛑 **A binomial interval on `A` is wrong and must not appear.**
I mispriced clustering in prose on T2 and the gate was underpowered by 3.5×; **compute it here.**

---

## 3. Pre-registered gate (HK-021)

```python
def p1_row0(n1_raw, n1_dedup, n3_raw, n3_dedup, ratio_d3_live, n_cycles):
    if n_cycles < 800:
        return "ROW 0a"   # too few cycles replayed to read A at all
    if n3_dedup == n1_dedup:
        return "ROW 0b"   # depth flag had no effect: wrong invocation, not a finding
    if not (0.90 <= ratio_d3_live <= 1.40):
        return "ROW 0c"   # Angle 1 measured 1.112 for d3 vs FT991A live; outside this the
                          # instrument has changed and nothing is comparable
    if n1_raw == n1_dedup and n3_raw == n3_dedup:
        return "ROW 0d"   # dedup removed nothing on either leg -- N4's duplicate defect is an
                          # established property; its absence means the parser is wrong
    return None

def p1_gate(a):
    if a >= 5.0:
        return "ROW 1"
    if a <= 1.5:
        return "ROW 2"
    return "ROW 3"
```

`ratio_d3_live` = `|D3|` ÷ WSJT-X FT991A's own **live** `ALL.TXT` decode count over the replayed
cycles. **ROW 0c is a bound against a number already believed** (Angle 1's +11.2%), per HK-021(e).

| row | consequence — as an assertion |
|---|---|
| **ROW 0a–0d** | **Instrument failure, not a null.** Report the failing check and its value. The depth caveat stays exactly as it is today. Do not repair-and-rerun in-session without fresh pre-registration. |
| **ROW 1** (`A ≥ 5.0`) | **Depth is a material *upper bound* on the gap — and that is ALL it is (§0.2).** 🛑 Do **not** restate any recovery figure, and do **not** subtract `A` from the deficit. Assert into the board: the depth asymmetry needs a **time-budgeted** instrument before it can be priced, and the sync-refinement build case cannot be sized until then. Escalate to the Captain as a blocking uncertainty, **with `A` and its clustered CI**. |
| **ROW 2** (`A ≤ 1.5`) | 🔴 **CLOSE the depth question.** Depth is not a material part of the deficit even at its upper bound. **Replace the standing "every recovery figure is against `NDepth = 3`" caveat with the measured bound `A`** in the 1942 report §8 and on the board — edit it, do not annotate. The architectural reading (demodulation/sync) **hardens**, and the case for building sync refinement is correspondingly stronger. |
| **ROW 3** (`1.5 < A < 5.0`) | Report `A` and its CI. **Keep the depth caveat but quantify it** — it stops being "some unknown part" and becomes "at most `A` pp." No restatement of any headline. |

---

## 4. Architect's recorded predictions

| # | prediction | tested by |
|---|---|---|
| 1 | `|REF|` over the replayed window reproduces the T1/H1 population scale (≈69 222 if full window) | §2.2 |
| 2 | `ratio_d3_live` = **1.05–1.25** (Angle 1: 1.112) | ROW 0c |
| 3 | `C` ≥ **70%** — offline `d1` alone already recovers most of `REF` | §2.3 |
| 4 | `A` = **2–6 pp** | the gate |
| 5 | **ROW 3** | the gate |
| 6 | clustered CI on `A` is **≥3× wider** than a binomial one would be | §2.4 |

⚠️ **Weight prediction 5 lightly and say so in the report: my categorical ROW calls are running 2 of 4
(T1 miss, H1-A hit, H1-B miss, H1a hit) while my ranges run 3 of 5 — and both range misses were too
*pessimistic* about how cleanly an effect separates.** Prediction 4 is a range; 5 is a categorical call.

## 5. Deliverables

1. Harness `qa/cycleframer-alignment-replay/p1_decode_depth_contrast.py`. Reuse T1's `load()` for
   `ALL.TXT` parsing so `REF`/`MISS` are provably the same populations.
2. Report `…-qa-to-architect-p1-decode-depth-contrast-results.md`, filename and byline from real
   `date -u` and in agreement (HK-017): the timing probe and which path was taken; raw and deduped
   counts both legs; `A` with its **clustered** CI, `B`, `C`; the ordered gate trace; predictions
   scored; **§0.2's upper-bound caveat restated whichever row fires**; citation limits.
3. If **ROW 2** fires, the §3 edits to the 1942 report §8 and `BOARD.md`, **same edit** (HK-024).
4. **No push, no merge, no `src/` change, no WSJT-X reconfiguration.** Committing is the Captain's
   call (HK-010/HK-014).

## 6. Citation limits set in advance

**May be cited:** `A` **always as an upper bound, always with its clustered CI**; `B` and `C` as
context; the gate row; the timing/subsample provenance.

🛑 **May not be cited:** any `jt9` decode count as a level or reference (§1.1); `A` as "the amount
depth costs us" rather than "at most"; `A` subtracted from the 42% deficit or from the 57.8% recovery
figure; any binomial interval on `A`; any restatement of `G`, `D_int`, `U`, `M`, or the recovery
headline.
