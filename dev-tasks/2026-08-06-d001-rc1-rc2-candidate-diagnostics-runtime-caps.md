# Developer handoff: D-001 RC1 (per-decode attribution) + RC2 (runtime-settable candidate caps)

**Authored by:** QA (per HK-000/HK-015). **Status: AUTHORISED** by the Captain, 2026-08-07, per
`2026-08-07-1616-architect-to-qa-captain-rulings-and-d001-reconciliation.md` §1.1 — RC1+RC2,
bundled, one Developer session. This file is now the vehicle. Per HK-011 the Captain still
reviews the `src/` diff before any push, and per HK-006 `pre_merge_check.py` remains the
Captain's to run, not QA's or the Developer's.

> 🔴 **S.1r flag (per the 1616 handoff §6.1's instruction to flag this at the top before the
> Developer session starts):** S.1r ran 2026-08-07 —
> `qa/cycleframer-alignment-replay/2026-08-07-s1r-spectral-locality/s1r_report.md`. At the
> **pre-registered** 50/150 Hz boundary the result is **ROW 4 (no verdict)**: the `clear
> (>150 Hz)` Separation level has zero surviving strata (0/12) once a live-discovered band-edge
> confound is excluded (WSJT-X decodes outside OpenWSFZ's hardcoded [200, 3000) Hz search band
> are 100% missed by construction, per the 2323 note §4, and were inflating that level's
> apparent miss rate). **RC1's gate stands exactly as specced below — it is NOT narrowed.**
> Reported for context only, never gating: a tighter, still physically-motivated *sensitivity*
> boundary (25/100 Hz) shows both mechanisms LIVE and large (E_sep=+49.0pp p<1e-6, E_dens=
> +11.2pp p<1e-5) — suggestive that locality matters a great deal in this dense window, but this
> does not pre-empt RC1's own diagnostic classification below, which is decode-side and
> independent of S.1r's observational design.
>
> 🔴 **Superseding update, 1616 handoff §7.9 (Captain's direction, 2026-08-07): standalone S.1r is
> retired — do not re-run §7.1–§7.7 as specced.** Spectral locality is instead re-evidenced as a
> **rider on RC1 itself, zero additional playback**, because RC1's per-candidate list answers the
> mechanism directly (was a candidate generated there at all?) rather than S.1r's correlate (do
> misses cluster spectrally?). The rider is folded into RC1's own procedure below — see the new
> **§4.5**. It is non-gating: **it cannot narrow or reverse RC1's own ROW 1/2/3 verdict** (§4's
> `f_nocand` gate is untouched); if the two disagree, RC1 governs and the disagreement is itself
> the finding.

**Source:** `qa/cycleframer-alignment-replay/2026-08-06-2336-architect-to-qa-spec-d001-root-cause-rc1-rc4.md`
§2 (RC1), §3.1 (RC2's runtime-settable-caps prerequisite), §5 (why these two are bundled).
**Captain's open decision this unblocks:** §7.1 of
`2026-08-06-2346-architect-to-qa-handoff-index-and-work-queue.md` — "Authorise the RC1 (+RC2)
Developer session? RC1's 15 minutes decides whether RC2/RC3's 45 are worth spending." **Answered
2026-08-07: yes.**

---

## 1. Why this is the right experiment, and why these two are bundled

D-001's deficit is real and localised (WSJT-X 752/cycle-window vs our 461, on identical replayed
audio, 40.4% miss rate). The leading mechanism, found from data already on disk: both candidate
caps are saturated on ~95% of cycles (`K_MAX_CANDIDATES=140` pass 1, `K_MAX_CANDIDATES_PASS2=200`
pass 2), and the budget is allocated backwards — pass 1 converts candidates to decodes at 16.4%
and is capped at 140; pass 2 converts at 0.80% and is given 200. That parameter family was
excluded from D-009's 45-point grid by construction.

Saturation alone does not prove the *missed* decodes were in the truncated tail — candidates are
ranked by sync score, so a truncated tail is *consistent* with the miss profile but is not
evidence (candidates are ranked, so a signal present but scored low would be truncated the same
way whether or not it was ever going to decode). **RC1 is the diagnosis; RC2 is the treatment.**
They are independent edits in the same files (`ft8_shim.c`, `Ft8LibInterop.cs`), so one Developer
session, one build, one review covers both — but RC2 must not run until RC1 reports (§4 below),
and RC1 alone is only 15 minutes of playback against 30–45 for RC2.

## 2. RC1 — the `src/` change (diagnostic only, no logic change)

Add a new TLS getter, in the same family as the existing `ft8_get_last_candidate_counts`,
`ft8_get_last_pass_counts`, `ft8_get_last_llr_stats` (all already exported, P/Invoked at
`Ft8LibInterop.cs:324/336/347`, called every decode at `Ft8Decoder.cs:280-294`). This one exposes
the per-pass candidate **list** rather than its count: for each candidate,
`(time_offset, freq_offset, score)` exactly as `ftx_find_candidates()` returned it, before any
LDPC attempt.

**No decode logic, pass configuration, candidate search, or struct layout changes.** Export,
P/Invoke, adapter and interface follow the existing pattern exactly (same shape as shim 20260018,
per the Architect spec §2.1). **State the `time_offset` units explicitly in the write-up** — the
spec is explicit that it has not verified whether the candidate struct's `time_offset` is in
symbols or seconds, and QA must not guess the conversion when classifying decodes against it.

## 3. RC2 — the `src/` change (runtime-settable caps + the array-sizing landmine)

### 3.1 Make the caps runtime-settable

`K_MAX_CANDIDATES` and `K_MAX_CANDIDATES_PASS2` are compile-time `#define`s (`ft8_shim.c:467,
504`). Extend the existing `ft8_set_decode_params()` runtime-setter mechanism (already used for
the D-009 parameters, e.g. `s_k_min_score_pass2`) to cover both caps, so a sweep over them becomes
one rebuild, N configurations — not one rebuild per point.

### 3.2 ⚠️ Mandatory, already documented as a latent overflow — do not rediscover it

`ft8_shim.c:514-525` already documents that the local `candidates[]` array is sized
`K_MAX_CANDIDATES_ANY_PASS`, and `K_MAX_DECODED` is `K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2`.
**Raising either cap past 200 at runtime requires the array allocation and both dependent macros
to be driven from the runtime maxima, not the old compile-time constants.** This exact class of
bug (`candidates[]` sized to a value that stops being the true maximum once caps move) was found
once already during the 2026-07-26 `K_MAX_CANDIDATES` cap-sweep task
(`dev-tasks/2026-07-26-d001-candidate-cap-sweep.md` §2 — a genuine stack-buffer-overflow landmine
in the same array, same root cause). **It must be handled deliberately in this session, not
rediscovered a third time.** Confirm no crash/hang at the largest configuration tested (`C3`, pass
1 = 560) before trusting any of its numbers.

## 4. Procedure and sequencing — RC1 gates RC2

**Step 1 — RC1 only.** Replay the busy window (`260804_085845 → 260804_090330`, the same 20-cycle
window used throughout the 08-06 replay series), 3 runs, pass 1 only. For every WSJT-X decode we
did not produce, classify against the new getter's output:

| class | test |
|---|---|
| `OUT_OF_BAND` | WSJT-X `freq_hz` outside `[200, 3000]` |
| `NO_CANDIDATE` | no candidate within tolerance of the decode's (DT, freq) |
| `CANDIDATE_NOT_DECODED` | a candidate was present; decode failed |

Tolerance: frequency ±6.25 Hz (one FT8 tone spacing); time — our reported DT runs **+0.65 s**
against WSJT-X's on this pipeline (per the 2115 ANOVA note §4) — **centre the DT window on that
measured +0.65 s offset, not on zero**, and allow ±0.5 s either side. Report the three-way split
overall and stratified by SNR band and density band, using the same bands as the 2323 note
(`2026-08-06-2323-architect-where-the-decode-gap-actually-lives.md`), so it joins directly to that
stratification.

**Gate — evaluate before touching RC2 at all:**

```python
def rc1_row(f_nocand):  # f_nocand = NO_CANDIDATE / (total misses - OUT_OF_BAND)
    if f_nocand > 0.60:  return "ROW 1"  # candidate generation is the root cause -> RC2 is the lever
    if f_nocand < 0.30:  return "ROW 2"  # decode is the root cause -> RC2 will NOT help, do not run it
    return "ROW 3"                        # MIXED -> report stratified, no single lever
```

**If RC1 fires ROW 2, stop. Do not proceed to RC2** — its mechanism is already excluded by the
data; report RC1's result and return to the Architect/Captain for what comes next (RC4 depth
becomes the thing worth revisiting per the source spec's §5 sequencing diagram, not this task).

## 4.5 S.1r-R rider — spectral locality, folded into RC1 (non-gating, zero extra playback)

**Run this regardless of which row RC1's own gate fires.** It reuses RC1's classification output
(§4's three-way split) and adds one predictor, `sep`, computed from the WSJT-X reference set
already collected for §4 — no new capture, no new decode run.

**Predictor.** For every **in-band** WSJT-X decode (i.e. excluding `OUT_OF_BAND`, per §4's own
band-edge exclusion — same 50-record exclusion the 2323 note reports as 47+3), compute `sep` = Hz
to the nearest *other* WSJT-X decode in the same cycle. Undefined for single-decode cycles ⇒
excluded, count reported.

**Stratification — terciles of the *observed* `sep` distribution among in-band misses, computed
before outcomes are joined.** Sort the in-band misses' `sep` values; split into three equal-count
bins T1 (tightest spacing) / T2 / T3 (most isolated). This is a structural fix over the retired
standalone spec: terciles of a continuous variable are populated by construction, so §7.8's
"boundary sat at the 97th percentile and couldn't populate" failure cannot recur here. Report the
observed `sep` cutpoints and each tercile's `n` (expect ≈492 each on the corpus this was sized
against — recompute for whatever `n` this run actually produces, since RC1 replays the busy window
3 times, not 5).

**Gate:**

```python
def s1rr_row(d_cnd, d_noc):
    """
    d_cnd = (CANDIDATE_NOT_DECODED share of in-band misses in T1) minus (same share in T3), pp.
    d_noc = (NO_CANDIDATE share of in-band misses in T1) minus (same share in T3), pp.
    T1 = tightest tercile, T3 = most isolated. Boundaries strict; rows mutually exclusive in order.
    """
    if d_cnd > 15.0 and abs(d_noc) < 5.0:   return "ROW 1"   # LOCAL: collision/subtraction
    if d_noc > 15.0 and abs(d_cnd) < 5.0:   return "ROW 2"   # GLOBAL: candidate budget confirmed
    if d_cnd > 15.0 and d_noc > 15.0:       return "ROW 3"   # BOTH real
    return "ROW 4"                                            # no verdict
```

`15.0` pp is ~6.5 SE at n≈492 per tercile; `5.0` pp is ~2 SE and is the "flat" bar. Report `d_cnd`,
`d_noc`, the row, and the full T1/T2/T3 × {NO_CANDIDATE, CANDIDATE_NOT_DECODED} cell table
regardless of which row fires — per HK-021, boundary values fall to ROW 4 by construction, do not
round toward a verdict.

⚠️ **This rider does not gate RC1 and cannot change RC1's §4 verdict.** It is reported alongside
RC1's result, not in place of it. If `s1rr_row` and `rc1_row` disagree (e.g. RC1 fires ROW 3 mixed
but the rider fires ROW 2 global-only), report both and say so plainly — do not adjudicate between
them in this task.

**Step 2 — RC2, only if RC1 fired ROW 1 or ROW 3.** 3 runs each, pass 1 only, busy window, against
these configurations (`C0` is free — the 5 runs already on disk, 461 decodes/run baseline):

| | pass 1 cap | pass 2 cap | tests |
|---|---:|---:|---|
| `C0` | 140 | 200 | baseline, already measured |
| `C1` | 280 | 200 | does pass 1 keep converting past its ceiling? |
| `C2` | 340 | 60 | reallocation at ~constant total budget |
| `C3` | 560 | 200 | **conditional** — only if `C1` fires ROW 1 below |

FP arms: the existing S5/S7 synthetic scenarios, unchanged, sequential per the standing
CONTAMINATED.md constraint (never run concurrently).

**Gate, evaluated per configuration** (`g` = mean decodes/run(C) − 461):

```python
def rc2_row(g, s5_fp, s7_fp, s7_base):
    if g > 40.0 and s5_fp == 0 and s7_fp <= s7_base:  return "ROW 1"  # cap was binding, live lever
    if g > 40.0:                                       return "ROW 2"  # gain at an FP cost
    if g < 10.0:                                        return "ROW 3"  # not the constraint
    return "ROW 4"                                                      # partial, report g per config
```

`40.0` is ~5x the baseline's own run-to-run spread (8 counts across 5 runs) and ~14% of the
291-decode gap to WSJT-X. `10.0` is just above noise. Boundaries fall to ROW 4 by construction —
do not adopt a knife-edge reading. **Adoption of any configuration is the Captain's call, not
QA's or the Developer's**, regardless of which row fires.

## 5. Definition of done

- [ ] RC1 getter added: export, P/Invoke, adapter, interface — same pattern as the three existing
      TLS getters. `time_offset` units stated explicitly in the write-up (verified, not assumed).
- [ ] RC1 run (3 runs, pass 1, busy window), three-way classification reported overall + by SNR
      band + by density band, gate evaluated per §4's code.
- [ ] §4.5 rider computed regardless of §4's outcome: `sep` per in-band WSJT-X decode, terciles
      populated and reported (cutpoints + per-tercile `n`), `d_cnd`/`d_noc` and `s1rr_row`
      reported alongside — never in place of — RC1's own verdict.
- [ ] **If RC1 fires ROW 2: stop here.** Report and hand back — RC2 is not authorised to proceed
      by this task in that case, regardless of the bundling. The §4.5 rider is still reported.
- [ ] If RC1 fires ROW 1 or ROW 3: caps made runtime-settable via `ft8_set_decode_params()`
      extension; §3.2's array-sizing fix applied and confirmed present at every configuration
      tested, including the untested-at-scale `C3`.
- [ ] RC2 run (`C0` free, `C1`+`C2` always if reached, `C3` only if `C1` fires ROW 1), gate
      evaluated per configuration per §4's code, S5/S7 FP arms run sequentially (never concurrent).
- [ ] No crash/hang confirmed at the largest configuration actually run.
- [ ] `python3 tools/pre_merge_check.py` green (HK-006) before any "ready" claim.
- [ ] `git status` clean of any locally-rebuilt `libft8.dll` unless a configuration change is
      being deliberately kept — do not leave one staged by accident (per the 07-26 cap-sweep
      task's own closing note: it silently changes every other test's decode counts on this
      machine).
- [ ] Per HK-011: present the `src/` diff to the Captain for explicit pre-push sign-off before any
      merge. Per HK-010: merge always needs the Captain's explicit sign-off, green CI
      notwithstanding.

## 6. What this does not do

- Does not run RC3 (search-band widening) or RC4 (depth, `K_MAX_PASSES` 2→3) — both explicitly
  sequenced after this task in the source spec (RC3 must follow RC2 only; RC4 is recommended
  against unless RC1 fires ROW 2). Separate dev-tasks if/when authorised.
- Does not touch Arm R.D, Measurement D, D-009's parameter decision, or any existing pre-registered
  gate.
- Does not re-derive or revise any D-001 figure in `project-state-2026-07-31-d001-competition-confirmed.md`.
- Does not decide FP-cost tradeoffs or cap adoption — every gate above routes an adoption decision
  back to the Captain, never resolves one itself.

## 7. Cross-references

- `qa/cycleframer-alignment-replay/2026-08-06-2336-architect-to-qa-spec-d001-root-cause-rc1-rc4.md`
  — full spec, RC1 §2, RC2 §3, sequencing diagram §5, cost table.
- `qa/cycleframer-alignment-replay/2026-08-06-2323-architect-where-the-decode-gap-actually-lives.md`
  — the SNR/density stratification RC1's classification joins to.
- `dev-tasks/2026-07-26-d001-candidate-cap-sweep.md` §2 — the prior instance of the exact
  array-sizing overflow §3.2 above requires handling again, deliberately this time.
- `qa/cycleframer-alignment-replay/2026-08-06-2346-architect-to-qa-handoff-index-and-work-queue.md`
  §6, §7.1 — why this is bundled, and the open Captain decision this task exists to answer.
- `qa/cycleframer-alignment-replay/2026-08-07-1616-architect-to-qa-captain-rulings-and-d001-reconciliation.md`
  §1.1 (authorisation), §1.5.2 (D-009 Option B must not ship before RC2's `C0` baseline is
  measured — this task's RC2 leg is what that baseline depends on), §7.8 (standalone S.1r's ROW 4
  and why), §7.9 (the rider retiring standalone S.1r and specifying §4.5 above).
- `qa/cycleframer-alignment-replay/2026-08-07-s1r-spectral-locality/s1r_report.md` — the retired
  standalone S.1r run; retained for provenance of the band-edge exclusion and the boundary-choice
  lesson, not re-run.

---

*Per HK-015 this is QA-authored, for a Developer session. Per HK-011 not to be started without the
Captain's explicit authorisation — this file's existence is not that authorisation. Per HK-010
merge still needs separate explicit sign-off even after a green build. Per NFR-021 no message text
or callsign appears here.*
