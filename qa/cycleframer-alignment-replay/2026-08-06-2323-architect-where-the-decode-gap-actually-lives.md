# Architect: where the decode gap actually lives — stratification of what we miss

**Author:** Architect, 2026-08-06 (23:23 UTC, `date -u`, per HK-017). Repo `main` at `f7717e3`.
**For:** QA, and the Captain for the two decisions in §7.
**Status:** Findings from data already on disk. **No new runs, no playback, no `src/` change,
nothing authorised or proposed for authorisation without the Captain's sign-off.**
**Inputs:** the five preserved replay runs (`artefacts/20260806_cross_decode_replay_2009/`,
M0), `_work/run{1..5}/our_ALL.TXT`, and `src/OpenWSFZ.Ft8/Native/ft8_shim.c`.

---

## 0. Why this exists

The D-009 recalibration swept 45 parameter points and returned **+0.109 pp** of recall on a
41.508% baseline. That is a clear negative result: **the deficit is not parametric.** This note
asks the question the sweep could not — *what are we actually failing on* — using the five-run
replay corpus, which is the first valid instrument this project has had for the question.

Everything here is reference-free in the sense that matters: both legs decoded the same audio,
fresh, in the same sessions. Nothing depends on the archived corpus `ALL.TXT` whose validity is
open (`2026-08-06-2249-…-m3-void-preflight-desync.md`).

---

## 1. The measurement

Pass 1 of each of the 5 runs, busy window (`260804_085845 … 260804_090330`), matched on
`(cycle, normalize_hash_tokens(message))`, tonight's timestamps mapped back to corpus cycles.

| run | WSJT-X | ours | matched | missed | miss rate |
|---|---:|---:|---:|---:|---:|
| 1 | 752 | 461 | 447 | 305 | 0.406 |
| 2 | 754 | 457 | 448 | 306 | 0.406 |
| 3 | 758 | 461 | 452 | 306 | 0.404 |
| 4 | 759 | 465 | 456 | 303 | 0.399 |
| 5 | 756 | 463 | 450 | 306 | 0.405 |

**Miss rate 0.399–0.406 across five independent live sessions.** Pooled: 3,779 WSJT-X decodes,
we miss 1,526 (40.4%).

---

## 2. SNR is the dominant axis, and it is monotone

WSJT-X's own reported SNR used throughout, as the common scale (ours reads 2.0–2.6 dB low —
the tracked S7 gain error).

| WSJT-X SNR | total | missed | **miss rate** |
|---|---:|---:|---:|
| < −20 dB | 144 | 114 | **0.792** |
| −20 … −15 | 496 | 340 | **0.685** |
| −15 … −12 | 491 | 277 | **0.564** |
| −12 … −10 | 373 | 159 | **0.426** |
| −10 … −7 | 439 | 167 | **0.380** |
| −7 … −4 | 445 | 162 | **0.364** |
| −4 … 0 | 407 | 144 | **0.354** |
| ≥ 0 dB | 984 | 163 | **0.166** |

Monotone across all eight buckets, spanning **4.8×**. Missed decodes: median −12.0 dB, mean
−10.54. Matched: median −5.0, mean −3.73 — a **6.8 dB** separation in means.

**Decodes below −12 dB are 29.9% of all traffic but 47.9% of everything we miss.**

This independently corroborates D-009's own framing: its recall arm is restricted to *low-SNR*
decodes and returned 41.5%, against 60% here across all SNRs. Two different instruments, same
conclusion — **our deficit is a weak-signal deficit.**

---

## 3. The density penalty is real, and it is not an SNR artifact

Miss rate by per-cycle density (WSJT-X decodes in that cycle), **within** fixed SNR bands:

| SNR band | dens 30–34 | dens 35–39 | dens 40–49 |
|---|---:|---:|---:|
| very weak (< −15) | 0.626 | 0.716 | **0.754** |
| weak (−15…−10) | 0.454 | 0.469 | **0.595** |
| mid (−10…−3) | 0.290 | 0.349 | **0.475** |
| strong (≥ −3) | 0.150 | 0.206 | **0.214** |

**Monotone increasing in all four bands.** For mid-SNR signals the miss rate rises 64% relative
across a 1.4× density range.

The obvious confound runs the *wrong* way and therefore strengthens this. Denser cycles carry
**stronger** signals on average (median WSJT-X SNR −7.0 dB at density 40+, against −9.5 dB at
density < 35). Density hurts us despite the signals being easier.

**This is the D-001 density penalty, reproduced reference-free on a valid instrument, for free.**
It does not depend on the archived `ALL.TXT`, so it survives whatever M3 eventually says. It is
also the part of D-001 the 07-27 design never addressed.

⚠️ **Citation limit:** one window, density range 30–49 decodes/cycle. This establishes the
penalty exists and is SNR-independent within that range. It does **not** establish its shape, and
it does not extrapolate to the 7/cycle regime M3 was designed to probe.

---

## 4. A defect that is certain, bounded, and explained

Our candidate search is hardcoded to 200–3000 Hz (`ft8_shim.c:1183`, `monitor_config_t cfg`).

| band | n | missed | miss rate |
|---|---:|---:|---:|
| < 200 Hz | 47 | 47 | **1.000** |
| 200–3000 Hz | 3,729 | 1,476 | 0.396 |
| ≥ 3000 Hz | 3 | 3 | **1.000** |

50 decodes, 100% missed, fully explained: they lie outside the band we look in. WSJT-X finds
them; we cannot see them.

That is **3.3% of all our misses** — small, but it is the only finding tonight with a *certain*
mechanism and a *bounded* cost. Everything else in this note is a direction; this is a fact.

Frequency is otherwise not a strong axis (0.288–0.487 across the remaining bands), and what
structure there is likely rides on SNR.

---

## 5. The size of the prize

If our miss rate at all SNRs matched **our own** rate on strong (≥ 0 dB) signals — 0.166, i.e.
no new capability, just consistency — we would miss 626 instead of 1,526.

> **631 decodes/run against WSJT-X's 756 — 83% of WSJT-X, up from 60%.**

That is the weak-signal gap, priced. Against it, D-009's best grid point was **+0.109 pp**.

---

## 6. What the decoder actually does

From `ft8_shim.c` (read-only; nothing here modifies `src/`):

| | ours | WSJT-X at `NDepth=3` (Deep) |
|---|---|---|
| passes | **`K_MAX_PASSES = 2`** | multi-pass, deeper |
| between passes | PCM-domain SIC — synthesise CP-FSK from pass-0 decodes, subtract from a PCM residual, rebuild the waterfall | iterative subtraction |
| candidate cap | **140** (pass 0), **200** (pass 1) | not equivalently capped |
| LDPC iterations | 50 both passes | |
| OSD fallback | yes (`fix-d001-osd`, shim 20260025) | yes, depth-dependent |
| search band | **hardcoded 200–3000 Hz** | wider in practice (§4) |

### 6.1 The three-pass experiment does not close the question it appears to close

`ft8_shim.c:48-56` records `K_MAX_PASSES` raised 2→3 and reverted: S7 R&R **50.54% vs 54.84%,
−4.30 pp**, "H2 rejected: no improvement on any co-channel part."

Three reasons that verdict does not settle whether depth would help *here*:

1. **It tested a co-channel hypothesis.** H2 was about exact co-channel separation, scored on
   synthetic co-channel parts (P0/P1/P2/P8). Tonight's dominant axis is **weak signals**, which
   is a different mechanism — successive subtraction lowers the effective noise floor for weak
   signals whether or not it separates co-channel ones.
2. **It was measured on the synthetic arm.** Per standing record the QA synth is an
   encoder-only test oracle, not a decoder replacement. Real weak-signal recall against a live
   WSJT-X reference was never in scope — there was no valid instrument for it until this week.
3. **It predates `be5960a`** (`results/2026-06-12-3ecf8ae`, June) and therefore the entire
   post-drift-fix framing and this corpus.

**I am not claiming three passes would help.** I am claiming the experiment on record was
pointed at a different question, on a different instrument, before the current framing — and
that we can now answer the real question in about five minutes of playback.

### 6.2 The sweep excluded the parameter family the density evidence points at

D-009 swept `kMinScorePass2`, `osdCorrThreshold`, `osdNhardMax`. It explicitly listed
`K_MAX_CANDIDATES_PASS2` as out of scope.

But §3 says our failure scales with density at fixed SNR — and a **hard candidate cap is exactly
what produces that signature**. `K_MAX_CANDIDATES = 140` in pass 0 is a ceiling; when a dense
cycle generates more candidates than that, the surplus is never attempted, and the ones dropped
are disproportionately the weak ones. That predicts precisely the interaction in §3: density
hurts, independently of SNR, worst in the weakest bands.

The 08-04 board's candidate-saturation pointer (`sat_0 = 0.4576`, recorded as a pointer and not
a verdict) sits directly underneath this.

**This is checkable without any decode run.** `ft8_get_last_candidate_counts()` is already
exported from the shim (`FT8_SHIM_VERSION 20260018`) and returns per-pass candidate counts
before any LDPC attempt. Whether it is reachable from the managed layer I have not verified —
worth establishing before anything is proposed, since the 08-04 note recorded S.2a as blocked
for want of instrumentation that may in fact partly exist.

---

## 7. Recommendations

Priority order. **None of these is authorised; §7.1 and §7.2 touch `src/` and therefore need a
Developer session plus the Captain's sign-off per HK-011.**

**7.1 — Widen the search band.** §4 is a certain defect with a known mechanism and a measured
cost. Smallest, safest change on the board. Needs a decision on the new limits and a check that
widening does not import low-frequency noise as false positives — which the existing S5/S7 arms
can answer.

**7.2 — Re-test decode depth against the live instrument.** Build `K_MAX_PASSES = 3`, replay the
busy window, compare miss-rate-by-SNR against tonight's 2-pass baseline. ~5 min of playback per
configuration against an instrument with 0.9% run-to-run repeatability. This is the single
highest-value experiment available and it exists only because of this week's harness work.

**7.3 — Establish whether the pass-0 candidate cap binds.** Free if the exported getter is
reachable; a small managed-layer change if not. §6.2's prediction is sharp and falsifiable: if
saturation correlates with the §3 density effect, the cap is a live constraint and belongs in
the next sweep — which D-009's grid excluded by construction.

**7.4 — Do not re-run the D-009 grid.** 45 points returned +0.109 pp. The parameter space as
scoped is exhausted. Any future sweep should include the candidate caps and be scored against
the replay instrument, not the archived `ALL.TXT`.

### 7.5 — A citation correction that should propagate now

**`41.508%` must not be cited as "our recall" going forward.** D-009's recall reference is
`20260803_live_run_1713/wsjt-x/ALL.TXT`, restricted to low-SNR decodes — the exact log this
week's replay found suppressed ~2.3× on the busy window, and low-SNR decodes are precisely the
population a suppressed log loses first. The figure is very likely optimistic, by an unknown
factor. This does **not** change the D-009 parameter decision (+0.109 pp is far too small for
reference bias to flip), but the number should not travel.

**Also for the Captain, on the D-009 decision itself** (QA raised it, §2.1 of their results
note): `k10_*_n40` ties baseline recall exactly and posts **zero false positives on both
synthetic arms** — it strictly dominates the shipped baseline for one changed parameter. It is
not the nominee only because I wrote the rule with a strict `>` on recall. That is a different
proposition from +0.109 pp and it should be in front of you explicitly, since my rule structure
is what obscured it.

---

## 8. What this does not establish

- **Not a corpus-wide claim.** One window, the busiest in the corpus. §3's density result holds
  over 30–49 decodes/cycle and is silent outside it.
- **Does not resolve M3.** Whether the archived reference is suppressed corpus-wide is still
  open. §2–§5 do not depend on it.
- **Does not touch Arm R.D**, which remains unauthorised. Note however that §3 delivers a
  density asymmetry result, reference-free, from data already on disk — which is close to what
  R.D was specced to obtain. Whether R.D is still worth running is a question I owe the Captain
  once M3 reports.
- **No D-001 figure is re-derived**, and I still have not opened
  `project-state-2026-07-31-d001-competition-confirmed.md`. §3 is a fresh measurement, not a
  restatement of the density penalty recorded there, and the two should not be conflated until
  someone reconciles them.
- **Nothing was changed in `src/`.** §6 is a read.

---

*Per HK-015 Architect → QA; task breakdown remains QA's. Per HK-014 committed locally, not
pushed, no merge implied. Per HK-011 nothing here modifies `src/`; §7.1 and §7.2 are proposals
requiring a Developer session and the Captain's authorisation. Per NFR-021 message text was used
only to build match keys — never printed, never written to any committed file; every figure here
is a count or a statistic.*
