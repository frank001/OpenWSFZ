# ARCHITECT → QA — GH #3 / #111: the D-001 state of play, and Route B2 authorised

**2026-08-19 18:40Z · Architect · follows `G3` (18:01Z, ROW 1, N=20/20 PASS) and the Product
Owner's authorisation of Route B2 in the same session**

**Status: DRAFT TEXT, NOT POSTED.** The Captain assigned #3/#111 to QA; HK-015 says I write *for*
QA, and HK-014 keeps me off anything that publishes. Both bodies below are final text — post
verbatim or tell me what to change.

Standing bar, unchanged from the 12:58Z round: **counts, rates and document paths only**
(NFR-021, the repo is PUBLIC). No callsigns, no message text.

---

## 0. Three framing decisions I made, stated so they can be overruled rather than discovered

🔴 **(1) I have kept every Architect CREDENCE out of the public text.** My report to the Captain
was built partly on the 08-18 ledger's route probabilities (root cause correctly identified ~65%;
ship a ≥half-gap fix ~55% pre-`AO1`; Route B2 45%). The ledger's own §11 bars those figures from
pre-registrations, and the 12:58Z round extended that bar to public comments. The Captain asked
for "this" as a report, and the credences were part of "this" — so this is a real subtraction from
what he asked for, not an oversight. **The public comments carry only measured figures and the
decision.** If the Captain wants the credences published, that is a one-line instruction and I
will redraft; I did not want to publish my own 6/11-calibrated priors into a public issue without
him choosing it explicitly.

🔴 **(2) I have kept the STAKES statement out of the public text.** The Captain's framing — that
without D-001 this project is "a nice exercise in coding/testing/statistics, but nothing more" —
is recorded in `memory/BOARD.md` and in §4 below. It is a product-owner judgement about the
project's viability, on a PUBLIC repo, and publishing it is a disclosure decision that is his and
not mine. **Not published unless he says so.**

⚠️ **(3) Neither comment closes either issue.** #3 gets a state-of-play and a route decision, not
a changed gap. #111 gets a sharpened purpose — and Route B2 makes its open axis MORE load-bearing,
not less, which is an argument against closing it rather than for.

---

## 1. Comment for #3 — post as-is

## Status update — 2026-08-19: the gap is unchanged, the diagnosis has converged, and a route is authorised

Follows the 2026-08-19 12:58Z update. This one is a state-of-play rather than a result: **no
figure in this issue changes.** What changes is what happens next.

### The gap, restated

| corpus | recovery vs WSJT-X | source |
|---|---|---|
| 20m (primary) | **57.8%** | H1a-corrected; supersedes the earlier `[55.5%, 57.8%]` bracket |
| 17m | **64.1%** | `X1`, density × SNR standardised |
| 80m | **77.1%** | `X0`-repaired (the pre-repair 76.84% is void) |
| any band, SNR ≥ 0 dB | **83.2%** | replicates an independent 2026-08-06 estimate to 0.2 pp |

Roughly 460 messages read where the reference reads roughly 750 — a **~42 pp gap on 20m**.

⚠️ **Every figure means "against WSJT-X at `NDepth = 3`"**, its deepest setting, while OpenWSFZ
runs two decode passes, candidate caps 140/200 and a 200–3000 Hz window. Part of the gap is depth
and budget asymmetry rather than capability. `RC4` and `C.1` bound that part small (+0.70 pp and
+0.93% respectively). They do not bound it at zero.

### Three findings localise it, and they have been stable since 2026-08-11

1. **`RC1`'s decomposition of 894 pooled misses:** **3.1%** out-of-band, **8.9%** no-candidate,
   **87.9% candidate-present-and-failed.** In nine misses out of ten the signal was spotted and
   not read. Please cite the decomposition; "40% unexplained" is not a figure this project holds.

2. **The bimodality (`W1` / `B.2` §5).** Matched-hit control BER median **2.9%**; our BP+OSD
   corrects to `B50` = **11.3%** BER; the missed population's own BER median **44.0%** (p10
   17.2%). That is bimodal, not a gradient — the misses sit at roughly 4× the correction
   threshold. The complement, `E = 4.28` of 135, says **~97% of the missed population was never
   correctable by any error-correction change.** ⚠️ Caveat carried in full: a July corpus, n = 126
   measured, and candidate mismatch inflates BER toward 50% — that cuts *toward* this reading but
   is not the same as having measured it cleanly.

3. **The architectural divergence.** For each surviving candidate WSJT-X returns to the original
   audio and builds a second, private, per-candidate front end: complex-baseband downconversion
   with phase retained, fine frequency (±5 × 0.5 Hz), fine time (±4 × 5 ms), coherent Costas
   correlation, and 1-/2-/3-symbol **coherent** bit metrics. Achieved resolution **≈0.5 Hz / 5 ms**
   against our **3.125 Hz / 0.08 s** — **≈6× coarser in frequency, ≈16× coarser in time.**
   **OpenWSFZ has no equivalent of this stage at all.**

### What has closed since the last update, and which way it moved

Four pre-registered arms have reported. **All four subtracted a candidate explanation rather than
recovering decodes:**

- **`AO1` — CLOSED.** The production time-origin offset is real and measured: `R` = **+0.700 s**
  on the live path, `K` = **+0.650 s** by physical-position sweep. Its recall cost, measured at
  matched SNR, is `L` = **+0.706 pp**, CI95 **[+0.492, +0.926] pp**. Real, well-powered — and
  ~2 pp against a ~42 pp gap. **It does not explain D-001.**
- **`D1` — ROW 1, locus SHARED.** `K_ref` = `K_ours` = **+0.650 s**, bit-identical, 0 grid steps
  apart. A `CycleFramer` product-fix recommendation was **withdrawn in full** on this result.
- **`D2` — NO ROW.** The convention-versus-physical-offset slope was voided on validity grounds:
  the regressor had two populated values, making it a two-point contrast rather than a regression.
- **`N1` / `N5` / P-LIVE Stage 2.** Limb 1 is dead as a D-001 treatment — the failure is in how
  the bits are formed, not where they are read. Limb 2 is held on a thin 67-cluster bound. Stage 2
  fired ROW 3 (harm) at scale.

### An instrument defect, found and fixed in the same session

`synth/modulator.py` clamped positive `dt_s` at both ends. The FT8 signal occupies 12.64 s of a
15 s slot, so the maximum representable offset is 2.36 s — but the S3 sweep runs to 2.7 s.
**Parts 8 (label 2.4 s) and 9 (label 2.7 s) both rendered at 2.3600 s: two different truth labels
producing bit-identical audio, since 2026-06-06.** Every S3 Bias & Linearity and DT GR&R number
since that date is computed against wrong truth for 20% of its parts.

Fixed, and the fix is validated end-to-end: gate `G3` ran `jt9` over all 20 rendered files, twice,
mechanically diffed at two levels (0/20 differ), **N = 20/20 PASS** across the full grid including
all ten negative-offset parts. The earlier "negative DT cannot be measured" claim was a synthesis
artefact and is retired.

🔴 **This is instrument repair, not gap closure.** It is a prerequisite for sizing any future
change honestly; it does not recover one message.

### The decision

**Route B2 is authorised by the Product Owner as of 2026-08-19: build a per-candidate
complex-baseband front end.** Retain the cycle PCM; mix and decimate per candidate to complex
baseband; correlate coherently against the Costas arrays over a fine (Δf, Δt) grid; form coherent
multi-symbol LLRs from that baseband.

**Also authorised, and in this order: finish the S3b instrument first.** Route B2 is the largest
piece of engineering this project has attempted, and it cannot be sized against a bench that
mislabels its own truth.

Three shortcuts are already closed and will not be re-derived: `WATERFALL_USE_PHASE` is a dead
switch rather than a disabled feature; `ft8_decode_multi_symbols()` is dead code that sums dB
magnitudes where the reference sums complex values, so wiring it up does not buy the coherent
gain; and framing offset alone cannot be a ~42 pp effect.

Licence position unchanged and binding: **WSJT-X may be read for method; not one line is copied,
transliterated or ported.** This project is AGPL-3.0 and takes in only permissively licensed
third-party code.

### Still open, unchanged by this update

Whether the depth and budget asymmetry above contributes more than `RC4` and `C.1` bound it to;
the post-fix false-positive surge; and #111's device axis, which Route B2 makes more load-bearing
rather than less — see the cross-reference there.

---

## 2. Comment for #111 — post as-is

## Cross-reference 2026-08-19: the authorised route makes this issue's open axis load-bearing

Follows the 2026-08-19 12:58Z cross-reference, which widened this issue's band and session axes
and left the **device** axis explicitly untouched. That position is unchanged: the four corpora
behind the offset replication ran through a single capture device, mechanically confirmed —
identical endpoint GUID and friendly name in all four daemon logs — so they widen band and
session while holding device constant by construction.

**What is new is the consequence.** Route B2 — a per-candidate complex-baseband front end — is now
authorised (see #3). Its whole premise is that phase is retained from the captured audio and used
coherently, at a target resolution of ≈0.5 Hz / 5 ms against the current 3.125 Hz / 0.08 s.

That raises the stakes on this issue in a specific way:

- A **magnitude-only, single-symbol** extractor is largely indifferent to capture-path phase and
  timing behaviour below its own lattice. That is measured rather than assumed: `N1` found
  position insensitivity, and the current lattice is ~16× coarser in time than the reference's.
- A **coherent** front end is not indifferent to it. Capture-device drift is already known to be
  device-dependent in this project (48.0 ppm on one path, 4.7 ppm on another — **no zero-drift
  control exists in any corpus**), and this issue's unreplicated axis is exactly the one that
  varies there.

⇒ **Attribution that was tolerable to leave open while the decoder was magnitude-only becomes a
sizing input once the decoder goes coherent.** Whatever gain Route B2 delivers will be measured on
one device unless this axis is replicated, and a device-dependent term would be confounded with
the treatment.

**This issue stays OPEN and is not superseded by the offset replication** — that measured a
time-origin offset, not this issue's capture-versus-decoder decomposition, and a wider corpus for
a different quantity does not satisfy an acceptance criterion written for this one.

⚠️ Resolution limit, stated so it is not paraphrased away: the offset's invariance across band and
session is invariant **to within the sweep's own 0.05 s grid step**. A device-dependent difference
smaller than that is invisible to that instrument, and nothing finer may be inferred from it.

---

## 3. Notes for QA — not for posting

**Nothing here needs a run.** Every figure in both drafts is restated from a committed report,
ruling or the board. No `src/`, no rebuild, no capture, no Developer session. HK-011 not engaged.

⚠️ **Two assertions to verify before posting, rather than take on my word (HK-022):**

1. **The #3 recovery table.** Four figures from four different arms with four different
   corrections applied (H1a, `X1` standardisation, `X0` repair, and the 08-06 replication). I have
   restated them from the 08-18 ledger §1, which is itself a synthesis. **Check each against its
   originating report before posting** — the ledger's own §11 says to cite the originating report
   and not the ledger, and I have just done the thing §11 warns about.
2. **`G3`'s N = 20/20 and the two-level diff.** Read those off the 18:01Z report, not off my
   summary of it.

⚠️ **A number I deliberately did NOT put in the #3 draft, flagged so nobody helpfully adds it
back.** The 08-18 ledger's aggregate ("we ship something closing ≥ half the 20m gap", ~55%) is now
**stale in a known direction**: it carried 20% on the anchor-offset route, and `AO1` closed that
route at a measured ~2 pp ceiling. My own `AO1` §10 had already ceilinged it at ~2 pp six days
earlier — the two were incompatible when written and I did not notice until this session. **The
aggregate is lower than 55% and I have not restated it with a number.** If anyone asks for one
publicly, the answer is that it needs re-derivation, not a guess.

🛑 **Do not let either comment be paraphrased into "Route B2 will close D-001."** It is the
best-motivated untested thing on the board and the only remaining route with a mechanism behind
it. That is not the same as a prediction that it works.

---

## 4. Recorded for the board — the Product Owner's authorisation, and its stated stakes

Verbatim, because it is a product-owner ruling and my paraphrase should not replace it:

> Route B2 is authorized by me, including finishing the S3b instrument.

> when D-001 won't be closed this project is dead, a nice exercise in
> coding/testing/statistics, but nothing more.

🔴 **What this changes in how I work the programme, written down so it can be held against me:**
the cheap-arm reflex stops. Every arm since 2026-08-15 has subtracted a candidate explanation
without recovering a decode, and several of the recent defects found were in my own specs rather
than in QA's execution or the code under test. Route B2 gets a phased spec with an early kill-gate
that can be evaluated before the expensive half is built, and anything that is not Route B2 or the
S3b instrument now needs an explicit argument for why it is not a side-track.

⚠️ **NOT published.** §0(2) explains why; the Captain can reverse that in one line.

---

## 5. Housekeeping

- HK-017: filename `2026-08-19-1840-…` and the byline `2026-08-19 18:40Z` both derive from a real
  `date -u` in this session and agree.
- HK-014: committed locally only. **Not pushed, not merged, and I have not asked.**
- HK-015: written for QA. The posting is QA's, the two verifications in §3 are QA's, and the
  decisions in §0(1)–(2) are the Captain's to overrule.
- HK-024: `memory/BOARD.md` and `memory/MEMORY.md` updated in the same edit as this document, not
  afterwards.
- NFR-021: counts, rates, statistics and document paths only. No callsigns, no message text.
  Verified by read-through of both draft bodies before writing this line.
