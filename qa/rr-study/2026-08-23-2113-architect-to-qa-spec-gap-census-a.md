# GAP-CENSUS-A — an additive attribution of the D-001 gap, and the school of small fish

**Architect → QA.** Drafted 2026-08-23 21:13Z (`date -u`, HK-017). Captain-directed.

**Status: pre-registration, with a MAJOR disclosure — see §0.1. No `src/` change, no rebuild,
no Developer session, no capture run. Pure census against data already on disk.**

---

## §0. Disclosure

### 0.1 🔴 THE ARCHITECT HAS ALREADY RUN THIS AND IS DE-BLINDED. PREDICTION SCORING IS SUSPENDED.

The Captain asked, in conversation, where all the small improvements land if added together. I
answered by measuring rather than quoting, and in doing so I computed **every headline number
this arm would gate on.** Those numbers are in §0.2, in full.

**Consequences, applied automatically:**

- **Architect prediction scoring is SUSPENDED for this arm.** No prediction section exists below
  and none may be added later. This follows the X1/X2 precedent (2026-08-10 scoping run).
- **My figures are EXPLORATORY. No ROW. They may not be cited as a result** in any report,
  board entry, issue comment, or ruling. They exist to size the instrument and to be
  *contradicted* by QA's independent derivation.
- **QA derives everything independently from the corpus**, not by re-running my one-liners.
  Where QA's figure disagrees with mine, **QA's is the result and mine is the error** — and the
  disagreement itself must be reported, not reconciled away.

### 0.2 What I measured, exploratory, on `artefacts/20260803_live_run_1713/`

Population: raw distinct `(timestamp, message)` keys from both legs' `ALL.TXT`, **no** hash or
band exclusions applied. ours 64,417 · theirs 43,423 · both 24,729 · **theirs-only 18,694** ⇒
**D-001 = 43.05 %**.

Four-way partition of the 18,694, exhaustive and additive by construction:

| bucket | definition | count | observed | null | excess | pp of D-001 |
|---|---|---|---|---|---|---|
| **A** | reference decode below `f_min = 200 Hz` | 1,154 | — | n/a | 1,154 | **2.66** |
| **B1** | an ours-decode within 4 Hz, same cycle, **our text carries `<...>`** | 754 | 754 | 61 | **693** | **1.60** |
| **B2** | an ours-decode within 4 Hz, same cycle, text differs otherwise | 1,133 | 1,133 | 793 | **340** | **0.78** |
| **C** | no ours-decode within 4 Hz — **genuine DSP miss** | 15,653 | — | — | — | **≈ 38.01** |

Supporting figures: our decodes below 200 Hz = **0** (`f_min = 200.0f`, `ft8_shim.c:1278`,
`:1640`). Either leg at or above 3000 Hz = **0**. Our `<...>` rate **6.75 %**, reference
**6.61 %**. Max decodes in any one cycle = **30** against `K_MAX_DECODED` 340/540.
Miss rate `[200,250)` = **19.9 %** against a `[700,3000)` baseline of **38.3 %**.

### 0.3 ⚠️ The correction I made to my own answer, disclosed because it is the whole lesson

My first pass reported B1+B2 as **4.35 pp** by counting co-located decodes directly. **That was
wrong by roughly a factor of two.** Our decode density is ~14 per cycle over 2,800 Hz, so an
8 Hz matching window catches a meaningful number of *accidental* neighbours.

A circular-shift null (our frequencies rotated within the band, five offsets) returns a mean of
**854 accidental co-locations**, against 1,887 observed ⇒ true excess **1,033**, i.e. **2.38 pp,
not 4.35 pp.** The null splits very unevenly: B1's null is **61** (only 6.75 % of our decodes
carry `<`, so accidental hash-matches are rare) while B2's is **793** — **roughly 70 % of
bucket B2 as I first counted it was noise.**

🔴 **This is why the arm is pre-registered rather than banked.** The null is not a refinement;
it is the difference between a defensible number and a wrong one. **Bucket B is meaningless
without it**, and §5 makes it mandatory.

⚠️ My five-offset null has a wide spread (658–1053). It is a sizing estimate, **not** an
adequate null. §5.2 specifies the real one.

### 0.4 Running order — this arm is FIRST

Four arms are now specced and unrun. **Run them in this order unless the Captain directs
otherwise:**

| # | arm | why here |
|---|---|---|
| **1** | **`GAP-CENSUS-A` (this one)** | Cheapest, and it defines the partition every other arm's result is quoted against. Its bucket C is the population `OSD-FA-A` is really asking about. |
| 2 | `G2A-REMEASURE-A` | Depends on this arm's bucket definitions and its null construction (§5.2), which it reuses verbatim. |
| 3 | G2(b) `140 Hz` rung | Independent; unblocked by the 2026-08-23 withdrawal memo. May run in parallel — different harness, different corpus. |
| 4 | `OSD-FA-A` | The DSP-side arm. Independent of all three, sequenced last because the ledger puts its subject in the smaller half. |

**1 and 2 are strictly ordered. 3 may run at any time. 4 is independent.**

---

## §1. The question

The programme has spent months on D-001 as a single large defect. **It has never built an
additive attribution of the gap.** `B_std` (+5.70 pp, band), `F_std` (+17.22 pp, crowding) and
the quantisation floor (≥3.16 pp) are **contrasts** — between bands, between density regimes,
against a lattice. They are not shares of the gap, they cannot be summed, and nobody has summed
them.

This arm builds the thing that can be summed, and answers one decision:

> **How much of the measured gap is recoverable WITHOUT any decoding improvement — by opening
> the search band and by fixing message text — and is that share large enough to be funded
> ahead of the next DSP arm?**

The Captain's framing, which this arm adopts: **we have been chasing one big fish and may have
walked past a school of small ones.**

---

## §2. Population

**`artefacts/20260803_live_run_1713/`** — the D-001 replication corpus, confirmed in
`qa/ARTEFACT_INVENTORY.md:38`, flagged **"DO NOT PROPOSE A CAPTURE RUN FOR D-001."** Both legs
on one verified audio path (median |r| = 0.987 over 8 WAV pairs).

🔴 **QA defines the canonical population, not me.** My §0.2 figures use raw distinct
`(ts, message)` keys with no exclusions and produce D-001 = 43.05 %, against the 42.2 % on
record from the 2026-08-05 reciprocal pass (a different, filtered basis). **ROW 0a below requires
QA to state its population definition explicitly, reproduce a committed baseline where one
exists, and report the reconciliation.** Do not adopt my basis by default.

⚠️ **Replicate on the three weekend corpora** (`20260808…-8080` 20 m, `…-1154-8080-17m`,
`…-0155-8080-80m`) as a secondary, reported alongside. A one-corpus census is a fact about one
corpus.

### 2.1 Carried hazards

1. **Sort at construction** everywhere a set is built or a sample drawn — hash-randomised set
   iteration silently breaks seeded determinism.
2. **Check what any reused helper's `limit=` does** before trusting it; it truncates in file
   order, it does not sample.
3. **Report CLUSTER counts (cycles), never bare row counts** (HK-021(i)).

### 2.2 NFR-021

Both legs carry **real off-air callsigns**. Message text may be held in memory to build match
keys and to test for `<`; it must **never** be printed, logged, or written to any output file.
**Counts only.** `git check-ignore -v` every artefact before any commit.

---

## §3. ROW 0 — preconditions, strict order

| row | check | bar | consequence |
|---|---|---|---|
| **0a** | Population definition stated; committed baseline reproduced where one exists; the 43.05 % / 42.2 % basis difference reconciled | exact reproduction of whichever baseline QA binds to | **VOID.** An unstated population makes every share below unreadable. |
| **0b** | Partition is exhaustive and mutually exclusive: A+B1+B2+C == theirs-only, asserted in code | exact equality | **VOID.** The whole design rests on additivity. |
| **0c** | Our leg produces **zero** decodes below `f_min` | `n == 0` | **VOID bucket A only.** A non-zero count means `f_min` is not what the source says and A is not a pure aperture census. |
| **0d** | Determinism: two independent full runs, result JSON **mechanically diffed** | byte-identical | **VOID.** Diffed, not asserted. |
| **0e** | Null adequacy (see §5.2): null estimator's own 95 % half-width | ≤ **0.25 pp** | **Bucket B reported as UNRESOLVED**, A and C unaffected. Routes to a row; does not void. |
| **0f** | Sub-200 Hz reference decodes are real signal, not reference artefact — confirmed against the **raw WAV spectrum**, not against either decoder | median in-band power in `[140,200)` measurably above the noise floor | **Bucket A reported as UNCONFIRMED.** Routes to a row. |

### 3.1 Why ROW 0f exists (HK-026)

Bucket A counts decodes **we have no aperture for**. Establishing that they are real signal
cannot be done with our own decoder — it is exactly an instrument bounding its own blind spot.
The reference decoder is a wider aperture there and is the enumerating instrument, but it may
not also be the *confirming* one. **The raw WAV spectrum is the approved bypass** and the
existing measurement (`[140,200)` at **−21.5 dB** relative to `[500,3000)`; `[100,140)` at
−41.7 dB; `[3000,3030)` at −42.9 dB) is the model.

### 3.2 What ROW 0b cannot detect (HK-022)

If the bucket predicates are computed from one shared match structure, a defect in that
structure keeps the partition exhaustive while mis-assigning every row. **Mitigation, mandatory:
compute bucket C independently** (count theirs-only keys with no ours-decode in the cycle at
all, by a separate code path) and assert it agrees with the residual. Report both.

---

## §4. Part A (GATED) — the aperture census

**Statistic:** `S_A` = theirs-only decodes below `f_min`, as a share of all theirs-only decodes,
and its pp-of-D-001 equivalent.

This bucket needs **no null** — our leg produces literally zero decodes below `f_min`, so every
sub-200 Hz reference decode is a miss by construction and accidental matching is impossible.
It is a census, not an estimate; report the exact count and no confidence interval on the count
itself.

| row | condition | consequence |
|---|---|---|
| **A1** | `S_A ≥ 0.04` **and** ROW 0f confirms | **The passband is a funded item.** The G2(b) ladder — specced, five Architect reviews, never armed — is recommended for arming ahead of the next DSP arm. |
| **A2** | `S_A < 0.04` | Passband is real but marginal; report and do not prioritise. |
| **A3** | ROW 0f unconfirmed | `S_A` reported as an upper bound only; no funding consequence. |

⚠️ **`S_A` is a CEILING on recovery, never a delivery.** It assumes we would decode every one of
those signals through a chain 21.5 dB down. The burned-corpus `[140,200)` yield was **2.71 %
against a 1.00 % bar** — real but partial. **Report `S_A` as "the population that exists", and
state in the same sentence that the realised fraction is what G2(b) was built to measure.**

🛑 **The upper edge is not in scope.** Both legs produce zero at or above 3000 Hz, the raw WAV
puts `[3000,3030)` at −42.9 dB, and **"zero gains in `[3000,3030)`" is on the permanently-uncitable
list.** Do not sweep upward, do not re-measure it, do not mention it as a limitation.

---

## §5. Part B (GATED) — the text-recovery census, null-corrected

### 5.1 Statistic

For each theirs-only decode at `(ts, hz)` with `hz ≥ f_min`, test whether any ours-decode in the
same cycle falls within **±4.0 Hz** (`FREQ_TOLERANCE_HZ`, the matcher's own tolerance — pinned,
not re-derived). Split hits by whether our text contains an unresolved-hash marker.

**`S_B` = (observed co-locations − null expectation) / theirs-only**, reported separately for
B1 (hash) and B2 (other), signed, cluster-bootstrapped by cycle.

### 5.2 🔴 The null is mandatory and is the arm's real work

**A raw co-location count is not a result.** At ~14 ours-decodes per cycle over 2,800 Hz, an
8 Hz window catches accidental neighbours at a rate comparable to the effect.

Required construction:
- **Circular frequency shift** of our decodes within `[f_min, 3000)`, preserving each cycle's
  own decode count and the reference's positions.
- **≥ 200 offsets**, drawn on a seeded, sorted-at-construction grid — not the five I used.
- Report the null's **own** distribution, its mean, and its 95 % half-width (ROW 0e gates on it).
- Compute the null **separately for B1 and B2** — their nulls differ by more than an order of
  magnitude (mine: 61 vs 793) because the hash-carrying share of our decodes is small.

⚠️ A circular shift preserves marginal density but not fine structure (signals cluster in the
band). **Report a second null of a different construction** — cycle-label permutation, matching
each theirs-only decode against a *different* cycle's ours-decodes — and report both. If the two
nulls disagree by more than the ROW 0e bar, say so and read B as unresolved.

### 5.3 Gate

| row | condition | consequence |
|---|---|---|
| **B1** | `S_B` CI excludes zero and B1's excess exceeds B2's | **Text recovery is dominated by hash resolution.** G2(a) (256→4096, merged `9500e03`) targets it directly and has **never been re-measured** — a post-G2(a) re-measure is recommended as the cheapest item on the board. |
| **B2** | `S_B` CI excludes zero, B2's excess dominates | Text recovery is **not** primarily hash — the T3 callsign-character population needs its own diagnosis before any fix is proposed. |
| **B3** | `S_B` CI includes zero, or ROW 0e fails | **Text recovery is not established.** Report the counts and the null; propose nothing. |

⚠️ **Our `<...>` rate on this corpus is 6.75 % against the reference's 6.61 %** — near parity,
unlike the 5.5 %-vs-1.7 % that motivated G2(a) on the 2026-08-08 leg. **Report this comparison
explicitly.** It is evidence that hash-table sizing may not be the whole of B1, and it must not
be omitted because it complicates the story.

---

## §6. Part C (DESCRIPTIVE — NOT GATED) — the residual

Report bucket C's size and its composition by SNR stratum, band, and per-cycle density, using
X1/X2's **pinned** L1 SNR edges `[-15, -10, -5, 2]` — never re-derived.

🛑 **No stratification of C by frequency separation to a neighbouring decode, in any form, under
any name.** That is the retired spectral-locality metric (`E_sep`, permanently uncitable, four
attempts, zero readings). **If this leg starts to look like one, refuse under HK-025 and
escalate.** This prohibition is the single most likely way for this arm to go wrong.

Report also, as diagnostics with no consequence: the max decodes per cycle against
`K_MAX_DECODED`, and the miss rate in `[200,250)` against the `[700,3000)` baseline.

---

## §7. The addition — the deliverable the programme has never had

Produce one table: every bucket, its count, its cluster count, its null where one applies, its
excess, and its pp-of-D-001 — **and the sum**, with the additive and non-additive items
explicitly separated.

**Mechanically enforced:** A + B1 + B2 + C must equal the whole gap (ROW 0b). Anything that
cannot be placed in exactly one bucket — `B_std`, `F_std`, the quantisation floor, the
extraction ceiling, limb 2's bound — **goes in a separate table labelled NOT ADDITIVE, with the
reason.** A contrast is not a share. `G(3)`'s ~7 pp is a ceiling *inside* bucket C, not an
increment beside it.

---

## §8. What this arm does NOT do

- 🛑 **No spectral-locality metric, under any name** (§6).
- 🛑 **No upper-passband work** (§4).
- 🛑 **Does not arm G2(b)** — A1 recommends, it does not authorise. That is a Captain decision.
- 🛑 **Does not propose a hash-table change** — B1 recommends a *re-measure*, not an edit.
- 🛑 **Does not touch `src/`, does not rebuild, does not push, does not merge** (HK-011, HK-014, HK-010).
- **Makes no claim about the reference decoder's behaviour** beyond enumerating what it produced.
- **Does not subsume `OSD-FA-A`**, which is specced and unrun and addresses a different question
  (whether our exclusive decodes are false). This arm partitions *their* decodes we missed;
  `OSD-FA-A` audits *ours* they didn't make.

---

## §9. Reporting and stopping

1. ROW 0 first, in strict order, stopping at the scope each row names.
2. State the population definition before any share.
3. **Never report a co-location count without its null in the same sentence.**
4. Report cluster counts throughout.
5. Disclose every correction in full; a disclosed correction is a result, a silent one voids the arm.
6. **Where QA's figure disagrees with §0.2, QA's is the result.** Report the disagreement.
7. Stop at the gate. No push, no merge, no `pre_merge_check.py`.
8. 🔴 **HK-025 stands: QA may refuse this spec without my agreement.** Given §0.1, the obvious
   failure mode is a gate shaped to reproduce numbers I have already seen. **If any row cannot
   change a verdict, name it, evaluate both branches, and stop — no partial run.**
