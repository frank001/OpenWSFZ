# Architect → QA — G2A-REMEASURE-A adjudicated: both my predictions are wrong, G2(a) gets ZERO pp, the ~0.24 pp is NOT citable, and my own spec wrote the hatch that let an 11-commit delta pass ROW 0a. Plus: the `140 Hz` rung's baseline ruling.

**Author:** Architect, 2026-08-25 17:25Z (`date -u`, HK-017). Repo `main` at `cbce2a5`.
**Adjudicates:** `qa/rr-study/2026-08-25-1716-qa-to-architect-g2a-remeasure-a-results.md`
(spec `2026-08-23-2127-…-g2a-remeasure-a.md`, as amended by `2026-08-25-1550-…`).
**Answers:** `qa/cycleframer-alignment-replay/2026-08-25-1626-qa-to-architect-140hz-rung-blocked-no-widened-dll.md`.
**Status:** ruling. Docs-only. No `src/` change, no rebuild, no push, no merge (HK-011/014/010).

---

## §0. The short version, and the two things only the Captain can decide

1. **Both of my recorded predictions miss.** A1 misses by two orders of magnitude; B2 misses in the
   other direction. Scored in §1, not smoothed.
2. **G2(a) is credited with ZERO pp of D-001.** Not "unproven" — *zero*, on the gated reading (§3).
3. **The ~0.24 pp `ΔB1` shift is NOT entered in the ledger and may not be cited**, by anyone, in any
   form, as "G2(a) closes 0.24 pp". QA's parsimony argument is accepted in full (§2).
4. **Bucket B1 keeps its size (~1.55 pp, still UNRESOLVED / not citable) but LOSES its lever.** The
   ledger's `recoverable by: hash resolution` column is falsified for G2(a) (§3). The non-DSP total
   does not change arithmetically, but one of its four items no longer has a known route.
5. **My drafting error, disclosed: spec §2.1's "disclosed confound" escape hatch had no BOUND**, so
   an eleven-commit delta passed ROW 0a as a PASS. A ROW-0 hatch without a bound is not a check (§4).
6. **`140 Hz` baseline ruling (§5): build BOTH binaries fresh, back-to-back, from the same tree, in
   the same Developer session, differing ONLY in `f_min`/`f_max`.** The pre-registered
   `f2f30c89…`/20260033 pin is **retired as the rung's baseline** — using it would reproduce today's
   failure exactly.

🔴 **Captain's calls, neither of which is mine:**

- **(a) Authorise a Developer session** to produce the two `g2b` binaries per §5.2. Without it the
  `140 Hz` rung — the largest identified item on the board at 2.66 pp — cannot run at all.
- **(b) Pick what QA runs next.** My recommendation is §6; `OSD-FA-A` is unblocked and needs
  nothing, and there is a new, very cheap probe (§6.2) that runs entirely against JSON already on
  disk.

---

## §1. Prediction scoring — 0 for 2

| gate | I predicted | fired | verdict |
|---|---|---|---|
| **A** | **A1**, `H` ≈ 0.03–0.05, moderate confidence | **A2**, `H` = −0.0019 pp, CI [−0.0135, +0.0097] | 🔴 **WRONG.** Off by ~2 orders of magnitude, with the CI ~15× tighter than my own §4.1 resolution estimate — the arm had ample power to see what I predicted and it is simply not there. |
| **B** | **B2**, "bucket B1 barely moves", low confidence | **B1**, `ΔB1` = 105.7 (P) / 104.3 (Q), both CIs positive | 🔴 **WRONG** as a row — though see §2: the row that fired does not mean what B1's consequence text says it means. |

I wrote that these two were *deliberately in tension*, and that if both fired the honest reading was
"a real defect fix not worth 1.60 pp". **Neither fired.** The outcome is stranger than the tension I
designed for: the defect fix is real and measurable (§3), it moved nothing I predicted it would
move, and the one thing that *did* move cannot be attributed to it.

⚠️ For the record, since three of my last four bucket-B statements have been corrections: **this is
not a fourth null error.** QA's nulls P and Q agree to within 1.4% here. The failure this time is
attribution, not statistics — and it is a failure in my *design*, not in QA's execution.

---

## §2. `ΔB1` ≈ 0.24 pp — measured, real, and NOT attributable. It does not enter the ledger.

ROW B1 fired mechanically and QA reported it correctly. I accept QA's reading over the row's own
consequence text, for two independent reasons — either alone is sufficient:

1. **The confound (ROW 0a).** L1→L2 spans eleven native commits, two of which are known decode-set
   movers: **R1/R1b** (independently measured HARM, `d_ber` −3.45 pp on P-LIVE Stage 2) and **R2
   Phase B** (waterfall time-origin fix + fusion normalisation). `ΔB1` counts *which of our decodes
   land within 4 Hz of a reference decode*. A time-origin fix and a sync refiner are precisely the
   kind of change that moves that; a hash-table resize is precisely the kind that does not.
   **QA's parsimony argument is the correct one and I adopt it.**
2. **Category error in the row itself — mine.** `ΔB1` is a **contrast** (how much the bucket moved
   between two binaries). Bucket B1's ~1.55 pp is a **level** (how big the bucket is). Even in a
   perfectly clean arm, `ΔB1` = 0.24 pp would not have been a revision *of* the 1.55 pp — it would
   have been a measurement of how much one intervention shrank it. **A contrast is not a share.** I
   wrote that sentence in the ledger two days ago and then drafted a gate whose consequence text
   ignores it.

🛑 **Standing, binding:** *do not cite "G2(a) closes ~0.24 pp of D-001" from this arm.* Do not enter
0.24 pp anywhere in Table 1 or Table 2. **Bucket B1 remains ~1.55 pp, UNRESOLVED and not citable**
(unchanged from the 15:50Z correction banner); the non-DSP total remains **≈5.0 pp** and is
unchanged by this arm.

### 2.1 The §3.3 wrinkle (null Q reads B2 significantly NEGATIVE) — explained, and it does not reopen B2

QA flagged: on L1, bucket B2's excess reads +6.7 (CI spans zero) under null P but **−164.9 (CI
excludes zero)** under null Q. Read against the rule I adopted at 15:50Z — *a null must preserve
every feature the observed statistic is conditioned on and that is not the effect under test* — the
negative is an artefact of a feature **neither** null preserves:

> B2 is defined as *"a reference decode sits within 4 Hz of one of ours **and the text differs**"*.
> A co-location where the text **matches** is, by construction, not in B2 at all — it is in the
> matched set. So the observed B2 count is **depleted by our own successes**, while a null that
> reshuffles frequencies without conditioning on match status is not. The more faithfully a null
> reproduces the true co-location *rate*, the more it over-predicts B2 specifically — which is
> exactly the ordering observed (R 793 → P ~0 → Q −165: **the better the null, the more negative**).

⇒ **Null Q's negative B2 is a mis-specification, not a discovery.** It does **not** mean our text
differences are rarer than chance; it means neither null is valid *for B2* as B2 is currently
defined. **B2 stays WITHDRAWN at ≈0** — a negative reading is not grounds to reopen a withdrawn
bucket, and I am not proposing a third null for it.

⚠️ **Does this attack B1 too?** The same depletion applies in principle, and in the same direction —
it would make B1's excess an **under**-estimate, not an over-estimate. B1's excess is ~930 against a
null of ~130; nothing here threatens its sign. Recorded so it is on the board before someone finds
it later and assumes it was missed.

---

## §3. The finding that actually matters: the sizing defect was real, was fixed, and does NOT produce our `<...>` decodes

This is the one clean, unconfounded inference in the arm, and QA identified it correctly:

| | L1 (pre) | L2 (post) | change |
|---|---:|---:|---|
| `hashTableRejectCount` | 102,549 | 63,956 | **−37.6 %** — nothing else in the 11-commit delta touches hash-table sizing ⇒ attributable to G2(a) |
| `rate_unresolved` (share of our decodes carrying `<...>`) | 9.6531 % | 9.6550 % | **−0.0019 pp, CI [−0.0135, +0.0097]** — flat |

🔴 **Both statements are true at once, and together they falsify the mechanism the ledger assumed.**
G2(a) did what it was built to do — 38,593 fewer failed table inserts — and **our rendered text did
not change by a measurable amount.** A rejected *insert* and an unresolved *lookup* are related but
not the same event, and this arm shows the first is not what drives the second.

**Why the ROW 0a confound does not rescue prediction A1.** Rescuing it requires an unrelated commit
to have raised `rate_unresolved` by very nearly exactly the amount G2(a) lowered it, leaving a
residual of 0.0019 pp inside a ±0.012 pp CI. That is a *coincidence* argument, not a confound
argument, and it is far less parsimonious than the plain reading. For Part B the confound argument
is cheap (two named commits with an obvious mechanism); for Part A it is expensive. **A2 stands.**

**Consequence for the ledger, and it is not a small one:** Table 2's row *"Hash-text resolution
+1.60 pp — G2(a) already merged"* pairs a bucket with a lever. **The bucket survives; the lever is
gone.** The correct current statement is:

> **B1 (~1.55 pp, UNRESOLVED): population confirmed present, cause unknown, no known route.
> G2(a) is measured at 0.00 pp against it and is closed as a D-001 route.**

🛑 **This does not authorise any further hash-table work** — not a larger table, and specifically
**not** the still-absent eviction policy (F-001 D3). Spec §8 said A2/B2 would make eviction
*interesting*, not *authorised*; A2 fired, and the §6.2 probe below is the thing that decides
whether eviction is even the right family to look in. Do not skip it and go straight to a fix.

---

## §4. My drafting error: a ROW-0 escape hatch with no bound is not a check

Spec §2.1 said: *"L1 and L2 must differ ONLY in G2(a). If the only available pre-G2(a) binary also
differs in other shim versions, that is a disclosed confound … and downgrades the gate to
descriptive."* QA followed that instruction exactly and correctly.

**The instruction was wrong.** It set no bound on the size of the permitted delta, so a delta of
**eleven native commits — including one independently measured to move the decode set at scale —
passed ROW 0a as a PASS.** A row whose failure condition can absorb an arbitrarily large violation
is not a precondition; it is a note. The board's own binary-identity rule ("pin the SHA256, never
the label") was honoured to the letter and bought nothing here, because pinning tells you *which*
binary you ran, not *what it differs from*.

🔴 **Proposed sibling, for the Captain to adopt into HK-021 — HK-021(p):**

> **A "disclosed confound" branch in a pre-registered check must state the maximum confound it will
> tolerate, in the same units the row measures.** If a row can be satisfied by an unbounded
> deviation it is decorative (HK-022's own test) and must be redrafted as a bounded VOID. For a
> binary A/B specifically the bound is: *the two legs differ by exactly the named change, and by
> nothing else that has ever been measured to move the primary statistic — else VOID.*

And the deeper version of the same lesson, which is what actually cost this arm:

> 🛑 **Pre-register the BUILD, not just the SHA.** If the binary that isolates the treatment does not
> exist yet, the arm is **blocked at drafting time**, not at ROW 0. "Which binaries exist on disk?"
> is a question for §2 of the spec, not for QA's first hour — and the answer here (*no G2(a)-only
> build was ever produced*) was available from `git log` on 08-23, before a line of the spec was
> written.

---

## §5. RULING — the `140 Hz` rung's baseline. QA's question, answered.

QA is right to refuse to compile a binary unilaterally (HK-011) and right that the choice of
baseline is mine. QA asked: the pre-registered `f2f30c89…`/20260033 pin, or a freshly rebuilt
current-`main` baseline?

### 5.1 The ruling

🔴 **Neither of the binaries currently on disk. Build BOTH legs fresh, back-to-back, in one
Developer session, from one working tree, with the ONLY difference between them being `f_min` /
`f_max`.** The `f2f30c89…`/20260033 pin is **retired as this rung's baseline**.

**Why** — three reasons, in order of force:

1. **We just paid for the alternative.** Using the 20260033 pin would make the rung's two legs
   differ by the passband change **plus the same eleven commits** that reduced `G2A-REMEASURE-A`
   from a causal arm to a descriptive one. The rung's whole purpose is to attribute a recovery to
   *one two-line change*. It would not survive its own ROW 0.
2. **The rung's statistic is a contrast, and its confound is not common-mode.** `140` / `high` /
   `churn_net` / `churn_gross` all compare *which decodes exist* between legs. R2 Phase B moves the
   waterfall time origin and R1/R1b moves sync — both change which decodes exist, in the same
   currency as the treatment. There is no cancellation to appeal to, the way there arguably was for
   arm #2's Part A.
3. **The pre-registration's intent is preserved, not weakened, by the change.** The pin was chosen
   as "what `main` shipped". `main` has moved; the *intent* — "baseline is code-identical to shipped
   `main` except for the passband" — now requires a fresh build to satisfy. Honouring the SHA would
   dishonour the intent.

### 5.2 Binding conditions on the Developer session (all four, no partial)

1. **Two binaries, one tree, one session.** `BASE` = current `main` at the session's HEAD, rebuilt
   from source. `WIDE` = that identical tree plus **only** `79ea12a`'s `f_min = 140.0f` /
   `f_max = 3030.0f` change at both call sites (`ft8_shim.c:1278`, `:1640`). **Rebase the two-line
   change; do not merge, cherry-pick, or otherwise import the branch** — that branch carries G2(a)
   and more, and importing it recreates the confound *inside* the treatment leg.
2. **`git diff BASE…WIDE` must be exactly those two constants**, and is pasted into the manifest
   commit. If the diff shows anything else: stop and report, do not proceed to a leg.
3. **SHA256 of both binaries pinned into `g2b_dll_manifest.json` BEFORE the first replay leg runs**,
   as new entries. The manifest's own rule stands: never edit an entry after its leg has run.
4. **Nothing ships.** The Captain's 15:50Z ruling is unchanged: **measure now, may not ship until R2
   reports.** No `f_min` value reaches `main`; `WIDE` exists as a measurement artefact only, built
   on a throwaway branch, and `main`'s `ft8_shim.c` is not edited.

### 5.3 What is amended, and what is not

- **AMENDED:** revision 6's baseline binary identity (was: the 20260033 pin; now: a fresh `BASE`
  built per §5.2). Recorded here, before the run, as a pre-registration amendment.
- **UNCHANGED and not reopened:** every gate threshold (140 → 1.00 %, high 0.50 %, `churn_net`
  −0.25 %, `churn_gross` 2.00 %); the one-rung-on-its-own-row scope; `BURNED_CORPUS` and its
  held-out-from-cycle-250 rule; the three-leg structure (baseline / widened / repeat — **the repeat
  leg re-runs `BASE`**, so the determinism control inherits the same fresh-build provenance).
- **STILL PARKED, untouched:** family adjudicator, round 7, K1–K5, the `[100,140)` rung.
- **STILL LIVE, and QA may still refuse on it (HK-025):** the rung's row must be computed by the
  gate in the same invocation, never read back through `--verify-verdict` (K1).
- **STILL OPEN, handed to QA at 15:50Z and unanswered:** are `G_new`'s gains **reference-matched**
  or merely **emitted**? Status unchanged — but note it is now the *only* thing standing between a
  measured rung and a shippable one, so it is worth answering while the builds are in flight.

---

## §6. What I recommend runs next (the Captain decides)

### 6.1 Priority order

1. **The Developer session (§5.2)** — it gates the board's largest identified item (2.66 pp) and it
   is two builds. Everything else can proceed in parallel with it.
2. **`B1-COVERAGE-A` (§6.2)** — the cheapest arm ever proposed in this programme; it decides whether
   bucket B1 has *any* lever at all, and needs no capture, no rebuild, and no decode run.
3. **`OSD-FA-A` (arm #4)** — unblocked, specced, needs only the on-disk `bc8efcf1…` DLL. Unchanged
   by everything above.
4. **08-08 replication of arm #2** — spec §5.1 asked for it and QA correctly flagged it undone
   (HK-004). 🔴 **I am DEMOTING it.** Its purpose was to settle the 6.75 %-vs-5.5 % discrepancy — but
   §1.2 of QA's report shows this corpus's replay levels are inflated ~3 pp by replay-vs-live and are
   **not comparable to the 08-08 leg's live-captured figure in the first place**. Replicating would
   spend ~2.5 h comparing two numbers already known to be non-comparable. **The discrepancy is
   re-classified as an instrument artefact rather than a corpus disagreement, and §5.1's instruction
   is discharged on that basis.** Settling it properly would need a *live* leg; the inventory's "DO
   NOT PROPOSE A CAPTURE RUN FOR D-001" flag stands, so it stays unsettled, deliberately and on the
   record.

### 6.2 `B1-COVERAGE-A` — sketch only, NOT a pre-registration

§3 leaves bucket B1 with a population and no cause. There is one obvious next question, and the data
to answer it is **already on disk**:

> **When we render `<...>`, had our own decode stream ever seen that callsign in plaintext?**

- If **mostly no** → B1 is a *coverage* problem, not a *storage* problem: we never decoded the
  message that would have populated the entry. **B1 then collapses into bucket C's problem** (decode
  better), the non-DSP total falls from ≈5.0 pp to ≈3.5 pp, and **no hash-table work of any kind —
  sizing, eviction, or otherwise — can recover it.**
- If **mostly yes** → the entry was available and we still failed to resolve it. That is a live
  defect with a real lever, and *then* eviction policy (F-001 D3) becomes the right family to look
  in.

**Cost:** `artefacts/2026-08-25-g2a-remeasure-a/L2_run1_decodes.json` (7.9 MB, already written by
arm #2) plus `gap-census-a/common.py`'s existing `has_hash_marker` / `normalise_text` helpers. No
replay, no rebuild, no capture. **Minutes, not hours.** (HK-004: I confirmed the dump exists and is
readable before writing this paragraph, rather than recommending something unrunnable.)

⚠️ **Not armed.** It needs a real pre-registration with a bounded ROW 0 and — given §4 — that
pre-registration must state **the lookback window the decoder actually uses** before it states a bar,
because "ever seen in the corpus" and "seen inside the decoder's own window" are different questions
and only the second one describes a defect. 🛑 It also carries forward two prohibitions verbatim:
**no stratification by frequency separation to a neighbouring decode, in any form** (retired
spectral-locality metric), and NFR-021 hashed-identity handling exactly as
`qa/rr-study/callsign_recurrence_proxy.py` already does it (SHA-256 on extraction, no real callsign
in VCS).

---

## §7. Scope and compliance

- Docs-only. No `src/`, no `native/`, no rebuild, no push, no merge, no `pre_merge_check.py`
  (HK-011, HK-014, HK-010, HK-006).
- HK-015: written for QA. The Developer task in §5.2 is QA's to author as a `dev-tasks/*.md` if and
  when the Captain authorises it — I have specified the *constraints*, not the procedure.
- HK-018: `GAP-CENSUS-A` and `G2A-REMEASURE-A` results, the ledger, arm #2's spec, the 15:50Z
  amendment, the 140 Hz blocker memo, the 2026-08-04 callsign-recurrence observation and the on-disk
  artefact dumps were all opened before this ruling was written.
- Prediction scoring: §1. Both wrong, on the record.
