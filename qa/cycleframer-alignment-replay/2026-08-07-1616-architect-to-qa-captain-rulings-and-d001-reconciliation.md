# Architect → QA: Captain's rulings on §7, and the D-001 reconciliation that was owed

**Author:** Architect, 2026-08-07 (16:16 UTC, `date -u`, per HK-017). Repo `main` at `ea2d94d`.
**For:** QA. §1 records Captain decisions; §6 lists what is still open with him.
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

### 1.5 D-009 parameter decision — **NOT PUT**, deferred by me

I did not put this one. I have not opened `report.md` §5 and would have been describing options
A/B/C from memory of my own summary. It returns in a separate note. See §6.2 for what the Captain
should have in front of him when it does.

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

### 6.1 S.1 — asked, not yet answered

07-31 §5.1 frames S.1 as: is the density penalty frequency-**local** (collision / subtraction
architecture — expensive) or cycle-**global** (candidate budget — cheap)? **That is very nearly
RC1's question**, and §0.2's 95% saturation is direct evidence for the cheap limb.

Memory records S.1 as answered by the Captain in conversation on 2026-08-04 and never written up,
with the standing instruction to **ask, not re-derive** — it has already been re-investigated twice
off a stale line. I have asked.

**Asked and answered in part, 2026-08-07:** the Captain proposed that the 3-way ANOVA
(`2026-08-06-2115`) already settles S.1. **It does not, for two independent reasons:**

1. **Wrong factors.** The model is Decoder × Source × Cycle. There is **no frequency term in it.**
   Frequency appears only in §4 as a reported quantity (1482.0 vs 1481.9 Hz, itself flagged there as
   statistically significant but practically meaningless). S.1 asks a *spectral locality* question;
   the design has no spectral factor to answer it with. What the ANOVA does settle — Decoder and
   Source are not confounded, 84.7% of variance on Decoder — is a different and important result.
2. **The dates preclude it.** The conversational S.1 answer is recorded as **2026-08-04**; the 3-way
   ANOVA is **2026-08-06**. The ANOVA postdates it by two days and cannot be what was said.

**So the 08-04 answer remains uncaptured and S.1 stays parked.** Do not re-derive it.

⚠️ **But note, for the Developer session:** RC1's per-candidate `(time_offset, freq, score)` list is
*incidentally* the data a spectral-locality test needs — it permits asking whether our misses cluster
in frequency near strong decodes (local: collision / subtraction architecture) or spread across the
band (global: candidate budget). Combined with §0.2's 95% saturation — a **per-cycle global** resource
exhausting — S.1 may close for free as a by-product of RC1. **This is an observation about what RC1's
data will permit, not a proposal to re-open S.1, and not a verdict.**

Until S.1 is answered:

> **RC1's gate stands as specced.** If S.1's answer already settles local-vs-global, RC1's gate may
> be redundant or need rewriting — and that must happen **before** the Developer session, not after.
> Flag this at the top of the dev-task.

### 6.2 D-009 parameter decision — returns separately

When it does, it must go to the Captain with QA's §2.1 finding stated explicitly and not as a
footnote: **`k10_*_n40` ties baseline recall exactly and posts zero false positives on both
synthetic arms — it strictly dominates the shipped baseline for one changed parameter.** It is not
the nominee **only because I wrote the rule with a strict `>` on recall.**

That is an HK-021-family drafting failure — a rule structure that hid a dominating option — and it
should be visible to the Captain when he weighs how much authority to give my nomination.

⚠️ Also propagate: **`41.508%` must not be cited as "our recall."** Its reference is the archived
corpus `ALL.TXT` restricted to low-SNR decodes — the exact log found suppressed ~2.3× on the busy
window, biased in precisely the population it measures. This does not change the D-009 decision
(+0.109 pp is far too small for reference bias to flip) but the number must not travel.

---

## 7. Citation limits in force — unchanged, restated

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
authorises the work, it does not break it down. Per HK-014 committed locally, not pushed, no merge
implied or requested. Per HK-011 RC1+RC2 require the Developer session the Captain has now
authorised, and he reviews the diff before any push. Per HK-021 §0 records a correction QA raised
against an Architect draft, and says so. Per NFR-021 no message text or callsign appears here, and
§1.4 makes the ignore rule a precondition of the HK-016 widening rather than a follow-up.*
