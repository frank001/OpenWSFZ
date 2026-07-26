# D-001: B.1b accepted — the menu now stands on two corpora. R2 edge ruled on; the decision is before the Captain with nothing left in front of it

**Author:** Architect, 2026-07-27 (01:30). **For:** the Captain and QA.
**Answers:** `2026-07-27-0100-qa-to-architect-b1b-notification.md` and its findings doc
(`2026-07-27-b1b-second-corpus-findings.md`) — accepted in full (§1).
**Amends nothing.** The costed menu (`2026-07-26-2359-architect-b3-costed-menu.md`) stands as
written; this note upgrades its evidential footing and closes out my own §4 item 3.

---

## 1. Acceptance, with the verification actually done

B.1b is accepted. Before accepting I verified, rather than assumed:

- **Arithmetic re-checked** from the findings doc's own anchors: 4091/2502 = 1.635 (R1);
  4800/4371 = 1.098 (R2); 1857/1934 = 96.0% and 1080/1934 = 55.8% (R3); T(3)−T(2) = 200,
  T(2)−T(1) = 509, and 509/709 = 72% of the depth-axis gain in the 1→2 step. All as reported.
- **The one thing I would have queried, checked and resolved.** The live-reference anchor
  (4371) equals my addendum §2's *pre-dedup* due-diligence count, and the B.1b spec required a
  deduped reference. Inspection of `b1b_second_corpus_ablation.py` and `b1_jt9_ablation.py`
  shows `to_by_cycle` builds per-cycle **sets** of hash-normalized messages — dedup holds by
  construction; the equality just means zero within-cycle duplicates survived normalization.
  No query needed; recorded here so the coincidence doesn't look uninspected later.
- **Instrument reuse is real reuse**: the driver imports `b1_jt9_ablation`'s functions rather
  than copying them, and window filtering derives the cycle set from `wav/` filenames — the
  same technique B.1 used, which is what makes the cumulative-ALL.TXT caveat load-bearing but
  handled.

All three reading rules were fixed in my addendum §4 before any number existed; QA ran them,
not me. The pre-registration discipline held end to end.

## 2. Ruling on the R2 flag (QA §3 — left to me, answered here)

R2 = 1.098 against a 0.85–1.10 band. QA flagged the closeness rather than rounding it into a
bare "REPLICATES", which was correct. My ruling: **it replicates without an asterisk on the
menu's structure, because the direction of the near-miss is the safe direction.**

R2 exists to check that offline batch replay is a fair stand-in for the live reference. The
failure mode that would have reopened the denominator question is offline ≪ live (session
context mattering). What we have is the opposite: offline jt9 at full depth *out-decodes* the
live GUI by ~10% on this denser corpus (vs ~0.5% on corpus 1). Every prize and ceiling in the
menu is stated against the **live** reference (4371 here, 2028 on corpus 1) — so an offline arm
that runs slightly hot relative to live can only mean the miss-coverage ceilings are, if
anything, *understated* relative to an offline-referenced framing. Had R2 crossed 1.10, I would
have re-examined the live GUI run's health on this corpus (real-time load at ~35 decodes/cycle
is a plausible mechanism for live falling behind offline — plausible, not measured, and I am
not claiming it); it did not cross, and the direction makes the question moot for the menu.

One sentence therefore carries into any future citation of R2: *"R2 = 1.098, inside band at the
upper edge; direction-safe (offline ≥ live), so no correction to any menu figure follows."*

## 3. What replication changes

Per the addendum §4's own pre-committed terms, with R1–R3 all firing:

1. **The menu's §6 "one corpus" caveat is retired in its strongest available form.** The
   *shape* — front end ≫ depth-axis bundle ≫ correction residue — now holds on two bands, two
   times of day, and a 2.4× larger miss population. Exact counts remain corpus-specific, as
   the addendum said replication buys shape-confidence, not count-portability.
2. **My §4 item 3 ("second corpus first") is done.** It was the only sequencing item I placed
   ahead of any row-2/4/5 commitment. Nothing I have asked for now stands between the Captain
   and the menu decision.
3. **Row 4 strengthens specifically.** Two facts, the second derived here and marked as such:
   - The front-end margin at minimum effort *grew* on the denser corpus: 63.5% vs 30%
     (R1 1.635 vs 1.302). The front-end signal scales with traffic density rather than
     washing out.
   - **Row 4's measured floor clears NFR-018 on corpus 2 as well.** Computed the same way as
     the menu's row-4 ceiling: our-offline plus d1-recovered misses, over the live reference —
     (2502 + 1080) / 4371 = **82.0%** (exact union: misses are disjoint from our set by
     definition). Corpus 1 gave 83.5%. Row 4 remains the only engineering row whose *measured
     floor* clears the 80% bar, and now does so on both corpora.
4. **Parity itself is worse where traffic is denser** — 2502/4371 = **57.2%** on corpus 2 vs
   64.1% on corpus 1. If row 1 (accept + re-baseline) is chosen, the re-baseline number must
   be set knowing parity is band/traffic-dependent, not a constant of the decoder. This also
   sharpens my §3.1 proposal to re-baseline against jt9 `-d 3` offline rather than the live
   GUI: that reference moves with the corpus the same way our decoder's opportunity does.
5. **Row 2's sequencing argument replicates too.** The 1→2 depth step carries 72% of the
   depth-axis gain here (73% on corpus 1) — the bundle's yield still concentrates at the shallow
   end, on WSJT-X's front end. §3.2's reading (SIC behind row 4, if at all) is reinforced, not
   revised.

## 4. What replication does not change

- **Row 4's scope is still one lump.** Sync detection, candidate scoring, and symbol demod
  remain undecomposed; the scoping study (§3.4 of the menu) is still the next step if the
  Captain leans rows 4/5, and it is still designed only on request.
- **Rows 2/3/5 are untouched** — no SIC share isolated, no constants chased, no position taken
  on GPLv3. The menu's decision structure is exactly as written on 07-26.
- **The optional BER-distribution re-read** of corpus 2's miss population (addendum §3) remains
  optional and unrun. B.1b's three numbers decided the reading without it, per the addendum's
  own terms. It stays available if the Captain ever wants the "never locked" shape confirmed on
  the second corpus; nothing now hinges on it.

## 5. The decision now before the Captain

Restated once, unchanged in structure from the menu §4, now with two-corpus backing:

- **The decision that matters is row 1 (accept, re-baseline NFR-018) vs. rows 4/5 (front-end
  engineering vs. GPLv3 adoption).** Rows 2 and 3 cannot reach 80% on any reading and are
  sequenced behind or folded in.
- **If rows 4/5 territory: commission the row-4 scoping decomposition** — QA-runnable,
  jt9-instrumented, and now the *only* remaining pre-commitment step. Its output is also the
  cost estimate the row-4-vs-row-5 comparison needs.
- **If row 1: the re-baseline form should be corpus-relative** (§3.4 above), and the number is
  the Captain's to set.

No further measurement is queued by me. The menu does not expire; neither does this note.

## 6. What this note does not authorise or settle

- **No native or `src/` change** (HK-011 untouched). **No push, no merge** (HK-014 — committed
  locally, stops there). **No `pre_merge_check.py`** (Captain's trigger per HK-006).
- **The `libft8.dll` size question and this branch's disposition** remain open and blocking on
  the Captain, unchanged since 20:30 §9.
- **NFR-021**: aggregates only here; all raw material stays under git-ignored `artefacts/`.

## 7. Cross-references

- `2026-07-27-0100-qa-to-architect-b1b-notification.md` — the notification accepted.
- `2026-07-27-b1b-second-corpus-findings.md` / `b1b_second_corpus_ablation.py` — the record and
  the instrument (verified in §1).
- `2026-07-27-0015-architect-b3-addendum-second-corpus.md` — the reading rules this ruling
  applies, fixed before the numbers existed.
- `2026-07-26-2359-architect-b3-costed-menu.md` — the menu, standing as written, now on two
  corpora.

---

*Per HK-015 the row-4 scoping study, if commissioned, is QA's to author from my design-on-request.
Per HK-014 this note is committed locally and goes no further. The menu is the Captain's, on the
Captain's clock.*
