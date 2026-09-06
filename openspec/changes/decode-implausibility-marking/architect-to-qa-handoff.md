# Architect → QA handoff — `decode-implausibility-marking`

**Architect, 2026-09-05 16:05 UTC** (HK-017). PO-directed 2026-09-05.

🛑 **No instruction has been issued to any Developer session.** Per HK-015 this change ships
`proposal.md`, `design.md` and `specs/**` only. **`tasks.md` is QA's to author** — and the PO has
directed explicitly that the Developer instructions go through **OpenSpec**, i.e. as this change's
own `tasks.md` for `opsx:apply`, **not** a standalone `dev-tasks/*.md`.

`openspec validate --strict` passes without a `tasks.md`, so this change is valid as delivered.

---

## 1. QA's tasks, in order

1. **Run `FP-MARK` first** — `qa/rr-study/2026-09-05-1605-architect-to-qa-spec-fp-marking-rule-validation.md`.
   Pre-registered, offline, no run, no `src/` change. Report mechanical row outcomes only.
2. **Wait for the PO's pick** of one predicate (R-CONT / R-CQZ / R-ENT) from ROW 1's trade-off table.
   🛑 **`design.md` D2 is this change's single blocking open parameter — do not author `tasks.md`'s
   predicate section before the pick exists.**
3. **Author `openspec/changes/decode-implausibility-marking/tasks.md`** carrying the ratified
   predicate, and resolve `design.md`'s three non-blocking open questions (age-out default;
   whether `Dismissed` is reversible from the UI; both are QA's to fix).
4. **Hand to a separate Developer session** which runs `opsx:apply` (build and tests only, **never**
   `pre_merge_check.py`). Captain reviews the diff pre-push. **HK-011.**
5. **Verify D4 mechanically before merge** — see §2.

## 2. 🔴 The one thing most likely to bite

`design.md` D4 *intends* the ordering to keep implementation off `DecodeFilterState`,
`DecodeFilterEvaluator`, `IDecodeFilterStore` and the `QsoAnswererService`/`QsoCallerService`
filtering hook. **That is an intention, not a measurement.**

If the diff touches any of them, the `decode-panel-filtering` live-verification policy applies:
`qa/decode-filter-synth-verify/live_verify_9_axes.py` must be re-run against a real, isolated daemon
before merge, with its auto-generated report committed alongside. **Check the actual diff; do not
inherit the design's claim** (HK-022 — a green result answers whatever it was pointed at).

## 3. Material for QA to own, revise or discard

Not instructions — design rationale, offered so QA does not have to re-derive it.

- **Why marking is a separate capability** — `decode-noise-suppression`'s every Requirement is
  written around *removal*; marking's default is the opposite. D1.
- **Why `Dismissed` is never a deletion** — a quarantine that deletes cannot be audited for
  false-suppression, and **46.6% of real callsigns are heard exactly once**, so a wrong removal
  usually costs the only chance at that station. D3.
- **Why Phase 1 excludes automation ineligibility** — a badge is safe at any false-flag rate; an
  eligibility change at an *unmeasured* rate is not, and the cost concentrates on `/P`/`/M`/`/MM`
  DXpedition operators. `proposal.md` "Phase-1 boundary".
- **Why no shim bump** — grid and callsign already cross the boundary in `FT8Result`; a bump would
  also collide with the live `20260051`/`20260052` renumbering. D5.

## 4. 🛑 Guards that travel with this change

- **Coverage ceiling ~71%.** 51 of 72 labelled FPs are evaluable; **29.2% carry a hash reference**
  (12/21 in the addressee slot) where the rule is **blind, not weak**. `FP-MARK` ROW 4 reports it so
  it stays visible.
- **The severe case is untouched and unmeasurable here** — 0 of 241,000 decodes name `PD2FZ`, so
  own-call h12 residency never occurred: **structural exposure zero, not absence** (HK-021(j)), and
  HK-026 forbids reading those corpora as reassurance.
- **`ALL.TXT` untouched in every state** — this is what keeps the S5 AWGN FP metric unmoved. There is
  still **no established baseline** for it (guard (e)), so a change there would be undetectable.
- **No threshold anywhere**, per the PO's constraint. All three candidate predicates are categorical.
