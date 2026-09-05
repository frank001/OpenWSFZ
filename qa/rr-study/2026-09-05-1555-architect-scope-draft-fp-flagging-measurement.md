# SCOPE DRAFT — measuring whether FP flagging is shippable, and what it can never cover

**Architect, 2026-09-05 15:55 UTC** (`date -u`, HK-017).

🛑 **THIS IS A SCOPE DRAFT FOR PO APPROVAL. IT IS NOT A SPEC AND IT ARMS NOTHING.** No row here is
pre-registered yet; the bars in §6 are proposals. Nothing is to be run until the PO rules on §8 and
the approved scope is rewritten as a QA spec (HK-015).

**Origin:** the PO's decode-panel observation (six S5 FPs at −26…−28 dB with implausible callsigns),
then the proposed mechanism — *flag a suspicious decode, suppress it until a second sighting clears
the flag, delete flagged decodes older than XX minutes* — and the PO's constraints: **no decoder
change** and **no threshold**.

---

## 1. What is already measured — do not re-derive it (HK-018)

Everything in this table was computed today from data already on disk. Sources are the windowed S5
FP corpus (`S5_matched.csv` × 13 runs, `analyse.py`'s own `fp_in_window` scoping — guards §0.2) and
seven live off-air sessions under `artefacts/**/OpenWSFZ ALL.TXT`.

| Fact | Value | Why it matters |
|---|---|---|
| Windowed S5 OpenWSFZ FP decodes | **72** across 13 runs | The only *labelled* FP population that exists |
| Distinct FP messages | 69 of 72 | — |
| FP messages seen more than once | **1** (`CQ <...>` ×4, already killed by R5 Rule C) | — |
| **Distinct FP callsign tokens repeating** | **0 of 161** (only `RR73`, a keyword) | 🔴 **The PO's corroboration premise is CONFIRMED.** A CRC-14 coincidence redraws a 77-bit payload; it does not recur |
| FPs carrying a hash reference `<...>` | **21 / 72 = 29.2%** | The half a grid-based rule cannot see |
| — of those, hash in **token 0** (addressee slot) | **12 / 21** | The shape `QsoAnswererService` reads as "calling me" |
| Today's FPs whose grid contradicts their own callsign's region | **5 of 5** carrying a grid | Three placed NA/OC stations in **Antarctica** |
| Real live corpora | 241k decodes, **21,242** distinct callsigns, 7 sessions | The cost population |
| **Real distinct callsigns heard exactly ONCE** | **9,890 / 21,242 = 46.6%** (range 7.9–57.5%) | 🔴 **Corroboration cannot be a general policy** — it would hold ~half of all real stations |
| Real messages carrying a grid at all | **~66%** | A grid rule is structurally silent on the other third |
| **Decodes naming `PD2FZ` across all live corpora** | **0** | 🔴 See §4 — the severe case has never been reachable in anything we own |

**HK-031 discharged.** The S5 AWGN series was read and quoted in the `S5-STANDALONE` spec §1 and
that run's own Section 6 before any of the above was computed. This scope introduces no new sweep.

---

## 2. The two halves are different in kind — this is the whole point of the scope

The PO's mechanism assumes one population of "suspicious decodes". There are two, and they need
different instruments:

- **The visible half** — an FP that names a callsign in plain text and carries a grid. A
  grid-vs-region consistency check can see these. **Threshold-free by construction:** the grid
  either falls inside the entity the prefix resolved to, or it does not. There is nothing to tune.
- **The hash half — 29.2% of FPs** — an FP of the form `<HASH> CALL GRID`. There is no prefix in
  the addressee slot, therefore no region, therefore **no contradiction to detect**. A grid rule is
  not weak here; it is **blind**.

🔴 **Consequence the PO should hold onto: whatever comes out of SCOPE A, it covers at most ~71% of
the FP population, and specifically excludes the shape with the worst operational consequence.**

---

## 3. SCOPE A — is the grid–region rule shippable? (offline, existing data, decisive)

**Question:** if a decode is flagged when its grid falls outside the DXCC entity its prefix resolves
to, **how often does that fire on real traffic?**

**Instrument:** the seven live corpora above, plus the existing `ICallsignRegionStore` /
`CallsignRegionEntry` / `ICountryFileConverter` path that already fills the panel's REGION/DXCC
columns. **No new run, no hardware, no decoder change, no `src/` change.** Pure offline analysis.

**Unit:** the **distinct callsign** (you lose a station, not a decode). Decode-level reported
secondarily. Denominator is decodes that carry **both** a grid and a resolved region — the only
population where the rule is defined at all.

**Why it is not outcome-selected (HK-021(y)):** the rule's *form* was suggested by six FPs, and that
is disclosed. Its **content is categorical and carries no tunable parameter** — no distance, no
threshold, no cutoff. There is nothing in it that could be fitted to those six.

⚠️ **Candidate rules, all pre-registered together, all reported:** the "entity containing the grid"
lookup has more than one defensible construction (entity-polygon containment; entity-centroid
nearest-match; prefix→known-grid-field set). **All candidates are evaluated and ALL their rates
reported.** The PO picks on the published trade-off. 🛑 **Selecting the candidate with the best
number after seeing the numbers is exactly HK-021(y) in a new costume and is forbidden.**

---

## 4. SCOPE B — the hash half, and why it is BLOCKED rather than expensive

### 4.1 The chain, read from code today (not inferred)

1. An FP emits `<HASH> CALL GRID` — 12 of 72 observed.
2. `hash_table_lookup` (`ft8_shim.c:637`) resolves the 12-bit code **iff that code is resident**.
3. `hash_table_add` (`ft8_shim.c:832`, decode path) makes a callsign resident **only when it has
   been heard in a decode**. No own-call seeding exists.
4. `DestMatchesOwnCallsign` (`QsoMessageParsing.cs:61`) strips brackets, **rejects the unresolved
   `<...>` marker**, then compares the *resolved* text to the configured callsign.

⇒ **The severe case fires only when the station's own callsign is h12-resident**, which requires
**another station to have named it on air** — i.e. normal two-way operation.

### 4.2 🔴 Why no existing corpus can measure it, and re-analysis will not help

**0 of 241,000 decodes across all seven live corpora name `PD2FZ`.** Residency therefore never
occurred, so the severe case had **structural exposure zero** in every corpus we own. This
independently reproduces the accepted defect's own finding —

> *"severe form (a station addressing PD2FZ by hash) has exposure exactly **ZERO** in this
> receive-only corpus — **an exposure of zero, not absence** (HK-021(j))"*

🛑 **HK-026 applies directly: these corpora are FLAT where this boundary sits.** No amount of
re-analysis of them bounds the severe case in either direction. **A null from SCOPE B data would be
uninformative and must never be reported as reassurance.**

### 4.3 What is available now, and what is not

| Available offline, cheap | Blocked |
|---|---|
| The hash-addressed FP **share** (measured: 12/72) | The severe-case **rate** — needs ≈4,096 hash-addressed FPs to expect one hit at a uniform 1/4096 |
| Whether F-001's existing `tls_h12_lookup_performed` / `tls_h12_resolved` telemetry **already records a resolved-to-own-call event** — a **code-reading task, not a run** | Whether FP-drawn 12-bit codes are **uniformly distributed** (n=21 far too small; the 1/4096 assumption is unvalidated **in both directions**) |

🔴 **The HK-027 move, and my recommendation for this half:** do **not** commission a transmitting
corpus for this. Ask first what the daemon already records. If F-001's h12 telemetry can distinguish
"resolved to own call", then **ordinary operating sessions accumulate the exposure for free**, at
zero marginal cost — the same free-surveillance pattern the PO already ratified for the FP rate.
Establish the observable; let normal use fill it.

---

## 5. Explicitly NOT in scope

- 🛑 **No decoder change, no ABI change, no shim bump.** Both halves use data that already crosses
  the boundary. HK-011 is not engaged by the *measurement*; it would be engaged by any feature built
  after it.
- 🛑 **No threshold anywhere**, per the PO's constraint. SCOPE A is categorical. The −26…−28 dB
  observation is **not** carried forward as a rule (it is real — −26.02 dB is the SNR estimator's own
  zero point, so it is a structural floor, not a coincidence — but it is not being turned into a cut).
- 🛑 **Not a re-opening of `FP-REGRESSION`.** This measures a *proposed rule's cost*, not the FP
  rate. 🔴 **If any resulting feature ever suppresses rather than annotates, it changes the S5 AWGN
  FP rate — the metric with NO established baseline (guard (e)) — and that needs its own
  pre-registration BEFORE it is built, not a measurement afterwards.**
- 🛑 **The `AWGN-FP` §8 offline seam stays un-run.** Using it here would be a new pre-registration,
  not a continuation, and its ≈6.9 dB level bias is unaddressed.

---

## 6. Proposed pre-registration skeleton (bars are PROPOSALS, not yet binding)

| Row | Check | Proposed bar | Consequence if it fires |
|---|---|---|---|
| **0a** | **Positive control (HK-021(q)) — the rule must move on the thing it targets.** Flag rate on the 5 grid-bearing labelled FPs, same pipeline | fires if the rule flags **< 3 of 5** | 🛑 **STOP.** A rule that cannot catch known FPs has no false-flag rate worth measuring |
| **0b** | **Identifiability.** Fraction of real decodes where prefix→region resolves AND a grid is present | fires if **< 40%** of decodes are evaluable | 🛑 **STOP** — the denominator is not the population the feature would act on |
| **1** | **PRIMARY — false-flag rate on real traffic**, per distinct callsign | **≥ 5%** ⇒ unshippable as a suppressor · **1–5%** ⇒ annotate-only, never suppress · **< 1%** ⇒ shippable as an automation suppressor | Band determines the feature's permitted form. Bands are disjoint and fixed **before** measurement |
| **2** | **HK-021(u) base rate, same sentence.** ROW 1 must be reported alongside the same rule's flag rate on labelled FPs | — | A flag rate quoted without its base rate is not reportable |
| **3** | **Cost concentration.** Share of flagged real callsigns carrying `/P`, `/M`, `/MM`, `/R` | descriptive | Tests the "legitimate portable/DXpedition" hypothesis — the population whose loss is most expensive |

**Precision, not power:** ~159k grid-bearing decodes / ~14k evaluable distinct callsigns. Even a 1%
rate yields ≈140 events, so ROW 1 is precision-rich; no power calculation is load-bearing and none
should be quoted as one.

🔴 **What ROW 1 canNOT do, stated before it runs:** it says nothing about the hash half (§2), nothing
about the ~34% of messages with no grid, and nothing about the severe case (§4.2).

---

## 7. NFR-021 — the constraint that most shapes the deliverable

This measurement reads **real callsigns at scale** (21,242 of them) and the station's own call.

- Inputs live under `artefacts/` — blanket-gitignored, so raw processing is safe there.
- **All committed outputs must be aggregate**: counts, rates, intervals. **No callsign lists, no
  per-callsign tables, no worked examples drawn from real traffic.**
- `PD2FZ` is the one permitted exception (privacy policy); public figures aside, **no other real
  call may appear in a committed file or in report prose** — and prose is scanned, not just files.
- Scan with the project's own `scan()`/`classify()` over the committed artefacts — **not** a
  directory walk, and never against an uncommitted directory (false-green).

---

## 8. What the PO is asked to decide

1. **Approve SCOPE A** (offline, existing data, no run, no `src/` change) to be rewritten as a QA
   spec with §6's bars ratified or amended. **This is the one I recommend.**
2. **Approve the SCOPE B first step only** — a **code-reading** task: does F-001's existing h12
   telemetry already record a resolved-to-own-call event? No run, no build. If yes, exposure
   accumulates free during normal operation and nothing further is commissioned.
3. **Rule on the feature's permitted form *before* it is built**, so ROW 1's bands land on a decision
   already made: **annotate-and-retain** (my recommendation — reversible, measurable, leaves
   `ALL.TXT` untouched per `DecodeNoiseSuppressionConfig` Decision 1) versus **suppress-and-delete**
   as originally proposed.

🔴 **My concern, stated once (§4 of the earlier answer, unchanged):** the *delete* step destroys the
evidence needed to measure its own false-suppression rate. A quarantine that deletes its contents
cannot be audited, and the loss is concentrated on rare DX — the contacts worth most. I recommend
**mark-and-retain, age out to "dismissed", never delete.** If the PO prefers deletion, I will spec
it, and I would want the un-auditability recorded as an accepted risk rather than discovered later.

---

**Architect, 2026-09-05 15:55 UTC.** Scope draft only — **nothing armed, nothing measured, no board
figure moved.** To be committed locally, **not pushed** (HK-014).
