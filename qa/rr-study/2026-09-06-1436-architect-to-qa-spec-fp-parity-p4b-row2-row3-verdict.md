# `FP-PARITY` P4b — Architect → QA spec: the ROW 2 / ROW 3 verdict

**Architect, 2026-09-06 14:36Z** (`date -u`, HK-017). Base `main`@`1b7ca29` (PR #140, shim
`20260050`), current branch head `65e2017` (the docs-only chain this spec sits on: P3 spec `1311d55`
→ P3 execution `628f070`/`cf500d4` → P3 ruling `e813801`/`7dce5cf` → persona identity `65e2017`).
Docs-only; `git diff --stat -- src/ native/` empty, verified before commit (HK-014). **Local, not
pushed (HK-014).**

**This document is `FP-PARITY` Amendment 4.** Numbering check performed, not assumed: `AWGN-FP` has
no `A4.x` yet either. Everything numbered `A4.x` below is `FP-PARITY` A4.x.

**Executes:** the ROW 2 / ROW 3 predicate pre-registered in the base spec
(`2026-09-03-1616-architect-to-qa-spec-fp-parity-and-inchain-floor.md` §4 — "ROW 2: the emission
floor is viable" / "ROW 3: the margin is not there"), whose knife-edge shape and reporting
obligation were disclosed in advance by Amendment 1 A1.3 (2026-09-04), and which has been held for
P3 twice in writing — the 2026-09-04 14:11Z ruling ("P4b must not be run as a formality when P3
closes") and the 2026-09-06 09:51Z P3 spec §0 ("ROW 2 is P4b, and P4b is not in this document").
**P3 has now closed, without firing, on every row** (`e813801`, `2026-09-06 10:25Z`) — §0 below
restates that ruling's own authorisation trigger as an executable spec rather than leaving it as
board prose for QA to reconstruct.

**Preconditions you must have read (HK-018):** base `FP-PARITY` §2 (units/definitions, including
where `C = +1.622 dB` comes from) and §4 (ROW 1 / ROW 2 / ROW 3 — the predicate this executes,
**unchanged**); Amendment 1 A1.1 (the frozen 5-sweep ROW 1 population) and A1.3 (the reporting
obligation this spec turns into code); the ROW 1 report
(`qa/rr-study/fp-parity/results/2026-09-04-row1-excess-floor-report.md`) and its script/output
(`row1_excess_floor.py`, `row1_excess_floor_results.txt`); and the P3 ruling
(`2026-09-06-1025-architect-to-qa-ruling-p3-adjudication.md`) §2.4 and §5.

---

## 0. What P4b is, and the two things it must not become

**P4b answers one question:** given `F` (ROW 1, already landed) and `T` (now confirmed
production-valid by P3's ROW 0n-C), does `F − T ≥ 6.0 dB`? That predicate was fixed on 2026-09-03,
before either number existed (HK-021(k) — the split/threshold was chosen before the data). Nothing
about the predicate itself moves in this document.

🛑 **What P4b is NOT.**

1. **Not a re-measurement of `F` or `T`.** Both are frozen, pre-registered quantities — `F` under
   Amendment 1 A1.1's closed 5-sweep population (*"no sweep may be added or removed after ROW 1 is
   read"*), `T` under the base spec's `T ≜ C + 1.0 dB`, confirmed stable by P3 ROW 0n-C
   (`C′ − C = +0.030 dB`, non-fire). Recomputing either "for extra confidence" against a different
   population is a **new pre-registration**, not this row.
2. **Not a licence to build anything.** Even if ROW 2 fires, its own consequence text is *"QA
   authors the emission-side filter dev-task"* (HK-011: authors, and **stops**) — no filter code is
   written in this document or by executing it, and no Developer session is opened by this spec.

🔴 **Standing disclosure, unchanged:** the Architect is de-blinded on this arithmetic — `FP-PARITY`
A2.3 published `F − T = 5.378` against the 6.0 dB bar on 2026-09-04, **before P3 ran**, and the P3
ruling repeats it (§5). **Scoring stays suspended** (`AWGN-FP` A1.0). This spec's job is not to
discover that number — it is to make QA **re-derive it mechanically, from code, with the
disclosures A1.3 made mandatory** — so the record does not rest on the Architect's by-hand
arithmetic alone.

### 0.1 Why "the answer is already known" is not "there is nothing to run"

Restated because it is the exact trap A2.3 and the P3 ruling both named twice: **the verdict turns
on one decode's 1 dB readout quantum, and on which binary recorded it.** A pre-registered row whose
inputs happen to already be computed is still owed its own mechanical execution. Printing "ROW 3
fires" from the board's prose — without QA independently re-deriving `F`, the four-sweep
leave-one-out `F`, and the per-decode binary attribution from the underlying `truth.csv` /
`owsfz-all.txt` files — is exactly the *"run as a formality"* both documents warned against.

---

## 1. What this spec adds to the base predicate — codifying A1.3's obligation, not changing it

**A1.3 (2026-09-04) required, for whoever writes the ROW 2/ROW 3 verdict:** the lowest-5 table
**with the binary each decode was recorded on**, and the **four-sweep leave-one-out `F`** quoted
beside the five-sweep `F`. **Neither exists as code today.** `row1_excess_floor.py` prints the
lowest-5 and near-line tables with `sweep_id` (not a binary label), and explicitly declines to
compute a leave-one-out figure or render a verdict — its own final section is headed *"ROW 2 / ROW
3 — NOT DECIDED HERE"*. The four-sweep leave-one-out figure quoted in the 2026-09-04 14:11Z ruling
(`12/12` at −18 dB, `0/12` at −21 dB, `F = +8.00 dB` unchanged) was computed **by hand** against the
raw `row1_excess_floor_results.txt` output, not shipped as code.

**⇒ New script, `qa/rr-study/fp-parity/p4b_row2_row3.py`.** Build it by copying
`row1_excess_floor.py`'s exact method (same frozen `_FROZEN_SWEEPS` list, same ROW 0q `−0.5 dB`
correction, same `harness.common.parse_all_txt` against raw `owsfz-all.txt` + `truth.csv` — **never
`matcher.py`**, HK-026), and add exactly three things:

**(a) A sweep→binary-era table, pre-registered with its citation inline, not inferred:**

```python
# Binary era per sweep, per AWGN-FP ROW 0r (2026-09-04) + FP-PARITY Amendment 2 Ruling 2
# (2026-09-04 14:11Z): 2026-09-03-35378b9 is the first sweep ever run on 20260050;
# the other four sweeps in the Amendment 1 A1.1 frozen population are all <=20260049.
_SWEEP_BINARY_ERA: dict[str, str] = {
    "2026-08-27-22b749c": "<=20260049",
    "2026-08-29-872ba65": "<=20260049",
    "2026-08-30-2e60949": "<=20260049",
    "2026-09-02-3b52608": "<=20260049",
    "2026-09-03-35378b9": "20260050",
}
```

Assert `set(_SWEEP_BINARY_ERA) == set(_FROZEN_SWEEPS)` before doing anything else — **fires ⇒
STOP**, the frozen population and this table have drifted apart, which is a bigger finding than P4b.

**(b) The four-sweep leave-one-out `F`.** Recompute `F`, `p01`, `p05`, and the per-rung table over
the 48 slots belonging to every sweep **not** labelled `"20260050"` in the table above. **Derive the
drop set from the era table — do not hardcode "drop 35378b9" as a literal.** If the frozen list is
ever legitimately extended (which A1.1 currently forbids), a hardcoded drop would silently compute
the wrong thing instead of failing loudly.

**(c) Binary attribution on the lowest-5 and near-line tables.** For every row
`row1_excess_floor.py` already prints in its *"lowest 5 reconstructed excess values"* and
*"distinct decodes within ±1 dB of the fire line"* blocks, add the `_SWEEP_BINARY_ERA` label
alongside `sweep_id` and `cycle_utc`.

**This script's own internal guard — fires ⇒ STOP, not a ROW:** if the five-sweep `F`, or any
lowest-5/near-line row this script recomputes, differs **at all** from the values already committed
in `row1_excess_floor_results.txt`, STOP and report — ROW 1's frozen result has moved since it was
landed, which voids this spec until that is explained on its own terms.

⚠️ **What this cross-check cannot detect** (HK-022): a bug shared between the two scripts, since the
new one is a copy of the old one's method. It catches drift in the *input population* against the
committed record; it is not an independent verification of the reconstruction method itself.

---

## 2. The ROW 2 / ROW 3 predicate — restated verbatim, not redrafted

From the base spec (§4, unchanged by any amendment):

> **ROW 2 — the emission floor is viable, and the dev-task is authorised.** `T ≜ C + 1.0 dB` (one
> in-chain readout quantum above the highest false accept measured anywhere). **FIRES iff
> `F − T ≥ 6.0 dB`.** ⇒ QA authors the emission-side filter dev-task (HK-011: authors and **stops**)
> at that `T`, with acceptance criteria measured in-chain, and the rule-of-three 95% upper bound on
> genuine loss — never "costs nothing."
>
> **ROW 3 — the margin is not there. FIRES iff `F − T < 6.0 dB`.** ⇒ No dev-task is authored. State
> plainly: *the emission-side floor cannot be set with the project's required margin on the evidence
> available, because the genuine population reaches down to within `F − T` dB of the false-accept
> ceiling.* 🛑 **PARKED, not closed** — closing the route requires a population that reaches the
> decoder's true floor, which S1b's bottom rung may not. Do **not** soften this into "needs more
> data" and do **not** re-run with a smaller margin.
>
> ROW 2 and ROW 3 are exact complements by construction; exactly one fires.

**Inputs, both frozen, both cited rather than recomputed here:**

- **`F = +8.00 dB`** (upper bound) — ROW 1,
  `qa/rr-study/fp-parity/results/2026-09-04-row1-excess-floor-report.md`, over Amendment 1 A1.1's
  frozen 60-slot population. **§1 above re-derives this as a cross-check, not a new measurement** —
  disagreement is STOP, per §1's own guard.
- **`T = 2.622 dB`** — base spec `T ≜ C + 1.0`, where `C = +1.622 dB` is the maximum offline `excess`
  over 454 false accepts (base spec §2, citing
  `qa/rr-study/awgn-fp-replay/results/M1-M4-report.md` §4). **Confirmed production-valid by P3 ROW
  0n-C** (`2026-09-06-1025-architect-to-qa-ruling-p3-adjudication.md` §2.4): under the normalised
  production input contract, `C′ = +1.652 dB`, signed difference `C′ − C = +0.030 dB`, **0 of 432
  rows exceed `T`**. **This spec does not re-open that measurement** — it is P3's, already landed;
  P4b's only precondition on it is that it closed without firing, which it did.

**Compute and print, as code, in `p4b_row2_row3.py`:**

```python
F_FIVE_SWEEP = <recomputed by this script; must equal +8.00, cross-checked against the committed
                 row1_excess_floor_results.txt>
F_FOUR_SWEEP_LOO = <recomputed by this script, over the sweeps not labelled "20260050">
T = 2.622  # C=1.622 (base FP-PARITY spec sec.2, citing M1-M4-report.md sec.4) + 1.0,
           # confirmed by FP-PARITY P3 ROW 0n-C (non-fire, e813801 sec.2.4)
MARGIN = F_FIVE_SWEEP - T
FIRE_ROW2 = MARGIN >= 6.0
```

**Print, in this order:** `F` (five-sweep), `F` (four-sweep leave-one-out, beside it — A1.3's
mandatory pairing), `T` with its full citation chain, `F − T`, the 6.0 dB bar, the verdict, and the
lowest-5/near-line table with per-decode binary.

🛑 **If the four-sweep leave-one-out `F` would flip the verdict against the five-sweep `F`** (i.e.
`F_FOUR_SWEEP_LOO − T` falls on the opposite side of the 6.0 dB bar from `F_FIVE_SWEEP − T`) —
**STOP and report to the Architect rather than choosing one.** The pre-registered population for
ROW 1 / ROW 2 / ROW 3 is the frozen five-sweep set (A1.1); the four-sweep figure is a **disclosure**,
mandated by A1.3 precisely because it might do this, not an alternate predicate. **Do not adjudicate
this yourself** — a verdict-flipping disagreement between the registered population and a
robustness check is HK-021(k)/HK-025 territory, not a script's tie-break to make.

---

## 3. Units, scope, and what does not change

- Same units as the base spec: `excess ≜ signal_db − local_noise_db`, reconstructed at the **1 dB
  readout quantum** (`Ft8NativeResult.Snr` is `int`), ROW 0q's round-half-away-from-zero correction
  (`−0.5 dB` conservative adjustment) applied identically to the five-sweep and four-sweep-LOO
  figures.
- **`F` stays labelled an upper bound**, not the floor. The truncation statement (bottom-rung decode
  rate, base spec §2.3) is unchanged and must be restated here, not dropped, because this row cites
  `F` again: bottom rung (−18 dB) decodes at 100% pooled (15/15) ⇒ the true floor is demonstrably
  lower and unmeasured by this instrument (HK-026).
- **No new decode, no new sweep, no `src/`/`native/` change.** Every input is a re-read of
  `truth.csv` / `owsfz-all.txt` already on disk for the five frozen sweeps (A1.1) — the same files
  `row1_excess_floor.py` already reads. Assert `git diff --stat -- src/ native/` is empty and state
  it in the report.
- **No filter is built, whichever row fires.** A ROW 2 fire licenses QA to *author* a dev-task
  (HK-011: author, then stop — a Developer session builds it later, on the Captain's initiative); it
  does not license writing filter code in this session.
- Standing bars from the base spec §6 all still apply unchanged: the candidate-budget family stays
  closed, input scaling stays closed, no root-cause chase of ROW 0r's message-text fire, NFR-021
  applies to any new output.

---

## 4. What QA does, in order

1. **Confirm the precondition**: read the P3 ruling's §2.4/§5 (`e813801`) and verify `T = 2.622 dB`
   is stated there as confirmed and non-fired. If it reads otherwise, **STOP** — this spec assumes a
   closed P3; do not proceed on a stale reading.
2. **Write and run `p4b_row2_row3.py`** per §1–§2: five-sweep `F` (cross-checked against the
   committed `row1_excess_floor_results.txt` — mismatch is STOP), four-sweep leave-one-out `F`,
   per-decode binary attribution on the lowest-5/near-line tables, the mechanical ROW 2/ROW 3
   predicate.
3. **If the two `F` values disagree on which row fires**: STOP per §2's guard, report to the
   Architect, render no verdict.
4. **Otherwise, render the verdict** exactly as the firing row's consequence text reads (§2, quoted
   verbatim above) — if ROW 3, use its exact wording, including **"PARKED, not closed"**, and do
   **not** append softening language of your own.
5. **Report per HK-001.** Headline carries §0's bar: **P4b builds no filter, whichever row fires; a
   ROW 2 fire only authorises QA to author a dev-task, per HK-011.**
6. **NFR-021**: this row's outputs are excess values (floats), reported SNR integers, injected
   rungs, sweep directory names, cycle timestamps, and a binary-era label — no message text, no
   callsigns. Scan anyway, via the shipped scanner's own `scan()` (not a claim), before commit — and
   scan report prose too.
7. **Commit and STOP.** No dev-task is authored in this session even if ROW 2 fires — HK-011
   requires QA to *author* the dev-task as a separate artefact and stop there; a Developer session
   builds it later, on the Captain's initiative.

**HK-025 stands: QA may refuse any step here on HK-021(k) grounds without the Architect's
agreement.** Classify (validity vs. precision), evaluate both branches, and if the same row fires
either way it is decorative — refuse it and say why.

---

## 5. Predictions — calibration only, nothing gates on them

De-blinded, unchanged since `FP-PARITY` A2.3 (2026-09-04): **P(ROW 3) — near certainty**, since `F`
and `T` are both already frozen and the arithmetic (`5.378 < 6.0`) has been on the board since
before P3 ran. The only genuinely live uncertainty is whether the four-sweep leave-one-out `F`
(not yet shipped as code, only computed by hand) reproduces the 2026-09-04 ruling's figure
(`+8.00 dB`, unchanged) exactly — **P(§2's disagreement guard fires) ≈ 0.05**, because that figure
was already computed once from the same raw files, just not as committed, re-runnable code.
🔴 **My directional calls in this programme are poor** (0/2 at last count, plus a ROW 1 miss) — this
prediction leans entirely on arithmetic already public, not on judgement.

---

## 6. Reporting obligations, in addition to HK-001

1. `git diff --stat -- src/ native/` **empty**, stated.
2. `F` (five-sweep) **and** `F` (four-sweep leave-one-out) side by side, per A1.3.
3. `T` with its full citation chain: `C = 1.622` (base `FP-PARITY` spec §2, citing
   `M1-M4-report.md` §4) → `T = C + 1.0 = 2.622` (base spec §4) → confirmed by `FP-PARITY` P3
   ROW 0n-C (`e813801` §2.4, `C′ = 1.652`, non-fire).
4. The lowest-5 (or full near-line) table, **every row carrying its binary-era label.**
5. The exact verdict-row consequence text, quoted, not paraphrased — if ROW 3, **"PARKED, not
   closed"** must appear verbatim.
6. Any HK-021 fault found in this spec: flag and escalate (HK-025), do not silently repair.

**Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>**
**Claude-Session: https://claude.ai/code/session_01B4jo45WuCnaNnu6wbXnkMo**
