# `FP-FLOOR-LIVE-2` Part B — acceptance ruling: **ROW 2 ACCEPTED**, and the bound label corrected

**Architect, 2026-09-10 14:43Z** (`date -u`, HK-017). Branch `arch/fp-floor-operator-setting`.
Docs-only; `git diff --stat -- src/ native/` empty.

Accepts: QA's `qa/rr-study/2026-09-10-1436-qa-to-architect-fp-floor-live-2-part-b-results.md`
against the gate in `2026-09-10-1426-…-part-b-authorised.md` (`32375fb`).

---

## 1. Verdict

**ROW 2 fires, and I accept it.** `K_removed = 313/601 = 52.08%`, CP95 `[48.00%, 56.14%]`. The
lower bound of 48.00% is well above the `≥ 5%` bar. ROW 0 is clear on all five checks (0a–0e), as
QA reported. Checked independently:

- The CP95 interval recomputes to `[48.0009%, 56.1383%]`. It matches.
- The `K(s)` bins from −38 to −24 sum to `k = 313` and `n = 601`. Both match.
- Over the span's own elapsed `21.754 h`, the rate is `313 / 21.754 = 14.39` corroborated removed
  decodes per operating hour.

**Consequence, per §2.5 and unchanged:** no operator control is drafted. The threshold is not
re-opened. "A higher threshold would be fine" is barred. No `src/` work is authorised, and no
baseline is created. `FP-PARITY` ROW 3 (`F−T = 5.378 dB`) stays fired. D-003 is still untested. The
`19:36:45Z` boundary is frozen permanently (Amendment 3).

My recorded prediction was ROW 1 at ~55% credence, with `K_removed` expected in 0.5–4%. The
prediction was wrong, by more than an order of magnitude.

## 2. Correction: the "UPPER BOUND on `T`'s own loss" label was wrong (my error)

Since FP-FLOOR-LIVE Amendment 1 (`3afc362`), every spec in this arm has said that every loss figure
is an **upper bound** on `T`'s own loss. That statement is false, and the specs also wrote that §4's
bounds both point "against the filter", which gets the direction backwards. `k/n` carries two biases,
and they pull in **opposite** directions:

| bias | mechanism | direction on the quantity we care about |
|---|---|---|
| Predicate superset | The rounded cut removes `excess ≤ 3.0`, while `T` removes `< 2.622`. The extra 0.378 dB slice sits at the high-SNR end, where `K(s)` is higher. | `K_arm ≥ K_T`, so this is an **upper** bound on `T`'s *corroborated* rate |
| Corroboration undercount | `REF` misses genuine decodes too. | `k` is a **lower** bound on genuine loss |

Combined, **`52.08%` is neither bound on `T`'s genuine-loss rate.** Also, the two §4 bounds of the
1710 spec (the corroborated count as a lower bound on genuine loss, the uncorroborated count as an
upper bound on junk) both err **in the filter's favour**, not against it. For that reason ROW 2 is
the conservative outcome for this instrument, and ROW 1 was not (see §3).

**Why the verdict still holds for `T` itself.** The entire superset slice (true SNR in
`[−23.878, −23.5)`) is reported as −24. It therefore lies inside the −24 bin (`n = 180`, `k = 124`).
Take the worst admissible allocation: every removed decode is corroborated.

| allocation of the −24 bin to the superset slice | `k_T / n_T` | CP95 |
|---|---|---|
| none (the arm as measured) | 313/601 = 52.08% | [48.00%, 56.14%] |
| entire bin | 189/421 = 44.89% | [40.07%, 49.78%] |
| **worst case**: 124 removed, all corroborated | **189/477 = 39.62%** | **[35.20%, 44.17%]** |

The worst case is about 7× the `5%` bar. To move ROW 2 for `T`, chance same-cycle `±3 Hz` wildcard
collisions would have to supply more than 30 pp of the corroboration. That is an order of magnitude
above QA's §9 plausibility estimate (~4%) and three times H1a's `V_null ≤ 0.10` bound on a
comparable population. **The ROW 2 verdict is robust to both biases.**

**How to cite it:** `K_removed = 313/601 = 52.08%` (CP95 `[48.00%, 56.14%]`), measured on the
rounded (−24 dB) cut. Under the worst-case allocation, `T`'s corroborated removal rate is
`≥ 39.6%` (CP95 lower bound 35.2%). Both are corroboration rates, which bound genuine loss from
below. Never cite it as "an upper bound on `T`'s loss", and never as "`T`'s genuine-loss rate".
The per-hour figure has the same caveat: `14.39`/h on the arm's cut, and `≥ 189/21.754 = 8.69`/h
under the worst-case allocation to `T`.

The original passages have been struck where they live (HK-022):

- `2026-09-08-1710-…-spec-fp-floor-live-corroboration.md`: §1.1 (the paragraph beginning
  "The direction is safe") and §4's opening (two paragraphs)
- `2026-09-08-1754-…-capture-post-fix-corpus.md`: the Amendment 1 bullet
- `2026-09-10-1426-…-part-b-authorised.md`: the comment inside the §2.4 code block

## 3. For whoever designs the next operator-control arm: ROW 1 was not identifiable

The heading of the 1710 spec's ROW 1 is "the provable genuine cost is negligible", and it fires on
`hi ≤ 0.02` of the **corroborated** rate. Corroboration bounds genuine loss from **below**, so a
small `hi` could never have proven that genuine cost is small (HK-021: the metric must be
identifiable from its data). Had ROW 1 fired, its consequence (drafting an operator-control
pre-registration) would have rested on a premise the metric cannot establish.

The flaw did not reach the verdict, because ROW 2 fired and ROW 2 reads the bias in its
conservative direction. **Any future arm that wants to prove the loss is *small* needs a reference
whose miss rate is itself bounded**, for example synthetic truth or a REF recall measured at the
relevant SNR. A second decoder's corroboration alone cannot do it. This is recorded, not acted on:
no such arm is proposed.

## 4. Artefacts

QA's result file and harness (`qa/cycleframer-alignment-replay/fp_floor_live_2_part_b.py`) are
untracked in the QA worktree. QA commits them locally on its own branch, after striking the
upper-bound paragraph on its result file's lines 16–20. Pushing is the Captain's go-ahead, per
HK-033. NFR-021: this ruling contains only aggregate counts and rates.
