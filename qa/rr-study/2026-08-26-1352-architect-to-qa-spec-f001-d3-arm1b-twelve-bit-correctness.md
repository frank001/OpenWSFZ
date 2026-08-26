# SPEC -- `F-001 D3` ARM 1B: IS THE CURRENT BUILD PRINTING **WRONG CALLSIGNS** ON THE 12-BIT PATH?

**Architect -> QA.** 2026-08-26 13:52Z (`date -u`, HK-017). Repo `main` @ `70347ef`.

Pure re-analysis of dumps already on disk. **No `src/` change, no `native/` change, no rebuild, no
replay, no capture, no Developer session** (HK-011). Docs-only on my side, committed locally, nothing
pushed (HK-014). **Runnable by QA now; minutes, not hours.**

Parent ruling: `qa/rr-study/2026-08-26-1307-architect-to-qa-ruling-f001-d3-arm1.md` (**read its Sec.7
amendment first** -- this arm exists because of what that amendment withdrew and what it did not).

---

## 0. Read this before anything else: what changed, and what this arm is NOT

**0.1 This arm no longer gates arm 2.** I raised the 12-bit path as a blocker on the enlargement
`#define` at 13:07Z and withdrew it at 13:41Z, falsified by my own drafting probe. Enlargement
**cannot flip** a 12-bit resolution -- decoys always live in the query's own bucket, chain order is
insertion order in both legs, and an entry CUR rejected always lands *after* everything already on the
chain -- so it can only ADD a resolution where CUR had none. Measured: **15 discordant queries out of
1,868, all of them "CUR had no entry", ZERO flips.** Arm 2 is unblocked and independent of this arm.

**0.2 What is still open, and it is a PRODUCT question, not a D-001 question.** 56.7% of every resolved
hashed callsign in this corpus (1,899 decodes vs 1,448) comes out of the 12-bit path, where
`ft8_shim.c:649-651` compares TRUNCATED bits and **returns the first matching entry on the chain without
ever checking whether a second entry also matches**. 12 bits is 4,096 codes against a table holding
thousands of callsigns. Nobody has ever checked whether the name we print there is the right one. **A
wrong callsign is worse than an unresolved one: `<...>` is honest, a wrong name is loggable.**

**0.3 Four facts read out of source while drafting (HK-018), two of which shape the design:**

1. `message.c:431` (`decode_nonstd`, **12-bit**) and `message.c:782` (`unpack28`, **22-bit**) are the
   ONLY two lookup call sites. `message.c:589` `save_hash(callsign, n22)` always stores the FULL 22-bit
   hash. `FTX_CALLSIGN_HASH_10_BITS` is never invoked in this tree.
2. 🔴 **The query hash is recoverable EXACTLY from the rendered name, correct or not.** The shim returned
   an entry because `(stored_n22 >> 10) == query_n12`, and `stored_n22` is the hash of the name it
   printed. So `n12(rendered name) == query n12` **by construction** -- there is no circularity in
   replaying the query stream from the dump, and this is what makes the whole arm possible offline.
3. 🔴 **Fact 2 gives the arm a free validity test.** If our name and the reference's name for the same
   slot DISAGREE but the two names do not share the same `n12`, the pair is **not the same message** and
   must be dropped -- the disagreement is a matching failure, not a mis-resolution. ROW 0d gates on this.
4. The 12-bit path is simulable: a CUR-sized simulated table reproduces the REAL decoder's rendered name
   on **1,727/1,868 = 92.5%** of type-4 queries (Architect probe, `artefacts/2026-08-26-arm1b-probe/`).
   The 7.5% shortfall is the emitted-decode proxy's own insert gap, already priced in by arm 1's ROW 0b.

**0.4 What I deliberately did NOT measure while drafting.** I measured the population size `k`, its
clustering, and the paired discordance -- the *exposure*. **I did not compute the agreement rate.** A
threshold chosen after seeing the answer is worthless (HK-021(s)'s spirit), and the thresholds in Sec.5
were fixed before any agreement number existed. **QA must not read the probe scripts' output before
fixing its own run.** The scripts are gitignored under `artefacts/2026-08-26-arm1b-probe/`; read the
code if useful, not a result.

---

## 1. Question, and the only two consequences this arm can have

> **Of the hashed callsigns this build prints on the 12-bit path, how many are the WRONG station?**

- **ROW A1 fires** ⇒ a defect is confirmed ⇒ QA raises `DEFECT-twelve-bit-hash-misresolution.md` and a
  fix earns its own pre-registration. **It does not authorise a fix, a policy, or a `src/` change.**
- **ROW A2 fires** ⇒ not detectable at this exposure ⇒ the question closes **for this table size**, with
  the exposure stated, and arm 2 carries ROW B forward as a counter-metric.
- Anything else ⇒ **INDETERMINATE**, declared before the run, no consequence in either direction.

---

## 2. Inputs, pinned -- never re-derived

| pin | value | source |
|---|---|---|
| ours | `artefacts/2026-08-25-g2a-remeasure-a/L2_run1_decodes.json` | sha256 + `shim_version` + `n_decodes`=71,600 asserted via `common_g2a` |
| reference | `artefacts/20260803_live_run_1713/wsjt-x/ALL.TXT` | `gc.parse_all_txt`, 43,423 rows |
| replicate | `L2_run2_decodes.json` | ROW 0e |
| `HASH_TABLE_SIZE` | 4,096 | `ft8_shim.c:631` |
| enlarged legs | 16,384 / 32,768 | arm 1 `SZ4`/`SZ8` |

**Reuse, do not re-implement** (HK-018): `common_g2a.rows_from_dump_corrected`, `gc.parse_all_txt`,
`common_b1.is_callsign_token`, `common_arm1.n22_of` and `common_arm1.SimTable`. ROW 0c asserts the reuse
by object identity, as arm 1's ROW 0d did.

---

## 3. Method

**3.1 The type-4 population.** Ship this predicate verbatim (HK-021(r) -- the prose below is a gloss on
the code, the code is the spec):

```python
STD   = re.compile(r'^[A-Z0-9]{1,2}[0-9][A-Z]{1,3}$')
GRID  = re.compile(r'^[A-R]{2}[0-9]{2}$')
UNRES = re.compile(r'^<\.*>$')
NONCALL = {'CQ','DE','QRZ','RRR','RR73','73','TU','NA','SA','EU','AS','AF','OC','AN','DX','TEST'}

def slot(msg):
    """None unless the message has EXACTLY ONE bracket slot."""
    toks = msg.split()
    br = [t for t in toks if t.startswith('<')]
    if len(br) != 1:
        return None
    others = [t for t in toks if not t.startswith('<')]
    nonstd = any((not STD.fullmatch(t)) and (not GRID.fullmatch(t)) and t not in NONCALL
                 and not re.fullmatch(r'[+-]?[0-9]{1,2}', t)
                 and any(c.isdigit() for c in t) and any(c.isalpha() for c in t) for t in others)
    kind = "unresolved" if UNRES.fullmatch(br[0]) else "resolved"
    return kind, br[0].strip('<>'), tuple(others), nonstd, len(toks)
```

`nonstd == True` is the 12-bit path. It is a **lower bound**: a nonstandard callsign that happens to look
standard is counted on the wrong side. Report it as such, never as an exact split.

**3.2 Pairing to the reference. The match key EXCLUDES the hash slot, deliberately.** Two decodes pair
iff: identical `ts`, identical token count, identical tuple of ALL non-bracket tokens, and
`|freq_ours - freq_theirs| <= 4.0` Hz. **Excluding the slot from the key is load-bearing** -- it means
the population is not selected on the outcome under test (the trap I proposed as HK-021(t) in the parent
ruling). If several reference rows match, keep the nearest in frequency; ties break on lowest `freq_hz`,
then on `message_norm`, sorted before selection (the hash-randomised-iteration hazard on the board).

**3.3 PART A -- correctness against an outside instrument.** For each pair where BOTH sides resolved the
slot: `agree` iff the two names are byte-equal after `normalise_text`. Otherwise `disagree`.

⚠️ **Attribution is NOT claimed and must not be written as though it were.** WSJT-X carries the same
protocol-level 12-bit ambiguity we do, so a disagreement means **one of the two is wrong**, not that we
are. The measured rate is therefore a **LOWER BOUND on the joint error rate** and is quoted that way in
every line of the report. HK-026 is satisfied precisely here: our own decoder's output cannot bound its
own blind spot, and the reference is the wider-aperture instrument -- but only for a bound, never for
attribution.

**3.4 PART B -- the 15, adjudicated.** Rebuild the paired simulation of the parent ruling's Sec.7
(`CUR` vs `SZ4` vs `SZ8`, same insert stream, `SimTable` + the 12-bit probe) and recover the queries
whose resolution DIFFERS between legs. For each, report: does a reference pair exist, and does the
enlarged leg's new name agree with it? **This is arm 2's counter-metric, computed once, here.**

**3.5 Unit and clustering (HK-021(i)).** The unit for every CI in Part A is the **named callsign**, never
the decode. Probe sizing: `k = 243` decodes over **115 distinct callsigns**, top-5 = 24.7% of `k` (far
less concentrated than B1's 72.3%, but not flat). Decode counts are exact point counts, printed beside a
concentration table, and **never carry a CI**.

**3.6 NFR-021.** Counts, cycle timestamps, frequencies, `sha256[:6]` redactions. No real callsign and no
raw message text in `result.json`, the report, or the log. PD2FZ is the only exception the policy allows
and this arm has no reason to use it.

---

## 4. ROW 0 -- run in strict order, any FAIL VOIDS the arm, no partial run

| row | check | bar |
|---|---|---|
| 0a | dump identity | `L2_run1` sha256 / `shim_version` / `n_decodes`=71,600 match `common_g2a`'s pins; reference `ALL.TXT` parses to 43,423 rows |
| 0b | **population reproduction (load-bearing)** | the `slot()` predicate above yields **1,899** resolved type-4 decodes and **1,448** resolved standard ones; bar `[1,850, 1,950]` and `[1,400, 1,500]`. Outside ⇒ the predicate is not the one specced ⇒ VOID |
| 0c | predicate reuse | `is_callsign_token` / `n22_of` / `SimTable` are the SAME objects as arm 1's, asserted by identity, not by eye |
| 0d | **the free validity test (Sec.0.3 fact 3)** | for **every** disagreeing pair, `n22(ours) >> 10 == n22(theirs) >> 10`. Bar: **100%**. Any pair failing it is dropped from Part A as a matching failure and COUNTED separately; if more than **10%** of disagreements drop, the pairing rule is broken ⇒ VOID |
| 0e | determinism + independent input | rerun byte-identical; `L2_run2` reproduces `k` within `[k-15, k+15]` |
| 0f | **predicate-movement exhibit (HK-021(q))** | take one agreeing pair; mutate our name by one character; assert the classifier moves `agree -> disagree` AND that the mutated pair then FAILS ROW 0d's `n12` test. Paste the worked example (redacted) in the report. A classifier that cannot be made to move is not measuring anything |
| 0g | 12-bit simulator fidelity (Part B only) | simulated `CUR` reproduces the real decoder's rendered name on **>= 85%** of type-4 queries (Architect probe: 92.5%; the bar sits below it because the proxy gap is corpus-dependent). Below 85% ⇒ Part B is VOID, **Part A is unaffected** -- Part A never uses the simulator |

`k` itself is NOT a gate. If `k < 60` after ROW 0d, the arm STOPS and reports **UNDER-POWERED**, with no
verdict in either direction -- stated here, before the run (HK-021(m)).

---

## 5. Gates -- mutually exclusive, evaluated in strict order, unit = callsign

A callsign is **`cs-disagree`** if at least one of its paired decodes disagrees, **`cs-agree`** otherwise.
`p_dis` = `cs-disagree` / (`cs-disagree` + `cs-agree`). CI: **Clopper-Pearson, one-sided 95%**, never a
bootstrap (HK-021(n)/(o) -- this metric can land on a degenerate 0/115).

| row | condition | consequence |
|---|---|---|
| **A1** | CP one-sided 95% **lower** bound on `p_dis` **> 0.05** | **CONFIRMED**: the 12-bit path mis-resolves at a rate the corpus can see. QA raises `DEFECT-twelve-bit-hash-misresolution.md` (evidence + counts, no fix) and a remedy earns its own pre-registration |
| **A2** | CP one-sided 95% **upper** bound on `p_dis` **< 0.05** | **NOT DETECTABLE at this exposure.** The question closes for `HASH_TABLE_SIZE` 4,096, with `k`, the callsign count and the bound stated. **Never write "does not happen"** (HK-021(j)) |
| **A3** | neither | **INDETERMINATE.** No defect raised, no closure. Report the interval and stop |

**Resolution, stated while drafting (HK-021(m)).** At 115 callsigns: 0 disagreeing ⇒ CP upper bound
**2.6%** ⇒ A2 fires. 10 of 115 (8.7%) ⇒ CP lower bound **5.0%** ⇒ A1 fires at the boundary. **So the arm
separates "under ~3%" from "over ~9%" and NOTHING in between; 1-9 disagreeing callsigns lands in A3 by
construction.** That is on the record before the run and is not a reason to move the bar afterwards.

**ROW B (Part B, ungated, reported beside A):** the count of enlargement-discordant queries (Architect
probe: 15, all "CUR had no entry", zero flips -- QA must reproduce, and a **non-zero flip count is a
finding in its own right that contradicts the parent ruling's Sec.7 and must be escalated, not
smoothed**), and how many of the new resolutions the reference confirms.

---

## 6. Contingencies, decided now rather than mid-run

- **Reference resolves where we do not, or vice versa.** Out of Part A (it needs both sides named).
  Counted and reported as a descriptive four-way table. It is a *coverage* difference, not a *correctness*
  one, and must not be folded into `p_dis`.
- **More than one bracket slot in a message.** Excluded by `slot()` returning `None`. Count them.
- **A disagreement where our name never appears in plaintext anywhere in the corpus, or the reference's
  does.** Descriptive tiebreaker ONLY, reported ungated and explicitly not used to attribute. Attribution
  needs an instrument we do not have.
- **HK-021(p):** this arm is single-leg re-analysis, no A/B, no binary to isolate -- so (p) is satisfied
  trivially, and the ONLY confound in scope is the emitted-decode proxy, which touches Part B alone and is
  bounded by ROW 0g's 85% bar. **Part A does not use the simulator at all and is proxy-free.**

---

## 7. My predictions, recorded BLIND before QA runs anything (Sec.0.4: I have not computed the answer)

1. **`p_dis` lands in A3, the indeterminate band** -- moderate confidence. I expect a handful of
   disagreeing callsigns, not zero and not fifteen.
2. **Part B reproduces 15 discordant / 0 flips exactly** -- high confidence; it is a deterministic replay
   of the same code path.
3. **The reference will confirm the majority of the enlarged leg's new resolutions** -- low confidence,
   and honestly stated: I got the magnitude of this whole line of reasoning wrong once already today.
4. **Coverage differences (Sec.6 item 1) will outnumber correctness disagreements by more than 3:1** --
   moderate. If that holds, the interesting question was never mis-resolution but who resolves *at all*.

---

## 8. Scope

Authorises: **one QA run and one report.** No `src/`, no `native/`, no rebuild, no replay, no capture, no
Developer session, no push, no merge, no `pre_merge_check.py` (HK-006/HK-011/HK-014). A1's maximum
consequence is a defect file plus a pre-registration; A2's is a closure sentence with its exposure
attached.

**QA may refuse this spec on HK-021(k)/HK-025 grounds without my agreement** -- classify each ROW 0 row
as validity or precision, evaluate both branches, and if a row lands on the same verdict either way it is
diagnostic, not a gate: name it, stop, and do not run a partial arm.
