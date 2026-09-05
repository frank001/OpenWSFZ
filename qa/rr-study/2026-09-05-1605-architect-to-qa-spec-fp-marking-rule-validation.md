# `FP-MARK` — Architect to QA: validate the geographic-implausibility marking rule before it is built

**Architect, 2026-09-05 16:05 UTC** (`date -u`, HK-017). PO-directed, 2026-09-05, on the scope draft
`2026-09-05-1555-architect-scope-draft-fp-flagging-measurement.md` (§8 item 1 approved, plus the
feature's form ruled: **mark, do not delete; "dismissed" instead of delete; a settings toggle to show
or hide marked decodes**).

**This spec is PRE-REGISTERED and armed. It is QA's to execute.** It is an **offline analysis of data
already on disk** — no live run, no hardware, no rebuild, **no `src/` or `native/` change**.

🛑 **QA draws no verdict on whether the feature ships.** Mechanical row outcomes only, as in
`S5-BASELINE`, `FP-COMPOSITION` and `S5-STANDALONE`. Adjudication is the Architect's; ratification is
the PO's (HK-015).

---

## 0. What this measures, and what it can never settle

**Measures:** how often a categorical grid-vs-region implausibility rule fires on **real** traffic —
the cost side of the marking feature.

🛑 **Does not settle, and no row may be read as settling:**

- **The hash half.** 29.2% of labelled FPs carry a hash reference; 12/21 put it in the addressee
  slot. A grid rule has **no prefix to resolve there, therefore no region, therefore no
  contradiction** — it is blind, not weak. Out of scope by construction.
- **The severe case** (an FP resolving by h12 collision to this station's own callsign). **0 of
  241,000 decodes across all seven live corpora name `PD2FZ`** ⇒ own-call h12 residency never
  occurred ⇒ **structural exposure zero in every corpus we own.** 🛑 **HK-026: these corpora are FLAT
  where that boundary sits. A null here is uninformative about it and must never be reported as
  reassurance** (HK-021(j) — an exposure of zero, not an absence).
- **Anything about the S5 AWGN FP *rate*.** This measures a proposed rule's cost, not the rate. The
  `FP-REGRESSION` line stays closed and `21/840` is still not a baseline (guard (e)).

---

## 1. Established — do not re-derive (HK-018)

All computed 2026-09-05 from data already on disk. Re-run only if a row below requires it.

| Fact | Value | Source |
|---|---|---|
| Windowed S5 OpenWSFZ FP decodes | **72** across 13 runs | `S5_matched.csv` × 13, scoped by `analyse.py`'s own `fp_in_window` (guards §0.2) |
| — **evaluable** by a grid-vs-region rule (plain callsign **and** grid) | **51 (70.8%)** | ⇐ **ROW 0a population** |
| — carrying no grid at all (rule silent) | 19 (26.4%) | |
| — hash-only, no plain callsign (rule **blind**) | 6 (8.3%) | |
| FPs carrying a hash reference `<...>` | 21/72 (29.2%); **12/21 in token 0** | |
| Distinct FP callsign tokens that ever repeat | **0 of 161** | corroboration premise, confirmed |
| Real corpora | 241k decodes, **21,242** distinct callsigns, 7 sessions | `artefacts/**/OpenWSFZ ALL.TXT` |
| Real distinct callsigns heard exactly **once** | **9,890/21,242 = 46.6%** (7.9–57.5%) | ⇐ why corroboration cannot be a general policy |
| Real messages carrying a grid | ~66% | |
| Decodes naming `PD2FZ` | **0** | ⇐ §0's structural-zero finding |

**HK-031 discharged.** No new R&R sweep is introduced or read; the S5 series was quoted in the
`S5-STANDALONE` spec §1 and that run's Section 6.

---

## 2. The three candidate rules — fixed at drafting, before any cost measurement (HK-021(p))

All three are **categorical and carry no tunable parameter** — no distance, no threshold, no cutoff,
per the PO's constraint. Each answers "is this grid geographically consistent with this callsign?" at
a different granularity.

| ID | Predicate — flag the decode when… | Data source |
|---|---|---|
| **R-CONT** | the **continent** containing the message's grid square ≠ the continent the callsign's prefix resolves to | existing region store (REGION column) + Maidenhead→lat/lon |
| **R-CQZ** | the **CQ zone** containing the grid ≠ the CQ zone the prefix resolves to | existing country-file CQZ + Maidenhead→lat/lon |
| **R-ENT** | the grid square is **not among the squares occupied by the DXCC entity** the prefix resolves to | entity→square set + Maidenhead→lat/lon |

**Maidenhead decode is fixed here so it cannot drift:** field char 0 = longitude, 20° per step from
180°W; char 1 = latitude, 10° per step from 90°S; digits 2/3 = 2°/1° squares. Report the **square
centre**.

⚠️ **Disclosed, because it matters for how ROW 0a is read:** the rule's *form* was suggested by six
FPs observed on 2026-09-05. Its *content* is categorical with nothing fittable to those six. ROW 0a
therefore runs on the **full 51-decode evaluable population**, not the six.

**Worked example (Architect's own, from the six — illustration only, NOT a result):** R-ENT and
R-CQZ flag 5/5; **R-CONT flags 4/5** (a VK6 callsign with a Papua New Guinea grid stays inside OC).
The candidates genuinely differ in sensitivity, which is why all three are measured.

🛑 **HK-021(y), stated as a prohibition:** all three candidates' rates are reported. **Choosing the
candidate with the best number after seeing the numbers is outcome-selection in a new costume and is
forbidden.** The PO picks on the published trade-off table; QA recommends nothing.

---

## 3. Populations

- **Cost population (ROW 1/3):** the seven live corpora. **Unit = the distinct callsign** — the
  operationally meaningful loss is a station, not a decode. Decode-level reported secondarily.
  Denominator = decodes carrying **both** a grid **and** a prefix that the region store resolves;
  this is the only population where any candidate is defined.
- **Positive-control population (ROW 0a):** the **51** evaluable labelled FP decodes.
- 🔴 **Both populations must pass through the *same* rule implementation and the same region-store
  path.** A cost rate and a base rate produced by two different code paths are not comparable
  (HK-021(u)).

---

## 4. The rows

| Row | Check | Bar | Consequence |
|---|---|---|---|
| **0a** | **Positive control (HK-021(q)) — the rule must move on what it targets.** Per candidate: flag rate on the 51 evaluable labelled FPs | **fires if a candidate flags < 31 of 51 (< 60%)** | 🛑 That candidate is **STOPPED** and reported as such — its cost is not worth measuring. Evaluate the remaining candidates. **If all three fire ⇒ STOP the whole arm, pause and hand back (HK-030)** |
| **0b** | **Identifiability.** Share of real decodes that are evaluable (grid present **and** prefix resolved) | **fires if < 40%** | 🛑 **STOP, pause and hand back.** The denominator is not the population the feature would act on |
| **1** | **PRIMARY — false-flag rate on real traffic**, per distinct callsign, per candidate, with exact Clopper–Pearson 95% CI | **< 1%** · **1–10%** · **≥ 10%** — three disjoint bands, fixed here, before measurement | Band per candidate is reported as the mechanical outcome. **Consequences are the Architect's to draw in adjudication, not QA's** |
| **2** | **HK-021(u) base rate, same sentence.** ROW 1 must be reported alongside ROW 0a's flag rate on labelled FPs, per candidate, in the same table | — | A cost rate quoted without its base rate is **not reportable** |
| **3** | **Cost concentration (descriptive).** Share of flagged **real** callsigns carrying `/P`, `/M`, `/MM`, `/R` | descriptive, no bar | Tests the "legitimate portable / DXpedition" hypothesis — the population whose loss is most expensive. **No ratio, no p-value** |
| **4** | **Coverage, reported so it cannot be forgotten.** Share of *all* labelled FPs each candidate would mark = (ROW 0a hits) ÷ 72 | descriptive | Keeps the ~71% ceiling and the blind hash half visible in the result itself |

**Precision, not power:** ~159k grid-bearing decodes / ~14k evaluable distinct callsigns. Even a 1%
rate yields ≈140 events. 🛑 **No power calculation is load-bearing here and none may be quoted as
one** — report exact CP intervals, and per HK-021(o) the readout quantum, never a bootstrap SE.

---

## 5. Execution notes

- **Reuse, do not reimplement:** import the project's own region-resolution path
  (`ICallsignRegionStore` / `CallsignRegionEntry` / `ICountryFileConverter`) rather than writing a
  second prefix parser. If that is not importable from Python, say so and stop — **do not
  hand-roll a substitute** (a second instrument silently redefines the metric).
- ⚠️ **`compute_matched_hit_control(..., limit=N)` TRUNCATES in file order, it does not sample** — do
  not reuse it here for any sub-sampling. If sampling is needed, sample explicitly and seed it.
- ⚠️ **Sort at construction** — no `set(a) & set(b)` over string keys in any seeded path
  (hash-randomised iteration silently breaks determinism).
- **HK-009:** Windows console `stdout` is `cp1252` — write ASCII or `reconfigure(encoding="utf-8")`.

---

## 6. 🔴 After the measurement — QA authors the Developer instructions **in OpenSpec** (PO-directed)

The Architect has opened the OpenSpec change **`openspec/changes/decode-implausibility-marking/`**
carrying `proposal.md`, `design.md` and `specs/**` — the Architect→QA artefacts per HK-015. It
deliberately has **no `tasks.md`** (`openspec validate --strict` passes without one).

**QA's task, on the PO's explicit direction:**

1. **Author `openspec/changes/decode-implausibility-marking/tasks.md`** — the Developer-facing task
   list. `tasks.md` is QA's per HK-015, and the Developer session runs **`opsx:apply`** against it.
2. 🛑 **Use OpenSpec for this — not a standalone `dev-tasks/*.md`.** The PO directed the OpenSpec
   route explicitly.
3. Fold this measurement's ratified candidate (the PO's pick from ROW 1's trade-off table) into
   `tasks.md` as the concrete predicate to implement. **The change must not be applied before that
   pick is made** — `design.md` D2 records the predicate as the one open parameter.
4. **HK-011 stands:** QA proposes and stops. A separate **Developer** session runs `opsx:apply`
   (build and tests only, **never** `pre_merge_check.py`); the Captain reviews the diff pre-push.
5. **`decode-panel-filtering` live-verification policy:** if implementation touches
   `DecodeFilterState`, `DecodeFilterEvaluator`, `IDecodeFilterStore` or the
   `QsoAnswererService`/`QsoCallerService` filtering hook, `qa/decode-filter-synth-verify/live_verify_9_axes.py`
   must be re-run against a real isolated daemon before merge, with its auto-generated report
   committed. `design.md` D4 argues the Phase-1 design avoids that path; **verify it, do not inherit
   the claim.**

---

## 7. What QA reports — and must not conclude

**Report:** the mechanical outcome of ROW 0a, 0b, 1, 2, 3, 4 — per candidate, in one trade-off
table, with ROW 1 and its ROW 2 base rate in the same row.

🛑 **QA recommends no candidate, draws no verdict on shipping, and does not adjudicate the
feature's form.** That is the Architect's, then the PO's.

**HK-025 stands.** If any row here is non-mechanical, or a precondition cannot change a verdict,
QA may **refuse to run it** on HK-021(k) grounds without Architect agreement — classify (validity vs
precision), evaluate both branches, and if the same row results either way it is diagnostic ⇒ refuse.

---

## 8. 🔴 NFR-021 — the binding constraint on this arm

This measurement reads **21,242 real callsigns**.

- Inputs live under `artefacts/` (blanket-gitignored) — raw processing there is safe.
- **Every committed output must be aggregate**: counts, rates, CP intervals. 🛑 **No callsign lists,
  no per-callsign tables, no worked examples drawn from real traffic, in files or in prose.**
- `PD2FZ` is the single permitted exception (privacy policy); no other real call may appear.
- Scan with the project's own `scan()`/`classify()` from `nfr021_pre_merge_scan.py` — **not** a
  directory walk, and never against an uncommitted directory (false-green "CLEAN"). **Scan the report
  prose too.**

**HK-016:** gather artefacts into a dated, `README.md`'d `./artefacts/` directory before reporting
done. **HK-014:** commit locally, **do not push**; verify `git diff --stat -- src/ native/` is empty
and say so. **HK-030:** every STOP above means **pause and hand back**, not merely "don't push".

---

**Architect, 2026-09-05 16:05 UTC.** Pre-registered; nothing measured by the Architect beyond §1's
already-recorded facts.
