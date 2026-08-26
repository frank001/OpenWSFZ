# F-001 D3 ARM 1D -- the unique-match trade, measured with BOUNDS instead of a FILTER

**Architect → QA.** 2026-08-26 17:43Z (`date -u`, HK-017). Repo `main` @ `5c5aea3`.

**This is a NEW pre-registration, not a re-run of ARM 1C and not ARM 1C with Sec.3.2 deleted.**
ARM 1C is VOID and stays VOID (`qa/rr-study/2026-08-26-1717-architect-to-qa-ruling-f001-d3-arm1c.md`).
Its gates were never computed and nothing in this spec may be read against them.

Drafting probe: `artefacts/2026-08-26-arm1c-ruling-probe/arm1d_exposure.py` (gitignored).
**RUNNABLE BY QA NOW -- minutes, no rebuild, no replay, no capture.**

---

## 0. What this arm is, and what it is not

### 0.1 The question

**Of the names this build printed on the 12-bit path, how many were AMBIGUOUS at print time** -- a
second resident table entry sharing the query's 12-bit code -- and how does that ambiguity line up
with whether the name was RIGHT or WRONG? A "unique-match rule" (resolve only when exactly one entry
matches, otherwise print nothing) is then an **arithmetic re-labelling** of that fact: ambiguous
queries would have been blanked.

### 0.2 HK-021(p): this arm measures NO treatment, and no row may pretend otherwise

**No unique-match binary exists or is authorised.** This is a property of the build we already ran.
🛑 **No row, no log line and no report sentence may say "the fixed build would…".** That is a
different arm and (p) blocks it until a Developer session produces the binary.

### 0.3 What replaced ARM 1C's fatal filter -- read this before anything else

ARM 1C admitted a decode to its gates only if the replayed table returned **the same name** the real
build printed. **That filter was selection on a variable correlated with the outcome, and ROW 0d
caught it: fidelity was 95.7% on disagreeing decodes vs 78.1% on agreeing ones (+17.5pp, Fisher
p=1.6e-4). The arm VOIDed.**

🔴 **ARM 1D keeps the same label and throws away the filter. All 243 decodes enter. The 37 whose
replay does not reproduce the printed name are marked UNKNOWN, and their ambiguity is assigned
ADVERSARIALLY in both directions, producing an INTERVAL rather than a point.** Nothing is selected
on anything, so there is no differential-selection threat to check for and **no ROW 0d equivalent in
this arm** -- what is gated instead is the **WIDTH** of the resulting ignorance (ROW 0d below).

⚠️ **What this does NOT fix, stated here so it is never claimed later:** for the 206 KNOWN decodes
the arm still assumes the replayed *multiplicity* is right because the replayed *name* was right.
ARM 1C's ROW 0d attacked the selection, not that assumption, and a correlation between the two is
unmeasurable without multiplicity ground truth. 🔴 **Consequence, binding on every figure this arm
produces: rescue and loss numbers are quoted as bounds on a SIMULATED stratifier, and the report must
carry that sentence beside the numbers, not in a footnote.**

### 0.4 Drafting facts, disclosed now so they cannot be discovered later and used to explain a result away

| fact | value |
|---|---|
| population (from ARM 1B, unchanged) | **243 decodes / 115 callsigns / 92 disagreeing** |
| all decodes present in the replayed leg | **243/243** |
| KNOWN (replay reproduces the printed name) | **206 (84.8%)** |
| UNKNOWN | **37** -- **4 of 92 disagreeing, 33 of 151 agreeing** |
| ROW C units (>=1 disagreeing decode) | **59** |
| ROW D units (all decodes agree) | **56** |
| ROW C units carrying an UNKNOWN *disagreeing* decode | **3** ⇒ ignorance width **<= 5.08pp** |
| ROW D units carrying any UNKNOWN decode | **7** ⇒ ignorance width **<= 12.50pp** |
| gate decodes issued AFTER the table froze | **144/243 = 59.3%** |
| ARM 1C's error channel, carried forward | replay finds NOTHING on the chain where the real build resolved: **20/1,868 = 1.1%** |

🔴 **The 2x2 crossing multiplicity with outcome does not exist on the Architect's side.** The
drafting probe is firewalled against `matches12` (`v.pop("matches12", None)` before any use) and
asserts it. I have measured exposure and ignorance. **I have not measured the answer.**

---

## 1. The outcomes this arm can produce -- ALL FIVE, including the one ARM 1C forgot

| # | outcome | what it authorises |
|---|---|---|
| 1 | **C1 + D2** -- reaches a majority of wrong names, costs a minority of right ones | a remedy earns a **pre-registered Developer arm** -- itself (p)-blocked until a binary exists. **Not a fix, not a policy** |
| 2 | **C1 + D1** -- works AND is expensive | a **PRODUCT call** for the PO: is a blanked name better than a wrong one? **No build proposed by this arm** |
| 3 | **C2** (with any D) -- does not reach a majority | **no remedy build proposed.** Defect stands accepted-and-marked. ⚠️ HK-021(j): never write "it does not work" |
| 4 | **C3 or D3** -- INDETERMINATE | **no verdict, no remedy.** The band is declared in Sec.5 before the run |
| 5 | 🛑 **ROW 0 VOID** -- the instrument fails its own validity check | **nothing may be inferred about the trade, in either direction.** ARM 1C's Sec.1 omitted this outcome and then landed on it; it is enumerated here |

🛑 **Every outcome above, INCLUDING C1+D2, authorises no `src/` change, no fix, no policy and no
Developer session.**

---

## 2. Reuse, do not re-implement (HK-018)

Import and use unmodified -- **object identity, not a copy**:

- `common_arm1b`: `slot`, `build_theirs_index`, `best_match`, `T12`, `cp_lower_one_sided`,
  `cp_upper_one_sided`, the input pins.
- `run_arm1b`: `build_part_a`, `apply_row0d`, `callsign_flags`.
- `common_arm1c`: `T12C.matches12`, `run_12bit_leg_c`, `clone_table`, `redact`, `CUR_SIZE`,
  `SZ8_SIZE`.

🔴 **`matches12` is NOT re-specified here.** ARM 1C's ROW 0c proved it walks the same probe chain
`lookup12` does, with zero exceptions over 1,868 queries, and that row **PASSED**. It is re-checked
below (ROW 0c) as a drift guard, not re-derived.

**New code in this arm is only Sec.3's four functions and the two-pass driver.**

---

## 3. The measurement -- shipped as code, character for character (HK-021(r))

```python
# ---- Sec.3.1 -- KNOWN vs UNKNOWN: a LABEL, never a filter -----------------
def is_known(p, leg):
    """True iff the replay reproduced the EXACT name the real build printed.
    ARM 1C used this as a FILTER and was VOIDed for it. Here it is only a
    label: every one of the 243 decodes enters the analysis either way."""
    v = leg.get((p["ts"], p["freq_hz"], p["message_norm"]))
    return v is not None and v["sim_name"] == p["o_payload"]


# ---- Sec.3.2 -- adversarial assignment ------------------------------------
def ambiguous(p, leg, unknown_as):
    """Ambiguity of ONE decode under ONE adversarial pass. `unknown_as` is
    True or False and applies ONLY to UNKNOWN decodes; a KNOWN decode reads
    its replayed multiplicity identically in both passes."""
    if not is_known(p, leg):
        return unknown_as
    return leg[(p["ts"], p["freq_hz"], p["message_norm"])]["matches12"] >= 2


# ---- Sec.3.3 -- the two unit families, unchanged from ARM 1C (HK-021(t)) --
def rowc_units(by_cs):
    """Callsigns with >=1 DISAGREEING decode -- where a rescue could happen."""
    return sorted(cs for cs, ps in by_cs.items() if any(q["disagree"] for q in ps))


def rowd_units(by_cs):
    """The COMPLEMENT: callsigns with NO disagreeing decode -- where the cost
    lands. HK-021(t): the cost is gated on the complement of the population
    the rescue is measured on, in the same run."""
    return sorted(cs for cs, ps in by_cs.items() if not any(q["disagree"] for q in ps))


def is_rescued(ps, leg, unknown_as):
    """ROW C, deliberately conservative AGAINST the remedy: ALL of a
    callsign's disagreeing decodes must be ambiguous."""
    return all(ambiguous(q, leg, unknown_as) for q in ps if q["disagree"])


def is_lost(ps, leg, unknown_as):
    """ROW D, deliberately conservative AGAINST the remedy: ANY one of a
    callsign's decodes being ambiguous is enough to call the name lost."""
    return any(ambiguous(q, leg, unknown_as) for q in ps)
```

**Unit key is `p["o_payload"]` -- the name this build PRINTED** (for a disagreeing decode that is the
wrong name). Same unit as ARM 1C, deliberately: the unit definition is not what failed.

**HK-021(i):** the unit is the **callsign, not the decode** -- decodes of one callsign share a table
chain and are not independent. All CP intervals are computed over units.

### 3.4 Which bound tests which claim -- the rule, stated once

🔴 **Each row's own claim is tested against the assignment LEAST favourable to that claim.** No row
may be read off the assignment that flatters it.

| row | claim | bound it must clear |
|---|---|---|
| **C1** | the rule reaches a majority of wrong names | `rescued_min` (`unknown_as=False`) |
| **C2** | it does not reach a majority | `rescued_max` (`unknown_as=True`) |
| **D1** | it blanks a majority of correct names | `lost_min` (`unknown_as=False`) |
| **D2** | it costs a minority | `lost_max` (`unknown_as=True`) |

⚠️ `rescued_min` and `lost_max` come from **different passes**. They are per-quantity partial-
identification bounds, **not one joint worst-case scenario** -- do not present them as a single
"world". The joint corner where the remedy looks worst (`rescued_min` with `lost_max`) may be
reported as such, named explicitly as a corner.

---

## 4. ROW 0 -- strict order, any FAIL VOIDs the arm, no partial run

| row | check | bar |
|---|---|---|
| 0a | input identity | `L2_run1` sha256 / `shim_version` / `n_decodes`=71,600 match `common_arm1b`'s pins; reference parses to 43,423 rows |
| 0b | **population + label reproduction** | ARM 1B's pairing gives **243 / 115 / 92** EXACTLY; **243/243** decodes present in the leg; **KNOWN=206**; **UNKNOWN = 4 disagreeing + 33 agreeing**; units **59 (ROW C) / 56 (ROW D)**. Any deviation ⇒ **VOID**. ⚠️ **This is a REPRODUCTION row, not a discovery** -- every value was measured while drafting (Sec.0.4). It catches reused helpers moving underneath us and nothing else, and must be described that way |
| 0c | **predicate coherence, STRUCTURAL ONLY** | for every replayed resolved type-4 query: `lookup12(n12) is None` **iff** `matches12(n12) == 0`. Bar: **100%, zero exceptions** ⇒ else VOID. 🔴 **ARM 1C's second clause ("`matches12 >= 1` wherever the real build resolved") is DELETED, not moved.** It was an empirical fidelity claim smuggled into a structural row -- the Architect's drafting error, ruled on 17:17Z. It belongs to no row in this arm |
| 0d | **ignorance-width reproduction** | ROW C units carrying an UNKNOWN *disagreeing* decode == **3**; ROW D units carrying any UNKNOWN decode == **7**. Exact ⇒ else VOID. **This row replaces ARM 1C's differential-error test:** with no filter there is no selection to be differential, so what must be controlled is no longer the *direction* of the replay's error but the *width* of the ignorance it leaves |
| 0e | **assignment-leak check** | for **every KNOWN decode**, `ambiguous()` returns the SAME value under both passes (zero exceptions), **and** `rescued_min <= rescued_max`, `lost_min <= lost_max`. A leak here means the adversarial assignment is touching decodes it must not ⇒ VOID |
| 0f | **determinism, OUT OF PROCESS** | re-run the whole arm in a **fresh process** under a **different `PYTHONHASHSEED`**; `result.json` **byte-identical**. ⚠️ Same-process re-runs cannot see the hash-randomised-iteration hazard |
| 0g | **predicate-movement exhibit (HK-021(q))** | reuse ARM 1C's ROW 0f verbatim: take one unambiguous KNOWN query, inject a synthetic entry sharing its `n12` on the same chain, assert `matches12` moves `1 -> 2` and the unit moves `unambiguous -> ambiguous`. Paste the worked example (redacted) |
| 0h | **stated, not gated** | table-freeze exposure (**expect 144/243 = 59.3%**) and the carried error channel `n_sim_none_but_real_resolved` (**expect 20/1,868 = 1.1%**). Pre-registered so neither can later be discovered and used to explain a result away |

**Under-power stop (HK-021(m)):** if either gate denominator falls **below 40**, that gate reports
**UNDER-POWERED** with its exposure and returns no verdict; the other still runs. *At the
pre-registered denominators (59, 56) this stop does not fire -- it is carried for the case where
ROW 0b reveals the population has moved.*

⚠️ **HK-025 stands: if any ROW 0 row here is not mechanical, or its two branches would land the same
verdict, QA REFUSES and names the row. No Architect agreement needed.**

---

## 5. Gates -- interval versions of ROW C and ROW D

**ROW C -- does the rule reach the wrong names?** `p_rescue` over `rowc_units`, n = 59.

| row | condition | consequence |
|---|---|---|
| **C1** | CP one-sided 95% **lower** bound at **`rescued_min`** **> 0.50** | the rule suppresses **at least** a majority of mis-resolved names -- robust to BOTH the ignorance and sampling |
| **C2** | CP one-sided 95% **upper** bound at **`rescued_max`** **< 0.50** | it does not reach a majority. ⚠️ **Never write "it does not work"** (HK-021(j)) |
| **C3** | neither | INDETERMINATE |

**ROW D -- what does it cost?** `p_lost` over `rowd_units`, n = 56.

| row | condition | consequence |
|---|---|---|
| **D1** | CP one-sided 95% **lower** bound at **`lost_min`** **> 0.50** | it blanks **at least** a majority of currently-correct names |
| **D2** | CP one-sided 95% **upper** bound at **`lost_max`** **< 0.50** | it costs a minority |
| **D3** | neither | INDETERMINATE |

### Resolution, on the record BEFORE the run (HK-021(m), HK-021(o))

| gate | n | quantum | majority row fires at | minority row fires at | INDETERMINATE band | ignorance costs at most |
|---|---:|---:|---|---|---|---:|
| **C** | 59 | **1.69pp** | `rescued_min >= 37` (62.7%, CP lo 0.5120) | `rescued_max <= 22` (37.3%, CP hi 0.4880) | **23-36** (39.0%-61.0%), 14 units | **3 units** |
| **D** | 56 | **1.79pp** | `lost_min >= 35` (62.5%, CP lo 0.5065) | `lost_max <= 21` (37.5%, CP hi 0.4935) | **22-34** (39.3%-60.7%), 13 units | **7 units** |

One unit below each firing count does **not** fire (C: k=36 ⇒ CP lo 0.4948; D: k=34 ⇒ CP lo 0.4885),
and one unit above each minority count does not either (C: k=23 ⇒ CP hi 0.5052; D: k=22 ⇒ CP hi
0.5115). **Resolution is one unit at both edges of both gates.**

🔴 **Say this plainly in the report: the arm separates "clear majority" from "clear minority" and
NOTHING in a ~14-unit band between. The ignorance the bounds carry (3 and 7 units) is SMALLER than
that band already is** -- switching from a filter to bounds costs less resolution than the gate's own
indeterminate zone. It is enough for the PO's go/no-go and **not** enough to size a remedy. Both
halves of that sentence must appear.

---

## 6. Descriptive, ungated, reported beside the gates

- **ROW E -- post-rule agreement among survivors:** `unambiguous & agree / (unambiguous & agree +
  unambiguous & disagree)`, as an **interval** over the two passes. 🔴 **HK-021(u): quote ARM 1B's
  baseline in the SAME sentence -- 62.1% (151/243) -- or the figure is not evidence.**
  ⚠️ Descriptive only: it conditions on surviving, which is selection on the stratifier, and it may
  never be quoted as a correctness rate for any build.
- **Contingency / the ceiling on ANY suppression remedy:** decodes that are KNOWN, `matches12 == 1`,
  and **WRONG** -- the correct entry was never resident (the table freezes at 4,096 of 16,320 names
  seen), so no unique-match rule can help them. Count it separately and name it as the ceiling.
- **Part B -- multiplicity at 32,768 beside 4,096** (parent ruling measured 50.9% → 78.4%
  corpus-wide). **DESCRIPTIVE ONLY: no real decoder output exists at 32,768, so there is no outcome
  to cross it with.** It informs the coupled ARM 2 decision; it adjudicates nothing.

---

## 7. Blind predictions (Sec.8 discipline -- recorded before the run, evidence of nothing)

1. **C1 fires.** Rationale: 50.9% of resolved 12-bit queries are already ambiguous corpus-wide, and
   disagreeing decodes are *selected on a collision having happened*, so their ambiguity should run
   well above that base. **Moderate-high.** ⚠️ **The mechanism that could sink it, named up front:**
   a wrong name printed at multiplicity 1 -- the correct entry never resident (Sec.6's ceiling).
   Those units can never be rescued, and if that share is large, C1 fails.
2. **D1 fires too.** ROW D uses ANY over a callsign's decodes, so multi-decode callsigns trip easily
   at a ~50% per-query base rate. **Moderate.**
3. **The arm lands C1+D1** -- the rule works AND is expensive, so the decision becomes a PRODUCT call.
   ⚠️ **This is the same prediction I made for ARM 1C and it is not evidence; I am repeating it so
   that repeating it is visible.**
4. **The ignorance changes neither gate's row** (3 and 7 units against 14- and 13-unit bands).
   **Moderate-high.**
5. **ROW E > 80%.** **LOW confidence, and flagged low.**

---

## 8. Authorisation and scope

- ✅ Pure offline re-analysis of dumps already on disk. **No rebuild, no replay, no capture, no
  `src/` or `native/` edit** (HK-011).
- ✅ Commit locally; **nothing pushed** (HK-014). No `pre_merge_check.py` (HK-006).
- ✅ **NFR-021:** real callsigns live in memory only. `result.json`, `run.log` and the report carry
  counts, cycle timestamps, frequencies, the DLL sha256, and `redact()`-ed `CS-xxxxxx` tokens --
  nothing else. Grep both output files before committing.
- 🛑 **No investigation of ARM 1C's differential-fidelity mechanism.** Two hypotheses are on the
  record (QA's and mine); **neither is adopted, neither may be assumed, and this arm tests neither.**
- 🛑 **No de-attenuated, corrected, or "adjusted" version of any figure.**

## 9. Deliverables

`qa/rr-study/f001-d3-arm1d/{common_arm1d.py,run_arm1d.py}` +
`results/<date>-<sha>/{result.json,run.log}` + a QA→Architect report following ARM 1C's shape:
ROW 0 table first, gates second, then what it does and does not mean.

## Cross-references

- `qa/rr-study/2026-08-26-1717-architect-to-qa-ruling-f001-d3-arm1c.md` -- the ruling that named the
  filter as the fault and measured this arm's feasibility.
- `qa/rr-study/2026-08-26-1619-architect-to-qa-spec-f001-d3-arm1c-unique-match-trade.md` -- VOID.
  Read for the unit definitions and the ROW 0f exhibit only.
- `qa/rr-study/2026-08-26-1504-architect-to-qa-ruling-f001-d3-arm1b.md` -- parent ruling; the
  chain-multiplicity exposure that motivated the whole question.
