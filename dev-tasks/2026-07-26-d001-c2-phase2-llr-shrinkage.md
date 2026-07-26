# Developer handoff: D-001 C.2 Phase 2 — LLR shrinkage fix, ceiling re-derivation first

**Authored by:** QA (per HK-000/HK-015).
**Status:** split into two gated steps with different owners.
  - **Phase 2a (ceiling re-derivation) is QA-doable analysis only** — reuses committed C.4
    artefacts, no rebuild, no native/managed code touched. Can start immediately.
  - **Phase 2b (the shrinkage fix itself) needs a Developer session** (HK-011) — it changes
    `ftx_normalize_logl`, which runs on every decode in production, not behind a flag.
  **Do not start 2b before 2a reports.** Same discipline C.2 itself used for its own
  Phase 1 → Phase 2 gate, and C.3 → C.4 before it.
**Source:**
  - `qa/cycleframer-alignment-replay/2026-07-26-c2-llr-normalization-findings.md` §6 — the
    original Phase 2 recommendation (shrinkage toward a per-pass median, not clamp/floor) and
    validation requirements this executes.
  - `qa/cycleframer-alignment-replay/2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md`
    §5.1 — promotes this to the **primary D-001 avenue** and specifically instructs re-deriving
    Phase 2's ceiling against the K=4 candidate set before anything else, calling it "the cheapest
    way to test it."

---

## 1. Why this is being scoped now

C.2 Phase 1 confirmed a real, score-controlled LLR-weakness signature separating messages we
missed from messages we decoded — but it was measured only against the 135-message population
that already had a candidate at the shipped `K_MIN_SCORE=10`. Phase 1's stated ceiling ("~17% of
the remaining gap, 135/793") explicitly assumed the other 648 missed messages — the ones with **no
candidate at all** — were out of reach for an LLR fix, because LLR normalisation only applies to
candidates that exist.

C.4 (the `K_MIN_SCORE` sweep) has since shown that assumption is doubtful. At `K_MIN_SCORE=4`,
618 of those 648 messages **do** gain a candidate near the right frequency/time — and the
Architect's ruling verified only +2 of them actually decode. That is not "no candidate exists,"
it is "a candidate exists and fails" — which is exactly the shape of question C.2 Phase 1 already
knows how to answer. The ruling's §5.1: *"re-deriving Phase 2's ceiling against the K=4 candidate
set is the cheapest way to test it."*

Crucially, the diagnostic data to do this **already exists**, committed, from C.4's own run: C.4
merged C.2's `--candidate-diag-csv` capture in before sweeping, so every C.4 setting's
`candidate_diag.csv` already has per-candidate `freq_hz, dt, score, decoded, prenorm_var,
postnorm_mean_abs_llr` for every pass-0 candidate, at every K value, on the same 68-cycle corpus.
No rebuild, no re-decode, no Developer session is needed for Phase 2a.

## 2. Phase 2a — ceiling re-derivation (QA-doable, this week)

**Inputs, all already committed:**
- `artefacts/20260725_live_run_1806/c4_min_score/k4_cap2000/k10_c0.10_n60/candidate_diag.csv` and
  its `ALL.TXT` — the least-confounded, highest-recovery C.4 setting (95.4% of the 648 population
  regains a candidate; still saturated at 2000, so this is a lower bound, which is fine for this
  purpose).
- C.3's 648-message population identity, already regenerated bit-for-bit against this same corpus
  in C.4 §4.3 (`c4_min_score_sweep_analysis.py`'s Step 1, reused unmodified from
  `c3_candidate_generation_gap_analysis.py`).
- C.2 Phase 1's own matched-missed-vs-matched-hit methodology
  (`2026-07-26-c2-llr-normalization-findings.md` §3–§4): frequency match within ±10 Hz / ±0.5 s,
  score-banded comparison, Mann-Whitney U on `prenorm_var` and `postnorm_mean_abs_llr`.

**Method:**
1. Write a new script (`c2_phase2_ceiling_rederivation.py`, alongside the existing C.2/C.3/C.4
   scripts) that, for each of the 648 no-candidate-at-K10 messages, looks up whether a candidate
   now exists near it in the K=4/cap2000 `candidate_diag.csv`.
2. Self-check first, before any LLR comparison: cross-tabulate `decoded` for these newly-found
   candidates against C.4's own matched-decode count (+2 at K=4/cap2000, ruling §2 table). The
   count of `decoded=1` rows in this new population should be small and consistent with that +2 —
   if it is not, the matching logic has diverged from C.4's and needs fixing before trusting
   anything downstream.
3. For the (large majority, expected ~616 of 618) `decoded=0` rows: this is the **expanded
   matched-missed population** — candidates that exist, at the right place, and still failed.
   Compare their `prenorm_var` / `postnorm_mean_abs_llr` against a matched-hit control population
   drawn from the *same* K=4/cap2000 capture (all `decoded=1` pass-0 candidates on the same
   cycles), score-banded exactly as C.2 §4 did, not just in aggregate.
4. Report medians, Mann-Whitney p-values per band, and the same "does the matched-hit population's
   minimum sit below the matched-missed population's minimum" check C.2 §4 used to rule out a
   naive floor/clamp fix — re-check that conclusion against this larger population, since a
   6x-larger sample could change it.

**Decisive interpretation (write a verdict, do not leave this ambiguous):**
- **Expanded population shows the same weak-LLR signature** (lower `prenorm_var`/
  `postnorm_mean_abs_llr` than matched-hit, surviving score-banding, same direction and rough
  magnitude as C.2's original 135-message result) ⇒ Phase 2's realistic ceiling is much larger
  than the original 135/17% bound — potentially most of the 648. Proceed to Phase 2b with this
  revised ceiling stated up front, and flag the revision to the Architect per the same convention
  C.2/C.4 used (this changes a number in the ruling's own §4 table, which per HK-015 routes back
  up, not sideways into a quiet edit).
- **No consistent signature, or a materially weaker/inconsistent one** (e.g., `prenorm_var` not
  systematically lower once banded by score, or the gap present but tiny next to C.2's original
  effect size) ⇒ Phase 2's ceiling stays bounded near the original 135. Report that finding and
  stop — do not proceed to 2b on the strength of the original 135-message result alone without
  the Architect/Captain explicitly deciding it is still worth a hot-path change for that yield.
  This is also the point where the ruling's promoted §6.3 (structural comparison) becomes the
  Architect's next call, not a QA one.

Either outcome answers the specific open question the ruling raised, at zero rebuild cost.

## 3. Phase 2b — the shrinkage fix (gated on 2a; HK-011 Developer session)

Only start this if Phase 2a supports it, or if the Architect/Captain decide the original
135-message yield is worth it regardless. Per C.2 findings §6, already established there and not
re-litigated here:

1. **Implement shrinkage, not clamp/floor.** C.2 §6 already ruled out a naive variance
   floor/clamp — the matched-hit and matched-missed populations' distributions overlap too much
   for a cutoff to separate them (matched-hit's own minimum sits *below* matched-missed's). Blend
   each candidate's own 174-sample variance estimate with a robust reference — a per-cycle or
   per-pass median raw variance across candidates — reusing `ftx_compute_candidate_llr_stats`
   (already cheap, no extra BP iterations) rather than inventing a new estimator.
2. **Sweep the shrinkage weight on a held-out corpus** — explicitly **not**
   `artefacts/20260725_live_run_1806/`, which is the corpus C.1 through C.4 and Phase 2a all
   discovered and characterised this effect on. Candidates with an existing WSJT-X-matched
   audio/`ALL.TXT` pair: `artefacts/20260723_live_run_2223/`, `artefacts/20260724_live_run_0821/`,
   `.../20260724_live_run_1607/`, `.../20260724_live_run_2227/`. Confirm whichever is picked
   actually has a filename-matched WSJT-X intersection before committing to it (same check C.1/C.2
   did before trusting their own corpus) — do not assume without looking.
3. **Confirm the gap narrows before touching decode counts.** Re-run `--candidate-diag-csv`
   capture with the new normalisation on the held-out corpus and re-verify the matched-missed vs.
   matched-hit LLR gap actually shrinks. Only once that holds, move to decode counts.
4. **Then, and only then, report before/after decode counts** on the standard 68-cycle discovery
   corpus (`20260725_live_run_1806`), same reporting shape as C.1's and C.4's tables: total
   decodes, `failCands`, `meanAbsLLR`, elapsed time against the 15 s budget.
5. **Full R&R S1–S8 gate suite rerun is still required before any shipped-constant decision.**
   This is independent of the Architect's ruling dropping the *K_MIN_SCORE* follow-up conditions
   (ruling §5.3) — that drop was specific to validating a `K_MIN_SCORE` ship decision. D-009's OSD
   gate (`OSD_CORR_THRESHOLD`, `OSD_NHARD_MAX`) is calibrated against the *current* LLR
   distribution shape; a normalisation change invalidates that calibration regardless of what
   happens with `K_MIN_SCORE`, and needs its own re-verification.
6. **No partial or opt-in shipping.** `ftx_normalize_logl` runs on every `bp_decode`/OSD attempt in
   production, for every candidate, both passes — there is no flag to hide this change behind, so
   it ships fully or not at all. Keep this branch's diagnostic-only commits (if any) clearly
   separated from the actual normalisation change, mirroring how C.1/C.2/C.4 kept their diagnostic
   capture separate from their (in the end, unshipped) constant changes.

## 4. Definition of done

**Phase 2a:**
- [ ] `c2_phase2_ceiling_rederivation.py` written, reusing C.2/C.3/C.4's existing matching and
      scoring conventions (±10 Hz / ±0.5 s, score-banding, Mann-Whitney U).
- [ ] Self-check against C.4's own +2 matched-decode count passes before any LLR comparison is
      trusted.
- [ ] Score-banded matched-missed vs. matched-hit comparison reported for the expanded (up to
      ~618-message) population, alongside a re-check of the floor/clamp-infeasibility conclusion.
- [ ] A written verdict per §2's decision rule — ceiling revised upward, or held near 135 — not
      left ambiguous.
- [ ] If the ceiling is revised, the Architect is notified per HK-015 before Phase 2b is scoped
      further or started.
- [ ] `python3 tools/pre_merge_check.py` green (HK-006) — this is analysis-only but the repo gate
      still applies to whatever is committed.
- [ ] NFR-021: aggregate statistics only in any committed script output — no callsigns, message
      text, or per-record field, same discipline as `c4_matched_decode_verification.py`.

**Phase 2b (only if reached):**
- [ ] Shrinkage estimator implemented (native), weight swept on a held-out corpus, corpus choice
      recorded explicitly.
- [ ] `candidate_diag.csv` re-capture confirms the matched-missed/matched-hit gap narrows on the
      held-out corpus, before any decode-count comparison.
- [ ] Before/after decode counts on the standard 68-cycle corpus, same reporting shape as C.1/C.4.
- [ ] Full R&R S1–S8 gate suite rerun, green or explicitly justified, before any "ready to ship"
      claim.
- [ ] `git status` clean of any rebuilt `libft8.dll` beyond what this branch is explicitly shipping,
      with its own Captain sign-off (HK-010/HK-011) — this is a production hot-path change, not a
      dormant diagnostic constant like C.1's/C.4's.
- [ ] Any deviation from this spec recorded in the findings doc, per project convention.

## 5. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-26-c2-llr-normalization-findings.md` §3, §4, §6 — Phase
  1's method and results, and the original Phase 2 scoping this refines.
- `qa/cycleframer-alignment-replay/2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md`
  §4, §5 — the revised decomposition table and the instruction to re-derive Phase 2's ceiling
  against the K=4 candidate set first.
- `qa/cycleframer-alignment-replay/2026-07-26-c4-min-score-sweep-findings.md` §4.3, §5 — the
  already-committed K=4/cap2000 `candidate_diag.csv` and 648-population recovery figures Phase 2a
  reuses directly.
- `qa/cycleframer-alignment-replay/2026-07-26-c3-candidate-generation-gap-findings.md` — the
  648-message population's original identity and statistics.
- `artefacts/20260725_live_run_1806/c4_min_score/k4_cap2000/k10_c0.10_n60/` — Phase 2a's input
  data (git-ignored per NFR-021, referenced by path only).
- `native/ft8_lib_build/patched/ft8/decode.c:380-399` (`ftx_normalize_logl`), `:752-808`
  (`ftx_compute_candidate_llr_stats`) — the code Phase 2b would change.
- Consolidation doc §6.3, promoted by the ruling's §5 — the next avenue if Phase 2a does not
  support a larger ceiling.

---

*Per HK-015, this is QA-authored dev-task material. Phase 2a's result — whichever way it comes
out — should reach the Architect before Phase 2b is scoped in detail, since it either revises the
ruling's own §4 decomposition table or confirms it as written.*
