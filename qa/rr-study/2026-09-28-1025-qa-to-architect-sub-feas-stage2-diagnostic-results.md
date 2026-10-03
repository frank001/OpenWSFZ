# SUB-FEAS Stage 2: labelled diagnostic result — WIN. Does not retro-promote Stage 1's FAIL

**QA, 2026-09-28 10:25Z** (`date -u`, HK-017). Branch `qa/sub-feas`. **Captain, 2026-09-28: "proceed
with stage 2."** Authorised as a labelled diagnostic per the Architect's Stage 1 ruling
(`qa/rr-study/2026-09-28-0040-architect-sub-feas-stage1-ruling.md`, §4-5) — Stage 1 read FAIL and
**this result does not overturn or retroactively change that reading**. Spec §8, bars unchanged, plus
the Architect's recommended extra `W=0.16s` descriptive leg. Harness: `qa/rr-study/sub-feas/stage2.py`
+ `run_stage2.py`. Full result: `qa/rr-study/sub-feas/stage2_result.json`, NFR-021/HK-037 scanned
clean (as is every file in this delivery).

## Method (spec §8, as executed)

For each of the **1,051 split-B cycles**: fit and subtract **every one of OWS's re-encodable decodes**
in that cycle (not just the isolated/SNR≥0 population `P` — the point is to clean the whole cycle),
at L2 (fitted position + drift, per Amendment 2) with the `W*`=0.32s envelope. Decode the residual
with the pinned DLL (nhard 40). Text-dedup within the cycle exactly as `Ft8Decoder.cs:338-354`
(`HashSet` on trimmed message text, first occurrence kept). A decode is **new** if its payload (bit-
level, RR73-equivalent — see note below) doesn't match anything in that cycle's *original* OWS list.
**Corroborated** = also present in WSJT-X's `ALL.TXT` for the same cycle (same payload-match +
`|Δf|≤10Hz` nearest-pairing convention as Amendment 1's twin detection). Parallelised (12 workers,
same infrastructure as Stage 1's `bigfit.py`). Run detached (HK-023): **13,028s (3.62h)**.

**RR73 asymmetry, caught before running** (same defect class as ROW 0f, not reused blindly): every
*reference* payload here (the cycle's own OWS list, WSJT-X's list) comes from re-encoding logged TEXT,
so it always carries our own `MAXGRID4+3` sentinel. A **new** decode's payload comes from the pinned
DLL's own LDPC decode of real RF — if it's genuinely an RR73 report, it may legitimately carry the
on-air sentinel (`32373`) instead. Using `comparator.payload_match` with `v_star=RR73_STD` (as
corpus.py's twin-detector correctly does, since there both sides are text-derived) would have been
wrong here and would have silently missed every genuine on-air RR73 "new" decode — fixed with the
correct `v_star` before the first run.

## Result

| leg | n new | n corroborated | uncorroborated (share) | ΔR (pp) | 95% CI | verdict |
|---|---:|---:|---|---:|---|---|
| **W\* = 0.32s (primary)** | 2,650 | **2,553** | 97 (3.66%) | **10.07** | [9.69, 10.44] | **WIN** |
| W = 0.16s (descriptive) | 2,231 | 2,146 | 85 (3.81%) | 8.47 | [8.12, 8.81] | WIN |

(`total_wsjtx` = 25,348 decodes across these 1,051 cycles, both legs' denominator.) `ci_lo`=9.69 clears
the WIN bar (`≥1.0`) by nearly **10×**. This is not a borderline read.

🛑 **Uncorroborated ≠ false positive** (DENSITY guard, restated per spec §8's own instruction): the
3.66% uncorroborated share is disclosed, not folded into the corroborated count, and is not itself
evidence of anything wrong — WSJT-X not seeing a signal doesn't mean it wasn't real.

## Due diligence before trusting this (HK-018 — a result this large gets checked, not just reported)

A `ΔR`≈10pp WIN is large, and sits in tension with the GAP-LOCATE record ("the strong-miss pool ...
is lost in extraction/decoding [17.06 of 19.27pp], not candidate search or the seam" —
`2026-09-27-1610-architect-gap-locate-final-ruling-s0-lb.md`). That prior finding tested decodability
**at the correct position in the original, unmodified audio** — it never removed a dominant co-channel
interferer first. Subtraction is a categorically different intervention (interference cancellation,
not better positioning), so the two findings are not in direct contradiction, but the coincidence in
magnitude was reason enough to check rather than accept at face value.

**Ghost-decode check** (`stage2_ghost_check.py`, 150-cycle random sample, same parallel harness):
for each new+corroborated decode, the frequency distance to the **nearest signal subtracted from that
same cycle**. If most "new" decodes were really just re-decoded ghosts of an imperfectly-subtracted
*known* signal (a same-QSO exclusion miss), distances would cluster near zero. They don't:

| distance from nearest subtracted signal | share of new+corroborated decodes |
|---|---:|
| ≤5 Hz | 15.2% |
| ≤10 Hz | 25.6% |
| ≤40 Hz | 79.0% |
| ≤60 Hz | 93.1% |
| ≤200 Hz | 99.1% |

Median 25Hz, p75 37Hz. This is exactly the shape expected for **revealing a co-channel neighbour that
was masked by the signal just removed** — clustered near, not on top of, the subtracted signal's own
frequency (FT8 tone spacing is 6.25Hz; two *distinct* real transmissions 10-60Hz apart on a busy band
is an entirely ordinary co-channel collision, the exact scenario this arm targets). It is not the
near-zero clustering a "same signal miscounted as new" bug would produce. This does not *prove* every
one of the 2,553 corroborated finds is a clean, independent discovery — a message-text audit would be
needed for that, and is out of scope here (HK-037) — but it rules out the most obvious mechanism by
which this number could be a large, systematic artifact.

## Caveat (spec §8, stated as required)

A DLL replay is not the live path. `ALL.TXT` is post-`IsPlausibleMessage` plus text-dedup
(`Ft8Decoder.cs:338-354`). This harness applies the same text-dedup; corroboration against WSJT-X
stands in for the plausibility filter, per spec.

## Architect control (added 2026-09-28, ruling `dc9fceed`)

The Architect ran a control this report didn't have: the ghost-check above had no **null** (with
~24 signals subtracted per cycle, almost any decode sits near *some* one of them by pure density),
and `ΔR`'s "new" test compared against **live** `ALL.TXT`, not a same-instrument replay — GAP-LOCATE's
own ROW 0e record shows a DLL replay can decode more than the live path did, so replay-vs-live gain
would have been silently credited to subtraction.

Read-only, using this harness's own `stage2` functions: 150 split-B cycles (seed 20260928), each
decoded **twice** — **ORIG** (the original PCM, no subtraction at all) and **SUB** (the W\*=0.32
residual, as above) — same new/corroboration rules both times:

| leg | new | corroborated | ΔR (pp of 3,668 WSJT-X) | median dist. to nearest subtracted signal | ≤5Hz |
|---|---:|---:|---:|---|---|
| **ORIG** (no subtraction) | 43 | 28 | **0.76** | 76.5 Hz | 0.0% |
| **SUB** (W\*=0.32) | 367 | 354 | **9.65** | 25.0 Hz | 13.0% |
| **NET (SUB − ORIG), paired per cycle** | | | **+8.89pp, 95% CI [8.01, 9.75]** | | |

The replay reproduces the live path closely (16.0 DLL decodes/cycle vs 15.8 live) — replay-vs-live
accounts for only 0.76pp, not the headline gain. **ORIG's own new decodes are the ghost-check's
missing null**: they sit nowhere near a subtracted signal (median 76.5Hz, 0% within 5Hz) — a flat
background rate from replay noise, not from proximity to anything just removed — while SUB's cluster
at 25Hz, confirming the earlier ghost-check's read was not just database density. The sample's SUB
reading (9.65pp) agrees with this report's full-run number (10.07pp [9.69,10.44]).

**Net result after the control: on this corpus, one subtraction pass recovers ≈8.9pp net of
WSJT-X-corroborated decodes beyond replay-vs-live gain — roughly a quarter of the OWS-vs-WSJT-X gap
in these cycles (2,370 OWS decodes vs 3,668 WSJT-X, in the 150-cycle sample).** Full ruling, including
the Architect's stated limits (one corpus, offline replay only — production runtime for the per-signal
fit is unmeasured, one pass only, FP exposure unmeasured beyond the uncorroborated share) and the
recommendation on lifting the build prohibition for one scoped, flag-gated arm:
`qa/rr-study/2026-09-28-1100-architect-sub-feas-stage2-diagnostic-ruling.md`. **The subtract-and-
resynthesise build prohibition stands unchanged; lifting it for that one scoped arm is now the
Captain's decision**, not licensed by this report or that ruling on their own.

## Standing

- **Stage 1 = FAIL still stands, unrevised.** This diagnostic's WIN does not retro-promote it —
  per the Architect's ruling, that would require closing/re-opening the gate itself, which nobody has
  done.
- HK-019 orphan check after both the full run and the ghost-check sample: clean, zero Python
  processes remaining.
- Nothing pushed (HK-033). Holding `qa/sub-feas` for the Captain's/Architect's disposition.
