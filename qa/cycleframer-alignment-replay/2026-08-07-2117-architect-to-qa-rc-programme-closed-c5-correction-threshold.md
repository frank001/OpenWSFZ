# Architect → QA: the RC programme is closed — and most of it re-derived results already on disk

**Author:** Architect, 2026-08-07 (21:17 UTC, `date -u`, per HK-017). Repo `main` at `6e938c7`.
**For:** QA. §1 and §4.4 are for the Captain.
**Reports against:** `2026-08-07-1856-rc1-result-row2-stop.md` (on branch
`d001-rc1-rc2-candidate-diagnostics`) and `2026-08-07-2020-rc4-result-row2-no-effect.md`.
**Supersedes:** `2026-08-06-2336-architect-to-qa-spec-d001-root-cause-rc1-rc4.md` §5's sequencing
diagram, and the "NEXT: RC1 → RC2 → RC3" board entry.
**Authorisation:** **NOTHING HERE IS AUTHORISED TO RUN.** §5's ladder is a recommendation to QA
per HK-015; §5.1 and §5.2 need no `src/` change and no capture, but neither is armed by this note.

---

## 1. Read this first — I specced a four-arm programme without opening the existing branches

Three of the four RC arms measured something this project had already measured. The evidence was on
disk the whole time, in places the standing rules name explicitly.

| what I specced | what already existed | when |
|---|---|---|
| **RC2** — "the leading treatment hypothesis": raise `K_MAX_CANDIDATES` | **C.1** swept it at 140/300/**600**. `+12 decodes (+0.93%)` at 300, **byte-identical at 600**. Candidate population plateaus ~220–295 regardless of ceiling. | 2026-07-25 |
| **RC1** — partition misses into "no candidate" vs "candidate failed" | **C.2 Phase 1 CONFIRMED** the discriminator: matched-missed candidates have lower `prenorm_var`/`postnorm_mean\|LLR\|` than matched-hit **within every score band** (score-overlap-restricted `p=9.1e-34`). | 2026-07-26 |
| **the LLR fix I was about to spec tonight** | **C.2 Phase 2c RAN IT.** Shrinkage toward a per-pass reference, swept at w=0.00/0.25/0.50/0.75/1.00. **0/135 recovered at every weight**; regressions rise monotonically 0/0/1/2/5. **Closed on evidence** by my own 07-26 20:30 ruling. | 2026-07-26 |

C.1's own §5 closes with: *"QA/Architect should decide whether that follow-up is worth scoping
**given C.2 is likely to dominate**."* That sentence predicted RC1's ROW 2 six weeks before I
wrote the spec that went looking for it.

**How the third one was caught.** I had drafted a "C.2 Phase 2 — shrinkage" spec and opened
`qa/ARTEFACT_INVENTORY.md` only because the standing rule forces it before proposing a window. The
inventory row `d001_c2_phase2c` lists `sweep/w0.00 … w1.00`. The rule caught a spec that was one
commit from being written. That is the rule working exactly as designed, and it is the reason it
exists.

**This is HK-018 three times in one sitting**, on top of the five logged earlier today. Same shape
every time: I reasoned from what was in context instead of opening the branch. None of these were
reasoning errors. The RC gates were sound, pre-registered, and correctly executed — they were
pointed at ground already surveyed.

**What this does *not* devalue.** RC1's ROW 2 is not redundant, for one specific reason given in
§3.2: it supplies a *magnitude* nothing before it could.

---

## 2. RC1 and RC4 — gates verified, results accepted

### 2.1 RC1 → ROW 2, accepted

`f_nocand = 80 / 866 = 0.0924` → `rc1_row = ROW 2` (< 0.30). Correct against the spec's §2.3 code.

**90.8% of in-band misses already had a candidate; LDPC/OSD failed to convert it.** The result holds
in every stratum tried: `f_nocand` never approaches 0.30 in any SNR band (max 0.210 at −20…−15 dB),
any density band (max 0.123 at 30–34), or any spectral tercile. The S.1r-R rider fired ROW 4
(`d_cnd = +4.8` pp, `d_noc = −4.8` pp, both under the 15.0 pp bar) — no locality signature. That
rider used **terciles of the observed `sep` distribution**, populated by construction, which is the
structural fix S.1r's failure earned this morning. It worked.

### 2.2 RC4 → ROW 2, accepted

`d = +0.70` pp, `worst_band_regression = +2.06` pp → `abs(d) < 2.0` fires first in strict row order
→ **ROW 2, no effect.** ROW 1 was unreachable regardless (it needs `d < −5.0`). Correct against
§4.2's code.

**The Developer improved on my spec and said so.** I told them to baseline against the 2323 note's
table. They used **RC1's own 3-run replay of the identical window** — same day, same WSJT-X session,
same corpus, pass count the only variable — and reported my cited baseline alongside as a secondary
cross-check. Both agree (+0.70 pp / −0.50 pp, opposite signs, both inside noise). That is a tighter
control than I specified, and flagging it rather than silently substituting is the right handling.

### 2.3 Authorisation note

RC4 ran on the Captain's authorisation against a pre-registered trigger that had already fired, with
no Architect available. That was correct. §4.2's row table pre-wrote every consequence including the
June reconciliation; the only outcome needing fresh judgement was ROW 4 (mixed), which did not
occur. This is the pre-registration discipline paying for itself — the gate was executable without
me, which is the whole point of HK-021.

---

## 3. Where D-001 actually stands

### 3.1 The arms

| arm | status | basis |
|---|---|---|
| **RC1** candidate generation | **CLOSED** — not the cause | ROW 2, `f_nocand = 0.0924` |
| **RC2** candidate budget | **CLOSED twice** | excluded by RC1's gate; and already bounded at **+0.93%** by C.1 in July |
| **RC4** decode depth | **CLOSED** | ROW 2, `d = +0.70` pp |
| **RC3** search band | **survives, and is small** | RC1 sized it exactly: 28 OOB of 894 pooled misses = **3.1% of the gap** |
| **C.2 Phase 2** LLR normalisation | **CLOSED on evidence** | 0/135 recovered at every shrinkage weight; harm rises monotonically with weight |

### 3.2 What RC1 contributed that nothing before it could

C.2 Phase 1 proved the discriminator *exists*. It could not say how much of D-001 it owns — its
matched-missed population was **n=135** on a 68-cycle July corpus. RC1 gives the magnitude on the
August replication corpus: **786 CANDIDATE_NOT_DECODED out of 866 in-band misses, 90.8%**, pooled
over 3 runs at **5.8× C.2's sample**, on a different corpus, on a different band-day, through a
verified single audio path.

That converts "a correlation exists" into "this stage owns essentially the whole remaining gap." It
is the number the 07-26 thread needed and did not have.

### 3.3 The corollary nobody has stated plainly

Candidate generation is fine. Candidate budget is worth ~1%. Decode depth is worth nothing. LLR
rescaling recovers nothing. **Every cheap lever on the candidate side of the pipeline has now been
measured and is exhausted.** What remains is the decode path itself — BP iterations, OSD depth, the
OSD gate — and one question, first asked on 2026-07-26 and never answered:

> **How many bit errors can *this codebase's* BP+OSD actually correct?**

Every reading rule in this project that mentions BER has been written against a threshold I invented
and never measured. I flagged that as a caveat on 07-26 18:30, then built two rulings on top of the
uncalibrated table anyway, and corrected myself at 20:30. It is still uncalibrated.

---

## 4. Rulings

### 4.1 RC2 — CLOSED. Do not re-scope it.

Excluded by RC1's own pre-registered gate *and* independently bounded at +0.93% by C.1's 140/300/600
sweep. The array-sizing landmine at `ft8_shim.c:514-525` was already fixed by C.1 in July
(`K_MAX_CANDIDATES_ANY_PASS`) — my spec's §3.2 flagged it as outstanding work. It is not.

**Citation limit:** the ~95%-of-cycles saturation finding is real and reproduced by RC1
(pass 0 at exactly 140, pass 1 at exactly 200). "The candidate budget is allocated backwards" (my
2336 §0.3) is still a true description of the *allocation*. It is **not** a description of
recoverable decodes, and must not be cited as one — C.1 measured the recoverable surplus at 12
decodes on 68 cycles.

### 4.2 RC4 — CLOSED. My recommendation on the branch.

The June verdict holds on real audio. Decode depth is not a lever on either population.

The branch is left as built, deliberately, for the Captain's diff review. **My recommendation:
revert `K_MAX_PASSES` to 2, keep the test fix.** Shipping a third pass costs CPU inside a 15 s
budget and `K_MAX_DECODED` 340→540 in memory for a measured no-effect. The test fix is a separate
matter and should land regardless of the revert: replacing the hardcoded `[0, 0]` two-pass literal
with `new int[Ft8LibInterop.MaxDecodePasses]` removes a root cause that has now broken twice, at
20260007 and again at 20260035. That is the durable half of the session.

Whether and how to land it is the Captain's call under HK-011/HK-010; this is a recommendation, not
a merge request, and I am not asking for one.

### 4.3 RC3 — DEFERRED, pending a measurement that is already paid for

RC3's sequencing precondition was "must not run before RC2 reports." RC2 will never report, so that
instruction is now unsatisfiable as written — and it would be wrong to read that as clearing RC3.
The *reason* for the precondition is untouched: the caps are still saturated on ~95% of cycles, so
widening the band still adds candidates to a list that will truncate something to make room.

But the sequencing was always a proxy for a question that can be answered directly:

> **Do the candidates at the bottom of the ranked list convert into decodes at all?**

If they convert at ~0%, displacement costs nothing and RC3's 3.1% is free. RC1's
`_work/run{1,2,3}/candidate_lists.json` — 390 KB per run of `(time_offset, freq_offset, score)`
triples — is **still on disk**, alongside `our_rows_p1.json`. Conversion-rate-by-rank is computable
offline: no replay, no `src/` change, no authorisation, no NFR-021 exposure. See §5.3.

**A prior worth stating so the measurement is read honestly:** C.1's sweep implies candidates ranked
beyond 140 convert at roughly 0.2% (5,440 extra candidates over 68 cycles yielded +12 decodes). That
is a *lower* bound on rank ~139's conversion, not an estimate of it — the bottom of the kept list
scores higher than anything beyond it. The measurement is still needed. I expect it to clear RC3,
and I am recording that expectation in advance so it can be checked against the result.

### 4.4 D-009 Option B — I recommend the Captain HOLD it

Option B is `osd_nhard_max` 60 → 40. **It makes OSD shallower.** RC1 has just localised 90.8% of the
remaining gap to the stage that constant governs.

Two things changed under the ruling since it was made:

1. **Its sequencing is void.** I ruled B ships *after RC2*. RC2 will never run, so B is now unblocked
   by default — which is not what "after RC2" was meant to achieve.
2. **Its direction now opposes the localisation.** My own 07-26 18:30 reading rule names *"OSD
   depth/gate"* as the cheap-constants response to exactly the failure mode RC1 measured, and C.2's
   Phase 2 scope named `OSD_NHARD_MAX` as calibration that a decode-path change would invalidate.

**Stated fairly against my own recommendation:** B tied recall *exactly* (`recall_dpp = 0.000`) on
the arms measured, so there is no measured recall harm, and B's case never rested on recall. But
those arms were synthetic S5/S7. The live busy-window population RC1 just characterised was never
among them, and it is the one that is OSD-limited.

I am not asking to reverse the ruling — it was yours and it was reasonable on what was known. I am
recording that its precondition evaporated and its direction is now suspect, and recommending it
waits behind §5. If it ships first, §5's threshold measurement is taken against a moved gate.

### 4.5 `FT8_SHIM_VERSION` 20260034 is claimed twice — QA to resolve

| branch | version | date |
|---|---|---|
| `main` | 20260033 | — |
| `d001-c2-llr-normalization` | **20260034** | 2026-07-26 |
| `d001-rc1-rc2-candidate-diagnostics` | **20260034** | 2026-08-07 |
| `d001-rc4-decode-depth` | 20260035 | 2026-08-07 |

RC4 deliberately skipped 20260034 to avoid colliding with RC1 — correctly, but unaware that C.2 had
held it since July. Whichever lands second needs a bump, and §5.3's ladder may want C.2's
`candidate_diag` capture back, so this is not hypothetical. Note also that all three branches carry
a rebuilt `win-x64/libft8.dll` at overlapping version numbers; version alone will not tell you which
binary you are running.

**Two smaller housekeeping items found while checking the above, neither urgent:**

- A stray git worktree is still checked out at
  `.claude/worktrees/agent-a374614f1802aa80c`, holding `d001-c1-candidate-cap-sweep` at `c65dddb`
  since the July C.1 session. Harmless, but it means a naive repo-wide `find` for
  `patched/ft8/decode.c` returns the worktree copy first — which is how I nearly cited the wrong
  file tonight. (The two copies are byte-identical at present; I checked.)
- `d001-c1-candidate-cap-sweep` is **not an ancestor of `main`**, yet its
  `K_MAX_CANDIDATES_ANY_PASS` fix *is* on `main` — so it landed by squash or re-apply, not merge.
  Worth knowing before anyone reasons about what shipped from `git merge-base`. Per HK-003, verify
  individually before deleting that branch; the ancestry check alone would mislead.

---

## 5. What I recommend next — re-issuing the session that was recommended on 2026-07-26 and never run

`2026-07-26-2030-architect-c2-phase2c-ruling.md` §6 recommended a two-part session. No dev-task, no
scripts, and no artefacts for it exist. The thread moved to the B.3 menu the next day and then into
the drift saga, and it was never picked up.

It is now a better idea than it was then, because RC1 supplies the magnitude it was missing. I am
re-issuing it as **C.5**, restructured into three rungs so the free ones report before anything is
built. Naming it C.5 rather than RC5 is deliberate: it belongs to the C-thread that was already
answering this question, not to the RC programme that has closed.

### 5.1 C.5a — calibrate the correction threshold (free; no corpus, no capture, no `src/`)

Take known-good synthetic codewords (Q-prefix, per NFR-021 — the same construction the Phase 2c
Gray/sync round-trip used, which verified 6/6 two independent ways), inject *k* bit errors for
k = 0…45, run our own `bp_decode`/OSD path at the shipped D-009 constants, and plot success rate
against k.

**Report a curve, not a point.** The interesting output is where success falls from ~100% to ~0% and
how wide the transition is.

**Two error patterns, and the primary is the conservative one.** Real demodulation errors are
correlated within a symbol (58 tone decisions carry 3 bits each). My 07-26 note said a uniform-error
threshold "may be optimistic" and then left the choice open. Closing it now: **clustered-within-
symbol is primary, uniform-random is secondary.** If they disagree, the clustered figure governs.

Define the threshold mechanically: **`k_50` = the largest k at which success rate ≥ 0.50**, under
the clustered pattern, at ≥ 200 trials per k.

**One claim to verify rather than inherit.** My 07-26 note asserted this needs "no native change, no
rebuild." I did not verify that, and it is exactly the kind of inherited framing HK-020 warns about.
Check whether the shipped exports let you drive `bp_decode`/OSD on arbitrary LLR input. If they do
not, **stop and escalate** — do not quietly convert this into a Developer session on your own
authority.

This number is permanently useful. Every future LLR, BER, or decode-effort question in this project
reads against it, and none of them can be read without it.

### 5.2 C.5b — re-read the captured BER distributions against C.5a's threshold (free)

36 MB of LLR captures are already on disk under `artefacts/d001_c2_phase2c/ber/`. Pure re-analysis:

1. **Decile table** for all three arms (matched-hit control, THE 135, THE 567) — not median/mean/
   min/max. The 07-26 ruling's own §4 correction was forced by reading a heterogeneous population
   off its median; deciles are the fix.
2. **Control-arm mismatch rate** — the fraction of the control above 25% BER. That is the *measured*
   artefact floor (the control's max is 52.9%, so some control candidates are mismatched by the
   ±10 Hz/±0.5 s nearest-candidate rule). It lets the missed populations' upper tails be discounted
   by a measured quantity instead of an assumed one.
3. **The count that matters:** how many of THE 135 sit **below** C.5a's `k_50` and did not decode.
4. **BER against sync score and against `postnorm_mean_abs_llr`** within THE 135 — both columns are
   already in `candidate_diag.csv`.

**Stratify by deciles of the observed BER distribution, never by absolute BER constants.** This is
the rule S.1r's failure earned this morning, and the 07-26 band table (`≈50%` / "close" / "low") is
precisely the absolute-constant form that failed there.

**Directional facts to carry, both already established and neither to be re-derived:**
- Mismatch inflates BER *toward* 50% and can never push one *down*. So the ≈50% mass is partly
  artefact and the true distribution sits at or below what was measured — **the low tail is
  artefact-proof.**
- THE 567's n=279/567 truncation is a **head-take of the top 600 by descending sync score**, so it
  biases 49.4% *optimistically*. Fixing it can only move THE 567 further into the front-end band.
  Do not spend a session on it.

### 5.3 C.5c — candidate rank-conversion, which also clears or blocks RC3 (free)

Independent of C.5a/C.5b and answerable from RC1's retained `_work/`. From
`candidate_lists.json` + `our_rows_p1.json`, pooled over the 3 runs:

- Rank candidates **by descending score explicitly** — do not assume the returned list order is
  sorted, verify it and report whether it already was. (`ftx_find_candidates` in
  `native/ft8_lib_build/patched/ft8/decode.c` does heap-sort descending immediately before its
  `return heap_size`, under the comment *"At the end the elements will be sorted in descending
  order"* — I verified this tonight. The 07-26 ruling cited it as `decode.c:340–353`; that line
  range has drifted and the function name is the durable reference. Confirm the order survived
  RC1's getter and the marshalling into `candidate_lists.json`.)
- Match decodes back to candidates on the same ±6.25 Hz / ±0.5 s tolerance RC1's classifier used,
  and carry RC1's own stated ±1.5625 Hz / ±0.04 s sub-bin residual as a separate reported
  uncertainty rather than folding it in.
- Report conversion rate **by rank decile**, pass 0 and pass 1 separately. Deciles of a 0–139 lattice
  are populated by construction; no boundary can strand a stratum.

`c_bottom` = conversion rate in the bottom rank decile (pass 0).

### 5.4 Pre-registered gates

Drafted as executable code, per HK-021. Rows are mutually exclusive, evaluated in strict order, and
boundary values fall to the inconclusive row by construction.

**Note the ROW 0 in both gates.** S.1r returned ROW 4 from an empty stratum this morning, and ROW 4
read like a null when it was an instrument failure. Every gate I write from here carries an explicit
instrument-failure row so the two cannot be confused again.

```python
def c5_row(f_corr, n_measured, k_50_defined):
    """C.5b. f_corr = fraction of the measured missed population whose BER < k_50/174.

    Rates, not absolute counts: the 07-26 rule's 0 / 1-15 / >15 bands were calibrated
    on n=126 and do not transfer to a different population size.
    """
    if not k_50_defined or n_measured < 200:   return "ROW 0"   # instrument failed, NOT a null
    if f_corr > 0.12:                          return "ROW 1"   # DEFECT at material scale
    if f_corr < 0.01:                          return "ROW 2"   # front-end limited
    return "ROW 3"                                              # small real residue
```

| row | condition | consequence |
|---|---|---|
| **ROW 0** | `k_50` undefined, or fewer than 200 candidates measured | **NO VERDICT — instrument failure.** Report what blocked it. Do **not** read as evidence either way. |
| **ROW 1** | `f_corr > 0.12` | **We are dropping correctable codewords at material scale. This is a defect, not a structural gap**, and it outranks everything else on the D-001 board including any decoder-scope question. Re-decompose around it. |
| **ROW 2** | `f_corr < 0.01` | **Front-end limited.** No decode-path constant recovers this. The decoder-scope question goes to the Captain with the front-end-limited count as its denominator. |
| **ROW 3** | otherwise | **Small real residue.** Chase it only if the cause is a single constant or gate; otherwise fold the count into the framing. Captain's call, with a number. |

```python
def c5c_row(c_bottom, n_bottom):
    """C.5c. c_bottom = conversion rate of the bottom pass-0 rank decile."""
    if n_bottom < 500:          return "ROW 0"   # instrument failed
    if c_bottom < 0.01:         return "ROW 1"   # displacement is free
    if c_bottom > 0.05:         return "ROW 2"   # displacement is real
    return "ROW 3"                               # inconclusive
```

| row | condition | consequence |
|---|---|---|
| **ROW 0** | fewer than 500 candidates in the bottom decile | **NO VERDICT — instrument failure.** |
| **ROW 1** | `c_bottom < 0.01` | Displacement costs ~nothing. **RC3's cap-interaction objection is retired**; RC3 becomes a clean ~3.1% for two constants. Captain's call to run it. |
| **ROW 2** | `c_bottom > 0.05` | Displacement is real. **RC3 must not run as specced** — a widening that evicts converting candidates can net negative, which was the original objection. |
| **ROW 3** | otherwise | Inconclusive. Report the full decile curve; RC3 stays deferred. |

Lattice check, done in advance so the gate can populate: pass 0 saturates at exactly 140 candidates
on essentially every cycle × 20 cycles × 3 runs ≈ **8,400 candidates**, so a decile holds ~840 —
comfortably clear of the 500 floor. At `c_bottom` ≈ 1%, SE ≈ 0.34 pp, so the 1% and 5% boundaries
sit ~12 SE apart. The gate can fire.

### 5.5 Sequencing and cost

```
   C.5a  synthetic waterfall  ─┐
   (free, no corpus)           ├─→  C.5b  BER re-read  ──→  gate c5_row
   C.5b needs C.5a's k_50     ─┘     (free, 36 MB on disk)

   C.5c  rank-conversion  ──→  gate c5c_row  ──→  clears or blocks RC3
   (free, independent, runs in parallel)
```

**All three rungs are free of `src/`, of capture, and of NFR-021 exposure.** C.5c is independent and
can run in parallel. A fourth rung — porting C.2's `candidate_diag` capture onto current `main` and
re-measuring on RC1's window at 5.8× the sample — would need a Developer session, and I am **not**
scoping it here: whether it is worth building depends entirely on which row `c5_row` fires.

---

## 6. Citation limits

- **"D-001 is 40% and unexplained" is no longer accurate.** As of RC1: **3.1%** is out-of-band (a
  known, certain, unrelated defect), **8.9%** is no-candidate, **87.9%** is candidate-present-and-
  failed. Cite the decomposition, not the aggregate.
- **`f_nocand = 0.0924` is one window**, 30–49 decodes/cycle, 20m, 3 runs, `260804_085845 →
  260804_090330`. It is not a claim about sparse regimes, other bands, or other times of day.
- **C.2 Phase 1's correlation stands; the inference from it is closed.** Phase 1 found a real
  discriminator and said only re-decoding could establish whether correcting it recovers decodes.
  Phase 2c re-decoded: it does not. Neither half may be cited without the other.
- **"LLR scaling is dead" must not be written as "all LLR avenues are permanently dead."** Phase 2c
  closed *magnitude rescaling* on a direct measurement. That is the strong, narrow claim; the broad
  one was explicitly refused in the 07-26 20:30 ruling §4.5 and is still refused.
- **C.1's +0.93% is a 68-cycle July corpus** (`20260725_live_run_1806`), not the August replication
  corpus. Its *order of magnitude* is what transfers; the figure itself is not measured on the window
  RC1 used.
- **No BER band reading is valid until C.5a produces `k_50`.** Every "≈50% means front-end limited"
  statement in this thread reads against a threshold I invented. Treat all of them as suspended, not
  as background fact.

---

## 7. What this note does not do

- **It does not merge, push, or ask to.** Three branches carry unmerged `src/` and rebuilt binaries
  pending the Captain's HK-011 review. §4.2 and §4.5 are recommendations about them, not requests.
- **It does not authorise C.5.** QA owns the dev-task and the decision to scope it, per HK-015.
- **It does not re-open S.1, M3, or Arm R.D**, and does not touch the post-fix FP surge, which
  remains open with no Task 5 ruling.
- **It does not propose a capture run.** Every measurement in §5 reads artefacts already on disk.
- **It does not resolve Mechanism 1.** That still needs a low-density window, and
  `qa/ARTEFACT_INVENTORY.md` is still the first thing to open before anyone proposes one.

---

*Per HK-015 this is Architect → QA; the dev-task is QA's to author. Per HK-014 I have committed this
locally and will not push or merge. Per HK-011 nothing here changes `src/`. Per HK-006
`pre_merge_check.py` is the Captain's to run. Per NFR-021 no message text or real callsign appears
here; §5's synthetic codewords are Q-prefix, and C.5b/C.5c read only frequency, timing, score, and
BER columns.*
