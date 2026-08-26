# F-001 D3 ARM 1D -- RESULT: ROW 0 CLEARS IN FULL, gates land C3 + D3 (INDETERMINATE)

**QA → Architect.** 2026-08-26 18:00Z (`date -u`, HK-017). Repo `main` @ `c3cd550`.

Spec: `qa/rr-study/2026-08-26-1743-architect-to-qa-spec-f001-d3-arm1d-unique-match-trade-bounded.md`.
Harness (new): `qa/rr-study/f001-d3-arm1d/{common_arm1d.py,run_arm1d.py}`. Result:
`qa/rr-study/f001-d3-arm1d/results/2026-08-26-c3cd550/{result.json,run.log}`. Pure re-analysis of
on-disk dumps, no rebuild/replay/capture, no `src/`/`native/` edit (Sec.8). Committed locally, nothing
pushed (HK-011/014 convention).

🔴 **Every row of ROW 0 PASSED, including the out-of-process determinism check. The gates themselves
report Sec.1 outcome #4: C3 and D3, both INDETERMINATE.** Bounds land inside the pre-registered
indeterminate bands for both C and D -- neither a majority nor a minority is established for either
claim. **No outcome here authorises `src/` change, fix, policy, or a remedy decision** (true under
every outcome per Sec.1, and doubly so for an INDETERMINATE one).

⚠️ **Binding on every figure below, per Sec.0.3, said beside the numbers as instructed, not in a
footnote: for the 206 KNOWN decodes this arm still assumes the replayed *multiplicity* is right
because the replayed *name* was right. That assumption is unmeasured and every rescue/loss figure is
a bound on a SIMULATED stratifier, never a bound on the real one.**

---

## ROW 0 -- strict order, all rows clear

| row | check | result |
|---|---|---|
| 0a | input identity | PASS -- `L2_run1` sha/shim/`n_decodes`=71,600 match; reference `ALL.TXT` parses to **43,423** rows |
| 0b | **population + label reproduction** | PASS -- ARM 1B's pairing reproduces **243/115/92** EXACTLY; **243/243** decodes present in the leg; **KNOWN=206**; UNKNOWN = **4** disagreeing + **33** agreeing; units **59** (ROW C) / **56** (ROW D) -- every figure an exact match to Sec.0.4's drafting facts |
| 0c | **predicate coherence, structural only** | PASS -- `lookup12(n12) is None` iff `matches12(n12)==0` over **1,868** queries, **zero exceptions**. (ARM 1C's second, empirical clause is deleted per this spec and was not checked -- correctly, per Sec.4) |
| 0d | **ignorance-width reproduction** | PASS -- ROW C units carrying an UNKNOWN disagreeing decode = **3** (exact); ROW D units carrying any UNKNOWN decode = **7** (exact) |
| 0e | **assignment-leak check** | PASS -- zero exceptions on `ambiguous()` agreement across both passes for all 206 KNOWN decodes; `rescued_min(33) <= rescued_max(36)`; `lost_min(20) <= lost_max(27)` |
| 0f | **determinism, out of process** | PASS -- fresh-process reruns under `PYTHONHASHSEED=11111` and `999983` produced **byte-identical** `result.json` |
| 0g | **predicate-movement exhibit (HK-021(q))** | PASS -- first candidate tried: `matches12` moved 1→2 on synthetic-entry injection, unit moved unambiguous→ambiguous (worked example in `row0g_detail`, redacted) |
| 0h | stated, not gated | table-freeze exposure **144/243 = 59.3%** (exact match); carried error channel **20/1,868 = 1.1%** (exact match) |

No VOID anywhere. All eight rows ran; nothing was skipped.

---

## Gates (Sec.5) -- both INDETERMINATE

**ROW C -- rescue, n=59, quantum 1.69pp.**

| quantity | value | CP one-sided 95% | tests |
|---|---:|---:|---|
| `rescued_min` (unknown_as=False) | 33 (55.9%) | lower = **0.4442** | C1 needs > 0.50 -- **fails** |
| `rescued_max` (unknown_as=True) | 36 (61.0%) | upper = **0.7169** | C2 needs < 0.50 -- **fails** |

Both bounds land inside the pre-registered indeterminate band (23-36 units, 39.0%-61.0%) -- `rescued_max`
sits exactly at its top edge. **→ ROW C3.**

**ROW D -- cost, n=56, quantum 1.79pp.**

| quantity | value | CP one-sided 95% | tests |
|---|---:|---:|---|
| `lost_min` (unknown_as=False) | 20 (35.7%) | lower = **0.2508** | D1 needs > 0.50 -- **fails** |
| `lost_max` (unknown_as=True) | 27 (48.2%) | upper = **0.5995** | D2 needs < 0.50 -- **fails** |

`lost_max` lands inside the indeterminate band (22-34 units); `lost_min` falls below it, which only
means D1 fails by a wider margin -- D1's own bar is `>= 35`, not the band edge, so this changes no
verdict. **→ ROW D3.**

**Both gates are INDETERMINATE.** Per Sec.1 outcome #4: **no verdict, no remedy proposed either
way.** ⚠️ Per HK-021(j), this is not "the rule doesn't work" -- it is "this instrument, at this
resolution, cannot tell majority from minority for either claim."

🔴 **The ignorance width did not decide this.** The 3-unit (ROW C) and 7-unit (ROW D) ignorance bands
are, as pre-registered, narrower than the ~14-/13-unit indeterminate bands -- and in this run neither
bound crossed a firing threshold from either side. The indeterminacy comes from **sampling
uncertainty at n=59/56**, not from the adversarial assignment. Swapping the filter for bounds cost
less resolution than the gates' own indeterminate zone, exactly as the spec said it would -- it simply
was not enough to resolve this particular pair of point estimates either.

---

## Descriptive (Sec.6)

**ROW E -- post-rule agreement among survivors**, interval over the two passes:

| pass | unambig & agree | unambig & disagree | rate |
|---|---:|---:|---:|
| unknown_as=False | 97 | 32 | 75.2% |
| unknown_as=True | 64 | 28 | 69.6% |

**Interval: [69.6%, 75.2%].** HK-021(u), same sentence: **ARM 1B's unfiltered baseline is 62.1%
(151/243).** Both ends of the interval sit above that baseline. ⚠️ Descriptive only -- conditions on
surviving (selection on the stratifier), never a correctness rate for any build.

**Contingency / ceiling on any suppression remedy:** KNOWN, `matches12==1`, and WRONG: **28**
decodes. These can never be rescued by a unique-match rule -- the correct entry was never resident.

**Part B (descriptive, not adjudicated):** ambiguous share @4096 = 950/1,868 = **50.9%**; @32,768 =
1,465/1,868 = **78.4%** -- unchanged from the parent ruling's own measurement, reproduced here as a
drift guard, not a new finding.

---

## Blind predictions (Sec.7) vs. what happened

| # | prediction | outcome |
|---|---|---|
| 1 | C1 fires, moderate-high | **Did not fire.** C3 (indeterminate) |
| 2 | D1 fires, moderate | **Did not fire.** D3 (indeterminate) |
| 3 | lands C1+D1 | **Did not land.** C3+D3 |
| 4 | ignorance changes neither gate's row, moderate-high | **Held.** Both bounds stayed inside the same indeterminate band on each gate |
| 5 | ROW E > 80%, low confidence | **Did not clear.** Interval tops out at 75.2%, below 80% -- consistent with the flagged low confidence |

Four of five predictions did not hold as stated; only #4 (about the ignorance width specifically, not
about which row would fire) held. Recorded per Sec.7 discipline: evidence of nothing, kept on the
record because it was kept on the record before the run.

---

## What this does and does not mean

- **Does NOT answer the PO's rescue/cost question either way.** Both gates are INDETERMINATE at the
  pre-registered n. This is not a defect in the arm's design (ROW 0 cleared in full, including the
  assignment-leak and determinism checks) -- it is what the data support at this sample size.
- **Does NOT revise** ARM 1B's result, the accepted defect, or ARM 1C's VOID.
- **Does NOT re-open or pre-judge** ARM 2 or the remedy-worth-a-pre-registration question -- both stay
  exactly where the 17:17Z ruling left them, coupled, awaiting the PO's word.
- **Does NOT license** treating `rescued_min`/`rescued_max`/`lost_min`/`lost_max` as a single joint
  scenario -- they come from different passes (Sec.3.4). The joint worst-case corner
  (`rescued_min`=33, `lost_max`=27) may be named as a corner if useful, but it is not "the" answer.
- **A larger n (more resolved-both decodes, e.g. from a longer or repeated capture) is the only lever
  visible from here that could move either gate out of INDETERMINATE** -- not proposed as a next step
  unprompted (HK-004/HK-015), just named as the mechanical reason two clean, VOID-free, leak-free
  bounds still didn't resolve.

---

## Process

Per HK-021(r): Sec.3's four functions were transcribed character-for-character into
`common_arm1d.py` against the spec's own listing (diffed by eye, docstrings included verbatim) --
not re-derived from prose. Per HK-018: all ARM 1B/ARM 1C machinery (`build_part_a`, `apply_row0d`,
`T12C.matches12`, `run_12bit_leg_c`, `clone_table`, CP helpers, input pins) is imported, not
re-implemented; ROW 0g reuses ARM 1C's ROW 0f exhibit verbatim. Per HK-011/HK-014: no `src/`/`native/`
change, nothing pushed. Per HK-006: no `pre_merge_check.py` run. Per NFR-021: `result.json`/`run.log`
grepped for un-redacted callsign-shaped tokens outside `CS-xxxxxx` form -- none found; both files
carry only counts, cycle timestamps, frequencies, the DLL sha256, and redacted tokens.

## Cross-references

- `qa/rr-study/2026-08-26-1717-architect-to-qa-ruling-f001-d3-arm1c.md` -- the ruling that named the
  filter as ARM 1C's fault and measured this arm's feasibility.
- `qa/rr-study/2026-08-26-1644-qa-to-architect-f001-d3-arm1c-result.md` -- ARM 1C's VOID result;
  stays VOID, not read against here.
- `qa/rr-study/2026-08-26-1504-architect-to-qa-ruling-f001-d3-arm1b.md` -- parent ruling; the
  chain-multiplicity exposure that motivated the whole question.
- `artefacts/2026-08-26-arm1c-ruling-probe/arm1d_exposure.py` -- the drafting probe whose exposure
  numbers (243/115/92, KNOWN=206, units 59/56, ignorance 3/7, freeze 144/243) this arm's ROW 0b/0d/0h
  reproduce exactly.
