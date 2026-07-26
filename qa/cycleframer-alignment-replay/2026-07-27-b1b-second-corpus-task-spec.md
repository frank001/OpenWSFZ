# D-001 B.1b — second-corpus jt9 ablation replication, QA task spec

**Author:** QA, 2026-07-27. **Operationalises:**
`2026-07-27-0015-architect-b3-addendum-second-corpus.md` §2, §3, §4 — corpus, arms, scoring,
and the three reading rules (R1/R2/R3), fixed in advance by the Architect and reused verbatim.
QA-runnable directly: no `src/`/native change, HK-011 does not apply. No `dev-tasks/` entry, same
posture as B.1/B.2.

---

## 1. Corpus, confirmed this session

- `artefacts/20260724_live_run_1607/` — 20 m (14.074 MHz), afternoon, 16:07–16:38, **126**
  filename-matched cycles.
- `wav/` — **126 files, all WSJT-X's own saved audio** (confirmed per the addendum's 00:30
  correction: `cycle-audio-archive` did not exist on 07-24; the run log has no save/archive
  lines). Filenames span `260724_160730.wav` .. `260724_163845.wav`.
- `ALL.TXT` — WSJT-X's own, **cumulative** (43,707 raw lines, opens 08:21). Window filtering is
  load-bearing here in a way it was not for corpus 1: restricting by ts membership in the
  126-name cycle set (the same "filename-matched" technique B.1 used, not a hardcoded time range)
  filters correctly by construction, since the wav directory only contains names inside the run
  window.
- `owsfx ALL.TXT` (filename as shipped, with the typo) — our own **live** decode for this run,
  2,466 raw lines. Used only for the addendum's "report the live figure alongside for continuity"
  instruction (§3 table) — not as the anchor (see below).
- **No our-side WAV capture exists for this run** (pre-dates `cycle-audio-archive`), so no A4
  arm — per the addendum, this is not a loss: A4's question (capture-chain parity) is already
  closed by the 07-25 parity result, and every arm here runs on the *same substrate* (WSJT-X's own
  audio) as corpus 1's A0–A2 and corpus 1's 1300 offline anchor, which is a cleaner comparison
  than corpus 1 had (corpus 1 also used WSJT-X's own audio for A0–A2 and the offline anchor, so
  this matches, not diverges).

## 2. Our-offline anchor, produced this session

Re-decoded the 126 WAVs at shipped settings via the existing `D001ParamSweep` harness (the same
tool that produced corpus 1's 1300 anchor):

```
dotnet run -c Release --no-build -- --wav-dir <wav/> --out-dir <out/> --all-txt-name ALL.TXT
  --dial-mhz 14.074 --points k10_c0.10_n60 --fresh-decoder-per-wav --progress-every 20
```

2,502 raw decode lines over 126 cycles. `hashTableRejectCount` (process-lifetime cumulative) =
1839 — plausible for a fresh-decoder-per-wav run of this length, not investigated further (no
cross-cycle hash-table leakage is possible under `--fresh-decoder-per-wav`, so this counter is
informational only, same as every prior use of this harness).

## 3. Arms and scoring — B.1's driver, reused not re-derived

`b1_jt9_ablation.py`'s `parse_all_txt`, `parse_jt9_stdout`, `normalize_hash_tokens`, `to_by_cycle`,
and `run_arm` are generic over corpus paths already (parametrised, not hardcoded to corpus 1) —
imported directly by `b1b_second_corpus_ablation.py`, not copied. Arms A0′/A1′/A2′ (`-d 3/2/1`,
`-p 15`, no `-c`/`-x`, all 126 WAVs in one process per arm, chronological order) run on
`wav/` (WSJT-X's own audio, per §1).

## 4. Reading rules — fixed in advance by the Architect (addendum §4), reused verbatim

| rule | quantity | corpus 1 | replicates if |
|---|---|---:|---|
| R1 | A2′ / our-offline ratio | 1.302 | > 1.10 |
| R2 | A0′ / live-reference ratio | 1.005 | 0.85–1.10 |
| R3 | miss coverage at d1 / d3 | 55.4% / 98.0% | d3 > 85% and d1 > 35% |

QA computes the three ratios and states plainly whether each fires; no new judgement call is
introduced at this step — the addendum's own "if any rule fails, the menu is not put to the
Captain as-is; I revise it first" means the read-out goes back to the Architect either way, not a
QA verdict on the menu itself.

## 5. What this does not authorise

Same guardrails as B.1/B.2/the plan: no native/`src/` change, no push/merge, no
`pre_merge_check.py` (HK-006), NFR-021 — raw jt9/decoder output under git-ignored
`artefacts/d001_b1b_second_corpus/`, aggregates only in the findings doc.

## 6. Cross-references

- `2026-07-27-0015-architect-b3-addendum-second-corpus.md` — the design this operationalises.
- `2026-07-26-b1-jt9-ablation-findings.md` / `b1_jt9_ablation.py` — arms, scoring, conventions
  reused verbatim.
- `artefacts/20260724_live_run_1607/` — corpus (git-ignored, real callsigns).
