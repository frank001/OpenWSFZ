# D-001: QA -> Architect notification — B.1b replicates; R1/R2/R3 all fire on the second corpus

**Author:** QA, 2026-07-27 (01:00). **For:** the Architect, per HK-015.
**Answers:** `2026-07-27-0015-architect-b3-addendum-second-corpus.md` — run in full this session.
**This is a notification, not an escalation.** All three of your fixed-in-advance reading rules
fire/replicate; nothing here contradicts a prior ruling.

---

## 1. Result

| rule | corpus 1 | corpus 2 | outcome |
|---|---:|---:|---|
| R1 (A2′/our-offline) | 1.302 | **1.635** | FIRES (>1.10) — larger margin, not smaller |
| R2 (A0′/live-ref) | 1.005 | 1.098 | REPLICATES (band 0.85–1.10; near the upper edge) |
| R3 (miss coverage d1/d3) | 55.4%/98.0% | 55.8%/96.0% | REPLICATES (>35%/>85%) |

Full method, anchors, and per-arm tables: `2026-07-27-b1b-second-corpus-findings.md`.

The 20 m/afternoon corpus (126 cycles, denser traffic, ~2.4x the miss population) shows the same
shape as the 40 m/evening corpus (68 cycles) — if anything the front-end margin is *stronger*
here (63.5% vs 30%). The depth-axis price-list shape also replicates: the 1→2 step carries 72% of
the depth-axis gain on corpus 2, vs 73% on corpus 1.

## 2. What was produced this session

- Our-offline anchor for the second corpus (2502, via the existing `D001ParamSweep` harness,
  shipped settings, `--fresh-decoder-per-wav`, dial 14.074) — this did not exist before this
  session and was needed as the R1/R3 denominator.
- `b1b_second_corpus_ablation.py` — thin driver reusing `b1_jt9_ablation.py`'s functions directly
  against the new corpus's paths; nothing re-derived, per your addendum's own instruction.
- `2026-07-27-b1b-second-corpus-task-spec.md` / `-findings.md`.

## 3. One thing flagged, not resolved

R2 (1.098) sits close to the band's own upper edge (1.10). It replicates as measured, but I am
flagging the margin rather than only reporting "REPLICATES" — your call whether that closeness
needs any comment in how this feeds the menu.

## 4. What this does not settle

- **No verdict on the menu.** Per your own addendum, replication buys shape-confidence for row 4
  and retires the "one corpus" caveat in its strongest form for the *shape* of the finding; it does
  not decompose row 4's scope, isolate SIC's share, or touch the GPLv3 question. QA has not framed
  a recommendation.
- **No native or `src/` change**; **no push, no merge** (HK-014); **no `pre_merge_check.py`**
  (Captain's trigger, HK-006, not run).
- **The `libft8.dll` size question and branch disposition remain open**, untouched by this
  session, same as every prior note in this thread.
- **NFR-021**: raw jt9/decoder output stays under git-ignored `artefacts/d001_b1b_second_corpus/`
  (verified via `git check-ignore -v`); only aggregates appear in the findings doc or here.

## 5. Cross-references

- `2026-07-27-0015-architect-b3-addendum-second-corpus.md` — the addendum this executes.
- `2026-07-27-b1b-second-corpus-task-spec.md` / `-findings.md` — full detail.
- `2026-07-26-2359-architect-b3-costed-menu.md` — the menu this de-risks.

---

*Per HK-015, what this means for the Captain's decision is yours to frame, not QA's. Per HK-014,
nothing here is pushed or merged.*
