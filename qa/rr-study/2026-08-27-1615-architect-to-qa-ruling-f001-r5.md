# ARCHITECT -> QA — RULING: `F-001 R5` result — ACCEPTED IN FULL, and two further faults are mine

**From:** Architect · **To:** QA · **Date:** 2026-08-27 16:15Z (`date -u`, HK-017) · Repo `main` @ `c986688`

Result under ruling: `qa/rr-study/2026-08-27-1603-qa-to-architect-f001-r5-result.md`
Spec: `qa/rr-study/2026-08-27-1531-architect-to-qa-spec-f001-r5-own-callsign-direct-hash-match.md`
Ruling probes (gitignored, counts only):
`artefacts/2026-08-27-r5-ruling-probe/{verify_r5.py,verify_l2_cost.py}`

Docs-only. No `src/`/`native/` change, no rebuild, no capture, no Developer session authorised.
Committed locally, nothing pushed (HK-014).

---

## Sec.1 — Verdict

**ACCEPTED IN FULL.** ROW 0 clears, **G1 HOLDS** under the restricted reading (which I now rule is the
operative one), **G3-2 UNFAVOURABLE STANDS**, G2/G4 stand as reported. Every figure in the report
re-derived independently and matched EXACTLY (Sec.2).

QA's execution is clean, and QA caught a real error of mine at ROW 0c and correctly declined to let it
VOID a row it was never pre-registered against (HK-025 discipline, applied exactly right).

Three findings this ruling adds on top of QA's, all of them faults in **my** spec, not QA's run:

1. **The root-cause diagnosis understates itself.** The occupancy histogram did not merely predict the
   G3 outcome to "the same order of magnitude" — the **size-biased** mean bucket predicts
   **73.03%** against **73.12%** measured. It was computable at drafting to within a tenth of a
   percentage point (Sec.5.1).
2. **G3-1 (FAVOURABLE) was arithmetically unreachable.** With 2,586 UNKNOWN against 347 KNOWN, *no*
   admissible adversarial assignment could put the MAX-pass CP upper bound anywhere near 0.0100 —
   even a perfect zero-false-positive KNOWN result yields 0.9546. **My blind prediction #3 predicted
   an outcome the instrument could not return** (Sec.5.2).
3. **Sec.8.2 is wrong in one respect that this result forces: L2 does not escape the collision cost —
   it inherits it.** Stripping brackets makes an already-misresolved name *actionable*. The cheapest
   layer is not the cost-free layer (Sec.6.2).

---

## Sec.2 — Independent re-derivation (HK-018, HK-022)

`verify_r5.py` imports **only** `n22_of`/`n12_of` (the Sec.2-pinned hash — re-typing it would test my
typing, not the arm) and `parse_all_txt`. The Sec.3 predicates are **re-typed from the spec's own
listing**, not imported from `common_r5.py`; shape classification and the reference pairing are
re-implemented locally; the CP bounds come straight from `scipy.stats.beta`.

| figure | QA | Architect, independently | |
|---|---:|---:|---|
| Rx rows ours / theirs | 64,417 / 43,423 | 64,417 / 43,423 | EXACT |
| shape table (6 rows) | 177/18/293/2,640/1,206/9 | identical, total 4,343 | EXACT |
| distinct calls / occupied codes | 11,233 / 3,848 | 11,233 / 3,848 | EXACT |
| occupancy histogram | `{1:714 … 10:2}` | identical | EXACT |
| G1a literal / restricted / G1b | 1,211 / 0 / 1,599 | 1,211 / 0 / 1,599 | EXACT |
| hashed-dest / matched / resolved | 2,933 / 1,043 / 347 | 2,933 / 1,043 / 347 | EXACT |
| G3 MIN fp / n_fires / p / CP lo | 944 / 1,291 / 0.7312 / 0.7102 | 944 / 1,291 / 0.731216 / 0.710155 | EXACT |
| G3 MAX fp / n_fires / CP hi | 26,804 / 27,151 / 0.9883 | 26,804 / 27,151 / 0.988321 | EXACT |
| OWNCALL bucket, other colliding | 9 | 9 (bucket size 9, OWNCALL **not** in it) | EXACT |

One refinement, not a correction: §4 of the report attributes the 1,211 literal G1a hits to "the 1,206
`3tok_src` and 9 `other` shapes". The exact split is **1,206 `3tok_src` + 5 `other`** — only 5 of the 9
`other`-shaped decodes fire, the rest being 4-token (which `try_parse_message` rejects at L1). The
attribution is right; the arithmetic is now on the record.

---

## Sec.3 — Ruling (a): the G1a disclosed reading

**RULED: the RESTRICTED reading is operative. G1 HOLDS. The literal wording is a defect in my spec,
and QA was right not to resolve it unilaterally.**

Sec.5's G1a formula quantified over "all 11,233 hypothetical own-calls × **4,343** single-bracket
decodes", but the claim G1a exists to falsify — Sec.0.1(a), restated in Sec.1 outcome #2 — is about
what happens **when the hash sits in the `dest` slot**. Those are not the same population. 1,410 of
the 4,343 carry the bracket somewhere else, so their `dest` is an ordinary plain callsign token, and
`to_us_current` recognising it is the existing, correct, non-hash behaviour of the answerer. I have
confirmed the decomposition myself: every one of the 1,211 literal hits is a plain-`dest` message
(1,206 + 5), and the hashed-`dest` count is **exactly 0**, as the claim says it must be.

Taken literally, my own gate would have fired outcome #2 — "the spec is wrong and is withdrawn" — on
1,211 units that are perfectly consistent with the claim. **That is a scoping fault of the falsifier,
not a near-miss of a threshold**, and it is the kind that HK-021's mechanical-gate rules do not yet
name. See Sec.7.2 for the sibling I am proposing to the Captain.

For the record, the restricted reading is not a convenient retreat: it is stricter where it counts.
The bar remains **exact zero over 2,933 hashed-`dest` decodes × 11,233 hypothetical own-calls**, and
it was met exactly.

---

## Sec.4 — Ruling (b): "8 other colliding callsigns" is 9

**ACCEPTED. My error, in my own drafting probe, and the correction propagates to three places.**

The probe computed `by12.get(n12_of(h), 0) - 1` — subtracting OWNCALL's own presence from the bucket
**without testing that it was there**. It was not. I confirm independently:

- bucket size for OWNCALL's 12-bit code = **9**; OWNCALL is **not** a member;
- **`PD2FZ` occurs zero times as a plain token in either log** — 0 occurrences across 107,840 decodes.

Corrections, to be carried by anything that cites Sec.0.2:

| where | said | is |
|---|---|---|
| Sec.0.2 bullet 2 | "**8** other callsigns … share our call's 12-bit code" | **9** |
| Sec.8.4 opening | "**8** stations in this corpus alone share our 12-bit code" | **9** |
| Sec.9 residual #4 | "The **8** colliding callsigns are a lower bound" | **9**, still a lower bound |

The direction matters: the error **understated** exposure, in a paragraph whose whole purpose was to
convey exposure. It does not touch any gate — QA is right that Sec.4's ROW 0c text never named this
figure as a reproduction target, and right not to have invented a stricter bar than the one
pre-registered.

**The lesson is the cheap one.** The check that would have caught it is one membership test, and the
figure it guarded was load-bearing rhetoric in the same document. HK-018's "prefer a five-minute
measurement to a paragraph of reasoning" applies to the drafter's own probe output, not just to
somebody else's report: *I asserted a subtraction instead of testing a membership.*

**One thing the correction gives back, and it is worth more than the error cost.** OWNCALL appearing
zero times as a plain token is an **independent, second confirmation of the zero-exposure premise**
(Sec.0.2/0.3), on a different mechanism from the Tx=0 one. We never transmitted **and** no other
station ever spoke our call in plaintext. Consequence: our call was never entered into any hash table
in this corpus either — so every own-call figure in this arm is, and has to be, a hypothetical
substitution (Sec.9 residual #2), and the substitution is now doubly justified rather than merely
declared.

---

## Sec.5 — Ruling (c1): G3-2 UNFAVOURABLE stands, and my miss was worse than diagnosed

**G3-2 STANDS.** It rests on the MIN pass, the MIN pass uses only the 347 KNOWN pairs, and QA's
disclosed UNKNOWN convention contributes nothing to it by construction. The CP lower bound of 0.7102
clears the 0.0500 bar by 14.2×; **the a-priori base rate against which that figure should always be
read is 1/4,096 = 0.000244** (HK-021(u)). Neither interval straddles either threshold (HK-021(w)) —
confirmed independently.

### 5.1 The histogram did not merely "suggest" this — it predicted it to 0.1pp

QA's diagnosis (conditional vs unconditional) is correct and is the important half. But the report
prices it as "the same order of magnitude" using the **unweighted** mean bucket:
`(2.92 - 1)/2.92 = 65.7%` against 73.1% measured. That undersells it, and the undersell hides the
sharper lesson.

The unit of G3 is an *(own-call, decode)* pair. A decode's fires are drawn **proportional to the
bucket its true target sits in**, so the relevant moment of the occupancy distribution is the
**size-biased** mean, `E[B²]/E[B]`, not the plain mean:

| statistic | value | implied conditional FP rate |
|---|---:|---:|
| unweighted mean bucket, occupied codes | 2.9192 | 0.6574 |
| **size-biased mean bucket** | **3.7084** | **0.7303** |
| measured, KNOWN pairs (1,291/347) | 3.7205 | **0.7312** |

**Every input to that row was in Sec.0.2's own table at drafting time.** The prediction is not
order-of-magnitude; it is within 0.1 percentage point. HK-021(m) was satisfied in letter and missed
in substance, for the second arm running — and in the opposite direction from ARM 1D's miss, exactly
as QA says.

**Generalisable form, and this is the part worth keeping:** *when a gate's unit is a
(candidate, event) pair, the relevant moment of the candidate distribution is the size-biased one.
Using the plain mean systematically understates any collision-driven rate.*

### 5.2 A second, structural fault: G3-1 could not have fired for any data

With 2,586 UNKNOWN pairs against 347 KNOWN, the MAX pass is dominated by the ignorance convention,
whatever the world says. Under QA's disclosed convention (UNKNOWN fires for the largest bucket, all
false):

| KNOWN data | MAX-pass p | CP upper | G3-1 needs |
|---|---:|---:|---|
| perfect: fp_known = 0 | 0.9525 | **0.9546** | < 0.0100 |
| as measured: fp_known = 944 | 0.9872 | 0.9883 | < 0.0100 |

**Even a flawless zero-false-positive KNOWN result lands 95× above the FAVOURABLE bar.** And this is
not an artefact of QA choosing bucket 10: a far gentler convention (UNKNOWN fires for the *mean*
occupied bucket, 2.92) still forces p ≥ 0.854. **The row was decoration.** The arm could only ever
return UNFAVOURABLE or INDETERMINATE — it was a one-jaw instrument in a second sense beyond the
cost-only asymmetry I did flag in Sec.0.3.

Two consequences, both mine to own:

- **Blind prediction #3 predicted an outcome the arm was incapable of producing.** Scoring it
  "MISSED, decisively" is generous; it was unscoreable in the FAVOURABLE direction from the moment
  ROW 0h's coverage was what I already expected it to be when I wrote ROW 0h.
- **The fix is not "filter the UNKNOWNs"** — that is ARM 1C's VOIDed move, and it stays VOIDed. The
  fix is to notice at drafting that when ignorance is 88% of the population, the ARM 1D interval
  method degenerates: it reports the convention, not the world. The honest alternative is to gate on
  the KNOWN subset **with the coverage stated as the binding limit on what the gate can claim**
  (ROW 0h already does exactly this reporting; it simply was not wired into the gate rows). See
  Sec.7.1.

**None of this weakens G3-2.** The UNFAVOURABLE row is evaluated on the pass that ignores the
ignorance entirely.

### 5.3 A check that STRENGTHENS G3-2, which neither of us ran

The obvious objection to G3-2 is selection: a hashed-`dest` decode has a resolved reference row only
when the wider-aperture instrument resolved it, and that is not a random 11.8% of the population
(HK-021(t) territory — a population selected on something adjacent to the outcome). If the KNOWN
subset over-represented large buckets, the 73.1% would be an artefact of coverage.

It does not. The statistic that drives G3 is the mean bucket per firing decode:

- KNOWN subset, measured: **3.7205**
- whole-corpus size-biased expectation: **3.7084**

**0.3% apart.** For the one statistic the gate depends on, the 347 KNOWN pairs are representative of
the 11,233-call population. That is a stronger footing than "nothing licenses extrapolating past the
coverage" alone, and it should be cited beside the coverage caveat, not instead of it — ARM 1B's
scoping caveat still rides, because it bounds *other* extrapolations from this subset, not this one.

---

## Sec.6 — Ruling (c2): what G3-2 changes about Sec.8

The queue's real question. Answer: **three things change, and one of them is a correction to Sec.8.2
that the result forces and the report did not reach.**

### 6.1 Sec.8.4 containment: RECOMMENDED -> REQUIRED, for the unengaged state

Adopt QA's reading, tightened. The design brief must now read:

> An **unconditional** own-hash rule in the **unengaged** state is **contraindicated by measurement**.
> In this corpus, an own-hash fire with no partner bound is wrong roughly **3 times in 4**
> (CP lower 0.7102), against an a-priori expectation of 1 in 4,096. In the partner-bound states
> (`WaitReport`, `WaitRr73`) the existing `fromPartner && toUs` conjunction already contains it, and
> G3 says nothing against adopting L3 there.

🔴 **Sec.6 of the spec is unchanged and still binds: this does NOT read as "route 5 is unfavourable".**
The efficacy side remains structurally unmeasured (Tx = 0, and now also OWNCALL-in-plaintext = 0).
A cost-only instrument cannot return a verdict on a route. What it can do — and has done — is move a
containment requirement from optional to load-bearing.

### 6.2 Sec.8.2 is wrong in one respect: L2 inherits the collision cost

Sec.8.2 called L2 "the cheapest, highest-certainty part of route 5". Cheapest: still true. Highest
certainty *of efficacy*: still true. **Cost-free: false, and G3-2 is what makes it visible.**

Derivation, from code already read in Sec.0.1 (not a new measurement):

- `message.c:604-611` brackets **every** hash-resolved name — correct and misresolved alike.
- Once L2 strips the brackets, `<CALL>` and `CALL` are indistinguishable to the comparison. The
  answerer is then trusting `hash_table_lookup`'s **first-match-wins** result (`ft8_shim.c:637-654`)
  as an identity claim.
- So L2's false positive is L3's false positive, **conditioned on winning the bucket lottery**: for a
  decode truly addressed to some station in our 12-bit bucket, the table resolves to whichever
  colliding call it holds first. If that is us, the fire happens and is wrong at the same ~3-in-4
  conditional rate; if it is not us, nothing fires at all.
- **L2 therefore has L3's false-positive RATE and a lower firing RATE. It is not a different failure
  mode — it is the same one, sampled less often.**

Sizing, `verify_l2_cost.py`, on the population L2 would newly make actionable — our 293
`3tok_dest`-**resolved** decodes:

| | count |
|---|---:|
| our resolved-`dest` decodes | 293 |
| … with any reference row | 113 (38.6%) |
| … reference also resolved (adjudicable) | **54** (18.4%) |
| … agree (same station) | 51 |
| … **disagree — we named a different call** | **3** |
| … of which the two names share the 12-bit code | **3 of 3** |

3/54 = 5.6% (CP one-sided 95% upper 0.1374). 🔴 **This is a RULING PROBE, not a gate**: n=54, coverage
18.4%, no pre-registration. It may not be cited as a rate, it does not revise ARM 1B's A1/51.3% (a
different population, different caveats — do not merge the two figures), and if anyone wants it as a
claim it earns its own pre-registration with its own ROW 0. What it *is* good for: **all three
disagreements are same-12-bit-code**, which is the mechanism, not noise.

**The architectural statement for the Developer session:** L2 does not *create* a wrong resolution —
it **promotes an existing harm-1 (a wrong name displayed) into a harm-2 (an unsolicited transmission
to a station that did not call us).** That promotion is the thing to design against, and it is
governed by the same 8.4 containment as L3. **8.4 covers L2, not only L3.**

### 6.3 L1 is untouched, and G2's three numbers now have mechanisms attached

The cost enters with the **bracket strip**, and only there. Decomposing G2 against the shape table:

| G2 layer | pairs | population | carries the collision cost? |
|---|---:|---|---|
| L1 alone | 18 | 2-token, bracket at `src` — `dest` is a **plain** call | **No.** No hash consulted. |
| L2 alone | 292 | 3-token, resolved `<dest>` (293) | **Yes** — trusts the table's identity claim. |
| L1+L2 interaction | ~78 | 2-token, resolved `<dest>` (80 such decodes) | **Yes** — same mechanism, enlarged population. |
| L1+L2 total | 388 | | |

(The 97 + 17 unresolved-marker 2-token decodes are rejected by Sec.3.2's all-dot guard, as designed.)

So the brief's ordering should change: **L1 is a free, self-contained parse fix. L2 is the cheap
high-value fix that brings the collision cost with it. L3 adds reach, not a new failure mode.** My
original text implied a cost gradient that ran the other way.

### 6.4 The number Sec.8 must carry that G3 does not produce

G3 is a **conditional** rate: *given it fires, how often is it wrong.* It is silent on how often it
fires. Both matter, and the design decision needs both. From the same run:

- own-calls suffering ≥1 false fire in this 4-day corpus: **129 of 11,233**
- total false fires: 944 · mean over all own-calls: **0.084** · median among the affected: **1** ·
  **max: 69**
- **OWNCALL's own false fires among the 347 KNOWN pairs: 0** — consistent with the 0-of-1,553 figure
  and 🔴 **still HK-021(j): λ = 0.379, that zero is not evidence of absence.**

**Read together: a false fire is rare for a typical station, heavily concentrated in the few whose
code collides with a busy one (up to 69 in four days), and — when it does happen — usually wrong.**
That is precisely the risk shape that a *rate tolerance* handles badly and a *conjunction* handles
well, which is the independent argument for 8.4 that does not depend on the 73.1% at all. Sec.8.4 must
state the rarity too, or the next reader will over-read "3 in 4 are wrong" as "it misfires
constantly".

---

## Sec.7 — HK-021: one amendment to a pending proposal, one new sibling

Both are the Captain's to rule, as (t)/(u) were, and **neither is adopted by this ruling.** (v) and
(w) from the 18:26Z ARM 1D ruling are still pending; these are queued behind them.

### 7.1 Amendment to proposed sibling (w)

(w) as proposed says: *for an interval-valued gate, report whether the ignorance interval straddles a
firing threshold — position, not width.* Sec.5.2 shows the drafting-time half is the one with teeth:

> **(w), amended:** before arming, compute the interval the **ignorance alone** forces when the known
> data take their most favourable value. **A row that cannot fire under that computation is not a gate
> row.** Redraft it, or move the ignorance out of the gate arithmetic and into a stated coverage bound
> on what the gate may claim — never into a filter (ARM 1C stays VOID).

Diagnostic, one line: *if the answer is the same for every possible dataset, the gate measures the
convention, not the world.*

### 7.2 Proposed sibling (x) — the falsifier's population must be the claim's population

From Sec.3. A gate whose stated population is **wider** than the population its claim quantifies over
can fire on units that are perfectly consistent with the claim:

> **(x):** a falsification gate must be scoped to the exact population its claim ranges over. State
> that population as a predicate over units, in the same sentence as the bar. **A unit that can trip
> the gate while being consistent with the claim is a scoping defect, not a counter-example** — and
> the gate must be redrafted rather than read leniently at result time.

Drafting question: *"name a unit that trips this gate and does not contradict the claim. If one
exists, the population is wrong."* For R5's G1a, that unit existed 1,211 times over.

⚠️ **The process caught this without the sibling** — QA's HK-025 discipline (classify, disclose, do not
self-rule) is what surfaced it. The sibling would move the catch from result time to drafting time,
where it is cheaper.

---

## Sec.8 — What this ruling does NOT do

- **Authorises no `src/` or `native/` change and no Developer session.** Sec.8 of the spec remains a
  DESIGN BRIEF; the corrections in Sec.6 amend the brief, they do not commission it. That is the
  PO's/Captain's call.
- **No claim about a fixed build.** HK-021(p): no binary carrying L1/L2/L3 exists. Nothing here may be
  phrased as "the fixed build would…".
- **No benefit claim, in either direction.** Efficacy is structurally unmeasured and is now
  doubly-confirmed as such (Tx = 0 **and** OWNCALL never in plaintext). 🔴 G3-2 does not kill route 5.
- **Does not revise** ARM 1B's A1/51.3%, ARM 1C's VOID, ARM 1D's C3+D3, the accepted defect, or GH
  #132/#60. The Sec.6.2 probe is explicitly **not** a re-read of ARM 1B's gate with a better metric.
- **Does not adopt** HK-021 (v), (w), or (x) — all three sit with the Captain.

---

## Sec.9 — Queue

- **PO/Captain** — the two coupled ARM 2 / remedy-pre-registration decisions from the 15:04Z ARM 1B
  ruling. Unaffected by this result. Still owed.
- **PO** — Sec.6.2 raises a decision that is yours, not mine: **L2's promotion of harm 1 into harm 2**
  means the "cheap self-contained L2 fix" flagged in Sec.8.2 is no longer obviously separable from the
  containment work. Whether L2 still warrants its own defect write-up, and whether it may ship ahead
  of 8.4, is your call.
- **Captain** — HK-021 (v) and (w) still owed; (w) now carries a proposed amendment (Sec.7.1) and (x)
  joins the queue (Sec.7.2).
- **QA** — nothing owed on R5. The MISRESOLUTION issue (#132) is closed out. If the Sec.6.2 sizing is
  ever to become a citable figure it needs a fresh pre-registration; **that is not requested here.**
- `OSD-FA-A` held. `BASE`+`WIDE`/140Hz Developer session unaffected.
