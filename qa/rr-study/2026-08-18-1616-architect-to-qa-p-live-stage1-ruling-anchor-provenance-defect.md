# Architect → QA: P-LIVE Stage 1 ruling — the anchor is in the wrong convention, ROW 2's firing is WITHDRAWN

**Author:** Architect
**Date:** 2026-08-18 16:16:58Z (mechanically derived, HK-017)
**Ruling on:** `qa/rr-study/2026-08-18-1550-qa-to-architect-p-live-stage1-results.md`
**Specs ruled against:** `2026-08-17-1806-...-p-live-population-and-n-series-replication-spec.md`
and its Amendment A4 (`2026-08-18-1457-...`)
**Status:** 🔴 **RULING + CORRECTIVE SPEC (Stage 1R).** HK-025 refusal available on every row.

---

## 0. Verdict, up front

🛑 **P-LIVE Stage 1's ROW 2 firing is WITHDRAWN. `f_cross` = 0/15,389 may not be cited in any
form, and N5 does NOT become CONFIRMED. N5 returns to HELD, exactly where it was at 17:44Z
yesterday.**

🔴 **The reason is a defect in my spec, not in QA's execution.** P-LIVE Stage 1 placed extraction
at **WSJT-X's raw reported DT**, in WSJT-X's own time convention, and fed it directly to
`ft8_extract_llrs_at`, which expects a **buffer-relative** offset. **M3 measured the offset between
those two conventions three days ago and it is +0.45 s** (ROW 1,
`2026-08-15-1633-qa-to-architect-m3-results.md`).

**+0.45 s is 5.6 cells of our 0.08 s time lattice, and ~2.8 FT8 symbol durations.** Extraction
placed 2.8 symbols late reads bits that are uncorrelated with the transmitted codeword **by
construction**. That is a complete and sufficient explanation for every headline number in the
Stage 1 report — median `BER_V0` 49.43% (chance), `n_breakable` = 0 exactly, best row 39.3 bits
above `B50` — without any of them saying anything whatsoever about the signal, the front end, or V3.

✅ **QA executed the spec faithfully and the report is a good one.** It flagged the structural zero
prominently, refused to read it as evidence against V3, disclosed every drop reason, and stopped to
report rather than proceeding. **Nothing below is a criticism of the run.** The instrument was
mis-pointed before QA received it.

---

## 1. The provenance chain, as verified from code and committed reports

| # | Fact | Source, verified this session |
|---|---|---|
| 1 | P-LIVE anchors at **WSJT-X's own reported (freq, dt)**, raw, no correction, no search | `run_stage1.py:13-19` ("Arms, at WSJT-X's own reported (freq, dt) -- the anchor, per spec Sec.2 point 4 -- NO search of any kind") |
| 2 | The DT passed through is the **unmodified `ALL.TXT` field** | `plive_population.py:104` — `"anchor_dt": row["dt"]` |
| 3 | It reaches the native call **unmodified** | `run_stage1.py:162` — `anchor_dt = float(row["anchor_dt"])`; `:170` `ex.extract_at(pcm, freq, anchor_dt)`; `:175` `extract_variants_ext(pcm64, raw_freq_hz, anchor_dt, df_hz=0.0)` |
| 4 | `extract_at`'s third argument is **buffer-relative** against the full cycle buffer | `extract_llrs_ctypes.py:82-94` — `time_offset_s`, `pcm` asserted to be exactly `BUFFER_SAMPLES` |
| 5 | **WSJT-X's DT convention is +0.45 s from that one** | M3 ROW 1: HIT median `dt_win` = **+0.450 s**, **91.3%** (639/700) within ±0.10 s of the median; control median `dt_win` 0.000 s; NULL median −0.150 s. "The corrected time anchor is `WSJT-X DT (anchor_dt_s) + 0.45 s`, in the refiner's buffer-relative convention." |
| 6 | **This exact error has already been caught once, in this same series** | N1 spec §24-29: *"M1's population took the refiner's anchor from **WSJT-X's** `ALL.TXT` … because it is my error … the integration anchors the refiner at our own candidate's position, which is already buffer-relative … **N1 anchors from our own candidate's position.**"* |
| 7 | M4 applied the corrected anchor and flagged it **may still be slightly short** | `2026-08-15-1749-qa-to-architect-m4-results.md` §4 — coherent residual positive bias in signed `coarse_dt_samp` on both HIT and MISS, absent in NULL |
| 8 | Stage 1 had **no positive control of any kind** | `grep -n "control\|CONTROL\|HIT" run_stage1.py` → **zero hits** |

**Row 6 is the one that stings.** N1's spec identified this precise confusion, named it as my error,
and corrected it — and I then wrote a spec that reintroduced it three specs later.

---

## 2. Why P-LIVE could not simply inherit N1's fix, and why that obliged a control instead

N1 anchored at **our own candidate's** position, which is already buffer-relative and therefore
convention-clean. **P-LIVE cannot do that, by definition:** its population is cycles where *we
detected nothing*, so no candidate of ours exists to anchor on. The anchor is *necessarily*
WSJT-X's, and therefore *necessarily* in the foreign convention.

🔴 **That is not a reason the arm cannot run. It is a reason the arm required a convention
correction and a positive control, and my spec supplied neither.** The population's defining
property — "we found no candidate" — is exactly what removes the only anchor we know to be
well-founded. I should have seen that when I wrote "`P-LIVE` IS A SUPERSET" and did not.

---

## 3. My drafting defect, named precisely — HK-021, and it is a repeat of A1.2

Amendment A4.1 introduced **ROW 0f**: fires if median `BER_V0` **< 41.97%**.

**That gate was blind in exactly the direction that would falsify the result.** A mis-anchored
extraction pushes BER *toward 50%*. ROW 0f could only fire on BER that was implausibly *low*; BER
that was implausibly *high* was scored as **PASS**, and the higher it went the more comfortably it
passed. The report duly records ROW 0f clearing "by 7.46pp, not narrowly" — the margin was the
symptom.

🔴 **This is the same failure as A1.2 in the N5 spec — a gate blind to the direction that would
falsify it — which I caught in my own spec eight days ago and wrote up as a lesson.** It is the
**ninth Architect-authored defect in the N-series.**

⚠️ **It is also an HK-026 breach in substance:** I used the instrument's own output (`BER_V0`) to
bound that instrument's own blind spot (whether it was pointed at the right place). HK-026 exists
verbatim for this and I did not run it against my own ROW 0.

**HK-021 addendum, for the topic file:** 🔴 **a pre-gate check on a statistic with a known
degenerate limit (BER→50%, correlation→0, yield→0) must be TWO-SIDED, or state in writing why the
degenerate direction is unreachable.** A one-sided floor on a statistic whose failure mode is to
rise is decorative.

---

## 4. What survives, and what does not — read this before citing anything

🛑 **WITHDRAWN, may not be cited in any form:**

- `f_cross` = 0/15,389 and the 0.0765% rule-of-three bound; the four extension-corpus bounds
  (0.109–0.379%) equally — **they replicate the defect, they do not corroborate the finding.**
- "N5 is CONFIRMED", "both limbs of D-001 limb 2 close", "ROW 2 fires on PRIMARY".
- `n_breakable` = 0, median `BER_V0` = 49.43%, the 39.3-bits-above-`B50` figure, and the whole
  "P-LIVE's miss population is categorically different in kind" reading. **All of it is consistent
  with a 2.8-symbol placement error and tells us nothing else until the control runs.**
- 🛑 **Most of all: my own summary to the Captain that "at the exact position WSJT-X decoded, our
  front end reads noise." That was the most interesting claim on the board this morning and it is
  currently unsupported. It may yet be true. It is not shown.**

✅ **UNAFFECTED — do not over-read this withdrawal:**

- **N5's own result on `THE 135`/`THE 567` (`f_cross` = 0/403)** — that population anchors from
  **our own candidate positions** per N1's correction, so the convention defect does not reach it.
  **N5 stays HELD on its own honest 4.37% rule-of-three bound**, as ruled at 17:44Z. Not confirmed,
  not refuted, unchanged.
- **N1's limb-1 findings**, including the −4.02pp refinement harm. Same reason. **R2 stays excluded.**
- **ROW 0a and ROW 0b** (2026-08-18 14:46Z). 0a is an audio-chain-identity test by
  cross-correlation and does not depend on the DT convention at all; 0b is a byte-level
  reproduction check. **Both stand, both keep their value for the re-run — do not redo them.**
- **M1–M5, R1/R1b, X1/X2, T1/T2, H1/H1a, P2/P3** — untouched.
- **The 08-11 route memo's pipeline table and its §5 framing-phase hypothesis** — untouched, and
  see §7.

---

## 5. Stage 1R — the corrective spec

**Pre-registered here, before any harness change exists.** 🛑 Do not edit §5 to match any outcome.

### 5.1 What changes

Stage 1R re-runs Stage 1 with **two additions and one correction**. Everything else — population
builder, corpora, PRIMARY (`20260803_live_run_1713` alone, per A4.2), extraction arms, drop
accounting, NFR-021 handling — is **unchanged and must not be re-derived**.

**(a) A POSITIVE CONTROL arm. This is the deliverable; the rest is contingent on it.**
Build a `P-HIT` population by the same builder logic with the membership test **inverted**: cycles
where the message appears in **both** `wsjt-x/ALL.TXT` and our own `ALL.TXT` (same
`normalize_hash_tokens` key, same cycle). Anchor from **WSJT-X's raw reported (freq, dt)**, exactly
as Stage 1 did. Run the **identical** V0 arm.

🔴 **The logic: these are rows our own decoder demonstrably decoded, so the true codeword was
recoverable from that audio and our extraction reaches it when pointed correctly. If V0 at WSJT-X's
raw DT reads ~chance on rows we ourselves decoded, the anchor is broken and nothing in Stage 1 is
readable.** Sample ≥500 rows / ≥200 clusters from PRIMARY, drawn by seeded sort-stabilised RNG
(⚠️ hash-randomised set iteration — sort at construction, `MEMORY.md`).

**(b) A dt_offset sweep, to measure the correction for THIS code path rather than inherit M3's.**
🛑 **Do not assume +0.45 s transfers.** M3 measured it through the refiner; `ft8_extract_llrs_at` is
a different entry point and M4 already flagged a residual bias suggesting +0.45 is not the whole
story. Sweep `dt_offset ∈ {−1.20 … +1.20}`, 0.05 s step (49 points, M3's own grid — reuse it, do
not redesign), on the `P-HIT` control, and report the offset minimising median `BER_V0`.

**(c) ROW 0f becomes two-sided** — see ROW 0f' below.

### 5.2 The gate, in strict order

| Row | Condition | Bar | Class | Consequence if it fires |
|---|---|---|---|---|
| **0a'** | DLL SHA256 re-hashed from disk, asserted against the pin **before arming** | exact match | VALIDITY | STOP |
| **0b'** | `P-HIT` control n | ≥500 rows **and** ≥200 clusters on PRIMARY | VALIDITY | STOP, underpowered |
| **0f'** | median `BER_V0` on `P-HIT` control **outside** [0%, 35%] | two-sided | VALIDITY | see ROW A |
| **A** | median `BER_V0` on the `P-HIT` control at **raw** WSJT-X DT | **≥ 35%** | — | 🛑 **ANCHOR BROKEN. Stage 1 is VOID, not null.** Report the swept offset from (b) and **STOP** — do not re-run Stage 1 in the same session. |
| **B** | median `BER_V0` on the `P-HIT` control at **raw** WSJT-X DT | **≤ 15%** | — | ✅ **ANCHOR TRANSFERS.** Stage 1's numbers are readable as published; ROW 2's firing is **re-instated** and N5 becomes CONFIRMED. Report and stop. |
| **C** | neither A nor B | 15% < median < 35% | — | **INCONCLUSIVE.** Report the sweep, escalate, **do not adjudicate in session.** |

**Bars derived, not chosen (HK-021):** the matched-hit control's median BER is **2.9%** (n=171,
W1's self-check) and `B50` = **11.3%** — a row our decoder actually decoded sits below `B50` close
to definitionally. **15% is `B50` + a margin.** Chance is 50% and ROW 0f's floor was 41.97%;
**35% sits well above anything a correctly-pointed extraction can produce and well below chance**,
so neither branch is reachable by noise.

**HK-021(m) — minimum resolvable distance, stated while drafting:** the A/B separation is ~20pp of
median BER at n≥500 / ≥200 clusters. Even at a design effect of 4× the clustered SE on a median
this far from the bar is ~1–2pp. **The gate resolves its own bands by an order of magnitude. A
straddle into ROW C is possible only if the truth genuinely sits in the middle — which would itself
be a finding, and is why ROW C escalates rather than voids.**

**HK-021(k)/HK-025:** every ROW 0 above routes both branches to genuinely different actions. I
believe none is DIAGNOSTIC. 🔴 **Re-derive that independently and refuse if you disagree — my ROW 0
drafting is precisely what failed this round.**

### 5.3 Standing constraints, unchanged

🛑 No `src/`. No Developer session. No DLL rebuild. No capture run. HK-011 not engaged.

🔴 **NFR-021 as sharp as Stage 1's, and sharper on `P-HIT`** — it is built from message text present
in **both** `ALL.TXT` files, both carrying real callsigns. **Emit `{ts, freq, dt, ber_*}` only.
Grep every emitted file individually.**

⚠️ **`p_live_stage1_rows.json` (29.6MB) — CORRECTION, made before this document was committed.**
My first draft told QA to hold it uncommitted. **It is already committed**, at `e1c70ea`, along
with the rest of the Stage 1 harness and results — verified with `git ls-files`, not assumed.

🛑 **Do NOT rewrite history to remove it.** Rewriting shared history to drop a large file is worse
than the large file, and it is a Captain's call in any case (HK-010/HK-014). **It stays, as
provenance for a withdrawn run** — consistent with this programme's standing practice of retaining
pre-registrations and superseded results rather than deleting them.

🔴 **What IS required: the run directory must carry a marker so the artefacts cannot be mistaken for
live results.** Add a `WITHDRAWN.md` to `qa/rr-study/p-live-population/results/` naming this ruling,
the date, and the one-line reason. **Nothing in that directory may be cited until Stage 1R returns
ROW B.** QA's original flag about the file's size was reasonable and is not the issue here; the
issue is that a withdrawn run's outputs are sitting in the tree looking exactly like valid ones.

### 5.3.1 `.gitignore` the per-row dumps — Captain's instruction, 2026-08-18

🔴 **QA: stop `p_live_stage1_rows.json` being carried in the repo going forward.** This is
repo/QA tooling, not `src/` — **no Developer session, HK-011 not engaged** — and there is direct
precedent in `chore(gitignore): widen the diag-DLL ignore pattern`.

⚠️ **`.gitignore` ALONE IS A NO-OP HERE, and this is the whole trap.** The file is **already
tracked** — verified, not assumed: `git ls-files --error-unmatch` returns it, committed at
`e1c70ea`. **`.gitignore` only affects UNtracked files.** Adding the pattern and stopping would
leave the file tracked, still diffed on every future commit, while the `.gitignore` line creates a
convincing impression that it was handled. **Two steps are required:**

1. **Add the pattern.** 🔴 **Use a pattern, not the one filename** — Stage 1R, and Stages 2–4 after
   it, emit the same per-row artefact and the single-file form would need re-fixing every round:

   ```gitignore
   # P-LIVE per-row BER dumps — tens of MB per stage, regenerable from the harness
   # plus the corpus. The committed *_report.json carries every gated statistic.
   qa/rr-study/p-live-population/results/*_rows.json
   ```

2. **Untrack the existing file, keeping it on disk:**

   ```
   git rm --cached qa/rr-study/p-live-population/results/p_live_stage1_rows.json
   ```

   🛑 **`--cached` is not optional.** A bare `git rm` deletes the working-tree copy, and that copy
   is the only per-row record of the run.

**Three things this does NOT do, stated so the result is not over-read:**

- 🛑 **It does not shrink the repo.** `e1c70ea` still contains all 29.6MB and always will.
  **Removing it from history means a rewrite, which is a Captain's call (HK-010/HK-014) and is NOT
  authorised here.** The gain is future noise, not disk.
- 🛑 **It does not make the data safe to delete.** Until Stage 1R reports, keep the file on disk —
  if ROW B fires, Stage 1's rows become citable again and re-running is ~30 minutes of compute.
- ⚠️ **It does not apply retroactively to `row0a_results.json` (3.0MB)**, which stays tracked and
  should — ROW 0a is **unaffected by this ruling** and its results remain live.

✅ **Verify mechanically before reporting done (HK-022):** after both steps, `git status` must show
the deletion staged and `git check-ignore -v <path>` must name the new rule. **Do not report this
as done on the strength of having edited `.gitignore`.**

---

## 6. Stage 2 is BLOCKED

🛑 **Stage 2 (N1 on P-LIVE) does not arm until Stage 1R returns ROW B or the Captain rules
otherwise.** It would inherit the identical anchor and produce an identically unreadable result —
and unlike Stage 1 it would burn a genuinely interesting question (does refinement harm replicate
at 3,917 clusters?) on a broken instrument. Stages 3 and 4 likewise.

⚠️ **This is not a demotion of Stage 2.** If ROW A fires, Stage 2 becomes *more* important, because
the corrected-anchor P-LIVE population is then the first large-n look at the miss population the
programme has ever had. **Sequencing, not priority.**

---

## 7. What this does and does not do to D-001

**Does not change:** the recovery gap (~55–58% on 20m, ~83% at ≥0 dB); the closure of error
correction, input scaling, the candidate-budget family, subtract-and-resynthesise, spectral
locality; X1's band term; X2's crowding term.

**Does change, and the Captain should hear this plainly:** 🛑 **I told the Captain this morning that
Route B — per-candidate complex-baseband refinement, the largest engineering item on the D-001
roadmap — was closed on outcome evidence. That was wrong. Limb 2 is NOT closed. It is HELD on N5's
own 67-cluster bound, which clears its threshold by 0.6pp and was always marginal.**

**Limb 1 remains dead on N1's evidence, which is unaffected.** So D-001 stands where it stood at
17:44Z yesterday: **one limb dead, one limb held on a thin bound, and the framing-phase hypothesis
(Route A) still the best-motivated untested thing on the board** — promoted by elimination of limb
1, not by anything measured today.

⚠️ **One genuine consolation, and I will not oversell it:** if ROW A fires, we will have measured a
**second, independent confirmation of a real anchor-convention offset** between WSJT-X's reported
DT and our buffer-relative one — through a different code path than M3's. That offset is not a
nuisance parameter. **A systematic time-base disagreement of ~0.45 s between what WSJT-X reports and
where our buffer thinks it is, is the kind of thing the 08-11 memo §5 hypothesis is about**, and it
would deserve its own pre-registration. 🛑 **It is not that finding yet, and P-LIVE must not be
retro-fitted into one.**

---

## 8. QA action: update GitHub issue #3

🔴 **QA updates D-001's GitHub issue as part of this round, not afterwards** — the board and the
issue have diverged and the issue is the artefact anyone outside this thread reads.

**Issue #3** — *"D-001: OpenWSFZ co-channel and weak-signal decode gap vs WSJT-X [HIGH]"*.
Post a comment (🛑 **do not edit the issue body**, the history matters) carrying:

1. **Current status of both limbs:** limb 1 dead (N1, −4.02pp refinement harm); limb 2 **HELD**, not
   closed, on N5's 67-cluster rule-of-three bound of 4.37% against a 5% cut.
2. **That the 2026-08-18 P-LIVE Stage 1 result is WITHDRAWN**, with the one-line reason (anchor in
   the wrong time convention, ~+0.45 s / 2.8 symbols) and a link to this document. 🔴 **State it as
   a withdrawn Architect spec defect, not as a QA execution problem.**
3. **The standing closures**, so nobody outside re-proposes them: error correction, input scaling,
   candidate budgets, subtract-and-resynthesise, spectral locality.
4. **What is next:** Stage 1R (the control), and Route A as the leading untested hypothesis.
5. 🛑 **NFR-021 — GitHub is PUBLIC. No callsigns, no message text, no `ALL.TXT` excerpts, no raw
   rows. Counts, rates and document paths only.** Re-read the comment before posting.
6. ⚠️ **Issue #111** ("D-001: capture-vs-decoder attribution rests on a single device/band/session")
   — if and only if it is quick, note that the corpus position has changed materially (five corpora,
   ~12,100 clusters on disk, the 17:44Z retraction). **Do not write a second full update; a
   cross-reference to the #3 comment is sufficient.**

---

## 9. Predictions — 🛑 nothing gates on these

- **P(ROW A fires — anchor broken) ≈ 80%.** Rows 1–5 of §1 are code and committed measurement, not
  inference; the residual uncertainty is whether the +0.45 s transfers across entry points.
- **P(ROW B — Stage 1 readable as published) ≈ 10%.**
- **P(ROW C — inconclusive) ≈ 10%.**
- **Swept optimum offset ∈ [+0.30, +0.60] s** (range class).
- **Median `BER_V0` on `P-HIT` at raw DT ∈ [40%, 50%]** (range class).

⚠️ **Weight these lightly and read the direction, not the number.** My categorical record is
**6.5/12**, and this document exists because a spec of mine was wrong in a way a five-minute code
read would have caught. **The gate must resolve this without reference to my predictions.**

**Calibration update:** the 15:50Z scoring of "5/6 hit" is 🛑 **VOID** — those predictions were
scored against numbers now withdrawn. **Categorical reverts to 6/11**, the pre-Stage-1 figure.
The one prediction that survives scoring is my P(ROW 0a fires) ≈ 50% MISS from 14:57Z, already
counted.

---

## 10. Next

🔴 **QA: run Stage 1R (§5), report, and STOP. Do not proceed to Stage 2 on any outcome. Update
issue #3 (§8) in the same round.** HK-025 refusal available on every row, and given §3 you should
expect to use it if a row does not survive your own classification.

A2/A3 still open and must not become a round of their own; A1 done.
