# Architect → QA — spec: the post-drift-fix false-positive surge, plus the Window 4 closure
# Four tasks. One closes a stale record; three test one hypothesis. All offline or bench.

**Author:** Architect, 2026-08-04 (15:00 UTC, `date -u`, per HK-017). Repo at `c3c11e3`.
**For:** QA.
**Raised by the Captain, 2026-08-04:** OpenWSFZ has been emitting *"a whole lot of false
positives since the drift fix"*, and the ~40% shortfall against WSJT-X is still unexplained.
**Priority:** this goes **ahead of** `2026-08-04-1441-…-isolated-replay-rerun-post-drift-fix.md`.
That spec measures how much live-path loss the fix recovered; the answer is worth less if part of
what came back is junk.

---

## 0. The board

| # | task | kind | verdict? | cost |
|---|---|---|---|---|
| **1** | Close Window 4 against `be5960a` | Closure, evidence-backed | **Yes, mechanical (§2)** | ~15 min |
| **2** | Re-run S5 — baseline FP rate vs the ratified bar | Bench, ratified instrument | **Yes, already ratified (§4)** | ~1 h |
| **3** | Candidate-budget saturation on the 08-03 corpus | Offline measurement | **Yes, mechanical (§5)** | ~1 h |
| **4** | Live-band FP proxy by callsign recurrence | Offline observation | **No — no oracle (§6)** | ~30 min |

**No capture run. No `src/` change.** Task 2 needs the loopback rig; 1, 3 and 4 are pure analysis
of corpora already on disk.

---

## 1. The hypothesis these tasks test

Two hard numbers from `src/OpenWSFZ.Ft8/Native/ft8_shim.c`:

```
:467   #define K_MAX_CANDIDATES        140   /* pass 0 */
:504   #define K_MAX_CANDIDATES_PASS2  200   /* pass 1 */
```

And `qa/endurance/2026-08-02-multiday-20m-anova/CONTAMINATION-NOTE.md` records 8081 **"held steady
at 140 throughout"** — that is the pass-0 cap, pinned.

**If the candidate budget is saturated, candidates are rivalrous.** `ftx_find_candidates` keeps the
top N by sync score and discards the rest, so every false candidate holding a slot displaces a real
signal that scored below it. Under that reading the Captain's two symptoms are **one mechanism**:
a full budget both emits false positives and misses signals WSJT-X finds.

**Why it would surface now.** A misaligned window degraded every candidate's score, real and
spurious alike — drift was acting as an accidental FP filter, bought with sensitivity we did not
know we were paying. `be5960a` removed it, so both populations clear the gates again. On this
reading the FPs are **not a regression the fix introduced**; they are the operating point the D-009
gates were always calibrated to, visible for the first time.

**This is a hypothesis, not a finding.** Task 3 is what makes it testable. If saturation is rare,
it is refuted and the FP question stands on its own.

## 2. Task 1 — close Window 4 against `be5960a`, with a measurement

**Attribution, from the Captain, 2026-08-04:** the ~14 h decode collapse of 2026-08-01
(`CONTAMINATION-NOTE.md` Window 4) was the capture window drifting past FT8's ~2.36 s guard, and
`be5960a` fixed it. The supporting arithmetic is already on record — the FT-991A chain at 48.0 ppm
reaches the guard at **~13.7 h**, the collapse hit at **~14 h**, a daemon restart cured it while a
radio power-cycle did not, and 8081 (4.7 ppm, needs ~118 h) was unaffected on the same band in the
same minutes. I find the attribution convincing.

**Measure it anyway before closing.** This programme has twice recorded a closure that had not
happened — §1 of the D-001 ground-truth memory carried a wrong claim for two days, and the ~12 h
cap was lifted on one. An attribution this good still deserves ten minutes of evidence.

**Method.** On `artefacts/20260803_live_run_1713/`, decisive epoch 1 (18.96 h, past the cliff, on
the fixed build): compute per-cycle `ratio = openwsfz_decodes / wsjtx_decodes`. WSJT-X sits behind
the same splitter, so propagation is common-mode and cancels — this is a control, not a second
measurement.

**Pre-registered rule** (commit before running; strict order, first match wins):

| row | condition | consequence |
|---|---|---|
| **1 VOID** | either uptime window `[0, 13.7 h)` or `[13.7 h, end]` has `< 200` cycles with both legs non-zero | no verdict; Window 4 stays open |
| **2 NOT CLOSED** | `median(ratio, after) < 0.80 × median(ratio, before)` | the cliff is still present ⇒ **escalate; do not close anything** |
| **3 CLOSED** | otherwise | no cliff past 13.7 h on the fixed build ⇒ close, per §2.1 |

**On ROW 3 only:**
- Close `dev-tasks/2026-08-01-8080-decode-collapse-after-long-uptime.md`, citing `be5960a` and this
  measurement.
- Supersede `CONTAMINATION-NOTE.md` Window 4's *"Root cause not yet identified"* — amend in place
  with a dated note; **do not rewrite the original observation**, it was recorded correctly and its
  diagnostic detail is what made the attribution possible.
- Record that the disarmed cross-instance detector (disarmed 2026-08-01) **is not needed for this
  failure mode**. It may still be wanted for others; that is a separate question and stays open.

## 3. Standing constraint for tasks 2–4

**WSJT-X is a co-appraiser, not an oracle** — 86.9–93.0% within-appraiser repeatability on
bit-identical audio (S6, two corpora). Nothing below may treat a WSJT-X-only decode as
automatically real or an 8080-only decode as automatically false. That framing is ratified as D1 in
`STUDY-SPEC.md` §2.2 and the S6 report §5 says so explicitly.

**`jt9` offline is not a reference leg** and must not be used as one.

## 4. Task 2 — re-run S5 against current `main`

**Execute the ratified rule as it stands. Do not draft a new one.** `STUDY-SPEC.md` §10, ratified
2026-07-04 (R&R-004), already gates this: **PASS iff the one-sided 95% Clopper–Pearson upper bound
on the per-slot FP event rate is ≤ 6.0%** (`THRESH_FP_UB95` in `harness/analyse.py`). The minimum-n
VOID gate is already mechanised as `_min_n_for_fp_gate` — use it, do not invent a threshold.

**Report additionally, without letting it change the verdict:** the delta against the last recorded
S5 run, and the commit hash of the build under test. The verdict is the ratified one; the delta is
context.

**If the WSJT-X leg is unavailable on the rig**, run OpenWSFZ-only and **disclose it** — the FP
gate is a single-appraiser statistic and survives, but comparability against the historical figure
does not, and that must be stated rather than assumed.

**The limit of this task, stated up front so the result is not over-read.** S5 measures FPs in
**signal-free slots**. A dense live 20m band is not signal-free, and the FPs the Captain is seeing
are most plausibly co-channel and near-threshold — a population **S5 cannot see by construction**.
A PASS here does **not** clear the live-band question. Task 4 is the partial substitute.

## 5. Task 3 — is the candidate budget actually saturated?

**Corpus:** `artefacts/20260803_live_run_1713/`, decisive epoch 1.

**Step 1 — find out whether candidate counts are already in the gathered daemon log.** Window 4's
diagnostics cite raw LDPC candidate counts, so they are emitted at some verbosity; I do not know
whether the archived log carries them. **If they are not there, say so and stop** — replaying a
cycle sample with diagnostics raised is a reasonable next step but it is a different task, and I
would rather scope it knowing the answer than have you improvise it.

**Step 2 — if the counts are present**, report `sat_0` = fraction of cycles where pass-0 candidates
`== 140`, and `sat_1` = fraction where pass-1 candidates `== 200`.

**Pre-registered rule** (strict order, first match wins):

| row | condition | consequence |
|---|---|---|
| **1 VOID** | candidate counts unavailable, or `< 500` cycles carry them | no verdict; report and stop |
| **2 SATURATED** | `sat_0 >= 0.50` | budget is rivalrous ⇒ FPs cost real decodes ⇒ the cap sweep gets priced |
| **3 PARTIAL** | `0.10 <= sat_0 < 0.50` | rivalrous in the dense regime only ⇒ report `sat_0` stratified by decodes/cycle |
| **4 REFUTED** | `sat_0 < 0.10` | the budget is not the constraint on this corpus ⇒ §1's hypothesis is dead; the FP question stands alone |

**Do not propose raising either cap in this task.** `ft8_shim.c:514-522` warns that raising
`K_MAX_CANDIDATES` past 200 silently overruns a 200-element stack array on pass 0 — that is `src/`
work under HK-011, needs a Developer session, and reaches the Captain priced, via
`dev-tasks/2026-07-26-d001-candidate-cap-sweep.md`, not from here.

## 6. Task 4 — live-band FP proxy. Observation only, no verdict

**No pre-registered rule governs this and none should.** There is no oracle for a live band. Like
§8 of the drift-screen PASS report, this **must not acquire verdict status by repetition**.

**Premise:** real stations transmit repeatedly across cycles; a false decode is typically a one-off.

**Method.** On `artefacts/20260803_live_run_1713/`, for each callsign, count the distinct cycles it
appears in. Compare the recurrence distribution of callsigns appearing **only in 8080-only decodes**
(the 37,511 set) against those in the **matched-in-both** set (24,480). Normalise hashed callsigns
first — §8 measured that at 1.55 pts and it must not be left in.

**Report the distributions and the singleton fractions. Draw no verdict.** A higher singleton rate
in the 8080-only set is *consistent with* an elevated FP rate; it is not a measurement of one, and
several innocent explanations exist (weak DX heard once, band edges, our own greater sensitivity
genuinely finding one-off signals). Say which of those you can and cannot exclude.

## 7. What this does not authorise

- **No capture run.** Check `qa/ARTEFACT_INVENTORY.md` first regardless.
- **No `src/` change**, no cap change, no gate re-tuning. If task 3 fires ROW 2, the *next* step is
  a priced proposal to the Captain — not an edit.
- **Not D-001.** The baseline deficit and density penalty are untouched.
- **Not S.1/S.1b.** Still open on my record; the Captain's pointer to the 2026-08-02 ANOVA
  directory did not contain a locality analysis (searched: `frequency-local`, `cycle-global`,
  `locality`, `subtraction`, `spectral`, `K_MAX` — zero hits).
- **Not the isolated-replay re-run**, which stays specced and queued behind this.
