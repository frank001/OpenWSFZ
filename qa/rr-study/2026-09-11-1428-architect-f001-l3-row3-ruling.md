# `F-001` L3 — ruling on the ROW 3 escalation: **arm CLOSED at ROW 3**, the occupancy null was mis-specified, and the ROW 0b refusal is upheld

**Architect, 2026-09-11 14:28Z** (`date -u`, HK-017). Branch `arch/f001-l3`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Rules on: QA's `qa/rr-study/2026-09-10-1814-qa-to-architect-f001-l3-own-hash-compare-result.md`
(QA branch `f001-l3-own-hash-compare-result`, `fadaf0a`), against the gate in
`2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md` §5 as changed by
Amendment 1 (same file) and Amendment 2
(`2026-09-08-2031-architect-to-qa-f001-l3-amendment-2-corpus-substitution-and-row0d-withdrawal.md`,
`4fbaffe`; PO ruling on the scalar `97c57ca`).

⚠️ Amendment 2's commits were rebased onto `origin/main` today, before this ruling was written.
Their old SHAs (`20a8b72`, `8cbee2d`, `d61b2fd`) are now `4fbaffe`, `2121d23`, `97c57ca`. The
content is unchanged.

---

## 1. Verdict

**ROW 3 stands. It is this arm's final verdict, and the arm is closed.** I am not re-reading it as
ROW 2, and §2's explanation of why it fired does not turn it into one. Re-reading a gate after the
result with a better metric is a standing prohibition.

I recomputed these independently from the run's own JSON
(`artefacts/2026-09-10-f001-l3-live-measurement/`, in QA's worktree), not from the report:

- **ROW 0e.** 5,222 cycles on both legs, cycle stamps aligned, **0 cycles with any decode
  difference**, 65,798 decodes on each leg. Matches.
- **0d′** `3,610 == 3,610` and **0d″** `1,529 == 1,529`. Both match.
- **Binaries.** Subject is shim `20260050` (`6b2e16a6991a…`), control is shim `20260049`
  (`ce02c7ba10e2…`). Both match Amendment 2 §2.1.
- **Gate figures.** `U_total = 1,585`, `U[0] = 24`, `U_clean = 1,561`, `U149 = 0`,
  `occ_obs = 948`, `occ_exp = 1,297.9`, `occ_sd = 29.8`, `z = −11.75`. All match.

**Consequence, per spec §8 and Amendment 2 §5, unchanged:** this arm sized L3's **COST ONLY**.
Efficacy is still structurally unmeasurable because every corpus we hold has zero `Tx` lines. L3 is
not built, and this ruling authorises no `src/` or `native/` work (HK-011).

## 2. Why ROW 3 fired: the occupancy null counts the wrong unit (my error)

**The defect.** Spec §4 modelled the unresolved lookups as independent draws spread uniformly
across the 4,096 codes (Poisson with `λ = U/4096`). They are not independent. The hash is a fixed
function of the callsign, so every time one unresolved station is referenced again, the lookup
lands on **the same code**. The lookups cluster by source. So even if the hash is perfectly
uniform, a corpus where stations repeat will occupy **fewer** codes than the lookup-level null
expects, and the check fires.

This is the same class of error as T2a (2026-08-08). There, `r` was a constant per station, so
decodes were not independent units. That lesson has been on the board since August, and I did not
apply it here.

**The evidence (exploratory, not pre-registered, no row).** The same run carries three other
per-code tables. They come from the same corpus, the same hash, the same code index
(`tls_h12_code`) and the same emission site. None of them has anything to do with L3. I ran the
identical occupancy test on them:

| table (shim `20260050`, same run) | lookups | `occ_obs` | `occ_exp` | `z` | max on one code | lookups per source if the hash is uniform |
|---|---:|---:|---:|---:|---:|---:|
| **unresolved (L3)** | 1,561 | 948 | 1,297.9 | **−11.75** | 16 | 1.45 |
| resolved: displaying | 3,610 | 1,393 | 2,399.1 | **−31.92** | 265 | 2.12 |
| resolved: ambiguous | 1,529 | 574 | 1,276.0 | **−23.69** | 230 | 2.47 |
| resolved: divergent | 1,079 | 502 | 948.6 | **−16.54** | 91 | 2.01 |

All four tables fail the same null, and the three control tables fail it **harder** than the L3
table does. A displaying count of 265 on one code is one station being resolved 265 times. Nobody
would read that as a flaw in the hash. The L3 table is actually the **least** clustered of the four.

**Reading it as HK-021(k).** If the hash is uniform and stations repeat, the occupancy clause fires.
If the hash is non-uniform, it also fires. The same row fires either way, so the clause could not
answer the question it was put to: can our code's rate be derived from the base rate? On real
traffic, ROW 2 could never have fired. My §4 z-table showed the check was *sensitive*. It never
showed the check could *pass* on correct data.

This was checkable at drafting time. The spec's own §0.1 table lists eight artefacts that already
carried `h12_by_code`. One occupancy computation on any of them would have shown the clause fails
on data with nothing wrong with it (HK-018). The HK-021 sibling this adds is recorded in §7.

**What the occupancy figure does say:** nothing about whether the hash is uniform. By inference, not
measurement, it is consistent with about 1,080 distinct unresolved sources hashed uniformly,
averaging ~1.45 lookups each (`948 = 4095·(1 − e^(−D/4095))` gives `D ≈ 1,078`).

**Predictions scored (spec §7).** `U149 ∈ {0, 1}`: **HIT**. The row call (ROW 2 at 0.65): **MISS**,
and I had put 0.65 on a row that was effectively unreachable. The `U_total` range is not scored,
per Amendment 1 A1.4 and Amendment 2 §5. This is my third consecutive prediction miss of some kind:
the `FP-FLOOR-LIVE-2` Part B row reversal, the `D003-LIVE` rate outside its range, and now this row
call.

## 3. QA's two candidate mechanisms: both mean sources repeat, and neither bears on uniformity

QA's §3 names two explanations: the hash table filling up (saturation), and ordinary repeat
traffic. **They are both reasons a source generates more than one lookup.** They differ in *why*
stations repeat, not in whether the hash is uniform. So telling them apart would not answer
anything ROW 3 raised. **I am not commissioning a disambiguation arm.**

**The saturation message is now received.** The board's 2026-09-09 00:04Z entry could not reach me
twice, and QA's report was carrying it. Here is what it means for L3:

- **The table filling up is a standing fact, not a new finding.** It holds 4,096 slots and is never
  re-initialised. `hash_table_add` rejects only a genuinely new callsign, and only once the table is
  full (`ft8_shim.c:771`, after the D-012 reordering). So this replay's final
  `hash_table_reject_count = 65,034` means its table did fill.
- **After that point**, a station whose full callsign we *do* hear can no longer be stored, so every
  later hashed reference to it stays unresolved. **L3's cost therefore grows with session length.**
  The unresolved population L3 would act on keeps growing once the table is full. This is a
  property of any L3 design, not of this run.
- **A descriptive signal, confounded and not attributable:** `<...>` renderings (all hash widths)
  per 100 decodes run 3.9 in the first eighth of the window and 6.3–8.1 in the last four eighths.
  The overnight band change falls in between, so this cannot be attributed to saturation.

## 4. Disposition: the arm is closed, with no follow-up arm

The same both-branch test applied to commissioning more work:

- **A source-level follow-up finds the hash uniform.** The cost is small, but efficacy is still
  unmeasurable, so L3 is not licensed.
- **It finds the hash non-uniform.** L3 is not licensed.

**Both branches reach the same outcome, so a follow-up would be decorative for the L3 decision.**

**Only efficacy evidence could move L3:** a corpus in which stations actually call us. We hold none.
I am **not** proposing a capture run. Whether L3 is wanted enough to go and get that evidence is the
PO's decision, and it is outside this arm.

## 5. ROW 0b: QA's HK-025 refusal is UPHELD, and it leaves the L3 table unreconciled

**The refusal is correct.** Evaluate both branches. If the counter is correct, `1,585 < 4,199` and
the row fires. If the counter under-counts, the row also fires. The same row fires either way, so
it is decorative, and refusing it was right. The comparator counts `<...>` from all hash widths.
The 22-bit path (`message.c:782`, standard Type-1/2 messages) renders the same brackets. I wrote
ROW 0b in spec §5, then promoted it to "load-bearing" in Amendment 2 §4.3 without re-reading its
comparator against code I had cited myself.

**The consequence, which the result file does not yet state.** Three things have now happened:

- ROW 0d was withdrawn (Amendment 2 §4).
- ROW 0b has been refused.
- The PO declined the scalar (2026-09-08).

⇒ **the L3 table's accumulation has no independent reconciliation anywhere in this arm.** Amendment
2 §4.3 said ROW 0b was the *only* check reaching the L3 table from an independent direction. The
rows that did clear do not cover it:

- **0d′ and 0d″** exercise the sibling tables and the sibling predicate.
- **0e** shows the added branch does not change decode output. It does not show the new table
  counts correctly.
- **0c** shows no code was masked out of range.

**What I checked instead (exploratory).** Two gross mis-indexing errors would themselves produce low
occupancy, and both are excluded:

- Indexing by the 10-bit code instead of the 12-bit one would put every occupied code below 1024.
  In fact 680 of the 948 occupied codes are ≥1024.
- A bit-shift would empty three of the four residues mod 4. All four are populated (208–263 codes
  each).

This does **not** prove the table accumulates correctly. It does not need to, because the closure in
§4 depends on no figure from this table.

**ROW 0b is WITHDRAWN**, in the same way as 0d: not renumbered, not repaired in place, since the arm
will not run again. If L3 is ever re-registered, that pre-registration must bring a real
reconciliation. The options:

- A comparator restricted to `i3 = 4` decodes, which needs `i3` exported per decode. The decode
  JSON does not carry it today.
- The `ft8_get_h12_unresolved_count()` scalar.

The PO's 2026-09-08 "we'll evaluate later" is still open for that future arm. For this arm it no
longer matters.

## 6. ROW 0f: accepted as disclosed

Two independent implementations of `message.c`'s formula agree on `n12 = 149`: spec §2 and
`common_arm1.py`. The remaining risk is that the DLL computes something different from its own
source. That would matter only through row order: ROW 1 is evaluated before ROW 3, so a wrongly
derived own-code landing on a hot code could have changed the verdict. 31 of 4,095 codes carry ≥5
unresolved lookups. Since the arm closes and no `U149` figure is cited (§7), 0f carries no weight in
this ruling. **QA need not complete it.** QA's §5 recommendation 3 (where to pick it up) stands for
any future arm.

## 7. Citation limits, and the new HK-021 sibling

**Citable, descriptive only**, and only together with the corpus, binary and caveats. Corpus
`FP-FLOOR-LIVE-2` `[260908_193645, 260909_172200)`, 5,222 cycles (~21.8 h), 20m, shim `20260050`
`6b2e16a6…`:

- `U_total = 1,585`, `U[0] = 24`, `U_clean = 1,561`, 948 occupied codes, `U149 = 0`.
- Always carrying three caveats: the population is gated (A1.1), it depends on session length (§3),
  and the table is unreconciled (§5).

🛑 **Never cite:**

- `U149 = 0` as "L3's exposure is zero". The expectation is ~0.4 events, so absence proves nothing
  (HK-021(j)).
- `E_uniform = 0.381` as L3's false-fire exposure. ROW 3 withholds that derivation, and the
  population is non-stationary (§3).
- `z = −11.75` as evidence the hash is non-uniform, or that lookups concentrate on our code (§2).
- `U_clean` as a rate per hour or per session. It grows once the table fills (§3).
- "ROW 0 clears in full" without the §5 gap.
- `4,199` as a 12-bit rendering count. It counts all hash widths.

**One design note for any future L3 pre-registration (inference, not a finding).** Unresolved
lookups repeat per source, up to 16 on one code here. So an L3 false fire would most likely come
**in bursts from one colliding station**, not as isolated events. Containment would then need to
work per source, not per decode.

**New HK-021 sibling (z), folded into `hk021-pre-registered-checks-must-be-mechanical.md`.** A null
model must be stated in units that are actually independent. Before it gates anything, show that
the check **passes** on a population where the null is known to hold. A sibling table from the same
instrument is the cheapest such population. §4's z-table showed this check was sensitive, but
sensitivity alone is not enough.

## 8. What QA does

1. **Correct the result file in place, striking each original where it lives (HK-022).** Only
   wording changes; no number changes:
   1. **§2.1, lines 65–66.** Strike *"0c/0d′/0d″/0e all independently confirm the 12-bit table
      itself is internally consistent and non-perturbing"*. Replace it with: none of these rows
      reconciles the L3 table (0d′/0d″ exercise the sibling tables; 0e shows non-perturbation only).
      This ruling §5 is the reference.
   2. **Headline and §2's "ROW 0 clears in full".** Add that the L3 table's accumulation has no
      independent reconciliation. Amendment 2 §4.6 required this in the report's own validity
      statement. QA could not apply it without the amendment in hand, and that is my fault: it was
      never pushed.
   3. **Lines 5–10 (the note that Amendment 2 was reconstructed from the board).** Keep it, and add
      that the amendment is now at `arch/f001-l3` `4fbaffe`. (For next time: any local branch can
      be read from any worktree with `git show <branch>:<path>`.)
   4. **§5 recommendation 4.** Mark the saturation message as delivered and answered by this ruling
      §3.
2. **No re-run, no further analysis, no disambiguation arm.**
3. **Remote.** Pushing QA's result branch needs the Captain's go-ahead (HK-033). `arch/f001-l3`
   holds Amendment 2, the PO scalar ruling and this ruling, and QA may take it per HK-014. One PR
   carrying both branches is the simplest route. Merging needs the Captain's sign-off (HK-010).
