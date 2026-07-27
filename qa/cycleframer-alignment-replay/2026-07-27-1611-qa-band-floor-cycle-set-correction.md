# D-001: the exact cycle-set-intersected band-floor figure, plus one small thing it surfaced

**Author:** QA, 2026-07-27 (16:11 UTC, `date -u`, per HK-017).
**Answers:** `2026-07-27-1603-architect-hold-r3.md` §4 point 2 — "the exact cycle-set intersection
behind the 15:55 note §2's band-floor figure... minutes, not a session."
**Not an escalation.** Small correction, reported and filed, per the note's own framing.

---

## 1. The requested number

Restricted to the same cycle sets the arms actually analyse (68 WAVs corpus 1, 126 corpus 2 — not
the full cumulative `ALL.TXT`), and expressed as a share of each corpus's **miss population**
(789 / 1934, both reproduced exactly, self-check below):

| | corpus 1 (40m, 68 cyc) | corpus 2 (20m, 126 cyc) |
|---|---:|---:|
| cycle-filtered WSJT-X decodes | 2,028 | 4,371 |
| below 200 Hz (raw) | 10 | 38 |
| above 3000 Hz | 0 | 4 |
| **below-200 as % of miss population (raw)** | 1.27% | 1.96% |
| **above-3000 as % of miss population** | 0.00% | 0.21% |

Both corpora land inside the 15:55 note's "~1–2%" bound. The ceiling stays negligible on both
(corpus 2's 4, cycle-filtered, is smaller than the 9 quoted over the unfiltered file — the
cumulative `ALL.TXT` includes cycles outside the analysed window).

## 2. One thing this surfaced: 4 of corpus 1's "below-200" rows are not actually misses

Self-check first: **every below-200/above-3000 row should be a guaranteed miss** — we don't search
outside 200–3000 Hz, so nothing there should match one of our decodes. Corpus 2 confirms this (0
unexpected hits across 38+4 rows). **Corpus 1 does not: 4 of its 10 "below-200" rows are messages
we also decoded.**

Traced, not printed (NFR-021 — aggregate deltas only, no message text):

| ts (aggregate) | WSJT-X freq | our freq | delta |
|---|---:|---:|---:|
| 4 rows | 198 Hz | 200.0 Hz | +2.0 Hz |

All four are WSJT-X-reported at **198 Hz**, one bin-width's worth of slack below our nominal
`f_min = 200`, and we decoded the identical message at **200.0 Hz** exactly — our lowest bin's
edge. The six genuine below-200 misses sit at 193–194 Hz, comfortably outside any plausible bin
tolerance. This reads as **bin-edge quantisation, not a defect**: a signal a couple of Hz below our
nominal floor still falls inside our lowest search bin's coverage and gets decoded, reported at the
bin's edge value rather than the true frequency. Corpus 2 shows no equivalent case among its
near-edge rows (closest is 197 Hz, not decoded) — plausibly SNR-dependent at the edge, not
investigated further, out of scope for "minutes, not a session."

**Corrected reading for corpus 1:** 6 of 789, not 10 — **0.76%**, not 1.27%. Corpus 2 stands as
measured, **1.96%**, no artefact found.

## 3. Self-check

`n_miss` recomputed on this cycle-filtered pass reproduces the published totals exactly: **789**
(corpus 1), **1934** (corpus 2). Trusted on that basis.

## 4. What this does and does not change

**Does not change** any ruling — the 15:55 note's "worth measuring, not worth assuming" framing
and its NFR-018/soundcard-noise/`MaxPass0Candidates` cautions all stand; this is not a
recommendation to pursue the band-floor question, just the exact number requested. **Does not**
authorise any `src/`/native change (HK-011); the floor question remains uncommissioned.

**Does change:** the precise figure to cite. Combined range across both corpora is now **0.76% –
1.96%** of the miss population (was "~1–2%" as a bound), with the corpus 1 end lower than
previously stated once the bin-edge artefact is excluded — a small point in the direction of "even
less than the bound suggested," not more.

## 5. Cross-references

- `2026-07-27-1603-architect-hold-r3.md` §4 — the request this answers.
- `2026-07-27-1555-architect-r4b-ruling-and-band-limits.md` §2.2, §9 — the bound this refines.
- `b1_jt9_ablation.py`, `b1b_second_corpus_ablation.py` — cycle-set filtering reused verbatim.
