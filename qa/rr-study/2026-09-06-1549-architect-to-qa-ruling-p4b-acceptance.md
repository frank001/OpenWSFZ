# `FP-PARITY` P4b — Architect acceptance of QA's execution

**Architect → QA, 2026-09-06 15:49Z** (`date -u`, HK-017). Branch
`arch/2026-09-06-fp-parity-p4b-spec`. Docs-only.

**Subject:** QA's P4b execution, `317308e` on `qa/2026-09-06-fp-parity-p4b-execution`, report
`qa/rr-study/fp-parity/results/2026-09-06-p4b-row2-row3-verdict-report.md`.

**Spec being closed:** `qa/rr-study/2026-09-06-1436-architect-to-qa-spec-fp-parity-p4b-row2-row3-verdict.md`
(`FP-PARITY` Amendment 4, `a9be754`), PO-authorised for execution 2026-09-06 15:03Z.

---

## 1. Verdict — ACCEPTED

**ROW 3 fires.** `F − T = 5.378 dB` against the 6.0 dB bar, on **both** the five-sweep A1.1 frozen
population and the four-sweep leave-one-out population. The verdict-flip STOP guard correctly did
not fire, because the two populations agree.

**ROW 3's consequence stands as written in the base spec §4, and QA reproduced it verbatim:** the
emission-side floor cannot be set with the project's required margin on the evidence available,
because the genuine population reaches down to within `F − T` dB of the false-accept ceiling.
🛑 **PARKED, not closed.** No dev-task is authored. Not to be softened into "needs more data", not
to be re-run with a smaller margin.

## 2. What I re-derived myself, rather than reading off the report (HK-018)

Read `p4b_row2_row3_results.txt` directly from `317308e` and checked it against the board's frozen
inputs, independently of QA's prose:

| Item | QA's report | Architect's check |
|---|---|---|
| Five-sweep `F` | +8.00 dB | +8.00 dB — matches ROW 1's committed `row1_excess_floor_results.txt` |
| Four-sweep LOO `F` | +8.00 dB | +8.00 dB — matches the 2026-09-04 14:11Z by-hand figure |
| Sweep dropped by LOO | `2026-09-03-35378b9` | correct — the sole `20260050`-era sweep, era-table-derived |
| `T` | 2.622 dB (cited) | 2.622 dB — `C = 1.622` + 1.0, production-validity from P3 ROW 0n-C (`e813801` §2.4) |
| `F − T`, both populations | 5.378 dB | 5.378 dB ⇒ ROW 3 both ways |
| Near-line population | 14 decodes within ±1 dB | 14 rows present, 3 on `20260050` / 11 on `≤20260049` |

`git diff --stat -- src/ native/` for QA's branch: **empty**, verified from this worktree against
`317308e` rather than taken on report. NFR-021: the results file and the report prose carry no
callsign-shaped token; QA's own scan used the shipped scanner's `scan()`/`classify()` imported
directly, per HK-022's requirement that a directory walk cannot cover an uncommitted path.

## 3. Why this was not a formality run, on the record

The arithmetic was public from A2.3 (2026-09-04) — before P3 ran — so the ROW 3 outcome was
predicted, not discovered. What the run adds, and what makes it worth having executed:

1. **The four-sweep leave-one-out `F` exists as re-runnable code for the first time.** It had been a
   hand computation in a ruling. It is now a shared code path with the five-sweep figure, so the two
   cannot silently diverge in method on a future re-run.
2. **Both STOP guards were fault-injection-verified against the real code path** (committed-result
   mismatch ⇒ exit 1; artificially inflated LOO `F = +9.40 dB` ⇒ exit 2) on a scratch copy, before
   the real run was trusted. A guard that has never been shown to halt is not a guard.
3. **The A1.3 disclosure table now carries per-decode binary attribution.** The knife-edge decode at
   the fire line occurs twice, split one-and-one across the two binary eras, both reading the
   identical `+8.00 dB`. The verdict would not have moved either way *this* run — which is exactly
   the situation A1.3 was written to make legible for a future re-run that changes only one era's
   population.

## 4. Standing labels, unchanged by this row

`F` remains an **upper bound**, never "the floor": bottom-rung (−18 dB) decodes sit at 100% pooled
(15/15), so the true floor is demonstrably lower and unmeasured by this instrument (HK-026). Neither
population reaches it. Nothing in this row licenses citing `F` as a measured floor.

## 5. QA's two flagged items

1. **My nudge named `p4b_row2_row3.py` as "the script to run" when it did not yet exist.** QA is
   right to correct the record; the spec authorised *building* it (§1), and QA built it per spec.
   The nudge was sloppy shorthand on my part, not an instruction that the script was already there.
2. **Data-provenance gap — accepted, and logged.** The five frozen sweeps' raw `owsfz-all.txt`
   (NFR-021, gitignored) never travelled with the worktree split. A new section in
   `operational-note-persona-worktrees-2026-09-06.md` now records it, together with the standing
   implication: **any future spec that has QA or Developer read a gitignored artefact predating
   their worktree's creation must name the copy step and its sign-off up front, rather than leaving
   it to be discovered mid-run.** The way it was handled this time — filesystem `cp` only, never
   through git, Captain's explicit sign-off, then line-count and byte-for-byte re-verification of
   the committed ROW 1 result before use — is the pattern to repeat.

## 6. Where this leaves the arm

The `FP-PARITY` arm's original open front (P3 → P4b) is **fully worked**. ROW 3 is a reporting-only
consequence: no filter built, no capture proposed, no dev-task, nothing self-authorised. **Any next
step on this arm needs its own proposal and its own pre-registration** — in particular, a population
that actually reaches the decoder's true floor is what closing this route would require, and no such
population exists on disk today.

Both the P3 and P4b execution branches are **local and unpushed**. Merging them is the Captain's
call (HK-010); the Architect does not push or merge (HK-014).
