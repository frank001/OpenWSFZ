# F-001 D3 ARM 1C -- ARCHITECT RULING: VOID UPHELD. The design fault is mine and it is named.

**Architect → QA.** 2026-08-26 17:17Z (`date -u`, HK-017). Repo `main` @ `86c68c2`.

Report ruled on: `qa/rr-study/2026-08-26-1644-qa-to-architect-f001-d3-arm1c-result.md`.
Spec at fault: `qa/rr-study/2026-08-26-1619-architect-to-qa-spec-f001-d3-arm1c-unique-match-trade.md`.
Ruling probe: `artefacts/2026-08-26-arm1c-ruling-probe/void_audit.py` (gitignored).
Docs-only, committed locally, nothing pushed (HK-014). **No `src/` change authorised.**

---

## 0. Verdict

🛑 **VOID at ROW 0d is UPHELD.** The arm produced no outcome, and nothing in this ruling
retro-fits one. ROW C, ROW D, ROW E, the Sec.3.3 2x2 and Part B remain **uncomputed**, and
this ruling did not compute them either -- the ruling probe is firewalled against `matches12`
and asserts it (`v.pop("matches12", None)` before any use).

✅ **And the VOID does not rest on QA's one judgment call.** ROW 0c under the OTHER reading --
the literal one my spec actually wrote -- **also FAILS** (20 exceptions against a 100% bar), which
would have VOIDed the arm one row EARLIER. **The arm is VOID under both readings.** QA's disclosure
was the right thing to do; the verdict never depended on how it was resolved.

🔴 **The fault is a design fault in my spec, not a defect in QA's execution, and it has a name:
the per-query fidelity FILTER (Sec.3.2). Selecting the analysis population on whether the replay
reproduces the real build's output is selection on a variable correlated with the outcome. ROW 0d
is the check that caught my own design doing it.** ROW 0d existed because I did not assume
HK-021(h)'s protection; it earned its place.

---

## 1. What I verified mechanically (HK-018/HK-022 -- not by re-reading the report)

Re-derived from the on-disk dumps by an independent script, not by re-running `run_arm1c.py`:

| claim | reported | re-derived | verdict |
|---|---|---|---|
| ARM 1B population reproduces | k=243 / n=115 / 92 disagreeing | 243 / 115 / 92 | ✅ exact |
| fidelity(disagree) | 95.7% (88/92) | 88/92 = 0.95652 | ✅ exact |
| fidelity(agree) | 78.1% (118/151) | 118/151 = 0.78146 | ✅ exact |
| signed difference | +17.5pp | +17.506pp | ✅ exact |
| bar | abs(diff) <= 15pp | breached by 2.506pp | ✅ VOID correctly declared |

---

## 2. ROW 0c -- my wording was wrong, QA's verdict was right, one of its three reasons is not

**I own this.** Sec.4's ROW 0c welded two unlike claims into one row: a structural clause
(`lookup12 is None` iff `matches12 == 0`) and, in the same sentence, `matches12 >= 1` **"wherever
the real build resolved"** -- which is an *empirical fidelity claim about an external decoder*
smuggled into a row whose stated purpose is internal coherence between two functions on one table.
That is my drafting error. A row must test one thing.

- **QA adopted Reading B** (structural). Given the row's stated purpose, that matches my intent, and
  I ratify it.
- **Reason (ii) in QA's Sec.1 is incorrect and I am correcting the record:** Reading A was **not
  un-passable in principle.** The 84.8% already disclosed in Sec.0.4 is *same-name* fidelity; Reading
  A's clause is the strictly weaker "the replay found **something** on that chain", which ran at
  **98.9%** (20/1,868 exceptions). A 100% bar on it is achievable in principle -- it simply failed.
  So Reading A was a **badly-drafted gate, not a foregone one.** QA's conclusion stands on reasons
  (i) and (iii); (ii) should not be cited again.
- **Consequence for the verdict: none.** Reading A ⇒ VOID at 0c. Reading B ⇒ VOID at 0d. Same arm,
  same outcome, one row apart.

🔴 **Carry forward as a real error channel, not a footnote: on 1.1% of resolved type-4 queries the
replayed table has NO entry at all on the query's chain while the real build printed a name.** That
is table-state divergence (a missed insertion, or an eviction the replay does not model), and any
successor design must budget for it explicitly rather than discover it again.

---

## 3. ROW 0d -- how strong is it, and how close to the bar (HK-021(o))

**Resolution against the readout quantum, on the record:** one disagreeing decode flipping
verified→unverified moves the difference by **1.087pp**; one agreeing decode by **0.662pp**. The
measured difference sits **2.506pp past the bar = 2.31 disagree-flips**. ⚠️ **Say it plainly: had
three of the 92 disagreeing decodes failed verification, this arm would have PASSED ROW 0d.** The
VOID is correct as pre-registered, and it is thin against the bar.

**That thinness is not a reason to doubt the differential itself.** Descriptive, non-gating,
post-hoc, and stated as such: the 2x2 `[[88,4],[118,33]]` gives **Fisher two-sided p = 1.6e-4**. The
differential is real; it is the *15pp bar* that is arbitrary, not the effect. Both facts belong on
the record together, and neither licenses moving a bar afterwards.

**Which way it cuts** (QA reported it, I confirm it): positive ⇒ the filter preferentially drops
**right** names, so the arm would have over-stated **cost**. Under HK-021(h) that is the *unsafe*
direction for a design whose every figure was to be quoted as a floor.

**Mechanism: still a hypothesis, and I am NOT adopting QA's.** QA's Sec.2 hypothesis is reasonable
and unmeasured; I have one of my own that is equally unmeasured (agreement in the real build may be
over-determined -- reachable by table states the 12-bit replay does not model -- while a collision
error is single-mechanism and therefore easier to replay). **Neither is evidence. Sec.9 authorised no
investigation and this ruling authorises none either.** No successor arm may assume either.

---

## 4. The repair, and the measurement that decides whether it is worth speccing

The failure is not "the replay is too inaccurate to use". It is that **I used accuracy as a
FILTER.** Remove the filter and the differential stops being a validity threat, because nothing is
selected on the outcome any more. The unverified decodes become **bounded ignorance** instead: each
one's true multiplicity is unknown, but **its callsign is known** (it is the name the build printed),
so it can be assigned adversarially in both directions and the gate reported as an interval.

**Whether that is decisive is arithmetic, and it is answerable WITHOUT touching the voided crossing.
I measured it** (probe Q3 -- no `matches12` read anywhere):

| | unfiltered units | units carrying >=1 unverified decode | max ignorance width |
|---|---:|---:|---:|
| **ROW C** (>=1 disagreeing decode) | **59** | **3** | **5.1pp** |
| **ROW D** (all decodes agree) | **56** | **7** | **12.5pp** |

The unverified decodes are **concentrated, not spread**: 37 unverified decodes touch only 10 of 115
callsigns. Both denominators **rise** (C 56→59, D 49→56, both clear of the n>=40 under-power stop)
because dropping the filter returns population rather than costing it, and the worst-case ignorance
is **narrower than the ~21-point indeterminate band those gates already declared.**

The bound is one-directional per row, which is why it is this tight: ROW C's rule ("ALL of a
callsign's disagreeing decodes ambiguous") can only be *broken* by an unverified decode, and ROW D's
("ANY decode ambiguous") can only be *triggered* by one -- so each unverified unit moves its gate in
one known direction, never both.

⚠️ **What the repair does NOT fix, stated up front so it is never claimed:** for the ~85% of decodes
the replay does verify, the design still assumes the replayed *multiplicity* is right because the
replayed *name* was right. ROW 0d attacks the selection, not that assumption -- but a correlation
between the two is unmeasurable without multiplicity ground truth, so every figure stays a **floor**,
and a successor arm must say so in the same sentence as its numbers.

🛑 **A successor is a NEW pre-registration with its own ROW 0, not a re-run of this one, and not this
spec with Sec.3.2 deleted.** Standing rule: never re-read a closed gate with a better metric. And
HK-021(p) still bites -- no unique-match binary exists, so a successor still measures a **property of
the build we ran**, never "what the fixed build would do".

---

## 5. What this changes -- and what it does not

- ❌ **Does not revise ARM 1B.** A1 stands; 51.3% stands as a lower bound on the joint error, with its
  both-resolved scoping caveat intact. ROW 0d is information about *this arm's instrument*.
- ❌ **Does not revise `DEFECT-twelve-bit-hash-misresolution.md`.** Accepted-and-marked, unchanged.
- ❌ **Does not re-open, unblock, or pre-judge ARM 2 or the remedy pre-registration.** Both stay
  coupled and awaiting the PO, decidable on exactly the information they had before ARM 1C ran.
- ❌ **Authorises no `src/` change, no Developer session, no policy, no remedy** -- as was already
  true under every enumerated outcome.
- ✅ **Leaves the PO's actual question -- what would a unique-match rule buy and cost -- OPEN and,
  on the evidence above, still answerable offline in minutes** by a design that bounds the replay's
  error instead of filtering on it.

---

## 6. Recommendation

**Spec `ARM 1D`: the same question, filter replaced by adversarial bounds, fresh pre-registration.**
It is cheap (pure re-analysis, no rebuild), it directly serves the PO's standing preference for
sizing the trade before committing to arm 2 or a blind remedy, and its decisiveness is no longer a
hope -- Sec.4's 5.1pp/12.5pp says the bounds are narrow enough to separate at the gate.

**My honest caveat: this is the second design against this question, and it inherits an
unfalsifiable assumption (Sec.4's warning).** If the PO would rather stop paying for simulated
stratifiers, the alternative is defensible and I will say so plainly: **close the offline route, and
let the trade be measured exactly, with no simulation at all, inside the Developer arm any remedy
would require anyway.** That answer costs a build; it owes nothing to a replay.

**I do not draft ARM 1D unprompted (HK-004/HK-015).** The PO's word decides.

---

## Queue

➡️ **PO: (1) `ARM 1D` -- spec it, or close the offline route · (2) the two coupled `ARM 2` /
remedy-pre-registration decisions, unchanged by this VOID · `OSD-FA-A` still held ·
`BASE`+`WIDE`/140Hz Developer session per the Captain, unaffected. QA owes nothing on ARM 1C.**

## Cross-references

- `qa/rr-study/2026-08-26-1644-qa-to-architect-f001-d3-arm1c-result.md` -- the report ruled on.
- `qa/rr-study/2026-08-26-1619-architect-to-qa-spec-f001-d3-arm1c-unique-match-trade.md` -- the spec
  whose Sec.3.2 filter is the named design fault.
- `qa/rr-study/2026-08-26-1504-architect-to-qa-ruling-f001-d3-arm1b.md` -- parent ruling; ARM 1B
  unrevised by this one.
