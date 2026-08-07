# Architect → QA: Captain's rulings on §7, and the D-001 reconciliation that was owed

**Author:** Architect, 2026-08-07 (16:16 UTC, `date -u`, per HK-017). Repo `main` at `ea2d94d`.
**For:** QA. §1 records Captain decisions; §6 lists what is still open with him; **§7 is a
pre-registered spec (S.1r) that is free to run and should precede the RC1 Developer session.**
**Supersedes:** `2026-08-06-2346-architect-to-qa-handoff-index-and-work-queue.md` §7 (all five
decisions), and corrects that document's §2 table (see §0).
**Authorisation:** RC1+RC2 are **now authorised** by the Captain (§1.1). Everything else in this
document is docs-only and touches no `src/`.

---

## 0. Correction to my own 2346 handoff, §2

QA's W2(a) flagged that my §2 table attributed the 2123 correction block to `f7717e3` §0.1. **QA is
correct and I have confirmed it mechanically rather than accepting the report:**

| commit | subject | files |
|---|---|---|
| `f7717e3` | `arch: M3 VOID -- preflight sleep desynchronises replay...` | 1 file, the 2249 note only. **No §0.1 exists in it.** |
| `1135406` | `arch: reference-suppression spec M0-M4...` | 1 file, the 2144 spec — the actual source |

The correction itself landed and is verbatim-consistent; only my pointer to it was wrong. Recording
this rather than silently editing the table, per HK-021's discipline on corrections.

**QA raised this correctly and did the right thing by flagging rather than fixing.** As with the two
prior HK-021 failures, the defect was in an Architect draft and QA executed correctly.

---

## 1. Captain's rulings — 2026-08-07

All five §7 items are now closed or reassigned. These are decisions, not recommendations.

### 1.1 RC1 + RC2 — **AUTHORISED**, one Developer session

Both, bundled, per the RC spec §5. QA's draft
`dev-tasks/2026-08-06-d001-rc1-rc2-candidate-diagnostics-runtime-caps.md` is the vehicle; the
sequencing constraint stands — **RC2 does not proceed if RC1 fires ROW 2.**

Two constraints to carry into the session, both already on record and neither optional:

- ⚠️ **`ft8_shim.c:514-525` — the latent array overflow.** `candidates[]` is sized
  `K_MAX_CANDIDATES_ANY_PASS`; `K_MAX_DECODED` is the sum of both caps. Sizing must be driven from
  the **runtime maxima**, not the old constants. This was found once already. It is to be handled
  deliberately, not rediscovered.
- **RC3 must not precede RC2.** Widening the band adds candidates to a list saturated on 95% of
  cycles; under a binding cap it can displace stronger candidates and *reduce* decodes.

Per HK-011 the Captain reviews the diff before any push. Per HK-006 `pre_merge_check.py` is not
QA's to run.

### 1.2 M3 — **PARKED**

Not archaeology worth 15 minutes. Window selection is repaired and the playback fix is verified, so
it remains re-runnable without re-derivation should a historical question ever need the archived
log — but nothing on the current board gates on it. The RC programme and the 2323 stratification are
reference-free by construction.

**Do not re-open M3 to "close the loop."** The repaired rule and the corrected window are recorded
in `ORCHESTRATION_REPORT.md`; that is the durable artefact, not a fired gate.

### 1.3 Arm R.D — **STOOD DOWN**

Not "still parked" — stood down. Its reciprocity premise is undermined by M2 (ROW 1, citable) on
this window, and the density-asymmetry result it was specced to obtain arrived reference-free from
data already on disk (2323 §3). The spec remains committed at `07cbd1b` for provenance.

⚠️ **This does not make 2323 §3 a superset of R.D.** §3 is one window, density 30–49 decodes/cycle,
and establishes that the penalty *exists and is SNR-independent within that range*. It does not
establish shape and does not extrapolate. R.D is stood down because its premise weakened, not
because the question is fully answered.

### 1.4 HK-016 — **WIDEN** to cover WSJT-X's AppData `ALL.TXT`

Collection-side only. **Nothing here proposes configuring WSJT-X** — that remains the Captain's and
is out of scope by standing rule.

> ⚠️ **WITHDRAWN — the precondition I attached to this ruling was wrong on the facts.**
> I wrote: *"Widening the gatherer without the ignore rule already in place would automate the exact
> NFR-021 exposure W1 found live in `_work_recal/`."* The Captain challenged it and he is correct.
> Verified mechanically, 2026-08-07:
>
> ```
> $ git check-ignore -v artefacts/
> .gitignore:105:artefacts/    artefacts/
> $ git ls-files artefacts/ | wc -l
> 0
> ```
>
> `artefacts/` is covered by a **blanket ignore** and has **zero tracked files**. HK-016 gathers into
> `artefacts/`. There is no exposure path into VCS and no precondition is required.
>
> **How I got it wrong, since the mechanism matters more than the error:** W1's exposure was in
> `qa/rr-study/d001-param-sweep-2026-07-22/_work_recal/` — a *different* directory under a
> *different* ignore rule. I generalised from one gitignore gap to a second location without running
> the single command that would have settled it. That is precisely HK-018, from the Architect, one
> day after writing HK-018 discipline into a handoff. Recorded rather than quietly deleted.

**Corrected position:** the widening is not merely safe, it is **an improvement on the status quo**.
Today WSJT-X's `ALL.TXT` lives in AppData under no repository policy at all — which is exactly how a
five-run experiment ended with its reference leg outside the repo until M0 rescued it. Gathering it
into a blanket-ignored directory brings it *under* policy. Proceed without preconditions.

**Nothing here proposes configuring WSJT-X** — that remains the Captain's and is out of scope by
standing rule.

### 1.5 D-009 parameter decision — **OPTION B**

> ⚠️ **My deferral of this item was on a false premise.** I recorded it as "not put" because I had
> not read `report.md` §5. The report has been on disk at
> `qa/rr-study/results/2026-08-05-f6c5b46-d009-recalibration/report.md` since 2026-08-06 — the 2346
> handoff's own document map cites it. I deferred a Captain decision by a day for want of a file I
> had already been told the location of. Same family as §1.4: not checking before concluding.

**Ruling: Option B — `osd_nhard_max` 60 → 40. One parameter. `k` and `corr` unchanged.**

| | recall | S5 FP | S7 FP | S7 signal recovery | params moved |
|---|---|---|---|---|---|
| C — no change | 41.508 | 1 | 8 | 84.651% | 0 |
| **B — adopted** | 41.508 | **0** | **0** | 84.651% | **1** |
| A — `k` 10→5 + `nhard` 60→40 | +0.109 pp | 0 | 1 | **87.442%** | 2 |

Rationale, in order of weight:

1. **B's entire case rests on arms with a real oracle.** It ties recall exactly
   (`recall_dpp = 0.000`), so no part of its argument touches the archived reference — the log found
   suppressed ~2.3× and biased in exactly the low-SNR population D-009's recall arm is restricted to.
   **Option A's only recall advantage is measured there.**
2. **`k` is the parameter RC2 is about to sweep.** `k_min_score_pass2` sits in the candidate-scoring
   path; per `report.md` §3.4 `k=5` pushes every slot into the `100+` candidate bucket, changing the
   candidate accounting wholesale. B moves only `nhard`, an OSD parameter downstream of candidate
   generation.
3. **Nothing measured gets worse.** Recall identical, S7 recovery identical (84.651% both), FP
   eliminated on both arms.

### 1.5.1 Three things the costed menu does not say — carry these

- **The menu leads with A's weakest evidence and omits its strongest.** §5 sells A on "+0.109 pp
  recall" — ~19 decodes in 17,469, about **0.3 standard errors**, on the compromised reference.
  A's actual gain is **+2.79 pp of S7 signal recovery** (84.651 → 87.442), measured on a *seeded
  synthetic arm with ground truth*. It is ~25× the recall effect and appears nowhere in §5, because
  recovery was never a gated term. **The third instance today of a rule structure deciding what the
  Captain gets to see** — after the strict `>` that hid Option B itself.
- **"C fails a gate" does not differentiate.** C is knocked for `co_channel_sweep` 86.67% < 89%.
  **A reaches 87.442% and B stays at 84.651% — both also fail that bar.** ⚠️ This sweep's baseline
  recovery is **84.651%**, not June's **86.67%**; they may not be the same metric. **QA should
  confirm whether they are before that argument is used again either way.** I am not asserting it.
- **A's +2.79 pp is ~1.2 standard errors on 215 signals.** Suggestive, not established — but still
  stronger relative to its own uncertainty than the recall figure the menu leads with.

### 1.5.2 ⚠️ Sequencing — B must NOT ship before RC2 runs

**I argued the opposite to the Captain and it was wrong. Correcting it here before it propagates.**

I said shipping B first would sharpen RC2's gate, by turning `S7 FP <= baseline` into "introduce no
false positives at all." That part is true. **What I missed is that it invalidates RC2's free
baseline.**

RC2's gate is `g = mean decodes/run(C) − 461`, and that **461 was measured on the shipped build —
i.e. at `nhard = 60`.** Change `nhard` first and `C0` no longer describes the build under test.

- On the D-009 recall corpus, `nhard` 60→40 moved recall by **exactly 0.000 pp**, so the effect on
  the replay window is *probably* nil.
- **"Probably" is not good enough for a pre-registered baseline.** RC2's threshold is `g > 40.0`
  against a run spread of 8 counts; a shift of even 10–15 decodes would eat a quarter of it.

| option | cost | consequence |
|---|---|---|
| **Ship B after RC2 reports (recommended)** | none | RC2 keeps its free `C0`. B is a Pareto improvement, not an urgent one. |
| Ship B first, re-measure `C0` | 15 min playback, 3 runs | Buys RC2 the sharper FP gate; pays for it in a baseline that was previously free. |

**Nothing ships either way without a Developer session and the Captain's sign-off (HK-011/HK-010).**
Changing the shipped default is a `src/` change; QA does not ship, merge or push a parameter value.

---

## 2. The reference instrument — nomination, now on the record

The standing board carries *"Mechanism 1 needs a recalibrated reference — the Architect's call to
choose and put to the Captain. Not done."* It has been de facto settled by this week's harness work
without ever being stated. Stating it:

> **Nominated reference: fresh WSJT-X decoding the identically replayed audio, in the same session.**
> Not `jt9 -d 3` offline (barred). Not any archived corpus `ALL.TXT` (validity open, and found
> suppressed ~2.3× on the busy window).

Why this one:

| property | value | why it matters |
|---|---|---|
| duplicate `(ts, message)` pairs | **none** | the defect that VOIDed Angle 1 and inflates `n_local` metrics at small `W` |
| run-to-run repeatability | miss rate **0.399–0.406** over 5 runs | an instrument whose own noise is ~0.9% can resolve the effects being chased |
| audio path | identical, same session, same replay | removes the confound that killed the offline comparison |

Operationally this changes nothing — every RC gate is already written against it. It is nominated
so the choice is visible and rejectable rather than implicit.

---

## 3. The reconciliation that three of my documents deferred

The 2323 note, the RC spec and the 2346 handoff each state that I had **not** opened
`project-state-2026-07-31-d001-competition-confirmed.md`, and that reconciling its density penalty
with the fresh measurement *"should not be done by assuming either side."* **I have now opened it.**

### 3.1 Mechanism 2 — the two measurements agree

| source | instrument | figure |
|---|---|---|
| 07-31, Measurement D §6.2, segment 1 | `jt9 -d 3` (now barred) | density penalty **~19.8 pts** |
| 2323 §3, mid-SNR band, dens 30–34 → 40–49 | fresh WSJT-X, same audio | **+18.5 pts** (0.290 → 0.475) |

**Why the agreement holds despite the barred instrument** — this is the part worth carrying forward:

> A biased reference corrupts a **level** far more than a **slope**. Mechanism 1 is a level — how far
> below the reference we sit — so `jt9`'s +93.8% overshoot passes directly into it. Mechanism 2 is a
> difference-of-differences *within one reference*, so a bias roughly neutral across density largely
> cancels.

That is the structural reason the ~34% is dead and the ~19.8 pts is not. It is also a general rule
for triaging every other figure measured against a barred instrument: **check whether the quantity
is a level or a contrast before assuming the bar kills it.**

One honest direction, deliberately not quantified: `jt9`'s duplicate pairs would inflate the
reference count *more* in dense cycles, which would inflate the old density penalty. The fresh
figure landing slightly lower is directionally consistent with that. I am not claiming the 1.3 pt
difference *is* duplicate inflation — n is far too small a basis and the two statistics are not
identical.

### 3.2 Citation limits, both sides, unchanged

- 07-31's figures remain governed by their own blacklist — two-session corpus, **segment 2 VOID**
  (do not cite its +12.26 / 21-of-28 / "75% vs 80%"), density law **not predictive**, "withheld
  figures" never existed.
- 2323 §3 remains **one window**, density 30–49/cycle, silent outside that range, and explicitly
  does not extrapolate to the ~7/cycle regime M3 was designed to probe.
- The two figures corroborate each other. **They do not merge into a single citable number.**

---

## 4. Mechanism 1 needs a different *window*, not just a different *reference*

This is the substantive finding from opening the 07-31 file, and it corrects the standing TODO's
framing — including my own.

Mechanism 1 is the baseline deficit **in the sparsest quartile** (~34% lost against the reference
even where density is lowest). The replay corpus cannot measure it:

- The replay window is the **busiest in the corpus** by construction.
- Its sparsest density bucket is **30–34 decodes/cycle** — approximately where 07-31's *sparse*
  stratum already sat (segment 2's was 33.02, which is why segment 2 VOIDed self-check 2).
- **There is no sparse regime in the current instrument at all.**

So the standing TODO as written — *"needs a recalibrated reference"* — is **necessary but not
sufficient**. Nominating fresh WSJT-X (§2) does not recover Mechanism 1. Recovering it requires a
replay window selected for *low* density, against the same instrument.

**I am not proposing that run.** Per the standing rule, `qa/ARTEFACT_INVENTORY.md` is opened before
anyone concludes such a window does or does not already exist on disk, and I have not done that.
It may well be a window-selection exercise over existing corpora rather than any new capture. That
check comes first, and it is free.

---

## 5. Three board entries that are now wrong

For whoever next reads the project board cold:

1. **S.2a is not "blocked on instrumentation."** `ft8_get_last_candidate_counts`,
   `ft8_get_last_pass_counts` and `ft8_get_last_llr_stats` are exported, P/Invoked, called per
   decode and written to the debug log per cycle — and were doing so in the five runs already on
   disk. Whatever S.2a still lacks, it is not those. The blocker was bookkeeping, not code.
2. **07-31 §5.6 already named RC2.** *"`K_MAX_CANDIDATES` in the dense regime — still untested, not
   refuted. Reaches the Captain priced via S.2a's result, not before."* RC2 is that item, arriving
   seven days later by a different route — with the gate that was meant to price it now shown never
   to have been blocked. **The hypothesis was correctly identified on 07-31 and then gated behind a
   blocker that did not exist.**
3. **The "29.9% agreement is unexplained" TODO is closed.** QA's decode-config comparison
   (`2026-08-06-1933`) and the five-run replay superseded it. It is no longer an open cheap check,
   and the worry it carried — that months of shortfall figures might be measuring a config artefact
   — did not materialise: the deficit reproduces at 0.399–0.406 on identical audio.

---

## 6. Still open with the Captain

### 6.1 S.1 — CLOSED. Only its *limb* is outstanding, and only for RC1's scope

07-31 §5.1 frames S.1 as: is the density penalty frequency-**local** (collision / subtraction
architecture — expensive) or cycle-**global** (candidate budget — cheap)? **That is very nearly
RC1's question**, and §0.2's 95% saturation is direct evidence for the cheap limb.

Memory records S.1 as answered by the Captain in conversation on 2026-08-04 and never written up,
with the standing instruction to **ask, not re-derive** — it has already been re-investigated twice
off a stale line. I asked, and then argued with the answer. See the withdrawal below.

> ⚠️ **WITHDRAWN — a second bad argument from me, 2026-08-07.**
> I argued that the 3-way ANOVA (`2026-08-06-2115`) could not have settled S.1 because it
> **postdates** the recorded 08-04 conversation by two days. **That reasoning is void.** It addresses
> only whether the ANOVA *is* the 08-04 answer — a claim the Captain never made. He said two separate
> things: S.1 was closed in conversation, *and* later work measured the mechanism. Whether a later
> study answers S.1 on its own merits is entirely independent of what was said on 08-04. I used a
> provenance argument in place of a substantive one.
>
> Recorded rather than deleted. It is the same family as §1.4's withdrawal: **reaching for a cheap
> structural argument instead of checking the substance.**

**S.1 is CLOSED.** The Captain closed it in conversation on 2026-08-04 and reconfirmed it on
2026-08-07. It is not open, not partially open, and **not to be re-derived** — the standing rule is
to ask him, and that rule was violated twice on 08-04 already.

**The one item outstanding is narrow:** *which limb* S.1 landed on — frequency-**local**
(collision / subtraction architecture) or cycle-**global** (candidate budget). This is asked solely
because it is load-bearing for RC1's scope (below), not to re-litigate the closure.

⚠️ **Caveat on my own framing, stated because it may invalidate the question entirely:** everything
above rests on `project-state-2026-07-31` §5.1's *one-line* summary of S.1. If the question the
Captain actually closed is broader or different from that line, this item is void and the later
study may cover it in full.

**The Captain's 2026-08-07 direction supersedes the ask above.** The conversational closure rested
on roughly **86 samples**. The five-run replay corpus carries **3,779 reference decodes and 1,526
misses** — about **44× the evidence, already on disk.** Rather than reconstruct the 08-04 reasoning,
S.1 is to be **re-evidenced at power** from data already gathered. Specced as **S.1r** in §7.

> **RC1's gate stands as specced unless S.1r fires ROW 2 or ROW 3.** S.1r is free and can narrow
> RC1's scope, so it runs **before** the Developer session, not after. Flag this at the top of the
> dev-task.

### 6.2 D-009 parameter decision — **CLOSED, see §1.5**

**Decided 2026-08-07: Option B.** The material below is retained because its two warnings survive
the decision and must keep travelling.

**`k10_*_n40` — the option the Captain adopted — was never the nominee, and the reason is mine.**
It ties baseline recall exactly and posts zero false positives on both synthetic arms, strictly
dominating the shipped baseline for one changed parameter. It failed `WIN(p)` **only because I wrote
the rule with a strict `>` on recall.** QA surfaced it in §2.1 of their results note despite the
rule, not because of it.

That is an HK-021-family drafting failure — a rule structure that hid the option that turned out to
be the right one — and it should stay visible when weighing how much authority to give my future
nominations. **It is the same failure as §1.5.1's second bullet**, found twice in one sweep.

⚠️ Also propagate: **`41.508%` must not be cited as "our recall."** Its reference is the archived
corpus `ALL.TXT` restricted to low-SNR decodes — the exact log found suppressed ~2.3× on the busy
window, biased in precisely the population it measures. **Option B is immune to this** — it ties
recall exactly, so its case rests entirely on the synthetic arms — but the number must not travel.

---

## 7. S.1r — spectral locality, re-evidenced at power (PRE-REGISTERED SPEC)

**Requested by the Captain, 2026-08-07.** S.1 is closed; **S.1r does not re-open it.** It replaces a
~86-sample conversational basis with the five-run corpus, at ~44× the evidence, and its purpose is to
put the *limb* beyond argument.

**Cost: a re-analysis.** No `src/` change, no playback, no capture, no authorisation. Files are
already on disk. ~1 h of QA scripting. Per HK-004 this is a *do*, not a *recommend* — the data and
the ANOVA machinery both exist.

### 7.1 The question, made mechanical

| mechanism | prediction |
|---|---|
| frequency-**local** (collision / imperfect subtraction) | misses cluster near neighbouring signals; a weak signal alone in a quiet part of the band survives even in a busy cycle |
| cycle-**global** (candidate budget) | misses track total cycle occupancy; spectral isolation buys nothing |

### 7.2 Inputs and derived quantities

Source: `_work/run{1..5}/`, five runs, busy window (`260804_085845 … 260804_090330`), pass 1.
Match key `(cycle, normalize_hash_tokens(message))` as established. Reference is **fresh WSJT-X on
the same replayed audio** (§2) — never the archived `ALL.TXT`.

For every **WSJT-X** decode (the reference set defines what was actually on the air):

| symbol | definition |
|---|---|
| `sep` | Hz to the **nearest other WSJT-X decode in the same cycle**. Undefined for single-decode cycles ⇒ **excluded, and the excluded count reported.** |
| `dens` | count of WSJT-X decodes in that cycle (identical definition to the 2323 note §3) |
| `snr` | WSJT-X's reported SNR — the common scale, since ours reads 2.0–2.6 dB low (tracked S7 gain error) |
| `missed` | no matching decode of ours in that cycle |

### 7.3 Design — the existing ANOVA machinery, one factor added

`qa/rr-study/harness/anova_compute.py` / `qa/endurance/anova_common.py`, unchanged.

| factor | levels | note |
|---|---|---|
| **Separation** (local) | `< 50` / `50–150` / `> 150` Hz | **physically motivated, not fished** — FT8 occupies ~50 Hz, so `<50` is overlap and `>150` is clear air |
| **Density** (global) | `30–34` / `35–39` / `40–49` | identical bands to 2323 §3, so results join directly |
| **SNR** | the existing 4 bands | **control, mandatory** — see §7.6 |
| **Run** | 1–5 | replicates ⇒ every term tested against the pure run-to-run residual, exactly as the 3-way ANOVA did |

Response: **miss rate per cell.**

⚠️ **Why `sep` and not a neighbour count.** My first draft used *count of neighbours within ±50 Hz*.
Checking the lattice before setting the threshold — 2800 Hz band, 30–49 signals — the expected count
is only **~1–2**, so terciles would be dominated by ties and the predictor would carry almost no
usable variance. **That is the RC spec §0.5 trap exactly**, and it was caught by applying that rule
rather than by luck. `sep` is continuous, defined for every decode, and mean spacing (~70 Hz) sits
between the two boundaries — so all three levels populate.

**Mandatory lattice check before evaluating any gate:** report the observed distribution of `sep`
and the per-cell `n`. **Any cell with pooled `n < 20` is excluded and reported as excluded.** If any
*level* of Separation or Density is unpopulated, **the gate does not fire and the result is ROW 4** —
a factor with no variance cannot be tested.

### 7.4 Effect sizes

Least-squares marginal means from the fitted model, in **percentage points of miss rate**:

- `E_sep` = miss rate at `sep < 50` **minus** miss rate at `sep > 150`, marginal over Density and SNR
- `E_dens` = miss rate at `dens 40–49` **minus** miss rate at `dens 30–34`, marginal over Separation and SNR

`p_sep`, `p_dens` = F-test p-values for those main effects against the pure run-to-run residual.

### 7.5 Pre-registered gate

```python
def limb(e, p):
    """Classify one mechanism. Boundary values fall to PARTIAL by construction."""
    if e > 5.0 and p < 0.01:   return "LIVE"
    if e < 2.0 or  p > 0.05:   return "NULL"
    return "PARTIAL"

def s1r_row(e_sep, p_sep, e_dens, p_dens):
    local  = limb(e_sep,  p_sep)
    glob   = limb(e_dens, p_dens)
    if local == "LIVE" and glob == "LIVE":  return "ROW 1"
    if local == "LIVE" and glob == "NULL":  return "ROW 2"
    if glob  == "LIVE" and local == "NULL": return "ROW 3"
    return "ROW 4"
```

| row | condition | consequence |
|---|---|---|
| **ROW 1** | both LIVE | **BOTH MECHANISMS ARE REAL.** ⇒ S.1's either/or framing is false. RC1 proceeds as specced; RC2 is **necessary but not sufficient**. Report both effect sizes — the split decides where to spend. |
| **ROW 2** | local LIVE, global NULL | **FREQUENCY-LOCAL.** ⇒ The candidate budget is **not** the dominant term. RC2 is demoted; the lever is collision / subtraction architecture. RC1 should be expected to fire its own ROW 2 (*decode, not search*). |
| **ROW 3** | global LIVE, local NULL | **CYCLE-GLOBAL.** ⇒ Candidate budget confirmed as the mechanism. RC1 becomes **confirmatory rather than diagnostic**, and the Captain may elect to skip it and go straight to RC2. |
| **ROW 4** | anything else (any PARTIAL, or a factor without variance) | **NO VERDICT.** ⇒ Report the full cell table. **RC1 stands as specced and is not narrowed.** |

**Thresholds, with rationale, per HK-021 — challenge these before execution, not after:**

- **`5.0` pp for LIVE.** Pooled run-to-run miss-rate spread is **0.7 pp** (0.399–0.406 over 5 runs),
  so 5.0 pp is ~7× the instrument's own noise. The known density effect is ~18.5 pp (2323 §3), so
  5.0 pp is ~27% of a known-real effect — large enough to matter, small enough that a genuine
  *secondary* mechanism is not discarded.
- **`2.0` pp / `p > 0.05` for NULL.** Just above noise; a mechanism below this is not carrying the
  40% deficit.
- **`p < 0.01` not `0.05` for LIVE** — several terms are tested on one corpus.
- **Boundaries fall to PARTIAL** (`> 5.0`, `< 2.0` both strict) and PARTIAL routes to ROW 4.

### 7.6 Confounds, stated in advance

1. **Separation correlates with density** — busier cycles crowd everyone. This is why Density is in
   the model: `E_sep` is a marginal mean **with Density held**, not a raw contrast.
2. **Denser cycles carry *stronger* signals** (median WSJT-X SNR −7.0 dB at density 40+, −9.5 dB
   below 35, per 2323 §3). This runs **against** a positive density finding, so a ROW 1/ROW 3 result
   is *strengthened* by it, not threatened. SNR is nonetheless controlled.
3. **`sep` is computed on WSJT-X's decodes, not ours** — using our own set would condition the
   predictor on the outcome.
4. **Sensitivity, reported but NOT gated:** re-run at boundaries `25/100` and `75/200`. **Only the
   pre-registered `50/150` evaluates the gate.** Reporting the others guards against a boundary
   artefact; letting them fire the gate would be fishing.

### 7.7 What S.1r does not establish

- **One window, density 30–49/cycle.** It fixes the limb **in the dense regime** — where the density
  penalty lives — and is **silent** on the ~7/cycle regime.
- **Decode-side, not pipeline-side.** It says whether locality matters, not *where* it acts. RC1
  supplies the pipeline side; the two are complementary and neither substitutes for the other.
- **Observational, not interventional.** It stratifies a designed experiment; it does not manipulate
  the mechanism. **RC2's cap sweep is the interventional test**, and only the three together make
  the answer durable.
- It does **not** re-open S.1, and its result does not reverse a Captain's closure — it re-evidences
  the limb at ~44× the sample the closure rested on.

---

## 8. Citation limits in force — unchanged, restated

- **`s_low = 0.217`** — never cite. Void, harness defect.
- **`F_dec = 1.2455`** — never citable.
- **`41.508%`** — not "our recall" (§6.2).
- **"drift explains *most*"**, never "~83%" — 4 events, interval [0.55, 0.93].
  ⚠️ **Do not confuse this with the 2323 note's "83% of WSJT-X" prize figure.** Different quantity,
  different derivation, coincidentally the same number. This is a live conflation risk.
- **~34% baseline deficit** — measured against `jt9 -d 3`, barred. See §3.1 and §4.
- **Everything in the 2323/RC notes is one window**, the busiest in the corpus.
- No D-number quoted without opening `project-state-2026-07-31-d001-competition-confirmed.md`
  first — **which, as of this document, I finally have.**

---

*Per HK-015 this is Architect → QA; `tasks.md` and `dev-tasks/*.md` remain QA's to author — §1.1
authorises the work and §7 specs it, neither breaks it down. Per HK-014 committed locally, not
pushed, no merge implied or requested. Per HK-011 RC1+RC2 require the Developer session the Captain
has now authorised, and he reviews the diff before any push; **§7 touches no `src/` and needs no
authorisation.** Per HK-021 §0 records a correction QA raised against an Architect draft and says so;
§7.5's gate is drafted as the code that evaluates it, rows mutually exclusive and exhaustive in
strict order, boundary values falling to PARTIAL and thence to the no-verdict row, with §7.3
recording a predictor I discarded for want of variance before writing its threshold. Per NFR-021 no
message text or callsign appears here; §7 reads message text only to build match keys, and the
replay harness already writes per-row SNR/DT/frequency with callsigns stripped. Two Architect claims
were withdrawn in this document on the Captain's challenge — §1.4 and §6.1 — and both are recorded
in place rather than deleted.*
