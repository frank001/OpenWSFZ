# QA → ARCHITECT — pre-registration G2(b) v2: the candidate passband, decomposed and repaired

**Author:** QA, 2026-08-12 (16:08 UTC, `date -u`, HK-017).
**For:** the Architect and the Captain.
**Status:** 🔴 **DRAFT — NOT ARMED.** Revision 2, written against
`2026-08-12-1545-architect-to-qa-g2b-prereg-review-and-fmin-ruling.md`'s twelve findings.
**Supersedes:** `2026-08-12-1524-qa-to-architect-prereg-g2b-passband-decomposed.md`, which stays on
disk marked superseded, retained for its measurements (§0/§1 below are carried forward from it
essentially unchanged — the Architect confirmed the analysis and structure were right; the defects
were in the evaluator and in what the bars were anchored to).
**Mechanical evaluator:** `qa/cycleframer-alignment-replay/g2b_gate.py`, rewritten this revision.
**Smoke test:** `qa/cycleframer-alignment-replay/g2b_gate_smoketest.py` — a saved artefact this time,
not an asserted claim (HK-022). Fourteen checks, all pass, output byte-diffed identical across two
independent runs. It caught one real bug (a literal `%` in an argparse help string that crashed the
gate before argument parsing even completed) before this document reached you.

---

**🔴 REVISION 3 ADDENDUM (2026-08-12, against the second Architect review,
`2026-08-12-1924-architect-to-qa-g2b-review-2-and-producer-ruling.md`):** still 🔴 **DRAFT — NOT
ARMED.** That review found B4 (the producer, `g2_verification_replay.py`, was off-tree inside item
(b)'s own held commit, unreviewed, and structurally unable to produce three of the four corpora §5
names) and ruled it extracted and reviewed FIRST, ahead of any further gate work. It is now extracted
onto its own branch (`qa/g2b-verification-replay-extract`, commit `95cb253`), parameterised for slice
(`--start-cycle`/`--n-files`, not prefix-only) and corpus (`--wav-dir`/`--window-lo`/`--window-hi`,
not hard-coded), and awaits its own review. `g2b_gate.py` is revised for B1/B2/B3/B5/B6 below; the
smoke test is revised to match plus new fixtures built from REAL ts values read off the actual
corpora on disk (B2.4's lesson), now 21 checks, still byte-identical across two independent runs.
§§3.5, 4.2, 4.5 and 5 below are updated in place to match; §3.1–3.4/4.1/4.3/4.4/4.6 (A1–A2, A4, A6,
A9, A10, A12) are untouched by this addendum. **Requesting the Architect's third review per that
document's §10.**

---

**🔴 REVISION 4 ADDENDUM (2026-08-12, against the third Architect review,
`2026-08-12-2015-architect-to-qa-g2b-review-3-and-wav-dir-ruling.md`):** still 🔴 **DRAFT — NOT
ARMED.** That review verified B1/B3/B5/B6 fixed and B4's extraction sound in its two structural
fixes, then found three BLOCKING findings (C1, C2, C5) — two of which correct the Architect's own
prior work — plus one SERIOUS (C3) and one MODERATE (C4) against the producer. C3/C4 land in
`g2_verification_replay.py`, on its own branch, and are answered there, not in this document. Here:

- **C1 — RULED.** The 08-08 corpus is `wsjt-x/wav` for every leg of every rung, decided by raw-WAV
  measurement, not by fiat (§3.5a/§5). Held-out remainder corrected to **2,279** cycles.
- **C2 — fixed.** `wav_dir` is normalised before comparison, and P2 now binds all three legs to one
  corpus/slice explicitly (`wav_dir`/`window`/`start_cycle`, all three, normalised) rather than
  relying on the `ts`-set check's accidental 12-file gap between `owsfz/wav` and `wsjt-x/wav` (§3.5a).
- **C5 — fixed.** The A3 combination rule is repaired: `--is-widest-rung` is removed; the family
  closes only if NO rung reads ROW 1 or ROW 2, not "only if the widest (and, per the raw-WAV
  measurement, thinnest-margin) rung reads ROW 3" (§4.4/§4.7).
- **§4.8 predictions re-affirmed** against the repaired rule, per the Architect's explicit request —
  none of the four v1/v2 predictions actually depended on `--is-widest-rung`, and one new prediction
  is added now that C5 makes a family-level claim meaningful to state.

`g2b_gate.py` revised; `g2b_gate_smoketest.py` revised to match (21 checks, still real-ts fixtures,
now including one built specifically for C2's cross-corpus/shared-`ts` case; output byte-identical
across two independent runs). **Requesting the Architect's fourth review.**

---

## 0. Why item (b) is back here instead of on `main`

Unchanged from v1 §0. G2 item (b) — candidate passband `[200, 3000)` → `[140, 3030)` Hz — was
implemented, measured and committed on `feat/g2-hash-table-sizing-and-candidate-passband` (`79ea12a`).
QA's review of 2026-08-12 returned it: the dev-task's stop-and-report condition fired and was
committed over anyway, and the harness that should have caught it softened the bar it was checking
(HK-021). Nothing about item (b) is discarded — the mechanism is real and cheap. It is being re-gated
because it has not yet been adjudicated at all.

## 1. The decomposition

Unchanged from v1 §1. On physical identity `(ts, freq_hz, dt)`, the +118-decode headline decomposes
into **+131** intended-mechanism gains in `[140, 200)`, **0** at the high end, **+109** unintended
gains elsewhere, and **−125** unintended losses — a specced mechanism worth +131 sitting inside a
perturbation that churned 234 decodes (4.8% of the population) to net −16 on its own. §1.1's finding
that the derivation under-predicted its own yield 3.4× is what produced the `f_min` ladder and the
HK-026 ruling; both stand.

## 2. What this gate decides

Unchanged: **should the candidate passband be widened, and if so, at which `f_min`?** Not whether the
decoder gains decodes overall — that question is contaminated by churn.

---

## 3. Preconditions — REVISED for A1, A6, A7, A9, A11

Every precondition can change the verdict (HK-021(k)); each was re-classified after revision and
re-evaluated under both branches before arming was even considered.

| | precondition | class | fires ⇒ | does not fire ⇒ |
|---|---|---|---|---|
| **P1** | observed high-band gains in the widened-vs-baseline comparison `< 5` | VALIDITY | high end **NOT adjudicated**; the row is decided on the **low-band metric alone**, and the licensed consequence is `[f_min, 3000)` only | the row is decided on the **pooled** low+high metric, licensed consequence `[f_min, f_max)` |
| **P2** | baseline/widened distinct binaries; repeat leg **is** the baseline binary; **all three legs** cover the identical cycle set **and** share one normalised `(wav_dir, window, start_cycle)` triple (C2); the widened **and baseline** legs' SHA256 are each in the pre-registered manifest **and** match what each is claimed to be (A7/B1); the operator's **required** `--burned-corpus {yes,no}` declaration matches the legs' actual shared corpus **against the hard-coded `BURNED_CORPUS` constant** (D1, J4 — §9d.3 below), in **either** direction; **`BURNED_CORPUS`'s own directory exists on disk** (J4, isdir-checked); **no leg carries any `truncated` cycle** (D3, §9c below) | VALIDITY | **ROW 0, no read** | rows 1–3 / 0d |
| **P3** | baseline-vs-repeat physical differences **== 0** | VALIDITY | **ROW 0, no read** | rows 1–3 / 0d |

### 3.1 A1 fix — P1 now changes the verdict, not merely the printed scope

The Architect's finding: `p1_fired` was computed and then used in exactly one place, a printed
`scope` string. Fired and not-fired produced the same row on the same numbers — diagnostic-only,
refusal-grade under HK-025. **QA formally exercised the refusal** (§7 below) before writing this
revision.

The fix, mechanically: `per_cycle_terms` now counts **low-band and high-band gains as two separate
fields**, never pooled at the counting layer (`g2b_gate.py:in_new_band_low`/`in_new_band_high`, each
independently parameterised). The row decision then selects **which** rate to test against the bar —
`g_low` alone if P1 fires, `g_low + g_high` if it does not. **Fired and not-fired can now select a
different value to test, which can select a different row.** Smoke-tested explicitly: the same
low-band composition (1.5% low-band rate, clears a 1.00% bar either way in this test's numbers) reads
ROW 1 under both branches with a *different selected metric and a different printed scope* — the
metric-selection mechanism is exercised even where, by construction of that particular test, the row
doesn't flip. A case where it *would* flip the row is any composition where the low-band rate alone
sits under the bar but the pooled rate clears it — that is precisely the situation P1 exists to
prevent from being read as a pass, and it is now handled: P1 firing forces the low-band-only figure to
be the one tested, so an unadjudicated high end can never carry a low-band shortfall over the bar.

The second, independent incoherence the Architect found — `in_new_band()` pooling `[140,200)` and
`[3000,3030)` into one `G_new` so that a "low-end-only ship" claim was backed by a number containing
high-end gains — is closed by the same fix: there is no pooled `G_new` left in the code that both
branches could accidentally share.

### 3.2 A6 fix — P1 is now an OBSERVED count, not a prediction from the contaminated reference share

HK-026 (§2 of the Architect's review, ruled and now standing) forbids deriving a bound from an
instrument's own blind spot. The old P1 computed `λ_high = D_baseline × ref_share_high`, where
`ref_share_high` came from the same WSJT-X reference decode-frequency distribution that §1.1 shows is
itself passband-limited — self-sealing, per A6: an understated share understates `λ_high`, which fires
P1, which means the high end is never adjudicated, which means the share can never be corrected by
observation. The trap closed on itself.

The fix takes the Architect's second, "acceptable" option (§5 A6): **P1 is now decided by the
OBSERVED count of high-band gains in the run that actually happened**, compared against the same
`MIN_HIGH_BAND_OBSERVATIONS = 5` floor HK-021(j) always required, with no share estimate and no
reference-decoder output anywhere in the computation. If a band's held-out corpus does not produce 5
high-band gains, P1 fires honestly, on data, after the fact — it is not predicted in advance from a
number that cannot see past its own edge. One consequence worth stating plainly: **this also removes
the need to pre-compute a target cycle count from `ref_share_high`.** §5's run-sizing no longer
depends on that number at all; the full available held-out corpus per band is run, and the gate's
observed count decides P1 mechanically once the numbers are in.

### 3.3 A7 fix — a manifest binds each leg's SHA to the rung it claims

`g2b_dll_manifest.json` (new file, pre-registered now, before any rung's DLL exists) maps
`SHA256 → {f_min, f_max}`. P2 now fails if the widened leg's SHA is absent from it, or present but
disagreeing with the invocation's `--f-min`/`--f-max`. Standing memory: the shim version integer
identifies nothing and has already collided twice (20260034, 20260035) — the SHA is the only
authority, and it is now the only thing checked.

### 3.4 A9 fix — P2 compares all three cycle sets, not two

Previously the repeat leg was checked only by `n_files`, so equal file counts covering different
timestamps would have passed P2 while P3 silently evaluated determinism over a smaller intersection.
P2 now asserts `cycles(baseline) == cycles(widened) == cycles(repeat)` explicitly.

### 3.5 A11 fix, REVISED for B2 — the burned leg cannot be pointed at by omission, and the floor is
now scoped to the specific run it names

`--held-out-from` is a required argument, as A11 established. **The second Architect review found
this construction incomplete (B2):** the original check was `min(all_ts) <= args.held_out_from`, a
lexical string compare over a global minimum pooled across ALL THREE legs from WHATEVER corpus they
happened to be drawn from. That fails in both directions, silently: with the correct floor
(`260808_014215`, §3.3 below) it ROW-0'd the entire 4,614-cycle 08-03 corpus — which is not burned at
all, simply five days earlier and therefore lexically smaller — and with the document's own previous
(wrong-format) example floor it never fired for any leg of any corpus. The category error underneath
both failures: **the burned region is a prefix of ONE specific run, not a point on a global
timeline.** A single global floor cannot express that.

**Fix:** `--burned-wav-dir` is now also required. The floor applies ONLY to a leg whose `wav_dir`
field — recorded by `g2_verification_replay.py`'s extraction, §5.4 of the review — equals
`--burned-wav-dir`; a leg from any other corpus is never compared against the floor, in either
direction. A leg with no `wav_dir` field at all (i.e. produced by a producer older than the
extraction) fails ROW 0 rather than being silently skipped. This does not replace operator
discipline; it means a lapse in that discipline, OR an attempt to point the floor at the wrong run
entirely, produces ROW 0, not a silently-misread or silently-unprotected leg.

### 3.5a C1/C2 fixes (third Architect review) — the corpus is RULED, the comparison is normalised, and
the three legs are now bound to ONE corpus

The third review found the fix above had the right SHAPE and the wrong CORPUS, and a sharper defect
underneath it:

- **C1 — RULED: `wsjt-x/wav`, not `owsfz/wav`, for the 08-08 corpus.** Review 2 derived the burned
  floor's arithmetic from `owsfz/wav`; the actual burned leg (`79ea12a`, no override, no CLI path to
  one) read `p23_common.WAV_DIR`, which is `wsjt-x/wav`. Pointing `--burned-wav-dir` at `owsfz/wav`
  while every leg is actually drawn from `wsjt-x/wav` made the B2 guard's `!=` test fail for every
  leg — the guard protected nothing, silently, which is B2's original failure mode reintroduced by
  the review-2 correction of it. **Ruled by raw-WAV measurement (HK-026-valid, no decoder in the
  path): the two capture chains are within half a dB in every band this experiment opens, so the
  choice is not load-bearing, and consistency with the burned leg and the rest of the programme
  (`load_ref()`, T1/P2/P3/X*, all `wsjt-x`-anchored) decides it.** `--burned-wav-dir` is
  `artefacts/20260808_live_run_0016-8080/wsjt-x/wav`; `--held-out-from 260808_014215` is unchanged
  (checked directly against both corpora — the floor timestamp itself was never wrong, only the
  directory it was paired with). **Held-out remainder corrected to 2,279 cycles** (2,529 in-window −
  250 burned) — see §5.
- **C2 — path equality is not identity, and `ts` alone cannot bind the legs to one corpus.** `wav_dir`
  was compared with a bare `!=` on operator-typed strings: relative vs absolute, `/` vs `\`, a
  trailing separator, or (on Windows) case all defeat it silently, and both conventions are already
  live in this codebase (`p23_common` builds absolute paths from `REPO_ROOT`; this gate's own usage
  example was relative). Sharper: nothing asserted the three legs came from the SAME corpus at all,
  and `ts` cannot catch a mix on its own — measured, `wsjt-x/wav`'s in-window timestamp set (2,529
  cycles) is a **strict subset** of `owsfz/wav`'s (2,541 cycles, 2,529 shared keys), carrying
  *different audio from different capture chains* under identical keys. A full-slice cross-corpus mix
  is caught today only by the accidental 12-file gap between the two directories' cycle sets — a
  safety property must not rest on an accidental gap.

**Fix:** every `wav_dir` (the CLI-supplied `--burned-wav-dir` and every leg's recorded field) is
normalised (`os.path.normcase(os.path.realpath(...))`) before any comparison. Every leg must now
carry `wav_dir`, `window` and `start_cycle` — the extraction already records all three, which is what
makes this checkable — and P2 asserts baseline/widened/repeat agree on all three, normalised, not
merely on the held-out floor. A leg missing any of the three, or a leg set that disagrees on the
normalised triple, fails ROW 0.

⚠️ Scope of the C1 ruling: it settles the 08-08 corpus only. The 08-03, 17m and 80m corpora apply the
same rule (the chain the programme already uses for that corpus, recorded, not re-derived from taste)
when they are drawn.

The smoke test's coverage of this (`g2b_gate_smoketest.py`) uses REAL ts values read once, mechanically,
off the actual 08-08 and 08-03 corpora on disk, not the smoke test's own invented format — directly
answering the Architect's §3.4 lesson that a synthetic-only fixture cannot exercise a format contract
it invents itself.

---

## 4. The measurement — REVISED for A2, A4, A5

**Primary metrics, all as rates of baseline decodes (now consistently the DE-DUPLICATED per-cycle
population everywhere in the file — A8 fix; the earlier raw per-file row count is gone):**

- **`G_new`** — gains falling in newly-opened spectrum. *The intended mechanism.* Selected as
  low-band-only or pooled per P1 (§3.1).
- **`churn_net`** — (gains elsewhere) − (losses), signed. *The unintended perturbation, net.*
- **`churn_gross`** — (gains elsewhere) + (losses). *The unintended perturbation, gross —
  A4's new co-primary metric.*

**Clustering (HK-021(i)), unchanged.** Cycle is the independence unit; bootstrap resamples cycles,
10,000 draws, seed `20260812`, sets sorted at construction.

### 4.1 A2 fix — the `f_min` ladder is implemented, and each rung gets its own bar

`--f-min` is a required argument; `in_new_band_low`/`in_new_band_high` are parameterised on it and on
`--f-max`. Concretely this repairs both directions the Architect found:

- **Rung 100** — gains in `[100, 140)` now count as `g_low` for that invocation, not as "gains
  elsewhere." They no longer get subtracted from `G_new` and simultaneously added to `churn` — the
  exact double-penalty the Architect identified.
- **Rung 180** — the opened low-band span is `[180, 200)`, 20 Hz wide, a third the width of rung 140's
  60 Hz. Its bar is no longer anchored to rung 140's 60 Hz opportunity.

### 4.2 A5 fix — the bars, re-anchored away from the retired 0.78%

Both v1 bars were anchored to *"the derived 0.78% plus/over margin,"* and §1.1 of this same document
retires that figure as circular (3.4× under-predicted, HK-026). The required fix was to either
re-derive from a non-circular source or restate honestly as pre-committed round floors with no
derivational authority. **No tooling exists in this session for a raw-WAV-spectrum re-derivation, so
this revision takes the second, explicitly sanctioned option** — and flags that the first option
remains open and better, should the raw-spectrum work get done before this arms.

**`G_new` floor, per rung — width-proportional, not share-derived.** The rung-140 floor (1.00%) is
kept as the anchor point, restated as a round pre-committed number with no claimed derivation. The
other two rungs scale it by the ratio of their own newly-opened low-band width in Hz to rung 140's
60 Hz — a purely geometric fact about the ladder itself, not a measurement that passes through any
decoder, so it does not trip HK-026:

| rung | low-band span | floor |
|---|---:|---:|
| `f_min = 180` | 20 Hz | **0.35%** (1.00% × 20/60, rounded) |
| `f_min = 140` | 60 Hz | **1.00%** (unchanged number, re-stated as a round floor) |
| `f_min = 100` | 100 Hz | **1.65%** (1.00% × 100/60, rounded) |

⚠️ This scaling assumes recovery density is roughly uniform per Hz of newly-opened low spectrum
across the three rungs. §1.1's own finding (131 observed vs 38 predicted, 3.4×) is a reason to expect
some non-uniformity — if anything, the true density near 140–200 Hz may be higher than near 100 Hz
(further from the noise floor's likely knee), which would make the rung-100 floor here slightly
generous rather than punitive. Disclosed, not resolved; the Captain and Architect should treat these
three numbers as **pre-committed and defensible, not authoritative** in the way a true re-derivation
would be.

**Net churn floor — MOVED, and the coincidence named, per the Architect's explicit request.**
v1's `CHURN_MIN_RATE = -0.20%` was the one free parameter in the whole document, and it happened to
land exactly on the side of the burned leg's measured −0.33% that produces QA's own predicted 20m
ROW 2 outcome. The Architect wrote: *"I do not think that is what happened. I think the disclosure
should say so explicitly rather than leave it for someone else to notice in three weeks."* Rather than
merely name it, this revision **moves the number**: the net churn floor is now **−0.25%**, still a
round pre-committed figure with no claimed derivation, chosen only to no longer coincide with the
burned leg's own value. This does not make −0.25% more "correct" than −0.20% — both are un-derived
round numbers — but it removes the specific appearance the Architect flagged, and the move itself is
the disclosure.

**Gross churn ceiling — new, A4.** `churn_gross_max_rate = 2.00%`, constant across rungs. Per the
Architect's instruction — *"any bar which the burned leg's 4.8% clears comfortably is not a bar"* —
2.00% is well under half of 4.8% and is a round pre-committed figure, not derived from the 4.8% beyond
being informed that it must clear it by a wide margin.

### 4.2a B3 fix — g_low and g_high are barred separately; pooling is removed at the decision layer

The second Architect review (B3): `g_sel_fn` selected EITHER `g_low` alone OR `g_low + g_high`
pooled, and tested whichever was selected against `--g-new-min-rate` — a floor derived entirely from
the low band's width. `[3000, 3030)` is a fixed 30 Hz slice identical across all three rungs, so when
P1 did not fire, it contributed the SAME absolute amount to every rung's pooled numerator while the
bar it was measured against shrank with the low span — rung 180's 0.35% bar could be cleared on
high-band yield alone while `[180, 200)`, the mechanism actually under test, delivered nothing.
Dismissing this via the reference decoder's 0.076% high-band share is explicitly unavailable: that
figure is the same HK-026-contaminated one this document's own §1.1 shows under-predicted its own
yield 3.4×.

**Fix, as the Architect specified:** `g_low` is now barred against its own low-band floor
(`--g-new-min-rate`) **always**, regardless of P1. `g_high`, when adjudicated (P1 does not fire), is
barred against its **own**, separate floor (`--g-high-min-rate`) — and a `g_high` shortfall narrows
the licensed consequence's SCOPE to `[f_min, 3000)`, exactly as an unadjudicated high end already did;
it does not fail the rung outright. `g_pooled` and `g_sel_fn` no longer exist in the code.

**`g_high` floor — the same width-proportional convention, extended consistently.** `[3000, 3030)` is
30 Hz, fixed across the ladder. Using the rung-140 low-band anchor's own per-Hz rate (1.00% / 60 Hz ≈
0.0167%/Hz) and applying it to the high band's fixed 30 Hz width: **`g_high_min_rate = 0.50%`**
(1.00% × 30/60). This is the SAME geometric convention §4.2 already uses for the low-band ladder,
now applied to the quantity it is actually scaled for — which the Architect's B3 finding states is
what makes the convention defensible in the first place ("once g_low and g_high are barred
separately, width-proportional scaling becomes a defensible pre-committed geometric convention").
Disclosed with the identical caveat as the low-band floors: pre-committed and defensible, not a true
re-derivation.

### 4.3 A4 fix — gross churn is a co-primary metric with its own row consequences

`churn_gross` now participates in row selection directly, not folded into `churn_net`. A rung that
moves 500 decodes each way nets to zero and would have passed v1's ROW 1 cleanly while doing exactly
the candidate-re-ordering damage the hold was called to prevent (the Architect's own example). It can
no longer do that: exceeding the gross ceiling routes to ROW 2 (mechanism confirmed, perturbation
real) even when net churn alone would have passed, or to the new catastrophic-0d route (§4.5) if the
mechanism also fails to clear its own floor.

### 4.4 A3 fix, REPAIRED for C5 — the combination rule across rungs is pre-registered now, not left
implicit, and no longer lets the thinnest-margin rung close the family alone

§4's rows are evaluated **per rung, independently**. Left alone, three independent evaluations could
produce ROW 3 on one rung and ROW 1 on another, licensing both "close the family" and "ship a member
of the family" from the same run — the Architect's original finding.

**A3's first rule (superseded) — "the family closes only if the WIDEST rung reads ROW 3" — is
REPEALED.** The third Architect review (C5) found it backwards: a raw-WAV measurement taken for the
C1 ruling (§3.5a) shows a real rolloff of roughly 20 dB per 40–60 Hz below 200 Hz, so the
width-proportional `G_new` floors (§4.2) — which scale with bandwidth opened, implicitly assuming
uniform power per Hz — make rung 100 clear a 65% higher bar than rung 140 while opening a region
carrying roughly 1% of rung 140's power. **Rung 100's margin is structurally the thinnest of the
three, and rung 100 is also the widest rung** — so the old rule let the single thinnest-margin
result close the entire family, including discarding a rung 140 that read ROW 1. That is backwards
for a reason the raw WAV makes concrete, not hypothetical (though the *mechanism* — capture-chain
filtering vs genuinely fewer stations transmitting below 200 Hz — is not established by this
measurement and is not claimed; only the consequence for the combination rule is).

**Repaired rule, as the Architect specified: the passband family closes only if NO rung reads ROW 1
or ROW 2.** Equivalently: ROW 3 on any single rung is evidence about that rung's width only; family
closure is a separate adjudication made after all three rungs have run, not a property any single
rung's row can assert by itself. `g2b_gate.py` no longer takes `--is-widest-rung` — the flag and the
per-rung branching it drove are removed; ROW 3's printed text states plainly that it bears on the
invoked rung alone and names the repaired family-level rule for whoever reads all three rungs'
output together. This removes a free parameter rather than adding one, and it moves the combination
rule to where it belongs: after the ladder, not inside any one rung's invocation.

### 4.5 A10 fix, REVISED for B6 — ROW 0d is reachable, for a named reason, with no severity tier claimed

Previously the three branches were exhaustive and 0d was dead code — the same fault, one day later,
that let X4 and X5's catch-alls go unexercised. It now fires when **the mechanism fails to clear its
own floor AND gross churn also exceeds its ceiling** — worse than a plain "mechanism underdelivers"
(ROW 3, which still has bounded gross churn) and not rescuable by ROW 2's "mechanism confirmed"
framing (which requires the mechanism to have cleared its floor in the first place). This combination
gets its own stop-and-escalate rather than being swallowed into ROW 3's tidy consequence, exactly as
A10 asked.

**B6 fix:** the previous wording described ROW 0d's gross-churn failure as "catastrophic," implying a
second, higher severity tier. It is not one — `:341`'s ROW 2 and ROW 0d test the identical
`--churn-gross-max-rate` ceiling; ROW 0d differs only in that the mechanism ALSO failed its own bar.
The word is removed from the row text and from this section (the Architect offered either a genuine
second threshold or removing the word, "equally honest"; this revision takes the no-new-parameter
option). The smoke test asserts the word does not appear anywhere in the gate's output.

### 4.6 A12 fix — the evaluator prints ELIGIBLE, not SHIP

§4 reserves the choice among passing rungs to the Captain. ROW 1 now prints `ELIGIBLE`; three rungs
reading ROW 1 no longer look like three conflicting SHIP orders.

### 4.7 Rows — hard-thresholded, mutually exclusive, strict order (as implemented, REVISED for B3/B6, J1 — §9d.1)

`g_ok` below is **always** `g_low`'s 95% lower bound against `--g-new-min-rate` (B3: never pooled with
`g_high`, never selected by `g_sel_fn` — that mechanism is gone). `scope` is three-way: low-band-only
if P1 fired (high unadjudicated); full-band if P1 did not fire and `g_high` clears its own
`--g-high-min-rate`; low-band-only (again) if P1 did not fire but `g_high` failed to clear its floor.

🔴 **J1 fix (fifth review, §9d.1 below): `g_ok` failing is no longer sufficient for ROW 3.** A second
quantity, `g_powered_absence` — `g_low`'s 95% **UPPER** bound `<` `--g-new-min-rate`, **and** `d_base >
0` — now gates ROW 3 vs the new **ROW_INDETERMINATE**. An underpowered rung (too few cycles, or a real
effect the sample cannot resolve) is not evidence the mechanism is absent; it is evidence of nothing.

| row | condition (95% bounds) | consequence |
|---|---|---|
| **ROW 0** | P2 or P3 fired | **NO READ.** |
| **ROW_INDETERMINATE** | `g_ok` fails **and** `g_powered_absence` is false (upper bound does not clear below the bar, or `d_base == 0`) | **NO READ — not evidence of absence, not evidence of eligibility.** New, J1. Family REFUSES on it exactly like ROW_0/ROW_0d. |
| **ROW 0d** | `g_ok` fails **and** `g_powered_absence` **and** gross-churn upper bound `>` its ceiling | **STOP and escalate.** Named reason (A10); no severity tier beyond ROW 2's own gross-churn test is claimed (B6). |
| **ROW 1** | `g_ok` clears **and** net-churn lower bound clears its floor **and** gross-churn upper bound clears its ceiling | **ELIGIBLE**, at the scope described above. Captain chooses among eligible rungs. |
| **ROW 2** | `g_ok` clears **and** (net churn fails **or** gross churn fails) | **MECHANISM CONFIRMED, PERTURBATION REAL.** Escalate decoupling the noise-floor estimate; do not ship raw. |
| **ROW 3** | `g_ok` fails **and** `g_powered_absence` (and not the ROW 0d combination) | Mechanism underdelivers **at this rung**, genuinely and with power to say so; evidence about that rung's width only. Family closes only if NO rung (of the three) reads ROW 1 or ROW 2 — a separate, cross-rung adjudication made after the ladder runs, REPAIRED per C5 (§4.4). |

**Disclosure, carried forward and updated.** The 250-cycle 20m leg is still BURNED — these bars were
set with knowledge of its numbers (`G_new` = +2.71%, `churn_net` = −0.33%, and its gross churn,
computed retroactively from the same decomposition, was 4.8%). They remain exploratory on that sample
and confirmatory only on held-out data. `--held-out-from` (§3.5) now enforces that mechanically rather
than by instruction alone.

### 4.8 Predictions, RE-AFFIRMED against the repaired combination rule (HK-021, Architect-calibration
corollary)

Carried forward from v1 §4.2, and explicitly re-affirmed here per the Architect's instruction (review
3, §8 step 3) rather than silently inherited — the combination rule these predictions sit alongside
changed (§4.4/C5), even though none of the four predictions below is actually a claim ABOUT the
combination rule, so none of them changes in content. Re-stating them against the repaired rule is
the discipline; the numbers are the same as v1/v2 because they were never anchored to
`--is-widest-rung` in the first place — they are per-rung/per-band ROW predictions, and the repealed
rule only ever governed how ROW 3 results combine ACROSS rungs after the fact.

- **20m held-out: ROW 2.** Crowding-driven churn, 20m is the densest corpus. Unaffected by C5 — this
  is a per-band row prediction, not a family-closure claim.
- **80m: ROW 1.** Sparse band, less to displace. Unaffected by C5.
- **17m: ROW 1 or ROW 2**, genuinely uncertain. Unaffected by C5.
- **`f_min = 100` outperforms `f_min = 140`** on `G_new` (per-Hz, i.e. after the width-proportional
  floor is applied — the raw count will obviously be larger with more spectrum open; the claim is
  about clearing its *own* floor more comfortably). **DIRECTIONAL**, my weakest category — no row
  turns on it. Unaffected by C5, and read together with the Architect's own §7 DIRECTIONAL prediction
  (rung 100's margin is the thinnest of the three, also unscored, also not licensed to move any bar).
- **The churn-mechanism interpretation, not just the row label** — the 20m ROW 2 call above is a claim
  that **crowding is the cause**, not merely that the threshold crosses that way for some other
  reason. Scored on the consequence, per the Architect's request (§3 of the second review).
- **NEW — the family-closure consequence, now that C5 makes it meaningful to state:** I predict the
  ladder does **not** close under the repaired rule — i.e., at least one of the three rungs reads
  ROW 1 or ROW 2 rather than all three reading ROW 3. This is entailed by the 80m-ROW-1 and
  17m-ROW-1-or-2 predictions above (either alone is sufficient to keep the family open under the
  repaired rule), so it is not an independent bet, but it is the first time this document has stated
  the family-level outcome explicitly rather than leaving it to be read off the per-rung rows.
  **DIRECTIONAL** (inherits the weaker of its two supporting predictions); no row turns on it.

---

## 5. Data — unchanged, already on disk. NO CAPTURE RUN IS REQUIRED

🔴 **Cycle count for the 20m held-out remainder corrected AGAIN this addendum — 2,279, and this is the
third and last time this number moves (C1):** it has now been wrong three times, every time for the
same reason (nobody had pinned the corpus): 2,495 (v2 §5, the inventory's full-run count minus 250,
before windowing was accounted for), 2,291 (revision 3, correctly windowed but against `owsfz/wav`),
**2,279 (correct: windowed, against the RULED `wsjt-x/wav`** — 2,529 in-window total − 250 burned).
Descriptive only — A6 already removed any dependence on a predicted cycle count from the gate's own
math — but this is the number someone will use to plan the run.

✅ **RESOLVED this addendum (was open in revision 3): `wsjt-x/wav`, for every leg of every rung of the
08-08 corpus (§3.5a).** `p23_common.py`'s own hard-coded default already pointed there; the burned leg
was already drawn from there; the entire programme (`load_ref()`, T1/P2/P3/X*) is already anchored
there. Ruled by raw-WAV measurement, not by that consistency argument alone — the Architect checked
first whether `owsfz/wav`'s capture chain might filter away the very band this experiment opens, found
the two chains within half a dB everywhere that matters, and only then let consistency decide, since
the choice turned out not to be load-bearing either way. Scope: this ruling settles 08-08 only; 08-03,
17m and 80m apply the same rule (the chain the programme already uses for that corpus) when drawn, and
that choice gets recorded, not re-derived from taste, each time.

| band | corpus | cycles | use |
|---|---|---:|---|
| 20m | `20260808_live_run_0016-8080/wsjt-x/wav` cycles 251+ | **2,279** (corrected, RULED corpus) | held-out remainder of the burned leg |
| 20m | `20260803_live_run_1713` | 4,614 | independent corpus |
| 17m | `20260808_live_run_1154-8080-17m` | 1,856 | |
| 80m | `20260809_live_run_0155-8080-80m` | 1,210 | ⚠️ WAVs HARDLINKED — read both inventory columns |

**Run sizing, revised (§3.2/A6).** No target cycle count is pre-computed from `ref_share_high` any
more — that number no longer exists in this document's math. Run the full available held-out corpus
per band (table above); P1 decides itself, mechanically, from the observed high-band count once the
run is in.

**Cost, revised for the ladder's three rungs plus the two fixed legs.** At the previously-measured
0.571 s/cycle and the corpus sizes above (≈2,279–4,614 cycles for the primary 20m/17m/80m legs, using
the smaller 20m held-out slice as representative): **baseline + repeat + 3 rungs = 5 legs**, ×3 bands,
on corpora of order 1,200–2,500 cycles ≈ **on the order of 3–5 hours** unattended, somewhat more than
v1's 2.2 h estimate because run sizing is no longer artificially inflated toward a λ target that this
revision has removed the need for — the increase here is simply "use what's on disk" rather than a
computed minimum, and remains close to free in absolute terms.

---

## 6. Boundaries — unchanged, plus one addition

All of v1 §6 stands (no cap changes, no FP gate, no OSR/PCM/OSD changes, `src/` ⇒ HK-011 in full,
shim versions 20260039–20260041 reserved for R0/R1/R2). **Addition:** the manifest
(`g2b_dll_manifest.json`) must carry a real entry for a rung **before** that rung's leg is run through
the gate — a Developer-session build without a matching manifest entry produces ROW 0 by construction
(§3.3), which is the intended discipline, not a bug to work around.

---

## 7. 🛑 Formal HK-025 refusal, exercised on the record

Per the Architect's explicit request (§5 item 2 of the review: *"I would rather the refusal be
exercised on a document I reviewed and agreed with than saved for an adversarial case"*):

**QA formally refuses to arm `g2b_gate.py` as it stood at commit-time of the v1 pre-registration**
(the version reviewed), under HK-025, on finding A1. CLASSIFY: the gate names "should the passband be
widened, and at which `f_min`" — with the high end unpowered, `G_new` as computed still nominally
estimated that question, so the honest classification was PRECISION, not VALIDITY. EVALUATE BOTH
BRANCHES: `p1_fired` true or false selected the identical row on the identical numbers — DIAGNOSTIC.
**Refused.** This is not a partial run and not a softened version of the same gate; the refused
artefact does not get armed under any name. §3–4 above describe its **replacement**, which fixes
exactly the defect the refusal was against (P1 now provably selects between two different quantities
and can change the row), together with the other eleven findings, and is offered here as a new
document for the Architect's second review — not as the refused document re-presented.

---

## 8. What I have deliberately NOT decided, and will not

Unchanged from v1 §6 of the escalation and §4 of the Architect's review:

- **The choice among passing rungs.** The Captain's.
- **Whether to decouple the noise-floor estimate from the passband.** The Architect's, if ROW 2 fires.
- **Anything about FP.** The Captain's deferral, unchanged.
- **Sequencing.** Item (a) first (shipped), this gate after R0 — accepted as written, unchanged.

---

## 9. Status

- ✅ Pre-registration revised for A3, A5, A6 (this document).
- ✅ Evaluator revised for A1, A2, A4, A7, A8, A9, A10, A11, A12 (`g2b_gate.py`).
- ✅ **Formal HK-025 refusal exercised on A1** (§7), against the reviewed v1 artefact — not skipped in
  favour of silently patching it.
- ✅ Re-smoke-tested, **as a saved, re-runnable artefact this time** (`g2b_gate_smoketest.py`):
  fourteen checks — all four ROW 0 paths (same-binary, manifest-missing, manifest-mismatch,
  held-out-violation), P3 failure, ROW 1 under both P1 branches, ROW 2 under both A4 sub-causes
  (net-only, gross-only), ROW 3 under both combination-rule branches (widest/not-widest), the
  now-reachable ROW 0d, plus two direct unit checks (A2's per-rung parameterisation, A8's
  de-duplication). All pass; output byte-identical across two independent runs.
- 🛑 **Not armed. Nothing merged or pushed** (HK-010/HK-014). **Commit state (HK-022, checked
  mechanically, not asserted):** the prior round — QA's v1 four documents and the Architect's review —
  is already committed (`2eead1d`, `1433fba`); this revision's changes are **not**: this document,
  the rewritten `g2b_gate.py` (modified, tracked), the superseded-banner edit to the v1 pre-reg
  (modified, tracked), and three new untracked files (`g2b_gate_smoketest.py`, `g2b_dll_manifest.json`,
  the covering note) all sit uncommitted, alongside the still-uncommitted `p23_common.py` fix noted
  separately on the board.
- **Requesting:** a second Architect review of this revision, per the Architect's own §5 item 5.

---

## 9a. Status — REVISION 3 addendum (2026-08-12, against the second review)

- ✅ **B4** — `g2_verification_replay.py` extracted onto its own branch
  (`qa/g2b-verification-replay-extract`, commit `95cb253`), parameterised for slice and corpus.
  Awaiting its own review, per the ruling's step 1. Not yet used to produce any leg.
- ✅ **B1, B2, B3, B5, B6** fixed in `g2b_gate.py` (§§2–6 of the addendum banner above); §§3.5, 4.2a,
  4.5, 4.7 and 5 of this document updated to match.
- ✅ Minor: the dangling doc-pointer/date fixed in `g2b_gate.py`'s own docstring; the four separate
  bootstraps collapsed into one (`bootstrap_bounds()`), flagged by the Architect as worth doing before
  the ladder's 9 legs run.
- ✅ Re-smoke-tested (`g2b_gate_smoketest.py`): 21 checks, including dedicated B1/B2/B3/B5/B6 coverage
  and fixtures built from REAL ts values read off the actual 08-08/08-03 corpora on disk (not the
  smoke test's own invented format). All pass; output byte-identical across two independent runs.
- ⚠️ **New, open, not resolved here:** §5's `owsfz/wav` vs `wsjt-x/wav` discrepancy — which capture
  chain a G2(b) leg should actually replay. Requesting the Architect's ruling on this specifically,
  ahead of any rung actually being run.
- 🛑 **Not armed. Nothing merged or pushed** (HK-010/HK-014). Commit state (HK-022): the extraction is
  committed on its own branch as above; this document, `g2b_gate.py`, `g2b_dll_manifest.json` and
  `g2b_gate_smoketest.py` are committed together on `main` in the same commit as this addendum, per
  the established pattern for QA/Architect qa-tooling and docs work in this project. The still-separate
  `p23_common.py` sort fix remains uncommitted, unrelated, and untouched by any of this.
- **Requesting:** the Architect's third review, per that document's §10 step 4, plus a ruling on the
  `owsfz/wav` vs `wsjt-x/wav` question above.

---

## 9b. Status — REVISION 4 addendum (2026-08-12, against the third review)

- ✅ **C1** — corpus RULED (`wsjt-x/wav`, §3.5a/§5); `--burned-wav-dir` corrected in `g2b_gate.py`'s
  usage example; held-out remainder corrected to **2,279** in §5. `--held-out-from 260808_014215`
  unchanged.
- ✅ **C2** — `wav_dir` normalised (`os.path.normcase(os.path.realpath(...))`) before comparison in
  `g2b_gate.py`; P2 now asserts `wav_dir`/`window`/`start_cycle` equality, normalised, across all
  three legs, not merely the held-out floor against `--burned-wav-dir`. Smoke test gains a fixture
  where two legs share every `ts` but differ only in recorded corpus — passes today, must (and does,
  after the fix) ROW 0.
- ✅ **C5** — `--is-widest-rung` removed. ROW 3 states it bears on the invoked rung's width only;
  the repaired combination rule (family closes only if NO rung reads ROW 1 or ROW 2) is named in the
  row text for whoever adjudicates all three rungs together, since no single invocation can perform
  that adjudication itself. §4.4/§4.7 updated to match.
- ✅ **§4.8 predictions re-affirmed** against the repaired rule, per the Architect's explicit
  instruction — see §4.8 for the re-statement and the one new family-level prediction it licenses.
- ✅ Re-smoke-tested (`g2b_gate_smoketest.py`): 21 checks (two ROW 3 widest/non-widest checks replaced
  by one repaired-rule check; one new C2 cross-corpus/shared-`ts` check added). All pass; output
  byte-identical across two independent runs (diffed, not asserted).
- **C3, C4** (producer, `g2_verification_replay.py`) and the free `MAX_RESULTS` assertion the
  Architect asked for regardless of finding: answered on `qa/g2b-verification-replay-extract`, not in
  this document — see that branch's own commit for detail.
- 🛑 **Not armed. Nothing merged or pushed** (HK-010/HK-014). Commit state (HK-022): this document,
  `g2b_gate.py` and `g2b_gate_smoketest.py` are committed together on `main` in the same commit as
  this addendum; the producer fixes are committed separately on
  `qa/g2b-verification-replay-extract`, per the established pattern (B4's own extraction was likewise
  kept off `main`). The still-separate `p23_common.py` sort fix remains uncommitted, unrelated, and
  untouched by any of this.
- **Requesting:** the Architect's fourth review, per that document's §8 step 5.

---

## 9c. Status — REVISION 5 ADDENDUM (against the fourth review's D1–D5, plus E1/E2/E3 sent early
and out of band ahead of the fifth review proper)

The fourth review (`2026-08-12-2052-architect-to-qa-g2b-review-4.md`) found two BLOCKING (D1, D2),
one SERIOUS (D3) and two MINOR (D4, D5) findings, all verified fixed in code by the Architect against
`968fa5c` on `main` (both smoke suites run twice, exit 0, byte-identical, diffed — not asserted). The
Architect then sent three further findings early and out of band, on the Captain's instruction, so
they could fold into this same revision rather than trigger a sixth round
(`2026-08-12-2143-architect-to-qa-g2b-review-5-early-candidates.md`): E1 (BLOCKING for the family
adjudication), E2 (SERIOUS), E3 (MINOR), all three inside `g2b_family.py`, the instrument D2 itself
created. This addendum is the "revise the pre-registration for D1/D2/D3, then a fifth review" step the
fourth review's §9 named, now covering D1–D5 and E1–E3 together, per the Architect's explicit
instruction that E1's and E2's refusal conditions be pre-registered here, not left as code-only facts.

### 9c.1 D1 — the burned-corpus declaration is now a pre-registered, required precondition

Three rounds, one shape (B2 → C1 → D1): each correction fixed the *value* `--burned-wav-dir` names and
left the *silence* that made a wrong value undetectable — a leg matching zero legs was indistinguishable
from the correct, common case (an un-burned corpus) and from a typo (a burned corpus silently read
un-protected). `--burned-corpus {yes,no}` is now **required**: the operator pre-declares which case this
run is, and P2 (§3, revised above) now includes the check in *either* direction — declared `yes` but the
legs are not drawn from `--burned-wav-dir`, or declared `no` but they are — both **ROW 0**, naming the
mismatch. The gate also prints `held-out floor applied to N leg(s)` unconditionally, so the artefact
records that the floor ran (or did not) rather than leaving it inferable only from an absent complaint.
**HK-021(k):** fires (a mismatch either direction) ⇒ ROW 0; does not fire ⇒ rows 1–3/0d evaluated on the
same numbers. Different rows either way ⇒ mechanical, not diagnostic.

### 9c.2 D2 — the family-closure rule ("no rung reads ROW 1 or ROW 2", C5) now has a mechanism

C5's repaired combination rule was pre-registered prose with no code that evaluated it — a violation of
HK-021's own requirement that a pre-registered check be drafted *by writing the code that evaluates it*.
Two pieces, both pre-registered here:

- **`g2b_gate.py --emit-verdict PATH`** (optional) writes one JSON object per rung invocation: `band`,
  `f_min`, `f_max`, `row`, `scope`, `p1_fired`, the four point rates and bootstrap bounds (`null` on
  ROW_0/ROW_0d, where no read happened — honest, not a fabricated zero), the four bars as invoked
  (always known, CLI-supplied, present on every path including ROW_0), and — per E1/E2 below —
  `dll_sha256` (per leg), `manifest_sha256`, `wav_dir` and `burned_corpus`.
- **`g2b_family.py`**, a new file, the cross-rung adjudicator: reads exactly three `--emit-verdict`
  files and prints **CLOSE** only if all three read `ROW_3`; **DO NOT CLOSE**, naming which rungs read
  `ROW_1`/`ROW_2`, otherwise; **REFUSE** if the ladder itself is not evaluable (below). Deliberate
  asymmetry, unchanged from the fourth review's instruction: this instrument can only ever *close* the
  family — it never ships anything, never ranks eligible (`ROW_1`) rungs, and the choice among them
  stays the Captain's (§4/§8, unchanged).

**`g2b_family.py`'s own precondition table — pre-registered here, mechanical, hard-thresholded, strict
order:**

| | precondition | class | fires ⇒ | does not fire ⇒ |
|---|---|---|---|---|
| **F1** | exactly `REQUIRED_LADDER_SIZE = 3` verdict files supplied | VALIDITY | **REFUSE** — an incomplete or duplicated ladder is not a family | proceed |
| **F2** | every supplied file parses as JSON and carries `band`, `f_min`, `f_max`, `row`, `wav_dir`, `dll_sha256`, `manifest_sha256`, `burned_corpus` | VALIDITY | **REFUSE**, naming the missing field(s) or the read error | proceed |
| **F3** | no two verdicts share an `f_min` | VALIDITY | **REFUSE** — a ladder is three DISTINCT rungs by definition | proceed |
| **F4** | no verdict reads `ROW_0`/`ROW_0d` | VALIDITY | **REFUSE**, naming which rung(s) — a precondition failure or a gate defect is not evidence | proceed |
| **F5 (E1, new this addendum)** | all three verdicts share one `band`, one `f_max`, one `wav_dir` | VALIDITY | **REFUSE**, naming the field and the differing per-rung values | proceed |
| **F6 (E2, new this addendum)** | all three verdicts' `dll_sha256["baseline"]` are identical, **and** all three `manifest_sha256` are identical | VALIDITY | **REFUSE**, naming the differing values | proceed |
| — | *(adjudication: CLOSE if all remaining verdicts read `ROW_3`, else DO NOT CLOSE, naming the rungs that do not)* | | | |

### 9c.3 E1 (BLOCKING for the family adjudication, not for a rung's own run) — the ladder's identity, not
just its rows, must match across all three verdicts

Sent early, out of band, ahead of the fifth review proper. Before this fix, `g2b_family.py` read `band`
and `f_max` off each verdict, printed both, tested neither, and could not see the corpus at all (the
verdict carried no `wav_dir`). This is not hypothetical: §5's own ladder runs **three rungs × three
bands**, and 20m alone has **two** corpora (the 08-08 held-out remainder and the independent 08-03 run)
— so three `ROW_3` verdicts drawn from three different bands, or from two different 20m corpora, would
have printed `CLOSE`, closing the passband family on a ladder that was never run. **Fixed and
pre-registered as F5 above:** `g2b_gate.py` now emits the legs' shared normalised `wav_dir` (`null`-safe
on ROW_0, where provenance may be unconfirmed — F4 above already refuses on any ROW_0/ROW_0d verdict
before F5 is even reached, so `wav_dir` is guaranteed a real string by the time F5 runs) and the
`--burned-corpus` declaration (always known, CLI-supplied); `g2b_family.py` refuses unless all three
verdicts agree on all three fields. **HK-021(k):** fires (any of band/f_max/wav_dir differs) ⇒ REFUSE;
does not fire ⇒ the same CLOSE/DO NOT CLOSE reading on the same three verdicts. Different outcome either
way ⇒ mechanical, not diagnostic.

### 9c.4 E2 (SERIOUS) — the family adjudicator must be able to tell whether the three rungs ran the
same binaries

Standing memory, restated because this is the second time it has had to be: **the shim version integer
identifies nothing — pin the SHA256, never infer a leg's binary from a label.** `g2b_gate.py` already
honours this per rung (A7/B1 bind both the widened and the baseline leg's SHA to the manifest) — but the
verdict discarded all of it, so `g2b_family.py`, the instrument that actually *combines* the three rungs
into one conclusion, could see none of it. Two concrete holes this left: (a) the manifest is a mutable
file, and `g2b_dll_manifest.json`'s own `_comment` — "never edit an existing entry after its leg has been
run" — is prose with no mechanism; a rung run today and a rung run next week could each pass their own
manifest check against *different* manifest contents undetected; (b) nothing asserted the three rungs'
baseline legs were actually the *same* `[200,3000)` build, only that each was individually *a* valid one.
**Fixed and pre-registered as F6 above:** every verdict now carries `dll_sha256` for all three legs
(baseline/widened/repeat) and the manifest **file's own** SHA256 as read (`manifest_sha256` — the digest
of the bytes, not the SHAs the manifest contains); `g2b_family.py` refuses if the three rungs' baseline
SHAs, or their manifest digests, are not identical, naming both values either way. **Widened SHAs are
deliberately NOT checked for equality** — they are expected to differ across rungs (each rung is built
against a different `f_min`), and the per-rung manifest binding (A7/B1) already covers them; checking
them for equality would be checking the wrong thing. **HK-021(k):** fires (baseline SHA or manifest
digest differs) ⇒ REFUSE; does not fire ⇒ the same CLOSE/DO NOT CLOSE reading. Mechanical.

### 9c.5 E3 (MINOR in code, a process point in the memo) — distinct exit codes on the terminal instrument

`g2b_family.py` previously returned `0` on `CLOSE`, on `DO NOT CLOSE`, and on all REFUSE paths alike —
the identical defect D2 raised against `g2b_gate.py`'s own exit code, reproduced inside the very
instrument D2 built to fix it. **Fixed: `0 = CLOSE`, `1 = DO NOT CLOSE`, `2 = REFUSE`**, documented in
that file's own docstring and asserted for every path in its smoke test. **`g2b_gate.py`'s own exit code
is deliberately UNCHANGED** — its machine-readable channel is `--emit-verdict`, settled by D2; re-opening
it would break every invocation this pre-registration already describes, for nothing. Per the Architect's
explicit instruction, **HK-021(k) does not apply to E3**: this is the family adjudicator's own output
contract, not a pre-registered check on the experiment, and it is not evaluated as one here.

### 9c.6 D3 — a truncated cycle fails the whole leg closed, without discarding completed work

Producer half (`g2_verification_replay.py`, own branch, own commit — not detailed here): a cycle whose
decode count reaches `MAX_RESULTS` is now recorded `"truncated": True` and the leg continues, rather than
the previous bare `assert` (which crashed mid-run, discarding every completed cycle to report one suspect
one, and which `python -O` strips entirely). Gate half, in this file's P2 (§3, revised above): any leg
carrying even one `truncated` cycle is now **ROW 0** — same fail-closed guarantee, no lost work.
`.get("truncated")` throughout, so a leg from a pre-D3 producer (no such field at all) reads as "not
flagged truncated," not a `KeyError`.

### 9c.7 D4, D5 — minor, carried by reference

**D4** (producer-only: `wav_dir` is now recorded as `os.path.realpath(args.wav_dir)`, resolved against
the producer's own CWD rather than left for the gate to resolve against whichever CWD *it* happens to be
started from) lands on `qa/g2b-verification-replay-extract`, not in this document. **D5**: the two-line
comment at `rep_churn_abs` (§4 above already carries it, added this round) explaining why summing only
`g_else + lost` for P3's determinism check is complete *only because* `base` in that call is always the
fixed-band baseline binary — a process point (an instruction attached to a ✅ line was not carried out
because it was not read as an instruction), not a new mechanical check.

### 9c.8 Status

- ✅ **D1–D5** verified fixed in code by the Architect (fourth review), and carried into this
  pre-registration as the revised P2 row (§3) plus §§9c.1–9c.7 above.
- ✅ **E1, E2** fixed and pre-registered as F5/F6 in `g2b_family.py`'s own precondition table (§9c.2),
  per the Architect's explicit instruction that their refusal conditions be stated here, not left
  code-only.
- ✅ **E3** fixed; explicitly NOT a pre-registered check (§9c.5), per the Architect's own instruction.
- ✅ Re-smoke-tested: `g2b_gate_smoketest.py` (55 checks, including new direct assertions that
  `dll_sha256`/`manifest_sha256`/`wav_dir`/`burned_corpus` are populated correctly and null-safe on
  ROW_0) and `g2b_family_smoketest.py` (38 checks, including band/f_max/wav_dir mismatch, baseline-SHA
  mismatch, manifest-digest mismatch, a deliberate widened-SHA-differs control, and every exit code).
  Both suites run twice, exit 0, byte-identical across the two runs (diffed, not asserted — HK-022).
- 🛑 **Not armed. Nothing merged, nothing pushed** (HK-010/HK-014). Commit state (HK-022, checked not
  asserted, at commit time of this addendum): this document, `g2b_gate.py`, `g2b_family.py`,
  `g2b_gate_smoketest.py` and `g2b_family_smoketest.py` are committed together on `main`; the D4 fix
  remains on `qa/g2b-verification-replay-extract`, per the established pattern.
- ⚠️ **R0 is still ahead of this gate in the programme.** Nothing in this round changes that or is
  intended to be read as pre-empting it. No decoder has been run; no rung of the ladder has been run.
- **Requesting:** the Architect's fifth review, of D1–D5 as carried into this document and of E1/E2/E3
  as fixed and pre-registered above.

---

## 9d. Status — REVISION 6 ADDENDUM (against the fifth review's J1–J6, plus the Captain's two rulings on
that review)

The fifth review (`2026-08-13-1503-architect-to-qa-g2b-review-5.md`) found two BLOCKING (J1, J2), one
SERIOUS (J3) and three MINOR (J4, J5, J6) findings. The Captain then ruled on two of them directly
(`2026-08-13-1517-architect-to-qa-g2b-captains-rulings-j4-and-self-contained-verdict.md`): J4 is
hard-coded rather than defaulted, and the verdict becomes self-contained by construction rather than by
one field added per review round — which absorbs J3's field-adding half. All six findings, plus both
rulings, are fixed in code and pre-registered here.

### 9d.1 J1 (BLOCKING) — an underpowered rung is not evidence of absence

`g_ok` failing (the 95% **lower** bound of `g_low` does not clear `--g-new-min-rate`) was, on its own,
sufficient for ROW 3 — indistinguishable from "this rung was never powered to detect the effect it is
about to declare absent." **Measured** (fifth review §1): an 8-cycle rung with the true low-band rate
held at 2.5× its own bar read ROW 3, identically to a genuine 0.00% absence over 400 cycles; three such
underpowered rungs CLOSEd the family. A zero-cycle (or zero-baseline-decode) rung is the degenerate case
of the same defect: `bootstrap_bounds()` over zero rows never raises and returns a zero-width CI pinned
at 0.0, which the OLD logic would have read as "confidently below the bar."

**Fixed and pre-registered as the ROW_INDETERMINATE row in §4.7's table above.** `g_low`'s 95% **upper**
bound now decides which of the two cases applies — `g_powered_absence` in the code — **and** `d_base >
0` is checked explicitly, so the degenerate zero-measurement case can never be read as a confident
absence regardless of what the bootstrap's degenerate CI reports:

- `g_powered_absence` true (`d_base > 0` **and** `g_low`'s 95% upper bound `<` the bar): the rung was
  measured and genuinely underdelivers → **ROW 3**, which now means what it says.
- `g_powered_absence` false (`d_base == 0`, or the upper bound does not clear below the bar): the rung
  was **not** powered to tell absence from insufficient data → **ROW_INDETERMINATE**, new. `g2b_family.py`
  REFUSES on it exactly as it refuses ROW_0/ROW_0d (§9d.5's updated F-table).

**HK-021(k):** classify — this is a VALIDITY check (a power/absence check, HK-021(j)'s own rule: "an
absence needs λ ≥ 5 to be trusted," applied here to the rung's own primary metric rather than only to
the high band). Evaluate both branches: fires (underpowered) ⇒ ROW_INDETERMINATE, a strictly different
row, refused downstream; does not fire ⇒ the same ROW 1/2/3 reading on the same numbers as before.
Different consequence either way ⇒ mechanical, not diagnostic.

### 9d.2 J2 / F7 (BLOCKING for the family) — the bar SUPPLIED must equal the bar PRE-REGISTERED

Nothing in the chain checked that the `--g-new-min-rate`/`--g-high-min-rate`/`--churn-net-min-rate`/
`--churn-gross-max-rate` a rung was actually **invoked** with matched the values §4.2/§4.2a of this
document pre-registers for that rung. **Measured** (fifth review §2): inflating all four bars on every
rung of an otherwise-eligible ladder converted three ROW_1 reads into three ROW_3 reads and CLOSEd the
family — one mistyped argument, repeated three times, and no instrument in the chain said a word. This
is E1's shape a second time: the verdict already carries `bars` (D2); nothing downstream reads it against
anything.

**Fixed:** `g2b_family.py` now defines `PRE_REGISTERED_BARS`, keyed by `f_min`, restating exactly the
table in §4.2/§4.2a:

| `f_min` | `g_new_min_rate` | `g_high_min_rate` | `churn_net_min_rate` | `churn_gross_max_rate` |
|---:|---:|---:|---:|---:|
| 180 | 0.35% | 0.50% | −0.25% | 2.00% |
| 140 | 1.00% | 0.50% | −0.25% | 2.00% |
| 100 | 1.65% | 0.50% | −0.25% | 2.00% |

Per the Captain's explicit instruction (carried from the Architect's fix, unchanged): **the mechanism
belongs at the adjudication layer** (`g2b_family.py`), not in `g2b_gate.py` — A5 made the bars
CLI-supplied deliberately, and moving them into the gate as constants would remove the operator's ability
to supply them at all, which is not what this finding is about. `bars` joins `REQUIRED_VERDICT_KEYS`.

**F7 (pre-registered here, mechanical):** REFUSE unless every rung's `bars` equal
`PRE_REGISTERED_BARS[f_min]`, naming the rung, the field, the value supplied and the value expected.
**HK-021(k):** fires (any of the four fields on any rung mismatches) ⇒ REFUSE; does not fire ⇒ the same
CLOSE/DO NOT CLOSE reading on the same three verdicts. Mechanical.

### 9d.3 J4 (MINOR, escalated by the Captain to a ruling) — the burned region is hard-coded

`--burned-wav-dir`/`--held-out-from` were operator-typed CLI values, defeated by the same class of typo
three rounds running (B2 → C1 → D1). **RULING (Captain):** both are **removed**, not defaulted, and
become one pre-registered constant in `g2b_gate.py`:

```python
BURNED_CORPUS = {
    "wav_dir": "artefacts/20260808_live_run_0016-8080/wsjt-x/wav",
    "held_out_from": "260808_014215",
}
```

Resolved against the **repo root** (`Path(__file__).resolve().parents[2]`, never the process's CWD — D4's
hazard, already fixed once in the producer and now closed here too), and **isdir-checked**: if the
resolved directory does not exist (a fresh checkout has no `artefacts/` at all — it is blanket-gitignored)
the gate cannot determine whether the legs it was handed are burned in either direction, and fails ROW 0
rather than silently treating an unconfirmable constant as "not burned." **No test-only override flag**
exists, per the Captain's explicit instruction — a fixture that wants to exercise burned behaviour points
its own recorded leg `wav_dir` at the constant.

`--burned-corpus {yes,no}` **stays** — D1's point (the operator's declaration must exist and be checked
against something) is unchanged; only *what it is checked against* moved from another operator-typed
value to a ruled constant. Pre-registered as P2's revised row, §3 above.

### 9d.4 Captain's ruling — the verdict is self-contained by construction (absorbs J3)

J3 (SERIOUS) found the verdict emitted `wav_dir` only, so nothing bound three rungs' `ROW_3` reads to one
corpus **slice** (as opposed to one directory) — two rungs could share `wav_dir` yet run on different
`window`/`start_cycle`. Rather than add that one field (the pattern that produced five rounds of "carry
one more field, discovered one field at a time" — the Architect's own §7.3 self-criticism), **the Captain
ruled the structural question**: the verdict now carries **everything the row was computed from**, as a
property, not a list:

> **The verdict must be sufficient to RE-DERIVE the row without the leg JSONs.**

**What it carries, concretely (`build_verdict()` in `g2b_gate.py`):**

- **The evidence:** `rows` — the actual `(g_low, g_high, g_else, lost, n_base)` per-cycle tuples
  `per_cycle_terms()` computed. `None` on ROW_0 (no read happened).
- **The identity:** everything already there, **plus** `window`, `start_cycle`, `n_cycles`, `d_base`
  (absorbs J3), `av_excluded_count`, `truncated_count`.
- **The constants that entered the decision:** `bars` (already there), `bootstrap_n`, `bootstrap_seed`,
  `min_high_band_observations`, `old_f_min`, `old_f_max`, and **`gate_sha256`** — this file's own SHA256,
  E2's own logic ("pin the SHA256, never infer identity from a label") applied to the instrument rather
  than the DLL.

**The mechanism that makes it true:** the row-decision logic is extracted into `decide()`, a pure
function of `(rows, f_min, f_max, bars, constants)` — `main()` calls it on a fresh read; **`g2b_gate.py
--verify-verdict PATH`** (new) reads a verdict, calls the SAME `decide()` on the verdict's own carried
`rows`/`bars`/constants, and asserts the re-derived row equals the row recorded. Exercised in the smoke
suite for a ROW_1, a ROW_0 (`rows: null`, nothing to re-derive) and a ROW_INDETERMINATE verdict, plus a
negative control (a verdict whose `row` is tampered while its `rows` are left genuine, which
`--verify-verdict` catches and names). **`--verify-verdict` may only ever check a verdict against
itself — never produce a row used as new evidence** (Captain's explicit instruction; enforced by taking
no input but a single verdict path).

**Boundary, stated in `build_verdict()`'s own docstring so the artefact is not over-trusted:** a passing
`--verify-verdict` certifies what the gate **saw** re-derives to what the gate **said** — not that what it
saw was **true**. It cannot certify that `wav_dir` held the audio it claims, that a DLL SHA was built from
the source it claims, or that the producer read the cycles it recorded. **The instrument still cannot
bound its own blind spot (HK-026).**

### 9d.5 F8, F9 — the family's precondition table, updated in full

`g2b_family.py`'s own precondition table (§9c.2) is restated here in full — F1–F6 unchanged, F7 new
(§9d.2 above), F8/F9 new (absorbing J3's field-adding half and adding the evaluator-identity check):

| | precondition | class | fires ⇒ | does not fire ⇒ |
|---|---|---|---|---|
| **F1** | exactly `REQUIRED_LADDER_SIZE = 3` verdict files supplied | VALIDITY | **REFUSE** | proceed |
| **F2** | every file parses as JSON and carries all of `REQUIRED_VERDICT_KEYS` (now: `band`, `f_min`, `f_max`, `row`, `wav_dir`, `dll_sha256`, `manifest_sha256`, `burned_corpus`, `bars`, `window`, `start_cycle`, `gate_sha256`) | VALIDITY | **REFUSE**, naming the missing field(s) | proceed |
| **F3** | no two verdicts share an `f_min` | VALIDITY | **REFUSE** | proceed |
| **F4** | no verdict reads `ROW_0`/`ROW_0d`/**`ROW_INDETERMINATE`** (J1, new this addendum) | VALIDITY | **REFUSE**, naming which rung(s) | proceed |
| **F5** | all three verdicts share one `band`, one `f_max`, one `wav_dir`, **and one `burned_corpus`** (J5, extends E1) | VALIDITY | **REFUSE**, naming the field and the differing values | proceed |
| **F6** | all three verdicts' `dll_sha256["baseline"]` and `manifest_sha256` are identical | VALIDITY | **REFUSE**, naming the differing values (null-safe both ways — J6) | proceed |
| **F7 (new)** | every rung's `bars` equal `PRE_REGISTERED_BARS[f_min]` (§9d.2) | VALIDITY | **REFUSE**, naming rung/field/supplied/expected | proceed |
| **F8 (new, absorbs J3)** | all three verdicts share one `window` and one `start_cycle` | VALIDITY | **REFUSE**, naming the field and the differing values | proceed |
| **F9 (new)** | all three verdicts' `gate_sha256` are identical | VALIDITY | **REFUSE** — three rungs were read by different evaluators | proceed |
| — | *(adjudication: CLOSE if all remaining verdicts read `ROW_3`, else DO NOT CLOSE, naming the rungs that do not)* | | | |

**HK-021(k), F8/F9:** fires ⇒ REFUSE; does not fire ⇒ the same CLOSE/DO NOT CLOSE reading on the same
three verdicts. Mechanical, same shape as F5/F6/F7.

### 9d.6 J5, J6 — minor, carried by reference

**J5** (`burned_corpus` joins F5's identity set, §9d.5's table above) closes, at the adjudication layer,
the same two-error conjunction J4 closes at the source (§9d.3) — the Captain's instruction was explicit
that both land, not either. **J6**: `g2b_family.py`'s F6 previously formatted a `None` manifest digest as
`'FILE NOT FOUND'` while an equivalent `None` baseline SHA would have raised `TypeError` on `sha[:16]` —
fixed via one shared, null-safe `_fmt_sha()` helper (text now `'MISSING'` for both). Low reachability (the
gate itself dies earlier on a `None` baseline SHA); no new machinery, per the Architect's own instruction.

### 9d.7 Status

- ✅ **J1** fixed and pre-registered: ROW_INDETERMINATE in §4.7's table (above) and §9d.1; `g2b_family.py`
  refuses on it via the updated F4 (§9d.5).
- ✅ **J2** fixed and pre-registered as F7 (§9d.2/§9d.5), including the restated `PRE_REGISTERED_BARS`
  table.
- ✅ **J3** absorbed into the Captain's self-contained-verdict ruling (§9d.4) rather than fixed as a
  single added field; its field-adding half is F8 (§9d.5).
- ✅ **J4** fixed per the Captain's ruling: `BURNED_CORPUS` hard-coded, repo-root-resolved, isdir-checked
  (§9d.3); P2's row updated (§3 above).
- ✅ **J5** fixed: `burned_corpus` in F5's identity set (§9d.5/§9d.6).
- ✅ **J6** fixed: null-safe SHA formatting shared across F6 (§9d.6).
- ✅ **Captain's ruling (self-contained verdict):** implemented as a property with a mechanism
  (`decide()` shared by a fresh read and `--verify-verdict`), not a field list — §9d.4.
- ✅ Re-smoke-tested: `g2b_gate_smoketest.py` (65 checks, including ROW_INDETERMINATE under both the
  underpowered-real-effect and zero-cycle/`d_base=0` cases, the self-contained-verdict fields, and
  `--verify-verdict` re-derivation including its tampered-row negative control) and
  `g2b_family_smoketest.py` (62 checks, including F7 on all four bar fields plus a same-rung-bars
  control, F8 on `window` and `start_cycle` independently, F9, J5, and J6's null-safe baseline-SHA case).
  Both suites run twice, exit 0, byte-identical across the two runs (diffed, not asserted — HK-022).
- 🛑 **Not armed. Nothing merged, nothing pushed** (HK-010/HK-014). No decoder has been run; no rung of
  the ladder has been run. `p23_common.py`'s sort fix remains on its own branch, untouched by this.
- **Requesting:** the Architect's sixth review, of J1–J6 and both Captain's rulings as fixed and
  pre-registered above.
