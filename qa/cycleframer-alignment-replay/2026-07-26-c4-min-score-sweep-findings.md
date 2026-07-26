# D-001 C.4 — min-score sweep findings

**Author:** Developer session (HK-011), 2026-07-26. **For:** QA/Architect (per HK-000/HK-015 —
Dev reports up to QA, not directly to the Architect/Captain).
**Source:** `dev-tasks/2026-07-26-d001-c4-min-score-sweep.md`.
**Build under test:** branch `d001-c4-min-score-sweep`, off `main` (post-PR #115), merged with
`d001-c2-llr-normalization`'s diagnostic-capture code (neither parent branch alone had both the
stack-safety fix and `--candidate-diag-csv`; see the branch's own merge commit).

---

## 1. Summary verdict

**Positive — decisively so, once a methodology bug was found and fixed mid-experiment (§3).**
Lowering `K_MIN_SCORE` recovers a large and *rapidly rising* share of C.3's 648-message
candidate-generation-gap population — 16.2% at the shipped floor (10) up to 91–95%+ once the
`K_MAX_CANDIDATES=600` pairing itself stopped being a confound (§4.2) — while the false-positive
ratio (unique-to-us decodes per recovered message) stays roughly bounded (0.34–0.61), not runaway.
`K_MIN_SCORE` is a real, large constraint on this corpus, not a dead end like C.1's candidate-cap
question. **Per §5's decision rule this is the first branch: escalate to a deliberate, validated
follow-up (§9) — do not ship a new constant from this branch itself.**

## 2. Prerequisite (dev-task §2) and required setup deviation

`main` @ merge time already carried PR #115's stack-safety fix (`K_MAX_CANDIDATES_ANY_PASS`) —
confirmed a no-op re-check, not a re-implementation, per that section's own instruction. However
`main` did **not** carry C.2's `--candidate-diag-csv` capture (still unmerged, sitting only on
`d001-c2-llr-normalization`), and that branch did not carry PR #115's fix — **neither parent had
both features this dev-task needs simultaneously.** Resolved by branching C.4 off `main` and
merging `d001-c2-llr-normalization` into it; both feature sets are additive and merged cleanly in
`ft8_shim.c` (the harness's `Program.cs` needed manual conflict resolution to keep both
`--debug-log` and `--candidate-diag-csv` side by side — mechanical, not a design conflict).

## 3. A real methodology bug found and fixed before any C.4 number can be trusted

C.2's diagnostic-capture managed wrapper (`Ft8LibInterop.cs`) hardcoded
`private const int MaxPass0Candidates = 140`, passed as the `capacity` argument to
`ft8_get_last_candidate_diag`. This mirrors the *native* `K_MAX_CANDIDATES` only for as long as
that constant stays 140 — exactly the same class of latent landmine C.1's own
`K_MAX_CANDIDATES_ANY_PASS` fix addressed on the native side, but on the managed side of this
opt-in diagnostic path, and C.1 did not touch it (C.2's diagnostic capture postdates C.1's fix).
Raising native `K_MAX_CANDIDATES` to 600 for this sweep (per §3 of the dev-task) did nothing for
`candidate_diag.csv`: the native buffer itself grew correctly, but `GetLastCandidateDiagnostics()`
still asked for only the first 140 entries back, silently truncating every setting's diagnostic
CSV to the *first* 140 candidates the native loop happened to capture — independent of how many
actually cleared the floor. First-pass numbers computed before this was caught showed the 648
population's recovery **flat at 34–36 across all four settings** — the wrong-direction "null"
answer §5 predicts for "the floor is not the constraint." That was an artifact of the bug, not a
finding: `candidate_diag.csv` row counts were suspiciously identical (9520 = 140×68) across every
K_MIN_SCORE setting, which is what caught it.

Fixed by raising `MaxPass0Candidates` to 600 to match (`Ft8LibInterop.cs`), with the same
"dormant, zero-cost-until-the-constant-moves-again" framing C.1 used for its own fix — this
diagnostic path is opt-in and never called by the daemon. **All four settings were rebuilt and
re-decoded after this fix; every number below is post-fix.**

## 4. Method

### 4.1 Corpus — deliberate deviation from C.1/C.2 (per dev-task §3 itself)

Decoded `artefacts/20260725_live_run_1806/wsjt-x/wav68/` — **WSJT-X's own captured audio**,
filename-matched down to the same 68-cycle intersection C.1/C.2 used (`wsjt-x/wav/` contains 75
files; 7 outside the matched intersection were excluded to build `wav68/`, mirroring the existing
`owsfz/wav68/` convention) — cross-decoded through our decoder. This is the dev-task's own
explicit choice (§3 step 3), not an oversight: it keeps the capture-chain difference (already
measured at ~0.5% of the D-001 gap) out of this experiment, unlike C.1/C.2's `owsfz/wav` corpus.
One consequence: **baseline totals are not directly comparable to C.1/C.2's reported figures**
(different audio source) — there is no external reference to "reproduce" here; K_MIN_SCORE=10 at
`K_MAX_CANDIDATES=600` is this experiment's own internal baseline, matching the table shape C.1
used ("140 (baseline)").

### 4.2 The 600-candidate ceiling is *not* generous once the floor drops — a second confound

C.1 verified `K_MAX_CANDIDATES=600` was crash-free and "generously sized" relative to the real
candidate population (220–295 per cycle) — but only at the shipped `K_MIN_SCORE=10`. On this
corpus, per-cycle pass-0 candidate counts at `K_MAX_CANDIDATES=600`:

| setting | median cand/cycle | max seen | cycles at ceiling |
|---|---:|---:|---:|
| K=10 | 220 | 295 | 1/68 |
| K=8 | 538 | 600 | 12/68 |
| K=6 | 600 | 600 | **68/68 — fully saturated** |
| K=4 | 600 | 600 | **68/68 — fully saturated** |

K=6 and K=4 hit the 600-slot ceiling on *every single cycle* — the exact confound dev-task §3 was
designed to prevent ("cannot tell apart 'no real signals down there' from 'real signals crowded
out of the top N'"), just one ceiling higher than C.1 needed to worry about. **Deviation from the
literal spec, recorded here per project convention:** reran K=8, K=6, K=4 a second time at
`K_MAX_CANDIDATES=2000` (K=10 not rerun — never approached 600, so 600 was already non-binding for
it) to check whether the required table's K=6/K=4 rows understate recovery. K=8 barely moved
(600-cap and 2000-cap results agree within noise — confirms K=8's required-table row was already
clean). K=6 moved enormously (91.0% vs 54.9% recovered). K=4 moved enormously and **still
saturated at 2000** (68/68 cycles at the ceiling) — the true ceiling-free recovery number at K=4
remains unknown, only bounded below by 95.4%.

### 4.3 648-recovery matching

Reused `c3_candidate_generation_gap_analysis.py`'s own Step 1 logic unmodified, re-run against the
frozen C.2 Phase 1 (`owsfz`-audio, K_MIN_SCORE=10/K_MAX_CANDIDATES=140) artefacts to regenerate the
exact 648-message population — reproduced **1235 shared-hit / 135 matched-failed / 10
near-decoded / 648 no-candidate-anywhere**, bit-for-bit matching C.3's own reported figures (this
population's *identity* — which WSJT-X messages — is corpus-independent; only whether a new
candidate now exists nearby, checked against each C.4 setting's own `candidate_diag.csv`, changes).
Same tolerances throughout (±10 Hz, ±0.5 s, per C.2/C.3). New script:
`qa/cycleframer-alignment-replay/c4_min_score_sweep_analysis.py`.

## 5. Results

**Required table** (`K_MAX_CANDIDATES=600` throughout, per dev-task §3/§8):

| K_MIN_SCORE | total decodes | recov648 | recov% | unique-to-us | uniq/recov ratio | failCands (med/mean) | meanAbsLLR (med/mean) | ms/cycle (med/p90) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 (baseline) | 1300 | 105 | 16.2% | 61 | 0.58 | 166.5 / 167.3 | 4.081 / 4.079 | 987 / 1115 |
| 8 | 1358 | 327 | 50.5% | 117 | 0.36 | 482.0 / 476.7 | 4.117 / 4.118 | 1899 / 2107 |
| 6 | 1365 | 356 | 54.9% | 124 | 0.35 | 537.5 / 538.3 | 4.117 / 4.118 | 2023 / 2201 |
| 4 | 1368 | 376 | 58.0% | 126 | 0.34 | 538.0 / 538.5 | 4.120 / 4.121 | 2099 / 2216 |

**Supplementary, non-ceiling-confounded check** (`K_MAX_CANDIDATES=2000`, §4.2 — K=10 omitted,
never binding at 600):

| K_MIN_SCORE | total decodes | recov648 | recov% | unique-to-us | uniq/recov ratio | ms/cycle (med/p90) | ceiling status |
|---|---:|---:|---:|---:|---:|---:|---|
| 8 | 1357 | 331 | 51.1% | 116 | 0.35 | 1972 / 2187 | clean (1/68 at max) |
| 6 | 1573 | 590 | **91.0%** | 332 | 0.56 | 5717 / 6094 | clean (5/68 at max) |
| 4 | 1617 | 618 | **95.4%** | 376 | 0.61 | 4694 / 6295 | **still saturated (68/68)** |

`hashTableRejectCount` (process-lifetime cumulative, context only): 690 (K=10) → 1251 → 1330 → 1368
(K=8/6/4 @ 600), 1247/2861/3123 at the 2000-cap reruns — rises with candidate volume as expected,
no crash or hang at any setting (68/68 decoded every run).

## 6. Interpretation (dev-task §5)

**First branch, unambiguously.** Recovery rises sharply and monotonically with a lower floor —
16.2% → 50–51% → 55–91% → 58–95%+ — while the false-positive ratio stays in a bounded 0.34–0.61
band rather than climbing in lock step with recovery (it briefly *falls* at K=8 relative to
baseline, then partially recovers toward baseline levels at the lower K values, never exceeding
roughly the baseline's own 0.58). This is qualitatively different from C.1's `K_MAX_CANDIDATES`
result (a real but small, quickly-plateauing +12/+1.6%-of-gap effect) and from what a "not the
constraint" verdict would look like (§5's flat-recovery / lock-step-noise pattern this experiment
does *not* show). `K_MIN_SCORE` is a materially larger lever than `K_MAX_CANDIDATES` on this
corpus's candidate-generation gap.

**Caveat the verdict does not erase:** the required table's K=6/K=4 rows are *understated* (§4.2)
— the true picture is closer to the supplementary table (91–95%+), not the 55–58% the literal
600-cap spec produced. Both tables point the same direction; only the magnitude differs.

## 7. Timing budget (dev-task §6)

**Required-table settings stay comfortably inside the 15 s production budget** at every K value
(worst case 2216 ms p90 at K=4/600 — 14.8% of budget). The supplementary 2000-cap settings cost
much more (up to 6295 ms p90 at K=4/2000, 42% of budget) but were never intended as ship
candidates — they exist only to unconfound the required table's interpretation, per §4.2. Timing
rises roughly with pass-0 candidate volume in both tables, as C.1's own §6 anticipated for a lower
floor at a fixed higher ceiling.

## 8. False-positive spot-check (dev-task §4 step 6, not optional)

Unique-to-us decode counts do rise in absolute terms at every setting (61 → 117 → 124 → 126 at
600-cap; 116 → 332 → 376 at the clean 2000-cap points) — lowering the floor does admit some noise,
exactly as §6 of the dev-task warned it would. But the **ratio** to recovered-648-count (the actual
false-positive-risk signal, per that section's own framing) does not climb in step with recovery:
it *falls* from baseline (0.58) to 0.34–0.36 through K=8/6/4 at 600-cap, and only rises back to
roughly baseline levels (0.56–0.61) at the least-confounded 2000-cap points. **This is not the
signature of a setting whose recovery is "just as likely to be noise as signal"** (§5's own
phrasing for the negative branch) — recovery is growing faster than false positives are, not the
reverse. This corpus's baseline unique-to-us (61, wsjt-x-audio) is not directly comparable to
C.1/C.3's reported ~49 (`owsfz`-audio, different corpus per §4.1) — not evidence of a regression,
an expected consequence of the deliberate corpus change.

## 9. What this experiment does not resolve (dev-task §7)

`score` remains a sync-correlation metric, not SNR directly (C.3 §4's own hedge, restated here
unchanged) — this experiment measures candidate-generation and false-positive-ratio behaviour
directly; it does not independently re-confirm the SNR-sensitivity mechanism C.3 proposed.
Additionally, and specific to this experiment: **the true ceiling-free recovery ceiling at
K_MIN_SCORE=4 is still unknown** — even `K_MAX_CANDIDATES=2000` fully saturates every cycle at that
floor. Whoever scopes a follow-up should not treat 95.4% as an upper bound.

## 10. Recommendation

**Do not ship any `K_MIN_SCORE`/`K_MAX_CANDIDATES` change from this branch.** Per dev-task §9, this
result contradicts the consolidation doc's decomposition table more than C.1's did (C.1 was
confirmatory of "small effect, don't ship"; this is a large, real effect) — **escalating to the
Architect, not quietly revising the table, per that section's own rule.** A permanent constant
change needs, at minimum: (a) resolving the still-open true-ceiling question at K=4 (§9's open
question above) with a properly validated, crash-tested higher `K_MAX_CANDIDATES` (its own
C.1-style safety pass, not assumed from this branch's 2000-cap spot check), (b) re-calibrating
D-009's OSD gate against the new, much larger candidate population reaching LDPC/OSD (dev-task §6's
own caveat — untouched in this branch), and (c) a full R&R S1–S8 rerun before any ship decision,
exactly as the dev-task's §9 specifies and C.2's own Phase 2 scoping required for a change of this
weight. K=8 is the cheapest, least-confounded, most immediately actionable data point if that
follow-up is scoped (recovery already at 50%+ with a bounded, even improved, false-positive ratio,
and comfortably inside the timing budget at its own already-verified 600-cap setting).

## 11. Definition of done

- [x] §2's prerequisite confirmed (PR #115's stack-safety fix present on `main` at merge time).
- [x] Four rebuilds (`K_MIN_SCORE` ∈ {10, 8, 6, 4}, `K_MAX_CANDIDATES = 600` throughout), each
      re-decoding the full 68-cycle `wsjt-x/wav68/` corpus with `--candidate-diag-csv` enabled.
- [x] Report table: setting → count of the 648 gaining any candidate → total decodes →
      unique-to-us decode count → `failCands`/`meanAbsLLR` (median/mean) → decode elapsed time
      (median/p90 ms/cycle). See §5.
- [x] A written verdict per §5's criteria — not left ambiguous. See §1, §6.
- [x] Deviations recorded: corpus choice (§4.1, per the dev-task's own instruction, not a
      deviation from it), the `MaxPass0Candidates` truncation bug and fix (§3), and the
      600-candidate-ceiling saturation confound requiring supplementary 2000-cap reruns (§4.2).
- [x] `python3 tools/pre_merge_check.py` run before any "ready" claim (§12).
- [ ] `git status` clean of any rebuilt `libft8.dll` beyond the shipped 10/140 state — restored
      before this branch is considered for merge (§12); the `MaxPass0Candidates=600` managed-side
      fix (§3) is kept permanently (dormant, zero-cost at the shipped native constant, same class
      of fix as C.1's own `K_MAX_CANDIDATES_ANY_PASS`) — flagged explicitly for Captain sign-off
      since it is a `src/` change surviving this branch even though the sweep's own headline
      constants do not.

## 12. Cross-references

- `dev-tasks/2026-07-26-d001-c4-min-score-sweep.md` — the task spec this executes.
- `qa/cycleframer-alignment-replay/2026-07-26-c3-candidate-generation-gap-findings.md` — C.3; the
  648-message population this sweep tests recovery against.
- `qa/cycleframer-alignment-replay/2026-07-26-c2-llr-normalization-findings.md` — C.2; source of
  the `--candidate-diag-csv` capture this branch merged in, and of the `owsfz`-audio 648 origin.
- `qa/cycleframer-alignment-replay/2026-07-26-c1-candidate-cap-sweep-findings.md` — C.1; the
  stack-safety-fix prerequisite and the `K_MAX_CANDIDATES=600` ceiling this experiment discovered
  is *not* generous once the floor also moves (§4.2) — a refinement of, not a contradiction of,
  C.1's own "600 is generously sized" finding (true at K_MIN_SCORE=10, false below K=8).
- `qa/cycleframer-alignment-replay/c4_min_score_sweep_analysis.py` — this analysis.
- `native/ft8_lib_build/patched/ft8/decode.c:264-306` (`ftx_find_candidates`) — the score-gate
  mechanism under test.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:466-472` (`K_MIN_SCORE`, `K_MAX_CANDIDATES`) — the constants
  swept, restored to 10/140 on this branch's final committed state.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` (`MaxPass0Candidates`) — the managed-side fix (§3),
  kept at 600 permanently.
