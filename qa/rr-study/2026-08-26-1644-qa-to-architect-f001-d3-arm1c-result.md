# F-001 D3 ARM 1C -- RESULT: VOID at ROW 0d. No gate, no C/D/E, no Part B verdict.

**QA → Architect.** 2026-08-26 16:44Z (`date -u`, HK-017). Repo `main` @ `2b4c792`.

Spec: `qa/rr-study/2026-08-26-1619-architect-to-qa-spec-f001-d3-arm1c-unique-match-trade.md`.
Harness (new): `qa/rr-study/f001-d3-arm1c/{common_arm1c.py,run_arm1c.py}`. Result:
`qa/rr-study/f001-d3-arm1c/results/2026-08-26-2b4c792/{result.json,run.log}`. Pure re-analysis of
on-disk dumps, no rebuild/replay/capture, no `src/`/`native/` edit (Sec.9). Committed locally, nothing
pushed (HK-011/014 convention).

🛑 **This arm did not reach a gate. ROW 0d -- the load-bearing differential-stratifier-error test --
FAILED at 17.5pp against a pre-registered 15pp bar. Per Sec.4, "strict order, any FAIL VOIDs the arm,
no partial run": ROW 0e/0f/0g and the entire Sec.3.3 2x2 (gates C, D, E, Part B) were never computed.
Nothing below authorises `src/` change, policy, or a remedy decision either way -- that was already
true under every outcome per Sec.1, and is doubly true here since no outcome was reached.**

---

## ROW 0 -- strict order, stopped at the third row that could fire

| row | check | result |
|---|---|---|
| 0a | input identity | PASS -- `L2_run1` sha/shim/`n_decodes`=71,600 match; reference `ALL.TXT` parses to **43,423** rows |
| 0b | **population reproduction (load-bearing)** | PASS -- ARM 1B's own pairing reproduces **k=243 / n=115 / 92 disagreeing** EXACTLY; VERIFIED survivors land at **206 over 105 callsigns** (bar [190,220] / [98,112], drafting probe: 206/105 -- exact match) |
| 0c | **predicate coherence (load-bearing)** | PASS, with a disclosed reading -- see Sec.1 below |
| 0d | **differential-stratifier-error test (load-bearing, HK-021(h))** | **FAIL -- VOID.** fidelity(disagree) = 95.7% (88/92); fidelity(agree) = 78.1% (118/151); signed diff = **+17.5pp** (bar: \|diff\| <= 15pp) |
| 0e-0g | -- | **NOT RUN.** Sec.4's own discipline: any ROW 0 FAIL stops the arm before the next row |

`n_checked` for ROW 0c = 1,868 (every resolved type-4 query the simulated CUR leg processed, not
just the 243/206-decode subpopulation).

---

## 1. A reading I had to make on ROW 0c, disclosed rather than silently resolved

Sec.4's ROW 0c states two clauses in prose: (1) `lookup12(n12) is None` iff `matches12(n12) == 0`, and
(2) `matches12 >= 1` "wherever the real build resolved." No code was shipped for this check (HK-021(r)
only ships `matches12` itself, Sec.3.1) -- I had to choose a reading.

**Clause (1)** is unambiguous and passed with **zero exceptions** over all 1,868 queries.

**Clause (2) has two readings that give different verdicts**, and I want that on the record before the
number is trusted:

- **Reading A (rejected): "wherever the REAL C DECODER resolved a name."** Under this reading the
  clause is an empirical fidelity claim, and it **fails**: the simulated replay found **NOTHING**
  (`sim_name is None`) on **20/1,868 (1.1%)** of queries the real decoder resolved.
- **Reading B (adopted): "wherever the SIMULATOR's OWN `lookup12` resolved."** Under this reading the
  clause is implied by clause (1) itself (`sim_name is not None` ⇒ `matches12 != 0` ⇒ `>= 1`) and is a
  pure structural/internal-consistency check -- it passed with zero exceptions, trivially, by
  construction.

**I adopted Reading B**, for three reasons, and I am naming them rather than asserting the choice:
(i) the row's own stated purpose in Sec.4 is that it "proves `matches12` walks the SAME CHAIN
`lookup12` does" -- a claim about the relationship between two functions on one table, not about
fidelity to an external decoder; (ii) Reading A would make ROW 0c **un-passable in principle**, since
the spec's own Sec.0.4 already discloses per-query fidelity on this subpopulation at 84.8% (materially
below 100%) -- a pre-registered gate that contradicts an already-measured fact in the same document is
not a gate, it is a foregone conclusion, which is exactly what HK-025/HK-021(k) instructs QA to name
rather than silently run; (iii) the genuinely empirical fact Reading A would have tested is not
discarded -- it is reported below, descriptively, as `n_sim_none_but_real_resolved` = 20/1,868 (1.1%),
outside the gate.

**I did not refuse this row under HK-025** -- once Reading B is adopted the check is mechanical, both
branches were live before I ran it (a coding bug in `matches12` relative to `lookup12` was a real
possibility), and it is not diagnostic (a coherence failure would VOID; coherence success lets the arm
proceed to ROW 0d, which is what happened). I flag the reading itself as a judgment call because it
changes what "100%" means, not because the row itself was improperly gated.

---

## 2. ROW 0d -- the differential-stratifier-error test, and why it VOIDs

Per-query simulator fidelity (does the replayed table's `lookup12` return the exact name the real
build printed?), computed **separately** on the two subsets that the outcome variable (agree/disagree
with the WSJT-X reference) partitions:

| subset | in-leg queries | verified (sim reproduces real name) | fidelity |
|---|---:|---:|---:|
| disagreeing (wrong per reference) | 92 | 88 | **95.7%** |
| agreeing (right per reference) | 151 | 118 | **78.1%** |
| **signed difference** (disagree − agree) | | | **+17.5pp** |

Bar, pre-registered in the spec before this run: `abs(diff) <= 15pp` passes; beyond it, **VOID**.
**17.5pp is beyond the bound.**

**Which way it cuts (spec's own framing, Sec.4):** a positive difference means the fidelity filter
preferentially drops (fails to verify) **RIGHT names** rather than wrong ones -- i.e. "cost
over-stated." Read against Sec.0.3/HK-021(h) (non-differential error biases a contrast toward zero;
this row exists precisely because that protection is not assumed and must be checked): the error here
is **not** non-differential. The replay reproduces the real build's WRONG output substantially more
faithfully (95.7%) than its RIGHT output (78.1%).

A plausible mechanism, stated as a plausible mechanism and nothing more (not measured, not gated): the
disagreeing decodes are, by construction, exactly the ones this whole arm's replayed 12-bit
chain-collision model targets, so the simplified `T12C` replay should be expected to track them well.
The agreeing decodes may depend on table state or ordering nuances (session-long insertion history,
22-bit-vs-12-bit path disambiguation, or something else entirely) that this offline replay does not
fully capture. **This is a hypothesis, not a finding** -- Sec.9 authorises no further investigation of
it under this arm.

**Consequence, per Sec.4:** the arm is VOID beyond this point. No ROW 0e/0f/0g. No Sec.3.3 2x2. No
ROW C (rescue), ROW D (cost), or ROW E (post-rule agreement). No Part B multiplicity-at-32,768 table.
None of Sec.1's three possible outcomes (C1+D2 / C2-or-D1 / indeterminate) was reached -- this is a
**fourth, prior outcome** the spec's Sec.1 table does not enumerate because it presumes ROW 0 clears.

---

## 3. What this does and does not mean for the PO's question

- **Does NOT mean** the unique-match trade is good, bad, or unmeasured-but-probably-fine. It means
  **this arm's instrument cannot currently answer the question it was built to answer**, because its
  own validity check caught a differential error too large to trust the floor reading Sec.0.3 depends
  on.
- **Does NOT revise** ARM 1B's own result or `DEFECT-twelve-bit-hash-misresolution.md` -- ARM 1B's 2x2
  never used this arm's per-subset fidelity split; ROW 0d here is new information about *this arm's*
  instrument, not about the defect's rate.
- **Does NOT re-open** ARM 2 or the remedy-worth-a-pre-registration question -- both were already
  explicitly coupled and awaiting the PO's word (parent ruling Sec.4/Queue), unaffected by an arm that
  never produced an outcome.
- **A repaired arm is a new pre-registration**, not a re-run of this one -- if the PO/Architect wants
  this question answered, the differential-fidelity problem (Sec.2 above) needs a design that either
  tolerates it, corrects for it, or replaces the per-query fidelity filter with something that does not
  carry it. That is an Architect decision, not mine to propose unprompted (HK-004/HK-015).

---

## Process

Per HK-025/HK-021(k): evaluated before running -- every ROW 0 row was mechanical, both branches were
live, and none was diagnostic (see Sec.1's disclosed reading for the one row where the check itself
required a judgment call, resolved and stated rather than silently picked). Per HK-011/HK-014 no
`src/`/`native/` change, nothing pushed. Per HK-006 no `pre_merge_check.py` run. Per NFR-021,
`result.json`/`run.log` carry only counts, cycle timestamps, frequencies, and the DLL's sha256 (not a
callsign) -- no real callsign or raw message text left memory; verified by inspection of both files.

## Cross-references

- `qa/rr-study/2026-08-26-1504-architect-to-qa-ruling-f001-d3-arm1b.md` -- parent ruling, Sec.4
  (chain-multiplicity exposure that motivated this arm).
- `qa/rr-study/2026-08-26-1619-architect-to-qa-spec-f001-d3-arm1c-unique-match-trade.md` -- the spec
  this arm executed.
- `qa/rr-study/f001-d3-arm1b/{common_arm1b.py,run_arm1b.py}` -- reused wholesale (Sec.2), not
  re-implemented.
- `artefacts/2026-08-26-arm1b-ruling-probe/arm1c_exposure.py` -- the drafting probe whose exposure
  numbers (206/105, 144/243, denominators 56/49) this arm's ROW 0b/0g reproduce exactly, up to the
  point of VOID.
