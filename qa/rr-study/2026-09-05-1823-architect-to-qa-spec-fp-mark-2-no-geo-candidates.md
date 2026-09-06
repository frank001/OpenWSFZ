# `FP-MARK-2` — Architect to QA: four categorical candidates that need no geographic instrument

**Architect, 2026-09-05 18:23 UTC** (`date -u`, HK-017). PO ruled **Option A** on the 16:40Z ruling
(`2026-09-05-1640-architect-to-qa-ruling-fp-mark-row0-block.md` §5).

**This is a RE-DRAFT, not an amendment** — a fresh pre-registration pass, as that ruling required. It
supersedes the `FP-MARK` candidate set entirely. **PRE-REGISTERED and ARMED. QA's to execute.**
Offline analysis of data already on disk — no live run, no hardware, no rebuild, **no `src/` or
`native/` change, and no geographic classifier.**

🛑 **QA draws no verdict on which candidate ships.** Mechanical row outcomes only. Adjudication is
the Architect's; ratification is the PO's (HK-015).

---

## 0. What carries over, and what is dead

| | |
|---|---|
| ✅ **ROW 0b** (65.89% evaluable, 25.89 pp of margin) | **Stands, accepted.** Not re-run. It bounds only candidates needing a resolved prefix **and** a grid — of the four below, **only R-UNALLOC** depends on the prefix side, and none needs a grid |
| 🛑 **R-ENT** | **RETIRED** — unsatisfiable from this data model |
| 🛑 **R-CONT / R-CQZ** | **SUSPENDED** and now **superseded** by this re-draft. Not to be revived without new PO direction. If ever revived, `KG4` must carry a pinned tie-break |
| ✅ **The SHA256 pins** | **Carry over unchanged** and apply to every row here — region table **and** the 7-corpus manifest |

---

## 1. Established — do not re-derive, and note what is ALREADY measured (HK-018)

| Fact | Value |
|---|---|
| Windowed labelled FP decodes | **72** across 13 runs |
| — carrying a hash reference `<...>` | **21 (29.2%)**; **12 (16.7% of 72)** with the hash in **token 0** |
| — distinct FP callsign tokens that ever repeat | **0 of 161** |
| Real corpora (pinned manifest) | **241,858** decodes, 7 sessions, **21,242** distinct callsigns |
| — evaluable (grid **and** resolved prefix) | 159,364 = **65.89%** (ROW 0b) |
| — distinct real callsigns heard **exactly once** | **9,890/21,242 = 46.6%** (range 7.9–57.5%) |
| Region table | 29,013 entries, SHA256-pinned; **35 duplicate ranges, index-order-dependent tie-break** |

🔴 **Disclosure, so nothing below is presented as a fresh result:** **R-SOLO's numbers are already
known on both sides** (0/161 FP repeat; 46.6% real singletons) — it is included as a **calibration
anchor**, not a discovery. **R-HASH's FP-side share is already known** (29.2% / 16.7%); its
**real-traffic side is NOT measured** and is the live question. **R-UNALLOC and R-SUFFIX are
unmeasured on both sides.**

**HK-031 discharged** — no new R&R sweep is introduced or read.

---

## 2. The four candidates — fixed here, before any rate is computed (HK-021(p), HK-021(y))

All four are **categorical**, carry **no tunable parameter**, and use **only instruments that already
exist**. Each is measured independently; **they are never combined** (a combined rule needs weights,
and weights are a threshold by another name).

| ID | Flag the decode when… | Instrument (existing) |
|---|---|---|
| **R-UNALLOC** | any callsign-position token's prefix **does not resolve** to any entity in the region table | pinned region table + `TryMatchPrefix` port (already built and verified for ROW 0b) |
| **R-SUFFIX** | **both** callsign-position tokens carry a portable/rover suffix (`/P`, `/M`, `/MM`, `/R`, `/A`, `/QRP`) | `CallsignTokenHelpers.StripPortableSuffix` |
| **R-HASH** | **token 0** (the addressee position) is a hash reference `<…>` | message text; `IsUnresolvedHashMarker` shape |
| **R-SOLO** | the callsign appears **exactly once** in its session | within-session counting; no new instrument |

### 2.1 🔴 Provenance disclosure — ranked honestly, because this is where outcome-selection hides

- **R-UNALLOC — strongest.** Mechanism-derived: a CRC-14 coincidence draws the callsign field at
  random, and most of that space is unallocated. **Not suggested by the six FPs.** ⚠️ **It is also
  already shipping as a suppressor** — `decode-noise-suppression`'s `SuppressUnknownRegion` — whose
  false-suppression rate **has never been measured.** ROW 1 for this candidate therefore prices a
  control that is *already costing whatever it costs, today, invisibly.*
- **R-HASH — strong.** Derived from the **full 72-decode labelled corpus**, not from the six. Reaches
  the class every geographic candidate was **blind** to.
- **R-SOLO — independent.** The **PO's own** original corroboration proposal, measured across the
  full corpus. Included as a calibration anchor.
- ⚠️ **R-SUFFIX — weakest, and flagged as such.** Its form was suggested **only** by the six FPs
  observed on 2026-09-05 (two carried `/R` on both callsigns). n=6 is not a basis for a rule. It is
  included so the hypothesis is tested rather than assumed, and 🛑 **if its ROW 0a is weak it should
  be dropped without argument.**

### 2.2 🛑 R-SHAPE was considered and deliberately EXCLUDED — the reason is a trap worth recording

A "stricter callsign-shape grammar" candidate is the obvious fifth. It is excluded because:

1. **It cannot be built as a stricter `IsPlausibleMessage`.** That filter's failure branch does
   `continue` at `Ft8Decoder.cs:348`, **dropping the decode before it reaches `ALL.TXT`.** Tightening
   it would change `ALL.TXT` ⇒ **move the S5 AWGN FP metric — the metric with no established
   baseline (guard (e))** ⇒ the change would be undetectable and the guard violated.
2. Every labelled FP **already passed** the shipped grammar (that is why it is in `ALL.TXT`), so
   "fails the shipped grammar" flags **nothing**, and "fails a stricter grammar" is a **tunable
   parameter** — precisely the threshold the PO ruled out.

🔴 **If a shape predicate is ever wanted it must be a separate marking evaluation, never a change to
the decoder's drop filter.**

---

## 3. Populations, per candidate (HK-021 — the metric must be identifiable from its data)

**Primary unit is the DECODE, not the distinct callsign** — a change from `FP-MARK`, and deliberate:
the PO ruled the feature *marks* rather than suppresses, so the thing acted on is a decode carrying a
badge. Distinct-callsign figures are reported secondarily where the candidate defines a callsign.

| Candidate | Evaluable population |
|---|---|
| R-UNALLOC | decodes with ≥1 callsign-position token (prefix resolution attempted) |
| R-SUFFIX | decodes with ≥2 callsign-position tokens |
| R-HASH | **all** decodes (token 0 either is or is not a hash reference) |
| R-SOLO | all decodes, evaluated within their own session |

🔴 **Both sides — labelled FPs and real corpora — must pass through the SAME predicate
implementation.** A positive rate and a false-flag rate produced by two code paths are not
comparable (HK-021(u)).

---

## 4. The rows

| Row | Check | Bar | Consequence |
|---|---|---|---|
| **0a** | **Positive control (HK-021(q)) — R-UNALLOC and R-SUFFIX ONLY.** Flag rate on their evaluable share of the 72 labelled FPs | **fires if a candidate flags < 40% of its evaluable FP population** | 🛑 That candidate is **STOPPED** and reported as such. Evaluate the others. If **both** fire, continue with R-HASH/R-SOLO only — **not** a whole-arm stop |
| **1** | **PRIMARY — false-flag rate on real traffic**, per decode, per candidate, with exact Clopper–Pearson 95% CI | **< 1%** · **1–10%** · **≥ 10%** — three disjoint bands, fixed here | Band per candidate reported as the mechanical outcome. **Consequences are the Architect's to draw, not QA's** |
| **2** | **HK-021(u) base rate, same sentence.** ROW 1 reported alongside the same candidate's FP-side rate, in the same row of one table | — | A cost rate quoted without its base rate is **not reportable** |
| **3** | **Coverage.** Share of all 72 labelled FPs each candidate would mark | descriptive | Keeps each candidate's ceiling visible |
| **4** | **Overlap (descriptive).** Pairwise: of the FPs candidate A marks, what share does B also mark | descriptive, no bar | Determines whether shipping several adds coverage or repeats it. **No ratio, no p-value** |

🛑 **ROW 0a deliberately does NOT apply to R-HASH or R-SOLO.** For both, the FP-side rate is
**100% by construction** — they are *categories*, not detectors, and a precondition that cannot fail
is diagnostic (HK-021(k) ⇒ QA may refuse it, HK-025). Their entire question is ROW 1. Their coverage
is a **known constant** (R-HASH 16.7% of 72; R-SOLO 100%), reported in ROW 3, not measured.

**Precision, not power:** ~242k decodes. Even a 0.1% rate yields ≈240 events. 🛑 **No power
calculation is load-bearing and none may be quoted as one** — exact CP intervals, and per HK-021(o)
the readout quantum, never a bootstrap SE.

---

## 5. Execution notes

- **Reuse the ROW 0b machinery** — `fp_mark_row0b_identifiability.py`'s verified ports
  (`ExtractPrimaryCallsignToken`, `StripPortableSuffix`, `TryMatchPrefix`). **Do not re-port.**
- ⚠️ **The binary-search reindex now feeds a RATE, not merely an existence check.** Per the 18:20Z
  verification: **bank the linear-vs-binary mechanical diff over a seeded sample before ROW 1**
  — behavioural identity is diffed, never asserted. `KG4` and the 35 duplicate ranges are the reason.
- **Assert the SHA256 pins at run time** (region table + 7-corpus manifest) and record them.
- ⚠️ **Sort at construction**; no `set(a) & set(b)` over string keys in any seeded path.
- ⚠️ **No unguarded slices on a population** — `[:N]` on a corpus list is the HK-021(i) defect and it
  already nearly bit the Architect once today.
- **HK-009:** ASCII `stdout` or `reconfigure(encoding="utf-8")`.

---

## 6. 🔴 After the measurement — Developer instructions go through OpenSpec (PO-directed, unchanged)

The OpenSpec change `openspec/changes/decode-implausibility-marking/` stands; its `design.md` **D2**
has been amended to carry this candidate set in place of the geographic one.

1. **QA authors `openspec/changes/decode-implausibility-marking/tasks.md`** — QA's per HK-015, and
   the PO directed the **OpenSpec** route, **not** a standalone `dev-tasks/*.md`.
2. **Not before the PO picks** a candidate (or candidates) from ROW 1's trade-off table. **D2 remains
   the change's single blocking open parameter.**
3. **HK-011:** QA proposes and stops; a separate Developer session runs `opsx:apply`; Captain reviews
   the diff pre-push.
4. **Verify `design.md` D4 against the real diff** — its claim of avoiding the
   `decode-panel-filtering` live-verify path is an **intention, not a measurement** (HK-022).

---

## 7. What QA reports — and must not conclude

**Report:** ROW 0a (two candidates), 1, 2, 3, 4 — in **one trade-off table**, each candidate's ROW 1
and its ROW 2 base rate in the same row.

🛑 **QA recommends no candidate and draws no verdict on shipping.** 🛑 **Selecting a candidate after
seeing the numbers is HK-021(y) — the defect that retired `4.88×` and `3.25×`.** The PO picks from
the published table.

**HK-025 stands** — if any row is non-mechanical, or a precondition cannot change a verdict, refuse
on HK-021(k) grounds and say so. §4's exclusion of ROW 0a for R-HASH/R-SOLO is exactly that
reasoning applied in advance; **if any other row here has the same defect, refuse it too.**

---

## 8. 🔴 NFR-021 and housekeeping

Reads **21,242 real callsigns**. **Every committed output aggregate** — counts, rates, CP intervals.
🛑 **No callsign lists, no per-callsign tables, no worked examples from real traffic, in files or in
prose.** `PD2FZ` is the single permitted exception. Scan with the project's own
`scan()`/`classify()` — **not** a directory walk, never on an uncommitted directory — **and scan the
report prose.** ⚠️ The Architect tripped this exact guard on prose earlier today; it is not
theoretical.

**HK-016** artefacts into a dated `./artefacts/` dir with a `README.md`. **HK-014** commit locally,
do not push; verify `git diff --stat -- src/ native/` is empty and say so. **HK-030** every STOP
means pause and hand back.

---

**Architect, 2026-09-05 18:23 UTC.** Pre-registered; nothing measured beyond §1's already-recorded
facts.
