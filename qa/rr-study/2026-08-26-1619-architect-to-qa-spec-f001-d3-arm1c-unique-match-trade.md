# SPEC -- `F-001 D3` ARM 1C: WHAT WOULD A UNIQUE-MATCH RULE BUY, AND WHAT WOULD IT COST?

**Architect -> QA.** 2026-08-26 16:19Z (`date -u`, HK-017). Repo `main` @ `5307cf7`.

Pure re-analysis of dumps already on disk. **No `src/` change, no `native/` change, no rebuild, no
replay, no capture, no Developer session** (HK-011). Docs-only on my side, committed locally, nothing
pushed (HK-014). **Runnable by QA now; minutes, not hours.**

Parent ruling: `qa/rr-study/2026-08-26-1504-architect-to-qa-ruling-f001-d3-arm1b.md` (read its Sec.4
first -- the chain-multiplicity table is why this arm exists). Ordered by the PO, 2026-08-26, in
preference to drafting arm 2 or a remedy blind.

---

## 0. Read this first: what this arm is, and the rule it would otherwise break

**0.1 The PO's question, in one line.** *Is a 12-bit naming remedy worth a pre-registration at all?*
The remedy under discussion is a **unique-match rule**: on the truncated (12-bit) lookup path, name
the station only if **exactly one** resident entry matches the query's 12-bit code; otherwise render
`<...>`. It trades resolution for correctness, and the size of that trade has never been measured.

**0.2 🛑 HK-021(p) would block this arm if it claimed a treatment effect. It does not, and here is the
exact scope line.** (p)'s corollary is absolute: *if the binary that isolates the treatment does not
exist, the arm is blocked at DRAFTING time.* **No unique-match binary exists and none is authorised.**
So this arm does **not** measure a treatment. It measures a property of **the build we already ran**:

> Of the names the REAL build printed on the 12-bit path, **how many were AMBIGUOUS at the moment it
> printed them** -- i.e. how many had a second resident entry sharing the query's 12-bit code?

That is a fact about today's table, not a simulation of a hypothetical one. The unique-match rule is
then an **arithmetic re-labelling** of that fact, not a measured intervention. 🛑 **Consequently no
row in this spec may be written, and no line of QA's report may be written, as "the fixed build
would...". The verdict is always "of the names this build printed, N were ambiguous."** If the PO
later wants what a fixed build actually does, that is a different arm and (p) blocks it until a
Developer session produces the binary.

**0.3 The outcome is REAL; only the STRATIFIER is simulated.** Agree/disagree comes from ARM 1B's
pairing against the WSJT-X reference -- real decoder output, no proxy. Multiplicity comes from the
replayed table. So HK-021(h) governs directly:

> **Non-differential measurement error in a stratifying variable biases a contrast toward zero.**

⇒ 🔴 **Every rescue/loss figure in this arm is quoted as "at least X", never as "X"**, and 🛑 **no
de-attenuated or error-corrected version may be computed or published** ((h) discipline 2). The floor
reading is an inference; the only measured thing is that no finer instrument exists in this corpus.
⚠️ **That protection holds only if the error is NON-differential, which is not assumed -- ROW 0d
measures it and VOIDs the arm if it is differential.**

**0.4 What I measured while drafting, and what I refused to.** I measured the **population**: how many
of ARM 1B's 243 paired decodes survive the per-query fidelity filter (**206, 84.8%**, over **105**
distinct callsigns, top-5 = 22.3%), the two gate denominators (**56** and **49**), and the share of
queries issued after the table froze (**144/243, 59.3%**). 🛑 **I did NOT cross multiplicity with the
agree/disagree outcome. That 2x2 IS the answer and it does not exist anywhere on my side.** Probe:
`artefacts/2026-08-26-arm1b-ruling-probe/arm1c_exposure.py` (gitignored). Read the code if useful;
there is no result in it beyond the exposure printed above.

⚠️ **One drafting fact QA should know going in:** per-query simulator fidelity on this 243-decode
subpopulation is **84.8%**, materially below the corpus-wide **92.5%** (ARM 1B ROW 0g). The
both-resolved population is harder for the replay than the corpus at large. That is exactly why ROW 0d
exists and why it is load-bearing rather than decorative.

---

## 1. Question, and the only consequences this arm can have

> **Of the wrong names this build printed on the 12-bit path, how many were ambiguous at print time
> (so a unique-match rule would have suppressed them) -- and how many of the RIGHT names would the
> same rule have suppressed?**

| outcome | consequence |
|---|---|
| **C1 and D2** | the rule reaches a majority of mis-resolved callsigns and costs a minority of correct ones ⇒ **a remedy earns a pre-registered Developer arm**, which is itself blocked at drafting until the binary exists (HK-021(p)) |
| **C2, or D1** | the rule does not reach the wrong names, or costs the majority of right ones ⇒ **no remedy build is proposed.** `DEFECT-twelve-bit-hash-misresolution.md` stands accepted-and-marked and the PO decides product policy on it |
| anything else | **INDETERMINATE**, declared before the run. The descriptive tables go to the PO and no engineering consequence follows either way |

🛑 **This arm authorises no `src/` change, no fix, no policy, and no Developer session, under every
outcome including C1+D2.**

---

## 2. Inputs, pinned -- never re-derived

| pin | value | source |
|---|---|---|
| ours | `artefacts/2026-08-25-g2a-remeasure-a/L2_run1_decodes.json` | sha256 + `shim_version` + `n_decodes`=71,600 via `common_g2a` |
| reference | `artefacts/20260803_live_run_1713/wsjt-x/ALL.TXT` | `gc.parse_all_txt`, 43,423 rows |
| `HASH_TABLE_SIZE` | 4,096 | `ft8_shim.c:631` |
| Part B leg | 32,768 | ARM 1 `SZ8` |

**Reuse, do not re-implement** (HK-018): `common_arm1b.{slot, build_theirs_index, best_match, T12,
cp_lower_one_sided, cp_upper_one_sided}`, `run_arm1b.{build_part_a, apply_row0d, callsign_flags}`,
`common_arm1.{n22_of, n12_of, SimTable}`. ROW 0c asserts the reuse by object identity.

---

## 3. Method

**3.1 The multiplicity predicate. Ship it verbatim (HK-021(r)); the prose is a gloss on the code.**

```python
class T12C(common_arm1b.T12):
    """T12 plus the chain-multiplicity count. matches12 walks the SAME probe
    chain as lookup12 under the SAME break-on-EMPTY rule, and counts every
    OCCUPIED entry whose stored n22 truncates to the query's n12. lookup12
    returns the FIRST of exactly these; multiplicity >= 2 is the definition
    of an AMBIGUOUS query."""

    def matches12(self, n12):
        h10 = (n12 >> 2) & 0x3FF
        idx = (h10 * 23) % self.n
        found = 0
        for _ in range(self.n):
            st = self.state[idx]
            if st == common_arm1.EMPTY:
                break
            if st == common_arm1.OCCUPIED and (self.hash[idx] >> 10) == n12:
                found += 1
            idx = (idx + 1) % self.n
        return found
```

A query is **AMBIGUOUS** iff `matches12(n12) >= 2`, **UNAMBIGUOUS** iff `== 1`. `== 0` cannot occur for
a query the real build resolved and is a ROW 0c failure if it does.

**3.2 The per-query fidelity filter.** Replay the insert stream into a fresh `T12C(4096)` exactly as
`common_arm1b.run_12bit_leg` does, keyed `(ts, freq_hz, message_norm)`. A paired decode is
**VERIFIED** iff the replayed table's `lookup12` returns **the same name the real decoder printed**.
Only VERIFIED decodes enter the gates. **This is the whole proxy-control of the arm:** on a verified
query the replay demonstrably stands where the real decoder stood, so its multiplicity is the real
table's multiplicity.

**3.3 The 2x2.** Cross the REAL outcome (ARM 1B's `disagree` flag, reference-derived) with the
SIMULATED stratifier (ambiguous / unambiguous), over VERIFIED decodes only. Report the full 2x2 with
exact counts. Decode counts are point counts and **never carry a CI** (HK-021(i)).

**3.4 Units for the gates (HK-021(i)) -- and both definitions are deliberately CONSERVATIVE AGAINST
THE REMEDY.**

- **ROW C unit** -- a callsign with **>= 1 VERIFIED DISAGREEING** decode. It is **`rescued`** iff
  **EVERY** one of its verified disagreeing decodes is AMBIGUOUS. *(ALL, not ANY: a callsign the rule
  only partly cleans does not count as a win.)*
- **ROW D unit** -- a callsign whose verified decodes **ALL AGREE**. It is **`lost`** iff **>= 1** of
  them is AMBIGUOUS. *(ANY, not ALL: one blanked correct name is a cost.)*

🔴 **State the asymmetry in the report.** Both definitions make the remedy look worse than a symmetric
reading would. A **C1+D2** result is therefore hard to fake and a **C2/D1** result is not an artefact
of a kind bar.

**3.5 CIs.** Clopper-Pearson, one-sided 95%, never a bootstrap (HK-021(n)/(o)); this metric can land
on a degenerate 0/n or n/n.

**3.6 NFR-021.** Counts, cycle timestamps, frequencies, `sha256[:6]` redactions. No real callsign and
no raw message text in `result.json`, the report or the log.

---

## 4. ROW 0 -- strict order, any FAIL VOIDs the arm, no partial run

| row | check | bar |
|---|---|---|
| 0a | input identity | `L2_run1` sha256 / `shim_version` / `n_decodes`=71,600 match `common_g2a`'s pins; reference parses to 43,423 rows |
| 0b | **population reproduction (load-bearing)** | ARM 1B's pairing reproduces **k=243 / n=115 / 92 disagreeing pairs** EXACTLY (it is the same code on the same input -- anything else means the reused helpers moved). Then VERIFIED survivors land in **[190, 220]** decodes over **[98, 112]** callsigns (drafting probe: 206 / 105). Outside ⇒ VOID |
| 0c | **predicate coherence (load-bearing)** | for **every** replayed type-4 query: `lookup12(n12) is None` **iff** `matches12(n12) == 0`, and `matches12 >= 1` wherever the real build resolved. Bar: **100%**, zero exceptions. This is the row that proves `matches12` walks the same chain `lookup12` does; a single exception ⇒ VOID |
| 0d | **differential-stratifier-error test (load-bearing -- HK-021(h) depends on it)** | compute per-query fidelity SEPARATELY on the disagreeing and agreeing subsets and report the **SIGNED** difference `fid(disagree) - fid(agree)`. Bar: **abs difference <= 15 pp** ⇒ error is non-differential enough for the floor reading to hold. **Beyond 15 pp ⇒ VOID.** ⚠️ **Two-sided BY DESIGN, and this is not an HK-021(l) violation: both signs corrupt, in opposite ways** -- a NEGATIVE difference means the filter preferentially drops wrong names (rescue over-stated), a POSITIVE one means it preferentially drops right names (cost over-stated). Report the sign and name which way it cuts |
| 0e | **determinism, OUT OF PROCESS** | re-run the whole arm in a **fresh process** under a **different `PYTHONHASHSEED`**; `result.json` must be **byte-identical**. 🔴 **This replaces ARM 1B's same-process determinism check, which could not see the hash-randomised-iteration hazard. My wording, my fix.** |
| 0f | **predicate-movement exhibit (HK-021(q))** | take one UNAMBIGUOUS verified query; inject a synthetic table entry sharing its `n12` on the same chain; assert `matches12` moves `1 -> 2` and the unit moves `unambiguous -> ambiguous`. Paste the worked example (redacted). A stratifier that cannot be made to move is not measuring anything |
| 0g | table-freeze exposure (stated, not gated) | report the share of gate queries issued AFTER the table froze (drafting probe: **144/243 = 59.3%**). ⚠️ Pre-registered so it cannot later be discovered and used to explain a result away |

**Under-power stop, declared now (HK-021(m)):** if either gate denominator falls **below 40** after
ROW 0d, that gate reports **UNDER-POWERED** with its exposure and returns no verdict. The other gate
still runs.

---

## 5. Gates -- two families, each mutually exclusive, each in strict order

**ROW C -- does the rule reach the wrong names?** `p_rescue` = `rescued` / (ROW C units).

| row | condition | consequence |
|---|---|---|
| **C1** | CP one-sided 95% **lower** bound on `p_rescue` **> 0.50** | the rule suppresses **at least** a majority of mis-resolved callsigns |
| **C2** | CP one-sided 95% **upper** bound **< 0.50** | it does not reach a majority. **Never write "it does not work"** (HK-021(j)) |
| **C3** | neither | INDETERMINATE |

**ROW D -- what does it cost?** `p_lost` = `lost` / (ROW D units).

| row | condition | consequence |
|---|---|---|
| **D1** | CP one-sided 95% **lower** bound on `p_lost` **> 0.50** | the rule blanks **at least** a majority of currently-correct callsigns |
| **D2** | CP one-sided 95% **upper** bound **< 0.50** | it costs a minority |
| **D3** | neither | INDETERMINATE |

**Resolution, stated while drafting (HK-021(m)), at the denominators the probe measured:**

| gate | n | fires the "majority" row at | fires the "minority" row at | INDETERMINATE band |
|---|---:|---|---|---|
| **C** | 56 | `rescued >= 35` (**62.5%**) | `rescued <= 21` (**37.5%**) | 22-34 (39.3%-60.7%) |
| **D** | 49 | `lost >= 31` (**63.3%**) | `lost <= 18` (**36.7%**) | 19-30 (38.8%-61.2%) |

🔴 **Say this plainly in the report: at these denominators the arm separates "clear majority" from
"clear minority" and NOTHING in a ~21-point band between them.** That is on the record before the run
and is not a reason to move a bar afterwards. It is enough to answer the PO's go/no-go and it is not
enough to size a remedy.

🔴 **Every rescue and loss figure is reported as a FLOOR ("at least X"), per HK-021(h)/Sec.0.3.**

**ROW E (ungated, descriptive, reported beside C and D):** the post-rule agreement rate among names
that SURVIVE the rule -- `unambiguous & agree` / (`unambiguous & agree` + `unambiguous & disagree`) --
with its CP interval, beside ARM 1B's measured 62.1% (151/243) baseline. **Descriptive only: it
conditions on surviving, which is selection on the stratifier, and it must never be quoted as a
correctness rate for a fixed build.**

---

## 6. Part B -- the arm-2 interaction, DESCRIPTIVE ONLY

Re-run the multiplicity distribution at **32,768** and report it beside 4,096 in one table (parent
ruling Sec.4: 50.9% -> 78.4% ambiguous). 🛑 **Not adjudicated and not gated. No real decoder output
exists at 32,768, so there is no outcome to cross it with** -- this is exposure for the PO's coupled
arm-2 decision, nothing more.

---

## 7. Contingencies, decided now rather than mid-run

- **A verified query with `matches12 == 1` whose name is WRONG.** Expected and important: it means the
  correct entry **was not resident** at query time, so the rule cannot help that decode. Count these
  separately and name them in the report -- they are the ceiling on any suppression-based remedy.
- **A callsign with both agreeing and disagreeing verified decodes.** It is a ROW C unit and is
  excluded from ROW D by construction (D requires ALL verified decodes to agree). Count them.
- **Fidelity filter drops a callsign entirely.** Out of both gates; counted and reported.
- **ROW 0d lands between 10 and 15 pp.** PASS, but the report must state the sign and which figure it
  inflates. (p): the maximum tolerated confound is written down, in the row's own units, above.
- **HK-021(p):** satisfied by SCOPE, not by a build -- see Sec.0.2. There is no A/B and no treatment
  binary, and no row claims one.

---

## 8. My predictions, recorded BLIND (Sec.0.4: the 2x2 does not exist on my side)

1. **C1 fires** -- moderate. Wrong names should concentrate in ambiguous queries by construction.
   ⚠️ **The mechanism that could sink it:** the table freezes at 4,096 of 16,320 distinct names seen,
   so on many queries the correct entry was never resident and the wrong name is a **unique** match --
   invisible to the rule. Contingency 1 measures exactly this.
2. **D1 also fires** -- moderate-to-high. 50.9% of all queries are ambiguous and the ROW D unit
   definition is ANY-based, which is the unforgiving direction.
3. **So the arm lands C1+D1: the rule works AND is expensive**, and the PO gets a genuine trade rather
   than a free win -- moderate. If that is the answer, the decision stops being technical and becomes
   a product call about whether a blanked name beats a wrong one.
4. **ROW E lands above 80%** -- low confidence, flagged as low. I have been wrong on this path's
   magnitudes twice today and this is the figure most exposed to selection.

---

## 9. Scope

Authorises **one QA run and one report.** No `src/`, no `native/`, no rebuild, no replay, no capture,
no Developer session, no push, no merge, no `pre_merge_check.py` (HK-006/HK-011/HK-014).

**QA may refuse this spec on HK-021(k)/HK-025 grounds without my agreement** -- classify each ROW 0 row
as validity or precision, evaluate both branches, and if a row lands on the same verdict either way it
is diagnostic, not a gate: name it, stop, and do not run a partial arm. **ROW 0c and ROW 0d are the two
I would attack first if I were reviewing this rather than writing it.**
