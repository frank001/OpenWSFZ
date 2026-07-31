# Architect → QA — consolidated handoff after Measurements A/B/C
# What to read, in what order, what to do, and what will bite you.
# Covers `2026-07-31-0029` (the ruling) and `2026-07-31-0853` (the Measurement D spec).
# Contains one amendment to the ruling (§5) — read it before acting on the ruling's §1.4.

**Author:** Architect, 2026-07-31 (09:10 UTC, `date -u`, per HK-017). Repo at `0e23697`.
**For:** QA. Every action below is QA's to route or author; none of it is mine to apply.
**Status:** this document is a **navigation and work-order layer** over two existing documents. It
adds one amendment (§5) and one disclosure (§6). Everything else here explains, prioritises and
warns — it does not introduce new findings or new measurements.
**Standing programme reference remains** `2026-07-27-2012-architect-to-qa-d001-closing-handoff.md`,
including its §0 stop rule. Nothing here re-opens the diagnostic programme.

---

## 1. The two documents, and the order to read them

| order | document | what it is |
|---|---|---|
| **1st** | `2026-07-31-0029-architect-ruling-measurements-abc-and-drift-root-cause.md` | **The parent.** Rules on all four items QA raised in `2026-07-31-0018`, plus the capture-drift root cause established in code. Contains the full work list at its §6 |
| **2nd** | `2026-07-31-0853-architect-to-qa-measurement-d-spec-within-band-density.md` | **One authorised action out of that ruling**, specified in full. Read alone it is a measurement with no account of why it matters or what it unblocks |

**Read the ruling first.** The spec is downstream of it and assumes its §1.

**One item in the ruling is already stale.** Its §6 item 1 tells QA to *put the within-band
stratification to the Captain as a recommendation*. **The Captain has since authorised it** —
that is what the `0853` spec records. Read §6 item 1 as: *escalate Measurement A's corrected
reading; the stratification is authorised, see the spec.* The rest of §6 stands unchanged.

## 2. Where the programme actually stands

So QA is not reconstructing this from four documents.

| thread | state after the ruling | who owns the next move |
|---|---|---|
| **Measurement A** — SNR-stratified recall | **Partially rejected.** The co-channel withdrawal is **dead** (row 1 excluded by a 36-point separation — pure sensitivity is refuted). But the **reversal is not licensed**: the "monotone in density" half of S5.3 row 2 fails in 10 of 26 bins and the curves cross, so rows 3+4 fire — *escalate, do not interpret*. What is measured is a **20m-specific deficit**, not a density law | QA escalates; Measurement D settles the mechanism |
| **Measurement B** — capture-chain replication | **Strike accepted**, and upgraded: the capture chain is now **bounded at ≤ ~4–5% with a point estimate of zero**. One of the closing handoff §2.3's three unmeasured candidates is retired on evidence | Architect — folds into the row 4 decomposition |
| **Measurement C** — realignment | **Accepted in full.** Mechanism now **established in code**: `CycleFramer` syncs to UTC once at startup, then counts samples and advances by arithmetic, never re-reading the clock; 48.4 ppm closes exactly against the measured −0.1744 s/h and explains the zero-drift Voicemeeter control. Closes the defect report's §7 first bullet | QA authors two dev-tasks (§3 task 1) |
| **SNR gain error** | Correctly routed standalone. No ruling needed | open decision, not QA's to force |
| **Row 4 decomposition** | Still owed by me. Was gated on Measurement A; **now gated on Measurement D** | Architect, once D lands |
| **The menu** (row 1 / row 4 / row 5) | Unchanged and still the Captain's. Nothing in this thread re-opens it | Captain |

## 3. The work queue, in priority order

Reading order is not work order. D is the most interesting item; it is not the one to start.

### Task 1 — the drift fix, as **two** dev-tasks in this order ⟨highest priority⟩

**Why first:** Critical severity, and it is *actively blocking*. Every long-session corpus
gathered on the affected device before this is fixed needs the same forensic salvage the two 40m
corpora now need. Given HK-020's record on multi-band overnight runs, this belongs in the
pre-flight for the **next** run, not in a post-mortem after it.

- **1a — the offline oracle. Test-only, no `src/` behaviour change.** Drive `CycleFramer` from a
  synthetic source clocked at 11 999.42 Hz against a fake clock, simulate 24 h, assert window
  boundaries stay within a stated tolerance of UTC. Add a second case that injects a dropped
  chunk mid-stream. Runs in milliseconds; no audio, no radio, no live session.
- **1b — the fix.** Re-derive each window boundary from the wall clock rather than accumulated
  sample counts, absorbing the residual per cycle. **Gated on 1a going red against current
  `main` first.**

**The acceptance constant is derivable, not a guess.** The DT cliff is bracketed at 2.34–2.48 s.
Holding boundary error under ~0.2 s is an order of magnitude inside it, and at 48 ppm that
permits ~1.1 h between resyncs — so **resynchronising every cycle is trivially sufficient**, with
three orders of magnitude of margin.

**Boundaries:** per HK-011 both are `src/` work → separate Developer session, Captain signs off
the diff before push. Per HK-015 the dev-task specs are QA's to author, not mine. Neither
checklist carries `pre_merge_check.py` (HK-006). I propose no code.

### Task 2 — Measurement D ⟨highest value for the D-001 decision⟩

Spec: `2026-07-31-0853`. Half a QA session, no decoding, no new data, no `src/` change. It
ungates the row 4 decomposition, which is on the critical path for the Captain's menu decision.
Pitfalls at §4 below — that section is the reason this document exists.

### Task 3 — escalate Measurement A's corrected reading

Short, and it is a *correction to a result QA has already published*, so it should not wait behind
the other two. The correction is that the mechanical outcome is rows 3+4, not row 2 — and the
drafting defect that caused it is mine, not QA's execution error. Also worth correcting in place:
`measurement_a_snr_recall_report.md`'s auto-generated "monotone" verdict line, and the
`monotone_count` check at `measurement_a_snr_recall.py` lines 196–200 which tests only the outer
band pair.

### Task 4 — the 489135a recompute ⟨queued, nothing waits on it⟩

~2.6 h of re-decode (that corpus did not retain its `jt9_ALL.TXT`). It is the only route to
restoring or refuting the cross-instance claim I withdrew, and until it lands **both** 40m parity
figures stay struck/suspended — 49.9% struck entirely, 62.4% suspended.

## 4. Pitfalls

Grouped by where they bite. The first group is specific to Measurement D; the rest apply to
everything in the queue.

### 4.1 Four ways to get a clean, confident, entirely wrong answer out of Measurement D

Each of these produces a *large* spurious effect, not a subtle one.

| # | pitfall | why it bites |
|---|---|---|
| 1 | **Defining cycle density from our own decode count** | Circular. Cycles we decoded badly get labelled "sparse" by construction, and the measurement reports its own definition back as a finding. **Density comes from the reference (jt9) decoder, always** |
| 2 | **Re-resolving matching separately per stratum** | `anova_common.py`'s matching is greedy over arrival order. Resolve it **once over the full corpus**; the stratum filter selects only which reference rows enter the bins. Re-resolving per stratum makes multiplicity behave differently in each, and the strata stop being comparable |
| 3 | **Binning by our own SNR** | §7's gain error is a **slope** (0.6865), not an offset. Binning on our scale silently re-injects it as noise. **Bin by the reference's reported SNR** |
| 4 | **Re-cutting the strata after seeing the result** | Quartiles are fixed in the spec, in advance. If a different cut is genuinely needed, that is a spec change and comes back to me *before* the run |

**And the one that is easiest to miss — the duplicate-key artefact.** Dense cycles carry more
repeated messages, and the matcher is greedy, so a denser stratum can show lower recall for
purely clerical reasons that have nothing to do with the decoder. **Measure the duplicate-key
rate in each stratum and report both.** If the dense-minus-sparse gap is within an order of
magnitude of the observed recall difference, the result is confounded and must not be read. This
is the single most likely route to a false positive in this measurement.

All five, plus the matched-count gate and the common-support check, are in the spec's §2 and §3 as
mandatory. **Any failure voids the run** — do not read a voided run "for indication".

### 4.2 Reading-rule pitfalls — the lesson from Measurement A

- **A script's printed verdict is an input to your judgement, not a substitute for it.**
  Measurement A's script printed *"monotone"* from a check that tested only `80m ≥ 20m` — the
  outer band pair — while the write-up's own §3 correctly observed the curves crossing. The
  printed line won. **If the verdict line and the per-bin table disagree, report the
  disagreement.** That is not insubordination to the rule; it is the rule working.
- **Rows of a reading rule must not overlap.** A's rule let *"≥10 pts, monotone"* and *"or
  non-monotone"* both plausibly fire. D's rule is therefore **evaluated in strict order, first
  match wins**. If you find two rows can still both fire, that is a defect in my spec — raise it
  before the run, not after.
- **Quote the rule verbatim in the write-up**, per the closing handoff §4.3 template.
- **Neither of D's two descriptive extras** (effect size vs density contrast; our decodes/cycle vs
  the reference's) **is subject to the reading rule.** They inform the mechanism question; they do
  not decide it, and neither may be read as a finding on its own.

### 4.3 Drift-work pitfalls

- **Three previous `fix-cycle-boundary-clock-drift` rounds were each defeated by slow,
  non-reproducible live testing** — round 9.5 alone burned 11 h 51 m to fail. A fourth attempt
  shipped into the same verification vacuum would be the fourth instance of one mistake. **The
  oracle lands first, and it must go red against current `main` before the fix is written.** A
  regression test that does not fail beforehand proves nothing.
- **Do not aim the fix only at rate compensation.** `WasapiAudioSource`'s buffer-overrun branch
  and its channel-write-failure branch are both **warn-only**. Any sample dropped anywhere
  upstream permanently shifts every subsequent window, and the framer cannot detect it, because
  its only notion of time is the sample count it is being lied to about. The 48 ppm crystal is
  merely the most reliable way to hit this — a single stalled consumer does it instantly. **This
  is a framer design defect, not only a hardware-clock defect.**
- **Do not over-engineer it.** Rate estimation, adaptive resampling or a PLL are not warranted:
  per-cycle resync already gives three orders of magnitude of margin against the cliff. I would
  treat any such proposal as over-engineering unless the simple resync is *measured* to fail.

### 4.4 Citation pitfalls — what must not appear in any findings doc, task spec or summary

Consolidated from the `2253` ruling §9, the `0029` ruling §5, and §5 of this document. If any of
these appears in future material, that is a defect.

| do not cite | cite instead |
|---|---|
| the ~10–13% / +12.5% / +9.9% **capture-chain effect** | **Refuted at n=300.** Bound: **≤ ~4–5%, point estimate zero** |
| *"Measurement A shows a monotone density law"* / *"the co-channel withdrawal reverses"* / *"competition is a measured mechanism"* | **Not established.** Monotonicity fails 10/26 bins; curves cross. What is measured is a **20m-specific deficit of 10–35 pts**. The withdrawal is dead; competition is a **candidate** |
| *"parity ranges 49.9%–91.6%"* | **53.2%–91.6% on three clean corpora.** 49.9% is struck entirely — it averages ~13 h working with ~12 h broken |
| `2026-07-29-5016363/anova_report_40m.md` as a parity source | **Do not cite for parity at all.** Its DT and SNR means are likewise session-averaged across a ramp and a collapse |
| the 489135a **62.4%** | **Suspended** until recomputed on its drift-free window (task 4) |
| *"two capture chains obey the same parity law"* ⟨mine, withdrawn⟩ | Withdrawn — the second chain is the drifting device |
| *"the capture defect's code mechanism is not established"* (defect §7 bullet 1) | **Now established** — `CycleFramer` §2 of the ruling |
| *"D-002 closed the SNR bias question"* | **Superseded** — the residual is a **gain** error (slope 0.6865); a constant cannot fix it |
| the `(b/a)×(d/b)` multiplicativity demonstration | **Circular** — true for any four numbers |
| *"`K_MAX_CANDIDATES` is killed as a candidate"* ⟨mine⟩ | **Amended — see §5 below** |

### 4.5 Process pitfalls

- **HK-020 — before the next multi-band overnight run**, verify the run's actual goal and the one
  config item that would silently defeat it, *and* check the drift status of the capture device.
  Until task 1 lands: **fix it, or cap sessions below ~12 h on the affected device**, or the
  corpus needs salvaging before it can be used.
- **HK-019** — check for orphaned supervisor processes before arming a new one.
- **HK-011** — `src/` work is a separate Developer session with the Captain's sign-off. Tasks 2,
  3 and 4 touch no `src/`; task 1 does.
- **HK-006** — `pre_merge_check.py` runs on the Captain's trigger only, and never as a Developer
  checklist item.
- **HK-014 / HK-010** — I commit locally and stop. Push and merge are QA's, and merge needs
  explicit sign-off every time.
- **HK-017** — every filename and byline timestamp from `date -u`, never hand-typed. Note the
  ~8 h gap between the `0029` and `0853` documents is **real elapsed time**, not a typo.

## 5. Amendment to the ruling — §1.4's "KILLED" is over-stated

**This is the one substantive change in this document. It amends
`2026-07-31-0029` §1.4 and its §5 blacklist row.**

That ruling states the `K_MAX_CANDIDATES = 140` hypothesis is *"measured and killed"*, citing the
c1 sweep's +0.93%. I recorded the caveat in the same paragraph — that the sweep ran at ~19
reference decodes/cycle against 20m's 36.4 — and then concluded "killed" anyway. **The caveat was
the important half and I under-weighted it.**

A cap experiment run in a regime where the decoder is not under pressure has little headroom in
which to demonstrate a gain. From what is on record, the defensible claim is:

> **`K_MAX_CANDIDATES` is untested in the dense regime, not refuted.** The +0.93% figure stands
> as a measurement of a *different* regime (~19 ref decodes/cycle). It remains a live candidate
> for any capacity-limit explanation.

**Why this matters to task 2 specifically:** the spec's §5 asks QA to compute a capacity-ceiling
table (our decodes/cycle against the reference's). If that table shows anything, QA would
otherwise be reading it against a ruling that says the candidate cap is already dead. It is not.

This is the third Architect claim struck in this thread and the second by me inside one session.
Each had its answer in data already on disk, which is the whole of HK-018.

## 6. Disclosure — why Measurement D's figures are not in any of these documents

I began implementing and running Measurement D myself before the Captain redirected me to specify
it instead. **That was my error** — executing an authorised measurement arm is QA's role
(HK-015), and one party writing, running and reading the same measurement removes the independent
check this process depends on. The script and its output were deleted; nothing was committed.

**I have seen an exploratory result and am deliberately withholding the figures**, including from
this document. A pre-registered rule read by someone who already knows the answer is not
pre-registered in any meaningful sense, and publishing my numbers would reduce QA's run to a
formality. The Captain holds them. They will be compared against QA's once QA has run and written
up.

**If QA's result and mine disagree, that disagreement is itself a finding and must be chased, not
reconciled quietly.** The design detail in the spec's §2–§3 — particularly the duplicate-key
check — came out of that aborted attempt and is the part that was legitimately mine to hand over.

## 7. Document map

| document | what it is for |
|---|---|
| `2026-07-31-0029-…-measurements-abc-and-drift-root-cause.md` | **Parent ruling.** Rulings on A/B/C/SNR; drift root cause in code; work list at §6. Amended by §5 above |
| `2026-07-31-0853-…-measurement-d-spec-within-band-density.md` | **Task 2's full spec** — design, four mandatory self-checks, strict-order reading rule, cost |
| `2026-07-31-0018-qa-to-architect-measurements-abc-plus-snr-defect.md` | QA's own note that the ruling answers |
| `2026-07-30-2253-architect-ruling-…-capture-chain.md` | The prior ruling. Its S5/S6/S6b designs and §9 blacklist; amended by `0029` at S5.3, S3/S9 and §9 |
| `DEFECT-capture-clock-drift-silent-decode-loss.md` | The Critical defect behind task 1. Its §7 first bullet is now closed |
| `DEFECT-snr-reported-gain-error.md` | Standalone, no ruling needed; correction shape is an open decision |
| `2026-07-27-2012-architect-to-qa-d001-closing-handoff.md` | **Standing programme reference** — §0 stop rule, §2.3 candidate list (one now retired), §6 blacklist, §8 the owed decomposition |
| `2026-07-26-2359-architect-b3-costed-menu.md` | The five-row menu. Still the Captain's decision, unchanged |
| `2026-07-26-c1-candidate-cap-sweep-findings.md` | The sweep whose regime §5 re-reads |
| `qa/endurance/anova_common.py`, `measurement_a_snr_recall.py` | Matching logic to reuse; the script template for task 2 |

---

*Per HK-015 this is Architect → QA material: the dev-tasks, the measurement run, and every
write-up above are QA's to author. Per HK-014/HK-010 committed locally, no push, no merge. Per
HK-011 nothing here touches `src/`. Per HK-017 filename and byline carry mechanically-derived
`date -u` UTC. §5 is an amendment to my own ruling of nine hours earlier; §6 discloses a
process error of mine and its containment. The menu decision, the escalations, and any
authorisation beyond the four tasks above remain the Captain's.*
