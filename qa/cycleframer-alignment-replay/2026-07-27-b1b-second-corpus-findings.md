# D-001 B.1b — second-corpus jt9 ablation: findings

**Author:** QA, 2026-07-27. **Executes:** `2026-07-27-0015-architect-b3-addendum-second-corpus.md`
§2–§4, per `2026-07-27-b1b-second-corpus-task-spec.md`. QA-run directly, no `src/`/native change.

---

## 0. Verdict

**All three reading rules fire/replicate, on a different band, a different time of day, and
roughly double the cycle count.** The front-end/sync signal is not a one-corpus artefact.

| rule | quantity | corpus 1 (40m, evening, 68 cyc) | corpus 2 (20m, afternoon, 126 cyc) | outcome |
|---|---|---:|---:|---|
| R1 | A2′/our-offline ratio | 1.302 | **1.635** | **FIRES** (threshold >1.10) — front-end margin, if anything, *larger* on the second corpus |
| R2 | A0′/live-reference ratio | 1.005 | 1.098 | **REPLICATES** (band 0.85–1.10; close to the upper edge but inside it) |
| R3 | miss coverage d1/d3 | 55.4% / 98.0% | 55.8% / **96.0%** | **REPLICATES** (thresholds d3>85%, d1>35%) |

Per the addendum's own §4: *"if R1–R3 all fire, the costed menu stands on two corpora spanning
two bands and two times of day, and the memo's §6 'one corpus' caveat is retired in its strongest
form."* That condition is met.

## 1. Method

Reused `b1_jt9_ablation.py`'s functions directly (`parse_all_txt`, `parse_jt9_stdout`,
`normalize_hash_tokens`, `to_by_cycle`, `run_arm`) against the second corpus
(`artefacts/20260724_live_run_1607/`), per the addendum's own instruction that nothing new is
invented. Two pieces this session added:

1. **Our-offline anchor**, produced via the existing `D001ParamSweep` harness (the same tool
   behind corpus 1's 1300 anchor): 126 WAVs, shipped settings (k10/c0.10/n60), dial 14.074,
   `--fresh-decoder-per-wav` → **2502** raw decodes.
2. **`b1b_second_corpus_ablation.py`**, a thin driver over the reused functions pointing at the
   new corpus's paths and computing the three fixed reading rules.

Window filtering: WSJT-X's `ALL.TXT` for this corpus is **cumulative** (43,707 raw lines, opens
08:21 — the run window is 16:07–16:38). Restricting by ts membership in the 126-name cycle set
(derived from `wav/`'s own filenames, the same technique B.1 used on corpus 1, not a hardcoded
time range) filters correctly by construction.

## 2. Anchors

| anchor | value |
|---|---:|
| live WSJT-X GUI (window-filtered, cumulative-file) | **4371** |
| our decoder, offline, on WSJT-X's own 126 WAVs (same substrate as corpus 1's anchor) | **2502** |
| our decoder, live (different substrate — real-time stream; continuity only, not the anchor) | 1830 |
| the miss population (WSJT-X-live minus our-offline, per cycle) | **1934** |

Note the addendum's own framing: there is no our-side WAV capture for this run
(`cycle-audio-archive` post-dates it), so every arm here — A0′–A2′ *and* the offline anchor — runs
on the identical substrate (WSJT-X's own audio), which is a *cleaner* apples-to-apples comparison
than corpus 1 had reason to worry about (corpus 1's own A0–A2/anchor were already on this
substrate too; the two corpora therefore match on this axis, not diverge).

## 3. Arms

| arm | depth | total | miss coverage (of 1934) | overlap w/ our-2502 |
|---|---:|---:|---:|---:|
| A0′ | 3 | 4800 | 1857 (96.0%) | 2436 (97.4%) |
| A1′ | 2 | 4600 | 1669 (86.3%) | 2433 (97.2%) |
| A2′ | 1 | **4091** | 1080 (55.8%) | 2421 (96.8%) |

Price list: **T(3)−T(2) = 200, T(2)−T(1) = 509.** Same qualitative shape as corpus 1 (the 1→2
step dominates: 509/709 = 72% of the depth-axis gain, vs corpus 1's 73%) — the *shape* of where
the depth-axis yield concentrates also replicates, not just the three headline ratios.

## 4. Reading

**R1 (front-end margin) fires more strongly here than on corpus 1** — 1.635 vs 1.302. At *minimum*
jt9 effort, WSJT-X's decoder out-decodes our full-effort offline decoder by **63.5%** on this
corpus's identical audio (vs 30% on corpus 1). This corpus is denser (126 cycles vs 68, more
traffic per the addendum's own due-diligence note in §2 of that memo), and the front-end gap
scales with it rather than shrinking — consistent with a front-end/sync limitation rather than
some corpus-1-specific artefact.

**R2 sits close to its upper edge (1.098 vs a 0.85–1.10 band) but is inside it.** Offline batch
replay at full effort again needs no material upward correction for live session/GUI context —
the same reading as corpus 1 (A0/A0′ both ≥ their respective live anchors), now on a corpus with
double the traffic and a different band.

**R3 replicates cleanly.** d3 coverage (96.0%) and d1 coverage (55.8%) both clear their
thresholds with room; the "ceiling ≈ the whole gap, and more than half of it needs no decode
effort at all" reading from corpus 1 holds on corpus 2.

## 5. What this changes for the B.3 menu

Per the addendum's own terms, this replication was the precondition the menu's item-3
recommendation ("gather the second corpus first... before the commitment") was pointing at.
With R1–R3 all firing:

- The menu's row 4 (front-end/sync) measured prize is no longer a single-corpus number — it holds,
  and strengthens, on a second band/time-of-day.
- The "one corpus" caveat (menu §6, and every prior note in this thread) is retired in its
  strongest available form for the *shape* of the finding (front end ≫ correction residue);
  the *exact counts* remain corpus-specific, as the addendum itself was careful to say replication
  buys shape-confidence, not count-portability.
- Nothing about row 2 (SIC), row 3 (constants), or row 5 (GPLv3 adoption) is touched by this
  session — the addendum was explicit that replication does not decompose row 4's scope or isolate
  SIC's share, and this findings doc adds nothing on those fronts.

**This is a QA measurement, not a menu recommendation.** Per HK-015, the read-out on what this
means for the Captain's decision is the Architect's, same as B.1/B.2.

## 6. Honest caveats

- **R2 replicates but sits near its own boundary (1.098 vs a 1.10 ceiling).** A slightly different
  window-filtering choice or a slightly noisier live-GUI run on this corpus could have pushed it
  outside the band; reported as measured, not rounded generously.
- **Absolute counts differ substantially from corpus 1** (miss population 1934 vs 789, roughly
  2.4x) — expected given ~double the cycles and a denser band, not itself evidence of anything;
  the reading rules were built as *ratios* precisely so absolute-count differences would not be
  mistaken for a finding.
- **Still two corpora, one device, one operator, one season.** The addendum retired the
  "one device" caveat as an actionable item (there is only one radio at this station); it remains
  true as a statement of fact, same as before.
- **`hashTableRejectCount` = 1839** on the offline anchor pass is informational only —
  `--fresh-decoder-per-wav` means no cross-cycle hash-table state persists, so this counter cannot
  reflect cross-cycle leakage; not investigated further, consistent with every prior use of this
  harness.

## 7. Cross-references

- `2026-07-27-0015-architect-b3-addendum-second-corpus.md` — design, corpus provenance
  correction, reading rules.
- `2026-07-26-b1-jt9-ablation-findings.md` / `b1_jt9_ablation.py` — instrument and conventions
  reused verbatim.
- `2026-07-26-2359-architect-b3-costed-menu.md` — the menu this replication de-risks.
- `b1b_second_corpus_ablation.py` — driver; raw jt9/decoder output under git-ignored
  `artefacts/d001_b1b_second_corpus/` (NFR-021).
- `artefacts/20260724_live_run_1607/` — corpus (git-ignored, real callsigns).
