# 🛑 ARCHITECT WITHDRAWAL — Part A's statistic COUNTS RESOLVED AND UNRESOLVED HASHES IDENTICALLY. `H` WAS INCAPABLE OF MOVING. G2(a) IS NOT CLOSED — IT WORKS, AND MY PREDICTION A1 IS CORRECT.

**Author:** Architect, 2026-08-25 17:35Z (`date -u`, HK-017). Repo `main` at `4ce1bd4`.
**WITHDRAWS:** `qa/rr-study/2026-08-25-1725-architect-to-qa-g2a-remeasure-adjudication-and-140hz-baseline-ruling.md`
§0.2, §0.4, §1 (gate A row), §3 in full, and the second ledger correction banner it added.
**Does NOT withdraw:** that same ruling's §2 (`ΔB1` not attributable), §4 (HK-021(p)), §5 (the
`140 Hz` baseline ruling), §6.1 items 1/3/4. Those stand — see §5 below for exactly what survives.
**Status:** withdrawal + correction. Docs-only. No `src/`, no rebuild, no push, no merge.

---

## §1. The defect, in one line

> **`has_hash_marker()` is `re.compile(r"<[^>]*>")` — it matches ANY angle-bracket token. A
> RESOLVED hashed callsign renders as `<CALL>`. An UNRESOLVED one renders as `<...>`. Both match.
> G2(a)'s entire effect is to turn the second into the first. The statistic I gated on is
> INVARIANT UNDER THE TREATMENT BY CONSTRUCTION.**

`H` could not have moved no matter how well G2(a) worked. It measured 0.0019 pp because 0 pp is
what it was built to return.

## §2. What the data actually says (counts only, NFR-021: no message text printed or retained)

Re-derived by the Architect directly from `artefacts/2026-08-25-g2a-remeasure-a/*_decodes.json` —
the dumps QA already wrote, unmodified — splitting bracket tokens into **unresolved** (empty or
all-`.`) and **resolved** (anything else):

| leg | decodes | any bracket | **≥1 UNRESOLVED `<...>`** | only RESOLVED `<CALL>` |
|---|---:|---:|---:|---:|
| **L1 (pre-G2a)** | 71,583 | 6,910 (9.6531 %) | **6,409 (8.9532 %)** | 501 (0.6999 %) |
| **L2 run 1 (post-G2a)** | 71,600 | 6,913 (9.6550 %) | **3,566 (4.9804 %)** | 3,347 (4.6746 %) |
| **L2 run 2 (determinism)** | 71,600 | 6,913 (9.6550 %) | **3,566 (4.9804 %)** | 3,347 (4.6746 %) |

**The "any bracket" column is flat to four decimal places — that is the number the gate read.
The unresolved column falls 8.9532 % → 4.9804 %.**

```
H (as specified in English)  = 8.9532pp − 4.9804pp = 3.9728 pp  =  0.0397
H (as computed by the gate)  = 9.6531pp − 9.6550pp = −0.0019 pp = −0.000019
```

🔴 **ROW A1 fires, not A2** (`CI_lo > 0.02`: the point estimate is 2× the bar and the shift is
~44 % relative on a population of 6,409 → 3,566 over 4,627 clusters; QA owns the clustered CI, but
no plausible CI puts this below 0.02). 🔴 **My recorded prediction was A1, `H` ≈ 0.03–0.05. The
measured value is 0.0397 — inside the predicted interval.** I scored myself wrong at 17:25Z because
I scored against a broken instrument.

⚠️ The two L2 runs agree exactly on the corrected split as well, so ROW 0d's determinism finding is
unaffected and this is not a nondeterminism artefact.

## §3. Everything §3 of the 17:25Z ruling concluded is withdrawn

| I wrote at 17:25Z | correct status |
|---|---|
| "G2(a) = 0.00 pp, **CLOSED as a D-001 route**" | 🛑 **WITHDRAWN.** G2(a) resolves **2,846 more decodes** (501 → 3,347) and halves our unresolved rate. It is the most effective merged change in the programme's recent record. |
| "A rejected INSERT is not what produces an unresolved LOOKUP" | 🛑 **WITHDRAWN — exactly backwards.** The reject count fell 37.6 % **and** resolution rose 44 %. The two agree, as they always should have. My whole §3 was an elaborate mechanism invented to explain an artefact. |
| "Bucket B1 keeps its size and **loses its lever**" | 🛑 **WITHDRAWN.** The lever is real and demonstrated. |
| "actionable non-DSP total ≈3.5 pp" | 🛑 **WITHDRAWN.** Back to **≈5.0 pp**, with B1's size now needing re-derivation (§4). |
| "no further hash-table work is authorised, eviction included" | ⚠️ **STANDS, but for a different reason** — the table is still saturating (§4.2), so eviction is now *plausible* rather than *pointless*. It is still **not authorised** and still needs its own arm. |

**The failure mode is one I named in my own ruling ninety minutes ago and then walked straight
into:** I built an elaborate causal story on top of a number instead of checking that the number
could move. HK-022's drafting question — *"what error could this row NOT detect?"* — answers itself
here: **it could not detect the treatment.**

🔴 **Proposed sibling, for the Captain to adopt alongside HK-021(p) — HK-021(q):**

> **Before a gate runs, demonstrate that its predicate MOVES under the treatment.** Exhibit at
> least one concrete unit whose metric value differs between treated and untreated states, and
> paste it into the spec. A metric that cannot distinguish treated from untreated states is
> decorative regardless of its CI. **Pin the metric to the exact predicate that computes it** —
> "carries an unresolved-hash marker" (English, in my §4) and `<[^>]*>` (Python, in the harness)
> are different metrics, and nobody diffed them because the English sounded right.

⚠️ Note where this was **not** caught: not by ROW 0a–0e (all passed), not by the determinism diff,
not by two independently constructed nulls agreeing to 1.4 %, not by a cycle-clustered bootstrap,
and not by QA's own careful confound disclosure. **Statistical rigour applied to the wrong
observable produces a confident wrong answer, and every check we own is downstream of the
observable.**

## §4. What must be re-derived, and what it means for the census

### 4.1 Bucket B1 inherits the same defect

`GAP-CENSUS-A` defines bucket **B1** as *"we decoded it but our text carries an unresolved `<...>`
hash"* — and uses the **same** `has_hash_marker` predicate. So B1's population as published mixes
resolved-`<CALL>` decodes in with unresolved ones, and **B1's ~1.55 pp and the `ΔB1` ≈ 0.24 pp are
both computed on the wrong observable.** Two nulls agreeing tells you nothing when the statistic
they are nulls *for* is mis-specified.

🛑 **Bucket B1's size is now UNKNOWN, not "~1.55 pp UNRESOLVED".** It must be re-derived on the
corrected predicate, on **L2** (post-fix) as the citable basis, before any figure is quoted.
🛑 **`ΔB1` ≈ 0.24 pp remains uncitable** — now for *two* independent reasons (the 11-commit confound
from §2 of the 17:25Z ruling, which stands, *plus* this).

### 4.2 A structural fact read out of the source that changes what "capacity" means

`ft8_shim.c` (current `main`), read directly:

- `g_session_hash_table` is a **process-global**, initialised once, **never re-initialised, never
  evicted, never shrunk** (`:705-711`).
- `hash_table_add` increments `g_hash_table_reject_count` **only** when `tbl->count >=
  HASH_TABLE_SIZE` (`:694`), and re-announcements of a known callsign return early and are
  explicitly **not** rejects (`:685`).

⇒ **Once the table reaches capacity it is FROZEN for the life of the process. Every callsign first
heard after that instant is permanently unresolvable, for the rest of the session.** And L2's
reject count of **63,956 proves the 4096-slot table still saturates.** So the ladder did not end at
4096 — it moved the freeze point, and the freeze still happens.

🔴 **This is directly measurable with an already-exported function.** `ft8_get_hash_table_reject_count()`
is exported and monotonic, and the first cycle at which it becomes non-zero **is the exact moment
the table froze**. Polling it per cycle during a replay — no rebuild, no `src/` change — gives the
saturation cycle for any table size. That is the single most informative cheap measurement now
available, and it did not exist as a question until this hour.

### 4.3 `B1-COVERAGE-A` survives, sharpened, and now has an exhaustive mechanical partition

The Captain approved `B1-COVERAGE-A` at 17:25Z on my recommendation. It still runs, on the
**corrected** B1 population, and §4.2 lets me state it far more precisely than "was the callsign
ever seen". For each genuinely-unresolved decode, using the **reference's** own resolved text to
name the callsign (hashed on extraction per NFR-021), exactly one of three is true, in strict order:

| bucket | condition | what it means | is a hash-table change a lever? |
|---|---|---|---|
| **B1-cov** | our stream never emits that callsign in plaintext, anywhere in the session | we never decoded the message that would have populated the entry | **No.** Collapses into bucket C. |
| **B1-ord** | our stream emits it, but only **after** this decode | ordering — the entry did not exist yet | **No** (causally impossible in a streaming decoder; a re-render pass is a product feature, not DSP) |
| **B1-cap** | our stream emits it **before** this decode, and it is still unresolved | the entry should have been there — it was rejected at a frozen table, or a lookup defect | **YES — and only here.** This is the population an eviction policy or a larger table can serve. |

Mutually exclusive, exhaustive, strict order (HK-021). **The spec is mine to write and is not yet
written** — it needs bounded ROW 0 rows per HK-021(p), a stated `λ ≥ 5` power floor if any bucket
is claimed absent (HK-021(j)), a demonstrated-moving predicate per HK-021(q) above, and the
standing 🛑 against any frequency-separation stratification.

## §5. What survives from the 17:25Z ruling — read this before citing any of it

✅ **STANDS, unaffected:**
- **§5 in full — the `140 Hz` baseline ruling.** Build `BASE` and `WIDE` fresh, back-to-back, one
  tree, one Developer session, diff exactly the two `f_min`/`f_max` constants. **The Captain's
  authorisation of that Developer session is unaffected and should proceed.** Nothing in this
  withdrawal touches the passband, bucket A's 2.66 pp, or any gate threshold.
- **§2 — `ΔB1` is not attributable to G2(a)** (11-commit confound; and a contrast is not a share).
  Reinforced, not weakened.
- **§4 — HK-021(p)** (a disclosed-confound branch must state its bound) and *pre-register the BUILD,
  not just the SHA*.
- **§6.1 items 1, 3, 4** — Developer session first; `OSD-FA-A` unblocked and unchanged; the 08-08
  replication stays demoted (that demotion rests on QA's replay-vs-live finding, which is
  independent of this defect).
- **§2.1 — null Q's negative B2 is a mis-specification.** Independent of the predicate bug, and if
  anything a second instance of the same disease.

🛑 **WITHDRAWN:** §0 items 2 and 4; §1's gate-A row (**A1 fired and my prediction was right**);
**§3 in its entirety**; the second ledger correction banner added at 17:25Z, replaced by a third.

⚠️ **Prediction scoring, corrected and final for this arm: A = A1, PREDICTED CORRECTLY.
B = unscoreable (the observable is mis-specified; not a miss, not a hit).** I record that my
17:25Z self-score of "0 for 2" was itself wrong, in the direction that made me look worse — which
is not a defence of anything, but it is the honest record.

## §6. Immediate consequence for the queue

1. **Developer session (BASE + WIDE) — proceed as authorised.** Untouched by this.
2. 🔴 **NEW, ahead of `B1-COVERAGE-A`: re-derive `rate_unresolved` and bucket B1 on the corrected
   predicate**, from the dumps already on disk, with cycle-clustered CIs — QA's numbers, not mine.
   This is minutes of work and it is the basis every subsequent bucket-B figure is quoted against.
   Fold in per-cycle `ft8_get_hash_table_reject_count()` polling (§4.2) when convenient.
3. **`B1-COVERAGE-A`** per §4.3, once (2) fixes the population. Spec still to be written by me.
4. **`OSD-FA-A`** — unchanged.

## §7. Disclosure and compliance

- 🔴 **I computed the §2 table myself**, from QA's dumps, while checking a mechanism claim. That
  de-blinds nothing (the arm is run and reported, scoring is closed) but it is disclosed, per the
  X1/X2 and ledger precedent. **QA's re-derivation is the citable one; where it disagrees with my
  table, QA's is the result and mine is the error.**
- No message text was printed, written, or retained — counts and pattern classes only (NFR-021).
- Docs-only. No `src/`, no `native/`, no rebuild, no push, no merge (HK-011/014/010).
- The defect is in a **spec I wrote** and a **helper QA implemented in good faith from it**. The
  helper's own docstring says it is *not* hash-normalisation; my spec said *unresolved*; nobody
  diffed the English against the regex. **That diff is now HK-021(q).**
