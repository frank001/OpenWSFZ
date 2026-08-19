# ARCHITECT → QA — GH #3 / #111 cross-reference, drafted for posting

**2026-08-19 12:58Z · Architect · follows `D1` (12:40Z, ROW 1, locus SHARED)**

**Status: DRAFT TEXT, NOT POSTED.** The Captain assigned #3/#111 to QA; HK-015 says I write
*for* QA, not around them, and HK-014 keeps me off anything that publishes. Both bodies below
are final text — post verbatim or tell me what to change. If the Captain would rather I post
them myself, that is a one-line instruction and I will.

Both are written to the standing bar: **counts, rates, and document paths only** (NFR-021), and
**no probability from the D-001 investigation ledger** (its §11 citation limit).

🔴 **The one framing decision I made, so it can be overruled rather than discovered:** neither
comment closes anything. #3 gains a *closed candidate explanation*, not a changed gap. #111 gains
a *sharpened axis*, not a resolution. I considered and rejected recommending #111 be closed —
see §3.

---

## 1. Comment for #3 — post as-is

## Status update — 2026-08-19: the anchor-convention offset is measured, closed as a D-001 route, and its locus is shared

Follows the 2026-08-18 update. Two pre-registered arms have run since. **Neither changes any
recovery figure in this issue** — one closes a candidate explanation, the other locates it.

### `AO1` — the offset measured on its own terms, then closed

The ~+0.65 s time-convention mismatch flagged in the 2026-08-18 update was pre-registered as its
own arm rather than inherited as a known quantity.

**Part B (ROW 3 — production framing defect, confirmed in part).** Two independent statistics on
the primary 20 m corpus: a live-path offset `R = +0.700 s` (25,411 rows) and an offset located
directly inside our own archived audio by a 49-point sweep, `K = +0.650 s` (median BER 6.32 % at
the argmin, chance level 43–50 % across the rest of the grid, zero extraction failures in 26,999
calls). The two agree to within one reference reporting tick. `K` is the discriminator: the
signal does not merely carry a wrong *label*, it physically sits ~0.65 s later inside the buffer
than the reference's grid says.

**Replicated on three further corpora — three days, three bands.**

| corpus | matched (rows / clusters) | `R` | `K` |
|---|---|---|---|
| `20260808_live_run_0016-8080` (20 m) | 43,662 / 2,733 | +0.700 s | **+0.650 s** |
| `20260808_live_run_1154-8080-17m` | 25,437 / 1,856 | +0.700 s | **+0.650 s** |
| `20260809_live_run_0155-8080-80m` | 8,598 / 1,179 | +0.700 s | **+0.650 s** |

Every corpus, every leg, lands on the identical offset to the sweep's own grid resolution. It is
not a single-corpus artefact.

**Part C (ROW C2) — how much recall it actually costs.** `L = +0.706 pp`, CI95
`[+0.492, +0.926] pp`, on SNR/`dt`-standardised strata with a cluster bootstrap.

🔴 **Consequence, pre-registered before the number was known: fix it on product grounds, not as a
D-001 route.** A ~0.7 pp recall cost does not move a ~42 pp gap. An audit of the statistic's own
blind spot (`L` is a contrast and cancels any cost borne equally by all `dt` strata) found the
concern does not bite: an FT8 transmission occupies 12.64 s of the 15 s slot, so a constant
offset *translates* the acceptance window without narrowing it, and the cost lands in the tails —
which is exactly what `L` is built to see. The ~1.0 % of the population above `dt ≈ +1.5 s`
independently predicts an effect of the right size.

**`AO1` is closed.**

### `D1` — which file carries the offset

`AO1` established the offset exists in our audio. It could not say whether we *introduce* it,
because it never swept the reference's own audio. That mattered, because the two answers demand
opposite fixes, and because a third measured fact contradicted the simple reading: our WAV and
the reference's WAV, same filename, are the same audio to a median cross-correlation lag of
15.5 ms over 4,956 pairs. If the two files are the same audio to ~16 ms, the same sweep anchored
the same way is *forced* to return the same argmin on either.

`D1` re-ran the `AO1` sweep verbatim with one thing changed — the audio directory repointed to
the reference's own WAVs. Same anchor, same 49-point grid, same seeded sample, same corpus.

| quantity | value |
|---|---|
| `K_ref` (reference's own audio) | **+0.650 s**, median BER 6.32 % |
| `K_ours` (`AO1`'s published figure) | **+0.650 s** |
| difference | **0 grid steps — bit-identical argmin** |

Cycle-set overlap between the two loads was 519 / 519 (full). All five preconditions cleared.

🔴 **The offset is shared by both files, not introduced by our framing relative to the
reference.** A code fix in our cycle-framing window placement would have moved a window that
already sits where the reference's does. **That recommendation — made earlier the same day, by
me — is withdrawn in full. No source change and no spec change was written.**

### What is still open

**The mechanism inside that shared path is not named.** `D1` was built to discriminate *shared*
from *ours*, and it was not built to name what *shared* is. The two surviving candidates — a
common-mode capture-chain latency, and the `dt` convention itself — are not yet separated, and
they have different consequences. A follow-up arm is being designed; it is not yet specified and
nothing above should be read as prejudging it.

### Unchanged

No recovery figure in this issue moves. Both limbs stand as at 2026-08-18: limb 1 (per-candidate
complex-baseband refinement) dead on a measured −4.02 pp harm, replicated at scale; limb 2
(order-3 coherent extraction) held on a thin bound. The standing closures — error-correction
changes, PCM input scaling, candidate-budget increases, subtract-and-resynthesise, spectral
locality — are all still closed, and nothing here reopens any of them.

Full detail: `qa/rr-study/2026-08-19-1058-architect-to-qa-prereg-ao1-production-time-origin-offset.md`,
`qa/rr-study/2026-08-19-1135-qa-to-architect-ao1-results.md`,
`qa/rr-study/2026-08-19-1211-qa-to-architect-ao1-part-c-c2-fires.md`,
`qa/rr-study/2026-08-19-1217-architect-ruling-ao1-part-c-accepted-and-ledger-correction.md`,
`qa/rr-study/2026-08-19-1226-architect-to-qa-spec-d1-offset-locus-discriminator-and-fix-shape.md`,
`qa/rr-study/2026-08-19-1240-qa-to-architect-d1-row1-fires-shared-locus.md`.

---
*Counts, rates, and document paths only per this repo's NFR-021 policy — no callsigns or message text in this comment.*

---

## 2. Comment for #111 — post as-is

## Cross-reference 2026-08-19: two of this issue's three axes are now covered; the device axis is not, and it has become the discriminating one

This issue records that the "~98.5 % decoder-side" attribution rested on **one device, one band,
one 21-minute session**. Recent work moves two of those three axes, and — more usefully — makes
the third one *load-bearing for a live open question* rather than merely unreplicated.

### Band and session are now much better covered

The `AO1` arm (full detail in the 2026-08-19 update at #3) measured a production time-origin
offset across **four corpora, three days, three bands (20 m / 17 m / 80 m)**, ranging from 8,598
to 43,662 matched rows. So this issue's "one band, one 21-minute session" caveat no longer
describes the corpus position for time-origin work: the band and session-length axes have been
exercised, and the measured quantity was **invariant across all of them** — identical to the
sweep's own grid resolution, every corpus, every leg.

This does **not** amount to re-running the 2×2 capture-vs-decoder decomposition this issue asks
for. It is a different measurement on a wider corpus. The acceptance criteria stated here are
untouched and this issue is **not** closed by it.

### The device axis is untouched — and now matters more than it did

All four corpora ran through the same capture chain. The paired second instances were excluded
from the analysis as non-independent (Jaccard ≈ 1.000 with their twins), so they add nothing on
this axis. **Device remains a single point.**

That is now sharper than a general validity caveat, because of what `D1` found. The offset is
present, bit-identically, in **both** our archived audio and the reference application's own
archived audio from the same capture chain — so it is not a differential defect of our capture
path relative to theirs, which is the quantity this issue's "capture share" metric measures.
Two candidate mechanisms survive, and **they split precisely on the device axis:**

- a **common-mode capture-chain latency** — one chain, both applications, so both are displaced
  equally. This predicts the offset **changes with the capture device**.
- the **`dt` convention** itself — a protocol/interpretation quantity. This predicts the offset
  is **identical on every device**.

Invariance across band and day is consistent with both, and therefore separates neither. **A
second capture device does separate them**, in one measurement. Two are known to be materially
different in this project's own records — the two chains differ by roughly an order of magnitude
in clock-rate error, and the routing in use changed on 2026-08-15, after all four corpora above
were captured.

### Consequence for this issue

No change to its severity, its acceptance criteria, or its status — it stays **open**, and the
2×2 decomposition it asks for is still the thing that closes it. What changes is the priority
argument: the device axis is no longer only a generalisability check on a closed decision, it is
now the discriminating axis for an *open* mechanism question. The follow-up arm being designed
for that question should carry a device axis, and if it does, it produces most of what this issue
asks for as a by-product — consistent with this issue's own advice to fold the work into a run
happening for other reasons.

---
*Counts, rates, and document paths only per this repo's NFR-021 policy — no callsigns or message text in this comment.*

---

## 3. Notes for QA, not for posting

**Why #111 is not recommended for closure.** It would be easy to read `AO1`'s four-corpus
replication as discharging #111 and close it. That would be wrong twice over. First, `AO1`
measured a *time-origin offset*, not the *2×2 capture-vs-decoder decomposition* that #111's
acceptance criteria name — different statistic, and a wider corpus for a different quantity does
not satisfy a criterion written for this one. Second, the axis #111 cares about most (device) is
the exact axis all four corpora hold constant. The comment is written to widen two axes honestly
and to refuse the third explicitly.

**Why I did not claim `D1` reopens the capture avenue.** It does not. #111's capture share is a
*differential* — our capture path versus the reference's. `D1` measured that differential as
zero to the grid's resolution. A common-mode latency, if that is the mechanism, is invisible to
that metric by construction and would not raise the capture share as #111 defines it. Whether it
should be counted against "capture" at all is a definitional question, and I have not smuggled
an answer to it into a public comment.

⚠️ **HK-026, checked while drafting.** The offset's invariance across band and day is measured by
the sweep, and the sweep's grid step is 0.05 s. "Invariant" here means *invariant to within one
grid step*, and nothing finer may be inferred from it — a device-dependent difference smaller
than 0.05 s would be invisible to this instrument. The #111 comment says "identical to the
sweep's own grid resolution" for this reason; do not let it be paraphrased into "identical".

⚠️ **One factual assertion in the #111 draft that QA should verify before posting, rather than
take on my word (HK-022):** that all four `AO1` corpora ran through the same OpenWSFZ capture
device. I believe it from the capture dates (all pre-dating the 2026-08-15 routing change) but I
have **not** confirmed it against `qa/ARTEFACT_INVENTORY.md` or the per-run configs. If it turns
out two devices are already represented, the #111 comment's central argument changes shape and
should come back to me before posting.

⚠️ **A pin worth recording somewhere durable:** `D1` ran against DLL `6890d84c4bcf2e90…`,
shim **20260042**. The memory's reserved-range note stops at 20260041. Not a defect, but the
allocation record is now behind the reality, and the standing rule is to pin the SHA rather than
trust the integer.
