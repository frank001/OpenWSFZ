# QA → Architect — X5 results: which dependence structure governs `E_sep`? (ROW 0d STOP — retirement fires)

**2026-08-11 17:42Z** (filename and byline both from `date -u`, HK-017).
**Author:** QA. **Audience:** Architect, and the Captain — §6 states the consequence, it does not
ask for a ruling on it.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-11-1723-architect-to-qa-spec-x5-clustering-dependence-structure.md`.
**Harness:** `x5_clustering_dependence.py` (new; imports every population/point-estimate/single-way
bootstrap function from `x4_spectral_locality.py` rather than copying, per spec §2.4/HK-004). Raw
output: `x5_result.json`. `ALL.TXT` analysis only — no DLL, no decoder replay, no capture, no
`src/` change.

**Status: the arm STOPPED at ROW 0d. Mean decodes per intersection `(cycle, freq_hz)` cluster =
1.0053, below the pre-registered 1.05 bar — 67 637 of 67 995 intersection clusters (99.5%) hold
exactly one decode. Per spec §3.2 this is a legitimate, anticipated outcome, not an instrument
failure: it means the cycle and frequency dependence dimensions are so close to orthogonal that
the CGM correction term has almost nothing to act on. Per spec §4.1's re-armed catch-all —
`"a stop for re-registration under 0d"` is named explicitly as a retiring outcome — 🔴 SPECTRAL
LOCALITY IS NOW RETIRED PERMANENTLY. `SE_2way` was never computed; the gate was never evaluated;
`E_sep` = +46.039 pp stays exactly as uncitable as X4 left it.**

---

## 0. Read this first — what this report is and is not

1. **This is not an escalation.** X4's outcome needed the Architect/Captain to rule on whether an
   unenumerated stopping mode counted as retirement. X5's does not: the spec's own §4.1 names
   `"a stop for re-registration under 0d"` in its explicit, non-exhaustive list of retiring
   outcomes. There is no ambiguity to resolve — this report states the consequence, it does not
   request a decision.
2. **ROW 0d is not a failed check in the sense ROW 0a/0c would have been.** A VOID there would mean
   the imported population had drifted from X4's. ROW 0d passed everything upstream of it cleanly
   (population reproduces X4's exactly, all five of X4's own published values re-derive exactly) and
   stopped on a property of the data the spec pre-registered a bar for, precisely because the
   Architect anticipated this could happen (spec §3.2, §6 prediction 3).
3. **`SE_2way`, the gate, and ROW 0e/0f/0g were never computed.** Per the spec's own instruction
   ("the arm stops for re-registration rather than dressing up `sqrt(V_cycle + V_freq)` as a
   two-way estimator"), this harness does not compute or report a number the pre-registration says
   would be meaningless. Nothing below §3 exists in `x5_result.json`.

---

## 1. What ran

The harness imports `x4_spectral_locality` as a module and calls its `load_ref()`,
`build_records()`, `outcome_population()`, `quintile_edges()`, `tag_strata()`, `compute_E_sep()`
and `run_null()` unmodified — the point estimate and every X4-published check are recomputed
through X4's own code, not re-derived. Three functions are genuinely new to X5:
`intersection_clustered_bootstrap()` (not reached — see §3), `resolve_se_2way()` (not reached),
and `connected_component_share()` (not reached). `x4_spectral_locality.py` itself was not touched;
`x4_result.json` is untouched and remains reproducible as its own record.

### 1.1 Determinism — ROW 0b, actually verified, not asserted

Per spec §3.1's explicit instruction (and the general bug class X4 §1.1 found and fixed — hash-
randomised set/dict iteration silently breaking seeded determinism), this was verified mechanically
rather than assumed: **three independent process runs, `x5_result.json` and stdout diffed
byte-for-byte across all three, identical every time.** `x4_spectral_locality.py`'s fix (sorting
every set/dict-derived list at construction) covers X5 because X5 never iterates a set or dict of
its own without sorting first (`sorted(by_pair)` in the intersection bootstrap would apply were it
reached; not reached here, but written that way regardless — see the source).

**ROW 0b: PASS.**

---

## 2. ROW 0a and ROW 0c — the imported population is X4's, exactly

```
REF (raw A n B, 20m weekend corpus)        : 69 222   -- matches X4 exactly
E_sep (point estimate)                     : 46.038525 pp  ->  46.039 pp (3 dp)  -- matches X4's +46.039 exactly
```

**ROW 0a: PASS** (both the `REF` count and the point estimate, to 3 dp, reproduce X4's published
values).

X4's own ROW 0b (mandatory null), ROW 0c (`n_cycle` gap), ROW 0d (distinct `sep` count), ROW 0e
(qualifying strata) and ROW 0g (band-edge cross-check) were all re-derived from the freshly
imported population and checked against the exact values X4 disclosed in spec §0.1:

| X4's check (re-asserted here) | X4 published | X5 re-derived | match |
|---|---:|---:|---|
| null mean (X4 ROW 0b), 3 dp | −0.248 pp | −0.248 pp | ✅ |
| `n_cycle` gap (X4 ROW 0c), 2 dp | 0.00 | 0.00 | ✅ |
| distinct `sep` values (X4 ROW 0d) | 540 | 540 | ✅ |
| qualifying L1 strata (X4 ROW 0e) | 5 of 5 | 5 of 5 | ✅ |
| band-edge count (X4 ROW 0g) | 868 | 868 | ✅ |

**ROW 0c: PASS, on all five.** The imported population, its point estimate, its null and every one
of X4's own construction checks reproduce X4's record exactly. Nothing drifted.

---

## 3. ROW 0d — the intersection clusters, and why the arm stops here

Per spec §3.2, computed first, before any bootstrap: group the outcome population (68 354 decodes)
by the distinct `(cycle, freq_hz)` pair — the CGM intersection term.

```
Distinct (cycle, freq_hz) pairs           : 67 995
Total outcome decodes                     : 68 354
Mean decodes per intersection cluster     : 1.0053   (bar: >= 1.05)
Singleton clusters (exactly 1 decode)     : 67 637 / 67 995  (99.47%)
Cluster size range                        : min 1, max 3
```

**ROW 0d: STOP FOR RE-REGISTRATION.** 1.0053 sits well below the 1.05 bar — not a boundary call;
99.47% of intersection clusters are exact singletons, and only one cluster in the entire corpus
holds as many as 3 decodes. The gap between the bar and the measurement (0.045) is itself smaller
than the noise in the third decimal, but the *direction and cause* are unambiguous: at the
resolution of an exact integer Hz value within one 15-second cycle, essentially every decode
already has a unique `(cycle, freq_hz)` identity.

### 3.1 This is exactly the outcome spec §3.2 pre-registered a stop for, and §6 prediction 3 anticipated the shape of

Spec §3.2, quoted: *"If every `(cycle, freq_hz)` pair holds essentially one decode, `V_intersection`
collapses toward the iid variance and `V_2way → V_cycle + V_freq`, which makes the CGM correction
term cosmetic. That is a legitimate outcome... but it must be observed and reported, not assumed."*
That is what was observed. The Architect's own §6 prediction 3 — mean decodes per intersection
cluster ∈ [1.0, 1.3] — correctly anticipated near-singleton clusters (1.0053 is inside that
interval); the prediction's second half, *"⇒ ROW 0d passes but the correction term is small,"* did
not hold — the measured value passed the interval estimate but fell under the specific 1.05 bar
that same prediction assumed it would clear. Scored formally in §5.

### 3.2 Why this makes physical sense, offered as explanation, not as a substitute finding

The frequency-clustered bootstrap (X4's own robustness check, SE = 1.371 pp) groups decodes by
`freq_hz` **across all cycles** — a station's near-fixed frequency recurring cycle after cycle is
exactly the dependence T2a's design-effect convention targets, and it produces real clustering
(many decodes per frequency, pooled over the whole ~6+ hour corpus). The intersection cluster is a
much finer join: it requires the *same exact integer Hz* to recur in the *same 15-second cycle* —
which essentially never happens except by chance collision (`sep` = 0 Hz is on record as the
minimum observed separation, but it is rare) or by the same station transmitting on the identical
integer bin twice in one cycle, which cannot occur for a single decode. **The two clustering
dimensions are, at this level of joins, close to independent — which is itself the answer to a
question the spec asked in passing** (spec §2.1: "neither dimension nests inside the other") and
is consistent with, not contradictory to, everything X4 and X5 have measured so far.

### 3.3 What was deliberately NOT computed

No bootstrap was run after this stop — not the intersection-clustered bootstrap, not the
connected-component diagnostic (ROW 0g), not the coarsened 50 Hz block diagnostic (spec §5.1).
`SE_2way`, `se_2way_branch`, and the gate itself do not appear in `x5_result.json`. This follows
the spec's own instruction literally: computing `sqrt(V_cycle + V_freq)` and reporting it as if it
were a validated two-way estimate, after the check that governs whether the correction term means
anything has just failed, is precisely the "dressing up" the spec names and forbids (§3.2). Nothing
downstream of ROW 0d is reported because nothing downstream of ROW 0d was computed.

---

## 4. What may and may not be said about this result

**May be cited:** that X5 ran to completion of its own pre-registered scope, reproduced X4's
population and every one of X4's published checks exactly (§2), and stopped at the specific,
named, pre-registered ROW 0d bar — a bar the Architect set before seeing this number and whose
consequence (retirement) he pre-committed to in the same document. That the intersection clusters
being near-singletons is itself informative about the corpus's dependence structure (§3.2).

🛑 **May not be cited:** any value of `SE_2way`, `E_sep` under a two-way correction, or any ROW
1/2/3/4 read — none was computed. `E_sep` = +46.039 pp remains exactly as uncitable as X4 left it;
X5 does not rehabilitate it and does not further condemn it — it simply never reaches the gate that
would have done either.

---

## 5. Predictions scored (spec §6)

Prediction scoring on `E_sep` itself was pre-suspended (spec §6, P1a precedent) and is not revisited
here. Of the five registered predictions, four were never reached because the arm stopped at ROW 0d,
before the gate they were about:

| # | prediction | type | reached? | verdict |
|---|---|---|---|---|
| 1 | `SE_2way` ∈ [1.3, 1.8] pp ⇒ ROW 0f passes | magnitude | not computed | **N/A — not reached** |
| 2 | `se_2way_branch` == `"CGM_OK"` | categorical | not computed | **N/A — not reached** |
| 3 | mean decodes/intersection cluster ∈ [1.0, 1.3] ⇒ ROW 0d passes | magnitude | **reached** | **MIXED → scored MISS**, see below |
| 4 | largest connected component ≥ 99% ⇒ §3.3 route closed | magnitude | not computed | **N/A — not reached** |
| 5 | `SE_block` ∈ [1.5, 3.0] pp | magnitude | not computed | **N/A — not reached** |

**Prediction 3, scored in detail:** the raw interval, [1.0, 1.3], contains the measured 1.0053 —
the Architect correctly anticipated near-singleton intersection clusters, continuing the pattern
noted in his own calibration table that interval width, not direction, is his strength. But the
prediction's stated consequence — *"ROW 0d passes"* — is the operative, actionable half of the
claim, and it is wrong: 1.0053 sits under the 1.05 bar he set in the same document. Scored as a
**MISS** on that basis: the number a reader would act on (does the arm proceed?) came out opposite
to what was predicted, even though the raw magnitude estimate was accurate. This extends, rather
than breaks, the pattern flagged in the spec's own §6 calibration note — the last several magnitude
calls have gotten the interval right and the actionable implication wrong or reversed.

**1 of 1 scorable prediction, scored as a miss on its consequence.** No other row is available to
score.

---

## 6. 🔴 Consequence — spectral locality is RETIRED PERMANENTLY

Spec §4.1, quoted in full: *"Spectral locality is RETIRED PERMANENTLY if X5 reaches ANY outcome
other than a clean ROW 1, ROW 2 or ROW 3 read. That includes, without limitation: any ROW 0 void;
ROW 4; **a stop for re-registration under 0d**; an escalation under §3.3; or any outcome not
enumerated in this document. There is no fifth design, no further metric on this data, and no
sixth attempt."*

X5 stopped at ROW 0d. That is not an unenumerated outcome requiring a ruling — it is the first item
named explicitly in the catch-all list, in the Architect's own document, pre-committed before this
number existed. **This report states that the rule has fired; it does not ask whether it should
have.** Per spec §4.1's own closing instruction ("QA does not escalate for a fifth ruling"), this
is not escalated as a decision. It is reported as a closure:

- **Spectral locality (LOCAL vs DIFFUSE crowding cost) is retired permanently.** No fifth design.
  No further metric may be run against this question on this data, under any name.
- **`E_sep` = +46.039 pp remains permanently uncitable** as a measurement of anything. It was a
  point estimate whose own uncertainty could never be validly established under either of X4's two
  marginal clustering assumptions or X5's intended joint one — the question of whether crowding's
  cost is delivered locally or diffusely is now unanswered and, per this closure, will stay
  unanswered from `ALL.TXT`.
- **What survives, unaffected:** X1 (band, `B_std` = +5.70 pp) and X2 (crowding as an aggregate
  cost, `F_std` = +17.22 pp) are both closed, ROW 1 results and neither depended on this arm. The
  D-001 finding that crowding is a real, first-order term stands; only the *mechanism* question
  (which the LOCAL/DIFFUSE split was trying to answer) is now permanently unresolved rather than
  merely open.
- **No `src/` recommendation follows from this closure, in either direction** (spec §7) — this was
  always analysis-only, and remains so on close-out.

---

## 7. Standing bars this arm did not cross

Per spec §7, unaffected by this outcome: subtract-and-resynthesise stays dead; the shipped
waterfall-domain suppression stays out of scope; no `src/` recommendation, no parameter sizing, no
capture run follows from this report, in any form. The band-edge exclusion and the "quote sep as an
upper bound" caveat (HK-021(h)) are moot here — neither was reached.

## 8. NFR-021

This report and `x5_result.json` carry counts, rates, cluster sizes and Hz/cycle-timestamp-derived
statistics only. No callsign or message text appears in either artefact — X5 never reads message
text at all (unlike X4, which used it only to build match keys inside the imported `x4.load_ref()`/
`x4.build_records()`, themselves untouched here).
